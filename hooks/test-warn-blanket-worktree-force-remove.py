"""Test the warn-blanket-worktree-force-remove guard.

Case W1 is the incident shape verbatim, per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against
the incident that prompted it": a `||`-chained fallback that force-removes
a worktree on any failure of the plain removal, written during a
`clean-git` session on 2026-09-10 and flagged by
`hooks/no-mistake-without-a-hook.py` as a mistake worth mechanizing.

An adversarial self-review of the first version of this hook found it
matched too loosely -- "a forced removal AND a `||` ANYWHERE in the
command" and "a forced removal AND a loop keyword ANYWHERE in the
command", neither checking the two ingredients are actually related. S9
through S12 below are the cases that review added: a forced removal that
merely SHARES a command with an unrelated `||` or an unrelated loop, which
the fixed hook must not warn on.

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
     "via ||, adjacent across the ||"),
    ("W2", GWR + ' "$p" || ' + GWR + ' -f "$p"',
     "short `-f` (not `--force`) on the forced side still counts as "
     "forced"),
    ("W3",
     'for p in "${DEAD[@]}"; do ' + GWR + ' --force "$p"; done',
     "the loop form: the forced removal's own segment sits between the "
     "loop's opener and its `done`"),
    ("W4",
     'while read -r p; do ' + GWR + ' --force "$p"; done < list.txt',
     "a `while` loop is also a loop keyword, not only `for`"),
    ("W5",
     GWR + ' "$a"; ' + GWR + ' "$b" || ' + GWR + ' --force "$b"',
     "the fallback pair need not be the first two commands in the line, "
     "as long as the forced side is adjacent to a bare removal across "
     "`||` (uses `;` for the unrelated prefix, not `&&`, so this case "
     "is sensitive to `||` detection specifically)"),
    ("W6",
     ('for x in a b; do echo "$x"; done; '
      'for p in "${DEAD[@]}"; do ' + GWR + ' --force "$p"; done'),
     "a SECOND loop reopens depth after the first one's `done` closed "
     "it -- the forced removal in the second loop must still be seen"),
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
     "a single forced removal with an ignore-failure `|| true` tail -- "
     "the segment on the OTHER side of || is not a worktree removal at "
     "all, so this is not the retry-harder shape the guard targets"),
    ("S9",
     GWR + ' --force "$p"; for x in a b; do echo "$x"; done',
     "a forced removal followed by an UNRELATED loop that never touches "
     "a worktree -- the forced removal's own segment is not inside the "
     "loop's depth"),
    ("S10",
     'for x in a b; do echo "$x"; done; ' + GWR + ' --force "$p"',
     "a forced removal AFTER a loop that already closed (`done` seen) -- "
     "loop depth is back to zero by the time the removal runs"),
    ("S11",
     'true || ' + GWR + ' --force "$p"',
     "a forced removal chained via || after an UNRELATED failing "
     "command (not itself a worktree removal) -- there is no bare "
     "removal being retried, just an unrelated fallback pattern"),
    ("S12",
     GWR + ' "$a" && ' + GWR + ' --force "$b"',
     "&&, not ||, between a bare removal and a forced one -- a "
     "different worktree, chained on SUCCESS rather than retried on "
     "failure, is not the fallback shape"),
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
        "forced -- dropping `--force` from the check misses every case "
        "whose forced side spells it that way (W1, W3, W4, W5, W6)",
        [('return "--force" in rest[1:] or "-f" in rest[1:]',
          'return "-f" in rest[1:]')],
        {"W1", "W3", "W4", "W5", "W6"},
    ),
    "M2_pipe_operator_detection": (
        "the segment scan must recognize a `||`-containing preceding op "
        "-- checking for `&&` instead misses every `||`-fallback case "
        "(W1, W2, W5) AND wrongly starts firing on S12's `&&`-chained "
        "pair instead",
        [('if not op or "||" not in op:',
          'if not op or "&&" not in op:')],
        {"W1", "W2", "W5", "S12"},
    ),
    "M3_loop_keyword_detection": (
        "a loop keyword opening a segment must be recognized -- an empty "
        "loop-keyword set misses every loop-shape case (W3, W4, W6)",
        [('_LOOP_KEYWORDS = {"for", "while", "until"}',
          '_LOOP_KEYWORDS = set()')],
        {"W3", "W4", "W6"},
    ),
    "M4_worktree_remove_subcommand_match": (
        "only `git worktree remove` (not some other `git worktree` "
        "subcommand) is in scope -- requiring `rest[0] == 'list'` instead "
        "makes every case go silent, since none of them ever removes "
        "a worktree named `remove`",
        [("if subcommand != \"worktree\" or not rest or rest[0] != \"remove\":",
          "if subcommand != \"worktree\" or not rest or rest[0] != \"list\":")],
        {"W1", "W2", "W3", "W4", "W5", "W6"},
    ),
    "M5_bare_removal_required_on_pipe_left_side": (
        "the `||` shape requires the segment BEFORE the `||` to be an "
        "actual BARE (unforced) worktree removal, not merely anything "
        "that is not itself forced-True -- dropping that requirement "
        "fires on a forced removal chained after ANY unrelated command "
        "via `||` (tested against S11, not a WARN case)",
        [('if prev_forced is False:  # explicitly bare, not "not a removal"',
          'if True:  # explicitly bare, not "not a removal"')],
        set(),  # verified against S11 below, not the fixed WARN table
    ),
    "M6_done_closes_loop_depth": (
        "`done` must decrement loop depth -- without it, a forced "
        "removal AFTER a loop has already closed (S10) is still read "
        "as inside one",
        [('if argv[0] == "done":\n            loop_depth = max(0, loop_depth - 1)',
          'if argv[0] == "done":\n            pass')],
        set(),  # verified against S10 below, not the fixed WARN table
    ),
}

print("\nmutation tests (revert one clause, see which cases flip):")
mutation_wrong = 0
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    if not expected_flips:
        continue  # M5/M6 verified separately below, against a non-WARN case
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
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<44} {statement}\n"
          f"         {note}")


def _mutate_and_check(edits, command, want_before, want_after, label):
    """Confirm the UNMUTATED hook gives WANT_BEFORE on COMMAND, then that
    applying EDITS flips it to WANT_AFTER -- i.e. the clause is
    load-bearing for this specific synthetic case, checked outside the
    fixed CASES table."""
    before = verdict_for_command(HOOK, command)
    before_ok = before == want_before

    mutated = SOURCE
    for find, replace in edits:
        count = mutated.count(find)
        if count != 1:
            sys.exit(f"FATAL: {label}'s anchor is not present exactly "
                     f"once in {HOOK} (found {count}).\n---\n{find}\n---")
        mutated = mutated.replace(find, replace)
    fd, path = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(HOOK))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        after = verdict_for_command(path, command)
    finally:
        os.unlink(path)
    after_ok = after == want_after

    ok = before_ok and after_ok
    if ok:
        print(f"  ok    {label:<44}\n"
              f"         unmutated={before} (want {want_before}), "
              f"mutated={after} (want {want_after}), as declared")
    else:
        print(f"  WRONG {label:<44}\n"
              f"         unmutated={before} (want {want_before}), "
              f"mutated={after} (want {want_after})")
    return not ok


S11_COMMAND = 'true || ' + GWR + ' --force "$p"'
mutation_wrong += _mutate_and_check(
    MUTATIONS["M5_bare_removal_required_on_pipe_left_side"][1],
    S11_COMMAND, "silent", "WARN",
    "M5_bare_removal_required_on_pipe_left_side",
)

S10_COMMAND = 'for x in a b; do echo "$x"; done; ' + GWR + ' --force "$p"'
mutation_wrong += _mutate_and_check(
    MUTATIONS["M6_done_closes_loop_depth"][1],
    S10_COMMAND, "silent", "WARN",
    "M6_done_closes_loop_depth",
)

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses "
      "behaved as declared under reversion")

sys.exit(1 if (wrong or mutation_wrong) else 0)
