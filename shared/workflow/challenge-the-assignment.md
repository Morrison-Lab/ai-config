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

## Four shapes, in rising order of how settled they look

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

**A supplied measurement.**
A brief can hand over a number rather than a claim or an instruction ---
"four POSTs, HTTP 200, zero reviews resulted" --- offered as the evidence a
conclusion already rests on.
This looks the most settled of the four, because it arrives with a count
attached, and a count reads as having already been checked.
It has not: the number is real, but the measurement can carry a confound the
person who ran it never saw, because seeing it required knowing something the
measurement itself does not show.
`POST /pulls/{n}/requested_reviewers` returning HTTP 200 rather than the
success code is itself evidence the PR was already merged or closed when the
call ran, and adds nobody --- so "four POSTs, HTTP 200, zero reviews
resulted" is not evidence that requesting a reviewer buys nothing; it may be
evidence that the four PRs were no longer open.
The confound was invisible to whoever ran the measurement because seeing it
required knowing what the status code encodes, which the count itself does
not show.
Re-deriving the measurement, not just re-reading it, is what a supplied
number needs before it can settle anything --- check each PR's state at the
time the call ran, not just the aggregate count.

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

For a supplied measurement, add a fourth: name what would have to be true
about *how it was taken* for the number to mean what the brief says it
means, and check that rather than the number itself.

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
- **Do:** re-derive a supplied measurement --- check the conditions under
  which it was taken --- rather than accepting the number and reasoning only
  from it.
- **Don't:** work around a wrong brief silently --- delivering something that
  quietly repairs the instruction reads as competence and leaves the error in
  place for the next reader.
- **Don't:** treat an assertion as verified because a convention document
  carries it; being written down is what makes a claim citable, not what makes
  it true.
- **Don't:** answer a choice as posed when its options share a false
  presupposition, and don't stall on the choice either --- say which
  presupposition fails and what follows.
- **Don't:** treat a supplied number as settled because it arrived with a
  count attached --- a count that is real can still carry a confound the
  measurer never saw.

See [`challenge-the-assignment.cases.md`](challenge-the-assignment.cases.md),
"A supplied measurement carried a status-code confound" and
"A run-level conclusion stood in for a job-level one".

## When the work itself settles the premise, run it before writing anything

The check above costs a sentence, which is what makes it affordable.
One shape makes it cost nothing at all, and it is the shape most likely to be
skipped: an assignment to **widen an instrument's coverage**, carrying an
incidental claim about what the widened coverage will find.

The claim is unverifiable *by construction*, and the assignment says why.
An issue reporting that a checker does not scan some tree cannot also know
that tree is clean, because the instrument that would establish it is the
thing being asked for.
So its clean-state claim rests on a hand scan --- which is exactly the
substitute the whole issue exists to retire.

Two things keep it from being questioned.
It is **incidental**: it sits beside the request rather than in it, so nothing
about deciding to do the work requires reading it.
And it is **reassuring** --- "a missing guard rather than an outstanding
breakage" narrows the scope and lowers the stakes, and a premise that makes a
task smaller draws less scrutiny than one that makes it bigger.

The cost is not a wasted task, which is what "The check" above is calibrated
for.
The work is right either way.
What the claim spoils is the **report**: inherit it and the PR ships framed as
coverage-only, so a real defect the change surfaced goes out described as
nothing found.

Ordering is the whole remedy, and it is free.
**Run the widened instrument before writing the PR body, the changelog, or the
commit message** --- not to check the premise as a separate step, but because
the first run answers it as a side effect.
Then report what it actually returned.

- **Do:** run a coverage-widening change and read its output before writing
  any prose that describes what the change found.
- **Do:** treat a defect the widened instrument surfaces as in scope, per
  [`dont-incur-technical-debt`](../principles/dont-incur-technical-debt.md) ---
  leaving it puts the newly-added check red on the default branch.
- **Don't:** carry an issue's "currently clean" claim into a PR body; the
  issue could not have checked it, which is why the issue exists.
- **Don't:** read the claim's reassuring direction as making it safer to
  inherit --- a premise that shrinks the task is the one nobody re-derives.

