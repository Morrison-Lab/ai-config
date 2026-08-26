If you see something, say something.
When you notice a mistake — in code, prose, configuration, data, CI, or any
other medium — file a tracking issue for it immediately, even when it is out
of scope for your current task.
An observation that lives only in the conversation is lost when the session
ends; the issue is what makes it durable.

Worked-example case records for the rules below live in
[`report-mistakes-proactively.cases.md`](report-mistakes-proactively.cases.md), moved out of the auto-loaded context.

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
2. **Dupe-check the tracker.** Search the target repo's issues first with
   a qualifying all-state search (the same search step
   [`issue-first`](issue-first.md) runs: `gh issue list --state all --search`
   or `glab issue list --all --search`); when an existing issue already
   covers the mistake, comment there with the new evidence instead of
   filing a duplicate.
   Not an open-only listing: a closed issue for the same bug is the
   duplicate an open-state search cannot see.
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

## A gated action bundled into a discretionary one is still an offer

The section above rules out the *standalone* offer --- a message whose only
ask is permission to do the thing this rule already requires.
That one is recognizable, because the sentence has no other business.

The version that survives it is a compound question, where filing rides along
with something genuinely discretionary:

> Want me to file the issue and open that PR?

Opening the PR is a real decision, and asking about it is correct.
Filing is not, and putting them in one sentence hands the whole question to
the user under cover of the half that was legitimately theirs.
It also reads as *more* diligent than the standalone offer rather than less,
since the reply is now consulting them about scope instead of merely stalling.

Note where the two failures live, because it explains why re-reading the rule
does not prevent this one.
The rule is consulted at **read time**, when the mistake is noticed and the
disposition is chosen; the violation happens at **composition time**, in a
long message's closing paragraph, where two actions concerning the same
subject get folded into one question for the sake of brevity.
Nothing at that moment feels like a decision about whether to file --- that
decision was already made, correctly, several paragraphs earlier.

So make the split at composition time.
Take the ungated action first, report it in the past tense, and let the
question carry only the remainder:

> Filed as #466.
> Want me to open the PR as well?

- **Do:** scan any question you are about to ask for a second verb, and
  perform whichever half this rule already requires.
- **Do:** report the filing as done in the same message that asks about the
  rest, so the user sees one decision rather than two.
- **Don't:** conjoin filing with a discretionary action --- "file X and do Y?"
  is an offer to file, whatever the second clause is.
- **Don't:** treat a question that is *mostly* legitimate as therefore
  legitimate; the gated clause is the one that decides it.

A `Stop` hook can enforce this mechanically, which is the right shape for a
check with a lexical definition (see
[`algorithmatize-checks`](algorithmatize-checks.md)): scan the outgoing
message for an offer-to-file pattern and block it.
Note the limit before relying on one --- hooks are configured per user in
`~/.claude/settings.json` and are **not** distributed by this repo, so a hook
protects the machine it was written on and no other.
Treat it as a backstop for your own setup rather than as a reason to relax the
rule, since every other session still runs on the prose alone.

## Handing the filing decision to a named third party is the same offer, aimed away from the reader

The two sections above rule out asking the **user** for permission, standalone or bundled.
A third form asks nobody, and that is what makes it survive both: it assigns the decision to a person who is not in the conversation.

> Flagging for the reviewer's call on whether it warrants a follow-up issue.

Read that as an offer with the request removed and the recipient replaced.
It shares the declarative form's defect exactly -- nothing durable exists afterwards -- and adds a distinct one of its own.
The declarative form names no recipient at all, so nobody is left holding anything.
This form names one, which reads as having routed the decision somewhere.
But a reviewer named in a PR comment may never read that comment, and will not read it as a request if they do.
An unrouted decision at least looks unrouted.

It is the hardest of the three to catch from the inside, because deferring to a reviewer's judgment is a **virtue** nearly everywhere else in this corpus.
[`address-every-comment`](address-every-comment.md) and [`fully-clean`](fully-clean.md) both insist that a reviewer's finding is theirs to close rather than yours.
Escalating a genuine impasse to a human is the prescribed move.
So the sentence pattern-matches to deference at composition time, and the question of whether anything got recorded never comes up.

The discriminator is what is being deferred, and it is the same split "Filing is not gated on approval" already draws for the user:

- **Whether to act on a finding** is genuinely the reviewer's call, and saying so is correct.
- **Whether to record it** is not anyone's call, because recording is the reversible half.

Those two live in one sentence and read as one question.
Separate them: file it, then defer the part that is actually theirs.

