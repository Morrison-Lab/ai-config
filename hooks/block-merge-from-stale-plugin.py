#!/usr/bin/env python3
"""PreToolUse: run the installed ai-config's merge gates when this session's hooks are a stale snapshot.

## The failure this exists for (ai-config#5603)

Claude Code loads a plugin's hooks once, at session start, from the cache
snapshot the session began with. A cloud session's SessionStart hook
(`refresh-stale-plugin-pin-cloud.py`) then updates the installed pin, so
`installed_plugins.json` names a newer snapshot than the one whose hooks are
running. Until a restart, every gate merged since the old snapshot is absent,
and nothing says so at the moment it matters.

On 2026-11-13 a session merged Morrison-Lab/mds#748 at 01:07 UTC with no
non-Claude review. The installed snapshot (refreshed at 01:06) carried
`warn-merge-without-cross-harness-review.py` as a deny; the running snapshot
carried the warn-only version, so the merge went through.

## What it does

    the call merges a PR or arms auto-merge
        (recognized by warn-merge-without-cross-harness-review.py's _targets)
    AND this file's plugin root is not the installPath of any
        `ai-config@<marketplace>` entry in installed_plugins.json that applies
        to this session (user scope, or a project/local scope whose
        projectPath contains the session directory)
    => run the INSTALLED snapshot's PreToolUse hooks whose matcher matches
       this tool, on the same payload, with CLAUDE_PLUGIN_ROOT set to the
       installed snapshot; deny if any of them denies, and deny (fail closed)
       if any of them cannot run.

When the installed gates all pass, the merge proceeds, so a stale session is
held to the current gates rather than locked out. A restart loads them
natively.

## What it cannot do

A stale snapshot that predates this hook does not run it, so the protection
starts with the first snapshot that contains it.
No installed_plugins.json, or no applicable ai-config entry (a non-plugin
install, another harness), means there is nothing to compare: the hook stays
silent, and the running hooks are the only gates.

`AI_CONFIG_PLUGINS_DIR` overrides `~/.claude/plugins` and `AI_CONFIG_SELF_ROOT`
overrides this file's plugin root, both for tests.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PLUGIN = "ai-config"
SELF = os.path.basename(__file__)
BUDGET = float(os.environ.get("AI_CONFIG_STALE_GATE_BUDGET", "50"))  # seconds for all installed hooks; registered timeout is 60

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from sibling import load_sibling
except ImportError:
    load_sibling = None


def plugins_dir() -> Path:
    override = os.environ.get("AI_CONFIG_PLUGINS_DIR")
    return Path(override) if override else Path.home() / ".claude" / "plugins"


def self_root() -> Path:
    override = os.environ.get("AI_CONFIG_SELF_ROOT")
    if override:
        return Path(override).resolve()
    return Path(os.path.realpath(__file__)).parent.parent


def session_dir(payload: dict) -> Path:
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def applies(entry: dict, here: Path) -> bool:
    scope = entry.get("scope")
    if scope == "user":
        return True
    project = entry.get("projectPath")
    if scope not in ("project", "local") or not project:
        return False
    try:
        here.resolve().relative_to(Path(project).resolve())
    except ValueError:
        return False
    return True


def installed_paths(here: Path) -> list[Path]:
    """installPaths of the applicable ai-config entries; [] when there is no record."""
    try:
        record = json.loads((plugins_dir() / "installed_plugins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    plugins = record.get("plugins") if isinstance(record, dict) else None
    if not isinstance(plugins, dict):
        return []
    out = []
    for key, entries in plugins.items():
        if not isinstance(key, str) or key.split("@", 1)[0] != PLUGIN:
            continue
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and entry.get("installPath") and applies(entry, here):
                out.append(Path(entry["installPath"]).resolve())
    return out


MERGE_TOOLS = ("merge_pull_request", "enable_pr_auto_merge")
MERGE_WORDS = ("gh pr merge", "/merge")


def looks_like_merge(payload: dict) -> bool:
    """A coarse merge test, used only when the precise one cannot run.

    Erring toward True is the safe direction here: a false positive costs
    one run of the installed gates, while a false negative lets a merge
    past a stale session's weaker hooks unchecked.
    """
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    if tool.endswith(MERGE_TOOLS):
        return True
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    return tool == "Bash" and isinstance(command, str) and any(
        word in command for word in MERGE_WORDS)


def is_merge(payload: dict) -> bool:
    """True when the call merges or arms auto-merge, per the cross-harness hook.

    Falls back to looks_like_merge when the sibling cannot be loaded or
    raises, so a broken import fails closed rather than open.
    """
    if load_sibling is None:
        return looks_like_merge(payload)
    try:
        xh = load_sibling(__file__, "warn-merge-without-cross-harness-review.py",
                          "_sib_wmwchr")
    except Exception:
        return looks_like_merge(payload)
    if xh is None:
        return looks_like_merge(payload)
    try:
        sib = xh._sibling()
    except Exception:
        return looks_like_merge(payload)
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input") or payload.get("toolInput")
    if not isinstance(tool_input, dict):
        return looks_like_merge(payload)
    try:
        return bool(xh._targets(sib, tool, tool_input))
    except Exception:
        return looks_like_merge(payload)


def matching_hooks(root: Path, tool: str) -> list[dict]:
    """The installed snapshot's PreToolUse command hooks whose matcher matches *tool*."""
    spec = json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    out = []
    for group in spec.get("hooks", {}).get("PreToolUse", []):
        matcher = group.get("matcher") or ""
        if matcher and not re.fullmatch(matcher, tool):
            continue
        for hook in group.get("hooks", []):
            if hook.get("type") != "command" or hook.get("script") == SELF:
                continue
            out.append(hook)
    return out


