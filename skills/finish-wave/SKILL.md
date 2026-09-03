---
name: finish-wave
description: "Finish the current wave; start no new one."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# finish-wave --- cap the run at the wave already in flight

Cap an orchestration run at its current wave.
Drive everything already in flight to a terminal state, grab nothing new, then hand the decision about a next wave back to the user.

The cap bounds *issue grabs*, not activity.
[`gii`](../gii/SKILL.md)'s wave boundary defines a wave as the issues taken from the backlog plus the PRs that ship them, so the work that finishes those PRs runs inside the cap rather than against it.

## When this fires

- "finish the current wave but don't start a new one", "fw"
- "finish the wave", "no new wave", "last wave", "wind down after this one"
- "finish what's in flight, then stop"
- A [`gii`](../gii/SKILL.md) or [`gia`](../gia/SKILL.md) run reaching its own wave boundary, where this skill is the procedure for the hold

## Procedure

### 1. Derive the wave, don't enumerate it

Take the wave from a live query at every check-in, rather than freezing a list of numbers at the moment the cap arrives.
A PR opened minutes ago, or one the review bot pushed to, belongs to the wave and never entered any list written earlier ([`derive-dont-enumerate`](../../shared/workflow/derive-dont-enumerate.md)).

```bash
gh pr list --state open --author @me --json number,title,url,headRefName
gh issue list --state open --assignee @me --json number,title,url
```

In a remote session without `gh` on `PATH`, substitute the GitHub MCP equivalents from [`tool-mappings.md`](../../tool-mappings.md).

- **Do:** re-run the queries each time you report the wave's state.
- **Don't:** work from a list of PR numbers captured when the cap was issued.

### 2. Hold every grab

No new issue is claimed, no new branch is cut off the backlog, and no further `gi` / `gii` / `gip` iteration starts.
An issue already claimed before the cap stays in the wave and gets finished.

- **Do:** finish an issue claimed before the cap arrived.
- **Don't:** grab one more issue because it is small, adjacent, or already triaged.

### 3. Drive what is in flight to a terminal state

Run [`ardi`](../ardi/SKILL.md) on each open PR in the wave until its verdict is clean, and merge only where a grant such as [`mwc`](../mwc/SKILL.md) already applies.
A PR still in CI or review is not a finished wave, so the check-in loop that drives it to green continues uninterrupted.
Where an item is blocked, surface it and keep driving the rest ([`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md)).

- **Do:** keep the monitoring loop running until every wave item is merged, closed, or explicitly escalated.
- **Don't:** read the cap as permission to stop babysitting the wave's open PRs.

### 4. Know what still runs inside the cap

Four kinds of work are implied by the current wave rather than being a new one:

- A **UMS pass and the PR it opens**, owed at the wave's clean verdicts and merges --- see [`gii`](../gii/SKILL.md)'s "A UMS pass is not a new wave" paragraph and [`run-ums-proactively`](../../shared/workflow/run-ums-proactively.md).
- A **fix for a defect inside the wave's own diff**, which stays yours to fix now ([`dont-incur-technical-debt`](../../shared/principles/dont-incur-technical-debt.md)).
- A **tracking issue filed** for anything noticed or deferred, since filing is not grabbing ([`issue-first`](../../shared/workflow/issue-first.md)).
- **Syncing, conflict resolution, and re-review** on a wave branch whose base moved.

- **Do:** run the owed UMS pass and open its PR under the cap.
- **Don't:** count a UMS PR, a follow-up issue, or a sync as a grab from the backlog.

### 5. Report the boundary, then stop and ask

Report the wave as a table, each PR and issue linked per `CLAUDE.md`'s "Link PRs in tables" convention, with what was deferred and the issue that tracks it.
Then stop and ask whether to continue into the next wave or archive the session, giving a recommendation either way.
End with the stopping-point declaration ([`flag-session-boundaries`](../../shared/workflow/flag-session-boundaries.md)), which stays non-clean while any wave PR is unmerged.

- **Do:** name the recommendation, then let the user decide the next wave.
- **Don't:** ask "what would you like next?" in place of the recommendation, or start the next wave on your own once the current one is finished.

## Scope and limits

The cap is session-scoped and lasts until the user lifts it by authorizing a next wave.
It grants nothing: merge authority still comes from [`mwc`](../mwc/SKILL.md) alone, and question-suppression still comes from [`away`](../away/SKILL.md) alone.
It is not a stop order either --- "stop" or "that's enough" ends the loop where it stands, leaving PRs mid-flight, while this skill finishes them first.

## Relationship to other skills

- **[`gii`](../gii/SKILL.md)** --- owns the wave boundary this skill executes, including the default 5-issue max and the "A UMS pass is not a new wave" rule.
- **[`gia`](../gia/SKILL.md)** --- honors the same boundary in its Phase 2.
  Invoke this skill for the hold rather than restating it.
- **[`gip`](../grab-issues-in-parallel/SKILL.md)** --- the parallel grabber the cap also halts.
- **[`ardi`](../ardi/SKILL.md)** --- the loop that drives each wave PR to clean while the cap holds.
- **[`ums`](../ums/SKILL.md)** --- runs inside the cap, at the wave's clean verdicts and merges.
- **[`wrap-up`](../wrap-up/SKILL.md)** --- the end-of-session sweep to run once the wave has closed and the user chooses to stop.
- **[`away`](../away/SKILL.md)**, **[`mwc`](../mwc/SKILL.md)** --- separate session-scoped grants this skill neither extends nor revokes.

## Anti-patterns

- ❌ Reading the cap as "open no more PRs", which strands the wave's learnings by holding back the UMS PR.
- ❌ Freezing the wave as a list of numbers instead of re-deriving it each check-in.
- ❌ Declaring the wave finished while one of its PRs is still in CI or review.
- ❌ Starting the next wave on your own judgment once the current one is fully finished.
- ❌ Treating the cap as a merge grant, an `away` grant, or a reason to stop monitoring.
