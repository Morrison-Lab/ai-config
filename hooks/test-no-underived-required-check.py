"""Test the no-underived-required-check guard, clause by clause.

Test case W1 is the incident shape verbatim, per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against the
incident that prompted it": a `gh api -X PUT .../rulesets/<id> --input <file>`
composed from check names read off a merged pull request.

The S2x cases are the documentation shapes README.md names as this repo's
cautionary example -- a heredoc, a commit message, and a comment body that
merely QUOTE such a command. `require-gh-repo-flag.py`'s first version fired
on all of them, which is why this guard borrows that hook's parser rather than
scanning the raw string.

The second half is the MUTATION harness described in
`shared/workflow/algorithmatize-checks.md`'s "A guard whose condition ANDs
several clauses masks its own mutation test the same way". It mutates the
regex ALTERNATIONS as well as the `if` statements: an earlier draft reported
6/6 clauses covered while four sub-clauses flipped nothing when reverted, so
its green line was positive evidence for coverage that did not exist.

Run:  python3 hooks/test-no-underived-required-check.py \\
          hooks/no-underived-required-check.py
"""
import json
import os
import subprocess
import sys
import types

HOOK = os.path.abspath(sys.argv[1])
SOURCE = open(HOOK, encoding="utf-8").read()

RULESET_PUT = (
    "gh api -X PUT repos/ucdavis/rampp/rulesets/3889405 --input rs-fixed.json"
)

