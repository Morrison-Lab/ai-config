#!/usr/bin/env python3
"""Test suite for hooks/enforce-mwc-review-gate.py.

Verifies that enforce-mwc-review-gate.py correctly enforces review gating
under both Claude Code (Bash & MCP payloads) and Antigravity (run_command payloads),
emits the dual-compatible output shape (decision + hookSpecificOutput),
and handles GitLab merges, GraphQL mutations, chained merges, and auto-merge tools.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and os.path.isfile(sys.argv[1])
    else str(Path(__file__).parent / "enforce-mwc-review-gate.py")
)

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")

spec = importlib.util.spec_from_file_location("enforce_mwc_review_gate", HOOK)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

HEAD = "8d7864c66c90ce495ae53deeaa8f1e86f3cf18b7"

# The mwr cases merge Morrison-Lab/psw, an owner the standing infra-PR grant
# covers, so the grant would read the PR's files from GitHub (round 10). It
# stays off unless a case serves the files from `infra_gh` below.
os.environ["NO_UNAUTHORIZED_MERGE_DISABLE_INFRA_GRANT"] = "1"

# A `gh` stand-in for the infra-PR grant's two reads, served from
# FAKE_INFRA_FILES (a JSON list of paths) and FAKE_INFRA_HEAD.
_INFRA_GH_DIR = tempfile.TemporaryDirectory()
_INFRA_GH = r'''#!/usr/bin/env python3
import json, os, sys
files = json.loads(os.environ.get("FAKE_INFRA_FILES") or "[]")
args = [a for a in sys.argv[1:] if a != "--paginate"]
path = args[1] if len(args) > 1 and args[0] == "api" else ""
if path.endswith("/files?per_page=100"):
    print("\n".join("F\t" + f for f in files))
elif "/pulls/" in path and "--jq" in args:
    print(f"{len(files)}\n{os.environ['FAKE_INFRA_HEAD']}")
else:
    sys.exit(1)
'''
with open(os.path.join(_INFRA_GH_DIR.name, "gh"), "w") as _fh:
    _fh.write(_INFRA_GH)
os.chmod(os.path.join(_INFRA_GH_DIR.name, "gh"), 0o755)


def infra_gh(files):
    """Turn the infra-PR grant on, its reads served by the fake `gh`."""
    env = dict(os.environ, FAKE_INFRA_FILES=json.dumps(files), FAKE_INFRA_HEAD=HEAD,
               PATH=_INFRA_GH_DIR.name + os.pathsep + os.environ.get("PATH", ""))
    env.pop("NO_UNAUTHORIZED_MERGE_DISABLE_INFRA_GRANT")
    return patch.dict(os.environ, env, clear=True)

checks = 0
failures = []


def check(desc: str, condition: bool, detail: str = ""):
    global checks
    checks += 1
    if condition:
        print(f"  ok: {desc}")
    else:
        print(f"  FAIL: {desc} {detail}")
        failures.append(f"{desc}: {detail}")


def run_main(payload_dict_or_str: dict | str, argv: list[str] | None = None) -> dict:
    inp = payload_dict_or_str if isinstance(payload_dict_or_str, str) else json.dumps(payload_dict_or_str)
    args = argv or ["enforce-mwc-review-gate.py"]
    captured = io.StringIO()
    with patch("sys.stdin", io.StringIO(inp)), patch("sys.argv", args), patch("sys.stdout", captured):
        gate.main()
    val = captured.getvalue().strip()
    return json.loads(val) if val else {}


def clean_pr_state():
    return {
        "url": "https://github.com/Morrison-Lab/ai-config/pull/123",
        "headRefOid": HEAD,
        "author": {"login": "someone"},
        "reviews": [],
        "comments": [
            {
                "author": {"login": "github-actions"},
                "body": (
                    "**Claude finished review**\n\n"
                    "### Verdict\n"
                    "**Ready for merge** --- all prior findings addressed.\n\n"
                    f"Reviewed commit: {HEAD}"
                ),
                "createdAt": "2026-10-07T12:00:00Z",
            }
        ],
        "reviewComments": [],
        "statusCheckRollup": [
            {
                "name": "test",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            }
        ],
    }


def not_clean_pr_state():
    return {
        "url": "https://github.com/Morrison-Lab/ai-config/pull/123",
        "headRefOid": HEAD,
        "author": {"login": "someone"},
        "reviews": [],
        "comments": [
            {
                "author": {"login": "github-actions"},
                "body": f"### Verdict\nNeeds more work\nReviewed commit: `{HEAD}`\n",
                "createdAt": "2026-10-07T12:00:00Z",
            }
        ],
        "reviewComments": [],
        "statusCheckRollup": [
            {
                "name": "test",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            }
        ],
    }


MWR_REPO = "Morrison-Lab/psw"
# The plugin root the clean-checker hook trusts for an mwr merge (round 4,
# finding 2): a fixture checkout whose checker blob is origin/main's.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                                "scripts", "lib"))
from mwr_checker_fixture import trusted_checker_root  # noqa: E402

_MWR_ROOT_DIR = tempfile.TemporaryDirectory()
MWR_ROOT = trusted_checker_root(_MWR_ROOT_DIR.name)
os.environ["CLAUDE_PLUGIN_ROOT"] = MWR_ROOT


def mwr_ready_line(sha=HEAD, n=123, repo=MWR_REPO):
    """The checker's `--mwr` pass line (ai-config#3946)."""
    return (f"✅ {repo}#{n} is MERGE-READY under mwr (review not evaluated) "
            f"on HEAD {sha}! [stale-base rule]")


