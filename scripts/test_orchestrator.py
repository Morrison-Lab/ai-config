#!/usr/bin/env python3
"""Comprehensive unit and integration test suite for the Persistent Orchestrator."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

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
        task = Task(title="Research query", role="researcher", payload={"query": "Find AST parsers", "dry_run": True})
        ctx = SubagentContext(task=task, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        res = agent.execute(task, ctx)
        self.assertTrue(res.success)
        self.assertIn("Find AST parsers", res.data["query"])

    def test_reviewer_adversarial_check(self):
        agent = self.registry.get_for_role("reviewer")

        # Clean code
        task_clean = Task(title="Review clean diff", role="reviewer", payload={"diff": "+ def foo(): return 42", "dry_run": True})
        ctx = SubagentContext(task=task_clean, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        res_clean = agent.execute(task_clean, ctx)
        self.assertTrue(res_clean.success)
        self.assertEqual(res_clean.data["verdict"], "CLEAN")

        # Unsafe code
        task_unsafe = Task(title="Review unsafe diff", role="reviewer", payload={"diff": "+ eval(user_input)", "dry_run": True})
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

    def test_extract_files_from_markdown_formats(self):
        from orchestrator.subagents import extract_files_from_markdown

        sample = (
            "Here is the solution:\n"
            "```scripts/foo.py\n"
            "print('foo')\n"
            "```\n\n"
            "```python scripts/bar.py\n"
            "print('bar')\n"
            "```\n\n"
            "```main.py\n"
            "print('main')\n"
            "```\n\n"
            "```markdown docs/guide.md\n"
            "# Guide\n"
            "```\n\n"
            "```python\n"
            "# pure language block, not a file\n"
            "```\n"
        )
        extracted = extract_files_from_markdown(sample)
        self.assertIn("scripts/foo.py", extracted)
        self.assertEqual(extracted["scripts/foo.py"].strip(), "print('foo')")
        self.assertIn("scripts/bar.py", extracted)
        self.assertEqual(extracted["scripts/bar.py"].strip(), "print('bar')")
        self.assertIn("main.py", extracted)
        self.assertEqual(extracted["main.py"].strip(), "print('main')")
        self.assertIn("docs/guide.md", extracted)
        self.assertEqual(extracted["docs/guide.md"].strip(), "# Guide")
        self.assertNotIn("python", extracted)

    def test_extract_files_from_markdown_context_fallback(self):
        from orchestrator.subagents import extract_files_from_markdown

        generic_sample = (
            "Here is the code to fix the issue:\n"
            "```python\n"
            "import os\n"
            "def sweep(): pass\n"
            "```\n"
        )
        context = "Issue: `hooks/monitor-open-prs.py` accumulates temporary state files."
        extracted = extract_files_from_markdown(generic_sample, context_text=context)
        self.assertIn("hooks/monitor-open-prs.py", extracted)
        self.assertIn("def sweep(): pass", extracted["hooks/monitor-open-prs.py"])

    def test_coder_subagent_empty_patch_fails_fast(self):
        from unittest.mock import MagicMock
        from orchestrator.model_adapters import ModelResponse, ModelProvider
        from orchestrator.subagents import CoderSubagent

        mock_router = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.invoke.return_value = ModelResponse(
            success=True,
            content="I am only conversational text with no code blocks or target files.",
            model_used="mock-conversational",
            provider=ModelProvider.CLAUDE,
            execution_time_seconds=0.1,
        )
        mock_router.route_task.return_value = (mock_adapter, "mock-conversational")

        agent = CoderSubagent(model_router=mock_router)
        task = Task(
            title="Non-code conversational response",
            role="coder",
            payload={
                "instruction": "Fix bug without providing file headers",
                "use_worktree": True,
                "branch_name": "task/empty-patch-live-test",
                "dry_run": False,
                "push_remote": False,
            },
        )
        ctx = SubagentContext(task=task, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        res = agent.execute(task, ctx)
        self.assertFalse(res.success)
        self.assertIn("no valid file modifications", res.error)

    def test_coder_subagent_push_failure_fails_fast(self):
        import subprocess
        from unittest.mock import patch, MagicMock
        from orchestrator.subagents import CoderSubagent

        agent = CoderSubagent()
        task = Task(
            title="Push failure task",
            role="coder",
            payload={
                "instruction": "Implement feature",
                "target_file": "scripts/test_push_fail.py",
                "code_content": "# test content\n",
                "use_worktree": True,
                "branch_name": "task/push-fail-test",
                "dry_run": False,
                "push_remote": True,
            },
        )
        ctx = SubagentContext(task=task, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)

        orig_run = subprocess.run

        def mock_subprocess_run(cmd, *args, **kwargs):
            if isinstance(cmd, list):
                if len(cmd) >= 2 and cmd[:2] == ["git", "commit"]:
                    mock_proc = MagicMock()
                    mock_proc.returncode = 0
                    mock_proc.stdout = "commit ok"
                    mock_proc.stderr = ""
                    return mock_proc
                if len(cmd) >= 2 and cmd[:2] == ["git", "push"]:
                    mock_proc = MagicMock()
                    mock_proc.returncode = 1
                    mock_proc.stderr = "fatal: remote rejected (permission denied)"
                    return mock_proc
            return orig_run(cmd, *args, **kwargs)

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            res = agent.execute(task, ctx)
            self.assertFalse(res.success)
            self.assertIn("Git push failed from worktree", res.error)

    def test_reviewer_subagent_empty_branch_diff_blocks(self):
        agent = self.registry.get_for_role("reviewer")
        task = Task(
            title="Review empty branch",
            role="reviewer",
            payload={"branch_name": "nonexistent-empty-branch-test", "dry_run": False},
        )
        ctx = SubagentContext(task=task, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        res = agent.execute(task, ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.data["verdict"], "BLOCKED")

    def test_extract_files_from_markdown_discards_stubs_and_self_referential_blocks(self):
        from orchestrator.subagents import extract_files_from_markdown

        # Self-referential single line
        text1 = "```memories/tools.md\nmemories/tools.md\n```"
        files1 = extract_files_from_markdown(text1)
        self.assertEqual(files1, {})

        # Basename echo
        text2 = "```memories/tools.md\ntools.md\n```"
        files2 = extract_files_from_markdown(text2)
        self.assertEqual(files2, {})

        # Ellipsis stub
        text3 = "```scripts/check.py\n...\n```"
        files3 = extract_files_from_markdown(text3)
        self.assertEqual(files3, {})

        # Real multi-line implementation
        text4 = "```scripts/foo.py\nimport os\nprint('hello world')\n```"
        files4 = extract_files_from_markdown(text4)
        self.assertEqual(files4, {"scripts/foo.py": "import os\nprint('hello world')\n"})

    def test_coder_subagent_destructive_truncation_guard(self):
        from unittest.mock import MagicMock
        from orchestrator.subagents import CoderSubagent
        from orchestrator.model_adapters import ModelProvider, ModelResponse

        mock_router = MagicMock()
        mock_adapter = MagicMock()
        # Model outputs a 2-line stub for an existing 50-line file
        mock_adapter.invoke.return_value = ModelResponse(
            success=True,
            content="```scripts/big_file.py\n# stub\npass\n```",
            model_used="mock-stub-coder",
            provider=ModelProvider.OLLAMA,
            execution_time_seconds=0.1,
        )
        mock_router.route_task.return_value = (mock_adapter, "mock-stub-coder")

        # Create big file in temp workspace
        big_file_path = os.path.join(self.temp_dir.name, "scripts", "big_file.py")
        os.makedirs(os.path.dirname(big_file_path), exist_ok=True)
        with open(big_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"# Line {i}" for i in range(50)))

        mock_wt_mgr = MagicMock()
        mock_wt_mgr.isolated_worktree.return_value.__enter__.return_value = Path(self.temp_dir.name)
        mock_wt_mgr.isolated_worktree.return_value.__exit__.return_value = None

        agent = CoderSubagent(model_router=mock_router, worktree_manager=mock_wt_mgr)
        task = Task(
            title="Refactor scripts/big_file.py",
            role="coder",
            payload={
                "instruction": "Fix bug in scripts/big_file.py",
                "use_worktree": True,
                "branch_name": "task/truncation-test",
                "dry_run": False,
                "push_remote": False,
            },
        )
        ctx = SubagentContext(task=task, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        res = agent.execute(task, ctx)
        self.assertFalse(res.success)
        self.assertIn("Destructive truncation detected", res.error)

    def test_extract_files_from_markdown_fallback_discards_all_stub_patterns(self):
        from orchestrator.subagents import extract_files_from_markdown

        for stub in ["...", "# ...", "// ...", "pass", "/* same */", "# same"]:
            text = f"```scripts/check.py\n{stub}\n```"
            res = extract_files_from_markdown(text, context_text="please fix scripts/check.py now")
            self.assertEqual(res, {}, f"Failed to discard stub: {stub}")

    def test_extract_files_from_markdown_fallback_discards_stub_with_multiple_candidates(self):
        from orchestrator.subagents import extract_files_from_markdown

        text = "```\nmemories/tools.md\n```"
        res = extract_files_from_markdown(text, context_text="update memories/tools.md and also scripts/foo.py please")
        self.assertEqual(res, {})

        text2 = "```\nscripts/a.py\n```"
        res2 = extract_files_from_markdown(text2, context_text="please fix scripts/a.py and scripts/b.py now")
        self.assertEqual(res2, {})

        # Shape variants: bare path for unrelated file, header cross-path, and comment-prefixed path
        text3 = "```\ndocs/readme.md\n```"
        res3 = extract_files_from_markdown(text3, context_text="fix scripts/a.py")
        self.assertEqual(res3, {})

        text4 = "```scripts/a.py\nscripts/b.py\n```"
        res4 = extract_files_from_markdown(text4, context_text="fix scripts/a.py and scripts/b.py")
        self.assertEqual(res4, {})

        text5 = "```\n# scripts/a.py\n```"
        res5 = extract_files_from_markdown(text5, context_text="fix scripts/a.py")
        self.assertEqual(res5, {})

        # Multi-line path stub variants
        text6 = "```scripts/foo.py\nscripts/a.py\nscripts/b.py\n```"
        res6 = extract_files_from_markdown(text6)
        self.assertEqual(res6, {})

        text7 = "```\nscripts/a.py\nscripts/b.py\n```"
        res7 = extract_files_from_markdown(text7, context_text="fix scripts/a.py and scripts/b.py")
        self.assertEqual(res7, {})

        text8 = "```\n# ...\n# ...\n```"
        res8 = extract_files_from_markdown(text8, context_text="fix scripts/a.py")
        self.assertEqual(res8, {})

        # ./ prefixed and multi-dot extension path stub variants
        text9 = "```scripts/foo.py\n./scripts/a.py\n./scripts/b.py\n```"
        res9 = extract_files_from_markdown(text9)
        self.assertEqual(res9, {})

        text10 = "```\n./scripts/a.tar.gz\n```"
        res10 = extract_files_from_markdown(text10, context_text="fix scripts/a.tar.gz")
        self.assertEqual(res10, {})

        # Single dotted tokens (version numbers, domains, numbers) must NOT be discarded as stubs
        text11 = "```version.txt\n1.0.0\n```"
        res11 = extract_files_from_markdown(text11)
        self.assertEqual(res11, {"version.txt": "1.0.0\n"})

        text12 = "```config.txt\nexample.com\n```"
        res12 = extract_files_from_markdown(text12)
        self.assertEqual(res12, {"config.txt": "example.com\n"})

        text13 = "```scripts/pi.py\n3.14\n```"
        res13 = extract_files_from_markdown(text13)
        self.assertEqual(res13, {"scripts/pi.py": "3.14\n"})

        # Bare no-directory filenames echoing other files must be discarded as stubs
        text14 = "```scripts/foo.py\nutils.py\n```"
        res14 = extract_files_from_markdown(text14)
        self.assertEqual(res14, {})

        text15 = "```scripts/foo.py\nutils.py\nhelpers.py\n```"
        res15 = extract_files_from_markdown(text15)
        self.assertEqual(res15, {})

        # Generic extensions (vue, proto, mdc, jsonc, service, env, etc.)
        text16 = "```scripts/foo.py\nconfig.env\n```"
        res16 = extract_files_from_markdown(text16)
        self.assertEqual(res16, {})

        text17 = "```scripts/foo.py\napp.vue\nmain.proto\n```"
        res17 = extract_files_from_markdown(text17)
        self.assertEqual(res17, {})

        text18 = "```scripts/foo.py\n.cursor/rules/a.mdc\n```"
        res18 = extract_files_from_markdown(text18)
        self.assertEqual(res18, {})

        text19 = "```scripts/foo.py\nsettings.jsonc\nunit.service\n```"
        res19 = extract_files_from_markdown(text19)
        self.assertEqual(res19, {})

        # ./ and / prefixed dotfiles
        text20 = "```scripts/config_loader.py\n./.env\n```"
        res20 = extract_files_from_markdown(text20)
        self.assertEqual(res20, {})

        text21 = "```scripts/foo.py\n/.gitignore\n```"
        res21 = extract_files_from_markdown(text21)
        self.assertEqual(res21, {})

        # Paths with numeric stem in directory (e.g. docs/2023.md)
        text22 = "```scripts/foo.py\ndocs/2023.md\n```"
        res22 = extract_files_from_markdown(text22)
        self.assertEqual(res22, {})

        # Numbered list markers
        text23 = "```memories/tools.md\n1. memories/tools.md\n2. memories/git.md\n```"
        res23 = extract_files_from_markdown(text23)
        self.assertEqual(res23, {})

        # Legitimate glob files like .gitignore must NOT be discarded
        text24 = "```.gitignore\n*.pyc\n*.pyo\n.env\n```"
        res24 = extract_files_from_markdown(text24)
        self.assertEqual(res24, {".gitignore": "*.pyc\n*.pyo\n.env\n"})

        # Comma-, semicolon-, and lettered-lists
        text25 = "```scripts/foo.py\nscripts/a.py, scripts/b.py\n```"
        res25 = extract_files_from_markdown(text25)
        self.assertEqual(res25, {})

        text26 = "```scripts/foo.py\nscripts/a.py; scripts/b.py\n```"
        res26 = extract_files_from_markdown(text26)
        self.assertEqual(res26, {})

        text27 = "```scripts/foo.py\na. scripts/a.py\nb. scripts/b.py\n```"
        res27 = extract_files_from_markdown(text27)
        self.assertEqual(res27, {})

        # Bare multi-dot config / minified / typed definition filenames
        text28 = "```scripts/foo.py\nwebpack.config.js\n```"
        res28 = extract_files_from_markdown(text28)
        self.assertEqual(res28, {})

        text29 = "```scripts/foo.py\njquery.min.js\nfile.d.ts\n```"
        res29 = extract_files_from_markdown(text29)
        self.assertEqual(res29, {})

    def test_find_candidate_file_paths_adjacent_paths(self):
        from orchestrator.subagents import find_candidate_file_paths

        res = find_candidate_file_paths("update scripts/a.py scripts/b.py scripts/c.py please")
        self.assertEqual(res, ["scripts/a.py", "scripts/b.py", "scripts/c.py"])

        res2 = find_candidate_file_paths("update scripts/a.py, scripts/b.py, and scripts/c.py.")
        self.assertEqual(res2, ["scripts/a.py", "scripts/b.py", "scripts/c.py"])

        res3 = find_candidate_file_paths("update scripts/a.py,scripts/b.py and .gitignore, README.md, main.py")
        self.assertEqual(res3, ["scripts/a.py", "scripts/b.py", ".gitignore", "README.md", "main.py"])

    def test_extract_files_from_markdown_default_target_file(self):
        from orchestrator.subagents import extract_files_from_markdown

        text = "```python\nprint('hello world')\n```"
        res = extract_files_from_markdown(text, default_target_file="scripts/my_target.py")
        self.assertEqual(res, {"scripts/my_target.py": "print('hello world')\n"})

    def test_resolve_within_worktree(self):
        from orchestrator.subagents import resolve_within_worktree

        root = Path(self.temp_dir.name).resolve()
        safe_path = resolve_within_worktree("scripts/foo.py", root)
        self.assertIsNotNone(safe_path)
        self.assertTrue(safe_path.is_relative_to(root))

        # Root itself must return None (strictly contained)
        self.assertIsNone(resolve_within_worktree(".", root))
        self.assertIsNone(resolve_within_worktree("", root))
        self.assertIsNone(resolve_within_worktree("/", root))

        # Relative paths escaping worktree root must return None
        escape_path = resolve_within_worktree("../../../etc/passwd", root)
        self.assertIsNone(escape_path)

        # Absolute paths are rebased under the worktree root
        abs_rebased = resolve_within_worktree("/scripts/bar.py", root)
        self.assertIsNotNone(abs_rebased)
        self.assertEqual(abs_rebased, (root / "scripts/bar.py").resolve())

    def test_coder_subagent_path_traversal_context_injection_blocked(self):
        from unittest.mock import MagicMock, patch
        from orchestrator.subagents import CoderSubagent
        from orchestrator.model_adapters import ModelProvider, ModelResponse

        mock_router = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.invoke.return_value = ModelResponse(
            success=True,
            content="```scripts/safe.py\n# safe\nprint('ok')\n```",
            model_used="mock-coder",
            provider=ModelProvider.OLLAMA,
            execution_time_seconds=0.1,
        )
        mock_router.route_task.return_value = (mock_adapter, "mock-coder")

        mock_wt_mgr = MagicMock()
        mock_wt_mgr.isolated_worktree.return_value.__enter__.return_value = Path(self.temp_dir.name)
        mock_wt_mgr.isolated_worktree.return_value.__exit__.return_value = None

        agent = CoderSubagent(model_router=mock_router, worktree_manager=mock_wt_mgr)
        task = Task(
            title="Fix bug with path traversal attempt",
            role="coder",
            payload={
                "instruction": "Fix scripts/../../../../../../etc/passwd.txt vulnerability",
                "use_worktree": True,
                "branch_name": "task/path-traversal-test",
                "dry_run": False,
                "push_remote": False,
            },
        )
        ctx = SubagentContext(task=task, state_store=self.store, worker_id="w1", workspace_root=self.temp_dir.name)
        with patch("subprocess.run") as mock_proc:
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = "ok"
            mock_res.stderr = ""
            mock_proc.return_value = mock_res
            res = agent.execute(task, ctx)

        # Should succeed without crashing or leaking sensitive file
        self.assertTrue(res.success)
        self.assertIn("scripts/safe.py", res.data["files_modified"])


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
            payload={"goal": "Feature X", "stages": ["researcher", "coder", "tester"], "dry_run": True},
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
        # Test opt-in auto_claim_pr=True (with dry_run)
        dag = self.sweeper.ingest_issue(fake_issue, auto_claim_pr=True, dry_run=True)
        self.assertEqual(len(dag), 4)

        roles = [t.role for t in dag]
        self.assertEqual(roles, ["researcher", "coder", "reviewer", "tester"])

        # Check dependencies: coder depends on researcher, reviewer on coder, tester on reviewer
        self.assertEqual(dag[1].depends_on, [dag[0].id])
        self.assertEqual(dag[2].depends_on, [dag[1].id])
        self.assertEqual(dag[3].depends_on, [dag[2].id])

        # Check PR-on-claim metadata attached to tasks
        for task in dag:
            self.assertTrue(task.payload["branch_name"].startswith("fix/issue-9999"))
            self.assertIsNotNone(task.payload["pr_number"])
            self.assertIsNotNone(task.payload["pr_url"])

        # Test default safe mode (auto_claim_pr=False)
        fake_issue_2 = {
            "number": 9998,
            "title": "Fix crash in task worker",
            "body": "Detailed description of crash.",
        }
        dag_default = self.sweeper.ingest_issue(fake_issue_2, dry_run=True)
        self.assertEqual(len(dag_default), 4)
        for task in dag_default:
            self.assertIsNone(task.payload["pr_number"])

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

    def test_coder_subagent_worktree_path_traversal_blocked(self):
        from orchestrator.subagents import CoderSubagent
        from orchestrator.models import SubagentContext
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            from orchestrator.worktree_manager import WorktreeManager
            wt_mgr = WorktreeManager(repo_root=Path.cwd(), worktree_parent=Path(tmpdir))
            coder = CoderSubagent(worktree_manager=wt_mgr)

            task = PathTraversalTask = Task(
                title="Path traversal attack simulation",
                role="coder",
                payload={
                    "instruction": "Overwrite outside file",
                    "target_file": "../../../outside.txt",
                    "code_content": "malicious content\n",
                    "use_worktree": True,
                    "branch_name": "task/traversal-test",
                    "persist_branch": False,
                },
            )
            ctx = SubagentContext(task=task, state_store=None, worker_id="worker-test", workspace_root=str(Path.cwd()))
            result = coder.execute(task, ctx)

            self.assertFalse(result.success)
            self.assertIn("escapes worktree root", result.error)


class TestAIConfigProtocolsAndPRClaim(unittest.TestCase):
    """Tests that orchestrator and subagents strictly follow Morrison-Lab / ai-config protocols."""

    def test_protocols_system_prompts_encode_agents_md(self):
        from orchestrator.protocols import AIConfigProtocols
        from orchestrator.subagents import ResearcherSubagent, CoderSubagent, ReviewerSubagent, TesterSubagent

        for agent_cls in [ResearcherSubagent, CoderSubagent, ReviewerSubagent, TesterSubagent]:
            agent = agent_cls()
            prompt = agent.get_system_prompt()
            self.assertIn("WORKTREE ISOLATION", prompt)
            self.assertIn("PR-ON-CLAIM", prompt)
            self.assertIn("FAIL-FAST", prompt)
            self.assertIn("ADVERSARIAL SELF-REVIEW", prompt)
            self.assertIn("STRICT MERGE POLICY", prompt)

    def test_pr_claim_manager_branch_naming_and_dry_run(self):
        from orchestrator.pr_claim_manager import PRClaimManager

        mgr = PRClaimManager(repo_slug="Morrison-Lab/ai-config")
        branch_feat = mgr.generate_branch_name(2112, "feat: add persistent orchestration loop")
        self.assertTrue(branch_feat.startswith("feat/issue-2112-feat-add-persistent"))

        branch_fix = mgr.generate_branch_name(2115, "fix memory leak in worker daemon")
        self.assertTrue(branch_fix.startswith("fix/issue-2115-fix-memory-leak"))

        claim_info = mgr.claim_issue_and_open_draft_pr(2112, "feat: add persistent orchestration loop", dry_run=True)
        self.assertTrue(claim_info["draft_pr_opened"])
        self.assertIsNotNone(claim_info["pr_number"])
        self.assertIn("https://github.com/Morrison-Lab/ai-config/pull/", claim_info["pr_url"])

    def test_pr_claim_manager_merge_pr_under_mwc(self):
        from orchestrator.pr_claim_manager import PRClaimManager

        mgr = PRClaimManager(repo_slug="Morrison-Lab/ai-config")
        merged = mgr.merge_pr_under_mwc(pr_number=2112, dry_run=True)
        self.assertTrue(merged)

    def test_tester_subagent_marks_draft_pr_ready_and_merges_under_mwc(self):
        from orchestrator.subagents import TesterSubagent
        from orchestrator.models import SubagentContext

        tester = TesterSubagent()
        task = Task(
            title="Verify quality gates and merge under mwc",
            role="tester",
            payload={
                "pr_number": 2112,
                "dry_run": True,
                "mwc": True,
                "expected_assertions": 5,
            },
        )
        ctx = SubagentContext(task=task, state_store=None, worker_id="worker-tester", workspace_root=str(Path.cwd()))
        res = tester.execute(task, ctx)

        self.assertTrue(res.success)
        self.assertTrue(res.data.get("pr_marked_ready", False))
        self.assertTrue(res.data.get("pr_merged", False))

    def test_check_repo_allows_mwc_policy(self):
        from orchestrator.protocols import AIConfigProtocols

        # ai-config has standing mwc policy
        self.assertTrue(AIConfigProtocols.check_repo_allows_mwc(repo_slug="Morrison-Lab/ai-config"))
        self.assertTrue(AIConfigProtocols.check_repo_allows_mwc(repo_slug="owner/ai-config"))

        # External repo slug targeting does NOT inherit current workspace directory
        self.assertFalse(AIConfigProtocols.check_repo_allows_mwc(repo_slug="SomeOrg/unrelated-repo"))

        # Arbitrary external repo without written policy does not allow mwc by default
        with tempfile.TemporaryDirectory() as empty_dir:
            self.assertFalse(AIConfigProtocols.check_repo_allows_mwc(repo_root=Path(empty_dir), repo_slug="external/foo"))

    def test_is_pr_fully_clean_detection(self):
        import json
        from unittest.mock import MagicMock
        from orchestrator.pr_claim_manager import PRClaimManager

        mgr = PRClaimManager(repo_slug="Morrison-Lab/ai-config")

        # 1. Clean PR with approved external Claude review comment
        clean_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"name": "check-links", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": "**Claude finished** -- review\n\n### Verdict\n**Clean**\n\nReady for merge"}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, clean_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertTrue(is_clean)
        self.assertIn("fully clean", reason)

        # 2. Formal GitHub review approval without Claude Code Review is REJECTED under mwc
        clean_gh_review_json = json.dumps({
            "headRefOid": "commit123",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [{"state": "APPROVED", "author": {"login": "d-morrison"}, "authorAssociation": "OWNER", "commit": {"oid": "commit123"}}],
            "comments": [],
        })
        mgr._run_cmd = MagicMock(return_value=(0, clean_gh_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("no independent external claude code review found", reason.lower())

        # 2b. Formal GitHub review approval from random passerby (NONE / CONTRIBUTOR) is REJECTED
        passerby_review_json = json.dumps({
            "headRefOid": "commit123",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [{"state": "APPROVED", "author": {"login": "random-passerby"}, "authorAssociation": "NONE", "commit": {"oid": "commit123"}}],
            "comments": [],
        })
        mgr._run_cmd = MagicMock(return_value=(0, passerby_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("no independent external claude code review found", reason.lower())

        # 2c. Formal GitHub review self-approval (dem-extra1) is REJECTED
        self_review_json = json.dumps({
            "headRefOid": "commit123",
            "author": {"login": "dem-extra1"},
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [{"state": "APPROVED", "author": {"login": "dem-extra1"}, "authorAssociation": "COLLABORATOR", "commit": {"oid": "commit123"}}],
            "comments": [],
        })
        mgr._run_cmd = MagicMock(return_value=(0, self_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("no independent external claude code review found", reason.lower())

        # 2d. Stale formal GitHub review (commit.oid != headRefOid) is REJECTED
        stale_review_json = json.dumps({
            "headRefOid": "commit456_new",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [{"state": "APPROVED", "author": {"login": "d-morrison"}, "authorAssociation": "OWNER", "commit": {"oid": "commit123_old"}}],
            "comments": [],
        })
        mgr._run_cmd = MagicMock(return_value=(0, stale_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("no independent external claude code review found", reason.lower())

        # 3. Passing CI but NO review or comment -> MUST NOT MERGE
        no_review_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [],
        })
        mgr._run_cmd = MagicMock(return_value=(0, no_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("no independent external claude code review found", reason.lower())

        # 3. Failing CI check
        dirty_ci_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "FAILURE"},
            ],
            "reviews": [{"state": "APPROVED", "author": {"login": "d-morrison"}, "authorAssociation": "OWNER"}],
            "comments": [],
        })
        mgr._run_cmd = MagicMock(return_value=(0, dirty_ci_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("failed", reason)

        # 4. Self-posted comment from collaborator / orchestrator account is REJECTED as an approval gate
        self_comment_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [
                {"author": {"login": "dem-extra1"}, "body": "**Claude finished** -- review\n\n### Verdict\n**Clean**"},
            ],
        })
        mgr._run_cmd = MagicMock(return_value=(0, self_comment_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("no independent external claude code review found", reason.lower())

        # 5. Null author dictionary does not crash and is rejected
        null_author_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [
                {"author": None, "body": "**Claude finished** -- review\n\n### Verdict\n**Clean**"},
            ],
        })
        mgr._run_cmd = MagicMock(return_value=(0, null_author_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("no independent external claude code review found", reason.lower())

        # 6. Blocking AI review verdict ("Needs more work")
        dirty_review_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": "**Claude finished** -- review\n\nVerdict: Needs more work."}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, dirty_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("needs more work", reason.lower())

        # 7. Alternative blocking verdict phrasing ("Blocked on human review")
        blocked_human_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": "**Claude finished** -- review\n\nVerdict: Blocked on human review"}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, blocked_human_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("blocked", reason.lower())

        # 8. Production Claude review header format ("**Claude finished** -- ...") from claude[bot]
        prod_review_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "claude[bot]"}, "body": "**Claude finished** -- adversarial review\n\n### Verdict\nClean / Approved"}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, prod_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertTrue(is_clean)
        self.assertIn("fully clean", reason)

        # 9. Closed PR notice with em-dash ("No action \u2014 PR is closed/merged")
        closed_pr_emdash_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": "**Claude finished** -- review\n\nVerdict: No action \u2014 PR is closed/merged"}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, closed_pr_emdash_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("blocking verdict", reason.lower())

        # 10. Stub review (Claude completed but no positive clean/approved verdict)
        stub_review_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": "**Claude finished** -- review\n\nI examined the files but got cut short."}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, stub_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("does not contain a recognized positive clean/approved verdict", reason)

        # 11. PR without Claude Code Review where human submits formal APPROVED review is REJECTED under mwc
        dm_self_review_json = json.dumps({
            "author": {"login": "d-morrison"},
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [{"state": "APPROVED", "author": {"login": "d-morrison"}, "authorAssociation": "OWNER"}],
            "comments": [],
        })
        mgr._run_cmd = MagicMock(return_value=(0, dm_self_review_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("no independent external claude code review found", reason.lower())

        # 12. Multi-verdict comment (prior round's 'Needs more work' cited before final 'Clean' verdict)
        multi_verdict_body = """**Claude finished** review

