# detect-informal-definitions — find concepts defined only in prose

A concept can be defined with all the precision of a formal definition — a bolded name, an equation, an `\eqdef` — and still never become one, because the sentence stating it was never wrapped in the project’s formal definition construct. That concept has no stable id: nothing downstream can cite it, and `definition-crossrefs.md`’s hyperlink-on-first-mention check has nothing to link to, since as far as that check is concerned no definition exists.

The full detection heuristic, confirmation checklist, and fix menu live in [`shared/writing/informal-definitions.md`](../../shared/writing/informal-definitions.md) — read it before running this skill; the steps below are the short version.

## When this fires

- “detect informal definitions”, “find informal definitions”, “check for missing definitions”, “is this concept formally defined”, “this reads like a definition but has no div”, “detect-informal-definitions”, “did”
- **As part of any PR/MR review, or self-review before a push, that introduces new technical content** — run alongside `definition-crossrefs.md`’s formal-crossref-div ordering check, `fix-forward-references`, `fact-check-prose`, and `find-ai-tells`.

## Procedure

1.  **Identify the target.** A file, a PR/MR diff, or pasted prose that introduces new technical content.
2.  **Grep for candidates** using the two patterns in [`informal-definitions.md`](../../shared/writing/informal-definitions.md#the-detection-heuristic) — a bolded term followed by defining language (`\eqdef`, “is the”, “=”), and a naming sentence ending “is:”/“are:” immediately before a display equation. Run both; each catches phrasing the other misses.
3.  **For each hit, find its enclosing div** (search backward for the nearest `:::{#...}` opener, forward for its matching closer). It’s a candidate if it sits in no formal-definition div at all, or if it sits inside a *different* concept’s div (riding along inside someone else’s definition).
4.  **Confirm each candidate** against the checklist in the fragment: is it introducing something new (not just reusing an already-defined term)? Is it a practical/tool-usage aside rather than a theoretical concept? Is it part of a deliberately informal list? Is it actually cited downstream? Drop anything that fails the “new, theoretical, not-a-list, worth-citing” bar.
5.  **Fix each confirmed finding**, per the fragment’s fix menu:
    - Wrap it in its own formal-definition div, with its own id and heading.
    - Give it its own worked example, immediately after — before any new theoretical claim builds on it.
    - Update anything that already depended on it informally to cite the new id explicitly.
    - If it was riding along inside a different concept’s div, split it out into its own div rather than leaving both sharing one id.
6.  **Re-scan** the touched section after editing — a newly-added definition can itself introduce a forward reference (see `fix-forward-references`) if its worked example isn’t moved to sit right after it.
7.  **Report.** For each finding: the term, its location, whether it had no div at all or was riding along inside another’s, the fix applied (new div id, new example, updated citations), and the diff.

## Relationship to other skills

- **`shared/writing/definition-crossrefs.md`** (cited from `CLAUDE.md`’s “Hyperlink technical terms and results” section, not a standalone skill) — assumes the defining div already exists and checks that mentions link to it in the right order, flagging a term as “undefined” only when no div states it *anywhere*. This skill runs conceptually first: it catches prose that reads like a definition but never became a div at all, which is exactly the case `definition-crossrefs.md`’s div-position comparison has nothing to compare.
- **`fix-forward-references`** — a concept without its own div can’t be crossref’d, which is exactly what forces an author into a forward- pointing phrase (“the definition below”) instead of a working link. Fixing this skill’s findings often removes a forward reference for free; run both on a diff that touches definitions.
- **`fact-check-prose`** / **`check-info-quality`** — sibling prose-rigor checks; run this alongside them on a diff that introduces new technical content.
- **`ard` / `ardi`** — when reviewing a PR/MR, or self-reviewing before a push, apply this check alongside the other prose-review rules `CLAUDE.md` lists.

## Anti-patterns

- ❌ Flagging every bolded term as a missing definition — most bolded text is emphasis on a term already formally defined elsewhere; check for an existing div before flagging.
- ❌ Treating a practical tool-usage explanation (what a function argument or CLI flag does) as a theoretical concept needing a formal div.
- ❌ Flagging items in a deliberately informal list (a “practical considerations” or “gotchas” section) that the surrounding content already signals isn’t the formal-definitions section.
- ❌ Wrapping a confirmed finding in a div without also giving it a worked example — a definition with no example is still incomplete by this project’s own content-writing conventions.
- ❌ Leaving a split-out concept’s new example after, instead of immediately after, its new definition — reintroduces the forward- reference problem this skill is meant to help avoid.

Back to top