def mwr_transcript(tmp, steps):
    """A transcript of ("user", text) and ("checker", output) steps."""
    path = os.path.join(tmp, "transcript-mwr.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for i, (kind, text) in enumerate(steps):
            if kind == "user":
                fh.write(json.dumps({"type": "user", "message": {
                    "role": "user", "content": text}}) + "\n")
                continue
            tid = f"toolu_mwr_{i}"
            # Run from the repository root, so the script is the plugin
            # root's own checker (round 3, finding 2).
            fh.write(json.dumps({"type": "assistant", "cwd": MWR_ROOT, "message": {"content": [{
                "type": "tool_use", "id": tid, "name": "Bash", "input": {
                    "command": f"python3 scripts/check-pr-fully-clean.py 123 -R {MWR_REPO} --mwr"}}]}})
                     + "\n")
            fh.write(json.dumps({"type": "user", "message": {"content": [{
                "type": "tool_result", "tool_use_id": tid,
                "content": [{"type": "text", "text": text}]}]}}) + "\n")
    return path


MAIN_BASE = "b" * 40
DECOY_BASE = "d" * 40


def live_gh(head=HEAD, base=MAIN_BASE, reviews=None, compare=None, fail=()):
    """A `run_gh` stand-in for the gate's merge-time mwr reads (round 7).

    `compare` maps a base sha to the changed files of
    `compare/<base>...<head>`, as (filename, previous_filename) pairs. A path
    containing any string in `fail` answers non-zero.
    """
    reviews = [] if reviews is None else reviews
    compare = {MAIN_BASE: [("src/a.py", None)], DECOY_BASE: [("src/a.py", None)]} \
        if compare is None else compare

    def run(args, cwd):
        path = args[1] if len(args) > 1 else ""
        if any(f in path for f in fail):
            return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 502")
        if path.endswith("/pulls/123"):
            body = {"head": {"sha": head}, "base": {"sha": base, "ref": "main"}}
        elif "/pulls/123/reviews" in path:
            body = reviews
        elif "/compare/" in path:
            spec = path.split("/compare/", 1)[1].split("?", 1)[0]
            left, _, right = spec.partition("...")
            if right != HEAD or left not in compare:
                return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 404")
            body = {"files": [dict({"filename": n}, **({"previous_filename": p} if p else {}))
                              for n, p in compare[left]]}
        else:
            return SimpleNamespace(returncode=1, stdout="", stderr=f"unexpected {path}")
        return SimpleNamespace(returncode=0, stdout=json.dumps(body), stderr="")
    return run


def mwr_decision(steps, state, bash=False, command=None, tool=None, direct=False, live=None,
                 merge_input=None):
    """The gate's decision on a merge of MWR_REPO#123 at HEAD, given `steps`.

    `command` is a Bash merge command to use instead of the default one, and
    `tool` an MCP tool name to use instead of merge_pull_request. With
    `direct`, `command` goes straight to `decide()`, for a route `main()`
    does not itself read as a merge. `live` is the `run_gh` stand-in for the
    merge-time mwr reads; by default a clean live state (`live_gh()`).
    `merge_input` replaces the default merge_pull_request input.
    """
    with patch.object(gate, "run_gh", live or live_gh()):
        return _mwr_decision(steps, state, bash, command, tool, direct, merge_input)


def _mwr_decision(steps, state, bash, command, tool, direct, merge_input=None):
    import tempfile
    # The PR merged is MWR_REPO#123, which no standing grant covers (round 10).
    state = dict(state, url=f"https://github.com/{MWR_REPO}/pull/123")
    with tempfile.TemporaryDirectory() as tmp:
        path = mwr_transcript(tmp, steps)
        if direct:
            payload = {"tool_name": "Bash", "transcript_path": path,
                       "tool_input": {"command": command}}
            return gate.decide(command, state, False, payload).get("decision")
        if command is not None:
            payload = {"tool_name": "Bash", "transcript_path": path,
                       "tool_input": {"command": command}}
        elif tool is not None:
            payload = {"tool_name": tool, "transcript_path": path,
                       "tool_input": {"owner": "Morrison-Lab", "repo": "psw",
                                      "pull_number": 123, "pullNumber": 123,
                                      "expectedHeadSha": HEAD}}
        elif bash:
            payload = {"tool_name": "Bash", "transcript_path": path, "tool_input": {
                "command": f"gh pr merge 123 -R {MWR_REPO} --squash --match-head-commit {HEAD}"}}
        else:
            payload = {"tool_name": "mcp__github__merge_pull_request", "transcript_path": path,
                       "tool_input": merge_input or {"owner": "Morrison-Lab", "repo": "psw",
                                                     "pullNumber": 123, "expectedHeadSha": HEAD}}
        with patch.object(gate, "fetch_pr_data") as mock_fetch:
            mock_fetch.return_value = (state, None)
            out = run_main(payload)
            _MWR_LAST.clear()
            _MWR_LAST.update(out)
            return out.get("decision")


# The whole output of the last `_mwr_decision` that ran `main()`.
_MWR_LAST = {}


def last_denied_for_route():
    """Whether the last mwr decision was the round-12 route denial, which
    names the MCP merge tool and its `expectedHeadSha` pin."""
    reason = _MWR_LAST.get("reason", "")
    return (_MWR_LAST.get("decision") == "deny" and "under `mwr`" in reason
            and "mcp__github__merge_pull_request" in reason and "expectedHeadSha" in reason)


def mwr_checks():
    """The `mwr` grant: a review-only deny lifts on a MERGE-READY line (ai-config#3946)."""
    ready = ("checker", mwr_ready_line())
    # Round 3, finding 8: an auto-merge never skips review under mwr,
    # with or without mwc active.
    auto = f"gh pr merge 123 -R {MWR_REPO} --squash --auto --match-head-commit {HEAD}"
    check("mwr: `gh pr merge --auto` over a not-clean verdict denies under 'mwrs'",
          mwr_decision([("user", "mwrs"), ready], not_clean_pr_state(), command=auto) == "deny")
    check("mwr: `gh pr merge --auto` denies under 'mwrs' with mwc also active",
          mwr_decision([("user", "mwc"), ("user", "mwrs"), ready], not_clean_pr_state(),
                       command=auto) == "deny")
    check("mwr: the MCP auto-merge tool denies under 'mwrs'",
          mwr_decision([("user", "mwrs"), ready], not_clean_pr_state(),
                       tool="mcp__github__enable_pull_request_auto_merge") == "deny")
    ccr = (f"gh api -X PUT repos/{MWR_REPO}/pulls/123/ccr/auto_merge "
           f"-f sha={HEAD} -f merge_method=squash")
    check("mwr: the ccr/auto_merge route over a not-clean verdict denies under 'mwrs'",
          mwr_decision([("user", "mwc"), ("user", "mwrs"), ready], not_clean_pr_state(),
                       command=ccr, direct=True) == "deny")
    # Round 4: a bare "name#N" means Morrison-Lab/name, with or without a cwd,
    # and a repo-less "#N" grants nothing.
    check("mwr: 'mwr psw#123' with no recorded cwd allows (Morrison-Lab/psw#123)",
          mwr_decision([("user", "mwr psw#123"), ready], not_clean_pr_state()) == "allow")
    check("mwr: a repo-less 'mwr #123' denies",
          mwr_decision([("user", "mwr #123"), ready], not_clean_pr_state()) == "deny")
    check("mwr: MCP merge over a not-clean verdict allows with 'mwr' and a MERGE-READY line",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ready], not_clean_pr_state()) == "allow")
    # Round 11: the server merges `pullNumber`, so a granted `pull_number`
    # beside a different `pullNumber` denies; agreeing keys still allow.
    _psw = {"owner": "Morrison-Lab", "repo": "psw", "expectedHeadSha": HEAD}
    check("mwr: 'mwr psw#123' with pull_number=123, pullNumber=124 denies",
          mwr_decision([("user", "mwr psw#123"), ready], not_clean_pr_state(),
                       merge_input=dict(_psw, pull_number=123, pullNumber=124)) == "deny")
    # Round 12: under mwr alone the MCP input is strict, so an agreeing
    # extra key denies; under mwc it still allows.
    check("mwr: 'mwr psw#123' with matching pull_number and pullNumber denies (strict input)",
          mwr_decision([("user", "mwr psw#123"), ready], not_clean_pr_state(),
                       merge_input=dict(_psw, pull_number=123, pullNumber=123)) == "deny"
          and last_denied_for_route())
    check("mwr: 'mwr psw#123' with pullNumber alone allows",
          mwr_decision([("user", "mwr psw#123"), ready], not_clean_pr_state(),
                       merge_input=dict(_psw, pullNumber=123)) == "allow")
    check("mwr: 'mwr psw#123' with a digit-string pullNumber and the full key set allows",
          mwr_decision([("user", "mwr psw#123"), ready], not_clean_pr_state(),
                       merge_input=dict(_psw, pullNumber="123", merge_method="squash",
                                        commit_title="t", commit_message="m")) == "allow")
    for _desc, _inp in [
        ("expected_head_sha in place of expectedHeadSha",
         {"owner": "Morrison-Lab", "repo": "psw", "pullNumber": 123, "expected_head_sha": HEAD}),
        ("an extra key", dict(_psw, pullNumber=123, sha=HEAD)),
        ("a 16-hex sha", dict(_psw, pullNumber=123, expectedHeadSha=HEAD[:16])),
        ("an uppercase sha", dict(_psw, pullNumber=123, expectedHeadSha=HEAD.upper())),
    ]:
        check(f"mwr: 'mwrs' with {_desc} denies, naming the MCP route",
              mwr_decision([("user", "mwrs"), ready], not_clean_pr_state(),
                           merge_input=_inp) == "deny" and last_denied_for_route())
    check("mwc: matching pull_number and pullNumber is unchanged under mwc (no route denial)",
          mwr_decision([("user", "mwc"), ("checker", "")], clean_pr_state(),
                       merge_input=dict(_psw, pull_number=123, pullNumber=123),
                       live=live_gh(fail=("/",))) == "allow")
    # Round 12: under mwr alone a shell merge is refused, naming the MCP tool.
    check("mwr: Bash `gh pr merge` under 'mwrs' with a MERGE-READY line denies, naming MCP",
          mwr_decision([("user", "mwrs"), ready], not_clean_pr_state(), bash=True) == "deny"
          and last_denied_for_route())
    decoy = (f"gh api -X PUT repos/{MWR_REPO}/pulls/124/merge "
             f"-f note=repos/{MWR_REPO}/pulls/123/merge -f sha={HEAD}")
    check("mwr: `gh api` with a decoy pulls/123/merge field under 'mwrs' denies, naming MCP",
          mwr_decision([("user", "mwrs"), ready], not_clean_pr_state(), command=decoy) == "deny"
          and last_denied_for_route())
    check("mwc: Bash `gh pr merge` is unchanged under mwc (allows a clean PR)",
          mwr_decision([("user", "mwc"), ("checker", "")], clean_pr_state(), bash=True,
                       live=live_gh(fail=("/",))) == "allow")
    no_verdict = not_clean_pr_state()
    no_verdict["comments"] = []
    check("mwr: a PR with no review at all allows with 'mwr' and a MERGE-READY line",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ready], no_verdict) == "allow")
    in_flight = not_clean_pr_state()
    in_flight["reviewRequests"] = [{"login": "someone-else"}]
    check("mwr: a review still requested does not block under 'mwr'",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ready], in_flight) == "allow")
    check("mwr: a bare 'mwr' names no PR, so it denies",
          mwr_decision([("user", "mwr"), ready], not_clean_pr_state()) == "deny")
    check("mwr: a message that only mentions mwr denies",
          mwr_decision([("user", "mwr psw#123 would skip review, explain first"), ready],
                       not_clean_pr_state()) == "deny")
    check("mwr: a MERGE-READY line with no mwr grant denies",
          mwr_decision([ready], not_clean_pr_state()) == "deny")
    check("mwr: a MERGE-READY line under 'mwc' only denies",
          mwr_decision([("user", "mwc"), ready], not_clean_pr_state()) == "deny")
    check("mwr: a MERGE-READY line under 'merge when ready' denies",
          mwr_decision([("user", "merge when ready"), ready], not_clean_pr_state()) == "deny")
    check("mwr: 'mwr' with no MERGE-READY line denies",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ("checker", "NOT fully clean")],
                       not_clean_pr_state()) == "deny")
    check("mwr: a MERGE-READY line for an older head denies",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ("checker", mwr_ready_line("0" * 40))],
                       not_clean_pr_state()) == "deny")
    check("mwr: a revocation after 'mwr' denies",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ready, ("user", "stop merging")],
                       not_clean_pr_state()) == "deny")
    check("mwr: a question about mwr is no grant",
          mwr_decision([("user", "what does mwr mean?"), ready], not_clean_pr_state()) == "deny")
    check("mwr: a named 'mwr psw#99' does not cover #123",
          mwr_decision([("user", "mwr Morrison-Lab/psw#99"), ready], not_clean_pr_state()) == "deny")
    formal = not_clean_pr_state()
    formal["reviews"] = [{"author": {"login": "maintainer"}, "state": "CHANGES_REQUESTED",
                          "body": "", "authorAssociation": "MEMBER", "commit": {"oid": HEAD}}]
    check("mwr: a formal CHANGES_REQUESTED review still denies",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ready], formal) == "deny")
    red = not_clean_pr_state()
    red["statusCheckRollup"] = [{"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"}]
    check("mwr: failing CI still denies",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ready], red) == "deny")
    pending = not_clean_pr_state()
    pending["statusCheckRollup"] = [{"name": "test", "status": "IN_PROGRESS", "conclusion": ""}]
    check("mwr: pending CI still denies",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ready], pending) == "deny")
    threads = not_clean_pr_state()
    threads["reviewThreads"] = [{"isResolved": False, "isOutdated": False, "path": "a.py", "line": 3}]
    check("mwr: an unresolved review thread still denies",
          mwr_decision([("user", "mwr Morrison-Lab/psw#123"), ready], threads) == "deny")
    check("mwr: an unreadable transcript is no grant (fails closed)",
          not gate.mwr_cleared({"transcript_path": "/nonexistent.jsonl"}, not_clean_pr_state()))
    check("mwr: a PR with no URL is no grant (fails closed)",
          not gate.mwr_cleared({"transcript_path": "/nonexistent.jsonl"}, {"headRefOid": HEAD}))
    mwr_live_checks(ready)


