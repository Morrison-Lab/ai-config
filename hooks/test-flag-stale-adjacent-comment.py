"""Test the flag-stale-adjacent-comment guard, clause by clause.

Case #1 is the `ucdavis/bcs#679` incident verbatim: the four-line comment
block above `#SBATCH --array=1-25%6`, and that directive changed to `%20`,
reproduced as the unified diff `git diff --cached -U10` would emit for it.
Per `shared/workflow/algorithmatize-checks.md`'s "Test the instrument against
the incident that prompted it, verbatim", the fixture carries the real comment
text rather than a summary -- including the `192G` arithmetic and the `32G`,
neither of which is reported.
`192` is not caught and structurally cannot be: it never appears on a REMOVED
line, only inside the unchanged comment, and M3 builds `old_lits` as
`removed_lits - added_lits`, so a literal that is never removed can never
become old. The check reports exactly one literal here, `6`, which the
incident-literal assertion below pins.

Most cases run against `findings()` over a diff string, because the detector
is pure over the diff. Two cases run the hook end-to-end through its JSON
protocol on a real scratch git repo, since the hook's own job is to derive
that diff from the staged tree at `git commit` time -- and one of those is a
negative control proving the hook can stay silent on a real repo, so a
uniformly-silent hook cannot pass by accident.

The last section is the MUTATION harness described in
`shared/principles/fail-fast.md`: each clause is broken on its own and the
cases expected to flip are checked against what actually flipped.

Run:  python3 hooks/test-flag-stale-adjacent-comment.py \\
          hooks/flag-stale-adjacent-comment.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

SUBJECT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "flag-stale-adjacent-comment.py")


def load(path):
    spec = importlib.util.spec_from_file_location("subject_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def hunk(path, body):
    """Wrap hunk `body` (already prefixed with ' ', '+', '-') in a diff."""
    return (f"diff --git a/{path} b/{path}\n"
            f"--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,20 +1,20 @@\n{body}")


# Case 1 -- the incident, verbatim.
INCIDENT = hunk("data-raw/ab507bs-imp.sbatch", """\
 #!/bin/bash
 #SBATCH --job-name=ab507bs-imp
 # Cap concurrent tasks at 6 (%6): each task needs 32G, so 6 running at once
 # already claims 192G, and capping bounds simultaneous network-FS I/O to the
 # setup/output .rds files -- an unbounded array here previously drained a
 # node with an unkillable process stuck on network I/O.
-#SBATCH --array=1-25%6
+#SBATCH --array=1-25%20
 #SBATCH --mem-per-cpu=32G
""")

# Case 2 -- negative control: the comment was updated in the same diff, so the
# stale text is on a REMOVED line, never on a context line.
UPDATED_TOO = hunk("data-raw/ab507bs-imp.sbatch", """\
 #!/bin/bash
-# Cap concurrent tasks at 6 (%6): 6 x 32G = 192G
+# Cap concurrent tasks at 20 (%20): 20 x 32G = 640G
-#SBATCH --array=1-25%6
+#SBATCH --array=1-25%20
""")

# Case 3 -- negative control: no comment anywhere near the change.
NO_COMMENT = hunk("conf/app.ini", """\
 [limits]
-workers = 6
+workers = 20
 queue = local
""")

# Case 4 -- negative control: the comment is FARTHER than WINDOW lines away.
FAR_COMMENT = hunk("conf/app.py", """\
 # workers is 6 by default
 a = 1
 b = 2
 c = 3
 d = 4
 e = 5
 f = 6666
 g = 7
 h = 8
 i = 9
 j = 10
 k = 11
-workers = 6
+workers = 20
""")

# Case 5 -- the value moved but the literal survives on an added line, so it
# is not an OLD literal at all (M3).
LITERAL_SURVIVES = hunk("conf/app.py", """\
 # retry 6 times before giving up
-retries = 6
+retries = 6 if fast else 20
""")

# Case 6 -- a quoted path changed, comment still names the old path (M4).
QUOTED_PATH = hunk("scripts/run.py", """\
 # reads from 'data/v6/raw.parquet' and writes a summary
-SRC = 'data/v6/raw.parquet'
+SRC = 'data/v7/raw.parquet'
""")

# Case 7 -- a long flag changed, comment still names the old flag (M4).
FLAG_CHANGE = hunk("scripts/run.sh", """\
 # --dry-run keeps this safe to re-run
-run --dry-run "$@"
+run --check-only "$@"
""")

# Case 8 -- a bare word changed. NOT a literal by M4, so nothing is reported
# even though the comment names it. This is a deliberate scope limit.
BARE_WORD = hunk("scripts/run.py", """\
 # uses the fallback backend
