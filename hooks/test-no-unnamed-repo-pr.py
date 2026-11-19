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
PROJECT_BRIEF = ("<session-context>\nProject: P\nRepositories configured for this project:\n"
                 "- https://github.com/Morrison-Lab/mlg\n- https://github.com/morrison-lab/csci201\n\nMore text</session-context>")
RELAY_BRIEF = ('<coordinator-relay><relay from="coordinator" session="s"><cited author="user">epi205</cited>'
               "<note>Open the PR in Morrison-Lab/epi204.</note></relay></coordinator-relay>")
CASES = [
    ("repo#N names the repo", MCP, "mlg", NAMED, "pass"),
    ("an unnamed repo is denied", MCP, "epi204", NAMED, "deny"),
    ("config is not ai-config", MCP, "config", transcript("fix ai-config"), "deny"),
    ("a tool result does not name it", MCP, "mlg", transcript({"type": "user", "message": {"content": [
        {"type": "tool_result", "content": "mlg"}]}}, "go"), "deny"),
    ("a system-reminder does not name it", MCP, "mlg", transcript("go <system-reminder>mlg</system-reminder>"), "deny"),
    ("an isMeta record does not", MCP, "mlg", transcript("go", {"type": "user", "isMeta": 1, "message": {"content": "mlg"}}), "deny"),
    ("a principal wake names it", MCP, "mlg", transcript('<wake><message trigger="true" from="human" trust="principal">mlg</message></wake>'), "pass"),
    ("a slash command's args name it", MCP, "mlg", transcript(
        "<command-name>/gi</command-name><command-args>Morrison-Lab/mlg#12</command-args>"), "pass"),
    ("a peer wake or task notification cannot smuggle command-args", MCP, "mlg", transcript("go", *(
        f"<{t}><command-name>/x</command-name><command-args>mlg</command-args></{t}>" for t in ("wake", "task-notification"))),
     "deny"),
    ("a queued peer wake does not name it", MCP, "mlg", transcript("go", {"type": "attachment", "attachment": {
        "type": "queued_command", "prompt": '<wake><message trigger="true" from="agent" trust="peer">mlg</message></wake>'}}), "deny"),
    ("a queued message names it", MCP, "mlg",
     transcript("go", {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "mlg"}}), "pass"),
    ("the home repo passes unnamed", MCP, "csci201", GO, "pass"),
    ("home is the first record's cwd", MCP, "mlg", GO, "deny", OTHER),
    ("--repo=URL names the target", "Bash", "gh pr create --repo=https://github.com/Morrison-Lab/csci201", GO, "pass"),
    ("cd into another clone is denied", "Bash", f"cd {OTHER} && gh pr create -t x", GO, "deny"),
    ("a fork targets upstream", "Bash", f"cd {FORK} && gh pr create", GO, "pass"),
    ("a GH_REPO prefix names the target", "Bash", "GH_REPO=o/mlg gh pr create", GO, "deny"),
    ("exported GH_REPO is unresolved under a FOO=1 prefix", "Bash", "export GH_REPO=o/mlg; FOO=1 gh pr create", GO, "note"),
    ("wrapped glab mr create", "Bash", "timeout 9 glab mr create -R g/s/mlg", GO, "deny"),
    ("brace- and bang-led", "Bash", "{ ! gh pr create --repo o/mlg; }", GO, "deny"),
    ("do- and if-led", "Bash", "for i in 1; do if gh pr create -R o/mlg; then :; fi; done", GO, "deny"),
    ("a quoted example is not a creation", "Bash", "echo 'gh pr create -R o/mlg'", GO, "pass"),
    ("nested bash -c is checked", "Bash", "bash -c 'gh pr create -R o/mlg'", GO, "deny"),
    ("an agent-side prefix does not override", "Bash", "ALLOW_UNNAMED_REPO_PR=1 gh pr create -R o/mlg", GO, "deny"),
    ("gh api POST /pulls to an unnamed repo is denied", "Bash", "gh api repos/o/mlg/pulls -X POST -f title=x", GO, "deny"),
    ("gh api --method=POST is denied", "Bash", "gh api --method=POST /repos/o/mlg/pulls", GO, "deny"),
    ("gh api -f implies POST", "Bash", "gh api repos/o/mlg/pulls -f title=x -f head=b", GO, "deny"),
    ("gh api POST to a named repo passes", "Bash", "gh api repos/o/mlg/pulls -X POST", NAMED, "pass"),
    ("gh api POST to the home repo passes", "Bash", "gh api repos/Morrison-Lab/csci201/pulls -f title=x", GO, "pass"),
    ("gh api GET of /pulls passes", "Bash", "gh api repos/o/mlg/pulls", GO, "pass"),
    ("gh api explicit GET with -f passes", "Bash", "gh api -X GET repos/o/mlg/pulls -f state=open", GO, "pass"),
    ("gh api POST to another endpoint passes", "Bash", "gh api repos/o/mlg/issues -f title=x", GO, "pass"),
    ("gh api graphql createPullRequest gives a note", "Bash",
     "gh api graphql -f query='mutation { createPullRequest(input: {}) { pullRequest { id } } }'", GO, "note"),
    ("gh api graphql without createPullRequest passes", "Bash", "gh api graphql -f query='{ viewer { login } }'", GO, "pass"),
    ("glab api POST merge_requests to an unnamed repo is denied", "Bash",
     "glab api projects/g%2Fmlg/merge_requests -X POST -f title=x", GO, "deny"),
    ("glab api POST to the home repo passes", "Bash", "glab api -X POST projects/Morrison-Lab%2Fcsci201/merge_requests", GO, "pass"),
    ("glab api POST to a named repo passes", "Bash", "glab api projects/g%2Fmlg/merge_requests -f title=x", NAMED, "pass"),
    ("glab api numeric project gives a note", "Bash", "glab api projects/42/merge_requests -f title=x", GO, "note"),
    ("glab api GET of merge_requests passes", "Bash", "glab api projects/g%2Fmlg/merge_requests", GO, "pass"),
    ("gh api -XPOST attached method", "Bash", "gh api -XPOST repos/o/mlg/pulls", GO, "deny"),
    ("gh api --method POST space form", "Bash", "gh api --method POST repos/o/mlg/pulls", GO, "deny"),
    ("gh api -ftitle=x attached field implies POST", "Bash", "gh api repos/o/mlg/pulls -ftitle=x", GO, "deny"),
    ("gh api placeholders from another checkout are denied", "Bash", "gh api -X POST repos/{owner}/{repo}/pulls", GO, "deny", OTHER),
    ("gh api placeholders from the home checkout pass", "Bash", "gh api -X POST repos/{owner}/{repo}/pulls", GO, "pass"),
    ("gh api a mixed placeholder from home passes", "Bash", "gh api -X POST repos/{owner}/csci201/pulls", GO, "pass"),
    ("gh api a GH_REPO prefix fills the placeholders", "Bash",
     "GH_REPO=o/mlg gh api -X POST repos/{owner}/{repo}/pulls -f title=x", GO, "deny"),
    ("gh api a query string does not hide the endpoint", "Bash", "gh api -X POST 'repos/o/mlg/pulls?x=1' -f title=x", GO, "deny"),
    ("gh api a full URL does not hide the endpoint", "Bash",
     "gh api -X POST https://api.github.com/repos/o/mlg/pulls -f title=x", GO, "deny"),
    ("gh api a GHE api/v3 prefix does not hide the endpoint", "Bash",
     "gh api -X POST https://ghe.x/api/v3/repos/o/mlg/pulls -f title=x", GO, "deny"),
    ("glab api a query string does not hide the endpoint", "Bash", "glab api 'projects/g%2Fmlg/merge_requests?x=1' -X POST", GO, "deny"),
    ("glab api a full URL does not hide the endpoint", "Bash",
     "glab api https://gitlab.com/api/v4/projects/g%2Fmlg/merge_requests -X POST", GO, "deny"),
    ("glab api :fullpath from another checkout is denied", "Bash", "glab api projects/:fullpath/merge_requests -X POST", GO, "deny", OTHER),
    ("glab api :fullpath from home passes", "Bash", "glab api projects/:fullpath/merge_requests -X POST", GO, "pass"),
    ("gh api /graphql createPullRequest gives a note", "Bash",
     "gh api /graphql -f query='mutation { createPullRequest(input: {}) { clientMutationId } }'", GO, "note"),
    ("gh api graphql URL gives a note", "Bash",
     "gh api https://api.github.com/graphql -f query='mutation { createPullRequest(input: {}) { clientMutationId } }'", GO, "note"),
    ("gh api graphql --input gives a note", "Bash", "gh api graphql --input mut.json", GO, "note"),
    ("gh api graphql -F query=@file gives a note", "Bash", "gh api graphql -F query=@mut.graphql", GO, "note"),
    ("gh api graphql substituted body gives a note", "Bash", 'gh api graphql -f query="$(cat mut.graphql)"', GO, "note"),
    ("glab api --form implies POST", "Bash", "glab api projects/g%2Fmlg/merge_requests --form title=x", GO, "deny"),
    ("glab api --output takes a value", "Bash", "glab api --output out.json projects/g%2Fmlg/merge_requests -X POST", GO, "deny"),
    ("glab api --placeholder takes a value", "Bash", "glab api --placeholder x projects/g%2Fmlg/merge_requests -X POST", GO, "deny"),
    ("glab api :namespace%2F:repo from home passes", "Bash", "glab api -X POST projects/:namespace%2F:repo/merge_requests", GO, "pass"),
    ("glab api :namespace%2F:repo from another checkout is denied", "Bash",
     "glab api -X POST projects/:namespace%2F:repo/merge_requests", GO, "deny", OTHER),
    ("glab api an unknown placeholder gives a note", "Bash", "glab api -X POST projects/o%2F:nope/merge_requests", GO, "note"),
    ("gh api a double slash does not hide the endpoint", "Bash", "gh api -X POST repos/o/mlg//pulls", GO, "deny"),
    ("gh api a leading double slash does not hide the endpoint", "Bash", "gh api -X POST //repos/o/mlg/pulls", GO, "deny"),
    ("glab api a path-prefixed instance URL", "Bash",
     "glab api -X POST https://git.example.com/gitlab/api/v4/projects/g%2Fmlg/merge_requests", GO, "deny"),
    ("gh api the hook-environment GH_REPO fills the placeholders", "Bash", "gh api -X POST repos/{owner}/{repo}/pulls", GO, "deny"),
    ("gh api an exported GH_REPO elsewhere gives a note", "Bash",
     "export GH_REPO=o/mlg; gh api -X POST repos/{owner}/{repo}/pulls", GO, "note"),
    ("gh api a fragment does not hide the endpoint", "Bash", "gh api -X POST 'repos/o/mlg/pulls#x?y' -f title=x", GO, "deny"),
    ("glab api a fragment does not hide the endpoint", "Bash", "glab api -X POST 'projects/g%2Fmlg/merge_requests#x'", GO, "deny"),
    ("glab api :username is unknown, so a note", "Bash", "glab api -X POST projects/:namespace%2F:username/merge_requests", GO, "note"),
    ("glab api graphql mergeRequestCreate gives a note", "Bash",
     "glab api graphql -f query='mutation { mergeRequestCreate(input: {}) { clientMutationId } }'", GO, "note"),
    ("gh api -R value is not the endpoint", "Bash", "gh api -R o/mlg repos/o/mlg/pulls -X POST -f title=x", GO, "deny"),
    ("glab api -R value is not the endpoint", "Bash", "glab api -R g/x projects/g%2Fmlg/merge_requests -X POST", GO, "deny"),
    ("glab api graphql after -R still notes", "Bash",
     "glab api -R g/x graphql -f query='mutation { mergeRequestCreate(input: {}) { clientMutationId } }'", GO, "note"),
    ("gh api -R fills the placeholders", "Bash", "gh api repos/{owner}/{repo}/pulls -R o/mlg -X POST", GO, "deny"),
    ("glab api --repo fills :fullpath", "Bash", "glab api --repo=g/mlg projects/:fullpath/merge_requests -X POST", GO, "deny"),
    ("glab api -R of the home repo fills :fullpath", "Bash",
     "glab api -R Morrison-Lab/csci201 projects/:fullpath/merge_requests -X POST", GO, "pass"),
    ("gh api -X=POST attached shorthand with an equals sign", "Bash", "gh api -X=POST repos/o/mlg/pulls", GO, "deny"),
    ("gh api :owner/:repo from another checkout is denied", "Bash", "gh api -X POST repos/:owner/:repo/pulls", GO, "deny", OTHER),
    ("gh api :owner/:repo from home passes", "Bash", "gh api -X POST repos/:owner/:repo/pulls", GO, "pass"),
    ("glab api a GITLAB_REPO prefix fills :fullpath", "Bash",
     "GITLAB_REPO=g/mlg glab api -X POST projects/:fullpath/merge_requests", GO, "deny"),
    ("glab api the hook-environment GITLAB_REPO fills :fullpath", "Bash", "glab api -X POST projects/:fullpath/merge_requests", GO, "deny"),
    ("glab api an exported GITLAB_REPO elsewhere gives a note", "Bash",
     "export GITLAB_REPO=g/mlg; glab api -X POST projects/:fullpath/merge_requests", GO, "note"),
    ("gh api a repo named api/v3 is not stripped", "Bash", "gh api -X POST https://h.example/repos/api/v3/pulls", GO, "deny"),
    ("gh api a leading api/v3 is stripped", "Bash", "gh api -X POST https://h.example/api/v3/repos/o/mlg/pulls", GO, "deny"),
    ("gh api an unknown flag is not the endpoint", "Bash", "gh api --weird repos/o/mlg/pulls -X POST", GO, "deny"),
    ("gh api an unknown flag on a GET of /pulls gives a note", "Bash", "gh api repos/o/mlg/pulls --weird", GO, "note"),
    ("gh api a known boolean flag on a GET passes", "Bash", "gh api repos/o/mlg/pulls --paginate -i", GO, "pass"),
    ("gh api -iX POST is a cluster, not an endpoint", "Bash", "gh api -iX POST repos/o/mlg/pulls", GO, "deny"),
    ("gh api -iXGET stays a GET", "Bash", "gh api repos/o/mlg/pulls -iXGET -f state=open", GO, "pass"),
    ("gh api after -- a dash token is positional", "Bash", "gh api -X POST -- -x repos/o/mlg/pulls", GO, "pass"),
    ("glab api an unknown flag may hide the endpoint", "Bash", "glab api --weird x projects/g%2Fmlg/merge_requests", GO, "note"),
    ("glab api :namespace/:repo is one segment", "Bash",
     "glab api -X POST projects/:namespace/:repo/merge_requests -f title=x", GO, "deny", OTHER),
    ("glab api :namespace/:repo from home passes", "Bash", "glab api -X POST projects/:namespace/:repo/merge_requests", GO, "pass"),
    ("glab api :group/:namespace/:repo is one segment", "Bash",
     "glab api -X POST projects/:group/:namespace/:repo/merge_requests", GO, "deny", OTHER),
    ("glab api nested -R fills :fullpath", "Bash", "glab api -R g/s/mlg projects/:fullpath/merge_requests -X POST", GO, "deny"),
    ("glab api nested -R of a named repo passes", "Bash", "glab api -R g/s/mlg projects/:fullpath/merge_requests -X POST", NAMED, "pass"),
    ("glab api nested hook-environment GITLAB_REPO", "Bash", "glab api -X POST projects/:fullpath/merge_requests", GO, "deny"),
    ("glab api a nested literal path is denied", "Bash", "glab api -X POST projects/g%2Fs%2Fmlg/merge_requests", GO, "deny"),
    ("glab api a one-segment -R gives a note, not a crash", "Bash", "glab api -R g projects/:fullpath/merge_requests -X POST", GO, "note"),
    ("gh api a two-segment host prefix is stripped", "Bash", "gh api -X POST https://h.example/a/b/api/v3/repos/o/mlg/pulls", GO, "deny"),
    ("gh api a GHE api/graphql URL gives a note", "Bash",
     "gh api https://h.example/api/graphql -f query='mutation { createPullRequest(input: {}) { clientMutationId } }'", GO, "note"),
    ("glab -R before api is a global flag", "Bash", "glab -R g/mlg api projects/:fullpath/merge_requests -X POST", GO, "deny"),
    ("glab -R before mr create is a global flag", "Bash", "glab -R g/mlg mr create -t x", GO, "deny"),
    ("glab --help before api does not hide it", "Bash", "glab --help api projects/g%2Fmlg/merge_requests -X POST", GO, "deny"),
    ("a POST to a shell-variable endpoint gives a note", "Bash", 'EP=repos/o/mlg/pulls; gh api "$EP" -X POST -f title=x', GO, "note"),
    ("a GET of a shell-variable endpoint passes", "Bash", 'gh api "$EP"', GO, "pass"),
    ("glab -Rvalue attached before api", "Bash", "glab -Rg/mlg api projects/:fullpath/merge_requests -X POST", GO, "deny"),
    ("glab -R=value attached before api", "Bash", "glab -R=g/mlg api projects/:fullpath/merge_requests -X POST", GO, "deny"),
    ("glab -Rvalue attached before mr create", "Bash", "glab -Rg/mlg mr create -t x", GO, "deny"),
    ("glab a global -R before -- stays a flag", "Bash", "glab -R g/mlg api -X POST -- projects/:id/merge_requests", GO, "deny"),
    ("glab a later -R wins over the global one", "Bash",
     "glab -R Morrison-Lab/csci201 api -R g/mlg -X POST projects/:fullpath/merge_requests", GO, "deny"),
    ("glab a later home -R wins over the global one", "Bash",
     "glab -R g/mlg api -R Morrison-Lab/csci201 -X POST projects/:fullpath/merge_requests", GO, "pass"),
    ("glab -h before api does not hide it", "Bash", "glab -h api projects/g%2Fmlg/merge_requests -X POST", GO, "deny"),
    ("a shell expansion in the query does not hide the path", "Bash", 'gh api -X POST "repos/o/mlg/pulls?a=$X" -f title=x', GO, "deny"),
    ("a host variable does not hide the path", "Bash", 'gh api -X POST "https://$H/repos/o/mlg/pulls" -f title=x', GO, "deny"),
    ("a variable in a repo segment gives a note", "Bash", 'gh api -X POST "repos/$O/mlg/pulls" -f title=x', GO, "note"),
    ("a variable in a non-PR path passes", "Bash", 'gh api -X POST "repos/o/x/issues/$N/comments" -f body=x', GO, "pass"),
    ("glab --repo value before api", "Bash", "glab --repo g/mlg api projects/:fullpath/merge_requests -X POST", GO, "deny"),
    ("glab --repo=value before api", "Bash", "glab --repo=g/mlg api projects/:fullpath/merge_requests -X POST", GO, "deny"),
    ("a multi-segment variable in repos/$R/pulls gives a note", "Bash", 'gh api -X POST "repos/$R/pulls" -f title=x', GO, "note"),
    ("a braced variable gives a note", "Bash", 'gh api -X POST "repos/${R}/pulls" -f title=x', GO, "note"),
    ("a leading $BASE/pulls gives a note", "Bash", 'gh api -X POST "$BASE/pulls" -f title=x', GO, "note"),
    ("a leading $API/repos/o/mlg/pulls gives a note", "Bash", 'gh api -X POST "$API/repos/o/mlg/pulls" -f title=x', GO, "note"),
    ("a trailing variable in repos/o/$P gives a note", "Bash", 'gh api -X POST "repos/o/$P" -f title=x', GO, "note"),
    ("glab projects/$G/$R/merge_requests gives a note", "Bash", 'glab api -X POST "projects/$G/$R/merge_requests"', GO, "note"),
    ("a literal that rules out every shape passes", "Bash", 'gh api -X POST "repos/o/x/issues/$N/comments/$M" -f body=x', GO, "pass"),
    ("a method from a variable on a creation path gives a note", "Bash", 'gh api -X "$M" repos/o/mlg/pulls -f t=x', GO, "note"),
    ("a method from a variable on another path passes", "Bash", 'gh api -X "$M" repos/o/mlg/issues -f t=x', GO, "pass"),
    ("a 2000-segment all-expansion path gives a note, no crash", "Bash",
     'gh api -X POST "' + "/".join(["$X"] * 2000) + '" -f t=x', GO, "note"),
    ("a path longer than the cap with a literal gives a note", "Bash",
     'gh api -X POST "' + "/".join(["$X"] * 65 + ["issues"]) + '" -f t=x', GO, "note"),
    ("a project-configured repo passes unnamed", MCP, "mlg", transcript(PROJECT_BRIEF, "go"), "pass"),
    ("a project-configured repo passes by URL case", MCP, "MLG", transcript(PROJECT_BRIEF, "go"), "pass"),
    ("a repo outside the project list is denied", MCP, "epi204", transcript(PROJECT_BRIEF, "go"), "deny"),
    ("a same-name repo of another owner is denied", "Bash", "gh pr create -R other/mlg", transcript(PROJECT_BRIEF, "go"), "deny"),
    ("a repo the coordinator's note names passes", MCP, "epi204", transcript(RELAY_BRIEF, "go"), "pass"),
    ("a repo the user's cited message names passes", MCP, "epi205", transcript(RELAY_BRIEF, "go"), "pass"),
    ("a repo the relay never names is denied", MCP, "epi206", transcript(RELAY_BRIEF, "go"), "deny"),
    ("a project list in a later prompt does not count", MCP, "mlg", transcript("go", PROJECT_BRIEF), "deny"),
    ("a relay note in a later prompt does not count", MCP, "epi204", transcript("go", RELAY_BRIEF), "deny"),
    ("a note outside a coordinator relay does not count", MCP, "epi204",
     transcript('<relay from="agent" session="x"><note>Open it in epi204</note></relay>', "go"), "deny"),
    ("an html-escaped project list counts", MCP, "mlg", transcript(PROJECT_BRIEF.replace("<", "&lt;"), "go"), "pass"),
    ("a missing transcript gives a note", MCP, "mlg", os.path.join(TMP, "none.jsonl"), "note"),
    ("no user message gives a note", MCP, "mlg", transcript({"type": "assistant", "message": {}}), "note"),
]
for name, tool, inp, tpath, want, *cwd in CASES + [("the hook-environment grant", MCP, "mlg", GO, "pass")]:
    CASE_ENV = {"ALLOW_UNNAMED_REPO_PR": "1"} if name == "the hook-environment grant" else (
        {"GH_REPO": "o/mlg"} if "hook-environment GH_REPO" in name else
        {"GITLAB_REPO": "g/s/mlg" if "nested" in name else "g/mlg"} if "hook-environment" in name and "GITLAB_REPO" in name
        else {})
    got = verdict(tool, inp, tpath, *cwd)
    failures += got != want
    print(("PASS: " if got == want else f"FAIL (got {got}, want {want}): ") + name)

