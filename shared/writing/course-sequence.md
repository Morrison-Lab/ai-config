# Course sites: prerequisite sequence and content placement

The Morrison-Lab course sites form a prerequisite sequence.
Place content, and direct links, according to it.

## The sequence

```
mds -> pds -> sds -+-> lds   (prediction-focused statistics)
                   |
                   +-> rme   (model-inference-focused statistics)
                        ^
                        |
                  win, cie   (causal inference)
```

- mds, pds and sds form a linear chain:
  each site assumes the ones before it.
- sds branches into two sites that both build on it:
  - lds, which focuses on prediction
  - rme ([*Regression Models for Epidemiology*](https://morrison-lab.github.io/rme/)),
    which focuses on inference about model parameters;
    epidemiology is one area where data science is applied
- win and cie are complementary views of causal inference.
  They sit outside the statistics chain,
  and rme also depends on them.

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
