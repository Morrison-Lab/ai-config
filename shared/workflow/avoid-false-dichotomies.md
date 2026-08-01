Avoid false dichotomies.
When laying out alternatives --- in a question to the user, a design
note, a PR description --- test whether they are actually exclusive
before presenting them as such.
Frequently several can be true, or chosen, at once.

## The tell: an answer of "both"

The signal is unmistakable and arrives after the fact: a question posed
as either/or, answered with "both".
When that happens, the exclusivity was constructed by the person asking.
Nothing about the underlying work forced a choice.

The mechanical half is worth naming, because it explains why this is a
default rather than a judgment failure.
The `AskUserQuestion` tool carries a multi-select option, and it is off
unless set --- so presenting options as mutually exclusive is simply
what happens when nobody decides otherwise.
A long session can pose a dozen single-select questions without one
deliberate choice to make any of them exclusive.
(Confirm the current field name against the tool's own schema before
relying on it; it is not documented in this corpus.)

That reframes the rule: it is not "consider whether both apply", which
is weak and easy to feel you have done.
It is "you are shipping a default; decide it".

## The check

Before presenting alternatives, state **what would be lost by taking
more than one**.

- If the answer is *nothing*, they are not alternatives.
  Either enable multi-select, or present them as composable steps with
  an order ("relabel now, restructure after").
- If the answer names a real cost --- they contradict, they cannot
  coexist in one file, doing both wastes the work of one --- then the
  choice is genuine, and posing it as a choice is correct.

Writing that sentence is the whole discipline.
It converts an unexamined default into a decision, which is the only
part that was ever missing.

## The limit

Genuinely exclusive options exist, and presenting those as combinable is
its own error: two incompatible designs, a merge strategy, a name, a
schema for one field.
Offering "both" there produces an incoherent result and pushes the real
decision back to the person who asked.

What this rule targets is the **unexamined** default, not the act of
choosing.

## Distinct from asking one question at a time

`CLAUDE.md`'s "Present decisions one at a time" constrains **how many
questions** to pose in a message, and says to rank by how blocking each
is and pose only the top one.
This rule constrains **how the options within one question relate**.

They are easy to conflate and they compose cleanly: ask one question,
and let that question's options be non-exclusive when nothing makes them
exclusive.
Neither licenses relaxing the other --- a single question with falsely
exclusive options is still a false dichotomy, and three well-formed
multi-select questions in one message is still a batch.

- **Do:** state what would be lost by taking more than one option, before
  presenting them as alternatives.
- **Do:** offer composable options as steps with an order when they
  simply sequence rather than compete.
- **Don't:** ship single-select as an unexamined default in a tool that
  offers multi-select.
- **Don't:** present genuinely incompatible options as combinable, which
  hands the real decision back to the asker.

(Corrected 2026-07-30: "cai: avoid false dichotomies; when considering
alternative options, consider whether multiple of them could be
true/chosen at once."
Three single-select questions in one session were answered "both": a
mislabelled estimand posed as fix-the-prose / change-the-estimand /
report-both, where the third was framed as a compromise rather than as
simply doing the first two; a calibration anchor posed as SEER incidence
or the cohort's own observed rate, answered "I think we should consider
both"; and a figure fix posed as relabel-now versus restructure-later,
answered by doing the first and then, minutes later, the second.
In each case the exclusivity was constructed, and multi-select was never
once set in that session.)
