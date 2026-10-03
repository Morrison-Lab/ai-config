"""Test the remind-record-standing-guidance hook.

Builds a synthetic transcript per case and feeds the hook a UserPromptSubmit
payload (transcript_path plus prompt). The hook must print a reminder when the
new prompt, or the previous user message with nothing recorded after it, reads
as standing guidance, and print NOTHING otherwise. It must never exit non-zero
and never emit a block decision.

Run:  python3 hooks/test-remind-record-standing-guidance.py hooks/remind-record-standing-guidance.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = sys.argv[1]
if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")


def user(s):
    return {"type": "user", "message": {"content": [{"type": "text", "text": s}]}}


def result():
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "From now on always do it."}]}}


def say(s):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": s}]}}


def tool(name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}


RULE = "Always link every PR in tables when you report status to me."


def run(recs, prompt="Thanks, now please run the tests again.", sentinel_dir=None,
        raw=None, twice=False, count=False):
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    own = sentinel_dir is None
    if own:
        sentinel_dir = tempfile.mkdtemp()
    outs = []
    try:
        for _ in range(2 if twice else 1):
            stdin = raw if raw is not None else json.dumps(
                {"transcript_path": tpath, "prompt": prompt})
            p = subprocess.run([sys.executable, HOOK], input=stdin,
                               capture_output=True, text=True,
                               env=dict(os.environ, TMPDIR=sentinel_dir))
            if p.returncode != 0:
                sys.exit(f"FATAL: hook exited {p.returncode}\n{p.stderr.strip()}")
            if '"decision"' in p.stdout or "block" in p.stdout.lower():
                sys.exit(f"FATAL: block-shaped output\n{p.stdout}")
            if count:
                outs.append(p.stdout.count("Standing-guidance reminder"))
            else:
                outs.append("REMIND" if p.stdout.strip() else "silent")
    finally:
        os.unlink(tpath)
        if own:
            shutil.rmtree(sentinel_dir, ignore_errors=True)
    return outs if twice else outs[0]


# (records, prompt, description); prompt "" means a neutral new prompt.
NEUTRAL = "Thanks, now please run the tests again."
REMIND = [
    ([], "From now on, record every rule in ai-config right away.", "new: from now on"),
    ([], "Going forward, put prose rules in psw as well as project memory.", "new: going forward"),
    ([], RULE, "new: always at sentence start"),
    ([], "You should never wait to be told a rule is global.", "new: you should never"),
    ([], "Please don't save rules only in project memory again.", "new: sentence-start don't"),
    ([], "Do not leave rules only in project memory, ever.", "new: do not"),
    ([], "It's up to you whether to streamline project memory afterwards.", "new: it's up to you whether"),
    ([], "The rule is: global home first, project memory second.", "new: the rule is"),
    ([], "Assume a repo is private unless I say it is public.", "new: assume ... unless"),
    ([], "Start enforcing rules as soon as I give them to you.", "new: start enforcing"),
    ([user(RULE), say("Understood.")], NEUTRAL, "earlier message, nothing recorded"),
    ([user(RULE), say("Saved it."),
      tool("Write", {"file_path": "/home/u/proj/.claude/memory/x.md", "content": "x"})],
     NEUTRAL, "earlier message, only project-local non-global write"),
    ([user(RULE), tool("Bash", {"command": "cat /home/u/ai-config/AGENTS.md"})],
     NEUTRAL, "a read-only Bash on a global path does not discharge"),
    ([user(RULE), tool("Agent", {"prompt": "Summarize the project README"})],
     NEUTRAL, "an Agent prompt not naming ai-config or psw does not discharge"),
    ([tool("Edit", {"file_path": "/home/u/ai-config/AGENTS.md"}), user(RULE), say("ok")],
     NEUTRAL, "an Edit BEFORE the message does not discharge it"),
    ([user(RULE), result(), say("ok")], NEUTRAL, "tool_result records are not human messages"),
]
SILENT = [
    ([], "Please fix the failing test in foo.py and rerun the suite.", "plain task request"),
    ([], "Should we always link PRs in tables, or only in summaries?", "question about a rule"),
    ([], "Why does the build never finish on this branch?", "question using never"),
    ([], "Can you always link every PR in tables when you report status to me?",
     "question that would match the always alternative"),
    ([], "ok thanks", "short ack"),
    ([], "Never mind.", "short, under the length floor"),
    ([], "Here is the text:\n```\nFrom now on always link every PR in tables.\n```\nsummarize it", "fenced text"),
    ([], "> From now on always link every PR in tables.\nPlease summarize the quote above", "blockquoted text"),
    ([], "Please explain what `going forward` means in this changelog entry.", "inline-code phrase"),
    ([], "Don't worry about the lint warnings in that file for now.", "don't worry"),
    ([user(RULE), tool("Edit", {"file_path": "/home/u/ai-config/AGENTS.md"})],
     NEUTRAL, "discharged by later Edit under ai-config"),
    ([user(RULE), tool("Write", {"file_path": "/home/u/psw/rules/x.md", "content": "x"})],
     NEUTRAL, "discharged by later Write under psw"),
    ([user(RULE), tool("Edit", {"file_path": "/home/u/proj/shared/workflow/y.md"})],
     NEUTRAL, "discharged by later Edit under shared/"),
    ([user(RULE), tool("NotebookEdit", {"notebook_path": "/home/u/ai-config/shared/x.ipynb", "new_source": "x"})],
     NEUTRAL, "discharged by later NotebookEdit (notebook_path) under ai-config"),
    ([user(RULE), tool("write_to_file", {"TargetFile": "/home/u/ai-config/AGENTS.md", "CodeContent": "x"})],
     NEUTRAL, "discharged by later cross-agent write_to_file (TargetFile) under ai-config"),
    ([user(RULE), tool("Bash", {"command": "cd ai-config && git add AGENTS.md && git commit -m x"})],
     NEUTRAL, "discharged by later git Bash on ai-config"),
    ([user(RULE), tool("Agent", {"prompt": "Record this rule in psw and ai-config."})],
     NEUTRAL, "discharged by Agent prompt naming psw"),
    ([user(RULE), tool("Task", {"prompt": "Update ai-config AGENTS.md with the rule."})],
     NEUTRAL, "discharged by Task prompt naming ai-config"),
    ([user("From now on always link every PR in tables."), say("ok")],
     "From now on always link every PR in tables.",
     "same text already in transcript is the new prompt, not an earlier one, and the new one fires once only below"),
]

wrong = 0
print("should REMIND:")
for recs, prompt, desc in REMIND:
    v = run(recs, prompt)
    wrong += v != "REMIND"
    print(f"  {v:<7} {desc}")

print("\nshould stay silent:")
for recs, prompt, desc in SILENT[:-1]:
    v = run(recs, prompt)
    wrong += v != "silent"
    print(f"  {v:<7} {desc}")

print("\nsentinel and fail-open:")
# Fires once per distinct message: the same prompt twice, same transcript.
got = run([], RULE, twice=True)
ok = got == ["REMIND", "silent"]
wrong += not ok
print(f"  {'ok' if ok else 'WRONG':<7} new prompt fires once, then is silent ({got})")

got = run([user(RULE), say("Understood.")], NEUTRAL, twice=True)
ok = got == ["REMIND", "silent"]
wrong += not ok
print(f"  {'ok' if ok else 'WRONG':<7} earlier message fires once, then is silent ({got})")

# A new prompt echoed as the last transcript record is not also an "earlier" one.
got = run([user(RULE)], RULE, twice=True)
ok = got == ["REMIND", "silent"]
wrong += not ok
print(f"  {'ok' if ok else 'WRONG':<7} prompt echoed in transcript fires once ({got})")

# With the new prompt echoed as the last record, the REAL earlier rule before
# it is still checked: two reminders, one per distinct rule.
n = run([user("Never skip the pre-push review on any branch."), say("ok"), user(RULE)],
        RULE, count=True)
ok = n == 2
wrong += not ok
print(f"  {'ok' if ok else 'WRONG':<7} echoed prompt does not hide the real earlier rule ({n} reminders)")

# Two distinct rules each get their own firing in one sentinel dir.
sd = tempfile.mkdtemp()
a = run([], "From now on, record every rule in ai-config.", sentinel_dir=sd)
b = run([], "Going forward, record every prose rule in psw.", sentinel_dir=sd)
shutil.rmtree(sd, ignore_errors=True)
ok = (a, b) == ("REMIND", "REMIND")
wrong += not ok
print(f"  {'ok' if ok else 'WRONG':<7} distinct messages each fire ({a}, {b})")

for desc, raw in [("empty stdin", ""), ("non-JSON stdin", "not json"),
                  ("JSON list payload", "[1, 2]"),
                  ("non-string prompt", json.dumps({"prompt": 5, "transcript_path": 7})),
                  ("missing transcript file", json.dumps(
                      {"prompt": "hello there", "transcript_path": "/nonexistent/x.jsonl"}))]:
    v = run([], raw=raw)
    ok = v == "silent"
    wrong += not ok
    print(f"  {'ok' if ok else 'WRONG':<7} fails open and silent: {desc}")

# Missing transcript must still fire for a rule in the new prompt (no crash).
v = run([], raw=json.dumps({"prompt": RULE, "transcript_path": "/nonexistent/x.jsonl"}))
ok = v == "REMIND"
wrong += not ok
print(f"  {'ok' if ok else 'WRONG':<7} missing transcript still reminds for the new prompt")

total = len(REMIND) + len(SILENT) - 1 + 5 + 5 + 1
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
