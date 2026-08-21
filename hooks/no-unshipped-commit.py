#!/usr/bin/env python3
"""Stop-hook guard: a successful commit must be pushed before reporting done."""
import hashlib
import json
import os
import re
import sys
import tempfile

COMMIT = re.compile(r"(?:^|[;&|\n]\s*)git\s+commit\b", re.MULTILINE)
PUSH = re.compile(r"(?:^|[;&|\n]\s*)git\s+push\b", re.MULTILINE)
CREATE = re.compile(r"(?:^|[;&|\n]\s*)gh\s+pr\s+create\b", re.MULTILINE)

# A heredoc body redirected INTO A FILE is text, not commands: `cat > x <<'EOF'
# ... EOF` writes the lines rather than running them. A corpus about git
# workflow quotes git commands inside issue and PR bodies constantly, and a
# line-oriented scan cannot tell a quoted example from an executed one --
# shared/writing/examples-are-scanned.md states exactly this, and names
# teaching the checker about quoted regions as the fix where we own it.
#
# Measured on ai-config#1806: filing an issue whose body quoted
# `pr-on-claim.md`'s own start-commit mechanic armed this guard, and the same
# command's `gh issue create` did not disarm it, so a fully-pushed session was
# told to push.
#
# ONLY the file-redirect form is stripped. `bash <<'EOF' ... EOF` genuinely
# executes its body, so a heredoc this does not recognise as a file write
# keeps arming the guard -- the unrecognised case fails toward the old
# behaviour rather than toward a hole.
HEREDOC_START = re.compile(r"(<<(-?))\s*(['\"]?)([A-Za-z_]\w*)\3")
# A redirect token on the heredoc-start line. This is necessary and NOT
# sufficient: `bash <<'EOF' > /tmp/log` redirects and still executes its body,
# and `2>&1` is fd duplication rather than a file write at all. WRITER below
# is what actually discriminates, so no fd-dup exclusion is spelled here --
# it would be unreachable, and an unpinned line in a safety guard is worse
# than an absent one.
REDIRECT = re.compile(r"[12]?>>?\s*\S")
# ...and the command word has to be one that WRITES its heredoc rather than
# running it. Testing only for "a redirect somewhere on the line" is not
# enough: `bash <<'EOF' > /tmp/log` redirects and still executes its body.
WRITER = re.compile(r"(?:^|[;&|]|&&|\|\|)\s*(?:cat|tee)\b[^<]*$")


def _terminates(line, tag, dash):
    """Match bash's heredoc terminator rule exactly."""
    return (line.lstrip("\t") if dash else line) == tag


def strip_quoted(command):
    """Drop heredoc bodies written to a file rather than executed."""
    lines = command.split("\n")
    kept, i = [], 0
    while i < len(lines):
        line = lines[i]
        start = HEREDOC_START.search(line)
        before = line[: start.start()] if start else ""
        if start and REDIRECT.search(HEREDOC_START.sub("", line)) and WRITER.search(before):
            kept.append(line)
            dash, tag = start.group(2), start.group(4)
            i += 1
            # Drop the body AND the terminator: neither is executed, and the
            # terminator line carries nothing this scans for. Keeping it was
            # an equivalent mutant -- no assertion could pin it, so it was
            # untestable code rather than tested code.
            # bash's real termination rule, not `.strip()`. A plain `<<TAG`
            # terminates only on a line equal to TAG with NO surrounding
            # whitespace; `<<-TAG` strips leading TABS only. `.strip()` was
            # looser than both, so an indented decoy `  EOF` ended the strip
            # early and exposed body text -- including a quoted `git push`,
            # which then discharged a genuinely pending commit.
            while i < len(lines) and not _terminates(lines[i], tag, dash):
                i += 1
            i += 1
            continue
        kept.append(line)
        i += 1
    return "\n".join(kept)


def pending_commit(path):
    pending = None
    try:
        with open(path, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if record.get("type") != "assistant":
                    continue
                for block in (record.get("message") or {}).get("content") or []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") not in {"Bash", "bash", "run_command"}:
                        continue
                    command = str((block.get("input") or {}).get("command") or (block.get("input") or {}).get("cmd") or (block.get("input") or {}).get("CommandLine") or "")
                    scanned = strip_quoted(command)
                    if COMMIT.search(scanned):
                        pending = command
                    if pending and (PUSH.search(scanned) or CREATE.search(scanned)):
                        pending = None
    except Exception:
        return None
    return pending


def last_assistant_text(path):
    last = ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if record.get("type") != "assistant":
                    continue
                blocks = (record.get("message") or {}).get("content") or []
                text = "".join(
                    b.get("text", "") for b in blocks
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                if text.strip():
                    last = text
    except Exception:
        return ""
    return last


def main():
    try:
        path = json.load(sys.stdin).get("transcript_path") or ""
    except Exception:
        return
    command = pending_commit(path)
    if not command:
        return
    text = last_assistant_text(path)
    key = hashlib.sha256((path + command + text).encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-unshipped-commit-{key}")
    if os.path.exists(sentinel):
        return
    open(sentinel, "w").close()
    print(json.dumps({"decision": "block", "reason": "A commit was made without a later push or PR creation. Push the branch, open or verify its PR, then report status. The standing rule is executable work, not a handoff item."}))


if __name__ == "__main__":
    main()
