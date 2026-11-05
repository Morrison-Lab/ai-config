#!/usr/bin/env python3
"""PreToolUse deny: a forge comment says no prereq site defines a term, and
this turn never searched the sites for a `def-` anchor.

Measured on Morrison-Lab/dds#36 (2026-11-04): a PR comment said "no lds, mds,
pds or sds page defines them" with no search; mds had `def-rank` and lds had
`def-reinforcement`. The prose rules were read, then broken at composition time.

Denies when the body of a GitHub comment tool call (or `gh pr|issue comment`)
makes that claim AND no tool call since the last user message named a `def-`
anchor with a search verb (grep, rg, find, curl, `gh api`, `search/code`).
Posting tools are excluded from the scan, so a comment mentioning `def-rank` is
not evidence. A quoted or backticked claim is a citation. The denial names the
search to run, and the retry after it passes. Fails OPEN on parse trouble.
"""
import json
import re
import sys

TOOL = re.compile(
    r"^mcp__github__(?:add_issue_comment|update_issue_comment"
    r"|add_reply_to_pull_request_comment|add_comment_to_pending_review"
    r"|pull_request_review_write)$"
)
GH_COMMENT = re.compile(r"\bgh\s+(?:pr|issue)\s+comment\b")

# The prereq sites a claim may name (course-sequence.md).
SITE = r"(?:lds|mds|pds|sds|rme|dds|win|cie|ids|cds)"
CLAIMS = (
    # "no lds, mds, pds or sds page defines them"
    re.compile(
        rf"\bno\b[^.\n]{{0,60}}\b{SITE}\b[^.\n]{{0,40}}\b(?:page|site|chapter|section)s?\b"
        r"[^.\n]{0,30}\bdefines?\b", re.I),
    # "no page on the prereq sites defines it"
    re.compile(
        r"\bno\b[^.\n]{0,20}\b(?:page|site|chapter|section)s?\b[^.\n]{0,40}"
        r"\b(?:prereq\w*|lds|mds|pds|sds)\b[^.\n]{0,30}\bdefines?\b", re.I),
    # "is not defined in mds", "isn't defined on any of the prereq sites"
    re.compile(
        rf"\b(?:is|are|was|were)(?: not|n't)\s+defined\s+(?:in|on|by|at)\s+"
        rf"(?:any\s+)?(?:of\s+)?(?:the\s+)?(?:prereq\w*\s+)?(?:{SITE}\b|sites?\b|pages?\b)", re.I),
    # "no prereq site defines it", "no prerequisite page covers"
    re.compile(r"\bno prereq\w*\s+(?:site|page|chapter)s?\b[^.\n]{0,30}\bdefin", re.I),
    # "none of the lds, mds ... pages defines it"
    re.compile(rf"\bnone of (?:the )?[^.\n]{{0,40}}\b{SITE}\b[^.\n]{{0,40}}\bdefin", re.I),
)

QUOTED = re.compile(r"```.*?```|^>.*$|\"[^\"\n]*\"|“[^”\n]*”|`[^`\n]*`", re.S | re.M)

# A tool whose input is the agent's own prose is never evidence of a search.
POSTING = re.compile(
    r"(?:^|__)(?:reply|post_message|update_message|edit_message|message_thread"
    r"|message_coordinator|add_issue_comment|update_issue_comment"
    r"|add_reply_to_pull_request_comment|add_comment_to_pending_review"
    r"|pull_request_review_write|create_pull_request|update_pull_request"
    r"|issue_write|update_progress_checklist|request_decision|post_widget"
    r"|Write|Edit)$")
ANCHOR = re.compile(r"\bdef-[\w-]+|\{#def\b|#def-", re.I)
SEARCH = re.compile(r"\b(?:grep|rg|ag|find|curl|search/code|gh api|git grep)\b|^Grep$", re.I)

REASON = (
    "[hook: no-undefined-claim-without-def-search] This comment says no prereq "
    "site defines a term (\"{claim}\"), but this turn never searched the sites "
    "for a `def-` anchor. On Morrison-Lab/dds#36 that claim was wrong: `def-rank` "
    "was in mds and `def-reinforcement` in lds. Search each site, then post: "
    "`grep -rn '{{#def-<slug>' <checkout>` or `gh api -X GET search/code -f "
    "q='def-<slug> repo:Morrison-Lab/<site>'`. If a site defines it, link that "
    "definition instead. ai-config#4949."
)


def claim_in(text: str):
    plain = QUOTED.sub(" ", text)
    for rx in CLAIMS:
        m = rx.search(plain)
        if m:
            return m.group(0).strip()
    return None


def bodies(payload):
    name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    if TOOL.search(name):
        return [v for v in (tool_input.get("body"), tool_input.get("text")) if isinstance(v, str)]
    if name == "Bash":
        cmd = tool_input.get("command")
        if isinstance(cmd, str) and GH_COMMENT.search(cmd):
            return [cmd]
    return []


def _blocks(msg):
    blocks = (msg.get("message") or {}).get("content") or msg.get("content") or []
    return blocks if isinstance(blocks, list) else []


def searched_def_anchor(path: str) -> bool:
    """True when a non-posting tool call since the last user message names a
    `def-` anchor and a search verb. Fails open (True) when unreadable."""
    try:
        found = False
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(m, dict):
                    continue
                raw = (m.get("message") or {}).get("content") or m.get("content")
                if m.get("type") == "user" or m.get("role") == "user":
                    texts = raw if isinstance(raw, list) else [{"type": "text", "text": raw}]
                    if any(isinstance(b, dict) and b.get("type") == "text" and (b.get("text") or "").strip()
                           for b in texts):
                        found = False
                    continue
                for b in _blocks(m):
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    if POSTING.search(b.get("name") or ""):
                        continue
                    blob = json.dumps(b.get("input") or {})
                    if ANCHOR.search(blob) and (SEARCH.search(blob) or SEARCH.search(b.get("name") or "")):
                        found = True
        return found
    except OSError:
        return True
    except Exception:
        return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    claim = None
    for body in bodies(payload):
        claim = claim_in(body)
        if claim:
            break
    if not claim:
        return 0
    path = payload.get("transcript_path")
    if not isinstance(path, str) or searched_def_anchor(path):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(claim=claim[:120]),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
