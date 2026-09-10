#!/usr/bin/env python3
"""Test the warn-generated-file-stale guard.

Builds a throwaway git repo carrying a fake source/generated pair and a
generator with a --check mode, so the test exercises the real subprocess and
diff paths rather than a mocked stand-in.

Run: python3 hooks/test-warn-generated-file-stale.py hooks/warn-generated-file-stale.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1])

GENERATOR = '''#!/usr/bin/env python3
import sys
src = open("src.json").read()
out = open("out.json").read() if __import__("os").path.exists("out.json") else ""
if "--check" in sys.argv:
    sys.exit(0 if src == out else 1)
open("out.json", "w").write(src)
'''


def build_repo(source_edited, regenerated, only_output_edited=False):
    d = tempfile.mkdtemp()
    run = lambda *a: subprocess.run(a, cwd=d, capture_output=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    os.makedirs(os.path.join(d, "scripts"), exist_ok=True)
    with open(os.path.join(d, "scripts", "gen.py"), "w") as fh:
        fh.write(GENERATOR)
    for name in ("src.json", "out.json"):
        with open(os.path.join(d, name), "w") as fh:
            fh.write('{"a": 1}')
    run("git", "add", "-A")
    run("git", "commit", "-qm", "base")
    run("git", "branch", "-q", "feature")
    run("git", "checkout", "-q", "feature")
    if only_output_edited:
        # The generated file drifts without its source being touched, so
        # --check fails while this push changes nothing that caused it.
        with open(os.path.join(d, "out.json"), "w") as fh:
            fh.write('{"a": 99}')
        run("git", "add", "-A")
        run("git", "commit", "-qm", "drift")
        return d
    if source_edited:
        with open(os.path.join(d, "src.json"), "w") as fh:
            fh.write('{"a": 2}')
        if regenerated:
            with open(os.path.join(d, "out.json"), "w") as fh:
                fh.write('{"a": 2}')
        run("git", "add", "-A")
        run("git", "commit", "-qm", "edit")
    return d


def warned(d, command):
    env = dict(os.environ)
    patched = open(HOOK).read().replace(
        '("hooks/hooks.json", ["python3", "scripts/gen-hooks-plugin.py", "--check"]),',
        '("src.json", ["python3", "scripts/gen.py", "--check"]),',
    ).replace('"origin/HEAD", "origin/main"', '"main", "main"'
    ).replace('"@{upstream}", ', '')
    hook_copy = os.path.join(d, "hook.py")
    with open(hook_copy, "w") as fh:
        fh.write(patched)
    out = subprocess.run(
        [sys.executable, hook_copy],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True, text=True, cwd=d, env=env,
    ).stdout
    return "systemMessage" in out


CASES = [
    (True, False, "git push", True, "source edited, generator not run -> warns"),
    (True, True, "git push", False, "source edited and regenerated -> silent"),
    (False, False, "git push", False, "source untouched -> silent"),
    (True, False, "git status", False, "not a push -> silent"),
    # Without the "is this push's diff touching the source" check, the
    # hook would warn here about drift the push did not cause.
    ("only-output", False, "git push", False,
     "generated file stale but source untouched by this push -> silent"),
]


def main():
    passes = failures = 0
    for edited, regen, cmd, expected, label in CASES:
        if edited == "only-output":
            d = build_repo(False, False, only_output_edited=True)
        else:
            d = build_repo(edited, regen)
        got = warned(d, cmd)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected warn={expected}, got {got})")
            failures += 1
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
