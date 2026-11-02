"""Test the flag-tool-gap-handling guard.

Run: python3 hooks/test-flag-tool-gap-handling.py hooks/flag-tool-gap-handling.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def bash(cmd):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}


def user(text):
    return {"type": "user", "message": {"content": text}}


RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "content": "ok"}]}}

CASES = [
    ([say("I skipped the render because the cloud toolchain lacks R's "
          "reticulate.")], "missing tool", "skip-because-missing warns"),
    ([say("The PDF could not be built: tinytex is not installed here.")],
     "missing tool", "could-not plus not-installed warns"),
    ([say("Rendering was skipped; Julia isn't installed.")], "missing tool",
     "skipped then missing, either order, warns"),
    ([say("Julia was missing, so I installed it and re-ran the render.")],
     None, "an excuse that was fixed in the same sentence stays silent"),
    ([say("Rendered both pages; no warnings.")], None, "plain report is silent"),
    ([user("go"), bash("Rscript -e 'install.packages(\"reticulate\")'"), RESULT,
      say("Rendered the chapter.")], "startup script",
     "an install with no startup-script mention warns"),
    ([user("go"), bash("uv pip install matplotlib"), RESULT,
      say("Rendered. Matplotlib is worth adding to the cloud startup script: "
          "`uv pip install matplotlib`.")], None,
     "an install reported with the startup script stays silent"),
    ([bash("pip install old"), RESULT, user("next task"),
      say("Done.")], None, "an install before the last user prompt is ignored"),
    ([user("go"), bash("git status"), RESULT, say("Clean.")], None,
     "no install, no excuse: silent"),
]

fails = 0
for lines, expect, name in CASES:
    with tempfile.TemporaryDirectory() as d:
        tp = os.path.join(d, "t.jsonl")
        with open(tp, "w") as fh:
            fh.write("\n".join(json.dumps(x) for x in lines) + "\n")
        env = dict(os.environ, TMPDIR=d)
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(
            {"transcript_path": tp, "session_id": "t" + name}), text=True,
            capture_output=True, env=env)
    out = p.stdout + p.stderr
    fired = bool(out.strip())
    ok = fired == (expect is not None) and (expect is None or expect in out)
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1
        print("   output:", out[:300])
sys.exit(1 if fails else 0)
