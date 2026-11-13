# polish-page — clean up and flesh out one notes page, and consolidate overlap

Bring one page of a Morrison-Lab notes site (`lds`, `mds`, `pds`, `sds`, `rme`, `mcs` and the rest) up to the lab’s current rules, fill the gaps in its content, and decide where it duplicates another page or repository. This skill points at the rules; it does not restate them. When a rule changes, the linked source changes and this skill does not.

## When this fires

- “clean up and flesh out this page”, “polish this page”, “bring this page up to our style”.
- “check for overlap with other pages or repos”, “should we consolidate this?”
- A page link plus “follow our psw style and semantic macros”.

## Procedure

### 1. Scope the page and open the issue first

- Name the one page (and its `_subfiles/` units) the task covers. One page per PR; adjacent pages and findings outside the ask become issues (`defer-issue`).
- File the issue before editing (`st` / `shared/workflow/issue-first.md`). Read the repository’s `CLAUDE.md`, `AUTHORING.md` and `.github/copilot-instructions.md` first: they override the lab defaults for that site.
- Fetch the live page and the source together. The source is the truth. The live page shows what a reader sees (slides and handout too, when the site builds them).

### 2. Survey overlap before editing

Search for the page’s main terms and results across the notes repos, and decide per overlap.

``` bash
# every attached notes repo; adjust the list to the sites that exist
for r in mds pds sds lds rme mcs ids win cie; do
  [ -d "$r" ] && grep -rniE "<term one>|<term two>" "$r" --include='*.qmd' -l
done
```

- Place content by the prerequisite sequence in [`course-sequence`](../../shared/writing/course-sequence.md): math in mds, probability in pds, statistics in sds, information theory in ids.
- **Same idea, earlier site** (a prerequisite already defines or derives it): link its definition and drop the local copy ([`notes-content-rules`](../../shared/writing/notes-content-rules.md), “Link prerequisite definitions”).
- **Same idea, same site, another page**: keep one home, link from the other, and fix cross-references.
- **Same idea, later or sibling site**: link as further reading only. Never define a page’s own terms by pointing forward.
- **Copied from a source**: run gha’s `check-source-overlap` and read [`avoid-unintentional-plagiarism`](../../shared/writing/avoid-unintentional-plagiarism.md).
- Track a useful outside resource in every notes repo whose topic it covers (AGENTS.md, “Track each useful resource in each notes repo whose topic it covers”).
- Never lose content: moved or removed text goes to the repository’s outtakes location, not the bin.
- A move across repositories is a separate PR per repository, stacked, with the issue linked in GitHub’s relationships field. Use [`send-notes`](../../skills/send-notes/SKILL.llms.md) to route content to the destination repo.

Record the decisions (keep / link / move, with the destination) in the issue before editing.

### 3. Clean up the existing text

Apply the rules from their canonical homes. Read these, rather than working from memory:

- Prose: [`use-preferred-style`](../../skills/use-preferred-style/SKILL.llms.md), [`plain-prose`](../../shared/writing/plain-prose.md), [`semantic-line-breaks`](../../shared/writing/semantic-line-breaks.md), and psw’s `chapters/word-choice.qmd`, `chapters/conciseness.qmd` and `chapters/defining-terms.qmd`.
- Lecture structure (exercise and solution pairs, definitions, one term or result per div, headings): [`lecture-conventions`](../../shared/writing/lecture-conventions.md) and [`quarto-divs-for-typed-content`](../../shared/writing/quarto-divs-for-typed-content.md).
- Math: [`use-math-macros`](../../skills/use-math-macros/SKILL.llms.md). Look each operator up in the `macros` repository’s `macros.qmd` before writing LaTeX. Add a missing macro there instead of writing `\operatorname`. Also psw’s `chapters/notation/` pages.
- Figures and data: [`visuals-everywhere`](../../shared/writing/visuals-everywhere.md), [`quarto-figure-captions`](../../shared/writing/quarto-figure-captions.md), [`quarto-visible-chunk-results`](../../shared/writing/quarto-visible-chunk-results.md). Code produces every output the page shows; never type output.
- Arbitrary analysis choices get a prose explanation: [`explain-analysis-choices`](../../shared/writing/explain-analysis-choices.md).
- Use real data, not a hypothetical example, wherever the site has a dataset: [`hypothetical-examples`](../../shared/writing/hypothetical-examples.md).

