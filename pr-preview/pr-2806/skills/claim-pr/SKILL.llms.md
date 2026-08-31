# claim-pr

Before working a PR/MR or issue — fetching its branch, editing, or running `@claude` review cycles — post a brief comment so other people and the `@claude` CI bot know not to start a conflicting parallel session. **Resolve** (or post a closing comment on) the claim when the session ends. Posting a review is in scope too; the firing list below includes it.

## When this fires

- Before any **write** session on a PR/issue: fix, implement, debug, refactor, review-and-edit, or an iterative `@claude review` loop that pushes commits.
- Before any **posted review** of a PR: adversarial review, code-review, self-review fallback, or any other pass that will post a SHA-stamped review comment. Post the claim **before** dispatching the reviewer or fetching the branch for review, not after the comment lands. Unclaim-when-the-review-lands applies only to a **review-only** pass. A session that is also driving the branch (implementing, ARDI) keeps its write claim until that work ends.
- Triggered by a prompt referencing a PR/issue by `#N` or URL that asks you to *change* something, **or** to review it and post the verdict.

It does **NOT** fire for read-only inspection that will not post — “show me PR \#X”, “what’s the status of \#Y”, “explain the diff on \#Z”. Those don’t risk a parallel session. A persistent watch after a review has landed is not a standing claim; re-claim only when a new review round starts. Do not claim every open PR at the start of a sweep — claim the one whose review is starting, unclaim a **review-only** pass when that review lands, then claim the next. A write/ARDI sweep keeps its write claim until that work ends.

## Claim (start of session)

First check whether you’ve already claimed it — if your (Claude’s) most recent comment on the thread already says you’re working on it **and the claim is still live** (under 2 hours since the most recent push or comment on the thread — see “Claim expiration” below), **skip** re-posting. Past 2 hours the claim has expired; re-post it before resuming.

### GitHub

``` bash
gh pr comment <N> --body "Claude Code CLI (local session) is working on this — please hold off on pushing to this branch until I'm done.

_Posted by Claude Code (AI agent) --- not written by a human._"      # COMMENT_PR
gh issue comment <N> --body "Claude Code CLI (local session) is working on this — please hold off until I'm done.

_Posted by Claude Code (AI agent) --- not written by a human._"   # COMMENT_ISSUE
```

A review-only session uses the same `hold off` invariant so existing detectors still match, and names the review so authors know when they can push again:

``` bash
gh pr comment <N> --body "<agent> is reviewing this PR --- please hold off on pushing to this branch until the review comment lands.

_Posted by <agent> (AI agent) --- not written by a human._"      # COMMENT_PR
```

Unclaim that review-only pass when the SHA-stamped review comment is posted (see Unclaim below), even if a watch on the PR continues. Do not unclaim a still-driving write claim just because a review comment landed in the same session.

(`COMMENT_PR` / `COMMENT_ISSUE` are abstract operation tokens — resolve to your model’s tool via [`tool-mappings.md`](../../tool-mappings.md).)

### GitLab

On GitLab, post the claim as a **resolvable discussion** (not a plain note) so it can be resolved later:

``` bash
glab mr note create <N> --message "Claude Code CLI (local session) is working on this — please hold off on pushing to this branch until I'm done.

_Posted by Claude Code (AI agent) --- not written by a human._"
```

A review-only session on GitLab uses the same resolvable discussion, with review-shaped wording:

``` bash
glab mr note create <N> --message "<agent> is reviewing this MR --- please hold off on pushing to this branch until the review comment lands.

_Posted by <agent> (AI agent) --- not written by a human._"
```

> GitLab MR notes are resolvable discussions by default.

Then proceed with the work.

## Claim expiration

A claim is **live for 2 hours from the most recent push or comment** on the PR/issue, and **expired** past that — in both directions:

- Your own expired claim doesn’t cover resuming work: post a fresh claim comment first.
- Another session’s expired claim doesn’t block you: post your own claim (never a silent takeover), then run the branch-head check in the Notes below before your first push.

Check staleness with one read.

### GitHub — read the last-activity timestamp

``` bash
gh pr view <N> --json updatedAt --jq .updatedAt        # VIEW_PR
gh issue view <N> --json updatedAt --jq .updatedAt     # VIEW_ISSUE
```

### GitLab — read the last-activity timestamp

``` bash
glab api "projects/<PROJECT_ID>/merge_requests/<MR_IID>" | jq -r .updated_at
glab api "projects/<PROJECT_ID>/issues/<ISSUE_IID>" | jq -r .updated_at
```

On both platforms the updated-at field moves on more events than pushes and comments (labels, reviews, body edits), so it only ever over-approximates freshness: a stale verdict from it is definitive, and a borderline-fresh one defaults to respecting the claim — the safe direction. The full statement of the convention lives in [`claim-pr`](../../shared/workflow/claim-pr.md).

## Unclaim (end of session)

After the work is done (MR merged, issue closed) or paused, **resolve the claim discussion thread** so it doesn’t clutter the MR as an open thread.

### GitLab — resolve the discussion

