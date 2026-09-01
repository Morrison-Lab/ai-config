#!/usr/bin/env python3
"""Aider hook adapter: parse markdown chat history into JSON payloads.

Aider maintains session transcripts in Markdown format (`.aider.chat.history.md`).
This adapter parses markdown chat history into structured conversation turns,
generates standard JSONL transcripts compatible with repository hooks (such as
`hooks/no-empty-promise.py` and `hooks/no-mistake-without-a-hook.py`), and executes
configured hooks for Stop, PreToolUse, and UserPromptSubmit events.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any

# Default hook timeout in seconds when unspecified in hooks.json.
DEFAULT_HOOK_TIMEOUT = 30.0

# Regex patterns for matching Aider chat markers.
AIDER_SESSION_START = re.compile(
    r"^#\s+aider\s+chat\s+started\s+at\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
    re.IGNORECASE,
)
EXPLICIT_USER_HDR = re.compile(
    r"^(?:####\s+User:?|###\s+User:?|\*\*User:\*\*)\s*(.*)$",
    re.IGNORECASE,
)
EXPLICIT_ASST_HDR = re.compile(
    r"^(?:####\s+Assistant:?|###\s+Assistant:?|\*\*Assistant:\*\*)\s*(.*)$",
    re.IGNORECASE,
)
USER_PROMPT_HEADER = re.compile(
    r"^####\s+(?!User:|Assistant:)(.+)$",
    re.IGNORECASE,
)
USER_QUOTE_LINE = re.compile(r"^>\s*(.*)$")

# Tool execution markers in Aider history.
SHELL_COMMAND_LINE = re.compile(
    r"^(?:>\s*)?(?:/run|/test|run:|bash:)\s+(.+)$",
    re.IGNORECASE,
)
FILE_EDIT_LINE = re.compile(
    r"^(?:Applied\s+edit\s+to|Updated|Modified|Created|Wrote)\s+([^\s:]+)",
    re.IGNORECASE,
)
SEARCH_BLOCK_START = re.compile(r"^<{5,}\s*SEARCH")
DIVIDER_BLOCK = re.compile(r"^={5,}")
REPLACE_BLOCK_END = re.compile(r"^>{5,}\s*REPLACE")
COMMIT_LINE = re.compile(
    r"^(?:Commit\s+([0-9a-fA-F]{7,40})\s+(.+)|git\s+commit\s+(.+))$",
    re.IGNORECASE,
)


def _clean_path(raw: Any) -> str | None:
    """Normalize a path string, decoding file:// URIs and stripping whitespace."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    p = raw.strip()
    if p.startswith("file://"):
        p = urllib.parse.unquote(p[7:]).strip()
    return p if p else None


def find_repo_root(start_file: str | Path | None = None) -> Path:
    """Derive the repository root directory containing `hooks/hooks.json`."""
    target_file = Path(start_file or __file__).resolve()

    # 1. Check environment variable override
    for env_var in ("AI_CONFIG_ROOT", "CLAUDE_PLUGIN_ROOT"):
        val = os.environ.get(env_var)
        if val and (Path(val) / "hooks" / "hooks.json").is_file():
            return Path(val).resolve()

    # 2. Standard layout: 3 levels above plugins/ai-config/aider-hook-adapter.py
    candidate = target_file.parent.parent.parent
    if (candidate / "hooks" / "hooks.json").is_file():
        return candidate

    # 3. Direct parent walk
    curr = target_file.parent
    while curr != curr.parent:
        if (curr / "hooks" / "hooks.json").is_file():
            return curr
        curr = curr.parent

    return candidate


def find_history_file(cwd: str | Path | None = None) -> Path | None:
    """Locate `.aider.chat.history.md` in cwd or environment override."""
    env_override = os.environ.get("AIDER_CHAT_HISTORY_FILE")
    if env_override:
        p = Path(env_override)
        if p.is_file():
            return p.resolve()

    start_dir = Path(cwd or os.getcwd()).resolve()
    candidate = start_dir / ".aider.chat.history.md"
    if candidate.is_file():
        return candidate

    # Check parent directories up to git root or filesystem root
    curr = start_dir
    while curr != curr.parent:
        candidate = curr / ".aider.chat.history.md"
        if candidate.is_file():
            return candidate
        if (curr / ".git").exists():
            break
        curr = curr.parent

    return None


