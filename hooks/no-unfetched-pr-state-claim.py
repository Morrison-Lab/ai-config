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

  1. PR state -- "waiting on your merge", "awaiting review", "ready for you to
     merge", "PR #52 is still open", "hasn't been merged". Merge wording counts
     on its own; review, approval and open-state wording count only when the
     sentence names a PR. Needs a fetch of that PR: GitHub MCP
     `pull_request_read` (method get) or `issue_read`, a PR list or search,
     hearthbot `list_prs`, `gh pr view/list/status`, `gh api .../pulls[/N]`,
     `glab mr view/list`, or `check-pr-fully-clean.py`. When the sentence names
     numbers, a single-PR fetch must name the same number, and the same repo
     when both name one; a list or search covers any number.
  2. Pending work -- "Homework 3 still needs drafting", "issue #40 hasn't been
     done", "drafting Homework 2-6 is next". Counts only when the sentence
     names a forge item or a course deliverable, so "next, write the tests"
     passes. Needs any live forge or remote read: a PR fetch as above, a
     GitHub MCP issue, commit, branch, file or code read, a read-only `gh
     issue`/`gh search`/`gh api` call, or `git fetch`/`pull`/`ls-remote`. A
     forge write, a local checkout, a remote-tracking ref read without a fetch,
     and a memory note do not count; those are where a stale claim comes from.

Text in code spans, in double or curly quotes, and on blockquote lines is a
quotation rather than a claim, and is skipped.

