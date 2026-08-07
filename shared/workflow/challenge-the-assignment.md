Question what you are asked to **do**, not only what you are told is **true**.

Worked-example case records for the rules below live in
[`challenge-the-assignment.cases.md`](challenge-the-assignment.cases.md), moved out of the auto-loaded context.

The verification rules in this corpus all point at claims.
A claim asserts something, so writing one or repeating one is an act that a
rule can fire on.
An assignment asserts nothing.
A brief, an issue body, a plan, an orchestrator's directive, a convention
document, a posed choice: each tells you what to do rather than what is so, and
so none of the claim-checking rules reach it.

The cost of being wrong runs the other way, though.
A wrong claim spoils a sentence.
A wrong assignment spoils the whole task, and spoils it invisibly, because
every downstream step can be executed correctly and checked green.

## Why nothing prompts the check

[`metacognitive-monitoring`](metacognitive-monitoring.md) explains that a
premise handed to you triggers on nothing, because it arrives as *context*
rather than as an assertion.
A directive is one step further along the same axis: it arrives as
**authority**.

That makes adopting it feel like compliance, which is a virtue, so the moment
of adoption feels like doing the job well rather than like skipping a step.
Questioning it feels like insubordination, or like scope creep, or like
stalling --- and all three are real failures, which is exactly why the
suspicion lands on the check rather than on the instruction.

The result is that the least examined input is the one determining everything
else.

## Three shapes, in rising order of how settled they look

**A convention document's own claims.**
A `CLAUDE.md`, a design doc, a lab manual, a README.
These are the hardest to question because being written down *is* what
normally makes something checkable, so the form that should invite scrutiny
supplies the appearance of having received it.
Worse, they propagate: an assertion in a convention document is copied into
issues and briefs by everyone who reads it, so by the time it is wrong it is
wrong in a dozen places, each of which corroborates the others.

**A brief or a directive.**
A subagent brief is self-contained by force, so nothing outside it can
contradict it.
Its completeness is not evidence of its correctness --- writing a long brief
requires justifying nothing, so a false claim inside one survives precisely
because the document was never a test of anything.

**A posed choice.**
A question that offers A or B is also an instruction: it directs you to pick
from a set, and the set is the part you did not choose.
Answering it well is not the same as answering it correctly, because the right
answer may be neither, or both, or a third thing the options obscured.

## The check

Keep it bounded, or it becomes paralysis and gets dropped.
Two writable artifacts, neither longer than a line:

1. **Before starting**, name the assignment's load-bearing premise and its
   falsifier: what has to be true for this work to be worth doing, and what
   observation would show it is not.
   Load-bearing means the work is wasted if it is false --- not merely that it
   is unverified.
2. **In the report**, name at least one thing in the assignment you checked.
   "The brief checked out" counts only when it says what was checked against
   what.

For a posed choice, add a third:
state what the options share before picking one.
An option set has a presupposition, and naming it is what makes rejecting it
possible; unnamed, it is simply the shape of the question.

The point of writing rather than considering is that a consideration cannot
fail.
This is [`algorithmatize-checks`](algorithmatize-checks.md)'s judgment residue,
so no instrument decides it --- but a sentence that names a falsifier is
checkable by a reader, and a resolution to be thoughtful is not.

- **Do:** write the assignment's load-bearing premise and its falsifier before
  starting work on it.
- **Do:** report the one thing you checked in the assignment, whether it held
  or not.
- **Do:** name what a posed choice's options presuppose, before answering
  within them.
- **Don't:** work around a wrong brief silently --- delivering something that
  quietly repairs the instruction reads as competence and leaves the error in
  place for the next reader.
- **Don't:** treat an assertion as verified because a convention document
  carries it; being written down is what makes a claim citable, not what makes
  it true.
- **Don't:** answer a choice as posed when its options share a false
  presupposition, and don't stall on the choice either --- say which
  presupposition fails and what follows.

## The limit

This is not a licence to relitigate every task before starting it, and a rule
read that way will correctly be ignored.
Most assignments are fine, the premise check usually confirms rather than
overturns, and confirming is a successful outcome rather than a wasted step.

The escalation is proportionate: a premise that is merely unverified gets a
line in the report, while one whose falsity would waste the work gets raised
before the work starts.
Where the assignment is sound, the whole cost is one sentence.

## The authoring side

Everything above is written for the recipient.
The author is the other half, and it is the half with no rule pointed at it.

The trigger gap is the same one this fragment opens with, running the other
direction.
[`metacognitive-monitoring`](metacognitive-monitoring.md) monitors claims as
they are composed and keys on claim type, and a sentence saying that a file
contains a phrase, that a rule lives at a path, or that N sites exist is a
**state** claim, which that rule says to re-query rather than recall.
That machinery is right and it never runs, because writing a brief feels like
*instructing* rather than asserting, so the premise reads as setup for the
task instead of as an assertion inside it.

Two properties already named above then make the brief the worst place for
such a claim to land.
It is self-contained by force, so nothing the agent can see contradicts it.
And it arrives as **authority**, which is exactly what the "Why nothing prompts
the check" section says makes adoption feel like compliance.

So the only detector is the recipient's own premise check, and that check is
discretionary.
An agent that runs it and pushes back is the good outcome rather than the
default one, which leaves a false premise in a brief resting on the diligence
of whoever receives it.

