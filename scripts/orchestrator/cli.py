"""Command-line interface for managing and executing the persistent orchestrator."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List

from .backlog_sweeper import BacklogSweeper
from .engine import OrchestratorEngine
from .model_adapters import ModelProvider, ModelRouter
from .models import Task, TaskPriority, TaskStatus
from .state_store import StateStore
from .task_queue import TaskQueue


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_start(args: argparse.Namespace) -> None:
    setup_logging(args.verbose)
    engine = OrchestratorEngine(
        db_path=args.db,
        max_concurrency=args.concurrency,
        poll_interval_seconds=args.poll_interval,
        stale_threshold_seconds=args.stale_threshold,
    )
    print(f"Starting Persistent Orchestrator on {args.db} (concurrency={args.concurrency})...")
    try:
        engine.start(run_in_background=False)
    except KeyboardInterrupt:
        print("\nShutdown requested by user.")
    finally:
        engine.stop()


def cmd_submit(args: argparse.Namespace) -> None:
    store = StateStore(args.db)
    queue = TaskQueue(store)

    payload: Dict[str, Any] = {}
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            print(f"Error parsing payload JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    depends_on: List[str] = []
    if args.depends_on:
        depends_on = [d.strip() for d in args.depends_on.split(",") if d.strip()]

    # Priority mapping
    priority = TaskPriority.NORMAL.value
    if args.priority:
        if args.priority.upper() in TaskPriority.__members__:
            priority = TaskPriority[args.priority.upper()].value
        else:
            try:
                priority = int(args.priority)
            except ValueError:
                pass

    task = Task(
        title=args.title,
        role=args.role,
        priority=priority,
        payload=payload,
        depends_on=depends_on,
        timeout_seconds=args.timeout,
    )

    created = queue.enqueue(task)
    print(f"Enqueued Task:")
    print(f"  ID:         {created.id}")
    print(f"  Title:      {created.title}")
    print(f"  Role:       {created.role}")
    print(f"  Priority:   {created.priority}")
    print(f"  Status:     {created.status.value}")
    if created.depends_on:
        print(f"  Depends On: {', '.join(created.depends_on)}")


def cmd_status(args: argparse.Namespace) -> None:
    store = StateStore(args.db)
    queue = TaskQueue(store)
    stats = queue.get_stats()

    if args.json:
        print(json.dumps(stats, indent=2))
        return

    print("=" * 50)
    print("       PERSISTENT ORCHESTRATOR QUEUE STATUS       ")
    print("=" * 50)
    print(f"Database:        {args.db}")
    print(f"Total Tasks:     {stats['total_tasks']}")
    print(f"Ready:           {stats['ready_tasks']}")
    print(f"Running:         {stats['active_tasks']}")
    print(f"Blocked:         {stats['blocked_tasks']}")
    print(f"Completed:       {stats['completed_tasks']}")
    print(f"Failed:          {stats['failed_tasks']}")
    print("-" * 50)
    print("Tasks by Role:")
    for role, cnt in stats["role_counts"].items():
        print(f"  - {role:<15}: {cnt}")
    print("=" * 50)


def cmd_list(args: argparse.Namespace) -> None:
    store = StateStore(args.db)
    status_enum = TaskStatus(args.status.upper()) if args.status else None
    tasks = store.list_tasks(status=status_enum, role=args.role, limit=args.limit)

    if not tasks:
        print("No tasks found matching criteria.")
        return

    print(f"{'ID':<38} {'STATUS':<11} {'PRIORITY':<8} {'ROLE':<12} {'TITLE'}")
    print("-" * 90)
    for t in tasks:
        stat = t.status.value if isinstance(t.status, TaskStatus) else str(t.status)
        print(f"{t.id:<38} {stat:<11} {t.priority:<8} {t.role:<12} {t.title[:25]}")


def cmd_inspect(args: argparse.Namespace) -> None:
    store = StateStore(args.db)
    task = store.get_task(args.task_id)
    if not task:
        print(f"Task '{args.task_id}' not found.", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print(f"TASK INSPECTION: {task.id}")
    print("=" * 60)
    print(f"Title:         {task.title}")
    print(f"Role:          {task.role}")
    print(f"Status:        {task.status.value}")
    print(f"Priority:      {task.priority}")
    print(f"Worker:        {task.assigned_worker_id or 'Unassigned'}")
    print(f"Retry Count:   {task.retry_count}/{task.max_retries}")
    print(f"Created At:    {time.ctime(task.created_at)}")
    if task.started_at:
        print(f"Started At:    {time.ctime(task.started_at)}")
    if task.completed_at:
        print(f"Completed At:  {time.ctime(task.completed_at)}")
    if task.depends_on:
        print(f"Depends On:    {', '.join(task.depends_on)}")
    if task.error:
        print(f"Error:         {task.error}")

    print("\nPayload:")
    print(json.dumps(task.payload, indent=2))

    if task.result is not None:
        print("\nResult:")
        print(json.dumps(task.result, indent=2))

    artifacts = store.get_artifacts(task.id)
    if artifacts:
        print("\nArtifacts:")
        print(json.dumps(artifacts, indent=2))

    if args.events:
        events = store.get_events(task.id)
        print(f"\nAudit Events ({len(events)}):")
        for ev in events:
            print(f"  [{time.ctime(ev.timestamp)}] {ev.event_type}: {json.dumps(ev.details)}")
    print("=" * 60)


def cmd_retry(args: argparse.Namespace) -> None:
    store = StateStore(args.db)
    task = store.get_task(args.task_id)
    if not task:
        print(f"Task '{args.task_id}' not found.", file=sys.stderr)
        sys.exit(1)

    if task.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
        print(f"Cannot retry task '{task.id}': current status is {task.status.value}. Only FAILED or CANCELLED tasks can be retried.", file=sys.stderr)
        sys.exit(1)

    # Force status transition back to READY with incremented retry count
    with store.transaction() as cur:
        now = time.time()
        import uuid
        cur.execute(
            """
            UPDATE tasks
            SET status = 'READY',
                error = 'Manual retry requested via CLI',
                retry_count = retry_count + 1,
                assigned_worker_id = NULL,
                heartbeat_at = NULL,
                completed_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now, task.id),
        )
        event_id = f"{task.id}-retry-{uuid.uuid4().hex}"
        cur.execute(
            """
            INSERT INTO task_events (id, task_id, event_type, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, task.id, "TASK_RETRY", json.dumps({"reason": "Manual retry requested via CLI"}), now),
        )
    print(f"Task '{task.id}' reset to READY for retry.")


def cmd_cancel(args: argparse.Namespace) -> None:
    store = StateStore(args.db)
    cancelled = store.cancel_task(args.task_id, reason=args.reason or "Cancelled via CLI")
    if cancelled:
        print(f"Task '{args.task_id}' marked CANCELLED.")
    else:
        print(f"Task '{args.task_id}' could not be cancelled (may be already completed/failed).")


def cmd_ingest_issues(args: argparse.Namespace) -> None:
    store = StateStore(args.db)
    sweeper = BacklogSweeper(store, repo=args.repo)
    print(f"Querying GitHub issues (limit={args.limit})...")
    count = sweeper.ingest_backlog(limit=args.limit)
    print(f"Successfully ingested {count} issues into the orchestration queue.")


def cmd_sweep_backlog(args: argparse.Namespace) -> None:
    setup_logging(args.verbose)
    store = StateStore(args.db)
    sweeper = BacklogSweeper(store, repo=args.repo)
    print(f"Sweeping GitHub backlog (limit={args.limit})...")
    ingested = sweeper.ingest_backlog(limit=args.limit)
    print(f"Ingested {ingested} issues. Starting multi-model orchestration engine (concurrency={args.concurrency})...")

    engine = OrchestratorEngine(
        db_path=args.db,
        max_concurrency=args.concurrency,
        poll_interval_seconds=args.poll_interval,
        stale_threshold_seconds=args.stale_threshold,
    )
    try:
        engine.start(run_in_background=False)
    except KeyboardInterrupt:
        print("\nSweep interrupted by user.")
    finally:
        engine.stop()


def cmd_list_models(args: argparse.Namespace) -> None:
    router = ModelRouter()
    print("=" * 60)
    print("          MULTI-MODEL PROVIDER AVAILABILITY           ")
    print("=" * 60)
    for provider, adapter in router.adapters.items():
        if provider == ModelProvider.MOCK:
            continue
        available = adapter.is_available()
        status_str = "READY / AVAILABLE" if available else "NOT DETECTED / OFFLINE"
        print(f"  - {provider.value.upper():<15}: {status_str}")
    print("=" * 60)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrate",
        description="Persistent Orchestration Loop CLI backed by SQLite and specialized subagents.",
    )
    parser.add_argument("--db", default="orchestrator_state.db", help="Path to state SQLite database")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # start
    p_start = subparsers.add_parser("start", help="Start the persistent orchestration loop daemon")
    p_start.add_argument("-c", "--concurrency", type=int, default=4, help="Worker concurrency limit")
    p_start.add_argument("-p", "--poll-interval", type=float, default=0.5, help="Poll interval seconds")
    p_start.add_argument("-s", "--stale-threshold", type=float, default=60.0, help="Heartbeat stale threshold seconds")
    p_start.set_defaults(func=cmd_start)

    # ingest-issues
    p_ingest = subparsers.add_parser("ingest-issues", help="Ingest open GitHub issues into orchestration queue")
    p_ingest.add_argument("--limit", type=int, default=10, help="Number of issues to ingest")
    p_ingest.add_argument("--repo", help="Target GitHub repository (owner/repo)")
    p_ingest.set_defaults(func=cmd_ingest_issues)

    # sweep-backlog
    p_sweep = subparsers.add_parser("sweep-backlog", help="Ingest open issues and execute orchestration loop")
    p_sweep.add_argument("-c", "--concurrency", type=int, default=3, help="Worker concurrency limit")
    p_sweep.add_argument("--limit", type=int, default=5, help="Number of issues to sweep")
    p_sweep.add_argument("--repo", help="Target GitHub repository (owner/repo)")
    p_sweep.add_argument("-p", "--poll-interval", type=float, default=0.5, help="Poll interval seconds")
    p_sweep.add_argument("-s", "--stale-threshold", type=float, default=60.0, help="Heartbeat stale threshold seconds")
    p_sweep.set_defaults(func=cmd_sweep_backlog)

    # list-models
    p_models = subparsers.add_parser("list-models", help="Inspect status of all configured AI models & providers")
    p_models.set_defaults(func=cmd_list_models)

    # submit
    p_submit = subparsers.add_parser("submit", help="Enqueue a new task into the dynamic queue")
    p_submit.add_argument("--title", required=True, help="Task title")
    p_submit.add_argument("--role", default="generic", help="Specialized subagent role (researcher, coder, reviewer, tester, coordinator, generic)")
    p_submit.add_argument("--priority", default="NORMAL", help="Priority (LOW, NORMAL, HIGH, CRITICAL, or integer)")
    p_submit.add_argument("--payload", default="{}", help="Task payload JSON string")
    p_submit.add_argument("--depends-on", default="", help="Comma-separated prerequisite task IDs")
    p_submit.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    p_submit.set_defaults(func=cmd_submit)

    # status
    p_status = subparsers.add_parser("status", help="Display overall queue and worker status")
    p_status.add_argument("--json", action="store_true", help="Output status in JSON format")
    p_status.set_defaults(func=cmd_status)

    # list
    p_list = subparsers.add_parser("list", help="List tasks in the queue")
    p_list.add_argument("--status", help="Filter by status (PENDING, READY, RUNNING, COMPLETED, FAILED, CANCELLED, BLOCKED)")
    p_list.add_argument("--role", help="Filter by subagent role")
    p_list.add_argument("--limit", type=int, default=50, help="Max tasks to list")
    p_list.set_defaults(func=cmd_list)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect detailed information for a task")
    p_inspect.add_argument("task_id", help="Task UUID")
    p_inspect.add_argument("--events", action="store_true", help="Include full audit event history")
    p_inspect.set_defaults(func=cmd_inspect)

    # retry
    p_retry = subparsers.add_parser("retry", help="Retry a failed task")
    p_retry.add_argument("task_id", help="Task UUID")
    p_retry.set_defaults(func=cmd_retry)

    # cancel
    p_cancel = subparsers.add_parser("cancel", help="Cancel a pending or running task")
    p_cancel.add_argument("task_id", help="Task UUID")
    p_cancel.add_argument("--reason", default="", help="Cancellation reason")
    p_cancel.set_defaults(func=cmd_cancel)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
