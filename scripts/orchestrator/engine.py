"""The persistent orchestration loop engine."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import logging
import os
import signal
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from .models import SubagentContext, SubagentResult, Task, TaskPriority, TaskStatus
from .state_store import StateStore
from .subagents import BaseSubagent, SubagentRegistry
from .task_queue import TaskQueue

logger = logging.getLogger("orchestrator")


class OrchestratorEngine:
    """Persistent Orchestration Engine managing the continuous task loop, worker pool,

    crash recovery, and dynamic subagent dispatch.
    """

    def __init__(
        self,
        db_path: str = "orchestrator_state.db",
        max_concurrency: int = 4,
        poll_interval_seconds: float = 0.5,
        stale_threshold_seconds: float = 300.0,
        workspace_root: Optional[str] = None,
        registry: Optional[SubagentRegistry] = None,
    ):
        self.db_path = db_path
        self.state_store = StateStore(db_path)
        self.queue = TaskQueue(self.state_store)
        self.registry = registry or SubagentRegistry()
        self.max_concurrency = max_concurrency
        self.poll_interval_seconds = poll_interval_seconds
        self.stale_threshold_seconds = stale_threshold_seconds
        self.workspace_root = workspace_root or os.getcwd()

        self._running = False
        self._shutdown_event = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_futures: Dict[Future[Any], str] = {}
        self._lock = threading.Lock()
        self._loop_count = 0

    def start(self, run_in_background: bool = False) -> None:
        """Start the persistent orchestration loop."""
        self._running = True
        self._shutdown_event.clear()
        self._executor = ThreadPoolExecutor(max_workers=self.max_concurrency, thread_name_prefix="subagent-worker")

        # Initial crash recovery: reclaim any orphaned tasks from a prior crashed run
        reclaimed = self.state_store.reclaim_stale_tasks(self.stale_threshold_seconds)
        if reclaimed > 0:
            logger.info("Crash recovery: Reclaimed %d stale tasks from previous session", reclaimed)

        # Unblock any pending dependencies
        self.state_store.resolve_blocked_tasks()

        if run_in_background:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="orchestration-loop")
            self._thread.start()
        else:
            self._setup_signals()
            self._loop()

    def _setup_signals(self) -> None:
        """Setup graceful termination handlers."""
        def handler(signum, frame):
            logger.info("Shutdown signal received (%s), stopping orchestration loop gracefully...", signum)
            self.stop()

        try:
            signal.signal(signal.SIGINT, handler)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, handler)
        except (ValueError, AttributeError):
            # Signal handling may not be supported in non-main threads
            pass

    def stop(self, timeout: float = 10.0) -> None:
        """Signal the orchestration loop to shut down and await active tasks."""
        self._running = False
        self._shutdown_event.set()
        if hasattr(self, "_thread") and self._thread is not None and threading.current_thread() != self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=False)
            self._executor = None
        self.state_store.close()
        logger.info("Orchestration loop stopped.")

    def step(self) -> int:
        """Perform a single iteration of the orchestration loop.

        Returns the number of new tasks dispatched.
        """
        self._loop_count += 1

        # 1. Clean up completed futures
        with self._lock:
            done_futures = [f for f in self._active_futures if f.done()]
            for f in done_futures:
                task_id = self._active_futures.pop(f)
                try:
                    f.result()
                except Exception as exc:
                    logger.error("Unhandled exception in task %s: %s", task_id, exc)

            current_active = len(self._active_futures)

        # 2. Reclaim stale/timed-out tasks periodically
        if self._loop_count % 20 == 0:
            self.state_store.reclaim_stale_tasks(self.stale_threshold_seconds)

        # 3. Resolve any newly unblocked dependencies
        self.state_store.resolve_blocked_tasks()

        # 4. Check available capacity
        available_slots = self.max_concurrency - current_active
        if available_slots <= 0:
            return 0

        # 5. Fetch ready tasks
        ready_tasks = self.queue.dequeue_ready(limit=available_slots)
        dispatched_count = 0

        for task in ready_tasks:
            worker_id = f"worker-{os.getpid()}-{threading.get_ident()}-{time.time()}"
            if self.state_store.claim_task(task.id, worker_id):
                task.assigned_worker_id = worker_id
                task.status = TaskStatus.RUNNING
                if self._executor:
                    fut = self._executor.submit(self._execute_task_wrapper, task, worker_id)
                    with self._lock:
                        self._active_futures[fut] = task.id
                    dispatched_count += 1

        return dispatched_count

    def _loop(self) -> None:
        """Continuous execution loop."""
        logger.info("Persistent orchestration loop started (concurrency=%d, db=%s)", self.max_concurrency, self.db_path)
        try:
            while self._running and not self._shutdown_event.is_set():
                self.step()
                time.sleep(self.poll_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            self.stop()

    def _execute_task_wrapper(self, task: Task, worker_id: str) -> None:
        """Thread worker wrapper that manages heartbeats, execution, child spawning, and persistence."""
        subagent = self.registry.get_for_role(task.role)
        context = SubagentContext(
            task=task,
            state_store=self.state_store,
            worker_id=worker_id,
            workspace_root=self.workspace_root,
        )

        stop_heartbeat = threading.Event()

        def heartbeat_worker():
            interval = max(1.0, self.stale_threshold_seconds / 4.0)
            while not stop_heartbeat.wait(interval):
                self.state_store.heartbeat_task(task.id, worker_id)

        hb_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        hb_thread.start()

        start_time = time.time()
        try:
            # Execute subagent logic
            result: SubagentResult = subagent.execute(task, context)
            stop_heartbeat.set()
            hb_thread.join(timeout=1.0)

            if result.success:
                # Handle dynamic child tasks spawned by subagent
                if result.spawned_tasks:
                    self.queue.enqueue_child_tasks(task.id, result.spawned_tasks)

                completed = self.state_store.complete_task(
                    task.id,
                    result=result.data,
                    artifacts=result.artifacts,
                )
                if completed:
                    logger.info("Task %s ('%s') completed successfully in %.2fs", task.id, task.title, time.time() - start_time)
                else:
                    logger.warning(
                        "Task %s ('%s') finished execution in %.2fs but complete_task was rejected (status was not RUNNING, may have been cancelled or reclaimed).",
                        task.id,
                        task.title,
                        time.time() - start_time,
                    )
            else:
                err_msg = result.error or "Subagent reported execution failure."
                self.state_store.fail_task(task.id, error=err_msg, can_retry=True, worker_id=worker_id)
                logger.warning("Task %s ('%s') failed: %s", task.id, task.title, err_msg)

        except Exception as exc:
            stop_heartbeat.set()
            err_msg = f"Exception during execution: {str(exc)}"
            logger.exception("Error executing task %s ('%s')", task.id, task.title)
            self.state_store.fail_task(task.id, error=err_msg, can_retry=True, worker_id=worker_id)

    def get_status(self) -> Dict[str, Any]:
        """Return live health and queue status of the orchestrator."""
        stats = self.queue.get_stats()
        with self._lock:
            active_workers = len(self._active_futures)

        return {
            "running": self._running,
            "max_concurrency": self.max_concurrency,
            "active_workers": active_workers,
            "available_slots": max(0, self.max_concurrency - active_workers),
            "db_path": self.db_path,
            "registered_roles": self.registry.list_roles(),
            "queue_stats": stats,
        }
