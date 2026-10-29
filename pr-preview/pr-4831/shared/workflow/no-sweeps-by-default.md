# A new rule is not swept across existing content

Ezra, 2026-10-29 ([ai-config#4829](https://github.com/Morrison-Lab/ai-config/issues/4829)): "don't sweep new rules unless I explicitly tell you to sweep;
by default, just fix incrementally when you are editing a passage anyway."

## The rule

- When a rule lands (a writing rule, a notation rule, a convention), apply it to the content you write or edit from then on.
- Do not open a PR, issue or batch series whose purpose is to bring existing content into line with the new rule, unless Ezra explicitly says to sweep.
- When you edit a passage for any reason, fix its violations of current rules in the same edit, as part of the passage's own diff.
  That is the incremental fix, and it needs no ask.
- Checks look at changed lines only.
  A new content check defaults to diff-scoped;
  a whole-repo mode is for a requested sweep.
- A sweep Ezra asks for goes out as small batches ([`small-prs`](small-prs.md)), and its PR body carries a `Sweep authorized:` line quoting or linking his message.

## What is not a sweep

- Fixing the same defect in the PR you are already working on, including sibling files that PR touches and the divs it includes or follows (`notes-pre-review-pass`, `address-every-comment`) ([`learn-from-review-findings`](learn-from-review-findings.md)).
- Classification work on ai-config's own hooks and scripts, such as [#1967](https://github.com/Morrison-Lab/ai-config/issues/1967) and [#1449](https://github.com/Morrison-Lab/ai-config/issues/1449).
- A one-off audit whose output is a list in an issue, with no content changed.
  Do not file one for a rule that just landed, though: leftover violations are fixed when someone next edits that passage.

## The mechanisms

- `hooks/warn-sweep-pr-without-ask.py` warns when `gh pr create` or `mcp__github__create_pull_request` has "sweep" in the title (or, for `gh pr create` only, a `sweep` label) and no `Sweep authorized:` marker (followed by a message id or link).
  It warns rather than blocks because a title containing the word is not always a sweep, and a hook cannot read Ezra's intent.
- gha's content checks (`check-new-line-breaks`, `check-def-commentary`, `check-exm-figures`, `check-one-div-per-subfile`, `check-tree-lists`, `check-visualization-figures`, `check-typos` and others) are diff-scoped by default (checked 2026-10-29), reflagging nothing already merged.
  Where a whole-tree mode exists (the `whole-tree` input of `check-solution-citations` and `check-exercise-before-result`), it is opt-in, so keep it off by default.
- `hooks/no-oversized-pr-push.py` already caps any PR at 10 files and 300 lines ([`small-prs`](small-prs.md)), so an unrequested sweep that slips past the title check still cannot ship as one large PR.
- The part with no mechanism: deciding that a fix is incremental, not a sweep, depends on whether the passage was already being edited.
  A hook cannot know that, so this prose carries it.

## Decisions

- Explicit asks still win: Ezra's 2026-10-14 request to backfill visuals ([`visuals-everywhere`](../writing/visuals-everywhere.md)) stands, because he asked for it in those words.
- Earlier follow-ups of the form "sweep lds#..." on rule threads are superseded by this rule, unless Ezra explicitly asked for that sweep.
- "Going forward" alone in a rule message is not a sweep ask;
  the visuals message also said "backfilling the existing content".

- **Do:** fix a violation in the passage you are already editing.
- **Don't:** open a sweep PR or issue because a rule just landed, or add a whole-repo mode to a new check by default.
