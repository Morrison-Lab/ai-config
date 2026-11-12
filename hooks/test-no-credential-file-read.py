#!/usr/bin/env python3
"""Regression tests for no-credential-file-read.py (ai-config#4780)."""
import json
import os
import subprocess
import sys
import tempfile

SUBJECT = sys.argv[1]
HOME = tempfile.mkdtemp()
ENV = dict(os.environ, HOME=HOME)


def run(tool, inp):
    payload = json.dumps({"tool_name": tool, "tool_input": inp, "cwd": HOME})
    proc = subprocess.run([sys.executable, SUBJECT], input=payload,
                          capture_output=True, text=True, env=ENV, check=False)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.strip() and json.loads(proc.stdout)
    return out and out["hookSpecificOutput"]["permissionDecision"] or None


DENIED = [
    "cat ~/.config/canvas/token",
    "sed 's/token: .*/token: REDACTED/' ~/.config/canvas/token",
    "cat $HOME/.netrc",
    "head -n 3 ~/.config/gh/hosts.yml | tail -1",
    "cd /tmp && grep login ~/.netrc",
    "cat .netrc",  # relative to cwd, which is HOME here
    "base64 ~/.ssh/id_ed25519",
    "FOO=1 cat ~/.aws/credentials",
    "(cat ~/.git-credentials)",
    "echo $(cat ~/.netrc)",
    "echo `cat ~/.netrc`",
    'printf "%s" "$(cat ~/.config/canvas/token)"',
    "echo ALLOW_CREDENTIAL_READ=1; cat ~/.netrc",
    "cat $XDG_CONFIG_HOME/canvas/token",
    "cat ~/.config/myapp/api_token.json",
]
ALLOWED = [
    'curl -H "Authorization: Bearer $(cat ~/.config/canvas/token)" https://x',
    "TOKEN=$(cat ~/.config/canvas/token) python3 upload.py",
    "test -s ~/.config/canvas/token && echo present",
    "cat ~/.ssh/id_ed25519.pub",
    "cat README.md",
    "ls -l ~/.config/canvas/",
    "ALLOW_CREDENTIAL_READ=1 cat ~/.netrc",
    "echo 'cat ~/.netrc is forbidden'",
    "cat ~/.config/nvim/tokenize.lua",
    "cat ~/.config/myapp/secret.py",
    "grep .netrc notes.md",  # a search pattern, not a path
]

for c in DENIED:
    assert run("Bash", {"command": c}) == "deny", f"not denied: {c}"
for c in ALLOWED:
    assert run("Bash", {"command": c}) is None, f"wrongly denied: {c}"

home_token = os.path.join(HOME, ".config", "canvas", "token")
assert run("Read", {"file_path": home_token}) == "deny"
assert run("Read", {"file_path": os.path.join(HOME, "notes.md")}) is None
assert run("Write", {"file_path": home_token, "content": "x"}) is None

proc = subprocess.run([sys.executable, SUBJECT], input="not json",
                      capture_output=True, text=True, env=ENV, check=False)
assert proc.returncode == 0 and not proc.stdout.strip()

print(f"PASS: {len(DENIED)} denied, {len(ALLOWED)} allowed, Read, bad input")
