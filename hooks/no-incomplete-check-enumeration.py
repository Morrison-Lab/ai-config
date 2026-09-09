#!/usr/bin/env python3
"""Stop-hook guard: catch declaring a PR clean on a short check list alone.

`gh pr checks` does not enumerate every check run on a head. Measured
2026-08-19 on ucdavis/bcs#651 at a5f4f3f2: it printed 21 rows, all passing,
while `commits/<sha>/check-runs` returned 24 runs, one of them a `failure`
(`review / antigravity-review`). The PR was reported fully clean on the
strength of the shorter list.

GraphQL `statusCheckRollup` is a different short surface, not a second
measurement of that omission. On Morrison-Lab/ai-config#2277 (2026-08-26)
the rollup matched the endpoint (8==8); the false Ready-for-merge claim
failed because the complete instrument (`check-pr-fully-clean.py`) exited 1
for missing automated review. The hook still treats the rollup as a partial
reading: a terminal clean claim needs the complete instrument, not any short
CI list that happens to look green.

That omission (for `gh pr checks`) is invisible by construction. A short list
and a clean list are the same observable -- there is no gap in the output, no
warning, and the counts look healthy. So the reader cannot tell a complete
enumeration from an incomplete one, and neither can the author, which is why
this is a hook rather than a rule to remember.

It is distinct from its sibling `no-stale-pr-status.py`, which asks whether a
reading is CURRENT. A reading can be perfectly current and still incomplete;
that hook's RX_QUERY accepts `gh pr checks` / `statusCheckRollup` as a fresh
reading, correctly for staleness and insufficiently for a terminal claim.
This one asks whether the reading could authorize the claim.

The original condition, decidable from the transcript:

    message declares the PR clean (original vocabulary: "fully clean",
        "ready to/for merge", "safe to merge", "nothing failing/red",
        "all/every checks green")
    AND a partial reading (`gh pr checks` or `statusCheckRollup`) appears
    AND no complete enumeration appears after the last push

where a complete read is `check-pr-fully-clean.py` (exit status + finding
bullets). A paginated `commits/<sha>/check-runs` read covers the check-run
half only and does not authorize "fully clean" / "ready to merge".

EXTENSION -- two gaps measured 2026-09-09, written up in ai-config#3472
-------------------------------------------------------------------------------
A session dispatched sidecar subagents to open PRs. One subagent's own
report read "status: CLEAN / MERGEABLE, CI green, @claude review verdict
CLEAN"; the conducting session relayed that as "fully clean: CI green,
@claude verdict CLEAN, no open threads" to the user -- without itself
running any instrument, partial or complete. `check-pr-fully-clean.py`
exited 1: a verdict-bearing review had landed AFTER the subagent's report.
That false claim was made in chat on Morrison-Lab/ai-config#3468 -- the
subject PR where it happened, not a write-up of it; #3468's own thread
never discusses PR-readiness claims.
A second PR was reported "green, awaiting your merge" four times across
separate messages; the instrument found no automated review had EVER run on
it (only Copilot quota-exhaustion notices, which are not reviews). That
claim was made in chat on d-morrison/macros#87 -- again the subject PR
where it happened, not a write-up; #87's own body is a LaTeX `\v` bug fix
and never mentions PR-readiness claims either. ai-config#3472 is the
write-up covering both.

Two distinct misses, both folded into this hook rather than split into a
sibling, because both are instances of the same underlying question this
file already asks -- "could the reading in this transcript authorize the
claim?" -- just answered over a wider evidence set:

  (a) VOCABULARY: "green, awaiting your merge" asserts the identical
      terminal fact as "ready to merge" (nothing more to check, go ahead
      and merge) but used none of RX_DECLARE's original phrases, so it
      tripped nothing. RX_DECLARE_MERGE_READY covers this family.

  (b) EVIDENCE SOURCE: a dispatched subagent's report is a CLAIM, not an
      instrument reading, and it is stale by construction -- the agent
      stops, then reviews and checks keep landing. The original condition
      required a *partial* reading (`gh pr checks` etc.) to even consider
      firing; relaying a subagent's report with NO reading of any kind by
      the conducting session tripped nothing at all. `last_subagent` tracks
      the most recent point a dispatched Agent/Task call's result landed in
      THIS transcript (via tool_use_id correlation, the same technique
      `remind-brief-premises.py` uses to attribute a value to a session's
      own agent calls); a complete read is now required after that point
      too, not just after the last push.

      Scoped to the CLAIM's own evidence, not the whole transcript: a
      subagent report counts as involved only if it landed after the CI
      reading in play (`last_partial`) or its own target PR matches the PR
      named in the claim (`_relevant_last_subagent`). An adversarial review
      of an earlier draft reproduced a regression where this was scoped
      globally instead -- a totally unrelated `Agent` dispatch anywhere
      earlier in the session flipped the original BLOCK case to a WARN,
      which would have silently disarmed the hook's core protection for
      most real sessions, since this corpus pushes routine subagent
      dispatch.

Both extensions WARN (`systemMessage`) rather than BLOCK. The original,
narrowly-scoped condition -- original vocabulary, a partial CI reading in
play, no subagent involved -- keeps blocking exactly as before (same cases,
same verdicts; see test file). Warning rather than blocking for the wider
evidence set follows the standing instruction for this rule: prefer warning
where the vocabulary or evidence is more heterogeneous than the original
"fully clean" family, and a subagent's report is common and not
automatically suspect -- it is the *lack of a fresh instrument reading after
it* that is the problem, and that is a softer, more inferential signal than
"you quoted `gh pr checks` and then said fully clean."

Deliberately narrow on the assertion side either way. A progress report --
"13 pass, 5 pending" -- is honest and must not trip this; only a terminal
claim does.

Fails OPEN on any parse trouble, and fires at most once per distinct message,
so it cannot wedge a session.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Terminal claims only. "N pass, M pending" is a progress report and is fine.
# UNCHANGED from the original hook -- this is the vocabulary the BLOCK path
# still keys on; see RX_DECLARE_MERGE_READY below for the newer, WARN-only
# vocabulary added 2026-09-09.
RX_DECLARE = re.compile(
    r"\bfully clean\b|"
    r"\bready (to|for) merge\b|"
    r"\bready for you to merge\b|"
    r"\bsafe to merge\b|"
    r"\bnothing (is )?(failing|red)\b|"
    r"\b(all|every) checks? (are |is )?green\b",
    re.I,
)

# Merge-readiness vocabulary that asserts the same terminal fact -- "nothing
# left to check, go ahead and merge" -- without using RX_DECLARE's original
# words. Measured 2026-09-09 (write-up: ai-config#3472; the claim itself was
# made in chat on d-morrison/macros#87, not a write-up): "green, awaiting
# your merge" was repeated across four separate messages and tripped
# nothing. Matched separately from RX_DECLARE because a claim resting on
# THIS vocabulary only ever WARNS below, never blocks.
RX_DECLARE_MERGE_READY = re.compile(
    r"\bawaiting (your )?merge\b|"
    r"\bgood to merge\b|"
    r"\bgood for you to merge\b|"
    r"\bjust needs (your )?merge\b|"
    r"\bneeds (only )?your merge\b|"
    r"\byour call to merge\b|"
    r"\bup to you to merge\b",
    re.I,
)

# RX_DECLARE_MERGE_READY has no PR/git anchoring of its own, so a plain
# data-frame merge ("the covariates are good to merge with the outcome
# table") shares its vocabulary without naming a PR at all -- a real risk
# in a statistics repo. Require a nearby `#N` reference or a PR/branch
# token before treating a match as a merge-readiness claim.
RX_PR_ANCHOR = re.compile(
    r"#\d{1,6}\b|\bpull requests?\b|\bPRs?\b|\bbranch(es)?\b",
    re.I,
)
_ANCHOR_WINDOW = 80


def _anchored_merge_ready(text):
    """Return the first RX_DECLARE_MERGE_READY match that has a PR/git
    anchor within _ANCHOR_WINDOW characters, or None.
    """
    for m in RX_DECLARE_MERGE_READY.finditer(text):
        lo = max(0, m.start() - _ANCHOR_WINDOW)
        hi = m.end() + _ANCHOR_WINDOW
        if RX_PR_ANCHOR.search(text[lo:hi]):
            return m
    return None

# Incomplete instruments for a terminal clean claim.
# `gh pr checks` can omit runs (bcs#651); `statusCheckRollup` is a short
# rollup that is not the complete instrument (ai-config#2277). Paginated
# `commits/<sha>/check-runs` and MCP `get_check_runs` cover the check-run
# half only --- same demotion as in RX_COMPLETE's docstring.
RX_PARTIAL = re.compile(
    r"gh\s+pr\s+checks|"
    r"\bstatusCheckRollup\b|"
    r"commits/[0-9a-f]{7,40}/check-runs|"
    r"\bget_check_runs\b",
    re.I,
)

# Only the fully-clean script authorizes a terminal clean / ready-to-merge
# claim. A paginated check-runs read is the check half only (ai-config#2277).
RX_COMPLETE = re.compile(
    r"(?<!test_)\bcheck-pr-fully-clean\.py",
    re.I,
)

RX_PUSH = re.compile(r"git\s+push|create_or_update_file|push_files", re.I)

# A PR reference in the claim itself, so the warning can name it instead of
# saying "the PR" generically. First match wins; good enough for a hook that
# fails open on anything it cannot parse.
RX_PR_REF = re.compile(r"#\d{1,6}\b")

# Tool names a subagent dispatch arrives under, for correlating a dispatch's
# `tool_use` id with the `tool_result` that later carries its report. Same
# set `remind-brief-premises.py` uses for the identical correlation.
AGENT_TOOLS = {"Agent", "Task", "agent", "task", "dispatch_agent", "run_agent"}


def scan(path):
    """Return (last_push, last_partial, last_complete, subagent_events, text).

    `subagent_events` is a list of `(index, pr_refs)` for every
    `tool_result` in THIS transcript whose `tool_use_id` belongs to a
    dispatched Agent/Task call -- i.e. every point a subagent's report
    landed. `pr_refs` is the set of `#N` references found in that
    dispatch's own input plus its report's content, so a later relevance
    check can tell which PR the subagent was actually working on.
    Relevance to a *specific* claim (in-window vs. matching target) is
    scored in `main()`, not here -- see the module docstring's EXTENSION
    section, finding (1) in ai-config#3472.
    """
    last_push = last_partial = last_complete = -1
    agent_pr_refs = {}
    subagent_events = []
    text = ""
    i = 0
    with open(path, errors="ignore") as fh:
        for line in fh:
            i += 1
            try:
                m = json.loads(line)
            except Exception:
                continue
            role = m.get("type") or m.get("role")
            blocks = (m.get("message") or {}).get("content")
            if blocks is None:
                blocks = m.get("content") or []

            # Antigravity tool calls
            if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL" or "tool_calls" in m:
                for tc in m.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        blob = (tc.get("name") or "") + " " + json.dumps(tc.get("args") or tc.get("input") or {})
                        if RX_PUSH.search(blob):
                            last_push = i
                        if RX_COMPLETE.search(blob):
                            last_complete = i
                        elif RX_PARTIAL.search(blob):
                            last_partial = i

            # Antigravity text content
            if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
                raw_content = m.get("content")
                if isinstance(raw_content, str) and raw_content.strip():
                    text = raw_content

            if isinstance(blocks, list):
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        bname = b.get("name") or ""
                        blob = bname + " " + json.dumps(b.get("input") or {})
                        if RX_PUSH.search(blob):
                            last_push = i
                        if RX_COMPLETE.search(blob):
                            last_complete = i
                        elif RX_PARTIAL.search(blob):
                            last_partial = i
                        if bname in AGENT_TOOLS:
                            tid = b.get("id")
                            if tid:
                                agent_pr_refs[tid] = set(RX_PR_REF.findall(blob))
                    elif b.get("type") == "tool_result":
                        tid = b.get("tool_use_id") or b.get("id")
                        if tid and tid in agent_pr_refs:
                            content = b.get("content")
                            content_text = content if isinstance(content, str) else json.dumps(content or "")
                            pr_refs = agent_pr_refs[tid] | set(RX_PR_REF.findall(content_text))
                            subagent_events.append((i, pr_refs))
                    elif b.get("type") == "text" and role == "assistant":
                        if b.get("text", "").strip():
                            text = b["text"]
            elif isinstance(blocks, str) and role == "assistant" and blocks.strip():
                text = blocks
    return last_push, last_partial, last_complete, subagent_events, text


def already_fired(text):
    """Fire at most once per distinct message, so a block cannot wedge a session."""
    digest = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()[:16]
    marker = os.path.join(tempfile.gettempdir(), "no-incomplete-check-enum-" + digest)
    if os.path.exists(marker):
        return True
    try:
        open(marker, "w").close()
    except Exception:
        pass
    return False


# How far from the claim phrase a `#N` may sit and still be taken as its
# subject. Past this, the message is naming something else -- another PR, a
# closed duplicate, an issue -- and a guess is worse than saying nothing,
# because the label is carried into the remediation command the user runs.
_LABEL_WINDOW = 120


def _pr_label(text, hit=None):
    """Name the PR the CLAIM is about, or decline to name one.

    A message routinely mentions several PRs and issues -- "#100 was closed
    as a duplicate. #200 is green, awaiting your merge." -- and the first
    reference is very often not the subject of the terminal claim. The
    payload's remediation command carries this label, so naming the wrong
    one points the user's instrument run at the wrong PR (#3475 round 5).

    No heuristic over free text can always pick right, so this one is
    bounded rather than clever: the nearest reference within
    `_LABEL_WINDOW` characters of the claim phrase, preferring one before
    it, since a claim's subject usually precedes it. Outside that window it
    returns the generic label. Round 6 found the unbounded form reaching
    across a whole message to grab a reference the text itself called
    unrelated -- a confident wrong label, which is worse than an honest
    vague one.
    """
    generic = "the PR you named"
    if hit is None:
        m = RX_PR_REF.search(text)
        return m.group(0) if m else generic
    pos = hit.start()
    before = [m for m in RX_PR_REF.finditer(text)
              if m.end() <= pos and pos - m.end() <= _LABEL_WINDOW]
    if before:
        return before[-1].group(0)
    after = RX_PR_REF.search(text, pos)
    if after and after.start() - hit.end() <= _LABEL_WINDOW:
        return after.group(0)
    return generic


def _relevant_last_subagent(subagent_events, last_partial, claim_pr_refs):
    """Scope subagent involvement to THIS claim's own evidence chain
    (ai-config#3472, finding 1), rather than to the whole transcript.

    A subagent report counts as involved in the claim only if it sits in
    the relevant evidence window -- landed AFTER the CI reading in play
    (`last_partial`), i.e. after the point whose evidence the claim could
    be resting on -- or if its own target (the PR named in its dispatch or
    its report) matches the PR named in the claim. A totally unrelated
    earlier dispatch (different PR, before any CI reading was even taken)
    must not count: the reviewer reproduced that flipping the original
    BLOCK case to a WARN.

    Returns the highest transcript index of a relevant event, or -1.
    """
    relevant = -1
    for idx, pr_refs in subagent_events:
        # A window exists only if there IS a CI reading to be after.
        # With `last_partial == -1`, `idx > -1` is true for EVERY
        # event, which re-admits the whole transcript through the
        # very branch that was scoped to stop it (#3475 finding 2).
        in_window = last_partial >= 0 and idx > last_partial
        matches_target = bool(claim_pr_refs) and bool(pr_refs & claim_pr_refs)
        if in_window or matches_target:
            relevant = max(relevant, idx)
    return relevant


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_push, last_partial, last_complete, subagent_events, text = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit_core = RX_DECLARE.search(text)
    hit_merge_ready = _anchored_merge_ready(text)
    hit = hit_core or hit_merge_ready
    if not hit:
        return 0

    claim_pr_refs = set(RX_PR_REF.findall(text))
    last_subagent = _relevant_last_subagent(subagent_events, last_partial, claim_pr_refs)

    # A complete enumeration after BOTH the last push AND the last subagent
    # report covers the claim -- a subagent's report is an event that can
    # move the ground out from under an earlier complete read exactly the
    # way a push does (a review can land after the subagent stops).
    reading_needed_since = max(last_push, last_subagent)
    if last_complete > reading_needed_since:
        return 0

    # Nothing to warn about: no partial CI reading, and no subagent report
    # either -- the claim rests on neither a short CI list nor a dispatched
    # agent's say-so.
    if last_partial < 0 and last_subagent < 0:
        return 0

    if already_fired(text):
        return 0

    pr_label = _pr_label(text, hit)

    # BLOCK only the narrow, original case this hook has always covered:
    # original clean-claim vocabulary, a partial CI reading in play, no
    # subagent involved. Everything the 2026-09-09 extension added --
    # broader merge-readiness vocabulary, or a subagent's report as the
    # only evidence -- WARNS instead. See the module docstring's EXTENSION
    # section for why.
    # `last_partial >= 0` is implied here: the guard above returned when
    # both were negative, so `last_subagent < 0` already forces it.
    is_original_ci_case = bool(hit_core) and last_subagent < 0

    if is_original_ci_case:
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"Your message declares a PR clean -- \"{hit.group(0).strip()}\" -- but the "
                "supporting reading in this transcript is `gh pr checks`, "
                "`statusCheckRollup`, paginated `commits/<sha>/check-runs`, or "
                "MCP `get_check_runs` --- none of which is the complete instrument for a "
                "terminal clean claim.\n\n"
                "Measured 2026-08-19 on ucdavis/bcs#651 at a5f4f3f2: `gh pr checks` printed "
                "21 rows, all passing, while the commit endpoint returned 24 runs including "
                "a `failure`. The PR was reported fully clean on the shorter list. A short "
                "list and a clean list look identical -- there is no gap in the output and "
                "no warning, so neither the reader nor you can tell them apart.\n\n"
                "`statusCheckRollup` is a different short surface: on ai-config#2277 "
                "(2026-08-26) it matched the endpoint (8==8), but a Ready-for-merge claim "
                "still rested on it instead of `check-pr-fully-clean.py`, which exited 1 "
                "for missing automated review.\n\n"
                f"Run an instrument that can authorize the claim about {pr_label}, then "
                "report from it:\n\n"
                "    python3 scripts/check-pr-fully-clean.py <PR> -R <owner>/<repo>\n\n"
                "reading its EXIT STATUS three ways -- 0 clean, 1 a verdict of not-clean "
                "(confirm the output has `  - ` finding bullets, since an unhandled "
                "exception also exits 1), anything else the check having failed to answer.\n\n"
                "For the check-run half only, read the endpoint directly with --paginate "
                "(an unfinished or failing run on page 2 returns the same empty result as a "
                "clean head):\n\n"
                "    gh api \"repos/<owner>/<repo>/commits/<sha>/check-runs?per_page=100\" "
                "--paginate --jq '.check_runs[]|select(.conclusion!=\"success\" and "
                ".conclusion!=\"skipped\")|\"\\(.conclusion) \\(.name)\"'\n\n"
                "That check-runs read does not authorize a terminal fully-clean claim; "
                "only `check-pr-fully-clean.py` does. "
                "Note the repo may also use legacy commit statuses, which that endpoint does "
                "not cover; add `commits/<sha>/status` where it does.\n\n"
                "If you meant a progress report rather than a terminal claim, say the counts "
                "without declaring the PR clean -- \"13 pass, 5 pending\" trips nothing."
            ),
        }))
        return 0

    # WARN path: broader vocabulary and/or a subagent's report as the
    # evidence, per the 2026-09-09 extension (ai-config#3472). Derive the
    # explanation from the condition that ACTUALLY fired -- not from an
    # independent predicate that can disagree with it (finding 2): we are
    # here only because `is_original_ci_case` was False, which by
    # construction means `(not hit_core) or (last_subagent >= 0)`, so at
    # least one of the two branches below always applies, and both apply
    # when both reasons are in play.
    # Derive the explanation TOTALLY, from which evidence is actually the
    # newest, rather than from independent predicates. Three review rounds
    # of #3475 each found another transcript where the independent form
    # emitted a false sentence or no sentence at all: a push blamed on a
    # subagent, a tie yielding an empty note, and a fresher partial reading
    # while the message still blamed the subagent. An argmax cannot have
    # that shape -- every reachable state names the evidence it found.
    evidence = [
        (last_subagent, "subagent"),
        (last_partial, "partial"),
        (last_push, "push"),
        (last_complete, "complete"),
    ]
    newest = max(v for v, _ in evidence)
    kinds = {k for v, k in evidence if v == newest and v >= 0}

    reasons = []
    # `complete` can never be the SOLE newest kind here: the early return
    # above fires when it strictly exceeds both push and subagent, so
    # reaching this line with `complete` newest means it is tied with
    # something. A `len(kinds) > 1` conjunct would be inert -- confirmed by
    # exhaustive enumeration over the 920 reachable states (#3475 round 4).
    if "complete" in kinds:
        # A complete read shares the newest index with something it would
        # have to postdate. Same turn, so the transcript cannot order them.
        reasons.append(
            "A complete instrument read and the push (or subagent report) it "
            "would have to postdate are in the SAME turn, so the transcript "
            "cannot say which came first. Re-run the instrument in a turn of "
            "its own, so the reading is unambiguously the later one."
        )
    else:
        if "subagent" in kinds:
            reasons.append(
                "The most recent evidence in this transcript for that claim is a "
            "dispatched subagent's OWN report, not a reading you ran yourself. "
            "A subagent's report is a claim, not an instrument, and it is stale "
            "by construction: the agent stops, and then reviews and checks keep "
            "landing. Measured 2026-09-09 (write-up: ai-config#3472; the false "
            "claim itself was made in chat on Morrison-Lab/ai-config#3468, not a "
            "write-up): a subagent reported \"status: CLEAN / MERGEABLE\", and "
            "`check-pr-fully-clean.py` later exited 1 because a verdict-bearing "
            "review landed AFTER the subagent finished."
            )
        if "partial" in kinds:
            reasons.append(
                "The most recent reading in this transcript is a SHORT CI surface -- "
            "`gh pr checks`, `statusCheckRollup`, a paginated check-runs "
            "read. A short list and a clean list look identical, and none of "
            "them carries a review verdict at all, so none can authorize a "
            "terminal claim."
            )
        if "push" in kinds and last_complete >= 0:
            reasons.append(
                "A complete instrument read is in this transcript, but a "
            "`git push` landed after it, so it describes a head that is "
            "no longer this PR's. A verdict covers the commit it named; "
            "re-run the instrument against what you just pushed."
            )
        if "push" in kinds and last_complete < 0:
            reasons.append(
                "A `git push` is the newest thing in this transcript, and no "
                "complete instrument read appears anywhere in it -- only a "
                "short CI surface, which the push has now outdated as well. "
                "Run the instrument against the head you just pushed."
            )
    if not hit_core:
        reasons.append(
            "This phrasing (\"awaiting merge\", \"good to merge\", \"just needs "
            "your merge\", ...) asserts the same terminal fact as \"ready to "
            "merge\" -- nothing left to check, go ahead -- without the vocabulary "
            "this guard originally keyed on. Measured 2026-09-09 (write-up: "
            "ai-config#3472; the claim itself was made in chat on "
            "d-morrison/macros#87, not a write-up): \"green, awaiting your "
            "merge\" was repeated across four separate messages, and "
            "`check-pr-fully-clean.py` found no automated review had ever run "
            "on the PR at all."
        )
    if not reasons:
        # Unreachable by the argmax above (the guard earlier guarantees at
        # least one of last_partial / last_subagent is non-negative), but a
        # guard against a claim with no stated basis is cheaper than the
        # empty explanation #3475 round 2 shipped.
        reasons.append(
            "No reading in this transcript postdates the evidence this claim "
            "rests on. Run the instrument and report from its exit status."
        )
    source_note = "\n\n".join(reasons)

    print(json.dumps({
        "systemMessage": (
            f"Your message makes a terminal merge-readiness claim about {pr_label} "
            f"-- \"{hit.group(0).strip()}\" -- with no `check-pr-fully-clean.py` run "
            "in this transcript that postdates the most recent push or subagent "
            "report.\n\n"
            f"{source_note}\n\n"
            f"Before relaying this, run and read the instrument yourself:\n\n"
            f"    python3 scripts/check-pr-fully-clean.py <PR> -R <owner>/<repo>\n\n"
            "reading its EXIT STATUS: 0 clean, 1 a verdict of not-clean (confirm "
            "the output has `  - ` finding bullets, since an unhandled exception "
            "also exits 1), anything else the check having failed to answer.\n\n"
            "If this is a progress report rather than a terminal claim, say the "
            "counts without the merge-readiness phrasing -- \"13 pass, 5 pending\" "
            "trips nothing."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
