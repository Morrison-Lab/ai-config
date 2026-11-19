"""Decide whether the Codex CLI may be used for the current project.

The lab's UCDH Codex plan is scoped to UCDH projects only: the `bcs` and
`hac` groups on any forge (Ezra, 2026-10-03; memories/delegation.md and
shared/workflow/standing-habits-from-ezra.md).  Any tool that would pick
Codex on its own, such as pre-push-review.py's `auto` and `alternate`
engines, asks this function first (ai-config#5084).
"""

import os
import re
import subprocess
from typing import Optional

# A UCDH remote: `ucdavis/bcs*` or `ucdavis/hac*` on GitHub, or any project on
# the UCDH GitLab (`hc2-gitlab.ucdmc.ucdavis.edu`), which hosts the `bcs` and
# `health-analytics-core` (hac) groups.
UCDH_REMOTE_PATTERN = re.compile(
    r"(?:[/:]ucdavis/(?:bcs|hac)[\w.-]*(?:\.git)?/?$)"
    r"|(?:hc2-gitlab\.ucdmc\.ucdavis\.edu[/:])",
    re.IGNORECASE,
)

OVERRIDE_ENV = "AI_CONFIG_ALLOW_CODEX"


def codex_allowed(repo_dir: str = ".", remote_url: Optional[str] = None) -> bool:
    """Return True when Codex may run for the project at repo_dir.

    `AI_CONFIG_ALLOW_CODEX=1` allows and `=0` refuses, overriding the
    inference.  Otherwise the origin remote URL must name a UCDH group.
    An unreadable remote refuses, so an unknown project never reaches Codex.
    """
    override = os.environ.get(OVERRIDE_ENV, "").strip()
    if override in ("1", "0"):
        return override == "1"
    if remote_url is None:
        res = subprocess.run(
            ["git", "-C", repo_dir, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return False
        remote_url = res.stdout.strip()
    return bool(UCDH_REMOTE_PATTERN.search(remote_url))
