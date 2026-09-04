# GitHub closing-keyword parser traps

GitHub's closing keywords (`close` / `closes` / `closed`, `fix` / `fixes` /
`fixed`, `resolve` / `resolves` / `resolved`) match as a substring:
`KEYWORD #N`, with an optional colon.
The rest of the sentence is not read.
A line that *says* the keyword is not being used still closes `#N` when the
keyword sits next to the number.

Split out of [`github.md`](github.md) because that file sits at the 1250-line
gate (`scripts/check-memory-file-size.py` fires strictly above 1250, enforced with `--strict` in CI per ai-config#2970).

## Measured case

The squash commit of [ai-config#1718](https://github.com/Morrison-Lab/ai-config/pull/1718)
(`b67a4cfe`, 2026-08-20) contained:

```
Closes #1717 is deliberately NOT used -- #1717 tracks the registration that
must follow this merge.

Refs #1717
```

GitHub still closed [#1717](https://github.com/Morrison-Lab/ai-config/issues/1717)
(closedAt `2026-08-20T06:40:40Z`).
The hook that commit shipped therefore never landed in `hooks/hooks.json`.
Registration had to be recovered later as #2275 / #2294.

GitHub's docs (retrieved 2026-08-26) state the syntax as
`KEYWORD #ISSUE-NUMBER` (optional colon, also uppercase):
<https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue>
They do not say the parser ignores a following negation.
This instance shows the parser still closes.

The parser also runs on commit messages merged to the default branch, not
only on the PR body.
The PR body of #1718 used `Refs #1717` and did not contain the closing
keyword.
The squash message did.

## Distinct from two nearby `Closes` traps

- An **invented** number filling a habitual `Closes` slot
  ([`ardi.cases.md`](../shared/workflow/ardi.cases.md), ai-config#1361).
  The number here was the *right* tracker.
- A **partial-ship** `Closes` that closes leftover sub-items
  ([`issue-first.md`](../shared/workflow/issue-first.md)).
  The author here was trying *not* to close.

## A `Refs` first commit closes nothing at merge time, whatever the brief said

The mirror of the case above: a branch whose commits carry only `Refs #N`
leaves #N open when the PR squash-merges, and a brief that asserts "the
branch's first commit already carries the closing keyword" does not make it
so.
Measured 2026-09-04 on the six wave-1 PRs of the r5 fix loop
(ai-config#3203): the fixer brief carried that assertion for every branch,
and `git log --reverse --format=%B origin/main..HEAD` showed `Refs` rather
than `Closes` on two of the six (#3068 under #3211, #3102 under #3215).
Both merged with their issues open;
Issue #3068 was then closed by hand after its "done when" items were checked
against the merged diff, and #3102 stayed open because only half its scope
had shipped, which the `Refs` had been right about.

- **Do:** before opening the PR, read the branch's first commit with
  `git log --reverse --format=%B origin/main..HEAD | head` and put the
  keyword the PR body needs in the body itself, `Closes #N` or `Refs #N`
  by whether the diff covers the whole issue.
- **Do:** after a squash merge, read the issue's state rather than the
  PR's, and close by hand with a comment naming the merge when the diff
  covered it.
- **Don't:** assert in a brief that a commit carries a closing keyword the
  brief's author never read;
  the assertion reads as a premise the recipient cannot check without the
  same command.
- **Don't:** close an issue by hand because its PR merged;
  close it because the merged diff satisfies its "done when".

## Do / Don't

- **Do:** if you must mention a closing keyword you are not using, keep the
  number off the keyword (`the closing keyword was not used for #1717`;
  `Refs #1717` only).
- **Do:** read the squash / merge commit message, not only the PR body,
  before assuming a tracker stayed open.
- **Don't:** write `Closes #N is deliberately NOT used` (or any
  `Closes` / `Fixes` / `Resolves` `#N` substring) in a commit message or
  PR body.
- **Don't:** treat a following dash, or a later `Refs #N`, as protection
  --- the keyword-plus-number substring is enough.
