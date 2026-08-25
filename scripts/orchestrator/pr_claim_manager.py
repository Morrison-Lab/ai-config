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

from .worktree_manager import WorktreeManager

logger = logging.getLogger("orchestrator.pr_claim")


class PRClaimManager:
    """Automates branch creation, draft PR opening on claim, and final ready-for-review."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        repo_slug: Optional[str] = None,
        worktree_manager: Optional[WorktreeManager] = None,
    ):
        self.repo_root = (repo_root or Path(os.getcwd())).resolve()
        self.repo_slug = repo_slug
        self.worktree_manager = worktree_manager or WorktreeManager(repo_root=self.repo_root)

    def _run_cmd(self, cmd: List[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or self.repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def get_effective_repo_slug(self, override_slug: Optional[str] = None) -> Optional[str]:
        """Resolve target repository slug dynamically from override, instance config, or git remote."""
        if override_slug:
            return override_slug
        if self.repo_slug:
            return self.repo_slug

        # Try resolving from git remote origin
        rc, out, _ = self._run_cmd(["git", "remote", "get-url", "origin"])
        if rc == 0 and out:
            # Match github.com:owner/repo.git or https://github.com/owner/repo.git
            m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", out)
            if m:
                return m.group(1)
        return None

    def generate_branch_name(self, issue_number: int, issue_title: str) -> str:
        """Generate slugged branch name from issue title."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", issue_title.lower()).strip("-")[:40]
        prefix = "feat" if any(k in issue_title.lower() for k in ["feat", "add", "support", "new"]) else "fix"
        return f"{prefix}/issue-{issue_number}-{slug}"

    def claim_issue_and_open_draft_pr(
        self,
        issue_number: int,
        issue_title: str,
        repo_slug: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Claim an issue up-front in an isolated worktree and open a draft PR."""
        branch_name = self.generate_branch_name(issue_number, issue_title)
        effective_repo = self.get_effective_repo_slug(repo_slug)
        result: Dict[str, Any] = {
            "issue_number": issue_number,
            "branch_name": branch_name,
            "draft_pr_opened": False,
            "pr_number": None,
            "pr_url": None,
            "repo_slug": effective_repo,
        }

        if dry_run or not shutil.which("gh"):
            logger.info("[Dry-Run/No GH] Simulating PR-on-claim for issue #%d (branch: %s)", issue_number, branch_name)
            result["draft_pr_opened"] = True
            result["pr_number"] = 9000 + (issue_number % 1000)
            repo_display = effective_repo or "Morrison-Lab/ai-config"
            result["pr_url"] = f"https://github.com/{repo_display}/pull/{result['pr_number']}"
            return result

        # 1. Fetch origin/main
        self._run_cmd(["git", "fetch", "origin", "main"])

        # 2. Use isolated worktree so main repo root is never mutated
        try:
            wt_path, _ = self.worktree_manager.create_worktree(
                task_id=f"claim_{issue_number}",
                branch_name=branch_name,
                base_ref="origin/main",
            )

            # 3. Create empty commit inside worktree
            commit_msg = f"start: {issue_title} (closes #{issue_number})"
            self._run_cmd(["git", "commit", "--allow-empty", "-m", commit_msg], cwd=wt_path)

            # 4. Push branch to origin
            rc_push, _, err_push = self._run_cmd(["git", "push", "-u", "origin", branch_name], cwd=wt_path)
            if rc_push != 0:
                logger.warning("Failed to push branch %s: %s", branch_name, err_push)

            # 5. Clean up temporary worktree, preserving the pushed branch
            self.worktree_manager.remove_worktree(wt_path, delete_branch=False)
        except Exception as exc:
            logger.error("Worktree error during claim for issue #%d: %s", issue_number, exc)
            return result

        # 6. Open draft PR using GitHub CLI
        body_text = f"Closes #{issue_number}\n\nWIP -- opened up front to claim the issue; implementing now."
        pr_cmd = [
            "gh", "pr", "create",
            "--draft",
            "--title", issue_title,
            "--body", body_text,
            "--head", branch_name,
        ]
        if effective_repo:
            pr_cmd.extend(["-R", effective_repo])

        rc_pr, out_pr, err_pr = self._run_cmd(pr_cmd)
        if rc_pr == 0:
            result["draft_pr_opened"] = True
            result["pr_url"] = out_pr.strip()
            m = re.search(r"/pull/(\d+)", out_pr)
            if m:
                result["pr_number"] = int(m.group(1))
            logger.info("Successfully opened draft PR for issue #%d: %s", issue_number, result["pr_url"])

            # 7. Post claim comment on issue
            # The trailing marker discloses agent authorship on every comment we
            # post, and is deliberately emoji-free: check-pr-fully-clean.py
            # matches the robot emoji as a review-body marker, so a claim
            # carrying it would scan as a finding-free review.
            # See shared/workflow/disclose-agent-authorship.md.
            claim_body = (
                f"Orchestrator worker is working on this via draft PR "
                f"#{result.get('pr_number')} -- please hold off until done."
                "\n\n_Posted by Claude Code (AI agent) --- not written by a human._"
            )
            comment_cmd = ["gh", "issue", "comment", str(issue_number), "--body", claim_body]
            if effective_repo:
                comment_cmd.extend(["-R", effective_repo])
            self._run_cmd(comment_cmd)
        else:
            logger.error("Failed to open draft PR for issue #%d: %s", issue_number, err_pr)

        return result

    def mark_pr_ready_and_request_review(
        self,
        pr_number: int,
        reviewers: Optional[List[str]] = None,
        repo_slug: Optional[str] = None,
        dry_run: bool = False,
    ) -> bool:
        """Mark a draft PR ready for review and request external review."""
        effective_repo = self.get_effective_repo_slug(repo_slug)
        if dry_run or not shutil.which("gh"):
            logger.info("[Dry-Run/No GH] Simulating marking PR #%d ready for review (repo: %s)", pr_number, effective_repo)
            return True

        cmd_ready = ["gh", "pr", "ready", str(pr_number)]
        if effective_repo:
            cmd_ready.extend(["-R", effective_repo])
        rc, out, err = self._run_cmd(cmd_ready)
        if rc != 0:
            logger.warning("gh pr ready failed for PR #%d: %s", pr_number, err)

        if reviewers:
            req_cmd = ["gh", "api", "-X", "POST"]
            if effective_repo:
                req_cmd.append(f"repos/{effective_repo}/pulls/{pr_number}/requested_reviewers")
            else:
                req_cmd.append(f"repos/:owner/:repo/pulls/{pr_number}/requested_reviewers")
            for r in reviewers:
                req_cmd.extend(["-f", f"reviewers[]={r}"])
            self._run_cmd(req_cmd)

        logger.info("PR #%d marked ready for review", pr_number)
        return True

    def is_pr_fully_clean(self, pr_number: int, repo_slug: Optional[str] = None) -> tuple[bool, str]:
        """Check if PR has 100% clean CI checks and an approved / clean review verdict."""
        effective_repo = self.get_effective_repo_slug(repo_slug)
        cmd = ["gh", "pr", "view", str(pr_number), "--json", "statusCheckRollup,reviews,comments,author,headRefOid"]
        if effective_repo:
            cmd.extend(["-R", effective_repo])

        rc, out, err = self._run_cmd(cmd)
        if rc != 0:
            return False, f"Failed to query PR #{pr_number} metadata: {err}"

        try:
            data = json.loads(out)
        except Exception as exc:
            return False, f"Failed to parse PR #{pr_number} JSON: {exc}"

        # 1. Check CI statusCheckRollup
        checks = data.get("statusCheckRollup", [])
        for chk in checks:
            name = chk.get("name") or chk.get("context", "unknown")
            status = chk.get("status")
            conclusion = (chk.get("conclusion") or chk.get("state") or "").upper()
            if status != "COMPLETED":
                return False, f"Check '{name}' is still in progress (status={status})"
            if conclusion not in ["SUCCESS", "SKIPPED", "NEUTRAL"]:
                return False, f"Check '{name}' failed with conclusion={conclusion}"

        # 3. Check for changes requested across all GitHub reviews
        reviews = data.get("reviews", [])
        has_changes_requested = any(r.get("state") in ["CHANGES_REQUESTED", "DISMISSED"] for r in reviews)
        if has_changes_requested:
            return False, "PR has CHANGES_REQUESTED review"

        # 4. Check for formal GitHub review approvals (from trusted OWNER/MEMBER humans or approved bots)
        # Stale reviews (commit != headRefOid), random passerby approvals, or self-reviews are strictly ignored!
        head_oid = data.get("headRefOid", "")
        pr_author_login = (data.get("author") or {}).get("login", "")
        trusted_reviews = [
            r for r in reviews
            if r.get("state") == "APPROVED"
            and (r.get("authorAssociation") in ["OWNER", "MEMBER"]
                 or (r.get("author") or {}).get("login") in ["claude", "claude[bot]", "d-morrison"])
            and (r.get("author") or {}).get("login") not in [pr_author_login, "dem-extra1"]
            and (not head_oid or not (r.get("commit") or {}).get("oid") or (r.get("commit") or {}).get("oid") == head_oid)
        ]
        has_approved_review = bool(trusted_reviews)

        comments = data.get("comments", [])
        claude_reviews = [
            c for c in comments
            if (c.get("author") or {}).get("login") in ["github-actions", "claude", "claude[bot]"]
            and ("claude finished review" in c.get("body", "").lower()
                 or "**claude finished" in c.get("body", "").lower())
        ]
        if not (has_approved_review or claude_reviews):
            return False, "No independent approved external review or GitHub approval found on PR"

        if claude_reviews:
            body = claude_reviews[-1].get("body", "")
            lower_body = (
                body.lower()
                .replace("\u2014", "--")
                .replace("\u2013", "--")
            )

            # Per fully-clean.md: anchor on the last `### Verdict` heading in the comment
            if "### verdict" in lower_body:
                verdict_section = lower_body.rsplit("### verdict", 1)[-1]
            elif "verdict:" in lower_body:
                verdict_section = lower_body.rsplit("verdict:", 1)[-1]
            else:
                verdict_section = lower_body

            # 1. Check for not-clean / blocking patterns in the verdict section
            not_clean_patterns = [
                r"\bneeds\s+(?:(?!no\b|nothing\b|none\b)\w+\s+){0,3}work\b",
                r"verdict:\s*(?:ready after addressing findings|changes requested|actionable findings|block(?:ed|ing)?|needs\s+more\s+work)",
                r"\bchanges\s+requested\b",
                r"\bblocked\s+on\s+human\s+review\b",
                r"\b(?:not|isn't|cannot\s+be|can't\s+be|nowhere\s+near|far\s+from)\s+(?:\w+\s+){0,2}(?:clean|approved|ready|lgtm)\b",
                r"\b(?:unapproved|rejected|deadlock|impasse)\b",
                r"\bfinding\s+(?:\d+\s+)?\(blocking\)",
                r"\bno\s+action\s+--\s+pr\s+is\s+(?:closed|merged)\b",
            ]
            not_clean_negation_prefix = re.compile(r"\b(?:no|not|nothing|none|never)\s+(?:\w+\s+){0,2}$", re.IGNORECASE)

            for pat in not_clean_patterns:
                for match in re.finditer(pat, verdict_section, re.IGNORECASE | re.MULTILINE):
                    prefix = verdict_section[max(0, match.start() - 25):match.start()]
                    if not_clean_negation_prefix.search(prefix):
                        continue
                    return False, f"Latest AI review has blocking verdict ('{match.group(0)}')"

            # 2. Check for positive clean / approved verdict patterns in the verdict section
            clean_patterns = [
                r"\bready\s+for\s+merge\b",
                r"\bapproved\s+for\s+merge\b",
                r"\bclean\s*/\s*approved\b",
                r"\bclean(?!-)\b",
                r"\bapproved\b",
                r"verdict:\s*(?:clean(?!-)|approved|ready)\b",
            ]
            bare_clean_patterns = {
                r"\bready\s+for\s+merge\b",
                r"\bapproved\s+for\s+merge\b",
                r"\bclean\s*/\s*approved\b",
                r"\bclean(?!-)\b",
                r"\bapproved\b",
            }
            bare_clean_marked = re.compile(
                r"(?:^|\n)[ \t]*(?:[#>*_+-]+[ \t]*)*(?:verdict[ \t]*[:.\-]*[ \t]*)?(?:[#>*_]+[ \t]*)*$",
                re.IGNORECASE,
            )
            clean_negation_prefix = re.compile(
                r"\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't|almost|nearly"
                r"|nowhere\s+near|close\s+to|far\s+from)\s+(?:\w+\s+){0,2}$",
                re.IGNORECASE,
            )
            clean_qualifier = re.compile(
                r"\b(?:once|after|when|if|unless|pending|provided|assuming"
                r"|subject\s+to|as\s+soon\s+as|contingent|but|however|except|though|although"
                r"|aside\s+from|other\s+than|apart\s+from|save\s+for|modulo|barring)\b",
                re.IGNORECASE,
            )

            has_clean_verdict = False
            for pat in clean_patterns:
                for match in re.finditer(pat, verdict_section, re.IGNORECASE | re.MULTILINE):
                    if pat in bare_clean_patterns:
                        line_start = verdict_section.rfind("\n", 0, match.start()) + 1
                        line_prefix = verdict_section[line_start:match.start()]
                        if not bare_clean_marked.search(line_prefix):
                            continue
                        prefix = verdict_section[max(0, match.start() - 40):match.start()]
                        if clean_negation_prefix.search(prefix):
                            continue
                    remainder = verdict_section[match.end():min(len(verdict_section), match.end() + 60)]
                    remainder_sentence = re.split(r"[.!?]|\n[ \t]*\n", remainder)[0]
                    if clean_qualifier.search(remainder_sentence):
                        continue
                    has_clean_verdict = True
                    break
                if has_clean_verdict:
                    break

            if not has_clean_verdict:
                return False, "Latest AI review does not contain a recognized positive clean/approved verdict"

        return True, "PR is fully clean across CI and review"

    def merge_pr_under_mwc(
        self,
        pr_number: int,
        repo_slug: Optional[str] = None,
        dry_run: bool = False,
    ) -> bool:
        """Merge a PR using squash and delete-branch under active mwc authorization once fully clean."""
        effective_repo = self.get_effective_repo_slug(repo_slug)
        if dry_run or not shutil.which("gh"):
            logger.info("[Dry-Run/No GH] Simulating merge of PR #%d under mwc (repo: %s)", pr_number, effective_repo)
            return True

        # Verify PR is fully clean across CI and review before executing merge
        is_clean, reason = self.is_pr_fully_clean(pr_number, repo_slug=effective_repo)
        if not is_clean:
            logger.warning("Cannot merge PR #%d under mwc: %s", pr_number, reason)
            return False

        merge_cmd = ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"]
        if effective_repo:
            merge_cmd.extend(["-R", effective_repo])

        rc, out, err = self._run_cmd(merge_cmd)
        if rc == 0:
            logger.info("Successfully merged PR #%d under mwc", pr_number)
            return True
        else:
            logger.warning("Failed to merge PR #%d under mwc: %s", pr_number, err)
            return False
