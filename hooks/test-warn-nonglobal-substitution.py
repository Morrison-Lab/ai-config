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
]

SHOULD_STAY_SILENT = [
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
CASES = {case_id: command
         for case_id, command, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

MUTATIONS = {
    "M1_cmd_word_gate": (
        "a command whose leading word is not perl/sed must never be "
        "treated as carrying the in-place flag",
        [("    return False", "    return True")],
        {"S3", "S4"},
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
        {"S1", "S5"},
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
        [(r'r"\bs(?P<delim>["', r'r"(?P<delim>["')],
        {"S9"},
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

sys.exit(1 if (wrong or mutation_wrong) else 0)