# id -> (description, tool_name, command, expect_warning)
CASES = {
    "W1": (
        "INCIDENT: ruleset PUT supplying a whole document",
        "Bash", RULESET_PUT, True,
    ),
    "W2": (
        "branch-protection PATCH naming contexts inline",
        "Bash",
        'gh api -X PATCH repos/o/r/branches/main/protection '
        '-f required_status_checks=\'{"contexts":["lint"]}\'',
        True,
    ),
    "W3": (
        "the concatenated pflag shorthand -XPUT, which gh accepts",
        # No parameter flag at all, so the implicit-POST inference cannot
        # carry this case and the shorthand is what pins it. The payload
        # marker is in the PATH. (An earlier draft appended `< body.json` and
        # called it "the body on stdin"; gh reads a request body only via
        # `--input` -- with `-` for stdin -- so a bare redirect sends nothing.)
        "Bash",
        "gh api -XPUT "
        "repos/o/r/branches/main/protection/required_status_checks",
        True,
    ),
    "W4": (
        "an ORG ruleset write, blocking merges across every repo in the org",
        "Bash", "gh api -X POST orgs/myorg/rulesets --input rs.json", True,
    ),
    "W5": (
        "a POST creating a repository ruleset",
        "Bash", "gh api -X POST repos/o/r/rulesets --input rs.json", True,
    ),
    "W6": (
        "the bare field name, with no --input and no 'contexts'",
        "Bash",
        "gh api -X PUT repos/o/r/rulesets/1 "
        "-f required_status_checks[][context]=lint",
        True,
    ),
    "W7": (
        "the write is the second segment of a compound command",
        "Bash",
        "cd /tmp && gh api -X PUT repos/o/r/rulesets/1 --input rs.json",
        True,
    ),
    "W8": (
        "IMPLICIT POST: gh switches to POST when parameters are supplied",
        "Bash", "gh api repos/o/r/rulesets --input rs.json", True,
    ),
    "W9": (
        "a write inside a for-loop body, applied across many repositories",
        "Bash",
        "for r in a b c; do gh api -X PUT repos/o/$r/rulesets/1 "
        "--input rs.json; done",
        True,
    ),
    "W10": (
        "a write inside an if-then branch",
        "Bash",
        "if [ -f rs.json ]; then gh api -X PUT repos/o/r/rulesets/1 "
        "--input rs.json; fi",
        True,
    ),
    "W11": (
        "UNBALANCED QUOTE: shlex fails, the fallback still anchors on gh api",
        "Bash",
        "gh api -X PUT repos/o/r/rulesets/1 -f x='unclosed --input rs.json",
        True,
    ),
    "W12": (
        "a bare `contexts` key with no required_status_checks and no --input",
        # The URL deliberately stops at /protection. Including
        # /required_status_checks would put the marker in the path, masking
        # the `contexts` alternative this case exists to pin.
        "Bash",
        "gh api -X PATCH repos/o/r/branches/main/protection "
        "-f 'contexts[]=lint'",
        True,
    ),
    "W13": (
        "an explicit method with no parameter flags at all",
        # This is what pins RX_WRITE_METHOD. Every other write case carries a
        # parameter flag, so the implicit-POST inference alone would cover
        # them -- checking the mutation anchor is what surfaced that.
        "Bash",
        "gh api --method PUT "
        "repos/o/r/branches/main/protection/required_status_checks",
        True,
    ),
    "W14": (
        "`-f` alone, gh's documented field form, with no --input",
        "Bash",
        "gh api repos/o/r/rulesets "
        "-f 'required_status_checks[][context]=lint'",
        True,
    ),
    "W15": (
        "`--field` alone, the long form of the same thing",
        "Bash",
        "gh api repos/o/r/rulesets "
        "--field 'required_status_checks[][context]=lint'",
        True,
    ),
    "W16": (
        "an explicit PATCH with no parameter flags",
        "Bash",
        "gh api -X PATCH "
        "repos/o/r/branches/main/protection/required_status_checks",
        True,
    ),
    "W17": (
        "a leading VAR=value assignment precedes the command word",
        "Bash",
        "GH_TOKEN=x gh api -X PUT repos/o/r/rulesets/1 --input rs.json",
        True,
    ),
    "W18": (
        "piped into xargs -- one write across many repositories",
        "Bash",
        "gh repo list -q .name | xargs -I{} gh api -X PUT "
        "repos/o/{}/rulesets/1 --input rs.json",
        True,
    ),
    "W19": (
        "UNBALANCED QUOTE behind a leading assignment",
        # Exercises the fallback's RX_ENV_PREFIX, which the plain
        # unbalanced-quote case (W11) leaves untouched.
        "Bash",
        "GH_TOKEN=x gh api -X PUT "
        "repos/o/r/branches/main/protection/required_status_checks "
        "-f x='unclosed",
        True,
    ),
    "W20": (
        "UNBALANCED QUOTE behind a command wrapper",
        # Exercises the fallback's RX_SHELL_WRAPPER_PREFIX. `nice` rather than
        # `timeout`, whose duration is a positional argument the wrapper-flag
        # skip does not cover -- a real limit, recorded rather than papered
        # over.
        "Bash",
        "nice gh api -X PUT "
        "repos/o/r/branches/main/protection/required_status_checks "
        "-f x='unclosed",
        True,
    ),
    "W21": (
        "`timeout 60 gh api ...` -- a wrapper with a POSITIONAL argument",
        "Bash",
        "timeout 60 gh api -X PUT repos/o/r/rulesets/1 --input rs.json",
        True,
    ),
    "S6": (
        "an explicit HEAD is a read, like GET",
        "Bash",
        "gh api -X HEAD repos/o/r/branches/main/protection/"
        "required_status_checks -f per_page=100",
        False,
    ),
    "S1": (
        "a READ of the same ruleset endpoint carries no write method",
        "Bash",
        "gh api repos/ucdavis/rampp/rulesets/3889405 "
        "--jq '.rules[].parameters.required_status_checks'",
        False,
    ),
    "S2": (
        "a ruleset PUT whose payload concerns no status checks",
        "Bash", "gh api -X PUT repos/o/r/rulesets/1 -f enforcement=disabled",
        False,
    ),
    "S3": (
        "a write to an unrelated endpoint",
        "Bash", "gh api -X POST repos/o/r/issues --input issue.json", False,
    ),
    "S4": (
        "a non-Bash tool is out of scope",
        "Read", RULESET_PUT, False,
    ),
    "S5": (
        "an explicit GET with parameters is a query, not a write",
        # Carries both a payload marker (in the path) and a parameter flag, so
        # the read-method clause is the ONLY thing keeping it silent.
        "Bash",
        "gh api -X GET repos/o/r/branches/main/protection/"
        "required_status_checks -f per_page=100",
        False,
    ),
    "S20": (
        "DOC SHAPE: a heredoc documenting the command",
        "Bash",
        "cat <<'EOF' > docs/note.md\n"
        "Run this to fix the ruleset:\n"
        "  " + RULESET_PUT + "\n"
        "EOF",
        False,
    ),
    "S21": (
        "DOC SHAPE: a commit message quoting the command",
        "Bash",
        'git commit -m "document ' + RULESET_PUT + '"',
        False,
    ),
    "S22": (
        "DOC SHAPE: a PR comment body quoting the command",
        "Bash",
        "gh pr comment 5 --body 'we ran " + RULESET_PUT + "'",
        False,
    ),
    "S23": (
        "DOC SHAPE: grepping for the guard's own trigger",
        "Bash",
        'grep -rn "gh api -X PUT repos/o/r/rulesets/1 --input" notes/',
        False,
    ),
}
EXPECTED = {cid: spec[3] for cid, spec in CASES.items()}
BASH_TOOLS = ("Bash", "bash", "run_command", "execute_command", "terminal",
              "shell")


