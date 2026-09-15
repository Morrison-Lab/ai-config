"""PreToolUse gate for Antigravity: deny PR merges that lack a clean review.

Fires on `run_command` tool calls that look like merges. Denies unless the
PR carries an affirmative approval: a human APPROVED review, a human
review whose body affirmatively approves (bounded per the reviews bullet
below), or a verdict-bearing bot comment whose latest verdict is clean for
the current head. Fails closed on ambiguity: an unparseable state denies
with a reason rather than allowing.

Hardened per Morrison-Lab/ai-config#2676 after Lacaedemon/sparta#1427 was
merged over a "Needs more work" verdict (reverted in sparta#1429):
- the verdict comes from the latest comment carrying a `### Verdict`
  heading outside blockquotes and code fences, not from whichever bot
  comment happens to be last (on sparta that was a demo-diff snapshot);
  a human-authored verdict *comment* counts for deny but never for
  allow (only a review can carry human approval; see below);
  a standing not-clean verdict vetoes merge even beside a human
  APPROVED review (ai-config#2274);
- only the text under `### Verdict` is classified, and negated approvals
  ("cannot approve", "not approved") classify as not-clean;
- a formal review's mere existence no longer satisfies the gate (Copilot's
  COMMENTED review used to); a human review counts as approval when its
  latest state is APPROVED or its body affirmatively approves
  (ai-config#3062 -- reviewers here never submit APPROVED, so keying the
  allow-path on that state alone made it dead code), and a standing
  CHANGES_REQUESTED denies. A body-derived approval is bounded so it
  cannot become a self-approval route: it never counts from the PR's own
  author, never from an `authorAssociation` outside the repository,
  never from a review whose own `commit.oid` is not the head, never from
  a raw body carrying the agent-disclosure marker (quoted or fenced
  included), and never from a body that says anything besides the
  approval itself -- one line, under an optional `### Verdict` heading,
  matched end to end, with no lead-in, no trailing clause, and no later
  line; a later non-approving review from the same human retracts it.
  Those bounds carry a narrower property across the reviews channel
  than the comments channel enforces: an agent posting under the user's
  login cannot approve the merge of a PR it opened. On a PR someone else
  opened (a bot's chore PR, another member's), the author key does not
  fire, and what stands between an agent's own review and an allow is
  the disclosure marker `hooks/require-agent-disclosure.py` obliges it
  to carry -- a convention rather than a property of the record.
  Keying the veto on the merging account instead would deny the human
  reviews this repo actually gets, since the reviewer and the merging
  agent share one login here (ai-config#3062);
- a verdict naming a `Reviewed commit:` other than the PR head is stale and
  denies;
- `--admin` merges (server-rule bypass) and GraphQL mergePullRequest
  mutations are denied outright, and `gh api .../pulls/N/merge` is
  gated against the PR named in the URL;
- comments are fetched via the paginated REST endpoint, so the latest
  verdict on a long thread is not lost to `gh pr view` truncation.

`git merge origin/main` is deliberately NOT gated: it merges main *into*
the branch (the corpus-mandated sync direction) and cannot merge into main.
"""
import sys
import json
import subprocess
import re
import shlex

# gh accepts inherited flags between the command group and the subcommand
# ("gh pr -R o/r merge 5"), so the trigger is token-based, not a literal.
GRAPHQL_MERGE_RE = re.compile(
    r"\bgh api\b(?=.*\bgraphql\b)"
    r"(?=.*\b(mergePullRequest|enablePullRequestAutoMerge)\b)",
    re.DOTALL,
)
GH_API_MERGE_RE = re.compile(
    r"\bgh api\b[^|;&\n]*?repos/(\S+?/\S+?)/pulls/(\d+)/merge\b"
)
VERDICT_MARKER_RE = re.compile(r"^\s*### Verdict", re.MULTILINE)
# Logins the review workflows post verdicts under (memories/gh-cli.md: the
# login varies by repo and run). GraphQL review/comment payloads report bot
# logins bare (no [bot] suffix); REST reports the suffixed form.
VERDICT_AUTHOR_LOGINS = {"github-actions", "claude"}
REVIEWER_BOT_LOGINS = VERDICT_AUTHOR_LOGINS | {
    "copilot-pull-request-reviewer", "coderabbitai", "gemini-code-assist",
    "jules",
}
FENCE_RE = re.compile(r"^\s*(```|~~~).*?^\s*\1\s*$", re.MULTILINE | re.DOTALL)
BLOCKQUOTE_LINE_RE = re.compile(r"^\s*>.*$", re.MULTILINE)
CLEAN_VERDICT_RE = re.compile(
    r"\b(ready (?:for|to) merge|verdict[:*\s]+\**\s*(?:clean|green|ready)"
    r"|no findings|approved?)\b",
    re.IGNORECASE,
)
NOT_CLEAN_VERDICT_RE = re.compile(
    r"\b(needs? (?:more )?work|changes requested"
    r"|request[_ ]changes|do not merge|needs? revision"
    r"|(?:\w+n'?t|not|cannot|never)\s+(?:be\s+|yet\s+)*"
    r"(?:approv\w*|ready)|unapproved|disapprov\w*)\b",
    re.IGNORECASE,
)
# The reviewer's machine-readable `review-data` payload, restated here.
# `scripts/check-pr-fully-clean.py` reads it through
# `scripts/lib/review_payload.py`; this gate must stay import-free (see
# `extract_request_names` below), so the semantics are duplicated rather than
# shared, and `scripts/test_enforce_mwc_review_gate.py` pins them against that
# module so the two cannot drift apart silently (ai-config#3628).
PAYLOAD_OPEN_RE = re.compile(r"<!--\s*review-data\s*:\s*", re.IGNORECASE)
# Verdict strings that block / clear, normalized to upper case with `-` and
# spaces folded to `_`, so `Not clean`, `NOT-CLEAN` and `NOT_CLEAN` are one key.
PAYLOAD_NOT_CLEAN_VERDICTS = frozenset({
    "NOT_CLEAN", "NEEDS_WORK", "NEEDS_MORE_WORK", "CHANGES_REQUESTED",
    "BLOCK", "BLOCKED", "REJECTED",
})
PAYLOAD_CLEAN_VERDICTS = frozenset({
    "CLEAN", "READY_FOR_MERGE", "APPROVED", "APPROVE",
})
# Code-region masking, transcribed from `scripts/lib/fences.py` for the same
# reason the payload reader is: this file takes no imports. Over-masking is the
# safe direction and under-masking is not -- a payload this mask hides falls
# back to the prose scan, which is the behaviour that predates structured
# review data, whereas a payload read out of quoted example text inverts a
# verdict. `evaluate_verdict`'s own `FENCE_RE.sub` is NOT a substitute: it
# requires a matching closing delimiter, so an UNCLOSED fence quoting the
# reviewer prompt's own CLEAN template stays fully live (the ai-config#2482
# class), and it does not touch inline code spans at all.
# An HTML comment is invisible in rendered Markdown, so nothing inside one is
# prose a reviewer wrote for a human to read. The `review-data` payload is the
# case that matters: its raw JSON is TEXT, and `"verdict": "approved"` matches
# `CLEAN_VERDICT_RE`'s own `approved?` alternative, so a payload reaching the
# prose scan votes twice -- once as structured data and once as prose. That
# defeats the rule directly above `classify_verdict_body`'s payload block: a
# payload without `schema_version` may block but must never clear, and one
# spelling its verdict `approved`, `approve`, or `Ready For Merge` cleared
# anyway, flipping the gate from deny to allow (review finding, PR #3629).
#
# `blank_comment_regions` does the stripping rather than a `<!--.*?-->` regex,
# which was the first cut and was defeated twice in the same direction:
#
#   - An UNTERMINATED comment matches nothing, so a truncated payload's JSON
#     stayed live in full.
#   - A payload whose JSON contains a literal `-->` (a finding quoting the
#     payload format, say) ends the non-greedy match early, leaving whatever
#     follows -- including a later `verdict` field -- live.
#
# Both are the terminator ambiguity `extract_structured_review` already
# refuses to have, by reading the object with `raw_decode` instead of matching
# a closing delimiter (ai-config#3054). Stripping by regex reintroduced in one
# half of the function the hazard the other half was hardened against, so the
# two halves now share `iter_payload_spans`.
#
# Sharing the span reader covers a payload that PARSES, and a third route ran
# under it: a payload `iter_payload_spans` declines -- invalid JSON is the
# likely spelling, since a model writes these -- reached the closer search
# after all, because the reader yielded only its successes and so said nothing
# about it. It now reports the failure as `(start, None, None)`, and both
# readers act on that: `read_payload_state` refuses to clear on a sibling
# payload, and `blank_comment_regions` records that some of that payload's
# text may have survived its blank.
PAYLOAD_FENCE_LINE_RE = re.compile(
    r"^(?P<indent> {0,3})(?P<run>`{3,}|~{3,})(?P<info>[^\r\n]*)$"
)
PAYLOAD_CODE_SPAN_RE = re.compile(
    r"(?<!`)(`+)(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
)

