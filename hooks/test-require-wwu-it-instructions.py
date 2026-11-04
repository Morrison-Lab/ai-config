#!/usr/bin/env python3
"""Tests for hooks/require-wwu-it-instructions.py.

Run: python3 hooks/test-require-wwu-it-instructions.py [hooks/require-wwu-it-instructions.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "require-wwu-it-instructions.py")


def transcript(*tool_uses):
    """A JSONL transcript holding the given (name, input) tool calls."""
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for name, inp in tool_uses:
        rec = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "input": inp}]}}
        fh.write(json.dumps(rec) + "\n")
    fh.close()
    return fh.name


READ_IT = ("Read", {"file_path": "/home/user/ai-config/memories/wwu-cs-it-instructions.md"})
CAT_IT = ("Bash", {"command": "cat /x/memories/wwu-cs-it-instructions.md"})
UNRELATED = ("Read", {"file_path": "/home/user/lds/README.md"})
SUBMIT = {"tool_name": "Bash", "tool_input": {"command": "ssh h condor_submit job.sub"}}


def payload(base, path):
    return dict(base, transcript_path=path)


def run(stdin):
    p = subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    unread = transcript(UNRELATED)
    read = transcript(UNRELATED, READ_IT)
    catted = transcript(CAT_IT)
    cases = [
        (payload(SUBMIT, unread), True, "condor_submit before reading the instructions is denied"),
        (payload(SUBMIT, read), False, "condor_submit after a Read is allowed"),
        (payload(SUBMIT, catted), False, "a cat of the file counts as reading it"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "ssh cse-head.cluster.cs.wwu.edu ls"}}, unread),
         True, "ssh to a cluster head is denied"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "echo CLUSTER_CI_ROOT"}}, unread),
         True, "CLUSTER_CI_ROOT is a trigger"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "ls /home/user"}}, unread),
         False, "an unrelated command is allowed"),
        (payload({"tool_name": "Edit", "tool_input": {"file_path": "/r/condor-batch/condor-batch.sh", "new_string": "x"}}, unread),
         True, "editing condor-batch is denied"),
        (payload({"tool_name": "Write", "tool_input": {"file_path": "/r/.github/workflows/cluster-render.yml", "content": "x"}}, unread),
         True, "writing a cluster workflow is denied"),
        (payload({"tool_name": "Write", "tool_input": {"file_path": "/r/job.sub", "content": "x"}}, unread),
         True, "writing a submit file is denied"),
        (payload({"tool_name": "Edit", "tool_input": {"file_path": "/r/a.yml", "new_string": "run: condor_q"}}, unread),
         True, "new text naming condor_q is denied"),
        (payload({"tool_name": "MultiEdit", "tool_input": {"file_path": "/r/a.yml", "edits": [{"new_string": "cse-head"}]}}, unread),
         True, "a multi-edit naming a head is denied"),
        (payload({"tool_name": "Edit", "tool_input": {"file_path": "/r/hooks/x.py", "new_string": "condor_submit"}}, unread),
         False, "hooks/ is exempt"),
        (payload({"tool_name": "Write", "tool_input": {"file_path": "/r/memories/x.md", "content": "condor-batch"}}, unread),
         False, "memories/ is exempt"),
        (payload({"tool_name": "Edit", "tool_input": {"file_path": "/r/chapters/a.qmd", "new_string": "hello"}}, unread),
         False, "an unrelated edit is allowed"),
        (payload({"tool_name": "Read", "tool_input": {"file_path": "/r/condor-batch.sh"}}, unread),
         False, "reading is never denied"),
        (payload(SUBMIT, transcript(("Bash", {"command": "ls memories/wwu-cs-it-instructions.md"}))),
         True, "an ls naming the file is not a read"),
        (payload(SUBMIT, transcript(("Read", {"file_path": "/x/not-wwu-cs-it-instructions.md"}))),
         True, "a Read of a differently named file is not a read"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "condor_submit_dag d.dag"}}, unread),
         True, "any condor_ tool is a trigger"),
        (payload({"tool_name": "Write", "tool_input": {"file_path": "/r/shared/condor-batch.sh", "content": "x"}}, unread),
         True, "a cluster file under shared/ is not exempt"),
        (payload({"tool_name": "Write", "tool_input": {"file_path": "/r/notes/condor_population.csv", "content": "x"}}, unread),
         False, "condor inside a longer file name is allowed"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "cat condor_population.csv"}}, unread),
         False, "a condor_ file name is not a command"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "ssh h condor_drain node1"}}, unread),
         True, "an HTCondor admin command is a trigger"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "condor_off -all"}}, unread),
         True, "condor_off is a trigger"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "ssh h /usr/bin/condor_submit job.sub"}}, unread),
         True, "an absolute path to a condor command is a trigger"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "ssh h ./condor_submit job.sub"}}, unread),
         True, "a ./ path to a condor command is a trigger"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "cat notes/condor_population.csv"}}, unread),
         False, "a condor_ file name in a path is not a command"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "grep condor_population_data notes.txt"}}, unread),
         False, "an extensionless condor_ identifier is not a command"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "mkdir condor_population_study"}}, unread),
         False, "a condor_ directory name is not a command"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "condor_restart -master"}}, unread),
         True, "condor_restart is a trigger"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "condor_advertise UPDATE_STARTD_AD ad"}}, unread),
         True, "condor_advertise is a trigger"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "condor_config_val -dump"}}, unread),
         True, "condor_config_val is a trigger"),
        (payload({"tool_name": "Bash", "tool_input": {"command": "cat no-condor-batch-notes.md"}}, unread),
         False, "a hyphenated near-match is allowed"),
        (dict(SUBMIT), False, "no transcript path fails open"),
        (payload(SUBMIT, "/nonexistent/transcript.jsonl"), False, "an unreadable transcript fails open"),
    ]
    fails = 0
    for pl, block, label in cases:
        rc, out = run(json.dumps(pl))
        blocked = '"permissionDecision": "deny"' in out
        ok = rc == 0 and blocked == block
        print(("  ok      " if ok else "  FAIL    ") + label)
        fails += 0 if ok else 1
    rc, out = run("not json")
    ok = rc == 0 and not out
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    rc, out = run(json.dumps(payload(SUBMIT, unread)))
    ok = "Avoid heavy home-directory I/O" in out
    print(("  ok      " if ok else "  FAIL    ") + "the deny reason prints the instructions")
    fails += 0 if ok else 1
    total = len(cases) + 2
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
