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
an interpreter), all three conditions must hold on THAT SAME segment:

  1. a punctuation-glyph replacement (mapping or .replace chain)
  2. a write-back (write_text / writelines / `>` / sed -i)
  3. NO scoping token (git show, origin/, HEAD:, diff, origset, ...)

Requiring all three keeps the two legitimate shapes silent: a read-only scan
fails (2), and a correctly scoped replace fails (3).

Evaluating per segment rather than over the whole command matters: a scope
token or write-back in an UNRELATED segment must not decide the mutating one.
`python3 <unscoped replace> && git diff` is still blocked (the `git diff` is a
different segment), and a read-only preview followed by `echo ok > report.md`
stays silent (the redirect is a different segment). Segmentation respects
quotes and heredoc bodies, so an interpreter's own `;`/`|` inside its body
does not split it.

Fails OPEN, like every guard here. A hook that breaks Bash when a regex
misbehaves costs more than the mistake it prevents.
"""
import json
import re
import sys

# The banned glyphs, as literals and as escapes. `\N{...}` and HTML entities
# are included because a replace table can be written any of these ways.
GLYPH = re.compile(
    r"\\u201[4-9]|\\u2013|\\u00d7|\\N\{EM DASH\}|\\N\{EN DASH\}|"
    r"&mdash;|&ndash;|[\u2014\u2013\u201c\u201d\u2018\u2019\u00d7]",
    re.I,
)

# A replacement, not merely a mention. Either a .replace() call or a
# sed/tr substitution.
REPLACING = re.compile(
    r"\.replace\s*\(|\bre\.sub\s*\(|\bsed\b[^|]*-i|\btr\b\s+[^|]*[\"']",
    re.I,
)

# Writing the result back. A read-only scan has none of these.
WRITING = re.compile(
    r"\.write_text\s*\(|\.writelines\s*\(|\.write\s*\(|"
    r"\bsed\b[^|]*-i|>\s*[\w./-]+\.(md|py|ya?ml|json|R|qmd)\b",
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
# that work, so it must remain possible -- name the override rather than
# pretend the case does not exist. Require an actual `=1` assignment: a bare
# mention of the variable (or of an issue number) must NOT exempt the command.
OVERRIDE = re.compile(r"ALLOW_WHOLE_FILE_PUNCT=1\b")


# Only an interpreter can actually rewrite a file here. Anchoring on the
# leading command is what keeps this quiet in a repo whose subject matter IS
# rules about punctuation: `gh issue comment --body '...replace...write...'`
# matches all three conditions in its TEXT while mutating nothing.
# `require-gh-repo-flag.py` solves the same false positive the same way.
MUTATORS = {"python", "python3", "sed", "perl", "ruby", "awk"}
_ENV = re.compile(r"^\w+=\S*$")
_SKIP = {
    "cd", "then", "do", "done", "fi", "else", "elif",
    "if", "while", "until", "for", "!", "(", "{",
}


def leading_command(segment):
    """First real command word of a segment, or '' -- skipping leading env
    assignments and shell control words. The segment is one pipeline stage
    already (split_segments splits on `|` too), so no pipe-splitting here."""
    for word in segment.split():
        if _ENV.match(word) or word in _SKIP:
            continue
        return word.split("/")[-1]
    return ""


def _mask(cmd):
    """`cmd` with single/double-quoted strings and heredoc bodies blanked to
    spaces, same length as `cmd`. Used only to locate top-level shell
    operators without matching inside an interpreter's own body (a heredoc or
    a `-c` argument), which routinely contains `;`, `|`, and `&&`."""
    out = []
    i, n = 0, len(cmd)
    pending = []  # heredoc delimiters whose bodies are not yet consumed
    while i < n:
        c = cmd[i]
        if c == "'":
            j = cmd.find("'", i + 1)
            if j == -1:
                out.append(" " * (n - i))
                break
            out.append("'" + " " * (j - i - 1) + "'")
            i = j + 1
            continue
        if c == '"':
            j = i + 1
            buf = ['"']
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\" and j + 1 < n:
                    buf.append("  ")
                    j += 2
                    continue
                buf.append(" ")
                j += 1
            if j < n:  # closing quote
                buf.append('"')
                j += 1
            out.append("".join(buf))
            i = j
            continue
        if cmd[i:i + 2] == "<<":
            m = re.match(r"<<-?\s*([\"']?)(\w+)\1", cmd[i:])
            if m:
                pending.append(m.group(2))
                out.append(" " * m.end())
                i += m.end()
                continue
        if c == "\n":
            out.append("\n")
            i += 1
            while pending and i < n:  # consume heredoc body line by line
                nl = cmd.find("\n", i)
                end = n if nl == -1 else nl
                line = cmd[i:end]
                if line.strip() == pending[0]:
                    pending.pop(0)
                out.append(" " * len(line))
                if nl == -1:
                    i = end
                else:
                    out.append("\n")
                    i = end + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def split_segments(cmd):
    """Top-level shell segments, split on `&&`/`||`/`;`/`|` but not inside a
    quoted string or a heredoc body. Returns slices of the original `cmd`."""
    mask = _mask(cmd)
    parts, last = [], 0
    for m in re.finditer(r"&&|\|\||;|\|", mask):
        parts.append(cmd[last:m.start()])
        last = m.end()
    parts.append(cmd[last:])
    return parts


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool = payload.get("tool_name") or ""
        cmd = (payload.get("tool_input") or {}).get("command") or ""
    except Exception:
        return 0  # fail open

    if tool != "Bash" or not cmd:
        return 0
    if OVERRIDE.search(cmd):
        return 0

    # Block only when a SINGLE mutating segment satisfies all conditions on
    # its own: an interpreter is its leading command, it replaces a glyph and
    # writes back, and nothing in that segment scopes it to added lines. A
    # `gh`/`echo` segment merely quoting the pattern is not a mutator; a scope
    # token or write in a different segment does not decide this one.
    blocked = any(
        leading_command(seg) in MUTATORS
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
                "include `ALLOW_WHOLE_FILE_PUNCT=1` in the command, and land "
                "it as its own commit so it does not ride along with "
                "unrelated work."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