REVIEWED_COMMIT_RE = re.compile(
    r"Reviewed[-\s]commit[:\s]+`?([0-9a-f]{7,40})`?", re.IGNORECASE
)
_COPILOT_HEADING_PREFIX = r"(?:^|\n)[ \t]*#{1,6}[ \t]*(?:[^\w\n\'\"]+[ \t]*)?"
COPILOT_AFFIRMATIVE_HEADER = re.compile(
    _COPILOT_HEADING_PREFIX + r"\bApproval\s+recommended\b", re.IGNORECASE
)
COPILOT_NEGATIVE_HEADER = re.compile(
    _COPILOT_HEADING_PREFIX
    + r"\b(?:Changes\s+recommended|Needs\s+a\s+closer\s+look)\b",
    re.IGNORECASE,
)
COPILOT_SUPPRESSED_BLOCK = re.compile(
    r"\b(?:Suppressed\s+comments|Comments\s+suppressed\s+due\s+to\s+low\s+confidence)\b",
    re.IGNORECASE,
)
# Shortest sha abbreviation a head-binding prefix test will accept.
ABBREV_SHA_LEN = 7
# Markdown emphasis and terminal punctuation around an approval headline,
# so `**Ready for merge**.` reads as the phrase itself. Heading, quote, and
# strikethrough markers are deliberately absent: a human approval must be
# the bare phrase, and a quoted or struck-through line is not it.
HEADLINE_TRIM_RE = re.compile(r"^[\s*_`]+|[\s*_`.!]+$")
LIST_ITEM_RE = re.compile(r"^([-+*]|\d+[.)])\s")
# The corpus-mandated agent-disclosure marker, plus the headers review
# workflows post under. `gh pr review --comment` is a first-class agent
# surface (hooks/require-agent-disclosure.py gates it), so a review body
# declaring itself agent-written is not human approval, whoever submitted it.
AGENT_AUTHORSHIP_RE = re.compile(
    r"posted by\b[^\n]*\(ai agent\)|\*\*claude finished|\U0001f916",
    re.IGNORECASE,
)
# `authorAssociation` values that mark a reviewer as belonging to the
# repository. A COMMENTED review is an ordinary drive-by comment that anyone
# with read access can post, so without this bound any stranger's "Ready for
# merge." would authorize the merge; a formal APPROVED review is a distinct
# authorizing act GitHub records, which is why its fast path needs no such
# check.
TRUSTED_REVIEW_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
PR_URL_RE = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)")
# "&" also covers "&&"; "$(" and "`" catch command substitution. Substring
# matching can over-fire on quoted bodies -- that direction fails closed.
CHAIN_CHARS = (";", "&", "|", "\n", "$(", "`", "(")

BLOCKED_CI_CONCLUSIONS = {
    "FAILURE", "ACTION_REQUIRED", "TIMED_OUT", "CANCELLED", "STARTUP_FAILURE",
}
PENDING_CI_STATUSES = {"IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED"}
BLOCKED_STATUS_STATES = {"FAILURE", "ERROR", "PENDING", "EXPECTED"}


def deny(reason):
    return {"decision": "deny", "reason": reason}


ALLOW = {"decision": "allow"}


def is_bot_login(login):
    return (login.endswith("[bot]")
            or login.removesuffix("[bot]") in REVIEWER_BOT_LOGINS)


