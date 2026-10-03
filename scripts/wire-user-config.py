#!/usr/bin/env python3
"""Wire ai-config into every agent's user-level config on this machine.

`bootstrap.sh` calls this. Each agent has its own user-global entry point,
and before ai-config#4206 none of them was set, so a session in any repo
other than ai-config saw the rules only if that repo happened to carry its
own wiring:

  Claude Code   ~/.claude/settings.json -- registers the Morrison-Lab
                marketplace and enables `ai-config@Morrison-Lab`, so the CLI,
                the desktop app and Remote Control sessions load the plugin
                (skills, hooks, and through hooks/inject-core-rules.py the
                AGENTS.md rules) in every project.
  Codex         $CODEX_HOME/AGENTS.md (default ~/.codex) -- Codex's
                user-global instruction file, linked to this checkout's
                AGENTS.md.
  Gemini CLI    ~/.gemini/GEMINI.md -- a marked block importing
                `@./ai-config-AGENTS.md`, a link beside it to this
                checkout's AGENTS.md (an import stays inside ~/.gemini).
  opencode      ~/.config/opencode/opencode.json -- this checkout's AGENTS.md
                in `instructions` (only when opencode is installed).

Every step is idempotent and conservative:

  - An explicit user choice wins. Any `ai-config@*` entry already present in
    `enabledPlugins` is left exactly as it is: a true one means the plugin
    loads, an all-false set is a deliberate opt-out.
  - The plugin is not enabled where it already arrives another way: when a
    synced copy or a user-scope install is on disk, or on a machine that
    registered the catalog through `scripts/install-hooks.py --fix`. Each of
    those plus a marketplace copy fires every hook twice. A remote (claude.ai)
    container with no synced copy is reported as `skip`: the account sync is
    missing or failed (ai-config#3948), and enabling a second copy there
    would double every hook once the sync delivers one.
  - A Codex file or link that is not ours is left alone; a dangling link, or
    one into another ai-config checkout, is repointed here.
  - Each step reports `ok`, `write`/`link`, `todo` (with --check) or `skip`
    with its reason. A step that raises is reported as `skip` and the rest
    still run.

`--check` writes nothing and exits 1 when any step is not `ok`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
from ai_config_wiring import (  # noqa: E402
    MARKETPLACE, MARKETPLACE_SOURCE, PLUGIN, is_ai_config, splice_block)
from plugin_overlap import ai_config_entries  # noqa: E402

GEMINI_LINK = "ai-config-AGENTS.md"
GEMINI_BEGIN = "<!-- ai-config:begin (managed by ai-config/scripts/wire-user-config.py) -->"
GEMINI_END = "<!-- ai-config:end -->"


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def load_json(path: Path) -> dict | None:
    """The parsed object, {} when absent, None when unreadable or not an object."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, data: dict) -> None:
    """Write atomically, so a concurrent reader never sees a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def catalog_scripts() -> set[str]:
    catalog = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    return {
        hook["script"]
        for groups in catalog["hooks"].values()
        for group in groups
        for hook in group["hooks"]
        if "script" in hook
    }


def non_plugin_hooks_registered(settings: dict) -> bool:
    """True when settings.json runs catalog hooks from ~/.claude/hooks."""
    scripts = catalog_scripts()
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    for groups in hooks.values():
        for group in groups if isinstance(groups, list) else []:
            entries = group.get("hooks") if isinstance(group, dict) else None
            for hook in entries if isinstance(entries, list) else []:
                command = hook.get("command", "") if isinstance(hook, dict) else ""
                if not isinstance(command, str):
                    continue
                if "CLAUDE_PLUGIN_ROOT" in command:
                    continue
                # install-hooks.py writes `$HOME/.claude/hooks/<name>`, or a
                # literal CLAUDE_HOME path, with either separator.
                if any(re.search(r"[\\/]hooks[\\/]" + re.escape(name) + r"\b", command)
                       for name in scripts):
                    return True
    return False


def plugin_on_disk(claude_home: Path) -> str | None:
    """Where an ai-config plugin copy already loads from, if anywhere."""
    synced = sorted((claude_home / "plugins" / "synced").glob("*/ai-config"))
    if synced:
        return f"account plugin sync ({synced[0]})"
    installed = load_json(claude_home / "plugins" / "installed_plugins.json") or {}
    plugins = installed.get("plugins")
    for name, records in (plugins.items() if isinstance(plugins, dict) else ()):
        if not name.startswith("ai-config@"):
            continue
        # A project-scoped install loads only in that project, so it does not
        # stand in for a user-wide enable.
        records = records if isinstance(records, list) else [records]
        if any(isinstance(r, dict) and r.get("scope", "user") == "user" for r in records):
            return f"installed plugin {name} (user scope)"
    return None


def wire_claude(check: bool) -> tuple[str, bool]:
    claude_home = Path(os.environ.get("CLAUDE_HOME", home() / ".claude"))
    path = claude_home / "settings.json"
    settings = load_json(path)
    if settings is None:
        return f"skip  {path} is not a JSON object; fix it by hand", False
    for key in ("enabledPlugins", "extraKnownMarketplaces", "hooks"):
        if key in settings and not isinstance(settings[key], dict):
            return f"skip  {path}: `{key}` is not a JSON object; fix it by hand", False
    explicit = ai_config_entries(settings)
    if explicit:
        state = ", ".join(f"{k}={v}" for k, v in sorted(explicit.items()))
        if any(explicit.values()):
            return f"ok    {path} enables the plugin ({state})", True
        return (f"skip  {path} disables the plugin ({state}); "
                "left as an explicit choice"), False
    elsewhere = plugin_on_disk(claude_home)
    if elsewhere:
        return f"ok    plugin already loads from {elsewhere}", True
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return ("skip  remote container with no synced plugin copy: the account "
                "plugin sync is missing or failed (ai-config#3948); a marketplace "
                "copy here would load twice once the sync delivers one"), False
    if non_plugin_hooks_registered(settings):
        return (f"skip  {path} registers the hook catalog from ~/.claude/hooks "
                "(install-hooks.py path); enabling the plugin too would fire "
                "every hook twice -- remove those entries, then rerun"), False
    if check:
        return f"todo  {path}: register {MARKETPLACE} and enable {PLUGIN}", False
    settings.setdefault("extraKnownMarketplaces", {}).setdefault(
        MARKETPLACE, {"source": MARKETPLACE_SOURCE})
    settings.setdefault("enabledPlugins", {}).setdefault(PLUGIN, True)
    write_json(path, settings)
    return f"write {path}: registered {MARKETPLACE}, enabled {PLUGIN}", True


def replaceable_link(path: Path, target: Path) -> bool:
    """A link we may repoint: dangling, or into another ai-config checkout."""
    if not path.is_symlink():
        return False
    pointee = Path(os.path.realpath(path))
    if not pointee.exists():
        return True
    return pointee.name == target.name and is_ai_config(pointee.parent)


def ensure_link(path: Path, target: Path, check: bool) -> tuple[str, bool]:
    if path.is_symlink() and Path(os.path.realpath(path)) == target.resolve():
        return f"ok    {path} -> {target}", True
    if (path.exists() or path.is_symlink()) and not replaceable_link(path, target):
        return (f"skip  {path} exists and is not a link to an ai-config "
                "checkout; merge it by hand or move it aside, then rerun"), False
    if check:
        return f"todo  {path}: link to {target}", False
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        path.unlink()
    path.symlink_to(target)
    return f"link  {path} -> {target}", True


def wire_codex(check: bool) -> tuple[str, bool]:
    codex_home = Path(os.environ.get("CODEX_HOME", home() / ".codex"))
    return ensure_link(codex_home / "AGENTS.md", ROOT / "AGENTS.md", check)


def gemini_block() -> str:
    return f"{GEMINI_BEGIN}\n@./{GEMINI_LINK}\n{GEMINI_END}\n"


def wire_gemini(check: bool) -> tuple[str, bool]:
    gemini_home = Path(os.environ.get("GEMINI_HOME", home() / ".gemini"))
    link_msg, link_ok = ensure_link(gemini_home / GEMINI_LINK, ROOT / "AGENTS.md", check)
    if not link_ok:
        return link_msg, False
    path = gemini_home / "GEMINI.md"
    if path.is_symlink():
        return (f"skip  {path} is a link; add `@./{GEMINI_LINK}` to its target "
                "by hand"), False
    block = gemini_block()
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if block in current:
        return f"ok    {path} imports ./{GEMINI_LINK}", True
    if check:
        return f"todo  {path}: add the ai-config import block", False
    updated = splice_block(current, block, GEMINI_BEGIN, GEMINI_END)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return f"write {path}: ai-config import block", True


def stale_instruction(entry: object, agents: str) -> bool:
    """An earlier AGENTS.md entry that is provably another ai-config checkout's.

    An entry whose file is gone cannot be attributed, so it is kept: it may be
    the user's own entry for a project that is moved or unmounted.
    """
    if not isinstance(entry, str) or entry == agents or not entry.endswith("/AGENTS.md"):
        return False
    candidate = Path(entry)
    return candidate.is_absolute() and is_ai_config(candidate.parent)


def wire_opencode(check: bool) -> tuple[str, bool]:
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", home() / ".config")) / "opencode"
    if not config_dir.exists() and shutil.which("opencode") is None:
        return "ok    opencode is not installed; nothing to wire", True
    if (config_dir / "opencode.jsonc").exists():
        return (f"skip  {config_dir / 'opencode.jsonc'} is the user config; add "
                f"{ROOT / 'AGENTS.md'} to its instructions by hand"), False
    path = config_dir / "opencode.json"
    config = load_json(path)
    if config is None:
        return f"skip  {path} is not a JSON object; fix it by hand", False
    agents = str(ROOT / "AGENTS.md")
    instructions = config.get("instructions") or []
    kept = [e for e in instructions if not stale_instruction(e, agents)]
    if agents in kept and kept == instructions:
        return f"ok    {path} instructions include {agents}", True
    if check:
        return f"todo  {path}: add {agents} to instructions", False
    config.setdefault("$schema", "https://opencode.ai/config.json")
    config["instructions"] = kept if agents in kept else [*kept, agents]
    write_json(path, config)
    return f"write {path}: instructions now include {agents}", True


STEPS = (
    ("Claude Code", wire_claude),
    ("Codex", wire_codex),
    ("Gemini CLI", wire_gemini),
    ("opencode", wire_opencode),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report only; exit 1 when any step is not ok")
    args = parser.parse_args(argv)
    all_ok = True
    for label, step in STEPS:
        try:
            message, ok = step(args.check)
        except (OSError, UnicodeError, ValueError) as err:
            message, ok = f"skip  {type(err).__name__}: {err}", False
        print(f"{label:<12} {message}")
        all_ok = all_ok and ok
    return 0 if all_ok or not args.check else 1


if __name__ == "__main__":
    sys.exit(main())
