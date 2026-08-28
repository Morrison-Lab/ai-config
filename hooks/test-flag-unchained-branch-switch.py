"""Test the flag-unchained-branch-switch guard, clause by clause.

Test case #1 is the incident verbatim -- pasted in as it was actually typed,
not retyped or tidied, per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against the
incident that prompted it, verbatim". You design against your SUMMARY of an
incident, and the summary is what made the rule statable; the real input
carries a `-q`, an `--ff-only`, and a `-m` message containing single quotes
inside double quotes, none of which the summary mentions.

The second half of this file is a MUTATION harness, per
`shared/principles/fail-fast.md`'s "A guard whose condition ANDs several
clauses masks its own mutation test the same way". Each clause of the match
condition is reverted on its own, in a temporary copy of the hook, and the set
of cases whose verdict flips is compared against a declared expectation. A
clause whose reversion flips NOTHING is untested, and that is the failure this
harness exists to catch.

One subsumption is declared rather than engineered away: C7 (a newline after
`&&` is not a separator) and C9 (only the nearest preceding switch counts) both
refine C4 (the separators are not all `&&`). With C4 gone the separators do not
matter at all, so C4's reversion necessarily flips their cases too. That is a
property of a nested refinement, not a masked clause -- C7's and C9's own
reversions each still flip a case, which is what "not masked" means.

Run:  python3 hooks/test-flag-unchained-branch-switch.py \\
          hooks/flag-unchained-branch-switch.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

# ---------------------------------------------------------------- the incident

# Verbatim. Two lines, one Bash call. The `&&` binds only within line 1, so
# line 2's merge ran against `main` after the checkout failed with
# `fatal: 'feat/some-branch' is already checked out at '<worktree path>'`.
INCIDENT = """git checkout feat/some-branch -q && git merge --ff-only origin/feat/some-branch -q
git merge origin/main -m "Merge branch 'main' into feat/some-branch"
"""


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# (case_id, payload, description)
SHOULD_WARN = [
    ("W1", bash(INCIDENT),
     "TEST CASE #1: the incident, verbatim"),
    ("W2", bash("git checkout feat/x; git merge origin/main"),
     "same hazard on one line: `;` is a separator too, not just a newline"),
    ("W3", bash("git switch feat/x\ngit commit -m 'wip'"),
     "`git switch` is a branch switch as much as `git checkout`"),
    ("W4", bash("git checkout -b feat/x\ngit push -u origin HEAD"),
     "`-b` creates AND switches; the push is still unchained"),
    # Round-1 review finding, reproduced verbatim before it was fixed. The
    # first version of C8 dropped a guarded switch from consideration entirely,
    # so the merge AFTER `fi` -- which runs unconditionally -- went unseen.
    ("W5", bash("if git checkout main 2>/dev/null; then git pull; fi\n"
                "git merge --no-ff feature-branch"),
     "guarded switch, mutation AFTER `fi`: the incident in a defensive wrapper"),
    ("W6", bash("while git checkout main; do git pull; done\n"
                "git commit -m 'wip'"),
     "a `while` block closes at `done`; the commit after it is unguarded"),
    ("W7", bash("if git checkout main; then\n"
                "  if git status --short; then git pull; fi\n"
                "fi\n"
                "git merge --no-ff feature-branch"),
     "nested blocks: the mutation is outside BOTH, so the outer guard is spent"),
    ("W8", bash("! git checkout main\ngit merge x"),
     "`!` inverts an exit status without making the switch conditional"),
]

SHOULD_STAY_SILENT = [
    ("S1", bash("git checkout feat/x -q && \\\n  git merge origin/main"),
     "chained across a `\\` line continuation"),
    ("S2", bash("git checkout feat/x -q &&\n  git merge origin/main"),
     "chained by a TRAILING `&&`; bash continues the list onto the next line"),
    ("S3", bash("git checkout -- path/to/file\ngit commit -m 'restore'"),
     "`git checkout -- <path>` restores a file and never moves HEAD"),
    ("S4", bash("cat <<'EOF' > /tmp/notes.txt\n"
                "git checkout feat/some-branch\n"
                "git merge origin/main\n"
                "EOF\n"),
     "a heredoc that MENTIONS the commands runs neither"),
    ("S5", bash("echo git checkout feat/x\ngit merge origin/main"),
     "an unquoted `echo` mention is not a command position"),
    ("S6", bash("grep -n \"git checkout\" README.md\ngit commit -m 'x'"),
     "a quoted `grep` pattern is not a command"),
    ("S7", bash("git commit -m \"checkpoint; git checkout main\"\ngit push"),
     "a separator inside a commit MESSAGE is not a separator"),
    ("S8", bash("git commit -m 'x'\ngit push"),
     "mutating commands with no branch switch anywhere"),
    ("S9", bash("git commit -m 'x'\ngit checkout main"),
     "the mutation is EARLIER than the switch"),
    ("S10", {"tool_name": "Agent",
             "tool_input": {"description": "x", "prompt": "x",
                            "command": INCIDENT}},
     "a different tool entirely, even carrying the incident text"),
    ("S11", bash("git status\ngit commit -m 'x'"),
     "a non-switching git command does not open the hazard"),
    ("S12", {"tool_name": "Bash", "tool_input": None},
     "malformed tool_input fails OPEN, does not warn"),
    ("S13", bash("git checkout feat/x && git merge origin/main"),
     "fully chained on one line"),
    ("S14", bash("# git checkout feat/x\ngit merge origin/main"),
     "a comment mentioning the switch is not a switch"),
    ("S15", bash("if git checkout feat/x; then\n  git merge origin/main\nfi"),
     "a switch used as an `if` CONDITION is checked before the merge runs"),
    ("S16", bash("git checkout branch-a && git merge --no-edit origin/main\n"
                 "git checkout branch-b && git merge --no-edit branch-a"),
     "a cascade: each merge is chained to the switch that decides ITS branch"),
    ("S17", bash("if git checkout a; then\n"
                 "  git merge x\n"
                 "elif git checkout b; then\n"
                 "  git merge y\n"
                 "else\n"
                 "  git merge z\n"
                 "fi"),
     "`elif` continues the block it sits in; `else` runs only when both failed"),
    ("S18", bash("if git checkout main; then\n"
                 "  if [ -f x ]; then git merge origin/main; fi\n"
                 "fi"),
     "a mutation NESTED deeper still sits inside the guarded block"),
    ("S19", bash("while git checkout main; do\n  git merge origin/main\ndone"),
     "a `while` guard reaches its whole `do`/`done` body"),
    ("S20", bash("for b in a b; do git checkout $b && git merge origin/main; done"),
     "`for` opens a block too, so its `done` cannot underflow the stack"),
]

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
             "read as 'silent' on every case and print a perfect pass")

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()


def verdict(hook_path, payload):
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    # a crashed hook must NOT read as 'silent' -- that is the failure mode where
    # the pass path and the broken path print the same thing
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
    # the hook must never make the harness MORE permissive than it was without it
    if "permissionDecision" in hso:
        sys.exit(f"FATAL: hook emitted permissionDecision="
                 f"{hso['permissionDecision']!r}; this guard must only ever add "
                 "context, never allow/deny/ask")
    return "WARN" if hso.get("additionalContext") else "silent"


EXPECTED = {case_id: "WARN" for case_id, _, _ in SHOULD_WARN}
EXPECTED.update({case_id: "silent" for case_id, _, _ in SHOULD_STAY_SILENT})
PAYLOADS = {case_id: payload
            for case_id, payload, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

wrong = 0
print("should WARN:")
for case_id, payload, desc in SHOULD_WARN:
    got = verdict(HOOK, payload)
    wrong += got != "WARN"
    print(f"  {got:<6} {case_id}  {desc}")

print("\nshould STAY SILENT:")
for case_id, payload, desc in SHOULD_STAY_SILENT:
    got = verdict(HOOK, payload)
    wrong += got != "silent"
    print(f"  {got:<6} {case_id}  {desc}")

total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT)
print(f"\n{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness

# clause -> (human-readable statement, [(find, replace), ...], {cases that flip})
MUTATIONS = {
    "C1": (
        "the tool is Bash",
        [('    if payload.get("tool_name") != "Bash":\n        return None',
          '    if False:\n        return None')],
        {"S10"},
    ),
    "C2": (
        "only a SWITCHING subcommand opens the hazard",
        [('        return "mutate", guarded\n    return None, guarded',
          '        return "mutate", guarded\n    return "switch", guarded')],
        {"S11"},
    ),
    "C2a": (
        "`git checkout -- <path>` is a file restore, not a switch",
        [('        if "--" in args:\n            return None, guarded',
          '        if False:\n            return None, guarded')],
        {"S3"},
    ),
    "C3": (
        "only a switch BEFORE the mutation decides its branch",
        # The forward fallback fires only when no PRECEDING switch exists, so
        # this isolates C3 from C9's cascade case.
        [("        return i\n    return None",
          "        return i\n"
          "    for i in range(j + 1, len(records)):\n"
          '        if records[i][0] == "switch":\n'
          "            return i\n"
          "    return None")],
        {"S9"},
    ),
    "C9": (
        "only the NEAREST preceding switch is weighed",
        [("    for i in range(j - 1, -1, -1):", "    for i in range(0, j):")],
        {"S16"},
    ),
    "C4": (
        "the separators between them are not all `&&`",
        [('        if any(sep != "&&" for sep in _separators_between(records, i, j)):',
          "        if True:")],
        # C7's and C9's cases are included by construction: with C4 gone, no
        # separator matters, so every case that is silent BECAUSE its commands
        # are chained flips. See the module docstring.
        {"S1", "S2", "S13", "S16", "S20"},
    ),
    "C5": (
        "heredoc bodies are stripped",
        [('    return "\\n".join(kept)', "    return command")],
        {"S4"},
    ),
    "C6q": (
        "quoted spans are dropped before separators are found",
        [("        if char == \"'\":", "        if False:"),
         ("        if char == '\"':", "        if False:")],
        {"S7"},
    ),
    "C6p": (
        "a git command counts only at a command POSITION",
        [('    if not tokens or tokens[0] != "git":\n        return None, []',
          '    if "git" in tokens:\n        tokens = tokens[tokens.index("git"):]\n'
          '    if not tokens or tokens[0] != "git":\n        return None, []')],
        {"S5"},
    ),
    "C8": (
        "a conditional switch protects mutations INSIDE the block it governs",
        [("        if guard_block is not None and guard_block in scope_j:",
          "        if False:")],
        {"S15", "S17", "S18", "S19"},
    ),
    "C8b": (
        "that protection STOPS at the closing `fi`/`done`",
        [("        if guard_block is not None and guard_block in scope_j:",
          "        if guard_block is not None:")],
        {"W5", "W6", "W7"},
    ),
    "C7": (
        "a newline after `&&`/`||`/`|` separates nothing",
        [('        if sep == "\\n" and separators and separators[-1] in CONTINUING:\n'
          "            return",
          "        if False:\n            return")],
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
                sys.exit(f"FATAL: clause {clause}'s anchor is not present exactly "
                         f"once in {HOOK} (found {mutated.count(find)}). The "
                         "mutation harness is measuring nothing; re-derive the "
                         f"anchor.\n---\n{find}\n---")
            mutated = mutated.replace(find, replace)

        path = os.path.join(tmp, f"mutant-{clause}.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(mutated)

        flipped = {case_id for case_id in PAYLOADS
                   if verdict(path, PAYLOADS[case_id]) != EXPECTED[case_id]}

        ok = flipped == expected_flips
        mutation_wrong += not ok
        if not flipped:
            note = "NOTHING FLIPPED -- this clause is untested"
        elif ok:
            note = "flipped " + ", ".join(sorted(flipped))
        else:
            note = (f"flipped {sorted(flipped)}, expected {sorted(expected_flips)}")
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<4} {statement}\n"
              f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved as "
      "declared under reversion")

sys.exit(1 if (wrong or mutation_wrong) else 0)