def human_review_body_approves(body):
    """Whether a human review body affirmatively approves the PR.

    An `APPROVED` state alone cannot carry human approval in this corpus,
    so keying the allow-path on it made that branch dead (ai-config#3062).
    Measured 2026-09-02 over the 25 most recently merged
    Morrison-Lab/ai-config PRs: 168 of 168 reviews were COMMENTED and none
    was APPROVED, and shared/workflow/fully-clean.md tells reviewers not to
    wait for a formal APPROVED review. So read the body's substance beside
    the state.

    The rule is that a reviewer who wants to authorize writes the approval
    and stops. One bar governs the whole body, not one bar per zone: every
    non-empty line is collected, an optional `### Verdict` heading may
    stand above them, and exactly one line may remain -- the approval
    phrase itself, once Markdown emphasis and a terminal `.` or `!` are
    trimmed, matched end to end rather than as a substring.

    That bar is emptiness rather than a word list because the ways of
    withholding an approval are unbounded while an approval is not.
    Enumerating in the allow direction fails closed; enumerating in the
    veto direction authorizes a merge over whatever the list omits. Three
    earlier attempts at the veto direction each shipped a hole a reviewer
    could walk through in ordinary prose: a conditional word list let
    "Ready for merge." stand over "Please fix the typo."; splitting the
    headline on sentence punctuation let the same request back in joined
    by a semicolon, comma, colon, or dash; and exempting the lead-in above
    a `### Verdict` heading let the findings stand wherever this corpus's
    own review layout puts them (`### Findings` above `### Verdict`, per
    shared/workflow/self-review-fallback.md).

    Nothing is blanked before the count, either. Blockquoting and fencing
    hide a region from a veto that reads text, so a quoted request or a
    fenced snippet would otherwise vanish and leave a bare approval
    standing. Here they add lines instead. `>` is also absent from the
    trim, so a body quoting someone else's approval is not itself one.

    Two further bounds, each closing a route by which this would be looser
    than the `APPROVED` state it stands in for:

    - a body carrying the agent-disclosure marker is not human approval,
      whichever login submitted the review;
    - the review must be head-bound and its author a repository member,
      which `body_approval_is_admissible` checks on the review record
      rather than on its prose.
    """
    if not body:
        return False
    if AGENT_AUTHORSHIP_RE.search(body):
        return False
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if lines and VERDICT_MARKER_RE.match(lines[0]):
        rest = VERDICT_MARKER_RE.sub("", lines[0], count=1).strip()
        lines = ([rest] if rest else []) + lines[1:]
    if len(lines) != 1 or LIST_ITEM_RE.match(lines[0]):
        return False
    return bool(CLEAN_VERDICT_RE.fullmatch(HEADLINE_TRIM_RE.sub("", lines[0])))


def body_approval_is_admissible(review, head_oid):
    """Whether a COMMENTED review's metadata permits reading approval from it.

    Two bounds, both on the review record rather than on its prose, so they
    hold whatever the body says:

    - `authorAssociation` must mark the reviewer as belonging to the
      repository. Submitting a COMMENTED review is what any commenter can
      do, so trusting a non-bot login alone would let a stranger's "Ready
      for merge." authorize the merge.
    - the review's own `commit.oid` must be the PR head. GitHub records the
      commit every review was submitted against, and never dismisses a
      COMMENTED review, so this is what makes a body-derived approval
      head-bound like every other allow path here; a `Reviewed commit:`
      footer is a bot convention a human body does not carry, so it is a
      secondary check rather than the head binding.

    Each fails closed on an absent value: a payload that cannot show the
    review was submitted by a repository member against the head cannot
    show the approval is admissible, and an unverifiable approval is
    treated as no approval.
    """
    assoc = (review.get("authorAssociation") or "").upper()
    if assoc not in TRUSTED_REVIEW_ASSOCIATIONS:
        return False
    oid = ((review.get("commit") or {}).get("oid") or "")
    if len(oid) < ABBREV_SHA_LEN:
        return False
    return bool(head_oid and head_oid.startswith(oid))


def latest_human_review_states(reviews, head_oid="", pr_author=""):
    """Latest standing per non-bot author.

    Values are APPROVED, CHANGES_REQUESTED, NOT_CLEAN, or SELF_APPROVED.
    NOT_CLEAN is a body-derived blocker: an admissible review body stating
    the PR is not clean, matched over the raw body with quotes and fences
    included. SELF_APPROVED is a body-derived approval that cannot be
    attributed to someone other than the PR's own author, which is
    recorded so the caller can say why it does not authorize a merge, and
    which never allows.

    PENDING never changes an author's standing, and COMMENTED changes it
    only when the review record is admissible (see
    `body_approval_is_admissible`) and the body either affirmatively
    approves (see `human_review_body_approves`) or matches
    `NOT_CLEAN_VERDICT_RE`. GitHub marks a dismissed review by
    mutating its state to DISMISSED in place; handle a trailing DISMISSED
    entry too, so either payload shape clears standing.

    A body-derived approval deliberately cannot clear a standing
    CHANGES_REQUESTED: CLAUDE.md holds that only that reviewer or an
    explicit dismissal resolves one, and an inferred approval is weaker
    evidence than the formal state it would be overriding.

    It is also genuinely *latest* rather than sticky: a later
    non-approving review from the same human retracts it, since GitHub
    never dismisses a COMMENTED review and `evaluate_verdict` reads issue
    comments only, so nothing else would see the retraction. Retraction is
    keyed on the approval a body *established*, not on every body that
    approves, so a formal APPROVED that a later approving COMMENTED review
    merely restates stays formal, and chatty follow-up prose cannot clobber
    it.

    The PR author's own body-derived approval never counts. GitHub itself
    forbids an author approving their own PR, which is why the formal
    APPROVED fast path never needed the guard; `gh pr review --comment`
    has no such restriction, so without this an agent running under the
    user's login could authorize its own merge by posting its self-review
    as a review rather than as a comment (which `evaluate_verdict`
    already refuses). An empty `pr_author` fails closed the same way: a
    payload that cannot name the author cannot show the reviewer is
    someone else.
    """
    states = {}
    inferred = set()
    for r in reviews:
        login = r.get("author", {}).get("login", "")
        if not login or is_bot_login(login):
            continue
        state = r.get("state", "")
        if state in ("APPROVED", "CHANGES_REQUESTED"):
            states[login] = state
            inferred.discard(login)
        elif state == "DISMISSED":
            states.pop(login, None)
            inferred.discard(login)
        elif state == "COMMENTED" and states.get(login) != "CHANGES_REQUESTED":
            raw_body = r.get("body", "") or ""
            admissible = body_approval_is_admissible(r, head_oid)
            if admissible and human_review_body_approves(raw_body):
                # Only an approval this body established is retractable.
                # Marking the login inferred while a formal APPROVED already
                # stands would let the next chatty review pop that formal
                # state, which is a false deny.
                if states.get(login) != "APPROVED" or login in inferred:
                    inferred.add(login)
                states[login] = (
                    "APPROVED" if pr_author and login != pr_author
                    else "SELF_APPROVED"
                )
            elif admissible and NOT_CLEAN_VERDICT_RE.search(raw_body):
                states[login] = "NOT_CLEAN"
                inferred.discard(login)
            elif login in inferred:
                states.pop(login, None)
                inferred.discard(login)
    return states


