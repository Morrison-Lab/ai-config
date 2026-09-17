#!/usr/bin/env python3
"""Test the warn-new-line-breaks-on-edit guard.

Tests that a `Write`/`Edit` about to place Markdown content on disk with a
new-line-breaks violation (a multi-sentence or unseparated-clause line)
surfaces a PreToolUse warning before the tool runs, while clean content,
non-Markdown targets, never-authored directories, non-Write/Edit tools, and
repos without the vendored checker stay silent. An `Edit` is classified with
its `new_string` spliced into the target file, so the suite also pins the
block-context cases that a fragment read in isolation gets backwards.

Run: python3 hooks/test-warn-new-line-breaks-on-edit.py hooks/warn-new-line-breaks-on-edit.py
"""
import atexit
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath("hooks/warn-new-line-breaks-on-edit.py")
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
REAL_CHECKER = os.path.join(ROOT, "scripts", "vendor", "gha-check-new-line-breaks.py")
PUSH_HOOK_SRC = os.path.join(os.path.dirname(HOOK), "warn-new-line-breaks-on-push.py")

BAD_CONTENT = "# Bad doc\n\nFirst sentence. Second sentence on the same line.\n"
CLEAN_CONTENT = "# Clean doc\n\nFirst sentence.\nSecond sentence on a new line.\n"


# The hook no longer excludes a `tmp`/`scratchpad` segment by name, but it
# does exclude `node_modules`/`.git`, and an earlier revision excluded `tmp`
# too. `tempfile.mkdtemp()` returns a path under `/tmp` on Linux (and under
# `/var/folders/...` on macOS), so fixtures placed there were scratch on CI
# and in scope locally -- the suite scored 14/14 on macOS and 11/14 on Linux
# from the same commit, with every SHOULD_WARN case short-circuiting before
# it reached the checker. Root the fixtures somewhere with no excluded
# segment regardless, so the suite measures the same thing everywhere and
# stays correct if the excluded set grows again.
FIXTURE_ROOT = tempfile.mkdtemp(prefix="nlb-edit-fixtures-", dir=os.path.expanduser("~"))
atexit.register(shutil.rmtree, FIXTURE_ROOT, ignore_errors=True)


def make_repo(with_checker=True) -> str:
    """Create a throwaway git repository, optionally vendoring the checker."""
    d = tempfile.mkdtemp(prefix="nlb-edit-test-", dir=FIXTURE_ROOT)
    subprocess.run(["git", "init", "-q", "-b", "main", d], check=True)
    if with_checker and os.path.isfile(REAL_CHECKER):
        vendor_dir = os.path.join(d, "scripts", "vendor")
        os.makedirs(vendor_dir, exist_ok=True)
        shutil.copy(REAL_CHECKER, os.path.join(vendor_dir, "gha-check-new-line-breaks.py"))
    os.makedirs(os.path.join(d, "docs"), exist_ok=True)
    os.makedirs(os.path.join(d, "tmp"), exist_ok=True)
    os.makedirs(os.path.join(d, "node_modules"), exist_ok=True)
    return d


REPO_WITH_CHECKER = make_repo(with_checker=True)
REPO_NO_CHECKER = make_repo(with_checker=False)

# Self-check, not a style assertion. If the fixture root ever lands somewhere
# the hook classifies as scratch, every SHOULD_WARN case silently passes
# through the skip branch and the suite reports success while measuring
# nothing -- which is exactly how this shipped. Fail here instead, where the
# message says what happened.
_spec = importlib.util.spec_from_file_location("_nlb_edit_hook_under_test", HOOK)
_HOOK_MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_HOOK_MOD)

if _HOOK_MOD.RX_EXCLUDED_PATH.search(os.path.join(REPO_WITH_CHECKER, "docs", "x.md")):
    raise SystemExit(
        "fixture root is path-excluded by the hook under test "
        f"({REPO_WITH_CHECKER}); the suite would pass without exercising "
        "anything. Re-root FIXTURE_ROOT away from node_modules/.git."
    )


def run_hook(payload, cwd=REPO_WITH_CHECKER, hook_path=HOOK):
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {payload!r}\n{proc.stderr.strip()}")
    if not proc.stdout.strip():
        return "silent", None
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: hook emitted non-JSON on stdout ({exc}): {proc.stdout!r}")
    hso = out.get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        sys.exit(f"FATAL: hook emitted permissionDecision={hso['permissionDecision']!r}; must only warn")
    verdict = "WARN" if hso.get("additionalContext") else "silent"
    return verdict, out


