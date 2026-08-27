"""Test the flag-add-a-outside-pathspec guard, clause by clause.

Test case #1 is the incident verbatim -- `git add -A ':!inst/extdata'`, the
exact command run in `ucdavis/bcs` on 2026-08-09, reproduced in a scratch
repo shaped like the real one: `inst/extdata/` already carries a tracked
aggregate artifact (so it does NOT collapse to a single untracked directory
line), an untracked secret sits inside it (the exclusion's intended target,
must NOT warn), and an unrelated untracked scratch file sits at the repo
root (must warn). Per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against the
incident that prompted it, verbatim", the fixture mirrors the incident's own
repo shape rather than a summary of it -- a fully-untracked `inst/` would
collapse `git status --porcelain` to one `?? inst/` line and mask the very
distinction this hook exists to draw.

Unlike `test-flag-unchained-branch-switch.py`, this hook reads LIVE
repository state (`git status`), so each case is a real scratch git repo, not
just a JSON payload. `verdict()` builds one with `_repo()`, runs the hook with
`cwd` (optionally a subdirectory of it, for the cwd-scope cases) set to it,
and tears it down.

`cwd` matters here in a way it never does for a pure-text guard: this hook is
`PreToolUse`, so it always sees the session's cwd BEFORE the command runs --
a `cd sub && git add .` in one Bash call is checked from the ORIGINAL cwd,
not from `sub/`, since none of the command has executed yet. So the
cwd-scope cases below run the hook directly with `cwd=<repo>/sub` and a bare
`git add .`, which is what a session already sitting in `sub/` (from an
earlier Bash call) issuing this one would actually look like -- NOT a
`cd ... &&`-prefixed command, which this hook cannot and does not simulate
(a documented limitation, not a bug).

The second half is the same MUTATION harness described in
`shared/principles/fail-fast.md`'s "A guard whose condition ANDs several
clauses masks its own mutation test the same way": each clause is reverted on
its own and the cases expected to flip are checked against what actually
flipped. One clause (M5 glob-skip) declares an EMPTY expected-flip set rather
than faking coverage it does not have -- see its own comment.

Run:  python3 hooks/test-flag-add-a-outside-pathspec.py \\
          hooks/flag-add-a-outside-pathspec.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1])


def _run(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=check)


def _repo(build):
    """A scratch git repo, shaped by `build(path)`, torn down by the caller."""
    path = tempfile.mkdtemp()
    _run(path, "init", "-q")
    _run(path, "config", "user.email", "t@t.com")
    _run(path, "config", "user.name", "t")
    build(path)
    return path


def _write(path, *parts, content="x\n"):
    full = os.path.join(path, *parts)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(content)


def _commit(path, *files):
    _run(path, "add", *files)
    _run(path, "commit", "-qm", "init")


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ---------------------------------------------------------------- fixtures

def incident_repo(path):
    """The 2026-08-09 shape: inst/extdata/ has a tracked artifact already, an
    untracked secret sits inside it, and an unrelated scratch file sits at
    the repo root."""
    _write(path, "tracked.txt")
    _write(path, "inst", "extdata", "aggregate.rds")
    _commit(path, "tracked.txt", "inst/extdata/aggregate.rds")
    _write(path, "HANDOFF-2026-07-30.md", content="handoff notes\n")
    _write(path, "inst", "extdata", "creds.txt", content="secret\n")


def explicit_path_repo(path):
    """A single tracked file, plus one untracked file."""
    _write(path, "tracked.txt")
    _commit(path, "tracked.txt")
    _write(path, "HANDOFF.md")


def clean_repo(path):
    _write(path, "tracked.txt")
    _commit(path, "tracked.txt")


def clean_after_commit_repo(path):
    """Everything committed -- git status is empty."""
    _write(path, "tracked.txt")
    _write(path, "HANDOFF.md")
    _commit(path, "tracked.txt", "HANDOFF.md")


def update_only_target_repo(path):
    """A tracked file modified, and an untracked one beside it -- for
    `git add -u`, which must never warn regardless of what is untracked."""
    _write(path, "tracked.txt", content="v1\n")
    _commit(path, "tracked.txt")
    _write(path, "tracked.txt", content="v2\n")
    _write(path, "HANDOFF.md")


def cwd_scope_clean_sub_repo(path):
    """`sub/` itself is entirely clean; the only untracked file is OUTSIDE
    it. Run `git add .` from `sub/`, this must filter the outside file and
    stay silent -- a wrongly-unfiltered outside file would flip this to
    WARN, which is exactly M6's positive control."""
    _write(path, "tracked.txt")
    os.makedirs(os.path.join(path, "sub"))
    _write(path, "sub", "keep.txt")
    _commit(path, "tracked.txt", "sub/keep.txt")
    _write(path, "HANDOFF.md")            # outside sub/


