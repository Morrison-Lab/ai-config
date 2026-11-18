#!/usr/bin/env python3
"""Tests for hooks/no-unnamed-repo-pr.py (ai-config#5780); optional arg: hook path."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "no-unnamed-repo-pr.py")
MCP, TMP, CASE_ENV, failures = "mcp__github__create_pull_request", tempfile.mkdtemp(prefix="nurp-"), {}, 0


def checkout(name, **remotes):
    path = os.path.join(TMP, name)
    subprocess.run(["git", "init", "-q", "-b", "main", path], check=True)
    for remote, url in remotes.items():
        subprocess.run(["git", "-C", path, "remote", "add", remote, url], check=True)
    return path


HOME = checkout("home", origin="http://proxy@127.0.0.1:4/git/Morrison-Lab/csci201")
OTHER = checkout("other", origin="git@github.com:Morrison-Lab/mlg.git")
FORK = checkout("fork", origin="https://github.com/me/x", upstream="https://github.com/Morrison-Lab/csci201")


def transcript(*records, cwd=HOME):
    fd, path = tempfile.mkstemp(suffix=".jsonl", dir=TMP)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for i, rec in enumerate({"type": "user", "message": {"content": r}} if isinstance(r, str) else r for r in records):
            fh.write(json.dumps({**rec, **({"cwd": cwd} if i == 0 else {})}) + "\n")
    return path


def verdict(tool, inp, tpath, cwd=HOME):
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_UNNAMED_REPO_PR", "GH_REPO", "GITLAB_REPO")}
    inp = {"command": inp} if tool == "Bash" else {"owner": "Morrison-Lab", "repo": inp}
    res = subprocess.run([sys.executable, HOOK], capture_output=True, encoding="utf-8", env={**env, **CASE_ENV},
                         input=json.dumps({"tool_name": tool, "tool_input": inp, "transcript_path": tpath, "cwd": cwd}))
    hso = (json.loads(res.stdout) if res.stdout.strip() else {}).get("hookSpecificOutput") or {}
    return "deny" if hso.get("permissionDecision") == "deny" else "note" if hso.get("additionalContext") else "pass"


GO, NAMED = transcript("go"), transcript("Adopt it in csci201; see mlg#423.")
CASES = [
    ("repo#N names the repo", MCP, "mlg", NAMED, "pass"),
    ("an unnamed repo is denied", MCP, "epi204", NAMED, "deny"),
    ("config is not ai-config", MCP, "config", transcript("fix ai-config"), "deny"),
    ("a tool result does not name it", MCP, "mlg", transcript({"type": "user", "message": {"content": [
        {"type": "tool_result", "content": "mlg"}]}}, "go"), "deny"),
    ("a system-reminder does not name it", MCP, "mlg", transcript("go <system-reminder>mlg</system-reminder>"), "deny"),
    ("an isMeta record does not", MCP, "mlg", transcript("go", {"type": "user", "isMeta": 1, "message": {"content": "mlg"}}), "deny"),
    ("a principal wake message names it", MCP, "mlg",
     transcript('<wake><message trigger="true" from="human" trust="principal">do mlg</message></wake>'), "pass"),
    ("a slash command's args name it", MCP, "mlg", transcript(
        "<command-name>/gi</command-name><command-args>Morrison-Lab/mlg#12</command-args>"), "pass"),
    ("a queued message names it", MCP, "mlg",
     transcript("go", {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "mlg"}}), "pass"),
    ("the home repo passes unnamed", MCP, "csci201", GO, "pass"),
    ("home is the first record's cwd", MCP, "mlg", GO, "deny", OTHER),
    ("-R names the target", "Bash", "gh pr create --repo Morrison-Lab/mlg -t x", GO, "deny"),
    ("--repo=URL names the target", "Bash", "gh pr create --repo=https://github.com/Morrison-Lab/csci201", GO, "pass"),
    ("cd into another clone is denied", "Bash", f"cd {OTHER} && gh pr create -t x", GO, "deny"),
    ("a fork targets upstream", "Bash", f"cd {FORK} && gh pr create", GO, "pass"),
    ("a GH_REPO prefix names the target", "Bash", "GH_REPO=o/mlg gh pr create", GO, "deny"),
    ("exported GH_REPO is unresolved", "Bash", "export GH_REPO=o/mlg; gh pr create", GO, "note"),
    ("GH_REPO before && is unresolved", "Bash", "GH_REPO=o/mlg true && gh pr create", GO, "note"),
    ("wrapped glab mr create", "Bash", "timeout 9 glab mr create -R g/s/mlg", GO, "deny"),
    ("if-led", "Bash", "if gh pr create -R o/mlg; then :; fi", GO, "deny"),
    ("brace-led", "Bash", "{ gh pr create -R o/mlg; }", GO, "deny"),
    ("bang-led", "Bash", "! gh pr create -R o/mlg", GO, "deny"),
    ("do-led", "Bash", "for i in 1; do gh pr create -R o/mlg; done", GO, "deny"),
    ("a quoted example is not a creation", "Bash", "echo 'gh pr create -R o/mlg'", GO, "pass"),
    ("nested bash -c is checked", "Bash", "bash -c 'gh pr create -R o/mlg'", GO, "deny"),
    ("an agent-side prefix does not override", "Bash", "ALLOW_UNNAMED_REPO_PR=1 gh pr create -R o/mlg", GO, "deny"),
    ("a missing transcript gives a note", MCP, "mlg", os.path.join(TMP, "none.jsonl"), "note"),
    ("no user message gives a note", MCP, "mlg", transcript({"type": "assistant", "message": {}}), "note"),
]
for name, tool, inp, tpath, want, *cwd in CASES + [("the hook-environment grant", MCP, "mlg", GO, "pass")]:
    CASE_ENV = {"ALLOW_UNNAMED_REPO_PR": "1"} if name == "the hook-environment grant" else {}
    got = verdict(tool, inp, tpath, *cwd)
    failures += got != want
    print(("PASS: " if got == want else f"FAIL (got {got}, want {want}): ") + name)

MUTATIONS = [  # each must fail this suite; skipped inside a mutant run
    ("named() matches anything", "    return any(rx.search(t) for t in texts)", "    return True"),
    ("isMeta records count", "rec.get(\"isMeta\") or rec.get(\"isSidechain\")", "rec.get(\"isSidechain\")"),
    ("keywords not stripped", "    while argv and argv[0] in SHELL_KEYWORDS:", "    while False:"),
    ("upstream not preferred", "(\"upstream\", \"github\", \"origin\")", "(\"origin\", \"upstream\", \"github\")"),
    ("payload cwd is home", "gh_target(first_cwd or payload.get(\"cwd\"))", "gh_target(payload.get(\"cwd\"))"),
]
if not os.environ.get("NURP_MUTANT"):
    original, hooks, lab = open(HOOK, encoding="utf-8").read(), os.path.dirname(os.path.realpath(HOOK)), tempfile.mkdtemp()
    os.makedirs(os.path.join(lab, "hooks"))
    os.symlink(os.path.join(os.path.dirname(hooks), "scripts"), os.path.join(lab, "scripts"))
    for sib in ("no-unrequested-sweep-pr.py", "remind-plain-english-merge-word.py"):
        os.symlink(os.path.join(hooks, sib), os.path.join(lab, "hooks", sib))
    for name, old, new in MUTATIONS:
        with open(os.path.join(lab, "hooks", "m.py"), "w", encoding="utf-8") as fh:
            fh.write(original.replace(old, new))
        res = subprocess.run([sys.executable, os.path.realpath(__file__), os.path.join(lab, "hooks", "m.py")],
                             capture_output=True, encoding="utf-8", env={**os.environ, "NURP_MUTANT": "1"}, timeout=300)
        failures += not (ok := original.count(old) == 1 and res.returncode != 0)
        print(("PASS: " if ok else "FAIL: ") + "suite catches mutation: " + name)
print(f"\n{failures} failed")
sys.exit(1 if failures else 0)
