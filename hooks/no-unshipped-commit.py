#!/usr/bin/env python3
"""Stop-hook guard: a successful commit must be pushed before reporting done."""
import hashlib
import json
import os
import re
import sys
import tempfile

# `(?![\w-])`, not `\b`. A word boundary sits happily between `commit` and
# `-`, because `-` is a non-word character -- so `git\s+commit\b` matched
# `git commit-tree`, plumbing that writes a commit object and moves no ref.
# There is nothing to push, by construction, so the call that used it never
# contained a `git push`, `pending` was never cleared, and every later Stop in
# the session blocked on a fully-pushed branch (ai-config#1963, measured while
# driving #1947). `git commit-graph write` is the second instance, and the one
# people actually run.
#
# PUSH carries the same guard for symmetry rather than as a second repair:
# `git push` has no hyphenated plumbing sibling today, so that half prevents
# the mirror bug instead of fixing a live one.
# `_ENV` tolerates leading NAME=value assignments before the command word.
# Without it, `ALLOW_UNREVIEWED_PUSH=1 git push` -- the sibling pre-push
# guard's own documented override spelling -- was invisible to PUSH, so a
# session whose every push carried the prefix was told on every Stop that a
# commit was never pushed, and only a literal no-op `git push` silenced it
# (ai-config#2365, #2395: three identical blocks on one shipped commit).
# The two guards' interaction guaranteed the loop: one required the prefix,
# the other could not see prefixed pushes.
_ENV = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
COMMIT = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+commit(?![\w-])", re.MULTILINE)
PUSH = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+push(?![\w-])", re.MULTILINE)
CREATE = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"gh\s+pr\s+create\b", re.MULTILINE)

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
# `(?<!<)` rejects the second `<` of a `<<<` HERESTRING. Without it,
# `cat <<< hello` parses as a heredoc with tag `hello`; a herestring has no
# body and no terminator line, so the terminator search runs off the end of
# the command and swallows EVERY remaining line -- unbounded trailing text,
# not one heredoc body. `cat <<< "$v" > /tmp/out` is an ordinary way to write
# a literal to a file, so this is reachable rather than contrived.
HEREDOC_START = re.compile(r"(?<!<)(<<(-?))\s*(['\"]?)([A-Za-z_]\w*)\3")
# Both tests below run against the pipeline/list SEGMENT that owns the
# heredoc, never the whole line. Scoping is the whole game here: on a whole
# line, `cat <<'EOF' | bash` finds `cat` and a redirect and calls an executed
# heredoc "data", and `cat notes > /tmp/x; bash <<'EOF'` does the same across
# a `;`. Both hide a real commit, which is the failure this guard exists to
# prevent.
SEPARATOR = re.compile(r"\|\||&&|[;&|]")
# A redirect to a file, within the owning segment. Necessary, not sufficient.
REDIRECT = re.compile(r"[12]?>>?\s*\S")
# The owning segment's command word must WRITE its heredoc rather than run it.
WRITER = re.compile(r"^\s*(?:cat|tee)\b")


def _owning_segment(line, start):
    """The pipeline/list segment containing the heredoc token.

    Separators inside quotes are not honoured. That is deliberate: a
    mis-split can only ever make the segment look LESS like a plain
    `cat`/`tee` write, so the guard keeps arming -- the safe direction.
    """
    cuts = [0] + [m.end() for m in SEPARATOR.finditer(line)] + [len(line)]
    for lo, hi in zip(cuts, cuts[1:]):
        if lo <= start.start() < hi:
            return line[lo:hi]
    return line


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
        segment = _owning_segment(line, start) if start else ""
        if (start and WRITER.search(segment)
                and REDIRECT.search(HEREDOC_START.sub("", segment))):
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



def unwrap_command(cmd):
    if not isinstance(cmd, str):
        return ""
    if cmd.startswith('"'):
        try:
            return json.loads(cmd)
        except Exception:
            # Handle truncated JSON strings by unescaping manually
            cmd = cmd[1:]
            if cmd.endswith('"'):
                cmd = cmd[:-1]
            return cmd.replace('\\n', '\n').replace('\\"', '"')
    return cmd

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
                commands = []
                if record.get("type") == "assistant":
                    for block in (record.get("message") or {}).get("content") or []:
                        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in {"Bash", "bash", "run_command"}:
                            cmd = str((block.get("input") or {}).get("command") or (block.get("input") or {}).get("cmd") or (block.get("input") or {}).get("CommandLine") or "")
                            commands.append(cmd)
                elif record.get("type") == "PLANNER_RESPONSE":
                    for block in (record.get("tool_calls") or []):
                        if isinstance(block, dict) and block.get("name") in {"Bash", "bash", "run_command"}:
                            args = block.get("args") or {}
                            cmd = str(args.get("CommandLine") or args.get("command") or args.get("cmd") or "")
                            cmd = unwrap_command(cmd)
                            commands.append(cmd)
                for command in commands:
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
                text = ""
                if record.get("type") == "assistant":
                    blocks = (record.get("message") or {}).get("content") or []
                    text = "".join(
                        b.get("text", "") for b in blocks
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                elif record.get("type") == "PLANNER_RESPONSE":
                    text = str(record.get("content") or "")

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