def cwd_scope_mixed_repo(path):
    """Untracked files both inside and outside the scope `git add .` will
    run in, from `sub/` -- must still warn about the one INSIDE."""
    _write(path, "tracked.txt")
    os.makedirs(os.path.join(path, "sub"))
    _write(path, "sub", "keep.txt")
    _commit(path, "tracked.txt", "sub/keep.txt")
    _write(path, "HANDOFF.md")            # outside sub/
    _write(path, "sub", "new.txt", content="v1\n")   # untracked, inside sub/


def fully_excluded_repo(path):
    """The ONLY untracked content is inside the excluded directory --
    exercises `_is_excluded`'s PREFIX-match branch (the untracked path is
    something UNDER the exclusion, not equal to it)."""
    _write(path, "tracked.txt")
    _write(path, "inst", "extdata", "aggregate.rds")
    _commit(path, "tracked.txt", "inst/extdata/aggregate.rds")
    _write(path, "inst", "extdata", "creds.txt", content="secret\n")


def fully_excluded_file_repo(path):
    """The only untracked entry EQUALS the exclusion pathspec exactly (a
    single excluded file, not a directory) -- exercises `_is_excluded`'s
    exact-match branch, which the prefix-match branch above cannot reach."""
    _write(path, "tracked.txt")
    _commit(path, "tracked.txt")
    _write(path, "secret.txt", content="secret\n")


def named_include_repo(path):
    """`-A` combined with a SPECIFIC (non-`.`) inclusion pathspec is scoped
    to that pathspec, not the whole repo -- must not warn about a file
    elsewhere."""
    _write(path, "tracked.txt")
    os.makedirs(os.path.join(path, "sub"))
    _commit(path, "tracked.txt")
    _write(path, "HANDOFF.md")            # untracked, outside sub/
    _write(path, "sub", "new.txt", content="v1\n")


def glob_exclude_repo(path):
    """An exclusion pathspec containing a glob metacharacter -- must NOT be
    evaluated, so its target still shows up as unexcluded (safe direction)."""
    _write(path, "tracked.txt")
    _write(path, "logs", "keep.rds")
    _commit(path, "tracked.txt", "logs/keep.rds")
    _write(path, "logs", "new.log", content="v1\n")


# ---------------------------------------------------------------- cases
# (case_id, repo_builder, command, description, subdir)
# subdir is None (repo root) unless stated.

SHOULD_WARN = [
    ("W1", incident_repo, "git add -A ':!inst/extdata'", None,
     "TEST CASE #1: the incident, verbatim"),
    ("W2", explicit_path_repo, "git add -A", None,
     "bare -A with an untracked file present and no exclusion at all"),
    ("W3", explicit_path_repo, "git add .", None,
     "bare `.` with an untracked file present"),
    ("W4", explicit_path_repo, "git add --all", None,
     "`--all` is the long form of `-A`"),
    ("W5", cwd_scope_mixed_repo, "git add .", "sub",
     "cwd-scoped `.`, run from sub/, warns about the untracked file INSIDE it"),
    ("W6", glob_exclude_repo, "git add -A ':!logs/*.log'", None,
     "a glob exclusion pathspec is not evaluated; its target still warns "
     "(the safe direction)"),
    ("W7", explicit_path_repo, "env FOO=1 git add -A", None,
     "a lead word (`env`) and a VAR=value assignment are both skipped "
     "before matching the invocation"),
]

