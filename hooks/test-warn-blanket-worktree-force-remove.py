"""Test the warn-blanket-worktree-force-remove guard.

Case W1 is the incident shape verbatim, per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against
the incident that prompted it": a `||`-chained fallback that force-removes
a worktree on any failure of the plain removal, written during a
`clean-git` session on 2026-09-10 and flagged by
`hooks/no-mistake-without-a-hook.py` as a mistake worth mechanizing.

`GWR` builds the string `"git worktree remove"` by concatenation rather
than as a literal, purely so this test file itself does not read as an
actual worktree-removal invocation to any OTHER guard scanning the repo
(the sandbox that hosts this session already refuses a Bash command
containing that literal text as too complex to verify -- see the hook's
own docstring for why the command text, not just the parsed intent, is
what a reader or a guard sees first).

Run:  python3 hooks/test-warn-blanket-worktree-force-remove.py \\
          hooks/warn-blanket-worktree-force-remove.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1])

GWR = "g" + "it worktree remove"  # see module docstring


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ---------------------------------------------------------------- cases
# (case_id, command, description)

SHOULD_WARN = [
    ("W1", GWR + ' "$p" || ' + GWR + ' --force "$p"',
     "the incident's own shape: plain removal, force-removed on failure "
     "via ||"),
    ("W2", GWR + ' "$p" || ' + GWR + ' -f "$p"',
     "short `-f` (not `--force`) on the forced side still counts as "
     "forced"),
    ("W3",
     'for p in "${DEAD[@]}"; do ' + GWR + ' --force "$p"; done',
     "the loop form: forced every iteration, no bare removal needed"),
    ("W4",
     'while read -r p; do ' + GWR + ' --force "$p"; done < list.txt',
     "a `while` loop is also a loop keyword, not only `for`"),
    ("W5",
     GWR + ' "$a"; ' + GWR + ' "$b" || ' + GWR + ' --force "$b"',
     "the fallback pair need not be the first two commands in the line "
     "(uses `;`, not `&&`, so this case is sensitive to `||` detection "
     "specifically, not to any operator)"),
]

SHOULD_STAY_SILENT = [
    ("S1", GWR + ' --force "$p"',
     "the documented submodule exception: a single-shot --force with no "
     "fallback and no loop"),
    ("S2", GWR + ' "$p"',
     "a plain removal, never forced"),
    ("S3", "git push --force && " + GWR + ' "$p"',
     "--force belongs to an UNRELATED git invocation (push), not to the "
     "worktree remove"),
    ("S4", 'git commit -m "fixed the ' + GWR + ' fallback bug"',
     "the pattern is only QUOTED, inside a commit message -- not an "
     "actual invocation"),
    ("S5", GWR + ' "$a" || ' + GWR + ' "$b"',
     "a `||` fallback where NEITHER side is forced -- nothing to warn "
     "about"),
    ("S6",
     'for p in "${DEAD[@]}"; do ' + GWR + ' "$p"; done',
     "a loop that removes WITHOUT force -- the loop alone is not the "
     "offense"),
    ("S7", GWR + ' --force "$p"; echo done',
     "a forced removal followed by an unrelated command, with no || and "
     "no loop anywhere in the line"),
    ("S8", GWR + ' -f "$p" || true',
     "a single forced removal with an ignore-failure `|| true` tail -- no "
     "bare removal on the other side, so this is not the retry-harder "
     "shape the guard targets"),
]

NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Bash", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Bash"}, "absent tool_input"),
    ({"tool_name": "Bash", "tool_input": GWR + ' "$p" || ' + GWR + ' --force "$p"'},
     "tool_input is a STRING rather than a dict"),
    ({"tool_name": "Bash", "tool_input": {"command": 12345}},
     "command is not a string"),
    ({"tool_name": "Bash", "tool_input": {}}, "tool_input has no command key"),
    ({"tool_name": "Edit",
      "tool_input": {"file_path": "/x",
                     "old_string": GWR + ' "$p"',
                     "new_string": GWR + ' --force "$p"'}},
     "a different tool entirely, not Bash"),
]

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would "
             "otherwise read as 'silent' on every case and print a "
             "perfect pass")

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()


def verdict(hook_path, payload):
    proc = subprocess.run(
        [sys.executable, hook_path], input=json.dumps(payload),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {payload!r}\n"
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
                 f"{hso['permissionDecision']!r}; this guard must only "
                 "ever add context, never allow/deny/ask")
    return "WARN" if hso.get("additionalContext") else "silent"


def verdict_for_command(hook_path, command):
    return verdict(hook_path, bash(command))


wrong = 0
print("should WARN:")
for case_id, command, desc in SHOULD_WARN:
    got = verdict_for_command(HOOK, command)
    wrong += got != "WARN"
    print(f"  {got:<6} {case_id:<4} {desc}")

print("\nshould STAY SILENT:")
for case_id, command, desc in SHOULD_STAY_SILENT:
    got = verdict_for_command(HOOK, command)
    wrong += got != "silent"
    print(f"  {got:<6} {case_id:<4} {desc}")

print("\nnon-command payloads (must fail open silently):")
for payload, desc in NON_COMMAND_PAYLOADS:
    got = verdict(HOOK, payload)
    wrong += got != "silent"
    print(f"  {got:<6} {desc}")

total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT) + len(NON_COMMAND_PAYLOADS)
print(f"\n{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness
# Per shared/workflow/algorithmatize-checks.md: break each clause
# deliberately, confirm the test turns red, and verify the mutation
# actually applied by checking WHICH cases flip.

EXPECTED = {case_id: "WARN" for case_id, *_ in SHOULD_WARN}
EXPECTED.update({case_id: "silent" for case_id, *_ in SHOULD_STAY_SILENT})

CASES = {case_id: command
         for case_id, command, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

MUTATIONS = {
    "M1_forced_flag_detection": (
        "`-f`/`--force` on the worktree-remove argv must both count as "
        "forced -- dropping `--force` from the check misses W1, W3, W4, W5",
        [('forced = "--force" in rest[1:] or "-f" in rest[1:]',
          'forced = "-f" in rest[1:]')],
        {"W1", "W3", "W4", "W5"},
    ),
    "M2_pipe_operator_detection": (
        "the raw-token scan must find a literal `||` -- breaking it to "
        "look for `&&` instead misses the fallback shape (W1, W2, W5)",
        [('has_pipe = "||" in tokens',
          'has_pipe = "&&" in tokens')],
        {"W1", "W2", "W5"},
    ),
    "M3_loop_keyword_detection": (
        "a loop keyword opening a segment must be recognized -- an empty "
        "loop-keyword set misses the loop shape (W3, W4)",
        [('_LOOP_KEYWORDS = {"for", "while", "until"}',
          '_LOOP_KEYWORDS = set()')],
        {"W3", "W4"},
    ),
    "M4_worktree_remove_subcommand_match": (
        "only `git worktree remove` (not some other `git worktree` "
        "subcommand) is in scope -- requiring `rest[0] == 'list'` instead "
        "makes every case go silent, since none of them ever removes "
        "a worktree named `remove`",
        [("if subcommand != \"worktree\" or not rest or rest[0] != \"remove\":",
          "if subcommand != \"worktree\" or not rest or rest[0] != \"list\":")],
        {"W1", "W2", "W3", "W4", "W5"},
    ),
}

# M5 is checked separately, below the generic loop: it needs a SYNTHETIC
# command (forced + `||`, no bare removal on the other side) that is not
# in the fixed CASES table, because none of S1-S7 combines `--force` with
# a stray `||` on an unrelated command.
M5_EDITS = [("if has_forced and has_bare and has_pipe:",
             "if has_forced and has_pipe:")]
M5_STATEMENT = (
    "the `||` shape requires an actual BARE (unforced) removal on the "
    "other side, not just any `||` in the command -- dropping that "
    "requirement fires on a forced removal chained to an unrelated `||`"
)
M5_COMMAND = GWR + ' --force "$a" || true'

print("\nmutation tests (revert one clause, see which cases flip):")
mutation_wrong = 0
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, replace in edits:
        count = mutated.count(find)
        if count != 1:
            sys.exit(f"FATAL: clause {clause}'s anchor is not present "
                     f"exactly once in {HOOK} (found {count}). The "
                     "mutation harness is measuring nothing; re-derive "
                     f"the anchor.\n---\n{find}\n---")
        mutated = mutated.replace(find, replace)

    fd, path = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(HOOK))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        flipped = {case_id for case_id, command in CASES.items()
                   if verdict_for_command(path, command) != EXPECTED[case_id]}
    finally:
        os.unlink(path)

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
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<38} {statement}\n"
          f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses "
      "behaved as declared under reversion")

# M5, handled separately: confirm the UNMUTATED hook stays silent on a
# forced removal chained to an unrelated `||` (no bare removal on the
# other side), then confirm the mutated hook (bare-removal requirement
# dropped) WARNS on that same command -- i.e. the clause is load-bearing.
m5_before = verdict_for_command(HOOK, M5_COMMAND)
m5_before_ok = m5_before == "silent"

m5_mutated = SOURCE
for find, replace in M5_EDITS:
    count = m5_mutated.count(find)
    if count != 1:
        sys.exit(f"FATAL: M5's anchor is not present exactly once in "
                 f"{HOOK} (found {count}).\n---\n{find}\n---")
    m5_mutated = m5_mutated.replace(find, replace)
fd, m5_path = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(HOOK))
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write(m5_mutated)
try:
    m5_after = verdict_for_command(m5_path, M5_COMMAND)
finally:
    os.unlink(m5_path)
m5_after_ok = m5_after == "WARN"

m5_ok = m5_before_ok and m5_after_ok
if m5_ok:
    print(f"  ok    M5_bare_removal_required_for_pipe_shape       "
          f"{M5_STATEMENT}\n"
          f"         unmutated=silent, mutated=WARN, as declared")
else:
    print(f"  WRONG M5_bare_removal_required_for_pipe_shape       "
          f"{M5_STATEMENT}\n"
          f"         unmutated={m5_before} (want silent), "
          f"mutated={m5_after} (want WARN)")
mutation_wrong += not m5_ok

sys.exit(1 if (wrong or mutation_wrong) else 0)
