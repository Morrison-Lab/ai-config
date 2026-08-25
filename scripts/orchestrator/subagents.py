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


CANDIDATE_FILE_REGEX = re.compile(
    r"(?:(?<=^)|(?<=[\s`'\",;:]))((?:[a-zA-Z0-9_.\-]+/[a-zA-Z0-9_.\-/]+\.[a-zA-Z0-9_]+|[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_]+|\.[a-zA-Z0-9_\-]+))(?=[,\s`'\":;.]|$)"
)
STUB_PATTERNS = ("...", "# ...", "// ...", "pass", "/* same */", "# same", "/* ... */", "-- ...")


def is_bare_path_line(s: str) -> bool:
    """Return True if string is a normalized repo-relative path, dotfile, or bare filename."""
    clean = s.replace("\\", "/").strip("`'\" \t\r\n")
    while clean.startswith("./") or clean.startswith("/"):
        if clean.startswith("./"):
            clean = clean[2:]
        elif clean.startswith("/"):
            clean = clean[1:]
    if not clean:
        return False
    # Pure numeric or version numbers (e.g. 1.0.0, 3.14) are not file paths
    if re.match(r"^\d+(?:\.\d+)+$", clean):
        return False
    # Domain names with no directory slash (e.g. example.com) are not file paths
    if "/" not in clean and re.search(r"\.(?:com|org|net|io|dev|ai|edu|gov|mil|info|biz|me|app|xyz)$", clean, re.IGNORECASE):
        return False
    # Must not contain code syntax characters or whitespace
    if any(c in clean for c in " \t()[]{}=:;,<>\"'\\"):
        return False
    parts = clean.split("/")
    filename = parts[-1]
    # Dotfiles (e.g. .gitignore, .env, .eslintrc) or files with extension (.py, .vue, .proto, .mdc, .service, etc.)
    if filename.startswith(".") and len(filename) > 1:
        if all(re.match(r"^[a-zA-Z0-9_.\-]+$", p) for p in parts):
            return True
    elif "." in filename:
        ext = filename.split(".")[-1].lower()
        stem = ".".join(filename.split(".")[:-1])
        # If no directory prefix, exclude numeric stems to avoid version collisions; with directory prefix, any valid extension is fine
        if ("/" in clean or not stem.isdigit()) and 1 <= len(ext) <= 12 and re.match(r"^[a-zA-Z0-9]+$", ext):
            if all(re.match(r"^[a-zA-Z0-9_.\-]+$", p) for p in parts):
                return True
    return False


def is_stub_or_self_referential(content: str, cand_path: str = "") -> bool:
    """Return True if content is a placeholder stub, echoes file paths, or is a list of bare path strings."""
    clean_content = content.strip()
    if not clean_content:
        return True

    lines = [line.strip() for line in clean_content.splitlines() if line.strip()]
    if not lines:
        return True

    # Build candidate variants for path checking
    cand_variants = set()
    if cand_path:
        clean_cand = cand_path.strip("`'\" \t\r\n").replace("\\", "/")
        cand_basename = clean_cand.split("/")[-1]
        cand_variants = {
            clean_cand,
            cand_basename,
            f"/{clean_cand}",
            f"./{clean_cand}",
            clean_cand.lstrip("./"),
        }

    def _is_single_token_stub_or_path(tok: str) -> bool:
        t = tok.strip("`'\" \t\r\n")
        if not t or t.lower() in ("and", "&"):
            return True
        if t in STUB_PATTERNS:
            return True
        if is_bare_path_line(t):
            return True
        if t in cand_variants or t.lstrip("./") in cand_variants:
            return True
        return False

    def _is_single_line_stub_or_path(raw_line: str) -> bool:
        line_clean = raw_line.strip()
        if not line_clean:
            return True
        # Strip leading comment markers (#, //, --, /*), bullet markers (*, - with whitespace), or list markers (1., 1), a., a) with whitespace)
        uncommented = re.sub(r"^(?:(?:#+|//|--|/\*+)\s*|(?:[\*\-]\s+)|(?:[a-zA-Z]|\d+)[.)]\s+)", "", line_clean)
        uncommented = re.sub(r"\s*\*+/$", "", uncommented).strip("`'\" \t\r\n")
        if not uncommented:
            return True
        if uncommented in STUB_PATTERNS or line_clean in STUB_PATTERNS:
            return True
        if is_bare_path_line(uncommented):
            return True
        if uncommented in cand_variants or uncommented.lstrip("./") in cand_variants:
            return True
        # If line contains separators (, or ;), split into tokens and check if all tokens are paths/stubs
        if "," in uncommented or ";" in uncommented:
            tokens = [t.strip() for t in re.split(r"[,;]", uncommented) if t.strip()]
            if tokens and all(_is_single_token_stub_or_path(t) for t in tokens):
                return True
        return False

    # Return True if ALL non-empty lines are stubs, comments, or bare file paths
    return all(_is_single_line_stub_or_path(line) for line in lines)