def mwr_live_checks(ready):
    """Merge-time re-checks under mwr, on live data (round 7)."""
    grant = ("user", "mwr Morrison-Lab/psw#123")
    check("mwr live: the clean case allows",
          mwr_decision([grant, ready], not_clean_pr_state()) == "allow")
    check("mwr live: the clean case denies on the Bash route, naming MCP (round 12)",
          mwr_decision([("user", "mwrs"), ready], not_clean_pr_state(), bash=True) == "deny"
          and last_denied_for_route())
    # The checker ran while the base was a decoy branch that already held the
    # PR's `.github/` change, so its file list showed none; the base was then
    # retargeted back to main. The live compare against main shows the edit.
    retarget = live_gh(base=MAIN_BASE, compare={
        DECOY_BASE: [("src/a.py", None)],
        MAIN_BASE: [("src/a.py", None), (".github/workflows/ci.yml", None)]})
    check("mwr live: a base retargeted to a decoy and back, showing .github/, denies",
          mwr_decision([grant, ready], not_clean_pr_state(), live=retarget) == "deny")
    check("mwr live: the same PR still on the decoy base would allow (control)",
          mwr_decision([grant, ready], not_clean_pr_state(),
                       live=live_gh(base=DECOY_BASE, compare={
                           DECOY_BASE: [("src/a.py", None)]})) == "allow")
    renamed = live_gh(compare={MAIN_BASE: [("ci/build.yml", ".github/workflows/build.yml")]})
    check("mwr live: a rename out of .github/ denies (previous name counts)",
          mwr_decision([grant, ready], not_clean_pr_state(), live=renamed) == "deny")
    dismissed = live_gh(reviews=[
        {"state": "DISMISSED", "user": {"login": "maintainer"}},
        {"state": "COMMENTED", "user": {"login": "maintainer"}}])
    check("mwr live: a review dismissed after the checker run denies, MERGE-READY line notwithstanding",
          mwr_decision([grant, ready], not_clean_pr_state(), live=dismissed) == "deny")
    superseded = live_gh(reviews=[
        {"state": "CHANGES_REQUESTED", "user": {"login": "maintainer"}},
        {"state": "APPROVED", "user": {"login": "maintainer"}}])
    check("mwr live: an earlier CHANGES_REQUESTED denies though a later review approves",
          mwr_decision([grant, ready], not_clean_pr_state(), live=superseded) == "deny")
    check("mwr live: an unreadable compare denies",
          mwr_decision([grant, ready], not_clean_pr_state(),
                       live=live_gh(fail=("/compare/",))) == "deny")
    check("mwr live: unreadable reviews deny",
          mwr_decision([grant, ready], not_clean_pr_state(),
                       live=live_gh(fail=("/reviews",))) == "deny")
    check("mwr live: an empty compare file list denies",
          mwr_decision([grant, ready], not_clean_pr_state(),
                       live=live_gh(compare={MAIN_BASE: []})) == "deny")
    check("mwr live: a live head that moved past the pinned sha denies",
          mwr_decision([grant, ready], not_clean_pr_state(),
                       live=live_gh(head="c" * 40)) == "deny")
    check("mwr live: no live data at all denies (evaluate fails closed)",
          gate.evaluate("gh pr merge 123", not_clean_pr_state(), mwr=True)["decision"] == "deny")
    check("mwr live: the mwc path never reads the live mwr data",
          mwr_decision([("user", "mwc"), ("checker", "")], clean_pr_state(),
                       live=live_gh(fail=("/",))) == "allow")
    ordinary_allow_checks(grant, ready)


