"""Test the warn-heredoc-doubled-backslash guard.

Case W1 reproduces the transport hazard this hook exists for, in miniature:
a heredoc body containing a doubled backslash (`\\\\n`), the shape that, on
this platform, arrives at the interpreter as a single backslash rather than
surviving as typed (ai-config#1923; recurred ai-config#3362). Per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against
the incident that prompted it", the case mirrors the incident's own shape
(a doubled backslash written into a Python string literal inside a heredoc)
rather than a paraphrase.

Note that this TEST FILE is itself written with the Write tool, not composed
through a Bash-tool heredoc -- so the doubled backslashes below are ordinary
Python string literals and are NOT subject to the collapse this hook detects.
Only a heredoc BODY passed as a Bash tool_input.command is in scope.

The rest of the WARN/SILENT cases each isolate one clause of the hook's
detection logic, and the mutation harness at the bottom confirms each clause
is load-bearing: revert it, and only the cases that clause protects should
flip.

Run:  python3 hooks/test-warn-heredoc-doubled-backslash.py \\
          hooks/warn-heredoc-doubled-backslash.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1])

B = chr(92)  # a single literal backslash, built rather than typed doubled --
             # the remedy this hook itself recommends, applied to its own test.


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def heredoc(delim, body, quoted=True, dash=False):
    """Build a `<<[-]DELIM ... DELIM` (or `<<[-]'DELIM' ...`) block."""
    opener = "<<" + ("-" if dash else "")
    q = "'" if quoted else ""
    return f"{opener}{q}{delim}{q}\n{body}\n{delim}\n"


# ---------------------------------------------------------------- cases
# (case_id, command, description)

SHOULD_WARN = [
    ("W1", "python3 " + heredoc("PY", 'target = "a' + B * 2 + 'nb"'),
     "the incident's own shape: a doubled backslash inside a Python string "
     "literal, written through a quoted-delimiter heredoc"),
    ("W2", "cat " + heredoc("EOF", "printf " + chr(34) + "a" + B * 2 + "nb" + chr(34)),
     "a doubled backslash inside a shell printf format string, same shape "
     "as the markdown-snippet incident of 2026-09-08"),
    ("W3", "cat " + heredoc("EOF", "a" + B * 2 + "b", dash=True),
     "<<- (dash form) with a doubled backslash in the body"),
    ("W4", "cat " + heredoc("EOF", "a" + B * 2 + "b", quoted=False),
     "an UNQUOTED delimiter (<<EOF, not <<'EOF') with a doubled backslash"),
    ("W5",
     "cat " + heredoc("FIRST", "a" + B + "b")
     + " && cat " + heredoc("SECOND", "c" + B * 2 + "d"),
     "two heredocs; only the SECOND carries a doubled backslash -- the "
     "match must name the offending one, not the first"),
    ("W6", "cat " + heredoc("EOF", "line one\nline two " + B * 2 + " more\nline three"),
     "the doubled backslash sits on a line other than the first body line"),
    ("W7",
     "cat " + heredoc("EOF", "first line\nEOF # not the end\na" + B * 2 + "b"),
     "a body line reading `EOF # not the end` must NOT be mistaken for the "
     "closer -- Bash requires the terminator line to be exactly the "
     "delimiter, so the doubled backslash on the line after the fake "
     "terminator must still be found"),
    ("W8",
     "<<-'EOF'\na" + B * 2 + "b\n\tEOF\n",
     "<<- (dash form) whose terminator line is indented with a tab -- Bash "
     "strips leading tabs for <<- only, and the closer must still "
     "recognize it"),
    ("W9", "cat " + heredoc("END-MSG", "a" + B * 2 + "b"),
     "a HYPHENATED delimiter (`END-MSG`) is an ordinary shell word, not a "
     "`\\w+` match -- the opener must still be recognized"),
    ("W10", "cat " + heredoc("EOF.1", "a" + B * 2 + "b"),
     "a DOTTED delimiter (`EOF.1`) is likewise an ordinary shell word and "
     "must not go unrecognized"),
    ("W11",
     "cat <<< " + chr(34) + "a" + B + "b" + chr(34)
     + " && cat " + heredoc("EOF", "c" + B * 2 + "d"),
     "a `<<<` here-string (no heredoc body of its own) followed by a REAL "
     "heredoc elsewhere in the same command -- the here-string must not be "
     "mistaken for an opener, and the real heredoc's doubled backslash "
     "must still be found"),
    ("W12",
     "cat <<'A' <<'B'\na" + B + "b\nA\nc" + B * 2 + "d\nB\n",
     "TWO heredocs queued on ONE opener line (`cat <<'A' <<'B'`), where "
     "only the SECOND body carries a doubled backslash -- B's opener sits "
     "before A's terminator, so a scanner that finds one opener at a time "
     "and resumes after A's closer never sees B and silently skips its "
     "body"),
]

SHOULD_STAY_SILENT = [
    ("S1", "python3 " + heredoc("PY", 'target = "a' + B + 'nb"'),
     "a heredoc body with only SINGLE backslashes -- the shape that "
     "survives transport intact and needs no warning"),
    ("S2", "echo " + chr(34) + "a" + B * 2 + "nb" + chr(34),
     "a doubled backslash OUTSIDE any heredoc -- a plain command-line "
     "argument is not subject to the heredoc-body collapse this hook "
     "warns about"),
    ("S3", "cat " + heredoc("EOF", "no backslashes here at all"),
     "a heredoc with no backslashes whatsoever"),
    ("S4", "git commit -m " + chr(39) + "see a" + B * 2 + "nb in the diff" + chr(39),
     "a doubled backslash inside a quoted argument, not a heredoc"),
    ("S5", "cat <<< " + chr(34) + "a" + B * 2 + "nb" + chr(34),
     "a `<<<` here-string carrying a doubled backslash and NO heredoc "
     "anywhere in the command -- the here-string's third `<` must not be "
     "mistaken for a `<<` opener that then reads the rest of the command "
     "as a (nonexistent) heredoc body"),
    ("S6",
     "<<-'EOF'\nbody\n\tEOF\necho " + chr(34) + "a" + B * 2 + "nb" + chr(34) + "\n",
     "a properly-closed `<<-` heredoc (tab-indented terminator) followed "
     "by a doubled backslash OUTSIDE the heredoc, in a later command -- "
     "the indent-tolerant closer must find the tab-indented terminator "
     "and stop the body there, not sweep the trailing command in as body "
     "text just because the terminator went unrecognized"),
]

# Two non-command / non-Bash payload shapes that must fail open silently,
# tested directly rather than through the (command, description) table.
NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Bash", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Bash"}, "absent tool_input"),
    ({"tool_name": "Bash", "tool_input": "cat <<'EOF'\na" + B * 2 + "b\nEOF"},
     "tool_input is a STRING rather than a dict -- .get() on a string "
     "would crash rather than fail open"),
    ({"tool_name": "Bash", "tool_input": {"command": 12345}},
     "command is not a string"),
    ({"tool_name": "Bash", "tool_input": {}}, "tool_input has no command key"),
    (["Bash", {"command": "cat <<'EOF'\na" + B * 2 + "b\nEOF"}],
     "the whole payload is a LIST rather than a dict"),
    ({"tool_name": "Edit",
      "tool_input": {"file_path": "/x", "old_string": "a" + B * 2 + "b",
                     "new_string": "a" + B + "b"}},
     "a different tool entirely, not Bash -- a doubled backslash in an Edit "
     "payload's old_string/new_string must not fire this Bash-only guard"),
]

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would "
             "otherwise read as 'silent' on every case and print a perfect "
             "pass")

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()


def verdict(hook_path, payload):
    proc = subprocess.run(
        [sys.executable, hook_path], input=json.dumps(payload),
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
    # scripts/check-hook-output-shape.py requires a warn-only PreToolUse hook
    # to emit additionalContext or systemMessage, and requires the TEST to
    # inspect that shape rather than merely bool(output) -- so assert on the
    # actual field rather than "stdout was non-empty".
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

# Confirm W5 (two heredocs, only the second offends) actually NAMES the
# second delimiter rather than merely warning generically -- a warning that
# fires but blames the wrong heredoc would send a reader to fix the wrong
# block.
def _names_offender_check():
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(bash(
            "cat " + heredoc("FIRST", "a" + B + "b")
            + " && cat " + heredoc("SECOND", "c" + B * 2 + "d")
        )),
        capture_output=True, text=True,
    )
    out = json.loads(proc.stdout)
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext", "")
    if "SECOND" in ctx and "FIRST" not in ctx.split("carries a doubled")[0]:
        print("  ok   NAMES_OFFENDER  W5's warning names the SECOND "
              "delimiter, not the first")
        return 0
    print(f"  WRONG NAMES_OFFENDER  W5's warning did not clearly name the "
          f"offending heredoc: {ctx[:200]!r}")
    return 1


names_wrong = _names_offender_check()

# ------------------------------------------------------------ mutation harness
# Per shared/workflow/algorithmatize-checks.md: break each clause
# deliberately, confirm the test turns red, and verify the mutation actually
# applied by checking WHICH cases flip -- not merely that some output
# changed. Every anchor below must appear in the hook's source EXACTLY ONCE.

EXPECTED = {case_id: "WARN" for case_id, *_ in SHOULD_WARN}
EXPECTED.update({case_id: "silent" for case_id, *_ in SHOULD_STAY_SILENT})

CASES = {case_id: command
         for case_id, command, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

MUTATIONS = {
    "M1_doubled_backslash_detection": (
        "the detector must require TWO consecutive backslashes, not one",
        [(r'_DOUBLED_BACKSLASH = re.compile(r"' + B + B + B + B + '")',
          r'_DOUBLED_BACKSLASH = re.compile(r"' + B + B + '")')],
        # flipping to a SINGLE-backslash detector makes every heredoc-body
        # case with any backslash warn, including S1 (single backslash only)
        {"S1"},
    ),
    "M2_heredoc_opener_recognized": (
        "only text INSIDE a recognized heredoc body may be scanned -- "
        "breaking the shared opener import makes every heredoc go "
        "unrecognized, same as a doubled backslash in a plain argument "
        "that must not warn",
        [("from shellcmd import RX_HEREDOC_OPEN",
          "from shellcmd import RX_HEREDOC_OPEN_MISSING")],
        # an unresolvable import leaves RX_HEREDOC_OPEN None, so no heredoc
        # is ever recognized and every WARN case goes silent
        {"W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W10", "W11",
         "W12"},
    ),
    "M3_closer_indent_approximation": (
        "the closer's `[ \\t]*` indent tolerance must accept a `<<-` "
        "terminator's leading tab, even though it is a known, deliberate "
        "approximation (see the module docstring) that can also cut a "
        "body short on an indented delimiter-lookalike line",
        [(r'r"^[ \t]*" + re.escape(delim) + r"[ \t]*(?=\n|\Z)"',
          r'r"^" + re.escape(delim) + r"[ \t]*(?=\n|\Z)"')],
        # W8's own offending line sits BEFORE its tab-indented terminator,
        # so losing the terminator only widens W8's captured body (it still
        # runs to end-of-input and still contains the offense) -- WARN
        # either way, no flip. S6 is what actually exercises this clause:
        # its heredoc is properly closed by a tab-indented terminator, and
        # the doubled backslash sits AFTER it, outside the heredoc. Losing
        # the terminator sweeps that trailing command into the (now
        # unterminated) body and flips S6 from silent to WARN.
        {"S6"},
    ),
    "M4_all_openers_on_one_line": (
        "every heredoc opened on ONE opener line must get its body scanned, "
        "in opener order -- collecting only the first opener per line and "
        "resuming after its closer leaves the later opener behind the "
        "cursor, never re-found",
        [("            m = RX_HEREDOC_OPEN.search(command, m.end())",
          "            m = None")],
        # only W12 queues two heredocs on one line; W5's two heredocs each
        # open on their own line, so it is unaffected
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

    # The mutated copy must live NEXT TO the real hook, not in the OS temp
    # directory. The hook resolves `scripts/lib/shellcmd.py` relative to its
    # own `__file__` (two directories up), so a mutated copy dropped
    # elsewhere silently fails that import -- RX_HEREDOC_OPEN becomes None,
    # every heredoc goes unrecognized, and every WARN case flips to silent
    # regardless of which clause was actually mutated. That reads as every
    # clause being load-bearing, which is not what the mutation is testing.
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
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<28} {statement}\n"
          f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses "
      "behaved as declared under reversion")

sys.exit(1 if (wrong or names_wrong or mutation_wrong) else 0)
