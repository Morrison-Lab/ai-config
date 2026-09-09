"""Test the warn-duplicate-key-blind-verification guard.

Case W1 reproduces the incident this hook exists for, verbatim in shape:
`isinstance(job.get('with'), dict) and len(job['with']) >= 1` run against a
`yaml.safe_load` result, the exact check that could not see a duplicate
`with:` key on gha#839.

The rest of the WARN/SILENT cases each isolate one clause of the hook's
detection logic (an extraction shape, an AST node kind, the already-guarded
escape hatch, the self-implication protection AST parsing buys over a
textual scan), and the mutation harness at the bottom confirms each clause
is load-bearing: revert it, and only the cases that clause protects should
flip.

Run:  python3 hooks/test-warn-duplicate-key-blind-verification.py \\
          hooks/warn-duplicate-key-blind-verification.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1])


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


GUARDED_LOADER = (
    "import yaml\n"
    "class Strict(yaml.SafeLoader): pass\n"
    "def _nodup(loader, node, deep=False):\n"
    "    seen = set()\n"
    "    for k, _ in node.value:\n"
    "        key = loader.construct_object(k, deep=deep)\n"
    "        if key in seen:\n"
    "            raise yaml.YAMLError(f'duplicate key {key!r}')\n"
    "        seen.add(key)\n"
    "    return yaml.SafeLoader.construct_mapping(loader, node, deep)\n"
    "Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, "
    "_nodup)\n"
    "d = yaml.load(open('f'), Loader=Strict)\n"
    "assert len(d) >= 1\n"
)

# ---------------------------------------------------------------- cases
# (case_id, command, description)

SHOULD_WARN = [
    ("W1", "python3 -c \"import yaml\n"
           "job = yaml.safe_load(open('f.yml'))\n"
           "assert isinstance(job.get('with'), dict) and len(job['with']) "
           ">= 1\"",
     "the incident, verbatim in shape: gha#839's own duplicate-key-blind "
     "check, as a -c one-liner"),
    ("W1_semicolon",
     "python3 -c \"import yaml; job = yaml.safe_load(open('f.yml')); "
     "print(isinstance(job.get('with'), dict) and len(job['with']) >= 1)\"",
     "W1's identical check joined with semicolons on ONE physical line. "
     "Python gives every statement on a line the same lineno, so an "
     "ordering test on lineno alone discards the assertion and the case "
     "goes silent -- measured, before the position pair was introduced. "
     "This is at least as natural a shape for a shell one-liner as W1's, "
     "so its absence left the suite pinning the incident only in the form "
     "that happened to be written first"),
    ("W2", "python3 <<'PY'\n"
           "import yaml\n"
           "d = yaml.safe_load(open('f.yml'))\n"
           "assert 'with' in d\n"
           "PY",
     "a heredoc piped directly to python's stdin, using membership `in` "
     "as the sole key-assertion signal"),
    ("W3", "cat <<'PY' > /tmp/check.py\n"
           "import yaml\n"
           "d = yaml.load(open('f.yml'))\n"
           "print(len(d.keys()))\n"
           "PY\n"
           "python3 /tmp/check.py",
     "a heredoc that writes a .py file the SAME command then executes -- "
     "the write-then-run shape"),
    ("W4", "python3 -c \"import yaml\n"
           "d = yaml.full_load(open('f'))\n"
           "ok = d == set()\"",
     "yaml.full_load paired with an `== set(...)` comparison"),
    ("W5", "python3 -c \"from yaml import safe_load\n"
           "d = safe_load(open('f'))\n"
           "print(d.keys())\"",
     "a bare `safe_load(...)` call from `from yaml import safe_load`, "
     "paired with .keys()"),
    ("W6", "python3 -c \"import yaml\n"
           "job = yaml.safe_load(open('f'))\n"
           "if 'with' in job:\n"
           "    print('has with')\"",
     "an `if 'with' in job:` membership test -- an ast.Compare, not a "
     "for-loop"),
    ("W7", "echo hi && python3 -c \"import yaml\n"
           "d = yaml.safe_load(open('f'))\n"
           "assert len(d) >= 1\"",
     "the dangerous invocation chained after an unrelated command"),
    ("W8", "python3 - <<'PY'\n"
           "import yaml\n"
           "d = yaml.safe_load(open('f'))\n"
           "assert len(d) >= 1\n"
           "PY",
     "python's `-` (explicit stdin) form before the heredoc operator"),
    ("W_assert_only", "python3 -c \"import yaml\n"
                       "d = yaml.safe_load(open('f'))\n"
                       "assert d\"",
     "a bare `assert d` with no len/keys/in alongside it -- isolates the "
     "Assert-node clause"),
    ("W_keys_only", "python3 -c \"import yaml\n"
                     "d = yaml.safe_load(open('f'))\n"
                     "ks = d.keys()\"",
     "a bare `.keys()` call with no assert/len/in -- isolates the "
     ".keys() clause"),
    ("W_len_only", "python3 -c \"import yaml\n"
                    "d = yaml.safe_load(open('f'))\n"
                    "n = len(d)\"",
     "a bare `len(d)` call with no assert/keys/in -- isolates the len() "
     "clause"),
    ("W_in_only", "python3 -c \"import yaml\n"
                   "d = yaml.safe_load(open('f'))\n"
                   "print('with' in d)\"",
     "a bare membership expression with no assert/len/keys -- isolates "
     "the `in` clause"),
    ("W_set_only", "python3 -c \"import yaml\n"
                    "d = yaml.safe_load(open('f'))\n"
                    "ok = d == set()\"",
     "a bare `== set(...)` comparison with no assert/len/keys/in -- "
     "isolates the set-equality clause"),
]

SHOULD_STAY_SILENT = [
    ("S_no_assertion", "python3 -c \"import yaml\n"
                        "d = yaml.safe_load(open('f'))\n"
                        "d2 = {**d}\"",
     "the load with no key assertion anywhere -- half the pattern is not "
     "enough"),
    ("S_guarded", "python3 -c \"" + GUARDED_LOADER + "\"",
     "a duplicate-rejecting constructor (add_constructor) already guards "
     "the load -- this IS the fix, and it must not warn on itself"),
    ("S_string_literal", "python3 -c \"print('warns when yaml.safe_load is "
                          "followed by len(x) or assert on keys')\"",
     "self-implication: the phrase appears only inside a string literal "
     "that is PRINTED, never called or asserted -- an AST walk sees a "
     "Constant, not a Call, where a textual scan would misfire"),
    ("S_doc_heredoc", "cat <<'EOF' > docs.md\n"
                       "This check flags yaml.safe_load followed by "
                       "len(job) or assert.\n"
                       "EOF",
     "a heredoc writing PROSE to a .md file -- never executed, and not "
     "even a .py target"),
    ("S_commit_message", "git commit -m \"docs: explain yaml.safe_load + "
                          "len(job) check (gha#839)\"",
     "a git commit message merely mentioning the pattern -- not a "
     "python invocation at all"),
    ("S_written_not_run", "cat <<'PY' > /tmp/check.py\n"
                           "import yaml\n"
                           "d = yaml.safe_load(open('f'))\n"
                           "assert len(d) >= 1\n"
                           "PY\n"
                           "echo done",
     "a heredoc writes a real duplicate-key-blind check to a .py file, "
     "but the SAME command never executes it"),
    ("S_cat_heredoc", "cat <<'EOF'\n"
                       "import yaml\n"
                       "d = yaml.safe_load(open('f'))\n"
                       "assert len(d) >= 1\n"
                       "EOF",
     "a heredoc with real duplicate-key-blind code, fed to `cat` (printed "
     "to stdout) rather than to python -- the cmd-word gate must hold "
     "even though the body would trigger every other clause"),
    ("S_for_loop", "python3 -c \"import yaml\n"
                    "d = yaml.safe_load(open('f'))\n"
                    "for k in d:\n"
                    "    print(k)\"",
     "iterating the parsed mapping (ast.For) says nothing about a "
     "specific key or a count, unlike `if k in d:` (ast.Compare)"),
    ("S_no_yaml_text", "python3 -c \"import json\n"
                        "d = json.load(open('f'))\n"
                        "assert len(d) >= 1\"",
     "json.load, not yaml -- the literal string 'yaml' never appears, "
     "which the cheap gate catches before any AST-level object-identity "
     "confusion between json.load and yaml.load could arise"),
    ("S_syntax_error", "python3 -c \"import yaml\n"
                        "d = yaml.safe_load(open(f)\n"
                        "assert len(d) >= 1\"",
     "invalid Python (unbalanced paren) -- ast.parse must fail closed "
     "rather than falling back to a textual scan that tolerates it"),
    ("S_not_bash", "echo not-a-bash-payload",
     "placeholder; the real non-Bash-tool case is exercised via "
     "NON_COMMAND_PAYLOADS below"),
]

# Two non-command payload shapes that must fail open silently, tested
# directly rather than through the (command, description) table above.
NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Bash", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Bash"}, "absent tool_input"),
    ({"tool_name": "Bash", "tool_input": "python3 -c 'import yaml'"},
     "tool_input is a STRING rather than a dict"),
    ({"tool_name": "Bash", "tool_input": {"command": 12345}},
     "command is not a string"),
    ({"tool_name": "Bash", "tool_input": {}}, "tool_input has no command key"),
    (["Bash", {"command": "python3 -c 'import yaml'"}],
     "the whole payload is a LIST rather than a dict"),
    ({"tool_name": "Edit",
      "tool_input": {"file_path": "/x", "old_string": "yaml.safe_load",
                     "new_string": "yaml.load"}},
     "a different tool entirely, not Bash"),
    ("not even a dict", "the whole payload is a bare string"),
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
    has_context = bool(hso.get("additionalContext"))
    has_system_message = bool(out.get("systemMessage"))
    # a warn-only hook that only ever emits `reason` reaches nobody -- see
    # README's "Writing a warn-only hook: emit systemMessage, not reason"
    if "reason" in out and not has_system_message:
        sys.exit("FATAL: hook emitted `reason` with no `systemMessage` -- "
                 "a warn-only hook's reason is read only alongside "
                 "decision=block, so this warning reaches nobody")
    if has_context and not has_system_message:
        sys.exit("FATAL: hook emitted additionalContext with no "
                 "systemMessage -- this repo's convention pairs the two "
                 "for a PreToolUse warn hook")
    return "WARN" if has_context else "silent"


def verdict_for_command(hook_path, command):
    return verdict(hook_path, bash(command))


wrong = 0
print("should WARN:")
for case_id, command, desc in SHOULD_WARN:
    got = verdict_for_command(HOOK, command)
    wrong += got != "WARN"
    print(f"  {got:<6} {case_id:<16} {desc}")

print("\nshould STAY SILENT:")
for case_id, command, desc in SHOULD_STAY_SILENT:
    if case_id == "S_not_bash":
        continue  # placeholder row, not a real case (see NON_COMMAND_PAYLOADS)
    got = verdict_for_command(HOOK, command)
    wrong += got != "silent"
    print(f"  {got:<6} {case_id:<16} {desc}")

print("\nnon-command payloads (must fail open silently):")
for payload, desc in NON_COMMAND_PAYLOADS:
    got = verdict(HOOK, payload)
    wrong += got != "silent"
    print(f"  {got:<6} {desc}")

REAL_SILENT = [c for c in SHOULD_STAY_SILENT if c[0] != "S_not_bash"]
total = len(SHOULD_WARN) + len(REAL_SILENT) + len(NON_COMMAND_PAYLOADS)
print(f"\n{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness
# Per shared/workflow/algorithmatize-checks.md: break each clause
# deliberately, confirm the test turns red, and verify the mutation actually
# applied by checking WHICH cases flip -- not merely that some output
# changed. Every anchor below must appear in the hook's source EXACTLY ONCE;
# a non-unique or missing anchor means the harness is measuring nothing, and
# the run aborts rather than reporting a false "ok".

EXPECTED = {case_id: "WARN" for case_id, *_ in SHOULD_WARN}
EXPECTED.update({case_id: "silent" for case_id in
                 [c[0] for c in SHOULD_STAY_SILENT if c[0] != "S_not_bash"]})

CASES = {case_id: command for case_id, command, _ in
         SHOULD_WARN + [c for c in SHOULD_STAY_SILENT if c[0] != "S_not_bash"]}

# Built as clean triple-quoted blocks rather than adjacent string-literal
# concatenation -- the first draft of these two mutations glued fragments
# together with a stray embedded quote at the seam, which produced a
# SYNTAX ERROR in the mutated hook file rather than the intended textual-
# scan fallback. A `git diff --quiet` / round-trip check would not have
# caught that (the file DID change); only running it did.
_NAIVE_TEXT_SCAN_AFTER_SYNTAX_ERROR = (
    "    try:\n"
    "        tree = ast.parse(script_text)\n"
    "    except SyntaxError:\n"
    "        naive = ('safe_load' in script_text or 'full_load' in "
    "script_text\n"
    "                 or '.load(' in script_text)\n"
    "        if naive and ('len(' in script_text or 'assert' in "
    "script_text):\n"
    "            return (1, 2)\n"
    "        return None\n"
)

_NAIVE_TEXT_SCAN_REPLACES_AST = (
    '    if "yaml" not in script_text:\n'
    "        return None  # cheap gate before paying for a parse\n"
    "    naive = ('safe_load' in script_text or 'full_load' in "
    "script_text\n"
    "             or '.load(' in script_text)\n"
    "    if naive and ('len(' in script_text or 'assert' in "
    "script_text\n"
    "                  or 'in ' in script_text):\n"
    "        return (1, 2)\n"
    "    return None\n"
    "    nodes = []\n"
)

MUTATIONS = {
    "M1_attr_load_call": (
        "a `<name>.safe_load(...)`/`.load(...)`/`.full_load(...)` "
        "ATTRIBUTE call must be recognized as a yaml load",
        [("    if isinstance(f, ast.Attribute) and f.attr in LOAD_FUNCS:\n"
          "        return True",
          "    if False:\n"
          "        return True")],
        {"W1", "W1_semicolon", "W2", "W3", "W4", "W6", "W7", "W8",
         "W_assert_only", "W_keys_only", "W_len_only", "W_in_only",
         "W_set_only"},
    ),
    "M2_bare_name_load_call": (
        "a bare `safe_load(...)` NAME call (from `from yaml import "
        "safe_load`) must also be recognized",
        [("    if isinstance(f, ast.Name) and f.id in LOAD_FUNCS:\n"
          "        return True\n"
          "    return False",
          "    return False")],
        {"W5"},
    ),
    "M3_already_guarded_escape": (
        "a load already protected by a registered `add_constructor` must "
        "not warn",
        [("    if any(_is_add_constructor_call(n) for n in nodes):\n"
          "        return None  # already guarded -- the fix this hook "
          "recommends\n",
          "")],
        {"S_guarded"},
    ),
    "M4_assert_clause": (
        "a bare `assert` must count as a key assertion",
        [('    if isinstance(node, ast.Assert):\n        return True\n',
          '')],
        {"W_assert_only"},
    ),
    "M5_keys_clause": (
        "a bare `.keys()` call must count as a key assertion",
        [('        if isinstance(f, ast.Attribute) and f.attr == "keys":\n'
          '            return True\n',
          '')],
        {"W5", "W_keys_only"},  # W5 also uses .keys() as its only
                                 # signal, alongside its bare-name
                                 # safe_load import
    ),
    "M6_len_clause": (
        "a bare `len(...)` call must count as a key assertion",
        [('        if isinstance(f, ast.Name) and f.id == "len":\n'
          '            return True\n',
          '')],
        # W1_semicolon rides on this clause and W1 does not, which is a real
        # difference between them rather than an oversight: W1 asserts
        # (`assert isinstance(...) and len(...)`), so the Assert node alone
        # carries it, while W1_semicolon prints (`print(isinstance(...) and
        # len(...))`), leaving `len` as its only key-assertion signal. The
        # printing form is the more natural shell one-liner, which is the
        # whole reason that case exists, so it stays as written.
        {"W_len_only", "W1_semicolon"},
    ),
    "M6b_position_is_a_pair": (
        "statement order must compare (lineno, col_offset), not lineno "
        "alone -- semicolon-joined statements share one lineno",
        [('        pos = (getattr(n, "lineno", 0), getattr(n, "col_offset", 0))\n'
          '        if pos <= load_pos:\n'
          '            continue\n',
          '        pos = (getattr(n, "lineno", 0), 0)\n'
          '        if pos <= load_pos:\n'
          '            continue\n')],
        # Only the one-line case flips. Every multi-line WARN case already
        # has distinct linenos, so zeroing the column changes nothing for
        # them -- which is exactly why the bug survived a 31-case suite and
        # a 15-mutation sweep before this case existed.
        {"W1_semicolon"},
    ),
    "M7_in_clause": (
        "a membership test (`ast.Compare` with an `In` op) must count as "
        "a key assertion",
        [('        if any(isinstance(op, ast.In) for op in node.ops):\n'
          '            return True\n',
          '')],
        {"W6", "W_in_only"},  # W6's `if 'with' in job:` also has no
                              # other signal
    ),
    "M8_set_eq_clause": (
        "an `== set(...)` comparison must count as a key assertion",
        [('        if any(isinstance(op, ast.Eq) for op in node.ops):\n'
          '            for comparator in node.comparators:\n'
          '                if (isinstance(comparator, ast.Call)\n'
          '                        and isinstance(comparator.func, ast.Name)\n'
          '                        and comparator.func.id == "set"):\n'
          '                    return True\n',
          '')],
        {"W4", "W_set_only"},  # W4's `d == set()` also has no other
                               # signal
    ),
    "M9_for_not_compare": (
        "iterating a mapping (ast.For) must NOT read as a key assertion "
        "the way a membership test (ast.Compare) does",
        [("    if isinstance(node, ast.Assert):\n        return True\n",
          "    if isinstance(node, ast.Assert):\n        return True\n"
          "    if isinstance(node, ast.For):\n        return True\n")],
        {"S_for_loop"},
    ),
    "M10_yaml_text_gate": (
        "the literal substring 'yaml' must be present before the (more "
        "expensive, and object-identity-blind) AST walk runs at all -- "
        "without it, `json.load(...)` reads as a yaml load",
        [('    if "yaml" not in script_text:\n'
          '        return None  # cheap gate before paying for a parse\n',
          '')],
        {"S_no_yaml_text"},
    ),
    "M11_syntax_error_fails_closed": (
        "a script that does not parse must be treated as unreadable, "
        "never as a textual match",
        [("    try:\n"
          "        tree = ast.parse(script_text)\n"
          "    except SyntaxError:\n"
          "        return None\n",
          _NAIVE_TEXT_SCAN_AFTER_SYNTAX_ERROR)],
        {"S_syntax_error"},
    ),
    "M12_ast_not_text": (
        "a phrase quoted inside a string literal must not read as an "
        "executed call -- the whole point of parsing rather than "
        "grepping the extracted script text",
        [('    if "yaml" not in script_text:\n'
          '        return None  # cheap gate before paying for a parse\n'
          '    try:\n'
          '        tree = ast.parse(script_text)\n'
          '    except SyntaxError:\n'
          '        return None\n\n'
          '    nodes = list(ast.walk(tree))',
          _NAIVE_TEXT_SCAN_REPLACES_AST)],
        {"S_string_literal", "S_syntax_error", "S_for_loop",
         "S_guarded", "W4", "W5", "W_keys_only", "W_set_only"},
        # The naive scan has no AST/position awareness, no
        # for-loop/membership distinction, and no add_constructor
        # guard -- so it misses W4/W5/W_keys_only/W_set_only
        # (whose only signal is .keys()/==set(), which the naive
        # scan never looks for) and wrongly fires on S_for_loop
        # (a for-loop) and S_guarded (an already-guarded load),
        # in addition to correctly demonstrating the two cases
        # this mutation targets.
    ),
    "M13_dash_c_extraction": (
        "a `-c`/`-e` argument must be extracted as executed python "
        "script text",
        [('            if arg == "-c" and j + 1 < len(rest):\n'
          '                out.append(rest[j + 1])\n'
          '                j += 2\n'
          '                continue\n'
          '            if arg.startswith("-c") and len(arg) > 2:\n'
          '                out.append(arg[2:])\n'
          '                j += 1\n'
          '                continue\n',
          '')],
        {"W1", "W1_semicolon", "W4", "W5", "W6", "W7", "W_assert_only",
         "W_keys_only", "W_len_only", "W_in_only", "W_set_only"},
        # Every -c-based WARN case goes silent (no script text is
        # ever extracted for it); the -c-based SILENT cases stay
        # silent -- they were never WARNing, so removing extraction
        # cannot flip them.
    ),
    "M14_heredoc_stdin_extraction": (
        "a heredoc attached directly to a `python`/`python3` command word "
        "must be extracted as executed script text",
        [("        seg = _last_segment(prefix)\n"
          "        if _PY_CMD_RE.match(_cmd_word(seg)):\n"
          "            scripts.append(body)\n",
          "        seg = _last_segment(prefix)\n"
          "        if False:\n"
          "            scripts.append(body)\n")],
        {"W2", "W8"},
    ),
    "M15_runs_file_check": (
        "a heredoc-written .py file must only count as executed when the "
        "SAME command actually runs it",
        [("        if redirect:\n"
          "            if _runs_file(command, redirect.group(1)):\n"
          "                scripts.append(body)\n"
          "            continue\n",
          "        if redirect:\n"
          "            scripts.append(body)\n"
          "            continue\n")],
        {"S_written_not_run"},
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

    # confirm the mutation actually changed the file before trusting any
    # verdict measured against it
    if mutated == SOURCE:
        sys.exit(f"FATAL: clause {clause} produced an IDENTICAL file -- "
                 "the mutation did not apply")

    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        with open(path, encoding="utf-8") as fh:
            on_disk = fh.read()
        if on_disk != mutated:
            sys.exit(f"FATAL: clause {clause}'s mutated file was not "
                     "written back correctly")
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

# ------------------------------------------------------------ coverage note
# Cases with no dedicated mutation above: S_commit_message and S_doc_heredoc
# and S_cat_heredoc are protected by the same cmd-word/extraction gates
# already exercised by M13/M14 (removing dash-c extraction or heredoc-stdin
# extraction does not touch them, since neither is a python invocation or a
# heredoc attached to one -- git/cat are never treated as python regardless).
# They are true negative controls: no clause exists whose removal would make
# THEM specifically fire, because nothing in the extraction logic ever
# considers their command word. Reported here rather than silently omitted.
UNMUTATED = {"S_commit_message", "S_doc_heredoc", "S_cat_heredoc",
             "S_no_assertion"}
covered_by_mutation = set()
for _clause, (_stmt, _edits, flips) in MUTATIONS.items():
    covered_by_mutation |= flips
uncovered = (set(EXPECTED) - covered_by_mutation) - UNMUTATED
if uncovered:
    print(f"\nWARNING: {sorted(uncovered)} have no mutation asserting they "
          "are load-bearing -- pin one or confirm they belong in UNMUTATED")
print(f"\nDeclared negative controls with no dedicated mutation (protected "
      f"only by never matching any extraction path at all): "
      f"{sorted(UNMUTATED)}")

sys.exit(1 if (wrong or mutation_wrong or uncovered) else 0)
