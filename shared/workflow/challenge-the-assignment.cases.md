# Case records: challenge-the-assignment

Worked-example case records for the rules in
[`challenge-the-assignment.md`](challenge-the-assignment.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "The authoring side" --- an unqueried brief premise

(2026-08-04, this fragment's own subject: a brief asserted that `CLAUDE.md`
carries a review-quota carve-out phrased as "`total_cost` 0 at `num_turns` 1",
written from recollection and never queried.
`grep -nE "total_cost|num_turns" CLAUDE.md` returns nothing, and
`git grep -n 'total_cost` 0 at' -- '*.md'` returns exactly one hit,
`shared/workflow/review-verdict-pitfalls.md:29` (moved there from
`fully-clean.md` per ai-config#1236), which is where that carve-out actually
lives.
`CLAUDE.md`'s quota material is about a bot comment stating that the review
was skipped for an exhausted quota --- a signal the bot posts, rather than an
inference drawn from a zero cost.
The receiving agent checked and pushed back, which is the discretionary
detector working rather than a mechanism.
The brief written to record this entry then repeated the shape at smaller
scale, saying `CLAUDE.md` had "five quota mentions" where `grep -ci quota`
returns 6 lines and `grep -oi quota | wc -l` returns 7 occurrences.)

## "the SAS source is the spec" convention-document premise

(2026-07-30, `ucdavis/bcs`: that repo's `CLAUDE.md` asserts, as a section
heading, "the SAS source is the spec".
The maintainer's correction was that the SAS programs are a proposal rather
than a specification.
By then the assertion had been treated as background fact by several agents and
had propagated into issues and briefs, which is the convention-document shape
[`challenge-the-assignment.md`](challenge-the-assignment.md) describes: no
single reader invented it, and each one found it corroborated.)

## This fragment's own brief overstated coverage

(2026-07-31, this fragment's own brief: it named four areas as likely
uncovered.
Two --- a premise handed down as settled, and a default nobody chose --- had
been closed hours earlier, both of them in
[`metacognitive-monitoring`](metacognitive-monitoring.md): the unexamined
default by ai-config#947, merged 06:28Z, and the handed premise by
ai-config#955, merged 07:13Z.
The brief also pointed at a checkout that was 37 commits behind `origin/main`,
so every search run there would have understated coverage.
The brief asked to be questioned, which is why this was caught; the general
case is a brief that does not.)
