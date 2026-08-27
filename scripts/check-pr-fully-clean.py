#!/usr/bin/env python3
"""Automated verification tool for ARDI / fully-clean status.

Verifies that:
1. All GitHub Actions check runs for the PR's HEAD commit SHA are completed and passing.
2. An automated review comment evaluating the exact HEAD commit SHA has been posted.
3. All review comments evaluating the HEAD commit SHA contain zero findings, and no active CHANGES_REQUESTED or REJECTED state exists on the PR.
4. Every reviewer's latest verdict-bearing statement is clean.

Criterion 4 is deliberately scoped wider than criteria 2 and 3, which look only
at items evaluating the current HEAD SHA. An explicit "Needs more work" posted
against an EARLIER commit falls outside them entirely, and a later comment that
states no verdict raises no finding either -- so the PR reads clean while its
last actual verdict was "Needs more work". Absence of a verdict is not a
clearing: only a later CLEAN verdict from the SAME reviewer supersedes that
reviewer's earlier not-clean (the ordinary ARDI iterate path, #1275).
A later CLEAN from a different reviewer does not: any reviewer's standing
not-clean vetoes, including under mwc (ai-config#2274).
See shared/workflow/fully-clean.md.

Which repository is being asked about is resolved once, at startup, and threaded
through every `gh` call. It is NOT hardcoded: the same value reaches the PR
lookup and the check-runs query, so the two halves cannot describe different
repositories. Pass `-R/--repo OWNER/REPO` to target a repo other than the
current checkout's. See Morrison-Lab/ai-config#1391.

Exit codes:
0: Fully clean (safe to end ARDI loop)
1: Not clean (in-progress checks, failing checks, missing review, findings present,
   or a standing not-clean verdict that nothing later superseded)
2: Called wrong, or the repository could not be resolved. Deliberately distinct
   from 1, so "you invoked this incorrectly" is never read as "the PR is not
   clean" (shared/principles/fail-fast.md).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import strip_fences  # noqa: E402
from typing import Dict, List, Optional, Tuple

# The status glyphs below are non-ASCII, and a Windows console defaults to
# cp1252, which cannot encode them -- so every run raised UnicodeEncodeError
# before reaching its verdict, including the test suite. Degrade the glyph
# rather than the run; on a UTF-8 console this changes nothing.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")


# `raise SystemExit("message")` prints the message but exits **1**, which is
# this script's "not clean" code -- so a usage or environment error would have
# been read as a verdict about the PR. The exit code is set explicitly for that
# reason.
USAGE_EXIT = 2


def die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(USAGE_EXIT)


def run_cmd(cmd: List[str]) -> str:
    try:
        # `encoding` is load-bearing on Windows, not tidiness. Without it the
        # locale codec decodes, which is cp1252 there, and cp1252 mis-handles
        # UTF-8 in TWO ways -- the quieter one being the commoner:
        #
        #   * Silent mojibake, for most non-ASCII. Only five bytes are
        #     undefined in cp1252 (0x81, 0x8D, 0x8F, 0x90, 0x9D), so a smart
        #     quote (e2 80 9c) or U+1F600 (f0 9f 98 80) decodes WITHOUT error
        #     into wrong characters. The JSON still parses, so callers matching
        #     verdict phrases against a review body were silently matching
        #     against corrupted text.
        #   * A hard failure, only when one of those five bytes appears --
        #     U+1F44D is f0 9f 91 8d, which carries 0x8D. The decode then
        #     raises inside subprocess's reader THREAD, so the thread dies,
        #     `returncode` stays 0, and `stdout` is left as None. The
        #     returncode guard below passes and the caller sees an
        #     AttributeError rather than anything about decoding.
        #
        # Strict UTF-8 fixes both: GitHub serves UTF-8, so strict is correct,
        # and errors="replace" would preserve the silent-corruption case this
        # is meant to end. `text=True` is omitted deliberately -- per
        # subprocess's own docs, "Text mode is triggered by setting any of
        # text, encoding, errors or universal_newlines", so `encoding` already
        # selects it and naming both invites the reader to think one of them is
        # doing separate work.
        res = subprocess.run(cmd, capture_output=True, encoding="utf-8", check=False)
    except FileNotFoundError:
        # A missing binary is an ENVIRONMENT failure, and it must not surface as
        # exit 1 -- that is this script's "not clean" code, so an uninstalled
        # `gh` would be reported as a verdict about the PR. Handled here rather
        # than at one call site: `resolve_repo` guarded its own call while every
        # other `gh` call still raised a raw traceback, which is the partial
        # guard fail-fast.md describes -- the guard's presence reads as the
        # hazard being handled everywhere. See Morrison-Lab/ai-config#1330 for
        # the standing dependency on `gh` itself, which this does not remove.
        die(
            f"`{cmd[0]}` is not installed or not on PATH.\n"
            "This script requires the GitHub CLI; -R cannot substitute for it."
        )
    if res.returncode != 0:
        # `stderr` is exposed to the same reader-thread decode failure as
        # `stdout`, so it can be None here even though the exit code arrived.
        #
        # Splitting the two cases rather than substituting a placeholder for
        # both. A non-zero exit WITH readable stderr is a fact about the command
        # -- a 404 on a deleted run, say -- and `_resolve_run_head_sha` is
        # entitled to catch that RuntimeError and degrade to "cannot resolve the
        # SHA". A non-zero exit with an UNREADABLE stderr is an environment
        # failure, and routing it through RuntimeError would let that same catch
        # launder it into "No review comment has been posted evaluating HEAD
        # SHA ..." -- exit 1 with a finding bullet, which is the laundering this
        # whole change exists to close. `die` exits 2 and raises SystemExit,
        # which derives from BaseException and so escapes both that catch and
        # the broad `except Exception` wrappers elsewhere.
        if res.stderr is None:
            die(
                f"Command failed ({' '.join(cmd)}) and its stderr could not be "
                "read or decoded, so the reason is unavailable. This is an "
                "environment failure, not a verdict about the PR."
            )
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {res.stderr.strip()}")
    if res.stdout is None:
        # Defence in depth for the reader-thread failure described above, and
        # for any future cause of it.
        #
        # `die` rather than `raise RuntimeError`, for two independent reasons,
        # both of which a RuntimeError gets wrong:
        #   * `_resolve_run_head_sha` wraps its `run_cmd` call in
        #     `except RuntimeError: return None`. A RuntimeError here would be
        #     swallowed there, and the caller would go on to report "No review
        #     comment has been posted evaluating HEAD SHA ..." -- exit 1 WITH a
        #     finding bullet, which is the one shape fully-clean.md's crash test
        #     (rc==1 plus no `  - ` bullets) cannot distinguish from a verdict.
        #   * SystemExit(USAGE_EXIT) exits 2, so an environment failure stays
        #     out of the "not clean" code, which is why USAGE_EXIT exists.
        die(
            f"Command produced no capturable stdout ({' '.join(cmd)}); "
            "its output could not be read or decoded. This is an environment "
            "failure, not a verdict about the PR."
        )
    return res.stdout.strip()


# `gh pr view --repo` accepts a URL as well as OWNER/REPO, while
# `gh api repos/{repo}/...` accepts only the bare OWNER/REPO. Interpolating one
# spelling into both call sites is how the two halves came apart in the first
# place, so a value that cannot serve both is refused rather than passed on.
REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


def resolve_repo(explicit: str = "") -> str:
    """The OWNER/REPO every `gh` call in this run will name.

    Defaults to the current checkout's repository rather than to a literal.
    Hardcoding a literal is the defect this function exists to remove: the PR
    lookup resolved the repo from the working directory while the check-runs
    query named `Morrison-Lab/ai-config`, so outside this repo the script read
    the PR from one repository and its checks from another -- loudly when the
    SHA did not exist there, and silently wrong when it did.

    Exits 2 rather than falling back when the repository cannot be resolved.
    A fallback is what made the wrong answer quiet.
    """
    if explicit:
        repo, source = explicit.strip(), "--repo"
    else:
        try:
            repo = run_cmd(
                ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
            )
        except RuntimeError as exc:
            # `gh` itself missing is handled in run_cmd, because -R cannot
            # substitute for it. This branch is the narrower case where `gh`
            # ran and could not name a repo -- not a checkout, no remote, not
            # authenticated -- and there -R IS the right hint.
            die(
                f"Cannot resolve the repository from the current directory: {exc}\n"
                "Run this from inside a git checkout, or pass -R OWNER/REPO."
            )
        source = "the current checkout"

    if not REPO_PATTERN.match(repo):
        die(
            f"Repository {repo!r} (from {source}) is not in OWNER/REPO form.\n"
            "Pass -R OWNER/REPO -- a URL is accepted by `gh pr view` but not by "
            "the check-runs API path, and a value that cannot serve both is what "
            "lets the two halves disagree."
        )
    return repo


def get_pr_info(pr_num: str, repo: str) -> Tuple[str, str, str, str, str]:
    out = run_cmd(["gh", "pr", "view", pr_num, "--repo", repo, "--json",
                   "headRefOid,headRefName,state,commits,reviewDecision"])
    data = json.loads(out)
    head_sha = data["headRefOid"]
    commits = data.get("commits", [])
    commit_date = ""
    if commits:
        commit_date = commits[-1].get("committedDate", "")
    review_decision = data.get("reviewDecision") or ""
    return head_sha, data["headRefName"], data["state"], commit_date, review_decision


def _is_bot_author(login: Optional[str]) -> bool:
    """Return True if *login* belongs to an automated review bot."""
    login_str = str(login or "")
    if not login_str:
        return False
    return (
        login_str in ("github-actions", "github-actions[bot]", "claude[bot]", "claude")
        or login_str.endswith("[bot]")
    )


# Known review agent opening markers -- used to detect a review whose format the
# classifier cannot read (Morrison-Lab/ai-config#1524).  The key is a lowercase
# substring to match against the body; the value is a human-readable agent name.
REVIEW_AGENT_MARKERS: Dict[str, str] = {
    "**claude finished": "Claude",
    "### \U0001f916 antigravity agent report": "Antigravity",
    "verdict: block": "Jules",
    "_posted by codex (ai agent)": "Codex",
    "_posted by opencode (ai agent)": "OpenCode",
}

# Logins that are one reviewer, never shared. Claude and Antigravity both post
# as github-actions, so they cannot live here; Jules posts as jules[bot], and
# its body marker (`verdict: block`) is only present on the not-clean form.
EXCLUSIVE_BOT_IDENTITY: Dict[str, str] = {
    "jules": "Jules",
    "jules[bot]": "Jules",
}


# Workflow STATUS notices, which are not reviews. Every one of these is posted
# by `github-actions[bot]`, so the comment-admission test below -- bot author OR
# a review-header marker -- admits them all on author alone, and a notice that
# happens to carry no finding vocabulary then reads as a clean review.
#
# Measured on ai-config#1841, #1845 and #1853 (2026-08-21): of the six distinct
# bot comment shapes those PRs carry, exactly ONE is a review. A PR whose review
# quota-skipped four times reported FULLY CLEAN, because the skip notice was
# admitted, matched HEAD through its own `View run` link, and contained no
# findings (ai-config#1719).
#
# Matched against a PREFIX WINDOW rather than the whole body, because this
# corpus quotes these strings constantly -- a real review discussing a dispatch
# notice must stay a review. A notice always leads with its marker; a review
# always leads with `**Claude finished`, which is deliberately absent here.
NON_REVIEW_NOTICE_MARKERS = (
    "claude review dispatched",
    "claude review skipped",
    "claude review did not finish",
    # The AGENT workflow's quota shape, distinct from the review workflow's
    # wording above. self-review-fallback.md documents both and says "Both mean
    # no bot will respond on this run", so covering one and not the other left
    # the identical false clean reachable through the other notice
    # (review finding on ai-config#1862). scripts/pr-sweep.py's REFUSAL_MARKERS
    # already carried "spend limit" for the same reason.
    "spend limit",
    "[pr preview action]",
    "**cost:**",
)

NOTICE_PREFIX_WINDOW = 200

# The body markers that make a comment look like a review regardless of author.
# Shared by the admission test and by is_non_review_notice()'s precedence guard,
# because those two must agree: anything wide enough to be ADMITTED as a review
# has to be wide enough to be PROTECTED from notice exclusion. They disagreed
# once, and a self-review opening by quoting the skip notice it was standing in
# for -- which self-review-fallback.md tells you to write -- was dropped
# entirely, verdict and all (review finding on ai-config#1862).
REVIEW_BODY_MARKERS = (
    "\U0001f916",
    "### \U0001f916",
    "code review",
    "**claude finished",
    "### verdict",
    "_posted by codex (ai agent)",
    "_posted by opencode (ai agent)",
    "verdict:",
)


def has_review_body_marker(body: str) -> bool:
    """True when *body* carries a marker that makes it read as a review."""
    body_lower = body.lower()
    return any(marker in body_lower for marker in REVIEW_BODY_MARKERS)


def _reviewer_identity(body: str, author: str = "") -> str:
    """Stable identity for per-reviewer latest-verdict grouping (#2274).

    GitHub Actions posts Claude and Antigravity under the same bot login, so
    author alone cannot tell two reviewers apart. Exclusive bots (Jules) are
    keyed on login first, because their body marker is not stable across
    verdicts. Shared-login reviewers are keyed on a known agent marker from
    the FIRST non-empty line; fall back to the login; then to "unknown".

    The first line, not the first paragraph: semantic line breaks often put
    the header and the next sentence in one paragraph, and a quote of
    ``**Claude finished**`` on line 2 must not inherit Claude's identity.
    Cited finding vocabulary is blanked first so a code span still does not
    match.

    Residual: a shared-login review whose first non-empty line has no known
    agent marker falls back to the login, so two unmarked ``github-actions``
    bodies share one identity.
    Real Claude and Antigravity reviews carry the marker on that first line.
    Scanning the whole body would re-open the quote-inheritance hole this
    first-line rule exists to close.
    """
    login = str(author or "").strip()
    exclusive = EXCLUSIVE_BOT_IDENTITY.get(login.lower())
    if exclusive:
        return exclusive
    scan = strip_cited_finding_vocab(body or "")
    first_line = next((ln.strip() for ln in scan.splitlines() if ln.strip()), "")
    agent = _detect_review_agent(first_line)
    if agent:
        return agent
    if login:
        return login
    return "unknown"


def _approval_clears(
    identity: str, author: str, approved_authors: set
) -> bool:
    """True when this reviewer's own later GitHub APPROVED supersedes them.

    `approved_authors` is logins. Skip only when this identity is that login
    (Copilot) or the exclusive-bot mapping of that login (Jules). A shared
    login such as github-actions must not clear Claude because a sibling
    bot later APPROVED.
    """
    if author not in approved_authors:
        return False
    if identity == author:
        return True
    return EXCLUSIVE_BOT_IDENTITY.get(author.lower()) == identity


def _detect_review_agent(body: str) -> Optional[str]:
    """Return the agent name if *body* contains a known review agent marker.

    Returns ``None`` when no marker matches -- which does NOT mean the comment
    is not a review; it means the comment is not one of the agents whose format
    we recognise.  A new agent or a format change lands here until its marker is
    added to ``REVIEW_AGENT_MARKERS``.

    The earliest marker in the text wins, not dict order. Claude's marker is
    first in the table, so a first-line Antigravity header that later quotes
    ``**Claude finished**`` would otherwise inherit Claude (#2274).
    """
    body_lower = body.lower()
    best_pos = None
    best_name = None
    for marker, name in REVIEW_AGENT_MARKERS.items():
        pos = body_lower.find(marker)
        if pos < 0:
            continue
        if best_pos is None or pos < best_pos:
            best_pos = pos
            best_name = name
    return best_name


def is_non_review_notice(body: str) -> bool:
    """True when *body* is a workflow status notice rather than a review.

    A known review-agent marker takes PRECEDENCE and settles it immediately: a
    real review that DISCUSSES a dispatch or skip notice -- which any review of
    this corpus routinely does, since the notices are what these checks are
    about -- must stay a review. Without that precedence a review quoting
    `Claude Review Dispatched` in its opening paragraph was excluded outright,
    turning a false clean into a false "no review at this HEAD".

    Only then is the prefix window consulted. A notice leads with its marker,
    so a window bounds the match rather than letting a mention anywhere in a
    long body decide.
    """
    # The agent check is redundant TODAY -- every REVIEW_AGENT_MARKERS entry
    # happens to contain a REVIEW_BODY_MARKERS entry, so the second call decides
    # every case. It stays because the redundancy is a coincidence of the current
    # marker values, not an invariant: a new agent marker that is not a superset
    # of some body marker would recreate the precedence gap this round existed to
    # close. A test pins the property rather than leaving it to whoever edits the
    # marker tables next.
    if _detect_review_agent(body) or has_review_body_marker(body):
        return False
    head = body[:NOTICE_PREFIX_WINDOW].lower()
    return any(marker in head for marker in NON_REVIEW_NOTICE_MARKERS)


def _resolve_run_head_sha(body: str, repo: str, branch: str = "") -> Optional[str]:
    """Extract a workflow run ID from a review comment body and return its head_sha.

    Review comments from the ``@claude`` workflow contain a "View run" link
    like ``https://github.com/{owner}/{repo}/actions/runs/{run_id}``.
    Fetching that run's ``head_sha`` proves which commit the reviewer was
    dispatched against, which is the authoritative source per #1520.

    A ``workflow_dispatch`` run's ``head_sha`` names the dispatch ref, not
    the reviewed commit (see ``fully-clean.rationale.md``), so this only
    trusts the field when the run's ``head_branch`` matches the PR's own
    branch -- confirming the dispatcher passed an explicit ``--ref``.
    Falls back to ``None`` (body-SHA scan) when the check cannot be made.
    """
    m = re.search(r"/actions/runs/(\d+)", body)
    if not m:
        return None
    run_id = m.group(1)
    try:
        out = run_cmd(["gh", "api", f"repos/{repo}/actions/runs/{run_id}"])
        run = json.loads(out)
        event = run.get("event", "")
        head_branch = run.get("head_branch", "")
        head_sha = run.get("head_sha")
        if event == "workflow_dispatch" and branch and head_branch != branch:
            return None
        return head_sha
    except RuntimeError:
        return None


def _workflow_path_for_run(run_id: str, repo: str, cache: dict) -> Optional[str]:
    """Resolve a workflow file path from an Actions run id, with per-call caching."""
    if run_id in cache:
        return cache[run_id]
    try:
        out = run_cmd(["gh", "api", f"repos/{repo}/actions/runs/{run_id}"])
        path = json.loads(out).get("path") or ""
    except RuntimeError:
        path = ""
    cache[run_id] = path
    return path or None


def _workflow_path_from_check_run(cr: dict, repo: str, cache: dict) -> Optional[str]:
    url = cr.get("html_url") or ""
    m = re.search(r"/actions/runs/(\d+)/", url)
    if not m:
        return None
    return _workflow_path_for_run(m.group(1), repo, cache)


def check_ci_runs(sha: str, repo: str) -> Tuple[bool, List[str]]:
    out = run_cmd(["gh", "api", f"repos/{repo}/commits/{sha}/check-runs?per_page=100"])
    data = json.loads(out)
    check_runs = data.get("check_runs", [])

    issues = []
    if not check_runs:
        issues.append(f"No check runs found for SHA {sha[:8]}")
        return False, issues

    # A job name is not unique across workflows: two workflows in one repo can
    # each define a job called `ubuntu-latest (release)`. Naming one alone is
    # therefore ambiguous exactly when it matters, and the ambiguity is
    # invisible in the rendered line, so nothing prompts the reader to check.
    # Disambiguate the duplicated names with the run's own URL, which the
    # payload already carries -- no extra API call.
    seen = {}
    for cr in check_runs:
        seen[cr["name"]] = seen.get(cr["name"], 0) + 1
    duplicated = {n for n, count in seen.items() if count > 1}

    # Concurrency `cancel-in-progress` leaves a superseded run `cancelled` beside
    # a later success with the same job name on the same SHA (ai-config#2277).
    # Scope by workflow file path, not name alone: two workflows can share a job
    # name (#1869) without one run superseding the other.
    workflow_cache: dict = {}
    success_keys = set()
    for cr in check_runs:
        if cr.get("status") != "completed" or cr.get("conclusion") != "success":
            continue
        wp = _workflow_path_from_check_run(cr, repo, workflow_cache)
        if wp:
            success_keys.add((cr["name"], wp))

    for cr in check_runs:
        name = cr["name"]
        status = cr["status"]
        conclusion = cr.get("conclusion")
        where = ""
        if name in duplicated:
            # `html_url` only. A check-suite id was tried as a fallback and
            # dropped: it is a different numeric namespace from the workflow-run
            # id that `gh run view` takes, so rendering it in the same slot
            # points the reader at nothing. And `check_suite` is documented as
            # `object or null`, so `.get("check_suite", {})` returns None on a
            # real payload -- `.get()` substitutes only for an absent KEY, not a
            # null VALUE -- and the AttributeError would exit 1, the status this
            # repo reserves for "not clean". A payload quirk would then read as
            # a PR regression. No annotation beats a wrong or fatal one.
            url = cr.get("html_url")
            where = f" ({url})" if url else ""

        if status != "completed":
            issues.append(
                f"Check run '{name}'{where} is still in status '{status}'")
        elif conclusion not in ("success", "neutral", "skipped"):
            if conclusion == "cancelled":
                wp = _workflow_path_from_check_run(cr, repo, workflow_cache)
                if wp and (name, wp) in success_keys:
                    continue
            issues.append(
                f"Check run '{name}'{where} completed with conclusion "
                f"'{conclusion}'")

    return len(issues) == 0, issues


def strip_cited_finding_vocab(text: str) -> str:
    """Blank out spans where finding-indicator vocabulary appears as a *citation*
    rather than as a raised finding, so ``finding_patterns`` keys on genuine
    findings.

    A clean verdict body routinely quotes finding vocabulary -- especially on PRs
    *about* the review tooling -- inside code spans (`**Location:**`), fenced
    blocks, or double quotes ("Needs more work"). A real verdict or findings
    heading is never expressed that way, and the structural findings-heading and
    formal CHANGES_REQUESTED/REJECTED checks remain as independent backstops.
    See Morrison-Lab/ai-config#1202.

    Code spans and fenced blocks are unambiguous citation and are always blanked.
    A double-quoted span is blanked only when it does NOT itself carry a bold
    ``**...**`` finding label, so a genuine finding that happens to fall inside
    quotes on the same line (e.g. ``"... **Location:** foo.py:1 ..."``) is
    preserved and still detected. Blanking less can only add safe-direction
    re-flags of a clean verdict; it never hides a real finding.

    A THIRD citation shape, found on Morrison-Lab/ai-config#1752 (tracked as
    #1760): a review narrating what changed since a prior round cites that
    round's verdict as bold text inside a plain parenthetical, with no quotes
    at all -- ``(**Needs more work**, reviewed at `abc1234`)``. Neither the
    code-span nor the quote handling above touches this, because there ARE no
    quotes.

    A first version of this gated on citation-shaped WORDING anywhere in the
    same parenthetical (``reviewed at``, or a ``previous``/``prior`` round)
    and blanked the WHOLE parenthetical. Review on #1762 (finding 1)
    confirmed that regresses: a genuine, still-unaddressed finding very
    plausibly mentions "the previous round" in its OWN text while re-raising
    it, and blanking the entire span erased that live finding along with the
    citation --

        (**Needs more work:** src/a.py:10 was flagged in the previous round
        and is still unfixed)

    -- which is exactly the unsafe direction line 269's ``_blank_quote``
    comment and fully-clean.md both warn against: missing a not-clean signal,
    not over-flagging, is the dangerous failure. Bold text plus citation
    wording CO-OCCURRING anywhere in the parenthetical cannot distinguish
    "citing a past verdict" from "a live finding that happens to reference
    the past" -- the two are lexically identical under that gate.

    A second version tightened the gate to SYNTACTIC adjacency -- the bold
    span immediately followed by ``reviewed at `sha` `` -- reasoning that "a
    live finding does not describe itself that way." Review on #1762 (round
    2) refuted that claim by execution: a reviewer re-raising a
    still-unresolved finding across rounds naturally cites the commit it was
    FIRST flagged at, using the identical syntax --

        (**Needs more work**, reviewed at `53f9acbf`) is still present
        and unaddressed in this diff.

    -- which the adjacency-only gate also silently erased. The syntax alone
    can never disambiguate "citing a resolved past finding" from "citing
    when a still-live finding was first raised", because both write the
    identical ``**bold**, reviewed at `sha` `` fragment; only what comes
    AFTER the citation says which one this is.

    So the gate now also requires explicit RESOLUTION wording following the
    citation within the same sentence -- ``is now Addressed`` (this corpus's
    own ARD disposition vocabulary; #1752's actual comment reads "... is now
    Addressed"), ``is now fixed/resolved``, ``has (since) been
    fixed/addressed/resolved``, or ``no longer applies``. Only "still
    present and unaddressed" (no resolution wording) fails this and is
    correctly left alone; "is now Addressed" passes and blanks the citation.
    This is deliberately grounded in the one wording actually observed
    (#1752) rather than invented -- the safe direction, when the true
    discriminator (was this specific finding actually resolved?) cannot be
    determined from text alone, is to require the narrowest signal that
    still covers the real case, not the broadest one that covers every
    hypothetical phrasing.

    Only the matched bold-plus-citation-suffix span is blanked, never the
    resolution wording or anything else in the surrounding text, so an
    unrelated live finding nearby always survives. Must run BEFORE the
    code-span stripping below, since the SHA citation is itself
    backtick-quoted and would otherwise already be blanked by the time this
    runs.

    Spans are replaced with a space (not deleted) so surrounding text and the
    ``changes requested`` negation-prefix lookbehind stay separated.
    """
    def _blank_quote(m: "re.Match") -> str:
        # Preserve a quoted span carrying a bold finding label; blanking it could
        # hide an incidentally-quoted genuine finding -- the unsafe direction.
        return m.group(0) if "**" in m.group(0) else " "

    # A bold-labeled citation of a PAST verdict's SHA, gated on BOTH tight
    # syntactic adjacency (the bold span immediately followed by "reviewed
    # at `sha`") AND explicit resolution wording within the same sentence
    # afterward (#1752/#1760/#1762 rounds 1-2). Neither signal alone is
    # sufficient: adjacency alone still matches a live finding re-raised
    # across rounds (round 2's finding), and wording alone still matches a
    # live finding that happens to mention a prior round (round 1's
    # finding). The lookahead scans past an optional closing paren and up to
    # 40 characters, bounded by the end of the sentence, for the resolution
    # phrase -- wide enough to cross ") is now Addressed." but not into the
    # next sentence.
    RESOLUTION_WORDING = (
        r"(?:is\s+now\s+(?:addressed|fixed|resolved)"
        r"|has\s+(?:since\s+)?been\s+(?:fixed|addressed|resolved)"
        r"|no\s+longer\s+applies)"
    )
    text = re.sub(
        r"\*\*[^*\n]+\*\*"
        r"(?=[ \t,;:-]{0,6}reviewed\s+at\s*`[0-9a-f]{7,40}`"
        r"\)?[^.!?\n]{0,40}\b" + RESOLUTION_WORDING + r"\b)"
        r"[ \t,;:-]{0,6}reviewed\s+at\s*`[0-9a-f]{7,40}`",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Fenced code blocks first, spanning lines.
    text = strip_fences(text, replacement=" ")
    # Inline code spans (`...`), within a line.
    text = re.sub(r"`[^`\n]*`", " ", text)
    # Straight and curly double-quoted spans, within a line (bold-carrying spans kept).
    text = re.sub(r"\"[^\"\n]*\"", _blank_quote, text)
    text = re.sub("\u201c[^\u201d\n]*\u201d", _blank_quote, text)
    return text


VERDICT_NOT_CLEAN_PATTERNS = [
    # Intervening words allowed, because the adjacent forms are not the only
    # ones a reviewer writes. Found by running this classifier over the real
    # verdict bodies on ai-config#1293, whose three "Needs MINOR work" rounds
    # each classified as no verdict at all -- so a genuine not-clean verdict
    # neither blocked nor superseded anything. Missing a not-clean signal is
    # the dangerous direction here, the mirror of an over-broad clean one.
    #
    # The filler refuses a NEGATOR, because the words it was widened to admit
    # are the same ones that invert the phrase: `needs no work` and `needs no
    # more work` are positive statements, and the widening turned every one of
    # them into a not-clean verdict. A negator sitting BEFORE the phrase
    # (`nothing here needs any further work`) is not the filler's business and
    # is handled by NOT_CLEAN_NEGATION_PREFIX below -- the mechanism that
    # already existed for `no changes requested`.
    r"\bNeeds\s+(?:(?!no\b|nothing\b|none\b)\w+\s+){0,3}work\b",
    r"Verdict:\s*(?:Ready after addressing findings|Changes requested|Actionable findings|Block(?:ed|ing)?|Rejected|Unapproved|Impasse|Deadlock)",
    r"changes\s+requested\b",
    r"\b(?:Rejected|Unapproved|Block(?:ed|ing)?|Impasse|Deadlock|Changes\s+requested|Actionable\s+findings)\b",
    r"\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't|unapproved|rejected)\s+(?:\w+\s+){0,2}(?:clean|approved|ready|lgtm)\b",
]

# Applies to EVERY not-clean pattern, not to one named member.
#
# This guard already existed, as an `if pat == r"changes\s+requested\b"` branch
# inside the matching loop -- so a sibling pattern added to the list above got
# no negation handling at all, which is precisely what happened. Enumerating
# which patterns need the guard is the same failure this file has already lost
# to twice on the clean side.
#
# Adjacency-anchored rather than a bare negator search anywhere in the prefix,
# and that is what keeps it in the safe direction. Missing a not-clean signal
# is the dangerous direction here, so the guard must not fire on a negator
# belonging to an earlier clause: the `\w+\s+` filler cannot cross punctuation,
# so `This is not done. Needs work` and `It is not ready; needs more work` both
# stay not-clean.
NOT_CLEAN_NEGATION_PREFIX = re.compile(
    r"\b(?:no|not|nothing|none|never)\s+(?:\w+\s+){0,2}$", re.IGNORECASE
)
# Two alternation groups on purpose. Emphasis markers are tolerated ONLY
# before the alternatives that are unambiguous negations when they open the
# emphasized text (`**None.**`, `**N/A**`): a bold `**Nothing major, but X is
# broken**`, `**0-day exploit...**`, or `**No issues, however...**` opens with
# a negator and carries a real finding, so extending emphasis tolerance to
# those branches would swallow it. Missing a not-clean signal is the dangerous
# direction here (see the prefix comment above), so the risky branches keep
# the plain-punctuation prefix they always had.
NOT_CLEAN_NEGATION_SUFFIX = re.compile(
    r"^\s*(?:"
    r"[*_:.\-]*\s*(?:none\b(?!\s+of\b)|n/a\b|none\s+identified\b|none\s+remaining\b)"
    r"|"
    r"[:.\-]*\s*(?:nothing\b|0\b|no\s+(?:\w+\s+){0,3}(?:findings|issues|bugs|violations|blockers)|no\s+new\b)"
    r")",
    re.IGNORECASE,
)

# Deliberately narrow. An over-broad CLEAN pattern is the dangerous direction:
# it would let an incidental "looks ready" in a later chatty comment discharge a
# standing "Needs more work". An over-narrow one only costs a safe-direction
# re-flag. This is fail-fast.md's "a guard's discharge fires on positive
# success, not the absence of failure" applied to a verdict.
VERDICT_CLEAN_PATTERNS = [
    r"\bReady\s+for\s+merge\b",
    r"Verdict:\s*(?:Clean|Approved|Ready)\b",
    r"\bApproved\s+for\s+merge\b",
    # Anthropic code-review plugin clean template (closes #2147).
    r"^\s*No\s+issues\s+found\.\s+Checked\s+for\s+bugs\s+and\s+(?:CLAUDE|AGENTS)\.md\s+compliance\.",
]

# The bare patterns above carry no verdict on their own: the phrase survives
# intact inside a sentence that says the opposite. `Verdict:\s*...` is safe
# without a guard because it requires immediate adjacency after the label.
#
# Both directions have to be checked, and only one of them is a negation. A
# negation sits BEFORE the phrase ("this is not ready for merge") while a
# CONDITION sits AFTER it ("ready for merge once the findings are fixed"), so a
# lookbehind alone leaves the conditional form classified clean. That form is
# the likelier one in a real review, since it is how a reviewer signs off on
# work that is nearly done.
BARE_CLEAN_PATTERNS = {
    r"\bReady\s+for\s+merge\b",
    r"\bApproved\s+for\s+merge\b",
    r"^\s*No\s+issues\s+found\.\s+Checked\s+for\s+bugs\s+and\s+(?:CLAUDE|AGENTS)\.md\s+compliance\.",
}
BARE_NOT_CLEAN_PATTERNS = {
    r"\b(?:Rejected|Unapproved|Block(?:ed|ing)?|Impasse|Deadlock|Changes\s+requested|Actionable\s+findings)\b",
    r"\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't|unapproved|rejected)\s+(?:\w+\s+){0,2}(?:clean|approved|ready|lgtm)\b",
}

# Criterion 3 (HEAD) and criterion 4 (per-reviewer latest) share this list.
# Headings such as ``## Nits`` are findings even when ``### Verdict`` says
# Ready for merge: fully-clean.md's "findings win" rule, and #2274's nits
# veto. Keep the two scans on one list so a heading added for one cannot
# vanish from the other.
FINDING_PATTERNS = [
    r"#+\s*(Actionable\s+|Detailed\s+)?Findings",
    r"\*\*Actionable Findings\*\*",
    r"\*\*Detailed Findings\*\*",
    r"#+\s*Issues",
    r"#+\s*Remaining",
    r"#+\s*Nits?\b",
    r"(?:^|\n)\s*\*\*Nits?\*\*",
    r"#+\s*Non-blocking\b",
    r"(?:^|\n)\s*\*\*Non-blocking\*\*",
    r"\*\*Location:\*\*",
    r"Verdict:\s*(?:Ready after addressing findings|Needs work|Needs more work|Changes requested|Actionable findings|Block(?:ed|ing)?|Rejected|Unapproved|Impasse|Deadlock)",
    r"\bNeeds\s+(?:(?!no\b|nothing\b|none\b)\w+\s+){0,3}work\b",
    r"changes\s+requested\b",
    r"\b(?:Rejected|Unapproved|Block(?:ed|ing)?|Impasse|Deadlock|Changes\s+requested|Actionable\s+findings)\b",
    r"\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't|unapproved|rejected)\s+(?:\w+\s+){0,2}(?:clean|approved|ready|lgtm)\b",
]
FINDING_HEADING_PATTERNS = {
    r"\bNeeds\s+(?:(?!no\b|nothing\b|none\b)\w+\s+){0,3}work\b",
    r"#+\s*(Actionable\s+|Detailed\s+)?Findings",
    r"\*\*Actionable Findings\*\*",
    r"\*\*Detailed Findings\*\*",
    r"#+\s*Issues",
    r"#+\s*Remaining",
    r"#+\s*Nits?\b",
    r"(?:^|\n)\s*\*\*Nits?\*\*",
    r"#+\s*Non-blocking\b",
    r"(?:^|\n)\s*\*\*Non-blocking\*\*",
}

# The primary guard is POSITION, not vocabulary. A qualifier list cannot be
# finished against free-form English -- the first version covered `not` and
# `once` and review immediately produced `but not`, `almost`, `however` and
# `except`, which is a class with no closed definition. So a bare phrase counts
# only where the comment MARKS it as the verdict: on its own line, behind a
# heading, a bold span, a list bullet, a blockquote, or a `Verdict` label. A
# reviewer stating a verdict marks it; a sentence merely containing the words
# does not, and every unmarked occurrence is now a mention rather than a
# sign-off, whatever words surround it.
#
# That is what makes the vocabulary below a SECOND line rather than the only
# one. It has to exist because a marked verdict can still carry a caveat
# ("**Ready for merge** -- however, two items remain"), but it now only has to
# cover qualifiers attached to an already-marked phrase, which is a far smaller
# job than parsing arbitrary prose.
BARE_CLEAN_MARKED = re.compile(
    r"(?:^|\n)[ \t]*(?:[#>*_+-]+[ \t]*)*"
    r"(?:verdict[ \t]*[:.\-]*[ \t]*)?(?:[#>*_]+[ \t]*)*$",
    re.IGNORECASE,
)
CLEAN_NEGATION_PREFIX = re.compile(
    r"\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't|almost|nearly"
    r"|nowhere\s+near|close\s+to)\s+(?:\w+\s+){0,2}$",
    re.IGNORECASE,
)
# Searched within the rest of the SENTENCE rather than anchored at the match's
# end, because where a match ends is an artifact of which pattern matched. Two
# patterns can match the same text at the same position with different lengths
# --- `Verdict: Ready for merge once ...` matches both `Ready for merge` and the
# shorter `Verdict: Ready` --- and an anchored check on the shorter one lands on
# ` for merge once ...`, sees no qualifier at position zero, and passes.
#
# So the guard stopped depending on match length. Sentence scope is what keeps
# that from over-reaching: a qualifier in the NEXT sentence ("Ready for merge.
# The tests pass, but coverage is unchanged.") is a separate statement and does
# not retract the verdict.
CLEAN_QUALIFIER = re.compile(
    r"\b(?:once|after|when|if|unless|pending|provided|assuming"
    r"|subject\s+to|as\s+soon\s+as|contingent|but|however|except|though|although"
    r"|aside\s+from|other\s+than|apart\s+from|save\s+for|modulo|barring)\b",
    re.IGNORECASE,
)
# A BARE newline does not end a sentence in this corpus, which writes semantic
# line breaks -- one clause per line. Treating `\n` as a terminator hid every
# qualifier that happened to start the next line, so `**Ready for merge**\nonce
# the findings are fixed` read as clean.
#
# This is the same corpus property the NEGATION guard is built around, mirrored:
# there a qualifier at the end of the PREVIOUS line is why the prefix scan has
# to cross a break, and here one at the start of the NEXT line is why the suffix
# scan must not stop at one. Reasoned about correctly on the prefix side and
# then contradicted on the suffix side a round later.
#
# A blank line is a real terminator -- that is a paragraph break, not a wrapped
# clause.
SENTENCE_END = re.compile(r"[.!?]|\n[ \t]*\n")


# Bounded as well as sentence-scoped, because a qualifier RETRACTS only when it
# sits close to the phrase. A real sign-off reads "Ready for merge -- three nits
# fixed, the additions are correctly sourced ..., but I noted X", where the
# `but` is ordinary continuation 100+ characters later; retracting on that makes
# criterion 4 unsatisfiable for a clean PR, which is the failure this whole
# check exists to avoid, arriving from the other side.
#
# A window is still immune to the pattern-length artifact that motivated
# dropping the anchored match: the shorter `Verdict: Ready` overlap puts its
# qualifier ~15 characters out, well inside. Only an anchored check at exactly
# position zero was brittle.
QUALIFIER_WINDOW = 60


def _sentence_remainder(text: str, start: int) -> str:
    """The rest of the sentence after `start`, for a trailing-qualifier scan.

    Bounded by QUALIFIER_WINDOW, and by the sentence, whichever comes first.
    """
    end = SENTENCE_END.search(text, start)
    stop = min(end.start() if end else len(text), start + QUALIFIER_WINDOW)
    return text[start:stop]


def _is_marked_pattern(scan: str, match_start: int) -> bool:
    """Return True if match is marked on its line (e.g. heading, bullet, bold, or label)."""
    line_start = scan.rfind("\n", 0, match_start) + 1
    return bool(BARE_CLEAN_MARKED.search(scan[line_start:match_start]))


def _is_marked_or_in_verdict_section(scan: str, match_start: int) -> bool:
    """Return True if match is marked on its line or located in the Verdict section paragraph."""
    if _is_marked_pattern(scan, match_start):
        return True
    last_verdict = -1
    for m in re.finditer(r"(?:^|\n)[ \t]*#{1,4}[ \t]*verdict\b", scan, re.IGNORECASE):
        if m.start() < match_start:
            last_verdict = m.start()
    if last_verdict != -1:
        between = scan[last_verdict:match_start]
        after_header = re.sub(r"^\s*#{1,4}\s*verdict\b\s*", "", between, flags=re.IGNORECASE)
        # Bounded by the immediate verdict paragraph (no blank line or header between verdict and match)
        if not re.search(r"\n\s*\n", after_header) and not re.search(r"\n[ \t]*#{1,4}[ \t]+", after_header):
            return True
    return False


def classify_verdict(body: str, state: str = "") -> str:
    """Classify one automated review item as 'not-clean', 'clean', or '' (none).

    Returns '' when the item states no verdict at all. That case is the whole
    point of the function: a long, evidence-dense comment that never concludes
    is NOT an approval, and must not supersede an earlier verdict. Its very
    thoroughness is what makes it read as a sign-off.

    A not-clean signal wins over a clean one within a single body, matching
    fully-clean.md's rule that when a verdict line and the findings beneath it
    disagree, the findings win.

    Cited finding vocabulary is blanked first (see strip_cited_finding_vocab),
    so a clean verdict that merely quotes "Needs more work" is not misread as
    stating it -- the #1202 false positive, one surface over.
    """
    if state in ("CHANGES_REQUESTED", "REJECTED"):
        return "not-clean"

    scan = strip_cited_finding_vocab(body)

    for pat in VERDICT_NOT_CLEAN_PATTERNS:
        for match in re.finditer(pat, scan, re.IGNORECASE | re.MULTILINE):
            if pat in BARE_NOT_CLEAN_PATTERNS:
                if not _is_marked_or_in_verdict_section(scan, match.start()):
                    continue
            prefix = scan[max(0, match.start() - 25):match.start()]
            if NOT_CLEAN_NEGATION_PREFIX.search(prefix):
                continue
            if pat == r"\bNeeds\s+(?:(?!no\b|nothing\b|none\b)\w+\s+){0,3}work\b":
                suffix = scan[match.end():match.end() + 60]
                if NOT_CLEAN_NEGATION_SUFFIX.search(suffix):
                    continue
            return "not-clean"

    for pat in VERDICT_CLEAN_PATTERNS:
        for match in re.finditer(pat, scan, re.IGNORECASE | re.MULTILINE):
            # Position and negation are about how the phrase is INTRODUCED, so
            # they apply only to a bare phrase -- a `Verdict:` label is itself
            # the marking, and it already excludes a preceding negation by
            # adjacency.
            if pat in BARE_CLEAN_PATTERNS:
                if not _is_marked_pattern(scan, match.start()):
                    continue
                prefix = scan[max(0, match.start() - 40):match.start()]
                if CLEAN_NEGATION_PREFIX.search(prefix):
                    continue
            # A trailing qualifier is about what FOLLOWS, and nothing about a
            # label stops one: `Verdict: Ready, but two items remain` reads as
            # clean to any prefix-anchored check. So this guard applies to every
            # clean pattern. It was scoped to the bare ones on the reasoning
            # that adjacency after the label "already binds it" -- which is true
            # of what precedes the phrase and says nothing about what follows.
            if CLEAN_QUALIFIER.search(_sentence_remainder(scan, match.end())):
                continue
            return "clean"

    # A review from a known agent whose format the classifier cannot read is
    # the dangerous third state (#1524): it is NOT "no review" (which triggers
    # self-review fallback and wastes a round), and it is NOT "no verdict"
    # (which is correctly skipped).  Report it as its own state so callers can
    # distinguish it from both.
    #
    # Only fire when no pattern matched at all -- if a not-clean or clean
    # pattern matched (even if later retracted by a negation/qualifier guard),
    # the body is readable and should return "" rather than "unreadable".
    if _detect_review_agent(body):
        has_any_pattern_match = bool(
            re.search("|".join(VERDICT_NOT_CLEAN_PATTERNS + VERDICT_CLEAN_PATTERNS),
                       scan, re.IGNORECASE | re.MULTILINE)
        )
        if not has_any_pattern_match:
            return "unreadable"

    return ""


def _unresolved_finding_pattern(body: str) -> Optional[str]:
    """Return the first unmatched finding pattern in *body*, or None.

    Same scan criterion 3 uses on HEAD items. A ``## Nits`` heading with
    real items is a finding even when ``classify_verdict`` returns clean
    because the same body also says Ready for merge (#2274).
    """
    scan_body = strip_cited_finding_vocab(body)
    for pat in FINDING_PATTERNS:
        for match in re.finditer(pat, scan_body, re.IGNORECASE | re.MULTILINE):
            if pat in BARE_NOT_CLEAN_PATTERNS:
                if not _is_marked_or_in_verdict_section(scan_body, match.start()):
                    continue
            prefix = scan_body[max(0, match.start() - 25):match.start()]
            if NOT_CLEAN_NEGATION_PREFIX.search(prefix):
                continue
            if pat in FINDING_HEADING_PATTERNS:
                suffix = scan_body[match.end():match.end() + 60]
                if NOT_CLEAN_NEGATION_SUFFIX.search(suffix):
                    continue
            if pat == r"changes\s+requested\b":
                start = match.start()
                pfx = scan_body[max(0, start - 25):start].lower()
                if re.search(r"\bno\s+(\w+\s+)?$", pfx):
                    continue
            return pat
    return None


def check_latest_verdict(
    all_items: List[tuple],
    approved_authors: Optional[set] = None,
) -> Tuple[bool, List[str]]:
    """Fail when any reviewer's latest verdict-bearing statement is not clean.

    Walks every automated review item chronologically -- not just those
    evaluating HEAD -- and keeps the last one that states a verdict at all,
    both globally (for the scan line agents already read) and per reviewer.

    Items stating no verdict are skipped rather than treated as clearing,
    which is the distinction this check exists to enforce (#1275).

    A later CLEAN from the SAME reviewer supersedes that reviewer's earlier
    not-clean (ordinary ARDI iterate). A later CLEAN from a DIFFERENT
    reviewer does not: any standing not-clean vetoes, including under mwc
    (ai-config#2274). Reviewers are keyed on `_reviewer_identity`, because
    Claude and Antigravity both post as `github-actions[bot]`.

    Formal-review authors whose latest GitHub state is APPROVED have
    superseded their own earlier CHANGES_REQUESTED; pass those logins as
    `approved_authors`. Skip only when identity is that login or its
    exclusive-bot mapping, so a later all-clear from a *different*
    reviewer still does not clear them, and a shared github-actions
    APPROVED does not clear Claude. Applied before the global-latest
    early return, because an empty-bodied later APPROVED does not
    itself update `latest_verdict`.

    Items from a known review agent whose format cannot be classified are
    reported as "unreadable" (#1524) -- distinct from both "no verdict" (skipped)
    and "no review" (triggers self-review fallback).  A wrong answer here is
    worse than an admitted one.

    Prints what it examined alongside what it found, so a zero here cannot be
    read as an all-clear when the real cause is that nothing was examined
    (fail-fast.md, "report what a check *examined*, not only what it *found*").
    """
    dated = sorted((it for it in all_items if it[1]), key=lambda it: it[1])
    approved_authors = set(approved_authors or [])

    latest_verdict = ""
    latest_when = ""
    latest_identity = ""
    latest_author = ""
    n_with_verdict = 0
    unreadable_items = []
    per_reviewer: Dict[str, Tuple[str, str, str]] = {}
    for item in dated:
        _kind, when, body, _oid, state = item[:5]
        author = item[5] if len(item) > 5 else ""
        verdict = classify_verdict(body, state)
        identity = _reviewer_identity(body, author)
        finding_pat = _unresolved_finding_pattern(body)
        # Findings win over unreadable: a known-agent body with ## Nits and no
        # classifiable verdict line is a standing not-clean, not a NOTE.
        if verdict == "not-clean" or finding_pat:
            n_with_verdict += 1
            latest_verdict, latest_when = "not-clean", when
            latest_identity, latest_author = identity, author
            per_reviewer[identity] = ("not-clean", when, author)
        elif verdict == "unreadable":
            agent = _detect_review_agent(body) or "unknown"
            unreadable_items.append((when, agent))
        elif verdict:
            n_with_verdict += 1
            latest_verdict, latest_when = verdict, when
            latest_identity, latest_author = identity, author
            per_reviewer[identity] = (verdict, when, author)

    per_bits = ", ".join(
        f"{identity}={verdict}"
        for identity, (verdict, _when, _author) in sorted(per_reviewer.items())
    )
    per_suffix = f"; per-reviewer: {per_bits}" if per_bits else ""
    print(
        f"  verdict scan: examined {len(dated)} dated automated review item(s), "
        f"{n_with_verdict} bore a verdict, latest = {latest_verdict or 'NONE'}"
        f"{per_suffix}"
    )

    if (
        latest_verdict == "not-clean"
        and not _approval_clears(latest_identity, latest_author, approved_authors)
    ):
        return False, [
            f"Latest verdict-bearing review statement ({latest_when}) is NOT clean, "
            "and no later comment supersedes it with a clean verdict"
        ]

    # Global latest is clean (or NONE), but another reviewer's latest may
    # still be not-clean -- the #2274 hole: a later all-clear from a
    # different reviewer used to supersede.
    issues = []
    for identity, (verdict, when, author) in sorted(per_reviewer.items()):
        if verdict != "not-clean":
            continue
        if _approval_clears(identity, author, approved_authors):
            continue
        issues.append(
            f"Latest verdict-bearing statement from {identity} ({when}) is "
            "NOT clean; a later all-clear from a different reviewer does "
            "not supersede it (ai-config#2274). ARD every finding from "
            "every review, then request fresh reviews."
        )

    # Unreadable reviews are reported but do NOT block -- they are a warning,
    # not a verdict.  The caller surfaces them so a human (or a later agent
    # session) can see that a review arrived but could not be read, rather than
    # the misleading "no review" message that previously triggered a wasted
    # self-review fallback round.
    for when, agent in unreadable_items:
        issues.append(
            f"NOTE: Review from {agent} ({when}) has a format the verdict "
            "classifier cannot read -- not treated as 'no review'"
        )
    blocking = [i for i in issues if not i.startswith("NOTE: ")]
    return len(blocking) == 0, issues


def check_review_comments(pr_num: str, sha: str, repo: str, review_decision: str = "", branch: str = "", quorum: int = 1) -> Tuple[bool, List[str]]:
    out = run_cmd(["gh", "pr", "view", pr_num, "--repo", repo, "--json", "comments,reviews"])
    data = json.loads(out)

    comments = data.get("comments", [])
    reviews = data.get("reviews", [])

    issues = []

    # Direct GitHub computed review decision check
    if review_decision in ("CHANGES_REQUESTED", "REJECTED"):
        issues.append(f"PR formal review decision is '{review_decision}'")

    # Track the latest formal review decision per author chronologically across all reviews
    author_latest_state: Dict[str, str] = {}
    for r in reviews:
        author = (r.get("author") or {}).get("login", "")
        state = r.get("state", "").upper()
        if author and state in ("CHANGES_REQUESTED", "REJECTED", "APPROVED"):
            author_latest_state[author] = state

    for author, state in author_latest_state.items():
        if state in ("CHANGES_REQUESTED", "REJECTED"):
            issues.append(f"PR has active formal review state '{state}' from {author}")

    # Collect automated review reports only (filtering out human/author disposition comments)
    all_items = []
    for c in comments:
        body = c.get("body", "")
        body_lower = body.lower()
        author_login = (c.get("author") or {}).get("login", "")

        if "ard review disposition summary" in body_lower:
            continue

        # A workflow status notice is not a review, whoever posted it.
        if is_non_review_notice(body):
            continue

        author_assoc = (c.get("authorAssociation") or "").upper()
        is_bot_author = _is_bot_author(author_login) or (
            author_assoc in ("OWNER", "MEMBER", "COLLABORATOR") and _detect_review_agent(body) is not None
        )
        verdict = classify_verdict(body)

        # Automated reviews must be authored by a recognized bot author or contain a known review agent marker.
        # A comment that is neither from a bot account nor carrying a review agent marker is admitted
        # ONLY if it states a blocking (not-clean) verdict -- fail closed.
        if is_bot_author:
            all_items.append(("comment", c["createdAt"], body, "", "COMMENT", author_login))
        elif verdict == "not-clean":
            all_items.append(("comment", c["createdAt"], body, "", "COMMENT", author_login))

    for r in reviews:
        body = r.get("body", "")
        commit_oid = r.get("commit", {}).get("oid", "")
        state = r.get("state", "").upper()
        submitted_at = r.get("submittedAt", "")
        author_login = (r.get("author") or {}).get("login", "")
        author_assoc = (r.get("authorAssociation") or "").upper()
        # A formal review carries a real commit.oid, so admitting one attributes
        # it to HEAD with no body-content check. Scope admission to automated bot
        # authors, including CLI agents posting under human accounts
        # detected via strict body text markers, OR a blocking CHANGES_REQUESTED/REJECTED state
        # from any author.
        is_bot_author = _is_bot_author(author_login) or (
            author_assoc in ("OWNER", "MEMBER", "COLLABORATOR") and _detect_review_agent(body) is not None
        )
        if is_bot_author or state in ("CHANGES_REQUESTED", "REJECTED"):
            all_items.append(("review", submitted_at, body, commit_oid, state, author_login))

    if not all_items:
        issues.append(f"No automated review comments or reviews found on PR #{pr_num}")
        return False, issues

    # Criterion 4, evaluated over the WHOLE review history rather than only the
    # items matching HEAD: a not-clean verdict at an earlier commit stands until
    # a later CLEAN from the SAME reviewer supersedes it. A later CLEAN from a
    # different reviewer does not (ai-config#2274).
    _verdict_ok, verdict_issues = check_latest_verdict(
        all_items,
        approved_authors={
            author for author, state in author_latest_state.items()
            if state == "APPROVED"
        },
    )
    issues.extend(verdict_issues)

    # Match items evaluating the target HEAD commit SHA
    sha_short = sha[:7]

    matching_items = []
    for item in all_items:
        body = item[2]
        body_lower = body.lower()
        oid = item[3]

        is_sha_match = bool((oid and oid == sha) or sha_short in body or sha in body)
        if oid:
            # Formal reviews with an explicit commit OID must match the target HEAD SHA exactly
            is_match = (oid == sha)
        else:
            # An issue comment counts as evaluating HEAD if either:
            # (a) it references the SHA in its body (original logic), or
            # (b) it is from a bot author AND contains a "View run" link whose
            #     run's head_sha matches the target -- proving the reviewer was
            #     dispatched against this commit.  This resolves the reviewed
            #     commit from the run rather than from the comment body, which is
            #     what fully-clean.md prescribes.  Falls back to body-SHA scan
            #     when no run can be resolved (no link, or API failure).
            #     See Morrison-Lab/ai-config#1520, #1213.
            is_match = is_sha_match
            if not is_match:
                author_login = item[5] if len(item) > 5 else ""
                if _is_bot_author(author_login):
                    run_sha = _resolve_run_head_sha(body, repo, branch)
                    if run_sha == sha:
                        is_match = True

        if is_match:
            matching_items.append(item)

    if not matching_items:
        issues.append(f"No review comment has been posted evaluating HEAD SHA {sha[:8]} yet")
        return False, issues

    dated_matching = sorted(matching_items, key=lambda it: it[1] or "")
    latest_by_provider = {}
    for item in dated_matching:
        if classify_verdict(item[2], item[4]) in ("clean", "not-clean", "unreadable") or _unresolved_finding_pattern(item[2]):
            provider = _detect_review_agent(item[2]) or item[5]
            latest_by_provider[provider] = item
    matching_items = list(latest_by_provider.values())

    has_findings = False
    for item in matching_items:
        body = item[2]
        state = item[4]
        if state in ("CHANGES_REQUESTED", "REJECTED"):
            has_findings = True
            issues.append(f"Matching review for SHA {sha[:8]} has state '{state}'")

        matched = _unresolved_finding_pattern(body)
        if matched:
            has_findings = True
            issues.append(
                f"Review comment for SHA {sha[:8]} contains findings "
                f"(matched pattern '{matched}')"
            )
        elif classify_verdict(body, state) == "not-clean":
            has_findings = True
            issues.append(f"Review comment for SHA {sha[:8]} explicitly blocks.")

    if not has_findings and not any(i for i in issues if not i.startswith("NOTE: ")):
        unique_authors = set((_detect_review_agent(item[2]) or item[5]) for item in matching_items if len(item) > 5 and classify_verdict(item[2], item[4]) == "clean")
        if len(unique_authors) < quorum:
            if len(unique_authors) == 0:
                issues.append(f"No valid clean review found for HEAD SHA {sha[:8]}.")
            else:
                issues.append(f"Multi-provider quorum not met. Expected {quorum} distinct providers, found {len(unique_authors)} ({', '.join(unique_authors)}).")
        else:
            print(f"\u2713 Found {len(unique_authors)} clean review(s) evaluating HEAD SHA {sha[:8]}, meeting quorum of {quorum}.")

    # NOTE-prefixed issues are informational (unreadable-format warnings) and
    # do not block -- only real findings or missing reviews cause a failure.
    blocking = [i for i in issues if not i.startswith("NOTE: ")]
    return len(blocking) == 0, issues


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check-pr-fully-clean.py",
        description="Verify that a pull request is fully clean (see shared/workflow/fully-clean.md).",
    )
    parser.add_argument("--quorum", type=int, default=1, help="Number of distinct providers required to return a clean verdict at HEAD")
    parser.add_argument("pr_number", help="Pull request number to check")
    parser.add_argument(
        "-R", "--repo", default="", metavar="OWNER/REPO",
        help="Repository to check. Defaults to the current checkout's repository. "
             "Previously an extra argument here was silently ignored and the "
             "check-runs query always named Morrison-Lab/ai-config.",
    )
    return parser.parse_args(argv)


def main():
    args = parse_args()
    pr_num = args.pr_number
    repo = resolve_repo(args.repo)

    # The resolved repo is printed rather than assumed, so a wrong-repo reading
    # is visible in the output instead of being inferable only from the branch
    # name in the next line.
    print(f"Checking ARDI / fully-clean status for {repo}#{pr_num}...")

    sha, branch, state, commit_date, review_decision = get_pr_info(pr_num, repo)
    print(f"PR #{pr_num} ({branch}): state={state}, HEAD={sha[:8]} (committed {commit_date})")

    ci_ok, ci_issues = check_ci_runs(sha, repo)
    review_ok, review_issues = check_review_comments(pr_num, sha, repo, review_decision, branch, args.quorum)

    all_issues = ci_issues + review_issues

    # NOTE-prefixed issues are informational (unreadable-format warnings) and
    # do not block -- only real findings or missing reviews cause a failure.
    notes = [i for i in all_issues if i.startswith("NOTE: ")]
    blocking = [i for i in all_issues if not i.startswith("NOTE: ")]

    if notes:
        print("\n\u2139\ufe0f Notes:")
        for n in notes:
            print(f"  - {n}")

    if blocking:
        print("\n\u274c PR is NOT fully clean:")
        for issue in blocking:
            print(f"  - {issue}")
        sys.exit(1)

    print(f"\n\u2705 {repo}#{pr_num} is FULLY CLEAN on HEAD {sha[:8]}!")
    sys.exit(0)


if __name__ == "__main__":
    main()
