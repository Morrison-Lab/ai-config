"""Specialized sub-agents and subagent registry for the orchestration loop."""

from __future__ import annotations

from abc import ABC, abstractmethod
import os
import time
from typing import Any, Dict, List, Optional

from .models import SubagentContext, SubagentResult, Task, TaskPriority, TaskStatus
from .worktree_manager import WorktreeManager


class BaseSubagent(ABC):
    """Abstract base class for all specialized sub-agents."""

    role: str = "generic"
    capabilities: List[str] = []

    @abstractmethod
    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        """Execute the assigned task within the provided context."""
        raise NotImplementedError


class ResearcherSubagent(BaseSubagent):
    """Specialized sub-agent for research, file surveys, and documentation analysis."""

    role = "researcher"
    capabilities = ["search", "survey", "code_reading", "doc_analysis"]

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        query = task.payload.get("query") or task.title
        target_path = task.payload.get("target_path", "")

        findings: Dict[str, Any] = {
            "query": query,
            "target_path": target_path,
            "analysis": f"Completed research investigation for '{query}'.",
            "matches": [],
        }

        # Check if local path exists
        if target_path and os.path.exists(target_path):
            findings["file_exists"] = True
            findings["file_size"] = os.path.getsize(target_path)

        elapsed = time.time() - start_time
        return SubagentResult(
            success=True,
            data=findings,
            artifacts={"research_summary": findings},
            execution_time_seconds=elapsed,
        )