``` bash
# 1. Find the discussion ID containing the claim note
DISCUSSION_ID=$(glab api "projects/<PROJECT_ID>/merge_requests/<MR_IID>/discussions?per_page=100" \
  | python3 -c "
import json, sys
for d in json.load(sys.stdin):
    for n in d.get('notes', []):
        body = n.get('body', '').lower()
        # Both wordings: claims posted before 2026-08-24 say 'paws off'.
        # A RELEASE is excluded first -- the retired release note
        # '... done --- paws off released.' contains 'paws off', so a claim-only
        # test resolves the release's thread instead of the claim's.
        is_release = any(t in body for t in
                         ('unclaim', 'released', 'pr is free', 'now mergeable'))
        is_claim = (any(t in body for t in ('hold off', 'paws off', 'back off'))
                    and not is_release)
        if is_claim and not n.get('resolved'):
            print(d['id']); break
    else: continue
    break
")

# 2. Resolve it
glab api --method PUT \
  "projects/<PROJECT_ID>/merge_requests/<MR_IID>/discussions/${DISCUSSION_ID}" \
  -f "resolved=true"
```

A review-only unclaim on GitLab is this same resolve step. Do not post a second note. An unresolved `hold off` discussion stays a live claim.

### GitHub — post a closing comment

``` bash
gh pr comment <N> --body "Done with my local session — unclaiming.

_Posted by Claude Code (AI agent) --- not written by a human._"      # COMMENT_PR
gh issue comment <N> --body "Done with my local session — unclaiming.

_Posted by Claude Code (AI agent) --- not written by a human._"   # COMMENT_ISSUE
```

After a **review-only** posted review on GitHub, unclaim that pass as soon as the SHA-stamped review comment lands (the author needs the thread free to address findings). The closing comment’s body must include `unclaiming` so claim detectors treat it as a release.

``` bash
gh pr comment <N> --body "Review posted --- unclaiming.

_Posted by Claude Code (AI agent) --- not written by a human._"      # COMMENT_PR
```

## Proactive hook compliance

Active hooks guard forge comments and PR/issue lifecycles (see [`memories/hooks.md`](../../memories/hooks.md)): - **`require-gh-repo-flag.py`**: Always supply `-R <owner>/<repo>` on mutating `gh` calls (`gh pr comment -R ...`, `gh issue comment -R ...`). - **`require-agent-disclosure.py`**: Every claim, update, or unclaim comment must include the disclosure trailer `_Posted by <Agent Name> (AI agent) --- not written by a human._` on its own line after a blank line. Never use the robot emoji. - **`warn-pr-create-without-dupe-check.py` & `warn-dupe-check-chained-to-create.py`**: When opening an immediate PR under [`pr-on-claim`](../../shared/workflow/pr-on-claim.md), search for existing PRs (`gh pr list --state all --search "<keywords>"`) in a separate tool call before creating the PR. - **`flag-uncounted-comment-claims.py`**: When referencing file lists or counts in comments, ensure deriving commands (`grep -c`, `wc -l`) ran in the session.

## Notes

- If the user explicitly says to contribute to a specific existing PR, keep your changes on that PR’s current head branch and push there; do not open a sibling PR unless they ask to supersede it. If the documented push-scope exception applies (e.g., remote session `HTTP 403` when pushing to that branch), open an incremental cross-fork PR stacked on the existing PR branch instead of superseding it.
- **Claim an issue you just filed and will implement now, too.** Filing an issue then starting work on it yourself is still a write session. Post the claim (or open and link the PR with `Closes #N`) *promptly* — a parallel issues-sweep session can grab the freshly-filed issue and build a duplicate before your PR shows up. (This exact collision produced a duplicate PR in one session; the claim, or a fast linked PR, makes the sweep skip it. The reciprocal check is `check-history` step 0 — look for an already-open PR before implementing.) The strongest form of this is to **open the PR immediately** — before implementing, from an empty commit, as a draft — so the open-PR signal fires right away; see [`pr-on-claim`](../../shared/workflow/pr-on-claim.md), which `gi`/`gii`/`gip`/`st` operationalize.
- If `@claude` agent runs are in flight on the branch, wait for them before pushing or polling — don’t edit while the bot is mid-session.
- **Detecting an already-active parallel session** (so you don’t collide): before pushing a fix to a PR you’re driving (especially in a long ARDI watch loop), re-fetch and check whether the branch HEAD has advanced **past your last commit**. New commit SHAs you didn’t push + review workflows actively re-running = another session (or the author) is driving that branch right now. Back off: do **not** push. Surface the fix to the user and offer to apply it, or hand it to the active session — and wait for an explicit “you take over” before resuming pushes. (Seen repeatedly on rme \#772 and \#706, where another session was substantially reworking the branch — even adding new content — while a watch session held a one-line diff.)
- This is the claim ritual referenced by `ardi` (step 1; aka `iterate`) and `ardia` (aka `iterate-all`); when those run, they cover the claim for you.
- On GitLab, **always prefer resolving** the discussion over posting a second “unclaim” comment — it keeps the MR thread clean and signals completion without adding noise.

Back to top
