# Case records: reorganize-prose

Worked-example case records for the rules in
[`reorganize-prose.md`](reorganize-prose.md), kept here to stay out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Three ordering regressions in one skill

(Morrison-Lab/ai-config#1849, 2026-08-21/22, `skills/clean-git/SKILL.md`.
Three insertions broke an ordering dependency across four review rounds, all
caught by reviewers rather than by any check.

1. `$TMP` was used in four redirects with no `TMP=$(mktemp -d)` anywhere in the
   file, so every redirect targeted the filesystem root.
2. The fix added the definition, and a later commit then added a *new consumer*
   --- a pre-prune ref snapshot --- fifteen lines **above** it, reintroducing
   the same defect.
   The original fix was still correct.
   What changed is that the file had grown a use upstream of it.
3. The same snapshot also sat sixty-four lines **after** the
   `Run clean-worktrees steps 1 through 3` instruction that triggers the
   `git fetch --prune origin` it exists to precede, so it captured post-prune
   state while the surrounding prose promised "anything the prune removed is
   recoverable from it".

Regressions 2 and 3 were introduced by the same commit, and 2's fix --- hoisting
the definition --- did not generalize to 3, because 3's dependency is semantic
rather than syntactic.
Fixed in `3efa0869` and `cde9e7eb` by hoisting and by stating the ordering
requirement in the prose.)

## A sweep's count moves while you write the sentence about it

(`Morrison-Lab/ai-config#3499`, 2026-09-09: the PR that added the inbound-link
sweep bullet to [`reorganize-prose.md`](reorganize-prose.md) tried four times to
state one figure --- how many inbound references to `memories/preferences.md`
the sweep had to examine --- and got it wrong three times, each in a different
way.

**Draft 1** said "100 hits across 54 files", pairing a hit count that included
the source file's own self-mentions with a file count that excluded it.
Two populations in one sentence, and neither named.

**Draft 2** fixed the exclusion and left the snapshot implicit.
A reviewer measuring at a later commit read it as a fresh error, because the
figures genuinely collide:

| commit | including the source | excluding it |
|---|---|---|
| `18d55aa86` | 100 hits / 55 files | 97 / 54 |
| `1ac9ebb9d` | 97 / 54 | 94 / 53 |

97 excluding the source at `18d55aa86` is the same number as 97 *including* it
three commits later, because in between the sweep's own fixes repointed five
links away --- exactly the three hits and one file the self-mentions contribute.
The same figure names two populations, and nothing in the sentence said which.

**Draft 3** named the commit and then asserted the tip figure was 97 including
the source.
It was 98, and the extra hit was the sentence itself: writing "for
`preferences.md` at `18d55aa86`" into the file added a literal occurrence of the
very string being counted.
The passage teaching that a sweep moves its own population demonstrated it live,
in the commit that made the point.

**Draft 4** removed the figure from the rule and moved this record here.
That is the difference worth keeping: the number was never load-bearing --- the
rule says to narrow the list mechanically, and works identically whether the
list holds 94 entries or 98 --- so pinning it bought a maintenance burden and no
reader anything.
Per [`timestamp-volatile-claims.md`](timestamp-volatile-claims.md), a figure
that decays needs its moment attached.
The stronger move, available here and not always, was to notice the rule did not
need the figure at all.

One measurement error along the way, from the same family.
`grep -vc '^memories/preferences.md$'` against `git grep -l <ref>` output
matches nothing, because `git grep` with an explicit ref prefixes every line
with `<ref>:` --- an anchor right about the path and wrong about the line.
The reviewer tripped the mirror image on its first pass, anchoring `^\./` against
`grep -rn .` output, which carries no `./` prefix.
A filter whose scope is not checked against the thing it filters fails silently
in both directions.)
