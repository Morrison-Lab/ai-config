"""Test the flag-reset-hard-uncommitted-work guard, clause by clause.

Test case #1 is the incident verbatim: a base commit, a throwaway "probe"
commit on top of it, then UNRELATED uncommitted edits to two already-tracked
files, then `git reset --hard <base-sha>` -- the exact shape of the
2026-08-09 `ucdavis/bcs` incident (a synthetic-secret probe commit dropped
with `reset --hard`, taking unrelated `.Rbuildignore`/`NEWS.md` edits with
it). Per `shared/workflow/algorithmatize-checks.md`'s "Test the instrument
against the incident that prompted it, verbatim", the fixture reproduces the
INCIDENT'S OWN SEQUENCE (commit, then a second commit, then dirty the tree,
then reset to the first) rather than a shorter summary of "some dirty
files exist somewhere".

Like `test-flag-add-a-outside-pathspec.py`, this hook reads LIVE repository
state, so each case is a real scratch git repo, not just a JSON payload.

The second half is the MUTATION harness described in
`shared/principles/fail-fast.md`'s "A guard whose condition ANDs several
clauses masks its own mutation test the same way".

Run:  python3 hooks/test-flag-reset-hard-uncommitted-work.py \\
          hooks/flag-reset-hard-uncommitted-work.py
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


def _write(path, *parts, content="x\n"):
    full = os.path.join(path, *parts)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(content)


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ---------------------------------------------------------------- fixtures
# Each returns (repo_path, command) -- the command embeds the base commit's
# own SHA, which only exists once the fixture repo is built, so the command
# is built alongside the repo rather than declared as a static string.

def _new_repo():
    path = tempfile.mkdtemp()
    _run(path, "init", "-q")
    _run(path, "config", "user.email", "t@t.com")
    _run(path, "config", "user.name", "t")
    return path


def _head(path):
    return _run(path, "rev-parse", "HEAD").stdout.strip()


def incident_case(path):
    """TEST CASE #1: base commit, a probe commit on top, then unrelated
    uncommitted edits to files the base commit already tracked -- then
    `git reset --hard <base>`."""
    _write(path, "NEWS.md")
    _write(path, ".Rbuildignore")
    _run(path, "add", "NEWS.md", ".Rbuildignore")
    _run(path, "commit", "-qm", "init")
    base = _head(path)

    _write(path, "probe.txt", content="secret\n")
    _run(path, "add", "probe.txt")
    _run(path, "commit", "-qm", "probe")

    _write(path, "NEWS.md", content="unrelated edit\n")
    _write(path, ".Rbuildignore", content="unrelated edit\n")
    return f"git reset --hard {base}"


def clean_hard_case(path):
    """A commit to drop, but nothing else uncommitted -- reset --hard here
    discards only the commit itself, which reflog can always recover."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    base = _head(path)

    _write(path, "probe.txt", content="secret\n")
    _run(path, "add", "probe.txt")
    _run(path, "commit", "-qm", "probe")
    return f"git reset --hard {base}"


def bare_hard_dirty_case(path):
    """`git reset --hard` with NO ref -- defaults to HEAD, still discards
    uncommitted tracked changes."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    return "git reset --hard"


def staged_only_dirty_case(path):
    """A STAGED (not committed) change -- must still warn, since --hard
    discards the index too, not just the working tree."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="staged\n")
    _run(path, "add", "tracked.txt")
    return "git reset --hard"


def untracked_only_case(path):
    """Only an UNTRACKED file present -- `reset --hard` never touches
    untracked files (that is `git clean`'s job), so this must not warn."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "scratch.md")
    return "git reset --hard"


def mixed_case(path):
    """A dirty tracked file present alongside an untracked one -- must warn
    (about the tracked one), regardless of the untracked file also there."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    _write(path, "scratch.md")
    return "git reset --hard"


def plain_reset_case(path):
    """`git reset` with NO `--hard` -- unstages only, never discards
    working-tree content, so this must not warn even on a dirty tree."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    return "git reset"


def mixed_mode_flags_case(path):
    """`--mixed` and `--hard` both present (redundant, but valid syntax --
    the LAST mode wins in real git); `--hard` is present, so this must warn."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    return "git reset --mixed --hard"


def lead_word_case(path):
    """A lead word (`sudo`) and an assignment are both skipped before
    matching the invocation."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    return "sudo FOO=1 git reset --hard"


def mention_in_string_case(path):
    """A mention of the command inside a quoted string is not an
    invocation."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    return "echo 'git reset --hard' > note.txt"


