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

## Do / Don't for the negated keyword

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

## Distinct from two nearby `Closes` traps

- An **invented** number filling a habitual `Closes` slot
  ([`ardi.cases.md`](../shared/workflow/ardi.cases.md), ai-config#1361).
  The number here was the *right* tracker.
- A **partial-ship** `Closes` that closes leftover sub-items
  ([`issue-first.md`](../shared/workflow/issue-first.md)).
  The author here was trying *not* to close.

## A `Refs` on a branch is a decision to read, not a gap to fill

The mirror of the #1718 case above.
There the squash body carried a keyword the author had not wanted;
here a brief asserted a keyword the branch did not carry,
and the branch was right to lack it.

Under a squash merge of a PR that targets the default branch,
what closes an issue is the whole squash commit message as entered, plus the PR body;
a PR targeting any other branch has its body keywords ignored, per the docs cited above.
The title counts:
the docs cited above say a keyword in a commit message merged to the default branch closes the issue,
and the subject is part of the message.
This repo sets `squash_merge_commit_title` to `COMMIT_OR_PR_TITLE` (read 2026-09-04),
which GitHub documents as the sole commit's subject on a one-commit PR and the PR title otherwise;
so a keyword in either of those reaches `main` unless the merger edits the prefilled title.
The branch's commit messages reach the squash *body* only through the default body,
which GitHub builds from them as a bullet list
when `squash_merge_commit_message` is `COMMIT_MESSAGES` (read 2026-09-04),
and a body written by hand at merge time replaces that default entirely.
So a listing of the branch's keyword-carrying commits answers what the default body would carry,
and the message actually entered is what to read once it exists.

Measured 2026-09-04 on the six wave-1 PRs,
[#3211](https://github.com/Morrison-Lab/ai-config/pull/3211) through [#3216](https://github.com/Morrison-Lab/ai-config/pull/3216),
whose first commits carry `Closes` in bd5f0400, 6bd132d3, 38222457, and 6ef32462 and `Refs` in 70caac00 and f30d108e,
on the fix-loop scripts from the first wave-1 script through r5
(r5 alone carries the shape ai-config#3203 proposed),
on issue #3068's timeline,
and on a run of `hooks/remind-brief-premises.py`.
The fixer brief asserted for every branch that its first commit already carried the closing keyword;
the assertion held for four of the six and failed for two.
The sentence entered the loop's brief on 2026-09-03, in the first wave-1 script,
and was copied into each later script through r5 without anyone re-reading the branches.
The assertion was never true for `fix/3102-memory-size-approach`,
which says `Refs #3102` because PR #3215 shipped one of the issue's two parts;
seven of that branch's nine commits carry the `Refs`, and the other two are generated merge-commit lines.
The assertion was true for `fix/3068-flag-cd-stderr` on 2026-09-03 and false by 03:57Z on 2026-09-04,
thirteen hours before the r5 script was written.
A rebase reworded the keyword out of the branch's first commit on purpose,
because the issue's first "done when" item (the warning surfaces in a live session)
is one that branch could not show;
the empty commit `78fda241` records the rebase and the reason.
Both PRs merged with hand-written squash bodies carrying `Refs`,
and both issues stayed open, which was the intended outcome in each case.
The mistake came after:
issue #3068 was closed by hand on the strength of the item
asking for a test that pins the `additionalContext` emission
plus an item the issue marks optional,
and reopened twenty minutes later once `78fda241` and `a92de7b4` on the branch were read.
The hook did not fire on the brief's sentence, and cannot:
its clauses A and B anchor a claim to a named corpus path,
and clause C fires only on the `[FINDINGS_COUNT: N]` token over findings, rounds, or reviews,
so a count in a claim about a branch's commits reaches neither.

- **Do:** before opening the PR, list the branch commits whose messages carry a closing keyword,
  in every spelling and both issue forms the parser accepts,
  with the PR's base resolved rather than assumed
  (`base="$(git remote show origin | sed -n 's/.*HEAD branch: //p')"`, or the branch a stacked PR targets):
  `git rev-list --count "origin/$base..HEAD"` first,
  since a zero says HEAD is not ahead of that base (wrong ref, uncommitted work, or a branch merged by a merge commit or fast-forward),
  and the count separates nothing-to-search from searched-and-found-nothing;
  then
  `pat='(close[sd]?|fix(es|ed)?|resolve[sd]?):? *([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?#[0-9]+'` and
  `git log --regexp-ignore-case --extended-regexp --grep="$pat" --format='== %h %s%n%b' "origin/$base..HEAD" | grep -iE "^== |$pat"`;
  each `==` line names a matching commit and the lines under it are its matching body lines,
  which is where this repo's keywords sit,
  and the pattern carries no word boundary,
  so it also hits a word that merely ends in a keyword (`prefixes #`);
  the substring claim at the top of this file is about the sentence around a keyword,
  not about letters inside a word,
  so read each hit.
- **Don't:** open the PR having written its body but not read what the branch's commits would land;
  the #1718 case above is a `Refs` PR body over a `Closes` squash body.
- **Do:** put whatever keyword the merge should carry in the PR body,
  scoped per [`issue-first.md`](../shared/workflow/issue-first.md),
  then read every surface the parser will see for the merge method in use.
  The PR body counts only when the PR targets the default branch (the docs cited above say so);
  on a stacked PR its keyword never fires,
  while the branch commits' keywords still fire once those commits reach the default branch.
  Under a squash merge whose body you write: the PR body, the squash title, and the squash body you write.
  Under a squash merge with the default body: the PR body, the squash title,
  and the default squash body with the branch commits listed in it.
  Under a merge commit: the PR body, the branch commits, the merge commit's subject
  (`merge_commit_title` read as `MERGE_MESSAGE` on 2026-09-04,
  the generated `Merge pull request #N from <owner>/<branch>` line),
  and the merge commit's body, which defaults to the PR title
  (`merge_commit_message` read as `PR_TITLE` on 2026-09-04);
  both merge-commit fields are editable in the dialog.
  Under a rebase merge: the PR body and the branch commits.
- **Don't:** read only the squash body you typed;
  the title arrives prefilled from the PR or the sole commit and reaches `main` unless you edit it.
- **Don't:** count a stacked PR's body keyword as what will close the issue.
- **Do:** when a branch carries `Refs` where a `Closes` was expected,
  read its commit messages for the reason before treating the absence as an omission,
  and look for the acceptance item a deliberate removal names.
- **Don't:** add the `Closes` because the branch appears to have forgotten it.
- **Do:** when a brief asserts what a branch's commits carry,
  run the listing above on that branch and paste its output beside the claim,
  per [`challenge-the-assignment.md`](../shared/workflow/challenge-the-assignment.md);
  the check is by hand, since the hook above does not see the claim.
- **Don't:** assert in a brief that a commit carries a closing keyword the brief's author never read,
  or read once and never re-read after the loop rewrote history.
- **Do:** close an issue by hand only when every required acceptance item is met,
  by the merged diff or by the evidence the item asks for (a transcript line, for an observation),
  with a comment naming that evidence.
- **Don't:** close an issue by hand because its PR merged,
  or because the required items that remain unmet are the hard ones.
