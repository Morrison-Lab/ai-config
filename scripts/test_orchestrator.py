#!/usr/bin/env python3
"""Comprehensive unit and integration test suite for the Persistent Orchestrator."""

import os
import sys
import tempfile
import time
import unittest

# Ensure orchestrator package is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator.engine import OrchestratorEngine
from orchestrator.models import (
    SubagentContext,
    SubagentResult,
    Task,
    TaskPriority,
    TaskStatus,
)
from orchestrator.state_store import StateStore
from orchestrator.subagents import (
    CoderSubagent,
    CoordinatorSubagent,
    ResearcherSubagent,
    ReviewerSubagent,
    SubagentRegistry,
    TesterSubagent,
)
from orchestrator.task_queue import CycleDetectedError, TaskQueue


class TestStateStore(unittest.TestCase):
    """Test SQLite state store persistence, ACID transactions, and atomic operations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_state.db")
        self.store = StateStore(self.db_path)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_create_and_get_task(self):
        task = Task(title="Test Task", role="coder", priority=TaskPriority.HIGH.value, payload={"foo": "bar"})
        saved = self.store.create_task(task)
        self.assertEqual(saved.status, TaskStatus.READY)

        fetched = self.store.get_task(task.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, task.id)
        self.assertEqual(fetched.title, "Test Task")
        self.assertEqual(fetched.role, "coder")
        self.assertEqual(fetched.priority, TaskPriority.HIGH.value)
        self.assertEqual(fetched.payload, {"foo": "bar"})

    def test_atomic_claim_and_complete(self):
        task = Task(title="Claim Task", role="generic")
        self.store.create_task(task)

        # First claim succeeds
        claimed = self.store.claim_task(task.id, "worker-1")
        self.assertTrue(claimed)

        # Second claim fails because already RUNNING
        claimed_again = self.store.claim_task(task.id, "worker-2")
        self.assertFalse(claimed_again)

        # Complete task
        completed = self.store.complete_task(
            task.id,
            result={"output": "success"},
            artifacts={"report": {"metrics": 100}},
        )
        self.assertTrue(completed)

        t = self.store.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.COMPLETED)
        self.assertEqual(t.result, {"output": "success"})

        artifacts = self.store.get_artifacts(task.id)
        self.assertIn("report", artifacts)
        self.assertEqual(artifacts["report"]["metrics"], 100)

        events = self.store.get_events(task.id)
        event_types = [e.event_type for e in events]
        self.assertIn("TASK_CREATED", event_types)
        self.assertIn("TASK_CLAIMED", event_types)
        self.assertIn("TASK_COMPLETED", event_types)


class TestDAGAndTaskQueue(unittest.TestCase):
    """Test dynamic task queue, DAG dependency resolution, and cycle validation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_dag.db")
        self.store = StateStore(self.db_path)
        self.queue = TaskQueue(self.store)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_dag_linear_unblocking(self):
        # A -> B -> C
        task_a = Task(title="Step A", role="researcher")
        task_b = Task(title="Step B", role="coder", depends_on=[task_a.id])
        task_c = Task(title="Step C", role="tester", depends_on=[task_b.id])

        self.queue.enqueue_dag([task_a, task_b, task_c])

        self.assertEqual(self.store.get_task(task_a.id).status, TaskStatus.READY)
        self.assertEqual(self.store.get_task(task_b.id).status, TaskStatus.BLOCKED)
        self.assertEqual(self.store.get_task(task_c.id).status, TaskStatus.BLOCKED)

        # Complete A
        self.store.claim_task(task_a.id, "worker-1")
        self.store.complete_task(task_a.id, {"done": True})

        # Check ready queue
        ready = self.queue.dequeue_ready()
        ready_ids = [t.id for t in ready]
        self.assertIn(task_b.id, ready_ids)
        self.assertNotIn(task_c.id, ready_ids)

        # Complete B
        self.store.claim_task(task_b.id, "worker-1")
        self.store.complete_task(task_b.id, {"done": True})

        # Check ready queue again
        ready = self.queue.dequeue_ready()
        ready_ids = [t.id for t in ready]
        self.assertIn(task_c.id, ready_ids)

    def test_dag_cycle_detection(self):
        task_1 = Task(id="1", title="Task 1", depends_on=["2"])
        task_2 = Task(id="2", title="Task 2", depends_on=["1"])

        with self.assertRaises(CycleDetectedError):
            self.queue.enqueue_dag([task_1, task_2])

    def test_dag_duplicate_dependencies_valid(self):
        task_a = Task(id="a", title="Task A")
        # Task B redundantly lists task A twice in its dependencies
        task_b = Task(id="b", title="Task B", depends_on=["a", "a"])

        self.queue.enqueue_dag([task_a, task_b])
        self.assertEqual(self.store.get_task("a").status, TaskStatus.READY)
        self.assertEqual(self.store.get_task("b").status, TaskStatus.BLOCKED)

    def test_dynamic_child_task_spawning(self):
        parent = Task(title="Parent Workflow", role="coordinator")
        self.queue.enqueue(parent)

        child1 = Task(title="Child 1", role="researcher")
        child2 = Task(title="Child 2", role="coder", depends_on=[child1.id])

        self.queue.enqueue_child_tasks(parent.id, [child1, child2])

        c1 = self.store.get_task(child1.id)
        c2 = self.store.get_task(child2.id)

        self.assertEqual(c1.parent_task_id, parent.id)
        self.assertEqual(c2.parent_task_id, parent.id)
        self.assertEqual(c1.status, TaskStatus.READY)
        self.assertEqual(c2.status, TaskStatus.BLOCKED)


