#!/usr/bin/env python3
"""Tests for hooks/no-unnamed-repo-pr.py (ai-config#5780); optional arg: hook path."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-unnamed-repo-pr.py")
MCP = "mcp__github__create_pull_request"
TMP = tempfile.mkdtemp(prefix="nurp-")
failures = 0


def checkout(name, remotes, resolved=None):
    path = os.path.join(TMP, name)
    subprocess.run(["git", "init", "-q", "-b", "main", path], check=True)
    for remote, url in remotes.items():
        subprocess.run(["git", "-C", path, "remote", "add", remote, url], check=True)
    if resolved:
        subprocess.run(["git", "-C", path, "config", "remote.origin.gh-resolved", resolved], check=True)
    return path


HOME = checkout("home", {"origin": "http://proxy@127.0.0.1:4/git/Morrison-Lab/csci201"})
OTHER = checkout("other", {"origin": "git@github.com:Morrison-Lab/mlg.git"})
FORK = checkout("fork", {"origin": "https://github.com/me/x", "upstream": "https://github.com/Morrison-Lab/csci201"})
FLIP = checkout("flip", {"origin": "https://github.com/Morrison-Lab/csci201"}, resolved="Morrison-Lab/mlg")


def user(content, **extra):
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


def transcript(*records, cwd=HOME):
    fd, path = tempfile.mkstemp(suffix=".jsonl", dir=TMP)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for i, rec in enumerate(records):
            fh.write(json.dumps({**rec, **({"cwd": cwd} if i == 0 else {})}) + "\n")
    return path


def verdict(tool, inp, tpath, cwd=HOME):
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_UNNAMED_REPO_PR", "GH_REPO", "GITLAB_REPO")}
    payload = {"tool_name": tool, "tool_input": inp, "transcript_path": tpath, "cwd": cwd}
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True,
                         encoding="utf-8", env={**env, **CASE_ENV})
    hso = (json.loads(res.stdout) if res.stdout.strip() else {}).get("hookSpecificOutput") or {}
    return "deny" if hso.get("permissionDecision") == "deny" else "note" if hso.get("additionalContext") else "pass"


def mcp(repo):
    return {"owner": "Morrison-Lab", "repo": repo, "title": "t", "head": "b", "base": "main"}


GO = transcript(user("go"))
NAMED = transcript(user("Adopt it in csci201; see mlg#423."))
CASES = [
    ("repo#N names the repo", MCP, mcp("mlg"), NAMED, "pass"),
    ("an unnamed repo is denied", MCP, mcp("epi204"), NAMED, "deny"),
    ("config is not ai-config", MCP, mcp("config"), transcript(user("fix ai-config")), "deny"),
    ("a tool result does not name it", MCP, mcp("mlg"), transcript(user("go"), {"type": "user", "message": {
        "content": [{"type": "tool_result", "tool_use_id": "t", "content": "mlg"}]}}), "deny"),
    ("a system-reminder does not name it", MCP, mcp("mlg"),
     transcript(user("go <system-reminder>mlg</system-reminder>")), "deny"),
    ("an isMeta record does not name it", MCP, mcp("mlg"), transcript(user("go"), user("mlg", isMeta=True)), "deny"),
    ("a principal wake message names it", MCP, mcp("mlg"), transcript(user(
        '<wake><message trigger="true" from="human" trust="principal">do mlg</message></wake>')), "pass"),
    ("a slash command's args name it", MCP, mcp("mlg"), transcript(user(
        "<command-message>gi</command-message><command-name>/gi</command-name>"
        "<command-args>Morrison-Lab/mlg#12</command-args>")), "pass"),
    ("a queued message names it", MCP, mcp("mlg"), transcript(user("go"), {"type": "attachment", "attachment": {
        "type": "queued_command", "prompt": "also mlg"}}), "pass"),
    ("the home repo passes unnamed", MCP, mcp("csci201"), GO, "pass"),
    ("home is the first record's cwd, not the payload's", MCP, mcp("mlg"), transcript(user("go")), "deny", OTHER),
    ("-R names the target", "Bash", {"command": "gh pr create -R Morrison-Lab/mlg -t x"}, GO, "deny"),
    ("--repo=URL names the target", "Bash",
     {"command": "gh pr create --repo=https://github.com/Morrison-Lab/csci201"}, GO, "pass"),
    ("cd into another clone is denied", "Bash", {"command": f"cd {OTHER} && gh pr create -t x"}, GO, "deny"),
    ("a fork targets upstream", "Bash", {"command": f"cd {FORK} && gh pr create"}, GO, "pass"),
    ("gh-resolved wins", "Bash", {"command": f"cd {FLIP} && gh pr create"}, GO, "deny"),
    ("a GH_REPO prefix names the target", "Bash", {"command": "GH_REPO=o/mlg gh pr create"}, GO, "deny"),
    ("exported GH_REPO is unresolved", "Bash", {"command": "export GH_REPO=o/mlg; gh pr create"}, GO, "note"),
    ("GH_REPO set before && is unresolved", "Bash", {"command": "GH_REPO=o/mlg true && gh pr create"}, GO, "note"),
    ("glab mr create is checked", "Bash", {"command": "timeout 9 glab mr create -R g/s/mlg"}, GO, "deny"),
    ("if-led", "Bash", {"command": "if gh pr create -R o/mlg; then :; fi"}, GO, "deny"),
    ("brace-led", "Bash", {"command": "{ gh pr create -R o/mlg; }"}, GO, "deny"),
    ("bang-led", "Bash", {"command": "! gh pr create -R o/mlg"}, GO, "deny"),
    ("do-led", "Bash", {"command": "for i in 1; do gh pr create -R o/mlg; done"}, GO, "deny"),
    ("a quoted example is not a creation", "Bash", {"command": "echo 'gh pr create -R o/mlg'"}, GO, "pass"),
    ("nested bash -c with -R is checked", "Bash", {"command": "bash -c 'gh pr create -R o/mlg'"}, GO, "deny"),
    ("an agent-side prefix does not override", "Bash",
     {"command": "ALLOW_UNNAMED_REPO_PR=1 gh pr create -R o/mlg"}, GO, "deny"),
    ("a missing transcript gives a note", MCP, mcp("mlg"), os.path.join(TMP, "none.jsonl"), "note"),
    ("no user message gives a note", MCP, mcp("mlg"), transcript({"type": "assistant", "message": {}}), "note"),
]
CASE_ENV = {}
for name, tool, inp, tpath, want, *cwd in CASES:
    got = verdict(tool, inp, tpath, *cwd)
    failures += got != want
    print(("PASS: " if got == want else f"FAIL (got {got}, want {want}): ") + name)
CASE_ENV = {"ALLOW_UNNAMED_REPO_PR": "1"}
got = verdict(MCP, mcp("mlg"), GO)
failures += got != "pass"
print(("PASS: " if got == "pass" else "FAIL: ") + "the hook-environment grant overrides")

MUTATIONS = [  # each must make this suite fail; skipped inside a mutant run
    ("named() matches anything", "    return any(rx.search(t) for t in texts)", "    return True"),
    ("isMeta records count", "rec.get(\"isMeta\") or rec.get(\"isSidechain\")", "rec.get(\"isSidechain\")"),
    ("reminders kept", "[PASTED.sub(\" \", t) for t in texts", "[t for t in texts"),
    ("keywords not stripped", "    while argv and argv[0] in SHELL_KEYWORDS:", "    while False:"),
    ("upstream not preferred", "(\"upstream\", \"github\", \"origin\")", "(\"origin\", \"upstream\", \"github\")"),
    ("payload cwd is home", "gh_target(first_cwd or payload.get(\"cwd\"))", "gh_target(payload.get(\"cwd\"))"),
]
if not os.environ.get("NURP_MUTANT"):
    original = open(HOOK, encoding="utf-8").read()
    lab, hooks = tempfile.mkdtemp(prefix="nurp-mut-"), os.path.dirname(os.path.realpath(HOOK))
    os.makedirs(os.path.join(lab, "hooks"))
    os.symlink(os.path.join(os.path.dirname(hooks), "scripts"), os.path.join(lab, "scripts"))
    for sib in ("no-unrequested-sweep-pr.py", "remind-plain-english-merge-word.py"):
        os.symlink(os.path.join(hooks, sib), os.path.join(lab, "hooks", sib))
    mutant = os.path.join(lab, "hooks", "no-unnamed-repo-pr.py")
    for name, old, new in MUTATIONS:
        with open(mutant, "w", encoding="utf-8") as fh:
            fh.write(original.replace(old, new))
        res = subprocess.run([sys.executable, os.path.realpath(__file__), mutant], capture_output=True,
                             encoding="utf-8", env={**os.environ, "NURP_MUTANT": "1"}, timeout=300)
        ok = original.count(old) == 1 and res.returncode != 0
        failures += not ok
        print(("PASS: " if ok else "FAIL: ") + "suite catches mutation: " + name)
print(f"\n{failures} failed")
sys.exit(1 if failures else 0)
