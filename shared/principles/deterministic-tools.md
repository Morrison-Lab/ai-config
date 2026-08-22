Prefer deterministic, inspectable algorithms over model judgment ---
and where none exists, build one.
The goal is to write ourselves out of a job: every task we perform by
reading and deciding is a candidate to become a script whose output we
merely consume.

This is one principle with two faces, operating on different timescales.
They are not alternatives, and neither supersedes the other.

- **As a constraint**, binding right now, on the task in front of you:
  where a deterministic option exists, use it.
  Do not spend judgment on something a script decides.
- **As a goal**, directional, over time: where none exists, build it, so
  that next time the constraint is cheap to obey.

A session that honours only the constraint does the same manual work
forever, because no tool ever gets built.
A session that pursues only the goal builds tooling while deciding the
thing in front of it by hand.
Both faces, or neither works.

## Distinct from algorithmatize-checks

[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) is the
checks-shaped special case, and most of the argument for correctness and
cost already lives there.
Read it first; this principle extends it on two axes rather than
restating it.

**Scope.** That rule governs *verification*: never spend reasoning on a
check an algorithm can decide.
This one governs the work itself.
Counting, extracting, transforming, resolving a routine merge, composing
a status line, harvesting job output --- each is doing rather than
checking, and each is a candidate.

**Inspectability**, which that fragment never argues for.
A deterministic algorithm can be read before it runs, reviewed by someone
who does not trust its author, diffed across revisions, and re-run to the
same answer.
Model reasoning is none of those: there is nothing to review in advance,
no artifact to diff afterwards, and no guarantee the next run agrees with
the last.
That is a different argument from correctness or cost, and it is why a
hook beats a rule *even when the model would usually follow the rule* ---
the hook can be read, tested, and mutation-tested by someone who trusts
nothing about the model at all.

## It applies to every repo, not only the infrastructure

This is ordinary engineering practice that happens to have agentic
examples, not a rule about how agents should behave.
It governs the analysis and manuscript repos exactly as it governs the
CI and tooling ones.

A hand-run analysis step, a manually refreshed figure, a provenance claim
made from recollection, a validation someone eyeballs, a catalog verified
by reading --- each is the same shape as a hand-composed status line, and
each is a candidate.
"Automate everything" is a **direction**, not a completeness claim.

## The test: after doing it twice, the third time is a tool

The goal needs an observable trigger, or it stays aspirational.
Two occurrences establish that a task recurs rather than being a one-off;
the third is where building repays itself.

The trigger fires on *recurrence*, which is what keeps it from colliding
with YAGNI (see the [catalog](README.md)): a tool for something done once
is speculative generality, and the once-only case is exactly what YAGNI
governs.
The failure this test prevents is the opposite one --- doing the same
mechanical task eight times, each instance too small on its own to
justify a script, and never noticing the total.

Turn it inward from [`dont-reinvent-wheel`](dont-reinvent-wheel.md), too.
That principle says to search for an existing tool before building one.
This one says to leave a tool behind when your search finds nothing, so
the next session's search succeeds where yours failed.

## A follow-up question gets a hastier instrument than the main task did

The test above fires on recurrence across occasions, which leaves a gap
inside a single one.
An instrument built for the main task, correct and still at hand, routinely
goes unused when a follow-up question arrives minutes later, and the
follow-up gets a throwaway one-liner instead.

Nothing about the two questions justifies the gap.
They run over the same corpus and ask the same kind of thing, so the
instrument would have answered the second one directly.
What differs is only how each felt.
The main task's tool reads as infrastructure, while the follow-up reads as a
quick lookup, and a quick lookup does not feel like something that needs a
tool.

Perceived stakes are therefore doing the work, and they point the wrong way.
A follow-up question is usually asked in order to settle something, so its
answer feeds a recommendation, a disposition, or a report to a human, whereas
the main task's output goes on to be reviewed, tested, and revised.
The artifact built with the least care is thus the one most likely to be
acted on unchecked, and its error arrives dressed as a measurement.

The constraint face at the top of this fragment already forbids this: use the
deterministic option where one exists.
What it lacks is the moment at which to notice, and that moment is
observable.
**A question of the same shape as one an existing instrument already answers
is a second use of that instrument**, not a new problem.
Re-run it with different arguments rather than writing a fresh matcher for
the same corpus.

This is not the reuse
[`check-purpose-before-reusing`](../workflow/check-purpose-before-reusing.md)
warns about, and the boundary is worth stating because the two look alike:
same session, same artifact, built minutes ago.
That fragment governs reuse across a **purpose** boundary, and says a
recently self-authored template gets too little scrutiny.
This one governs reuse within a single purpose, and says a recently built
instrument gets too little **use**.
Run its check first, naming what the original was for and what the new
question is for.
Where those match, reuse is the answer rather than the risk.

