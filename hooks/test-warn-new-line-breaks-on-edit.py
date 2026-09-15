#!/usr/bin/env python3
"""Test the warn-new-line-breaks-on-edit guard.

Tests that a `Write`/`Edit` about to place Markdown content on disk with a
new-line-breaks violation (a multi-sentence or unseparated-clause line)
surfaces a PreToolUse warning before the tool runs, while clean content,
non-Markdown targets, scratch paths, non-Write/Edit tools, and repos without
the vendored checker stay silent.

Run: python3 hooks/test-warn-new-line-breaks-on-edit.py hooks/warn-new-line-breaks-on-edit.py
"""
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


def make_repo(with_checker=True) -> str:
    """Create a throwaway git repository, optionally vendoring the checker."""
    d = tempfile.mkdtemp(prefix="nlb-edit-test-")
    subprocess.run(["git", "init", "-q", "-b", "main", d], check=True)
    if with_checker and os.path.isfile(REAL_CHECKER):
        vendor_dir = os.path.join(d, "scripts", "vendor")
        os.makedirs(vendor_dir, exist_ok=True)
        shutil.copy(REAL_CHECKER, os.path.join(vendor_dir, "gha-check-new-line-breaks.py"))
    os.makedirs(os.path.join(d, "docs"), exist_ok=True)
    os.makedirs(os.path.join(d, "tmp"), exist_ok=True)
    return d


REPO_WITH_CHECKER = make_repo(with_checker=True)
REPO_NO_CHECKER = make_repo(with_checker=False)


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


def edit_payload(path, new_string):
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": path, "old_string": "old", "new_string": new_string},
    }


SHOULD_WARN = [
    ("W1", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "bad.md"), BAD_CONTENT),
     REPO_WITH_CHECKER, "Write with a multi-sentence line warns"),
    ("W2", edit_payload(os.path.join(REPO_WITH_CHECKER, "docs", "bad.md"), BAD_CONTENT),
     REPO_WITH_CHECKER, "Edit's new_string with a multi-sentence line warns"),
    ("W3", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "BAD.MARKDOWN"), BAD_CONTENT),
     REPO_WITH_CHECKER, ".MARKDOWN extension (case-insensitive) warns"),
]

SHOULD_STAY_SILENT = [
    ("S1", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "clean.md"), CLEAN_CONTENT),
     REPO_WITH_CHECKER, "clean content stays silent"),
    ("S2", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "bad.py"), BAD_CONTENT),
     REPO_WITH_CHECKER, "non-Markdown extension stays silent"),
    ("S3", write_payload(os.path.join(REPO_WITH_CHECKER, "tmp", "bad.md"), BAD_CONTENT),
     REPO_WITH_CHECKER, "scratch (tmp/) path stays silent"),
    ("S4", write_payload(os.path.join(REPO_NO_CHECKER, "docs", "bad.md"), BAD_CONTENT),
     REPO_NO_CHECKER, "repo without vendored checker stays silent"),
    ("S5", {"tool_name": "Read", "tool_input": {"file_path": os.path.join(REPO_WITH_CHECKER, "docs", "bad.md")}},
     REPO_WITH_CHECKER, "non-Write/Edit tool stays silent"),
    ("S6", write_payload(os.path.join(REPO_WITH_CHECKER, "docs", "empty.md"), ""),
     REPO_WITH_CHECKER, "empty content stays silent"),
    ("S7", write_payload("/not/a/git/repo/bad.md", BAD_CONTENT),
     tempfile.gettempdir(), "path outside any git repo stays silent"),
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
        {"W1", "W2", "W3"},
    ),
    "M2_md_extension_gate": (
        "the Markdown extension gate must actually match .md/.markdown",
        [(r'RX_MD_PATH = re.compile(r"\.(?:md|markdown)$", re.I)',
          r'RX_MD_PATH = re.compile(r"UNMATCHABLE_EXTENSION_PATTERN$", re.I)')],
        {"W1", "W2", "W3"},
    ),
    "M3_classify_call_dropped": (
        "violation detection must actually classify prose lines",
        [("        kind = checker.classify_line(content, clause_breaks, clause_min_length)\n        if kind is None:\n            continue",
          "        kind = None\n        if kind is None:\n            continue")],
        {"W1", "W2", "W3"},
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
