#!/usr/bin/env python3
"""PreToolUse guard: refuse an unscoped whole-file punctuation replace.

`shared/coding/ascii-punctuation-in-source.md` bans em-dashes and friends
everywhere, and records the over-application too: a whole-file replace turns
a one-line finding into a huge diff. The rule exists and was broken twice on
2026-08-02 anyway, which is why this is a hook and not a stronger sentence.

THE COST IS NOT DIFF SIZE
-------------------------
A large mechanical diff HIDES real changes inside it. On the second instance
the same commit silently dropped two paragraphs during a conflict resolution,
and reading the 183-line diff did not surface it -- a normalized word-set
comparison did, reporting 13 lost words among ~44 false positives. So the
unscoped replace directly degrades the reviewability of whatever change it
rides along with.

THE CHECK
---------
For each MUTATING segment of the command (a segment whose leading command is
an interpreter), all of these must hold on THAT SAME segment:

  1. a punctuation-glyph replacement (mapping or .replace chain)
  2. a write-back (write_text / writelines / `>` / sed -i)
  3. NO scoping token (git show, origin/, HEAD:, diff, origset, ...)
  4. NO `ALLOW_WHOLE_FILE_PUNCT=1` env-assignment prefix on that segment

Requiring all of these keeps the two legitimate shapes silent: a read-only
scan fails (2), and a correctly scoped replace fails (3).

Evaluating per segment rather than over the whole command matters: a scope
token, a write-back, or an override assignment in an UNRELATED segment must
not decide the mutating one. `python3 <unscoped replace> && git diff` is
still blocked (the `git diff` is a different segment), and a read-only preview
followed by `echo ok > report.md` stays silent (the redirect is a different
segment). Segmentation is quote- and heredoc-aware, and a heredoc BODY is
attached to the segment that opened it -- so `python3 - <<'PY' && git add -A`
keeps the interpreter and its body together in one segment, and an
interpreter's own `;`/`|` inside its body does not split it.

Coverage is deliberately limited to `python`/`python3`/`sed`, the shapes the
recorded incident used. `perl`/`ruby`/`awk` in-place edits are the same
hazard but are not detected here; extending to them is a clean follow-up.

Fails OPEN, like every guard here. A hook that breaks Bash when a regex
misbehaves costs more than the mistake it prevents.
"""
import json
import re
import sys

# The banned glyphs, as literals and as escapes. `\N{...}` and HTML entities
# are included because a replace table can be written any of these ways. The
# escape branch must cover the curly DOUBLE quotes (U+201C/U+201D) too: `[c-d]`
# are hex nibbles a decimal `[4-9]` class cannot reach.
GLYPH = re.compile(
    r"\\u(?:201[3-9cd]|00d7)|\\N\{EM DASH\}|\\N\{EN DASH\}|"
    r"&mdash;|&ndash;|[\u2014\u2013\u201c\u201d\u2018\u2019\u00d7]",
    re.I,
)

# A replacement, not merely a mention. Either a .replace() call or a
# sed/tr substitution.
REPLACING = re.compile(
    r"\.replace\s*\(|\bre\.sub\s*\(|\bsed\b[^|]*-i|\btr\b\s+[^|]*[\"']",
    re.I,
)

# Writing the result back to a FILE. A read-only scan has none of these. A
# bare `.write(` is deliberately NOT here: it also matches `sys.stdout.write`
# and other stream writes, which touch no file -- and blocking a read-only
# preview is the false-positive direction this guard must avoid.
WRITING = re.compile(
    r"\.write_text\s*\(|\.writelines\s*\(|\bsed\b[^|]*-i|"
    r">\s*[\w./-]+\.(md|py|ya?ml|json|R|qmd)\b",
    re.I,
)

# Anything restricting the edit to lines this branch added. Deliberately
# broad: a false NEGATIVE here (letting a scoped replace through) is free,
# while a false POSITIVE blocks correct work.
SCOPED = re.compile(
    r"git\s+show|origin/|HEAD[:~^]|\bgit\s+diff|origset|orig_lines|"
    r"added_lines|--diff-filter|\bin\s+orig\b|not\s+in\s+orig|"
    r"changed_lines|diff-scoped",
    re.I,
)

# An explicit, deliberate corpus-wide cleanup. #685 and #720 track exactly
# that work, so it must remain possible. The override is a genuine shell
# env-assignment PREFIX on the mutating segment (`ALLOW_WHOLE_FILE_PUNCT=1
# python3 ...`), checked per segment -- NOT a bare mention of the token in a
# comment or an argument, and NOT an assignment on some unrelated segment.
OVERRIDE_ASSIGN = "ALLOW_WHOLE_FILE_PUNCT=1"

# Only an interpreter can actually rewrite a file here. Anchoring on the
# leading command is what keeps this quiet in a repo whose subject matter IS
# rules about punctuation: `gh issue comment --body '...replace...write...'`
# matches the text conditions while mutating nothing.
# `require-gh-repo-flag.py` solves the same false positive the same way.
MUTATORS = {"python", "python3", "sed"}
_ENV = re.compile(r"^\w+=\S*$")
_SKIP = {
    "cd", "then", "do", "done", "fi", "else", "elif",
    "if", "while", "until", "for", "!", "(", "{",
}


