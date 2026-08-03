"""Test the no-whole-file-punct-replace guard.

The negative cases carry the weight. A read-only scan and a correctly scoped
replace are the two things done constantly and correctly here, and a guard
that blocks either gets switched off -- taking the real case with it.

Run: python3 hooks/test-no-whole-file-punct-replace.py \\
         hooks/no-whole-file-punct-replace.py
"""
import json
import subprocess
import sys

HOOK = sys.argv[1]

# The exact shape run on 2026-08-02 that converted 71 pre-existing glyphs.
UNSCOPED = """python3 - <<'PY'
import pathlib
BAD={"\\u2014":"---","\\u2013":"-"}
for f in ["skills/ardi/SKILL.md"]:
    p=pathlib.Path(f); t=p.read_text(encoding="utf-8")
    for c,r in BAD.items(): t=t.replace(c,r)
    p.write_text(t,encoding="utf-8")
PY"""

# The correct shape: restricted to lines absent from the base branch.
SCOPED = """python3 - <<'PY'
import subprocess,pathlib
BAD={"\\u2014":"---"}
orig=subprocess.run(["git","show",f"origin/main:{f}"],capture_output=True,text=True).stdout
origset=set(orig.splitlines())
for line in cur.splitlines(keepends=True):
    if line.rstrip("\\n") not in origset:
        for c,r in BAD.items(): line=line.replace(c,r)
    out.append(line)
p.write_text("".join(out),encoding="utf-8")
PY"""

# Read-only: finds glyphs, writes nothing. Must never be blocked -- this is
# the pre-push check.
# A PREVIEW: computes the replacement and prints it, writing nothing. Uses
# .replace() on purpose -- without it the fixture never reaches the WRITING
# condition it exists to test, which is how the first version was vacuous.
SCAN = """python3 -c "
import pathlib
t=pathlib.Path('CLAUDE.md').read_text()
print(t.replace('\\u2014','---')[:200])"
"""

# A one-line `-c` form of the unscoped replace, for the segment-scoping cases
# below. Same four ingredients (glyph, replace, write, no scope) on one line.
INLINE_UNSCOPED = (
    "python3 -c \"import pathlib; "
    "p=pathlib.Path('a.md'); "
    "t=p.read_text().replace('\\u2014','---'); "
    "p.write_text(t)\""
)
# A mutator whose whole-file write is fed onward through a pipe. No top-level
# `;`/`&&` surfaces the interpreter, so selecting only the LAST pipeline stage
# (`tee`) would miss the mutation entirely -- every stage must be inspected.
# Deliberately statement-per-line (no `;`) so the whole thing is one segment.
PIPED = (
    "python3 -c \"\n"
    "import pathlib\n"
    "pathlib.Path('a.md').write_text("
    "pathlib.Path('a.md').read_text().replace('\\u2014','---'))\n"
    "\" | tee /tmp/x"
)
# An unscoped replace with an UNRELATED `git diff` in a second segment. The
# scope token belongs to `git diff`, not to the mutating command, so it must
# not exempt the replace.
COMPOUND_DIFF = INLINE_UNSCOPED + " && git diff --check"
# A read-only PREVIEW (no write) followed by an unrelated redirect. The `>`
# write belongs to `echo`, not to the interpreter, so the preview stays silent.
PREVIEW_THEN_WRITE = (
    "python3 -c \"import pathlib; "
    "print(pathlib.Path('a.md').read_text().replace('\\u2014','---')[:80])\""
    " && echo ok > report.md"
)
# A bare mention of the override token, and of an issue number, must NOT
# exempt an otherwise-blocked replace: only a real `=1` assignment does.
LOOSE_685 = INLINE_UNSCOPED + " # cleanup for #685"
BARE_VAR = INLINE_UNSCOPED + " # ALLOW_WHOLE_FILE_PUNCT (not set)"
SED_UNSCOPED = r"""sed -i '' 's/\u2014/---/g' skills/ardi/SKILL.md"""
OVERRIDE = "ALLOW_WHOLE_FILE_PUNCT=1 " + UNSCOPED
# Prose about the rule, e.g. this issue's own body being posted.
PROSE = (
    "gh issue comment 1046 --body 'the bad shape is t.replace(\"\\u2014\",\"---\") "
    "then p.write_text(t), which converts pre-existing glyphs'"
)
UNRELATED = "git status --short"
# Replacing something that is not a punctuation glyph.
OTHER_REPLACE = """python3 -c "
import pathlib
p=pathlib.Path('x.md'); t=p.read_text().replace('foo','bar'); p.write_text(t)"
"""

