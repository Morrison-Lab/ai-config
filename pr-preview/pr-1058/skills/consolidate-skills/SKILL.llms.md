# consolidate-skills — merge overlapping skills into one canonical + alias stubs

The corpus accretes near-duplicates: two sessions each author a skill for the same workflow, or a skill drifts until it overlaps a neighbor. This skill collapses a genuine-duplicate cluster into **one canonical skill** and turns the absorbed ones into **thin alias stubs** — so the corpus shrinks but no invocation name, slash command, or muscle-memory breaks.

It is the corpus-level complement to the single-skill tools: `skill-builder` *creates* (extend-first), `heal-skill` *repairs* one misfiring skill, and this *merges* a redundant set into one. The detection half — finding and classifying the overlap — is delegated to `find-overlap`; this skill adds the merge action on top.

## When this fires

- “consolidate skills”, “merge overlapping skills”, “merge skills”, “dedupe skills”, “collapse duplicate skills”, `/consolidate-skills`.
- You notice two skills whose descriptions and bodies describe the same workflow with different words.
- A `skill-builder` run discovers an existing skill it should have extended — hand the cleanup here.

## The one distinction that matters

Most “overlap” is **not** a duplicate. Before merging anything, classify each cluster into exactly one of three buckets:

1.  **Intentional alias family — LEAVE ALONE.** One canonical SKILL.md with real content; the rest are thin stubs that only redirect to it (e.g. `ard`/`adr`/`address-rebut-defer`, `cb`/`prune`/`clean-branches`, `sync-pr-branch`/`merge-main`/`resync-branch`). This is the *target* state, not a problem. Tell: the others’ bodies are ~5 lines ending in `→ **[<canonical>](../<canonical>/SKILL.md)**`.
2.  **Adjacent-but-distinct — LEAVE ALONE (maybe cross-link).** Same theme, genuinely different procedure (e.g. `tidy` audits for refactors vs `simplify` prunes dead code; `split-concerns` splits a PR vs `defer-issue` files a follow-up). Merging these *loses* capability. If they should reference each other, hand off to `link-skills` — don’t consolidate.
3.  **Genuine duplicate — CONSOLIDATE.** Two or more skills with **real bodies** that drive the same workflow to the same outcome. This is the only bucket this skill acts on.

If you can’t articulate what capability would be *lost* by keeping both, it’s a duplicate. If you can, it isn’t.

## Procedure

### 1. Detect overlap — delegate to `find-overlap`

Don’t re-implement the audit; run **`find-overlap`** over the skills corpus. It gathers every `skills/<name>/SKILL.md`, clusters by shared triggers / outcome, reads the bodies, and returns each cluster already sorted into the three buckets above (with a recommended disposition). Work from its report.