def extract_request_names(review_requests):
    """Extract reviewer logins or team slugs from reviewRequests.

    Defined self-contained here so the enforcement hook has no external
    library or module import dependencies when run across standalone or
    minimal plugin environments.
    """
    names = []
    for r in review_requests:
        if isinstance(r, dict):
            name = r.get("login") or r.get("name") or r.get("slug") or ""
        else:
            name = str(r).strip()
        if name:
            names.append(name)
    return names


def latest_bot_review_states(reviews, head_oid=""):
    """Latest standing per bot author.

    Tracks whether any bot review (e.g. Copilot, Coderabbit) submitted a formal
    CHANGES_REQUESTED review or has a negative verdict header (such as
    'Changes recommended' or 'Needs a closer look').
    A formal CHANGES_REQUESTED or an admissible negative verdict stands across commits
    until superseded by a clean review on the current head or dismissed.
    """
    states = {}
    for r in reviews:
        login = (r.get("author") or {}).get("login", "")
        if not login or not is_bot_login(login):
            continue
        state = (r.get("state") or "").upper()
        if state == "DISMISSED":
            states.pop(login, None)
            continue
        if state in ("CHANGES_REQUESTED", "REJECTED"):
            states[login] = state
            continue
        if state == "APPROVED":
            states[login] = "APPROVED"
            continue
        raw_body = r.get("body", "") or ""
        oid = ((r.get("commit") or {}).get("oid") or "")
        is_negative = bool(
            COPILOT_NEGATIVE_HEADER.search(raw_body)
            or NOT_CLEAN_VERDICT_RE.search(raw_body)
            or (COPILOT_SUPPRESSED_BLOCK.search(raw_body) if COPILOT_AFFIRMATIVE_HEADER.search(raw_body) else False)
        )
        if is_negative:
            states[login] = "NOT_CLEAN"
            continue

        is_affirmative = bool(
            (COPILOT_AFFIRMATIVE_HEADER.search(raw_body) and not COPILOT_SUPPRESSED_BLOCK.search(raw_body))
            or CLEAN_VERDICT_RE.search(raw_body)
        )
        if is_affirmative:
            if head_oid and oid and len(oid) >= ABBREV_SHA_LEN and head_oid.startswith(oid):
                states[login] = "CLEAN"
            elif states.get(login) == "CLEAN":
                states.pop(login, None)
    return states


def payload_code_mask(body):
    """Byte-per-character mask: 1 where *body* is inside a code region.

    Covers fenced blocks (including an UNCLOSED fence, swallowed to end of
    text), CommonMark indented code blocks, and inline code spans -- the same
    three regions `scripts/lib/review_payload.py`'s `code_region_mask` covers,
    because the two must score the same artifact the same way. The
    indented-block test is correspondingly crude (it also catches indented
    list continuations) for the over-masking reason above.
    """
    lines = body.split("\n")
    fenced_lines = set()
    in_fence = False
    fence_char = ""
    fence_len = 0
    start_idx = 0
    for idx, line in enumerate(lines):
        m = PAYLOAD_FENCE_LINE_RE.match(line.rstrip("\r"))
        if not in_fence:
            if m:
                run, info = m.group("run"), m.group("info")
                # A backtick opener's info string may not contain a backtick.
                if run[0] == "`" and "`" in info:
                    continue
                in_fence, fence_char, fence_len, start_idx = True, run[0], len(run), idx
        elif m:
            run, info = m.group("run"), m.group("info")
            if run[0] == fence_char and len(run) >= fence_len and not info.strip():
                fenced_lines.update(range(start_idx, idx + 1))
                in_fence = False
    if in_fence:
        # Swallow an unclosed fence to end of text. Recording only its opener
        # line leaves the interior live, which fails in both directions: a
        # truncated review's quoted CLEAN template counts as a real verdict,
        # and a quoted NOT_CLEAN payload mints a finding no ARD round can
        # discharge.
        fenced_lines.update(range(start_idx, len(lines)))

    mask = bytearray(len(body))
    offset = 0
    for idx, line in enumerate(lines):
        end = offset + len(line)
        if idx in fenced_lines or line.startswith("    ") or line.startswith("\t"):
            mask[offset:end] = b"\x01" * (end - offset)
        offset = end + 1
    for m in PAYLOAD_CODE_SPAN_RE.finditer(body):
        mask[m.start():m.end()] = b"\x01" * (m.end() - m.start())
    return mask


def normalize_payload_verdict(raw):
    """Fold a payload `verdict` value to the form the frozensets above use."""
    return str(raw or "").strip().upper().replace("-", "_").replace(" ", "_")


def iter_payload_spans(body):
    """Yield `(start, end, data)` for every `review-data` opener at a readable
    position: a well-formed payload as `(start, end, dict)`, and one that
    could not be bounded as `(start, None, None)`.

    `end` is derived from `raw_decode`, never from a search for `-->`, so a
    finding whose own text contains that substring cannot shorten the span.
    Both readers of a payload -- the one that classifies it and the one that
    removes it from the prose -- take their boundaries from here, so the text
    blanked is exactly the text parsed.

    REPORTING THE FAILURES is what makes "the last valid payload wins" safe.
    Yielding only the valid ones cannot distinguish a body with one payload
    from a body whose real, final payload has a trailing comma and whose only
    parseable one is an earlier draft the reviewer had already corrected. The
    second silently degrades to the first, so a CLEAN quoted above a genuine
    NOT_CLEAN decided the merge (review finding, PR #3629).
    """
    if not body or not isinstance(body, str):
        return
    mask = payload_code_mask(body)
    for m in PAYLOAD_OPEN_RE.finditer(body):
        if mask[m.start()]:
            continue
        line_start = body.rfind("\n", 0, m.start()) + 1
        if body[line_start:m.start()].strip():
            continue
        json_start = m.end()
        while json_start < len(body) and body[json_start] in " \t\r\n":
            json_start += 1
        if json_start >= len(body) or body[json_start] != "{":
            yield m.start(), None, None
            continue
        try:
            data, end_idx = json.JSONDecoder().raw_decode(body, json_start)
        except ValueError:
            yield m.start(), None, None
            continue
        tail = end_idx
        while tail < len(body) and body[tail] in " \t\r\n":
            tail += 1
        if body[tail:tail + 3] != "-->":
            yield m.start(), None, None
            continue
        if isinstance(data, dict) and "verdict" in data:
            yield m.start(), tail + 3, data
        else:
            yield m.start(), None, None


