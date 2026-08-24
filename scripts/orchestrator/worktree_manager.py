"""Worktree isolation and lifecycle manager for orchestrator subagents."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Generator, Optional

logger = logging.getLogger(__name__)


class WorktreeManager:
    """Manages creation, execution context, and cleanup of isolated git worktrees."""

    def __init__(self, repo_root: Optional[Path] = None, worktree_parent: Optional[Path] = None):
        self.repo_root = (repo_root or Path(os.getcwd())).resolve()
        self.worktree_parent = (
            worktree_parent or (self.repo_root / ".worktrees")
        ).resolve()

    def _run_git(self, args: list[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
        cmd = ["git"] + args
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def create_worktree(
        self,
        task_id: str,
        branch_name: Optional[str] = None,
        base_ref: str = "HEAD",
    ) -> Path:
        """Create an isolated worktree for a task under .worktrees/<sanitized_id>."""
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_id)
        worktree_path = self.worktree_parent / f"task_{safe_id}"
        target_branch = branch_name or f"task/{safe_id}"

        self.worktree_parent.mkdir(parents=True, exist_ok=True)

        # If worktree already exists, remove it first
        if worktree_path.exists():
            self.remove_worktree(worktree_path, force=True)

        # Create worktree with a dedicated branch
        rc, out, err = self._run_git(
            ["worktree", "add", "-b", target_branch, str(worktree_path), base_ref]
        )
        if rc != 0:
            # Fallback without -b if branch exists
            rc2, out2, err2 = self._run_git(
                ["worktree", "add", str(worktree_path), target_branch]
            )
            if rc2 != 0:
                # Detached head worktree fallback
                rc3, out3, err3 = self._run_git(
                    ["worktree", "add", "--detach", str(worktree_path), base_ref]
                )
                if rc3 != 0:
                    raise RuntimeError(
                        f"Failed to create worktree at {worktree_path}: {err}; {err2}; {err3}"
                    )

        logger.info("Created isolated worktree at %s for task %s", worktree_path, task_id)
        return worktree_path

    def remove_worktree(
        self,
        worktree_path: Path,
        delete_branch: Optional[str] = None,
        force: bool = True,
    ) -> bool:
        """Remove a git worktree and clean up residual directories."""
        if not worktree_path.exists():
            return True

        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))

        rc, out, err = self._run_git(args)
        if rc != 0:
            logger.warning("git worktree remove failed: %s; falling back to prune", err)
            self._run_git(["worktree", "prune"])

        # Clean residual folder if still on disk
        if worktree_path.exists():
            try:
                shutil.rmtree(worktree_path, ignore_errors=True)
            except Exception as exc:
                logger.warning("Failed to rmtree %s: %s", worktree_path, exc)

        self._run_git(["worktree", "prune"])

        if delete_branch:
            self._run_git(["branch", "-D", delete_branch])

        logger.info("Cleaned up worktree at %s", worktree_path)
        return True

    def cleanup_stale_worktrees(self) -> int:
        """Prune and clean all orphaned worktrees in .worktrees/."""
        cleaned = 0
        self._run_git(["worktree", "prune"])
        if not self.worktree_parent.exists():
            return cleaned

        for child in self.worktree_parent.iterdir():
            if child.is_dir() and child.name.startswith("task_"):
                self.remove_worktree(child, force=True)
                cleaned += 1

        self._run_git(["worktree", "prune"])
        return cleaned

    @contextmanager
    def isolated_worktree(
        self,
        task_id: str,
        branch_name: Optional[str] = None,
        base_ref: str = "HEAD",
        cleanup: bool = True,
    ) -> Generator[Path, None, None]:
        """Context manager creating a dedicated worktree and ensuring cleanup on exit."""
        wt_path = self.create_worktree(task_id, branch_name=branch_name, base_ref=base_ref)
        try:
            yield wt_path
        finally:
            if cleanup:
                self.remove_worktree(wt_path, force=True)
