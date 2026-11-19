# Port content between repos with a script

When content moves from one repository to another, copy the source files with a script.
Keep the ids, wording and citations.
Edit only what the target repository's style rules require.
Write generatively only for content that has nothing to port.
A port moves content, so the source is removed or stops being canonical, which is why it is not the copy [`dont-copy-decompose`](../principles/dont-copy-decompose.md) forbids.

## Why

A generative rewrite drifts from the source wording, ids and citations, and the diff does not show what changed.
A scripted copy plus targeted edits keeps the diff against the source small, so a reviewer can check the edits instead of rereading everything.

## What to do

- **Do:** search the source repositories for existing content on the topic before writing anything.
- **Do:** copy the source files with a script, such as `cp`, `git mv` within one repository, or a short loop that also records the source path and commit.
- **Do:** keep ids, cross-reference keys, wording, citations and `references.bib` keys exactly as in the source.
- **Do:** make each required edit a separate, named step, such as a macro substitution, a heading change, or a link retarget.
  Apply it with a script when it is mechanical.
- **Do:** state in the PR description the source repository, path and commit.
- **Do:** check the result with a diff against the source, in both directions, so a dropped passage shows up as well as an added one.
- **Do:** list every difference from the source in the PR as deliberate or accidental.
- **Don't:** retype, summarize or regenerate source content that exists.
- **Don't:** write generatively and call it a port.
  Content with nothing to port is new content, and the PR says so.

## Port every item: inventory, map, report

When Ezra asks to incorporate or port a source (a lab, a slide deck, a chapter) into a notes repo, the port covers the whole source, not only its gaps.

1. **Inventory** the source item by item with a script or an explicit list: every exercise, example, figure, definition and table.
2. **Map** each item to its target: an existing equivalent in the target repo (name it), or a new port.
3. **Port every item** unless Ezra agrees to a skip.
   A kickoff brief that says "leave out what the target already covers" is not that agreement.
   Map such an item to its equivalent and report the match instead of dropping it silently.
4. **Copy with a script, then improve.**
   The scripted copy comes first, and the style edits and improvements come after it as separate steps.
5. **Report the source-to-target map** before calling the work done, one row per source item.
   A missing row is the defect.

The method has a skill, `port-source-exercises`.

### Why no hook enforces this

A hook sees tool calls, PR text and diffs.
Whether a port is complete depends on the source's content, which only an inventory of that source shows, so the check is the map in step 5.
On 2026-11-18 about 20 of the 32 exercises in the ISLP chapter 7 lab were left unported and unreported, because the brief framed the task as filling gaps ([ai-config#5823](https://github.com/Morrison-Lab/ai-config/issues/5823), lds#2802, lds#2803, lds#2805).

## Drift: keep improvements, question accidents

Deliberate improvements are fine, and the PR says so.
An accidental drift is a difference nobody chose, such as a reworded sentence, a changed number, or a lost citation.
The agent questions each accidental drift and decides alone, without asking the user, between two outcomes:

- Keep the better version, when one clearly is.
- Combine the best of both, when each has something the other lacks.

Then the agent uses the result everywhere the content lives.
When the source has the better version, the port restores it.
When the port is better, the source repository gets the same improvement, in its own PR.

## Auditing open PRs

When this rule is recorded, or a new notes repository PR arrives, audit open PRs by diff.
For each ported file, diff it against its source.
Every difference beyond the required edits is either a deliberate improvement or an accidental drift.
Route the fix for each accidental drift to the PR's own thread, which applies the decision above.

Rule from Ezra, 2026-10-19; port-every-item section from Ezra, 2026-11-18.
See [ai-config#4632](https://github.com/Morrison-Lab/ai-config/issues/4632).
Related: [`send-notes`](../../skills/send-notes/SKILL.md), [`global-by-default`](global-by-default.md), [`reorganize-prose`](../writing/reorganize-prose.md).
