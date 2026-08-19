import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def run(text, tmpdir=None, raw_lines=None):
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        if raw_lines is not None:
            for l in raw_lines:
                f.write(l + "\n")
        else:
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
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return '"decision": "block"' in res.stdout


cases = [
    ("Completed the checks.", True),
    ("Completed the checks.\n\n**Stopping Point**: Clean stopping point reached.", False),
    ("Completed the task.\n\n- **Stopping Point**: Clean stopping point reached.", False),
    ("Indented list:\n  - **Stopping Point**: Clean stopping point reached.", False),
    ("Colon inside bold:\n**Stopping Point:** Clean stopping point reached.", False),
    ("### Stopping Point: Clean stopping point reached.", False),
    ("**Stopping Point**: Not a clean stopping point / work remains queued: finish X.", False),
    ("**Stopping Point**: Not clean --- CI is still running.", False),
    ("This PR adds a hook that requires text like `**Stopping Point**: Clean stopping point reached` in every final reply.", True),
    ("Discussion of rule:\n```\n**Stopping Point**: Clean stopping point reached\n```\nStill working on task.", True),
    ("Discussion of rule:\n```markdown\n**Stopping Point**: Clean stopping point reached\n```\nDone with task.\n\n**Stopping Point**: Clean stopping point reached.", False),
    ("**Stopping Point**: Cleanup pending, more work needed.", True),
    ("To open a fence type ``` on its own line.\n\n**Stopping Point**: Clean stopping point reached\n\n```\ncode\n```", False),
    ("Don't write a bare declaration like this:\n```\n**Stopping Point**: Clean stopping point reached\n```\nI have not actually finished; more work remains.\n\nAlso, here's a separate unrelated snippet I was about to show:\n```\n", True),
    ("```\n**Stopping Point**: Clean stopping point reached\n```\n```\n", True),
]

failed = 0
for text, expected in cases:
    got = run(text)
    status = "PASS" if got == expected else "FAIL"
    print(status, repr(text.splitlines()[0]))
    if got != expected:
        failed += 1

# Test per-line transcript error resilience (blank/malformed lines before assistant reply)
raw = [
    "",
    "malformed json {",
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Completed the checks. No declaration here."}]}}),
]
got_resilient = run("", raw_lines=raw)
if not got_resilient:
    print("FAIL per-line transcript resilience (did not block when declaration was missing)")
    failed += 1
else:
    print("PASS per-line transcript resilience on malformed lines")

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
