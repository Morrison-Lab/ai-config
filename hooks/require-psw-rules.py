#!/usr/bin/env python3
"""PreToolUse DENY: prose edits to a notes page before the psw chapters were read.

Ezra, 2026-11-09 (ai-config#5166): content sessions keep missing rules that
the Principles of Scientific Writing (psw) states, and the CLAUDE.md prose that
tells them to read psw first was already missed (Classification thread,
2026-11-09). The condition is decidable from the transcript, so this DENIES
rather than reminds.

WHAT IS DENIED
--------------
A Write, Edit or MultiEdit on a `.qmd` file under a `chapters/` or `_subfiles/`
directory (a notes-site page or subfile), while the transcript holds no read
of each chapter in `REQUIRED`:

  * defining-terms.qmd
  * conciseness.qmd
  * relative-pronouns.qmd (grammar/)

An exercise or solution also needs `EXERCISE_REQUIRED`, the chapter that holds
the exercise rules (one ask per exercise, a solution per exercise):

  * teaching.qmd

The edit counts as an exercise or solution when the file's name has an `exr`
or `sol` part (`_boolean_exr.qmd`, `_exr-boolean.qmd`) or the written text opens
an `#exr-` or `#sol-` div. Such a file is gated wherever it lives, so the
question banks outside `chapters/` (mcsg `exercises/`) are covered too
(ai-config#5632: a session that passed the three-chapter gate wrote twelve
multi-part exercises on mcs#168).

DISCHARGE
---------
A read-shaped call naming the chapter under a `psw` directory,
`morrison-lab.github.io/psw` or `Morrison-Lab/psw`: a Read, a WebFetch, a
GitHub file-contents call, or a Bash command using a read command (cat, head,
sed, grep, curl and the like). An Edit, a Write, or a Bash `ls` or `rm` that
merely names the path does not count. The deny reason lists the paths and
URLs, so the next call can read them and retry.

Exempt: files under `hooks/`, `memories/`, `shared/` and `outtakes/` are not notes pages,
and psw's own `chapters/` are matched like any other (editing psw is the
likeliest time to need its rules).

Fails OPEN and SILENT on any payload, transcript or parse trouble: a wedged
session is worse than a missed gate.
"""
import json
import os
import re
import sys

REQUIRED = {
    "defining-terms.qmd": "chapters/defining-terms.qmd",
    "conciseness.qmd": "chapters/conciseness.qmd",
    "relative-pronouns.qmd": "chapters/grammar/relative-pronouns.qmd",
}
EXERCISE_REQUIRED = {
    "teaching.qmd": "chapters/teaching.qmd",
}
EDIT_TOOLS = {"Write", "Edit", "MultiEdit"}
READ_TOOLS = {"Read", "WebFetch", "mcp__github__get_file_contents"}
READ_CMD_RE = re.compile(
    r"(?:^|[;&|(\s])(?:cat|bat|head|tail|less|more|sed|awk|grep|rg|nl|view|curl|wget)\s")
PAGE_RE = re.compile(r"(?:^|/)(?:chapters|_subfiles)/(?:[^/]+/)*[^/]+\.qmd$")
EXERCISE_NAME_RE = re.compile(r"(?:^|/)_?(?:[^/]*[_-])?(?:exr|sol)(?:[_-][^/]*)?\.qmd$")
EXERCISE_DIV_RE = re.compile(r"\{\s*#(?:exr|sol)-")
EXEMPT_RE = re.compile(r"(?:^|/)(?:hooks|memories|shared|outtakes)/")
SOURCE_RE = re.compile(r"(?:morrison-lab\.github\.io/psw|Morrison-Lab/psw|(?:^|/)psw/)", re.I)

REASON = (
    "[hook: require-psw-rules] This edit changes a notes page "
    "(`{page}`), and this session has not read every psw chapter the lab's "
    "writing rules live in: {missing}.\n\n"
    "Ezra, 2026-11-09 (ai-config#5166): content sessions must load the psw "
    "rules before editing prose, because the pages repeatedly shipped rules "
    "psw already states. Read each missing chapter, from a psw checkout or "
    "from the published site, then retry:\n\n{sources}"
)


def tool_uses(transcript_path):
    with open(transcript_path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else rec
            blocks = msg.get("content")
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield block


def chapters_read(transcript_path):
    seen = set()
    for block in tool_uses(transcript_path):
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        tool = block.get("name") or ""
        text = " ".join(
            str(inp.get(k) or "") for k in ("file_path", "path", "command", "url"))
        if tool == "Bash":
            if not READ_CMD_RE.search(text):
                continue
        elif tool not in READ_TOOLS:
            continue
        if not SOURCE_RE.search(text):
            continue
        for name in {**REQUIRED, **EXERCISE_REQUIRED}:
            stem = name[:-4]
            if re.search(r"(?<![\w-])" + re.escape(stem) + r"(?:\.qmd|\.html)?(?![\w-])", text):
                seen.add(name)
    return seen


def written_text(inp):
    parts = [inp.get("content"), inp.get("new_string")]
    for edit in inp.get("edits") or []:
        if isinstance(edit, dict):
            parts.append(edit.get("new_string"))
    return "\n".join(str(x) for x in parts if x)


def edited_page(payload):
    """Return (path, required chapters) for a gated edit, else None."""
    if payload.get("tool_name") not in EDIT_TOOLS:
        return None
    inp = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    path = str(inp.get("file_path") or inp.get("path") or "").replace("\\", "/")
    if not path.endswith(".qmd") or EXEMPT_RE.search(path):
        return None
    exercise = bool(EXERCISE_NAME_RE.search(path) or EXERCISE_DIV_RE.search(written_text(inp)))
    if exercise:
        return path, {**REQUIRED, **EXERCISE_REQUIRED}
    if PAGE_RE.search(path):
        return path, REQUIRED
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        gated = edited_page(payload) if isinstance(payload, dict) else None
        if not gated:
            return 0
        page, required = gated
        transcript = payload.get("transcript_path")
        if not isinstance(transcript, str) or not os.path.isfile(transcript):
            return 0
        missing = [n for n in required if n not in chapters_read(transcript)]
        if not missing:
            return 0
    except Exception:
        return 0
    sources = "\n".join(
        f"- psw/{required[n]} (https://morrison-lab.github.io/psw/{required[n][:-4]}.html)"
        for n in missing)
    reason = REASON.format(
        page=os.path.basename(page), missing=", ".join(missing), sources=sources)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": reason,
        },
        "systemMessage": "Blocked: read the psw writing chapters before editing a notes page.",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