def run_installed(root: Path, tool: str, raw: str) -> tuple[list[str], list[str]]:
    """(deny reasons, failures) from the installed snapshot's matching hooks."""
    denies, failures = [], []
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(root))
    deadline = time.monotonic() + BUDGET
    for hook in matching_hooks(root, tool):
        name = hook.get("script") or hook["command"]
        left = deadline - time.monotonic()
        if left <= 0:
            failures.append(f"{name}: not reached, because earlier hooks "
                            f"used the whole {BUDGET:.0f} s budget")
            continue
        command = hook["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(root))
        try:
            proc = subprocess.run(command, shell=True, input=raw, env=env,
                                  capture_output=True, text=True,
                                  timeout=min(left, float(hook.get("timeout", 20))))
        except subprocess.TimeoutExpired:
            failures.append(f"{name}: timed out")
            continue
        if proc.returncode == 2:
            denies.append(f"{name}: {proc.stderr.strip()[:600]}")
            continue
        if proc.returncode != 0:
            failures.append(f"{name}: exit {proc.returncode}")
            continue
        out = proc.stdout.strip()
        if not out:
            continue
        try:
            data = json.loads(out)
        except ValueError:
            continue
        spec = data.get("hookSpecificOutput") if isinstance(data, dict) else None
        if isinstance(spec, dict) and spec.get("permissionDecision") == "deny":
            denies.append(f"{name}: {spec.get('permissionDecisionReason', '')}")
        elif isinstance(data, dict) and data.get("decision") == "block":
            denies.append(f"{name}: {data.get('reason', '')}")
    return denies, failures


def emit(decision: str, reason: str) -> None:
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if decision == "deny":
        out["hookSpecificOutput"]["permissionDecision"] = "deny"
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
    else:
        out["hookSpecificOutput"]["additionalContext"] = reason
    print(json.dumps(out))


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        merge = is_merge(payload)
    except Exception:
        merge = looks_like_merge(payload)
    if not merge:
        return 0
    paths = installed_paths(session_dir(payload))
    mine = self_root()
    if not paths or mine in paths:
        return 0
    installed = paths[0]
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    head = (f"This session runs ai-config hooks from {mine.name}, but the "
            f"installed snapshot is {installed.name} (ai-config#5603). Hooks "
            f"load at session start, so the merge gates merged since then are "
            f"not running natively.")
    try:
        denies, failures = run_installed(installed, tool, raw)
    except Exception as exc:  # unreadable hooks.json, missing directory
        emit("deny", f"{head} The installed gates could not be run ({exc}), "
                     f"so this merge is refused. Restart the session to load "
                     f"them, then merge.")
        return 0
    if denies:
        emit("deny", f"{head} The installed gates refuse this merge:\n- "
                     + "\n- ".join(denies))
    elif failures:
        emit("deny", f"{head} These installed gates did not run, so this "
                     f"merge is refused: " + "; ".join(failures)
                     + ". Restart the session to load them natively.")
    else:
        emit("allow", f"{head} The installed snapshot's merge gates were run "
                      f"on this call and none refused it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
