# check-prose-claims — read-only check of claims, reasoning and values in prose

The *check* half of `fact-check-prose`, factored out so it runs forked ([ai-config#914](https://github.com/Morrison-Lab/ai-config/issues/914)). It checks whether prose is true and its logic holds, per [`shared/writing/fact-check-prose.md`](../../shared/writing/fact-check-prose.md), and returns a verdict table. It changes nothing: `fact-check-prose` runs it, then applies corrections in the main session on request, and you can run this skill on its own for a report with no edits.

## Step 1 — Resolve the target and extract checkable units

A PR/MR diff (`gh pr diff <N>` / `glab mr diff <N>`), a file, or pasted text. A forked run cannot ask the user, so when the target is ambiguous, take the narrowest reasonable reading and state at the top of the report which reading you chose. Read the changed prose and pull out the checkable units:

- **Factual claims** — statements that cite a value, a behavior, a result, an external fact (“X was introduced in version Y”, “the estimator is unbiased under Z”).
- **Undefended claims** — a factual claim with no internal reasoning and no citation backing it, even if it turns out to be accurate. Flag it separately from an accuracy check: a claim can pass accuracy and still fail this one.
- **Reasoning chains** — an argument the document makes, not just its individual facts. This includes **formal mathematical reasoning** (derivations, proofs, algebraic manipulations: check every step follows from the last, check dimensional/unit consistency, check edge cases) and **informal reasoning** (X therefore Y, a causal claim, a design justification).
- **Computed/rendered values** — a number, table entry, or figure the prose describes as the output of code, a model fit, or a render.
- **Citations to external works** — identify all sources cited that will need to be checked.
- **Config list and allowlist criteria** — when prose describes why an entry belongs on an allowlist or exclusion list, or what its entries have in common, verify the claim against the defining comment or documentation in code.
- **Protections, sandboxes, and security controls** — when prose documents how to configure a protection (a sandbox, an allowlist, a permission, a firewall), check each mode, platform limitation, precedence rule, and escape hatch against source documentation.

## Step 2 — Pre-flight readiness gate (hard stop)

If the target cites no external works, skip this gate. Otherwise, before evaluating any claim against an external source, check whether the repository’s local source corpus (`sources/` or equivalent) actually contains the needed sources:

1.  **Are required sources missing from the local corpus?**
2.  **Is the required source present but unconverted?** For example, a `.pdf`, `.docx`, or `.epub` file without a corresponding Markdown conversion.

If either holds, **refuse to run**: do not silently narrow scope, do not partially check around the gap, and do not fall back to memory or the open web for the missing sources. Return **`Pre-flight: NOT READY`** instead of a report, with remediation instructions, such as “Populate the `sources/` directory with Markdown conversions of the cited works so they can be verified locally.”

## Step 3 — Check factual claims

Check each factual claim against domain knowledge first. Where it is checkable against an external source (a package’s own docs, a spec, a paper, a dataset’s documentation), fetch that source **from the local `sources/` corpus**. Do **not** fall back to the open web (`WebFetch`) for a cited source missing from the local corpus; `WebFetch` is for rendered previews (step 5), not for cited works. If a local source turns out to be incomplete (a missing chapter, for example), abort and return **`Pre-flight: NOT READY`**. Confirm or refute the claim against the local source, not against a secondhand summary. Don’t wave a plausible-sounding claim through unchecked; [`challenge-ambiguous-terminology`](../../shared/workflow/challenge-ambiguous-terminology.md) is the sibling rule for ambiguous phrasing.

Separately from accuracy, check that the claim is **defended**: does the surrounding text give reasoning for it, or does it carry a citation?

When prose documents how to configure a protection or security control, verify four dimensions against the upstream source docs:

- **Modes:** what happens in non-default modes (bypass, prompt, strict).
- **Platforms:** where it does not run, and whether it fails open or fails closed.
- **Precedence:** what overrides it (project vs user settings, flags, env vars), and whether list-valued options merge or replace.
- **Escape hatches:** retries, exclusions, exceptions, or unmonitored tools.

## Step 4 — Verify document-internal reasoning

Walk each reasoning chain step by step:

- **Formal math** — re-derive or spot-check each step; confirm dimensions and units are consistent at every operation; check boundary and edge cases the claim implies; confirm a cited theorem’s hypotheses actually hold in this application (don’t apply a result that requires independence to correlated data without noting it).
- **Informal arguments** — does the stated reasoning support the conclusion drawn, or is there a gap (an unstated assumption doing the real work, a non sequitur, an overgeneralization from one example)?

## Step 5 — Cross-check computed values and figures against the rendered output

Don’t trust the prose’s own description of a computed value. Verify it against what was actually produced:

1.  Check whether the project has a **PR-preview deploy**: a sticky preview-link comment on the PR, or a preview workflow named in the project’s `CLAUDE.md` or `.github/workflows/` (such as `preview.yml` + `preview-deploy.yml` built on `rossjrw/pr-preview-action`, which deploy to a `gh-pages` branch under `pr-preview/pr-<N>/<path>`).
2.  If a live preview exists, fetch the rendered page (`WebFetch`) and read the actual value or figure off it.
3.  If no preview covers the changed page yet, render a scratch copy with the project’s render command (`quarto render <chapter.qmd> --to html` in an R/Quarto repo) and check that render instead of skipping the check.
4.  Compare what’s rendered against what the prose claims. A mismatch is a finding even if the prose sounds right: the rendered output is ground truth, not the sentence describing it.

## Step 6 — Return the report

Return the report only, one row per unit checked:

    | Claim/step | Verdict | Basis (source checked) |
    |------------|---------|-------------------------|
    | "the estimator is unbiased" | Inaccurate | Biased under this design per [source/derivation]; see step 3 below |
    | Derivation step 4 → 5 | Confirmed | Re-derived; algebra holds, dimensions consistent |
    | "Table 2, row 3 = 4.7" | Inaccurate | Rendered preview (pr-preview/pr-N/chapter.html) shows 4.9 |
    | "adoption has grown steadily" | Undefended | No citation or reasoning given; claim itself checks out but needs a source or an explicit basis |

A unit you genuinely could not check is **Unverifiable**, with the reason. Then, separately, list **additional citations worth adding**, anywhere a pointer to a source would help a reader, not only where a claim is flagged as uncited. Do not edit or write anything, even with `Bash`.

## Runs forked; `background: false` for synchronous return

This whole skill runs isolated as the `prose-claim-auditor` custom agent (`context: fork` + `agent: prose-claim-auditor`), as `find-reproducibility-gaps` does with `reproducibility-auditor`. Every step above needs only that agent’s tools (`Bash`, `Read`, `Grep`, `Glob`, `WebFetch`). The harness gives the fork no Edit or Write tool; the agent keeps `Bash` for its checks, so avoiding a write-capable shell command is still instruction-level. The agent has no `Agent` tool either, so a forked run checks every unit itself; the per-claim `prose-fact-checker` fan-out stays a main-session option. `background: false` returns the report before the caller continues, because the caller acts on it.

## Relationship to other skills

- **`fact-check-prose`** — the act half: runs this skill, then applies the corrections this report names, on the user’s request.
- **`prose-fact-checker` agent** — checks one unit handed to it; this skill’s agent covers a whole target in one pass.
- **`check-info-quality` (`ciq`)** — its check C catches a claim that passes here yet still misleads.

Back to top
