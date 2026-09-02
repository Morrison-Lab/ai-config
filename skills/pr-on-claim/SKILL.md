---
name: pr-on-claim
description: "Open draft PR on claiming issue."
user-invocable: true
allowed-tools:
  - Bash
---

# /pr-on-claim — Open a draft PR immediately after claiming an issue

Operationalizes the strong form of the claim workflow: branch → empty commit → draft PR, before writing any code. An open PR is the strongest "in-flight" signal that work is happening on an issue.

## Usage

```
/pr-on-claim <issue#> [title-override]
```

**Arguments:**
- `<issue#>` (required): GitHub issue number to claim and open a PR for
- `[title-override]` (optional): Override the PR title (defaults to issue title)

## What it does

1. Fetch `origin/main` and check out a clean branch: `feat/<slug>` or `fix/<slug>` (inferred from issue title)
2. Create an empty commit with message: `"start: <issue title> (closes #<N>)"`
3. Push the branch with `-u origin HEAD`
4. Open a **draft PR** with:
   - Title: issue title (or override)
   - Body: `"Closes #<N>\n\nWIP — opened up front to claim the issue; implementing now."`
5. Post a claim comment on the issue, whose body is the claim line, a blank line, and the agent-disclosure marker every agent-posted comment carries (see [`disclose-agent-authorship`](../../shared/workflow/disclose-agent-authorship.md)).
   `\n` here is notation for a real newline, as in step 4 --- inside a bash double-quoted string those two characters stay two characters, so [`pr-on-claim.sh`](pr-on-claim.sh) writes the body with actual line breaks: `"Claude Code CLI (local session) is working on this — please hold off until I'm done.\n\n_Posted by Claude Code (AI agent) --- not written by a human._"`

## Why draft?

A draft PR doesn't trigger `@claude` review bot, so no review round is spent on an empty or half-finished diff.
When implementation is complete and checks pass, mark ready-for-review (`gh pr ready <N>`), then request the external reviewer in the same stride.

## Request reviewer before reporting status

Opening a PR or marking a draft ready can trigger the repo's own review workflow, but that does not summon Copilot automatically --- unless the repo's own ruleset does (see below).
If Copilot is a configured reviewer, request it immediately after `gh pr create` for a non-draft PR, or immediately after `gh pr ready` for a draft PR --- the `REQUEST_COPILOT_REVIEW` operation token (`tool-mappings.md`):

```bash
gh api -X POST "repos/<owner>/<repo>/pulls/<N>/requested_reviewers" \
  -f 'reviewers[]=copilot-pull-request-reviewer[bot]'   # REQUEST_COPILOT_REVIEW
gh pr view <N> --json reviewRequests,reviews
gh pr checks <N>
```

In a remote/web session without `gh`, use `mcp__github__request_copilot_review` instead.

**Some repos schedule Copilot automatically via a `copilot_code_review` ruleset rule** (`review_on_push: true`, optionally `review_draft_pull_requests: true`), which re-requests Copilot on every push --- see [`pr-on-claim`](../../shared/workflow/pr-on-claim.md) for how to read that off a repo's rulesets, and [`memories/gh-cli.md`](../../memories/gh-cli.md) for the case record.
Request explicitly anyway when you can't tell whether that applies, on any repo when a ready-for-review head shows no `copilot-pull-request-reviewer` check run about a minute after the push (the case [`memories/github-mcp-tools.md`](../../memories/github-mcp-tools.md) measures per push), and after a Rebut/Defer-only round that pushed nothing, per [`ardi`](../ardi/SKILL.md), since a completed run on the unchanged head requests nothing.
A duplicate request spends one call on a run that may only have been delayed.
That is the accepted risk, weighed against a round that never starts.

Verify the request landed before writing a status report: the POST response should include the reviewer, then a fresh read should show either a pending request or a new review/check from that reviewer on the current head.
If the request disappears with no current-head review, report that blocker and start the fallback; do not write "review owed" as a status item.

## Workflow order

1. _(Caller)_ Decide to work on an issue
2. _(This skill)_ Claim the issue and open the draft PR (branch + empty commit + PR + claim comment)
3. _(Caller)_ Implement code on the branch
4. _(Caller)_ Mark PR ready-for-review (`gh pr ready <N>`)
5. _(Caller)_ Request and verify the external reviewer before reporting status
6. _(Caller)_ Iterate ARDI until clean
7. _(Caller)_ Merge

## Related

- `@shared/workflow/pr-on-claim.md` — policy documentation
- `@shared/workflow/claim-pr.md` — claim-only (no PR)
- `/ardi` — review iteration loop
- `/gi` — grab issue (includes PR-on-claim)
- `/st` — start task (includes PR-on-claim)