(`Morrison-Lab/ai-config#763` -> `#1454`, 2026-08-13: the issue reported that
`scripts/check-links.py` did not scan `memories/`, and added "All 26 resolve
today, so this is a missing guard rather than an outstanding breakage."
Adding the glob and running the script found a real broken link on the first
run --- `memories/preferences.md` pointed at `shared/workflow/ardi.md`, which
resolves relative to that file as `memories/shared/workflow/ardi.md` and does
not exist, while the other 80 links from `memories/` into `shared/` already
used the `../` form.
The issue's own repro command is the tell: it reported 683 links across 405
files, figures only the un-widened script could produce, so the scan behind
"all 26 resolve" was never the scan the issue was asking for.)

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
- **Do:** paste the query's *output* as well as the query, and check that the
  claim you wrote is the one that output settles rather than one inferential
  step past it.
- **Don't:** state a file's contents, a rule's location, or a site count from
  recollection because the sentence is an instruction rather than an
  assertion.
- **Don't:** rely on the recipient's premise check to catch it --- that check
  is discretionary, and your brief carries the authority that argues against
  running it.
- **Don't:** hand over the conclusion in place of the measurement --- the
  recipient cannot re-derive a number you did not supply, so the check this
  fragment prescribes for a supplied measurement has nothing to run on.

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

**A fact you leave OUT is the other failure, and it is quieter than a false one
--- a missing premise leaves a standing rule looking satisfied.**
Everything above governs what a brief **asserts**: verify it, or where the
premise is not yours to verify, name a target and let the agent settle it.
Nothing governs what a brief **omits**, and omission is the half that reaches a
standing rule.
A false premise usually breaks something, so it surfaces.
A missing one changes nothing the agent can see, so the agent follows the rule
correctly, gets a success back, and stops.

The class that matters is a **repo-level** fact on which a standing rule's
satisfiability depends.
Note it sits outside both halves above.
It is not an environment claim, because you *can* derive it --- it is a file in
a repository both parties can read --- so the "not derivable, therefore name a
target" remedy does not apply.
And it is not a corpus-state claim you got wrong, because you never made a claim
at all.

The review-trigger class is the worked instance.
[`pr-on-claim`](pr-on-claim.md) already says that requesting Copilot discharges
nothing where a repo's own reviewer runs on `workflow_dispatch` alone, and that
the `Stop` hook cannot catch it.
That rule is written for whoever opens the PR, and it fails silently when the PR
is opened by a dispatched agent --- not through carelessness.
The agent follows the standing "request the external reviewer in the same
stride" instruction, calls `request_copilot_review`, gets a success, and stops,
because nothing in that instruction says to go read the repo's review workflow's
`on:` block and the agent has no reason to suspect the repo is unusual.
The PR then goes green with no reviewer having looked, which is
indistinguishable on the board from a reviewed one.

So before dispatching an agent to open a PR, state the repo's review-trigger
class --- auto on `pull_request` versus dispatch-only --- and, when it is
dispatch-only, the exact dispatch call, including that its `ref` must be the PR
branch rather than the default branch.
The general test is cheap: for each standing rule the agent will invoke, ask
whether this repo makes it satisfiable, and supply whatever the answer depends
on.

- **Do:** state the repo's review-trigger class in any brief that will have an
  agent open a PR, and give the dispatch call when the reviewer is
  dispatch-only.
- **Do:** ask which standing rules the brief's task will invoke, and supply the
  repo-level facts their satisfiability turns on.
- **Don't:** treat a fact as the recipient's to derive merely because it is
  derivable --- the question is whether anything would prompt them to look.
- **Don't:** read a brief carrying correct environment facts as complete; those
  are the facts the agent could not get, not the facts it will not know to
  seek.

(2026-08-16, the brief that produced `Morrison-Lab/ai-config#1534`.
Read that number as naming the brief's own artifact and nothing further: #1534's
own subject is a reviewer's replacement diffstat, so a reader following it finds
no trace of the omission described here, and no issue or PR records the incident
itself --- this entry is the whole of it.
The brief carried every environment
fact the agent could not query --- clone path, `gh` absent from `PATH`,
GitHub MCP tools as the only working client, the branch name --- and omitted the
review-trigger class.
The agent requested Copilot and reported the PR ready; no review had been
scheduled.
It was caught only because the dispatching session read
`.github/workflows/claude-review.yml`'s `on:` block itself and dispatched the
run, which then returned a clean verdict.
`Lacaedemon/sparta` fires its review automatically on `pull_request`, so the
identical brief would have been fine there --- which is exactly why the fact is
repo-level and has to be stated rather than assumed.)