def find_candidate_file_paths(text: str) -> List[str]:
    """Extract candidate repo-relative file paths mentioned in a text block."""
    paths: List[str] = []
    for raw in CANDIDATE_FILE_REGEX.findall(text):
        cleaned = raw.strip("`'\" \t\r\n").replace("\\", "/")
        if (
            "." in cleaned
            and not (cleaned == ".git" or cleaned.startswith((".git/", "http://", "https://")))
            and cleaned not in paths
            and is_bare_path_line(cleaned)
        ):
            paths.append(cleaned)
    return paths


def resolve_within_worktree(rel_path: str, wt_path: Path, wt_resolved: Optional[Path] = None) -> Optional[Path]:
    """Resolve rel_path within wt_path and return Path if strictly contained within wt_path (excluding root), else None."""
    wt_root = wt_resolved if wt_resolved is not None else wt_path.resolve()
    clean_str = str(rel_path).replace("\\", "/").lstrip("/")
    clean_rel = Path(clean_str)
    if clean_rel.is_absolute():
        clean_rel = Path(*clean_rel.parts[1:])
    file_path = (wt_path / clean_rel).resolve()
    if file_path == wt_root or not file_path.is_relative_to(wt_root):
        return None
    return file_path


def extract_files_from_markdown(text: str, context_text: str = "", default_target_file: str = "") -> Dict[str, str]:
    """Extract (file_path, content) pairs from markdown code blocks, ignoring stub/self-referential blocks."""
    files: Dict[str, str] = {}
    pattern = re.compile(r"(?:(?:###?\s+(?:File:\s*)?|File:\s*|Path:\s*)[`'\"]?([a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+)[`'\"]?\s*\n\s*)?```([^\n]*)\n(.*?)```", flags=re.DOTALL)

    for match in pattern.finditer(text):
        preceding_cand, header, content = match.groups()
        found_path = ""

        # 1. Check tokens in header (e.g. ```python scripts/foo.py or ```scripts/foo.py)
        parts = header.strip().split()
        for p in reversed(parts):
            cand = p.strip("`'\" \t\r\n").replace("\\", "/")
            if "." in cand and not cand.startswith(("http://", "https://")) and is_bare_path_line(cand):
                found_path = cand
                break

        # 2. Check preceding markdown header (e.g. ### File: CLAUDE.md)
        if not found_path and preceding_cand:
            cand = preceding_cand.strip("`'\" \t\r\n").replace("\\", "/")
            if is_bare_path_line(cand):
                found_path = cand

        # 3. Check first line of content (e.g. # File: scripts/foo.py or // scripts/foo.py or <!-- CLAUDE.md -->)
        if not found_path and content:
            first_line = content.splitlines()[0].strip()
            # Match common comment path headers
            m = re.match(r"^(?:#+|//|--|/\*+|<!--)\s*(?:File:\s*|Path:\s*)?[`'\"]?([a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+)[`'\"]?(?:\s*\*+/|\s*-->)?$", first_line)
            if m:
                cand = m.group(1).strip("`'\" \t\r\n").replace("\\", "/")
                if is_bare_path_line(cand):
                    found_path = cand

        if found_path and not is_stub_or_self_referential(content, found_path):
            files[found_path] = content

    # Fallback: if no path header found, but valid non-stub code blocks exist
    if not files:
        blocks = re.findall(r"```([^\n]*)\n(.*?)```", text, flags=re.DOTALL)
        if blocks:
            first_block_content = blocks[0][1]
            if not is_stub_or_self_referential(first_block_content, ""):
                if default_target_file:
                    clean_default = default_target_file.strip("`'\" \t\r\n").replace("\\", "/")
                    if not is_stub_or_self_referential(first_block_content, clean_default):
                        files[clean_default] = first_block_content
                elif context_text:
                    candidates = find_candidate_file_paths(context_text)
                    if candidates and not any(is_stub_or_self_referential(first_block_content, c) for c in candidates):
                        files[candidates[0]] = first_block_content

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
        push_remote = task.payload.get("push_remote", False)

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
                wt_resolved = wt_path.resolve()
                files_to_write: Dict[str, str] = {}

                # 1. If explicit file and content provided, use directly
                if target_file and code_content:
                    files_to_write[target_file] = code_content
                else:
                    # 2. Locate existing candidate files in worktree to provide context
                    combined_context = f"{instruction}\n{issue_body}\n{task.payload.get('context_from_parent', '')}"
                    candidate_paths = find_candidate_file_paths(combined_context)
                    existing_context_blocks: List[str] = []

                    max_context_files = task.payload.get("max_context_files", 3)
                    max_context_lines_per_file = task.payload.get("max_context_lines", 400)
                    max_total_context_lines = task.payload.get("max_total_context_lines", 800)
                    total_lines_injected = 0

                    sorted_candidates = sorted(
                        candidate_paths,
                        key=lambda p: (0 if "/" in p and not p.startswith(("CLAUDE.", "AGENTS.")) else (2 if p in ("CLAUDE.md", "AGENTS.md", "README.md") else 1)),
                    )
                    for rel in sorted_candidates[:max_context_files]:
                        if total_lines_injected >= max_total_context_lines:
                            break
                        file_path = resolve_within_worktree(rel, wt_path, wt_resolved)
                        if file_path is None:
                            logger.warning("Skipping candidate path escaping worktree root: %s", rel)
                            continue
                        if file_path.is_file():
                            try:
                                cur_content = file_path.read_text(encoding="utf-8", errors="replace")
                                ext = file_path.suffix.lstrip(".") or "text"
                                cur_lines = cur_content.splitlines()
                                remaining_budget = max_total_context_lines - total_lines_injected
                                allowed_lines = min(max_context_lines_per_file, remaining_budget)
                                snippet = "\n".join(cur_lines[:allowed_lines])
                                if len(cur_lines) > allowed_lines:
                                    snippet += f"\n\n# ... ({len(cur_lines) - allowed_lines} remaining lines omitted) ...\n# Note: `{rel}` is a large file ({len(cur_lines)} lines). If modifying `{rel}`, use search/replace blocks:\n# <<<<<<< SEARCH\n# <exact lines to find>\n# =======\n# <replacement lines>\n# >>>>>>> REPLACE"
                                existing_context_blocks.append(f"Current content of `{rel}`:\n````{ext}\n{snippet}\n````")
                                total_lines_injected += min(len(cur_lines), allowed_lines)
                            except Exception as exc:
                                logger.warning("Failed to read candidate context file %s: %s", rel, exc)

                    context_str = "\n\n".join(existing_context_blocks)

                    # 3. Invoke generative AI model to synthesize solution
                    adapter, model_name = self.model_router.route_task(
                        tier=TaskTier.STANDARD_CODE,
                        retry_count=task.retry_count,
                    )
                    result_data["model_used"] = model_name

                    coder_prompt = (
                        f"Implement a complete, working solution for the following issue:\n"
                        f"Title: {instruction}\n"
                        f"Description:\n{issue_body}\n\n"
                    )
                    if context_str:
                        coder_prompt += f"{context_str}\n\n"
                    coder_prompt += (
                        f"Requirements:\n"
                        f"- Write complete, production-ready code with no omitted sections or placeholders.\n"
                        f"- Output each modified or new file in a markdown code block with the relative file path on the opening line, e.g.:\n"
                        f"```scripts/foo.py\n"
                        f"# complete file content here\n"
                        f"```\n"
                    )

                    resp = adapter.invoke(
                        prompt=coder_prompt,
                        system_prompt=AIConfigProtocols.get_coder_prompt(),
                        model=model_name,
                        timeout_seconds=300,
                    )

                    if not resp.success or not resp.content:
                        return SubagentResult(
                            success=False,
                            data=result_data,
                            error=f"Model code generation failed ({model_name}): {resp.error}",
                            execution_time_seconds=time.time() - start_time,
                        )

                    extracted = extract_files_from_markdown(
                        resp.content,
                        context_text=f"{instruction}\n{issue_body}",
                        default_target_file=target_file,
                    )
                    if extracted:
                        files_to_write.update(extracted)

                # Fail-fast if model produced no valid code modifications
                if not files_to_write:
                    return SubagentResult(
                        success=False,
                        data=result_data,
                        error=f"Model code generation failed: no valid file modifications produced by {result_data.get('model_used')}.",
                        execution_time_seconds=time.time() - start_time,
                    )

                # Pass 1: Validate all target files (path escape + destructive truncation on model output)
                validated_edits: List[Tuple[Path, str, str]] = []
                is_model_output = (result_data.get("model_used") != "direct_input")
                min_truncation_orig_lines = task.payload.get("min_truncation_orig_lines", 20)
                min_truncation_floor_lines = task.payload.get("min_truncation_floor_lines", 5)
                truncation_ratio = task.payload.get("truncation_ratio", 0.30)

                for rel_path, content in files_to_write.items():
                    file_path = resolve_within_worktree(rel_path, wt_path, wt_resolved)
                    if file_path is None:
                        return SubagentResult(
                            success=False,
                            data=result_data,
                            error=f"Security error: target_file '{rel_path}' escapes worktree root {wt_path}",
                            execution_time_seconds=time.time() - start_time,
                        )

                    # Destructive truncation guard on model-generated outputs
                    if is_model_output and file_path.is_file():
                        orig_text = file_path.read_text(encoding="utf-8", errors="replace")
                        orig_lines = len(orig_text.splitlines())
                        new_lines = len(content.splitlines())
                        if orig_lines > min_truncation_orig_lines and new_lines < max(min_truncation_floor_lines, int(orig_lines * truncation_ratio)):
                            return SubagentResult(
                                success=False,
                                data=result_data,
                                error=(
                                    f"Destructive truncation detected for '{rel_path}': "
                                    f"attempted to replace {orig_lines}-line file with {new_lines}-line stub. "
                                    f"Failing fast to trigger tier escalation."
                                ),
                                execution_time_seconds=time.time() - start_time,
                            )
                    validated_edits.append((file_path, rel_path, content))

                # Pass 2: Write all validated files
                total_lines = 0
                for file_path, rel_path, content in validated_edits:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")
                    total_lines += len(content.splitlines())

                result_data["lines_changed"] = total_lines
                result_data["files_modified"] = [rel for _, rel, _ in validated_edits]
                result_data["applied"] = bool(validated_edits)

                # Stage and commit
                subprocess.run(["git", "add", "."], cwd=str(wt_path), capture_output=True, check=False)
                commit_proc = subprocess.run(
                    ["git", "commit", "-m", f"fix: {instruction[:60]}"],
                    cwd=str(wt_path),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
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
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                    )
                    if push_proc.returncode != 0:
                        err_msg = push_proc.stderr.strip() or f"git push exited with code {push_proc.returncode}"
                        return SubagentResult(
                            success=False,
                            data=result_data,
                            error=f"Git push failed from worktree to origin/{branch_name}: {err_msg}",
                            execution_time_seconds=time.time() - start_time,
                        )
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
                subprocess.run(
                    ["git", "fetch", "origin", branch_name],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=False,
                )
                proc = subprocess.run(
                    ["git", "diff", f"origin/main...origin/{branch_name}"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    diff = proc.stdout
                else:
                    # Fallback to local ref if present
                    local_proc = subprocess.run(
                        ["git", "diff", f"origin/main...{branch_name}"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=30,
                        check=False,
                    )
                    if local_proc.returncode == 0 and local_proc.stdout.strip():
                        diff = local_proc.stdout
            except Exception:
                pass

        # Fail-fast if no diff found to review
        if not diff.strip() and not dry_run:
            return SubagentResult(
                success=False,
                data={
                    "verdict": "BLOCKED",
                    "findings": [{"level": "ERROR", "message": f"No implementation diff found to review (branch: '{branch_name or 'none'}')."}],
                    "model_used": "empty-diff-check",
                },
                error=f"Empty implementation diff to review (branch: '{branch_name or 'none'}').",
                execution_time_seconds=time.time() - start_time,
            )

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
            else:
                verdict = "BLOCKED"
                is_clean = False
                findings.append({"level": "ERROR", "message": f"Adversarial reviewer model invocation failed: {resp.error or 'Empty response'}"})

        # Post adversarial review comment to GitHub PR if pr_number is in payload
        pr_number = task.payload.get("pr_number")
        repo_slug = task.payload.get("repo_slug")
        if pr_number and not dry_run and shutil.which("gh"):
            try:
                cmd_pr = ["gh", "pr", "comment", str(pr_number)]
                if repo_slug:
                    cmd_pr.extend(["-R", repo_slug])
                if is_clean:
                    review_body = (
                        f"## Orchestrator Subagent Self-Review Report\n\n"
                        f"### Verdict\n\n"
                        f"**Ready for merge**\n\n"
                        f"Independent subagent adversarial review (`{model_used}`) verified:\n"
                        f"- Implementation diff audited against repository standards and security guidelines.\n"
                        f"- Clean verdict issued with 0 blocking findings.\n\n"
                        f"_Posted by Claude Code (AI agent) --- not written by a human._\n"
                    )
                else:
                    findings_summary = "\n".join(f"- {f.get('level', 'WARN')}: {f.get('message', '')}" for f in findings)
                    review_body = (
                        f"## Orchestrator Subagent Self-Review Report\n\n"
                        f"### Verdict\n\n"
                        f"**Needs more work**\n\n"
                        f"Independent subagent adversarial review (`{model_used}`) identified findings:\n"
                        f"{findings_summary}\n\n"
                        f"_Posted by Claude Code (AI agent) --- not written by a human._\n"
                    )
                cmd_pr.extend(["--body", review_body])
                proc = subprocess.run(cmd_pr, capture_output=True, text=True, check=False, timeout=30)
                if proc.returncode != 0:
                    logger.warning("Failed to post adversarial review comment to PR #%s (exit %d): %s", pr_number, proc.returncode, proc.stderr.strip())
            except Exception as exc:
                logger.warning("Failed to post adversarial review comment to PR #%s: %s", pr_number, exc)

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
            env = {**os.environ, "PYTHONUTF8": "1"}
            for cmd_str in test_commands:
                try:
                    proc = subprocess.run(
                        cmd_str,
                        shell=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=120,
                        check=False,
                        env=env,
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
                    encoding="utf-8",
                    errors="replace",
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
        pr_merged = False
        mwc = task.payload.get("mwc")
        if mwc is None:
            mwc = AIConfigProtocols.check_repo_allows_mwc(repo_slug=repo_slug)

        if passed and pr_number and (has_real_diff or dry_run):
            pr_marked_ready = self.pr_claim_mgr.mark_pr_ready_and_request_review(
                pr_number=pr_number,
                reviewers=["the repository owner"],
                repo_slug=repo_slug,
                dry_run=dry_run,
            )
            # Under active mwc authorization, auto-merge when ready & quality gates are green
            if mwc and pr_marked_ready:
                pr_merged = self.pr_claim_mgr.merge_pr_under_mwc(
                    pr_number=pr_number,
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
                "pr_merged": pr_merged,
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
                    "mwc": task.payload.get("mwc"),
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