# A heredoc with a trailing shell operator on the OPENER line -- the exact
# incident shape. The body (glyph/replace/write) must stay attached to the
# interpreter segment, not orphaned into the `git add`/`tee` segment.
HEREDOC_TRAIL = (
    "python3 - <<'PY' && git add -A\n"
    "import pathlib\n"
    "p=pathlib.Path('skills/ardi/SKILL.md')\n"
    "p.write_text(p.read_text().replace('\\u2014','---'))\n"
    "PY"
)
HEREDOC_PIPE = HEREDOC_TRAIL.replace(" && git add -A", " | tee /tmp/log")
# The same heredoc-plus-trailing-operator shape, but correctly scoped inside
# the body -- must stay allowed even though it has a trailing `| tee`.
HEREDOC_TRAIL_SCOPED = (
    "python3 - <<'PY' | tee /tmp/log\n"
    "import subprocess,pathlib\n"
    "orig=subprocess.run(['git','show',f'origin/main:{f}'],"
    "capture_output=True,text=True).stdout\n"
    "origset=set(orig.splitlines())\n"
    "for line in cur.splitlines(keepends=True):\n"
    "    if line.rstrip('\\n') not in origset:\n"
    "        line=line.replace('\\u2014','---')\n"
    "    out.append(line)\n"
    "p.write_text(''.join(out))\n"
    "PY"
)
# A genuine `ALLOW_WHOLE_FILE_PUNCT=1` mentioned in text (a comment) is NOT an
# assignment prefix, and an assignment on an UNRELATED segment must not exempt
# the mutating one -- the override is checked per segment.
OVERRIDE_MENTION = INLINE_UNSCOPED + " # cleanup, see ALLOW_WHOLE_FILE_PUNCT=1 in docs"
OVERRIDE_CROSS = "ALLOW_WHOLE_FILE_PUNCT=1 echo starting && " + INLINE_UNSCOPED
# The ESCAPE form of a curly double quote (U+201C) -- a cleanup written the
# way the incident's own replace table is written. `[4-9]` can't reach hex
# `c`, so the escape branch must spell `201[cd]` out.
ESC_CURLY = (
    "python3 -c \"import pathlib; p=pathlib.Path('a.md'); "
    "p.write_text(p.read_text().replace('\\u201c','_'))\""
)
# A read-only preview that writes to a STREAM, not a file. `.write(` on its
# own must not count as a file write, or a genuine preview is blocked.
STDOUT_WRITE = (
    "python3 -c \"import pathlib,sys; "
    "sys.stdout.write(pathlib.Path('a.md').read_text().replace('\\u2014','---'))\""
)
# A bare top-level NEWLINE separates statements just like `;`. An unrelated
# preceding line (whose command isn't a mutator) must NOT merge with the
# incident payload and disarm the leading-command check.
NEWLINE_BYPASS = "echo starting\n" + INLINE_UNSCOPED
# ...and two individually-safe lines must NOT jointly trip the guard: a
# read-only preview on one line, an unrelated file write on the next.
NEWLINE_FALSEPOS = (
    "python3 -c \"import pathlib; "
    "print(pathlib.Path('a.md').read_text().replace('\\u2014','---')[:80])\"\n"
    "python3 -c \"import pathlib; pathlib.Path('report.md').write_text('done')\""
)
# A backslash-newline is a line CONTINUATION, not a statement separator, so
# splitting the interpreter from its `-c` payload across a continued line must
# still keep them in one segment. (Regression the newline-split fix would open
# without this: `python3 \<nl>-c "..."` is one command per `bash -n`.)
BACKSLASH_CONT = (
    "python3 \\\n"
    "-c \"import pathlib; p=pathlib.Path('a.md'); "
    "t=p.read_text().replace('\\u2014','---'); p.write_text(t)\""
)

