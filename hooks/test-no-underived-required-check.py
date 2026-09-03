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
import importlib.util
import json
import os
import subprocess
import sys

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
        "Bash", "gh api -XPUT repos/o/r/rulesets/1 --input rs.json", True,
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
_MODULES = {}
BASH_TOOLS = ("Bash", "bash", "run_command", "execute_command", "terminal",
              "shell")


def _load(hook_path):
    """Import a guard module from `hook_path` under a unique name.

    In-process rather than by subprocess, deliberately. The mutation harness
    runs every case against every mutant, and a `python3` cold start costs
    ~1.4s on macOS -- so the subprocess form spends minutes on interpreter
    startup alone, which is long enough to look like a hang.
    """
    spec = importlib.util.spec_from_file_location(
        f"guard_{abs(hash(hook_path))}", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verdict(hook_path, case_id):
    """Run the guard at `hook_path` against a case; True when it warns."""
    _, tool_name, command, _ = CASES[case_id]
    if tool_name not in BASH_TOOLS:
        return False  # main() filters these before evaluate() is reached
    module = _MODULES.setdefault(hook_path, _load(hook_path))
    return module.evaluate(command) is not None


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


print("behaviour tests:")
wrong = 0
for cid in CASES:
    got = verdict(HOOK, cid)
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
    "write_method": (
        "a write method is required, so a read is not a settings change",
        [("        if not RX_WRITE_METHOD.search(segment):\n"
          "            continue\n", "")],
        {"S1"},
    ),
    "method_shorthand": (
        "`-XPUT` with no separator is a write method too",
        [(r'r"(?:-X|--method)[=\s]*(?:PUT|PATCH|POST)\b"',
          r'r"(?:-X|--method)[=\s]+(?:PUT|PATCH|POST)\b"')],
        {"W3"},
    ),
    "method_post": (
        "POST creates a ruleset, so it is a write method",
        [(r'r"(?:-X|--method)[=\s]*(?:PUT|PATCH|POST)\b"',
          r'r"(?:-X|--method)[=\s]*(?:PUT|PATCH)\b"')],
        {"W4", "W5"},
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
        {"W6"},
    ),
    "payload_contexts": (
        "a `contexts` key counts even without the field name",
        [(r'r"required_status_checks|\bcontexts\b|--input\b"',
          r'r"required_status_checks|--input\b"')],
        set(),  # W2 also names required_status_checks; documented as such
    ),
    "payload_input": (
        "`--input` counts, since the document cannot be read from here",
        [(r'r"required_status_checks|\bcontexts\b|--input\b"',
          r'r"required_status_checks|\bcontexts\b"')],
        {"W1", "W3", "W4", "W5", "W7"},  # every case whose payload is a file
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
        {"W7"},
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
HOOKS_DIR = os.path.dirname(HOOK)
_mutant_paths = []
try:
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

        path = os.path.join(HOOKS_DIR, f".mutant-{clause}.py")
        _mutant_paths.append(path)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(mutated)

        flipped = {cid for cid in CASES if verdict(path, cid) != EXPECTED[cid]}
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
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<22} {statement}\n"
              f"         {note}")

finally:
    for path in _mutant_paths:
        try:
            os.unlink(path)
        except OSError:
            pass

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under reversion")

sys.exit(1 if (wrong or mutation_wrong) else 0)
