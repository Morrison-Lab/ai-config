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

CASES = [
    (UNSCOPED, True, "the unscoped python replace is blocked"),
    (SED_UNSCOPED, True, "an unscoped sed -i on a glyph is blocked"),
    (SCOPED, False, "a base-branch-scoped replace is allowed"),
    (SCAN, False, "a read-only glyph scan is allowed"),
    (OVERRIDE, False, "an explicit override is allowed"),
    (OTHER_REPLACE, False, "a non-glyph replace is allowed"),
    (UNRELATED, False, "an unrelated command is allowed"),
]


def run(cmd, tool="Bash"):
    payload = {"tool_name": tool, "tool_input": {"command": cmd}}
    out = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True,
    ).stdout
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