CASES = [
    (UNSCOPED, True, "the unscoped python replace is blocked"),
    (INLINE_UNSCOPED, True, "the inline unscoped replace is blocked"),
    (SED_UNSCOPED, True, "an unscoped sed -i on a glyph is blocked"),
    (PIPED, True, "an unscoped replace piped onward is blocked"),
    (COMPOUND_DIFF, True,
     "an unrelated git-diff segment does not exempt the replace"),
    (LOOSE_685, True, "a bare #685 mention does not exempt the replace"),
    (BARE_VAR, True,
     "a bare override-var mention (no =1) does not exempt the replace"),
    (HEREDOC_TRAIL, True,
     "a heredoc with a trailing && operator is blocked"),
    (HEREDOC_PIPE, True,
     "a heredoc with a trailing | pipe is blocked"),
    (OVERRIDE_MENTION, True,
     "a text mention of ALLOW_WHOLE_FILE_PUNCT=1 does not exempt"),
    (OVERRIDE_CROSS, True,
     "an override assignment on an unrelated segment does not exempt"),
    (ESC_CURLY, True,
     "the escape form of a curly double quote is blocked"),
    (NEWLINE_BYPASS, True,
     "an unrelated line before the payload (bare newline) does not disarm it"),
    (BACKSLASH_CONT, True,
     "a backslash-newline continuation keeps the interpreter with its payload"),
    (SCOPED, False, "a base-branch-scoped replace is allowed"),
    (NEWLINE_FALSEPOS, False,
     "two safe lines separated by a newline are not jointly blocked"),
    (HEREDOC_TRAIL_SCOPED, False,
     "a scoped heredoc with a trailing pipe is allowed"),
    (SCAN, False, "a read-only glyph scan is allowed"),
    (STDOUT_WRITE, False,
     "a read-only preview writing to a stream is allowed"),
    (PREVIEW_THEN_WRITE, False,
     "a read-only preview with an unrelated redirect is allowed"),
    (OVERRIDE, False, "an explicit override is allowed"),
    (OTHER_REPLACE, False, "a non-glyph replace is allowed"),
    (UNRELATED, False, "an unrelated command is allowed"),
]


def run(cmd, tool="Bash"):
    payload = {"tool_name": tool, "tool_input": {"command": cmd}}
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True,
    )
    # A crashed hook must never read as "allow": the guard fails open only on
    # malformed INPUT (json errors), never on its own bug. Make a nonzero exit
    # fatal, as the neighboring hook harnesses do.
    if proc.returncode != 0:
        raise SystemExit(
            f"hook exited {proc.returncode} (a crash must not count as allow)\n"
            f"  cmd: {cmd!r}\n  stderr: {proc.stderr.strip()}"
        )
    out = proc.stdout
    return '"permissionDecision": "deny"' in out or '"permissionDecision":"deny"' in out


def main():
    passes = failures = 0
    for cmd, expected, label in CASES:
        got = run(cmd)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected deny={expected}, got {got})")
            failures += 1

    # Prose mentioning the pattern must not be blocked. Checked separately
    # because it is the false positive that would make this guard intolerable
    # in a repo whose whole subject matter is rules about punctuation.
    if not run(PROSE):
        print("PASS: prose describing the pattern is not blocked")
        passes += 1
    else:
        print("FAIL: prose describing the pattern must not be blocked")
        failures += 1

    # Only gates Bash.
    if not run(UNSCOPED, tool="Edit"):
        print("PASS: non-Bash tools are not gated")
        passes += 1
    else:
        print("FAIL: should only gate Bash")
        failures += 1

    # Fails open on malformed input rather than wedging every Bash call.
    r = subprocess.run(
        [sys.executable, HOOK], input="not json",
        capture_output=True, text=True,
    )
    if r.returncode == 0 and "deny" not in r.stdout:
        print("PASS: fails open on malformed input")
        passes += 1
    else:
        print("FAIL: should fail open on malformed input")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
