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
itself double-bind the `install-hooks.py` path. Desktop Cursor with
third-party Claude hooks enabled still loads `~/.claude/settings.json`
natively and runs every source; the tick sentinel only collapses two
adapter processes, not adapter-plus-native. Cloud agents have no home
Claude settings.
A per-payload sentinel still collapses a project-hook plus plugin-hook
double fire of the *same* Cursor event by replaying the first JSON result.

Adapter-level crashes, wrapper timeouts, and unreadable payloads fail open.
A missing catalog script fails closed for that script (Claude `python3`
on a missing path exits 2, which PreToolUse treats as deny).
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
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

ADAPTER = Path(__file__).resolve()
REPO = ADAPTER.parent.parent.parent
TICK_PENDING = "pending\n"
TICK_REPLAY_WAIT_S = 5.0
# Must match .cursor/hooks.json. Slack keeps sequential catalog runs
# from being SIGKILL'd by Cursor, which fail-opens the whole event.
WRAPPER_TIMEOUT_S = {
    "preToolUse": 300,
    "postToolUse": 180,
    "stop": 180,
    "sessionStart": 120,
}
WRAPPER_SLACK_S = 10
ENV_PREFIX = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+")
# Cursor JSONL omits tool_result (Cursor staff, 2026-04-13). These
# scripts fail closed or loop until they see one, so running them on
# Cursor is a lockout rather than a no-op.
SKIP_WITHOUT_TOOL_RESULT = frozenset({
    "no-push-without-self-review.py",
    "no-unreviewed-pr.py",
    "no-unmonitored-pr.py",
})
GITHUB_MCP_HINT = re.compile(
    r"(issue|pull_request|pull-request|pr_comment|merge_pull)",
    re.I,
)


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
# Values must be keys of HANDLERS; main() dispatches through HANDLERS.
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


