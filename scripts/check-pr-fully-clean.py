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

Exit codes:
0: Fully clean (safe to end ARDI loop)
1: Not clean (in-progress checks, failing checks, missing review, findings present,
   or a standing not-clean verdict that nothing later superseded)
"""
import json
import re
import subprocess
import sys
from typing import Dict, List, Tuple

# The status glyphs below are non-ASCII, and a Windows console defaults to
# cp1252, which cannot encode them -- so every run raised UnicodeEncodeError
# before reaching its verdict, including the test suite. Degrade the glyph
# rather than the run; on a UTF-8 console this changes nothing.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")


def run_cmd(cmd: List[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {res.stderr}")
    return res.stdout.strip()


def get_pr_info(pr_num: str) -> Tuple[str, str, str, str, str]:
    out = run_cmd(["gh", "pr", "view", pr_num, "--json", "headRefOid,headRefName,state,commits,reviewDecision"])
    data = json.loads(out)
    head_sha = data["headRefOid"]
    commits = data.get("commits", [])
    commit_date = ""
    if commits:
        commit_date = commits[-1].get("committedDate", "")
    review_decision = data.get("reviewDecision") or ""
    return head_sha, data["headRefName"], data["state"], commit_date, review_decision


def check_ci_runs(sha: str) -> Tuple[bool, List[str]]:
    out = run_cmd(["gh", "api", f"repos/Morrison-Lab/ai-config/commits/{sha}/check-runs?per_page=100"])
    data = json.loads(out)
    check_runs = data.get("check_runs", [])

    issues = []
    if not check_runs:
        issues.append(f"No check runs found for SHA {sha[:8]}")
        return False, issues

    for cr in check_runs:
        name = cr["name"]
        status = cr["status"]
        conclusion = cr.get("conclusion")

        if status != "completed":
            issues.append(f"Check run '{name}' is still in status '{status}'")
        elif conclusion not in ("success", "neutral", "skipped"):
            issues.append(f"Check run '{name}' completed with conclusion '{conclusion}'")

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

    Spans are replaced with a space (not deleted) so surrounding text and the
    ``changes requested`` negation-prefix lookbehind stay separated.
    """
    def _blank_quote(m: "re.Match") -> str:
        # Preserve a quoted span carrying a bold finding label; blanking it could
        # hide an incidentally-quoted genuine finding -- the unsafe direction.
        return m.group(0) if "**" in m.group(0) else " "

    # Fenced code blocks first (``` ... ```), spanning lines.
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
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
    r"\bNeeds\s+(?:\w+\s+){0,3}work\b",
    r"Verdict:\s*(?:Ready after addressing findings|Changes requested|Actionable findings|Block(?:ed|ing)?)",
    r"changes\s+requested\b",
]

# Deliberately narrow. An over-broad CLEAN pattern is the dangerous direction:
# it would let an incidental "looks ready" in a later chatty comment discharge a
# standing "Needs more work". An over-narrow one only costs a safe-direction
# re-flag. This is fail-fast.md's "a guard's discharge fires on positive
# success, not the absence of failure" applied to a verdict.
VERDICT_CLEAN_PATTERNS = [
    r"\bReady\s+for\s+merge\b",
    r"Verdict:\s*(?:Clean|Approved|Ready)\b",
    r"\bApproved\s+for\s+merge\b",
]

# The two BARE patterns above carry no verdict on their own: the phrase survives
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
SENTENCE_END = re.compile(r"[.!?\n]")


