"""Decide whether the Codex CLI may be used for the current project.

The lab's UCDH Codex plan is scoped to UCDH projects only: the `bcs` and
`hac` groups, on GitHub or the UCDH GitLab (Ezra, 2026-10-03: "ucdh codex is
only for ucdh projects on any forge (bcs + hac)"; memories/delegation.md).
Any tool that would pick Codex on its own, such as pre-push-review.py's
`auto` and `alternate` engines, asks this function first (ai-config#5084).
"""

import os
import re
import subprocess
import urllib.parse
from typing import Optional, Tuple

# The UCDH GitLab, which hosts the `bcs` and `health-analytics-core` (hac) groups.
UCDH_GITLAB_HOST = "hc2-gitlab.ucdmc.ucdavis.edu"
# On the UCDH GitLab, a UCDH project sits in one of those two groups or a subgroup.
UCDH_GITLAB_PATH = re.compile(r"^(?:bcs|health-analytics-core)/[^/]", re.IGNORECASE)
# On github.com, a UCDH project is `ucdavis/bcs*` or `ucdavis/hac*`.
UCDH_GITHUB_PATH = re.compile(r"^ucdavis/(?:bcs|hac)[\w.-]*$", re.IGNORECASE)
# scp-like syntax: `[user@]host:path`, with no scheme.
SCP_LIKE = re.compile(r"^(?:[^@/:]+@)?([^/:]+):(.*)$")

OVERRIDE_ENV = "AI_CONFIG_ALLOW_CODEX"


def _host_and_path(url: str) -> Tuple[str, str]:
    """Split a git remote URL into (lowercase host, path without slashes or .git)."""
    if "://" in url:
        parts = urllib.parse.urlsplit(url)
        host, path = parts.hostname or "", parts.path
    else:
        m = SCP_LIKE.match(url)
        if not m:
            return "", ""
        host, path = m.group(1), m.group(2)
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    return host.lower(), path


def codex_allowed(repo_dir: str = ".", remote_url: Optional[str] = None) -> bool:
    """Return True when Codex may run for the project at repo_dir.

    `AI_CONFIG_ALLOW_CODEX=1` allows and `=0` refuses, overriding the
    inference.  Otherwise the origin remote must be a UCDH project: one in the
    `bcs` or `health-analytics-core` group on the UCDH GitLab, or
    `ucdavis/bcs*` / `ucdavis/hac*` on github.com.
    An unreadable remote refuses, so an unknown project never reaches Codex.
    """
    override = os.environ.get(OVERRIDE_ENV, "").strip()
    if override in ("1", "0"):
        return override == "1"
    if remote_url is None:
        try:
            res = subprocess.run(
                ["git", "-C", repo_dir, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return False
        if res.returncode != 0:
            return False
        remote_url = res.stdout.strip()
    host, path = _host_and_path(remote_url)
    if host == UCDH_GITLAB_HOST:
        return bool(UCDH_GITLAB_PATH.match(path))
    return host == "github.com" and bool(UCDH_GITHUB_PATH.match(path))