def blank_comment_regions(text):
    """Replace every HTML comment in *text* with a space.

    Returns ``(blanked, payload_unreadable)``. The flag says a `review-data`
    opener was found that :func:`iter_payload_spans` could not bound, so some
    of that payload's text may have survived into *blanked*. The caller uses
    it to refuse a CLEAN reading while still honouring a not-clean one --- see
    :func:`classify_verdict_body`.

    A WELL-FORMED payload's span comes from :func:`iter_payload_spans`, so a
    literal `-->` inside its JSON cannot end the region early. An UNTERMINATED
    `<!--` is swallowed to end of text, which loses nothing a human could read
    anyway: everything after it is inside the comment. Any other comment,
    including a payload whose JSON will not parse, is blanked only as far as
    its own closer.

    THE FLAG RATHER THAN A WIDER BLANK, and the reasoning matters because the
    first cut got it backwards. An unparseable payload was swallowed to end of
    text on the argument that over-blanking is the safe direction, since a
    hidden verdict classifies ambiguous and ambiguous denies. That second
    clause is false: `evaluate` treats only `not-clean` and `stale` as vetoes,
    so an ambiguous bot verdict beside a standing human APPROVED review
    ALLOWS. Swallowing therefore discarded a reviewer's stated "needs more
    work" and let the merge through --- a fail-open built out of an
    over-cautious blank (review finding, PR #3629).

    So the asymmetry lives in what the text may CONCLUDE rather than in how
    much of it is erased. Leaked payload text can only manufacture a false
    CLEAN, which the flag refuses; prose that states a finding is left where
    the scan can still find it.
    """
    chars = list(text)
    for start, end, _ in iter_payload_spans(text):
        if end is not None:
            chars[start:end] = " " * (end - start)
    text = "".join(chars)

    out = []
    pos = 0
    unreadable = False
    while True:
        open_idx = text.find("<!--", pos)
        if open_idx < 0:
            out.append(text[pos:])
            return "".join(out), unreadable
        out.append(text[pos:open_idx])
        out.append(" ")
        # A `review-data` opener surviving the pass above is one
        # `iter_payload_spans` could not bound. Four reasons reach here:
        # invalid JSON, trailing text before the closer, a position the code
        # mask rejected, and one the line-start rule rejected. Its closer
        # cannot be located by searching for `-->`, since its own text may
        # contain that substring -- so some of it may survive the blank below,
        # and the flag is how the caller is told not to trust a CLEAN reading
        # of this section.
        #
        # The last two reasons carry a cost that is CHOSEN rather than
        # overlooked. A fenced example, or a sentence naming the format
        # mid-line, is benign, and flagging it denies an unrelated clean
        # headline elsewhere in the same section. Telling those apart means
        # asking whether the blank below actually fell short, which is the
        # terminator question this function exists not to answer -- so the
        # answer is the same one it gives everywhere else, and the reviewer
        # re-runs. `test_a_benign_payload_mention_withholds_a_clean_headline`
        # pins it so the cost stays visible, and refining it is ai-config#3691.
        if PAYLOAD_OPEN_RE.match(text, open_idx):
            unreadable = True
        close_idx = text.find("-->", open_idx + 4)
        if close_idx < 0:
            return "".join(out), unreadable
        pos = close_idx + 3


def extract_structured_review(body):
    """Return the LAST well-formed `review-data` payload in *body*, or None.

    Two properties are load-bearing, and both are the shared module's:

    * **The last valid payload wins.** The contract puts the authoritative
      payload after the verdict, and the reviewer persona template it is
      copied from hardcodes a CLEAN verdict -- so first-match-wins let a
      reviewer who quoted the template above their own payload publish a
      NOT_CLEAN review that scored clean.
    * **The opener must start its own line, outside every code region.**
      `payload_code_mask` decides the second half, because the caller's own
      blanking decides only part of the first: `evaluate_verdict` removes
      blockquote lines and CLOSED fences, and leaves an unclosed fence and
      every inline code span live. The line-start rule is what the mask
      cannot supply -- a payload written mid-sentence in ordinary prose
      ("reviewers must end with <!-- review-data: ... -->") sits in no code
      region at all. One to three spaces of indent stays readable, since four
      is a CommonMark indented code block the mask already covers: the review
      prompt once rendered the payload indented, and rejecting that spelling
      failed open by dropping a NOT_CLEAN payload.

    The JSON object is read with `raw_decode` rather than a non-greedy regex,
    so a finding's own text containing a literal close-brace-then-arrow
    substring cannot terminate the object early (ai-config#3054).
    """
    return read_payload_state(body)[0]


def read_payload_state(body):
    """Return `(last_valid_payload_or_None, unreadable)`.

    `unreadable` is True when any `review-data` opener at a readable position
    could not be bounded. A caller may still BLOCK on the payload it did get;
    it must not CLEAR on one, because the payload that would have decided the
    review may be the one that failed to parse.
    """
    found, unreadable = None, False
    for _start, end, data in iter_payload_spans(body):
        if end is None:
            unreadable = True
        else:
            found = data
    return found, unreadable


def payload_findings_malformed(payload):
    """True when `findings` is PRESENT but is not a list.

    A present-but-malformed field must never clear, only block: folding it to
    an empty list makes a type deviation do what an empty array does, which is
    the fail-open direction in a fail-closed gate.
    """
    if not payload:
        return False
    return "findings" in payload and not isinstance(payload["findings"], list)


def payload_is_blocking(payload):
    """True when the payload blocks: not-clean verdict, any finding, or a
    malformed `findings` field.

    Findings block regardless of the stated verdict: a reviewer that
    enumerates findings and then labels itself clean is contradicting itself,
    and the safe reading of a contradiction is the blocking one.
    """
    if not payload:
        return False
    if payload_findings_malformed(payload):
        return True
    findings = payload.get("findings")
    if isinstance(findings, list) and findings:
        return True
    verdict = normalize_payload_verdict(payload.get("verdict"))
    return verdict in PAYLOAD_NOT_CLEAN_VERDICTS


