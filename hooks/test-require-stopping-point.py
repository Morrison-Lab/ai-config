import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def run(text, tmpdir=None):
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        f.write(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": text}]},
                }
            )
            + "\n"
        )
    env = dict(os.environ, TMPDIR=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=env,
    )
    os.unlink(path)
    return '"decision": "block"' in res.stdout


cases = [
    ("Completed the checks.", True),
    ("Completed the checks.\n\n**Stopping Point**: Clean stopping point reached.", False),
    ("Completed the task.\n\n- **Stopping Point**: Clean stopping point reached.", False),
    ("### Stopping Point: Clean stopping point reached.", False),
    ("**Stopping Point**: Not a clean stopping point / work remains queued: finish X.", False),
    ("**Stopping Point**: Not clean — CI is still running.", False),
    ("This PR adds a hook that requires text like `**Stopping Point**: Clean stopping point reached` in every final reply.", True),
    ("Discussion of rule:\n```\n**Stopping Point**: Clean stopping point reached\n```\nStill working on task.", True),
]

failed = 0
for text, expected in cases:
    got = run(text)
    status = "PASS" if got == expected else "FAIL"
    print(status, repr(text.splitlines()[0]))
    if got != expected:
        failed += 1

# Test fail-safe / sentinel retry on identical text
tmp = tempfile.mkdtemp()
blocked_first = run("Missing stopping point.", tmpdir=tmp)
blocked_second = run("Missing stopping point.", tmpdir=tmp)
if not (blocked_first is True and blocked_second is False):
    print("FAIL sentinel retry behavior")
    failed += 1
else:
    print("PASS sentinel retry allows next attempt")

raise SystemExit(bool(failed))