Runs on two events, because a project thread posts its reply through a tool
call before the turn ends (ai-config#4830):

  PreToolUse on a hearthbot reply tool -- denies the call, so the claim never
      reaches the user.
  Stop -- blocks the final message in a session that replies in plain text.
      It yields when a reply tool call since the last user turn went through,
      since the PreToolUse run already judged that text.

Fires at most once per distinct text and at most twice per user turn, per
transcript, so a claim the forge cannot settle (the forge is down, or the
claim is not about forge work) cannot wedge the session however it is
reworded. Fails OPEN on any parse trouble, including when the sibling module
it reuses cannot load.
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
MAX_FIRES_PER_TURN = 2

_WHO = r"(your|ezra'?s|the user'?s|the|a|an|human|their|his|her)"
_PR_ACT = r"(merge|merging|mwc|review|approval|sign-?off|go-?ahead|merge words?)"
_WAIT = r"(waiting|waits?|awaiting|blocked|stuck|held|sitting)"

PR_STRONG_RX = re.compile(
    r"\b" + _WAIT + r" (on|for) (" + _WHO + r" )?" + _PR_ACT + r"\b"
    r"|\b(awaits?|awaiting) (" + _WHO + r" )?" + _PR_ACT + r"\b"
    r"|\bready (for (you|ezra|the user) )?to (be )?merged?\b"
    r"|\bready for (" + _WHO + r" )?(merge|review|mwc)\b"
    r"|\bup for (" + _WHO + r" )?(merge|review)\b"
    r"|\bfor (you|ezra|the user) to (merge|review)\b"
    r"|\bneeds? (" + _WHO + r" )?(merge|review|approval|mwc)\b"
    r"|\b(hasn'?t|has not|haven'?t|have not|isn'?t|is not|aren'?t|are not) (yet )?(been )?(merged|reviewed)\b"
    r"|\bnot (yet )?merged\b|\byet to (be )?merged?\b"
    r"|\bpending (merge|review)\b",
    re.I,
)
# Merge wording is about a PR by itself; review or approval wording is not.
MERGE_WORD_RX = re.compile(r"merg|mwc", re.I)

PR_WEAK_RX = re.compile(
    r"\b(is|are|still|remains?|stays?|sitting|sits)( still)? (open|in review|under review|unmerged)\b",
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
# Pending work is about forge state only when it names a forge item or a
# course deliverable.
WORK_CONTEXT_RX = re.compile(
    PR_CONTEXT_RX.pattern
    + r"|\b(issues?|homeworks?|hw ?\d|labs?|worksheets?|handouts?|exams?|midterms?"
    r"|quiz(zes)?|chapters?|assignments?|lectures?|syllabus)\b",
    re.I,
)

# A negation just before the match reports that nothing is pending. The gap
# stops at clause punctuation, so a stray "no," does not negate what follows.
NEGATED_BEFORE_RX = re.compile(
    r"\b(no longer|nothing|none|not|isn'?t|aren'?t|wasn'?t|no)\b[^.!?,;:\n]{0,12}$", re.I
)

# Quoted words are a report of someone's claim, not this message's claim.
QUOTED_RX = re.compile(r'"[^"\n]*"|\u201c[^\u201d\n]*\u201d|^[ \t]*>.*$', re.M)

REF_RX = re.compile(
    r"(?:\b([\w.-]+)/)?([\w.-]+)?#(\d+)\b|/([\w.-]+)/pull/(\d+)\b"
    r"|\b(?:PR|MR|pull request) (\d+)\b|(?<![\w&])!(\d+)\b",
    re.I,
)


def claim_refs(sentence):
    """{(repo or None, number)} named in `sentence`."""
    out = set()
    for m in REF_RX.finditer(sentence):
        if m.group(3):
            out.add(((m.group(2) or "").lower() or None, m.group(3)))
        elif m.group(5):
            out.add((m.group(4).lower(), m.group(5)))
        else:
            out.add((None, m.group(6) or m.group(7)))
    return out


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
# A command reads the forge only through a forge client.
FORGE_CLIENT_RX = re.compile(
    r"(^|[\s;&|(])(gh|glab|curl|wget)\s|\b(check-pr-fully-clean|build-pr-payload)\.py\b"
)
WRITE_CMD_RX = re.compile(
    r"\s(-X|--method)\s*['\"]?(POST|PUT|PATCH|DELETE)\b|\s(-f|-F|--field|--raw-field|--input)\s"
    r"|\bgh (pr|issue) (merge|create|close|edit|comment|reopen|ready|review)\b"
    r"|\bglab (mr|issue) (merge|create|close|update|note|approve)\b",
    re.I,
)
GH_VIEW_RX = re.compile(r"\b(gh pr view|glab mr view)\b([^|;&\n]*)")
VIEW_ARG_RX = re.compile(r"/pull/(\d+)\b|/merge_requests/(\d+)\b|(?<![\w/=-])#?(\d+)\b")
API_ONE_RX = re.compile(
    r"repos/[\w.-]+/([\w.-]+)/pulls/(\d+)(?![\w/])|/merge_requests/(\d+)(?![\w/])"
)
SCRIPT_RX = re.compile(r"\b(?:check-pr-fully-clean|build-pr-payload)\.py\b([^|;&\n]*)")
REPO_FLAG_RX = re.compile(r"(?:-R|--repo)[ =]['\"]?[\w.-]+/([\w.-]+)")
PR_LIST_CMD_RX = re.compile(
    r"\bgh pr (list|status)\b|\bglab mr list\b|\bgh search prs\b"
    r"|/pulls(?:\?|['\"\s]|$)|/merge_requests(?:\?|['\"\s]|$)"
)
WORK_CMD_RX = re.compile(
    r"\bgit (fetch|pull|ls-remote)\b"
    r"|\bgh (issue (view|list)|pr (view|list|status|diff)|search|api|release (view|list))\b"
    r"|\bglab (issue (view|list)|mr (view|list)|api)\b|api\.github\.com"
)

SYSTEM_BLOCK_RX = re.compile(
    r"<system-reminder[\s\S]*?</system-reminder>|^\s*\[SYSTEM NOTIFICATION[^\n]*", re.I
)


def _blocks(m):
    blocks = (m.get("message") or {}).get("content") or m.get("content")
    return blocks if isinstance(blocks, list) else []


def _human_text(text):
    """True when `text` holds something other than harness-injected blocks."""
    return bool(SYSTEM_BLOCK_RX.sub("", str(text or "")).strip())


def _is_user_turn(m):
    """A genuine user message: user role with text beyond tool results and reminders."""
    if m.get("type") != "user" and m.get("role") != "user":
        return False
    content = (m.get("message") or {}).get("content") or m.get("content")
    if isinstance(content, str):
        return _human_text(content)
    return any(
        isinstance(b, dict) and b.get("type") != "tool_result" and _human_text(b.get("text"))
        for b in _blocks(m)
    )


def classify_call(block):
    """(prs, pr_list, work) for one tool_use block.

    prs     -- {(repo or None, number)} whose live state the call read; the
               number "*" stands for the current branch's PR
    pr_list -- True when it read a list or search of PRs (covers any number)
    work    -- True when it read live forge or remote state of any kind
    """
    name = str(block.get("name") or "")
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    prs, pr_list, work = set(), False, False
    if PR_LIST_TOOL_RX.match(name):
        pr_list = work = True
    if PR_ONE_TOOL_RX.match(name) and str(inp.get("method") or "get") == "get":
        num = inp.get("pullNumber", inp.get("issue_number"))
        if num is not None:
            prs.add(((str(inp.get("repo") or "").lower() or None), str(num).lstrip("#")))
    if WORK_TOOL_RX.match(name):
        work = True
    cmd = inp.get("command")
    if isinstance(cmd, str) and FORGE_CLIENT_RX.search(cmd) and not WRITE_CMD_RX.search(cmd):
        flag = REPO_FLAG_RX.search(cmd)
        repo = flag.group(1).lower() if flag else None
        for v in GH_VIEW_RX.finditer(cmd):
            args = REPO_FLAG_RX.sub(" ", v.group(2))
            nums = [next(g for g in a.groups() if g) for a in VIEW_ARG_RX.finditer(args)]
            prs.update((repo, n) for n in (nums[:1] or ["*"]))
        for a in API_ONE_RX.finditer(cmd):
            prs.add(((a.group(1) or "").lower() or None, a.group(2) or a.group(3)))
        for s in SCRIPT_RX.finditer(cmd):
            n = re.search(r"\s#?(\d+)\b", s.group(1))
            if n:
                prs.add((repo, n.group(1)))
        if PR_LIST_CMD_RX.search(cmd):
            pr_list = True
    if isinstance(cmd, str) and not WRITE_CMD_RX.search(cmd) and WORK_CMD_RX.search(cmd):
        work = True
    if prs or pr_list:
        work = True
    return prs, pr_list, work


def turn_reads(path):
    """Live reads since the last user turn, whether a reply went through, and the turn's id."""
    calls, errored, replies = {}, set(), set()
    turn = 0
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for idx, line in enumerate(fh):
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if not isinstance(m, dict):
                    continue
                if _is_user_turn(m):
                    calls, errored, replies, turn = {}, set(), set(), idx
                for b in _blocks(m):
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        if REPLY_TOOL_RX.match(str(b.get("name") or "")):
                            replies.add(b.get("id"))
                        else:
                            calls[b.get("id")] = classify_call(b)
                    elif b.get("type") == "tool_result" and b.get("is_error"):
                        errored.add(b.get("tool_use_id"))
    except Exception:
        pass
    prs, pr_list, work = set(), False, False
    for cid, (p, lst, w) in calls.items():
        if cid in errored:
            continue
        prs |= p
        pr_list = pr_list or lst
        work = work or w
    replied = any(r not in errored for r in replies)
    return prs, pr_list, work, replied, turn


def _covered(ref, prs):
    repo, num = ref
    return any(n == num and (repo is None or r is None or r == repo) for r, n in prs)


def _negated(prose, start):
    return bool(NEGATED_BEFORE_RX.search(prose[max(0, start - 30):start]))


def find_claim(prose, prs, pr_list, work):
    """(kind, phrase, missing_refs) for the first unsupported claim, or None."""
    for rx, strong in ((PR_STRONG_RX, True), (PR_WEAK_RX, False)):
        for m in rx.finditer(prose):
            if _negated(prose, m.start()):
                continue
            sentence = sentence_around(prose, m.start(), m.end())
            merge_word = strong and MERGE_WORD_RX.search(m.group(0))
            if not merge_word and not PR_CONTEXT_RX.search(sentence):
                continue
            if pr_list:
                continue
            named = claim_refs(sentence)
            missing = sorted((r for r in named if not _covered(r, prs)), key=lambda r: int(r[1]))
            if named and not missing:
                continue
            if not named and prs:
                continue
            return "pr", m.group(0), missing
    if work:
        return None
    for m in WORK_RX.finditer(prose):
        if _negated(prose, m.start()):
            continue
        if not WORK_CONTEXT_RX.search(sentence_around(prose, m.start(), m.end())):
            continue
        return "work", m.group(0), []
    return None


def reason_for(kind, phrase, missing):
    if kind == "pr":
        which = (
            "PR " + ", ".join(f"{r or ''}#{n}" for r, n in missing)
            if missing else "the PR it names"
        )
        return (
            "[hook: no-unfetched-pr-state-claim] This message says a PR is still "
            f"pending (\"{phrase.strip()}\"), and nothing since the last user turn "
            f"read {which} live. A handoff summary, a memory note or an earlier "
            "turn is a reading from the past; on 2026-10-29 one said mcsg#52 was "
            "waiting on the user's merge after it had merged.\n\n"
            "Fetch the PR now (GitHub MCP pull_request_read method get, `gh pr "
            "view N -R O/R`, `gh api repos/O/R/pulls/N`, or hearthbot list_prs), "
            "then state what the reading says. If the forge cannot be reached, "
            "say the state is unverified. ai-config#4834."
        )
    return (
        "[hook: no-unfetched-pr-state-claim] This message says work is still to "
        f"do (\"{phrase.strip()}\"), and nothing since the last user turn read "
        "the forge or the remote. A memory note or handoff is a reading from "
        "the past; on 2026-10-29 one proposed drafting Homework 2-6 after it had "
        "merged.\n\n"
        "Check live state first (list or search the repo's PRs and issues, read "
        "the file on the default branch, or `git fetch` then `git log "
        "origin/main`), then restate. If the claim is not about forge work, "
        "send it again unchanged; this fires once per message. ai-config#4834."
    )


def _may_fire(text, path, turn):
    """Record this firing; False when this text already fired or the turn's cap is spent."""
    scope = hashlib.sha256(f"{path}\0{turn}".encode()).hexdigest()[:16]
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    ledger = os.path.join(tempfile.gettempdir(), f".claude-pr-state-claim-guard-{scope}")
    try:
        with open(ledger, encoding="utf-8") as fh:
            seen = fh.read().split()
    except Exception:
        seen = []
    if key in seen or len(seen) >= MAX_FIRES_PER_TURN:
        return False
    try:
        with open(ledger, "a", encoding="utf-8") as fh:
            fh.write(key + "\n")
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
        prs, pr_list, work, _, turn = turn_reads(path)
    else:
        text = last_assistant_text(path)
        if not text:
            return 0
        prs, pr_list, work, replied, turn = turn_reads(path)
        if replied:
            return 0

    prose = QUOTED_RX.sub(" ", strip_code(text))
    hit = find_claim(prose, prs, pr_list, work)
    if not hit or not _may_fire(text, path, turn):
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
