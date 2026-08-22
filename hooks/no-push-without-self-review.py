#!/usr/bin/env python3
"""PreToolUse guard: require local adversarial self-review before git push.

Enforces that an AI agent runs local self-review using an adversarial reviewer
subagent (`adversarial-reviewer`) and obtains a clean verdict (`Ready for merge`)
before pushing to remote.

WHY THE VERDICT SCAN IS ID-SCOPED RATHER THAN A TRANSCRIPT-WIDE PHRASE SEARCH
----------------------------------------------------------------------------
An earlier revision scanned every text/tool_result block in the transcript for
the verdict phrase. That is unfixable by tuning, for the reason
`no-handrolled-verdict-parse.py` already documents (ai-config#1297): verdict
vocabulary is quoted constantly by the very corpus that defines it, so a phrase
search cannot separate a verdict from a citation of one. Here it was worse than
unsound -- it was self-defeating. This guard's own denial message names the
phrase it looks for, a `PreToolUse` deny reason is surfaced back into the
transcript as the blocked call's result, and so one blocked push authorized
every retry after it. Reading `CLAUDE.md`, `skills/push/SKILL.md`, or this
hook's own persona file did the same thing, since each read is a `tool_result`
block carrying the phrase.

So a verdict counts only when it arrives as the `tool_result` of an `Agent`
call whose `subagent_type` IS the reviewer -- matched on that field alone,
never on the call's free-text prompt. That is a structural tie between the
permission and the reviewer's own output, and it is what makes the phrase in
the denial message below harmless rather than load-bearing.

CONSEQUENCE FOR HOW THE REVIEWER IS DISPATCHED
----------------------------------------------
A background dispatch returns an agent id rather than a report, so its verdict
never becomes that call's `tool_result` and this guard cannot see it. Dispatch
the reviewer in the foreground (`run_in_background: false`), which is correct
anyway: the push is waiting on the answer.

A clean verdict also goes stale. A file edit recorded after it describes a tree
the reviewer never read, so the guard requires the clean verdict to be the last
of the two.

Authorized overrides:
- `ALLOW_UNREVIEWED_PUSH=1` (env assignment prefix)
- `--allow-unreviewed-push` (flag outside quotes)
"""
from __future__ import annotations

import json
import os
import re
import sys

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

# One pattern for BOTH verdicts, so a body carrying more than one is read
# left-to-right and the LAST one wins. Two separate searches cannot order their
# matches against each other, which is how a review that opens by quoting the
# blocking verdict it is superseding gets read as blocking.
VERDICT = re.compile(
    r"(?:###\s*Verdict|Verdict):\s*(?:\*\*)?(Ready for merge|Needs (?:more )?work)\b",
    re.I,
)

# Matched against an Agent/Task call's `subagent_type` ONLY. The earlier
# revision also matched the call's free-text `prompt`, which any prompt
# containing the word "adversarial" satisfied -- including a prompt asking some
# other agent to do something else entirely.
ADVERSARIAL_AGENT_NAME = re.compile(r"\A\s*adversarial[-_ ]?reviewer\s*\Z", re.I)

# Tool names that dispatch a subagent.
AGENT_TOOLS = {"agent", "task", "invoke_subagent"}

# Tool names that change a file in the working tree. A clean verdict recorded
# BEFORE one of these describes a tree the reviewer never read.
EDIT_TOOLS = {"edit", "write", "multiedit", "notebookedit", "applypatch",
              "str_replace_editor", "str_replace_based_edit_tool"}


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


def _result_text(block: dict) -> str:
    """Flatten a tool_result block's payload into one searchable string.

    A subagent's report arrives as `content`, which is a plain string in some
    transports and a list of content blocks in others. Reading only one shape
    silently returns "" for the other, and an empty string is indistinguishable
    from a report that stated no verdict.
    """
    parts: list[str] = []
    content = block.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for sub in content:
            if isinstance(sub, str):
                parts.append(sub)
            elif isinstance(sub, dict):
                parts.append(str(sub.get("text") or sub.get("content") or ""))
    for key in ("output", "text"):
        val = block.get(key)
        if isinstance(val, str):
            parts.append(val)
    return "\n".join(p for p in parts if p)


