If you see something, say something.
When you notice a mistake — in code, prose, configuration, data, CI, or any
other medium — file a tracking issue for it immediately, even when it is out
of scope for your current task.
An observation that lives only in the conversation is lost when the session
ends; the issue is what makes it durable.

"Any medium" is literal: it includes our AI-config files themselves
(skills, shared fragments, memories, `CLAUDE.md`s), `gha` workflows and
composite actions, and generated or derived artifacts (test snapshots,
lockfiles, rendered output) — an infrastructure mistake is as trackable as
a product one.

## The procedure

1. **Say something in chat.** Surface the mistake as a one-line `⚠️ FLAG`
   (per `CLAUDE.md`'s chat-output-tagging convention) so the user sees it
   now — but don't stop there; chat is not durable.
   The flag is a heads-up, not a request.
   Ending it with an offer ("worth an issue --- say the word and I'll file
   it") is the failure this rule exists to prevent, dressed as courtesy.
2. **Dupe-check the tracker.** Search the target repo's issues first (the
   same search step [`issue-first`](issue-first.md) runs); when an open
   issue already covers the mistake, comment there with the new evidence
   instead of filing a duplicate.
3. **File the issue immediately, without waiting for approval.**
   Do it in the same work stride as noticing it, not batched for a wrap-up
   step, mirroring `CLAUDE.md`'s "run UMS proactively" timing rule.
   Write it to stand alone: what is wrong, where (file/line or URL), why
   it's wrong, and — for a bug — a reprex where feasible, per
   [`issue-first`](issue-first.md).
4. **Link it back.** Name the filed issue in chat — as a follow-up to
   step 1's flag, or as one combined flag-plus-link message when filing is
   quick — and in a PR comment when the mistake surfaced while working a
   PR, so the record is discoverable from both sides.

## Filing is not gated on approval

The rule above rules out *deferring* a report to a wrap-up step.
It has to rule out the adjacent move too, because that one looks like
compliance: flag the mistake now, and file it once the user says go.

That is not filing.
An offer to file is worth exactly what an unfiled observation is worth ---
both live only in the conversation, and both die with it.
So the offer does not even buy the caution it appears to buy; it just moves
the work onto the user that this rule exists to take off them.

Two asymmetries decide it:

- **A duplicate issue is cheap and a lost observation is not.**
  Filing something already tracked costs a close, or a comment on the
  existing issue.
  Not filing costs the observation outright, once the session ends.
- **Only the user can tell you a thing is not worth tracking, and they can
  tell you that after it is filed.**
  Waiting to ask converts a reversible action into a blocking one.

**Step 2's dupe-check is not an exception to this.**
It decides **where** the report lands --- a new issue, or a comment carrying
the new evidence onto an open one --- not **whether** to make it.
Those are different questions, and only the first has a discretionary
answer.

(Corrected in an ai-config session, 2026-07-28: a sweep found 49 of 179
installed skills stale or orphaned, and the finding was reported as "worth a
tracking issue separately --- say the word and I'll file it".
The user's correction was "always file issues as soon as you notice them" /
"don't wait for my approval".
The dupe-check then showed it was already tracked by #755 and #769, so the
correct action was a comment with the new evidence rather than a new issue
--- which is step 2 doing its job, and is exactly the decision the offer had
deferred instead of making.)

## Where to file

- **The repo where the mistake lives, when it's one we administrate** (our
  own repos and orgs — the same set [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)
  lists as "our own repos").
- **Never autonomously in an external repo.** When the mistake belongs to
  an upstream or third-party repo, follow
  [`upstream-issues`](upstream-issues.md): draft the report, file it in one
  of our own repos via that fragment's own-repo fallback, and ask the user
  to transfer or escalate it.
  External repos' contribution policies bind us, and some ban autonomous AI
  submissions outright.
- **When the session can't reach the home repo** (not in the session's
  GitHub scope, no network path), file in the current working repo, state
  plainly which repo it really belongs to, and ask the user to transfer it
  — the same fallback the `config-ai` skill's step 3 uses.

## Scope discipline

Filing the issue is the deliverable — don't derail the current task into
fixing the mistake.
The exception is a trivial fix in a file the current work already touches
(a typo on a line you're editing anyway): fold that in rather than filing.
Severity doesn't gate the rule: a nit gets tracked too — severity affects
the issue's priority, not whether it's recorded.

## Relationship to existing rules

- [`issue-first`](issue-first.md) governs work you're about to **start**;
  this rule governs mistakes you merely **notice**, whether or not anyone
  will work them soon.
- [`upstream-issues`](upstream-issues.md) supplies the where-to-file ladder
  this rule's external-repo case defers to.
- The [`defer-issue`](../../skills/defer-issue/SKILL.md) skill fires only
  on the **user's** explicit deferral ("let's handle this later"); this
  rule is self-initiated — no prompt needed.
- [`ardi`](ardi.md)'s Defer step already tracks out-of-scope **review
  findings**; this rule generalizes the same habit to any mistake noticed
  in any task.
