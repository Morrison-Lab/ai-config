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

## In review

Flag these with the same weight as the other principle-level findings:

- A hand-performed step that recurs in the same diff, or that the commit
  message says was done repeatedly, with no script proposed.
- A claim reported from reading or recollection where a one-line query
  settles it.
- A new rule written into prose where a hook, a CI step, or an assertion
  could decide the same thing mechanically.
- Conversely, a new instrument standing in for a judgment it cannot make,
  or built for a task with exactly one occurrence.

(Directives from the user, 2026-07-30: "cai: minimize use of generative
ai in agentic work; maximize use of deterministic, inspectable algorithms
(like hooks)", then "cai: our goal in developing tools, like in all
programming work, is to write ourselves out of a job", "that goes for the
ai-tools repo and everything else we do", "automate everything", and ---
correcting a framing that had set the two halves against each other ---
"it's both a constraint and a goal".
From a session with three judgment tasks done repeatedly by hand: a
`DESCRIPTION` version conflict resolved at least eight times with
identical logic, a PR status line composed from `gh pr checks` output and
once reported from a reading that predated its own pushes, and an ad-hoc
pre-push sweep run in a different order each time, which is why two of
its checks missed things.)