def parse_aider_chat_history(content_or_path: str | Path) -> list[dict[str, Any]]:
    """Parse Aider markdown chat history into structured conversation turns.

    Each turn is returned as a dict with:
    - role: "user" | "assistant" | "system"
    - content: string
    - tool_calls: list of {"name": str, "input": dict, "id": str}
    - tool_results: list of {"tool_use_id": str, "content": str}
    """
    if isinstance(content_or_path, Path) or (
        isinstance(content_or_path, str) and "\n" not in content_or_path and os.path.isfile(content_or_path)
    ):
        with open(content_or_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    else:
        lines = str(content_or_path).splitlines(keepends=True)

    turns: list[dict[str, Any]] = []
    current_role: str | None = None
    current_lines: list[str] = []
    current_tool_calls: list[dict[str, Any]] = []
    current_tool_results: list[dict[str, Any]] = []
    call_counter = 0

    def flush_current_turn():
        nonlocal current_role, current_lines, current_tool_calls, current_tool_results
        if current_role is not None and (current_lines or current_tool_calls or current_tool_results):
            text_content = "".join(current_lines).strip()
            turns.append({
                "role": current_role,
                "content": text_content,
                "tool_calls": list(current_tool_calls),
                "tool_results": list(current_tool_results),
            })
        current_lines = []
        current_tool_calls = []
        current_tool_results = []

    in_search_replace = False
    search_replace_file: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")

        # Session start header
        if AIDER_SESSION_START.match(line):
            flush_current_turn()
            current_role = "system"
            current_lines.append(line + "\n")
            flush_current_turn()
            current_role = None
            continue

        # Check for explicit User/Assistant section headers
        m_exp_user = EXPLICIT_USER_HDR.match(line)
        if m_exp_user:
            flush_current_turn()
            current_role = "user"
            content = m_exp_user.group(1).strip()
            if content:
                current_lines.append(content + "\n")
            continue

        m_exp_asst = EXPLICIT_ASST_HDR.match(line)
        if m_exp_asst:
            flush_current_turn()
            current_role = "assistant"
            content = m_exp_asst.group(1).strip()
            if content:
                current_lines.append(content + "\n")
            continue

        # Check for Aider user prompt header `#### <prompt>`
        m_prompt_hdr = USER_PROMPT_HEADER.match(line)
        if m_prompt_hdr:
            flush_current_turn()
            # User turn is the prompt in the header
            current_role = "user"
            current_lines.append(m_prompt_hdr.group(1).strip() + "\n")
            flush_current_turn()
            # Following lines become assistant turn until next user prompt
            current_role = "assistant"
            continue

        # Check for quote-style prompt lines `> ...` when not in an assistant turn or when starting prompt
        m_quote = USER_QUOTE_LINE.match(line)
        if m_quote and current_role != "user" and not in_search_replace and not current_tool_calls:
            # Check if this quote is a shell run command inside assistant turn vs user quote
            m_shell = SHELL_COMMAND_LINE.match(line)
            if not m_shell:
                flush_current_turn()
                current_role = "user"
                current_lines.append(m_quote.group(1).strip() + "\n")
                continue

        if m_quote and current_role == "user":
            current_lines.append(m_quote.group(1).strip() + "\n")
            continue

        # If we were in quote user mode and hit a non-quote line, flush and switch to assistant
        if current_role == "user" and not m_quote and line.strip():
            flush_current_turn()
            current_role = "assistant"

        # Search/replace block tracking
        if SEARCH_BLOCK_START.match(line):
            in_search_replace = True
            current_lines.append(raw_line)
            continue
        elif REPLACE_BLOCK_END.match(line):
            in_search_replace = False
            if search_replace_file:
                call_counter += 1
                call_id = f"call_edit_{call_counter}"
                current_tool_calls.append({
                    "id": call_id,
                    "name": "Edit",
                    "input": {"file_path": search_replace_file},
                })
                current_tool_results.append({
                    "tool_use_id": call_id,
                    "content": f"Applied edit to {search_replace_file}",
                })
            current_lines.append(raw_line)
            continue

        # Check for file path mentions preceding edits
        if not in_search_replace:
            words = line.strip().split()
            if len(words) == 1 and ("/" in words[0] or "." in words[0]) and not words[0].startswith("#"):
                search_replace_file = words[0]

        # Check for shell run
        m_shell = SHELL_COMMAND_LINE.match(line)
        if m_shell:
            cmd = m_shell.group(1).strip()
            call_counter += 1
            call_id = f"call_bash_{call_counter}"
            current_tool_calls.append({
                "id": call_id,
                "name": "Bash",
                "input": {"command": cmd},
            })
            current_tool_results.append({
                "tool_use_id": call_id,
                "content": f"Executed command: {cmd}",
            })
            current_lines.append(raw_line)
            continue

        # Check for edit line
        m_edit = FILE_EDIT_LINE.match(line)
        if m_edit:
            target_path = m_edit.group(1).strip()
            call_counter += 1
            call_id = f"call_edit_{call_counter}"
            current_tool_calls.append({
                "id": call_id,
                "name": "Edit",
                "input": {"file_path": target_path},
            })
            current_tool_results.append({
                "tool_use_id": call_id,
                "content": f"Applied edit to {target_path}",
            })
            current_lines.append(raw_line)
            continue

        # Check for git commit line
        m_commit = COMMIT_LINE.match(line)
        if m_commit:
            commit_cmd = f"git commit {m_commit.group(2) or m_commit.group(3) or ''}".strip()
            call_counter += 1
            call_id = f"call_commit_{call_counter}"
            current_tool_calls.append({
                "id": call_id,
                "name": "Bash",
                "input": {"command": commit_cmd},
            })
            current_tool_results.append({
                "tool_use_id": call_id,
                "content": f"Committed changes: {commit_cmd}",
            })
            current_lines.append(raw_line)
            continue

        # Default role to assistant if not set and line has text
        if current_role is None and line.strip():
            current_role = "assistant"

        current_lines.append(raw_line)

    flush_current_turn()
    return turns


def generate_jsonl_transcript(turns: list[dict[str, Any]], output_path: str | Path | None = None) -> Path:
    """Generate a JSONL transcript from structured turns compatible with repository hooks."""
    if output_path:
        out_file = Path(output_path)
    else:
        fd, temp_name = tempfile.mkstemp(prefix="aider_transcript_", suffix=".jsonl")
        os.close(fd)
        out_file = Path(temp_name)

    with open(out_file, "w", encoding="utf-8") as f:
        for turn in turns:
            role = turn.get("role", "user")
            text = turn.get("content", "")
            tool_calls = turn.get("tool_calls", [])
            tool_results = turn.get("tool_results", [])

            if role == "user":
                f.write(json.dumps({
                    "type": "user",
                    "source": "USER_EXPLICIT",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": text}],
                    },
                }) + "\n")
            elif role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                if text:
                    content_blocks.append({"type": "text", "text": text})
                for tc in tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", "call_1"),
                        "name": tc.get("name", "Bash"),
                        "input": tc.get("input", {}),
                    })

                f.write(json.dumps({
                    "type": "assistant",
                    "source": "MODEL",
                    "message": {
                        "role": "assistant",
                        "content": content_blocks,
                    },
                    "tool_calls": [
                        {"name": tc.get("name"), "args": tc.get("input", {})}
                        for tc in tool_calls
                    ],
                }) + "\n")

                # If there are tool results, emit them as user tool_result blocks
                if tool_results:
                    result_blocks = [
                        {
                            "type": "tool_result",
                            "tool_use_id": tr.get("tool_use_id", "call_1"),
                            "content": tr.get("content", ""),
                        }
                        for tr in tool_results
                    ]
                    f.write(json.dumps({
                        "type": "user",
                        "source": "TOOL_RESULT",
                        "message": {
                            "role": "user",
                            "content": result_blocks,
                        },
                    }) + "\n")
            elif role == "system":
                f.write(json.dumps({
                    "type": "system",
                    "source": "SYSTEM",
                    "message": {
                        "role": "system",
                        "content": [{"type": "text", "text": text}],
                    },
                }) + "\n")

    return out_file