**Read the scope an instrument prints, and compare it against the size you
expected.**
A printed denominator nobody checked is worth no more than one that was never
printed.
[`fail-fast`](fail-fast.md) makes the producer's half of this case at length,
in its rule that a check should report what it examined rather than only what
it found.
The consumer's half is the same number one step later: a range that stops
short of the population is right there in the output and gets read past,
because the finding beneath it is what the question was about.

- **Do:** re-run the instrument already built this session when a follow-up
  asks the same kind of question of the same corpus.
- **Do:** compare a printed examined-range or population count against the
  expected size before using the result beneath it.
- **Don't:** write a fresh throwaway matcher because the new question feels
  smaller; perceived stakes are not a property of the corpus.
- **Don't:** publish a scope figure a truncated scan produced as though it
  were the population's real size.

(2026-08-07, `UCD-SERG/serocalculator#635`: a fence-aware Quarto heading
scanner, written for the main task and used to drive a 15-file restructure,
was set aside minutes later for a follow-up question about how much one part
of the document used a concept.
The follow-up's fresh scan matched `^# ` with no fence tracking, so it stopped
at the first R comment inside a code chunk, covering 194 of the part's 538
lines.
It printed that truncated range, and the range went unread.
On that evidence the part was reported to hold a single passing mention of
the concept, and a proposed move was recommended against.
A fence-aware rescan found 5 mentions, one of them a named forward reference
in prose pointing 611 composed lines ahead, so the recommendation was the
opposite of correct.
`UCD-SERG/serocalculator#569` had already diagnosed the same thing, and it
surfaced only during the dupe check before filing a new issue.)

## Limits

Design, genuine judgment, and semantic work stay with a human or a model:
deciding what to build, weighing a tradeoff, reading whether prose is
clear.
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md)'s own
"Limits" section states the standard and should be read rather than
restated here, including its warning that an instrument with a mushy
threshold trains everyone to ignore it --- a bad tool is worse than the
judgment it replaced.

The difference this principle makes is in how that residue is framed.
It is the part **not yet** automated, shrinking as tools accumulate ---
not a fixed reserve that model reasoning owns by right.
That framing is the whole content of "write ourselves out of a job".

- **Do:** use the instrument that exists, rather than deciding by hand
  what it would decide.
- **Do:** build the instrument that does not exist, once the same
  judgment task has come up twice.
- **Do:** prefer the mechanism that can be reviewed before it runs, even
  where a rule would usually be followed.
- **Don't:** fall back to judgment merely because no tool is at hand ---
  that is the moment the goal fires.
- **Don't:** treat repeated manual work as acceptable because each single
  instance is small.
- **Don't:** automate a genuine judgment badly to satisfy the rule; a
  misfiring instrument is worse than none.

## Fix the class, not the site: route every call through one checked helper

When a review finds a defect that a *second* call site could reintroduce,
patching the sites the reviewer named leaves every future site free to
repeat it.
Routing all of them through one helper that performs the check narrows the
class, and the difference is observable: the raw primitive should appear
once, inside the helper, and nowhere else.
Read "one place the mistake could live" as the helper itself, never as a
tolerance for one stray call --- a stray call is a site the fix missed.

Two counts hide behind that sentence, and only the second is mechanical.
"How many call sites could still commit this defect" is a judgment about
reachability, and this file's own review list rejects an instrument
standing in for a judgment it cannot make.
What a script can count is the raw primitive the helper was built to
monopolize --- occurrences of `subprocess.run` in a file, of a bare
`open(`, of the unguarded API.
Ask the judgment question to decide whether the fix is structural, and
derive the primitive count to say where it stands.
If the primitive appears anywhere outside the helper, the fix went to a
site: one stray call is already an unguarded call site, not a margin.

A choke point narrows the class without closing it, so say which you
achieved.
The next author can still bypass the helper unless something asserts they
did not --- a test counting the raw primitive, a lint rule, or a
behavioural test that fails when an unguarded call is added.
Absent one of those, "one place the mistake could live" describes the
current revision and not an invariant, and the two claims are worth
different amounts.

This is the same instinct as the rest of this file, one scale down.
An instrument beats a rule because a rule can be forgotten.
A single choke point beats a repeated check for exactly that reason.

