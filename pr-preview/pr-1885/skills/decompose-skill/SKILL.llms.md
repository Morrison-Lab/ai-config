# decompose-skill — split an overly-broad skill into its real parts

The corpus also grows the opposite problem from what [`consolidate-skills`](../../skills/consolidate-skills/SKILL.llms.md) fixes: instead of two skills drifting into a duplicate, one skill drifts into **too much** — bundling a second, genuinely distinct workflow, or holding a chunk of content that other skills need too but can only get by duplicating it. This skill is that mirror-image action: split the bundle into a canonical skill plus whatever it should never have carried alone.

It is the corpus-level complement to `simplify`/`tidy` (which prune a single file’s own content) and the reverse of `consolidate-skills` (which merges several skills into one). Where `consolidate-skills` asks “should these two become one?”, this skill asks “should this one become two — or one plus a shared fragment?”

## When this fires

- “decompose this skill”, “split this skill up”, “this skill does too much”, “break this skill apart”, “extract this into a shared fragment”
- You notice a `SKILL.md` whose `## Procedure` covers two workflows a user would invoke separately, or whose content keeps getting copy-pasted into other skills instead of referenced
- `skill-builder`’s Step 0 “extend before create” check finds that the *closest* existing skill to extend is actually two concerns wearing one name — hand the cleanup here instead of bolting a third concern on

## The one distinction that matters

Not every long or detailed skill needs splitting — length alone is not the signal. Before touching anything, classify what’s actually there into exactly one of three buckets, the same discipline `consolidate-skills` uses in reverse:

1.  **Single coherent concern, just thorough — LEAVE ALONE.** A skill can be long because its one workflow has many steps, edge cases, and anti-patterns worth spelling out (several skills in this corpus run 200+ lines this way). That’s depth, not bundling. Tell: every section serves the same named workflow; removing any one section would leave the *same* task half-finished, not a *different* task untouched.
2.  **Reusable content stuck inline — EXTRACT to a shared fragment.** The skill contains a self-contained chunk (a convention, a checklist, a worked explanation) that other skills already duplicate, or plainly would benefit from referencing, but it currently lives only inside this one `SKILL.md`. This is the **cheap, usually-right** move: a `shared/` fragment carries no per-skill overhead (no new frontmatter, no new trigger phrases to make discoverable, no new entry in `skills.qmd`) — it’s just a file other `SKILL.md`s point at.
3.  **Genuinely distinct concerns bundled together — SPLIT into sibling skills.** The `SKILL.md` covers two (or more) workflows a user would invoke *separately*, under different triggers, producing different outcomes — not two steps of the same job. This is the **expensive** move: each new skill carries fixed overhead (frontmatter, a discoverable description, a `skills.qmd` row, cross-links to maintain), so only pay it when the concerns are truly separable asks, not just separable *paragraphs* within one ask.

If you can’t name a distinct trigger phrase and a distinct outcome for the proposed second skill, it’s bucket 1 or 2, not bucket 3. Over-splitting a thorough single-purpose skill into several thin ones hurts discoverability more than a long file ever does. The `fix-forward-references`-vs-`definition-crossrefs.md` split (a dedicated skill for one direction, a fragment cross-linked from several review skills for the other) is a useful precedent: the fragment is bucket 2 and the dedicated skill is a bucket-3 judgment call, decided on the merits of each piece rather than reflexively splitting everything.

## Procedure

### 1. Identify the candidate

Either take a named skill as input, or scan for signals: a `SKILL.md` whose line count is well above the corpus’s norm *and* whose headings name more than one distinct trigger/outcome pair; content duplicated near-verbatim across two or more other skills (a grep hit for a distinctive phrase in more than one `SKILL.md`); or a skill whose own `description` reads as two run-on workflows joined by “and”.

### 2. Read the whole file, then classify

Read the full `SKILL.md` (not just headings) before deciding. Sort its content into the three buckets above. Most files will be almost entirely bucket 1 with maybe one bucket-2 or bucket-3 piece — decomposition is usually a small, targeted extraction, not a full rewrite.

### 3. Propose the plan — get approval before touching anything

Same posture as `consolidate-skills` and `heal-skill`: present, don’t apply.

