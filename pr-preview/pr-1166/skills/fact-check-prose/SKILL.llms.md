# fact-check-prose — verify claims, reasoning, and computed values in prose

Prose review usually stops at style. This skill goes further: it checks whether the prose is actually **true** and its **logic actually holds** — per the standing rule in `d-morrison/ai-config`’s [`shared/writing/fact-check-prose.md`](../../shared/writing/fact-check-prose.md), which is the canonical statement of this policy (edit that file, not this skill’s procedure, if the policy itself changes).

## When this fires

- “fact-check this”, “check the math”, “verify this reasoning”, “check this proof”, “is this accurate”, “does this claim check out”
- As part of any PR/MR review where the diff touches narrative prose — docs, READMEs, lecture notes, textbook chapters, commit/PR descriptions making a substantive claim. Run it alongside (not instead of) style review (`use-preferred-style`, `find-ai-tells`) and terminology review (`challenge-ambiguous-terminology`, folded into `ard`/`ardi`).

## Procedure

### 1. Identify the target and extract checkable units

A PR/MR diff (`gh pr diff <N>` / `glab mr diff <N>`), a file, or pasted text. Read the changed prose and pull out three kinds of units to check:

- **Factual claims** — statements that cite a value, a behavior, a result, an external fact (“X was introduced in version Y”, “the estimator is unbiased under Z”).
- **Undefended claims** — a factual claim with no internal reasoning and no citation backing it, even if it turns out to be accurate. Flag it separately from an accuracy check (below) — a claim can pass accuracy and still fail this one.
- **Reasoning chains** — an argument the document makes, not just its individual facts. This includes **formal mathematical reasoning** (derivations, proofs, algebraic manipulations — check every step follows from the last, check dimensional/unit consistency, check edge cases) and **informal reasoning** (X therefore Y, a causal claim, a design justification).
- **Computed/rendered values** — a number, table entry, or figure the prose describes as the output of code, a model fit, or a render.

### 2. Check factual claims

For each factual claim, check it against domain knowledge first. Where it’s checkable against an external source — a package’s own docs, a spec, a paper, a dataset’s documentation — fetch that source (`WebFetch`/ `WebSearch`) and confirm or refute the claim against it, not against a secondhand summary. Don’t wave a plausible-sounding claim through unchecked — see [`challenge-ambiguous-terminology`](../../shared/workflow/challenge-ambiguous-terminology.md) for the sibling rule on ambiguous phrasing specifically.

Separately from accuracy, check that the claim is **defended**: does the surrounding text give reasoning for it, or does it carry a citation? A claim can be accurate and still undefended — flag both kinds of gap, not just outright inaccuracy.

### 3. Verify document-internal reasoning

Walk each reasoning chain step by step:

- **Formal math** — re-derive or spot-check each step; confirm dimensions and units are consistent at every operation; check boundary/edge cases the claim implies; confirm a cited theorem’s hypotheses actually hold in this application (e.g. don’t apply a result that requires independence to correlated data without noting it).
- **Informal arguments** — does the stated reasoning actually support the conclusion drawn, or is there a gap (an unstated assumption doing the real work, a non sequitur, an overgeneralization from one example)?

### 4. Cross-check computed values and figures against the rendered output

Don’t trust the source prose’s own description of a computed value — verify it against what was actually produced:

1.  Check whether the project has a **PR-preview deploy**. Look for a sticky preview-link comment on the PR, or check the project’s `CLAUDE.md` / `.github/workflows/` for a preview workflow (e.g. `preview.yml` + `preview-deploy.yml` built on `rossjrw/pr-preview-action`, common in this lab’s Quarto repos — those deploy to a `gh-pages` branch under `pr-preview/pr-<N>/<path>`).
2.  If a live preview exists, fetch the rendered page (`WebFetch`) and read the actual value/figure off it.
3.  If no preview covers the changed page yet, fall back to the project’s render command (e.g. `quarto render <chapter.qmd> --to html` in an R/ Quarto repo) and check the local render instead of skipping the check.
4.  Compare what’s rendered against what the prose claims. A mismatch is a finding even if the prose “sounds” right — the rendered output is ground truth, not the sentence describing it.

### 5. Report

For every unit checked:

    | Claim/step | Verdict | Basis (source checked) |
    |------------|---------|-------------------------|
    | "the estimator is unbiased" | Inaccurate | Biased under this design per [source/derivation]; see step 3 below |
    | Derivation step 4 → 5 | Confirmed | Re-derived; algebra holds, dimensions consistent |
    | "Table 2, row 3 = 4.7" | Inaccurate | Rendered preview (pr-preview/pr-N/chapter.html) shows 4.9 |
    | "adoption has grown steadily" | Undefended | No citation or reasoning given; claim itself checks out but needs a source or an explicit basis |

Then, separately, list **additional citations/references worth adding** — proactively, anywhere a pointer to a source would help a reader, not only where a claim is currently flagged as uncited.

### 6. Offer to apply corrections

On request, fix the flagged inaccuracies and reasoning gaps in place with `Edit`, preserving the author’s intent and voice — same posture as `find-ai-tells`’s apply step. Don’t silently rewrite without being asked; report first.

## Relationship to other skills

- [`challenge-ambiguous-terminology`](../../shared/workflow/challenge-ambiguous-terminology.md) — catches phrasing whose meaning is *unresolved*; this skill catches claims and reasoning that are resolved but *wrong*. Run both during review.
- **`use-preferred-style` / `find-ai-tells`** — style and AI-tell scans; this skill is the accuracy/reasoning counterpart, not a replacement.
- **`ard` / `ardi`** — when a reviewer (human or bot) flags a factual or reasoning error, `ard` handles the response disposition; this skill is how you (as reviewer) *find* that class of error in the first place.
- **`prose-fact-checker` agent** — the read-only, parallelizable version of step 2–4 above, for fanning claim-checking out across a `Workflow` when a document has many independent claims to verify at once.
- **`check-info-quality` (`ciq`)** — this skill verdicts a claim **Accurate / Inaccurate / Undefended**; `ciq`’s check C catches a claim that’s accurate by this skill’s own standard yet still misleads (missing context, cherry-picking, a citation that only weakly supports it). `ciq` also covers two failure modes this skill doesn’t: stale claims (check A) and irrelevant content (check B). Run both.

## Anti-patterns

- **Don’t** accept a claim because it sounds authoritative — check it.
- **Don’t** skip a derivation step because “it’s probably fine” — re-derive it or flag it as unverified, not silently pass it.
- **Don’t** trust the prose’s own description of a computed value when a rendered artifact (preview or local render) is available to check it against directly.
- **Don’t** limit citation suggestions to claims already flagged as uncited — suggest them anywhere they’d help a reader, per the fragment’s policy.

Back to top