def load_hooks_manifest(repo_root: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Load hooks configuration from hooks/hooks.json."""
    root = repo_root or find_repo_root()
    manifest_file = root / "hooks" / "hooks.json"
    if not manifest_file.is_file():
        return {}

    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("hooks", {})


def matches_tool(matcher_pattern: str | None, tool_name: str) -> bool:
    """Check if tool_name matches matcher_pattern."""
    if not matcher_pattern or matcher_pattern == "*":
        return True
    if matcher_pattern == tool_name:
        return True
    if "|" in matcher_pattern:
        parts = [p.strip() for p in matcher_pattern.split("|") if p.strip()]
        if tool_name in parts:
            return True
    try:
        return bool(re.search(matcher_pattern, tool_name))
    except re.error:
        return False


def run_hook_command(
    cmd: str,
    payload: dict[str, Any],
    cwd: str | Path,
    timeout_val: float,
    root: Path | None = None,
) -> tuple[int, str, str]:
    """Execute a single hook command with piped payload, returning (code, stdout, stderr)."""
    env = os.environ.copy()
    if root:
        env.update({
            "AI_CONFIG_ROOT": str(root),
            "CLAUDE_PLUGIN_ROOT": str(root),
            "PLUGIN_ROOT": str(root),
        })
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            cwd=str(cwd),
            timeout=timeout_val,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        print(f"aider-hook-adapter: hook timed out after {timeout_val}s", file=sys.stderr)
        return 0, "", "timeout"
    except Exception as exc:
        print(f"aider-hook-adapter: execution of hook failed: {exc}", file=sys.stderr)
        return 0, "", str(exc)


def execute_hooks_for_event(
    event: str,
    payload: dict[str, Any],
    cwd: str | Path,
    repo_root: Path | None = None,
    tool_name: str | None = None,
) -> dict[str, Any]:
    """Execute all registered hooks for a given event and return aggregated result."""
    root = repo_root or find_repo_root()
    manifest = load_hooks_manifest(root)
    event_groups = manifest.get(event, [])

    decision = "allow"
    reasons: list[str] = []
    warnings: list[str] = []
    injected_context: list[str] = []

    for group in event_groups:
        matcher = group.get("matcher")
        if event == "PreToolUse" and tool_name and not matches_tool(matcher, tool_name):
            continue

        hooks_list = group.get("hooks", [])
        for hook_entry in hooks_list:
            raw_cmd = hook_entry.get("command") or hook_entry.get("script")
            if not raw_cmd:
                continue

            cmd = raw_cmd.replace("${CLAUDE_PLUGIN_ROOT}", str(root)).replace("${PLUGIN_ROOT}", str(root))
            timeout_val = float(hook_entry.get("timeout") or DEFAULT_HOOK_TIMEOUT)

            code, out_txt, err_txt = run_hook_command(cmd, payload, cwd, timeout_val, root=root)

            # Check JSON stdout from hook
            if out_txt.strip():
                try:
                    hook_res = json.loads(out_txt.strip())
                    if isinstance(hook_res, dict):
                        hook_decision = hook_res.get("decision")
                        if hook_decision in ("block", "deny"):
                            decision = "block"
                            if hook_res.get("reason"):
                                reasons.append(hook_res["reason"])
                        if hook_res.get("systemMessage"):
                            warnings.append(hook_res["systemMessage"])
                        if hook_res.get("additionalContext"):
                            injected_context.append(hook_res["additionalContext"])
                except json.JSONDecodeError:
                    # Non-JSON stdout
                    pass

            # Exit code contract: only exit code 2 blocks; other non-zero exit codes warn
            if code != 0:
                detail = err_txt.strip() or f"exit code {code}"
                if code == 2:
                    decision = "block"
                    reasons.append(detail)
                else:
                    warnings.append(detail)

    return {
        "decision": decision,
        "reason": "\n\n".join(reasons) if reasons else None,
        "warnings": warnings,
        "injected_context": injected_context,
    }


def adapt_aider_event(
    event: str,
    history_path_or_content: str | Path | None = None,
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    cwd: str | Path | None = None,
    repo_root: Path | None = None,
    transcript_out: str | Path | None = None,
) -> dict[str, Any]:
    """Translate Aider chat history and execute hooks for the specified event."""
    effective_cwd = Path(cwd or os.getcwd()).resolve()
    effective_root = repo_root or find_repo_root()

    # Find history file if not provided
    if history_path_or_content is None:
        history_file = find_history_file(effective_cwd)
    elif isinstance(history_path_or_content, Path) or (
        isinstance(history_path_or_content, str)
        and "\n" not in history_path_or_content
        and os.path.isfile(history_path_or_content)
    ):
        history_file = Path(history_path_or_content).resolve()
    else:
        history_file = None

    if history_file and history_file.is_file():
        turns = parse_aider_chat_history(history_file)
    elif isinstance(history_path_or_content, str):
        turns = parse_aider_chat_history(history_path_or_content)
    else:
        turns = []

    # Generate JSONL transcript
    jsonl_path = generate_jsonl_transcript(turns, transcript_out)

    # Build standard payload
    payload: dict[str, Any] = {
        "session_id": f"aider-{hash(str(jsonl_path)) & 0xFFFFFFFFFFFFFFFF:016x}",
        "transcript_path": str(jsonl_path),
        "cwd": str(effective_cwd),
    }
    if tool_name:
        payload["tool_name"] = tool_name
    if tool_input is not None:
        payload["tool_input"] = tool_input

    # Execute hooks
    result = execute_hooks_for_event(
        event=event,
        payload=payload,
        cwd=effective_cwd,
        repo_root=effective_root,
        tool_name=tool_name,
    )
    result["transcript_path"] = str(jsonl_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aider hook adapter: parse markdown chat history into JSON payloads.",
    )
    parser.add_argument(
        "--event",
        choices=["Stop", "PreToolUse", "UserPromptSubmit", "PreInvocation"],
        default="Stop",
        help="Hook event type to execute (default: Stop)",
    )
    parser.add_argument(
        "--history-file",
        type=str,
        default=None,
        help="Path to .aider.chat.history.md file",
    )
    parser.add_argument(
        "--tool-name",
        type=str,
        default=None,
        help="Tool name for PreToolUse events (e.g. Bash, Edit)",
    )
    parser.add_argument(
        "--tool-input",
        type=str,
        default=None,
        help="JSON string of tool arguments for PreToolUse events",
    )
    parser.add_argument(
        "--cwd",
        type=str,
        default=None,
        help="Working directory path (default: current directory)",
    )
    parser.add_argument(
        "--transcript-out",
        type=str,
        default=None,
        help="Path to output generated JSONL transcript",
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Parse history and output parsed turns JSON without running hooks",
    )

    args = parser.parse_args()

    # Normalize tool input if provided
    tool_input_dict = None
    if args.tool_input:
        try:
            tool_input_dict = json.loads(args.tool_input)
        except Exception:
            tool_input_dict = {"command": args.tool_input}

    # Normalize event alias
    event = "UserPromptSubmit" if args.event == "PreInvocation" else args.event

    if args.parse_only:
        hist_path = args.history_file or find_history_file(args.cwd)
        if not hist_path:
            print(json.dumps({"error": "No history file found"}))
            return 1
        turns = parse_aider_chat_history(hist_path)
        print(json.dumps({"turns": turns}, indent=2))
        return 0

    res = adapt_aider_event(
        event=event,
        history_path_or_content=args.history_file,
        tool_name=args.tool_name,
        tool_input=tool_input_dict,
        cwd=args.cwd,
        transcript_out=args.transcript_out,
    )

    print(json.dumps(res, indent=2))
    return 0 if res.get("decision") == "allow" else 2


if __name__ == "__main__":
    sys.exit(main())