def payload_is_clean(payload):
    """True when the payload affirmatively clears.

    Requires all three: a clean verdict, a `findings` key that is present and
    a list, and that list empty. Requiring presence is the point -- the
    reviewer prompt says a CLEAN payload requires an empty findings array, and
    a payload that simply omits the key must not clear.
    """
    if not payload:
        return False
    if not isinstance(payload.get("findings"), list):
        return False
    if payload["findings"]:
        return False
    verdict = normalize_payload_verdict(payload.get("verdict"))
    return verdict in PAYLOAD_CLEAN_VERDICTS


def classify_verdict_body(body, head_oid):
    """Classify one blanked, marker-bearing verdict body."""
    section = VERDICT_MARKER_RE.split(body, maxsplit=1)[1]
    # The verdict's own footer is the last "Reviewed commit:" line; earlier
    # occurrences may quote prior rounds. A format that prints the line
    # above the heading still gets a staleness check via the whole body.
    shas = REVIEWED_COMMIT_RE.findall(section) or REVIEWED_COMMIT_RE.findall(body)
    if shas and head_oid and not head_oid.startswith(shas[-1]):
        return "stale"
    # The reviewer's own machine-readable payload outranks the prose scan
    # below, as it does in `scripts/check-pr-fully-clean.py` (ai-config#3054,
    # #3628): a verdict phrase matched out of a retrospective or a negated
    # sentence must not override the verdict the reviewer actually published.
    # `schema_version` is the contract's version marker, so a payload carrying
    # it decides on its own; one without it can still BLOCK, but never clear
    # -- the asymmetry keeps a half-formed payload out of the allow path of a
    # fail-closed gate.
    #
    # Deliberately NOT identical to that sibling, which is why this does not
    # claim to be. Its `classify_verdict` runs a second, unconditional
    # `payload_is_clean` AFTER its prose scans, so a `schema_version`-absent
    # payload can clear there when the prose matches nothing. A gate that
    # refuses a merge is the wrong place to copy an extra allow path into, so
    # a payload here clears only through the one route below and never after
    # the prose scan.
    structured, payload_unreadable = read_payload_state(body)
    # `read_payload_state` reports an opener it tried to parse and could not.
    # It says nothing about one it never tried, which it skips for POSITION --
    # masked as code, or not alone on its line. `blank_comment_regions` is the
    # reader that sees those, so its flag is consulted here as well as over
    # the prose section below.
    #
    # Consulting it HERE is the point. Without it the two clean routes
    # disagreed: a benign mid-line mention denied a clean stated in prose (the
    # cost `test_a_benign_payload_mention_withholds_a_clean_headline` pins)
    # and did not deny a clean stated in a payload, because this block
    # returned before the prose path ever ran. A reviewer quoting a NOT_CLEAN
    # payload mid-sentence and publishing a CLEAN one therefore cleared, while
    # the same quote beside a prose headline did not (review finding, #3629).
    _, body_unreadable = blank_comment_regions(body)
    payload_unreadable = payload_unreadable or body_unreadable

    # Blocking first, and once: a payload that blocks does so whether or not
    # it carries `schema_version`, so the two tests the fast path used to run
    # separately collapse into this one. Clearing then needs all three of the
    # version marker, a payload that affirmatively clears, and no sibling
    # opener either reader could not bound.
    if payload_is_blocking(structured):
        return "not-clean"
    if (isinstance(structured, dict) and "schema_version" in structured
            and payload_is_clean(structured) and not payload_unreadable):
        return "clean"

    # Everything below is a scan of PROSE, so the payload's own JSON must not
    # reach it -- see `blank_comment_regions`. Stripping here rather than at
    # the top of the function is deliberate: the payload block above needs the
    # comment intact, and the staleness check reads a `Reviewed commit:` line
    # that a reviewer may legitimately place inside one.
    section, section_unreadable = blank_comment_regions(section)
    payload_unreadable = payload_unreadable or section_unreadable
    # The headline (first non-empty line under the heading) outranks later
    # prose, so "Ready for merge --- the concern that this wasn't ready is
    # resolved" classifies by its headline rather than its narrative.
    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]
    headline = lines[0] if lines else ""
    for text in (headline, section):
        if NOT_CLEAN_VERDICT_RE.search(text):
            return "not-clean"
        if CLEAN_VERDICT_RE.search(text):
            # An unbounded payload may have leaked its own JSON into this
            # text, and that text can only ever manufacture a FALSE clean --
            # so the clean reading is withheld while the not-clean one above
            # is not. Downgrading to ambiguous rather than erasing the prose
            # is what keeps a reviewer's stated finding readable.
            return "ambiguous" if payload_unreadable else "clean"
    return "ambiguous"


def evaluate_verdict(comments, head_oid):
    """Classify the PR's review-verdict state.

    Returns one of: "clean", "not-clean", "stale", "ambiguous",
    "untrusted-clean", "none".

    The latest TRUSTED verdict (reviewer-login comment with an unquoted,
    unfenced `### Verdict` heading) governs. An untrusted verdict -- any
    other login, including the agent posting under the user's own -- can
    only tighten the result: a later untrusted not-clean/stale verdict
    (e.g. a human self-review) denies, but an untrusted clean or ambiguous
    comment never supersedes the trusted state, so a stray `### Verdict`
    heading in an ARD reply cannot launder a standing veto (nor block a
    legitimately clean merge).
    """
    trusted_state, trusted_idx = None, -1
    untrusted = []
    for idx, c in enumerate(comments):
        login = c.get("author", {}).get("login", "") or ""
        trusted = login.removesuffix("[bot]") in VERDICT_AUTHOR_LOGINS
        raw = c.get("body", "")
        # A blockquoted verdict (an ARD reply citing the review) is not a
        # verdict; fenced content (a comment showing the format) isn't either.
        unquoted = BLOCKQUOTE_LINE_RE.sub("", raw)
        blanked = FENCE_RE.sub("", unquoted)
        if VERDICT_MARKER_RE.search(blanked):
            if trusted:
                trusted_state = classify_verdict_body(blanked, head_oid)
                trusted_idx = idx
            else:
                untrusted.append((idx, classify_verdict_body(blanked, head_oid)))
        elif trusted and VERDICT_MARKER_RE.search(unquoted):
            # The reviewer's own verdict heading was swallowed by a fence
            # (e.g. an unclosed code block): unreadable, so fail toward
            # ambiguity rather than treating the round as verdict-free.
            trusted_state, trusted_idx = "ambiguous", idx
    for idx, state in untrusted:
        if idx > trusted_idx and state in ("not-clean", "stale"):
            return state
    if trusted_state:
        return trusted_state
    if any(state == "clean" for _, state in untrusted):
        return "untrusted-clean"
    return "none"