def write_payload(path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def seed(path, body):
    """Write `body` to `path` so an Edit has something to splice into."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)
    return path


def edit_payload(path, new_string, old_string="REPLACE_ME"):
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": path,
            "old_string": old_string,
            "new_string": new_string,
        },
    }


# Block-context fixtures. The hook splices `new_string` over `old_string` in
# the file and classifies the RESULT, so each of these pins a case that
# classifying the fragment alone gets backwards (ai-config#3690 review).
FENCED_DOC = seed(
    os.path.join(REPO_WITH_CHECKER, "docs", "fenced.md"),
    "# Fenced doc\n\n```sh\necho one\nREPLACE_ME\n```\n\nTrailing prose.\n",
)
PROSE_DOC = seed(
    os.path.join(REPO_WITH_CHECKER, "docs", "prose.md"),
    "# Prose doc\n\nOpening line.\nREPLACE_ME\nClosing line.\n",
)
EDIT_DOC = seed(
    os.path.join(REPO_WITH_CHECKER, "docs", "bad.md"),
    "# Bad doc\n\nREPLACE_ME\n",
)


SHOULD_WARN = [
    ("W1", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "bad.md"), BAD_CONTENT),
     REPO_WITH_CHECKER, "Write with a multi-sentence line warns"),
    ("W2", edit_payload(EDIT_DOC, BAD_CONTENT),
     REPO_WITH_CHECKER, "Edit's new_string with a multi-sentence line warns"),
    ("W3", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "BAD.MARKDOWN"), BAD_CONTENT),
     REPO_WITH_CHECKER, ".MARKDOWN extension (case-insensitive) warns"),
    # A worktree under a session scratchpad is a full checkout; excluding a
    # `tmp`/`scratchpad` segment by name silenced the hook on it while the
    # push-time sibling still warned on the identical content.
    ("W4", write_payload(os.path.join(REPO_WITH_CHECKER, "tmp", "bad.md"), BAD_CONTENT),
     REPO_WITH_CHECKER, "a tmp/ path inside a checker-vendoring repo warns"),
    # Fragment-only classification read the leading fence as OPENING a code
    # block and skipped every line after it.
    ("W5", edit_payload(FENCED_DOC, "```\n\nFirst sentence. Second sentence on the same line.\n"),
     REPO_WITH_CHECKER, "new_string closing a fence then writing prose warns"),
]

SHOULD_STAY_SILENT = [
    ("S1", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "clean.md"), CLEAN_CONTENT),
     REPO_WITH_CHECKER, "clean content stays silent"),
    ("S2", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "bad.py"), BAD_CONTENT),
     REPO_WITH_CHECKER, "non-Markdown extension stays silent"),
    ("S3", write_payload(os.path.join(REPO_WITH_CHECKER, "node_modules", "bad.md"), BAD_CONTENT),
     REPO_WITH_CHECKER, "node_modules/ path stays silent"),
    ("S4", write_payload(os.path.join(REPO_NO_CHECKER, "docs", "bad.md"), BAD_CONTENT),
     REPO_NO_CHECKER, "repo without vendored checker stays silent"),
    ("S5", {"tool_name": "Read", "tool_input": {"file_path": os.path.join(REPO_WITH_CHECKER, "docs", "bad.md")}},
     REPO_WITH_CHECKER, "non-Write/Edit tool stays silent"),
    ("S6", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "empty.md"), ""),
     REPO_WITH_CHECKER, "empty content stays silent"),
    ("S7", write_payload("/not/a/git/repo/bad.md", BAD_CONTENT),
     tempfile.gettempdir(), "path outside any git repo stays silent"),
    # Fragment-only classification read this as prose and warned about a
    # line CI will never flag, because the enclosing fence is in the file.
    ("S8", edit_payload(FENCED_DOC, "echo hello. echo goodbye on the same line and this is long."),
     REPO_WITH_CHECKER, "new_string inside an existing fence stays silent"),
    # No splice is possible, so classify nothing rather than guess.
    ("S9", edit_payload(PROSE_DOC, BAD_CONTENT, old_string="NOT_IN_THE_FILE"),
     REPO_WITH_CHECKER, "Edit whose old_string is absent stays silent"),
    # The violation is already on disk, outside the edited region.
    ("S10", edit_payload(
        seed(os.path.join(REPO_WITH_CHECKER, "docs", "preexisting.md"),
             "# Doc\n\nOld line one. Old line two on the same line.\nREPLACE_ME\n"),
        "A single clean sentence."),
     REPO_WITH_CHECKER, "a pre-existing violation outside the edit stays silent"),
]

NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Write", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Write"}, "absent tool_input"),
    ({"tool_input": {"file_path": "a.md", "content": "x"}}, "absent tool_name"),
    ({"tool_name": "Write", "tool_input": {"file_path": "a.md", "content": 12345}}, "content is not a string"),
]


def test_main():
    wrong = 0
    print("should WARN:")
    for case_id, payload, cwd, desc in SHOULD_WARN:
        got, out = run_hook(payload, cwd=cwd)
        is_ok = got == "WARN"
        if is_ok and out:
            ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
            if "sentence" not in ctx:
                is_ok = False
        wrong += not is_ok
        print(f"  {got:<6} {case_id:<4} {desc}")

    print("\nshould STAY SILENT:")
    for case_id, payload, cwd, desc in SHOULD_STAY_SILENT:
        got, _ = run_hook(payload, cwd=cwd)
        wrong += got != "silent"
        print(f"  {got:<6} {case_id:<4} {desc}")

    print("\nnon-command payloads (must fail open silently):")
    for payload, desc in NON_COMMAND_PAYLOADS:
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=REPO_WITH_CHECKER,
        )
        got = "silent" if proc.returncode == 0 and not proc.stdout.strip() else "WARN"
        wrong += got != "silent"
        print(f"  {got:<6} {desc}")

    total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT) + len(NON_COMMAND_PAYLOADS)
    print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
    return wrong


# ------------------------------------------------------------ mutation harness

MUTATIONS = {
    "M1_write_tool_names": (
        "WRITE_TOOL_NAMES must include Write/Edit",
        [('WRITE_TOOL_NAMES = (\n    "Write", "Edit", "write_to_file", "replace_file_content", "apply_diff",\n)',
          'WRITE_TOOL_NAMES = ()')],
        {"W1", "W2", "W3", "W4", "W5"},
    ),
    "M2_md_extension_gate": (
        "the Markdown extension gate must actually match .md/.markdown",
        [(r'RX_MD_PATH = re.compile(r"\.(?:md|markdown)$", re.I)',
          r'RX_MD_PATH = re.compile(r"UNMATCHABLE_EXTENSION_PATTERN$", re.I)')],
        {"W1", "W2", "W3", "W4", "W5"},
    ),
    "M3_classify_call_dropped": (
        "violation detection must actually classify prose lines",
        [("        kind = checker.classify_line(content, clause_breaks, clause_min_length)\n        if kind is None:\n            continue",
          "        kind = None\n        if kind is None:\n            continue")],
        {"W1", "W2", "W3", "W4", "W5"},
    ),
    # The three above only pin the WARN cases. These pin silent ones, so a
    # regression that widens the hook is caught too (ai-config#3690 review).
    "M4_excluded_path_gate": (
        "the never-authored-directory gate must actually exclude node_modules",
        [('RX_EXCLUDED_PATH = re.compile(\n    r"(?:^|[/\\\\])(?:node_modules|\\.git)(?:[/\\\\]|$)", re.I\n)',
          'RX_EXCLUDED_PATH = re.compile(r"UNMATCHABLE_EXCLUDED_PATH")')],
        {"S3"},
    ),
    "M5_splice_dropped": (
        "an Edit must be classified with its new_string spliced into the file",
        [("    old = tool_input.get(\"old_string\") or tool_input.get(\"TargetContent\")\n    if not isinstance(old, str) or not old:",
          "    old = None\n    if not isinstance(old, str) or not old:")],
        {"W5", "S8", "S9"},
    ),
}


def test_mutations():
    with open(HOOK, encoding="utf-8") as handle:
        source = handle.read()

    print("\nmutation tests:")
    mutation_wrong = 0
    for clause, (statement, edits, expected_flips) in MUTATIONS.items():
        mutated = source
        for find, replace in edits:
            count = mutated.count(find)
            if count != 1:
                sys.exit(f"FATAL: anchor not present once in {HOOK} (found {count}):\n{find}")
            mutated = mutated.replace(find, replace)

        fd, path = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(mutated)
        # The mutated copy imports its sibling by its OWN directory, so the
        # real push hook (needed for `_git_root`/`_find_checker`) must sit
        # alongside it.
        mutated_push_hook = os.path.join(os.path.dirname(path), "warn-new-line-breaks-on-push.py")
        shutil.copy(PUSH_HOOK_SRC, mutated_push_hook)

        try:
            flipped = set()
            for case_id, payload, cwd, _ in SHOULD_WARN:
                got, _ = run_hook(payload, cwd=cwd, hook_path=path)
                if got != "WARN":
                    flipped.add(case_id)
            for case_id, payload, cwd, _ in SHOULD_STAY_SILENT:
                got, _ = run_hook(payload, cwd=cwd, hook_path=path)
                if got != "silent":
                    flipped.add(case_id)
        finally:
            os.unlink(path)
            os.unlink(mutated_push_hook)

        ok = flipped == expected_flips
        mutation_wrong += not ok
        note = f"flipped {sorted(flipped)}" if flipped else "flipped nothing"
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<24} {statement}\n         {note}")

    return mutation_wrong


if __name__ == "__main__":
    w1 = test_main()
    w2 = test_mutations()
    for d in (REPO_WITH_CHECKER, REPO_NO_CHECKER):
        shutil.rmtree(d, ignore_errors=True)
    sys.exit(1 if (w1 or w2) else 0)
