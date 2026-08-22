# Case records: reorganize-prose

Worked-example case records for the rules in
[`reorganize-prose.md`](reorganize-prose.md), moved here verbatim to keep them
out of the auto-loaded `CLAUDE.md` context.
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
