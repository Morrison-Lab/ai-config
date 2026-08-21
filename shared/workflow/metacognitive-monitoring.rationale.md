# Rationale: metacognitive monitoring

The mechanism, evidence, and argument behind the rules in
[`metacognitive-monitoring.md`](metacognitive-monitoring.md),
moved here to keep it out of the auto-loaded `CLAUDE.md` context.
Each heading mirrors the fragment's own section, and each passage
opens with the bold rule statement it argues for, repeated from the
fragment; the fragment's copy is authoritative.

[Metacognition](https://en.wikipedia.org/wiki/Metacognition) splits into
**knowledge** (declarative, procedural, conditional) and **regulation**
(planning, monitoring, evaluating).
Of the three regulation steps, two happen unprompted.
Planning happens because the task demands it, and evaluating happens when
something fails and forces a look back.
Monitoring is the one nothing prompts, so it is the one that has to be made
procedural rather than left to attentiveness.

## Confidence is a warning sign, not a green light

> greater confidence in having performed well is associated with less accurate
> metacognitive judgment of the performance

Two further findings in the same article point the same direction.
Students "who were rigorously and continually evaluated reported being less
confident but still did better on initial evaluations", and students "who
thought their way was better/easier also seemed to perform worse on
evaluations".

So the moment a claim feels too obvious to check is the moment its error rate
is highest.
And continuous checking *feeling* worse while *working* better is the expected
shape, not evidence that you are doing it wrong.

## Key on claim type, because confidence cannot be the trigger

If confidence is inversely related to accuracy, it cannot be what fires the
check.
Claim **type** can, because it is observable in the sentence you are about to
write:

The four are worth keeping as a list rather than collapsing into "check your
claims", because each names a different *repair*, and the repair is the part
that is easy to skip.

## A premise you were handed is still a claim

All four types above describe assertions **you** generate, so all four trigger
on the act of writing one.
A premise supplied by the user triggers on nothing.
It arrives as context rather than as a claim, you did not reason your way to
it, and adopting it feels like listening rather than like asserting.

That makes it the highest-leverage error available, because a premise sits
*underneath* a conclusion rather than beside it.
Every downstream claim can be individually checked, correctly reported, and
wrong together.
Worse, the work built on it usually looks like careful analysis -- tables,
counts, a classification -- so the polish vouches for the foundation nothing
tested.

The tell is cheap and lexical: **a hedge in the source**.
"I think", "wasn't it", "probably", a trailing question mark.
The user marking their own uncertainty is an invitation to verify, and it is
routinely read as a mere softening of delivery.
Treat a hedged premise as the single most important thing to check, not the
least.

Ask what observation would show the premise false, and whether it is already
within reach.
Often it is, and often the user can produce it in one step.

**The source need not be the user, and a reviewer's finding is the variant this
section's own tell cannot catch.**
Everything above describes a premise a person hands you, and the detector it
offers is lexical: a hedge in the source.
A review comment carries no hedge.
It states its finding flatly, cites a file and a line, and reads as the output
of something that has already looked.
So the one signal this section supplies is silent exactly where the handed
premise arrives most often.

Two things then make such a premise feel checked when nothing has checked it.

**Comprehension feels like verification from the inside.**
Reading a finding closely enough to disposition it is real work, and the effort
goes into understanding what is claimed rather than into testing whether it
holds.
Effort spent is what usually licenses the sense of having verified, so the
finding you worked hardest to understand is the one you are least likely to
confirm.

**Delegating the check feels like having made it.**
Handing the verification to a subagent turns an open question into a dispatched
task, and a dispatched task reads as settled.
It is settled when its answer comes back and you read it, not when it is sent.

The asymmetry is what makes this a rule rather than a caution, because it says
which half to spend the check on.
A competent reviewer's **conclusion** is usually sound: there is something
wrong at that spot.
Its **particulars** are much less reliable -- which guard, which script, which
line, how many call sites, which of two commands failed and with what error.
Particulars are what decide the edit list, so relaying them unverified
propagates a wrong list of lines to change underneath a conclusion that is
right.

That is also why this failure survives a clean outcome.
The fix lands, the reviewer is satisfied, and the only thing left wrong is the
account you gave of it.

**The asymmetry inverts for a reviewer's incidental all-clear, which is the
shape that reaches code.**
The rule above says to trust the conclusion and re-derive the particulars.
An aside works the other way: its particular is a real command with a real
result, reproducible on demand, and the **conclusion drawn from it is wider than
the evidence supports.**
"This pattern is safe because the label binds it, verified: the negated form
returns no verdict" is one true measurement beside one over-reaching claim,
since a label binds what **precedes** the phrase and says nothing about what
follows.
A scope error hiding inside a true sentence is not caught by re-running the
evidence, because the evidence passes.

Three things make an aside worse than a finding, and they compound.
It arrives with evidence attached, so it reads as already-verified rather than
as something owed a check.
It asks for nothing, so no disposition step forces engagement --- a finding gets
Addressed, Rebutted, or Deferred, while an all-clear simply gets adopted.
And a reviewer's asides are usually about the code you are editing, so the claim
does not stop at your prose: it becomes an **exemption in a code path**, which is
how a sentence in a review thread turns into the one branch nobody tests.

The check is to read the evidence's scope against the claim's scope, rather than
to re-run the evidence.
Ask what the cited command actually varied, and whether the conclusion
quantifies over anything it did not.
Where an aside is about to become a carve-out, write the case its evidence did
not cover before writing the carve-out.

[`address-every-comment`](address-every-comment.md) already carries the
per-component versions of this check: verify a suggestion block's literals,
read a cited source, test a negative result's search scope.
Each of those governs what you do **to the PR**.
This one governs what you **assert**, which is a separate surface with no
reviewer standing on it.

**A subagent's report arrives in the same position, and the bullet directly
above stops one step short of it.**
That bullet ends by saying a dispatched check is settled "when its answer comes
back and you read it".
Reading is where this failure *begins* rather than where it ends: the answer
comes back, it is read closely enough to act on, and its particulars are then
repeated to a human as established fact.
Relaying does not feel like generating a claim, so the **state** check above --
re-query, never recall -- does not reliably fire on it, even though the sentence
you end up writing is exactly a state claim.

Two things make a commissioned report harder to doubt than a reviewer's.

**You framed the question.**
A reviewer's finding arrives unbidden, so it is at least recognizable as
somebody else's assertion.
A subagent's report answers a question you wrote, and having framed the
question feels like having controlled the answer.

**Its conclusion usually has a true neighbour.**
"A review workflow is failing repo-wide" can be true while "*this* workflow is
failing repo-wide, with *this* error" is false in both particulars.
The cheap spot check confirms the neighbour and reads as confirming the claim,
so the verification most likely to be run is the one that cannot discriminate.

The conclusion-versus-particulars asymmetry above transfers unchanged, and it
decides which half to spend the query on.
A subagent's **conclusion** is often sound, because it did the work -- and
where it is not, it is usually adjacent to something that is, which is the
neighbour effect above rather than an exception to it.
Its **particulars** -- a count, a version, an error string, which workflow,
which file -- are much less reliable, and particulars are exactly what gets
quoted onward.
So the cost lands differently from a reviewer's finding: that one mis-edits a
PR, while this one **publishes**, and a retraction then has to reach everyone
the first claim reached.

Relaying a subagent's factual claim to a human therefore requires running the
deriving query yourself first.
It is nearly always one command, and usually the very command the report should
have quoted.

Distinguish this from [`preferences.md`](../../memories/preferences.md)'s rule
on verifying a subagent's claim that it **pushed** a commit.
That governs a claim about the agent's own **action** -- did you do what you
said.
This governs a claim about the **world** that you are about to repeat as your
own.

**The same asymmetry decides where to look in the delivered WORK, and there it
points at the deviation the agent flagged.**
Everything above is about the report's *claims*.
A delegated task also produces an artifact, and the question of where to spend
a finite review on it has the same answer for the same reason.
Most of the work is brief-following, which the brief itself constrains and a
second reader can check against it.
A deviation is the one place the agent substituted its own judgment for an
instruction, so it is the least externally checked thing in the diff -- and it
is stated plainly in the report, which makes it also the cheapest to find.
Highest yield and lowest cost coincide, which is rare enough to be worth a
rule.

What suppresses the check is that flagging *feels* like handling.
An agent that names its own departure reads as candid, and candour reads as
diligence, so the disclosure discharges the suspicion it should create.
It is the same trade [`fail-fast`](../principles/fail-fast.md) prices for a
partial guard, arriving through the artifact written to demonstrate care: the
sentence spends the one signal that would have sent you looking.
Read a flagged deviation as a pointer to where the work was least constrained,
never as evidence it was considered enough.

Note what does **not** discharge it: agreeing with the reasoning.
A deviation's stated rationale can be correct on its own terms while the code
implementing it is not, so check the implementation against the rationale
rather than checking only whether the rationale persuades you.
[`fail-fast`](../principles/fail-fast.md)'s partial-guard family covers the
shape that takes inside a predicate.

**Verifying ONE particular from a report does not transfer to the one beside
it, and a reviewer confirming the checked half launders the unchecked one.**
The rule above says to re-derive a report's particulars.
It does not say how many there are, and a report sentence routinely carries
more than one.
Checking a single particular from such a sentence produces a real derivation
and a real answer, which is what makes the rest of the sentence feel handled:
the diligence happened, and it attaches to whichever claim you happened to
pick.

Two neighbouring rules look like they cover this and do not, on the same
distinction.
The **true neighbour** effect above concerns one claim at two levels of
specificity, where the cheap check confirms the weaker version and cannot
discriminate.
**Verification of the reachable half** below concerns two populations split by
whether you can probe them at all.
Here the particulars are independent claims rather than one claim restated,
and both are equally reachable, one command each.
The axis is neither specificity nor reachability but **adjacency**: they
arrived in one sentence, so verifying either one warms the other.

The second half is what makes it durable rather than merely likely.
A reviewer asked to check the published claim confirms the half that is true,
in as many words, and says nothing about the half it never looked at.
That reads as corroboration of the whole sentence, so the clean verdict retires
the suspicion instead of raising it.
This is not the ratified-enumeration case in
[`fully-clean`](fully-clean.md), where a reviewer inherits the author's own
*set*; here the reviewer independently confirms a real claim, and the
laundering comes from what happened to sit beside it.

So count the independent claims before quoting a report sentence, derive each
one you intend to publish, and read a reviewer's confirmation for which claim
it actually names.

This one is **not mechanizable**, and the limit is worth stating so nobody
builds the guard.
Deciding that an outgoing sentence restates an unverified particular from an
earlier report needs content matching between the report and the artifact,
which is semantic.
Any lexical proxy fires on essentially every dispatch-then-assert sequence,
which makes it the mushy threshold
[`algorithmatize-checks`](algorithmatize-checks.md) warns about --- the kind
that trains everyone to ignore the instrument.

**A hedge you attach for one audience is owed to the other, and writing it
once is the tell.**
The section above governs a claim arriving *from* a subagent.
This governs one going *to* a subagent, at the same moment it goes to the
user.
A finding you have just measured is routinely stated twice in close
succession: flatly in chat, and in a brief that says to verify it.

That brief's hedge is correct, and it is
[`challenge-the-assignment`](challenge-the-assignment.md)'s authoring-side rule
working as written.
What nothing currently reads it as is **your own doubt in writing**.
The "premise you were handed" tell above keys on a hedge someone else wrote;
this is the same signal with the authorship reversed, so it fires on nothing --
and it is the easier of the two to see, since you typed it.

The two audiences are not symmetric, which is why the hedge belongs to the one
that does not get it.
An agent told to verify can re-derive the claim and reports back when it fails.
The user cannot re-derive it, is the one who acts on it, and hears nothing
further unless you go back.
So the qualified copy goes to the reader who needs it least, and the artifact
ends up protected while the person does not.

## An action you recommend is a claim about state

The four types above fire on an assertion, and the section above extends them
to a premise you were handed.
Both are things somebody states.
A recommendation states nothing about the world.
It is a judgment about what the user should do, which is exactly how
`CLAUDE.md`'s chat-output tagging defines the RECOMMENDATION marker,
distinguishing it from an ANSWER that "reports what is true".
That definition is what carries a recommendation past every rule on this page.

Underneath the judgment sits a claim nobody wrote.
Advising an action presupposes that the action is still available, so
"merge these two whenever you like" asserts that both are open, in a form no
check keyed on status vocabulary can see.
The presupposition is the claim, and it is load-bearing: when it fails, the
advice is not merely imprecise but impossible to follow.

The cost also lands differently from an ordinary stale reading.
A stale assertion misinforms.
A stale recommendation asks the user to *act*, so they spend a turn
discovering the action is gone, and the failure surfaces on their side rather
than on yours.

The tell is positional.
A recommendation is usually the last line of a long recap, and its inputs come
from that recap's own table, which was correct when built minutes earlier.
That is why reciting it does not feel like recalling.

## Calling your own note stale is a state claim about that note

The section above finds a state claim hidden inside a recommendation.
This one is hidden inside a **retraction**.
Reporting that your own memory file, note, or doc has gone out of date reads as
housekeeping, and as an admission against your own interest, which is the last
kind of sentence anyone thinks to verify.
It is a claim about what that file currently says, so it owes the same re-query
as any other **state** claim in the list above: open the file.

Two things make the unverified version easy to reach.
An index or summary line usually names a note's *topic* rather than the fact
inside it, so skimming the index feels like having consulted the note while
telling you nothing about whether it is right.
And the trigger is a failure, so a culprit is wanted at exactly the moment
attention is somewhere else --- which makes "my note must be stale" arrive as
relief rather than as an assertion.
Those two readings are not in tension: the sentence is an admission to whoever
receives it and a deflection for whoever writes it, and it is the second that
decides whether it gets checked.

The cost is worse than an ordinary wrong claim, and it runs the wrong way.
A wrong claim about the world misinforms once.
A wrong claim that a **correct** note is stale teaches the user to distrust a
note that was working, so it damages an artifact rather than a sentence, and
that damage outlives the session.
Note also which note is likeliest to be blamed: one exists at all because
somebody was burned once and wrote it down, so the note nearest a fresh failure
is disproportionately likely to be the one that already describes it.

The same shape one artifact over is recorded in
[`memories/preferences.md`](../../memories/preferences.md), where a design gap
was asserted from a skill's frontmatter `description` without the body being
read.
Index, summary, and description are all pointers, and none of them is the note.

That file's opening `NEVER assume; ALWAYS verify` bullet already owns the
**inverted** direction, and the pair is worth reading together: it bans
reciting a note as current fact without a live check, where this bans declaring
one stale without one.
Both are unchecked claims about the same artifact, so neither substitutes for
the other, and a grep phrased for either direction will miss the other ---
which is [`grep-is-not-coverage`](grep-is-not-coverage.md)'s own subject.

## Question the answer that arrives without deliberation

This is distinct from the confidence point above, and harder to catch.
That one concerns how sure you feel after reaching a conclusion.
This one concerns the conclusion that arrives with no reaching step at all.

There is no moment of judgment to inspect, because the answer is simply
present, and inspecting it never occurs to you.
Fluency is doing the work that deliberation should have done, and it is
self-concealing in a way plain overconfidence is not.

So treat the *absence* of deliberation as the trigger.
Name the alternative you did not consider, and why it lost.
If you cannot name one, you did not choose.

## The moment is composition time

A rule with no moment attached is read only by whoever was already careful.
[`report-mistakes-proactively`](report-mistakes-proactively.md) draws exactly
the distinction this rule needs, about itself: the rule is consulted at **read
time**, when the disposition is chosen, while the violation happens at
**composition time**, in a long message's closing paragraph.
The same split governs monitoring, so the check belongs where the sentence is
written, not in a retrospective afterwards.

The behaviour it targets is a long structured recap produced quickly and
fluently: tables, headers, bolded conclusions.
The form projects more care than went into it, and the fluency is the problem
rather than a side effect of it.
A claim reads as considered because it is well organized, not because anything
checked it.

Note where that leaves the granularity.
Surrounding correctness is what hides a wrong cell, so the check is at the
**sentence** level rather than the message level.
For each assertion: was this measured in this turn, or recalled?

The cheap adversarial version composes with
[`algorithmatize-checks`](algorithmatize-checks.md).
State the claim, then state the command a reader would run to falsify it.
When that command is easy and unrun, run it before speaking rather than after
being corrected.

## Illusions of knowing have an exact software form

The software analogue is worth naming literally, because it feels like
verification rather than like guessing: running a command and treating its
**output** as knowledge without examining its **scope**.

A grep against a stale checkout, a status query taken before three later
pushes, a regex matching one of two link forms --- each returns a real result,
promptly, and the effortlessness of having run *something* substitutes for
having checked what it covered.
[`fixtures-are-not-evidence`](fixtures-are-not-evidence.md) is one instance of
this family; the general form is that an instrument's answer is only as wide
as its input.

## Verification of the reachable half does not transfer to the unreachable half

The section above concerns one claim whose supporting command was narrower than
it looked.
This concerns a **document** whose claims divide into two populations: the ones
about a system you can probe, and the ones about systems you cannot.

Verifying the first population well is what makes the second feel verified.
Both sets get written in one pass, in one voice, so they inherit the same felt
confidence --- and the effort spent measuring the reachable half is exactly the
"lack of effort" inversion above, one level up: the diligence is real, and it
attaches to the wrong sentences.

The asymmetry runs backwards from caution.
The systems you cannot test are where you hold the **least** evidence, so they
warrant more hedging than the parts you measured, not the same declarative
tone.

So when a document mixes both, name the boundary while writing, and treat
everything past it as owing a citation rather than a recollection.
Third-party defaults change underneath a claim that was true when learned,
which is why the citation and a date do work that careful memory cannot.

This is only partly mechanizable, and the honest limit is worth stating:
"is this claim about someone else's platform still current" has no decidable
condition, so it stays judgment.
The checkable proxy is **coverage** --- every claim about a system you cannot
reach carries a link or a date --- which a reviewer can verify even though no
script can judge the claim itself.

## Search for the artifact instead of arguing about whether it would exist

The section above concerns an instrument you ran whose scope you did not check.
This concerns the case where you ran nothing, because the question presented
itself as a matter of **mechanism** rather than of fact.

The shape is a claim about whether some component *can* do something: does this
token carry enough scope, does that path get reached, would this handler fire.
Reasoning about it feels like the appropriate response, because a mechanism
question invites a mechanism answer, and a good argument about mechanism is
genuinely satisfying to produce.

Underneath it there is almost always an **observable** the argument is trying to
predict, and the observable is one query away.
"Does the workflow token need write to post a review?" is an argument.
"Has a review ever been posted here?" is a search.
The second is cheaper, decides the first outright, and cannot be argued with.

Two things make this failure durable.
A mechanism argument is **falsifiable only by another argument**, so it invites
review rather than measurement --- and a reviewer handed a plausible mechanism
tends to check the reasoning rather than look for the artifact, which is how a
wrong premise collects agreement.
And the argument's conclusion is usually about the future ("this will work"),
where the observable is about the past ("this has never worked"), so nothing
about the framing points at the record that would settle it.

So when you catch yourself explaining why something *would* behave a certain
way, stop and ask what would already exist if it did.
Then look for that.

## Ask whether a candidate can produce the effect at all, before measuring how much it does

The section above says to stop reasoning and go look for the artifact.
This one points the other way in the same spirit, and the two need keeping
apart: sometimes the decisive check is neither a search nor a measurement but a
**structural constraint**, and that one is free.

Attributing an effect to a cause is a **cause** claim, so the claim-type list
above already asks what else explains it.
The prior question is cheaper and is the one that gets skipped: can this
candidate explain it at all?
A conservation law, a symmetry, or a geometric constraint frequently rules a
candidate out outright, and ruling it out costs a few lines of source rather
than an instrumented run.

A purely central displacement is the worked example.
Aiming each body of a pair at the other moves both along the line joining them,
which changes the separation's **length** and never its direction, so that term
cannot rotate the pair however large it is.
That is decidable from the function's own six lines, and no measurement of
how much it contributes was ever needed.
Read all six rather than the operative one.
The same function ends by clamping each coordinate against the field bounds
separately, which is the one thing in it that can make a displacement
non-central: at a boundary one coordinate truncates and the other does not.
So the constraint holds away from the edge and has to be re-derived at one,
and a reader who stopped at the line that obviously matters would have missed
the qualification rather than the rule.

What makes the expensive path feel correct is that instrumenting is visibly
rigorous where a feasibility argument is not.
It also resembles the plausible-mechanism story the section above warns
against, and the discriminator is whether the argument is **decidable**.
"This token probably carries enough scope" is a story, falsifiable only by
another story.
"A central displacement cannot change a bearing" is a constraint: it names what
would refute it, and you can go and check.
Checking is what found the clamp above, which bounds where the constraint
applies rather than overturning it --- a story has no such edge to find.
Where you cannot tell which of the two you are holding, you are holding the
story.

**A symmetry you find striking is worth asking what it implies.**
The same incident read exact anti-symmetry between the two bodies as evidence
that the term was the driver.
It is the signature of a **central pair** --- that is, of precisely the
structure that cannot rotate anything --- so the most distinctive feature of
the data was the disproof, mistaken for the confirmation.
A pattern is evidence for whatever generates it, which need not be the
hypothesis in front of you, so name the generator before crediting it.

## A symptom that both a mechanism and its opposite predict is evidence for neither

The two sections above are a pair, and this is the case they leave between
them.
"Search for the artifact" governs a question you answered by reasoning because
you observed nothing.
"Ask whether a candidate can produce the effect" governs a candidate a free
structural check rules out before any measurement.
Here you **did** observe something, the observation is real, and it is
consistent with the mechanism you inferred **and** with that mechanism's
opposite --- so it settles nothing, while feeling like the evidence.

The **cause** claim type above already asks what else explains an observation.
Sharpen it into something you can fail: ask what the opposite mechanism would
have produced, and compare that against what you saw.
When the two predictions coincide, no amount of re-examining the observation
separates them, and the only way forward is a **different** observation.

**Inferring a permanent state from an immediate one is the commonest shape.**
"It was still there when I looked" does not distinguish "it never goes away"
from "it goes away in two seconds", because a single early look is exactly what
both predict.
The discriminating observation is usually free and is simply the same one held
longer: extend the window, or sample until the state changes, and record how
long that took.
Note which direction the error runs --- an immediate look supports the
*stronger* claim, permanence, on the *weaker* evidence.

**A comment justifying a design choice is where such a claim goes unchecked
longest.**
No test exercises a comment, so nothing in the suite can contradict it; and it
reads as settled precisely because it successfully explains code that works,
which is the one property a false mechanism shares with a true one whenever
both predict the same behaviour.
[`fact-check-prose`](../writing/fact-check-prose.md)'s design-choice rule asks
whether the code implements what the prose claims, which is a different
question and passes here: the code does exactly what the comment says it does,
for a reason the comment gets wrong.

**Mutation is the remedy for the neighbouring case and is unavailable for this
one.**
[`algorithmatize-checks`](algorithmatize-checks.md)'s "An attribution claim in a
guide-for-future-edits comment is settled by mutation" governs a claim about
which part of **your own code** produces a behaviour, and removing that part
decides it.
A claim about the **runtime environment** --- what the kernel, the init
process, the shell, or the platform does --- has nothing in your code to remove,
so mutation cannot reach it and only measuring the environment can.
The two are easy to conflate because they arrive in the same artifact, a
comment, and both are cause claims; the discriminator is whether the subject of
the claim is something you can edit.

## A correction inherits its instrument, so a second reading is not a check

"Illusions of knowing" above concerns a **single** reading whose scope went
unexamined.
This concerns the **second** reading, taken to correct the first, from the same
command.

Reporting a figure that contradicts one you reported earlier feels like the
most rigorous thing you do all day.
That is the problem.
The diligence is real and it attaches to the wrong object: it is spent on the
*act of correcting*, and the replacement value inherits credibility the original
had just lost, so nothing prompts the question the retraction should have raised
first --- was the gauge ever right?

Two readings of one instrument are not a measurement and its correction.
They are two samples of the same thing, and if that thing is broken they are two
wrong answers, of which the second is now published under a banner of care.
It is worse than the original error, because a correction reaches further: it is
addressed to everyone the first claim reached, and it teaches them the number is
now settled.

### The tell

> You are about to report a figure that contradicts one you reported earlier,
> and the new figure comes from the same command.

That is the moment to reach for a **different** instrument, not to publish.

Note what does not count as different.
Two commands that read the same underlying field are one instrument wearing two
names, and reaching for the sibling command is the natural move precisely
because it looks like corroboration while confirming nothing.
"Different" means a different *source of truth*, not a different invocation ---
the file the daemon reads rather than the daemon's cache of it, the artifact
itself rather than the index over it.

### Which contradiction fires it

Not every changed number.
A quantity that genuinely moved is the ordinary case, and a rule that fired on
it would flag every progress report.

The discriminator is whether the underlying quantity was **expected to change
over that interval**, which is a semantic judgment rather than a decidable one.
A job counter going from 45 to 90 is a system doing its job.
A utilization figure going from 35% to 87% on a workload nobody changed is a
claim that something moved, and the burden is to say what.

So state the mechanism when you publish a correction.
"It was 35%, now it is 87%" is not a correction, it is a second number.
"It was 35% because I sampled during the serial phase, and here is a reading
that spans both phases" is one, and writing that sentence is itself the check:
a mechanism you cannot name is usually a gauge you did not verify.

### Why no instrument decides this

A hook can see the two figures and the repeated command.
It cannot see whether the quantity was supposed to change, and that is the whole
discriminator --- so its discharge would be wrong on exactly the ordinary case,
which is also the common one.
A guard that misfires on the common case gets disabled, and takes the real cases
with it.

The mechanizable residue is narrower and belongs in the repo that owns the
gauge: where a **specific** field is known cached, a note or a hook naming its
live counterpart is decidable and cheap.
The general rule stays judgment.

## A retraction is only as good as the instrument's reach

The section above concerns a second reading from the **same command**, where
the gauge is shared and so proves nothing.
This concerns a retraction made from a **genuinely different** instrument --- a
new command, a real source of truth, correctly run --- whose input could not
have contained the evidence for the claim being withdrawn.

The direction is the opposite of the one everything else here guards.
The rest of this file warns against **trusting** a null result as a finding.
This warns against **withdrawing a true claim** on one.
[`fail-fast`](../principles/fail-fast.md)'s "A zero-shaped summary can be
sound" is the nearest neighbour and differs in mechanism: there a scope line
was printed and misread, whereas here the scope is the argument you passed and
nothing prints it at all.

What makes it survive scrutiny is that the check is sound.
Every "did you actually verify this?" prompt fires and passes --- a real
command, a real file, a correct reading, a null result honestly reported.
The error is in the **join**: the claim was about a system, and the instrument
was pointed at one file of it.
That is the shape
[`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)'s "mirror
direction" records for a file read at the wrong ref, one axis over --- there
the wrong version of the right file, here the wrong file in the right chain.

So widen the tell the section above gives.
It fires when the new figure comes from the same command; extend it to fire
whenever **the new reading comes from an instrument that could not have seen
the original evidence**.
The question is not "is this check clean" but "could this check have returned
anything else, if the claim were true".
Where it could not, the null result is silent about the claim rather than
against it, and retracting on it publishes a second, worse error under a banner
of care --- one that, per the section above, reaches everyone the first claim
reached and teaches them the matter is settled.

## "Unresolved between two sources" is a place to stop checking, not a finding

The section above is one instrument read twice.
This is two different instruments, on the same fact, disagreeing outright ---
your own tool says X, a reviewer's tool says Y.
The natural next move is to report the disagreement itself: state both
readings, note neither is resolvable from here, and move on.
That move is often wrong, because it treats "I have two conflicting values"
as the end state rather than as evidence that a decisive third check exists
and has not been run yet.

The tell is that "unresolved" is reached for as a **conclusion**, when it is
actually a **description of where you stopped looking**.
A REST endpoint and a GraphQL endpoint disagreeing on one field is not, on
its own, proof that the field is genuinely ambiguous --- it is only proof
that two paths to it were tried.
A third path (a different API, a permissions/role listing, the underlying
database's own audit trail) frequently exists, costs one more call, and
settles it outright.
Reaching for "unresolved" before trying that third path is the same failure
[`fail-fast`](../principles/fail-fast.md) names for a check that stops at
"could not determine": it reports the search as exhausted when only the
cheap half of it was tried.

Declaring a disagreement unresolved also **publishes a claim of its own** ---
that the ambiguity is real --- which a reader has no way to distinguish from
a disagreement that actually was exhaustively checked.
That claim can itself be wrong, and correcting it later costs a full round
with whoever read the "unresolved" framing as settled.

## A re-measurement with a different instrument is a second measurement, not a correction

"A correction inherits its instrument" above governs two readings of the
**same** instrument, and its remedy is to reach for a different source of
truth.
This is what happens once you take that advice and the different instrument
returns a different number.

That remedy assumes the second reading settles the question.
It does not, because the instrument change is itself a candidate explanation
for the difference, and frequently the whole of it.
Where it is, the second reading supersedes nothing, and publishing it as a
correction does something worse than leave an error standing: it reports a
**correct** figure as an error, to everyone the first figure reached.

### Sharpening that section's own test

It already asks the right question and stops one word short.
"State the mechanism that explains the change" is the test, and "a mechanism
you cannot name is usually a gauge you did not verify" is its justification.
The sharpening is that the mechanism has to be a mechanism **in the world**,
not in the instrument.

"It was 93, now it is 99" is not a correction, and that section says so.
"The detector gained an `in (` alternative, which matches 6 more sites" is not
a correction either, and this is the half that reads like one.
It names a mechanism, it is specific, it is derived, and it accounts for the
difference completely --- while being a fact about the ruler.
A named instrument change is therefore the signal that you are holding **two
measurements**, each owed to the revision that produced it, rather than a
measurement and its repair.

### Why it evades the checks

Retracting your own figure is the most rigorous-feeling thing available, so
the replacement inherits credibility the original has just lost.
Nothing at that moment prompts the one question that separates the two cases:
**did the quantity change, or did my ruler?**

The revision usually goes unrecorded for a mundane reason rather than a
careless one.
A measurement is taken with whatever instrument is at hand, so which revision
that was reads as a detail of the run rather than as part of the finding ---
and it drops out first from the paragraph written to be quoted.

### When both revisions are live, neither figure retires

The commonest case has no stale reading in it at all.
A consumer pins one revision of a tool while the tool's own default branch
carries another, so both are running, and each answers a different question:
what the pinned check reports **today**, and what it will report once the pin
moves.
Neither supersedes the other, and a reader told the first figure was an error
stops quoting the one that describes their actual CI.

So label a published figure with the revision that produced it, and publish
both when both are live.

**This is the boundary with
[`algorithmatize-checks`](algorithmatize-checks.md)'s "Widening an instrument
invalidates every figure it produced".**
That section governs an instrument **you** widen, where the earlier readings
really are obsolete and the remedy is to re-derive every one of them in a
single pass.
Read literally it argues the opposite of this section, since "every number
that detector produced is stale" is exactly what invites publishing the new
figure as a correction.
It holds while one instrument has a before and an after.
It does not transfer when two revisions stay live at once, because then the
earlier figure is not stale --- it is still the answer to a question somebody
is asking.

## A sound measurement does not license the claim standing next to it

The two sections above concern instruments whose **reach** was the problem: a
scope narrower than it looked, or an input that could not have held the
evidence.
This concerns an instrument with no problem at all.
The command is right, the scope is right, the reading is right --- and the
sentence written next to the result asserts a different proposition.

### Why it survives every check in this file

Each of those checks asks a question about the evidence, and the evidence
answers well.
Was a command run?
Yes.
Was its scope examined?
Yes.
Did it return what it appeared to return?
Yes.
Nothing in the sequence asks whether the **conclusion** is a conclusion *from*
that evidence, which is the only step that failed.

The credibility transfer is what makes it invisible from the inside.
Measuring is the expensive part of a paragraph, so it is what the writer
remembers doing, and recency plus effort attach the felt confidence to the
whole passage rather than to the one sentence that earned it.
That is the same "lack of effort mistaken for understanding" inversion this
file records from the Wikipedia article, running in the opposite direction:
there an absence of effort licensed a claim, here a genuine effort licenses a
neighbouring one.

### Why optimism bias is the wrong frame

The obvious reading is that a verified mechanism makes the writer over-claim.
That reading predicts the error only ever runs toward confidence, and it does
not.
A measurement establishing that two candidate inputs are *different* can
license "we used the wrong one" just as readily as a measurement of agreement
licenses "this is correct" --- and the retraction case is the harder one to
catch, because withdrawing your own published figure is the most
rigorous-feeling act available.
[`fully-clean`](fully-clean.md) makes the same point about a checker's exit
status failing toward alarm rather than toward clean, and notes that both
directions come from reading a multi-valued answer as a two-valued one.
This is the prose form of that.

### Why the two-sentence test works

It is not a check on the world, and it costs no query.
It is a check on **subject agreement** between two sentences you already hold.
Writing "the measurement establishes X" forces X to be stated at the width the
instrument actually supports, and setting the claim beside it exposes any
subject the instrument never mentioned.
In all three recorded instances the two sentences name different subjects
outright --- a function's behaviour versus a directory's contents, a model
versus a population, a difference versus a currency --- so no judgment about
degree is needed.

### The subset case, and why it is the sharpest form

Three of the five recorded instances join two subjects that are plainly
different kinds of thing --- a function's behaviour and a directory's contents,
a model and a population, a difference and a currency.
The fourth and fifth join a set to a **superset of itself**, and that is harder
to see, because nothing about the sentence changes register.

`git branch -r --contains <sha>` is a complete and correct enumeration of the
branches containing a commit.
Reporting it as no ref containing that commit is one word wider, and the
excluded members --- `refs/pull/<N>/head`, notes, tags, the reflog --- are
precisely where the answer lived.
The default fetch refspec is `+refs/heads/*:refs/remotes/origin/*`, so
`refs/pull/*` is never fetched into a clone at all, which means the null result
was guaranteed independently of the fact being claimed.
That is the same "could this check have returned anything else, if the claim
were true" question the retraction-reach section asks, arriving here through a
sound positive-scope command rather than through a mis-pointed one.

Naming the population is a cheaper remedy than the two-sentence test and covers
this case exactly, because the two sentences would otherwise differ only in a
single noun.
It also produces a claim a reader can falsify without re-running anything,
which is the property [`grep-is-not-coverage`](grep-is-not-coverage.md) asks
for when it says to report the query rather than the conclusion.

The fifth instance shows the superset can be created by the **instrument's own
reporting format** rather than by a word choice.
A test runner returns three numbers and the habit reports two, so the omitted
one is what defines the unmeasured population.
That makes the skipped set invisible in a way the branch-versus-ref case is
not: there the wider noun at least appears in the sentence, whereas here
nothing in "43 pass, 0 fail" hints that a third number exists.

Its second lesson belongs to the **default** claim type rather than to this
section, and is worth naming because the two compound.
`R_PROFILE_USER=/dev/null` was an unexamined default, inherited from an
unrelated workaround, and its effect was to change the population the
measurement covered.
So an unexamined default upstream produced the population gap downstream, and
the reported figure moved not at all.
That is the general hazard with any environment-bypassing flag: it shrinks what
is measured while leaving the shape of the result unchanged, and it makes the
run faster, which is what turns a one-off workaround into a habit.

### Why this is not mechanizable

Stating the limit explicitly, per
[`algorithmatize-checks`](algorithmatize-checks.md)'s "Limits", so that nobody
builds the guard and then quietly disables it.

The condition is a semantic relation between a tool result and a
natural-language sentence: does this claim follow from that evidence.
No lexical or structural property decides it.
A hook keyed on "a factual assertion appears within N turns of a tool call"
would fire on nearly every paragraph this corpus produces, since reporting
findings next to the commands that produced them is the behaviour the rest of
the corpus **requires**.
Its false-positive rate would be close to its firing rate, which is the
condition [`deterministic-tools`](../principles/deterministic-tools.md) names
for leaving a check as judgment.

The checkable proxy is the same one the reachable-half section settles for:
**coverage of the form**, not correctness of the inference.
A reviewer can see whether the two sentences were written and whether their
subjects match, which is a property of the prose.
That is a review check rather than a hook, and it is where this rule is
enforceable.

### The one decidable sub-case, and why it still is not a hook

The skip-count instance is the exception to the paragraph above, and saying so
is what keeps the general claim honest.
"A message reports a testthat PASS and FAIL count from a run that had skips"
**is** decidable, unlike "does this claim follow from that evidence".

It is still the wrong thing to mechanize, for two reasons that are about the
instrument rather than about the principle.
A hook would have to parse prose to find the reported counts, and a prose
parser is exactly the brittle detector
[`algorithmatize-checks`](algorithmatize-checks.md) warns against building.
It would miss a count written as "all green" and fire on one quoted from a log.
And it would have to know the run's real skip count, which is not in the
transcript it can see.

The robust form is upstream of the report: run the tests with an invocation
that prints all three numbers, and carry all three into the sentence.
That makes the habit and the tooling the same act, and it fails safe, because
a runner that prints `SKIP` alongside `FAIL` cannot report a suite as passing
while hiding what did not execute.
[`test`](../../skills/test/SKILL.md)'s reporting step carries that instruction.

## Writing is the instrument, when the claim can be wrong

The article establishes that self-assessment is unreliable and that confidence
points the wrong way.
It does not say what to use instead.
Leslie Lamport does, in a
[2019 interview](https://mentors.fm/2019/08/13/think-and-write-with-leslie-lamport/):

> Writing is nature's way of showing you how fuzzy your thinking is.

> If you think you understand something, and don't write down your ideas, you
> only think you're thinking.

That second sentence is the "illusions of knowing" finding above, arriving from
a different tradition.
Read the two as converging rather than as two independent supports.

Writing is the **manual** instrument, and so the humane counterpart to
[`algorithmatize-checks`](algorithmatize-checks.md).
Where a check cannot be mechanized, writing the claim down precisely is the
next-best forcing function, because vagueness survives in the head and does not
survive on the page.
Lamport puts the same point upstream of the act: "You should think before you
do anything, because it will help you understand what you're doing, which will
help you to do it better", and "To think clearly, you need to be able to write
down your ideas clearly, which requires being able to write well".

**Not all writing tests, and the kind that does not is the kind that feels most
like work.**
Writing done *after* a conclusion is reached, summarizing what was decided, is
documentation.
It cannot fail, so it cannot function as a test --- and it is effortful and
yields a polished artifact, which is exactly why it gets mistaken for one.

So write the thing that **can be wrong**.
A specification, a prediction, a precise claim about state, a stated mechanism:
each can be contradicted by something.
A summary of what was already concluded cannot.

## Stripping is the part that tests

Lamport says writing reveals fuzzy thinking, and the section above says to
write the thing that can be wrong.
Neither says *which part of the writing does the work*.
[R4DS](https://r4ds.hadley.nz/workflow-help.html) does, for the reprex:

> 80% of the time, creating an excellent reprex reveals the source of your
> problem.

It names two components, and only one of them is diagnostic.
**Reproducible** asks you to "capture everything, i.e. include any `library()`
calls and create all necessary objects".
**Minimal** asks you to "Strip away everything that is not directly related to
your problem".

The asymmetry is the point.
Self-containment asks "is everything present?", which is satisfied by
including *more*, and including more never tests anything.
Minimization asks, of every element, "does the problem actually depend on
this?" --- and that question is answerable only by checking.
So a document can be complete, look thorough, and reveal nothing.

[`reprexes`](../../skills/reprexes/SKILL.md) already carries this for code,
and states the mechanism in the same terms: "the noise you strip away was
hiding it."
The increment here is that the property is not about code.
It holds for any self-contained artifact you write, and the one worth naming
is the **subagent brief**, because it is self-contained *by force* --- the
agent has no shared context --- and minimal only *by choice*.
An issue body and a PR description sit in the same position.
[`issue-first`](issue-first.md) already asks for a reprex in a bug report; the
addition is that writing one pays before anyone reads it, so it is worth doing
even when nobody will.

So: write it self-contained, then strip it, and treat whatever resists
stripping as the actual problem.
The stripping pass is not editing for length.
It is the diagnostic.

## Relationship to neighbouring rules

- [`algorithmatize-checks`](algorithmatize-checks.md) says to build the
  instrument rather than reason.
  This says when to reach for one, since a claim you never doubted is a claim
  you never instrumented.
- [`fact-check-code-logic`](../coding/fact-check-code-logic.md) reaches the
  same verdict on confidence from the code-review side: "a claim you are
  confident about is exactly the one you will publish without support."
  Read this fragment as the general case of that observation, differing in
  two ways that are the reason both exist.
  It supplies the *empirical basis* --- confidence is not merely unreliable
  but inversely related to accuracy --- and it supplies a filter that works
  where that one cannot.
  That rule's filter is "is this checkable here, right now?", which presumes
  a runtime and a diff; this one keys on claim type, so it still fires on an
  assertion in a chat recap, where there is nothing to execute.
- [`research-before-asking`](research-before-asking.md) governs a **question**
  aimed at the user.
  This governs an **assertion** aimed at them, which is the commoner act and
  the one with no built-in prompt to check anything.
- `CLAUDE.md`'s "Run UMS proactively" makes a corrected understanding a
  trigger, so it fires **after** a false claim has been discovered.
  This one fires **before** one goes out.
  They are the two ends of the same failure and neither replaces the other.
- [`fail-fast`](../principles/fail-fast.md) surrounds "A correction inherits its
  instrument" on both sides and is not it.
  Its "test the instrument against a known positive before trusting a negative"
  validates a gauge before believing a **null result**; this validates one
  before publishing a **correction**.
  Its "A zero-shaped summary can be sound" runs the opposite way, warning
  against retracting a true result too eagerly --- so read the two together
  rather than treating either as licence.
- [`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s "treat a
  shared origin as grounds for more care, not as corroboration" is the same
  instinct about two **values** that agree.
  The correction case is about two **readings over time** that disagree, where
  the shared origin is what makes the disagreement uninformative.