def load_module(source, label):
    """Build a guard module from `source` IN MEMORY, as `test-warn-status-read-after-pipe.py` does.

    `__file__` is set to the real hook path so `_load_shell_parser`, which
    resolves `require-gh-repo-flag.py` from its own directory, still finds it.
    An earlier draft wrote mutants to fixed paths inside `hooks/`, which
    collided between concurrent runs and left strays behind on a kill.

    In-process rather than by subprocess, deliberately: the harness runs every
    case against every mutant, and a `python3` cold start costs ~1.4s on
    macOS, so the subprocess form spends minutes on interpreter startup alone
    -- long enough to look like a hang.
    """
    module = types.ModuleType(f"guard_{label}")
    module.__file__ = HOOK
    exec(compile(source, HOOK, "exec"), module.__dict__)
    return module


class MutantCrashed(Exception):
    """A mutant raised rather than behaving differently."""


def verdict(module, case_id):
    """Run a loaded guard module against a case; True when it warns."""
    _, tool_name, command, _ = CASES[case_id]
    if tool_name not in BASH_TOOLS:
        return False  # main() filters these before evaluate() is reached
    try:
        return module.evaluate(command) is not None
    except Exception as exc:
        # A mutant that CRASHES measures nothing -- the clause it reverted is
        # untested either way, and the traceback hides which. Surfaced as its
        # own outcome so the anchor gets fixed rather than the run dying.
        raise MutantCrashed(f"{type(exc).__name__}: {exc}") from exc


def cli_verdict(hook_path, case_id):
    """Drive the guard through its real stdin/stdout contract, once."""
    _, tool_name, command, _ = CASES[case_id]
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps({
            "tool_name": tool_name,
            "tool_input": {"command": command},
        }),
        capture_output=True, text=True, timeout=30,
    )
    if not proc.stdout.strip():
        return False, False
    try:
        out = json.loads(proc.stdout)
    except Exception:
        return False, False
    warned = "additionalContext" in (out.get("hookSpecificOutput") or {})
    return warned, bool(out.get("systemMessage"))


BASELINE = load_module(SOURCE, "baseline")

print("behaviour tests:")
wrong = 0
for cid in CASES:
    got = verdict(BASELINE, cid)
    ok = got == EXPECTED[cid]
    wrong += not ok
    print(f"  {'ok  ' if ok else 'WRONG'} {cid:<4} "
          f"{'warns ' if got else 'silent'}  {CASES[cid][0]}")
print(f"\n{len(CASES) - wrong}/{len(CASES)} cases behaved as expected")

# The loop above calls evaluate() directly for speed, which skips main()'s
# stdin parsing and JSON envelope. Drive the real contract once per polarity
# so a break in that wiring cannot pass unnoticed, and assert the
# systemMessage every sibling warn-only PreToolUse hook emits.
print("\nstdin/stdout contract (real subprocess, one case per polarity):")
for cid, want_sysmsg in (("W1", True), ("S1", False), ("S4", False)):
    got, sysmsg = cli_verdict(HOOK, cid)
    ok = got == EXPECTED[cid] and sysmsg == want_sysmsg
    wrong += not ok
    print(f"  {'ok  ' if ok else 'WRONG'} {cid:<4} "
          f"{'warns ' if got else 'silent'}  "
          f"systemMessage={'yes' if sysmsg else 'no'}")

