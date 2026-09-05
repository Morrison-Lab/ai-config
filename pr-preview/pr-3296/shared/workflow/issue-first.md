When starting a **new** piece of work, go **issue-first**: before branching, editing, or opening a PR, make sure a tracking issue exists.
Search the tracker first with a qualifying all-state search, not an open-only listing;
if no existing issue covers the task, **file one** (`gh issue create` / `glab issue create`), then proceed.
Never jump straight into a PR without a tracking issue behind it.

On GitHub that search is `gh issue list --state all --search`;
on GitLab it is `glab issue list --all --search` (glab has no `--state`).
Not `--state open`: a closed issue for the same bug is the duplicate an open-only search cannot see, per [`check-open-prs-before-duplicating`](check-open-prs-before-duplicating.md).
`hooks/warn-pr-create-without-dupe-check.py` warns (never blocks) when a `gh issue create` / `glab issue create` runs with no such query earlier in the session.
It prompts the search;
it does not judge the terms ([`grep-is-not-coverage`](grep-is-not-coverage.md)).

The issue is the durable record of intent, scope, and "done" criteria --- it gives reviewers context, lets the PR auto-close it via `Closes #N`, and keeps the work discoverable even if the PR stalls.
Skip only when the task is already tracked by an open issue.
A closed match is not a skip: surface it and confirm before re-doing the work.

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

## A closing keyword plus #N closes #N even when the sentence negates it

GitHub's parser matches `KEYWORD #N` as a substring.
It does not read the rest of the sentence.
A line that says the keyword is not being used still closes the issue
when the keyword sits next to the number.
The squash commit of #1718 closed #1717 that way, and the hook that commit
shipped stayed unregistered until #2275 / #2294.

- **Do:** keep the number off the keyword (`Refs #N`, or "the closing
  keyword was not used for #N").
- **Don't:** write a sentence that places a closing keyword next to #N
  in order to say you are not using it.

See [`ardi.cases.md`](ardi.cases.md), "A negated closing-keyword sentence
still closes the issue", and
[`github-closing-keywords.md`](../../memories/github-closing-keywords.md).

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

## Label an agent-filed issue with its authorship and its model

Every issue an agent files into a repo we administrate carries two labels: `ai-authored`, saying an AI wrote it, and `model:<model-id>`, naming which one.
Add both in the command that creates the issue, not as a follow-up edit.

The labels exist because the issue body cannot say it.
[`disclose-agent-authorship`](disclose-agent-authorship.md) puts a marker line on every agent-posted forge *comment* and explicitly excludes an issue body, so an agent-filed issue discloses nothing at all.
It is filed under the account holder's credentials, so the API reports `type: User` and a `MEMBER` or `OWNER` association, and a reader who finds it later cannot tell it from an issue the maintainer typed.
A label closes that without touching the body, and `gh issue list --state all --label ai-authored` then answers the question for the whole tracker at once.
The model label is separate because it makes a second sweep possible: which model wrote an issue is what a later reader needs when one model turns out to have been systematically wrong about something.

[`label-agent-filed-issues`](label-agent-filed-issues.md) carries the mechanics: the `gh`, `glab`, and MCP forms, how to normalize the model id, creating the labels in a repo that lacks them, and what to do where you cannot.
`hooks/warn-unlabelled-agent-issue.py` warns (never blocks) when an issue is created with no `ai-authored` label.

- **Do:** pass `--label ai-authored --label "model:<model-id>"` in the creating command.
- **Do:** normalize the model id to its canonical form first, so one model maps to one label.
- **Do:** file the issue and report the gap when the labels cannot be created.
- **Don't:** put the disclosure in the issue body instead --- that is the one place [`disclose-agent-authorship`](disclose-agent-authorship.md) rules out.
- **Don't:** collapse the two into one label --- a combined `ai-authored:<model-id>` answers the model question, but finding AI-authored issues at all then costs one query per model spelling.
