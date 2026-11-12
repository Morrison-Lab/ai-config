# Course sites: prerequisite sequence and content placement

The Morrison-Lab course sites form a prerequisite sequence.
Place content, and direct links, according to it.

## The sequence

```
mcs -> mds -> pds -> sds -+-> lds   (prediction-focused statistics)
        |      |          |    ^
        |      +-> ids ---|----+    (information theory)
        |                 |    |
        +----> cds -------|----+    (computational complexity)
                          |
                          +-> rme   (model-inference-focused statistics)
                               ^
                               |
                         win, cie   (causal inference)
```

- mcs, mds, pds and sds form a linear chain:
  each site assumes the ones before it.
- mcs ([*Math for Computer Science*](https://morrison-lab.github.io/mcs/)) holds the shared math basics:
  logic and proof writing, sets, functions, number systems, relations, induction, growth rates, expressions and algorithms, and notation.
  mds links to those pages and no longer defines them (Morrison-Lab/mcs#60).
- sds branches into two sites that both build on it:
  - lds, which focuses on prediction
  - rme ([*Regression Models for Epidemiology*](https://morrison-lab.github.io/rme/)),
    which focuses on inference about model parameters;
    epidemiology is one area where data science is applied
- win and cie are complementary views of causal inference.
  They sit outside the statistics chain,
  and rme also depends on them.
- ids ([*Information Theory for Data Science*](https://morrison-lab.github.io/ids/))
  and cds ([*Computational Complexity for Data Science*](https://morrison-lab.github.io/cds/))
  are side branches that lds builds on.
  ids assumes pds, whose entropy, cross-entropy and Kullback--Leibler divergence it extends;
  cds assumes mds.
  sds and rme do not rely on either, but may cite them as further reading.

## Where content goes

- Put each topic in the earliest site whose readers need it.
  Material that both lds and rme need belongs in sds or earlier,
  not duplicated in either branch.
- Define a concept once, in that earliest site,
  and link to that definition from the sites after it.
- A site must not rely on a later site or a sibling branch for content.
  Linking forward or sideways is fine only as further reading on advanced topics,
  never to define or explain something the page itself needs.
  For example, sds does not send readers to rme for the definition of a residual,
  but it may point to rme's multilevel-model chapter as further reading.
- When content moves from a later site into an earlier one,
  as rme's statistics appendices are moving into sds,
  the later site then links back to the earlier site for it.

## When a full render runs too long, consider splitting the repo

Ezra, 2026-11-12 (`cai:`, [ai-config#5568](https://github.com/Morrison-Lab/ai-config/issues/5568)): "when full-repo renders in notes projects are taking excessively long, consider whether it's time to split the repo into multiple repos".

When a notes repo's full render (the publish on `main`, or a full PR preview) takes excessively long,
consider splitting the repo into several topic repos, and bring Ezra a recommendation.
The split itself is his decision.

- **Measure first.**
  Find where the time goes before blaming the repo's size:
  the freeze cache, umbrella pages that re-render their children in every format, and the fixed cost of starting each page.
  Fix those first if they are the cause.
  [mds#631](https://github.com/Morrison-Lab/mds/issues/631) is the worked example:
  per-page timings showed that splitting optimization out of mds would save at most about 14% of its HTML render.
- **Split along a topic seam**, not along a course syllabus ([ai-config#5012](https://github.com/Morrison-Lab/ai-config/issues/5012)),
  and place the new repo in the sequence above.
- **Count the cost of the split**:
  redirect stubs for every moved page and anchor, repointed links from the later sites,
  and one more repo's CI to keep green.

This rule is prose, not a hook or a check, because it asks for a judgment.
Its trigger is the wall-clock time of a render, which no PreToolUse hook sees.
A PR check cannot fail on a slow publish either, since the slowness is not a defect of the PR that started the publish.
