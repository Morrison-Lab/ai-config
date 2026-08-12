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

## A brief's own command contradicted its own disclaimer

(2026-08-12, a brief dispatched into a `Morrison-Lab/gha` clone: the prose said
"Do NOT assume anything about its checked-out branch or worktree layout ---
establish your own working state", and the command block directly beneath it
assumed both.
Its two `git worktree add` forms, joined by `||`, differed on whether to create
the branch or reuse it, and both failed because the branch was already checked
out in that clone --- so the chain enumerated two states and the real one was a
third.
The recipient recovered by detaching the existing checkout and using `-B`.

The same block resolved the default branch with
`DEF=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed ...)
|| echo main`, which is the silent half.
That ref is unset in the clones this corpus is developed in, so `DEF` came from
the literal rather than from resolution --- right by luck.
Derivable in any of them:
`git symbolic-ref --short refs/remotes/origin/HEAD` exits non-zero with
`fatal: ref refs/remotes/origin/HEAD is not a symbolic ref`, while
`git remote show origin | sed -n 's/.*HEAD branch: //p'` returns `main`.
Measured in `/home/user/ai-config` on 2026-08-12, and the recipient reported the
same result for the `gha` clone the brief targeted.

Two further premises in the same brief were the sections above, unchanged:
`python3 -m pytest check-phi/tests/ -q` was instructed into an environment whose
default interpreter has no pytest module (it is a `uv tool install` at
`/root/.local/bin/pytest`), which is the environment case; and
`Morrison-Lab/gha#445` was described as an open issue when it is a merged pull
request, `merged_at` 2026-08-12T07:35:21Z, which is the corpus-state case that
one `issue_read` call would have settled.
The recipient caught all three and reported them back, which is again the
discretionary detector rather than a mechanism.)

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
