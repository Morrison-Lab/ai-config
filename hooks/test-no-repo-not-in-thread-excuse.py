#!/usr/bin/env python3
"""Tests for hooks/no-repo-not-in-thread-excuse.py.

Run: python3 hooks/test-no-repo-not-in-thread-excuse.py
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, "no-repo-not-in-thread-excuse.py")
spec = importlib.util.spec_from_file_location("hook", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"
COORD = "mcp__hearthbot__message_coordinator"

# (name, tool, text, should_deny)
CASES = [
    ("the 2026-11-12 message", COORD, "ai-config isn't in this thread's repos, so could you route that as an issue?", True),
    ("curly apostrophe", POST, "mlr isn\u2019t in this thread\u2019s repositories.", True),
    ("not attached", POST, "The repo is not attached to this session.", True),
    ("outside scope", POST, "That repository is outside this session's repo scope.", True),
    ("repos attached to", POST, "ai-config is not in the repos attached to this thread.", True),
    ("repos don't include", POST, "The thread's repos don't include ai-config.", True),
    ("can't reach", POST, "I can't reach ai-config from this thread.", True),
    ("newline split", POST, "Done.\nai-config isn't in this thread's repos", True),
    ("has no checkout", COORD, "This session has no ai-config checkout, so route it as an issue.", True),
    ("don't see", POST, "I don't see ai-config in this thread's repos.", True),
    ("there is no repo", POST, "There is no ai-config repo in this thread.", True),
    ("added a note", POST, "I added a note that ai-config isn't in this thread's repos.", True),
    ("attached adjective", POST, "The attached patch failed, and ai-config isn't in this thread's repos.", True),
    ("a repo object", POST, "I don't have access to a repo in this thread.", True),
    ("other owner", POST, "ucdavis/rampp isn't in this thread.", True),
    ("attach other repo", POST, "I added the gha label; mlr isn't in this thread's repos.", True),
    ("reachable", POST, "ai-config isn't reachable from this thread.", True),
    ("project thread", POST, "ai-config isn't in this project thread.", True),
    ("failed before", POST, "add_repo has failed before, so ai-config is not in this thread.", True),
    ("returned 200", POST, "add_repo returned 200 OK, but ai-config isn't in this thread's repos yet.", True),
    ("reason is the excuse", POST, "I can't reach ai-config from this thread because it isn't attached.", True),
    ("asks for add_repo", POST, "mlg isn't in this thread's repos; I attached a screenshot, could you run add_repo for it?", True),
    ("current session", POST, "ai-config is not in the current session's repos.", True),
    ("hasn't been added", POST, "ai-config hasn't been added to this thread.", True),
    ("linked subject", POST, "[ai-config](https://github.com/Morrison-Lab/ai-config) isn't attached to this thread.", True),
    # Passes.
    ("attach and other repo", POST, "I attached mlg to this thread, since it wasn't in this thread's repos, and fixed the lds link. mlg wasn't in this thread's repos, so I attached it and pushed the fix for the lds link. I attached ai-config and mlg, since mlg wasn't in this thread's repos. ai-config isn't in this thread's repos yet, so I'm attaching it now.", False),
    ("not a repo", POST, "The merge-ready PR isn't in this thread yet. That file isn't in this thread. scripts/check.py isn't in this thread. `pytest` is not available in this session. mlr is not available in this session yet, so I used tidymodels. mlr isn't attached in this session, so library(mlr) failed. I don't have the SDs in this thread yet. ai-config isn't in this session, so the plugin hooks don't fire.", False),
    ("repo word as place", POST, "The bug is not in this thread's repo, it is in lds-site. Tests aren't in this session's repos folder. The issue is not in this thread's scope, so I left it.", False),
    ("status sentences", POST, "We have no gha changes in this thread. This session has no access to the network. The lds preview isn't in this thread yet. This thread does not edit lds; the change is in mds. lds is not in this thread's merge queue yet. mds is not in the plan for this session. I can't push to lds in this session. The bug isn't in this thread's repos; it is in gha. This session has no gha access token, so the dispatch failed. I didn't see lds in this thread's PR list. Updating lds is not in this thread's scope, so I filed an issue for it.", False),
    ("more status", POST, "I don't have the lds preview URL in this thread yet. I checked this thread's repos and found no open PRs. CI in this thread's repos is not failing anymore. I can't push to lds in this session because the branch is protected. mds is not checked out at main in this session. mds is not one of the repos this thread changed. I can't edit lds.qmd in this session until the render ends. This session doesn't have write access to lds; the push was denied with 403. Quarto/pandoc isn't available in this session yet. The cmsg ids aren't in this thread. lds is not in the session log. mlg is outside this thread's scope, so I filed an issue there. mds isn't cloned in this session yet; cloning it now. I can't reach mlr in this session because GitHub is down. I don't have write access to ai-config from this thread. GitHub is down, so I can't reach lds from this session. I can't reach lds from this session until the deploy finishes. Example: lds isn't attached to this thread.", False),
    ("object not subject", POST, "The fix for lds isn't in this thread. Work on mds is not part of this thread. The macros aren't available in this session. lds is not in draft here. The PR against lds isn't in this thread yet. I can't clone mlr in this session because the repo holds 4 GB of PDFs. The PR against that lds repo isn't in this thread.", False),
    ("reported refusal", POST, "add_repo refused ai-config, so it is not in this session's repos. The attach failed with a 403, so ai-config is not in this thread's repos. add_repo returned 403 Forbidden, so ai-config isn't in this thread. `add_repo` refused ai-config, so it is not in this thread's repos. I tried add_repo for ai-config but it was refused, so ai-config isn't in this thread. mlg isn't in this thread's repos; I tried to attach it but it failed with a 403.", False),
    ("attach reports", POST, "I've attached ai-config, since it wasn't in this thread's repos. lds wasn't in this thread's repos, so I ran add_repo and cloned it. I attached mlr, since it wasn't in this thread's repos, and opened [mlr#5](https://github.com/Morrison-Lab/mlr/pull/5). I attached ai-config to this thread and opened a PR. I added mlr after it wasn't in this thread's repos. I attached ai-config, since it wasn't in this thread's repos. Since ai-config wasn't in this thread's repos, I attached it. I attached [ai-config](https://github.com/Morrison-Lab/ai-config), since it wasn't in this thread's repos. ai-config wasn't in this thread's repos, so I've now attached it. ai-config wasn't in this thread's repos, so it is attached now. mlg wasn't in this thread's repos, so I added it. mlg wasn't in this thread's repos, so I cloned it and pushed the fix. lds wasn't in this thread's repos until I attached it. ai-config wasn't in this thread's repos. I attached it and pushed. lds wasn't in this thread's repos until add_repo attached it.", False),
    ("other tool", "Bash", "ai-config isn't in this thread's repos.", False),
]


def decision_denied():
    os.environ.pop(hook.OVERRIDE, None)
    bad = "ai-config isn't in this thread's repos."
    return all(hook.denial({"tool_name": "mcp__hearthbot__request_decision", "tool_input": ti}) is not None
               for ti in ({"question": "Where?", "options": [{"label": "a", "consequence": bad}]},
                          {"question": "Where?", "reason": bad}))


def denied(tool, text):
    os.environ.pop(hook.OVERRIDE, None)
    return hook.denial({"tool_name": tool, "tool_input": {"text": text}}) is not None


def main() -> int:
    failures = 0
    for name, tool, text, want in CASES:
        got = denied(tool, text)
        if got != want:
            failures += 1
            print(f"FAIL {name}: want deny={want}, got {got}")
    if not decision_denied():
        failures += 1
        print("FAIL request_decision option or reason")
    os.environ[hook.OVERRIDE] = "1"
    if hook.denial({"tool_name": POST, "tool_input": {"text": CASES[0][2]}}) is not None:
        failures += 1
        print("FAIL override")
    os.environ.pop(hook.OVERRIDE, None)
    out = subprocess.run([sys.executable, SCRIPT], input=json.dumps(
        {"tool_name": COORD, "tool_input": {"text": CASES[0][2]}}),
        capture_output=True, text=True).stdout
    if '"deny"' not in out:
        failures += 1
        print("FAIL end-to-end deny")
    out = subprocess.run([sys.executable, SCRIPT], input="not json",
                         capture_output=True, text=True)
    if out.returncode != 0 or out.stdout:
        failures += 1
        print("FAIL fail-open")
    print(f"{len(CASES) + 4 - failures}/{len(CASES) + 4} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
