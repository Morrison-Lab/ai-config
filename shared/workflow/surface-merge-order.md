# Surface merge-order constraints

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#surface-merge-order-constraints) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When two or more PRs are open and merging them in the wrong order would produce a wrong result,
say so where I'll act on it, not in ordinary prose I'll skim past.
Three surfaces, escalating in strength; use as many as the situation earns.

1. **In chat** --- the boxed `### 🔀 MERGE ORDER` marker defined in [`tag-chat-output`](../writing/tag-chat-output.md).
2. **On the PRs** --- lead each affected PR's body with a `> [!IMPORTANT]` alert
   naming that PR's position and its prerequisite,
   e.g. "Merge [#N](url) first --- this PR is stacked on its branch."
   Update or drop the alert once the prerequisite merges.
3. **Draft-gating** --- hold the dependent PR as a draft until its prerequisite merges,
   then mark it ready.
   GitHub won't merge a draft,
   so this makes the wrong action unavailable rather than merely discouraged.

Draft-gating is the last resort, not the default, because it costs something real:
converting a ready PR to draft **drops auto-merge and merge-queue membership**,
and a draft doesn't trigger the `@claude` review bot (see `shared/workflow/pr-on-claim.md`),
so drafting an unreviewed PR stalls its own ARDI loop.
Drive the PR to fully clean first, and draft-gate only if the prerequisite still hasn't merged.
Say in chat and on the PR that it's being held and why,
and un-draft promptly once the prerequisite lands.
A silent draft is never a substitute for stating the order.

This fires only when order changes the outcome:
a stacked PR whose base is another open PR,
a PR that would conflict or show a misleading diff if the other landed first,
a migration that must precede its consumer.
Two PRs touching disjoint files usually have no constraint,
and saying so plainly is the right answer, not an occasion for the marker.
But "disjoint" is a claim about their file *sets*, so derive both sets and check the intersection before asserting it, rather than recalling what each PR is "about" --- which is `metacognitive-monitoring.md`'s scope-claim failure (check the population, don't recall it).
`python3 scripts/pr-overlap.py -R <owner>/<repo>` is that derivation, sweeping every pair of open PRs at once and reporting how many pairs it examined alongside how many collided.
Fall back to `gh pr diff <N> --name-only` per PR only where the script cannot run, noting that the hand method misses a rename, whose new path is all the diff reports.
A follow-up PR that extends into a `shared/` (or any) file a prior PR also edited is a common collision, and the two conflict at merge time.
**An empty intersection settles the *collision* cases above and cannot see the *dependency* ones.**
A migration and its consumer, or a PR whose prose cites content another PR adds, are ordering constraints whose file sets never overlap ---
so a derived intersection of zero is evidence about conflicts, not a proof that either order is safe.
Ask separately whether one PR asserts something the other makes true.
For a citation the better fix is to dissolve the dependency rather than sequence it,
by phrasing it as a conditional that is accurate either way ---
see [`challenge-ambiguous-terminology`](challenge-ambiguous-terminology.md)'s cross-repo citation trap, which applies to a same-repo sibling PR unchanged.
The rationale behind each surface lives in `memories/preferences.md`,
alongside the rest of the taxonomy.