### 4. Flesh out the content

Find what a reader needs and the page lacks, and add it in the page’s existing form.

- List the page’s topic against the course outline and the calendar, and against the gap map or source book the site follows. For `lds`, that is ISL: see the repository’s `CLAUDE.md`.
- Add each missing item as the lecture form requires: an exercise, then its solution, then the formal definition or result.
- Cite every source through `references.bib`. Check the citation against the source, and never invent one ([`citations`](../../shared/writing/citations.md)).
- Fact-check every number and claim, and recompute every value the page states ([`fact-check-prose`](../../shared/writing/fact-check-prose.md)).

### 5. Check before the one push

Run gha’s checks locally on the diff. List them from the current checkout rather than from this file, because the set changes:

``` bash
ls -d <gha-checkout>/check-* | sed 's|.*/||'
```

Run at least the ones that match the edit, per each check’s `README` or `action.yml`:

- prose: `check-new-line-breaks`, `check-heading-titles`, `check-heading-siblings`, `check-avoided-words`, `check-hybrid-sentences`, `check-self-reference`, `check-term-links`, `check-definite-antecedents`;
- structure: `check-one-div-per-subfile`, `check-div-ids`, `check-exercise-before-result`, `check-multipart-exercises`, `check-solution-citations`;
- math and figures: `check-macro-expansions`, `check-literal-math-letters`, `check-equation-renders`, `check-self-contained-captions`, `check-figure-placement`;
- text hygiene: `check-non-standard-chars`, `check-typos`, `check-links`.

``` bash
NLB_GLOBS='*.qmd' NLB_BASE_REF=origin/main python3 <gha-checkout>/check-new-line-breaks/check-new-line-breaks.py
```

Then render the page to every format the site builds, and read the rendered output against the prose. A renamed heading changes its anchor: grep the repository for the old `#slug` before pushing. Checks are diff-scoped. Do not sweep other pages (AGENTS.md, “No sweeps for new rules by default”).

### 6. Ship

- Small PRs: at most 10 files and 300 lines. Content and infrastructure never share one. Split a large page into stacked PRs (`stack-prs`).
- Then `ardi` to clean. Do not merge without the merge grant in force (`mwc`).

### 7. Feed lessons back

Every correction Ezra or a reviewer makes on the page is a candidate rule. Record it where it lives: prose rules in psw, agent behavior here or in ai-config, a checkable content rule as a failing gha check (`ums`). Add a pointer to this skill only when the procedure changes.

## Relationship to other skills

- [`send-notes`](../../skills/send-notes/SKILL.llms.md): routes new content to a repo; this skill reworks an existing page.
- [`find-overlap`](../../skills/find-overlap/SKILL.llms.md): overlap between skills and memory, not notes pages.
- [`use-preferred-style`](../../skills/use-preferred-style/SKILL.llms.md), [`use-math-macros`](../../skills/use-math-macros/SKILL.llms.md), [`fact-check-prose`](../../skills/fact-check-prose/SKILL.llms.md): the rule skills this one calls.
- `defer-issue`, `st`, `stack-prs`, `ardi`, `mwc`: the PR workflow around it.

## Anti-patterns

- Copying a rule’s text into the PR or this skill instead of linking its source.
- Editing before the overlap survey, then moving the same text twice.
- Sweeping other pages for the same fix.
- Deleting overlapping text instead of moving it to outtakes.
- Defining a term locally that a prerequisite site already defines.

Back to top