def _lead(segment):
    """(leading env-assignments, command word) for a segment. Env assignments
    are only those appearing BEFORE the command word, as shell requires."""
    env = []
    for word in segment.split():
        if _ENV.match(word):
            env.append(word)
        elif word in _SKIP:
            continue
        else:
            return env, word.split("/")[-1]
    return env, ""


def leading_command(segment):
    """First real command word of a segment, or '' -- skipping leading env
    assignments and shell control words."""
    return _lead(segment)[1]


def has_override(segment):
    """True iff this segment carries a genuine ALLOW_WHOLE_FILE_PUNCT=1
    env-assignment prefix (not a mere mention elsewhere in the text)."""
    return OVERRIDE_ASSIGN in _lead(segment)[0]


def split_segments(cmd):
    """Top-level shell segments, split on `&&`/`||`/`;`/`|` but not inside a
    quoted string. A heredoc body is glued onto the segment that OPENED it,
    even when an operator sits between the opener and the body's first line,
    so the interpreter and its stdin stay in one segment for evaluation."""
    segs = []
    cur = []
    pending = []          # [delim, owner_list] for heredoc bodies not yet read
    i, n = 0, len(cmd)

    def flush():
        nonlocal cur
        segs.append(cur)
        cur = []

    while i < n:
        c = cmd[i]
        if c == "'":                              # single-quoted string
            j = cmd.find("'", i + 1)
            if j == -1:
                cur.append(cmd[i:])
                i = n
                break
            cur.append(cmd[i:j + 1])
            i = j + 1
            continue
        if c == '"':                              # double-quoted string
            j = i + 1
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                j += 1
            end = j + 1 if j < n else n
            cur.append(cmd[i:end])
            i = end
            continue
        if cmd[i:i + 2] == "<<":                  # heredoc opener
            m = re.match(r"<<-?\s*([\"']?)(\w+)\1", cmd[i:])
            if m:
                cur.append(cmd[i:i + m.end()])
                pending.append([m.group(2), cur])
                i += m.end()
                continue
        if c == "\n":
            i += 1
            if not pending:
                s = "".join(cur)
                if (len(s) - len(s.rstrip("\\"))) % 2 == 1:
                    # backslash-newline is a line continuation, not a
                    # separator: drop the trailing `\` and join the lines.
                    cur = [s[:-1]]
                    continue
                flush()                           # bare newline = separator
                continue
            cur.append("\n")                      # opener line's own segment
            while pending and i < n:              # consume heredoc body/bodies
                delim, owner = pending[0]
                nl = cmd.find("\n", i)
                end = n if nl == -1 else nl
                line = cmd[i:end]
                owner.append(line)                # body -> its opener's segment
                if line.strip() == delim:
                    pending.pop(0)
                if nl == -1:
                    i = end
                else:
                    owner.append("\n")
                    i = end + 1
            continue
        mop = re.match(r"&&|\|\||;|\|", cmd[i:])   # top-level operator
        if mop:
            flush()
            i += mop.end()
            continue
        cur.append(c)
        i += 1
    flush()
    return ["".join(s) for s in segs]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool = payload.get("tool_name") or ""
        inp = payload.get("tool_input") or {}
        cmd = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""
    except Exception:
        return 0  # fail open

    if tool not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell") or not cmd:
        return 0

    # Block only when a SINGLE mutating segment satisfies all conditions on
    # its own: an interpreter is its leading command, it replaces a glyph and
    # writes back, nothing scopes it to added lines, and it carries no genuine
    # override assignment. A scope token, write, or override on a DIFFERENT
    # segment does not decide this one.
    blocked = any(
        leading_command(seg) in MUTATORS
        and not has_override(seg)
        and GLYPH.search(seg)
        and REPLACING.search(seg)
        and WRITING.search(seg)
        and not SCOPED.search(seg)
        for seg in split_segments(cmd)
    )
    if not blocked:
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "This command replaces punctuation glyphs and writes the file "
                "back, with nothing restricting it to lines this branch "
                "added. It will convert PRE-EXISTING glyphs on lines you "
                "never touched.\n\n"
                "The cost is not diff size. A large mechanical diff hides "
                "real changes inside it -- on 2026-08-02 exactly this "
                "silently dropped two paragraphs during a conflict "
                "resolution, invisible in a 183-line diff.\n\n"
                "Scope it to lines you added:\n\n"
                "    orig = subprocess.run(\n"
                "        ['git', 'show', f'origin/main:{f}'],\n"
                "        capture_output=True, text=True).stdout\n"
                "    origset = set(orig.splitlines())\n"
                "    for line in cur.splitlines(keepends=True):\n"
                "        if line.rstrip('\\n') not in origset and any(\n"
                "                c in line for c in BAD):\n"
                "            ...  # only lines this branch added\n\n"
                "A read-only SCAN is fine and is not blocked -- only a scan "
                "that writes back is.\n\n"
                "For a deliberate corpus-wide cleanup (#685, #720), say so: "
                "prefix the command with `ALLOW_WHOLE_FILE_PUNCT=1` (a real "
                "env assignment, not a mention), and land it as its own "
                "commit so it does not ride along with unrelated work."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