class TestCrashRecoveryAndRetries(unittest.TestCase):
    """Test lease expiration, crash recovery, and retry backoff."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_recovery.db")
        self.store = StateStore(self.db_path)
        self.queue = TaskQueue(self.store)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_stale_task_reclaim(self):
        task = Task(title="Orphan Task", role="coder", max_retries=2)
        self.store.create_task(task)
        self.store.claim_task(task.id, "dead-worker")

        # Artificially set heartbeat to 100 seconds ago
        with self.store.transaction() as cur:
            cur.execute("UPDATE tasks SET heartbeat_at = ? WHERE id = ?", (time.time() - 100.0, task.id))

        reclaimed = self.store.reclaim_stale_tasks(stale_threshold_seconds=10.0)
        self.assertEqual(reclaimed, 1)

        t = self.store.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.READY)
        self.assertEqual(t.retry_count, 1)

    def test_max_retries_failure(self):
        task = Task(title="Failing Task", role="coder", max_retries=1)
        self.store.create_task(task)
        self.store.claim_task(task.id, "worker-1")

        # Fail once (retry)
        self.store.fail_task(task.id, error="Error 1", can_retry=True)
        t = self.store.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.READY)
        self.assertEqual(t.retry_count, 1)

        # Fail again (max reached)
        self.store.claim_task(task.id, "worker-1")
        self.store.fail_task(task.id, error="Error 2", can_retry=True)
        t = self.store.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.FAILED)


class TestSpecializedSubagents(unittest.TestCase):
    """Test specialized subagents behaviors and outputs."""

    def setUp(self):
        self.registry = SubagentRegistry()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = StateStore(os.path.join(self.temp_dir.name, "test_subagent.db"))

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_researcher_subagent(self):
        agent = self.registry.get_for_role("researcher")
        task = Task(title="Research query", role="researcher", payload={"query": "Find AST parsers"})
        ctx = SubagentContext(task=task, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        res = agent.execute(task, ctx)
        self.assertTrue(res.success)
        self.assertIn("Find AST parsers", res.data["query"])

    def test_reviewer_adversarial_check(self):
        agent = self.registry.get_for_role("reviewer")

        # Clean code
        task_clean = Task(title="Review clean diff", role="reviewer", payload={"diff": "+ def foo(): return 42"})
        ctx = SubagentContext(task=task_clean, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        res_clean = agent.execute(task_clean, ctx)
        self.assertTrue(res_clean.success)
        self.assertEqual(res_clean.data["verdict"], "CLEAN")

        # Unsafe code
        task_unsafe = Task(title="Review unsafe diff", role="reviewer", payload={"diff": "+ eval(user_input)"})
        res_unsafe = agent.execute(task_unsafe, ctx)
        self.assertFalse(res_unsafe.success)
        self.assertEqual(res_unsafe.data["verdict"], "BLOCKED")

    def test_coordinator_dynamic_decomposition(self):
        agent = self.registry.get_for_role("coordinator")
        task = Task(
            title="Implement Authentication",
            role="coordinator",
            payload={"goal": "Auth System", "stages": ["research", "code", "review", "test"]},
        )
        ctx = SubagentContext(task=task, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        res = agent.execute(task, ctx)
        self.assertTrue(res.success)
        self.assertEqual(len(res.spawned_tasks), 4)
        roles = [t.role for t in res.spawned_tasks]
        self.assertEqual(roles, ["research", "code", "review", "test"])


class TestOrchestratorEngineIntegration(unittest.TestCase):
    """End-to-end integration test of the multi-threaded orchestration engine."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_engine.db")
        self.engine = OrchestratorEngine(
            db_path=self.db_path,
            max_concurrency=3,
            poll_interval_seconds=0.05,
            stale_threshold_seconds=5.0,
        )

    def tearDown(self):
        self.engine.stop()
        self.temp_dir.cleanup()

    def test_end_to_end_orchestration_loop(self):
        # 1. Enqueue coordinator task that will decompose into 3 stages
        coord_task = Task(
            title="Coordinate Feature X",
            role="coordinator",
            payload={"goal": "Feature X", "stages": ["researcher", "coder", "tester"]},
        )
        self.engine.queue.enqueue(coord_task)

        # 2. Start engine in background
        self.engine.start(run_in_background=True)

        # 3. Wait for all tasks to complete
        start = time.time()
        completed = False
        while time.time() - start < 10.0:
            stats = self.engine.queue.get_stats()
            # 1 coordinator + 3 spawned tasks = 4 total completed
            if stats["total_tasks"] == 4 and stats["completed_tasks"] == 4:
                completed = True
                break
            time.sleep(0.1)

        self.assertTrue(completed, f"Orchestration loop did not finish in time. Stats: {self.engine.queue.get_stats()}")