def evaluate(cmd, pr_data):
    """Pure decision function: merge command + PR state -> hook decision."""
    if GRAPHQL_MERGE_RE.search(cmd):
        return deny(
            "Strict Merge Control Policy: merge via a GraphQL mutation is "
            "not allowed -- the gate cannot resolve which PR it targets. "
            "Use gh pr merge <number> -R <owner>/<repo> instead."
        )
    if "--admin" in cmd:
        return deny(
            "Strict Merge Control Policy: --admin bypasses the repository's "
            "own merge rules and is never allowed from an agent session. "
            "Drive the PR to a clean verdict and merge without --admin."
        )

    reviews = pr_data.get("reviews", []) or []
    comments = pr_data.get("comments", []) or []
    head_oid = pr_data.get("headRefOid", "") or ""
    pr_author = (pr_data.get("author") or {}).get("login", "") or ""

    # CI first: never merge red or incomplete checks.
    status_rollup = pr_data.get("statusCheckRollup") or []
    # CheckRun entries carry conclusion/status; classic StatusContext
    # entries carry only state (FAILURE/ERROR/PENDING/EXPECTED/SUCCESS).
    failures = [
        check.get("name") or check.get("context") for check in status_rollup
        if (check.get("conclusion") or "").upper() in BLOCKED_CI_CONCLUSIONS
        or (check.get("status") or "").upper() in PENDING_CI_STATUSES
        or (check.get("state") or "").upper() in BLOCKED_STATUS_STATES
    ]
    failures = list(dict.fromkeys(failures))
    if failures:
        return deny(
            "Strict Merge Control Policy: Cannot merge with failing or "
            f"incomplete CI checks: {', '.join(failures)}. Never ignore red "
            "CI; wait for all checks to complete."
        )

    # Reviews in flight check: never merge while reviews are still running/requested (ai-config#3570).
    review_requests = pr_data.get("reviewRequests") or []
    if review_requests:
        req_names = extract_request_names(review_requests)
        if req_names:
            return deny(
                "Strict Merge Control Policy: Cannot merge while reviews are still "
                f"in flight: pending review request(s) for {', '.join(sorted(req_names))}. "
                "Wait for all reviews to complete and post clean verdicts."
            )

    human_states = latest_human_review_states(reviews, head_oid, pr_author)
    blockers = [k for k, v in human_states.items() if v == "CHANGES_REQUESTED"]
    if blockers:
        return deny(
            "Strict Merge Control Policy: standing CHANGES_REQUESTED review "
            f"from {', '.join(sorted(blockers))}. Only that reviewer (or an "
            "explicit dismissal) can clear it -- a later bot verdict cannot."
        )
    not_clean_bodies = [k for k, v in human_states.items() if v == "NOT_CLEAN"]
    if not_clean_bodies:
        return deny(
            "Strict Merge Control Policy: a human review body from "
            f"{', '.join(sorted(not_clean_bodies))} states this PR is not "
            "clean. Disagreement among reviews is not fully clean; address "
            "it and get an approving review on the current head."
        )

    bot_states = latest_bot_review_states(reviews, head_oid)
    bot_blockers = [k for k, v in bot_states.items() if v in ("CHANGES_REQUESTED", "REJECTED", "NOT_CLEAN")]
    if bot_blockers:
        return deny(
            "Strict Merge Control Policy: automated review from "
            f"{', '.join(sorted(bot_blockers))} states this PR is not clean. "
            "Consensus clean verdicts across all reviewers are required to merge; address "
            "it and get an approving review on the current head."
        )

    verdict = evaluate_verdict(comments, head_oid)
    if verdict in ("not-clean", "stale"):
        # A standing not-clean (or stale) verdict vetoes merge even
        # alongside a human approval: disagreement among reviews is not
        # fully clean (CLAUDE.md Strict Merge Control Policy, ai-config#2274).
        pass
    elif any(v == "APPROVED" for v in human_states.values()):
        return ALLOW
    if verdict == "clean":
        return ALLOW
    if verdict == "none" and "SELF_APPROVED" in human_states.values():
        verdict = "self-approved"
    reasons = {
        "not-clean": (
            "the latest review verdict for this PR is not clean (e.g. "
            "'Needs more work'). Address every finding and get a clean "
            "verdict on the current head before merging."
        ),
        "stale": (
            "the latest review verdict names a Reviewed commit that is not "
            "the current PR head. Re-request review and wait for a clean "
            "verdict on the head commit."
        ),
        "ambiguous": (
            "the latest review comment carries no recognizable clean "
            "verdict. A merge needs an affirmative approval; ask a human "
            "to review or re-run the reviewer."
        ),
        "untrusted-clean": (
            "the only clean verdict is a comment posted under a "
            "non-reviewer login, which cannot authorize a merge (an agent "
            "posting under the user's login must not approve its own "
            "work). Get a clean verdict from the review workflow, or an "
            "approving review from a human."
        ),
        "self-approved": (
            "the only approving review is the PR author's own, or the PR "
            "author is not named in the payload, which "
            "cannot authorize a merge (an agent posting under the user's "
            "login must not approve its own work -- posting the "
            "self-review as a review rather than a comment does not "
            "change that). Get a clean verdict from the review workflow, "
            "or an approving review from someone else."
        ),
        "none": (
            "no review verdict and no human approval are present. You "
            "cannot use mwc to bypass the review boundary; request review "
            "first."
        ),
    }
    return deny("Strict Merge Control Policy: " + reasons[verdict])



# gh pr merge / gh stack merge flags that consume a following value token.
VALUE_FLAGS = {
    "-R", "--repo", "-t", "--subject", "-b", "--body", "-F", "--body-file",
    "-A", "--author-email", "--match-head-commit",
}


def parse_gh_pr_merge(cmd):
    """Detect a `gh pr merge` / `gh stack merge` invocation by tokens.

    Returns (is_merge, pr_arg). Token-based because gh accepts inherited
    flags between the command group and the subcommand
    ("gh pr -R o/r merge 5"), and flags before the number
    ("gh pr merge --squash 1427") -- a contiguous-literal trigger or a
    naive next-token grab misreads both. A shlex failure on a command
    containing "merge" reports (True, "") so the caller fails closed
    rather than letting an unparseable merge through.
    """
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return ("gh" in cmd and "merge" in cmd, "")
    gh_idx = next(
        (i for i, t in enumerate(tokens) if t == "gh" or t.endswith("/gh")),
        None,
    )
    if gh_idx is None:
        return False, ""
    rest = tokens[gh_idx + 1:]
    if not rest or rest[0] not in ("pr", "stack"):
        return False, ""
    rest = rest[1:]
    positionals = []
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok.startswith("-"):
            i += 2 if tok in VALUE_FLAGS else 1
            continue
        positionals.append(tok)
        i += 1
    if not positionals or positionals[0] != "merge":
        return False, ""
    return True, positionals[1] if len(positionals) > 1 else ""