- **What stays** — the canonical skill’s narrowed scope, and why the remaining content is bucket 1.
- **What gets extracted, and to where** — for bucket 2, the new `shared/<topic>.md` path and every `SKILL.md` (the origin plus any others already duplicating it) that should cross-link it afterward.
- **What gets split off, and as what** — for bucket 3, the new sibling skill’s proposed name, trigger phrases, and how its `description` differs from the canonical’s so the two are separately discoverable.
- **What doesn’t move** — call out anything that looked separable but turned out to be bucket 1 on closer read, so the proposal is explicit about what it *isn’t* touching.

### 4. Extract (bucket 2)

- Create `shared/<topic>.md` with the reusable content, written to stand on its own (a skill reading it later won’t have the origin skill’s own framing).
- Replace the extracted text in the origin `SKILL.md` with a short reference (`@shared/<topic>.md`-style citation or a plain link, matching how this corpus’s other `shared/` fragments are already cross-linked from skill bodies — grep an existing example before inventing a new citation style).
- Add the same cross-link to every other skill identified in step 3 as already duplicating the content, replacing their own copy with a reference instead of leaving both.

### 5. Split (bucket 3)

Follow [`skill-builder`](../../skills/skill-builder/SKILL.llms.md)’s conventions exactly for the new sibling: proper frontmatter, a discoverable trigger-rich `description`, and (if it encodes a standing rule) a matching `preferences.md`/`CLAUDE.md` update. Narrow the canonical skill’s own `description` and body to drop the split-off concern, and add a `## Relationship to other skills` cross-link each direction so neither reads as an unexplained fork of the other.

### 6. Fix every dangling reference

A decomposed skill’s old, broader description may still be quoted or cross-linked from elsewhere:

``` bash
grep -rn "<original-skill-name>" skills/*/SKILL.md memories/ CLAUDE.md 2>/dev/null \
  | grep -v "skills/<original-skill-name>/SKILL.md"
```

Update any cross-link that named the old bundled scope to point at the right piece now — the canonical, the new fragment, or the new sibling skill, whichever the reference actually meant.

### 7. Validate, then ship via branch + PR

``` bash
python3 scripts/validate-skills.py      # frontmatter + wrapper-sync + manifest checks
python3 scripts/sync-codex-skill-wrappers.py   # REQUIRED if a sibling skill was added (bucket 3)
python3 scripts/check-links.py
python3 scripts/check-vendored-drift.py
```

Branch + PR (not direct to `main`), request `d-morrison` as reviewer (`request-pr-review`), then **ARDI to clean** (`ardi`). If a new sibling skill was added, bump `skills.qmd`’s “All N+ canonical skills” count to the *actual* directory count (`ls -d skills/*/ | wc -l`), not a manual +1 — see `skill-builder`’s own note on why a hand-incremented count drifts.

## Relationship to other skills

- **`consolidate-skills`** — the mirror-image merge direction; run that when two-or-more skills should become one, this skill when one should become two (or one plus a fragment). (`find-overlap` : `consolidate-skills` :: this skill’s own step-1 scan : this skill’s steps 2–7.)
- **`skill-builder`** — Step 0’s “extend before create” judgment call is the narrower, upstream version of this skill’s classification step, applied at the moment a *new* request comes in rather than to an *existing* skill’s accumulated content. Once a genuine split is identified (not just an extend-vs-create decision), hand it here; step 5 above then delegates the actual sibling-skill scaffolding back to `skill-builder`’s own conventions.
- **`simplify`** / **`tidy`** — the code/prose-cleanup analogues that prune or tidy a single file’s own content without changing its scope; this skill changes scope (moves content out), those don’t.
- **`split-concerns`** — the PR-scope analogue: splits a pull request’s diff into independent PRs, rather than splitting a skill’s own content.

## Anti-patterns

- ❌ Splitting on length alone — a long, single-concern skill (bucket 1) is not a decomposition target; check for genuinely separable triggers/outcomes first.
- ❌ Extracting to a new sibling skill (bucket 3, expensive) when a `shared/` fragment (bucket 2, cheap) would do — over-splitting adds discoverability overhead the content doesn’t earn.
- ❌ Mutating before proposing the plan — same rule as `consolidate-skills` and `heal-skill`.
- ❌ Extracting a fragment but leaving the other skills that duplicated the same content still holding their own copy instead of cross-linking the new fragment.
- ❌ Forgetting to regenerate Codex wrappers and bump `skills.qmd`’s count when a bucket-3 split adds a genuinely new skill.

Back to top
