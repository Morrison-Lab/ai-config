# link-skills — find cross-reference gaps across skills

Skills in this repo cross-reference each other under a `## Relationship to other skills` section, so a reader who lands on one skill discovers the related ones. As the corpus grows, those links drift: a skill gets added without back-links, a workflow family gains a member that its siblings never mention, an A→B link never gets its B→A return. This skill **audits the whole `skills/` tree for those gaps and proposes the missing links.**

It’s the *discovery* counterpart to `scripts/check-links.py` (which only guards *existing* relative links from breaking), and the corpus-wide counterpart to `skill-builder` (which cross-links just the one skill being authored).

## When this fires

- “link skills”, “link-skills”, “cross-link the skills”
- “find cross-link opportunities”, “which skills should reference each other”, “audit skill cross-references”, “find missing skill links”
- After adding a batch of skills, or proactively when you notice a related skill goes unmentioned by its obvious sibling.

## What counts as a cross-link gap

Three kinds, roughly in priority order:

1.  **Asymmetric reference** — skill A’s body names skill B (in backticks or via a `skills/B/` link), but B’s `## Relationship to other skills` never names A. The return link is almost always warranted.
2.  **Thematic-cluster gap** — a set of skills clearly belong to one workflow family (e.g. the review/iterate family `ard` / `ardi` / `ardia`, the branch/sync family `sync-pr-branch` / `merge-main` / `clean-branches`), but some members don’t point to the others.
3.  **Missing section** — a *real* skill (one with `allowed-tools:`, not a thin alias redirect) has no `## Relationship to other skills` section at all.

Not every co-mention is a gap. Aliases only redirect to their canonical and need no Relationship section. Judgment decides which candidates are real — this skill *surfaces* candidates; it doesn’t link blindly.

## Procedure

### 1. Move to the repo and inventory the skills

``` bash
cd "$(git -C ~/.claude/skills/link-skills rev-parse --show-toplevel)"   # the ai-config repo
ls skills/
```

Real skills declare `allowed-tools:`; alias files don’t. Separate the two — only real skills are expected to carry a Relationship section:

``` bash
for f in skills/*/SKILL.md; do
  grep -q '^allowed-tools:' "$f" && kind=real || kind=alias
  grep -q 'Relationship to other skills' "$f" && rel=has-rel || rel=NO-REL
  printf '%-8s %-8s %s\n' "$kind" "$rel" "$f"
done
```

`real NO-REL …` lines are gap-kind 3 candidates.

### 2. Build the reference graph (who names whom)

For every ordered pair of skills, record when one skill’s body names the other — backticked (`` `name` ``) or as a `skills/name/` link. Iterate the glob directly so the loop runs the same under bash and zsh (no `mapfile`):

``` bash
for sd in skills/*/; do s=$(basename "$sd")
  for td in skills/*/; do t=$(basename "$td")
    [ "$s" = "$t" ] && continue
    grep -qE "\`$t\`|skills/$t/" "skills/$s/SKILL.md" 2>/dev/null && echo "$s $t"
  done
done | sort -u > /tmp/edges.txt
wc -l /tmp/edges.txt
```

### 3. Flag the asymmetric edges (gap-kind 1)

An edge `A B` with no matching `B A` is a one-directional reference — a candidate return link:

``` bash
# print A->B where B->A is absent
while read -r a b; do
  grep -qxF "$b $a" /tmp/edges.txt || echo "ONE-WAY: $a -> $b  (consider $b -> $a)"
done < /tmp/edges.txt
```

Expect alias→canonical pairs (`adr -> ard`) and short-name noise to dominate the raw list — both are filtered by the judgment in the note below and step 4.

> **Short-name noise.** Two-letter skills (`st`, `gi`, `cb`, `dc`, `ts`, `rc`, `and`) match backticked prose that isn’t a skill reference. Treat their edges as *candidates to eyeball*, not confirmed links. Reading the surrounding line settles it fast.

### 4. Apply judgment to clusters (gap-kind 2)

The graph won’t catch a sibling that’s simply never mentioned. Skim the skill list for workflow families and check each member points to the others — the review/iterate family, the branch/sync family, the issue-grabbing family (`gi` / `gii` / `gia`), the memory family (`memorize` / `ums` / `record-learnings`), the style family (`use-preferred-style` / `find-ai-tells`). Add the missing links.

### 5. Propose minimal edits, then validate

For each confirmed gap, add a bullet to the target skill’s `## Relationship to other skills` section (create the section just above `## Anti-patterns` if it’s missing), matching the house format — bolded backticked skill name, em-dash, one line on *why they relate*:

``` markdown
- **`other-skill`** — one line on how the two relate / hand off.
```

Show the user the exact diffs before applying. After editing, confirm no link broke:

``` bash
python3 scripts/check-links.py
python3 scripts/validate-skills.py   # if present — schema/frontmatter sanity
```

### 6. Ship it

Skill edits live in the ai-config repo — never local-only. Commit on a branch, open a PR, request `the repository owner` (see `request-pr-review`), and ARDI to clean (see `ardi`). Stage skills via their real `skills/<name>/SKILL.md` path, not through the `.claude/skills` symlink (`git add` rejects the symlinked path).

## Relationship to other skills

- **`skill-builder`** — authors a new skill and cross-links *that* skill on the way in; this skill is the corpus-wide audit that catches the links a single authoring pass missed.
- **`heal-skill`** — repairs one skill that misfired (including fixing an ambiguous overlap by cross-linking the two); `link-skills` is the proactive, whole-corpus sweep rather than a reaction to one failure.
- **`find-overlap`** — the complementary detector: `link-skills` finds skills that should *reference* each other but don’t; `find-overlap` finds skills that *duplicate* each other. When `find-overlap` flags an adjacent-but-distinct cluster (overlap that shouldn’t merge), the fix is a cross-link — this skill.
- **`request-pr-review`, `ardi`** — ship and clean the resulting PR.

## Anti-patterns

- ❌ Adding a link in only one direction when the relationship is mutual — that just creates the next audit’s gap.
- ❌ Linking every co-mention. A passing reference isn’t a relationship; only link skills a reader of one would genuinely want to discover from the other.
- ❌ Cross-linking two skills that are really near-duplicates — that’s a merge job for `simplify` / `tidy`, not a link.
- ❌ Adding a Relationship section to a thin **alias** file — aliases only redirect to their canonical.
- ❌ Trusting the short-name (`st`, `gi`, …) edges without reading the line — they over-match.
- ❌ Skipping `scripts/check-links.py` after editing — a typo’d `skills/<name>/` link silently rots.
- ❌ Leaving the edits local-only or pushing straight to main.

Back to top