**A prose disclaimer does not neutralize a supplied command that encodes the
assumption it disclaims.**
The section above prescribes naming the target and letting the agent establish
its own state, and a brief can follow that prescription in prose and still ship
the false premise --- because the prescription governs what the brief *says*,
and a brief also *supplies* things.
A runnable command is the second channel, and it is the one carrying the
assumption.

The disclaimer makes this worse rather than neutral, which is the part worth
stating.
The section above describes a convenience instruction that presents as a
convenience rather than as an assertion, so nothing marks it as a claim.
Here something does: the prose names that exact hazard, in as many words, one
line above the command embodying it.
That sentence is the only signal that would have sent the author looking, so
spending it is what leaves the command reading as already checked --- the
partial-guard trade [`fail-fast`](../principles/fail-fast.md) prices, arriving
through the artifact written to demonstrate care.

Which channel wins is not the recipient's judgment call.
Prose is read once and a command is pasted, so the assumption reaches execution
whatever the surrounding sentence says.
So read every command in a brief as an assertion about the recipient's
environment, and ask what would have to be true for it to run.

**A `||` fallback is how such a command passes as self-establishing, and the
fallback is itself an untested command.**
A brief's author reaches for one to guarantee a value, so what it produces is
the claim they are least likely to check --- and it is checkable in one line.

The measured behaviour, which is not what the author of the brief below
believed:

| form | `DEF` |
|---|---|
| `DEF=$(false \|\| echo main)` | `main` |
| `DEF=$(false) \|\| echo main` | *empty* |
| `DEF=$(false \| sed s/x/y/ \|\| echo main)` | *empty* |
| the same, under `set -o pipefail` | `main` |

Only the first supplies the literal.
In the second the `||` sits outside the substitution, so `echo` writes to stdout
and nothing reaches `DEF`.
In the third --- the form the brief actually carried --- the pipe discards the
failing command's status, `sed` exits 0 on empty input, and the fallback never
fires at all, which is
[`errexit-is-not-uniform`](../coding/errexit-is-not-uniform.md)'s "a pipe
discards the status of everything left of it".

So the fallback written to guarantee a value was **inert**, for a reason its
author had not considered, and would have left `DEF` empty.
The lesson is not that a guessing fallback is worse than an erroring one.
It is that neither behaviour was established: a fallback nobody ran is a belief
about control flow, and this one was wrong twice over.

The same holds for the `git worktree add` chain beside it.
Two forms joined by `||` read as defensive while both rested on one false
premise, so the chain enumerated two states when the real one was a third ---
a fallback varying on the wrong axis, which covers nothing however many
branches it has.

Resolve what a supplied command needs from a source that answers, and fail
loudly when it does not:

```bash
DEF=$(git remote show origin | sed -n 's/.*HEAD branch: //p')
[ -n "$DEF" ] || { echo "cannot resolve default branch" >&2; exit 1; }
```

- **Do:** read every command you put in a brief as a claim about the
  recipient's environment, and either drop it or make it self-establishing.
- **Do:** run a fallback before shipping it, and check what it assigns rather
  than what you intended it to assign --- one line settles it, and both forms
  above were wrong.
- **Do:** end a resolution step with a loud failure rather than a guessed
  default, so an unmet premise stops the agent instead of reaching execution.
- **Don't:** treat a "do not assume" sentence as covering the command beneath
  it --- the disclaimer is spent on the reader, and the command still runs.
- **Don't:** read a `||` chain as defensive without asking whether its branches
  differ on the axis that can actually fail; two forms sharing one false premise
  cover nothing.
- **Don't:** reason about where a `||` binds, or about whether a pipeline
  propagates a failure --- both are one command to test and both were guessed
  wrongly here, in a section about not guessing.

See [`challenge-the-assignment.cases.md`](challenge-the-assignment.cases.md),
"A brief's own command contradicted its own disclaimer".

**A brief you re-send each round carries a measurement, and the measurement
expires while the sentence does not.**
Both sections above fail because the author never derived the claim, or could
not.
This one fails after the derivation succeeded.
The author ran the check, got a real result, wrote it into the brief, and then
sent that brief again the next round and the round after, with nothing
re-testing it in between.

