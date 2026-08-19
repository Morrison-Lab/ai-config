import json, os, subprocess, sys, tempfile
HOOK = sys.argv[1]
def run(text):
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f: f.write(json.dumps({"type":"assistant","message":{"content":[{"type":"text","text":text}]}})+"\n")
    out = subprocess.run([sys.executable, HOOK], input=json.dumps({"transcript_path":path}), text=True, capture_output=True, env=dict(os.environ, TMPDIR=tempfile.mkdtemp())).stdout
    os.unlink(path); return '"decision": "block"' in out
cases = [("Completed the checks.", True), ("Completed the checks.\n\n**Stopping Point**: Clean stopping point reached.", False), ("**Stopping Point**: Not clean — CI is still running.", False)]
failed = 0
for text, expected in cases:
    got = run(text); print("PASS" if got == expected else "FAIL", text.splitlines()[0]); failed += got != expected
raise SystemExit(bool(failed))
