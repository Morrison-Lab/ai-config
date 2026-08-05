# fix-forward-references — detect and rearrange to remove forward pointers

A forward reference makes a reader hold an unresolved pointer: “as discussed below” promises content they haven’t seen yet. This skill finds those, confirms they’re real (not an idiom, not already fixed), and fixes them by moving content earlier or, when reordering isn’t the right call, rewording the pointer into a working link.

The full detection heuristic, confirmation checklist, and fix menu live in [`shared/writing/forward-references.md`](../../shared/writing/forward-references.md) — read it before running this skill; the steps below are the short version.

## When this fires

- “fix forward references”, “find forward references”, “check for forward references”, “remove forward references”, “fix-forward-references”, “ffr”
- “this points ahead to something not written yet”, “rearrange this so nothing references content below it”
- **As part of any PR/MR review that touches narrative prose** (docs, READMEs, papers, PR/issue descriptions) — run alongside `definition-crossrefs.md`’s formal-crossref-div check, `fact-check-prose`, and `find-ai-tells`.

## Procedure

1.  **Identify the target.** A file, a PR/MR diff, or pasted prose.
2.  **Grep for candidates** using the heuristic in [`forward-references.md`](../../shared/writing/forward-references.md#the-detection-heuristic) — start with the bare directional word (below, later, following, subsequently, further down, next, afterward); use the narrower reference-cue-paired pattern as a higher-confidence secondary filter when the primary grep returns too many idiom hits.
3.  **Confirm each hit.** Read the sentence: is it a genuine reference (not an idiom like “below average”), and does the target really come after the mention (not already earlier, just mis-worded)? Drop anything that fails either check.
4.  **Fix each confirmed forward reference**, in order of preference:
    - **Reorder** — move the referenced section/paragraph/div/figure/table earlier so it precedes the mention. Update the directional word (“below” → “above”) or drop it once a working crossref link carries the point.
    - **Reword** — only when reordering would break the document’s narrative logic. Replace the vague pointer with a precise, working link/crossref instead of leaving a bare “below”.
    - **Leave it** when the mention is a deliberate roadmap/overview preview (see the fragment’s “roadmap exception”) — not every forward-pointing sentence is a defect.
5.  **Re-scan** the touched section after editing to confirm no new forward reference was introduced by the reordering itself (e.g., a paragraph that used to follow the moved content and referenced it backward now needs the opposite fix).
6.  **Report.** For each finding: the phrase, its location, whether it was fixed by reordering or rewording (or left, with why), and the diff.

## Relationship to other skills

- **`shared/writing/definition-crossrefs.md`** (cited from `CLAUDE.md`’s “Hyperlink technical terms and results” section, not a standalone skill) — the narrower, formal-crossref-div case of this same problem, scoped to term/theorem definitions. Its check works by comparing div position to first mention directly, so it catches a bare `@def-x` crossref with no directional word at all — something this skill’s grep heuristic misses. Run both on a diff that touches definitions.
- **`detect-informal-definitions`** — a concept with no formal definition div of its own can’t be crossref’d, which is exactly what pushes an author toward a forward-pointing phrase in the first place. Run it alongside this skill on a diff that introduces new technical content; fixing its findings often removes a forward reference for free.
- **`check-rendered-refs` / `crr`** — checks whether a crossref *resolved* at render time; this skill checks whether it points in the right *direction*, on the source prose, before render.
- **`challenge-ambiguous-terminology.md`** — catches unclear terms; this skill assumes the term is clear and checks whether the reader has already been given whatever it’s pointing at.
- **`find-ai-tells` / `fact-check-prose`** — sibling prose-review passes; run all three together on a diff that touches narrative prose.
- **`ard` / `ardi`** — when reviewing a PR/MR, apply this check alongside the other prose-review rules `CLAUDE.md` lists.

## Anti-patterns

- ❌ Flagging every “below”/“later” as a forward reference — most idiomatic uses (“values below zero”) aren’t references at all; read the sentence before flagging.
- ❌ Reordering content without re-scanning afterward — a move can turn a previously-fine backward reference into a new forward one.
- ❌ Treating a deliberate roadmap/overview paragraph as a defect — see the fragment’s roadmap exception.
- ❌ Rewording as the default fix — reordering is the stronger fix (removes the pointer entirely); reserve rewording for when reordering would break the narrative.

Back to top
