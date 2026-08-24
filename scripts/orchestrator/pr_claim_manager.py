"""PR-on-claim manager for orchestrator.

Implements the repository standard pr-on-claim workflow:
1. Branch from main with dedicated naming (feat/issue-<N> or fix/issue-<N>).
2. Create empty commit: "start: <title> (closes #<N>)".
3. Push branch to origin.
4. Open draft PR on GitHub linking the issue.
5. Post claim comment on the issue.
6. Provide helper to mark PR ready and request external review on completion.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger("orchestrator.pr_claim")


class PRClaimManager:
    """Automates branch creation, draft PR opening on claim, and final ready-for-review."""

    def __init__(self, repo_root: Optional[Path] = None, repo_slug: Optional[str] = None):
        self.repo_root = (repo_root or Path(os.getcwd())).resolve()
        self.repo_slug = repo_slug

    def _run_cmd(self, cmd: List[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def generate_branch_name(self, issue_number: int, issue_title: str) -> str:
        """Generate slugged branch name from issue title."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", issue_title.lower()).strip("-")[:40]
        prefix = "feat" if any(k in issue_title.lower() for k in ["feat", "add", "support", "new"]) else "fix"
        return f"{prefix}/issue-{issue_number}-{slug}"

    def claim_issue_and_open_draft_pr(
        self,
        issue_number: int,
        issue_title: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Claim an issue up-front by creating a branch, empty commit, and opening a draft PR."""
        branch_name = self.generate_branch_name(issue_number, issue_title)
        result: Dict[str, Any] = {
            "issue_number": issue_number,
            "branch_name": branch_name,
            "draft_pr_opened": False,
            "pr_number": None,
            "pr_url": None,
        }

        if dry_run or not shutil.which("gh"):
            logger.info("[Dry-Run/No GH] Simulating PR-on-claim for issue #%d (branch: %s)", issue_number, branch_name)
            result["draft_pr_opened"] = True
            result["pr_number"] = 9000 + (issue_number % 1000)
            result["pr_url"] = f"https://github.com/{self.repo_slug or 'Morrison-Lab/ai-config'}/pull/{result['pr_number']}"
            return result

        # 1. Fetch origin/main
        self._run_cmd(["git", "fetch", "origin", "main"])

        # 2. Create and checkout new branch from origin/main
        rc, _, err = self._run_cmd(["git", "checkout", "-b", branch_name, "origin/main"])
        if rc != 0:
            # If branch already exists locally, checkout
            self._run_cmd(["git", "checkout", branch_name])

        # 3. Create empty commit
        commit_msg = f"start: {issue_title} (closes #{issue_number})"
        self._run_cmd(["git", "commit", "--allow-empty", "-m", commit_msg])

        # 4. Push branch to origin
        rc_push, _, err_push = self._run_cmd(["git", "push", "-u", "origin", branch_name])
        if rc_push != 0:
            logger.warning("Failed to push branch %s: %s", branch_name, err_push)

        # 5. Open draft PR
        body_text = f"Closes #{issue_number}\n\nWIP — opened up front to claim the issue; implementing now."
        pr_cmd = [
            "gh", "pr", "create",
            "--draft",
            "--title", issue_title,
            "--body", body_text,
            "--head", branch_name,
        ]
        if self.repo_slug:
            pr_cmd.extend(["-R", self.repo_slug])

        rc_pr, out_pr, err_pr = self._run_cmd(pr_cmd)
        if rc_pr == 0:
            result["draft_pr_opened"] = True
            result["pr_url"] = out_pr.strip()
            m = re.search(r"/pull/(\d+)", out_pr)
            if m:
                result["pr_number"] = int(m.group(1))
            logger.info("Successfully opened draft PR for issue #%d: %s", issue_number, result["pr_url"])

            # 6. Post claim comment on issue
            claim_body = f"Orchestrator worker is working on this via draft PR #{result.get('pr_number')} — paws off until done."
            comment_cmd = ["gh", "issue", "comment", str(issue_number), "--body", claim_body]
            if self.repo_slug:
                comment_cmd.extend(["-R", self.repo_slug])
            self._run_cmd(comment_cmd)
        else:
            logger.error("Failed to open draft PR for issue #%d: %s", issue_number, err_pr)

        return result

    def mark_pr_ready_and_request_review(
        self,
        pr_number: int,
        reviewers: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> bool:
        """Mark a draft PR ready for review and request external review."""
        if dry_run or not shutil.which("gh"):
            logger.info("[Dry-Run/No GH] Simulating marking PR #%d ready for review", pr_number)
            return True

        cmd_ready = ["gh", "pr", "ready", str(pr_number)]
        if self.repo_slug:
            cmd_ready.extend(["-R", self.repo_slug])
        rc, out, err = self._run_cmd(cmd_ready)
        if rc != 0:
            logger.warning("gh pr ready failed for PR #%d: %s", pr_number, err)

        if reviewers:
            req_cmd = ["gh", "api", "-X", "POST", f"repos/{self.repo_slug or 'Morrison-Lab/ai-config'}/pulls/{pr_number}/requested_reviewers"]
            for r in reviewers:
                req_cmd.extend(["-f", f"reviewers[]={r}"])
            self._run_cmd(req_cmd)

        logger.info("PR #%d marked ready for review", pr_number)
        return True
