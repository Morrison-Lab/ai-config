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
import json
import os
import re
import sys
import time

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
    "my word\"). Do not ask for or wait on his word. In a project, an owner thread never merges: "
    "send the PR's final head to the coordinator, whose runner thread merges it once the "
    "fully-clean checker exits 0, and say it merges under the infra grant. Outside a project, "
    "merge it yourself once fully clean. Drop it from the mwc list. ai-config#5097, #5111."
)


# One shared budget for every live lookup, well under the 10s hooks.json timeout.
TOTAL_BUDGET_S = 7.0
MAX_REFS = 8
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n")


_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from sibling import load_sibling
except ImportError as _exc:
    print(f"no-mwc-ask-for-infra-pr: cannot load scripts/lib/sibling.py "
          f"({_exc}); its sibling hook will not load", file=sys.stderr)
    load_sibling = None


_MERGE_HOOK = None


def load_merge_hook():
    """Import `no-unauthorized-merge.py` once (scripts/lib/sibling.py); raises if it cannot load."""
    global _MERGE_HOOK
    if _MERGE_HOOK is None:
        if load_sibling is None:
            raise ImportError("scripts/lib/sibling.py is not importable")
        _MERGE_HOOK = load_sibling(__file__, "no-unauthorized-merge.py",
                                   "no_unauthorized_merge", required=True)
    return _MERGE_HOOK


def refs(sentence):
    """Return (position, (owner, repo, number)) for each PR reference, in order."""
    found = {}
    for m in URL_REF.finditer(sentence):
        found.setdefault(m.start(), (m.group(1).lower(), m.group(2).lower(), int(m.group(3))))
    for m in FULL_REF.finditer(sentence):
        found.setdefault(m.start(), (m.group(1).lower(), m.group(2).lower(), int(m.group(3))))
    for m in SHORT_REF.finditer(sentence):
        found.setdefault(m.start(), (OWNER, m.group(1).lower(), int(m.group(2))))
    return sorted(found.items())


LIST_GAP = re.compile(r"[\s,]*(?:and|or|&)?[\s,]*", re.I)
REF_TOKEN = re.compile(r"^[^\s,;]+")


def _same_list(sentence, left, right):
    """True when only list connectors (commas, and, or, &) separate two references."""
    gap = sentence[left:right]
    return bool(LIST_GAP.fullmatch(REF_TOKEN.sub("", gap, count=1)))


def exempt_refs(sentence, found):
    """Positions of the refs a grant statement in this sentence is about.

    Each grant phrase belongs to the nearest PR reference and to the references
    listed with it ("a#1 and b#2 merge under the grant"), not to another one
    named across other words in the same sentence.
    """
    exempt = set()
    if not found:
        return exempt
    positions = [item[0] for item in found]
    for g in GRANT_STATED.finditer(sentence):
        i = min(range(len(positions)), key=lambda k: abs(positions[k] - g.start()))
        exempt.add(positions[i])
        j = i
        while j > 0 and _same_list(sentence, positions[j - 1], positions[j]):
            j -= 1
            exempt.add(positions[j])
        j = i
        while j + 1 < len(positions) and _same_list(sentence, positions[j], positions[j + 1]):
            j += 1
            exempt.add(positions[j])
    return exempt


def classify(owner, repo, number, deadline):
    """Return a reason string when the PR is provably infra, else None."""
    if (owner, repo) == ("d-morrison", "macros"):
        return "every PR in d-morrison/macros is infrastructure"
    if owner != OWNER:
        return None
    if repo in INFRA_REPOS:
        return f"every PR in Morrison-Lab/{repo} is infrastructure"
    if os.environ.get("NO_MWC_INFRA_HOOK_DISABLE_FETCH"):
        return None
    remaining = deadline - time.monotonic()
    if remaining < 1.0:
        return None
    mod = load_merge_hook()
    mod.INFRA_FETCH_BUDGET_S = remaining
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
        if not isinstance(text, str) or not MWC.search(text):
            return 0
        deadline = time.monotonic() + TOTAL_BUDGET_S
        checked = 0
        # A grant statement exempts only the PR reference nearest to it.
        for sentence in SENTENCE_SPLIT.split(text):
            found = refs(sentence)
            exempt = exempt_refs(sentence, found)
            for position, (owner, repo, number) in found:
                if position in exempt:
                    continue
                checked += 1
                if checked > MAX_REFS:
                    return 0
                why = classify(owner, repo, number, deadline)
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
