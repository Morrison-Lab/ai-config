# Port content between repos with a script

When content moves from one repository to another, copy the source files with a script.
Keep the ids, wording and citations.
Edit only what the target repository's style rules require.
Write generatively only for content that has nothing to port.

## Why

A generative rewrite drifts from the source wording, ids and citations, and the diff does not show what changed.
A scripted copy plus targeted edits keeps the diff against the source small, so a reviewer can check the edits instead of rereading everything.

## What to do

- **Do:** search the source repositories for existing content on the topic before writing anything.
- **Do:** copy the source files with a script, such as `cp`, `git mv` within one repository, or a short loop that also records the source path and commit.
- **Do:** keep ids, cross-reference keys, wording, citations and `references.bib` keys exactly as in the source.
- **Do:** make each required edit a separate, named step, such as a macro substitution, a heading change, or a link retarget.
  Apply it with a script when it is mechanical.
- **Do:** state in the PR description the source repository, path and commit, and the list of edits made.
- **Do:** check the result with a diff against the source, in both directions, so a dropped passage shows up as well as an added one.
- **Don't:** retype, summarize or regenerate source content that exists.
- **Don't:** "improve" wording while porting.
  File an issue or open a separate PR for improvements.
- **Don't:** write generatively and call it a port.
  Content with nothing to port is new content, and the PR says so.

## Auditing open PRs

When this rule is recorded, or a new notes repository PR arrives, audit open PRs by diff.
For each ported file, diff it against its source.
A PR whose ported content differs from the source in more than the required edits is a generative port.
Route the fix to the PR's own thread: replace the file with the scripted copy, then reapply the required edits.

Rule from Ezra, 2026-10-19.
See [ai-config#4632](https://github.com/Morrison-Lab/ai-config/issues/4632).
Related: [`send-notes`](../../skills/send-notes/SKILL.md), [`global-by-default`](global-by-default.md), [`reorganize-prose`](../writing/reorganize-prose.md).
