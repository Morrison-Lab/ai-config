#!/usr/bin/env python3
"""Wire a repository so every agent that opens it finds ai-config's rules.

Usage: wire-repo-config.py [--check] [--enable-plugin] REPO_DIR [REPO_DIR ...]

User-level wiring (scripts/wire-user-config.py, run by bootstrap.sh, and the
claude.ai account plugin sync) covers the surfaces the user controls. A
repository also gets opened where neither reaches: a teammate's checkout,
Codex cloud, Copilot's coding agent, Jules, Cursor background agents. This
writes what those surfaces read from the repository itself (ai-config#4206):

  AGENTS.md              a marked block pointing every agent at ai-config's
                         AGENTS.md, appended to the repo's own file (or a new
                         file holding only the block).
  CLAUDE.md              the same block, when the repo has a CLAUDE.md that
                         does not import AGENTS.md: Claude Code reads only
                         CLAUDE.md when one exists.
  .claude/settings.json  registers the Morrison-Lab marketplace, so Claude
                         Code offers the plugin to anyone who trusts the repo.
  .Rbuildignore          in an R package (a DESCRIPTION at the root), anchored
                         entries for the top-level paths above, so
                         `R CMD check` raises no "non-standard files" NOTE.
                         Existing patterns that already match a path are kept
                         and nothing is added for it.

The plugin itself is enabled in the repo only with `--enable-plugin`. Where
the account sync or a user-level enable already loads it, a second,
project-enabled copy fires every hook twice -- the case wire-user-config.py
refuses -- so a repo opts in only when its sessions are known to lack both.

Every merge keeps what is there. An existing marketplace entry is kept, an
`ai-config@*` entry already in `enabledPlugins` is the repo's own choice, and
a block is replaced in place between its markers rather than duplicated (an
unterminated block is an error, not a second copy). ai-config itself, or any
directory inside it, is refused, since it loads its own files.

`--check` writes nothing and exits 1 when any repo is unwired.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from ai_config_wiring import (  # noqa: E402
    MARKETPLACE, MARKETPLACE_SOURCE, PLUGIN, is_ai_config, splice_block)
from fences import strip_fences  # noqa: E402
from plugin_overlap import ai_config_entries  # noqa: E402

BEGIN = "<!-- ai-config:begin (managed by Morrison-Lab/ai-config scripts/wire-repo-config.py) -->"
END = "<!-- ai-config:end -->"
BLOCK = f"""{BEGIN}
## Cross-project agent rules (ai-config)