def _sentence_remainder(text: str, start: int) -> str:
    """The rest of the sentence after `start`, for a trailing-qualifier scan."""
    end = SENTENCE_END.search(text, start)
    return text[start:end.start() if end else len(text)]


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
            if pat == r"changes\s+requested\b":
                prefix = scan[max(0, match.start() - 25):match.start()].lower()
                if re.search(r"\bno\s+(\w+\s+)?$", prefix):
                    continue
            return "not-clean"

    for pat in VERDICT_CLEAN_PATTERNS:
        for match in re.finditer(pat, scan, re.IGNORECASE | re.MULTILINE):
            # Position and negation are about how the phrase is INTRODUCED, so
            # they apply only to a bare phrase -- a `Verdict:` label is itself
            # the marking, and it already excludes a preceding negation by
            # adjacency.
            if pat in BARE_CLEAN_PATTERNS:
                line_start = scan.rfind("\n", 0, match.start()) + 1
                if not BARE_CLEAN_MARKED.search(scan[line_start:match.start()]):
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

    return ""


def check_latest_verdict(all_items: List[tuple]) -> Tuple[bool, List[str]]:
    """Fail when the latest verdict-bearing statement is not clean.

    Walks every automated review item chronologically -- not just those
    evaluating HEAD -- and keeps the last one that states a verdict at all.
    Items stating no verdict are skipped rather than treated as clearing,
    which is the distinction this check exists to enforce.

    Prints what it examined alongside what it found, so a zero here cannot be
    read as an all-clear when the real cause is that nothing was examined
    (fail-fast.md, "report what a check *examined*, not only what it *found*").
    """
    dated = sorted((it for it in all_items if it[1]), key=lambda it: it[1])

    latest_verdict = ""
    latest_when = ""
    n_with_verdict = 0
    for _kind, when, body, _oid, state in dated:
        verdict = classify_verdict(body, state)
        if verdict:
            n_with_verdict += 1
            latest_verdict, latest_when = verdict, when

    print(
        f"  verdict scan: examined {len(dated)} dated automated review item(s), "
        f"{n_with_verdict} bore a verdict, latest = {latest_verdict or 'NONE'}"
    )

    if latest_verdict == "not-clean":
        return False, [
            f"Latest verdict-bearing review statement ({latest_when}) is NOT clean, "
            "and no later comment supersedes it with a clean verdict"
        ]
    return True, []