> In a **worktree**, `find-overlap`’s `rev-parse --show-toplevel` resolves to the *main* checkout (see issue \#76 / the `skill-builder` warning) — that’s correct: skills live in the main checkout, edit them there.

If `find-overlap` is somehow unavailable, fall back to its inline pass — list `skills/*/` with `name` + `description` + line count (a stub is ≈ \<15 lines, a real body more), cluster, then **read the full SKILL.md of every member** of each candidate cluster before classifying.

### 2. Keep only the genuine-duplicate clusters

From `find-overlap`’s report, act **only** on bucket 3 (genuine duplicate). Leave intentional alias families (bucket 1) untouched, and hand adjacent-but-distinct clusters (bucket 2) to `link-skills` if they want a cross-link — never a merge.

### 3. Propose the consolidation plan — get approval first

Like `heal-skill`, do not mutate before the user signs off. Present, per cluster:

- **The members** and why they’re genuine duplicates (not an alias family, not adjacent-but-distinct).
- **The chosen canonical name** — prefer the most discoverable / most-used / spelled-out name; keep the one whose triggers best cover the union. State why.
- **What gets folded in** — any trigger phrase or body step unique to an absorbed skill that must survive into the canonical.
- **Which names become stubs** (all non-canonical members).
- **References to fix** — `preferences.md`, `CLAUDE.md`, other skills’ bodies that name an absorbed skill (see step 6).

### 4. Build the canonical skill

In the canonical `skills/<canonical>/SKILL.md`:

- **Union the trigger phrases** from every absorbed skill’s `description` into the canonical `description`, deduped — discoverability must not regress.
- **Fold in unique body content** — any step, caveat, or example an absorbed skill had that the canonical lacks. Keep one coherent procedure; don’t just staple the bodies together.
- Preserve the family body shape: `# <name> — <tagline>`, `## When this fires`, `## Procedure`, `## Relationship to other skills`, `## Anti-patterns`.

### 5. Convert absorbed skills to thin alias stubs

**Never `git rm` an invocation name** — overwrite it with a redirect so every existing `/name` keeps resolving:

``` markdown
---
name: <absorbed>
description: "Alias for `<canonical>`. <one-line of what it does>. Use when asked to '<trigger>', '<trigger>'."
user-invocable: true
---

# <absorbed> (alias for `<canonical>`)

This is an alias for the **<canonical>** skill. Read and follow the canonical skill:

→ **[<canonical>](../<canonical>/SKILL.md)**
```

Carry the absorbed skill’s own trigger phrases into the stub’s `description` so those phrasings still match. The stub holds **zero** procedural content — the canonical is the single source of truth.

### 6. Fix every dangling reference

A consolidated name may be mentioned elsewhere. Find and update:

``` bash
grep -rn "<absorbed>" skills/*/SKILL.md memories/ CLAUDE.md 2>/dev/null \
  | grep -v "skills/<absorbed>/SKILL.md"
```

Repoint `## Relationship to other skills` cross-links and any `preferences.md` / `CLAUDE.md` mentions at the canonical name (note the stub still works, but links should name the canonical).

### 7. Validate, then ship via branch + PR

``` bash
python3 scripts/validate-skills.py      # if present — must pass
```

Skills live in the ai-config repo — never leave changes local-only. Branch + PR (not direct to main), request `d-morrison` as reviewer (`request-pr-review`), then **ARDI to clean** (`ardi`).

``` bash
git checkout -b consolidate-<canonical>-skill origin/main   # CREATE_BRANCH
# write the canonical, overwrite absorbed skills as stubs, fix references
git add skills/<canonical>/ skills/<absorbed-1>/ skills/<absorbed-2>/   # only the
# dirs you touched — plus memories/preferences.md and/or CLAUDE.md ONLY if you
# edited them. Never `git add -A` or a bare `skills/`, which sweeps in unrelated edits.
git commit -m "skills: consolidate <a>/<b> into <canonical> (+ alias stubs)"   # COMMIT
git push -u origin HEAD && gh pr create --fill                                # PUSH, CREATE_PR
```

## Relationship to other skills

- **`find-overlap`** — the read-only detector this skill delegates its audit to; it finds and classifies the overlapping clusters, consolidate-skills merges the genuine duplicates. (find-overlap : consolidate-skills :: `pr-status` : `ardi`.)
- **`skill-builder`** — the inverse-facing sibling: it *creates* (extend-first) and, when it finds it should have extended an existing skill, hands the cleanup here.
- **`heal-skill`** — repairs *one* misfiring skill; this merges a redundant *set*. If two skills “compete for the same request” but are genuinely distinct, that’s a `heal-skill` boundary fix, not a consolidation.
- **`link-skills`** — for adjacent-but-distinct skills that should reference each other but stay separate, cross-link instead of merging.
- **`tidy` / `simplify`** — the same “collapse near-duplicates over proliferating them” instinct, applied to code rather than the skill corpus.
- **`decompose-skill`** — the mirror-image direction: this skill merges several skills into one; `decompose-skill` splits one overly-broad skill into a canonical skill plus extracted shared fragments or narrower siblings.

## Anti-patterns

- ❌ Collapsing an **intentional alias family** (canonical + redirect stubs) — that’s the target state, not a duplicate.
- ❌ Merging **adjacent-but-distinct** skills and silently dropping a capability.
- ❌ `git rm`-ing an invocation name instead of converting it to an alias stub — it breaks every existing `/name`, automation, and muscle-memory.
- ❌ Dropping trigger phrases on the floor — the canonical’s `description` must cover the **union** of the absorbed skills’ triggers, or discoverability regresses.
- ❌ Leaving procedural content in a stub — aliases redirect only; one canonical source of truth.
- ❌ Mutating before the user approves the plan, or leaving dangling references to an absorbed name in `preferences.md` / `CLAUDE.md` / other skills.

Back to top
