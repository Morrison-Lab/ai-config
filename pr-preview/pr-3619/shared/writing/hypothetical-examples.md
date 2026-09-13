A worked example that illustrates a definition or theorem with **invented,
round-number quantities** --- "Suppose a binary covariate Z...", "If 20% of
the exposed group experience the outcome...", "Consider a hypothetical
scenario with two strata..." --- reaches for made-up data even when the
document already has a **real, already-loaded dataset** it uses elsewhere.
That's a distinct content-quality gap: it isn't wrong math, and it isn't
[`informal-definitions.md`](informal-definitions.md)'s missing-formal-div
problem (the example can sit in a perfectly well-formed `{#exm-...}` div) ---
it's a missed opportunity to ground the illustration in the project's own
running data instead of a toy scenario.

## The detection heuristic

Grep for the recurring signal phrases inside a worked-example or
formal-definition div:

```bash
rg -n '\b(hypothetical|[Ss]uppose a\b|[Ss]uppose the\b|[Ss]uppose only\b|[Ii]n a population where\b|[Cc]onsider a hypothetical|[Ii]f \d+% of\b)' <file>
```

Also grep for a made-up round-number proportion or rate sitting inside an
`#exm-`/`#def-` div --- `\b\d+%` for a round percentage (no trailing `\b`:
`%` isn't a word character, so a boundary right after it never matches
ordinary prose like "20% of"), or `\b0\.[1-9]0?\b` for a one- or two-digit
decimal (a suspiciously round value such as `0.1`, `0.3`, `0.20` is a
stronger signal than an irregular one like `0.112`, which reads as computed
rather than chosen for the example):

```bash
rg -n '\b\d+%|\b0\.[1-9]0?\b' <file>
```

For each hit, check whether the same document (or project) already loads a
real dataset earlier in execution order --- a `read.csv`/`read_csv`/
`haven::read_dta` call, a `glm(...)`/`lm(...)`/`coxph(...)` fit, or a
loaded data frame referenced elsewhere in the chapter --- or whether the
project has a documented "running example dataset" convention (e.g. this
book's WCGS dataset, used throughout `rme`). A hit with **no** real dataset
available anywhere in scope isn't a finding for this check; skip it.

## Confirming a candidate

Not every invented-number example is a finding. Check each hit against
these before flagging it:

1. **Is a real dataset actually already available for this specific
   illustration?** The check above only confirms *a* dataset is loaded
   somewhere in the document --- confirm it also has the variables the
   example needs (the right covariate, the right outcome, a comparable
   stratification).
2. **Is the invented-number version teaching a general mechanism that
   doesn't depend on a specific numeric example?** An abstract statement
   ("as the sample size grows, the estimator's variance shrinks") doesn't
   need real numbers to make its point --- don't flag prose that never
   needed a worked numeric example in the first place.
3. **Would forcing real numbers actually erase the point being
   illustrated?** A deliberately extreme edge case (complete separation, a
   degenerate distribution), a proof-of-concept introduced before the real
   dataset appears in the document, or a scenario the real data simply
   doesn't contain, are all legitimate reasons to keep an invented
   scenario. Confirm this by checking whether the real dataset can
   actually produce the pattern being taught, not by assuming it can't.

Only a candidate with an available real substitute, a genuine need for a
concrete number, and no dependence on an unrealizable edge case is a
confirmed finding.

## Fixing a confirmed finding

Fixing isn't mechanical find-and-replace --- forcing every invented number to
come from the real dataset's actual value can produce a much less dramatic
effect than the toy numbers showed (a confounding example built to show a
0.20-vs-0.14 gap can collapse to a real ~0.112-vs-0.109 gap once it's
recomputed from actual data), which can undermine the very point the example
exists to teach. Work through the fix menu in order:

1. **Recompute the illustration directly from the real dataset**,
   preserving the same worked-example structure (same steps, same
   notation) --- just substitute the invented inputs for values pulled from
   the data.
2. **If the real data's effect is much weaker and that undermines the
   teaching point**, do one of:
   - Search the real dataset for a more naturally illustrative
     covariate or subset first --- a different stratifying variable, a
     different subgroup --- before giving up on a real substitute.
   - If no real substitute makes the point clearly, keep the invented
     numbers but **hedge them explicitly and visibly**: "for
     illustration, suppose..." or a labeled toy scenario clearly
     distinguished from the document's real running example, rather
     than silently presenting invented numbers as if they were data.
3. **When a real substitute is used, verify the arithmetic numerically
   against the actual data** --- rerun the computation against the loaded
   dataset and compare --- before publishing. Don't eyeball whether the
   substituted numbers are plausible.

## Relationship to other checks

- **[`informal-definitions.md`](informal-definitions.md)** --- a sibling
  content-quality check on the same `#exm-`/`#def-` divs, but a different
  failure mode: that check catches a concept defined with definitional
  precision that never got its own formal div; this check assumes the div
  already exists and asks whether its *illustrative numbers* should have
  come from real data instead of being invented.
- **[`fact-check-prose.md`](fact-check-prose.md)** --- checks whether a
  document's claims and computed values are correct; this check is
  upstream of that: even a correctly-computed invented example is still a
  missed opportunity to use real data, which `fact-check-prose.md`'s
  accuracy lens alone wouldn't flag (an invented example can be
  internally consistent and still not be a finding for that check).
- **[`math-derivation-steps.md`](math-derivation-steps.md)** --- governs
  the completeness of the algebraic steps inside an example's derivation;
  this check governs where the example's *input numbers* come from. Apply
  both when fixing a confirmed finding, since replacing invented inputs
  with real ones is exactly the kind of edit that needs every step
  re-verified.
- **[`check-info-quality`](../../skills/check-info-quality/SKILL.md)** ---
  its check C (misleading/out-of-context information) covers a citation
  or statistic that misrepresents its source; this check is narrower and
  applies even with no citation involved at all, whenever a made-up
  number stands in for a value the document's own data could have
  supplied.
