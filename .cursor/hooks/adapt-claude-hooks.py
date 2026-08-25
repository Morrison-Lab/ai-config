#!/usr/bin/env python3
"""Run the Claude Code `hooks/` catalog under Cursor's hook protocol.

Cursor Cloud loads `.cursor/hooks.json` (native schema, `version: 1`).
It does not load `hooks/hooks.json`. Pointing the Cursor plugin `hooks`
field at that Claude file would feed a foreign schema (ai-config#1934).

This adapter is the Cursor-schema command those events invoke. It:

1. Reads a Cursor stdin payload.
2. Translates it into the Claude Code payload the existing scripts expect.
3. Runs matching entries from `hooks/hooks.json`.
4. Translates Claude stdout back into Cursor's response shape.

It never registers anything in `~/.claude/settings.json`, so it cannot
double-bind the Claude plugin / `install-hooks.py` path.
A per-payload sentinel still collapses a project-hook plus plugin-hook
double fire of the *same* Cursor event.

Fails open: a crash, timeout, or unreadable payload prints a Cursor
allow/continue response (or empty JSON for observational events).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ADAPTER = Path(__file__).resolve()
REPO = ADAPTER.parent.parent.parent


def hooks_dir() -> Path:
    override = os.environ.get("AI_CONFIG_HOOKS_DIR")
    if override:
        return Path(override)
    return REPO / "hooks"


def manifest_path() -> Path:
    override = os.environ.get("AI_CONFIG_HOOKS_JSON")
    if override:
        return Path(override)
    return REPO / "hooks" / "hooks.json"


def stash_dir() -> Path:
    override = os.environ.get("AI_CONFIG_CURSOR_HOOK_STASH")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "ai-config-cursor-hook-stash"

# Claude event -> Cursor events that run those Claude scripts.
# Keep this table in lockstep with docs/cursor-hook-mapping.md.
EVENT_MAPPING: dict[str, list[str]] = {
    "PreToolUse": ["preToolUse"],
    "Stop": ["stop"],
    "UserPromptSubmit": ["sessionStart", "postToolUse"],
}

# Claude matchers / events with no Cursor analog (documented, not silent).
NO_CURSOR_ANALOG = (
    "SendMessage",  # remind-brief-premises third matcher; Cursor has no peer
    "beforeSubmitPrompt-inject",  # event exists but cannot inject context
    "beforeMCPExecution-cloud",  # not loaded in Cursor Cloud; preToolUse covers MCP
)

SPECIAL_MATCHER = re.compile(r"[^A-Za-z0-9_\- ,|]")


def fail_open(event: str, extra: dict[str, Any] | None = None) -> int:
    """Print a non-blocking Cursor response and exit 0."""
    payload: dict[str, Any] = {}
    if event in ("preToolUse", "beforeShellExecution", "beforeMCPExecution",
                 "subagentStart"):
        payload["permission"] = "allow"
    elif event == "beforeSubmitPrompt":
        payload["continue"] = True
    if extra:
        payload.update(extra)
    print(json.dumps(payload))
    return 0


def load_manifest(path: Path | None = None) -> list[dict[str, Any]]:
    """Flatten hooks/hooks.json to `{script, event, matcher?, timeout?}`."""
    path = path or manifest_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    hooks = data.get("hooks")
    if not isinstance(hooks, dict) or not hooks:
        raise ValueError("hooks.json has no object-keyed hooks")
    entries: list[dict[str, Any]] = []
    for event, groups in hooks.items():
        for group in groups:
            matcher = group.get("matcher")
            for hook in group.get("hooks", []):
                script = hook.get("script")
                if not script:
                    continue
                entry: dict[str, Any] = {"script": script, "event": event}
                if matcher:
                    entry["matcher"] = matcher
                if hook.get("timeout"):
                    entry["timeout"] = hook["timeout"]
                entries.append(entry)
    return entries


def matcher_hits(matcher: str | None, tool_name: str) -> bool:
    if not matcher:
        return True
    if not tool_name:
        return False
    if SPECIAL_MATCHER.search(matcher):
        try:
            return re.search(matcher, tool_name) is not None
        except re.error:
            return False
    names = {part.strip() for part in matcher.split("|") if part.strip()}
    return tool_name in names


def cursor_to_claude_tool_names(cursor_name: str) -> list[str]:
    """Candidate Claude tool_name values for one Cursor tool_name."""
    if not cursor_name:
        return []
    names = [cursor_name]
    if cursor_name == "Shell":
        names.append("Bash")
    elif cursor_name == "Task":
        names.extend(["Agent", "Task"])
    elif cursor_name.startswith("MCP:"):
        rest = cursor_name[4:]
        names.append(rest)
        if rest.startswith("github-"):
            names.append("mcp__github__" + rest[len("github-"):])
        if rest.startswith("mcp__"):
            names.append(rest)
        else:
            names.append("mcp__" + rest.replace("-", "_"))
            names.append("mcp__" + rest.replace("-", "__"))
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def coerce_tool_input(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def claude_payload_for_pretool(cursor: dict[str, Any], claude_tool: str) -> dict[str, Any]:
    tool_input = coerce_tool_input(cursor.get("tool_input"))
    command = cursor.get("command")
    if command and "command" not in tool_input:
        tool_input["command"] = command
    if cursor.get("subagent_type") and "subagent_type" not in tool_input:
        tool_input["subagent_type"] = cursor["subagent_type"]
    return {
        "tool_name": claude_tool,
        "tool_input": tool_input,
        "transcript_path": (
            cursor.get("transcript_path")
            or os.environ.get("CURSOR_TRANSCRIPT_PATH")
            or ""
        ),
        "cwd": cursor.get("cwd") or os.environ.get("CURSOR_PROJECT_DIR") or "",
        "hook_event_name": "PreToolUse",
    }


def claude_payload_for_transcript(cursor: dict[str, Any], event: str) -> dict[str, Any]:
    return {
        "transcript_path": (
            cursor.get("transcript_path")
            or os.environ.get("CURSOR_TRANSCRIPT_PATH")
            or ""
        ),
        "cwd": os.environ.get("CURSOR_PROJECT_DIR") or "",
        "hook_event_name": event,
    }


def parse_hook_stdout(raw: str) -> tuple[dict[str, Any] | None, str]:
    """Return (parsed JSON or None, leftover plain text)."""
    text = raw.strip()
    if not text:
        return None, ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None, text
    if isinstance(parsed, dict):
        return parsed, ""
    return None, text


def run_script(script: str, payload: dict[str, Any], timeout: float) -> tuple[int, str, str]:
    path = hooks_dir() / script
    if not path.is_file():
        return 0, "", f"missing {script}"
    if script.endswith(".py"):
        argv = [sys.executable, str(path)]
    else:
        argv = ["sh", str(path)]
    try:
        proc = subprocess.run(
            argv,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(os.environ.get("CURSOR_PROJECT_DIR") or REPO),
            env=os.environ,
        )
    except subprocess.TimeoutExpired:
        return 0, "", f"timeout {script}"
    except OSError as exc:
        return 0, "", f"exec {script}: {exc}"
    return proc.returncode, proc.stdout, proc.stderr


def tick_already_ran(key: str) -> bool:
    base = stash_dir()
    base.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(key.encode()).hexdigest()[:20]
    sentinel = base / f"tick-{digest}"
    if sentinel.exists():
        return True
    try:
        sentinel.write_text("1", encoding="utf-8")
    except OSError:
        return False
    return False


def payload_tick_key(event: str, cursor: dict[str, Any]) -> str:
    return "|".join((
        event,
        str(cursor.get("conversation_id") or ""),
        str(cursor.get("generation_id") or ""),
        str(cursor.get("tool_use_id") or ""),
        str(cursor.get("loop_count") if cursor.get("loop_count") is not None else ""),
        str(cursor.get("tool_name") or cursor.get("command") or "")[:200],
    ))


def stash_context(tool_use_id: str, chunks: list[str]) -> None:
    if not tool_use_id or not chunks:
        return
    base = stash_dir()
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"ctx-{hashlib.sha256(tool_use_id.encode()).hexdigest()[:20]}"
    existing = ""
    if path.is_file():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError:
            existing = ""
    body = "\n".join(chunks)
    try:
        path.write_text((existing + "\n" + body).strip() + "\n", encoding="utf-8")
    except OSError:
        pass


def take_stashed_context(tool_use_id: str) -> str:
    if not tool_use_id:
        return ""
    path = stash_dir() / f"ctx-{hashlib.sha256(tool_use_id.encode()).hexdigest()[:20]}"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
        path.unlink()
        return text
    except OSError:
        return ""


def generation_ups_sentinel(generation_id: str) -> Path:
    base = stash_dir()
    base.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(generation_id.encode()).hexdigest()[:20]
    return base / f"ups-{digest}"


def pretool_decision(parsed: dict[str, Any], returncode: int) -> tuple[str | None, str]:
    """Return (deny-reason or None, additional context)."""
    if returncode == 2:
        return parsed.get("user_message") or parsed.get("reason") or "denied by hook", ""
    hso = parsed.get("hookSpecificOutput")
    if not isinstance(hso, dict):
        hso = {}
    if (
        parsed.get("permission") == "deny"
        or hso.get("permissionDecision") == "deny"
        or parsed.get("decision") == "block"
    ):
        reason = (
            parsed.get("user_message")
            or parsed.get("agent_message")
            or hso.get("permissionDecisionReason")
            or parsed.get("reason")
            or "denied by hook"
        )
        return str(reason), ""
    extra_parts = []
    for key in ("additionalContext", "additional_context"):
        val = parsed.get(key) or hso.get(key)
        if val:
            extra_parts.append(str(val))
    sys_msg = parsed.get("systemMessage")
    if sys_msg:
        extra_parts.append(str(sys_msg))
    return None, "\n".join(extra_parts)


def collect_plain_or_json_context(parsed: dict[str, Any] | None, text: str) -> str:
    parts = []
    if parsed:
        hso = parsed.get("hookSpecificOutput")
        if not isinstance(hso, dict):
            hso = {}
        for key in ("additionalContext", "additional_context"):
            val = parsed.get(key) or hso.get(key)
            if val:
                parts.append(str(val))
        sys_msg = parsed.get("systemMessage")
        if sys_msg:
            parts.append(str(sys_msg))
    if text.strip():
        parts.append(text.strip())
    return "\n".join(parts)


def handle_pretool(cursor: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    cursor_tool = str(cursor.get("tool_name") or "")
    candidates = cursor_to_claude_tool_names(cursor_tool)
    extra_chunks: list[str] = []
    deny_reason = None
    for entry in entries:
        if entry["event"] != "PreToolUse":
            continue
        hits = [name for name in candidates if matcher_hits(entry.get("matcher"), name)]
        if not hits:
            continue
        claude_tool = hits[0]
        payload = claude_payload_for_pretool(cursor, claude_tool)
        timeout = float(entry.get("timeout") or 10)
        code, stdout, stderr = run_script(entry["script"], payload, timeout)
        if stderr:
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        parsed, text = parse_hook_stdout(stdout)
        if parsed is None:
            parsed = {}
        reason, extra = pretool_decision(parsed, code)
        if extra:
            extra_chunks.append(extra)
        if text.strip():
            extra_chunks.append(text.strip())
        if reason and deny_reason is None:
            deny_reason = reason
    if extra_chunks:
        stash_context(str(cursor.get("tool_use_id") or ""), extra_chunks)
    if deny_reason:
        return {
            "permission": "deny",
            "user_message": deny_reason,
            "agent_message": deny_reason,
        }
    return {"permission": "allow"}


def handle_stop(cursor: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    payload = claude_payload_for_transcript(cursor, "Stop")
    followups: list[str] = []
    for entry in entries:
        if entry["event"] != "Stop":
            continue
        timeout = float(entry.get("timeout") or 10)
        code, stdout, stderr = run_script(entry["script"], payload, timeout)
        if stderr:
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        parsed, text = parse_hook_stdout(stdout)
        if parsed is None:
            parsed = {}
        hso = parsed.get("hookSpecificOutput")
        if not isinstance(hso, dict):
            hso = {}
        blocked = (
            parsed.get("decision") == "block"
            or hso.get("decision") == "block"
            or code == 2
        )
        if blocked:
            reason = (
                parsed.get("reason")
                or hso.get("reason")
                or parsed.get("followup_message")
                or text.strip()
                or "blocked by hook"
            )
            followups.append(str(reason))
        # Warn-only Stop hooks emit systemMessage and must not auto-continue.
        sys_msg = parsed.get("systemMessage")
        if sys_msg:
            print(str(sys_msg), file=sys.stderr)
    if followups:
        return {"followup_message": "\n\n".join(followups)}
    return {}


def handle_user_prompt_submit(
    cursor: dict[str, Any],
    entries: list[dict[str, Any]],
    once_per_generation: bool,
) -> str:
    generation_id = str(cursor.get("generation_id") or cursor.get("conversation_id") or "")
    if once_per_generation and generation_id:
        sentinel = generation_ups_sentinel(generation_id)
        if sentinel.exists():
            return ""
        try:
            sentinel.write_text("1", encoding="utf-8")
        except OSError:
            pass
    payload = claude_payload_for_transcript(cursor, "UserPromptSubmit")
    chunks: list[str] = []
    for entry in entries:
        if entry["event"] != "UserPromptSubmit":
            continue
        timeout = float(entry.get("timeout") or 10)
        _code, stdout, stderr = run_script(entry["script"], payload, timeout)
        if stderr:
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        parsed, text = parse_hook_stdout(stdout)
        extra = collect_plain_or_json_context(parsed, text)
        if extra:
            chunks.append(extra)
    return "\n".join(chunks).strip()


def handle_session_start(cursor: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    extra = handle_user_prompt_submit(cursor, entries, once_per_generation=True)
    if extra:
        return {"additional_context": extra}
    return {}


def handle_post_tool(cursor: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    parts: list[str] = []
    stashed = take_stashed_context(str(cursor.get("tool_use_id") or ""))
    if stashed:
        parts.append(stashed)
    extra = handle_user_prompt_submit(cursor, entries, once_per_generation=True)
    if extra:
        parts.append(extra)
    if parts:
        return {"additional_context": "\n".join(parts)}
    return {}


def read_stdin() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--event",
        required=True,
        help="Cursor hook event name (preToolUse, stop, sessionStart, postToolUse)",
    )
    args = parser.parse_args(argv)
    event = args.event
    cursor = read_stdin()
    if tick_already_ran(payload_tick_key(event, cursor)):
        return fail_open(event)
    try:
        entries = load_manifest()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"adapt-claude-hooks: cannot load hooks.json ({exc})", file=sys.stderr)
        return fail_open(event)

    try:
        if event == "preToolUse":
            result = handle_pretool(cursor, entries)
        elif event == "stop":
            result = handle_stop(cursor, entries)
        elif event == "sessionStart":
            result = handle_session_start(cursor, entries)
        elif event == "postToolUse":
            result = handle_post_tool(cursor, entries)
        else:
            result = {}
    except Exception as exc:  # fail open
        print(f"adapt-claude-hooks: {event} failed ({exc})", file=sys.stderr)
        return fail_open(event)

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