Two neighbouring rules cover what this one does not.
[`learn-from-review-findings`](../workflow/learn-from-review-findings.md)'s
recurrence section fires when the same finding class returns to a
*detector* that keeps almost working, and answers by replacing the kind of
evidence.
[`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s "safe
because X never happens" section fires when a second counter-example
refutes one ambiguity, and answers by searching for the general class of
counter-example instead of patching the instance.
The first asks whether the instrument is the right kind of thing; the
second asks how wide the defect is.
Both wait on a recurrence to tell them.
That file's "A fix for a defect class is where a fresh instance of that
class hides" is the closest relative of all, and the complement to this
one: it asks where the next instance will be and answers "the fix", where
this asks how many places could host one at all.
This one asks how many places can commit the defect, which a single diff
can answer before any recurrence --- though answerable is not answered,
and a class that reopens after a first fix is evidence that nobody asked.

Measured 2026-08-22 on
[ai-config#1932](https://github.com/Morrison-Lab/ai-config/pull/1932).
That PR added a `PreToolUse` guard and its test suite --- at the time of
writing they sit on its own branch rather than on `main` --- and every
function named below came from one or the other.
A timeout budget was enforced in `_rev_parse`.
Two helpers added later, `_git_config` and `_rev_parse_ref`, each ran
`git` on its own hardcoded timeout and read no deadline, so one path could
spend six unbudgeted subprocess calls --- eighteen seconds against a
ten-second `PreToolUse` timeout that fails **open**.
Patching those two would have left the next helper free to repeat it.
Every call was routed through one budgeted `_run_git`, leaving the guard
with a single `subprocess.run`, inside that helper.

How firmly that is held is worth stating, because the two counts land
differently.
`budget_cases()` asserts the budget behaviourally: it runs the bare push
--- the path with the most calls --- against a `git` shim sleeping a
second per call, and fails on any of four conditions: the hook
exiting non-zero, not denying, denying for a reason other than running out
of time, or elapsed passing 6.0 seconds against a 2-second budget.
The deadline is absolute, set once, so an unguarded call consumes the
budget instead of extending the run: elapsed tracks the larger of the
budget and the number of calls, and about six unguarded calls are needed
to pass 6.0.
Six is exactly the pre-fix shape, which the fixing commit's own
message recorded failing at 6.1 seconds.
So the test catches a wholesale reopening of the class and not one new
unguarded call, which is weaker than "the budget is enforced".
The structural count is asserted by nothing at all.

- **Do:** ask which call sites could still commit the defect to decide
  whether the fix is structural, and derive the primitive's count to say
  where it stands.
- **Do:** treat any occurrence of the primitive outside the helper as an
  unfinished fix, instead of counting to two.
- **Do:** prefer a choke point the next author must go out of their way to
  bypass over a check the next author must remember.
- **Do:** say whether the count is enforced or merely current, and name
  the assertion that would enforce it.
- **Don't:** patch the sites a reviewer happened to name --- they found
  the instances, not the boundary.
- **Don't:** claim a bypass is impossible when nothing tests for one.
- **Don't:** reach for a choke point when the defect genuinely has one
  site.
  `## Limits` above already says a bad tool is worse than the judgment it
  replaced.

## In review

Flag these with the same weight as the other principle-level findings:

- A hand-performed step that recurs in the same diff, or that the commit
  message says was done repeatedly, with no script proposed.
- A claim reported from reading or recollection where a one-line query
  settles it.
- A new rule written into prose where a hook, a CI step, or an assertion
  could decide the same thing mechanically.
- Two hand-written checks in one diff that ask the same question of the same
  corpus, where the second could have re-run the first.
- Conversely, a new instrument standing in for a judgment it cannot make,
  or built for a task with exactly one occurrence.
- A fix applied to the two or three call sites a reviewer named, where
  routing them through one checked helper would drop the unguarded count
  to zero.

(Directives from the user, 2026-07-30: "cai: minimize use of generative
ai in agentic work; maximize use of deterministic, inspectable algorithms
(like hooks)", then "cai: our goal in developing tools, like in all
programming work, is to write ourselves out of a job", "that goes for the
ai-tools repo and everything else we do"
(quoted as said; no repo of that name exists under any of our owners,
so read it as our AI tooling broadly, this corpus included),
"automate everything", and ---
correcting a framing that had set the two halves against each other ---
"it's both a constraint and a goal".
From a session with three judgment tasks done repeatedly by hand: a
`DESCRIPTION` version conflict resolved at least eight times with
identical logic, a PR status line composed from `gh pr checks` output and
once reported from a reading that predated its own pushes, and an ad-hoc
pre-push sweep run in a different order each time, which is why two of
its checks missed things.)
