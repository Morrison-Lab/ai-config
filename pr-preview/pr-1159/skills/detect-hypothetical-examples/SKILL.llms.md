# detect-hypothetical-examples — find invented illustrations where real data exists

A worked example can be perfectly well-formed — its own `{#exm-...}` div, a clean derivation, correct arithmetic — and still reach for invented, round-number quantities (“suppose 20% of the exposed group…”) when the document already loads a real dataset it uses elsewhere. That’s not a wrong example, and it’s not `detect-informal-definitions`’s missing-div problem — it’s a missed opportunity to ground the teaching point in real data that was already sitting right there.

The full detection heuristic, confirmation checklist, and fix menu live in [`shared/writing/hypothetical-examples.md`](../../shared/writing/hypothetical-examples.md) — read it before running this skill; the steps below are the short version.

## When this fires

- “detect hypothetical examples”, “find hypothetical examples”, “replace hypothetical examples with real data”, “is this example using made-up numbers”, “this example should use the real dataset”, “detect-hypothetical-examples”
- **As part of any PR/MR review, or self-review before a push, that introduces or edits a worked example** — run alongside `detect-informal-definitions`, `fix-forward-references`, `fact-check-prose`, and `find-ai-tells`.

## Procedure

1.  **Identify the target.** A file, a PR/MR diff, or pasted prose that introduces or edits a worked example (an `{#exm-...}` div, or the equivalent in a non-Quarto project).
2.  **Grep for candidates** using the patterns in [`hypothetical-examples.md`](../../shared/writing/hypothetical-examples.md#the-detection-heuristic) — the “hypothetical”/“suppose a”/“consider a hypothetical”/“if N% of” signal phrases, plus suspiciously round proportions (`0.1`, `0.3`, `20%`) sitting inside an example or definition div.
3.  **Check for a real dataset already in scope** — a `read.csv`/ `read_csv`/`glm(...)`-style loading chunk earlier in the same document, or a project-level running-example dataset convention. No real dataset in scope at all means the hit isn’t a finding — skip it.
4.  **Confirm each remaining candidate** against the checklist in the fragment: does the loaded dataset actually have the variables this example needs? Is the example illustrating a general mechanism that never needed a specific number? Would forcing real numbers erase a deliberate edge case or a proof-of-concept introduced before the real data appears? Drop anything that fails the “real data available, number actually needed, no unrealizable edge case” bar.
5.  **Fix each confirmed finding**, per the fragment’s fix menu — recompute from the real dataset first; if the real effect is much weaker, search for a more naturally illustrative real covariate/subset before falling back to explicitly hedged toy numbers; verify any real substitute’s arithmetic numerically against the actual data before publishing.
6.  **Re-check the surrounding text** after substituting real numbers — a sentence built around the invented effect size’s magnitude (“a stark 40 percentage-point gap”) often needs rewording once the real number is much smaller.
7.  **Report.** For each finding: the phrase and location, whether a real substitute worked or the fix was a hedge/search-for-a-better-covariate, the before/after numbers, and the diff.

## Relationship to other skills

- **`detect-informal-definitions`** — a sibling content-quality check on the same `#exm-`/`#def-` divs, but a different failure mode: that skill catches a concept defined with definitional precision that never got a formal div; this skill assumes the div already exists and asks whether its illustrative *numbers* should have come from real data instead of being invented.
- **`fact-check-prose`** — verifies a document’s claims and computed values are correct; this skill runs upstream of that, since an invented example can be internally consistent and still be a finding here even before any accuracy check applies.
- **`math-derivation-steps.md`** (cited from `CLAUDE.md`’s “math derivations” section, not a standalone skill) — governs the completeness of a derivation’s algebraic steps; run it alongside this skill when substituting real numbers into an existing derivation, since every step needs re-verifying against the new values.
- **`check-info-quality`** — its misleading/out-of-context check (check
  3.  covers a citation or statistic that misrepresents its source; this skill is narrower and fires even with no citation involved, whenever a made-up number stands in for a value the document’s own data could have supplied.
- **`ard` / `ardi`** — when reviewing a PR/MR, or self-reviewing before a push, apply this check alongside the other prose-review rules `CLAUDE.md` lists.

## Anti-patterns

- ❌ Flagging every invented number as a finding — first confirm a real dataset with the needed variables actually exists in scope; if none does, there’s nothing to substitute.
- ❌ Treating an abstract statement that never needed a specific numeric example as a finding just because it names a general mechanism.
- ❌ Mechanically substituting real numbers into an example without checking whether the resulting effect size still makes the teaching point — silently publishing a collapsed, unpersuasive example is worse than flagging the tradeoff and choosing a hedge or a better covariate.
- ❌ Eyeballing a real-data substitution instead of numerically verifying the new arithmetic against the actual dataset.
- ❌ Leaving a stale magnitude description (“a large gap”, “20 points higher”) in the surrounding prose after the underlying numbers changed.
- ❌ Silently keeping invented numbers without hedging them, when a real substitute wasn’t available — present a toy scenario as a toy scenario, not as if it were computed from data.

Back to top
