# GI — Grab Issue

Pick the highest-priority open issue, implement it, open an MR/PR, and drive it to a clean review verdict via ARDI.

Commands below are annotated with their abstract operation token (e.g. `LIST_ISSUES`, `CREATE_PR`) — resolve to your model’s tool via [`tool-mappings.md`](../../tool-mappings.md) instead of the `gh` command shown if this session doesn’t have `gh`.

## When this fires

- User says “gi”, “grab an issue”, “pick up the next issue”
- User says “what should I work on next?”
- User says “work on the top issue”, “grab the highest-priority one”

## Procedure

### 1. List open issues

``` bash
# GitHub
gh issue list --state open --limit 20 --json number,title,labels,assignees,createdAt | cat   # LIST_ISSUES

# GitLab
glab issue list --per-page=20 2>&1 | cat
```

### 2. Triage / prioritize

Scan the issue list and rank by priority. Use these signals (in order):

| Signal | Weight |
|----|----|
| Explicit priority label (`P0`, `critical`, `high-priority`, `urgent`) | Highest |
| Blocking other work (mentioned in other issues/MRs) | High |
| Bug vs feature (bugs first, generally) | Medium |
| Age (older unresolved issues accumulate cost) | Medium |
| Size/complexity (prefer issues you can complete in one session) | Tie-breaker |
| Internal infrastructure vs feature (infra slightly preferred — see [`pr-prioritization`](../../shared/workflow/pr-prioritization.md)) | Tie-breaker |
| Already assigned to someone else | **Skip** |
| Issue comment says “Working on this” | **Skip** |
| Open PR already exists for the issue | **Skip** |

**Re-triage if helpful:** If labels are stale, missing, or inconsistent, briefly suggest re-labeling to the user before proceeding. Don’t unilaterally relabel without asking — but do flag it:

> “Issues \#4 and \#7 both look high-priority but neither is labeled. Want me to label them before picking one, or just grab \#4 (older, looks like a bug)?”

### 3. Confirm selection with user

Present the top 1–3 candidates with a one-line summary each. Let the user pick, or proceed with \#1 if they say “just go”:

> | \#  | Issue                                    | Why                  |
> |-----|------------------------------------------|----------------------|
> | 1   | \#12 — Fix auth timeout on slow networks | Bug, P1, oldest      |
> | 2   | \#8 — Add retry logic to API client      | Feature, blocks \#12 |
> | 3   | \#15 — Update docs for v3 migration      | Docs, easy win       |
>
> I’d grab **\#12** — want me to proceed, or pick a different one?

