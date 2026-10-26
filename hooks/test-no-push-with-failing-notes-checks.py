#!/usr/bin/env python3
"""Test the no-push-with-failing-notes-checks guard.

Uses a stub gha checkout (GHA_CHECKS_DIR) whose scripts record their environment and
exit with the code in the repo's `.stub-exit` file, so the test pins the guard's
wiring (workflow parsing, env mapping, deny, bypass, fail-open) without network.
Set GHA_REAL_DIR to a real gha checkout to also run the two real scripts.

Run: python3 hooks/test-no-push-with-failing-notes-checks.py hooks/no-push-with-failing-notes-checks.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath("hooks/no-push-with-failing-notes-checks.py")
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e.com",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e.com"}
HOME = tempfile.mkdtemp(prefix="npc-home-")

WORKFLOW = """name: Check term links
on:
  pull_request:
jobs:
  check:
    uses: Morrison-Lab/gha/.github/workflows/check-term-links.yml@v3
    with:
      runs-on: ${{ vars.CI_RUNNER || 'ubuntu-latest' }}
      paths-ignore: '_extensions/**,chapters/outtakes/**'
      whole-tree: ${{ github.event_name == 'workflow_dispatch' }}
"""
NLB = """name: nlb
on:
  pull_request:
jobs:
  check:
    uses: Morrison-Lab/gha/.github/workflows/check-new-line-breaks.yml@v3
    with:
      globs: '*.md *.qmd'
      fail: true
"""
STUB = """import json, os, sys
open(os.path.join(os.environ["STUB_LOG"], os.path.basename(__file__) + ".env"), "w", encoding="utf-8").write(
    json.dumps({k: v for k, v in os.environ.items() if k.startswith(("TERM_LINKS_", "NLB_"))}))
code = int(open(".stub-exit", encoding="utf-8").read().strip()) if os.path.exists(".stub-exit") else 0
if code:
    print("::error file=chapters/a.qmd,line=3::unlinked-first-use: model")
