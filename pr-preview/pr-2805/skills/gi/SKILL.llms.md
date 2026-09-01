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

### 2. Triage, label, and prioritize

While surveying open issues to select the top candidate, inspect candidate issues and apply triage labels to any that are unlabeled or undertriaged.

**Apply triage labels:**

1.  **Check repo taxonomy:** Use existing labels on the repository (check `gh label list` / `glab label list` if unsure) rather than inventing new ones.
2.  **Classify each candidate:**
    - **Type:** `bug`, `enhancement`, `documentation`, `maintenance` / `refactor` / `chore` (match repo conventions).
    - **Priority:** `high-priority`, `low-priority`, `P0` / `P1` / `P2` if the repo uses explicit priority labels.
    - **Status:** `blocked`, `duplicate`, `invalid`, `wontfix` if applicable.
3.  **Add labels to inspected issues:**

``` bash
# GitHub
gh issue edit <N> --add-label "<label1>,<label2>"   # LABEL_ISSUE

# GitLab
glab issue update <N> --label "<label1>,<label2>"
```

`gh issue edit --add-label` is additive and preserves existing labels.

**Rank by priority:**

Scan the triaged issues and rank by priority. Use these signals (in order):

| Signal | Weight |
|----|----|
| Explicit priority label (`P0`, `critical`, `high-priority`, `urgent`) | Highest |
| Blocking other work (mentioned in other issues/MRs) | High |
| Bug vs feature (bugs first, generally) | Medium |
| Age (older unresolved issues accumulate cost) | Medium |
| Size/complexity (prefer issues you can complete in one session) | Tie-breaker |
| Internal infrastructure vs feature (infra slightly preferred — see [`pr-prioritization`](../../shared/workflow/pr-prioritization.md)) | Tie-breaker |
| Already assigned to someone else | **Skip** |
| Issue comment says “Working on this” (and the claim is live — under 2 h old) | **Skip** |
| Open PR already exists for the issue | **Skip** |

### 3. Select top issue automatically

Pick the highest-priority issue automatically based on the triage signals in step 2 (unless the user explicitly specified an issue or candidate preference). State which issue was selected and why, then proceed directly to check in-flight status and implementation without pausing for user confirmation.

Do not describe the issue as “in progress” or say that implementation has started until steps 4, 6, 7, and 8 have completed: the live claim, isolated branch/worktree, and draft PR are the observable start of work. Investigation or triage alone is preparatory work, not an active implementation.

### 4. Check the issue isn’t already in-flight

Before claiming or branching, confirm no other session is already on this issue. Two signals must **both** be clear (`gh issue list` in step 1 returns titles, labels, and assignees but neither comment text nor linked PRs, so check both explicitly here).

**(1) No live “Working on this” claim on the issue:**

``` bash
# GitHub -- read the claim/release exchange, not just the newest comment:
gh issue view <N> --json comments \
  --jq '[.comments[] | select(.body | test("hold off|paws off|back off|unclaim|released|PR is free|now mergeable"; "i"))] | last | "\(.createdAt) \(.author.login): \(.body)"'   # READ_ISSUE_COMMENTS
gh issue view <N> --json updatedAt --jq .updatedAt   # VIEW_ISSUE -- latest activity
```

**Reading only `.comments | last` is the bug this replaces.** A claim is live for two hours from the most recent *activity*, so any unrelated comment posted after it — a status note, a bot’s build result, a question — becomes the last comment while the claim is still binding. The claim then goes invisible and this check reports the issue free, which is the parallel-session collision the whole convention exists to prevent. Filter to the exchange and take the last member of *that*.

**Both timestamps are needed, which is why the second command is there.** The claim’s own `createdAt` says when it was made; the issue’s `updatedAt` says when the thread last saw activity, and the 2-hour rule expires on *activity*, not on the claim’s age. A day-old claim followed by a comment thirty minutes ago is **live**; the same claim with nothing after it is **expired**. Reading only the claim’s body cannot tell those apart, so it cannot decide the question the step is asking.