Note the rule does not need to know whether the result expired or was wrong to
begin with, and in the worked case that stayed unsettled.
Either way the brief asserted it every round on the strength of one reading,
and being unable to tell the two apart afterwards is itself the argument for
re-testing.

The claim type that expires is a **capability**: whether a reviewer is
reachable, whether a token can dispatch a workflow, whether a host answers.
Each is a property of a moment rather than of the world, so a correct reading of
one is a timestamp with a value attached, per
[`timestamp-volatile-claims`](../writing/timestamp-volatile-claims.md).
Restating it a round later keeps the value and drops the timestamp.

Recurrence is what turns that into a premise.
A brief restating what an earlier round established reads to every later round
as setup rather than as a claim, so the questioning this fragment asks for never
fires.
Author and recipient are also the same party here, which is the strongest form
of the authority the "Why nothing prompts the check" section describes.

**The sharp case is a brief that forbids the retry that would refute it.**
A step reading "If still nothing, do NOT re-post the request" is not
merely a brief failing to re-check.
It instructs the next round not to, so the falsifying action is ruled out by the
same document that asserts the thing it would falsify.

**More rules do not fix this, because the rule was already there.**
[`self-review-fallback`](self-review-fallback.md) says to re-check reachability
every round, and that a reviewer ineligible a few pushes ago can become
reachable mid-session.
That rule was loaded and was defeated by a brief restating the blocker as
settled, so what failed was not coverage but a mechanism that suppresses
coverage.
Read a recurring brief as a thing capable of switching off rules you already
hold.

The remedy is to carry the query rather than its answer.
State a blocker in a recurring brief as a command to re-run, with the time the
last result was taken, so each round re-measures instead of inheriting.
That is [`derive-dont-enumerate`](derive-dont-enumerate.md) applied to a
capability rather than to a set, and it belongs here because the author is the
one who has to write it that way.

- **Do:** write a recurring brief's blockers as a command to re-run each round,
  timestamped with when it last ran.
- **Do:** treat a step telling the next round not to retry something as the tell
  that the brief has closed a question it should hold open.
- **Don't:** restate an earlier round's finding as an established gate in the
  next round's prompt.
- **Don't:** read a rule you already hold as protection --- a brief asserting
  the blocker settled is what stops that rule running.

See [`challenge-the-assignment.cases.md`](challenge-the-assignment.cases.md),
"A recurring brief re-asserted a blocker nobody re-tested".

**A follow-up message is a brief, and it is the higher-risk one --- the guard
covered only the opening one until 2026-08-20.**
The section above and the rest of this fragment describe a premise inside the
brief that *starts* an agent's work.
`hooks/remind-brief-premises.py` mechanizes exactly that, and it worked: it
fired on an `Agent` launch and got the launch brief's one corpus claim verified
before the work began.

The claim that was actually wrong went by a different channel.
It arrived as a `SendMessage` to the already-running agent, and the hook's
tool-name gate accepted `Agent` and `Task` only, so nothing looked at it.

Note which way the risk runs, because it is the opposite of what the coverage
assumed.
A follow-up message is where **corrections and new premises** land --- it exists
to change what the recipient believes --- so a false claim in one does not merely
go unchecked, it *displaces* something the recipient may already have verified,
and it arrives with the sender's authority freshly attached.
The opening brief is read by an agent with no context and every reason to
question it.
A mid-flight correction is read by an agent that has already accepted the
sender as a reliable narrator.

The rule was in force and correct throughout.
What failed was its coverage, so the fix is coverage rather than a new rule:
the guard now reads `SendMessage`'s `message` field alongside `Agent`/`Task`'s
`prompt`, and `hooks.json` binds all three matchers.
Registration is half of that --- widening the script without widening the
matcher would have changed nothing, and the `Task` branch had in fact been
unreachable the whole time for exactly that reason.

- **Do:** apply this fragment's premise check to a follow-up message you send,
  not only to the brief that opened the task.
- **Do:** re-derive a claim before sending it as a correction, since a
  correction is trusted more than the thing it corrects.
- **Don't:** treat a guard's silence as coverage without checking which tools
  its matcher actually binds.
- **Don't:** read "the rule exists and I follow it" as sufficient --- both were
  true here, on the channel the mechanism did not watch.

