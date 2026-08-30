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
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import CODE_SPAN_RE, find_fence_spans  # noqa: E402
from payload_fetcher import PayloadError, PayloadFetcher  # noqa: E402
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
            repo = fetch(
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


# Set by --from-json. When present it replaces every `gh` invocation, so the
# script runs where the CLI does not exist (ai-config#2441). None means "use
# run_cmd", i.e. the unchanged local behaviour.
_FETCHER = None


def fetch(cmd):
    """Run *cmd* via `gh`, or answer it from a --from-json payload."""
    if _FETCHER is not None:
        return _FETCHER(cmd)
    return run_cmd(cmd)


def get_pr_info(pr_num: str, repo: str):
    if str(Path(__file__).resolve().parent.parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.lib.pull_request import PullRequest
    pr = PullRequest(pr_num, repo, fetcher=fetch)
    return pr


def _is_bot_author(login: Optional[str]) -> bool:
    """Return True if *login* belongs to an automated review bot."""
    login_str = str(login or "")
    if not login_str:
        return False
    return (
        login_str in ("github-actions", "github-actions[bot]", "claude[bot]", "claude", "cursor")
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
    "cursor": "Cursor",
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

    Residual: a shared-login review whose first or last non-empty line has no known
    agent marker falls back to the login, so two unmarked ``github-actions``
    bodies share one identity.
    Real Claude and Antigravity reviews carry the marker on that first line.
    CLI agents like Codex and OpenCode append the marker on the last line.
    Scanning the whole body would re-open the quote-inheritance hole this
    first-and-last-line rule exists to minimize.
    """
    login = str(author or "").strip()
    exclusive = EXCLUSIVE_BOT_IDENTITY.get(login.lower())
    if exclusive:
        return exclusive
    scan = strip_cited_finding_vocab(body or "")
    lines = [ln.strip() for ln in scan.splitlines() if ln.strip()]
    first_line = lines[0] if lines else ""
    last_line = lines[-1] if lines else ""
    agent = _detect_review_agent(first_line) or _detect_review_agent(last_line)
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
        out = fetch(["gh", "api", f"repos/{repo}/actions/runs/{run_id}"])
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
        out = fetch(["gh", "api", f"repos/{repo}/actions/runs/{run_id}"])
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


def check_ci_runs(pr) -> Tuple[bool, List[str]]:
    sha = pr.head_sha
    repo = pr.repo
    check_runs = [{"name": cr.name, "status": cr.status, "conclusion": cr.conclusion, "html_url": cr.html_url} for cr in pr.get_check_runs()]

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


# origin/main's own inline-span pattern, reused verbatim. The scan text this
# module produces is byte-identical to origin/main's; see
# strip_cited_finding_vocab_with_mask.
_BASE_INLINE_SPAN = re.compile(r"`[^`\n]*`")


_STRAIGHT_QUOTE_SPAN = re.compile(r'"[^"\n]*"')
_CURLY_QUOTE_SPAN = re.compile("\u201c[^\u201d\\n]*\u201d")


# Longest line this will scan for code spans. CODE_SPAN_RE restarts a lazy
# scan at every unpairable backtick run, so cost is quadratic in line length on
# a line of many unclosed runs: measured 674 ms at 34 KB against 1 ms for the
# base pass, versus 8 ms at GitHub's 65,536-character comment cap for a
# realistic multi-line body. Over the cap, a line is left UNMASKED, so nothing
# is suppressed on it and the checker behaves exactly as origin/main does --
# the over-flagging direction, which is the safe one.
_MAX_MASKED_LINE = 4096


def _citation_mask(text: str) -> bytearray:
    """Mark every offset lying inside a closed code span of 2+ backticks.

    The INTERSECTION of a per-line scan and a whole-body scan, which is
    strictly safer than either alone because each over-reaches where the other
    does not.

    A whole-body scan over-reaches downward: ``CODE_SPAN_RE`` bounds a span by a
    blank line rather than by a line ending, so a stray backtick on one line
    pairs with a stray backtick on the next and marks the finding between them.

    A per-line scan over-reaches upward, which is less obvious. It can
    MANUFACTURE a span CommonMark does not have, by pairing two runs on one line
    that CommonMark has already consumed into a span opened on the line above:

        A stray `` opener sits on this line.
        ``Needs more work`` on scripts/a.py is my actual verdict.

    CommonMark pairs line 3's run with the FIRST run on line 4, so
    ``Needs more work`` is literal prose and not a citation at all. A per-line
    scan sees a tidy span on line 4 and marks it, and the finding is suppressed.
    Measured: ``origin/main`` not-clean, per-line-only HEAD clean.

    Taking only offsets both scans agree on suppresses a match solely when it
    sits in a span under both readings. Everything either scan claims alone is
    left unmarked, which merely over-flags -- the safe direction
    (``shared/workflow/fully-clean.md``).
    """
    per_line = bytearray(len(text))
    offset = 0
    oversized = []
    for line in text.split("\n"):
        if len(line) > _MAX_MASKED_LINE:
            oversized.append((offset, offset + len(line)))
        else:
            for match in CODE_SPAN_RE.finditer(line):
                if len(match.group(1)) >= 2:
                    begin, finish = match.span()
                    per_line[offset + begin:offset + finish] = (
                        b"\x01" * (finish - begin)
                    )
        offset += len(line) + 1

    # Blank oversized lines to same-length filler before the whole-body scan
    # too, or the quadratic cost simply moves there. Offsets are preserved, and
    # losing a whole-body span that crosses such a line only masks LESS.
    scannable = text
    if oversized:
        chars = list(text)
        for begin, finish in oversized:
            chars[begin:finish] = " " * (finish - begin)
        scannable = "".join(chars)

    whole = bytearray(len(text))
    for match in CODE_SPAN_RE.finditer(scannable):
        if len(match.group(1)) >= 2:
            begin, finish = match.span()
            whole[begin:finish] = b"\x01" * (finish - begin)

    mask = bytearray(a & b for a, b in zip(per_line, whole))
    for begin, finish in oversized:
        mask[begin:finish] = b"\x00" * (finish - begin)
    return mask


def _sub_with_mask(
    pattern, repl, text: str, mask: bytearray
) -> Tuple[str, bytearray]:
    """Like ``re.sub``, but carrying the mask along so offsets stay aligned.

    A string ``repl`` is inserted LITERALLY, not expanded as a template, so
    ``r"[\\1]"`` stays those four characters rather than becoming the first
    group. Today's callers pass ``" "`` or a callable, and no expansion is
    wanted; the difference is named so a later caller does not assume it.

    A replaced region takes mask 1 only when the WHOLE matched region was
    masked; a partly-cited match is not a citation. A ``repl`` callable that
    returns the match unchanged keeps that region's mask, which is what lets
    ``_blank_quote``'s preserve path survive.
    """
    out: List[str] = []
    out_mask = bytearray()
    prev = 0
    for match in pattern.finditer(text):
        begin, finish = match.span()
        out.append(text[prev:begin])
        out_mask += mask[prev:begin]
        replacement = repl(match) if callable(repl) else repl
        if replacement == match.group(0):
            out_mask += mask[begin:finish]
        else:
            fill = 1 if finish > begin and all(mask[begin:finish]) else 0
            out_mask += bytes([fill]) * len(replacement)
        out.append(replacement)
        prev = finish
    out.append(text[prev:])
    out_mask += mask[prev:]
    return "".join(out), out_mask


def _strip_fences_with_mask(
    text: str, mask: bytearray
) -> Tuple[str, bytearray]:
    """``strip_fences(text, replacement=" ")``, carrying the mask along."""
    lines = text.split("\n")
    fenced, _, orphans = find_fence_spans(text)
    to_strip = fenced | orphans
    out: List[str] = []
    out_mask = bytearray()
    offset = 0
    for index, line in enumerate(lines):
        if index in to_strip:
            out.append(" ")
            out_mask += bytes([0])
        else:
            out.append(line)
            out_mask += mask[offset:offset + len(line)]
        if index != len(lines) - 1:
            out.append("\n")
            out_mask += bytes([0])
        offset += len(line) + 1
    return "".join(out), out_mask


def match_is_cited(mask: bytearray, start: int, end: int) -> bool:
    """True when a match lies WHOLLY inside cited text.

    Containment is the whole discriminator. A phrase that straddles a span
    boundary -- ``Needs ``more`` work``, whose verdict words are the author's
    own and only whose emphasis is quoted -- is not a citation, and every
    earlier attempt at this fix lost exactly that case by blanking text instead
    of filtering matches.
    """
    return end > start and all(mask[start:end])


def strip_cited_finding_vocab_with_mask(text: str) -> Tuple[str, bytearray]:
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

    Returns ``(scan, mask)``. The scan is byte-identical to what
    ``origin/main`` produces -- this function deliberately blanks NOTHING extra.
    The mask marks which offsets came from inside a code span delimited by a run
    of two or more backticks, and ``match_is_cited`` lets the finding scans
    ignore a match lying wholly inside one.

    That split is the entire design, and it was arrived at the hard way. A code
    span of 2+ backticks is a citation just as a single-backtick span is -- the
    longer run being the only way CommonMark lets a span quote text that itself
    contains a backtick, which is what a review of this corpus does constantly.
    The obvious fix is to blank those spans too. Four successive attempts to do
    that each broke a different downstream pass, because much of this module
    measures the scan in characters and offsets rather than reading it:

    - collapsing a span to one space moved ``classify_verdict``'s anchored
      negation windows, so a negator reached a finding it was never next to;
    - filling it to width with a non-word character unmarked a bare rejection
      that ``_is_marked_or_in_verdict_section`` had accepted, swallowed the
      sentence boundary ``RESOLVED_BLOCKING_SUFFIX`` stops at, destroyed the
      item tag ``_findings_section_resolves_empty`` vetoes on, and split
      ``Needs `` `` `` `` more `` `` `` `` work`` so the phrase stopped matching;
    - blanking the span at all removed a ``"`` the quote pass paired on and a
      ``**`` that ``_blank_quote`` preserves a span for, and could change which
      identity ``_reviewer_identity`` reads.

    Every one of those was fail-open on a fail-closed instrument. They are not a
    list of bugs to patch individually: they are what happens when the text a
    dozen character-sensitive checks consume is edited underneath them. Leaving
    the text alone retires the whole class, and the mask expresses the actual
    intent, which was never "blank more" but "do not count a quoted phrase as a
    stated one".

    Containment is the discriminator, and it falls out of the mask for free.
    ``Needs `` `` `` `` more `` `` `` `` work`` is the author's own verdict with
    one word emphasized, so the match straddles the span and still counts; a
    phrase wholly inside the span is a citation and does not.

    The line this was measured on is from the ``claude-review`` verdict comment
    on #2431 (ai-config#2449, 2026-08-27), verbatim:

        - The exact quoted string `` Addressed GitHub Claude of `9508454e`
          (Needs more work) `` matches the real comment (id 5430978306)
          verbatim, confirmed via direct API fetch.

    ``origin/main``'s pattern finds THREE matches on that line, not two: the
    inner pair around the SHA, plus each outer double-backtick delimiter
    consumed as an empty span. Consuming the delimiters is the whole mechanism
    -- it is what leaves ``(Needs more work)`` exposed between them, so a
    Ready-for-merge review reads NOT clean. The outer spaces are optional
    padding: the quoted content neither starts nor ends with a backtick, so the
    no-spaces form is fixed identically.

    That body stays not-clean after this fix, for a different reason: the bullet
    list under its ``## Findings`` heading vetoes
    ``_findings_section_resolves_empty``, so ``_unresolved_finding_pattern``
    still returns the findings-heading pattern.

    ai-config#2452 is a SEPARATE comment on the same PR, not a second signal on
    this body. Measured on ``origin/main``, the two sentences behave
    differently, which is worth recording because they read alike:

        No blocking findings.                              -> matched, then
                                                              exempted by
                                                              NOT_CLEAN_NEGATION_PREFIX
        No other findings, blocking or otherwise, remain
        open.                                              -> matched, NOT
                                                              exempted

    Only the second is #2452. The negation prefix looks back 25 characters, so
    it clears the ``No`` immediately before ``blocking`` and not the one five
    words away. Whether the second then counts still depends on whether its
    position is marked, which is why it needs the surrounding comment to
    reproduce and does not fire from the bare sentence alone.
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
    _SHA_CITATION = re.compile(
        r"\*\*[^*\n]+\*\*"
        r"(?=[ \t,;:-]{0,6}reviewed\s+at\s*`[0-9a-f]{7,40}`"
        r"\)?[^.!?\n]{0,40}\b" + RESOLUTION_WORDING + r"\b)"
        r"[ \t,;:-]{0,6}reviewed\s+at\s*`[0-9a-f]{7,40}`",
        re.IGNORECASE,
    )
    # A parenthesized citation of a PAST round's verdict -- the shape the
    # review bot uses when narrating which round a comment responded to:
    # "This is the author's direct response to [round 6's finding](<url>)
    # (posted 2026-08-30T05:22:14Z, verdict **Needs more work**), per ..."
    # (ai-config#2662). Like _SHA_CITATION above, the strip requires a
    # POSITIVE context signal, not just the parenthesized shape: the aside
    # must sit right after a markdown link to the cited round (a semantic
    # line break after the link is allowed), or follow an attribution
    # phrase ("in response to", "responds to", "replied to"), whose filler
    # may carry one parenthesized aside of its own. The filler's branches
    # are disjoint on "(" so a failing scan stays linear. An unattributed
    # "posted <ts>, verdict **X**" -- parenthesized or not -- is left
    # alone entirely: stripping a live not-clean is the dangerous
    # direction, and a veto list alone cannot enumerate every re-raise
    # phrasing.
    _POSTED_VERDICT_CITATION = re.compile(
        r"(?P<keep>\]\([^()\s]{1,400}\)[ \t\n]*"
        r"|\b(?:in\s+)?"
        r"(?:respon(?:se|ds|ded|ding)|repl(?:y|ies|ied|ying))\s+to\s+"
        r"(?:\([^()\n]{0,80}\)|[^.!?\n()]){0,80})"
        r"\(posted\s+[0-9]{4}-[0-9]{2}-[0-9]{2}"
        r"T[0-9]{2}:[0-9]{2}(?::[0-9]{2})?Z?"
        r"\s*,\s*verdict\s+\*\*[^*\n]+\*\*\)",
        re.IGNORECASE,
    )
    # The veto runs in code over the citation's WHOLE containing sentence,
    # in both directions -- a forward-only lookahead window missed "The
    # finding remains unaddressed despite my response to it (posted ...)"
    # and any re-raise past its length bound. Sentence bounds use the
    # glued-dot rule: [.!?] ends a sentence only when whitespace or
    # end-of-text follows, so "utils.py" and decimals do not truncate it.
    # The matched aside itself is excluded from the scan (its own "verdict
    # **Needs more work**" must not self-veto), while the kept attribution
    # filler is included.
    _RERAISE_VOCAB = re.compile(
        r"\b(?:still|remain(?:s|ed)?|open|unaddressed|unresolved|unfixed"
        r"|outstanding|ignored|reopen(?:s|ed)?|recurs?|persists?|stands?"
        r"|must\s+be|needs\s+to\s+be|appl(?:y|ies|ied)"
        r"|(?:not|never)\s+(?:yet\s+)?(?:been\s+)?"
        r"(?:fixed|resolved|addressed))\b",
        re.IGNORECASE,
    )
    _SENTENCE_END = _SENTENCE_END_RE

    def _strip_posted_aside(m: "re.Match") -> str:
        head = m.string[:m.start()]
        tail = m.string[m.end():]
        sentence_start = _sentence_start_before(head)
        forward = _SENTENCE_END.search(tail)
        sentence_tail = tail[:forward.end()] if forward else tail
        context = " ".join(
            (head[sentence_start:], m.group("keep"), sentence_tail)
        )
        if _RERAISE_VOCAB.search(context):
            return m.group(0)
        return m.group("keep") + " "

    text = _SHA_CITATION.sub(" ", text)
    text = _POSTED_VERDICT_CITATION.sub(_strip_posted_aside, text)
    mask = _citation_mask(text)
    # Fenced code blocks first, spanning lines.
    text, mask = _strip_fences_with_mask(text, mask)
    # Inline code spans, within a line.
    text, mask = _sub_with_mask(_BASE_INLINE_SPAN, " ", text, mask)
    # Straight and curly double-quoted spans, within a line (bold-carrying spans kept).
    text, mask = _sub_with_mask(_STRAIGHT_QUOTE_SPAN, _blank_quote, text, mask)
    text, mask = _sub_with_mask(_CURLY_QUOTE_SPAN, _blank_quote, text, mask)
    return text, mask


def strip_cited_finding_vocab(text: str) -> str:
    """The scan text alone, byte-identical to ``origin/main``'s.

    Kept as the public entry point because several callers only ever wanted
    the text. The mask is what the finding scans need, and they call
    ``strip_cited_finding_vocab_with_mask``.
    """
    return strip_cited_finding_vocab_with_mask(text)[0]


# The bare rejection alternation appears in three lists that must stay
# byte-identical, because BARE_NOT_CLEAN_PATTERNS membership is tested by
# string equality against the list entries -- so it is built once here.
#
# `Block(?:ed|ing)?` needs lookbehinds because `\b` treats a hyphen as a
# boundary, so "non-blocking" -- how a reviewer marks a nit as NOT blocking
# -- read a Ready-for-merge review as not-clean (ai-config#2369, measured
# 2026-08-26 on #2288). Only the `non-`/`non ` compounds are exempted.
# "previously-blocking" is deliberately NOT exempted, although it produces a
# safe-direction false positive when narrating a fixed finding: "the
# previously-blocking finding remains open; do not merge" is a real
# not-clean statement, and a lexical lookbehind cannot tell it from "the
# previously-blocking error was fixed". Missing a not-clean is the dangerous
# direction, so the narration form stays an over-flag -- as does any other
# `-blocking` compound ("merge-blocking" is a real signal) and the
# emphasized form ("non-**blocking**": the char before `blocking` is `*`,
# which the lookbehind cannot see through).
_BARE_REJECTION = (
    r"\b(?:Rejected|Unapproved|"
    r"(?<!non-)(?<!non\s)Block(?:ed|ing)?"
    r"|Impasse|Deadlock|Changes\s+requested|Actionable\s+findings)\b"
)

# The clause scan admits a parenthesized aside as a single unit, because a
# reviewer enumerating the resolved findings puts them in parens -- "both
# round-2 blocking findings (demo caption overclaim, missing tactics.qmd
# companion video) are resolved" -- and the commas and filename dots inside
# that aside are not clause boundaries. Bare parens are excluded from the
# character alternative so the two branches are disjoint: letting `(` match
# either branch is exponential backtracking on a failing enumeration like
# "(1) (2) ... (24)" (measured at 51s), and a stray unmatched paren failing
# the scan fails safe (the mention stays blocking). The resolution verb is
# tense-checked ("is/are/was/were ... fixed", "has/have been fixed", "no
# longer applies") so a live directive like "must be fixed before merge"
# never reads as already resolved.
RESOLVED_BLOCKING_SUFFIX = re.compile(
    r"^(?:(?!\b(?:and|but|while|although|however)\b)"
    r"(?:\([^()\n]{0,120}\)|[^,:;.!?()])){0,120}\b(?:"
    r"(?:is|are|was|were)\s+(?:now\s+)?"
    r"(?:fixed|resolved|addressed|closed|removed|corrected)"
    r"|ha(?:s|ve)\s+(?:since\s+)?been\s+"
    r"(?:fixed|resolved|addressed|closed|removed|corrected)"
    r"|no\s+longer\s+applies"
    r")\b"
    r"(?:\s+(?:by|in|via)\s+this\s+round(?:['\u2019]s)?\s+"
    r"(?:diff|push|commit|changes?|fixes?))?"
    r"(?:"
    r"\s+and\s+(?:confirmed\s+)?passing"
    r"|,?\s+and\s+(?:(?![.!?])[\s\S]){1,180}\b"
    r"(?:is|are|was|were)\s+(?:also\s+)?"
    r"(?:fixed|resolved|addressed|closed|removed|corrected)"
    r"|,?\s+with\s+no\s+new\s+(?:issues?|findings?)"
    r"(?:\s+(?:introduced|found|added|identified))?"
    r")?\s*[.!?]?\s*$",
    re.IGNORECASE,
)
AFFIRMATIVE_RESOLUTION_FOLLOWUP = re.compile(
    r"^\s*(?:I\s+found\s+no\s+new\s+(?:issues|findings)"
    r"(?:\s+in\s+(?:this|the)\s+(?:round|review|pass)[^.!?]*)?"
    r"[.!?]?)?\s*$",
    re.IGNORECASE,
)


# Shared by the citation-aside veto and the negated-resolution guard: a
# [.!?] ends a sentence only when whitespace or end-of-text follows, so a
# filename ("tactics.qmd") or a decimal does not split one. A trailing
# abbreviation dot does not either -- "e.g." mid-sentence otherwise
# restarts the sentence and hides everything before it, including a
# negator. Merging two sentences only ever widens the scan, which
# over-flags rather than exempting, so the safe direction.
_SENTENCE_END_RE = re.compile(
    r"(?<!\be\.g)(?<!\bi\.e)(?<!\bcf)(?<!\bvs)(?<!\betc)"
    r"(?<!\bapprox)(?<!\bresp)(?<!\bfig)"
    r"(?<![.!?])[.!?](?=\s|$)",
    re.IGNORECASE,
)
# A dot inside one of these is not a sentence end either. Checked in code
# against the token before the candidate, since the token has no bound a
# lookbehind could take.
_NOT_SENTENCE_TOKEN_RE = re.compile(r"(?:://|www\.|/)")


def _sentence_start_before(text: str) -> int:
    """Offset just past the last real sentence end in ``text``.

    Splits on ``_SENTENCE_END_RE`` and then discards any candidate whose
    preceding whitespace-delimited token looks like a URL or path, whose
    internal dots would otherwise restart the sentence mid-clause and
    hide everything before them from the caller's scan.
    """
    start = 0
    for end in _SENTENCE_END_RE.finditer(text):
        # The token is found by scanning back to the nearest whitespace,
        # which costs the token's own length. Slicing and splitting the
        # whole prefix instead is quadratic over a body with many
        # sentences, and a review comment at GitHub's 65536-character cap
        # took over five seconds that way.
        token_start = max(
            text.rfind(" ", 0, end.start()),
            text.rfind("\n", 0, end.start()),
            text.rfind("\t", 0, end.start()),
        ) + 1
        token = text[token_start:end.start()]
        if token and _NOT_SENTENCE_TOKEN_RE.search(token):
            continue
        start = end.end()
    return start
_NEGATOR_RE = re.compile(
    r"\b(?:none|no|not|never|neither|nothing|nobody|nor"
    r"|zero|hardly|barely|scarcely)\b",
    re.IGNORECASE,
)


def _is_resolved_blocking_mention(scan: str, match: re.Match) -> bool:
    """True for a past blocking state explicitly resolved in the same sentence."""
    if match.group(0).lower() != "blocking":
        return False
    prefix = scan[max(0, match.start() - 40):match.start()]
    past_state = re.search(
        r"(?:\bpreviously"
        r"|\bprior(?:\s+(?:round|verdict)(?:['\u2019]s)?"
        r"|\s+(?:finding|issue)s?)?"
        r"|\bearlier"
        r"|\bround-\d+(?:['\u2019]s)?"
        r")(?:[-\s]+|\s+\*{1,2}|\s+(?:the\s+)?)$",
        prefix,
        re.IGNORECASE,
    )
    if past_state is None:
        return False
    # A negated resolution -- "None of the earlier blocking findings were
    # resolved" -- is a live not-clean statement: the suffix reads as
    # resolved only because the negator sits BEFORE the past-state marker,
    # outside the suffix scan.
    #
    # Two narrower shapes were tried first and both failed OPEN, which is
    # the dangerous direction here. A fixed glue whitelist ("of the ...")
    # let a count or modifier through ("None of the TWO earlier ..."). A
    # bounded run of bare words then let anything longer than the bound
    # through ("None of the several very recently identified earlier
    # ..."), and its premise -- that punctuation ends a negator's scope --
    # is false when the punctuation sits INSIDE the negated noun phrase
    # ("None of the many previously-identified, still-outstanding earlier
    # ...").
    #
    # So the rule is the blunt one: ANY negator earlier in the same
    # sentence defeats the exemption, with no attempt to judge what it
    # quantifies.
    #
    # Three narrower rules were tried and each failed OPEN, which is the
    # dangerous direction, so this is a deliberate retreat rather than a
    # first guess. Deciding whether a negator scopes over the resolution
    # is a parsing problem, and every lexical proxy for it admitted a new
    # shape: a glue whitelist let a count through ("None of the TWO
    # earlier ..."), a bounded word run let a longer run and
    # punctuation-inside-the-noun-phrase through ("None of the many
    # previously-identified, still-outstanding earlier ..."), and testing
    # the negator's apparent grammatical role let a governor word
    # prepended to the target phrasing through ("WITH none of the
    # previously blocking findings were resolved"), including when a
    # required clause boundary was also present but sat inside the
    # negated noun phrase ("With none of the recently reported,
    # previously blocking ...").
    #
    # What the blunt rule costs is one over-flag: a genuinely resolved
    # narration whose sentence happens to open with an unrelated negated
    # clause ("With no new issues, both round-2 blocking findings ... are
    # resolved") stays blocking. That is a false NOT-clean, which stalls a
    # merge until a human looks, whereas every rule above bought that case
    # by risking a false clean, which merges over a live rejection. The
    # asymmetry is this file's stated policy, so the trade is not close.
    # A negator AFTER the mention is unaffected, so the common trailing
    # form ("... are resolved, with no new issues introduced") still
    # reads as resolved.
    sentence_start = _sentence_start_before(scan[:match.start()])
    if _NEGATOR_RE.search(scan[sentence_start:match.start()]):
        return False
    suffix = scan[match.end():]
    # A dot glued to the next character -- a filename ("tactics.qmd"), a
    # decimal -- is not a sentence end; only [.!?] followed by whitespace
    # or end-of-text terminates the sentence.
    sentence = re.match(r"^(?:(?![.!?](?:\s|$))[\s\S])*[.!?]?", suffix)
    if sentence is None:
        return False
    paragraph = re.match(r"^(?:(?!\n[ \t]*\n)[\s\S])*", suffix)
    if paragraph is None:
        return False
    following = paragraph.group(0)[sentence.end():]
    return (
        RESOLVED_BLOCKING_SUFFIX.fullmatch(sentence.group(0)) is not None
        and AFFIRMATIVE_RESOLUTION_FOLLOWUP.fullmatch(following) is not None
    )

# The findings-heading pattern is likewise built once: the two list copies
# below and the section-resolution wiring in _unresolved_finding_pattern
# compare against this exact string, so a drifted copy would silently
# disable the ai-config#2370 exemption.
_FINDINGS_HEADING_PATTERN = r"#+\s*(Actionable\s+|Detailed\s+)?Findings"

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
    _BARE_REJECTION,
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
    _BARE_REJECTION,
    r"\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't|unapproved|rejected)\s+(?:\w+\s+){0,2}(?:clean|approved|ready|lgtm)\b",
}

# Criterion 3 (HEAD) and criterion 4 (per-reviewer latest) share this list.
# Headings such as ``## Nits`` are findings even when ``### Verdict`` says
# Ready for merge: fully-clean.md's "findings win" rule, and #2274's nits
# veto. Keep the two scans on one list so a heading added for one cannot
# vanish from the other.
FINDING_PATTERNS = [
    _FINDINGS_HEADING_PATTERN,
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
    _BARE_REJECTION,
    r"\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't|unapproved|rejected)\s+(?:\w+\s+){0,2}(?:clean|approved|ready|lgtm)\b",
]
FINDING_HEADING_PATTERNS = {
    r"\bNeeds\s+(?:(?!no\b|nothing\b|none\b)\w+\s+){0,3}work\b",
    _FINDINGS_HEADING_PATTERN,
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

    scan, cited = strip_cited_finding_vocab_with_mask(body)

    for pat in VERDICT_NOT_CLEAN_PATTERNS:
        for match in re.finditer(pat, scan, re.IGNORECASE | re.MULTILINE):
            if match_is_cited(cited, match.start(), match.end()):
                # Wholly inside a 2+ backtick code span: the reviewer quoted
                # this phrase, they did not state it (ai-config#2449).
                continue
            if pat in BARE_NOT_CLEAN_PATTERNS:
                if not _is_marked_or_in_verdict_section(scan, match.start()):
                    continue
            prefix = scan[max(0, match.start() - 25):match.start()]
            if NOT_CLEAN_NEGATION_PREFIX.search(prefix):
                continue
            if pat == _BARE_REJECTION and _is_resolved_blocking_mention(
                scan, match
            ):
                continue
            if pat == r"\bNeeds\s+(?:(?!no\b|nothing\b|none\b)\w+\s+){0,3}work\b":
                suffix = scan[match.end():match.end() + 60]
                if NOT_CLEAN_NEGATION_SUFFIX.search(suffix):
                    continue
            return "not-clean"

    for pat in VERDICT_CLEAN_PATTERNS:
        for match in re.finditer(pat, scan, re.IGNORECASE | re.MULTILINE):
            if match_is_cited(cited, match.start(), match.end()):
                continue
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


# A line that reads as a finding ITEM. Severity/class tags and Location
# markers are the explicit forms; a bare list item in any CommonMark form
# (`-`, `*`, `+`, `1.`, `1)`) vetoes too, because an untagged finding
# ("1. `foo()` crashes on empty input") is still a finding, and swallowing
# it is the dangerous direction.
_SECTION_FINDING_ITEM = re.compile(
    r"(?im)"
    r"^\s*(?:\*\*)?\[?"
    r"(?:Defect|Factual\s+Error|Edge\s+Case|Convention|Nit|Non-blocking|"
    r"Suggestion|Note|Question|Warning|Blocking|Critical|Major|Minor|P[0-4])\b\]?"
    r"|^\s*(?:\d+[.)]|[-*+])\s+\S"
    r"|\*\*Location:\*\*"
    r"|^\s*>\s*\S"
    r"|^\s*\*\*(?!\s*$)"
)


def _findings_section_resolves_empty(scan_body: str, match_end: int) -> bool:
    """True when the findings section (on the lines after the heading containing *match_end*) opens with a
    whole-line no-findings statement and carries no finding-shaped content
    after it.

    Text after ``Findings`` on the matched heading line is still part of the
    heading, not the section body, so scanning starts on the following line
    (ai-config#2459). The section runs from there to the next heading or end
    of body. The FIRST non-empty line must match the
    NOT_CLEAN_NEGATION_SUFFIX allowlist -- the same trigger the old 60-char
    suffix shortcut keyed on, made line-anchored -- and everything after it
    must clear the item veto.

    A resolving line reached only AFTER other content (verification prose,
    alert blocks, items) never exempts: an untagged prose finding is
    lexically indistinguishable from verification prose, and swallowing a
    finding is the dangerous direction, so that shape is a deliberate
    safe-direction re-flag (ai-config#2370's free-prose remainder). The
    mirror direction shares the residual: untagged PLAIN PROSE after a
    resolving first line is also indistinguishable and is not vetoed --
    including finding prose packed onto the SAME physical line as the
    resolving word, whether in the body or in a heading trailer -- the
    same exposure the 60-char shortcut always had.

    No wider than the shortcut except one vetted way, still gated by the
    item veto: no 60-char cap on where the resolving line starts. The
    first line is tested UNSTRIPPED against the allowlist, whose own
    prefix classes already accept the bullet markers the shortcut
    accepted (`- None.`, `* None.`, `- No new issues.`) and reject the
    ones it rejected (`* No new issues.`, `1. None.`) -- exact vocabulary
    parity by reuse rather than by a re-derived strip.
    """
    heading_line_end = scan_body.find("\n", match_end)
    if heading_line_end == -1:
        return False
    # Any trailing text on the heading line is CONTENT -- the section's
    # first line, tested like any other (#2499 option (a), adopted on the
    # sixth #2488 review round). Five rounds of classifying trailers as
    # decoration each enumerated a finite set (finding signals, then
    # separators, then decoration lead-words, then signal vocabulary) and
    # each enumeration left a swallow bypass; promoting the whole trailer
    # closes the class. A resolving phrase after a leading separator
    # ("## Findings: none") still exempts; a decorative suffix
    # ("## Findings on the diff content") now re-flags, the recoverable
    # direction -- reviewer-side heading style is the systemic fix.
    trailing = scan_body[match_end:heading_line_end].strip()
    lead: list[str] = []
    content = trailing.lstrip(":(-\u2013\u2014 \t").strip()
    if content:
        lead = [content]
    section_start = heading_line_end + 1
    next_heading = re.search(r"(?m)^#{1,6}\s", scan_body[section_start:])
    section = scan_body[section_start:section_start + next_heading.start()] \
        if next_heading else scan_body[section_start:]
    lines = lead + [ln for ln in section.splitlines() if ln.strip()]
    if not lines:
        return False
    if not NOT_CLEAN_NEGATION_SUFFIX.search(lines[0]):
        return False
    return not _SECTION_FINDING_ITEM.search("\n".join(lines[1:]))


def _unresolved_finding_pattern(body: str) -> Optional[str]:
    """Return the first unmatched finding pattern in *body*, or None.

    Same scan criterion 3 uses on HEAD items. A ``## Nits`` heading with
    real items is a finding even when ``classify_verdict`` returns clean
    because the same body also says Ready for merge (#2274).
    """
    scan_body, cited = strip_cited_finding_vocab_with_mask(body)
    for pat in FINDING_PATTERNS:
        for match in re.finditer(pat, scan_body, re.IGNORECASE | re.MULTILINE):
            if match_is_cited(cited, match.start(), match.end()):
                continue
            if pat in BARE_NOT_CLEAN_PATTERNS:
                if not _is_marked_or_in_verdict_section(scan_body, match.start()):
                    continue
            prefix = scan_body[max(0, match.start() - 25):match.start()]
            if NOT_CLEAN_NEGATION_PREFIX.search(prefix):
                continue
            if pat == _BARE_REJECTION and _is_resolved_blocking_mention(
                scan_body, match
            ):
                continue
            if pat == _FINDINGS_HEADING_PATTERN:
                # The section-resolution check REPLACES the 60-char suffix
                # shortcut for this heading: the shortcut read "No new
                # issues." directly under the heading as resolving the whole
                # section, even when finding items followed it (ai-config
                # #2370's review of this very fix). The replacement keeps
                # the shortcut's first-line trigger and adds the item veto
                # over the rest of the section.
                if _findings_section_resolves_empty(scan_body, match.end()):
                    continue
            elif pat in FINDING_HEADING_PATTERNS:
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


_LEDGER_HOLD_PHRASE = re.compile(
    r"(?i)\bblocked on review of\b|\bdo not merge\b")
_LEDGER_TABLE_ROW = re.compile(r"(?im)^\|.*\bDisposition\b.*\|\s*$")
_CLAIM_TTL = timedelta(hours=2)


def _is_expired_driver_ledger(
    body: str,
    author: str,
    when: str,
    last_seen_by_author: Dict[str, str],
    now: Optional[datetime] = None,
) -> bool:
    """True for a dead driving session's status ledger, never for a review.

    A pre-#2448 driver-session disposition comment ("Do not merge. Blocked
    on review of <sha>" plus a Disposition table) posted under an
    exclusive-login bot stands as that reviewer's latest not-clean verdict
    forever, because only the same login can supersede it and the session
    behind it is gone -- the undischargeable state ai-config#2482 records,
    which blocked #2341 outright. Per #2430's fail-open analysis, the gate
    is a POSITIVE signature of the ledger class, all parts required:

      1. an EXCLUSIVE_BOT_IDENTITY author (a driving session's own login;
         shared logins never qualify),
      2. a markdown table with a Disposition column (the ARD ledger shape),
      3. a hold phrase ("Blocked on review of" / "Do not merge"),
      4. and the login's claim has EXPIRED per claim-pr's 2-hour rule:
         no item from that login on the thread within the last 2 hours.

    A real review carries none of 2-3, and a LIVE driving session fails 4,
    so anything short of the full signature stays a verdict -- admitting a
    comment is the recoverable direction, dropping one is not.

    Accepted residual: Cursor's driving persona and its Bugbot reviewer
    share one login, so a genuine review that VERBATIM restates a ledger
    (Disposition table plus hold phrase) from a session idle >2h would be
    excluded too. No such review has been observed -- the shapes differ
    by construction -- so the residual is carried as documented risk
    rather than mitigated. (The caller's commit-activity fold addresses
    the separate problem of an ACTIVE driver appearing idle; it cannot
    help here, since a reviewer never pushes.)
    """
    login = str(author or "").lower()
    if login not in EXCLUSIVE_BOT_IDENTITY:
        return False
    if not _LEDGER_TABLE_ROW.search(body or ""):
        return False
    if not _LEDGER_HOLD_PHRASE.search(body or ""):
        return False
    last = last_seen_by_author.get(login, when)
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            # A parseable but zone-naive timestamp would raise TypeError
            # against the aware `now`; read it as UTC instead of crashing.
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        now = now or datetime.now(timezone.utc)
        return (now - last_dt) > _CLAIM_TTL
    except (ValueError, TypeError):
        # An unreadable timestamp fails toward keeping the verdict.
        return False


def check_latest_verdict(
    all_items: List[tuple],
    approved_authors: Optional[set] = None,
    commit_activity: Optional[Dict[str, str]] = None,
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
    # Latest activity per author, for the expired-ledger test (#2482):
    # a login active on the thread within the claim TTL is a live driver.
    # Comment/review items AND commit authorship both count -- claim-pr's
    # rule is push-or-comment, and a driver mid-implementation may push
    # for hours without posting (review finding, 2026-08-28).
    last_seen_by_author: Dict[str, str] = {}
    for item in dated:
        author = str(item[5] if len(item) > 5 else "").lower()
        if author and item[1] > last_seen_by_author.get(author, ""):
            last_seen_by_author[author] = item[1]
    for login, when_c in (commit_activity or {}).items():
        login = login.lower()
        if when_c > last_seen_by_author.get(login, ""):
            last_seen_by_author[login] = when_c

    expired_ledgers = []
    for item in dated:
        _kind, when, body, _oid, state = item[:5]
        author = item[5] if len(item) > 5 else ""
        verdict = classify_verdict(body, state)
        identity = _reviewer_identity(body, author)
        finding_pat = _unresolved_finding_pattern(body)
        if (verdict == "not-clean" or finding_pat) and \
                _is_expired_driver_ledger(
                    body, author, when, last_seen_by_author):
            expired_ledgers.append((when, identity))
            continue
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

    ledger_notes = [
        f"NOTE: expired driver ledger from {identity} ({when}) excluded "
        "from the verdict scan (ai-config#2482); its findings were "
        "dispositioned in that comment itself"
        for when, identity in expired_ledgers
    ]
    if (
        latest_verdict == "not-clean"
        and not _approval_clears(latest_identity, latest_author, approved_authors)
    ):
        return False, [
            f"Latest verdict-bearing review statement ({latest_when}) is NOT clean, "
            "and no later comment supersedes it with a clean verdict"
        ] + ledger_notes

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
    issues.extend(ledger_notes)
    blocking = [i for i in issues if not i.startswith("NOTE: ")]
    return len(blocking) == 0, issues


_REVIEW_STRUCTURE_HEADING = re.compile(
    r"(?im)^#{1,6}\s*(?:Summary|(?:Critical\s+|Actionable\s+)?Findings|Verdict)\b"
)


def _is_structured_review_body(body: str) -> bool:
    """True when *body* is shaped like a review REPORT rather than prose.

    Requires both a report heading (Summary / Findings / Verdict families)
    and a Reviewed-Commit fingerprint line, tested over the CITED-VOCAB
    STRIPPED body so a casual comment quoting a prior report inside a
    fence cannot smuggle the structure in (#1202's convention). The two
    together are what a pre-push-review or adversarial-self-review report
    always carries and conversational prose does not, which is what keeps
    #1798's false-CLEAN direction closed while #2402's supersession path
    opens.
    """
    scan = strip_cited_finding_vocab(body)
    if not _REVIEW_STRUCTURE_HEADING.search(scan):
        return False
    return bool(re.search(
        r"(?im)^\*{0,2}Reviewed[- ]Commit\*{0,2}[ \t]*:", scan))


def _commit_activity(pr) -> Dict[str, str]:
    """Latest committedDate per author login (and lowercased author name).

    Names are included beside logins because a bot session's commits can
    carry an author name ("Cursor Agent") whose login differs from the
    comment-posting one; counting either as activity errs toward keeping
    a driver's hold standing, the safe direction.
    """
    activity: Dict[str, str] = {}
    for commit in (getattr(pr, "_data", {}) or {}).get("commits") or []:
        when = commit.get("committedDate") or ""
        for a in commit.get("authors") or []:
            for key in (a.get("login") or "", a.get("name") or ""):
                key = key.lower()
                if key and when > activity.get(key, ""):
                    activity[key] = when
    # An exclusive login also matches by substring of the author NAME
    # ("cursor" in "cursor agent"), so a rename cannot hide the activity.
    for login in EXCLUSIVE_BOT_IDENTITY:
        for key, when in list(activity.items()):
            if login in key and when > activity.get(login, ""):
                activity[login] = when
    return activity


def check_review_comments(pr, quorum: int = 1) -> Tuple[bool, List[str]]:
    pr_num, sha, repo, review_decision, branch = pr.pr_num, pr.head_sha, pr.repo, pr.review_decision, pr.branch
    comments = [{"author": {"login": c.author_login}, "createdAt": c.created_at, "body": c.body, "authorAssociation": c.author_association} for c in pr.get_comments()]
    reviews = [{"state": r.state, "author": {"login": r.author_login}, "submittedAt": r.submitted_at, "body": r.body, "commit": {"oid": r.commit_oid}, "authorAssociation": r.author_association} for r in pr.get_reviews()]

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
            author_assoc in ("OWNER", "MEMBER") and _reviewer_identity(body, author_login) not in (author_login, "unknown")
        )
        verdict = classify_verdict(body)

        # Automated reviews must be authored by a recognized bot author or contain a known review agent marker.
        # A comment that is neither from a bot account nor carrying a review agent marker is admitted
        # when it states a blocking (not-clean) verdict -- fail closed -- OR
        # when it is a STRUCTURED review report (headings plus a
        # Reviewed-Commit fingerprint) stating a clean verdict. Without the
        # second branch, one not-clean self-review round under a human login
        # pinned that identity's "latest" forever: later Ready-for-merge
        # rounds under the same account were dropped before
        # check_latest_verdict ever saw them, manufacturing a permanent
        # standing veto no ARDI round could clear (ai-config#2402, measured
        # on #2229's six-round sequence).
        #
        # The security invariant from #2308 is preserved by the QUORUM tag,
        # not by dropping the item: a non-bot clean may supersede that same
        # identity's own earlier not-clean, and may never count toward the
        # clean-review quorum that authorizes a merge -- body text still
        # buys no approval authority (see the unique_authors loop below).
        # A bare human comment quoting verdict phrases stays out entirely:
        # the structure test requires report headings AND a fingerprint,
        # which casual prose does not carry (#1798's guard, restated).
        if is_bot_author:
            all_items.append(("comment", c["createdAt"], body, "", "COMMENT", author_login, True))
        elif verdict == "not-clean":
            all_items.append(("comment", c["createdAt"], body, "", "COMMENT", author_login, False))
        elif (
            verdict == "clean"
            and _is_structured_review_body(body)
            and _reviewer_identity(body, author_login) == author_login
        ):
            # The identity gate is load-bearing: without it, any commenter
            # could paste an agent marker (`**Claude finished review**`)
            # into a structured clean body and SUPERSEDE the real bot's
            # standing not-clean, since supersession keys on
            # _reviewer_identity over body text. Marker-free bodies
            # resolve to the poster's own login, so a non-bot clean can
            # clear only that same account's earlier verdicts.
            all_items.append(("comment", c["createdAt"], body, "", "COMMENT", author_login, False))

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
            author_assoc in ("OWNER", "MEMBER") and _reviewer_identity(body, author_login) not in (author_login, "unknown")
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
        commit_activity=_commit_activity(pr),
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

    if quorum <= 0:
        issues.append(f"Quorum size is {quorum}, but it must be at least 1. Failing closed.")
        return False, issues

    if not matching_items:
        issues.append(f"No review comment has been posted evaluating HEAD SHA {sha[:8]} yet")
        return False, issues

    dated_matching = sorted(matching_items, key=lambda it: it[1] or "")
    latest_by_provider = {}
    for item in dated_matching:
        if classify_verdict(item[2], item[4]) in ("clean", "not-clean") or _unresolved_finding_pattern(item[2]):
            provider = _reviewer_identity(item[2], item[5] if len(item) > 5 else "")
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
        unique_authors = set()
        logins_with_markers = set()
        for item in matching_items:
            # Quorum eligibility is carried from ADMISSION time (item[6]):
            # a non-bot item admitted for supersession only (#2402) must
            # never count toward the clean-review quorum, per #2308's
            # invariant that approval authority comes from author identity
            # and never from body text. Items without the flag predate it
            # and keep their previous (bot-pooled) eligibility.
            if len(item) > 6 and item[6] is False:
                continue
            if len(item) > 5 and classify_verdict(item[2], item[4]) == "clean":
                login = item[5]
                identity = _reviewer_identity(item[2], login)
                unique_authors.add(identity)
                if identity != login and identity != "unknown":
                    logins_with_markers.add(login)
        for login in logins_with_markers:
            if login in unique_authors:
                unique_authors.remove(login)

        if len(unique_authors) < quorum:
            if len(unique_authors) == 0 and quorum > 0:
                issues.append(f"No valid clean review found for HEAD SHA {sha[:8]}.")
            elif quorum > 0:
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

    def non_negative_int(value):
        ivalue = int(value)
        if ivalue < 0:
            raise argparse.ArgumentTypeError(f"quorum must be >= 0, got {value}")
        return ivalue

    parser.add_argument("--quorum", type=non_negative_int, default=1, help="Number of distinct providers required to return a clean verdict at HEAD")
    parser.add_argument("pr_number", help="Pull request number to check")
    parser.add_argument(
        "--from-json", default="", metavar="FILE",
        help="Score a payload gathered by the agent instead of shelling out to "
             "`gh`. Use this in remote/web sessions, where the CLI does not "
             "exist (ai-config#2441). shared/workflow/fully-clean.md lists the "
             "payload keys and the MCP calls that fill them.",
    )
    parser.add_argument(
        "-R", "--repo", default="", metavar="OWNER/REPO",
        help="Repository to check. Defaults to the current checkout's repository. "
             "Previously an extra argument here was silently ignored and the "
             "check-runs query always named Morrison-Lab/ai-config.",
    )
    return parser.parse_args(argv)


def main():
    global _FETCHER
    args = parse_args()

    # Installed before resolve_repo, because repo resolution is itself one of
    # the `gh` reads the payload replaces.
    if args.from_json:
        try:
            _FETCHER = PayloadFetcher.from_file(args.from_json)
        except PayloadError as exc:
            die(str(exc))

    pr_num = args.pr_number
    repo = resolve_repo(args.repo)

    # The resolved repo is printed rather than assumed, so a wrong-repo reading
    # is visible in the output instead of being inferable only from the branch
    # name in the next line.
    print(f"Checking ARDI / fully-clean status for {repo}#{pr_num}...")

    pr = get_pr_info(pr_num, repo)
    sha, branch, state, commit_date, review_decision = pr.head_sha, pr.branch, pr.state, pr.commit_date, pr.review_decision
    print(f"PR #{pr_num} ({branch}): state={state}, HEAD={sha[:8]} (committed {commit_date})")

    ci_ok, ci_issues = check_ci_runs(pr)
    review_ok, review_issues = check_review_comments(pr, args.quorum)

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
    # Unusable --from-json data must exit USAGE_EXIT, never 1. Exit 1 is this
    # script's "NOT fully clean" verdict, so a payload problem surfacing as 1
    # is indistinguishable from a finding about the PR -- the same conflation
    # the `gh`-missing guard in run_cmd exists to prevent (ai-config#2441).
    #
    # The catch is deliberately BROAD while --from-json is active, and narrow
    # otherwise. A hand-built payload reaches library code that assumes shapes
    # `gh` always produced, so a wrong-typed value raises AttributeError or
    # TypeError inside pull_request.py rather than PayloadError -- six such
    # shapes were measured landing on exit 1. Under --from-json no exception
    # can be a statement about the PR, so every one of them is a usage error.
    try:
        main()
    except SystemExit:
        raise
    except PayloadError as exc:
        die(f"--from-json payload is unusable: {exc}")
    except Exception as exc:  # noqa: BLE001 - see the comment above
        if _FETCHER is None:
            raise
        die(
            f"--from-json payload is unusable: {type(exc).__name__}: {exc}\n"
            "This is a defect in the payload's shape, not a verdict about the PR."
        )