Match the two-word invariant `hold off`, or either retired wording `paws off` / `back off`, case-insensitively — then **exclude the comment if it also carries a release term** (`unclaim|released|PR is free|now mergeable`), because the retired release wording `... done --- paws off released.` contains `paws off` and would otherwise read as a live claim. See [`claim-pr`](../../shared/workflow/claim-pr.md)’s “Match the two-word invariant”. If a live claim stands, skip the issue — unless the claim has expired: no push or comment on the issue in over 2 hours, per [`claim-pr`](../../shared/workflow/claim-pr.md)’s expiration rule. An expired claim is taken over by posting your own claim comment, never silently.

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

### 5. Check history, peers, and research DRW

Before implementing, invoke the `check-history` skill to review merged MRs/PRs that touched the same area so you don’t undo past progress. Perform a research step to check whether the functionality or helper already exists (DRW) in our own repos or upstream ecosystems before writing custom code, following [`prefer-upstream`](../../skills/prefer-upstream/SKILL.llms.md) and [`dont-reinvent-wheel`](../../shared/principles/dont-reinvent-wheel.md). If the issue is a new feature or architectural change, also consider running `scout-peers` to see how other comparable projects solved it, ensuring we don’t reinvent the wheel. (Do NOT run `opposition-research` / `oppo` here; `oppo` mines community demand to decide *what* to build and feeds the issue tracker, while `scout-peers` checks *how* others built it once you’ve already grabbed an issue).

### 6. Claim the issue

``` bash
# GitHub
gh issue comment <N> --body "Claude Code CLI (local session) is working on this — please hold off until I'm done.

_Posted by Claude Code (AI agent) --- not written by a human._"   # COMMENT_ISSUE

# GitLab
glab issue note <N> --message "Claude Code CLI (local session) is working on this — please hold off until I'm done.

_Posted by Claude Code (AI agent) --- not written by a human._"
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

WIP — opened up front to claim the issue; implementing now." --assignee <your-gitlab-username>  # default: <user>
```

Keep it a draft: a draft doesn’t trigger the `@claude` review bot, so no review round is wasted on an empty diff. Include `Closes #N` to auto-close the issue on merge **only when this PR will finish the issue**. If a later comment splits the issue into independent cases and this PR ships only one, file the leftover as its own issue **before merge** and rewrite the PR body so it does not `Closes` the parent (link both: this PR for the shipped slice, the new issue for the rest). Closing the parent on a partial ship drops the deferred half from the tracker ([gha#373](https://github.com/Morrison-Lab/gha/issues/373) / [\#516](https://github.com/Morrison-Lab/gha/pull/516) / [\#517](https://github.com/Morrison-Lab/gha/issues/517)).

### 9. Implement

- Read the issue description carefully — understand “done” criteria
- Research before writing code: verify that no standard library, upstream package, or lab repo helper already provides what you are about to write (DRW). If custom implementation is needed, record the search and why existing options were unfit
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
- **`prefer-upstream`** — search existing packages, standard libraries, and lab repos before writing custom code to avoid reinventing the wheel
- **`scout-peers`** — suggested in step 5 to check how peers solved a problem so you don’t reinvent the wheel (distinct from `oppo`, which finds *what* to build)
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
- ❌ Hand-rolling custom code without researching existing packaged or shared solutions first (violating DRW)
- ❌ Opening an MR without running the repo’s standard checks first
- ❌ Picking a huge issue that can’t be completed in one session without discussing scope with the user first
- ❌ Implementing without understanding “done” criteria from the issue
- ❌ Skipping triage labeling on candidate issues — apply classification labels to candidate issues inspected during triage so the backlog stays organized
- ❌ Opening the PR only after implementing — open a draft PR up front (step 8) so the work is visible and a parallel session doesn’t grab the same issue
- ❌ Forgetting `Closes #N` in the MR/PR description
- ❌ Merging without re-checking that a concurrent session’s PR hasn’t already closed the issue (resolve a surprise merge conflict by reading the diff, not blindly)

Back to top
