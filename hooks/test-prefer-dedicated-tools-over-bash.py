#!/usr/bin/env python3
"""Tests for hooks/prefer-dedicated-tools-over-bash.py (ai-config#6065).

Run: python3 hooks/test-prefer-dedicated-tools-over-bash.py [hooks/prefer-dedicated-tools-over-bash.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "prefer-dedicated-tools-over-bash.py")

# (command, denied)
CASES = [
    # readers -> Read
    ("cat README.md", True),
    ("cat a.md b.md", True),
    ("head -n 40 hooks/x.py", True),
    ("head -40 hooks/x.py", True),
    ("tail -n 20 log.txt", True),
    ("sed -n '10,40p' AGENTS.md", True),
    ("sed -n 5p f.txt", True),
    ("cat < f.txt", True),
    ("cd /repo && cat f.txt", True),
    ("git status; head f.txt", True),
    ("(cat f.txt)", True),
    ("FOO=1 cat f.txt", True),
    ("cat f.txt 2>/dev/null", True),
    ("cat f.txt | head -5", True),
    # searchers -> Grep / Glob
    ("grep -rn 'foo' hooks/", True),
    ("rg -n 'a|b' scripts", True),
    ("grep -n x f.txt | head -20", True),
    ("rg --files | grep hook", True),
    ("find . -name '*.py'", True),
    ("find hooks -type f -name 'test-*'", True),
    # in-place edits -> Edit
    ("sed -i 's/a/b/' f.txt", True),
    ("sed -i.bak -e 's/a/b/' f.txt", True),
    ("sed -Ei 's/a/b/' f.txt", True),
    ("sed --in-place 's/a/b/' f.txt", True),
    ("perl -pi -e 's/a/b/' f.txt", True),
    ("perl -i -pe 's/a/b/' f.txt", True),
    ("git diff | sed -i 's/a/b/' f.txt", True),
    # writes -> Write
    ("cat > out.md <<'EOF'\nhello\nEOF", True),
    ("cat >> out.md <<EOF\nhello\nEOF", True),
    ("echo hello > out.txt", True),
    ("printf 'a\\n' >> out.txt", True),
    ("tee out.md <<'EOF'\nx\nEOF", True),
    ("echo hi | tee out.txt", True),
    # passes: no exact tool, or Bash is needed
    ("git log --oneline | head -5", False),
    ("git diff origin/main | grep '^+'", False),
    ("ls hooks", False),
    ("wc -l f.txt", False),
    ("cat -A f.txt", False),
    ("cat f.txt | python3 parse.py", False),
    ("head -c 100 f.bin", False),
    ("tail -f log.txt", False),
    ("grep x f.txt > hits.txt", False),
    ("grep -c x <<< \"$VAR\"", False),
    ("cat \"$f\"", False),
    ("for f in a b; do cat \"$f\"; done", False),
    ("if grep -q x f.txt; then echo y; fi", False),
    ("sudo cat /etc/shadow", False),
    ("x=$(cat f.txt) && echo ok", False),
    ('git commit -m "$(cat msg.txt)"', False),
    ("sed 's/a/b/' f.txt", False),
    ("sed -n '/re/p' f.txt", False),
    ("find . -mtime -1 -name '*.log'", False),
    ("find . -name '*.tmp' -delete", False),
    ("find . -type d -name x", False),
    ("echo hello", False),
    ("echo x > /dev/null", False),
    ("echo x >&2", False),
    ("echo \"$X\" > f.txt", False),
    ("cat a b > c", False),
    ("python3 tools/check.py > out.txt", False),
    ("git commit -F - <<'EOF'\ncat f.txt\nEOF", False),
    ('echo "cat f.txt"', False),
    ("ALLOW_BASH_OVER_TOOL=1 sed -i 's/a/b/' *.md", False),
    ("ALLOW_BASH_OVER_TOOL=1 cat f.txt", False),
    ("cat f.txt # ALLOW_BASH_OVER_TOOL=1", True),
    ("echo ALLOW_BASH_OVER_TOOL=1; cat f.txt", True),
    ("sed -i \"s/$A/b/\" f.txt", False),
]


def run(command):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
    out = json.loads(p.stdout) if p.stdout.strip() else {}
    decision = out.get("hookSpecificOutput", {}).get("permissionDecision")
    return p.returncode, decision == "deny"


def main():
    fails = 0
    for command, want in CASES:
        rc, denied = run(command)
        ok = rc == 0 and denied == want
        fails += 0 if ok else 1
        print(f"  {'ok' if ok else 'FAIL':<6} {'deny' if denied else 'pass':<6} {command!r}")
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    fails += 0 if ok else 1
    print(f"  {'ok' if ok else 'FAIL':<6} fails open on garbage stdin")
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