def heredoc_mention_case(path):
    """A heredoc that MENTIONS the command runs neither."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    return "cat <<'EOF' > note.txt\ngit reset --hard\nEOF\n"


def different_subcommand_case(path):
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    return "git status"


def other_subcommand_with_hard_token_case(path):
    """A different git subcommand that happens to carry a `--hard`-shaped
    token -- must not be mistaken for `git reset --hard`."""
    _write(path, "tracked.txt")
    _run(path, "add", "tracked.txt")
    _run(path, "commit", "-qm", "init")
    _write(path, "tracked.txt", content="dirty\n")
    return "git tag --hard"


# ---------------------------------------------------------------- cases
# (case_id, builder, description)

SHOULD_WARN = [
    ("W1", incident_case, "TEST CASE #1: the incident, verbatim"),
    ("W2", bare_hard_dirty_case,
     "bare `git reset --hard` (no ref) still discards a dirty tracked file"),
    ("W3", staged_only_dirty_case,
     "a STAGED (not just working-tree) change is discarded too"),
    ("W4", mixed_case,
     "a dirty tracked file plus an unrelated untracked one -- warns about "
     "the tracked one"),
    ("W5", mixed_mode_flags_case,
     "`--mixed --hard` together -- `--hard` is present, so this warns"),
    ("W6", lead_word_case,
     "a lead word (`sudo`) and an assignment are both skipped before "
     "matching the invocation"),
]

SHOULD_STAY_SILENT = [
    ("S1", clean_hard_case,
     "a commit to drop, nothing else uncommitted -- recoverable via reflog "
     "regardless, and there is no uncommitted work to lose"),
    ("S2", untracked_only_case,
     "only an untracked file present -- `reset --hard` never touches it"),
    ("S3", plain_reset_case,
     "`git reset` with no `--hard` never discards working-tree content"),
    ("S4", mention_in_string_case,
     "a mention inside a quoted string is not an invocation"),
    ("S5", heredoc_mention_case,
     "a heredoc that MENTIONS the command runs neither"),
    ("S6", different_subcommand_case, "a different git subcommand entirely"),
    ("S7", other_subcommand_with_hard_token_case,
     "a different subcommand carrying a `--hard`-shaped token is not "
     "`reset --hard`"),
]


def verdict(hook_path, repo, command):
    payload = bash(command)
    proc = subprocess.run(
        [sys.executable, hook_path], input=json.dumps(payload),
        capture_output=True, text=True, cwd=repo,
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


def build_and_verdict(hook_path, builder):
    repo = _new_repo()
    try:
        command = builder(repo)
        return verdict(hook_path, repo, command)
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
CASES = {case_id: builder
         for case_id, builder, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

wrong = 0
print("should WARN:")
for case_id, builder, desc in SHOULD_WARN:
    got = build_and_verdict(HOOK, builder)
    wrong += got != "WARN"
    print(f"  {got:<6} {case_id}  {desc}")

print("\nshould STAY SILENT:")
for case_id, builder, desc in SHOULD_STAY_SILENT:
    got = build_and_verdict(HOOK, builder)
    wrong += got != "silent"
    print(f"  {got:<6} {case_id}  {desc}")

total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT)
print(f"\n{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness

MUTATIONS = {
    "M2_lead_words": (
        "leading assignments/lead words are skipped before matching `git "
        "reset`",
        [('        while i < len(argv) and (ASSIGNMENT.match(argv[i])\n'
          "                                  or argv[i] in LEAD_WORDS):\n"
          "            i += 1",
          "        pass")],
        {"W6"},
    ),
    "M2_subcommand": (
        "only a `git reset` invocation matches, not another subcommand",
        [('        if len(rest) < 2 or rest[0] != "git" or '
          'rest[1] != "reset":\n            continue',
          "        pass")],
        {"S7"},
    ),
    "M3_hard_flag": (
        "the invocation must carry the literal `--hard` token",
        [('        if "--hard" not in rest[2:]:\n            continue',
          "        pass")],
        {"S3"},
    ),
    "M4_status_gate": (
        "only a status report with at least one non-untracked entry warns",
        [("    if not changed:\n        return 0  # None (git unreachable) "
          "or empty (clean tree) -- fail open",
          "    if False:\n        return 0")],
        {"S1", "S2"},
    ),
    "M4_untracked_excluded": (
        "an untracked (`??`) entry does not count as a change `--hard` "
        "would discard",
        [('        if xy != "??":\n            changed.append(path)',
          "        changed.append(path)")],
        {"S2"},
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

        flipped = {case_id for case_id, builder in CASES.items()
                   if build_and_verdict(path, builder) != EXPECTED[case_id]}

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