If the user already specified an issue (“gi \#12”), skip this step.

### 4. Check the issue isn’t already in-flight

Before claiming or branching, confirm no other session is already on this issue. Two signals must **both** be clear (`gh issue list` in step 1 returns titles, labels, and assignees but neither comment text nor linked PRs, so check both explicitly here).

**(1) No “Working on this” claim in the most recent comment:**

``` bash
# GitHub — read the issue's latest comment:
gh issue view <N> --json comments --jq '.comments | last | .body' | cat   # READ_ISSUE_COMMENTS
```

If it contains “Working on this” / “paws off” (or an equivalent claim), skip the issue.

**(2) No open PR already references the issue:**

``` bash
# GitHub — list open PRs and scan for any whose title or branch references this issue:
gh pr list --state open --json number,title,headRefName | cat   # LIST_PRS
# Authoritative — the issue's cross-referenced open PRs via the REST timeline API.
# (gh issue view --json has no timelineItems field; in the timeline, source.type is
#  always "issue", so a PR is one whose source.issue.pull_request is non-null. The
#  state filter keeps only open PRs — merged/closed siblings aren't active competitors.
#  --paginate walks every page so a cross-reference past the first 30 events isn't missed.)
gh api --paginate repos/<owner>/<repo>/issues/<N>/timeline \
  --jq '.[] | select(.event == "cross-referenced") | .source.issue | select(.pull_request != null) | select(.state == "open") | "#\(.number) \(.title)"' | cat   # ISSUE_LINKED_PRS
```

If an open PR already exists for the issue: - **Don’t open a competing PR.** The issue is already being worked. - Skip it and grab the next unblocked issue instead. - Or, if the existing PR is stalled/abandoned and you’re taking it over, check it out (use the existing PR branch), claim the PR, and ARDI it rather than starting fresh.

### 5. Check history

Before implementing, invoke the `check-history` skill to review merged MRs/PRs that touched the same area. Don’t undo past progress.

### 6. Claim the issue

``` bash
# GitHub
gh issue comment <N> --body "Claude Code CLI (local session) is working on this — paws off until I'm done."   # COMMENT_ISSUE

# GitLab
glab issue note <N> --message "Claude Code CLI (local session) is working on this — paws off until I'm done."
```

### 7. Create a branch

``` bash
git fetch origin main                    # FETCH
git checkout -b fix/<slug> origin/main   # CREATE_BRANCH — or feat/<slug>, docs/<slug>
```

Branch naming: - Bug fix → `fix/<issue-slug>` - Feature → `feat/<issue-slug>` - Docs → `docs/<issue-slug>` - Refactor → `refactor/<issue-slug>`

### 8. Open the PR now — draft, from an empty commit

Open the PR **immediately, before implementing**, so the open-PR signal that step 4 relies on fires right away and other sessions can see the issue is being worked (see [`pr-on-claim`](../../shared/workflow/pr-on-claim.md)). Give the branch a diff with an empty commit, push, and open a **draft** PR:

``` bash
git commit --allow-empty -m "start: <issue title> (closes #<N>)"   # COMMIT
git push -u origin fix/<slug>                                      # PUSH

# GitHub — draft PR
gh pr create --draft --title "<title>" --body "Closes #<N>

WIP — opened up front to claim the issue; implementing now."   # CREATE_PR

# GitLab — draft MR
glab mr create --draft --title "<title>" --description "Closes #<N>

WIP — opened up front to claim the issue; implementing now." --assignee <your-gitlab-username>  # default: demorrison
```

Keep it a draft: a draft doesn’t trigger the `@claude` review bot, so no review round is wasted on an empty diff. Include `Closes #N` to auto-close the issue on merge.

### 9. Implement

- Read the issue description carefully — understand “done” criteria
- Make the changes (code, tests, docs as needed)
- Run the repo’s standard checks (lint, test, build) before committing Prefer the same commands CI runs. If the repo has both subpackage tests and a root-level lint step, run both
- Commit with a message referencing the issue: `fix: handle auth timeout on slow networks (closes #12)`

### 10. Push and mark the PR ready for review

``` bash
git push origin fix/<slug>   # PUSH — push the implementation onto the draft PR from step 8
gh pr ready <N>              # MARK_PR_READY — GitHub, flip draft → ready, which kicks off review
# GitLab: glab mr update <N> --ready
```

The PR already exists (step 8), so there’s nothing new to create — pushing the implementation and marking it ready for review is what starts ARDI.

### 11. ARDI to clean

Invoke the `ardi` skill on the MR/PR. Drive it through review rounds until the verdict is clean (zero findings).

### 12. Report

When ARDI completes clean, report: - Issue number + link - MR/PR number + link - Round count - Any deferred items (with follow-up issue links)

Don’t merge unless asked. When you do merge, see [§Concurrent-session collisions](#concurrent-session-collisions) first.

## Concurrent-session collisions

This repo often has many sessions running at once, so another session can open a PR that closes “your” issue *after* you started — the claim comment and the opening PR-list scan won’t catch a PR that didn’t exist yet. Re-check right before merging (and treat an unexpected merge conflict as a signal):

- Search open *and merged* PRs for one that already references `Closes #<N>` for your issue (`SEARCH_PRS` — `gh pr list --state all --search "closes #<N>"` / the GitHub `mcp__github__search_pull_requests` tool) — the default `gh pr list` lists only open PRs and would miss a sibling that already merged and closed the issue, the case that matters most. If the issue is already closed, don’t merge a now-redundant PR blindly.
- If a sibling PR landed first, sync `main` into your branch and **read the resulting diff** — keep only the parts the sibling missed, drop the duplicates, and reframe the PR (it no longer `Closes #<N>`; it’s a follow-up).

## Delegating sidecar work

While implementing (step 9), delegate independent sidecar work to a subagent via the `Agent` tool when it won’t block the critical path — e.g. verifying a claim from the issue description, drafting a test fixture, or investigating a tangential failure surfaced along the way. Keep claiming, branching, opening the draft PR, and the ARDI loop itself on the main thread.

For a judgment-heavy sidecar task (a subtle bug hunt, an architecturally significant design call), override the subagent’s model to a stronger tier via the `Agent` tool’s `model` parameter (e.g. `model: 'opus'`) rather than the session default. Symmetrically, drop to a cheaper/faster tier (`model: 'fable'` or `'haiku'`) for a mechanical, bounded sidecar task instead of leaving it at the session default — see [`select-model`](../../skills/select-model/SKILL.llms.md)’s decision tree for both directions. For a heavy fan-out read/draft/verify pass, prefer a separately-billed provider (e.g. the `codex` CLI) first when available, to conserve Claude/Agent-tool budget — see [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md).

## Handling blocked issues

If during implementation you discover the issue is blocked (missing dependency, needs design decision, upstream bug):

1.  Post a comment on the issue explaining the blocker
2.  Label it `blocked` if the repo uses that label
3.  Report to the user and offer to pick the next issue instead

## Relationship to other skills

- **`check-history`** — invoked in step 5 to avoid undoing past work
- **`ardi`** — invoked in step 11 to drive the MR/PR to clean
- **`claim-pr`** — the issue claim in step 6 follows the same pattern
- **`pr-on-claim`** — the rule behind step 8: open the draft PR up front so the work is visible to other sessions before you implement
- **`split-concerns`** — if the implementation grows too large, offer to split
- **`defer-issue`** — if sub-tasks emerge during implementation, defer them
- **`select-model`** — decision tree for picking a subagent’s model tier when delegating sidecar work (see Delegating sidecar work)
- **`delegate-to-codex`** — when a sidecar task is a heavy fan-out read/draft/verify pass and codex is available, prefer it first

## Anti-patterns

- ❌ Grabbing an issue already assigned to someone else
- ❌ Starting implementation without checking history
- ❌ Opening an MR without running the repo’s standard checks first
- ❌ Picking a huge issue that can’t be completed in one session without discussing scope with the user first
- ❌ Implementing without understanding “done” criteria from the issue
- ❌ Opening the PR only after implementing — open a draft PR up front (step 8) so the work is visible and a parallel session doesn’t grab the same issue
- ❌ Forgetting `Closes #N` in the MR/PR description
- ❌ Merging without re-checking that a concurrent session’s PR hasn’t already closed the issue (resolve a surprise merge conflict by reading the diff, not blindly)

Back to top
