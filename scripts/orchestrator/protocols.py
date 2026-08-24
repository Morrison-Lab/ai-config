"""Repository and work-rule protocol definitions for orchestrator subagents.

Encodes the Morrison-Lab / ai-config cross-agent universal contract (AGENTS.md)
so all orchestrator subagents adhere to repository standards:
- Issue-first & PR-on-claim (open draft PR on claim with empty commit)
- Worktree isolation (never touch main checkout)
- Commit message formatting (type(scope): message closes #N)
- Check remote before pushing with lease & if-includes
- Adversarial self-review with cross-model independence
- Quality gates verification before un-drafting PR
- Strict merge control policy
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional


class AIConfigProtocols:
    """Provides system prompts, guidelines, and quality gates conforming to AGENTS.md."""

    UNIVERSAL_SYSTEM_PROMPT = """You are an AI subagent operating within Morrison-Lab/ai-config.
You must strictly follow the repository work-rules defined in AGENTS.md:
1. WORKTREE ISOLATION: Always operate inside your assigned isolated git worktree. Never modify the main repo root directly.
2. PR-ON-CLAIM: An issue must have an open draft PR on claim before code changes.
3. FAIL-FAST: Never swallow errors into silent fallbacks. Fail fast with descriptive diagnostics.
4. ADVERSARIAL SELF-REVIEW: Review diffs independently using a distinct model family from the author.
5. QUALITY GATES: All changes must pass repo validators (validate-skills, check-links, test suites) before un-drafting.
6. SAFE PUSH: Always verify remote state before push and use --force-with-lease --force-if-includes.
7. STRICT MERGE POLICY: Never merge without explicit user permission under mwc/maw.
"""

    RESEARCHER_PROMPT = """Role: Researcher Subagent
Goal: Inspect the issue, survey existing codebase patterns, locate relevant files, and produce an actionable implementation plan.
Do not write code files to disk. Output a structured plan with target files, proposed changes, and test cases.
"""

    CODER_PROMPT = """Role: Coder Subagent
Goal: Implement the required fix or feature cleanly inside your isolated worktree.
Rules:
- Make precise, atomic edits preserving formatting and SemBr conventions.
- Stage and commit changes with conventional commit messages: `fix: <desc>` or `feat: <desc>`.
- Fail fast if tests or syntax checks fail.
"""

    REVIEWER_PROMPT = """Role: Adversarial Code Reviewer Subagent
Goal: Rigorously audit the proposed diff against repository standards and security guidelines.
Rules:
- Check for security issues, regressions, data-loss defaults, or unintended side effects.
- Verify that tests accompany any new functionality.
- Issue a CLEAN verdict only when all standards are satisfied; otherwise issue BLOCKED with concrete findings.
"""

    TESTER_PROMPT = """Role: Quality Gate & Verification Subagent
Goal: Run repository validation scripts and unit tests to ensure quality gates pass.
Rules:
- Execute `python scripts/validate-skills.py`, `python scripts/check-links.py`, and relevant unit tests.
- Only when all tests pass cleanly, mark the draft PR ready for review and request external review.
"""

    @classmethod
    def get_prompt_for_role(cls, role: str) -> str:
        prompts = {
            "researcher": cls.RESEARCHER_PROMPT,
            "coder": cls.CODER_PROMPT,
            "reviewer": cls.REVIEWER_PROMPT,
            "tester": cls.TESTER_PROMPT,
        }
        base = cls.UNIVERSAL_SYSTEM_PROMPT
        specific = prompts.get(role, f"Role: {role.capitalize()} Subagent\nGoal: Execute task according to AGENTS.md.")
        return f"{base}\n---\n{specific}"

    @classmethod
    def get_researcher_prompt(cls) -> str:
        return cls.get_prompt_for_role("researcher")

    @classmethod
    def get_coder_prompt(cls) -> str:
        return cls.get_prompt_for_role("coder")

    @classmethod
    def get_reviewer_prompt(cls) -> str:
        return cls.get_prompt_for_role("reviewer")

    @classmethod
    def get_tester_prompt(cls) -> str:
        return cls.get_prompt_for_role("tester")

    @classmethod
    def get_repo_quality_gates(cls) -> List[str]:
        return [
            "python scripts/validate-skills.py",
            "python scripts/check-links.py",
            "python scripts/test_orchestrator.py",
        ]

    @classmethod
    def check_repo_allows_mwc(cls, repo_root: Optional[Path] = None, repo_slug: Optional[str] = None) -> bool:
        """Check if repository written policies grant standing mwc authorization.

        Evaluates:
        1. Explicit repo identity (Morrison-Lab/ai-config).
        2. Written policy files in repo root (AGENTS.md, CLAUDE.md, GEMINI.md) for standing permission / mwc grants.
        """
        if repo_slug and "ai-config" in repo_slug:
            return True

        root = (repo_root or Path.cwd()).resolve()
        for doc_name in ["AGENTS.md", "CLAUDE.md", "GEMINI.md"]:
            doc_path = root / doc_name
            if doc_path.exists():
                try:
                    content = doc_path.read_text(encoding="utf-8", errors="ignore")
                    if "standing permission" in content.lower() or "standing mwc" in content.lower() or "/mwc" in content.lower():
                        return True
                except Exception:
                    pass
        return False
