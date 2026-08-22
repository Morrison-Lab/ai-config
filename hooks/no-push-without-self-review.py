#!/usr/bin/env python3
"""PreToolUse guard: require local adversarial self-review before git push.

Enforces that an AI agent runs local self-review using an adversarial reviewer
subagent (`adversarial-reviewer`) and obtains a clean verdict (`Ready for merge`)
before pushing to remote.

Authorized overrides:
- `ALLOW_UNREVIEWED_PUSH=1` (env assignment prefix)
- `--allow-unreviewed-push` (flag outside quotes)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

CMD_POS = r"""(?:^|[;&`(\n]|\$\()\s*"""
KEYWORD_PREFIX = r"""(?:(?:!|\{|time|nohup|sudo|then|else|do|if|elif|while|until)\s+){0,4}"""
VAR_PREFIX = r"""(?:(?:\$\{?[A-Za-z0-9_]+\}?|\$\([^)]*\)|`[^`]*`)\s*){0,4}"""
LEAD = CMD_POS + KEYWORD_PREFIX + VAR_PREFIX
ENV_WRAP = r"""(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*"""
GIT_PROG = r"(?:[/\w.-]+/)?(?:git|\$GIT|\$\{GIT\})\b"
DELIM = r"(?:\s+|\$\{IFS\}|\$IFS\b|\$\([^)]*\)|\$[A-Za-z0-9_]+)+"

PUSH_PATTERN = re.compile(
    LEAD + ENV_WRAP + GIT_PROG + DELIM + r"push\b"
)

ALLOW_ENV_FLAG = re.compile(
    r"^\s*(?:(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)\s+)*ALLOW_UNREVIEWED_PUSH=(?:\"1\"|'1'|1\b)"
)
SPLIT = re.compile(r"&&|\|\||;|\||\n")

CLEAN_VERDICT = re.compile(
    r"(?:###\s*Verdict|Verdict):\s*(?:\*\*)?Ready for merge\b",
    re.I,
)
BLOCKING_VERDICT = re.compile(
    r"(?:###\s*Verdict|Verdict):\s*(?:\*\*)?Needs (?:more )?work\b",
    re.I,
)
ADVERSARIAL_AGENT_NAME = re.compile(
    r"\b(?:adversarial|oppositional)(?:-reviewer)?\b",
    re.I,
)


def unquote_words(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'''(["'])([A-Za-z0-9_./-]+)\1''', r'\2', text)
        text = re.sub(r'''(?<=[A-Za-z0-9_./-])(?:""|'')(?:(?=[A-Za-z0-9_./-])|$)''', '', text)
        text = re.sub(r'''(?:^|(?<=[\s;&|`()]))(?:""|'')(?:(?=[A-Za-z0-9_./-])|$)''', '', text)
    return text


def has_allow_override(segment: str) -> bool:
    if ALLOW_ENV_FLAG.search(segment):
        return True

    for m in re.finditer(r"(?:^|[\s;&|`\n])(--allow-unreviewed-push)\b", segment):
        idx = m.start(1)
        in_single = in_double = escaped = False
        for i in range(idx):
            c = segment[i]
            if escaped:
                escaped = False
                continue
            if c == "\\" and not in_single:
                escaped = True
                continue
            if c == "'" and not in_double:
                in_single = not in_single
                continue
            if c == '"' and not in_single:
                in_double = not in_double
                continue
        if not in_single and not in_double:
            return True
    return False


def mask_trailing_comments(text: str) -> str:
    lines = text.split("\n")
    masked_lines = []
    for line in lines:
        in_single = in_double = escaped = False
        comment_start = -1
        for i, c in enumerate(line):
            if escaped:
                escaped = False
                continue
            if c == "\\" and not in_single:
                escaped = True
                continue
            if c == "'" and not in_double:
                in_single = not in_single
                continue
            if c == '"' and not in_single:
                in_double = not in_double
                continue
            if c == "#" and not in_single and not in_double:
                if i == 0 or line[i - 1] in " \t;&|`()":
                    comment_start = i
                    break
        if comment_start != -1:
            line = line[:comment_start] + " " * (len(line) - comment_start)
        masked_lines.append(line)
    return "\n".join(masked_lines)


def mask_subexpressions(val: str) -> str:
    sub_pattern = r"(`[^`]*`|\$\([^)]*\))"
    tokens = re.split(sub_pattern, val)
    result = []
    for i, tok in enumerate(tokens):
        if i % 2 == 1:
            result.append(tok)
        else:
            result.append("".join("\n" if c == "\n" else " " for c in tok))
    return "".join(result)


HEREDOC_START = re.compile(
    r"""<<-?[ \t]*(?:(['"])([A-Za-z_][A-Za-z0-9_]*)\1|([A-Za-z_][A-Za-z0-9_]*))"""
)


def _heredoc_intro(line: str):
    in_single = in_double = escaped = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if escaped:
            escaped = False
        elif c == "\\" and not in_single:
            escaped = True
        elif c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "<" and not in_single and not in_double:
            if line.startswith("<<<", i):
                i += 3
                continue
            m = HEREDOC_START.match(line, i)
            if m:
                return m
        i += 1
    return None


def mask_heredocs(text: str) -> str:
    lines = text.split("\n")
    out = list(lines)
    i = 0
    while i < len(lines):
        m = _heredoc_intro(lines[i])
        if not m:
            i += 1
            continue
        quoted = bool(m.group(2))
        delim = m.group(2) or m.group(3)
        j = i + 1
        while j < len(lines) and lines[j].strip() != delim:
            out[j] = " " * len(lines[j]) if quoted else mask_subexpressions(lines[j])
            j += 1
        i = j + 1
    return "\n".join(out)


def mask_payloads(text: str) -> str:
    flag_pattern = (
        r"(?:--body-file\b|--body\b|--title\b|--subject\b|--comment\b|--message\b|"
        r"--commit-title\b|--commit-message\b|--reason\b|--notes\b|--description\b|"
        r"--summary\b|-m\b|-b\b|-d\b|-t\b|-s\b)"
    )
    hspace = r"[ \t]*"

    def repl_double(m):
        return m.group(1) + mask_subexpressions(m.group(2))

    def repl_single(m):
        val = m.group(2)
        return m.group(1) + "".join("\n" if c == "\n" else " " for c in val)

    def repl_unquoted(m):
        return m.group(1) + mask_subexpressions(m.group(2))

    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(\"(?:\\.|[^\"])*\")", repl_double, text, flags=re.DOTALL)
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(\'(?:\\.|[^\'])*\')", repl_single, text, flags=re.DOTALL)
    text = mask_trailing_comments(text)
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(`[^`]*`|\$\([^)]*\)|[^-;\s&|\n][^;\s&|\n]*)", repl_unquoted, text)
    return text


def has_git_push(command: str) -> bool:
    norm_command = re.sub(r"\\\n", "", command)
    heredoc_masked = mask_heredocs(norm_command)
    unquoted_command = unquote_words(heredoc_masked)
    masked_command = mask_payloads(unquoted_command)

    for seg in SPLIT.split(masked_command):
        if PUSH_PATTERN.search(seg):
            if not has_allow_override(seg):
                return True
    return False


def verify_transcript_review_status(transcript_path: str) -> tuple[bool, str]:
    """Check if transcript records a local adversarial self-review with a clean verdict.

    Returns (is_clean, reason).
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return False, "No transcript available to verify local adversarial self-review."

    has_agent_invocation = False
    latest_verdict = None  # None, 'clean', or 'needs_work'

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue

                blocks = []
                if "message" in record and isinstance(record["message"], dict):
                    blocks.extend(record["message"].get("content") or [])
                elif "content" in record:
                    content = record.get("content")
                    if isinstance(content, list):
                        blocks.extend(content)
                    elif isinstance(content, str):
                        blocks.append({"type": "text", "text": content})

                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    b_type = b.get("type")
                    if b_type == "tool_use":
                        name = (b.get("name") or "").lower()
                        inp = b.get("input") or {}
                        if name in ("agent", "task", "invoke_subagent"):
                            sub_type = str(inp.get("subagent_type") or inp.get("TypeName") or inp.get("Role") or "")
                            prompt = str(inp.get("prompt") or inp.get("Prompt") or inp.get("description") or "")
                            if ADVERSARIAL_AGENT_NAME.search(sub_type) or ADVERSARIAL_AGENT_NAME.search(prompt):
                                has_agent_invocation = True
                    elif b_type in ("tool_result", "text"):
                        text = str(b.get("content") or b.get("output") or b.get("text") or "")
                        if CLEAN_VERDICT.search(text):
                            latest_verdict = "clean"
                        elif BLOCKING_VERDICT.search(text):
                            latest_verdict = "needs_work"
    except Exception as e:
        return False, f"Failed reading transcript: {e}"

    if not has_agent_invocation and latest_verdict != "clean":
        return False, (
            "No local adversarial self-review pass found in transcript.\n"
            "Run an adversarial self-review with the `adversarial-reviewer` subagent on your diff before pushing."
        )

    if latest_verdict == "needs_work":
        return False, (
            "The latest local adversarial self-review produced a 'Needs more work' verdict.\n"
            "Address or rebut all findings and achieve a 'Ready for merge' verdict before pushing."
        )

    if latest_verdict == "clean" or has_agent_invocation:
        return True, "Clean local self-review verified."

    return False, "Local self-review has not completed with a clean verdict."


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool_name = payload.get("tool_name") or ""
        if tool_name != "Bash":
            return 0

        cmd = (payload.get("tool_input") or {}).get("command") or ""
        if not cmd:
            return 0

        if not has_git_push(cmd):
            return 0

        transcript_path = payload.get("transcript_path") or ""
        is_clean, reason = verify_transcript_review_status(transcript_path)
        if is_clean:
            return 0

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"git push blocked by pre-push self-review policy:\n{reason}\n\n"
                    "Standing rule: Run self-review locally using the `adversarial-reviewer` subagent "
                    "against `git diff origin/main...HEAD` and obtain a clean verdict (`### Verdict: Ready for merge`) "
                    "before pushing.\n\n"
                    "If you are pushing an initial empty PR branch (per pr-on-claim) or need an emergency override, "
                    "prefix the command with `ALLOW_UNREVIEWED_PUSH=1`."
                ),
            }
        }))
        return 0
    except Exception:
        return 0  # fail open


if __name__ == "__main__":
    sys.exit(main())
