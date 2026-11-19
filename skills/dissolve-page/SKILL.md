---
name: dissolve-page
description: "Dissolve a notes page into its neighbors."
user-invocable: true
allowed-tools:
- Bash
- Read
- Edit
- Write
- Grep
- Glob
---

# dissolve-page --- move every piece of a notes page to its natural home, and keep its links working

A notes page can outlive its job.
After earlier splits it may hold only a hub's leftovers: a recap exercise, a list of the pages it was split into, a reading list.
Dissolving it moves each remaining piece to the page where it belongs, leaves a hidden stub that forwards old links, and then rewrites the inbound links to point at the new homes.
This skill is the procedure;
the rules it applies live in their own files and are linked, not restated.

Grounded in the dissolve of lds's Big Ideas page (2026-11-19, Morrison-Lab/lds#2935, with the follow-ups Morrison-Lab/lds#2694 and Morrison-Lab/lds#2695).

## When this fires

- "Should we dissolve this page into other pages?", "fold this page into its neighbors", "this page is just a hub now".
- A [`polish-page`](../polish-page/SKILL.md) overlap survey ends with "move everything", not "link from one page to the other".
- Splitting a page in two is not this skill: that keeps the page.
  Use the page-splitting notes in the repository's own instructions for a split.

## Procedure

### 1. Inventory the page, piece by piece

Read the page's source and every subfile it includes, and list each unit: definitions, results, examples, exercise and solution pairs, remarks, figures, data divs, reading and video lists, the source or credits callout, any redirect script, and the dependency-graph or reference blocks.
For each, note its `#id` and which other pages already include the same subfile.

Count the inbound links too, because they decide the order of the later steps:

```bash
git grep -h -o "<page>.qmd#[a-z0-9-]*" origin/main -- chapters | sort | uniq -c | sort -rn | head -40
git grep -n "<page>.qmd)" origin/main      # links to the page itself, with no anchor
grep -n "<page>" _quarto-website.yml        # render list, navbar, sidebar
```

Read any existing moved-anchors script on the page: its map already says where each old id lives.

### 2. Check what else is in flight

List the open PRs that touch the page, its subfile folder, or the destination pages, and read the restructure plan or issue that covers the module, if there is one.
A move that edits a file an open PR edits will conflict with that PR, so the plan must route around them (step 5).
Search the tracker (`--state all`) for an existing issue on the subfile folder or the link rewrite before filing one.

### 3. Write the destination map and ask

Write one row per piece: the piece, and the page and position it moves to.
Typical destinations:

- a definition or result goes to the page whose topic it defines, next to the definitions it uses;
- a recap exercise goes at the start of the page whose lecture it opens;
- each reading or video item goes to the page whose content it covers, under a `# Reading {.unnumbered}` section before the dependency graph;
- each line of a source callout goes to the callout of the page whose content it credits;
- a navigation list ("the rest of this chapter") is dropped when the sidebar already lists those pages.

Recommend dissolve, partially dissolve or keep, with the map, on a decision card that offers "start now" or "file it" ([`start-or-file`](../../shared/workflow/start-or-file.md)).
Do not edit before the answer.

### 4. Move the pieces and make the stub (one PR)

- Move includes, not text: the subfile stays where it is and the destination page includes it, so every `#id` survives.
  Renaming the subfile folder is a later, separate PR.
- Keep a heading's explicit id when its section moves (`# The anatomy of a learning system {#sec-anatomy}`).
- Add the ids this PR moves to the redirect script's map and its hidden `<span id>` list.
  Retarget the links that name those ids (`<page>.qmd#fig-x` to `<new-page>.qmd#fig-x`), which are few because the ids are new to the map.
  Links to ids that earlier splits already moved off the page keep working through the redirect and wait for step 5.
- Turn the page into a stub: `format: html: default` only (a deck with one slide fails the site check, and the handout has no content), `search: false`, the redirect include, and a short list of the pages that now hold the content.
  Keep it in the render list, because old links from other repositories and course sites still reach it.
  Remove it from the navbar and the sidebar.
- Retarget the links to the page itself (no anchor) in this PR: the index, syllabus, calendar and study guide are few, and a reader should not land on the stub from inside the site.
  Check the calendar's map file, because a lecture link to a page with an anchor may not resolve there.
- Moved text counts as changed lines, so the diff-scoped checks re-read it in full.
  Expect `check-term-links`, `check-title-references`, `check-definite-antecedents` and the calendar-order check to flag moved prose, and fix it in the same PR.
- Render each destination page and the stub, then run the repository's local checks.

### 5. Rewrite the inbound links later, in batches

Links to `<page>.qmd#id` keep working through the redirect script, one hop each.
Rewrite them to their new homes with a mechanical replace driven by the redirect map, but only after the open PRs that edit the same files have merged: the rewrite touches hundreds of subfiles and would conflict with all of them.
Split it into small PRs by directory, each marked "mechanical, content-identical".
Keep the stub and its redirect script afterwards, for links from outside the repository.

### 6. Rename the subfile folder last

Moving `_subfiles/<page>/` into one folder per destination page is a pure rename that conflicts with every open PR touching those files.
File it as an issue in step 2 and do it after the link rewrite, one PR per destination folder.

## Ship

- Small stacked PRs ([`stack-prs`](../stack-prs/SKILL.md)); content and infrastructure never share one.
- Each PR body lists every moved piece and its destination, and says which later PR rewrites the links.
- Then [`ardi`](../ardi/SKILL.md) to clean.

## Relationship to other skills

- [`polish-page`](../polish-page/SKILL.md): reworks one page and decides overlap;
  it hands off here when the answer is "move everything".
- [`send-notes`](../send-notes/SKILL.md): brings content in from outside; this skill moves content within a site.
- [`split-concerns`](../split-concerns/SKILL.md): splits a PR, not a page.

## Anti-patterns

- Copying a subfile's text onto the destination page instead of including it, which forks the content and breaks its id.
- Rewriting hundreds of inbound links in the same PR as the moves, while other PRs edit those files.
- Deleting the page, or dropping it from the render list, so old links from other repositories 404.
- Leaving the stub in the navbar or sidebar, where readers keep landing on it.
- Renaming the subfile folder before the open PRs on it have merged.
