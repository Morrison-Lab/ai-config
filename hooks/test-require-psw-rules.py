#!/usr/bin/env python3
"""Tests for require-psw-rules.py (ai-config#5166, #5632)."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.realpath(__file__)), "require-psw-rules.py")
PSW = "/home/u/psw/chapters/"


def run(payload, raw=None):
    proc = subprocess.run(
        [sys.executable, HOOK], input=raw if raw is not None else json.dumps(payload),
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def transcript(reads):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for name, inp in reads:
        f.write(json.dumps({"message": {"content": [
            {"type": "tool_use", "name": name, "input": inp}]}}) + "\n")
    f.close()
    return f.name


def edit(path, tp, tool="Edit"):
    return {"tool_name": tool, "tool_input": {"file_path": path}, "transcript_path": tp}


ALL = [("Read", {"file_path": PSW + "defining-terms.qmd"}),
       ("Read", {"file_path": PSW + "conciseness.qmd"}),
       ("Read", {"file_path": PSW + "grammar/relative-pronouns.qmd"})]
PAGE = "/repo/lds/chapters/_subfiles/x/_a.qmd"
fails = []


def check(label, cond):
    if not cond:
        fails.append(label)


check("deny with no reads", run(edit(PAGE, transcript([])))["hookSpecificOutput"]["permissionDecision"] == "deny")
partial = run(edit(PAGE, transcript(ALL[:2])))
check("deny names the missing chapter", "relative-pronouns" in partial["hookSpecificOutput"]["permissionDecisionReason"])
check("allow after all reads", run(edit(PAGE, transcript(ALL))) is None)
urls = [("WebFetch", {"url": "https://morrison-lab.github.io/psw/chapters/%s.html" % n})
        for n in ("defining-terms", "conciseness", "grammar/relative-pronouns")]
check("allow after WebFetch reads", run(edit(PAGE, transcript(urls))) is None)
bash = [("Bash", {"command": "cat /home/u/psw/chapters/%s.qmd" % n})
        for n in ("defining-terms", "conciseness", "grammar/relative-pronouns")]
check("allow after Bash reads", run(edit(PAGE, transcript(bash))) is None)
names = ("defining-terms", "conciseness", "grammar/relative-pronouns")
check("Edit naming the chapters does not discharge",
      run(edit(PAGE, transcript([("Edit", {"file_path": PSW + n + ".qmd"}) for n in names]))) is not None)
check("Bash rm/ls naming the chapters does not discharge",
      run(edit(PAGE, transcript([("Bash", {"command": "ls -la /home/u/psw/chapters/%s.qmd" % n})
                                 for n in names]))) is not None)
check("non-psw read does not count",
      run(edit(PAGE, transcript([("Read", {"file_path": "/x/conciseness.qmd"})]))) is not None)
check("non-page file ignored", run(edit("/repo/lds/tools/a.py", transcript([]))) is None)
check("hooks/ exempt", run(edit("/repo/hooks/chapters/a.qmd", transcript([]))) is None)
check("Read tool ignored", run({"tool_name": "Read", "tool_input": {"file_path": PAGE},
                                "transcript_path": transcript([])}) is None)
check("Write denied", run(edit(PAGE, transcript([]), "Write")) is not None)
check("missing transcript fails open", run(edit(PAGE, "/nonexistent")) is None)
check("malformed payload fails open", run(None, raw="not json") is None)

# ai-config#5632: exercises and solutions also need teaching.qmd.
TEACH = ("Read", {"file_path": PSW + "teaching.qmd"})
EXR = "/repo/mcs/chapters/_subfiles/t/_boolean_exr.qmd"
ex = run(edit(EXR, transcript(ALL)))
check("exercise denied without teaching.qmd",
      ex is not None and "teaching" in ex["hookSpecificOutput"]["permissionDecisionReason"])
check("exercise allowed after teaching.qmd", run(edit(EXR, transcript(ALL + [TEACH]))) is None)
check("solution file gated",
      run(edit("/repo/mcs/chapters/_subfiles/t/_boolean_sol.qmd", transcript(ALL))) is not None)
check("mds-style _exr- name gated",
      run(edit("/repo/mds/_subfiles/t/_exr-boolean.qmd", transcript(ALL))) is not None)
check("exercise outside chapters/ gated",
      run(edit("/repo/mcsg/exercises/logic/_exr-boolean.qmd", transcript(ALL))) is not None)
check("teaching alone does not discharge an exercise",
      run(edit(EXR, transcript([TEACH]))) is not None)
div = {"tool_name": "Write", "transcript_path": transcript(ALL),
       "tool_input": {"file_path": PAGE, "content": ":::{#exr-x}\nAsk.\n:::\n"}}
check("exr div in content gated", run(div) is not None)
multi = {"tool_name": "MultiEdit", "transcript_path": transcript(ALL),
         "tool_input": {"file_path": PAGE, "edits": [{"new_string": "::: {#sol-x}"}]}}
check("sol div in MultiEdit gated", run(multi) is not None)
check("ordinary page needs no teaching.qmd", run(edit(PAGE, transcript(ALL))) is None)
check("console.qmd is not an exercise",
      run(edit("/repo/x/console.qmd", transcript([]))) is None)
check("non-qmd exercise name ignored",
      run(edit("/repo/x/_a_exr.py", transcript([]))) is None)

if fails:
    print("FAILED:", *fails, sep="\n  ")
    sys.exit(1)
print("all tests passed")