(Morrison-Lab/ai-config#1795, 2026-08-20.
A coordinator's follow-up message asserted that this repo's local check does not
predict its own CI, and instructed filing an issue on that basis.
It does predict it: [`semantic-line-breaks`](../writing/semantic-line-breaks.md)
already documents the runnable `gha` gate, which reproduced CI's failure verbatim
on `bb533295` and passed on `5643a872`.
The same message's other half was right, and is the reusable part --- the belief
that `scripts/semantic-line-breaks.py --write` is the pre-push gate was wrong in a
way that bites: before #2085 the script had no width policy, so it joined
hand-wrapped sentences and manufactured the long-line-with-a-semicolon
violation the CI gate rejects, which is how three commits failed that check
in one day.
After #2085 the reformatter consumes the gate's `classify_line`, so that
particular manufacture is gone.
The script is still not the diff-scoped job.
That fragment's own Don't pair already said not to treat it as the check CI runs.)

**An issue body is an assignment you author, and its proposed fix is a second
claim the brief case does not carry.**
This fragment's opening already names an issue body among the assignments a
**recipient** must challenge.
Everything in this section is written for a brief, though, so nothing here
fires when the artifact you are writing is an issue --- and an issue is the
worse case on every property the section leans on.
It is self-contained by force, like a brief.
It arrives as authority, like a brief.
And it outlives the session that wrote it, so its reader is a stranger or a
later you, with no conversation left to contradict it.

The derive-and-paste remedy transfers unchanged.
What does not transfer is the shape of the damage, because an issue body
carries something a brief usually does not: a **proposed fix**, whose
sufficiency is computed from the state claim above it.

So a wrong count does not merely make one sentence false.
It makes the proposal unable to produce the outcome the issue's own
motivation section promises, while every sentence stays individually
defensible --- the state claim is a sincere report of what the author found,
and the fix does address the problem as stated.
A reader checks the fix against the stated problem, and it passes.
The gap sits between the stated problem and the real one, and nothing inside
the issue exposes it.

The check is one question, asked before filing: does the sufficiency of what
I am proposing depend on a count, a set, or an enumeration?
When it does, derive that set with a command and paste the command, per the
bullets above.
[`derive-dont-enumerate`](derive-dont-enumerate.md)'s "A helper's call sites
are a subset of the effect's sites" covers how such a set gets undercounted
while looking complete.

- **Do:** apply this section's derive-and-paste rule to an issue body, not
  only to a brief handed to an agent.
- **Do:** ask whether the proposed fix's sufficiency turns on the count you
  just asserted, and derive that count before proposing.
- **Don't:** read an internally consistent issue as a checked one ---
  agreement between a problem statement and its own fix says nothing about
  either against the world.

([`Morrison-Lab/gha#778`](https://github.com/Morrison-Lab/gha/issues/778),
2026-08-31.
The issue was filed stating that `claude.yml` has three review-dispatch sites
and proposing an input that would gate one of them.
It has four, verified by grepping `gh workflow run` over that file at
`838011e`, so the proposed input would have left the fourth dispatching, and
the issue's own "Why it matters now" section promised an on-request-only
reviewer that its proposed fix could not deliver.
An [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) subagent found it;
the author had already read the same file twice without finding it.)

## Relationship to neighbouring rules

- [`metacognitive-monitoring`](metacognitive-monitoring.md) governs a premise
  stated as background fact, and the claims you generate yourself.
  This governs the instruction, which asserts nothing and so trips none of its
  five claim types.
  Its stripping pass is the nearest authoring-side rule, and the section above
  says why it does not reach a load-bearing premise.
- [`derive-dont-enumerate`](derive-dont-enumerate.md) also tells an author to
  hand over a query rather than an assertion, for a set that can grow while
  the work runs.
  There the claim was true when written and the set grew past it; here the
  author either never derived it, could not, or derived it once and never
  re-tested it.
- [`grep-is-not-coverage`](grep-is-not-coverage.md) is the same failure inside
  a single step: a real result, a sound command, and a conclusion that
  overreaches it.
- [`growth-mindset`](growth-mindset.md) challenges a **limitation** you
  believe you are under.
  This challenges a **task** you believe you are under.
- [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)'s
  "A constraint your own change authored is not evidence against an upstream"
  is one narrow instance, and the one where the premise check is hardest to
  reach: the constraint is real, verified against a file, and still not a
  reason, because the change being justified is what created it.
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
