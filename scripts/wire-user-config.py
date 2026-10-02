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
  Codex         ~/.codex/AGENTS.md -- Codex's user-global instruction file,
                linked to this checkout's AGENTS.md.
  Gemini CLI    ~/.gemini/GEMINI.md -- a marked block importing this
                checkout's AGENTS.md with Gemini's `@path` syntax.
  opencode      ~/.config/opencode/opencode.json -- this checkout's AGENTS.md
                added to `instructions` (only when opencode is installed).

Every step is idempotent and conservative:

  - An explicit user choice wins. An `ai-config@*` entry already present in
    `enabledPlugins` (true or false) is left alone, and so is a Codex or
    Gemini file that is not ours -- the step reports `skip` and says why.
  - The plugin is not enabled on a machine that registered the catalog
    through `scripts/install-hooks.py --fix`, because the two paths together
    fire every hook twice (README, "Hooks"). The step says which to pick.
  - `--check` reports what it would do and exits 1 when anything is unwired,
    so `doctor.py`-style checks and CI can call it without side effects.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = "Morrison-Lab"
PLUGIN = f"ai-config@{MARKETPLACE}"
MARKETPLACE_SOURCE = {"source": "github", "repo": "Morrison-Lab/ai-config"}
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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
    for groups in (settings.get("hooks") or {}).values():
        for group in groups or []:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if "CLAUDE_PLUGIN_ROOT" in command:
                    continue
                if any(f".claude/hooks/{name}" in command for name in scripts):
                    return True
    return False


def wire_claude(check: bool) -> tuple[str, bool]:
    path = home() / ".claude" / "settings.json"
    settings = load_json(path)
    if settings is None:
        return f"skip  {path} is not a JSON object; fix it by hand", False
    enabled = settings.get("enabledPlugins") or {}
    explicit = {k: v for k, v in enabled.items() if k.startswith("ai-config@")}
    known = (settings.get("extraKnownMarketplaces") or {}).get(MARKETPLACE)
    if explicit:
        state = ", ".join(f"{k}={v}" for k, v in sorted(explicit.items()))
        ok = any(explicit.values()) and (known is not None or PLUGIN not in explicit)
        if ok:
            return f"ok    {path} enables the plugin ({state})", True
        if not any(explicit.values()):
            return (f"skip  {path} disables the plugin ({state}); "
                    "left as an explicit choice"), False
    if non_plugin_hooks_registered(settings):
        return (f"skip  {path} registers the hook catalog from ~/.claude/hooks "
                "(install-hooks.py path); enabling the plugin too would fire "
                "every hook twice -- remove those entries, then rerun"), False
    if check:
        return f"todo  {path}: register {MARKETPLACE} and enable {PLUGIN}", False
    settings.setdefault("extraKnownMarketplaces", {})[MARKETPLACE] = {
        "source": MARKETPLACE_SOURCE}
    settings.setdefault("enabledPlugins", {})[PLUGIN] = True
    write_json(path, settings)
    return f"write {path}: registered {MARKETPLACE}, enabled {PLUGIN}", True


def wire_codex(check: bool) -> tuple[str, bool]:
    target = ROOT / "AGENTS.md"
    path = home() / ".codex" / "AGENTS.md"
    if path.is_symlink() and path.resolve() == target.resolve():
        return f"ok    {path} -> {target}", True
    if path.exists() or path.is_symlink():
        return (f"skip  {path} exists and is not a link to {target}; "
                "merge it by hand or move it aside, then rerun"), False
    if check:
        return f"todo  {path}: link to {target}", False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)
    return f"link  {path} -> {target}", True


def gemini_block() -> str:
    return f"{GEMINI_BEGIN}\n@{ROOT / 'AGENTS.md'}\n{GEMINI_END}\n"


def wire_gemini(check: bool) -> tuple[str, bool]:
    gemini_home = Path(os.environ.get("GEMINI_HOME", home() / ".gemini"))
    path = gemini_home / "GEMINI.md"
    block = gemini_block()
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if block in current:
        return f"ok    {path} imports {ROOT / 'AGENTS.md'}", True
    if check:
        return f"todo  {path}: add the ai-config import block", False
    if GEMINI_BEGIN in current and GEMINI_END in current:
        head, rest = current.split(GEMINI_BEGIN, 1)
        tail = rest.split(GEMINI_END, 1)[1].lstrip("\n")
        updated = head + block + tail
    else:
        sep = "" if not current or current.endswith("\n\n") else (
            "\n" if current.endswith("\n") else "\n\n")
        updated = current + sep + block
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return f"write {path}: ai-config import block", True


def wire_opencode(check: bool) -> tuple[str, bool]:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home() / ".config"))
    path = config_home / "opencode" / "opencode.json"
    if not path.parent.exists() and shutil.which("opencode") is None:
        return "skip  opencode is not installed", True
    config = load_json(path)
    if config is None:
        return f"skip  {path} is not a JSON object; fix it by hand", False
    agents = str(ROOT / "AGENTS.md")
    instructions = config.get("instructions") or []
    if agents in instructions:
        return f"ok    {path} instructions include {agents}", True
    if check:
        return f"todo  {path}: add {agents} to instructions", False
    config.setdefault("$schema", "https://opencode.ai/config.json")
    config["instructions"] = [*instructions, agents]
    write_json(path, config)
    return f"write {path}: added {agents} to instructions", True


STEPS = (
    ("Claude Code", wire_claude),
    ("Codex", wire_codex),
    ("Gemini CLI", wire_gemini),
    ("opencode", wire_opencode),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report only; exit 1 when anything is unwired")
    args = parser.parse_args(argv)
    all_ok = True
    for label, step in STEPS:
        message, ok = step(args.check)
        print(f"{label:<12} {message}")
        all_ok = all_ok and ok
    return 0 if all_ok or not args.check else 1


if __name__ == "__main__":
    sys.exit(main())