def _iter_blocks(record: dict):
    if isinstance(record.get("message"), dict):
        blocks = record["message"].get("content") or []
    else:
        blocks = record.get("content")
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        elif not isinstance(blocks, list):
            blocks = []
    for b in blocks:
        if isinstance(b, dict):
            yield b


def verify_transcript_review_status(transcript_path: str) -> tuple[bool, str]:
    """Decide whether the transcript records a CURRENT clean adversarial review.

    A verdict is admitted only from the `tool_result` of an `Agent` call whose
    `subagent_type` is the adversarial reviewer -- see this module's docstring
    for why a transcript-wide phrase search cannot work here.

    Returns (is_clean, reason).
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return False, "No transcript available to verify local adversarial self-review."

    reviewer_call_ids: set[str] = set()
    saw_reviewer_call = False
    verdict: str | None = None          # None | "clean" | "needs_work"
    verdict_seq = -1
    last_edit_seq = -1
    seq = 0

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
                if not isinstance(record, dict):
                    continue

                seq += 1
                for b in _iter_blocks(record):
                    b_type = b.get("type")

                    if b_type == "tool_use":
                        name = (b.get("name") or "").lower()
                        if name in AGENT_TOOLS:
                            inp = b.get("input") or {}
                            sub_type = str(
                                inp.get("subagent_type")
                                or inp.get("subagentType")
                                or inp.get("agent_type")
                                or ""
                            )
                            if ADVERSARIAL_AGENT_NAME.match(sub_type):
                                saw_reviewer_call = True
                                call_id = b.get("id")
                                if isinstance(call_id, str) and call_id:
                                    reviewer_call_ids.add(call_id)
                        elif name in EDIT_TOOLS:
                            last_edit_seq = seq

                    elif b_type == "tool_result":
                        if b.get("tool_use_id") not in reviewer_call_ids:
                            continue
                        found = VERDICT.findall(_result_text(b))
                        if found:
                            verdict = (
                                "clean"
                                if found[-1].lower().startswith("ready")
                                else "needs_work"
                            )
                            verdict_seq = seq
    except Exception as e:
        return False, f"Failed reading transcript: {e}"

    if not saw_reviewer_call:
        return False, (
            "No `adversarial-reviewer` subagent was dispatched in this session.\n"
            "Dispatch it against your diff and address its findings before pushing."
        )

    if verdict is None:
        return False, (
            "An `adversarial-reviewer` subagent was dispatched, but no verdict came "
            "back as that call's result.\n"
            "Dispatch it in the foreground (`run_in_background: false`) so its report "
            "returns as the tool result -- a background dispatch returns an agent id, "
            "which carries no verdict."
        )

    if verdict == "needs_work":
        return False, (
            "The latest adversarial self-review returned a blocking verdict.\n"
            "Address, rebut, or defer every finding and obtain a clean verdict before pushing."
        )

    if last_edit_seq > verdict_seq:
        return False, (
            "The clean adversarial self-review is stale: a file was edited after it.\n"
            "Re-dispatch `adversarial-reviewer` against the current diff, so the verdict "
            "describes the tree you are about to push."
        )

    return True, "Clean adversarial self-review verified against the current tree."


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
                    "Standing rule: every self-review is an adversarial review by a separate "
                    "subagent. Dispatch `adversarial-reviewer` (foreground) against "
                    "`git diff origin/<default-branch>...HEAD`, address or rebut every finding, "
                    "and obtain its clean verdict before pushing.\n\n"
                    "Only that subagent's own result counts -- this message does not, and neither "
                    "does reading a file that quotes a verdict.\n\n"
                    "If you are pushing an initial empty PR branch (per pr-on-claim) or need an "
                    "emergency override, prefix the command with `ALLOW_UNREVIEWED_PUSH=1`."
                ),
            }
        }))
        return 0
    except Exception:
        return 0  # fail open


if __name__ == "__main__":
    sys.exit(main())
