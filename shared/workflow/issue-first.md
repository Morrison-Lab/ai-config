When starting a **new** piece of work, go **issue-first**: before branching,
editing, or opening a PR, make sure a tracking issue exists. Search the tracker
first; if no open issue covers the task, **file one** (`gh issue create` /
`glab issue create`), then proceed. Never jump straight into a PR without a
tracking issue behind it.

The issue is the durable record of intent, scope, and "done" criteria --- it
gives reviewers context, lets the PR auto-close it via `Closes #N`, and keeps
the work discoverable even if the PR stalls. Skip only when the task is already
tracked by an open issue.

This rule settles *whether* something is tracked, not *where* it goes.
An item whose deliverable is a decision rather than a diff belongs on the
discussion board instead, per
[`choose-issue-or-discussion`](choose-issue-or-discussion.md) --- so read "file
one" here as "file one in the right venue", which for actionable work is the
tracker.

When the issue is a **bug report**, include a minimal reproducible example
(a reprex --- <https://reprex.tidyverse.org/>) whenever you can. A reprex is
what a maintainer needs to confirm and fix the bug, and it's what they'll ask
for anyway, so providing it up front saves a round trip. The `reprexes` skill
helps reduce the problem to a minimal, self-contained example.

When filing an issue that contains a list of independent subissues, file each
subissue as a child issue linked under the parent (GitHub sub-issues feature:
`mcp__github__sub_issue_write` in remote sessions, or `gh api` with the
sub-issues endpoint in local sessions).

**That splitting rule has teeth, and they are worth stating: a PR's
`Closes #N` closes the whole issue, including every item in it the PR never
addressed.**
Read as tidiness, the rule is easy to skip when the second item feels like a
footnote.
The actual consequence is that GitHub cannot partially close an issue, so the
residual items are not deferred and not reopened --- they are silently gone,
and nothing in the merge, the PR, or the closed issue reports that anything
was dropped.

It is worse than an ordinary lost to-do, because a closed issue is *evidence
that the work was handled*.
A later reader searching the tracker finds it closed and reasonably concludes
every item in it was dealt with, so the loss is not merely silent but
actively misleading.

So before writing `Closes #N`, re-read #N and confirm the diff covers all of
it.
When it doesn't, either split the remainder into its own issue first, or
reference the parent with `Refs #N`, which links without closing.

- **Do:** split at filing time, or at the latest before the closing PR merges.
- **Do:** use `Refs #N` when a PR advances an issue without completing it.
- **Don't:** let `Closes #N` ride on an issue whose scope is wider than the
  diff.

(Morrison-Lab/ai-config#847, 2026-07-29: an issue was filed carrying a
primary bug and a secondary note, and the PR fixing the first said
`Closes #847`.
The second item survived only because the maintainer asked about it before the
merge, which is not a mechanism; it was split into #852 and shipped as #853,
and both PRs merged within the following half hour.
The splitting rule directly above already existed and was simply not applied
when #847 was filed, which is the argument for stating its consequence rather
than only its instruction.)

## Deferring a request out of the current change is allowed, and the tracking issue is what allows it

The rule at the top governs work you are about to start.
Its mirror governs work you are declining to start now: a request that arrives
while a change is already in flight, and that would grow that change past what
it set out to do.
Such a request may be deferred, on your own judgment, **provided the deferred
item is filed as an issue in the same reply**.
The permission and the condition are one rule rather than two.
An untracked deferral is not a deferral, it is dropping the request in the
vocabulary of scope discipline.

**The requests this covers come from the user, which is what makes it worth
stating.**
A reviewer's finding already has a Defer disposition, per [`ardi`](ardi.md)'s
ARD step, and a request the user explicitly defers already routes to
[`defer-issue`](../../skills/defer-issue/SKILL.md).
Neither reaches the commonest case, where the user asks for something adjacent
mid-review and the standing instinct treats any direct request as
automatically in scope for whatever happens to be open.
A request can be genuinely wanted and genuinely out of scope for the current
PR at once, and saying so is a service rather than a refusal.

**It is a grant of latitude and not an instruction to defer.**
The default is unchanged: do what was asked.
What the grant removes is the bind a mid-flight request creates, where
responsiveness and scope discipline pull opposite ways and doing everything
asked is the only move that reads as cooperative.

**File the issue so it stands alone**, by this fragment's own standard.
The conversation that produced the request will not survive it, so an issue
reading "do the thing we discussed" defers nothing and only moves the loss
somewhere harder to notice.

**Say which parts you deferred and why, in the same reply.**
This is the near-miss, and it reads as compliance from the inside: three
things were asked, two were done, the reply describes the two, and nothing
states that a third existed.
A silent partial delivery is indistinguishable from having done the whole
thing, so the user finds out what was dropped only by rereading their own
request.
Name the deferred item, give the reason, and link the issue.

### The boundary with technical debt

[`dont-incur-technical-debt`](../principles/dont-incur-technical-debt.md) says
a filed issue records debt rather than paying it, and that a defect you have
already diagnosed inside your own diff is yours to fix now.
Nothing here softens that, and the two rules read as contradictory until the
boundary is drawn.

That fragment supplies the discriminator, so use its question:

> Does the diff I am about to push contain the thing I just diagnosed as
> wrong?

When it does, the request is not out of scope, it is the scope, and no issue
number buys it out.
This rule covers work **adjacent to** the diff instead: pre-existing prose the
change never authored, a broader sweep the change happens to touch one
instance of, a follow-on improvement that would be welcome later.

- **Do:** defer an out-of-scope request on your own judgment, and file the
  tracking issue in the same reply that declines it.
- **Do:** name each deferred item, its reason, and its issue, so a partial
  delivery is visible as partial.
- **Do:** ask the technical-debt question first, and fix rather than defer
  whatever the current diff itself introduced.
- **Don't:** treat a request as in scope merely because the user made it
  directly.
- **Don't:** defer without filing --- an untracked deferral is a dropped
  request, and it reads as scope discipline while being the opposite.
- **Don't:** read this as a reason to defer; the default is still to do what
  was asked.

(Directive from the user, 2026-08-09: "cai: it's ok to defer out-of-scope
requests from me; just make sure to track them in issues".
It came mid-review on `UCD-SERG/serocalculator#654`, a Quarto
methodology-vignette formalization, where adjacent requests kept arriving in
quick succession --- convert propositions to theorems, sweep the chapter for
overclaims, reformat multi-equality display equations --- several of them
touching prose the PR had never authored.)