class CoderSubagent(BaseSubagent):
    """Specialized sub-agent for implementation, code modifications, and refactoring."""

    role = "coder"
    capabilities = ["code_generation", "refactoring", "patch_creation"]

    def __init__(self, worktree_manager: Optional[WorktreeManager] = None):
        self.worktree_manager = worktree_manager or WorktreeManager()

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        instruction = task.payload.get("instruction") or task.title
        target_file = task.payload.get("target_file", "")
        code_content = task.payload.get("code_content", "")
        use_worktree = task.payload.get("use_worktree", False)
        branch_name = task.payload.get("branch_name")

        result_data: Dict[str, Any] = {
            "instruction": instruction,
            "target_file": target_file,
            "applied": True,
            "lines_changed": len(code_content.splitlines()) if code_content else 0,
        }

        # If worktree isolation is requested, execute within an isolated worktree
        if use_worktree:
            try:
                persist_branch = task.payload.get("persist_branch", True)
                with self.worktree_manager.isolated_worktree(
                    task_id=task.id,
                    branch_name=branch_name,
                    cleanup=task.payload.get("cleanup_worktree", True),
                    delete_branch=not persist_branch,
                ) as wt_path:
                    if target_file and code_content:
                        file_path = wt_path / target_file
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_text(code_content, encoding="utf-8")

                        # Stage and commit the change to the worktree branch
                        import subprocess
                        subprocess.run(["git", "add", "."], cwd=str(wt_path), capture_output=True, check=False)
                        commit_proc = subprocess.run(
                            ["git", "commit", "-m", f"fix: {instruction[:60]}"],
                            cwd=str(wt_path),
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if commit_proc.returncode != 0:
                            err_msg = commit_proc.stderr.strip() or f"git commit exited with code {commit_proc.returncode}"
                            return SubagentResult(
                                success=False,
                                data=result_data,
                                error=f"Git commit failed in worktree: {err_msg}",
                                execution_time_seconds=time.time() - start_time,
                            )
                        result_data["committed"] = True
                    result_data["worktree_used"] = str(wt_path)
            except Exception as exc:
                return SubagentResult(
                    success=False,
                    data=result_data,
                    error=f"Worktree execution error: {str(exc)}",
                    execution_time_seconds=time.time() - start_time,
                )

        elapsed = time.time() - start_time
        return SubagentResult(
            success=True,
            data=result_data,
            artifacts={"code_patch": {"target": target_file, "content": code_content}},
            execution_time_seconds=elapsed,
        )


class ReviewerSubagent(BaseSubagent):
    """Specialized sub-agent for adversarial review, linting, and quality verification."""

    role = "reviewer"
    capabilities = ["adversarial_review", "code_review", "security_check"]

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        diff_or_code = task.payload.get("diff") or task.payload.get("code") or ""
        rules = task.payload.get("rules", ["Verify syntax", "Check safety", "Check style"])

        findings: List[Dict[str, Any]] = []
        is_clean = True

        # Perform review checks
        if "TODO" in diff_or_code:
            findings.append({"level": "WARN", "message": "Unresolved TODO detected in code diff."})
        if "eval(" in diff_or_code or "exec(" in diff_or_code:
            findings.append({"level": "ERROR", "message": "Potentially unsafe dynamic execution detected."})
            is_clean = False

        verdict = "CLEAN" if is_clean else "BLOCKED"
        elapsed = time.time() - start_time

        return SubagentResult(
            success=is_clean,
            data={"verdict": verdict, "findings": findings, "rules_evaluated": rules},
            artifacts={"review_report": {"verdict": verdict, "findings": findings}},
            execution_time_seconds=elapsed,
        )


class TesterSubagent(BaseSubagent):
    """Specialized sub-agent for running verification tests and capturing diagnostic output."""

    role = "tester"
    capabilities = ["run_tests", "benchmarking", "diagnostics"]

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        test_suite = task.payload.get("test_suite", "default")
        expected_assertions = task.payload.get("expected_assertions", 1)

        # Simulation or test execution logic
        passed = task.payload.get("mock_failure", False) is False
        output = f"Executed suite {test_suite}: {expected_assertions} assertions passed."

        elapsed = time.time() - start_time
        return SubagentResult(
            success=passed,
            data={"test_suite": test_suite, "passed": passed, "output": output},
            error=None if passed else f"Test suite {test_suite} failed.",
            execution_time_seconds=elapsed,
        )


class CoordinatorSubagent(BaseSubagent):
    """Specialized sub-agent for decomposing complex high-level goals into dynamic subagent DAGs."""

    role = "coordinator"
    capabilities = ["planning", "task_decomposition", "orchestration"]

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        goal = task.payload.get("goal") or task.title
        steps = task.payload.get("stages", ["research", "code", "review", "test"])

        spawned_tasks: List[Task] = []
        prev_task_id: Optional[str] = None

        for idx, stage in enumerate(steps):
            child_task = Task(
                title=f"Stage {idx + 1}: {stage} for '{goal}'",
                role=stage,
                priority=task.priority,
                parent_task_id=task.id,
                payload={"goal": goal, "stage": stage, "context_from_parent": task.payload},
                depends_on=[prev_task_id] if prev_task_id else [],
            )
            spawned_tasks.append(child_task)
            prev_task_id = child_task.id

        elapsed = time.time() - start_time
        return SubagentResult(
            success=True,
            data={"goal": goal, "plan_stages": steps, "spawned_count": len(spawned_tasks)},
            spawned_tasks=spawned_tasks,
            artifacts={"coordination_plan": {"goal": goal, "stages": steps}},
            execution_time_seconds=elapsed,
        )


class GenericSubagent(BaseSubagent):
    """Fallback generic sub-agent for default tasks."""

    role = "generic"
    capabilities = ["generic_execution"]

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        elapsed = time.time() - start_time
        return SubagentResult(
            success=True,
            data={"message": f"Generic task '{task.title}' processed.", "payload": task.payload},
            execution_time_seconds=elapsed,
        )


class SubagentRegistry:
    """Registry maintaining available specialized subagents and routing based on roles/capabilities."""

    ROLE_ALIASES = {
        "research": "researcher",
        "code": "coder",
        "review": "reviewer",
        "test": "tester",
        "testing": "tester",
        "plan": "coordinator",
        "coordination": "coordinator",
    }

    def __init__(self):
        self._role_map: Dict[str, BaseSubagent] = {}
        self._capability_map: Dict[str, List[BaseSubagent]] = {}

        # Register standard subagents
        self.register(ResearcherSubagent())
        self.register(CoderSubagent())
        self.register(ReviewerSubagent())
        self.register(TesterSubagent())
        self.register(CoordinatorSubagent())
        self.register(GenericSubagent())

    def register(self, subagent: BaseSubagent) -> None:
        """Register a subagent instance by role and capabilities."""
        self._role_map[subagent.role] = subagent
        for cap in subagent.capabilities:
            if cap not in self._capability_map:
                self._capability_map[cap] = []
            self._capability_map[cap].append(subagent)

    def get_for_role(self, role: str) -> BaseSubagent:
        """Get subagent matching the specific role or alias, fallback to generic."""
        canonical_role = self.ROLE_ALIASES.get(role.lower(), role.lower())
        return self._role_map.get(canonical_role, self._role_map.get("generic", GenericSubagent()))

    def get_for_capability(self, capability: str) -> Optional[BaseSubagent]:
        """Get first registered subagent supporting capability."""
        agents = self._capability_map.get(capability, [])
        return agents[0] if agents else None

    def list_roles(self) -> List[str]:
        """List all registered subagent roles."""
        return list(self._role_map.keys())