> Filed as #1379.
> Whether it is worth acting on is still open.

Note that the paragraph carrying this is usually *longer* and more careful than a bare flag would be -- two readings of the evidence, an argument that the data does not distinguish them, an invitation to judge.
That thoroughness is the camouflage.
A finding described in that much detail feels handled by the description alone, which is precisely the reading this fragment exists to refuse.

- **Do:** file first, then hand the reviewer the decision that is theirs -- whether to act.
- **Do:** treat a sentence that names *anyone* as the decider of whether to track something as an unfiled finding, whoever it names.
- **Don't:** read deference as discharging this --- the deference is real, and aimed at the wrong half of the question.
- **Don't:** let the length of the write-up stand in for the durability of the record.

`hooks/no-unfiled-finding.py` does **not** yet cover this, and the gap is worth recording because it was invisible from the one case that produced the section.
Its patterns are keyed on filing-intent vocabulary -- `worth`, `needs`, `deserves`, `warrants` -- which the original phrasing happened to carry.
Every other spelling of the same structure walks straight past it:

```text
Flagging for the reviewer to judge whether this belongs in the tracker.
I'll defer to the reviewer on whether to open an issue for this.
Leaving it to the reviewer's discretion on whether this is worth pursuing an issue.
Deferring to the maintainer on whether this needs tracking.
```

So a guard matching one instance of a class is not a guard on the class, and "the existing hook already catches this" is a claim to test against fresh phrasings rather than against the case in hand.

