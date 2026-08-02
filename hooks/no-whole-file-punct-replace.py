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
Three conditions, ALL required:

  1. a punctuation-glyph replacement (mapping or .replace chain)
  2. a write-back (write_text / writelines / `>` / sed -i)
  3. NO scoping token (git show, origin/, HEAD:, diff, origset, ...)

Requiring all three keeps the two legitimate shapes silent: a read-only scan
fails (2), and a correctly scoped replace fails (3).

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
# pretend the case does not exist.
OVERRIDE = re.compile(r"ALLOW_WHOLE_FILE_PUNCT|#685\b|#720\b", re.I)


# Only an interpreter can actually rewrite a file here. Anchoring on the
# leading command is what keeps this quiet in a repo whose subject matter IS
# rules about punctuation: `gh issue comment --body '...replace...write...'`
# matches all three conditions in its TEXT while mutating nothing.
# `require-gh-repo-flag.py` solves the same false positive the same way.
MUTATORS = {"python", "python3", "sed", "perl", "ruby", "awk"}
_ENV = re.compile(r"^\s*(?:\w+=\S*\s+)*")


def leading_command(cmd):
    """First real command word of the last `&&`/`;`/`|` segment, or ''."""
    seg = re.split(r"&&|\|\||;|\|", cmd)
    for part in reversed(seg):
        part = _ENV.sub("", part).strip()
        if not part:
            continue
        word = part.split()[0].split("/")[-1]
        if word in {"cd", "then", "do", "fi"}:
            continue
        return word
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool = payload.get("tool_name") or ""
        cmd = (payload.get("tool_input") or {}).get("command") or ""
    except Exception:
        return 0  # fail open

    if tool != "Bash" or not cmd:
        return 0
    # Any segment run by an interpreter can mutate; a `gh`/`echo` command
    # merely quoting the pattern cannot.
    segments = re.split(r"&&|\|\||;", cmd)
    if not any(leading_command(s) in MUTATORS for s in segments):
        return 0
    if OVERRIDE.search(cmd):
        return 0
    if not (GLYPH.search(cmd) and REPLACING.search(cmd) and WRITING.search(cmd)):
        return 0
    if SCOPED.search(cmd):
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
