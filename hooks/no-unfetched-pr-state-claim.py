#!/usr/bin/env python3
"""Guard: a claim that a PR awaits merge, or that work is still to do, needs a live read.

ai-config#4834. On 2026-10-29 a project coordinator told the user that
mcsg#52 was "waiting on your merge". It had the claim from a stale handoff
summary, and the PR had already merged; the user had to answer "look again".
The same session proposed drafting Homework 2-6 as the next step from a stale
memory note, and those had merged too (mcsg#18, #43-#46).

A recalled state is a reading from some earlier moment. A claim that a PR is
open, or that work is not done, is a claim about NOW, and the forge answers it
in one call. The condition is decidable from the transcript:

    the reply asserts pending PR state or pending work
    AND no tool call since the last user turn read that state live

Two kinds of claim, with different evidence:

  1. PR state -- "waiting on your merge", "ready for you to merge", "awaits
     review", "PR #52 is still open", "hasn't been merged". Needs a fetch of
     that PR: GitHub MCP `pull_request_read` (get) or `issue_read`, a PR list or
     search, hearthbot `list_prs`, `gh pr view/list/status`, `gh api
     .../pulls[/N]`, `glab mr view/list`, or `check-pr-fully-clean.py`. When the
     sentence names numbers, a single-PR fetch must name the same number; a
     list or search covers any number.
  2. Pending work -- "still needs drafting", "hasn't been written yet", "yet to
     be ported", "drafting X is next". Needs any live forge or remote read: a
     PR fetch as above, a GitHub MCP issue, commit, branch, file or code read,
     `gh issue`/`gh search`/`gh api`, or `git fetch`/`pull`/`ls-remote`/`log
     origin/...`. Reading a local checkout or a memory note does not count;
     that is where the stale claim comes from.

Runs on two events, because a project thread posts its reply through a tool
call before the turn ends (ai-config#4830):

  PreToolUse on a hearthbot reply tool -- denies the call, so the claim never
      reaches the user.
  Stop -- blocks the final message in a session that replies in plain text.
      It yields when a reply tool ran since the last user turn, since the
      PreToolUse run already judged that text.

Fires at most once per distinct text (sentinel keyed by content hash), so a
claim the forge cannot settle cannot wedge the session. Fails OPEN on any parse
trouble, including when the sibling module it reuses cannot load.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

try:
    _spec = importlib.util.spec_from_file_location(
        "no_offer_to_file",
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-offer-to-file.py"),
    )
    _offer = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_offer)
    last_assistant_text = _offer.last_assistant_text
    sentence_around = _offer.sentence_around
    strip_code = _offer.strip_code
except Exception:
    sys.exit(0)

REPLY_TOOL_RX = re.compile(
    r"^mcp__hearthbot__(reply|post_message|update_message|edit_message)$"
)

_WHO = r"(your|ezra'?s|the user'?s|a|human|their|his|her)"
_PR_ACT = r"(merge|merging|review|approval|sign-?off|go-?ahead|merge words?)"

# Merge or review wording that is about a PR on its own.
PR_STRONG_RX = re.compile(
    r"\b(waiting|waits?|awaiting) (on|for) (" + _WHO + r" )?" + _PR_ACT + r"\b"
    r"|\bawaits? (" + _WHO + r" )?" + _PR_ACT + r"\b"
    r"|\bready (for (you|ezra|the user) )?to (be )?merged?\b"
    r"|\bready for (" + _WHO + r" )?(merge|review)\b"
    r"|\bfor (you|ezra|the user) to (merge|review)\b"
    r"|\bneeds? (" + _WHO + r" )?(merge|review|approval)\b"
    r"|\b(hasn'?t|has not|haven'?t|have not|isn'?t|is not|aren'?t|are not) (yet )?(been )?(merged|reviewed)\b"
    r"|\bnot (yet )?merged\b|\byet to (be )?merged?\b"
    r"|\bpending (merge|review)\b",
    re.I,
)

# State words that are about a PR only when the sentence names one.
PR_WEAK_RX = re.compile(
    r"\b(is|are|still|remains?|stays?) (still )?(open|in review|under review|unmerged)\b",
    re.I,
)
PR_CONTEXT_RX = re.compile(
    r"\b(PRs?|pull requests?|MRs?|merge requests?)\b|#\d+|/pull/\d+|(?<![\w&])!\d+\b",
    re.I,
)

_WORK_PART = (
    r"(drafted|written|done|implemented|started|finished|shipped|landed|ported"
    r"|built|merged|made|created|added|opened)"
)
WORK_RX = re.compile(
    r"\b(still|yet) (needs?|has|have|to be|remains? to be)\b[^.!?\n]{0,20}?"
    r"\b(draft|writ|implement|port|done|finish|ship|land|build|built|start|add|creat)\w*"
    r"|\b(hasn'?t|has not|haven'?t|have not|isn'?t|is not|aren'?t|are not) (yet )?(been )?"
    + _WORK_PART + r"\b"
    r"|\bnot yet " + _WORK_PART + r"\b"
    r"|\byet to be \w+ed\b"
    r"|\b(draft|writ|port|implement|build)\w*\b[^.!?\n]{0,60}?\b(is|are|comes?) next\b"
    r"|\bnext( up| step| steps)?( is| are| would be|:|,)\s+(to )?"
    r"(draft|write|port|implement|build)\w*\b",
    re.I,
)

# A negation just before the match reports that nothing is pending.
NEGATED_BEFORE_RX = re.compile(
    r"\b(no longer|nothing|none|not|isn'?t|aren'?t|wasn'?t|no)\b[^.!?\n]{0,12}$", re.I
)

NUMBER_RX = re.compile(
    r"(?:[\w.-]+/[\w.-]+)?#(\d+)\b|/pull/(\d+)\b|\b(?:PR|MR|pull request) (\d+)\b"
    r"|(?<![\w&])!(\d+)\b",
    re.I,
)

# --- live reads ---------------------------------------------------------
PR_LIST_TOOL_RX = re.compile(
    r"^mcp__(github__(list_pull_requests|search_pull_requests)|hearthbot__list_prs)$"
)
PR_ONE_TOOL_RX = re.compile(r"^mcp__github__(pull_request_read|issue_read)$")
WORK_TOOL_RX = re.compile(
    r"^mcp__github__(issue_read|list_issues|search_issues|list_commits|get_commit"
    r"|get_file_contents|search_code|list_branches|list_pull_requests"
    r"|search_pull_requests|pull_request_read)$"
)
PR_ONE_CMD_RX = re.compile(
    r"\b(?:gh pr view|glab mr view)\s+(?:-\S+\s+\S+\s+)*#?(\d+)\b"
    r"|/pulls/(\d+)(?![\w/])"
    r"|/merge_requests/(\d+)(?![\w/])"
    r"|\b(?:check-pr-fully-clean|build-pr-payload)\.py\b[^|;&\n]*?\s#?(\d+)\b"
)
PR_LIST_CMD_RX = re.compile(
    r"\bgh pr (list|status)\b|\bglab mr list\b|\bgh search prs\b"
    r"|/pulls(?:\?|['\"\s]|$)|/merge_requests(?:\?|['\"\s]|$)"
)
WORK_CMD_RX = re.compile(
    r"\bgit (fetch|pull|ls-remote)\b|\bgit log\b[^|;&\n]*\borigin/"
    r"|\bgh (issue|search|api|pr|run)\b|\bglab (issue|mr|api)\b|api\.github\.com"
)

SYSTEM_TEXT_RX = re.compile(r"<system-reminder|\[SYSTEM NOTIFICATION", re.I)


def _blocks(m):
    blocks = (m.get("message") or {}).get("content") or m.get("content")
    return blocks if isinstance(blocks, list) else []


def _is_user_turn(m):
    """A genuine user message: user role with at least one non-tool-result block."""
    if m.get("type") != "user" and m.get("role") != "user":
        return False
    content = (m.get("message") or {}).get("content") or m.get("content")
    if isinstance(content, str):
        return bool(content.strip()) and not SYSTEM_TEXT_RX.match(content.lstrip())
    return any(
        isinstance(b, dict)
        and b.get("type") != "tool_result"
        and not SYSTEM_TEXT_RX.match(str(b.get("text") or "").lstrip())
        for b in _blocks(m)
    )


def classify_call(block):
    """(pr_numbers, pr_list, work) for one tool_use block.

    pr_numbers -- PR numbers this call read the live state of
    pr_list    -- True when it read a list or search of PRs (covers any number)
    work       -- True when it read live forge or remote state of any kind
    """
    name = str(block.get("name") or "")
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    nums, pr_list, work = set(), False, False
    if PR_LIST_TOOL_RX.match(name):
        pr_list = work = True
    if PR_ONE_TOOL_RX.match(name) and str(inp.get("method") or "get") == "get":
        num = inp.get("pullNumber", inp.get("issue_number"))
        if num is not None:
            nums.add(str(num).lstrip("#"))
    if WORK_TOOL_RX.match(name):
        work = True
    cmd = inp.get("command")
    if isinstance(cmd, str):
        for m in PR_ONE_CMD_RX.finditer(cmd):
            nums.add(next(g for g in m.groups() if g))
        if PR_LIST_CMD_RX.search(cmd):
            pr_list = True
        if WORK_CMD_RX.search(cmd):
            work = True
    if nums:
        work = True
    return nums, pr_list, work


def turn_reads(path):
    """Live reads, and whether a reply tool ran, since the last user turn."""
    calls = {}
    errored = set()
    replied = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if not isinstance(m, dict):
                    continue
                if _is_user_turn(m):
                    calls, errored, replied = {}, set(), False
                for b in _blocks(m):
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        if REPLY_TOOL_RX.match(str(b.get("name") or "")):
                            replied = True
                        else:
                            calls[b.get("id")] = classify_call(b)
                    elif b.get("type") == "tool_result" and b.get("is_error"):
                        errored.add(b.get("tool_use_id"))
    except Exception:
        pass
    nums, pr_list, work = set(), False, False
    for cid, (n, lst, w) in calls.items():
        if cid in errored:
            continue
        nums |= n
        pr_list = pr_list or lst
        work = work or w
    return nums, pr_list, work, replied


def _negated(prose, start):
    return bool(NEGATED_BEFORE_RX.search(prose[max(0, start - 30):start]))


def find_claim(prose, nums, pr_list, work):
    """(kind, phrase, missing_numbers) for the first unsupported claim, or None."""
    for rx, needs_context in ((PR_STRONG_RX, False), (PR_WEAK_RX, True)):
        for m in rx.finditer(prose):
            if _negated(prose, m.start()):
                continue
            sentence = sentence_around(prose, m.start(), m.end())
            if needs_context and not PR_CONTEXT_RX.search(sentence):
                continue
            named = {next(g for g in n.groups() if g) for n in NUMBER_RX.finditer(sentence)}
            if pr_list:
                continue
            missing = sorted(named - nums, key=int)
            if named and not missing:
                continue
            if not named and nums:
                continue
            return "pr", m.group(0), missing
    for m in WORK_RX.finditer(prose):
        if work or _negated(prose, m.start()):
            continue
        return "work", m.group(0), []
    return None


def reason_for(kind, phrase, missing):
    if kind == "pr":
        which = (
            "PR " + ", ".join("#" + n for n in missing) if missing else "the PR it names"
        )
        return (
            "[hook: no-unfetched-pr-state-claim] This message says a PR is still "
            f"pending (\"{phrase.strip()}\"), and nothing since the last user turn "
            f"read {which} live. A handoff summary, a memory note or an earlier "
            "turn is a reading from the past; on 2026-10-29 one said mcsg#52 was "
            "waiting on the user's merge after it had merged.\n\n"
            "Fetch the PR now (GitHub MCP pull_request_read method get, `gh pr "
            "view N`, `gh api repos/O/R/pulls/N`, or hearthbot list_prs), then "
            "state what the reading says. ai-config#4834."
        )
    return (
        "[hook: no-unfetched-pr-state-claim] This message says work is still to "
        f"do (\"{phrase.strip()}\"), and nothing since the last user turn read "
        "the forge or the remote. A memory note or handoff is a reading from "
        "the past; on 2026-10-29 one proposed drafting Homework 2-6 after it had "
        "merged.\n\n"
        "Check live state first (list or search the repo's PRs and issues, read "
        "the file on the default branch, or `git fetch` and `git log "
        "origin/main`), then restate. If the claim is not about forge work, "
        "send it again unchanged; this fires once per message. ai-config#4834."
    )


def _first_time(text):
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-pr-state-claim-guard-{key}")
    if os.path.exists(sentinel):
        return False
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except Exception:
        pass
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    path = payload.get("transcript_path") or ""
    tool_name = payload.get("tool_name")

    if tool_name is not None:
        if not REPLY_TOOL_RX.match(str(tool_name)):
            return 0
        inp = payload.get("tool_input")
        text = inp.get("text") if isinstance(inp, dict) else None
        if not isinstance(text, str) or not text.strip():
            return 0
        nums, pr_list, work, _ = turn_reads(path)
    else:
        text = last_assistant_text(path)
        if not text:
            return 0
        nums, pr_list, work, replied = turn_reads(path)
        if replied:
            return 0

    hit = find_claim(strip_code(text), nums, pr_list, work)
    if not hit or not _first_time(text):
        return 0
    reason = reason_for(*hit)
    if tool_name is not None:
        out = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}
    else:
        out = {"decision": "block", "reason": reason}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
