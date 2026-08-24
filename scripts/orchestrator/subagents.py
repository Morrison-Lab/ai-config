"""Specialized sub-agents and subagent registry for the orchestration loop."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from .model_adapters import BaseModelAdapter, ModelProvider, ModelRouter, TaskTier
from .models import SubagentContext, SubagentResult, Task, TaskPriority, TaskStatus
from .pr_claim_manager import PRClaimManager
from .protocols import AIConfigProtocols
from .worktree_manager import WorktreeManager

logger = logging.getLogger("orchestrator.subagents")


def extract_files_from_markdown(text: str) -> Dict[str, str]:
    """Extract (file_path, content) pairs from markdown code blocks."""
    files: Dict[str, str] = {}
    # Matches ```path/to/file.ext\n<content>\n``` or ```python path/to/file.ext\n<content>\n```
    pattern = r"```(?:[a-zA-Z0-9_\-]+)?\s*([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_]+)\n(.*?)```"
    matches = re.findall(pattern, text, flags=re.DOTALL)
    for path_str, content in matches:
        clean_path = path_str.strip()
        # Avoid treating language names as filenames
        if "." in clean_path and not clean_path.startswith("http"):
            files[clean_path] = content

    return files


class BaseSubagent(ABC):
    """Abstract base class for all specialized sub-agents conforming to AIConfig protocols."""

    role: str = "generic"
    capabilities: List[str] = []

    def get_system_prompt(self) -> str:
        """Return the repository-standard system prompt for this subagent role."""
        return AIConfigProtocols.get_prompt_for_role(self.role)

    @abstractmethod
    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        """Execute the assigned task within the provided context."""
        raise NotImplementedError


class ResearcherSubagent(BaseSubagent):
    """Specialized sub-agent for research, file surveys, and documentation analysis."""

    role = "researcher"
    capabilities = ["search", "survey", "code_reading", "doc_analysis"]

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        query = task.payload.get("title") or task.payload.get("query") or task.title
        body = task.payload.get("body", "")
        target_path = task.payload.get("target_path", "")
        dry_run = task.payload.get("dry_run", False)

        # Check for pre-existing or direct path match
        file_matches = []
        if target_path and os.path.exists(target_path):
            file_matches.append(target_path)

        # Search workspace for relevant files
        ws_root = Path(context.workspace_root or os.getcwd())
        candidate_files = []
        for sub_dir in ["scripts", "hooks", "skills", "memories"]:
            d = ws_root / sub_dir
            if d.exists():
                for f in list(d.rglob("*.py"))[:10] + list(d.rglob("*.md"))[:10]:
                    rel = str(f.relative_to(ws_root)).replace("\\", "/")
                    candidate_files.append(rel)

        file_list_summary = "\n".join(f"- {f}" for f in candidate_files[:30])

        prompt = (
            f"Research and investigate the following issue for resolution:\n"
            f"Issue Title: {query}\n"
            f"Issue Description:\n{body}\n\n"
            f"Relevant repository structure:\n{file_list_summary}\n\n"
            f"Provide:\n"
            f"1. Problem analysis and root cause.\n"
            f"2. List of files that need to be changed.\n"
            f"3. Concrete implementation plan."
        )

        analysis = f"Completed research investigation for '{query}'."
        model_used = "mock-researcher"

        if not dry_run:
            adapter, model_name = self.model_router.route_task(
                tier=TaskTier.LOCAL_FAST,
                retry_count=task.retry_count,
            )
            resp = adapter.invoke(
                prompt=prompt,
                system_prompt=AIConfigProtocols.get_researcher_prompt(),
                model=model_name,
                timeout_seconds=90,
            )
            if resp.success and resp.content:
                analysis = resp.content
                model_used = resp.model_used

        findings: Dict[str, Any] = {
            "query": query,
            "target_path": target_path,
            "analysis": analysis,
            "model_used": model_used,
            "matches": file_matches or candidate_files[:5],
        }

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

    def __init__(
        self,
        model_router: Optional[ModelRouter] = None,
        worktree_manager: Optional[WorktreeManager] = None,
    ):
        self.model_router = model_router or ModelRouter()
        self.worktree_manager = worktree_manager or WorktreeManager()

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        instruction = task.payload.get("title") or task.payload.get("instruction") or task.title
        issue_body = task.payload.get("body", "")
        target_file = task.payload.get("target_file", "")
        code_content = task.payload.get("code_content", "")
        use_worktree = task.payload.get("use_worktree", True)
        branch_name = task.payload.get("branch_name")
        dry_run = task.payload.get("dry_run", False)
        push_remote = task.payload.get("push_remote", True)

        result_data: Dict[str, Any] = {
            "instruction": instruction,
            "target_file": target_file,
            "applied": False,
            "committed": False,
            "pushed": False,
            "lines_changed": 0,
            "model_used": "direct_input" if code_content else None,
        }

        if dry_run:
            result_data["applied"] = True
            result_data["committed"] = True
            result_data["pushed"] = True
            return SubagentResult(
                success=True,
                data=result_data,
                artifacts={"code_patch": {"target": target_file, "content": code_content}},
                execution_time_seconds=time.time() - start_time,
            )

        if not use_worktree or not branch_name:
            if not target_file and not code_content:
                result_data["applied"] = True
                return SubagentResult(
                    success=True,
                    data=result_data,
                    execution_time_seconds=time.time() - start_time,
                )
            return SubagentResult(
                success=False,
                data=result_data,
                error="Worktree and branch_name are required for safe isolated code generation.",
                execution_time_seconds=time.time() - start_time,
            )

        try:
            persist_branch = task.payload.get("persist_branch", True)
            with self.worktree_manager.isolated_worktree(
                task_id=task.id,
                branch_name=branch_name,
                cleanup=task.payload.get("cleanup_worktree", True),
                delete_branch=not persist_branch,
            ) as wt_path:
                files_to_write: Dict[str, str] = {}

                # 1. If explicit file and content provided, use directly
                if target_file and code_content:
                    files_to_write[target_file] = code_content
                else:
                    # 2. Invoke generative AI model to synthesize solution
                    adapter, model_name = self.model_router.route_task(
                        tier=TaskTier.STANDARD_CODE,
                        retry_count=task.retry_count,
                    )
                    result_data["model_used"] = model_name

                    coder_prompt = (
                        f"Implement a complete, working solution for the following issue:\n"
                        f"Title: {instruction}\n"
                        f"Description:\n{issue_body}\n\n"
                        f"Requirements:\n"
                        f"- Write complete, production-ready code with no omitted sections or placeholders.\n"
                        f"- Output each modified or new file in a markdown code block with the relative file path on the opening line, e.g.:\n"
                        f"```scripts/foo.py\n"
                        f"# file content here\n"
                        f"```\n"
                    )

                    resp = adapter.invoke(
                        prompt=coder_prompt,
                        system_prompt=AIConfigProtocols.get_coder_prompt(),
                        model=model_name,
                        timeout_seconds=180,
                    )

                    if not resp.success or not resp.content:
                        return SubagentResult(
                            success=False,
                            data=result_data,
                            error=f"Model code generation failed ({model_name}): {resp.error}",
                            execution_time_seconds=time.time() - start_time,
                        )

                    extracted = extract_files_from_markdown(resp.content)
                    if extracted:
                        files_to_write.update(extracted)
                    elif target_file:
                        files_to_write[target_file] = resp.content

                # Write files into worktree with path validation
                total_lines = 0
                wt_resolved = wt_path.resolve()
                for rel_path, content in files_to_write.items():
                    clean_rel = Path(rel_path)
                    if clean_rel.is_absolute():
                        clean_rel = Path(*clean_rel.parts[1:])
                    file_path = (wt_path / clean_rel).resolve()
                    if not file_path.is_relative_to(wt_resolved):
                        return SubagentResult(
                            success=False,
                            data=result_data,
                            error=f"Security error: target_file '{rel_path}' escapes worktree root {wt_path}",
                            execution_time_seconds=time.time() - start_time,
                        )
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")
                    total_lines += len(content.splitlines())

                result_data["lines_changed"] = total_lines
                result_data["files_modified"] = list(files_to_write.keys())
                result_data["applied"] = bool(files_to_write)

                # Stage and commit
                if files_to_write:
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

                    # Push branch to remote origin
                    if push_remote:
                        push_proc = subprocess.run(
                            ["git", "push", "-u", "origin", branch_name],
                            cwd=str(wt_path),
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if push_proc.returncode != 0:
                            logger.warning("Git push failed from worktree: %s", push_proc.stderr)
                        else:
                            result_data["pushed"] = True

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
            artifacts={"code_patch": {"files": list(files_to_write.keys()), "lines": total_lines}},
            execution_time_seconds=elapsed,
        )


class ReviewerSubagent(BaseSubagent):
    """Specialized sub-agent for adversarial review, linting, and quality verification."""

    role = "reviewer"
    capabilities = ["adversarial_review", "code_review", "security_check"]

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        diff = task.payload.get("diff", "")
        branch_name = task.payload.get("branch_name")
        author_family = task.payload.get("author_family", "claude")
        dry_run = task.payload.get("dry_run", False)

        # If diff not in payload, read from git branch
        if not diff and branch_name and not dry_run:
            try:
                proc = subprocess.run(
                    ["git", "diff", "origin/main...HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if proc.returncode == 0:
                    diff = proc.stdout
            except Exception:
                pass

        findings: List[Dict[str, Any]] = []
        is_clean = True

        # Fast static checks
        if "eval(" in diff or "exec(" in diff:
            findings.append({"level": "ERROR", "message": "Potentially unsafe dynamic execution detected."})
            is_clean = False

        verdict = "CLEAN" if is_clean else "BLOCKED"
        model_used = "static-rules"

        # Model-based adversarial review
        if is_clean and diff and not dry_run:
            adapter, model_name = self.model_router.route_task(
                tier=TaskTier.ADVERSARIAL_REVIEW,
                prior_author_model=author_family,
                retry_count=task.retry_count,
            )
            model_used = model_name
            review_prompt = (
                f"Perform rigorous adversarial code review against repository standards:\n\n"
                f"Diff:\n{diff[:4000]}\n\n"
                f"Verify:\n"
                f"1. Correctness and logic.\n"
                f"2. Edge cases and error handling.\n"
                f"3. Strict security and no command injections.\n"
                f"4. Output format: verdict (CLEAN, NEEDS_WORK, or BLOCKED) followed by concise findings."
            )
            resp = adapter.invoke(
                prompt=review_prompt,
                system_prompt=AIConfigProtocols.get_reviewer_prompt(),
                model=model_name,
                timeout_seconds=90,
            )
            if resp.success and resp.content:
                if "BLOCKED" in resp.content.upper() or "NEEDS_WORK" in resp.content.upper():
                    verdict = "NEEDS_WORK"
                    is_clean = False
                    findings.append({"level": "WARN", "message": resp.content[:300]})

        elapsed = time.time() - start_time
        return SubagentResult(
            success=is_clean,
            data={"verdict": verdict, "findings": findings, "model_used": model_used},
            artifacts={"review_report": {"verdict": verdict, "findings": findings}},
            execution_time_seconds=elapsed,
        )


class TesterSubagent(BaseSubagent):
    """Specialized sub-agent for running verification tests and capturing diagnostic output."""

    role = "tester"
    capabilities = ["run_tests", "benchmarking", "diagnostics"]

    def __init__(
        self,
        pr_claim_manager: Optional[PRClaimManager] = None,
        repo_slug: Optional[str] = None,
    ):
        self.repo_slug = repo_slug
        self.pr_claim_mgr = pr_claim_manager or PRClaimManager(repo_slug=repo_slug)

    def execute(self, task: Task, context: SubagentContext) -> SubagentResult:
        start_time = time.time()
        test_suite = task.payload.get("test_suite", "default")
        expected_assertions = task.payload.get("expected_assertions", 1)
        pr_number = task.payload.get("pr_number")
        branch_name = task.payload.get("branch_name")
        repo_slug = task.payload.get("repo_slug") or self.repo_slug
        dry_run = task.payload.get("dry_run", False)

        test_commands = task.payload.get("test_commands")
        if test_commands is None:
            if task.payload.get("stage") == "test_verification" or pr_number:
                test_commands = ["python scripts/validate-skills.py", "python scripts/check-links.py"]
            else:
                test_commands = []
        passed = task.payload.get("mock_failure", False) is False
        output_logs = []

        # Run real quality gate checks if not in dry-run mode
        if not dry_run and passed:
            for cmd_str in test_commands:
                try:
                    proc = subprocess.run(
                        cmd_str,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                    )
                    if proc.returncode != 0:
                        passed = False
                        output_logs.append(f"FAILED: {cmd_str}\n{proc.stderr}")
                        break
                    else:
                        output_logs.append(f"PASSED: {cmd_str}")
                except Exception as exc:
                    passed = False
                    output_logs.append(f"ERROR executing {cmd_str}: {exc}")
                    break

        output = f"Executed suite {test_suite} ({len(test_commands)} quality gate checks): {'PASSED' if passed else 'FAILED'}."

        # Verify non-empty implementation diff before un-drafting PR
        has_real_diff = True
        if not dry_run and branch_name:
            try:
                diff_proc = subprocess.run(
                    ["git", "diff", f"origin/main...origin/{branch_name}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if diff_proc.returncode == 0 and not diff_proc.stdout.strip():
                    has_real_diff = False
                    output += " [Warning: Branch diff is empty; draft PR will not be un-drafted]."
            except Exception:
                pass

        # Only promote PR if tests passed AND branch contains real implementation diff
        pr_marked_ready = False
        if passed and pr_number and (has_real_diff or dry_run):
            pr_marked_ready = self.pr_claim_mgr.mark_pr_ready_and_request_review(
                pr_number=pr_number,
                reviewers=["d-morrison"],
                repo_slug=repo_slug,
                dry_run=dry_run,
            )

        elapsed = time.time() - start_time
        return SubagentResult(
            success=passed,
            data={
                "test_suite": test_suite,
                "passed": passed,
                "output": output,
                "quality_gates": test_commands,
                "has_real_diff": has_real_diff,
                "pr_marked_ready": pr_marked_ready,
            },
            error=None if passed else f"Test suite {test_suite} failed: {'; '.join(output_logs)}",
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
                payload={
                    "goal": goal,
                    "stage": stage,
                    "dry_run": task.payload.get("dry_run", False),
                    "context_from_parent": task.payload,
                },
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

    def __init__(
        self,
        model_router: Optional[ModelRouter] = None,
        worktree_manager: Optional[WorktreeManager] = None,
        pr_claim_manager: Optional[PRClaimManager] = None,
        repo_slug: Optional[str] = None,
    ):
        self.model_router = model_router or ModelRouter()
        self.worktree_manager = worktree_manager or WorktreeManager()
        self.pr_claim_mgr = pr_claim_manager or PRClaimManager(repo_slug=repo_slug)

        self._role_map: Dict[str, BaseSubagent] = {}
        self._capability_map: Dict[str, List[BaseSubagent]] = {}

        # Register standard subagents with shared router and managers
        self.register(ResearcherSubagent(model_router=self.model_router))
        self.register(CoderSubagent(model_router=self.model_router, worktree_manager=self.worktree_manager))
        self.register(ReviewerSubagent(model_router=self.model_router))
        self.register(TesterSubagent(pr_claim_manager=self.pr_claim_mgr, repo_slug=repo_slug))
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