from orchestrator.backlog_sweeper import BacklogSweeper
from orchestrator.model_adapters import (
    ModelProvider,
    ModelRouter,
    TaskTier,
)


class TestModelRouterAndSweeper(unittest.TestCase):
    """Test model routing and backlog sweeper DAG generation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = StateStore(os.path.join(self.temp_dir.name, "test_sweeper.db"))
        self.sweeper = BacklogSweeper(self.store)
        self.router = ModelRouter()

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_model_router_confidential_routes_local_ollama(self):
        adapter, model = self.router.route_task(tier=TaskTier.LOCAL_FAST, is_confidential=True)
        # Should route to Ollama or Mock (both local, zero external leak)
        self.assertIn(adapter.provider, (ModelProvider.OLLAMA, ModelProvider.MOCK))

    def test_model_router_adversarial_review_routes_cross_model(self):
        # When author is Claude, reviewer must not be Claude
        adapter, model = self.router.route_task(
            tier=TaskTier.ADVERSARIAL_REVIEW,
            prior_author_model="claude-3-7-sonnet",
        )
        self.assertNotEqual(adapter.provider, ModelProvider.CLAUDE)

        # When author is Opencode, reviewer must not be Opencode
        adapter2, model2 = self.router.route_task(
            tier=TaskTier.ADVERSARIAL_REVIEW,
            prior_author_model="opencode/deepseek-v4-flash-free",
        )
        self.assertNotEqual(adapter2.provider, ModelProvider.OPENCODE)

        # When author is Cursor, reviewer must not be Cursor
        adapter3, model3 = self.router.route_task(
            tier=TaskTier.ADVERSARIAL_REVIEW,
            prior_author_model="cursor-agent",
        )
        self.assertNotEqual(adapter3.provider, ModelProvider.CURSOR)

        # When author is Codex, reviewer must not be Codex
        adapter4, model4 = self.router.route_task(
            tier=TaskTier.ADVERSARIAL_REVIEW,
            prior_author_model="codex-cli",
        )
        self.assertNotEqual(adapter4.provider, ModelProvider.CODEX)

    def test_backlog_sweeper_ingest_issue_creates_dag(self):
        fake_issue = {
            "number": 9999,
            "title": "Fix memory leak in background worker",
            "body": "Detailed description of memory issue.",
        }
        dag = self.sweeper.ingest_issue(fake_issue)
        self.assertEqual(len(dag), 4)

        roles = [t.role for t in dag]
        self.assertEqual(roles, ["researcher", "coder", "reviewer", "tester"])

        # Check dependencies: coder depends on researcher, reviewer on coder, tester on reviewer
        self.assertEqual(dag[1].depends_on, [dag[0].id])
        self.assertEqual(dag[2].depends_on, [dag[1].id])
        self.assertEqual(dag[3].depends_on, [dag[2].id])

    def test_retry_task_status_guard(self):
        task = Task(title="Failed Task", role="coder")
        self.store.create_task(task)
        self.store.claim_task(task.id, "worker-1")
        self.store.complete_task(task.id, {"status": "ok"})

        # Cannot retry a COMPLETED task
        retried = self.store.retry_task(task.id)
        self.assertFalse(retried)

        # Now test on a FAILED task
        task2 = Task(title="Failed Task 2", role="coder", max_retries=0)
        self.store.create_task(task2)
        self.store.claim_task(task2.id, "worker-1")
        self.store.fail_task(task2.id, "fatal error", can_retry=False)

        self.assertEqual(self.store.get_task(task2.id).status, TaskStatus.FAILED)
        retried2 = self.store.retry_task(task2.id, reason="Manual user retry")
        self.assertTrue(retried2)
        self.assertEqual(self.store.get_task(task2.id).status, TaskStatus.READY)

    def test_fail_task_status_guard_cannot_clobber_completed(self):
        task = Task(title="Guarded Task", role="coder")
        self.store.create_task(task)
        self.store.claim_task(task.id, "worker-1")
        self.store.complete_task(task.id, {"status": "ok"})

        # Late worker attempt to fail should be refused and return False
        failed = self.store.fail_task(task.id, error="Late error", can_retry=True, worker_id="worker-1")
        self.assertFalse(failed)

        # Task remains COMPLETED
        t = self.store.get_task(task.id)
        self.assertEqual(t.status, TaskStatus.COMPLETED)

    def test_find_tasks_by_payload_field_validation(self):
        task = Task(title="Issue Task", payload={"issue_number": 42})
        self.store.create_task(task)

        found = self.store.find_tasks_by_payload_field("issue_number", 42)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, task.id)

        # Invalid field name with SQL injection characters must raise ValueError
        with self.assertRaises(ValueError):
            self.store.find_tasks_by_payload_field("x') OR 1=1 --", 42)

    def test_codex_and_cursor_adapters_registered(self):
        self.assertIn(ModelProvider.CODEX, self.router.adapters)
        self.assertIn(ModelProvider.CURSOR, self.router.adapters)
        self.assertEqual(self.router.get_adapter(ModelProvider.CODEX).provider, ModelProvider.CODEX)
        self.assertEqual(self.router.get_adapter(ModelProvider.CURSOR).provider, ModelProvider.CURSOR)

    def test_reclaim_stale_tasks_status_guard_respects_cancelled(self):
        task = Task(title="Stale Task", role="coder")
        self.store.create_task(task)
        self.store.claim_task(task.id, "worker-1")

        # Simulate heartbeat expiring in past
        with self.store.transaction() as cur:
            cur.execute("UPDATE tasks SET heartbeat_at = 1.0 WHERE id = ?", (task.id,))

        # Cancel the task
        self.store.cancel_task(task.id, reason="User cancelled")
        self.assertEqual(self.store.get_task(task.id).status, TaskStatus.CANCELLED)

        # reclaim_stale_tasks must NOT reclaim a CANCELLED task
        reclaimed = self.store.reclaim_stale_tasks(stale_threshold_seconds=1.0)
        self.assertEqual(reclaimed, 0)
        self.assertEqual(self.store.get_task(task.id).status, TaskStatus.CANCELLED)

    def test_resolve_blocked_tasks_status_guard_respects_cancelled(self):
        t1 = Task(title="Parent", role="coder")
        t2 = Task(title="Child", role="tester", depends_on=[t1.id])
        self.store.create_task(t1)
        self.store.create_task(t2)

        self.assertEqual(self.store.get_task(t2.id).status, TaskStatus.BLOCKED)

        # Cancel child before parent completes
        self.store.cancel_task(t2.id, reason="No longer needed")
        self.assertEqual(self.store.get_task(t2.id).status, TaskStatus.CANCELLED)

        # Parent completes
        self.store.claim_task(t1.id, "worker-1")
        self.store.complete_task(t1.id, {"status": "ok"})

        # resolve_blocked_tasks must NOT unblock a CANCELLED child
        unblocked = self.store.resolve_blocked_tasks()
        self.assertEqual(unblocked, 0)
        self.assertEqual(self.store.get_task(t2.id).status, TaskStatus.CANCELLED)


class TestWorktreeIsolation(unittest.TestCase):
    """Test suite for worktree lifecycle, subagent isolation, and cleanup."""

    def test_worktree_manager_lifecycle_and_branch_cleanup(self):
        from orchestrator.worktree_manager import WorktreeManager
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            wt_mgr = WorktreeManager(repo_root=Path.cwd(), worktree_parent=tmppath)

            task_id = "test-wt-456"
            target_branch = "task/test-wt-456"

            with wt_mgr.isolated_worktree(task_id, cleanup=True, delete_branch=True) as wt_path:
                self.assertTrue(wt_path.exists())
                test_file = wt_path / "test_isolated.txt"
                test_file.write_text("isolated content", encoding="utf-8")
                self.assertTrue(test_file.exists())

            # Verify worktree directory is cleaned up
            self.assertFalse(wt_path.exists())

            # Verify branch was deleted and not leaked
            res = subprocess.run(["git", "branch", "--list", target_branch], capture_output=True, text=True, check=False)
            self.assertNotIn(target_branch, res.stdout)

    def test_coder_subagent_with_worktree_isolation(self):
        from orchestrator.subagents import CoderSubagent
        from orchestrator.models import SubagentContext
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            from orchestrator.worktree_manager import WorktreeManager
            wt_mgr = WorktreeManager(repo_root=Path.cwd(), worktree_parent=Path(tmpdir))
            coder = CoderSubagent(worktree_manager=wt_mgr)

            task = Task(
                title="Isolated code task",
                role="coder",
                payload={
                    "instruction": "Add helper function",
                    "target_file": "isolated_test_file.py",
                    "code_content": "def helper(): return 42\n",
                    "use_worktree": True,
                    "branch_name": "task/isolated-code-test",
                    "persist_branch": False,
                },
            )
            ctx = SubagentContext(task=task, state_store=None, worker_id="worker-test", workspace_root=str(Path.cwd()))
            result = coder.execute(task, ctx)

            self.assertTrue(result.success)
            self.assertTrue(result.data.get("committed", False))

            # Verify branch was cleaned up as requested
            res = subprocess.run(["git", "branch", "--list", "task/isolated-code-test"], capture_output=True, text=True, check=False)
            self.assertNotIn("task/isolated-code-test", res.stdout)

    def test_coder_subagent_worktree_commit_failure_fails_fast(self):
        from orchestrator.subagents import CoderSubagent
        from orchestrator.models import SubagentContext
        from unittest.mock import patch
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            from orchestrator.worktree_manager import WorktreeManager
            wt_mgr = WorktreeManager(repo_root=Path.cwd(), worktree_parent=Path(tmpdir))
            coder = CoderSubagent(worktree_manager=wt_mgr)

            task = Task(
                title="Failing commit task",
                role="coder",
                payload={
                    "instruction": "Add faulty code",
                    "target_file": "faulty.py",
                    "code_content": "def bad(): pass\n",
                    "use_worktree": True,
                    "branch_name": "task/failing-commit-test",
                    "persist_branch": False,
                },
            )
            ctx = SubagentContext(task=task, state_store=None, worker_id="worker-test", workspace_root=str(Path.cwd()))

            orig_run = subprocess.run
            def mock_subprocess_run(cmd, *args, **kwargs):
                if isinstance(cmd, list) and len(cmd) > 1 and cmd[0] == "git" and cmd[1] == "commit":
                    return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="fatal: mock commit failure")
                return orig_run(cmd, *args, **kwargs)

            with patch("subprocess.run", side_effect=mock_subprocess_run):
                result = coder.execute(task, ctx)
                self.assertFalse(result.success)
                self.assertIn("Git commit failed in worktree", result.error)


def main():
    unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
