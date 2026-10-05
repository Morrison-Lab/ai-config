"""Test the no-interpreter-heredoc guard.

The guard DENIES a heredoc whose body is the script an interpreter reads from
stdin AND carries a backslash or a backtick (ai-config#4298). Case D1 mirrors
the incident: a LaTeX `\\frac` written through `python - <<'EOF'`.

This TEST FILE is written with the Write tool, not through a Bash heredoc, and
builds backslashes with chr(92) -- the remedy the guard itself prescribes.

Each mutation reverts one clause of the hook and the harness checks WHICH
cases flip, not merely that something did.

Run:  python3 hooks/test-no-interpreter-heredoc.py \\
          hooks/no-interpreter-heredoc.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1])

B = chr(92)  # one literal backslash
T = chr(96)  # one literal backtick


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def heredoc(delim, body, quoted=True, dash=False):
    opener = "<<" + ("-" if dash else "")
    q = "'" if quoted else ""
    return f"{opener}{q}{delim}{q}\n{body}\n{delim}\n"


LATEX = "s = 'x = " + B * 2 + "frac{a}{b}'"
TICK = "print('use " + T + "code" + T + "')"

# (case_id, command, description, env)
SHOULD_DENY = [
    ("D1", "python3 - " + heredoc("EOF", LATEX),
     "the incident: a doubled backslash (\\frac) through python3 - <<'EOF'", {}),
    ("D2", "python3 - " + heredoc("EOF", TICK),
     "a backtick in the body", {}),
    ("D3", "python3 " + heredoc("EOF", "print('a" + B + "nb')"),
     "bare `python3 <<EOF` (no `-`, no positional): stdin is the script; a "
     "SINGLE backslash is enough", {}),
    ("D4", "cat " + heredoc("EOF", "print('a" + B + "nb')") .rstrip("\n")
     .replace("<<'EOF'", "<<'EOF' | python3 -", 1) + "\n",
     "heredoc fed to cat, whose output is PIPED to `python3 -`", {}),
    ("D5", "node - " + heredoc("EOF", "console.log('a" + B + "nb')"),
     "node", {}),
    ("D6", "bash -s " + heredoc("EOF", "echo a" + B + "nb"),
     "bash -s reads the script from stdin", {}),
    ("D7", "cd /tmp && python3 - " + heredoc("EOF", LATEX),
     "interpreter after `cd ... &&` on the opener line", {}),
    ("D8", "Rscript - " + heredoc("EOF", "cat('a" + B * 2 + "n')"),
     "Rscript", {}),
    ("D9", "cat " + heredoc("A", "plain") + " && python3 - "
     + heredoc("B", LATEX),
     "two heredocs; only the second feeds an interpreter and carries a "
     "backslash", {}),
    ("D10", "echo ALLOW_INTERPRETER_HEREDOC=1; python3 - "
     + heredoc("EOF", LATEX),
     "the override string only MENTIONED as an echo argument is not an "
     "override", {}),
    ("D11", "ALLOW_INTERPRETER_HEREDOC=0 python3 - " + heredoc("EOF", LATEX),
     "an assignment of any value but 1 is not an override", {}),
    ("D12", "python3.12 - " + heredoc("EOF", LATEX),
     "a versioned interpreter name", {}),
    ("D13", "python3 " + heredoc("EOF", LATEX).replace(
        "<<'EOF'", "<<'EOF' > /tmp/out", 1),
     "an output redirect is not a script path: stdin is still the script",
     {}),
    ("D14", "python3 " + heredoc("EOF", LATEX).replace(
        "<<'EOF'", "<<'EOF' 2>&1", 1),
     "`2>&1` is not a script path either", {}),
    ("D15", "ALLOW_INTERPRETER_HEREDOC=1 true; python3 - "
     + heredoc("EOF", LATEX),
     "the override on an UNRELATED command of the line does not cover the "
     "interpreter's", {}),
    ("D16", "echo it's; python3 - " + heredoc("EOF", LATEX),
     "an unbalanced quote earlier on the opener line must not make the "
     "guard fail open", {}),
    ("D17", "uv run python - " + heredoc("EOF", LATEX),
     "a launcher in front of the interpreter", {}),
    ("D18", "sudo -u bob python3 - " + heredoc("EOF", LATEX),
     "a wrapper option that takes a value", {}),
    ("D19", "timeout 5 python3 - " + heredoc("EOF", LATEX),
     "timeout with a duration", {}),
    ("D20", "python3 /dev/stdin " + heredoc("EOF", LATEX),
     "/dev/stdin is the stdin script spelled as a path", {}),
    ("D21", "R --no-save " + heredoc("EOF", LATEX),
     "R reading its script from stdin", {}),
]

SHOULD_ALLOW = [
    ("A1", "python3 - " + heredoc("EOF", "print('hello')"),
     "interpreter heredoc with no backslash or backtick", {}),
    ("A2", "cat " + heredoc("EOF", "plain text"),
     "cat <<EOF with plain text", {}),
    ("A3", "cat " + heredoc("EOF", "a" + B * 2 + "b and " + T + "x" + T)
     .replace("<<'EOF'", "<<'EOF' > /tmp/f", 1),
     "a backslash/backtick heredoc fed to cat, not an interpreter: the "
     "warn-only hook's territory", {}),
    ("A4", "echo " + chr(34) + "a << b" + chr(34),
     "a quoted string containing `<<`, no heredoc", {}),
    ("A5", "python3 script.py " + heredoc("EOF", "a" + B * 2 + "b"),
     "a script FILE is the program; the heredoc is its stdin data", {}),
    ("A6", "python3 -c " + chr(39) + "import sys" + chr(39) + " "
     + heredoc("EOF", "a" + B * 2 + "b"),
     "-c supplies the code; the heredoc is data", {}),
    ("A7", "ALLOW_INTERPRETER_HEREDOC=1 python3 - " + heredoc("EOF", LATEX),
     "the override as a real leading env assignment", {}),
    ("A8", "python3 - " + heredoc("EOF", LATEX),
     "the override in the hook's own environment",
     {"ALLOW_INTERPRETER_HEREDOC": "1"}),
    ("A9", "cat <<< " + chr(34) + "a" + B * 2 + "b" + chr(34),
     "a here-string, no heredoc", {}),
    ("A11", "python3 a.py - " + heredoc("EOF", "a" + B * 2 + "b"),
     "`-` after a script path is data passed to the script", {}),
    ("A12", "python3 --version " + heredoc("EOF", "a" + B * 2 + "b"),
     "an informational flag runs no script", {}),
    ("A10", "git commit -F - " + heredoc("EOF", "msg " + B * 2 + " " + T + "x" + T),
     "a heredoc fed to git", {}),
]

NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Bash", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Bash"}, "absent tool_input"),
    ({"tool_name": "Bash", "tool_input": {"command": 12345}},
     "command is not a string"),
    (["Bash"], "payload is a list"),
    ({"tool_name": "Edit",
      "tool_input": {"command": "python3 - " + heredoc("EOF", LATEX)}},
     "a different tool, not Bash"),
]

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()


def verdict(hook_path, payload, extra_env=None):
    env = dict(os.environ)
    env.pop("ALLOW_INTERPRETER_HEREDOC", None)
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, hook_path], input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {payload!r}\n"
                 f"{proc.stderr.strip()}")
    if not proc.stdout.strip():
        return "allow"
    out = json.loads(proc.stdout)
    hso = out.get("hookSpecificOutput") or {}
    if hso.get("permissionDecision") == "deny":
        if not hso.get("permissionDecisionReason"):
            sys.exit("FATAL: deny without a reason")
        return "DENY"
    sys.exit(f"FATAL: unexpected output shape {out!r}")


wrong = 0
print("should DENY:")
for case_id, command, desc, env in SHOULD_DENY:
    got = verdict(HOOK, bash(command), env)
    wrong += got != "DENY"
    print(f"  {got:<6} {case_id:<4} {desc}")

print("\nshould ALLOW:")
for case_id, command, desc, env in SHOULD_ALLOW:
    got = verdict(HOOK, bash(command), env)
    wrong += got != "allow"
    print(f"  {got:<6} {case_id:<4} {desc}")

print("\nnon-command payloads (fail open silently):")
for payload, desc in NON_COMMAND_PAYLOADS:
    got = verdict(HOOK, payload)
    wrong += got != "allow"
    print(f"  {got:<6} {desc}")

total = len(SHOULD_DENY) + len(SHOULD_ALLOW) + len(NON_COMMAND_PAYLOADS)
print(f"\n{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# The deny reason must carry the remedy and the override name.
proc = subprocess.run(
    [sys.executable, HOOK], input=json.dumps(bash(SHOULD_DENY[0][1])),
    capture_output=True, text=True)
reason = json.loads(proc.stdout)["hookSpecificOutput"][
    "permissionDecisionReason"]
reason_wrong = 0
for needle in ("Write tool", "ALLOW_INTERPRETER_HEREDOC=1", "python3"):
    if needle not in reason:
        reason_wrong += 1
        print(f"  WRONG deny reason lacks {needle!r}")

# ------------------------------------------------------------ mutations
CASES = {c: (cmd, env) for c, cmd, _d, env in SHOULD_DENY + SHOULD_ALLOW}
EXPECTED = {c: "DENY" for c, *_ in SHOULD_DENY}
EXPECTED.update({c: "allow" for c, *_ in SHOULD_ALLOW})

MUTATIONS = {
    "M1_backtick_trigger": (
        "a backtick alone must trigger, not only a backslash",
        [('                else "backtick" if "`" in body else None)',
          '                else None)')],
        {"D2"},
    ),
    "M2_redirections_are_not_positionals": (
        "an output redirect or 2>&1 must not read as a script path",
        [('_REDIRECT_ONLY = re.compile(r"^[0-9]*[<>]+&?$")',
          '_REDIRECT_ONLY = re.compile(r"^(?!)")'),
         ('_REDIRECT_WITH_TARGET = re.compile(r"^[0-9]*[<>]+&?[^<>]+$")',
          '_REDIRECT_WITH_TARGET = re.compile(r"^(?!)")')],
        {"D13", "D14"},
    ),
    "M3_positional_script_file": (
        "a script path (or `-` after one) means the heredoc is data",
        [('    return positionals[0] == "-" or positionals[0] == "/dev/stdin"',
          '    return True')],
        {"A5", "A6", "A11"},
    ),
    "M9_info_flags": (
        "--version and friends run no script",
        [("    if any(a in _INFO_FLAGS for a in args):",
          "    if False:")],
        {"A12"},
    ),
    "M10_dev_stdin": (
        "/dev/stdin is the script on stdin",
        [(' or positionals[0] == "/dev/stdin"', "")],
        {"D20"},
    ),
    "M11_launchers": (
        "timeout/uv/poetry/pipx/run are wrappers",
        [('"timeout", "uv", "poetry", "pipx", "run", "{", "!"}',
          '"{", "!"}')],
        {"D17", "D19"},
    ),
    "M12_wrapper_value_options": (
        "`sudo -u bob` consumes its value",
        [('_WRAPPER_VALUE_OPTS = {"-u", "-g", "-C", "-U", "-h", "-p", "-r", '
          '"-t"}', "_WRAPPER_VALUE_OPTS = set()")],
        {"D18"},
    ),
    "M13_unbalanced_quote_fallback": (
        "a ValueError from shlex falls back instead of failing open",
        [("    except ValueError:", "    except ZeroDivisionError:")],
        {"D16"},
    ),
    "M4_leading_assignment_override": (
        "a leading ALLOW_INTERPRETER_HEREDOC=1 assignment disarms the guard",
        [('            override = override or token == f"{OVERRIDE}=1"',
          "            override = override")],
        {"A7"},
    ),
    "M5_environment_override": (
        "the hook's own environment disarms the guard",
        [(' or os.environ.get(OVERRIDE) == "1"', "")],
        {"A8"},
    ),
    "M6_interpreter_filter": (
        "only an interpreter's heredoc is refused",
        [("_INTERPRETER.match(name)", "True")],
        {"A3", "D15"},
    ),
    "M7_pipe_is_a_command_boundary": (
        "`|` separates commands on the opener line, so `cat <<EOF | python3 -` "
        "finds the interpreter",
        [('_SHELL_OPS = set("();|&")', '_SHELL_OPS = set("();&")')],
        {"D4"},
    ),
    "M8_override_value_must_be_1": (
        "only =1 is an override",
        [('token == f"{OVERRIDE}=1"', "token.startswith(OVERRIDE + '=')")],
        {"D11"},
    ),
}

print("\nmutation tests (revert one clause, see which cases flip):")
mutation_wrong = 0
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, replace in edits:
        count = mutated.count(find)
        if count != 1:
            sys.exit(f"FATAL: clause {clause}'s anchor appears {count} "
                     f"times in {HOOK}, not once:\n---\n{find}\n---")
        mutated = mutated.replace(find, replace)
    # next to the real hook: it resolves scripts/lib and its sibling by path
    fd, path = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(HOOK))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        flipped = {c for c, (cmd, env) in CASES.items()
                   if verdict(path, bash(cmd), env) != EXPECTED[c]}
    finally:
        os.unlink(path)
    ok = flipped == expected_flips
    mutation_wrong += not ok
    note = (("flipped " + ", ".join(sorted(flipped))) if ok else
            f"flipped {sorted(flipped)}, expected {sorted(expected_flips)}")
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<34} {statement}\n"
          f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses "
      "behaved as declared under reversion")

sys.exit(1 if (wrong or reason_wrong or mutation_wrong) else 0)