def stale_approved_state():
    """A PR the ordinary gate allows on a formal APPROVED for an older commit."""
    state = not_clean_pr_state()
    state["comments"] = []
    state["reviews"] = [{"author": {"login": "maintainer"}, "state": "APPROVED", "body": "",
                         "authorAssociation": "MEMBER", "commit": {"oid": "0" * 40},
                         "submittedAt": "2026-10-01T00:00:00Z"}]
    return state


def mwr_only_fully_clean_checks(grant, ready, clean_line):
    """Round 9: under an mwr grant with no mwc grant, a FULLY CLEAN line does
    not skip the live re-checks; under mwc as well, it does."""
    ci_edit = live_gh(compare={MAIN_BASE: [("src/a.py", None), (".github/workflows/ci.yml", None)]})
    for route, bash in (("MCP", False), ("gh pr merge", True)):
        check(f"mwr only: FULLY CLEAN without MERGE-READY, live .github/ change, "
              f"denies on the {route} route",
              mwr_decision([grant, clean_line], stale_approved_state(), bash=bash,
                           live=ci_edit) == "deny")
        check(f"mwr only: FULLY CLEAN and MERGE-READY, live .github/ change, "
              f"denies on the {route} route",
              mwr_decision([grant, ready, clean_line], stale_approved_state(), bash=bash,
                           live=ci_edit) == "deny")
        check(f"mwr only: FULLY CLEAN and MERGE-READY, DISMISSED review, "
              f"denies on the {route} route",
              mwr_decision([grant, ready, clean_line], clean_pr_state(), bash=bash,
                           live=live_gh(reviews=[{"state": "DISMISSED",
                                                  "user": {"login": "maintainer"}}])) == "deny")
        # Round 12: under mwr alone the gh route is refused outright.
        want = "deny" if bash else "allow"
        check(f"mwr only: FULLY CLEAN and MERGE-READY, clean live data, "
              f"{want}s on the {route} route",
              mwr_decision([grant, ready, clean_line], stale_approved_state(),
                           bash=bash) == want and (not bash or last_denied_for_route()))
        calls = []
        base = live_gh(fail=("/",))

        def counting(args, cwd, calls=calls, base=base):
            calls.append(args)
            return base(args, cwd)
        check(f"mwc and mwr: FULLY CLEAN allows with no live mwr read on the {route} route",
              mwr_decision([("user", "mwc"), grant, ready, clean_line], stale_approved_state(),
                           bash=bash, live=counting) == "allow"
              and not calls)
        check(f"mwc and mwr: FULLY CLEAN allows past a live .github/ change "
              f"on the {route} route (mwc path)",
              mwr_decision([("user", "mwc"), grant, clean_line], clean_pr_state(),
                           bash=bash, live=ci_edit) == "allow")


