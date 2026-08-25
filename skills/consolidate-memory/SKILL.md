---
name: consolidate-memory
description: "Merge redundant memories."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# consolidate-memory — merge redundant memory entries into one canonical

The memory corpus (the topical files indexed in `memories/MEMORY.md`, plus
per-repo entries in `~/.claude/projects/<path>/memory/`)
accretes near-duplicates: two sessions each record the same lesson in different
words, or a fact lands in both a general file and a repo-specific one. This skill collapses a
genuine-duplicate cluster into **one canonical entry** — unioning the facts and
repointing any cross-links — so the corpus shrinks but no fact and no
`[[link]]` breaks.

It is the memory-corpus complement of `consolidate-skills`: same shape, different
data model. The key difference is that **memories are not invoked by name**, so
there is no alias stub to leave behind — a redundant entry is *removed* after its
unique content is folded into the survivor. The detection half — finding and
classifying the overlap — is delegated to `find-overlap`; this skill adds the
merge action on top.

## When this fires

- "consolidate memory", "consolidate memories", "merge duplicate memories",
  "dedupe memories", "collapse redundant memory entries", `/consolidate-memory`.
- You notice two memory entries that assert the same fact in different words.
- A `find-overlap` run over `memories/` reports a genuine-duplicate cluster.

## The one distinction that matters

Most "overlap" is **not** a duplicate. Before merging anything, classify each
cluster into exactly one of three buckets:

1. **Intentional scope layering — LEAVE ALONE.** A general rule in
   `preferences.md` *and* a concrete instance of it in a repo's project memory
   (`~/.claude/projects/<path>/memory/`) is deliberate — the general file states the
   principle, the repo file pins the specifics. Collapsing them loses either the
   generality or the specifics. Tell: the entries live in different scope files
   and one is the named application of the other.
2. **Adjacent-but-distinct — LEAVE ALONE (maybe cross-link).** Same topic,
   different facts (e.g. two `tools.md` bullets about the same tool but covering
   different flags). Merging them buries one fact inside another. If they should
   point at each other, add a `[[link]]` — don't merge.
3. **Genuine duplicate — CONSOLIDATE.** Two or more entries, in the same scope,
   that assert the **same fact** to the same end. This is the only bucket this
   skill acts on.

If you can't articulate what fact would be *lost* by keeping only one, it's a
duplicate. If you can, it isn't.

## Procedure

### 1. Detect overlap — delegate to `find-overlap`

Don't re-implement the audit; run **`find-overlap`** with scope `memories/`. It
gathers every entry across the memory files, clusters by shared subject, reads
the surrounding text, and returns each cluster already sorted into the three
buckets above (with a recommended disposition). Work from its report.

If `find-overlap` is unavailable, fall back to its inline pass — list the
headings/bullets across `memories/*.md` and per-repo project memories
(`~/.claude/projects/*/memory/`), cluster by subject, then **read the full
surrounding context of every member** before classifying.

### 2. Keep only the genuine-duplicate clusters

From `find-overlap`'s report, act **only** on bucket 3. Leave intentional scope
layering (bucket 1) untouched, and add a `[[link]]` to adjacent-but-distinct
clusters (bucket 2) only if they want one — never a merge.

### 3. Propose the consolidation plan — get approval first

Like `consolidate-skills` and `heal-skill`, do not mutate before the user signs
off. Present, per cluster:

- **The members** (file + heading/bullet) and why they're genuine duplicates
  (not scope layering, not adjacent-but-distinct).
- **The chosen canonical home** — which scope file the merged entry belongs in.
  A fact true everywhere belongs in the matching general file (one of the
  topical files indexed in `memories/MEMORY.md`); a repo-specific fact belongs in that repo's
  Claude project memory (`~/.claude/projects/<path>/memory/`). State why.
- **What gets folded in** — every non-obvious detail and *why*-clause unique to
  an absorbed entry that must survive into the canonical.