# --- mutation harness: revert one clause, see which cases flip ------------
MUTATIONS = {
    "explicit_write_method": (
        "an explicit -X/--method PUT|PATCH|POST is a write on its own",
        [("    if RX_WRITE_METHOD.search(segment):\n        return True\n",
          "")],
        {"W3", "W13", "W16"},  # the writes carrying no parameter flag
    ),
    "is_write_gate": (
        "a segment that neither declares nor implies a write is a read",
        [("        if not segment_is_write(segment):\n            continue\n",
          "")],
        # S5 and S6 flip too: with the gate gone, every segment is
        # scanned, so the explicit GET and HEAD reach the payload clause.
        {"S1", "S5", "S6"},
    ),
    "method_shorthand": (
        "`-XPUT` with no separator is a write method too",
        [(r'r"(?:-X|--method)[=\s]*(?:PUT|PATCH)\b"',
          r'r"(?:-X|--method)[=\s]+(?:PUT|PATCH)\b"')],
        {"W3"},
    ),
    "implicit_post_f_flag": (
        "`-f`/`-F` alone makes it a write",
        [(r'r"(?:^|\s)(?:--input\b|-[fF]\s|--(?:raw-)?field\b)"',
          r'r"(?:^|\s)(?:--input\b|--(?:raw-)?field\b)"')],
        {"W14"},
    ),
    "implicit_post_field_flag": (
        "`--field`/`--raw-field` alone makes it a write",
        [(r'r"(?:^|\s)(?:--input\b|-[fF]\s|--(?:raw-)?field\b)"',
          r'r"(?:^|\s)(?:--input\b|-[fF]\s)"')],
        {"W15"},
    ),
    "method_patch": (
        "PATCH is an explicit write method, not only PUT",
        [(r'r"(?:-X|--method)[=\s]*(?:PUT|PATCH)\b"',
          r'r"(?:-X|--method)[=\s]*(?:PUT)\b"')],
        {"W16"},
    ),
    "read_method_head": (
        "HEAD is a read method, not only GET",
        [(r'r"(?:-X|--method)[=\s]*(?:GET|HEAD)\b"',
          r'r"(?:-X|--method)[=\s]*(?:GET)\b"')],
        {"S6"},
    ),
    "env_assignment_strip": (
        "a leading VAR=value assignment is stripped before the command word",
        [('        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):\n'
          '            tokens.pop(0)\n', "        if False:\n            pass\n")],
        # W19 also carries an assignment but reaches the FALLBACK path, whose
        # own stripping is a separate clause (fallback_env_strip).
        {"W17"},
    ),
    "command_wrappers": (
        "wrappers taking a command as an argument are stripped too",
        [('COMMAND_WRAPPERS = ("env", "command", "xargs", "timeout", "nice", "stdbuf",\n'
          '                    "parallel")',
          'COMMAND_WRAPPERS = ("env", "command")')],
        {"W18", "W20", "W21"},
    ),
    "wrapper_duration_skip": (
        "a wrapper's positional duration is skipped too",
        [("            if tokens and RX_DURATION.match(tokens[0]):\n"
          "                tokens.pop(0)\n", "")],
        {"W21"},
    ),
    "wrapper_own_flags": (
        "a wrapper's own flags are dropped along with it",
        [('            while tokens and tokens[0].startswith("-"):\n'
          "                tokens.pop(0)\n", "")],
        {"W18"},
    ),
    "fallback_env_strip": (
        "the shlex fallback strips a leading assignment",
        [('        stripped = RX_ENV_PREFIX.sub("", stripped).lstrip()\n',
          "")],
        {"W19"},
    ),
    "fallback_prefix_strip": (
        "the shlex fallback strips wrappers and assignments too",
        # Substituted, not deleted: removing the line entirely leaves the
        # NEXT line reading an unbound `stripped`, so the mutant crashes
        # instead of behaving differently, which measures nothing.
        [('stripped = RX_SHELL_WRAPPER_PREFIX.sub("", segment)',
          "stripped = segment")],
        {"W20"},
    ),
    "implicit_post": (
        "parameters alone make it a write, since gh defaults to POST",
        [("    return bool(RX_IMPLICIT_POST.search(segment))",
          "    return False")],
        {"W4", "W5", "W8", "W14", "W15"},
    ),
    "explicit_get_wins": (
        "an explicit GET beats the implicit-POST inference",
        [("    if RX_READ_METHOD.search(segment):\n        return False\n",
          "")],
        {"S5", "S6"},
    ),
    "shell_wrappers": (
        "loop and conditional keywords precede the command word",
        [('        elif tokens[0] in SHELL_WRAPPERS:\n            tokens.pop(0)\n',
          '        elif tokens[0] in ("env", "command"):\n            tokens.pop(0)\n')],
        {"W9", "W10", "W18", "W21"},
    ),
    "shlex_fallback": (
        "an unbalanced quote falls back to anchoring on the command word",
        [('        stripped = RX_SHELL_WRAPPER_PREFIX.sub("", segment)\n'
          '        stripped = RX_ENV_PREFIX.sub("", stripped).lstrip()\n'
          '        return bool(re.match(r"gh\\s+api\\b", stripped))',
          "        return False")],
        {"W11", "W19", "W20"},
    ),
    "protection_endpoint": (
        "only ruleset / branch-protection endpoints are in scope",
        [("        if not RX_PROTECTION_ENDPOINT.search(segment):\n"
          "            continue\n", "")],
        {"S3"},
    ),
    "endpoint_orgs": (
        "organization rulesets are in scope, not only repository ones",
        [("(?:repos|orgs)/", "(?:repos)/")],
        {"W4"},
    ),
    "status_payload": (
        "the payload must concern required status checks",
        [("        if RX_STATUS_PAYLOAD.search(segment):\n"
          "            return True\n", "        return True\n")],
        {"S2"},
    ),
    "payload_field_name": (
        "the bare `required_status_checks` field name counts",
        [(r'r"required_status_checks|\bcontexts\b|--input\b"',
          r'r"\bcontexts\b|--input\b"')],
        # every case whose only payload marker is the field name, whether
        # it appears as a flag value or inside the URL path
        {"W3", "W6", "W13", "W14", "W15", "W16", "W19", "W20"},
    ),
    "payload_contexts": (
        "a `contexts` key counts even without the field name",
        [(r'r"required_status_checks|\bcontexts\b|--input\b"',
          r'r"required_status_checks|--input\b"')],
        {"W12"},
    ),
    "payload_input": (
        "`--input` counts, since the document cannot be read from here",
        [(r'r"required_status_checks|\bcontexts\b|--input\b"',
          r'r"required_status_checks|\bcontexts\b"')],
        # every case whose only payload marker is `--input`
        {"W1", "W4", "W5", "W7", "W8", "W9", "W10", "W11", "W17", "W18",
         "W21"},
    ),
    "heredoc_stripping": (
        "heredoc bodies are dropped before the command is scanned",
        # Mutates ONLY the stripper, leaving the splitter in place. Reverting
        # both at once flipped nothing, because the command-word check then
        # saw `cat` and stayed silent for the wrong reason -- the two halves
        # masked each other.
        [("split_command(strip_heredocs(command))", "split_command(command)")],
        {"S20"},
    ),
    "segment_splitting": (
        "the command is split on shell operators before scanning",
        [("    for segment in split_command(strip_heredocs(command)):",
          "    for segment in [strip_heredocs(command)]:")],
        {"W7", "W9", "W10", "W18"},
    ),
    "command_word_check": (
        "`gh api` must be the command word, not text inside an argument",
        [("        if not segment_invokes_gh_api(segment):\n"
          "            continue\n", "")],
        {"S21", "S22", "S23"},
    ),
}

