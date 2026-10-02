#!/usr/bin/env python3
"""Wire a repository so every agent that opens it loads ai-config.

Usage: wire-repo-config.py [--check] REPO_DIR [REPO_DIR ...]

User-level wiring (scripts/wire-user-config.py, run by bootstrap.sh) covers
the machines the user controls. A repository also gets opened where no user
config exists: a fresh claude.ai cloud container whose account plugin sync
has failed (ai-config#3948), a teammate's checkout, Codex cloud, Copilot's
coding agent, Jules, Cursor background agents. This writes the two files
those surfaces read from the repository itself (ai-config#4206):

  .claude/settings.json  registers the Morrison-Lab marketplace and enables
                         `ai-config@Morrison-Lab`, so any Claude Code session
                         in the repo installs the plugin -- skills, hooks, and
                         through hooks/inject-core-rules.py the AGENTS.md rules.
  AGENTS.md              a marked block pointing every other agent at
                         ai-config's AGENTS.md, appended to the repo's own
                         file (or a new file holding only the block).

Both merges keep what is there. An `ai-config@*` entry already present in
`enabledPlugins`, true or false, is the repo's own choice and is left alone,
and the AGENTS.md block is replaced in place between its markers rather than
duplicated. ai-config itself is refused, since it loads its own files.

`--check` writes nothing and exits 1 when any repo is unwired.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = "Morrison-Lab"
PLUGIN = f"ai-config@{MARKETPLACE}"
MARKETPLACE_SOURCE = {"source": "github", "repo": "Morrison-Lab/ai-config"}
BEGIN = "<!-- ai-config:begin (managed by Morrison-Lab/ai-config scripts/wire-repo-config.py) -->"
END = "<!-- ai-config:end -->"
BLOCK = f"""{BEGIN}
## Cross-project agent rules (ai-config)

This repository follows the maintainer's cross-project agent rules in
[Morrison-Lab/ai-config](https://github.com/Morrison-Lab/ai-config).
If your harness has not already loaded them (Claude Code loads them through
the `ai-config@Morrison-Lab` plugin enabled in `.claude/settings.json`), read
[AGENTS.md](https://github.com/Morrison-Lab/ai-config/blob/main/AGENTS.md)
before starting work, and follow it alongside this file.
Where the two conflict, the rule specific to this repository wins.
{END}
"""


def is_ai_config(repo: Path) -> bool:
    manifest = repo / ".claude-plugin" / "marketplace.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("name") == MARKETPLACE
    except (OSError, ValueError, AttributeError):
        return False


def settings_change(repo: Path) -> tuple[str, dict | None]:
    """(message, new settings or None when nothing to write)."""
    path = repo / ".claude" / "settings.json"
    if path.exists():
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as err:
            raise SystemExit(f"error: {path} is not valid JSON: {err}")
        if not isinstance(settings, dict):
            raise SystemExit(f"error: {path} is not a JSON object")
    else:
        settings = {}
    enabled = settings.get("enabledPlugins") or {}
    explicit = {k: v for k, v in enabled.items() if k.startswith("ai-config@")}
    known = (settings.get("extraKnownMarketplaces") or {}).get(MARKETPLACE)
    if explicit and (PLUGIN not in explicit or known is not None):
        state = ", ".join(f"{k}={v}" for k, v in sorted(explicit.items()))
        return f"ok    .claude/settings.json already decides ({state})", None
    settings.setdefault("extraKnownMarketplaces", {})[MARKETPLACE] = {
        "source": MARKETPLACE_SOURCE}
    settings.setdefault("enabledPlugins", {}).setdefault(PLUGIN, True)
    return "write .claude/settings.json: enable ai-config@Morrison-Lab", settings


def agents_change(repo: Path) -> tuple[str, str | None]:
    path = repo / "AGENTS.md"
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if BLOCK in current:
        return "ok    AGENTS.md already points at ai-config", None
    if BEGIN in current and END in current:
        head, rest = current.split(BEGIN, 1)
        tail = rest.split(END, 1)[1].lstrip("\n")
        return "write AGENTS.md: refresh the ai-config block", head + BLOCK + tail
    if not current:
        return "write AGENTS.md: new file with the ai-config block", BLOCK
    sep = "\n" if current.endswith("\n") else "\n\n"
    if current.endswith("\n\n"):
        sep = ""
    return "write AGENTS.md: append the ai-config block", current + sep + BLOCK


def wire(repo: Path, check: bool) -> bool:
    """Wire one repo. Returns True when it was already fully wired."""
    if is_ai_config(repo):
        print(f"{repo}: skip  ai-config loads its own rules")
        return True
    settings_msg, settings = settings_change(repo)
    agents_msg, agents = agents_change(repo)
    for msg in (settings_msg, agents_msg):
        if check and msg.startswith("write"):
            msg = "todo" + msg[len("write"):]
        print(f"{repo}: {msg}")
    if check:
        return settings is None and agents is None
    if settings is not None:
        path = repo / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    if agents is not None:
        (repo / "AGENTS.md").write_text(agents, encoding="utf-8")
    return settings is None and agents is None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report only; exit 1 when any repo is unwired")
    parser.add_argument("repos", nargs="+", type=Path)
    args = parser.parse_args(argv)
    all_wired = True
    for repo in args.repos:
        if not repo.is_dir():
            raise SystemExit(f"error: {repo} is not a directory")
        all_wired = wire(repo, args.check) and all_wired
    return 1 if args.check and not all_wired else 0


if __name__ == "__main__":
    sys.exit(main())