- **Which entries get removed** (all non-canonical members).
- **Links to repoint** — any `[[link]]` pointing at an absorbed entry's topic
  (see step 6).

### 4. Build the canonical entry

In the chosen scope file:

- **Union the facts** — fold every distinct detail from the absorbed entries
  into one coherent entry. Keep the *why*, not just the *what*; don't just
  staple the bullets together.
- Match the file's existing entry shape (bullet vs `##` section, heading style,
  terseness) so it reads like its neighbors.
- Keep it concise — bullet points, not prose, per `record-learnings`.

### 5. Remove the absorbed entries

Delete the now-redundant copies. Unlike `consolidate-skills`, there is **no
alias stub** — nothing invokes a memory by name, so a removed entry leaves no
dangling invocation. Only the survivor remains. Never delete a whole memory
*file* unless consolidation empties it.

### 6. Fix every dangling reference

A merged-away entry may be referenced by a `[[name]]` cross-link. List every
`[[...]]` use across the memory files and skill bodies, then repoint any that
pointed at an absorbed entry at the surviving canonical:

```bash
grep -rn "\[\[" memories/ skills/*/SKILL.md CLAUDE.md \
  ~/.claude/projects/*/memory/ 2>/dev/null
```

If you also named the absorbed entry in prose, grep that distinctive text and
repoint it too. Don't leave a reference resolving to an entry you removed.

### 7. Validate, then ship via branch + PR

```bash
python3 scripts/validate-skills.py      # this skill's own frontmatter must pass
python3 scripts/check-links.py          # no broken relative links
```

Memories live in the ai-config repo — never leave changes local-only. Branch +
PR (not direct to main), request `d-morrison` as reviewer (`request-pr-review`),
then **ARDI to clean** (`ardi`).

```bash
git checkout -b consolidate-memory-<topic> origin/main   # CREATE_BRANCH
# build the canonical entry, remove the absorbed copies, repoint links
git add memories/<file>.md   # only the files you touched — never a bare
                             # `git add memories/` (sweeps in unrelated edits) or `git add -A`
git commit -m "memories: consolidate <topic> duplicates into one canonical entry"   # COMMIT
git push -u origin HEAD && gh pr create --fill   # PUSH + CREATE_PR
```

## Relationship to other skills

- **`find-overlap`** — the read-only detector this skill delegates its audit to;
  it finds and classifies the overlapping memory clusters, consolidate-memory
  merges the genuine duplicates. (find-overlap : consolidate-memory :: `pr-status`
  : `ardi`.)
- **`consolidate-skills`** — the same operation for the *skills* corpus. The
  difference: skills preserve every invocation name via alias stubs;
  consolidate-memory removes the redundant entry outright (memories aren't
  invoked).
- **`memorize` / `record-learnings`** — they *write* memory entries; this *merges*
  the redundant ones they accumulate. Step 3's "check existing notes" in those
  skills prevents most duplicates; this is the cleanup when one slips through.
- **`link-skills`** — the skills-corpus analogue: for adjacent-but-distinct
  *skills* that should cross-reference each other but not merge. For memory
  cross-links, add the `[[link]]` manually (as step 2 describes) — `link-skills`
  only scans `skills/*/SKILL.md`.

## Anti-patterns

- ❌ Collapsing **intentional scope layering** (a general rule plus its
  repo-specific instance) — that's deliberate, not a duplicate.
- ❌ Merging **adjacent-but-distinct** entries and burying one fact inside
  another.
- ❌ Dropping a *why*-clause or a non-obvious detail on the floor — the canonical
  must carry the **union** of the absorbed entries' content.
- ❌ Leaving an absorbed entry's topic referenced by stale prose or a `[[link]]`.
- ❌ Mutating before the user approves the plan.
- ❌ `git add -A` / a bare `git add` that sweeps in unrelated in-flight edits —
  stage only the memory files you touched.
