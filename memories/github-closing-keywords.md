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
