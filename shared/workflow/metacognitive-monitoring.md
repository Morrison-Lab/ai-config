Monitor your own claims as you make them.

[Metacognition](https://en.wikipedia.org/wiki/Metacognition) splits into
**knowledge** (declarative, procedural, conditional) and **regulation**
(planning, monitoring, evaluating).
Of the three regulation steps, two happen unprompted.
Planning happens because the task demands it, and evaluating happens when
something fails and forces a look back.
Monitoring is the one nothing prompts, so it is the one that has to be made
procedural rather than left to attentiveness.

## Confidence is a warning sign, not a green light

The natural stopping rule for checking is feeling sure, and the article
reports that it runs the wrong way:

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

- **State** --- is it green, is it pushed, does it exist, is it public.
  Re-query, never recall.
- **Scope** --- all, every, none, only, the whole corpus.
  Check the population rather than the sample that came to mind.
- **Cause** --- it failed because, this is flaky, that change broke it.
  Ask what else produces the same observation.
- **An unexamined default** --- a flag, a template, a glob, a base ref.
  Name it and decide it, rather than inheriting it silently.

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

- **Do:** restate a load-bearing premise explicitly and name what would
  falsify it, before building on it.
- **Do:** read a hedge in the user's own wording as a request for
  verification.
- **Don't:** treat "the user told me" as having checked -- it establishes what
  they believe, not what is true.
- **Don't:** report a classification built on an unverified premise without
  saying which premise it rests on.

(2026-07-30, auditing Claude token provenance: the user offered "this account
was out of tokens since Sunday I think?" and an entire repo classification was
built on it -- any review succeeding after that Sunday must belong to the other
account.
The hedge went unread.
The user then posted their usage chart, showing continuous usage across the
whole week and peaking the day after the supposed cutoff, which refuted the
premise and voided the classification.
The chart was one screenshot away the entire time.)

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

[`address-every-comment`](address-every-comment.md) already carries the
per-component versions of this check: verify a suggestion block's literals,
read a cited source, test a negative result's search scope.
Each of those governs what you do **to the PR**.
This one governs what you **assert**, which is a separate surface with no
reviewer standing on it.

- **Do:** verify a finding's particulars before restating them as fact, even
  when its conclusion is obviously right.
- **Do:** name the check you ran, so a relayed finding stays distinguishable
  from a confirmed one.
- **Don't:** read a reviewer's flat, cited phrasing as evidence that anything
  was checked -- confidence is the house style of that genre, not a signal.
- **Don't:** count a dispatched verification as a completed one.

(2026-08-01, a six-PR session in this repo: four findings were read,
dispositioned, and reported to the user as established fact, each without the
one cheap check that would have confirmed it, and the user re-sent the same
link three times before one was run.
A fifth surfaced while this entry was being drafted, so five were checked in
the end.
Across those five the conclusion held in five of five and the particulars were
wrong in five of five -- a guard whose failure was broader than reported, a
script that was not the one running, a cited line number with nothing at it, a
hardcoded-value scope that named 2 of 6 sites, and
a two-command failure whose first command failed with an error the finding
never mentioned.
The shape then recurred while this entry was being written, and the sixth
instance breaks the pattern the sentence above states.
The observation recorded in
[`fully-clean`](fully-clean.md)'s fifth case was handed over with a completion
time of `04:08:13Z` and corrected here to `04:50:41Z`, which felt like the
check working.
Both are wrong: `#1008` carries no Copilot-attributable check run at all, so
its conclusion -- a green reviewer check with no review behind it -- was **not**
right, and this correction propagated an invented particular into
`fully-clean.md` rather than catching one.
So read "the conclusion held" as five of six, not as a rule.
A verification that only ever adjusts a figure, never asks whether the thing
being measured exists, can carry a fabrication forward while reading as
diligence.)

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

The [Wikipedia article](https://en.wikipedia.org/wiki/Metacognition) notes that
"students often mistake a lack of effort for understanding when evaluating
themselves and their overall knowledge of a concept".

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

- **Do:** convert a mechanism question into a search for its artifact --- a
  comment, a file, a row, a log line --- before reasoning about it.
- **Do:** treat "nobody has ever observed X" as stronger than any argument that
  X should occur.
- **Don't:** accept reviewer agreement as evidence for a mechanism claim; a
  reviewer checks the argument you gave, not the record you did not consult.
- **Don't:** let the future tense of the claim hide that the answer is already
  in the past.

(2026-08-01, `UCD-SERG/ucd-serg.github.io#89`: a review workflow's
`pull-requests` permission was narrowed to `read`, justified by the argument
that "the action posts with its own app token, so the workflow token does not
need write".
The argument was wrong, and two Copilot reviews restated it without objection.
One query --- whether a `claude`-authored comment existed on any earlier PR ---
returned zero across the workflow's entire month of operation, which settled
both the mechanism and the fact that reviews had never once posted.
Nobody ran it until a fourth PR was opened to fix the consequence.)

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

(Same session: writing a docstring that had to state precisely how a correction
behaved across two study arms is what exposed the claim "relative error is
identical across arms" as false, because the precision forced a computation
that contradicted it.
Tabulating the node types in a diagram is what exposed that four of them sat on
three different scales.
Against that, most of that hour's writing was post-hoc recaps: well organized,
tabulated, and incapable of surfacing anything, since everything in them was
settled before composition began.
The user corrected roughly every three minutes throughout, several times on the
same underlying failure, while the polished output continued.)

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

(2026-07-30, this task's own brief: long, complete, and carrying several false
claims about this corpus that survived precisely because writing it required
justifying nothing.
One --- "model on the two existing `Stop` hooks" --- would have had to earn its
place under a stripping pass, and one `ls` settles it.)

## Do and don't

- **Do:** classify each assertion as state, scope, cause, or default before it
  goes out, and re-measure any that is not from this turn.
- **Do:** name the falsifying command beside a claim, and run it when it is
  cheap.
- **Do:** treat a fluent, undeliberated answer as owing an alternative you can
  name and reject.
- **Do:** write the claim that can be wrong --- a specification, a prediction, a
  precise statement of mechanism --- early enough that being wrong still costs
  little.
- **Don't:** treat a polished retrospective as evidence that thinking happened;
  a summary of settled conclusions cannot fail, so it cannot test anything.
- **Do:** strip a brief, issue, or PR body after writing it, asking of each
  element whether the task actually depends on it.
- **Don't:** mistake a complete document for a tested one --- completeness is
  satisfied by adding, and adding tests nothing.
- **Don't:** use confidence as the signal to stop checking --- it runs the
  wrong way.
- **Don't:** read a command's output as settling a question without checking
  what that command's scope actually was.
- **Don't:** let a recap's overall accuracy vouch for an individual cell in it.

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

(2026-07-30, a `ucdavis/bcs` session: the five most confidently asserted claims
were all wrong, and each was one command from being settled.
A leaked credential was described as having gone into a *public* PR, when the
repository is private with three direct accounts.
This corpus was said to ship no hooks, from a grep against a checkout 27
commits behind.
A PR was reported green and conflict-free from a query returning 11 passing and
4 pending, taken before three of that PR's own later pushes.
A changelog count of ten was reported as nine, because the regex matched only
one of two link forms.
And a blocking `Stop` hook was called the right shape for a new rule, when it
would have suppressed error admissions.
The directives were "cai: use metacognition", "cai: think before you speak;
question yourself", and "cai: question your generative intuitions".)
