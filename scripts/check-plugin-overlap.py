#!/usr/bin/env python3
"""Report ai-config installs that stack: symlink + plugin, or plugin + plugin.

The detection itself lives in `scripts/lib/plugin_overlap.py`, which explains
the two overlap defects and why each one costs context (ai-config#1409). This
wrapper decides *which* settings files to read and *whether* the bare-name
symlink install is live, then prints whatever the library reports.

Run standalone, or let `bootstrap.sh` run it at the end of an install so the
warning lands at the moment the second install route is created. Advisory by
design: it always exits 0, because an overlap is a configuration to tidy
rather than a build failure, and a blocking form would break `bootstrap.sh`
on exactly the machines it is trying to help.

Settings files examined:

  * `<consumer-dir>/settings.json` and `settings.local.json` -- the user
    scope, where `/plugin install` writes its `enabledPlugins` entry;
  * `./.claude/settings.json` and `settings.local.json` under the current
    working directory -- the project scope, where a consumer repo's
    checked-in marketplace block lives (the sparta case in ai-config#1409).

Claude Code also merges an enterprise scope this script does not look for;
per the library's docstring that blind spot under-reports rather than
inventing an overlap, and the output names the files actually read.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from plugin_overlap import describe_overlap  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def symlink_install_live(consumer_dir: Path, repo_root: Path) -> bool:
    """True when the consumer dir serves this repo's skills under bare names.

    Two shapes count, mirroring the two ways `bootstrap.sh` installs:
    `<consumer>/skills` is itself a symlink resolving into the repo, or it is
    a real directory whose children include at least one entry resolving into
    the repo's `skills/` (the merged-install shape remote containers force).
    A consumer `skills/` holding only harness built-ins matches neither, so a
    plugin-only machine is not misreported as double-installed.
    """
    skills = consumer_dir / "skills"
    repo_skills = repo_root / "skills"
    if not skills.exists():
        return False
    try:
        if skills.is_symlink():
            return skills.resolve().is_relative_to(repo_root.resolve())
        return any(
            child.is_symlink()
            and child.resolve().is_relative_to(repo_skills.resolve())
            for child in skills.iterdir()
        )
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--consumer-dir",
        default=os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude")),
        help="directory bootstrap.sh installs into (default: $CLAUDE_HOME or ~/.claude)",
    )
    parser.add_argument(
        "--repo-root", default=str(REPO_ROOT),
        help="ai-config checkout the symlinks should resolve into",
    )
    parser.add_argument(
        "--project-dir", default=".",
        help="working directory whose .claude/ project settings to include",
    )
    args = parser.parse_args()

    consumer_dir = Path(args.consumer_dir).expanduser()
    repo_root = Path(args.repo_root).resolve()
    project = Path(args.project_dir).resolve()

    paths = [
        consumer_dir / "settings.json",
        consumer_dir / "settings.local.json",
        project / ".claude" / "settings.json",
        project / ".claude" / "settings.local.json",
    ]
    live = symlink_install_live(consumer_dir, repo_root)
    lines = describe_overlap(paths, symlink_install_live=live)

    if lines:
        for line in lines:
            print(f"WARNING: {line}")
    else:
        examined = [p for p in paths if p.is_file()]
        print(f"plugin-overlap check: {len(examined)} settings file(s) examined, "
              f"symlink install {'live' if live else 'not live'}, no stacked "
              f"ai-config installs found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