The prior review's verdict:
```markdown
### Verdict

**Needs more work**
```
This has since been resolved after addressing the finding.

### Verdict

**Clean** (0 blocking findings)
"""
        multi_verdict_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": multi_verdict_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, multi_verdict_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertTrue(is_clean)
        self.assertIn("fully clean", reason)

        # 13. Negated verdict phrasing ("This PR is not approved yet") is REJECTED
        not_approved_body = "**Claude finished** review\n\n### Verdict\n\nThis PR is **not approved** yet, two blocking findings remain."
        not_approved_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": not_approved_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, not_approved_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 14. Negated verdict phrasing ("This isn't ready for merge") is REJECTED
        not_ready_body = "**Claude finished** review\n\n### Verdict\n\nThis isn't ready for merge."
        not_ready_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": not_ready_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, not_ready_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 15. Review comment posted by author login 'claude' is accepted
        claude_login_body = "**Claude finished** review\n\n### Verdict\n\n**Approved** for merge"
        claude_login_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "claude"}, "body": claude_login_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, claude_login_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertTrue(is_clean)
        self.assertIn("fully clean", reason)

        # 16. Multiline review where first line says Ready but followed by cant be called ready
        cant_be_ready_body = "**Claude finished** review\n\n### Verdict\n\nReady.\nThis PR can't be called ready for merge because 2 blocking findings remain."
        cant_be_ready_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": cant_be_ready_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, cant_be_ready_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 17. Far from ready is rejected
        far_from_ready_body = "**Claude finished** review\n\n### Verdict\n\nThis PR is far from ready for merge."
        far_from_ready_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": far_from_ready_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, far_from_ready_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 18. Prose mentioning 'ready for merge' in a blocking description is rejected
        prose_mention_body = (
            "**Claude finished** review\n\n### Verdict\n\n"
            "This PR still has one blocking issue (SQL injection in the query builder, see\n"
            "finding above) standing between it and being ready for merge."
        )
        prose_mention_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": prose_mention_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, prose_mention_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 19. Clean-up needed in file X before merging is rejected
        cleanup_body = "**Claude finished** review\n\n### Verdict\n\nClean-up needed in file X before merging."
        cleanup_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": cleanup_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, cleanup_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 20. LGTM on first verdict line is accepted
        lgtm_body = "**Claude finished** review\n\n### Verdict\n\nLGTM"
        lgtm_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": lgtm_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, lgtm_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertTrue(is_clean)

        # 21. Multi-paragraph review where first line is Needs more work but paragraph 2 mentions Ready for merge
        multiparagraph_body = "**Claude finished** review\n\n### Verdict\n\n**Needs more work**\n\nOnce fixed, this will be ready for merge."
        multiparagraph_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": multiparagraph_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, multiparagraph_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 22. Code fence containing fake clean heading does not spoof real needs more work verdict
        code_fence_spoof_body = (
            "**Claude finished** review\n\n"
            "Example tested:\n```markdown\n### Verdict\n\n**Clean**\n```\n\n"
            "### Verdict\n\n**Needs more work**"
        )
        code_fence_spoof_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": code_fence_spoof_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, code_fence_spoof_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 23. Code fence containing fake needs work heading does not spoof real clean verdict
        code_fence_clean_body = (
            "**Claude finished** review\n\n"
            "Prior output was:\n```markdown\n### Verdict\n\n**Needs more work**\n```\n\n"
            "### Verdict\n\n**Clean**"
        )
        code_fence_clean_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": code_fence_clean_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, code_fence_clean_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertTrue(is_clean)

        # 24. Non-fenced decoy clean heading after a blocking verdict is strictly rejected
        non_fenced_decoy_body = (
            "**Claude finished** review\n\n"
            "### Verdict\n\n**Needs more work**\n\n"
            "Decoy note:\n"
            "### Verdict\n\n**Clean**"
        )
        non_fenced_decoy_json = json.dumps({
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{"author": {"login": "github-actions"}, "body": non_fenced_decoy_body}],
        })
        mgr._run_cmd = MagicMock(return_value=(0, non_fenced_decoy_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)

        # 25. Stale Claude review (reviewed an older commit than PR headRefOid) is strictly rejected
        stale_claude_json = json.dumps({
            "headRefOid": "c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{
                "author": {"login": "github-actions"},
                "body": "**Claude finished** review\n\n### Verdict\n\n**Clean**\n\nReviewed commit: 74d3f8c1b60dc25cf5c06d882027177ca54d45a0",
            }],
        })
        mgr._run_cmd = MagicMock(return_value=(0, stale_claude_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("stale", reason.lower())

        # 26. Matching commit Claude review (reviewed current PR headRefOid) is accepted
        matching_claude_json = json.dumps({
            "headRefOid": "c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{
                "author": {"login": "github-actions"},
                "body": "**Claude finished** review\n\n### Verdict\n\n**Clean**\n\nReviewed commit: c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            }],
        })
        mgr._run_cmd = MagicMock(return_value=(0, matching_claude_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertTrue(is_clean)

        # 27. Multi-line verdict with subsequent line qualification / condition is strictly rejected
        qualified_verdict_json = json.dumps({
            "headRefOid": "c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{
                "author": {"login": "github-actions"},
                "body": (
                    "**Claude finished** review\n\n"
                    "### Verdict\n\n"
                    "**Clean**\n\n"
                    "However, do not merge until human signoff is obtained.\n\n"
                    "Reviewed commit: c1427642ddf8ae431b7b920d01bfd9c5b270ae4f"
                ),
            }],
        })
        mgr._run_cmd = MagicMock(return_value=(0, qualified_verdict_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("trailing unrecognized prose", reason.lower())

        # 28. Multi-line verdict with trailing un-allowlisted contradiction ("2 blocking findings") is strictly rejected
        contradiction_1_json = json.dumps({
            "headRefOid": "c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{
                "author": {"login": "github-actions"},
                "body": (
                    "**Claude finished** review\n\n"
                    "### Verdict\n\n"
                    "Clean\n\n"
                    "There are 2 blocking findings that remain unresolved and must be fixed prior to merge."
                ),
            }],
        })
        mgr._run_cmd = MagicMock(return_value=(0, contradiction_1_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("trailing unrecognized prose", reason.lower())

        # 29. Multi-line verdict with trailing un-allowlisted contradiction ("Do not merge") is strictly rejected
        contradiction_2_json = json.dumps({
            "headRefOid": "c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{
                "author": {"login": "github-actions"},
                "body": (
                    "**Claude finished** review\n\n"
                    "### Verdict\n\n"
                    "LGTM\n\n"
                    "Do not merge -- there is a security vulnerability."
                ),
            }],
        })
        mgr._run_cmd = MagicMock(return_value=(0, contradiction_2_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("trailing unrecognized prose", reason.lower())

        # 30. Multi-line verdict with trailing un-allowlisted contradiction ("This should not be merged yet") is strictly rejected
        contradiction_3_json = json.dumps({
            "headRefOid": "c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{
                "author": {"login": "github-actions"},
                "body": (
                    "**Claude finished** review\n\n"
                    "### Verdict\n\n"
                    "Approved\n\n"
                    "This should not be merged yet."
                ),
            }],
        })
        mgr._run_cmd = MagicMock(return_value=(0, contradiction_3_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("trailing unrecognized prose", reason.lower())

        # 31. Trailing prose starting with 'Reviewed by' is strictly rejected
        reviewed_by_contradiction_json = json.dumps({
            "headRefOid": "c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{
                "author": {"login": "github-actions"},
                "body": (
                    "**Claude finished** review\n\n"
                    "### Verdict\n\n"
                    "**Clean**\n\n"
                    "Reviewed by a human who found 2 blocking security bugs."
                ),
            }],
        })
        mgr._run_cmd = MagicMock(return_value=(0, reviewed_by_contradiction_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("trailing unrecognized prose", reason.lower())

        # 32. Trailing prose starting with 'Posted by' is strictly rejected
        posted_by_contradiction_json = json.dumps({
            "headRefOid": "c1427642ddf8ae431b7b920d01bfd9c5b270ae4f",
            "statusCheckRollup": [
                {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "reviews": [],
            "comments": [{
                "author": {"login": "github-actions"},
                "body": (
                    "**Claude finished** review\n\n"
                    "### Verdict\n\n"
                    "**Clean**\n\n"
                    "Posted by someone who noticed this is broken."
                ),
            }],
        })
        mgr._run_cmd = MagicMock(return_value=(0, posted_by_contradiction_json, ""))
        is_clean, reason = mgr.is_pr_fully_clean(2112)
        self.assertFalse(is_clean)
        self.assertIn("trailing unrecognized prose", reason.lower())

    def test_cli_ingest_issues_dry_run_and_claim_pr_flags(self):
        from orchestrator.cli import build_parser

        parser = build_parser()
        # Default ingest-issues (safe opt-in default: claim_pr=False, mwc=None for auto-detection)
        args_default = parser.parse_args(["ingest-issues", "--limit", "5"])
        self.assertFalse(args_default.dry_run)
        self.assertFalse(args_default.claim_pr)
        self.assertIsNone(args_default.mwc)

        # Explicit --claim-pr opt-in and --no-mwc
        args_opt_in = parser.parse_args(["ingest-issues", "--claim-pr", "--limit", "3", "--no-mwc"])
        self.assertFalse(args_opt_in.dry_run)
        self.assertTrue(args_opt_in.claim_pr)
        self.assertFalse(args_opt_in.mwc)

        # Explicit sweep-backlog --dry-run and explicit --mwc
        args_sweep = parser.parse_args(["sweep-backlog", "--dry-run", "--limit", "2", "--mwc"])
        self.assertTrue(args_sweep.dry_run)
        self.assertFalse(args_sweep.claim_pr)
        self.assertTrue(args_sweep.mwc)


def main():
    unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
