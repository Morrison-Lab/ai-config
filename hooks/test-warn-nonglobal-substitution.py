"""Test the warn-nonglobal-substitution guard.

Cases W1 and W1b reproduce the incident this hook exists for, verbatim:
`perl -0pi -e 's/OLD/NEW/' file.pl`, the exact non-global substitution that
silently rewrote a prose comment instead of the intended code line on
2026-08-21 (incidents 1 and 4 in the hook's own docstring). Per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against
the incident that prompted it, verbatim", the fixture is the incident's own
command string rather than a paraphrase.

The rest of the WARN/SILENT cases each isolate one clause of the hook's
detection logic, and the mutation harness at the bottom confirms each clause
is load-bearing: revert it, and only the cases that clause protects should
flip.

Run:  python3 hooks/test-warn-nonglobal-substitution.py \\
          hooks/warn-nonglobal-substitution.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1])


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ---------------------------------------------------------------- cases
# (case_id, command, description)

SHOULD_WARN = [
    ("W1", "perl -0pi -e 's/OLD/NEW/' file.pl",
     "the incident, verbatim: bundled -0pi, no flags at all"),
    ("W1b", "perl -0pi -e 's/OLD/NEW/' file.pl",
     "incident 4 -- the same shape recurred; kept as its own case so a "
     "later edit cannot quietly drop the pair"),
    ("W2", "sed -i 's/a/b/' file.txt",
     "bare sed -i, no flags"),
    ("W3", "sed -i.bak 's/a/b/' file.txt",
     "sed -i with a bundled backup-extension suffix"),
    ("W4", "sed --in-place 's/a/b/' file.txt",
     "sed's long-option form"),
    ("W5", "sed -ni 's/a/b/p' file.txt",
     "sed -i bundled with -n (quiet) -- flags carry `p`, not `g`"),
    ("W6", "perl -Ilib -i -pe 's/a/b/' file.pl",
     "a genuine -i alongside an unrelated -Ilib -- -Ilib must not prevent "
     "the real -i from being found"),
    ("W7", "perl -i -pe 's/a/b/' -- 'file/with/slashes'",
     "a path argument carrying delimiter-shaped characters must not break "
     "parsing of the actual substitution"),
    ("W8", "sed -i 's/a/b/g' f1.txt && sed -i 's/c/d/' f2.txt",
     "two piped invocations -- only the second (non-global) should warn"),
    ("W9", "perl -pi -e 's/a/b/; s/c/d/g' file.pl",
     "two substitutions in one script; the first lacks `g`, the second "
     "has it -- the first alone is enough to warn"),
    ("W10", "FOO=1 sed -i 's/a/b/' file.txt",
     "a leading env-assignment is skipped before matching the invocation"),
    ("W12", "perl -0777pi -e 's/a/b/' file.pl",
     "slurp mode: -0 takes an octal argument, so -0777 is still the "
     "in-place flag -- and slurp plus non-global is the worst case of "
     "the bug this hook exists to catch"),
    ("W13", "sed -i '1s/a/b/' file.txt",
     "a numeric line address before the `s`; a word boundary never fires "
     "between a digit and `s`, so this was missed while the equivalent "
     "regex-addressed form warned"),
    ("W11", "sed -i 's/a#b/c/' file.txt",
     "a pattern containing ANOTHER delimiter character still matches -- the "
     "lookahead is keyed to the delimiter actually in use, so excluding "
     "every delimiter character would silently stop warning here"),
]

SHOULD_STAY_SILENT = [
    ("S11", "mytool -i 's/a/b/' file.txt",
     "a command that is neither perl nor sed, despite an -i flag and a "
     "substitution-shaped argument -- the cmd-word gate is the only thing "
     "keeping this quiet, so it is what makes that gate testable"),
    ("S10", "perl -pi -e 's/OLD/NEW/g' lib/s/x/y/z.pm",
     "the only real substitution is GLOBAL; the path merely LOOKS like a "
     "second one. Scanning the whole argv fabricated `s/x/y/z` here, which "
     "is a false claim about what the command does"),
    ("S1", "perl -pi -e 's/a/b/g' file.pl",
     "already carries the `g` flag"),
    ("S2", "sed 's/a/b/' file.txt",
     "no -i at all -- a read-only scan to stdout"),
    ("S3", "git commit -m 'use sed -i s/a/b/ to fix'",
     "a git command whose commit MESSAGE merely mentions the pattern"),
    ("S4", "gh pr comment 5 --body 'run sed -i s/a/b/ to fix'",
     "a non-git, non-perl/sed command whose body text mentions the pattern"),
    ("S5", "sed -i 's/a/b/2' file.txt",
     "a digit flag targets a specific occurrence on purpose"),
    ("S6", "perl -Ilib -pe 's/a/b/' file.pl",
     "-Ilib present, but no genuine -i flag anywhere"),
    ("S7", "perl -i -pe '$_ = uc' file.pl",
     "a real -i, but no substitution at all"),
    ("S8", "cat <<'EOF' > note.txt\nperl -i -pe 's/a/b/'\nEOF\n",
     "a heredoc that documents the pattern; it is never executed"),
    ("S9", """perl -i -pe 'my $x = "a/b/c/d"' file.pl""",
     "three delimiter-shaped characters (a genuine `s<delim>..<delim>.."
     "<delim>flags` shape once the `s`-prefix requirement is ignored) with "
     "no leading `s` anywhere nearby -- not a substitution"),
]

# Two non-command payload shapes that must fail open silently, tested
# directly rather than through the (command, description) table above.
NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Bash", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Bash"}, "absent tool_input"),
    ({"tool_name": "Bash", "tool_input": "sed -i 's/a/b/' file.txt"},
     "tool_input is a STRING rather than a dict -- .get() on a string "
     "would crash rather than fail open"),
    ({"tool_name": "Bash", "tool_input": {"command": 12345}},
     "command is not a string"),
    ({"tool_name": "Bash", "tool_input": {}}, "tool_input has no command key"),
    (["Bash", {"command": "sed -i 's/a/b/' file.txt"}],
     "the whole payload is a LIST rather than a dict"),
    ({"tool_name": "Edit",
      "tool_input": {"file_path": "/x", "old_string": "s/a/b/",
                     "new_string": "s/a/b/g"}},
     "a different tool entirely, not Bash"),
]

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would "
             "otherwise read as 'silent' on every case and print a perfect "
             "pass")

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()


def verdict(hook_path, payload):
    proc = subprocess.run(
        ["python3", hook_path], input=json.dumps(payload),
        capture_output=True, text=True,
    )
    # a crashed hook must NOT read as 'silent' -- that is the failure mode
    # where the pass path and the broken path print the same thing
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
    # the hook must never make the harness MORE permissive than it was
    # without it
    if "permissionDecision" in hso:
        sys.exit(f"FATAL: hook emitted permissionDecision="
                 f"{hso['permissionDecision']!r}; this guard must only ever "
                 "add context, never allow/deny/ask")
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

total = (len(SHOULD_WARN) + len(SHOULD_STAY_SILENT)
         + len(NON_COMMAND_PAYLOADS))
print(f"\n{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness
# Per shared/workflow/algorithmatize-checks.md and this hook's own subject
# matter: break each clause deliberately, confirm the test turns red, and
# verify the mutation actually applied by checking WHICH cases flip -- not
# merely that some output changed. Every anchor below must appear in the
# hook's source EXACTLY ONCE; a non-unique or missing anchor means the
# harness is measuring nothing, and the run aborts rather than reporting a
# false "ok".

EXPECTED = {case_id: "WARN" for case_id, *_ in SHOULD_WARN}
EXPECTED.update({case_id: "silent" for case_id, *_ in SHOULD_STAY_SILENT})
# The matcher must stay linear on an UNTERMINATED substitution carrying a run
# of backslashes. The two alternatives in `_SUBST_RE` were once ambiguous (a
# backslash matched both), which backtracks exponentially -- 0.357s at 30
# backslashes, no completion in 120s at 50,000. Every case above is
# well-formed, so none of them can reach it; this is the only guard.
# Asserted on elapsed time because the defect is runtime, not verdict.
def _redos_guard():
    import time
    # The quoting must BALANCE. An unbalanced quote makes shlex refuse the
    # command, so `find_offenses` returns before `_SUBST_RE` runs at all and
    # the guard passes with the vulnerable pattern in place -- which is how
    # the first version of this guard was vacuous.
    #
    # 37 is calibrated, not arbitrary. Measured 2026-08-21 against the
    # ambiguous pattern: 0.98s at 33, 2.7s at 35, 7.2s at 37. Below ~35 the
    # guard would not trip; far above it the suite HANGS instead of failing,
    # which stalls CI rather than reporting. 37 fails in seconds and leaves
    # headroom on a slower runner.
    payload = "perl -i -pe " + "'" + "s/" + ("\\" * 37) + "'"
    start = time.time()
    verdict_for_command(HOOK, payload)
    elapsed = time.time() - start
    if elapsed > 2.0:
        print(f"  WRONG REDOS  unterminated substitution with 37 backslashes "
              f"took {elapsed:.2f}s -- _SUBST_RE's alternatives are ambiguous "
              f"again")
        return 1
    print(f"  ok   REDOS    unterminated substitution stays linear "
          f"({elapsed:.4f}s)")
    return 0


CASES = {case_id: command
         for case_id, command, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

MUTATIONS = {
    "M1_cmd_word_gate": (
        "a command whose leading word is not perl/sed must never be "
        "treated as carrying the in-place flag",
        [("    return False", "    return True")],
        # S3/S4 (a git/gh command merely MENTIONING the pattern) stopped
        # discriminating this clause once _script_args landed: a subcommand
        # name is not script text, so they stay silent even with the gate
        # reverted. S11 is the case that isolates the gate itself.
        {"S11"},
    ),
    "M2_perl_real_flag": (
        "perl's -i must be a GENUINE bundled flag, not any perl "
        "invocation",
        [("        return any(_PERL_INPLACE_CLUSTER.match(a) for a in args)",
          "        return True")],
        {"S6"},
    ),
    "M3_sed_real_flag": (
        "sed's -i must be a GENUINE flag/long-option, not any sed "
        "invocation",
        [("        return any(_SED_INPLACE_CLUSTER.match(a) or "
          "_SED_INPLACE_LONG.match(a)\n                    for a in args)",
          "        return True")],
        {"S2"},
    ),
    "M4_global_digit_gate": (
        "a substitution carrying `g` or a digit flag must not be reported "
        "as non-global",
        [('        if "g" not in flags and not any(c.isdigit() for c in '
          'flags):\n            out.append((m.group(0), flags))',
          "        out.append((m.group(0), flags))")],
        {"S1", "S5", "S10"},
    ),
    "M5_heredoc_blanking": (
        "a heredoc body is blanked before parsing, so a MENTION inside one "
        "is not an invocation",
        [('    cmd = RX_HEREDOC.sub("<<", cmd)', "    pass")],
        {"S8"},
    ),
    "M6_lead_skip": (
        "a leading env-assignment (or lead word) is skipped before "
        "matching the invocation",
        [("        i = 0\n        while i < len(argv) and "
          "(ASSIGNMENT.match(argv[i])\n                                  "
          "or argv[i] in LEAD_WORDS):\n            i += 1",
          "        i = 0")],
        {"W10"},
    ),
    "M7_s_prefix_required": (
        "a substitution must be introduced by a literal `s`, not merely "
        "three delimiter-shaped characters",
        [(r'r"(?<![A-Za-z_])s(?P<delim>["', r'r"(?P<delim>["')],
        {"S9"},
    ),
    "M8_script_args_only": (
        "the substitution scan must see only script text, never a filename "
        "argument, or a path can fabricate a substitution the command does "
        "not contain",
        [('_script_args(rest[1:])', 'rest[1:]')],
        {"S10"},
    ),
    "M10_left_anchor_allows_digit": (
        "the left anchor must refuse an identifier character but ACCEPT a "
        "digit, so a numeric sed line address still reads as a substitution",
        [(r'r"(?<![A-Za-z_])s(?P<delim>["', r'r"\bs(?P<delim>["')],
        {"W13"},
    ),
    "M9_perl_octal_zero_flag": (
        "perl's -0 takes an optional octal argument, so -0777 must still "
        "read as carrying the in-place flag",
        [(r'r"^-(?:[np]|0[0-7]*)*i(?:[npi]|0[0-7]*)*(\.\S*)?$"',
          r'r"^-[0np]*i[0npi]*(\.\S*)?$"')],
        {"W12"},
    ),
}

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

    fd, path = tempfile.mkstemp(suffix=".py")
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
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<24} {statement}\n"
          f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses "
      "behaved as declared under reversion")

redos_wrong = _redos_guard()

sys.exit(1 if (wrong or mutation_wrong or redos_wrong) else 0)