def round10_checks(clean_line):
    """Round 10: only the user's own authority lifts an mwr grant onto the
    FULLY CLEAN path. The `.mwc` marker, which the agent can write, and
    `ALLOW_MERGE=1`, which the agent can type, do not; a typed mwc, a typed
    named grant and the standing infra-PR grant do."""
    mwrs = ("user", "mwrs")
    ci_edit = live_gh(compare={MAIN_BASE: [(".github/workflows/ci.yml", None)]})
    infra = [".github/workflows/ci.yml"]
    for route, bash in (("MCP", False), ("gh pr merge", True)):
        with infra_gh(infra):
            check(f"mwrs, infra-PR grant: a FULLY CLEAN .github/ PR allows on the {route} route",
                  mwr_decision([mwrs, clean_line], stale_approved_state(), bash=bash,
                               live=ci_edit) == "allow")
        with infra_gh(infra + ["src/a.py"]):
            check(f"mwrs, a PR with a non-infra file: FULLY CLEAN denies on the {route} route",
                  mwr_decision([mwrs, clean_line], stale_approved_state(), bash=bash,
                               live=ci_edit) == "deny")
        check(f"mwrs, infra grant unreadable: FULLY CLEAN denies on the {route} route",
              mwr_decision([mwrs, clean_line], stale_approved_state(), bash=bash,
                           live=ci_edit) == "deny")
        check(f"mwrs and a typed 'merge psw PR 123': FULLY CLEAN allows past a live "
              f".github/ change on the {route} route",
              mwr_decision([mwrs, ("user", "merge psw PR 123"), clean_line],
                           stale_approved_state(), bash=bash, live=ci_edit) == "allow")
        check(f"typed mwc and mwrs: FULLY CLEAN allows past a live .github/ change "
              f"on the {route} route",
              mwr_decision([("user", "mwc"), mwrs, clean_line], stale_approved_state(),
                           bash=bash, live=ci_edit) == "allow")
    allow_cmd = f"ALLOW_MERGE=1 gh pr merge 123 -R {MWR_REPO} --squash --match-head-commit {HEAD}"
    check("mwrs and ALLOW_MERGE=1 on the command: FULLY CLEAN with a live .github/ change denies",
          mwr_decision([mwrs, clean_line], stale_approved_state(), command=allow_cmd,
                       live=ci_edit) == "deny")
    with patch.dict(os.environ, {"ALLOW_MERGE": "1"}):
        check("mwrs and ALLOW_MERGE=1 in the environment: FULLY CLEAN with a live .github/ "
              "change denies",
              mwr_decision([mwrs, clean_line], stale_approved_state(), bash=True,
                           live=ci_edit) == "deny")
    # The `.mwc` marker for this transcript's session (its file stem), as
    # `ai-session.sh enable-mwc` writes it, found through CLAUDE_PROJECT_DIR.
    import subprocess
    with tempfile.TemporaryDirectory() as repo:
        subprocess.run(["git", "init", "-q", repo], check=True)
        reg = os.path.join(repo, ".git", "ai-sessions")
        os.makedirs(reg)
        Path(reg, "transcript-mwr.mwc").write_text("")
        Path(reg, "transcript-mwr.session").write_text(f"pid={os.getpid()}\n")
        old = os.getcwd()
        os.chdir(repo)
        try:
            with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": repo}):
                nua_spec = importlib.util.spec_from_file_location(
                    "_t_nua", str(Path(HOOK).parent / "no-unauthorized-merge.py"))
                nua = importlib.util.module_from_spec(nua_spec)
                nua_spec.loader.exec_module(nua)
                check("marker control: check_mwc_active reads the marker",
                      nua.check_mwc_active({"transcript_path": "/x/transcript-mwr.jsonl"}))
                for route, bash in (("MCP", False), ("gh pr merge", True)):
                    check(f"mwc marker, no typed mwc, mwrs: FULLY CLEAN with a live .github/ "
                          f"change denies on the {route} route",
                          mwr_decision([mwrs, clean_line], stale_approved_state(), bash=bash,
                                       live=ci_edit) == "deny")
        finally:
            os.chdir(old)


def round13_checks(ready, clean_line):
    """Round 13: when the MERGE-READY line lifts a review deny, the merge
    takes the strict MCP route under any grant, not only under mwr alone.
    Only a FULLY CLEAN line for the pinned head, or the user's typed
    override, keeps every route."""
    mwrs = ("user", "mwrs")
    loose = {"owner": "Morrison-Lab", "repo": "psw", "pullNumber": 123,
             "expected_head_sha": HEAD}
    for label, grant in [("a typed 'merge psw PR 123'", ("user", "merge psw PR 123")),
                         ("a typed mwc", ("user", "mwc"))]:
        check(f"round 13: {label}, mwrs and MERGE-READY: Bash gh pr merge denies, "
              "naming the MCP tool",
              mwr_decision([grant, mwrs, ready], not_clean_pr_state(), bash=True) == "deny"
              and last_denied_for_route())
        check(f"round 13: {label}, mwrs and MERGE-READY: MCP with expected_head_sha "
              "only denies, naming the MCP tool",
              mwr_decision([grant, mwrs, ready], not_clean_pr_state(),
                           merge_input=loose) == "deny" and last_denied_for_route())
        check(f"round 13: {label}, mwrs and MERGE-READY: strict MCP allows on clean "
              "live data",
              mwr_decision([grant, mwrs, ready], not_clean_pr_state()) == "allow")
        check(f"round 13: {label}, mwrs and MERGE-READY: strict MCP still denies on a "
              "live .github/ change",
              mwr_decision([grant, mwrs, ready], not_clean_pr_state(),
                           live=live_gh(compare={MAIN_BASE: [
                               ("src/a.py", None), (".github/workflows/ci.yml", None)]}))
              == "deny")
    check("round 13: typed mwc, mwrs and FULLY CLEAN: Bash gh pr merge of a clean PR "
          "still allows",
          mwr_decision([("user", "mwc"), mwrs, clean_line], clean_pr_state(), bash=True,
                       live=live_gh(fail=("/",))) == "allow")
    check("round 13: typed mwc, mwrs and FULLY CLEAN: MCP with expected_head_sha "
          "still allows",
          mwr_decision([("user", "mwc"), mwrs, clean_line], clean_pr_state(),
                       merge_input=loose, live=live_gh(fail=("/",))) == "allow")


