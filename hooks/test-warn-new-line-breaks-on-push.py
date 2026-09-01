#!/usr/bin/env python3
"""Test the warn-new-line-breaks-on-push guard.

Tests that a `git push` about to transfer Markdown commits carrying
new-line-breaks violations (multi-sentence lines or unseparated clauses)
surfaces a PreToolUse warning with the violating lines and remediation command,
while clean pushes, non-push commands, and repos without the checker stay silent.

Run: python3 hooks/test-warn-new-line-breaks-on-push.py hooks/warn-new-line-breaks-on-push.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath("hooks/warn-new-line-breaks-on-push.py")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_CHECKER = os.path.join(ROOT, "scripts", "vendor", "gha-check-new-line-breaks.py")
REAL_SEMBR = os.path.join(ROOT, "scripts", "semantic-line-breaks.py")

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(d, *args, env=None):
    merged = ENV if env is None else {**ENV, **env}
    return subprocess.run(
        ["git", "-C", d, *args],
        capture_output=True,
        text=True,
        env=merged,
        check=True,
    ).stdout.strip()


def make_repo(with_checker=True, with_sembr=True) -> str:
    """Create a throwaway git repository with main branch and clean initial commit."""
    d = tempfile.mkdtemp(prefix="nlb-push-test-")
    _git(d, "init", "-q", "-b", "main")

    if with_checker:
        os.makedirs(os.path.join(d, "scripts", "vendor"), exist_ok=True)
        if os.path.isfile(REAL_CHECKER):
            shutil.copy(REAL_CHECKER, os.path.join(d, "scripts", "vendor", "gha-check-new-line-breaks.py"))
        if with_sembr and os.path.isfile(REAL_SEMBR):
            shutil.copy(REAL_SEMBR, os.path.join(d, "scripts", "semantic-line-breaks.py"))

    with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Title\n\nInitial clean line.\n")

    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "Initial commit")
    return d


REPO_WITH_VIOLATION = make_repo(with_checker=True, with_sembr=True)
_git(REPO_WITH_VIOLATION, "checkout", "-q", "-b", "feat/bad-nlb")
with open(os.path.join(REPO_WITH_VIOLATION, "bad.md"), "w", encoding="utf-8") as f:
    f.write("# Bad doc\n\nFirst sentence. Second sentence on the same line.\n")
_git(REPO_WITH_VIOLATION, "add", "-A")
_git(REPO_WITH_VIOLATION, "commit", "-qm", "Add bad markdown")

REPO_WITHOUT_SEMBR = make_repo(with_checker=True, with_sembr=False)
_git(REPO_WITHOUT_SEMBR, "checkout", "-q", "-b", "feat/no-sembr")
with open(os.path.join(REPO_WITHOUT_SEMBR, "bad.md"), "w", encoding="utf-8") as f:
    f.write("# Bad doc\n\nFirst sentence. Second sentence on the same line.\n")
_git(REPO_WITHOUT_SEMBR, "add", "-A")
_git(REPO_WITHOUT_SEMBR, "commit", "-qm", "Add bad markdown without sembr script")

REPO_CLEAN = make_repo(with_checker=True, with_sembr=True)
_git(REPO_CLEAN, "checkout", "-q", "-b", "feat/clean-nlb")
with open(os.path.join(REPO_CLEAN, "clean.md"), "w", encoding="utf-8") as f:
    f.write("# Clean doc\n\nFirst sentence.\nSecond sentence on a new line.\n")
_git(REPO_CLEAN, "add", "-A")
_git(REPO_CLEAN, "commit", "-qm", "Add clean markdown")

REPO_NO_CHECKER = make_repo(with_checker=False, with_sembr=False)
_git(REPO_NO_CHECKER, "checkout", "-q", "-b", "feat/no-checker")
with open(os.path.join(REPO_NO_CHECKER, "bad.md"), "w", encoding="utf-8") as f:
    f.write("# Bad doc\n\nFirst sentence. Second sentence on the same line.\n")
_git(REPO_NO_CHECKER, "add", "-A")
_git(REPO_NO_CHECKER, "commit", "-qm", "Add bad markdown without checker")


def run_hook(command, cwd=REPO_WITH_VIOLATION, hook_path=HOOK, extra_env=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    env = {**os.environ, **(extra_env or {})}
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {command!r}\n{proc.stderr.strip()}")
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


SHOULD_WARN = [
    ("W1", f"git -C {REPO_WITH_VIOLATION} push origin feat/bad-nlb", REPO_WITH_VIOLATION,
     "push with new-line-breaks violation warns and recommends sembr script"),
    ("W2", "git push origin feat/bad-nlb", REPO_WITH_VIOLATION,
     "bare push in dirty branch warns"),
    ("W3", f"cd {REPO_WITH_VIOLATION} && git push origin feat/bad-nlb", ROOT,
     "cd followed by push in bad repo warns"),
    ("W4", f"env git -C {REPO_WITH_VIOLATION} push origin feat/bad-nlb", ROOT,
     "env wrapped git push warns"),
    ("W5", f"git -C {REPO_WITHOUT_SEMBR} push origin feat/no-sembr", REPO_WITHOUT_SEMBR,
     "push in repo without sembr reformatter warns with manual advice"),
]

SHOULD_STAY_SILENT = [
    ("S1", f"git -C {REPO_CLEAN} push origin feat/clean-nlb", REPO_CLEAN,
     "clean push without violations stays silent"),
    ("S2", f"git -C {REPO_WITH_VIOLATION} push --dry-run origin feat/bad-nlb", REPO_WITH_VIOLATION,
     "--dry-run push transfers nothing and stays silent"),
    ("S3", f"git -C {REPO_WITH_VIOLATION} push --delete origin feat/bad-nlb", REPO_WITH_VIOLATION,
     "--delete push stays silent"),
    ("S4", f"git -C {REPO_NO_CHECKER} push origin feat/no-checker", REPO_NO_CHECKER,
     "push in repo without checker script stays silent"),
    ("S5", f"git -C {REPO_WITH_VIOLATION} status", REPO_WITH_VIOLATION,
     "git status command stays silent"),
    ("S6", f"git -C {REPO_WITH_VIOLATION} commit -m 'git push'", REPO_WITH_VIOLATION,
     "git commit mentioning push stays silent"),
    ("S7", "echo 'git push origin main'", REPO_WITH_VIOLATION,
     "echo command stays silent"),
]

NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Bash", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Bash"}, "absent tool_input"),
    ({"tool_name": "Bash", "tool_input": {"command": 12345}}, "command is not string"),
    ({"tool_name": "Edit", "tool_input": {"file_path": "a.md"}}, "non-Bash tool"),
]


def test_main():
    wrong = 0
    print("should WARN:")
    for case_id, command, cwd, desc in SHOULD_WARN:
        got, out = run_hook(command, cwd=cwd)
        is_ok = got == "WARN"
        if is_ok and out:
            hso = out.get("hookSpecificOutput", {})
            ctx = hso.get("additionalContext", "")
            if case_id == "W5":
                if "semantic-line-breaks.py" in ctx or "break long lines" not in ctx:
                    is_ok = False
            else:
                if "bad.md" not in ctx or "semantic-line-breaks.py" not in ctx:
                    is_ok = False
        wrong += not is_ok
        print(f"  {got:<6} {case_id:<4} {desc}")

    print("\nshould STAY SILENT:")
    for case_id, command, cwd, desc in SHOULD_STAY_SILENT:
        got, _ = run_hook(command, cwd=cwd)
        wrong += got != "silent"
        print(f"  {got:<6} {case_id:<4} {desc}")

    print("\nnon-command payloads (must fail open silently):")
    for payload, desc in NON_COMMAND_PAYLOADS:
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=REPO_WITH_VIOLATION,
        )
        got = "silent" if proc.returncode == 0 and not proc.stdout.strip() else "WARN"
        wrong += got != "silent"
        print(f"  {got:<6} {desc}")

    total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT) + len(NON_COMMAND_PAYLOADS)
    print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
    return wrong


# ------------------------------------------------------------ mutation harness

MUTATIONS = {
    "M1_checker_candidates": (
        "checker candidates list must not be empty",
        [('CHECKER_CANDIDATES = (\n    os.path.join("scripts", "vendor", "gha-check-new-line-breaks.py"),\n    os.path.join("scripts", "check-new-line-breaks.py"),\n)',
          'CHECKER_CANDIDATES = ()')],
        {"W1", "W2", "W3", "W4", "W5"},
    ),
    "M2_base_ref_gate": (
        "resolving base ref is required for diff-scoped check",
        [('        base_ref = _resolve_base_ref(git_root)\n        if not base_ref:\n            continue',
          '        base_ref = None\n        if not base_ref:\n            continue')],
        {"W1", "W2", "W3", "W4", "W5"},
    ),
    "M3_error_line_parse": (
        "error line parser must match checker error format",
        [(r'r"^::error file=(?P<path>[^,]+),line=(?P<line>\d+)::(?P<msg>[^:]+):\s*(?P<preview>.*)$"',
          r'r"^UNMATCHABLE_ERROR_PATTERN$"')],
        {"W1", "W2", "W3", "W4", "W5"},
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

        try:
            flipped = set()
            for case_id, cmd, cwd, _ in SHOULD_WARN:
                got, _ = run_hook(cmd, cwd=cwd, hook_path=path)
                if got != "WARN":
                    flipped.add(case_id)
            for case_id, cmd, cwd, _ in SHOULD_STAY_SILENT:
                got, _ = run_hook(cmd, cwd=cwd, hook_path=path)
                if got != "silent":
                    flipped.add(case_id)
        finally:
            os.unlink(path)

        ok = flipped == expected_flips
        mutation_wrong += not ok
        note = f"flipped {sorted(flipped)}" if flipped else "flipped nothing"
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<24} {statement}\n         {note}")

    return mutation_wrong


if __name__ == "__main__":
    w1 = test_main()
    w2 = test_mutations()
    # Cleanup repos
    for d in (REPO_WITH_VIOLATION, REPO_WITHOUT_SEMBR, REPO_CLEAN, REPO_NO_CHECKER):
        shutil.rmtree(d, ignore_errors=True)
    sys.exit(1 if (w1 or w2) else 0)