def check_review_comments(pr_num: str, sha: str, review_decision: str = "") -> Tuple[bool, List[str]]:
    out = run_cmd(["gh", "pr", "view", pr_num, "--json", "comments,reviews"])
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

        is_bot_author = author_login in ("github-actions", "github-actions[bot]", "claude[bot]", "claude")
        # "**claude finished" and "### verdict" are the canonical review markers
        # CLAUDE.md prescribes ("Completed runs start the body with
        # `**Claude finished`"). The older "claude finished review" marker was a
        # near-miss: the real body reads "**Claude finished** -- adversarial
        # review", so "review" never follows "finished" directly and the marker
        # matched nothing. Measured on Morrison-Lab/ai-config#1267, where all four
        # review comments were posted under a human login and both verdict-bearing
        # ones carried "### Verdict" -- so admission failed, all_items was empty,
        # and every body-content criterion below was evaluated over nothing.
        is_review_header = any(marker in body_lower for marker in ("\ud83e\udd16", "### 🤖", "code review", "**claude finished", "### verdict", "verdict:"))

        if is_bot_author or is_review_header:
            all_items.append(("comment", c["createdAt"], body, "", "COMMENT"))

    for r in reviews:
        body = r.get("body", "")
        commit_oid = r.get("commit", {}).get("oid", "")
        state = r.get("state", "").upper()
        submitted_at = r.get("submittedAt", "")
        author_login = (r.get("author") or {}).get("login", "")
        # A formal review carries a real commit.oid, so admitting one attributes
        # it to HEAD with no body-content check. Scope admission to automated bot
        # authors only -- never sniff body text, which a human review can
        # trivially collide with -- OR a blocking CHANGES_REQUESTED/REJECTED state
        # from any author.
        is_bot_author = (
            author_login in ("github-actions", "github-actions[bot]", "claude[bot]", "claude")
            or author_login.endswith("[bot]")
        )
        if is_bot_author or state in ("CHANGES_REQUESTED", "REJECTED"):
            all_items.append(("review", submitted_at, body, commit_oid, state))

    if not all_items:
        issues.append(f"No automated review comments or reviews found on PR #{pr_num}")
        return False, issues

    # Criterion 4, evaluated over the WHOLE review history rather than only the
    # items matching HEAD: a not-clean verdict at an earlier commit stands until
    # a later CLEAN verdict supersedes it.
    _verdict_ok, verdict_issues = check_latest_verdict(all_items)
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
            # An issue comment counts as evaluating HEAD only if it actually
            # references the HEAD SHA (full or short). Matching on timing alone
            # (posted after the commit + a generic marker word) is unsafe: a slow
            # review of an earlier commit can post AFTER a newer push and would
            # then be accepted as a review of the new HEAD, reporting a stale
            # verdict as "fully clean" -- the exact review-vs-push race
            # shared/workflow/fully-clean.md documents ("a review comment's
            # header SHA can be stale"). Fail closed: no SHA reference, no match.
            is_match = is_sha_match

        if is_match:
            matching_items.append(item)

    if not matching_items:
        issues.append(f"No review comment has been posted evaluating HEAD SHA {sha[:8]} yet")
        return False, issues

    # Inspect ALL matching items for HEAD SHA (not just an empty trailing formal review object)
    finding_patterns = [
        r"#+\s*(Actionable\s+|Detailed\s+)?Findings",
        r"\*\*Actionable Findings\*\*",
        r"\*\*Detailed Findings\*\*",
        r"#+\s*Issues",
        r"#+\s*Remaining",
        r"\*\*Location:\*\*",
        r"Verdict:\s*(Ready after addressing findings|Needs work|Needs more work|Changes requested|Actionable findings)",
        r"\bNeeds\s+more\s+work\b",
        r"\bNeeds\s+work\b",
        r"changes\s+requested\b",
    ]

    has_findings = False
    for item in matching_items:
        body = item[2]
        state = item[4]
        if state in ("CHANGES_REQUESTED", "REJECTED"):
            has_findings = True
            issues.append(f"Matching review for SHA {sha[:8]} has state '{state}'")

        # Scan a copy with cited finding vocabulary (code spans, fenced blocks,
        # double-quoted spans) blanked out, so a clean verdict that merely quotes
        # finding vocabulary is not read as raising a finding (#1202).
        scan_body = strip_cited_finding_vocab(body)
        for pat in finding_patterns:
            for match in re.finditer(pat, scan_body, re.IGNORECASE | re.MULTILINE):
                if pat == r"changes\s+requested\b":
                    start = match.start()
                    prefix = scan_body[max(0, start - 25):start].lower()
                    if re.search(r"\bno\s+(\w+\s+)?$", prefix):
                        continue
                has_findings = True
                issues.append(f"Review comment for SHA {sha[:8]} contains findings (matched pattern '{pat}')")

    if not has_findings and not issues:
        print(f"\u2713 Found clean review comment evaluating HEAD SHA {sha[:8]}")

    return len(issues) == 0, issues


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/check-pr-fully-clean.py <pr-number>")
        sys.exit(1)

    pr_num = sys.argv[1]
    print(f"Checking ARDI / fully-clean status for PR #{pr_num}...")

    sha, branch, state, commit_date, review_decision = get_pr_info(pr_num)
    print(f"PR #{pr_num} ({branch}): state={state}, HEAD={sha[:8]} (committed {commit_date})")

    ci_ok, ci_issues = check_ci_runs(sha)
    review_ok, review_issues = check_review_comments(pr_num, sha, review_decision)

    all_issues = ci_issues + review_issues

    if all_issues:
        print("\n\u274c PR is NOT fully clean:")
        for issue in all_issues:
            print(f"  - {issue}")
        sys.exit(1)

    print(f"\n\u2705 PR #{pr_num} is FULLY CLEAN on HEAD {sha[:8]}!")
    sys.exit(0)


if __name__ == "__main__":
    main()