Widening it is tracked in [ai-config#2017](https://github.com/Morrison-Lab/ai-config/pull/2017), separately and deliberately.
The rule above stands on its own and does not depend on the guard: a mechanized check is what makes a rule cheap to obey, never what makes it true.
That separation is worth stating rather than leaving implicit, because the reverse reading -- that an unmechanized rule is somehow provisional -- is what turns a hard guard into a reason to stop writing the rule down.

## Offering to hand over work you have already finished

The general rule is [`no-cop-out-offers`](no-cop-out-offers.md), which covers any offer to do already-authorized work and carries the `Stop` hook this section anticipates.
This section is the sharpest instance of it: the artifact already exists.

Both sections above concern work not yet done, where the offer at least proposes spending something.
The version that survives them offers an artifact that **already exists**: the comment is drafted, the file is written, the diff is staged --- and the reply says "say the word and I'll post it" rather than posting it.

It is the most defensible-feeling offer of the three and the emptiest.
The two asymmetries in "Filing is not gated on approval" both collapse here, because the cost side is zero: there is no duplicate work to risk and no spend to authorize.
The only thing the offer purchases is a round trip.

Two things make it feel like courtesy rather than avoidance.
The work being done drains the urgency --- nothing is outstanding from the inside, so holding it reads as consideration for the user's attention rather than as withholding.
And the artifact is usually sitting in a scratch file, which feels like *somewhere*, so it does not feel at risk.
It is: a scratch file dies with the container, and the user cannot read it.
An artifact nobody has been shown has the same value as one never written.

The fix is positional rather than procedural.
The moment you find yourself writing that a deliverable exists, that sentence
is the place to deliver it --- inline, in the same message.
Where genuine discretion remains, it attaches to what happens *next* (open
the PR, post it publicly under their name), never to whether they may see
what you already made.

- **Do:** put the finished artifact in the message where you first mention
  it exists.
- **Do:** keep the question for the irreversible or outward-facing step that
  follows, and ask it in the past tense about the delivery ("here it is ---
  want me to post it?").
- **Don't:** offer to show, print, paste, or summarize something already
  written; that is not a decision the user has.
- **Don't:** treat a scratch-file path as delivery --- naming where it lives
  is not the same as handing it over.

## Never name an issue number before the issue exists

The rule above pushes filing earlier, and step 4 asks you to link the filed
issue back into the PR you were working.
Together they invite a specific error: writing the link-back **in the same
breath** as the intent to file, before either step 2 or step 3 has run.
An issue number is trivially predictable --- one more than the last one you
saw --- so "tracked in #821" reads exactly like a fact and costs nothing to
type.

It is a false claim about an artifact, which is worse than an ordinary wrong
sentence, because nothing in the repository contradicts it.
A reader who follows the link lands on whatever #821 turns out to be, or on
nothing; either way they have no reason to suspect the citation was invented
rather than mistaken.
[`ardi`](ardi.md)'s head-commit rule covers the same defect for a different
artifact: the claim is about *state*, and the number is the one part of an
issue you cannot verify by recollection.

The sharper reason to wait is that the announcement pre-empts step 2's
answer.
Saying "filed as #N" commits you to a *new issue* before the dupe-check has
decided whether a comment on an existing one was the right landing place ---
so the premature citation does not merely risk a wrong number, it forecloses
the correct action.
Run the dupe-check, take whichever action it selects, then quote the number
the API actually returned.

- **Do:** file (or comment) first, and cite only the identifier the create
  call returned.
- **Do:** write the link-back as a separate step after step 2 has chosen new
  issue versus comment, per step 4's ordering.
- **Don't:** predict an issue number, however obvious the next one looks.
- **Don't:** announce "filed as #N" while the dupe-check is still outstanding
  --- that asserts the new-issue outcome before anything has decided it.

## A dupe-check chained into the same call as the create gates nothing

The section above rules out announcing step 2's outcome before step 2 has
decided it.
This one rules out the opposite shape, where step 2 genuinely runs and its
answer is never consulted, because the search and the `gh issue create` it
gates were placed in **one** Bash call:

```bash
gh issue list -R O/R --state open --search "..." --json number,title
gh issue create -R O/R --title "..." --body-file /tmp/body.md
```

Both commands execute.
The search returns its match, and the create runs anyway.
Nothing can branch on a result that arrives at the same instant as the action
it was supposed to gate, so the check is decorative.

The near-miss is what makes this worth stating, because the check is not
skipped.
It is written, it appears in the transcript, and it returns the right answer,
so a reply asserting that the tracker was searched is true as far as it goes.
What is missing has no moment attached to it.
There is no point in the sequence where a step was dropped, only a call
boundary that was never drawn --- which is why re-reading step 2 does not
prevent this, and why it reads as compliance from the inside.
It also defeats review by transcript, since a compliant session and this one
emit the same two commands in the same order.

**The general form is what to carry away, because filing is only one
instance.**
Any rule of the shape "search first, then act" fails identically: the open-PR
check before `gh pr create`, a reviewer-reachability read before a dispatch,
the fresh `git ls-remote` that
[`check-before-pushing`](check-before-pushing.md) requires immediately before
every push.
Each becomes decorative the moment it shares a call with what it gates.

[`pr-on-claim`](pr-on-claim.md) already states the structural sibling for one
command: the Copilot `requested_reviewers` POST must be the sole, or last,
command in its Bash call, so that a `Stop` hook can tell whether it ran.
The reason here is different and stronger.
There the reader is a hook, and separability is enough.
Here the reader is you, so the query has to **finish in its own call**, with
its output in front of you, before the gated command is composed at all.

**The missing-search instrument does not reach this, so do not expect it to
warn here.**
`hooks/warn-pr-create-without-dupe-check.py` guards `gh pr create` /
`glab mr create` / `mcp__github__create_pull_request` and, as of #2088,
`gh issue create` / `glab issue create` / the MCP create-issue tools.
Its discharge is a session-wide lexical scan of the transcript for any earlier
qualifying search, so it asks whether a query happened rather than whether
its result was read --- which is the distinction this section is entirely
about.
`hooks/warn-dupe-check-chained-to-create.py` is the instrument for the
same-call shape this section names.

- **Do:** run the gating query in its own call, read its result, and only then
  run the action it gates.
- **Do:** treat the call boundary as where the decision gets made, since that
  is the only point at which a result exists to decide on.
- **Don't:** chain a dupe or precondition check and the action it gates into
  one Bash call --- the check runs and gates nothing.
- **Don't:** read "the search is in the transcript" as evidence it was
  consulted.
  A compliant session and this one look identical there.

See
[`report-mistakes-proactively.cases.md`](report-mistakes-proactively.cases.md),
"A dupe-check chained into the same call as the create".

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
- The [`defer-issue`](../../skills/defer-issue/SKILL.md) skill fires on the
  **user's** explicit deferral ("let's handle this later"), and on
  [`issue-first`](issue-first.md)'s standing permission to defer a request
  the user made that is out of scope for the change in flight; this rule is
  self-initiated, with no prompt needed.
- [`ardi`](ardi.md)'s Defer step already tracks out-of-scope **review
  findings**; this rule generalizes the same habit to any mistake noticed
  in any task.
- [`flag-practice-slippage`](flag-practice-slippage.md) is the same habit
  aimed at **practice** rather than at an artifact --- how the work is being
  done, including the user's own conduct.
  Every medium enumerated above is a thing, so nothing here fires on a
  behaviour, and the deliverable differs too: a filed issue there, one
  sentence at the actionable moment here.
