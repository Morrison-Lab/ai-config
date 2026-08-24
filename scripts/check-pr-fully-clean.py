#!/usr/bin/env python3
"""Automated verification tool for ARDI / fully-clean status.

Verifies that:
1. All GitHub Actions check runs for the PR's HEAD commit SHA are completed and passing.
2. An automated review comment evaluating the exact HEAD commit SHA has been posted.
3. All review comments evaluating the HEAD commit SHA contain zero findings, and no active CHANGES_REQUESTED or REJECTED state exists on the PR.
4. The LATEST verdict-bearing statement across the whole review history is clean.

Criterion 4 is deliberately scoped wider than criteria 2 and 3, which look only
at items evaluating the current HEAD SHA. An explicit "Needs more work" posted
against an EARLIER commit falls outside them entirely, and a later comment that
states no verdict raises no finding either -- so the PR reads clean while its
last actual verdict was "Needs more work". Absence of a verdict is not a
clearing: only a later CLEAN verdict supersedes an earlier not-clean one.
See shared/workflow/fully-clean.md and Morrison-Lab/ai-config#1275.

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


def _is_bot_author(login: str) -> bool:
    """Return True if *login* belongs to an automated review bot."""
    return (
        login in ("github-actions", "github-actions[bot]", "claude[bot]", "claude")
        or login.endswith("[bot]")
    )


# Known review agent opening markers -- used to detect a review whose format the
# classifier cannot read (Morrison-Lab/ai-config#1524).  The key is a lowercase
# substring to match against the body; the value is a human-readable agent name.
REVIEW_AGENT_MARKERS: Dict[str, str] = {
    "**claude finished": "Claude",
    "### \U0001f916 antigravity agent report": "Antigravity",
    "verdict: block": "Jules",
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
    "verdict:",
)


def has_review_body_marker(body: str) -> bool:
    """True when *body* carries a marker that makes it read as a review."""
    body_lower = body.lower()
    return any(marker in body_lower for marker in REVIEW_BODY_MARKERS)


def _detect_review_agent(body: str) -> Optional[str]:
    """Return the agent name if *body* contains a known review agent marker.

    Returns ``None`` when no marker matches -- which does NOT mean the comment
    is not a review; it means the comment is not one of the agents whose format
    we recognise.  A new agent or a format change lands here until its marker is
    added to ``REVIEW_AGENT_MARKERS``.
    """
    body_lower = body.lower()
    for marker, name in REVIEW_AGENT_MARKERS.items():
        if marker in body_lower:
            return name
    return None


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
            issues.append(
                f"Check run '{name}'{where} completed with conclusion "
                f"'{conclusion}'")


VERDICT_CLEAN_PATTERNS = [
    r"\bReady\s+for\s+merge\b",
    r"Verdict:\s*(?:Clean|Approved|Ready)\b",
    r"\bApproved\s+for\s+merge\b",
    r"^\s*No issues found\.\s+Checked for bugs and CLAUDE\.md compliance\.",
]

VERDICT_NOT_CLEAN_PATTERNS = [
    r"\bneeds more work\b",
    r"\bchanges requested\b",
    r"\brejected\b",
    r"\bneeds changes\b",
    r"\bchanges requested by.*\b",
    r"\brejected by.*\b",
]

def get_latest_clean_verdict(review_comments: List[str]) -> Optional[str]:
    latest_clean = None
    for comment in review_comments:
        if re.search(r"\bReady\s+for\s+merge\b", comment):
            latest_clean = comment
            break
        elif re.search(r"Verdict:\s*(?:Clean|Approved|Ready)\b", comment):
            latest_clean = comment
            break
        elif re.search(r"\bApproved\s+for\s+merge\b", comment):
            latest_clean = comment
            break
        elif re.search(r"^\s*No issues found\.\s+Checked for bugs and CLAUDE\.md compliance\.", comment):
            latest_clean = comment
            break
    return latest_clean


def check_pr_fully_clean(pr_num: str, repo: str) -> bool:
    head_sha, head_branch, state, commit_date, review_decision = get_pr_info(pr_num, repo)
    if state != "MERGED":
        print(f"PR {pr_num} is not merged, skipping fully clean check.")
        return False

    review_comments = []
    pr_comments = run_cmd(["gh", "pr", "list-comments", pr_num, "--repo", repo, "--json", "body", "user.login"])
    for comment in json.loads(pr_comments):
        if comment["user"]["login"] == "claude[bot]" and has_review_body_marker(comment["body"]):
            review_comments.append(comment["body"])

    latest_clean = get_latest_clean_verdict(review_comments)
    if latest_clean is None:
        print(f"PR {pr_num} has no clean verdict.")
        return False

    print(f"PR {pr_num} is fully clean.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated verification tool for ARDI / fully-clean status.")
    parser.add_argument("pr_num", help="The PR number to check.")
    parser.add_argument("-R", "--repo", help="The repository in OWNER/REPO form (default: current repo).")
    args = parser.parse_args()

    repo = resolve_repo(args.repo)
    check_pr_fully_clean(args.pr_num, repo)