def ordinary_allow_checks(grant, ready):
    """Round 8: when the ordinary gate allows but the merge rests on the
    MERGE-READY line alone, the live re-checks still run."""
    check("mwr allow: control - a stale APPROVED is an ordinary allow",
          gate.evaluate("gh pr merge 123", stale_approved_state())["decision"] == "allow")
    ci_edit = live_gh(compare={MAIN_BASE: [("src/a.py", None), (".github/workflows/ci.yml", None)]})
    dismissed = live_gh(reviews=[{"state": "DISMISSED", "user": {"login": "maintainer"}}])
    for name, state in (("stale APPROVED", stale_approved_state()),
                        ("trusted clean verdict", clean_pr_state())):
        check(f"mwr allow: {name} plus only a MERGE-READY line, live .github/ change, denies",
              mwr_decision([grant, ready], state, live=ci_edit) == "deny")
        check(f"mwr allow: {name} plus only a MERGE-READY line, DISMISSED review, denies",
              mwr_decision([grant, ready], state, live=dismissed) == "deny")
        check(f"mwr allow: {name} plus only a MERGE-READY line, failed live read, denies",
              mwr_decision([grant, ready], state, live=live_gh(fail=("/reviews",))) == "deny")
        check(f"mwr allow: {name} plus only a MERGE-READY line, clean live data, allows",
              mwr_decision([grant, ready], state) == "allow")
    calls = []
    base = live_gh(fail=("/",))

    def counting(args, cwd):
        calls.append(args)
        return base(args, cwd)
    clean_line = ("checker", f"✅ {MWR_REPO}#123 is FULLY CLEAN on HEAD {HEAD[:8]}! "
                             "[stale-base rule]")
    check("mwr allow: under mwc and mwr, a FULLY CLEAN line for the head skips the live mwr reads",
          mwr_decision([("user", "mwc"), grant, ready, clean_line], stale_approved_state(),
                       live=counting) == "allow"
          and not calls)
    check("mwr allow: under mwr only, a FULLY CLEAN line does not skip the live mwr reads",
          mwr_decision([grant, ready, clean_line], stale_approved_state(), live=counting) == "deny"
          and calls)
    calls.clear()
    mwr_only_fully_clean_checks(grant, ready, clean_line)
    round10_checks(clean_line)
    round13_checks(ready, clean_line)
    check("mwr allow: without the mwr grant, an ordinary allow reads no live data",
          mwr_decision([("user", "mwc"), ready], stale_approved_state(), live=counting) == "allow"
          and not calls)


