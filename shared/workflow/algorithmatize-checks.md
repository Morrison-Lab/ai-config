Never spend LLM reasoning on a check a deterministic algorithm can decide.
Whenever a verification, measurement, or classification step is decidable by
computation over data that is available (or cheaply instrumentable), build or
run the instrument and let the model consume its verdicts --- reserve model
judgment for the genuinely semantic remainder.

An LLM eyeballing a log, a diff, a state dump, or a rendered frame for a
property that has a numeric definition is the tell. The model's judgment on
such a check is slower, costlier, and less reliable than the two lines of
arithmetic that decide it exactly --- and unlike the model's read, the
instrument's verdict is reproducible, diffable across revisions, and wireable
into CI so the check runs on every change instead of only when someone thinks
to look.

## The procedure

1. **Name the property being checked.** If it has (or can be given) a precise
   definition over available data --- a threshold, an invariant, an expected
   state at a time, a comparison against a reference --- it is algorithmatizable.
2. **Check the data already exists** (a log, a transcript, an API field, a
   debug dump). If not, ask whether the system can be cheaply instrumented to
   emit it --- adding a machine-readable dump of internal state is usually a
   small, safe, render-only change, and it pays off on every future check.
3. **Write the instrument once, as a tool** (a script in the repo, a CI step),
   not as an inline throwaway --- the second use is where the payoff is.
   Thresholds come from the system's own constants, not magic numbers.
4. **Wire it to where the change happens** (CI on every PR, a pre-push check)
   so the check runs without anyone --- human or model --- remembering to run it.
5. **Let the model consume verdicts, not raw data.** The LLM's role shrinks to
   the semantic residue: is this legible, is the intent right, does the prose
   match --- plus deciding what new instruments are worth building.

## Tells that a check you're doing manually should be an instrument

- You (or a reviewer) re-derive the same numbers by hand on more than one
  occasion --- spacing, speeds, timings, counts, deltas.
- A review checklist item has words like "within", "never exceeds", "stays
  constant", "by tick/step/line N", "matches the reference".
- You compare two versions of an artifact and classify the differences by
  reading both --- when a metric computed on each side would classify most of
  them mechanically.
- A defect was caught by eye that a threshold over dumped state would have
  caught earlier and every time thereafter.
- You are about to write "the only X this could affect is Y" --- see the next
  section, which is that tell in its most reportable form.

## Never predict which case will fail; enumerate the class

The rule so far concerns checks you *perform*.
It has a second form that reaches further, because it survives into what you
*say*: predicting which member of a class will fail, in place of running the
enumeration.

The shape is a sentence like "the only new word this could flag is
`monotonicity`", or "the one file this could break is the parser".
It reads as the output of an analysis.
It is the output of an intuition, and the giveaway is that no command was run.

**A guess in a report is worse than reporting nothing**, which is why this is
worth a section of its own rather than a bullet.
Naming a single member implies the others were examined and cleared, so a gap
that is total gets recorded as narrow and understood.
The next reader --- often you, later --- then spends attention on the named
case and none on the rest.

So ask whether the class is enumerable by a command.
Usually it is, and usually the command needs less than the guess did: no
dictionary, no installed package, no network, just a pattern over the diff.
When it genuinely is not enumerable, say the class is unbounded and the check
did not run.
An honest "unverified" is worth more than a confident member, because it
leaves the gap the size it actually is.

Watch for the specific slip where sound reasoning about a **category** is
cashed in as a prediction about a **member**.
"CI's dictionary is more permissive than the local one" can be well evidenced
and still license nothing about which word will fail --- those are different
claims, and only the first had support.

- **Do:** enumerate with a command, and report what it examined.
- **Do:** say a check could not run, and name the class it would have covered.
- **Don't:** substitute "the only one that could fail is X" for running the
  check.
- **Don't:** let a supported claim about a category carry an unsupported one
  about a member.