-BACKEND = fallback
+BACKEND = primary
""")

# Case 9 -- the changed number appears in the comment only as part of a LONGER
# number, which M6's boundary rule must not match.
SUBSTRING_ONLY = hunk("conf/app.py", """\
 # calibrated against the 1962 cohort
-workers = 6
+workers = 20
""")

# Case 10 -- a Markdown file: `#` is a heading, not a comment, so a heading
# carrying the old value must not be reported (M5).
MARKDOWN_HEADING = hunk("docs/notes.md", """\
 # Release 6 notes
-version = 6
+version = 20
""")

# A .qmd is Markdown-derived, so `#` opens a heading rather than a comment.
# Mapping .rmd/.qmd to `#` reproduced markdown_heading's false positive one
# extension over; this pins the fix.
QUARTO_HEADING = hunk("analysis/report.qmd", """\
 # Release 6 notes
-version = 6
+version = 20
""")

CASES = [
    ("incident", INCIDENT, True),
    ("comment_updated_too", UPDATED_TOO, False),
    ("no_comment", NO_COMMENT, False),
    ("far_comment", FAR_COMMENT, False),
    ("literal_survives", LITERAL_SURVIVES, False),
    ("quoted_path", QUOTED_PATH, True),
    ("flag_change", FLAG_CHANGE, True),
    ("bare_word", BARE_WORD, False),
    ("substring_only", SUBSTRING_ONLY, False),
    ("markdown_heading", MARKDOWN_HEADING, False),
    ("quarto_heading", QUARTO_HEADING, False),
]


def verdicts(mod):
    """name -> bool(any finding), for every diff-level case."""
    return {name: bool(mod.findings(diff)) for name, diff, _ in CASES}


# --------------------------------------------------------------------------
# End-to-end cases: the hook's own JSON protocol over a real scratch repo
# --------------------------------------------------------------------------

STALE_FILE = """\
#!/bin/bash
#SBATCH --job-name=ab507bs-imp
# Cap concurrent tasks at 6 (%6): each task needs 32G, so 6 running at once
# already claims 192G, and capping bounds simultaneous network-FS I/O to the
# setup/output .rds files -- an unbounded array here previously drained a
# node with an unkillable process stuck on network I/O.
#SBATCH --array=1-25%{cap}
#SBATCH --mem-per-cpu=32G
"""


def _run_hook(repo, command):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc = subprocess.run(
        [sys.executable, SUBJECT], input=json.dumps(payload),
        capture_output=True, text=True, cwd=repo)
    return proc.stdout.strip()


def _scratch_repo(cap_before, cap_after):
    repo = tempfile.mkdtemp(prefix="stale-comment-")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    def git(*args):
        subprocess.run(["git", *args], cwd=repo, env=env,
                       capture_output=True, check=True)
    git("init", "-q")
    os.makedirs(os.path.join(repo, "data-raw"))
    target = os.path.join(repo, "data-raw", "ab507bs-imp.sbatch")
    with open(target, "w") as fh:
        fh.write(STALE_FILE.format(cap=cap_before))
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    with open(target, "w") as fh:
        fh.write(STALE_FILE.format(cap=cap_after))
    git("add", "-A")
    return repo


def end_to_end_results():
    """(stale_out, clean_out, non_commit_out) -- raw hook stdout for each."""
    stale_repo = _scratch_repo("6", "20")
    clean_repo = _scratch_repo("6", "6\n#SBATCH --time=01:00:00")
    try:
        stale = _run_hook(stale_repo, "git commit -m 'raise the cap'")
        non_commit = _run_hook(stale_repo, "git status --porcelain")
        clean = _run_hook(clean_repo, "git commit -m 'add a time limit'")
    finally:
        shutil.rmtree(stale_repo, ignore_errors=True)
        shutil.rmtree(clean_repo, ignore_errors=True)
    return stale, clean, non_commit


# --------------------------------------------------------------------------
# Mutations
# --------------------------------------------------------------------------

MUTATIONS = [
    # M3: stop subtracting the added literals, so any literal on a removed
    # line counts as "old" -- `literal_survives` starts reporting.
    # `comment_updated_too` does NOT flip, and deliberately is not claimed to.
    # The reason is narrower than "M3 is never consulted": UPDATED_TOO's first
    # line `#!/bin/bash` IS an unchanged comment line, so M5 finds it and M3
    # does run. It does not flip because `_boundary_match("6", "#!/bin/bash")`
    # is False -- the literal simply does not occur in the shebang text.
    # Its coverage comes from the M5 marker mutation instead.
    ("M3 old-literal subtraction",
     "old_lits = removed_lits - added_lits",
     "old_lits = removed_lits",
     {"literal_survives"}),
    # M5: drop the distance window, so an arbitrarily distant comment counts.
    ("M5 proximity window",
     "near = [i for i in changed_idx if abs(i - ci) <= WINDOW]",
     "near = list(changed_idx)",
     {"far_comment"}),
    # M6: match by plain substring instead of on a word boundary, so `6`
    # matches inside `1962`.
    ("M6 word-boundary match",
     "    return re.search(pattern, text) is not None",
     "    return literal in text",
     {"substring_only"}),
    # M5: treat every file's `#` as a comment marker regardless of extension,
    # so a Markdown heading is read as a comment. Both Markdown-derived cases
    # flip, which is what pins .rmd/.qmd to the HTML comment marker rather than
    # to `#`.
    ("M5 per-extension markers",
     'COMMENT_MARKERS.get(ext, DEFAULT_MARKERS)',
     'DEFAULT_MARKERS',
     {"markdown_heading", "quarto_heading"}),
]


def run_mutations(baseline):
    src = open(SUBJECT).read()
    failures = 0
    for label, old, new, expected_flips in MUTATIONS:
        if src.count(old) != 1:
            print(f"FAIL: mutation '{label}' anchor matched "
                  f"{src.count(old)} times, expected 1")
            failures += 1
            continue
        tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
        tmp.write(src.replace(old, new))
        tmp.close()
        try:
            mutated = verdicts(load(tmp.name))
        except Exception as exc:
            print(f"FAIL: mutation '{label}' would not load ({exc})")
            failures += 1
            continue
        finally:
            os.unlink(tmp.name)
        flipped = {n for n in baseline if baseline[n] != mutated[n]}
        if flipped != expected_flips:
            print(f"FAIL: mutation '{label}' flipped {sorted(flipped)}, "
                  f"expected {sorted(expected_flips)}")
            failures += 1
        else:
            print(f"PASS: mutation '{label}' caught by {sorted(flipped)}")
    return failures


def main():
    mod = load(SUBJECT)
    failures = 0

    baseline = verdicts(mod)
    for name, _diff, expected in CASES:
        got = baseline[name]
        if got != expected:
            print(f"FAIL: case {name}: expected {expected}, got {got}")
            failures += 1
        else:
            print(f"PASS: case {name} ({'flagged' if got else 'silent'})")

    # The incident must report the `6` specifically, not merely something.
    incident = mod.findings(INCIDENT)
    lits = {lit for _p, lit, _s, _c in incident}
    if "6" not in lits:
        print(f"FAIL: incident literals {sorted(lits)} do not include '6'")
        failures += 1
    else:
        print(f"PASS: incident reports stale literals {sorted(lits)}")
    if "32" in lits:
        print("FAIL: incident reports '32', which the diff did not change")
        failures += 1
    else:
        print("PASS: incident does not report the unchanged '32'")

    stale, clean, non_commit = end_to_end_results()
    if not stale:
        print("FAIL: end-to-end stale commit produced no hook output")
        failures += 1
    else:
        try:
            payload = json.loads(stale)
        except ValueError:
            print("FAIL: end-to-end output is not JSON")
            failures += 1
            payload = {}
        ctx = (payload.get("hookSpecificOutput") or {}).get("additionalContext")
        if not ctx or "systemMessage" not in payload:
            print("FAIL: warn-only output must carry additionalContext "
                  "and systemMessage, never a permissionDecision")
            failures += 1
        elif "permissionDecision" in json.dumps(payload):
            print("FAIL: warn-only hook emitted a permissionDecision")
            failures += 1
        else:
            print("PASS: end-to-end stale commit warns via "
                  "additionalContext + systemMessage")
    if clean:
        print(f"FAIL: end-to-end clean commit produced output: {clean[:120]}")
        failures += 1
    else:
        print("PASS: end-to-end clean commit is silent (negative control)")
    if non_commit:
        print("FAIL: hook fired on a non-commit command")
        failures += 1
    else:
        print("PASS: hook silent on a non-commit command")

    failures += run_mutations(baseline)

    # +5: 2 incident-literal checks and 3 end-to-end checks. Was +6, which
    # reported 20 while printing 19 PASS lines.
    total = len(CASES) + len(MUTATIONS) + 5
    if failures:
        print(f"{failures} failure(s) across {total} checks")
        return 1
    print(f"all {total} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