This repository follows the maintainer's cross-project agent rules in
[Morrison-Lab/ai-config](https://github.com/Morrison-Lab/ai-config).
If your harness has not already loaded them (Claude Code loads them through
the ai-config plugin), read
[AGENTS.md](https://github.com/Morrison-Lab/ai-config/blob/main/AGENTS.md)
before starting work, and follow it alongside this file.
This file's own instructions add to those rules, and win only where they are
more specific.
{END}
"""


# A Claude Code import: `@AGENTS.md` or `@./AGENTS.md` at the start of a line
# (an import inside a code span or fence is not read as one, so fenced
# blocks are stripped before matching).
IMPORTS_AGENTS = re.compile(r"^@(?:\./)?AGENTS\.md\s*$", re.MULTILINE)


def load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:
        raise SystemExit(f"error: {path} is not valid JSON: {err}")
    if not isinstance(settings, dict):
        raise SystemExit(f"error: {path} is not a JSON object")
    return settings


def settings_change(repo: Path, enable_plugin: bool) -> tuple[str, dict | None]:
    """(message, new settings or None when nothing to write)."""
    settings = load_settings(repo / ".claude" / "settings.json")
    markets = settings.get("extraKnownMarketplaces")
    if markets is not None and not isinstance(markets, dict):
        raise SystemExit("error: extraKnownMarketplaces is not a JSON object")
    explicit = ai_config_entries(settings)
    want_market = MARKETPLACE not in (markets or {})
    want_plugin = enable_plugin and not explicit
    if not want_market and not want_plugin:
        state = ", ".join(f"{k}={v}" for k, v in sorted(explicit.items())) or "not enabled here"
        return f"ok    .claude/settings.json registers {MARKETPLACE} (plugin: {state})", None
    done = []
    if want_market:
        settings.setdefault("extraKnownMarketplaces", {})[MARKETPLACE] = {
            "source": MARKETPLACE_SOURCE}
        done.append(f"register {MARKETPLACE}")
    if want_plugin:
        enabled = settings.get("enabledPlugins")
        if enabled is not None and not isinstance(enabled, dict):
            raise SystemExit("error: enabledPlugins is not a JSON object")
        settings.setdefault("enabledPlugins", {})[PLUGIN] = True
        done.append(f"enable {PLUGIN}")
    return f"write .claude/settings.json: {', '.join(done)}", settings


def block_change(repo: Path, name: str) -> tuple[str, str | None]:
    path = repo / name
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if BLOCK in current:
        return f"ok    {name} already points at ai-config", None
    # An unclosed fence runs to end of file (CommonMark), so swallow it too.
    outside_code = strip_fences(current, swallow_unclosed=True)
    if name == "CLAUDE.md" and (not current or IMPORTS_AGENTS.search(outside_code)):
        return f"ok    {name} absent or imports AGENTS.md; nothing to add", None
    try:
        updated = splice_block(current, BLOCK, BEGIN, END)
    except ValueError as err:
        raise SystemExit(f"error: {path}: {err}")
    verb = "refresh" if BEGIN in current else ("new file with" if not current else "append")
    return f"write {name}: {verb} the ai-config block", updated


# Top-level paths this script writes or appends to; an R package must keep them
# out of its build, or R CMD check reports them as non-standard files.
WIRED_PATHS = ("AGENTS.md", "CLAUDE.md", ".claude")


def rbuildignore_matches(patterns: list[str], path: str) -> bool:
    """True when an .Rbuildignore pattern excludes `path`.

    R reads each line as a Perl regex matched case-insensitively against the
    path relative to the package root; Python's `re` agrees on every pattern
    an .Rbuildignore realistically carries. A pattern `re` cannot compile is
    skipped rather than treated as a match, so the worst case is a redundant
    entry, never a missing one.
    """
    for pattern in patterns:
        try:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def rbuildignore_change(repo: Path, will_exist: set[str]) -> tuple[str, str | None]:
    """Anchored entries for the wired paths an R package does not yet ignore."""
    if not (repo / "DESCRIPTION").is_file():
        return "ok    .Rbuildignore not needed (no DESCRIPTION)", None
    path = repo / ".Rbuildignore"
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    patterns = [line.strip() for line in current.splitlines() if line.strip()]
    missing = [name for name in WIRED_PATHS
               if name in will_exist and not rbuildignore_matches(patterns, name)]
    if not missing:
        return "ok    .Rbuildignore already excludes the wired files", None
    sep = "" if not current or current.endswith("\n") else "\n"
    added = "".join(f"^{re.escape(name)}$\n" for name in missing)
    return f"write .Rbuildignore: exclude {', '.join(missing)}", current + sep + added


def wire(repo: Path, check: bool, enable_plugin: bool) -> bool:
    """Wire one repo. Returns True when it was already fully wired."""
    if is_ai_config(repo.resolve()):
        print(f"{repo}: skip  ai-config loads its own rules")
        return True
    settings_msg, settings = settings_change(repo, enable_plugin)
    docs = [block_change(repo, name) for name in ("AGENTS.md", "CLAUDE.md")]
    will_exist = {name for name, (_, text) in zip(("AGENTS.md", "CLAUDE.md"), docs)
                  if text is not None or (repo / name).exists()}
    if settings is not None or (repo / ".claude").exists():
        will_exist.add(".claude")
    ignore_msg, ignore = rbuildignore_change(repo, will_exist)
    for msg in (settings_msg, *(m for m, _ in docs), ignore_msg):
        if check and msg.startswith("write"):
            msg = "todo" + msg[len("write"):]
        print(f"{repo}: {msg}")
    already_wired = (settings is None and ignore is None
                     and all(text is None for _, text in docs))
    if check:
        return already_wired
    if settings is not None:
        path = repo / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    for name, (_, text) in zip(("AGENTS.md", "CLAUDE.md"), docs):
        if text is not None:
            (repo / name).write_text(text, encoding="utf-8")
    if ignore is not None:
        (repo / ".Rbuildignore").write_text(ignore, encoding="utf-8")
    return already_wired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report only; exit 1 when any repo is unwired")
    parser.add_argument("--enable-plugin", action="store_true",
                        help="also enable ai-config@Morrison-Lab in the repo's settings")
    parser.add_argument("repos", nargs="+", type=Path)
    args = parser.parse_args(argv)
    all_wired = True
    for repo in args.repos:
        if not repo.is_dir():
            raise SystemExit(f"error: {repo} is not a directory")
        all_wired = wire(repo, args.check, args.enable_plugin) and all_wired
    return 1 if args.check and not all_wired else 0


if __name__ == "__main__":
    sys.exit(main())