MUTATIONS = [  # each must fail this suite; skipped inside a mutant run
    ("named() matches anything", "    return any(rx.search(t) for t in texts)", "    return True"),
    ("isMeta records count", "rec.get(\"isMeta\") or rec.get(\"isSidechain\")", "rec.get(\"isSidechain\")"),
    ("keywords not stripped", "    while argv and argv[0] in SHELL_KEYWORDS:", "    while False:"),
    ("upstream not preferred", "(\"upstream\", \"github\", \"origin\")", "(\"origin\", \"upstream\", \"github\")"),
    ("a value flag ends no cluster", "                    flags.append((flag, val))\n                    break",
     "                    flags.append((flag, val))"),
    ("= after an attached shorthand kept", 'val = arg[k + 1:].removeprefix("=")', "val = arg[k + 1:]"),
    ("-- is not end-of-flags", "positionals, i = positionals + args[i:], len(args)", "positionals, i = positionals, i"),
    ("a flag taken as the endpoint", 'elif not arg.startswith("-") or arg == "-":', "elif True:"),
    ("implied POST removed", "post = bool(bodies) if not methods", "post = False if not methods"),
    ("a method expansion read as not POST", "None if re.search(r\"[$`]\", methods[-1]) else", "False if re.search(r\"[$`]\", methods[-1]) else"),
    ("the expansion length cap removed", "    if len(parts) > MAX_EXPANSION_PARTS:", "    if False:"),
    ("an expansion stands for exactly one segment", "return fits(shape, i, j + 1) or fits(shape, i + 1, j)", "return fits(shape, i + 1, j + 1)"),
    ("placeholder resolution dropped", "    if not any(x in fills for x in elems):", "    if True:"),
    ("URL normalisation dropped", "urlsplit(endpoint).path if url else", "endpoint if url else"),
    ("unreadable graphql body ignored", "* unreadable_body(bodies)", "* False"),
    ("hook-environment repo variable ignored", "key = _key(repo or os.environ.get(var)) if (repo or os.environ.get(var)) else gh_target(cur)",
     "key = _key(repo) if repo else gh_target(cur)"),
    ("glab reads GH_REPO", "var = REPO_ENV[prog[0]]", 'var = "GH_REPO"'),
    ("elsewhere note dropped", "if not repo and elsewhere:", "if False:"),
    ("-R not a repo flag", '"-R": "repo"', '"-R": ""'),
    ("-R does not win", "repo = flag_repo or env_value(lead, var)", "repo = env_value(lead, var)"),
    (":owner not filled for gh", 'fills.update({":owner": 0} if prog[0] == "gh" else {})', "fills.update({})"),
    ("unknown flags never noted", "for f in unknown[:1]]", "for f in []]"),
    ("hidden positionals ignored", "for p in positionals[1:] if unknown", "for p in positionals[1:] if False"),
    ("a repo named api/v3 is stripped", 'parts[i + 2:i + 3] in (["repos"], ["projects"], ["graphql"])', "True"),
    ("host path prefix not skipped", "if (url or i == 0) and", "if (i == 0) and"),
    ("empty segments kept", 'parts = [x for x in path.split("/") if x]', 'parts = path.split("/")'),
    ("compounds not rewritten", "for compound in COMPOUND_PLACEHOLDERS:", "for compound in ():"),
    ("compounds shortest first", 'COMPOUND_PLACEHOLDERS = (":group/:namespace/:repo", ":namespace/:repo")',
     'COMPOUND_PLACEHOLDERS = (":namespace/:repo", ":group/:namespace/:repo")'),
    ("glab globals not moved", 'return prog[:1] + rest[:k] + moved + rest[k:] if', "return prog if"),
    ("glab globals appended, not inserted", "rest[:k] + moved + rest[k:] if prog", "rest + moved if prog"),
    ("attached -R value ignored", 'if flag.startswith("-R") else', "if False else"),
    ("expansion note ignores the path shape", "if post is not False and expands(parts):",
     'if post is not False and any(re.search(r"[$`]", x) for x in parts):'),
    ("query not cut", 'else re.split(r"[?#]", endpoint or "", 1)[0]', 'else (endpoint or "")'),
    ("unreadable endpoint passes", "if post is not False and expands(parts):", "if False:"),
    ("glab --form not a body flag", '"--form": "body"', '"--form": ""'),
    ("unknown placeholder passes", 'if any(x.startswith(":") and x not in fills for x in elems):', "if False:"),
    ("fragment not cut", 'else re.split(r"[?#]", endpoint', 'else re.split(r"[?]", endpoint'),
    ("glab graphql mutation name", 'else "mergeRequestCreate"', 'else "createPullRequest"'),
    ("project keys ignored", "k != home and k not in project and", "k != home and"),
    ("relay notes ignored", "texts = texts + brief", "texts = texts"),
    ("any prompt counts as the first", '(prompts[:1] or [""])[0]', '" ".join(prompts)'),
    ("any relay author counts", r'\bfrom=\"coordinator\"', r'\bfrom=\"[a-z]+\"'),
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
