#!/usr/bin/env python3
"""Dispatch the canonical ai-config hook catalog through Codex hooks.

Codex and Claude use compatible lifecycle names and JSON payloads, but Codex
discovers project hooks from ``.codex/hooks.json`` and plugin hooks from a
Codex plugin manifest.  This dispatcher keeps one source of truth in
``hooks/hooks.json`` while translating only the small matcher and output
differences that matter to Codex.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "hooks" / "hooks.json"
TOOL_ALIASES = {
    "spawn_agent": "Agent",
    "apply_patch": "Edit|Write|NotebookEdit",
}


def load_entries(event: str) -> list[dict[str, Any]]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    for group in data.get("hooks", {}).get(event, []):
        matcher = group.get("matcher")
        for hook in group.get("hooks", []):
            if hook.get("type", "command") != "command":
                continue
            command = hook.get("command")
            if not command:
                continue
            entries.append({
                "matcher": matcher,
                "command": command,
                "timeout": hook.get("timeout", 600),
            })
    return entries


def matcher_hits(matcher: str | None, tool_name: str) -> bool:
    if not matcher:
        return True
    if not tool_name:
        return False
    candidates = [tool_name]
    alias = TOOL_ALIASES.get(tool_name)
    if alias:
        candidates.extend(alias.split("|"))
    for candidate in candidates:
        try:
            if re.fullmatch(matcher, candidate):
                return True
        except re.error:
            return candidate == matcher
    return False


def resolve_command(command: str) -> str:
    return (
        command.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT))
        .replace("${PLUGIN_ROOT}", str(ROOT))
    )


def run_entry(entry: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    env = os.environ.copy()
    env.update({
        "AI_CONFIG_ROOT": str(ROOT),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PLUGIN_ROOT": str(ROOT),
    })
    cwd = payload.get("cwd") or str(ROOT)
    try:
        result = subprocess.run(
            resolve_command(entry["command"]),
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=cwd,
            env=env,
            shell=True,
            timeout=float(entry["timeout"]),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"codex-hook-adapter: hook execution failed: {exc}", file=sys.stderr)
        return None
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if not result.stdout.strip():
        return None
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"codex-hook-adapter: invalid hook JSON: {exc}", file=sys.stderr)
        return None
    return parsed if isinstance(parsed, dict) else None


def output_fields(result: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    nested = result.get("hookSpecificOutput")
    nested = nested if isinstance(nested, dict) else {}
    decision = nested.get("permissionDecision") or result.get("decision")
    reason = nested.get("permissionDecisionReason") or result.get("reason")
    context = nested.get("additionalContext") or result.get("additionalContext")
    message = result.get("systemMessage")
    if context is not None and not isinstance(context, str):
        context = str(context)
    if message is not None and not isinstance(message, str):
        message = str(message)
    warning = "\n".join(x for x in (context, message) if x)
    return decision, str(reason) if reason is not None else None, warning or None


def dispatch(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["hook_event_name"] = event
    tool_name = str(payload.get("tool_name", ""))
    results = []
    for entry in load_entries(event):
        if event == "PreToolUse" and not matcher_hits(entry["matcher"], tool_name):
            continue
        result = run_entry(entry, payload)
        if result is not None:
            results.append(result)

    decisions: list[str] = []
    reasons: list[str] = []
    warnings: list[str] = []
    for result in results:
        decision, reason, warning = output_fields(result)
        if decision:
            decisions.append(decision)
        if reason:
            reasons.append(reason)
        if warning:
            warnings.append(warning)

    context = "\n\n".join(dict.fromkeys(warnings))
    if event == "PreToolUse":
        output: dict[str, Any] = {
            "hookSpecificOutput": {"hookEventName": "PreToolUse"}
        }
        nested = output["hookSpecificOutput"]
        if any(d in ("deny", "block") for d in decisions):
            nested["permissionDecision"] = "deny"
            nested["permissionDecisionReason"] = "\n".join(dict.fromkeys(reasons)) or "Blocked by ai-config hook."
        if context:
            nested["additionalContext"] = context
        if not nested.keys() - {"hookEventName"}:
            return {}
        return output
    if event == "Stop":
        output = {}
        if any(d in ("deny", "block") for d in decisions):
            output["decision"] = "block"
            output["reason"] = "\n".join(dict.fromkeys(reasons)) or "Continue the turn after ai-config hook feedback."
        if context:
            output["systemMessage"] = context
        return output
    output = {}
    if context:
        output["hookSpecificOutput"] = {
            "hookEventName": event,
            "additionalContext": context,
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", choices=("UserPromptSubmit", "PreToolUse", "Stop"), required=True)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"codex-hook-adapter: failed to read payload: {exc}", file=sys.stderr)
        print("{}")
        return 0
    print(json.dumps(dispatch(args.event, payload if isinstance(payload, dict) else {})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
