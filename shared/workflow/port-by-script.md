# Port content between repos with a script

When adapting any content (a port, a lab, a deck, a chapter, a snippet, a figure, text from any source), copy it first, algorithmically, and modify after the copy, never the reverse.
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

## Port every item: inventory, map, structure review, report

When Ezra asks to incorporate, port or adapt a source (a lab, a slide deck, a chapter, anything) into a repo, the port covers the whole source, not only its gaps.
An adaptation answers two questions (Ezra, 2026-11-19):
is every unit of content in the source covered somewhere in the destination,
and could the destination's organizational structure be improved, using the source as inspiration?
The coverage map in steps 2 and 3 answers the first, and the structure review in step 5 answers the second.

1. **Inventory** the source item by item with a script or an explicit list: every item of every kind, such as exercises, examples, figures, definitions, tables and listings.
2. **Map** each item to its target in a coverage map with one row per source item and three columns:
   the source item (its number and name),
   its place in the destination (a file and `#id`, or the PR that adds it),
   and a status of `covered`, `partly covered` (say what differs), `ported`, `banked` (a repeat sent to an exercise bank) or `skipped` (link Ezra's agreement).
   Write the map as a table or CSV, not prose, so a missing row or an empty cell shows.
3. **Give every item a row, and port every item that has no equivalent.**
   An item the target already covers is mapped to that equivalent, and the match is reported.
   Nothing is dropped unless Ezra agrees to the skip.
   A kickoff brief that says "leave out what the target already covers" is not that agreement: it still owes the row.
4. **Copy with a script, then improve.**
   The scripted copy comes first, and the style edits and improvements come after it as separate steps.
5. **Review the destination's structure against the source.**
   Compare how the source organizes the material with how the destination does:
   the order of topics, which items sit together under one heading, where a concept is introduced relative to its first use, and how finely items are split.
   Where the source's organization is clearer, propose that change to the destination, naming the source passage that suggests it.
   A move within the pages the adaptation already touches can go in the same PR, per [`reorganize-prose`](../writing/reorganize-prose.md);
   a restructure beyond them gets its own issue or PR, so the adaptation stays small.
   Where the destination's organization is better, keep it and say why.
6. **Report the coverage map and the structure review** before calling the work done:
   the map, and a structure section listing each proposed change and where it went (this PR, an issue, or declined with a reason).
   Write "none" in the structure section when the review found nothing, so a skipped review shows.
   A missing row, or a missing structure section, is the defect.

- **Do:** post a coverage map with a row and a status for every source item, and a structure section, even one that says "none".
- **Don't:** report only the items you ported, or port into the destination's existing layout without asking whether the source's layout is better.

### Why no hook enforces this

A hook sees tool calls, PR text and diffs.
An inventory script can list a source's items, but deciding whether a target page already covers an item needs a reader of both, so no hook can decide completeness.
Whether the source suggests a better structure is a judgment about how readers learn the material, so no hook can decide that either;
a hook could see that a structure section exists, but not that the review behind it happened.
The checks are the map and the structure section in step 6.
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

Rule from Ezra, 2026-10-19;
the copy-first-for-any-content rule and the port-every-item section from Ezra, 2026-11-18;
the coverage-and-structure questions from Ezra, 2026-11-19 ([ai-config#5950](https://github.com/Morrison-Lab/ai-config/issues/5950)).
See [ai-config#4632](https://github.com/Morrison-Lab/ai-config/issues/4632).
Related: [`send-notes`](../../skills/send-notes/SKILL.md), [`global-by-default`](global-by-default.md), [`reorganize-prose`](../writing/reorganize-prose.md).
