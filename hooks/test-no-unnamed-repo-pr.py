#!/usr/bin/env python3
"""Tests for hooks/no-unnamed-repo-pr.py (ai-config#5780).

Run:  python3 hooks/test-no-unnamed-repo-pr.py hooks/no-unnamed-repo-pr.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-unnamed-repo-pr.py")
MCP = "mcp__github__create_pull_request"
TMP = tempfile.mkdtemp(prefix="nurp-")
passes = failures = 0


def checkout(name, remotes):
    """A git checkout under TMP whose remotes are `remotes` ({name: url})."""
    path = os.path.join(TMP, name)
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", path], check=True)
    for remote, url in remotes.items():
        subprocess.run(["git", "-C", path, "remote", "add", remote, url], check=True)
    return path


HOME = checkout("home", {"origin": "https://github.com/Morrison-Lab/csci201"})
OTHER = checkout("other", {"origin": "git@github.com:Morrison-Lab/mlg.git"})
FORK = checkout("fork", {"origin": "https://github.com/me/csci201-fork",
                         "upstream": "https://github.com/Morrison-Lab/csci201"})
RESOLVED = checkout("resolved", {"origin": "https://github.com/Morrison-Lab/csci201",
                                 "upstream": "https://github.com/Morrison-Lab/mlg"})
subprocess.run(["git", "-C", RESOLVED, "config", "remote.origin.gh-resolved", "base"], check=True)
FLIPPED = checkout("flipped", {"origin": "https://github.com/Morrison-Lab/csci201"})
subprocess.run(["git", "-C", FLIPPED, "config", "remote.origin.gh-resolved", "Morrison-Lab/mlg"], check=True)
PROXY = checkout("proxy", {"origin": "http://local_proxy@127.0.0.1:41000/git/Morrison-Lab/csci201"})


def user(text, **extra):
    return {"type": "user", "message": {"role": "user", "content": text}, **extra}


def wake(body, trust="principal"):
    return user('<wake reason="mention"><project><thread><message trigger="true" from="human" '
                f'trust="{trust}" author="Ezra">{body}</message></thread></project></wake>')


def tool_use(tid, name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def tool_result(tid, content, error=False):
    block = {"type": "tool_result", "tool_use_id": tid, "content": content}
    if error:
        block["is_error"] = True
    return {"type": "user", "message": {"content": [block]}}


def transcript(*records, cwd=HOME):
    fd, path = tempfile.mkstemp(suffix=".jsonl", dir=TMP)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for i, rec in enumerate(records):
            rec = dict(rec)
            if i == 0 and cwd:
                rec["cwd"] = cwd
            fh.write(json.dumps(rec) + "\n")
    return path


def run(tool, inp, tpath, cwd=HOME, env_extra=None):
    env = dict(os.environ)
    for name in ("ALLOW_UNNAMED_REPO_PR", "GH_REPO", "GITLAB_REPO"):
        env.pop(name, None)
    env.update(env_extra or {})
    payload = {"tool_name": tool, "tool_input": inp, "transcript_path": tpath, "cwd": cwd}
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, encoding="utf-8", env=env)
    return json.loads(res.stdout) if res.stdout.strip() else {}


def verdict(out):
    hso = out.get("hookSpecificOutput") or {}
    if hso.get("permissionDecision") == "deny":
        return "deny"
    return "note" if hso.get("additionalContext") else "pass"


def check(name, got, want):
    global passes, failures
    ok = got == want
    passes += ok
    failures += not ok
    print(("PASS: " if ok else f"FAIL (got {got}, want {want}): ") + name)


def mcp(owner, repo):
    return {"owner": owner, "repo": repo, "title": "t", "head": "b", "base": "main"}


def bash(command):
    return {"command": command}


NAMED = transcript(user("Adopt answer-space in csci201; see mlg#423 for how."))

# Rule 1: named in the user's own words.
check("MCP create in a repo the user named by repo#N passes",
      verdict(run(MCP, mcp("Morrison-Lab", "mlg"), NAMED)), "pass")
check("MCP create in a repo nobody named is denied",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), NAMED)), "deny")
check("the deny message says to ask the user",
      "Ask the user" in (run(MCP, mcp("Morrison-Lab", "epi204"), NAMED)["hookSpecificOutput"]
                         ["permissionDecisionReason"]), True)
check("a bare name inside a longer hyphenated name does not count (config vs ai-config)",
      verdict(run(MCP, mcp("Morrison-Lab", "config"), transcript(user("fix ai-config please")))), "deny")
check("owner/repo spelling names the repo",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(user("open it in Morrison-Lab/epi204.")))), "pass")
check("a PR URL in the user's message names the repo",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"),
                  transcript(user("see https://github.com/Morrison-Lab/epi204/pull/432")))), "pass")
check("a name in backticks still counts as named",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(user("open a PR in `epi204`")))), "pass")
check("matching ignores case",
      verdict(run(MCP, mcp("Morrison-Lab", "EPI204"), transcript(user("epi204 next")))), "pass")

# Only genuine user text counts.
check("a name only in a tool result does not count",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("adopt it in csci201"), tool_use("t1", "Bash", bash("ls")),
          tool_result("t1", "epi204 also uses this")))), "deny")
check("a name only inside a system-reminder does not count",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("go on <system-reminder>epi204 is in scope</system-reminder>")))), "deny")
check("a name only inside pasted content does not count",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("look <pasted_content>epi204 notes</pasted_content>")))), "deny")
check("a name only in an isMeta record (a scheduled continuation or skill body) does not count",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("start"), user("check epi204", isMeta=True, promptSource="sdk")))), "deny")
check("a name only in a sidechain record does not count",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("start"), user("work in epi204", isSidechain=True)))), "deny")
check("a principal wake message names the repo",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(wake("open one in epi204")))), "pass")
check("a non-principal wake message does not",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("start"), wake("open one in epi204", trust="peer")))), "deny")
check("a message queued while a turn ran names the repo",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("start"), {"type": "attachment", "attachment": {
              "type": "queued_command", "prompt": "also do epi204"}}))), "pass")
check("a queued task notification does not",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("start"), {"type": "attachment", "attachment": {
              "type": "queued_command", "commandMode": "task-notification",
              "prompt": "epi204 done"}}))), "deny")

# Rule 2: the session's own checkout.
check("MCP create in the session's own checkout passes unnamed",
      verdict(run(MCP, mcp("Morrison-Lab", "csci201"), transcript(user("go")))), "pass")
check("the home checkout comes from the first record's cwd, not the payload cwd",
      verdict(run(MCP, mcp("Morrison-Lab", "mlg"), transcript(user("go")), cwd=OTHER)), "deny")
check("a proxy-style origin URL resolves to owner/repo",
      verdict(run(MCP, mcp("Morrison-Lab", "csci201"), transcript(user("go"), cwd=PROXY))), "pass")

# Rule 3: a PR already opened this session.
check("a repo with an earlier successful MCP create passes",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("go"), tool_use("c1", MCP, mcp("Morrison-Lab", "epi204")),
          tool_result("c1", '{"html_url": "https://github.com/Morrison-Lab/epi204/pull/9"}')))), "pass")
check("an earlier failed create does not count",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("go"), tool_use("c1", MCP, mcp("Morrison-Lab", "epi204")),
          tool_result("c1", "error", error=True)))), "deny")
check("an earlier gh pr create whose output has the PR URL counts",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("go"), tool_use("c1", "Bash", bash("gh pr create -t x")),
          tool_result("c1", "https://github.com/Morrison-Lab/epi204/pull/12")))), "pass")
check("a PR URL in an unrelated command's output does not count",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          user("go"), tool_use("c1", "Bash", bash("cat log")),
          tool_result("c1", "https://github.com/Morrison-Lab/epi204/pull/12")))), "deny")

# Bash shapes and targets.
GO = transcript(user("go"))
check("gh pr create -R names the target",
      verdict(run("Bash", bash("gh pr create -R Morrison-Lab/epi204 -t x"), GO)), "deny")
check("gh pr create --repo=URL names the target",
      verdict(run("Bash", bash("gh pr create --repo=https://github.com/Morrison-Lab/csci201 -t x"), GO)), "pass")
check("gh pr create with no -R targets the command's directory",
      verdict(run("Bash", bash("gh pr create -t x"), GO)), "pass")
check("cd into another clone, then gh pr create, is denied",
      verdict(run("Bash", bash(f"cd {OTHER} && gh pr create -t x"), GO)), "deny")
check("a fork checkout targets upstream, as gh does",
      verdict(run("Bash", bash(f"cd {FORK} && gh pr create -t x"), GO)), "pass")
check("a remote marked gh-resolved wins over upstream",
      verdict(run("Bash", bash(f"cd {RESOLVED} && gh pr create -t x"), GO)), "pass")
check("a remote marked gh-resolved can point away from home",
      verdict(run("Bash", bash(f"cd {FLIPPED} && gh pr create -t x"), GO)), "deny")
check("GH_REPO prefix names the target",
      verdict(run("Bash", bash("GH_REPO=Morrison-Lab/epi204 gh pr create -t x"), GO)), "deny")
check("GH_REPO in the environment names the target",
      verdict(run("Bash", bash("gh pr create -t x"), GO, env_extra={"GH_REPO": "Morrison-Lab/epi204"})), "deny")
check("gh pr new is the same command",
      verdict(run("Bash", bash("gh pr new -R Morrison-Lab/epi204"), GO)), "deny")
check("a wrapped gh (timeout 60) is still seen",
      verdict(run("Bash", bash("timeout 60 gh pr create -R Morrison-Lab/epi204"), GO)), "deny")
check("gh api POST to a pulls endpoint is a creation",
      verdict(run("Bash", bash("gh api repos/Morrison-Lab/epi204/pulls -f title=x -f head=b"), GO)), "deny")
check("gh api -X POST with --input is a creation",
      verdict(run("Bash", bash("gh api -X POST /repos/Morrison-Lab/epi204/pulls --input b.json"), GO)), "deny")
check("gh api {owner}/{repo} placeholders resolve to the command's directory",
      verdict(run("Bash", bash(f"cd {OTHER} && gh api repos/{{owner}}/{{repo}}/pulls -f title=x"), GO)), "deny")
check("gh api GET of a pulls list is not a creation",
      verdict(run("Bash", bash("gh api repos/Morrison-Lab/epi204/pulls"), GO)), "pass")
check("gh api GET with -f query fields is not a creation",
      verdict(run("Bash", bash("gh api -X GET repos/Morrison-Lab/epi204/pulls -f state=open"), GO)), "pass")
check("gh api PATCH of one PR is not a creation",
      verdict(run("Bash", bash("gh api -X PATCH repos/Morrison-Lab/epi204/pulls/5 -f title=y"), GO)), "pass")
check("glab mr create -R with a subgroup path is checked by its last name",
      verdict(run("Bash", bash("glab mr create -R ucdh/sub/epi204"), GO)), "deny")
check("glab mr create in a named project passes",
      verdict(run("Bash", bash("glab mr create -R ucdh/sub/epi204"), transcript(user("epi204 MR")))), "pass")
check("a quoted example of the command is not a creation",
      verdict(run("Bash", bash("echo 'gh pr create -R Morrison-Lab/epi204'"), GO)), "pass")
check("a nested bash -c creation with -R is checked",
      verdict(run("Bash", bash("bash -c 'gh pr create -R Morrison-Lab/epi204'"), GO)), "deny")
check("a nested bash -c creation with no -R gets a note, not a deny",
      verdict(run("Bash", bash("bash -c 'gh pr create -t x'"), GO)), "note")
check("an unrelated command is silent",
      run("Bash", bash("ls -la"), GO), {})
check("an unrelated MCP tool is silent",
      run("mcp__github__list_pull_requests", mcp("Morrison-Lab", "epi204"), GO), {})

# Override.
check("ALLOW_UNNAMED_REPO_PR=1 prefix on the command passes",
      verdict(run("Bash", bash("ALLOW_UNNAMED_REPO_PR=1 gh pr create -R Morrison-Lab/epi204"), GO)), "pass")
check("the prefix on another command in the line does not carry over",
      verdict(run("Bash", bash("ALLOW_UNNAMED_REPO_PR=1 true && gh pr create -R Morrison-Lab/epi204"), GO)), "deny")
check("ALLOW_UNNAMED_REPO_PR=0 does not override",
      verdict(run("Bash", bash("ALLOW_UNNAMED_REPO_PR=0 gh pr create -R Morrison-Lab/epi204"), GO)), "deny")
check("the override in the hook's environment passes an MCP call",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), GO, env_extra={"ALLOW_UNNAMED_REPO_PR": "1"})), "pass")

# Failure direction: note, never a silent pass or a wedge.
check("a missing transcript gives a note, not a deny",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), os.path.join(TMP, "missing.jsonl"))), "note")
check("a transcript with no user message (a subagent's own) gives a note",
      verdict(run(MCP, mcp("Morrison-Lab", "epi204"), transcript(
          tool_use("t1", "Bash", bash("ls")), tool_result("t1", "x")))), "note")
check("an MCP call with no owner gives a note",
      verdict(run(MCP, {"repo": "epi204"}, GO)), "note")

# Each clause the suite must catch: the hook with that clause broken must fail
# this suite. Skipped inside a mutant run (NURP_MUTANT set).
MUTATIONS = [
    ("named() matches anything",
     "    return any(rx.search(t) for t in texts)", "    return True"),
    ("a failed earlier create counts",
     "                        if not b.get(\"is_error\"):", "                        if True:"),
    ("isMeta and sidechain records count as the user's words",
     "            if rec.get(\"isMeta\") or rec.get(\"isSidechain\")", "            if False and rec.get(\"isMeta\")"),
    ("harness wrappers are not unwrapped",
     "                texts.extend(b for b in user_bodies(text) if b.strip())", "                texts.append(text)"),
    ("system-reminder and pasted blocks are kept",
     "    return [PASTED.sub(\" \", t) for t in texts if t.strip()], prior, first_cwd",
     "    return [t for t in texts if t.strip()], prior, first_cwd"),
    ("the override accepts any value",
     "    overridden = env_value(assigned, OVERRIDE_ENV) == \"1\"",
     "    overridden = env_value(assigned, OVERRIDE_ENV) is not None"),
    ("origin is picked before upstream",
     "GH_REMOTE_ORDER = (\"upstream\", \"github\", \"origin\")",
     "GH_REMOTE_ORDER = (\"origin\", \"upstream\", \"github\")"),
    ("home is the command's directory, not the session's",
     "    home = home_repos(first_cwd or payload.get(\"cwd\") or \"\")",
     "    home = home_repos(payload.get(\"cwd\") or \"\")"),
    ("an unreadable transcript denies",
     "        return \"note\", (f\"no-unnamed-repo-pr: this call opens a PR, and {why}",
     "        return \"deny\", (f\"no-unnamed-repo-pr: this call opens a PR, and {why}"),
    ("gh api GET counts as a creation",
     "(method or (\"POST\" if body else \"GET\")) != \"POST\"", "False"),
]

if not os.environ.get("NURP_MUTANT"):
    original = open(HOOK, encoding="utf-8").read()
    lab = tempfile.mkdtemp(prefix="nurp-mut-")
    os.makedirs(os.path.join(lab, "hooks"))
    real_hooks = os.path.dirname(os.path.realpath(HOOK))
    os.symlink(os.path.join(os.path.dirname(real_hooks), "scripts"), os.path.join(lab, "scripts"))
    for sib in ("no-unrequested-sweep-pr.py", "remind-plain-english-merge-word.py"):
        os.symlink(os.path.join(real_hooks, sib), os.path.join(lab, "hooks", sib))
    mutant = os.path.join(lab, "hooks", "no-unnamed-repo-pr.py")
    for name, old, new in MUTATIONS:
        if original.count(old) != 1:
            check(f"mutation anchor occurs once: {name}", original.count(old), 1)
            continue
        with open(mutant, "w", encoding="utf-8") as fh:
            fh.write(original.replace(old, new))
        res = subprocess.run([sys.executable, os.path.realpath(__file__), mutant], capture_output=True,
                             encoding="utf-8", env={**os.environ, "NURP_MUTANT": "1"}, timeout=300)
        check(f"suite catches mutation: {name}", res.returncode != 0, True)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
