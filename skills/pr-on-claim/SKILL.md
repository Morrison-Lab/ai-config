---
name: pr-on-claim
description: "Open a draft PR immediately after claiming an issue — branch, empty commit, draft PR, claim comment — before writing any code. Use when asked to 'pr-on-claim', 'open a draft PR for this issue', or after claiming an issue you are about to implement."
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
5. Post a claim comment on the issue: `"Claude Code CLI (local session) is working on this — paws off until I'm done."`

## Why draft?

A draft PR doesn't trigger `@claude` review bot, so no review round is spent on an empty or half-finished diff.
When implementation is complete and checks pass, mark ready-for-review (`gh pr ready <N>`), then request the external reviewer in the same stride.

## Request reviewer before reporting status

Opening a PR or marking a draft ready can trigger this repo's own review workflow, but that does not summon Copilot.
If Copilot is a configured reviewer, request it immediately after `gh pr create` for a non-draft PR, or immediately after `gh pr ready` for a draft PR:

```bash
gh api -X POST "repos/<owner>/<repo>/pulls/<N>/requested_reviewers" \
  -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
gh pr view <N> --json reviewRequests
```

Verify the request landed before writing a status report.
If the request is blocked, report that blocker and start the fallback; do not write "review owed" as a status item.

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
