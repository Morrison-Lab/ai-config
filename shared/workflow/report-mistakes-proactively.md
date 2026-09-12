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

1. **Say something in chat.**
   Surface the mistake as a one-line `⚠️ **FLAG** ---`
   (per `CLAUDE.md`'s chat-output-tagging convention) so the user sees it
   now — but don't stop there; chat is not durable.
   The flag is a heads-up, not a request.
   Ending it with an offer ("worth an issue --- say the word and I'll file
   it") is the failure this rule exists to prevent, dressed as courtesy.
2. **Dupe-check the tracker.**
   Search the target repo's issues first with a qualifying all-state search
   (the same search step [`issue-first`](issue-first.md) runs:
   `gh issue list --state all --search` or `glab issue list --all --search`).
   Not an open-only listing: a closed issue for the same bug is the
   duplicate an open-state search cannot see.
   When an **open** issue already covers the mistake, comment there with
   the new evidence instead of filing a duplicate.
   The same holds for a new symptom of a tracked defect family: a hook or
   checker that already has a tracking issue gets a comment on it, not a
   sibling issue per symptom
   ([`triage-backlog`](triage-backlog.md), "Fold, do not multiply").
   A closed match is not a skip: surface it and confirm before deciding
   whether to reopen it or file a new one, per
   [`issue-first`](issue-first.md).
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
   `CLAUDE.md`'s "Link PRs in tables" section covers the mechanics for any
   forge artifact, issues included: the link belongs in the comment itself,
   not merely in a later chat recap the PR thread never sees.

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

## How many you have already filed is not an input

The section above at least asks about the finding.
This one does not: it accepts the finding as valid, then withholds it on a
budget the session invented.

It reads as restraint rather than avoidance, which is why it survives
self-review.
It sounds like consideration for the tracker, for the reader's attention, for
a maintainer who will have to triage.
But a valid finding does not become less true because it is the ninth.

**Volume is a real problem, and it is decided somewhere else.**
[`triage-backlog`](triage-backlog.md) exists precisely as the counterweight to
this rule, and it does not claim the cost of filing is small --- it measures
the opposite, an open count going from 15 to 410 in six weeks with 67% of
those issues never commented on.
So the answer to volume is a weekly pass that assigns `P1`/`P2`/`P3` or
closes, run by someone with the standing to decide.
It is not a session silently raising its own bar partway through a sweep,
which produces no triage decision and no record of the thing it declined to
file.

A high count is evidence the sweep is working, not evidence to stop.
A session that surfaces nine defects and files eight of them has not been
disciplined;
it has produced an eight-item record and one thing nobody can find.

- **Do:** file the ninth exactly as you filed the first, and let the count
  land where it lands.
- **Do:** say what the volume suggests, if it suggests something --- a
  cluster of guard findings in one session is itself worth a filed
  observation, which is filing more rather than less.
- **Don't:** withhold a finding you have already judged valid because you
  judge you have filed enough --- the count is not a criterion, and deciding
  it is not the filer's job.
- **Don't:** read a long list of issues from one session as a reason to
  raise the bar partway through; the bar is whether the finding is valid.

(Directive from the user, 2026-09-10 --- "it doesn't matter how many issues
you've already filed" --- after a session that filed eight issues and then
handed the ninth back rather than filing it.
The withheld finding was filed as ai-config#3519 once the correction landed,
which is the measure of what the deferral was protecting: nothing.
Neither [`no-offer-to-file.py`](../../hooks/no-offer-to-file.py) nor
[`no-unfiled-finding.py`](../../hooks/no-unfiled-finding.py) fired on it:
the first wants an interrogative or a `let me know if you'd like` shape, and
the sentence was a declarative preference;
the second matches the artifact by name, and the sentence referred to it by
count.
ai-config#3520 carries the sentence verbatim and two candidate pattern
families.)

## The issue and "land it in this PR instead" are not alternatives

A specific offer shape earns its own section because the false choice inside
it is easy to miss: "I will open the issue unless you would rather it just
land here."
That reads as consideration for scope, not as the standalone offer the
section above rules out, because it names a real alternative --- the work
could genuinely land in the current PR instead of a separate one.

It is a false dichotomy wearing that real alternative as cover.
Filing the issue and landing the work in this PR are not competing
outcomes; they compose in sequence, per
[`avoid-false-dichotomies`](avoid-false-dichotomies.md)'s "offer composable
options as steps with an order when they simply sequence rather than
compete": file the issue now, and if the work then lands in the PR anyway,
close the issue as completed once that PR merges.
Posing them as either/or is what manufactures the exclusivity --- nothing
about the underlying work forces the choice, and the "unless you'd rather"
half of the sentence is already on
[`no-cop-out-offers`](no-cop-out-offers.md)'s list of offer phrasings.

- **Do:** file the issue immediately, whatever answer later arrives about
  where the work lands.
- **Do:** close the issue as completed when the PR that ends up containing
  the fix merges, rather than treating the PR as having made the issue
  unnecessary retroactively.
- **Don't:** phrase filing as conditional on the user preferring it over
  landing the work in the current PR --- state the filed issue as done, then
  ask separately whether the fix belongs here or in its own PR.

(User directive, 2026-09-09, verbatim: "file that issue; you should have
filed it immediately, and then if I told you to land it in 688, you could
have just closed the issue as completed once 688 merged.
never hesitate to file an issue for a valid problem or extension."
The incident: a PR comment on `UCD-SERG/serocalculator#688` closed with "I
will open the issue unless you would rather it just land here."
The issue was filed 11 minutes later as `UCD-SERG/serocalculator#693`, so
step 3 above was not skipped --- but the PR thread was never told, and read
as though nothing had been filed until corrected.
See step 4's linking-back requirement, and `CLAUDE.md`'s "Link PRs in
tables" section, for that second half of the same incident.)

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

## Repeating an "unfiled" status report is not tracking, however many times it gets said

The two sections above are about a message that carries an assertion --- a
fresh claim that something is worth an issue, or a fresh deferral of the
decision to someone else.
This one has no assertion in it at all.
It is a status report, said again: the same known gap, described as still
unfiled, once more.

> That set of stale equation-number comments is still unfiled.

Nothing about that sentence is false.
The gap really is unfiled, and saying so reads as diligence --- the kind of
line a careful stopping-point recap is supposed to carry.
That is exactly what makes it the worse failure rather than a milder one:
each repetition puts the omission on the record again, and each repetition
makes it feel more handled than the last, while the tracker still holds
nothing.
A reader scanning six such lines across six replies sees six honest
disclosures.
Nobody sees that the same sentence was never once acted on.

The near-miss is composition-time, and it is a habit rather than a single
bad sentence.
Step 3 above says file it in the same stride as noticing it, and the first
time the gap was noticed, it likely was flagged correctly.
What repeats is not the discovery --- it is the *report of the discovery*,
carried forward into every later stopping point as though restating the
status were itself an update to it.
Nothing about a repeated status line invites the question "did I ever
actually file this", because the sentence answers a different question
("is this still open") truthfully every time it is asked.

- **Do:** file the issue the moment a known gap is about to be described as
  unfiled again, before writing the sentence that reports it.
- **Do:** treat a stopping-point line naming an unfiled item as the trigger
  to file it, not as evidence that it is being tracked.
- **Don't:** repeat an "unfiled" disclosure across replies --- repetition is
  not tracking, and it reads as diligence while the omission persists.
- **Don't:** defer filing because the item is small, out of scope for the
  current task, or belongs to work still in progress; per
  [`issue-first`](issue-first.md)'s deferral section, an out-of-scope item
  may be deferred, but only by filing it, never by restating its status.

`hooks/flag-unfiled-issue.py` is the mechanism, and it is a WARN rather than
a BLOCK, unlike `no-unfiled-finding.py` above.
The two hooks answer different questions.
`no-unfiled-finding.py` matches a FORWARD assertion (`worth an issue`,
`needs a tracking issue`) and blocks, because the message is making a fresh
claim and nothing yet contradicts it.
This hook matches a RETROSPECTIVE status report (`is/was still unfiled`,
`hasn't been filed`) and warns, because whether the item should have been
filed is not lexically decidable from the phrase alone --- the reply may be
narrating an item already filed, or one this session cannot file into.
The two share almost no trigger vocabulary: a message built entirely from
this section's phrasing sails straight past `no-unfiled-finding.py`'s
`worth`/`needs`/`deserves`/`warrants` list, which is the same "a guard
matching one instance of a class is not a guard on the class" lesson the
section above already draws, arrived at independently and about a
differently-shaped near-miss.

(Directive from the user, 2026-09-09, verbatim: "always file issues
immediately; 'is still unfiled.' should be a hook trigger?"
The incident: across roughly six consecutive replies in one session, a
closing stopping-point line reported a known defect --- a set of stale
equation-number comments in a C source file --- as "still unfiled".
The rule requiring it was already loaded: this file's own procedure above,
and CLAUDE.md's "Status requests do not make issues report-only" section,
which says "File it before reporting it."
The issue was filed only once the user asked for it directly, as
[UCD-SERG/serocalculator#694](https://github.com/UCD-SERG/serocalculator/issues/694).)

**The sibling case, for a memory or skill update rather than a GitHub
issue, lives in [`no-empty-promises`](no-empty-promises.md)'s "Repeating
the disclosure across turns is not the discharge either."**
That section covers a stopping-point line describing a memory entry as
"owed," where the remedy is to dispatch a subagent rather than to file an
issue.
The two sections share the shape --- a truthful, repeated status report that
reads as diligence while nothing gets done --- and differ in the artifact
and the remedy, so a recap naming both an "owed" memory entry and a "still
unfiled" issue is caught in full only by reading both.

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

**The artifact the invented number lands in need not be a chat reply or a PR link-back --- it survives just as easily in a durable file, and there it outlives the conversation that invented it.**
Every example above is something said to a reader in the moment: a PR body, a merge message, a reply.
A predicted number written into a memory entry or a corpus fragment is the same invented claim, aimed at a file this session is about to commit rather than at a person reading the current thread --- and it is worse in one respect, since a chat claim dies with the conversation while a committed one persists until someone happens to notice the mismatch.

(Measured 2026-09-09: `ai-config#3439` was written into a memory entry before the filing call ran;
the issue that call actually created was `#3449`.
Caught and corrected before the entry was committed, but nothing in the repo would have caught it afterward --- a wrong issue reference passes every existing check, since nothing resolves an `ai-config#NNNN` citation against the tracker to confirm it names what the text claims it names.
Whether that gap is worth a dedicated checker, rather than only this rule, is its own open question, tracked separately rather than decided here.)

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
command: the Copilot `requested_reviewers` POST must be the sole command in
its Bash call, so that a `Stop` hook can tell whether it ran.
The reason here is different and stronger.
There the reader is a hook, and separability is enough.
Here the reader is you, so the query has to **finish in its own call**, with
its output in front of you, before the gated command is composed at all.

**The missing-search instrument does not reach this, so do not expect it to warn here.**
`hooks/warn-pr-create-without-dupe-check.py` guards `gh pr create` / `glab mr create` / `mcp__github__create_pull_request` and, as of #2324 (closing the proposal in #2088), `gh issue create` / `glab issue create` / the MCP create-issue tools.
Its discharge is a session-wide lexical scan of the transcript for any earlier qualifying search, so it asks whether a query happened rather than whether its result was read --- which is the distinction this section is entirely about.
`hooks/warn-dupe-check-chained-to-create.py` is the instrument for the same-call shape this section names.

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

## A defect that resolved itself on a retry is still a defect

The rules above all govern a finding you can still see.
This one governs the finding that stops reproducing while you are deciding
what to do about it, which is the shape most likely to go unfiled --- not
because anyone judged it unimportant, but because the reason to file it
disappeared before the filing did.

The reasoning that dismisses it sounds like proportion rather than avoidance:
the thing recovered, nothing is broken now, and filing an issue for a state
that no longer exists looks like noise.
Every clause there is true and the conclusion is still wrong, because a
defect that fires intermittently is *harder* to diagnose than one that fires
every time, not easier.
Self-resolution is evidence about this attempt.
It is no evidence at all about recurrence, and it destroys the artifact a
later investigator would have started from.

The transient case also carries diagnostic information the reproducible one
does not, and only a filed record preserves it: how often it fired, what the
population was, and what made it stop.
"Two of twelve, and re-dispatching fixed both" tells a maintainer that the
cause is intermittent rather than a formatting bug, and hands them a
workaround.
"It happened and then it did not" tells them nothing.

So file it, or add the measurement to the issue that already covers it, on
the same terms as any other finding.
The rate and the recovery step belong in the report, since those are the
parts that expire.

- **Do:** file a defect that stopped reproducing, and state the rate
  (how many of how many) and what made it stop.
- **Do:** dupe-check first --- a transient defect is disproportionately
  likely to be already known, precisely because it recurs.
- **Don't:** treat a successful retry as closing the finding; it closes the
  incident.
- **Don't:** reach for "it resolved itself" as a reason to skip the filing
  step --- that phrase describes the evidence, not the defect.

(Morrison-Lab/wai, 2026-09-10.
Two of twelve PR reviews emitted a `Reviewed commit` fingerprint naming a
commit absent from the repository, disqualifying both from an otherwise
authorized merge.
Re-dispatching the review produced correct fingerprints and the session
moved on, calling it "transient rather than a defect worth filing".
`hooks/no-unfiled-finding.py` caught the sentence, and the finding turned
out to be already tracked as ai-config#3508, where the rate and the
re-dispatch workaround were genuinely new information.)

## Scope discipline

Filing the issue is the deliverable — don't derail the current task into
fixing the mistake.
The exception is a trivial fix in a file the current work already touches
(a typo on a line you're editing anyway): fold that in rather than filing.
Severity doesn't gate the rule: a nit gets tracked too — severity affects
the issue's priority, not whether it's recorded.

## The site list in an issue you file is a scope claim, and filing is when it goes underived

An issue naming where a defect occurs asserts a **population**, and
[`metacognitive-monitoring`](metacognitive-monitoring.md) already says a scope
claim gets checked against that population rather than recalled.
Filing is where the rule does not fire, for a reason specific to filing: the
enumeration reads as the *finding* rather than as a claim about it.
You have just seen two occurrences, the issue is about those two, and listing
them feels like reporting what you found instead of asserting that it is all
there is.

The cost lands on someone else and lands late.
Whoever picks the issue up fixes exactly the sites it names, closes it, and the
remaining ones survive with a **closed issue standing over them** --- which is
worse than no issue, because a closed tracker entry is evidence the class was
handled.
That is the same trap [`issue-first`](issue-first.md) records for `Closes #N`
over a wider issue, arriving from the other end: there the diff is narrower
than the issue, here the issue is narrower than the defect.

The check is one command and it is the same one you will run when you start the
fix, so filing without it only defers the work past the point where it would
have been cheap.
Derive the set from the **pattern**, not from the paths you remember:

```bash
grep -rn 'select(\.\(author\|user\)\.login *|' --include=*.md --include=*.py .
```

Report what the sweep examined alongside what it found, so a later reader can
tell a complete population from a partial one --- the habit
[`derive-dont-enumerate`](derive-dont-enumerate.md) asks of a sweep, applied to
the issue that starts one.

**A site the sweep finds and you deliberately exclude belongs in the issue
too**, with its reason.
Silence there is indistinguishable from not having looked, and the next reader
re-derives the same set and re-opens the same question.

- **Do:** run the deriving query before filing, and state the population it
  examined.
- **Do:** name the sites you found and excluded, with why --- a quoted past
  attempt is history rather than a defect.
- **Do:** treat "another open PR already deletes it" as a reason to WATCH
  rather than to exclude.
  It is a claim about a merge that has not happened, so it expires the moment
  that PR closes unmerged, and the site is live on the default branch the whole
  time --- record it as pending on that PR rather than as handled.
- **Do:** correct the issue in the open when the sweep at fix time finds more
  than the issue named, rather than quietly fixing the wider set.
- **Don't:** enumerate the occurrences you happened to see and let the count
  read as the finding.
- **Don't:** leave a closing PR to cover a population the issue understated ---
  the issue closes, and what it missed keeps a closed entry standing over it.

(Morrison-Lab/ai-config#3069, 2026-09-02: filed naming **two** sites of an
unguarded `jq` filter that aborts on a deleted review author.
The sweep run at fix time found **five**.
One was a third prescribed command the issue never mentioned and #3081 fixed.
One was a quoted record of a past failed attempt and was correctly left alone.
One was excluded as "deleted outright by an open PR", which was the wrong
disposition: #3024 replaces that line with a guarded form, but #3024 is
**still open**, so the unguarded filter is live on `main` at
`hooks/no-unreviewed-pr.py:1912` as this is written.
ai-config#3081's own body carried the caveat --- "that fix rides entirely on #3024
merging" --- and the first draft of THIS entry dropped it and reported the
outcome as accomplished, which is the same expiring-state claim the section
above is about, made inside the section about it.
Had the fix covered only the two the issue named, `Closes #3069` would have
shut it with three sites unexamined.)

## An issue's stated reasoning goes unrevisited by default, and an entry citing it inherits whatever it argues

The section above is about an issue body's site list going underived at filing time.
This is the same body one field over: its **reasoning**.

A filed issue is a claim you stop re-reading the moment it is filed.
Its *conclusion* gets revisited whenever someone picks the issue up, because the conclusion is what they came for.
Nothing prompts a re-read of its stated reasoning, so an argument that later work refutes sits there indefinitely, still reading as the issue's justification --- and any corpus entry that cites the issue as a worked instance inherits that argument along with the citation.

Measured on [#3296](https://github.com/Morrison-Lab/ai-config/pull/3296).
[#3275](https://github.com/Morrison-Lab/ai-config/issues/3275) asserted that a pre-squash SHA "survives only in the loose-object store of whichever checkout created it", reasoning from `git for-each-ref --contains` returning zero refs.
`git ls-remote origin refs/pull/3060/head` prints the OID `f90682991a6d...` against `refs/pull/3060/head` --- the object the issue said had survived only locally --- so the reasoning was the exact misconception [`git.md`](../../memories/git.md) was being edited to correct at the moment it cited #3275 as an instance of that misconception.
The conclusion was unaffected, which is why nothing prompted a re-read.
A reviewer caught the stale reasoning only by following the link and reading what the issue actually said.

So when you cite your own earlier filing as an example, re-read that filing against what you now know, and correct it if the work has moved past it --- the citation is what makes its reasoning load-bearing again.

- **Do:** open and re-read an issue you are about to cite, rather than citing it from what you remember filing.
- **Do:** post a correction on the issue itself when its reasoning has been refuted, even where its conclusion still stands.
- **Don't:** treat an unchanged conclusion as evidence the body is still accurate.
- **Don't:** cite your own issue as a worked instance without checking that the instance still works the way the issue says.

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
- [`metacognitive-monitoring`](metacognitive-monitoring.md)'s **Scope** claim
  type is the umbrella rule the site-list section above is an instance of.
  What that file supplies is the check --- read the population, do not recall
  it --- and what the section adds is the one moment the check reliably does
  not fire, because at filing time an enumeration reads as the finding rather
  than as a claim about it.
- [`derive-dont-enumerate`](derive-dont-enumerate.md)'s "A closed population
  inside one file still needs deriving, not guessing" is the nearest existing
  parallel, and the mechanic is the same one level narrower: searching for the
  members a sweep expects rather than deriving the whole set.
  The section above is that habit applied to an issue BODY, which is where it
  costs a later reader rather than the author --- the enumeration ships, and
  whoever fixes it inherits the undercount.
- [`flag-practice-slippage`](flag-practice-slippage.md) is the same habit
  aimed at **practice** rather than at an artifact --- how the work is being
  done, including the user's own conduct.
  Every medium enumerated above is a thing, so nothing here fires on a
  behaviour, and the deliverable differs too: a filed issue there, one
  sentence at the actionable moment here.
