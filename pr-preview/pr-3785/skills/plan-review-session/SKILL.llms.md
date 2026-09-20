# plan-review-session

Convert a ranked list of common mistakes (e.g. from **grade-work**) into a review session: a self-contained chapter that, for each common error, pairs a *“common mistake”* callout with a worked correction, ordered most-impactful first.

**Origin:** built from a midterm review chapter that distilled grading findings into a new `chapters/<name>.qmd` in a Quarto course book.

## When to use

- You have a common-errors catalog and want classroom/handout material.
- The target is usually a Quarto course book, but the structure transfers to any Quarto/Markdown course site.

## Content structure

Per error category, in this order:

1.  A descriptive `##` heading that states the *correct* principle (not the mistake) — e.g. “Nelson-Aalen estimates the cumulative hazard first, then exponentiates”.
2.  A `::: {.callout-warning}` block with a `## Common mistake` sub-heading describing what students did wrong (anonymized — patterns, never names).
3.  A `::: {.solution}` block working through the correct approach with concrete numbers, reproducible R where it helps.

Order categories by **frequency × consequence**; lead each part with its most consequential error. Close with a summary table cross-linking each mistake to its section (`@sec-...`).

## Course-book conventions (the target book)

Match the existing chapters — read one first before writing.

- **Header:** front-matter with `title:` and the `html`/`revealjs`/`pdf`/`docx` format block, then the book’s shared-config include (which pulls in the R setup and any LaTeX macros).
- **Math macros:** use the book’s own math macros instead of raw LaTeX. Watch argument arity — some macros wrap their argument in parens, so for hand-written parens use the bare-operator variant.
- **Tables/figures:** use div form `::: {#tbl-...}` / `::: {#fig-...}` with the caption as the last line inside the div — *not* chunk-option `tbl-cap`.
- **Code chunks:** default `#| code-fold: true` for figure/table chunks; keep R simple and runnable.
- **Don’t** start an included subfile with a heading; one source line per major phrase keeps diffs readable.

## Wiring a new chapter in

1.  Add `- chapters/<name>.qmd` to the book’s `_quarto.yml` under the right part. (Some books split the config across separate book and website YAMLs — if so, add the chapter to each `project: render:` list **and** to the `website: navbar:` menu.)
2.  A chapter that is not in the render list won’t build on the site — don’t leave it stranded.

## Pre-commit checks (mandatory)

Run all three and fix what your change caused:

``` sh
quarto render chapters/<name>.qmd --to html      # no errors/warnings
Rscript -e 'lintr::lint("chapters/<name>.qmd")'  # no lints in your code
Rscript -e 'res <- spelling::spell_check_files("chapters/<name>.qmd", ignore = readLines("inst/WORDLIST")); print(res)'
```

- Confirm the render has no unresolved cross-refs (grep the output HTML for `?@`) and that tables/computed values resolved.
- **Spellcheck gotcha:** local `spell_check_files` on `.qmd` does *not* strip in-math content, so it false-flags LaTeX macro tokens (`mathbf`, `tfrac`, `ge`, …). CI (clean container) does not flag these. So **only add genuine prose words** to `inst/WORDLIST` (e.g. `exponentiate`); do not pollute it with math macros.

## PR

- Branch off `origin/main` (`git checkout -b <name> origin/main`); never commit to `main` directly.
- Stage only your files — the working tree may carry unrelated dirty files (e.g. CRLF-only diffs); don’t sweep them in with `git add -A`.
- Commit message ends with the Co-Authored-By line; PR body ends with the Generated-with-Claude line.
- After `gh pr create`, request a reviewer (see **request-pr-review**).
- Keep all commit/PR/issue text **anonymized** — no student names.

## Related

- **grade-work** — produces the ranked error catalog this skill consumes.
- **request-pr-review**, **r-pkg-spellcheck**, **sync-pr-branch** — the PR-hygiene skills this leans on.

Back to top
