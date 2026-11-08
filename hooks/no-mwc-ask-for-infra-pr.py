#!/usr/bin/env python3
"""PreToolUse: do not tell the user an infrastructure PR waits on his `mwc`.

ai-config#5097. Ezra, 2026-11-07, about Morrison-Lab/lds#2009 (a workflow-only PR):
"lds 2009 is infra and shouldn't need my word. why didn't you realize that"

strict-merge-policy.md already gives a fully clean infrastructure PR a standing
merge grant, yet agents kept reporting such PRs as waiting on a merge word,
because nothing made them classify the diff first.

Denies a user-visible reply tool call (post_message, reply, update_message,
edit_message) whose text mentions `mwc` and names a PR that is provably
infrastructure: every PR in gha, macros or ai-config, or any Morrison-Lab PR
whose changed paths all match no-unauthorized-merge.py's INFRA_PATH_PATTERNS
(the single source of truth for "infra path"). A message that says the PR merges
under the infra grant is allowed. Fails open on any parse or lookup trouble.
"""
import importlib.util
import json
import os
import re
import sys

REPLY_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")
MWC = re.compile(r"\bmwc\b", re.I)
GRANT_STATED = re.compile(
    r"infra(?:structure)?[- ](?:pr )?grant|standing (?:infra|mwc|merge)|\bno mwc\b|"
    r"without (?:an? )?(?:fresh )?mwc|merg(?:e|es|ed|ing) under",
    re.I,
)
OWNER = "morrison-lab"
INFRA_REPOS = frozenset({"gha", "macros", "ai-config"})
URL_REF = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)", re.I)
FULL_REF = re.compile(r"(?<![\w/.-])([\w.-]+)/([\w.-]+)#(\d+)\b")
SHORT_REF = re.compile(r"(?<![\w/.#-])([A-Za-z][\w.-]*)#(\d+)\b")

REASON = (
    "[hook: no-mwc-ask-for-infra-pr] This message mentions `mwc` and names {ref}, which is an "
    "infrastructure PR ({why}). Infra PRs carry a standing merge grant once fully clean "
    "(strict-merge-policy.md; Ezra, 2026-11-07 about lds#2009: \"it's infra and shouldn't need "
    "my word\"). Do not ask for or wait on his word: run the fully-clean checker, route the PR "
    "to the runner thread / merge it, and say it merges under the infra grant. Drop it from the "
    "mwc list. ai-config#5097."
)


def load_merge_hook():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "no-unauthorized-merge.py")
    spec = importlib.util.spec_from_file_location("no_unauthorized_merge", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def refs(text):
    seen = []
    for o, r, n in URL_REF.findall(text) + FULL_REF.findall(text):
        seen.append((o.lower(), r.lower(), int(n)))
    for r, n in SHORT_REF.findall(text):
        seen.append((OWNER, r.lower(), int(n)))
    return list(dict.fromkeys(seen))


def classify(owner, repo, number):
    """Return a reason string when the PR is provably infra, else None."""
    if owner != OWNER:
        return None
    if repo in INFRA_REPOS:
        return f"every PR in Morrison-Lab/{repo} is infrastructure"
    if os.environ.get("NO_MWC_INFRA_HOOK_DISABLE_FETCH"):
        return None
    mod = load_merge_hook()
    res = mod.fetch_pr_changed_paths(f"{owner}/{repo}", number)
    if not res:
        return None
    paths = res[0] if isinstance(res, tuple) else res
    if paths and all(mod.is_infra_path(p) for p in paths):
        return f"all {len(paths)} changed paths are CI, tooling or agent configuration"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        if not REPLY_TOOL.search(str(payload.get("tool_name") or "")):
            return 0
        tool_input = payload.get("tool_input")
        text = tool_input.get("text") if isinstance(tool_input, dict) else None
        if not isinstance(text, str) or not MWC.search(text) or GRANT_STATED.search(text):
            return 0
        for owner, repo, number in refs(text)[:8]:
            why = classify(owner, repo, number)
            if why:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON.format(ref=f"{repo}#{number}", why=why),
                }}))
                return 0
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