(2026-07-31, `ucdavis/bcs#503`: a spelling check could not run locally, and the
status report named `monotonicity` as the only newly-reachable word.
`monotonicity` passed; `unlabelled` failed --- a British spelling in prose
written minutes earlier.
A three-line pattern scan over the diff, needing nothing installed, then found
`unlabelled` **and** `neighbours` in one pass.
The user's correction was "no guessing".)

## Test the instrument against the incident that prompted it, verbatim

Building an instrument in response to a specific failure is the usual path
into this rule.
When that is why it exists, the incident's **exact input** is test case
number one -- pasted in unaltered from wherever it was reported, not retyped
and not tidied.

Expect the first draft to fail it.
That is the whole reason to write the test, and it is worth saying plainly
because the failure feels impossible from the inside: you have just finished
designing against that very case.

You do not design against the incident, though.
You design against your **summary** of it, and the summary is what made the
rule statable in the first place -- so the abstraction that let you write the
guard is the same one that lets the guard miss.
The real input carries an env-var prefix, an assignment, a `;`, a wrapping
quote.
The summary carries none of those, and neither does the matcher.

Write the negative cases in the same pass, since a guard that blocks too much
gets switched off and then protects nothing.
Mentioning a thing is not doing it: a `grep` for the gated command, an `echo`
of it, and a doc quoting it all have to pass.

**Treat a comment claiming the matcher's scope as an untested assertion.**
A comment beside a regex saying it "only matches at the start of a command"
sits exactly where a reviewer stops asking, and it was written by the same
mental model that wrote the regex -- so the two agree with each other and
neither is evidence.
Only a test separates them.

This is the guard-shaped case of [`ardi`](ardi.md)'s rule that a regression
test must be seen to fail before it is believed.
The gap runs the other way here: there the test encodes the bug as intended
behaviour, while here the test is the only thing that can catch the mismatch
between the incident and your memory of it.

- **Do:** make the reported input test case number one, copied literally.
- **Do:** test that mentions, greps, and quotes of the gated command pass.
- **Don't:** validate a matcher by reading it -- a wrong one reads as correct.
- **Don't:** trust a comment describing what the pattern cannot match.

(2026-07-31, a guard against running heavy R jobs on a cluster's head node:
the reported command was
`R -e 'Sys.setenv(NOT_CRAN="true"); res <- devtools::test()'`.
Splitting on `;` left a fragment leading with `res` rather than an
interpreter, so the one command the hook existed to stop was the one it let
through.
A second bug in the same file had a comment asserting that a leading anchor
kept bare mentions from matching, which it did not -- `grep -rn
'devtools::test'` was blocked.
Neither surfaced from re-reading the code.
Both surfaced from tests, and the first only from the test that pasted the
reported line in unaltered.)

## Limits

The rule targets *decidable* checks. Judgments of legibility, intent,
aesthetics, and prose accuracy stay with a human or model reviewer --- but even
these often decompose into a decidable core plus a smaller judgment (declare
the intended outcome as data, assert it mechanically, and review only the
framing). Prefer shrinking the judgment surface over automating a judgment
badly: an instrument with a mushy threshold that misfires trains everyone to
ignore it.

This generalizes the narrower habit of turning repeated manual verifications
into CI checks: that is the CI-shaped instance; this rule also covers one-off
investigations, review procedures, and any place model reasoning substitutes
for arithmetic. It is a different axis from multi-agent orchestration
([`when-to-orchestrate`](when-to-orchestrate.md)): orchestration parallelizes
model reasoning across subagents, while this rule removes model reasoning from
checks that never needed it --- apply this rule first, then orchestrate
whatever judgment remains.

## Apply this to writing a memory bullet, not just to runtime checks

The rule targets checks a system performs, but a UMS/memory bullet that
documents *how to tell X from Y* is itself a check --- and the same
tell applies: don't write down whatever fuzzy method you happened to use
live in the moment (eyeballing wording, matching timing) without first
asking whether a mechanical signal already exists in the data. Drafting a
memory is a natural moment to *notice* an available instrument even when
none was used at the time --- go back and check before finalizing the
bullet, the same way a reviewer would flag a manual check that should be
automated. (`ai-config#688`: a first-draft bullet on detecting self-echoed
PR replies said to match body text and timing --- both fuzzy --- when
every reply already carried a mechanical, unambiguous marker, the Claude
Code attribution footer, sitting unused in the same data. Caught only when
asked directly why the sharper signal hadn't been the first idea.)
