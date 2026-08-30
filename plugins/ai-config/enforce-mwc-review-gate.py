"""PreToolUse gate for Antigravity: deny PR merges that lack a clean review.

Fires on `run_command` tool calls that look like merges. Denies unless the
PR carries an affirmative approval: a human APPROVED review, or a
verdict-bearing bot comment whose latest verdict is clean for the current
head. Fails closed on ambiguity: an unparseable state denies with a reason
rather than allowing.

Hardened per Morrison-Lab/ai-config#2676 after Lacaedemon/sparta#1427 was
merged over a "Needs more work" verdict (reverted in sparta#1429):
- the verdict comes from the latest comment carrying a `### Verdict`
  heading outside blockquotes and code fences, not from whichever bot
  comment happens to be last (on sparta that was a demo-diff snapshot);
  a human-authored verdict counts for deny but never for allow, so an
  agent posting under the user's login cannot approve its own merge;
  a standing not-clean verdict vetoes merge even beside a human
  APPROVED review (ai-config#2274);
- only the text under `### Verdict` is classified, and negated approvals
  ("cannot approve", "not approved") classify as not-clean;
- a formal review's mere existence no longer satisfies the gate (Copilot's
  COMMENTED review used to), and a human review counts only when its latest
  state is APPROVED -- a standing CHANGES_REQUESTED denies;
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
REVIEWED_COMMIT_RE = re.compile(
    r"Reviewed[-\s]commit[:\s]+`?([0-9a-f]{7,40})`?", re.IGNORECASE
)
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


def latest_human_review_states(reviews):
    """Latest APPROVED/CHANGES_REQUESTED state per non-bot author.

    COMMENTED and PENDING never change an author's standing. GitHub marks a
    dismissed review by mutating its state to DISMISSED in place; handle a
    trailing DISMISSED entry too, so either payload shape clears standing.
    """
    states = {}
    for r in reviews:
        login = r.get("author", {}).get("login", "")
        if not login or is_bot_login(login):
            continue
        state = r.get("state", "")
        if state in ("APPROVED", "CHANGES_REQUESTED"):
            states[login] = state
        elif state == "DISMISSED":
            states.pop(login, None)
    return states


def classify_verdict_body(body, head_oid):
    """Classify one blanked, marker-bearing verdict body."""
    section = VERDICT_MARKER_RE.split(body, maxsplit=1)[1]
    # The verdict's own footer is the last "Reviewed commit:" line; earlier
    # occurrences may quote prior rounds. A format that prints the line
    # above the heading still gets a staleness check via the whole body.
    shas = REVIEWED_COMMIT_RE.findall(section) or REVIEWED_COMMIT_RE.findall(body)
    if shas and head_oid and not head_oid.startswith(shas[-1]):
        return "stale"
    # The headline (first non-empty line under the heading) outranks later
    # prose, so "Ready for merge --- the concern that this wasn't ready is
    # resolved" classifies by its headline rather than its narrative.
    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]
    headline = lines[0] if lines else ""
    for text in (headline, section):
        if NOT_CLEAN_VERDICT_RE.search(text):
            return "not-clean"
        if CLEAN_VERDICT_RE.search(text):
            return "clean"
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

    # CI first: never merge red or incomplete checks.
    status_rollup = pr_data.get("statusCheckRollup") or []
    # CheckRun entries carry conclusion/status; classic StatusContext
    # entries carry only state (FAILURE/ERROR/PENDING/EXPECTED/SUCCESS).
    failures = [
        check.get("name") or check.get("context") for check in status_rollup
        if check.get("conclusion") in BLOCKED_CI_CONCLUSIONS
        or check.get("status") in PENDING_CI_STATUSES
        or check.get("state") in BLOCKED_STATUS_STATES
    ]
    if failures:
        return deny(
            "Strict Merge Control Policy: Cannot merge with failing or "
            f"incomplete CI checks: {', '.join(failures)}. Never ignore red "
            "CI; wait for all checks to complete."
        )

    human_states = latest_human_review_states(reviews)
    blockers = [k for k, v in human_states.items() if v == "CHANGES_REQUESTED"]
    if blockers:
        return deny(
            "Strict Merge Control Policy: standing CHANGES_REQUESTED review "
            f"from {', '.join(sorted(blockers))}. Only that reviewer (or an "
            "explicit dismissal) can clear it -- a later bot verdict cannot."
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
            "work). Get a clean verdict from the review workflow, or a "
            "formal APPROVED review from a human."
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


def fetch_pr_data(cmd, cwd):
    """Resolve the merge target and fetch its state.

    Returns (pr_data, error_reason). Comments come from the paginated REST
    endpoint so a long thread cannot truncate away the latest verdict.
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
        view_args + ["--json", "url,reviews,statusCheckRollup,headRefOid"], cwd
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
    # --paginate with --jq emits one JSON array per page; merge them.
    comments = []
    decoder = json.JSONDecoder()
    text = comments_result.stdout.strip()
    pos = 0
    while pos < len(text):
        page, end = decoder.raw_decode(text, pos)
        comments.extend(page)
        pos = end
        while pos < len(text) and text[pos] in " \r\n":
            pos += 1
    pr_data["comments"] = comments
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