def run_gh(args, cwd):
    return subprocess.run(
        ["gh"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )


def _merge_paginated_json(text, decoder=None):
    """Merge whitespace-separated JSON-array pages emitted by gh --paginate."""
    items = []
    if not text:
        return items
    decoder = decoder or json.JSONDecoder()
    pos = 0
    while pos < len(text):
        page, end = decoder.raw_decode(text, pos)
        items.extend(page)
        pos = end
        while pos < len(text) and text[pos] in " \r\n":
            pos += 1
    return items


def fetch_pr_data(cmd, cwd):
    """Resolve the merge target and fetch its state.

    Returns (pr_data, error_reason). Comments come from the paginated REST
    endpoint so a long thread cannot truncate away the latest verdict. Check-runs
    come from the commit check-runs REST endpoint to detect copilot-pull-request-reviewer
    which is dropped by GraphQL statusCheckRollup (ai-config#3570).
    """
    api_match = GH_API_MERGE_RE.search(cmd)
    if api_match:
        repo, number = api_match.group(1), api_match.group(2)
        view_args = ["pr", "view", number]
        if "{" not in repo:
            view_args += ["--repo", repo]
        # A "{owner}/{repo}" placeholder resolves from Cwd, exactly as gh
        # api itself would, so plain `gh pr view <n>` inspects the same PR.
    else:
        _, pr_arg = parse_gh_pr_merge(cmd)
        repo_match = re.search(r"(?:-R|--repo)[= ](\S+)", cmd)
        view_args = ["pr", "view"]
        if pr_arg:
            view_args.append(pr_arg)
        if repo_match:
            view_args += ["--repo", repo_match.group(1)]

    result = run_gh(
        view_args
        + ["--json", "url,author,reviews,statusCheckRollup,headRefOid,reviewRequests"],
        cwd,
    )
    if result.returncode != 0:
        return None, (
            "Hook failed to fetch PR state (gh pr view returned non-zero). "
            "Ensure the PR exists and is checked out. Output: " + result.stderr
        )
    pr_data = json.loads(result.stdout)

    url_match = PR_URL_RE.search(pr_data.get("url", "") or "")
    if not url_match:
        return None, (
            "Hook could not resolve the PR's repository and number from its "
            "URL, so the review thread cannot be verified."
        )
    comments_result = run_gh(
        ["api", f"repos/{url_match.group(1)}/issues/{url_match.group(2)}/comments",
         "--paginate", "--jq", "[.[] | {author: {login: (.user.login // \"\")}, body: .body}]"],
        cwd,
    )
    if comments_result.returncode != 0:
        return None, (
            "Hook failed to fetch the PR's comments (gh api returned "
            "non-zero). Output: " + comments_result.stderr
        )
    decoder = json.JSONDecoder()
    pr_data["comments"] = _merge_paginated_json(comments_result.stdout.strip(), decoder)

    # GraphQL statusCheckRollup drops copilot-pull-request-reviewer
    # (ai-config#3570, fully-clean.cases.md:79). Query commit check-runs via REST
    # and merge them into statusCheckRollup so active or failed reviewer runs block merge.
    head_oid = pr_data.get("headRefOid", "") or ""
    if head_oid:
        check_runs_result = run_gh(
            ["api", f"repos/{url_match.group(1)}/commits/{head_oid}/check-runs",
             "--paginate", "--jq", "[.check_runs[]? | {name: .name, status: (.status // \"\"), conclusion: (.conclusion // \"\")}]"],
            cwd,
        )
        if check_runs_result.returncode != 0:
            return None, (
                "Hook failed to fetch the PR's commit check-runs (gh api returned "
                "non-zero). Output: " + check_runs_result.stderr
            )
        check_runs = _merge_paginated_json(check_runs_result.stdout.strip(), decoder)
        existing_rollup = pr_data.get("statusCheckRollup") or []
        for cr in check_runs:
            existing_rollup.append({
                "name": cr.get("name") or "",
                "status": (cr.get("status") or "").upper(),
                "conclusion": (cr.get("conclusion") or "").upper(),
            })
        pr_data["statusCheckRollup"] = existing_rollup
    return pr_data, None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        print(json.dumps(deny(f"Hook could not parse its input payload: {e}")))
        return
    tool_call = payload.get("toolCall") or {}
    if tool_call.get("name") != "run_command":
        print(json.dumps(ALLOW))
        return

    args = tool_call.get("args") or {}
    cmd = args.get("CommandLine") or ""
    cwd = args.get("Cwd") or "."

    if GRAPHQL_MERGE_RE.search(cmd):
        # Denied before any state fetch: the gate cannot resolve which PR a
        # GraphQL merge mutation targets.
        print(json.dumps(evaluate(cmd, {})))
        return

    # Detect merge-ness per chain segment, so "gh pr create; gh pr merge"
    # still registers as a merge (the chain check below then denies it).
    # "(", "$(", and backticks join the split set so a merge wrapped in a
    # subshell or command substitution becomes its own segment and registers.
    segments = re.split(r"[;&|\n(\x60]|\$\(", cmd)
    is_merge = any(
        parse_gh_pr_merge(seg)[0] or GH_API_MERGE_RE.search(seg)
        for seg in segments
    )
    if not is_merge:
        print(json.dumps(ALLOW))
        return

    # Merges must run standalone so the PR state inspected here is the state
    # the merge executes against.
    if any(ch in cmd for ch in CHAIN_CHARS):
        print(json.dumps(deny(
            "Merge commands (gh pr merge, etc) must be executed on their own, "
            "not chained, piped, backgrounded, or wrapped in command "
            "substitution, so the hook can reliably inspect the PR's review "
            "status before the merge runs."
        )))
        return

    try:
        pr_data, error = fetch_pr_data(cmd, cwd)
        if error:
            print(json.dumps(deny(error)))
            return
        print(json.dumps(evaluate(cmd, pr_data)))
    except Exception as e:  # fail closed: an undiagnosed state never merges
        print(json.dumps(deny(f"Hook exception during PR review check: {e}")))


if __name__ == "__main__":
    main()