def fail_open_payload(event: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Non-blocking Cursor response for adapter-level failure."""
    payload: dict[str, Any] = {}
    if event in ("preToolUse", "beforeShellExecution", "beforeMCPExecution",
                 "subagentStart"):
        payload["permission"] = "allow"
    elif event == "beforeSubmitPrompt":
        payload["continue"] = True
    if extra:
        payload.update(extra)
    return payload


def event_deadline(event: str) -> float:
    budget = WRAPPER_TIMEOUT_S.get(event, 60) - WRAPPER_SLACK_S
    return time.time() + max(budget, 1)


def remaining_timeout(deadline: float, advertised: float) -> float | None:
    left = deadline - time.time()
    if left <= 0:
        return None
    return min(advertised, left)


def fail_open(event: str, extra: dict[str, Any] | None = None) -> int:
    """Print a non-blocking Cursor response and exit 0."""
    print(json.dumps(fail_open_payload(event, extra)))
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
                extra_env = env_prefix_from_command(hook.get("command"))
                if extra_env:
                    entry["env"] = extra_env
                entries.append(entry)
    return entries


def env_prefix_from_command(command: str | None) -> dict[str, str]:
    """Leading KEY=VALUE tokens from a hooks.json command string."""
    if not command:
        return {}
    rest = command.lstrip()
    env: dict[str, str] = {}
    while True:
        match = ENV_PREFIX.match(rest)
        if not match:
            break
        env[match.group(1)] = match.group(2).strip("\"'")
        rest = rest[match.end():]
    return env


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
            if GITHUB_MCP_HINT.search(rest):
                suffix = rest[len("github-"):] if rest.startswith("github-") else rest
                names.append("mcp__github__" + suffix.replace("-", "_"))
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
        "transcript_path": translate_transcript_path(
            str(
                cursor.get("transcript_path")
                or os.environ.get("CURSOR_TRANSCRIPT_PATH")
                or ""
            )
        ),
        "cwd": cursor.get("cwd") or os.environ.get("CURSOR_PROJECT_DIR") or "",
        "hook_event_name": "PreToolUse",
    }


def claude_payload_for_transcript(cursor: dict[str, Any], event: str) -> dict[str, Any]:
    raw = (
        cursor.get("transcript_path")
        or os.environ.get("CURSOR_TRANSCRIPT_PATH")
        or ""
    )
    return {
        "transcript_path": translate_transcript_path(str(raw)),
        "cwd": os.environ.get("CURSOR_PROJECT_DIR") or "",
        "hook_event_name": event,
    }


def claude_tool_name_for_cursor(name: str) -> str:
    if name == "Shell":
        return "Bash"
    if name.startswith("MCP:"):
        mapped = cursor_to_claude_tool_names(name)
        mcp = [item for item in mapped if item.startswith("mcp__")]
        if mcp:
            return mcp[0]
    return name


def translate_content_block(block: Any) -> Any:
    if not isinstance(block, dict):
        return block
    out = dict(block)
    if out.get("type") == "tool_use" and isinstance(out.get("name"), str):
        out["name"] = claude_tool_name_for_cursor(out["name"])
    return out


def cursor_record_to_claude(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    if "type" not in out and out.get("role") in ("user", "assistant"):
        out["type"] = out["role"]
    message = out.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), list):
        out["message"] = dict(message)
        out["message"]["content"] = [
            translate_content_block(block) for block in message["content"]
        ]
    return out


def record_needs_translation(record: dict[str, Any]) -> bool:
    if record.get("role") in ("user", "assistant") and record.get("type") not in (
        "user",
        "assistant",
    ):
        return True
    message = record.get("message")
    blocks = message.get("content") if isinstance(message, dict) else None
    if not isinstance(blocks, list):
        return False
    for block in blocks:
        if (
            isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("name") == "Shell"
        ):
            return True
    return False


def transcript_needs_translation(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                if record.get("type") == "turn_ended":
                    continue
                if record_needs_translation(record):
                    return True
    except OSError:
        return False
    return False


def translate_transcript_path(raw: str) -> str:
    """Point Stop/UPS scripts at a Claude-shaped JSONL when Cursor wrote it."""
    if not raw:
        return raw
    path = Path(raw)
    if not path.is_file() or not transcript_needs_translation(path):
        return raw
    dest = stash_dir() / (
        f"tx-{hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:20]}.jsonl"
    )
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    lines.append(line if line.endswith("\n") else line + "\n")
                    continue
                if isinstance(record, dict):
                    record = cursor_record_to_claude(record)
                    lines.append(json.dumps(record) + "\n")
                else:
                    lines.append(line if line.endswith("\n") else line + "\n")
        dest.write_text("".join(lines), encoding="utf-8")
    except OSError:
        return raw
    return str(dest)


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


def run_script(
    script: str,
    payload: dict[str, Any],
    timeout: float,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    path = hooks_dir() / script
    if script.endswith(".py"):
        argv = [sys.executable, str(path)]
    else:
        argv = ["sh", str(path)]
    # Missing paths must fail closed. Claude `python3 missing.py` exits 2;
    # `sh missing.sh` exits 127, which PreToolUse would otherwise allow.
    if not path.is_file():
        return 2, "", f"missing {script}"
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(
            argv,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(os.environ.get("CURSOR_PROJECT_DIR") or REPO),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 0, "", f"timeout {script}"
    except OSError as exc:
        return 0, "", f"exec {script}: {exc}"
    return proc.returncode, proc.stdout, proc.stderr


def tick_sentinel(key: str) -> Path:
    base = stash_dir()
    base.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(key.encode()).hexdigest()[:20]
    return base / f"tick-{digest}"


def _tick_json(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped
    return None


def wait_for_tick_json(path: Path, timeout: float = TICK_REPLAY_WAIT_S) -> str:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            last = path.read_text(encoding="utf-8")
        except OSError:
            last = ""
        found = _tick_json(last)
        if found is not None:
            return found
        time.sleep(0.05)
    # First fire claimed the tick but stored no JSON. Do not emit a competing
    # allow; replay empty observational JSON.
    return "{}"


def claim_or_replay_tick(key: str, wait_s: float = TICK_REPLAY_WAIT_S) -> str | None:
    """Return stored JSON to replay, or None if this process owns the tick."""
    path = tick_sentinel(key)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return wait_for_tick_json(path, timeout=wait_s)
    except OSError:
        if path.exists():
            return wait_for_tick_json(path, timeout=wait_s)
        return None
    try:
        os.write(fd, TICK_PENDING.encode("utf-8"))
    finally:
        os.close(fd)
    return None


def store_tick_result(key: str, result: dict[str, Any]) -> None:
    path = tick_sentinel(key)
    try:
        path.write_text(json.dumps(result), encoding="utf-8")
    except OSError:
        pass


def conversation_id_of(cursor: dict[str, Any]) -> str:
    return str(cursor.get("conversation_id") or cursor.get("session_id") or "")


def payload_tick_key(event: str, cursor: dict[str, Any]) -> str:
    return "|".join((
        event,
        conversation_id_of(cursor),
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


def claim_ups_slot(cursor: dict[str, Any], event: str) -> bool:
    """True when this event should run UserPromptSubmit scripts.

    sessionStart often has only session_id; Cursor may also send a bootstrap
    generation_id. Write a conversation sentinel there so the first
    postToolUse of that conversation does not inject again, even when its
    generation_id differs. Later generations still inject.
    """
    conv = conversation_id_of(cursor)
    gen = str(cursor.get("generation_id") or "")
    if not conv and not gen:
        return True
    gen_sentinel = generation_ups_sentinel(f"{conv}|{gen}") if gen else None
    conv_sentinel = generation_ups_sentinel(f"{conv}|") if conv else None
    if event == "sessionStart":
        if conv_sentinel is not None:
            try:
                conv_sentinel.write_text("1", encoding="utf-8")
            except OSError:
                pass
        if gen_sentinel is not None:
            try:
                gen_sentinel.write_text("1", encoding="utf-8")
            except OSError:
                pass
        return True
    if gen_sentinel is not None and gen_sentinel.exists():
        if conv_sentinel is not None and conv_sentinel.exists():
            try:
                conv_sentinel.unlink()
            except OSError:
                pass
        return False
    if conv_sentinel is not None and conv_sentinel.exists():
        if gen_sentinel is not None:
            try:
                gen_sentinel.write_text("1", encoding="utf-8")
            except OSError:
                pass
        try:
            conv_sentinel.unlink()
        except OSError:
            pass
        return False
    if gen_sentinel is not None:
        try:
            gen_sentinel.write_text("1", encoding="utf-8")
        except OSError:
            pass
    elif conv_sentinel is not None:
        try:
            conv_sentinel.write_text("1", encoding="utf-8")
        except OSError:
            pass
    return True


def generation_ups_sentinel(key: str) -> Path:
    base = stash_dir()
    base.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(key.encode()).hexdigest()[:20]
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
    ran_scripts: set[str] = set()
    deadline = event_deadline("preToolUse")
    for entry in entries:
        if entry["event"] != "PreToolUse":
            continue
        script = entry["script"]
        if script in ran_scripts or script in SKIP_WITHOUT_TOOL_RESULT:
            continue
        hits = [name for name in candidates if matcher_hits(entry.get("matcher"), name)]
        if not hits:
            continue
        timeout = remaining_timeout(deadline, float(entry.get("timeout") or 10))
        if timeout is None:
            break
        ran_scripts.add(script)
        claude_tool = hits[0]
        payload = claude_payload_for_pretool(cursor, claude_tool)
        code, stdout, stderr = run_script(
            script, payload, timeout, entry.get("env"),
        )
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
    deadline = event_deadline("stop")
    for entry in entries:
        if entry["event"] != "Stop":
            continue
        if entry["script"] in SKIP_WITHOUT_TOOL_RESULT:
            continue
        timeout = remaining_timeout(deadline, float(entry.get("timeout") or 10))
        if timeout is None:
            break
        code, stdout, stderr = run_script(
            entry["script"], payload, timeout, entry.get("env"),
        )
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
    event: str = "postToolUse",
) -> str:
    if once_per_generation and not claim_ups_slot(cursor, event):
        return ""
    payload = claude_payload_for_transcript(cursor, "UserPromptSubmit")
    chunks: list[str] = []
    deadline = event_deadline(event)
    for entry in entries:
        if entry["event"] != "UserPromptSubmit":
            continue
        timeout = remaining_timeout(deadline, float(entry.get("timeout") or 10))
        if timeout is None:
            break
        _code, stdout, stderr = run_script(
            entry["script"], payload, timeout, entry.get("env"),
        )
        if stderr:
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        parsed, text = parse_hook_stdout(stdout)
        extra = collect_plain_or_json_context(parsed, text)
        if extra:
            chunks.append(extra)
    return "\n".join(chunks).strip()


def handle_session_start(cursor: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    extra = handle_user_prompt_submit(
        cursor, entries, once_per_generation=True, event="sessionStart",
    )
    if extra:
        return {"additional_context": extra}
    return {}


def handle_post_tool(cursor: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    parts: list[str] = []
    stashed = take_stashed_context(str(cursor.get("tool_use_id") or ""))
    if stashed:
        parts.append(stashed)
    extra = handle_user_prompt_submit(
        cursor, entries, once_per_generation=True, event="postToolUse",
    )
    if extra:
        parts.append(extra)
    if parts:
        return {"additional_context": "\n".join(parts)}
    return {}


HANDLERS: dict[str, Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]]] = {
    "preToolUse": handle_pretool,
    "stop": handle_stop,
    "sessionStart": handle_session_start,
    "postToolUse": handle_post_tool,
}


def mapped_cursor_events() -> set[str]:
    return {name for events in EVENT_MAPPING.values() for name in events}


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


def emit_result(key: str, result: dict[str, Any]) -> int:
    store_tick_result(key, result)
    print(json.dumps(result))
    return 0


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
    key = payload_tick_key(event, cursor)
    replay = claim_or_replay_tick(
        key, wait_s=float(WRAPPER_TIMEOUT_S.get(event, 60)),
    )
    if replay is not None:
        sys.stdout.write(replay if replay.endswith("\n") else replay + "\n")
        return 0
    try:
        entries = load_manifest()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"adapt-claude-hooks: cannot load hooks.json ({exc})", file=sys.stderr)
        return emit_result(key, fail_open_payload(event))

    handler = HANDLERS.get(event)
    try:
        result = handler(cursor, entries) if handler is not None else {}
    except Exception as exc:  # fail open
        print(f"adapt-claude-hooks: {event} failed ({exc})", file=sys.stderr)
        return emit_result(key, fail_open_payload(event))

    return emit_result(key, result)


if __name__ == "__main__":
    raise SystemExit(main())
