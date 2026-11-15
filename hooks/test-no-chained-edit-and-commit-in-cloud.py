#!/usr/bin/env python3
"""Tests for hooks/no-chained-edit-and-commit-in-cloud.py (ai-config#5688).

Run: python3 hooks/test-no-chained-edit-and-commit-in-cloud.py [hooks/no-chained-edit-and-commit-in-cloud.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-chained-edit-and-commit-in-cloud.py")

# (command, denied in a cloud session)
CASES = [
    ("sed -i s/a/b/ f.qmd && git commit -qm x", True),
    ("sed -i.bak s/a/b/ f.qmd; git commit -am x", True),
    ("sed -Ei s/a/b/ f.qmd && git add f.qmd && git commit -m x", True),
    ("sed --in-place=.bak s/a/b/ f && git commit -m x", True),
    ("perl -pi -e s/a/b/ f.qmd && git -C repo commit -F msg", True),
    ("echo x >> notes.md && git commit -am x", True),
    ("cat > f.qmd <<'EOF'\nbody\nEOF\ngit commit -am x", True),
    ("printf x >f.md\ngit commit -m x", True),
    ('bash -c "sed -i s/a/b/ f && git commit -m x"', True),
    ("sed -i s/a/b/ f && bash -c 'git commit -m x'", True),
    ("sed -i s/a/b/ f && git -c user.name=x commit -m x", True),
    ("sudo sed -i s/a/b/ f; git commit -m x", True),
    # either half alone passes
    ("sed -i s/a/b/ f.qmd", False),
    ("git commit -m x", False),
    ("git add f && git commit -m x && git push", False),
    # temp-file redirects pass
    ("echo msg > /tmp/m && git commit -F /tmp/m", False),
    ("cat > /tmp/claude-0/x/scratchpad/msg.txt <<EOF\nm\nEOF\ngit commit -F /tmp/claude-0/x/scratchpad/msg.txt", False),
    ("make 2>&1 >/dev/null; git commit -m x", False),
    # not an in-place edit
    ("sed -n 1,5p f && git commit -m x", False),
    ("sed -e s/a/b/ f | grep x; git commit -m x", False),
    ("git log --format=%s > /dev/null && git commit -m x", False),
    ("git commit -m 'sed -i s/a/b/ f'", False),
    ('echo "sed -i x f && git commit"', False),
    ("grep -n 'sed -i' f && git commit -m x", False),
    # not a commit
    ("sed -i s/a/b/ f && git status", False),
    ("sed -i s/a/b/ f && git log --grep commit", False),
    # override
    ("ALLOW_CHAINED_EDIT_COMMIT=1 sed -i s/a/b/ f && git commit -m x", False),
    ("sed -i s/a/b/ f && ALLOW_CHAINED_EDIT_COMMIT=1 git commit -m x", False),
    ("sed -i s/a/b/ f && git commit -m x # ALLOW_CHAINED_EDIT_COMMIT=1", True),
    ("echo ALLOW_CHAINED_EDIT_COMMIT=1; sed -i s/a/b/ f && git commit -m x", True),
]


def run(command, remote="true"):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_REMOTE", None)
    if remote is not None:
        env["CLAUDE_CODE_REMOTE"] = remote
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    return p.returncode, '"permissionDecision": "deny"' in p.stdout


def main():
    fails = 0
    denies = 0
    for command, want in CASES:
        rc, denied = run(command)
        denies += denied
        ok = rc == 0 and denied == want
        fails += 0 if ok else 1
        print(f"  {'ok' if ok else 'FAIL':<6} {'deny' if denied else 'allow':<6} {command!r}")
    chained = "sed -i s/a/b/ f && git commit -m x"
    extra = [
        ("silent outside a cloud session", run(chained, remote=None), (0, False)),
        ("silent when CLAUDE_CODE_REMOTE is false", run(chained, remote="false"), (0, False)),
    ]
    for desc, got, want in extra:
        ok = got == want
        fails += 0 if ok else 1
        print(f"  {'ok' if ok else 'FAIL':<6} {desc}")
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True,
                       env=dict(os.environ, CLAUDE_CODE_REMOTE="true"))
    ok = p.returncode == 0 and not p.stdout
    fails += 0 if ok else 1
    print(f"  {'ok' if ok else 'FAIL':<6} fails open on garbage stdin")
    # Vacuous-pass guard: a hook that never denies would pass every False case.
    want_denies = sum(1 for _c, w in CASES if w)
    ok = want_denies > 0 and denies == want_denies
    fails += 0 if ok else 1
    print(f"  {'ok' if ok else 'FAIL':<6} denied {denies} of the {want_denies} cases that must deny")
    total = len(CASES) + len(extra) + 2
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