SHOULD_STAY_SILENT = [
    ("S1", explicit_path_repo, "git add HANDOFF.md", None,
     "an explicit path is not an 'add everything' invocation"),
    ("S2", clean_repo, "git add -A", None,
     "a clean tree has nothing to sweep in"),
    ("S3", clean_after_commit_repo, "git add -A", None,
     "everything already committed"),
    ("S4", update_only_target_repo, "git add -u .", None,
     "`-u` beats a bare `.` include -- never stages an untracked file, "
     "regardless of what is untracked"),
    ("S5", fully_excluded_repo, "git add -A ':!inst/extdata'", None,
     "the only untracked content is inside the excluded directory"),
    ("S11", fully_excluded_file_repo, "git add -A ':!secret.txt'", None,
     "the only untracked file equals the exclusion pathspec exactly"),
    ("S6", named_include_repo, "git add -A sub/", None,
     "`-A` combined with a specific (non-`.`) pathspec scopes to it, not "
     "the whole repo"),
    ("S7", explicit_path_repo, "echo 'git add -A' > note.txt", None,
     "a mention inside a quoted string is not an invocation"),
    ("S8", explicit_path_repo,
     "cat <<'EOF' > note.txt\ngit add -A\nEOF\n", None,
     "a heredoc that MENTIONS the command runs neither"),
    ("S9", explicit_path_repo, "git status", None,
     "a different git subcommand entirely"),
    ("S10", cwd_scope_clean_sub_repo, "git add .", "sub",
     "cwd-scoped `.`, run from a clean sub/, filters out the untracked file "
     "OUTSIDE it and finds nothing to warn about"),
]


def verdict(hook_path, repo, command, subdir):
    payload = bash(command)
    cwd = os.path.join(repo, subdir) if subdir else repo
    proc = subprocess.run(
        [sys.executable, hook_path], input=json.dumps(payload),
        capture_output=True, text=True, cwd=cwd,
    )
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {command!r}\n"
                 f"{proc.stderr.strip()}")
    if not proc.stdout.strip():
        return "silent"
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: hook emitted non-JSON on stdout ({exc}): "
                 f"{proc.stdout!r}")
    hso = out.get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        sys.exit(f"FATAL: hook emitted permissionDecision="
                 f"{hso['permissionDecision']!r}; this guard must only ever "
                 "add context, never allow/deny/ask")
    return "WARN" if hso.get("additionalContext") else "silent"


def build_and_verdict(hook_path, builder, command, subdir):
    repo = _repo(builder)
    try:
        return verdict(hook_path, repo, command, subdir)
    finally:
        shutil.rmtree(repo, ignore_errors=True)


if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would "
             "otherwise read as 'silent' on every case and print a perfect "
             "pass")

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()