The remedy is cheap and it removes that dependency.
When a brief asserts corpus state, paste the query that derives it beside the
claim, or instruct the agent to verify the claim before acting on it.
Prefer the query: it costs one command, it settles the claim for the author
first, and it survives an agent who would otherwise have taken your word for
it.

Two neighbouring rules look like they already cover this, and neither does.
The stripping pass in
[`metacognitive-monitoring`](metacognitive-monitoring.md) is authoring-side
and asks of each element whether the task depends on it, so it removes the
claims the task does not need --- while a load-bearing premise is precisely
what stripping keeps.
[`derive-dont-enumerate`](derive-dont-enumerate.md) arrives at the same remedy
from a different failure: there the enumeration is true when written and rots
as the set grows, whereas here the premise is false at the moment it is
written and rots nothing.

- **Do:** run the deriving query before writing a claim about corpus state
  into a brief, and paste that query beside the claim.
- **Do:** instruct the agent to verify a premise you could not derive, and say
  which claim you mean.
- **Don't:** state a file's contents, a rule's location, or a site count from
  recollection because the sentence is an instruction rather than an
  assertion.
- **Don't:** rely on the recipient's premise check to catch it --- that check
  is discretionary, and your brief carries the authority that argues against
  running it.

**A claim about the recipient's *environment* is worse than one about corpus
state, and the remedy above cannot reach it.**
Everything in this section assumes the premise is derivable: its whole fix is to
run the deriving query and paste it beside the claim.
A claim about the agent's own environment --- the directory it starts in, the
repository that directory belongs to, the tools it was granted --- is not
derivable from the author's session at all.
There is no command you can run that reports it, so "check before asserting" is
not skipped here but *unavailable*.

That inverts the remedy rather than weakening it.
For a corpus claim the fix is to verify, then assert.
For an environment claim the fix is to **not assert**: name the target --- the
clone's path, the branch, the base --- and instruct the agent to establish its
own working directory, so the premise is settled in the one session that can
settle it.

The reason such a claim gets written anyway is that it does not arrive as a
claim.
"Work in the worktree you were given" reads as saving the recipient a step, so
it presents as a convenience rather than as an assertion about the world --- and
the claim-shaped tell this section relies on, a sentence saying a file contains
a phrase or a rule lives at a path, never fires on it.
Grammatically it is an instruction about where to work, which is exactly the
disguise the fragment's opening says an assignment wears.

Expect it most where the task is *least* like the session it is dispatched from.
A brief sent into another repository, another machine, or another toolchain is
the one whose environment the author has never seen, and it is also the one
whose environment feels safest to describe, because the description is doing the
work of orienting the agent.

- **Do:** name the repository, path, branch, or credential a dispatched agent
  should use, and tell it to establish that state for itself.
- **Do:** treat a convenience instruction about where or how the agent should
  work as a premise, since it asserts the environment is already in that state.
- **Don't:** assert anything about the recipient's environment that your own
  session cannot query --- the derive-and-paste remedy is unavailable, so the
  claim ships unchecked by construction.
- **Don't:** read "I could not have derived it" as an exemption; it is the
  reason to state a target rather than a state.

(Morrison-Lab/ai-config#1268, 2026-08-07: a session rooted in one repository
dispatched a UMS pass into a different one with `isolation: "worktree"` set, and
told the agent to work in "the git worktree you were given".
That worktree was a checkout of the *dispatching* session's repository, because
`isolation` is scoped to the session's primary repo --- so the instruction named
a state that did not exist and could not have been checked from the authoring
side.
The receiving agent caught it and built its own worktree in the target clone,
which is the discretionary detector the bullets above say not to rely on.
[`memories/git-worktrees.md`](../../memories/git-worktrees.md) carries the
measurement and the recovery.)

## Relationship to neighbouring rules

- [`metacognitive-monitoring`](metacognitive-monitoring.md) governs a premise
  stated as background fact, and the claims you generate yourself.
  This governs the instruction, which asserts nothing and so trips none of its
  four claim types.
  Its stripping pass is the nearest authoring-side rule, and the section above
  says why it does not reach a load-bearing premise.
- [`derive-dont-enumerate`](derive-dont-enumerate.md) also tells an author to
  hand over a query rather than an assertion, for a set that can grow while
  the work runs.
  That is staleness in something true; this is a premise that was never true.
- [`grep-is-not-coverage`](grep-is-not-coverage.md) is the same failure inside
  a single step: a real result, a sound command, and a conclusion that
  overreaches it.
- [`growth-mindset`](growth-mindset.md) challenges a **limitation** you
  believe you are under.
  This challenges a **task** you believe you are under.
- [`challenge-ambiguous-terminology`](challenge-ambiguous-terminology.md),
  [`challenge-redundant-content`](challenge-redundant-content.md), and
  [`challenge-unnecessary-complexity`](challenge-unnecessary-complexity.md) are
  review-side, applying to a diff or prose under review.
  This applies before any artifact exists.
- [`ardi`](ardi.md)'s "an instruction's own suggested code is not exempt" is
  the narrow case: a code snippet inside an issue, checked against project
  conventions before pushing.
  This is the general one, covering the prose directive that snippet sat in,
  at the start of the work rather than at its end.
- A companion rule on **posing** non-exclusive options as alternatives lives in
  [`avoid-false-dichotomies`](avoid-false-dichotomies.md); read that for the asking side and
  this for the answering side.