sys.exit(code)
"""


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, env=ENV, check=True).stdout.strip()


def make_repo(workflows):
    d = tempfile.mkdtemp(prefix="npc-repo-")
    git(d, "init", "-q", "-b", "main")
    os.makedirs(os.path.join(d, ".github", "workflows"))
    for name, text in workflows.items():
        open(os.path.join(d, ".github", "workflows", name), "w", encoding="utf-8").write(text)
    open(os.path.join(d, "a.qmd"), "w", encoding="utf-8").write("x\n")
    git(d, "add", "-A"); git(d, "commit", "-qm", "init")
    git(d, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(d, "checkout", "-q", "-b", "feat")
    open(os.path.join(d, "a.qmd"), "w", encoding="utf-8").write("y\n")
    git(d, "commit", "-qam", "change")
    return d


def stub_dir():
    g = tempfile.mkdtemp(prefix="npc-gha-")
    for sub, name in (("check-term-links", "check-term-links.py"), ("check-new-line-breaks", "check-new-line-breaks.py")):
        os.makedirs(os.path.join(g, sub))
        open(os.path.join(g, sub, name), "w", encoding="utf-8").write(STUB)
    return g


GHA = stub_dir()
LOG = tempfile.mkdtemp(prefix="npc-log-")
fails = []


def run(command, cwd, exit_code=0, gha=GHA, extra=None):
    open(os.path.join(cwd, ".stub-exit"), "w", encoding="utf-8").write(str(exit_code))
    env = {**os.environ, "HOME": HOME, "STUB_LOG": LOG, **({"GHA_CHECKS_DIR": gha} if gha else {}), **(extra or {})}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
                       capture_output=True, text=True, cwd=cwd, env=env)
    if p.returncode != 0:
        sys.exit(f"FATAL exit {p.returncode}: {p.stderr}")
    if not p.stdout.strip():
        return "silent", {}
    out = json.loads(p.stdout)
    hso = out["hookSpecificOutput"]
    return ("DENY" if hso.get("permissionDecision") == "deny" else "NOTE"), out


def expect(label, got, want):
    if got != want:
        fails.append(f"{label}: got {got}, want {want}")
    print(("ok   " if got == want else "FAIL ") + label)


repo = make_repo({"check-term-links.yml": WORKFLOW, "check-new-line-breaks.yml": NLB})
verdict, out = run("git push -u origin feat", repo, 0)
expect("T1 passing checks stay silent", verdict, "silent")
env_tl = json.load(open(os.path.join(LOG, "check-term-links.py.env"), encoding="utf-8"))
expect("T2 term-links gets repo paths-ignore", env_tl.get("TERM_LINKS_PATHS_IGNORE"), "_extensions/**,chapters/outtakes/**")
expect("T3 expression inputs are skipped", "TERM_LINKS_WHOLE_TREE" in env_tl, False)
expect("T4 base ref is origin/main", env_tl.get("TERM_LINKS_BASE_REF"), "origin/main")
expect("T5 fail forced true", env_tl.get("TERM_LINKS_FAIL"), "true")
env_nlb = json.load(open(os.path.join(LOG, "check-new-line-breaks.py.env"), encoding="utf-8"))
expect("T6 nlb globs from repo", env_nlb.get("NLB_GLOBS"), "*.md *.qmd")
expect("T7 nlb scope committed", env_nlb.get("NLB_SCOPE"), "committed")

verdict, out = run("git push origin feat", repo, 1)
expect("T8 failing check denies", verdict, "DENY")
reason = out["hookSpecificOutput"]["permissionDecisionReason"]
expect("T9 reason names finding and bypass", ("unlinked-first-use" in reason, "AI_CONFIG_SKIP_PUSH_CHECKS" in reason), (True, True))

verdict, _ = run("git status", repo, 1)
expect("T10 non-push is silent", verdict, "silent")
verdict, _ = run("git push origin --delete feat", repo, 1)
expect("T11 branch delete is silent", verdict, "silent")

verdict, _ = run("AI_CONFIG_SKIP_PUSH_CHECKS=1 git push origin feat", repo, 1)
expect("T12 bare flag bypass is refused", verdict, "DENY")
verdict, out = run("AI_CONFIG_SKIP_PUSH_CHECKS='CI runner outage' git push origin feat", repo, 1)
expect("T13 reasoned bypass allows with a note", verdict, "NOTE")
logf = os.path.join(HOME, ".cache", "ai-config", "push-check-bypass.log")
entry = json.loads(open(logf, encoding="utf-8").read().splitlines()[-1])
expect("T14 bypass is logged with its reason", entry["reason"], "CI runner outage")

verdict, _ = run("git push origin feat", repo, 1, gha="/nonexistent-gha")
expect("T15 unreachable gha fails open with a note", verdict, "NOTE")

plain = make_repo({})
verdict, _ = run("git push origin feat", plain, 1)
expect("T16 repo without gha check callers is silent", verdict, "silent")

same = make_repo({"check-term-links.yml": WORKFLOW})
git(same, "reset", "-q", "--hard", "origin/main")
verdict, _ = run("git push origin feat", same, 1)
expect("T17 nothing ahead of origin/main is silent", verdict, "silent")

real = os.environ.get("GHA_REAL_DIR")
if real:
    r = make_repo({"check-new-line-breaks.yml": NLB})
    open(os.path.join(r, "bad.md"), "w", encoding="utf-8").write("# T\n\nFirst sentence. Second sentence on the same line.\n")
    git(r, "add", "-A"); git(r, "commit", "-qm", "bad")
    verdict, _ = run("git push origin feat", r, 0, gha=real)
    expect("R1 real nlb script denies a packed line", verdict, "DENY")

if fails:
    sys.exit("FAILED:\n" + "\n".join(fails))
print("all passed")