def main():
    print(f"Testing {HOOK}...")
    mwr_checks()

    # 1. Output shape invariants
    allow_out = gate.ALLOW
    check("ALLOW has decision == 'allow'", allow_out.get("decision") == "allow")
    check("ALLOW has hookSpecificOutput.hookEventName == 'PreToolUse'",
          allow_out.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse")

    deny_out = gate.deny("test reason")
    check("deny has decision == 'deny'", deny_out.get("decision") == "deny")
    check("deny has reason", deny_out.get("reason") == "test reason")
    check("deny has hookSpecificOutput.permissionDecision == 'deny'",
          deny_out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")
    check("deny has hookSpecificOutput.permissionDecisionReason",
          deny_out.get("hookSpecificOutput", {}).get("permissionDecisionReason") == "test reason")

    # 2. Tool name detection
    check("is_mcp_merge_tool detects mcp__github__merge_pull_request",
          gate.is_mcp_merge_tool("mcp__github__merge_pull_request"))
    check("is_mcp_merge_tool detects enable_pull_request_auto_merge",
          gate.is_mcp_merge_tool("mcp__github__enable_pull_request_auto_merge"))
    check("is_mcp_auto_merge_tool detects auto_merge variant",
          gate.is_mcp_auto_merge_tool("enable_pull_request_auto_merge"))
    check("is_mcp_merge_tool returns False for non-merge tool",
          not gate.is_mcp_merge_tool("mcp__github__issue_read"))

    # 3. Claude Code Bash payloads
    out = run_main({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    check("Bash non-merge command allows", out.get("decision") == "allow" and
          out.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse")

    out = run_main({"tool_name": "Edit", "tool_input": {"file_path": "foo.py"}})
    check("Non-shell/non-MCP tool allows", out.get("decision") == "allow")

    out = run_main({"tool_name": "Bash", "tool_input": {"command": "glab mr merge 12"}})
    check("glab mr merge denies", out.get("decision") == "deny" and
          "GitLab merge requests" in out.get("reason", ""))

    out = run_main({"tool_name": "Bash", "tool_input": {"command": "glab api projects/1/merge_requests/2/merge -X PUT"}})
    check("glab api merge denies", out.get("decision") == "deny" and
          "GitLab merge requests" in out.get("reason", ""))

    out = run_main({"tool_name": "Bash", "tool_input": {"command": "gh api graphql -f query='mutation { mergePullRequest(input: {}) }'"}})
    check("GraphQL merge denies", out.get("decision") == "deny" and
          "GraphQL mutation is not allowed" in out.get("reason", ""))

    out = run_main({"tool_name": "Bash", "tool_input": {"command": "echo 'checking'; gh pr merge 123 --squash"}})
    check("Chained merge denies", out.get("decision") == "deny" and
          "must be executed on their own" in out.get("reason", ""))

    # 4. MCP payloads
    out = run_main({
        "tool_name": "mcp__github__enable_pull_request_auto_merge",
        "tool_input": {"owner": "foo", "repo": "bar", "pull_number": 1},
    })
    check("MCP auto-merge tool denies", out.get("decision") == "deny" and
          "auto-merge MCP tools cannot be verified" in out.get("reason", ""))

    out = run_main({
        "tool_name": "mcp__github__merge_pull_request",
        "tool_input": {"owner": "foo"},
    })
    check("MCP merge missing pull_number/repo denies", out.get("decision") == "deny" and
          "missing required owner, repo, or pull_number" in out.get("reason", ""))

    # 5. Review-gated evaluations with mocked fetch
    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (clean_pr_state(), None)
        out = run_main({
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": {
                "owner": "Morrison-Lab",
                "repo": "ai-config",
                "pull_number": 123,
                "expectedHeadSha": HEAD,
            },
        })
        check("MCP merge with clean review allows", out.get("decision") == "allow" and
              out.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse")

    # Round 11: the server merges `pullNumber` and ignores unknown keys, so
    # PR-number keys that disagree deny even over a clean review; keys that
    # agree, and `pullNumber` alone, still allow.
    for desc, keys, want in [
        ("conflicting pull_number=5, pullNumber=6 denies",
         {"pull_number": 5, "pullNumber": 6}, "deny"),
        ("conflicting pullNumber=6, number=5 denies",
         {"pullNumber": 6, "number": 5}, "deny"),
        ("matching pull_number=5, pullNumber='5 ' allows",
         {"pull_number": 5, "pullNumber": "5 "}, "allow"),
        ("pullNumber alone allows", {"pullNumber": 5}, "allow"),
    ]:
        with patch.object(gate, "fetch_pr_data") as mock_fetch:
            mock_fetch.return_value = (clean_pr_state(), None)
            out = run_main({
                "tool_name": "mcp__github__merge_pull_request",
                "tool_input": dict({"owner": "Morrison-Lab", "repo": "lds",
                                    "expectedHeadSha": HEAD}, **keys),
            })
            called = [c.kwargs.get("target_number") for c in mock_fetch.call_args_list]
        check(f"MCP merge with {desc}", out.get("decision") == want
              and (called == [] if want == "deny" else called == [5]))

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (clean_pr_state(), None)
        out = run_main({
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": {
                "owner": "Morrison-Lab",
                "repo": "ai-config",
                "pull_number": 123,
                "expectedHeadSha": "0000000000000000000000000000000000000000",
            },
        })
        check("MCP merge with mismatched expectedHeadSha denies", out.get("decision") == "deny" and
              "does not match current PR head SHA" in out.get("reason", ""))

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (not_clean_pr_state(), None)
        out = run_main({
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": {
                "owner": "Morrison-Lab",
                "repo": "ai-config",
                "pull_number": 123,
                "expectedHeadSha": HEAD,
            },
        })
        check("MCP merge with not-clean review denies", out.get("decision") == "deny" and
              "Needs more work" in out.get("reason", ""))

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (clean_pr_state(), None)
        out = run_main({
            "tool_name": "Bash",
            "tool_input": {"command": "gh pr merge 123 --squash"},
        })
        check("Bash gh pr merge with clean review allows", out.get("decision") == "allow")

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (not_clean_pr_state(), None)
        out = run_main({
            "tool_name": "Bash",
            "tool_input": {"command": "gh pr merge 123 --squash"},
        })
        check("Bash gh pr merge with not-clean review denies", out.get("decision") == "deny" and
              "Needs more work" in out.get("reason", ""))

    # 6. Antigravity run_command format
    out = run_main({
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "git status"},
        }
    })
    check("Antigravity run_command non-merge allows", out.get("decision") == "allow")
    check("Antigravity output omits hookSpecificOutput for protojson compatibility",
          "hookSpecificOutput" not in out)

    out = run_main({
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "glab mr merge 12"},
        }
    })
    check("Antigravity run_command glab mr merge denies", out.get("decision") == "deny")
    check("Antigravity deny omits hookSpecificOutput for protojson compatibility",
          "hookSpecificOutput" not in out)

    out = run_main({
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": "a.txt"},
        }
    })
    check("Antigravity non-run_command allows", out.get("decision") == "allow")

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (clean_pr_state(), None)
        out = run_main({
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "gh pr merge 123 --squash"},
            }
        })
        check("Antigravity run_command gh pr merge with clean review allows", out.get("decision") == "allow")

    # 6b. Pending CI blocks unless the user typed the override phrase
    pending_state = clean_pr_state()
    pending_state["statusCheckRollup"].append(
        {"name": "lint", "status": "IN_PROGRESS", "conclusion": None})
    out = gate.evaluate("gh pr merge 123 --squash", pending_state)
    check("pending check without override denies",
          out.get("decision") == "deny" and "lint" in out.get("reason", ""))
    out = gate.evaluate("gh pr merge 123 --squash", pending_state, override=True)
    check("pending check with override allows", out.get("decision") == "allow")
    failing_state = clean_pr_state()
    failing_state["statusCheckRollup"].append(
        {"name": "lint", "status": "COMPLETED", "conclusion": "FAILURE"})
    out = gate.evaluate("gh pr merge 123 --squash", failing_state, override=True)
    check("failing check with override still denies", out.get("decision") == "deny")

    import tempfile

    def transcript_with(*records):
        fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8")
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
        fh.close()
        return fh.name

    user_said = transcript_with(
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "merge them anyway"}]}})
    check("typed_override reads the user's phrase",
          gate.typed_override(user_said) is True)
    note_said = transcript_with(
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "<note>merge them anyway</note>"}]}})
    check("typed_override ignores an agent's note",
          gate.typed_override(note_said) is False)
    agent_said = transcript_with(
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "merge them anyway"}]}})
    check("typed_override ignores the assistant's words",
          gate.typed_override(agent_said) is False)
    negated = transcript_with(
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "don't merge them anyway"}]}})
    check("typed_override ignores a negated phrase",
          gate.typed_override(negated) is False)
    check("typed_override with no transcript is False",
          gate.typed_override("/nonexistent/transcript.jsonl") is False)
    for p in (user_said, note_said, agent_said, negated):
        os.unlink(p)

    # 7. Unparseable stdin fails closed
    out = run_main("not-json{{{")
    check("Unparseable stdin denies fail-closed", out.get("decision") == "deny" and
          out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")

    # 8. Dry-run arguments
    out = run_main("", argv=["enforce-mwc-review-gate.py", "--dry-run", "git status"])
    check("--dry-run non-merge allows", out.get("decision") == "allow")

    out = run_main("", argv=["enforce-mwc-review-gate.py", "--dry-run", "glab mr merge 5"])
    check("--dry-run glab mr merge denies", out.get("decision") == "deny")

    # 9. REST fallback when the session's proxy refuses GraphQL (ai-config#4304)
    graphql_refused = (
        "HTTP 403: GitHub GraphQL is not available from Claude Code sessions; "
        "use the REST API (gh api repos/{owner}/{repo}/...)."
    )
    repo = "repos/Morrison-Lab/ai-config"
    rest_pr = {
        "html_url": "https://github.com/Morrison-Lab/ai-config/pull/7",
        "user": {"login": "someone"},
        "head": {"sha": HEAD},
        "requested_reviewers": [{"login": "reviewer1"}],
        "requested_teams": [{"slug": "team-a"}],
    }
    rest_review = {
        "state": "COMMENTED", "body": "ok", "submitted_at": "2026-11-18T01:00:00Z",
        "author_association": "MEMBER", "user": {"login": "rev"}, "commit_id": HEAD,
    }
    rest_commit = {"sha": HEAD, "commit": {"committer": {"date": "2026-11-18T00:59:00Z"}}}
    rest_comment = {
        "author": {"login": "github-actions"},
        "body": ("**Claude finished review**\n\n### Verdict\n**Ready for merge** --- all prior "
                 f"findings addressed.\n\nReviewed commit: {HEAD}"),
        "createdAt": "2026-11-18T01:05:00Z",
    }

    def ok(body):
        return (0, json.dumps(body), "")

    def fake_gh(overrides=None):
        """A `run_gh` stand-in: GraphQL refused, every REST path answers."""
        routes = {
            f"{repo}/pulls/7": ok(rest_pr),
            f"{repo}/pulls/7/reviews?per_page=100": ok([rest_review]),
            f"{repo}/pulls/7/commits?per_page=100": ok([rest_commit]),
            f"{repo}/issues/7/comments": ok([rest_comment]),
            f"{repo}/pulls/7/comments": ok([]),
            f"{repo}/commits/{HEAD}/check-runs": ok([]),
            f"{repo}/pulls/7/ccr/review_threads?per_page=100": ok([]),
        }
        routes.update(overrides or {})

        def run(args, cwd):
            if args[:2] in (["pr", "view"], ["api", "graphql"]):
                return SimpleNamespace(returncode=1, stdout="", stderr=graphql_refused)
            code, out, err = routes.get(args[1], (1, "", f"no route for {args[1]}"))
            return SimpleNamespace(returncode=code, stdout=out, stderr=err)

        return run

    def fetch(overrides=None):
        with patch.object(gate, "run_gh", fake_gh(overrides)):
            return gate.fetch_pr_data(
                "", "/tmp", target_repo="Morrison-Lab/ai-config", target_number=7
            )

    threads = f"{repo}/pulls/7/ccr/review_threads?per_page=100"
    pr_data, err = fetch()
    pr_data = pr_data or {}
    check("GraphQL refused: fetch_pr_data falls back to REST with no error", err is None, str(err))
    check("REST fallback carries the head sha and url",
          pr_data.get("headRefOid") == HEAD and "pull/7" in pr_data.get("url", ""))
    check("REST fallback maps the author, review and last commit date",
          pr_data.get("author", {}).get("login") == "someone"
          and pr_data.get("reviews", [{}])[0].get("author", {}).get("login") == "rev"
          and pr_data.get("commits", [{}])[-1].get("committedDate") == "2026-11-18T00:59:00Z")
    check("REST fallback maps review requests to logins and team slugs",
          gate.extract_request_names(pr_data.get("reviewRequests", [])) == ["reviewer1", "team-a"])
    check("CCR fallback with no threads reads as no open threads",
          pr_data.get("reviewThreads") == [] and gate.unresolved_review_threads(pr_data) == [])

    two_threads = [{"resolved": False, "outdated": False, "path": "a.md", "line": 3},
                   {"resolved": True, "outdated": False, "path": "b.md", "line": 4}]
    pr_data, err = fetch({threads: ok(two_threads)})
    check("CCR fallback reports an unresolved thread as open",
          err is None and gate.unresolved_review_threads(pr_data) == ["a.md:3"], str(err))

    pr_data, err = fetch({threads: ok([{"resolved": True, "outdated": False}] * 100)})
    check("CCR answer of 100 threads is refused as possibly truncated",
          pr_data is None and "truncated" in (err or ""), str(err))

    pr_data, err = fetch({f"{repo}/pulls/7/reviews?per_page=100": (1, "", "HTTP 500")})
    check("A failed REST read after the fallback denies, not reads as empty",
          pr_data is None and "REST" in (err or "") and "HTTP 500" in (err or ""), str(err))

    pr_data, err = fetch({f"{repo}/pulls/7": ok(dict(rest_pr, commits=300))})
    check("A commits list shorter than the PR's commit count is refused as truncated",
          pr_data is None and "1 of 300" in (err or ""), str(err))

    pr_data, err = fetch({f"{repo}/pulls/7": ok(dict(rest_pr, commits=1))})
    check("A commits list that matches the PR's commit count is accepted",
          err is None and len(pr_data.get("commits", [])) == 1, str(err))

    pr_data, err = fetch({f"{repo}/pulls/7/commits?per_page=100": ok([rest_commit] * 250)})
    check("A full 250-commit page with no reported commit count is refused",
          pr_data is None and "may be truncated" in (err or ""), str(err))

    def other_failure(args, cwd):
        return SimpleNamespace(returncode=1, stdout="", stderr="GraphQL: Could not resolve to a PullRequest")

    with patch.object(gate, "run_gh", other_failure):
        pr_data, err = gate.fetch_pr_data(
            "", "/tmp", target_repo="Morrison-Lab/ai-config", target_number=7
        )
    check("A gh failure that is not the GraphQL refusal still denies with no fallback",
          pr_data is None and "gh pr view returned non-zero" in (err or ""), str(err))

    with patch.object(gate, "run_gh", fake_gh()):
        pr_data, err = gate.fetch_pr_data("gh pr merge --squash", "/tmp")
    check("Refused GraphQL with no repo and number to read over REST still denies",
          pr_data is None and "gh pr view returned non-zero" in (err or ""), str(err))

    merge_payload = {
        "tool_name": "mcp__github__merge_pull_request",
        "tool_input": {
            "owner": "Morrison-Lab", "repo": "ai-config", "pull_number": 7,
            "expectedHeadSha": HEAD,
        },
    }
    with patch.object(gate, "run_gh", fake_gh()):
        out = run_main(merge_payload)
    check("MCP merge denies on a pending review request read over the REST fallback",
          out.get("decision") == "deny" and "reviewer1" in out.get("reason", ""),
          json.dumps(out)[:300])

    no_requests = dict(rest_pr, requested_reviewers=[], requested_teams=[])
    with patch.object(gate, "run_gh", fake_gh({f"{repo}/pulls/7": ok(no_requests)})):
        out = run_main(merge_payload)
    check("MCP merge of a clean PR is allowed end to end when GraphQL is refused",
          out.get("decision") == "allow", json.dumps(out)[:300])

    print(f"\n{checks - len(failures)}/{checks} checks passed.")
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