print("\nmutation tests (revert one clause, see which cases flip):")
mutation_wrong = 0
# Mutants live IN the hooks directory, not in a temp dir beneath it: the
# guard borrows `require-gh-repo-flag.py` from its own directory via
# `os.path.dirname(__file__)`, so a mutant anywhere else -- including a
# subdirectory -- cannot resolve it and dies on import.
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, replace in edits:
        if mutated.count(find) != 1:
            sys.exit(f"FATAL: clause {clause}'s anchor is not present exactly "
                     f"once in {HOOK} (found {mutated.count(find)}). The "
                     "mutation harness is measuring nothing; re-derive the "
                     f"anchor.\n---\n{find}\n---")
        mutated = mutated.replace(find, replace)

    try:
        mutant = load_module(mutated, clause)
        flipped = {cid for cid in CASES if verdict(mutant, cid) != EXPECTED[cid]}
    except MutantCrashed as exc:
        mutation_wrong += 1
        print(f"  WRONG {clause:<22} {statement}\n"
              f"         MUTANT CRASHED ({exc}) -- the reversion broke the "
              "module rather than its behaviour; substitute the clause "
              "instead of deleting it")
        continue
    ok = flipped == expected_flips
    mutation_wrong += not ok
    if not flipped and expected_flips:
        note = "NOTHING FLIPPED -- this clause is untested"
    elif ok:
        note = ("flipped " + ", ".join(sorted(flipped))
                if flipped else "flipped nothing, as declared")
    else:
        note = f"flipped {sorted(flipped)}, expected {sorted(expected_flips)}"
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<22} {statement}\n"
          f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under reversion")

sys.exit(1 if (wrong or mutation_wrong) else 0)