EXPECTED = {case_id: "WARN" for case_id, *_ in SHOULD_WARN}
EXPECTED.update({case_id: "silent" for case_id, *_ in SHOULD_STAY_SILENT})
CASES = {case_id: (builder, command, subdir)
         for case_id, builder, command, subdir, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

wrong = 0
print("should WARN:")
for case_id, builder, command, subdir, desc in SHOULD_WARN:
    got = build_and_verdict(HOOK, builder, command, subdir)
    wrong += got != "WARN"
    print(f"  {got:<6} {case_id}  {desc}")

print("\nshould STAY SILENT:")
for case_id, builder, command, subdir, desc in SHOULD_STAY_SILENT:
    got = build_and_verdict(HOOK, builder, command, subdir)
    wrong += got != "silent"
    print(f"  {got:<6} {case_id}  {desc}")

total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT)
print(f"\n{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness

MUTATIONS = {
    "M2_lead_words": (
        "leading assignments/lead words are skipped before matching `git add`",
        [('        while i < len(argv) and (ASSIGNMENT.match(argv[i])\n'
          "                                  or argv[i] in LEAD_WORDS):\n"
          "            i += 1",
          "        pass")],
        {"W7"},
    ),
    "M3_bare_all": (
        "`-A`/`--all` with no including pathspec means whole-repo scope",
        [('    if has_all and not includes:\n        return "repo", excludes',
          "    if False:\n        return \"repo\", excludes")],
        {"W1", "W2", "W4", "W6", "W7"},
    ),
    "M3_bare_dot": (
        "a bare `.`/`./` including pathspec means cwd scope",
        [('    if any(inc.rstrip("/") in (".", "") for inc in includes):\n'
          '        return "cwd", excludes',
          '    if False:\n        return "cwd", excludes')],
        # S10 does NOT flip here: without dot-detection, `git add .` is
        # never classified as "add everything" at all, so the hook exits
        # before ever reaching the cwd-scope filter S10 exists to check --
        # it stays silent either way, for a different reason. S10's own
        # positive control is M6_cwd_filter below, not this clause.
        {"W3", "W5"},
    ),
    "M4_update_only": (
        "`-u`/`--update` beats a bare `.` include -- never stages an "
        "untracked file",
        [("    if has_update_only:\n        return None  # M4:"
          " never stages an untracked file",
          "    if False:\n        return None")],
        {"S4"},
    ),
    "M5_glob_not_evaluated": (
        "a glob-bearing exclusion pathspec excludes nothing (never matched "
        "as a literal path either)",
        [('        if any(ch in e for ch in "*?["):\n            continue  '
          "# M5: cannot statically evaluate a glob pathspec",
          "        if False:\n            continue")],
        # Declared EMPTY rather than faked: a glob string like `logs/*.log`
        # is never a literal PREFIX of the real untracked path `logs/new.log`
        # either, so evaluating it literally (this mutation) changes nothing
        # observable in this fixture. The clause is real defense-in-depth
        # (it stops a glob from ever being treated as a literal path at
        # all), but no case here constructs the coincidence that would make
        # its removal visible -- so this says "flipped nothing, as declared"
        # rather than silently omitting the mutation or padding a fake case.
        set(),
    ),
    "M5_exact_match": (
        "an untracked path is excluded when it equals an exclusion exactly "
        "(distinct from the prefix-match branch S5 exercises)",
        [("        if path == e or path.startswith(e + \"/\"):\n"
          "            return True",
          "        if path.startswith(e + \"/\"):\n            return True")],
        {"S11"},
    ),
    "M6_cwd_filter": (
        "cwd scope filters out untracked paths outside the current directory",
        [('    if scope == "cwd":\n'
          "        rel = _repo_relative_cwd()\n"
          '        if rel and rel != ".":\n'
          '            prefix = rel.rstrip("/") + "/"\n'
          "            untracked = [p for p in untracked\n"
          "                        if p == rel or p.startswith(prefix)]",
          "    if False:\n        pass")],
        {"S10"},
    ),
    "M_named_include_scopes": (
        "`-A` plus a specific non-`.` pathspec does NOT mean whole-repo scope",
        [('    if has_all and not includes:\n        return "repo", excludes\n'
          '    if any(inc.rstrip("/") in (".", "") for inc in includes):\n'
          '        return "cwd", excludes\n    return None',
          '    if has_all:\n        return "repo", excludes\n'
          '    if any(inc.rstrip("/") in (".", "") for inc in includes):\n'
          '        return "cwd", excludes\n    return None')],
        {"S6"},
    ),
}

print("\nmutation tests (revert one clause, see which cases flip):")
mutation_wrong = 0
with tempfile.TemporaryDirectory() as tmp:
    for clause, (statement, edits, expected_flips) in MUTATIONS.items():
        mutated = SOURCE
        for find, replace in edits:
            if mutated.count(find) != 1:
                sys.exit(f"FATAL: clause {clause}'s anchor is not present "
                         f"exactly once in {HOOK} (found "
                         f"{mutated.count(find)}). The mutation harness is "
                         "measuring nothing; re-derive the anchor.\n---\n"
                         f"{find}\n---")
            mutated = mutated.replace(find, replace)

        path = os.path.join(tmp, f"mutant-{clause}.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(mutated)

        flipped = {case_id for case_id, (builder, command, subdir) in CASES.items()
                   if build_and_verdict(path, builder, command, subdir)
                   != EXPECTED[case_id]}

        ok = flipped == expected_flips
        mutation_wrong += not ok
        if not flipped and expected_flips:
            note = "NOTHING FLIPPED -- this clause is untested"
        elif ok:
            note = ("flipped " + ", ".join(sorted(flipped))
                    if flipped else "flipped nothing, as declared")
        else:
            note = (f"flipped {sorted(flipped)}, expected "
                    f"{sorted(expected_flips)}")
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<24} {statement}\n"
              f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under reversion")

sys.exit(1 if (wrong or mutation_wrong) else 0)
