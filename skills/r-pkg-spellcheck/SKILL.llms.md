# r-pkg-spellcheck

Verifies spelling locally before pushing R-package changes that touch text the `Spellcheck` CI workflow scans. The repo runs `spelling::spell_check_package()` in CI and treats unknown words as a failure — the only allow-list is `inst/WORDLIST`.

**Why this exists:** a push that adds new words (e.g. `assignees`, `PR's`, `SHA`) to NEWS.md without updating `inst/WORDLIST` fails Spellcheck CI and forces a follow-up push.

## When to run

Before `git push` if the diff touches any of:

- `NEWS.md` (or `NEWS`)
- `R/*.R` roxygen comments (`#'`)
- `man/*.Rd`
- `vignettes/*.Rmd`
- `README.Rmd` / `README.md`
- `DESCRIPTION` `Title:` / `Description:` fields

CI-only / workflow-YAML changes alone don’t need a spellcheck pass.

## Procedure

1.  **Confirm this is an R package.** Check that `DESCRIPTION` exists at the repo root. If not, skip — this skill doesn’t apply.

2.  **Run the same check CI runs:**

    ``` sh
    Rscript -e 'spelling::spell_check_package()'
    ```

    - Exit code is 0 even with misspellings; check stdout for `WORD FOUND IN` blocks. No output = clean.
    - If `spelling` isn’t installed: `Rscript -e 'install.packages("spelling")'` then retry. If R isn’t available at all, fall back to step 4.

3.  **Triage each flagged word:**

    - Real misspelling → fix it in the source file.
    - Legitimate technical term, proper noun, acronym, or domain word → add to `inst/WORDLIST`.
    - Possessive of an existing word (e.g., `PR's`) → usually rewrite as `PR` or `the PR's foo`; only WORDLIST it if rewriting hurts clarity.

4.  **Add to `inst/WORDLIST` correctly.** This is the easy place to break CI.

    - The file is LC_ALL=C ASCII-sorted with CRLF line endings.

    - Preserve both — a quick Python pass works:

      ``` sh
      python3 -c 'import sys; lines=sorted(set(open("inst/WORDLIST","rb").read().decode().splitlines())); open("inst/WORDLIST","wb").write(("\r\n".join(lines)+"\r\n").encode())'
      ```

    - Or use `Rscript -e 'spelling::update_wordlist()'` interactively (it handles sort + line endings automatically).

5.  **Re-run step 2** to confirm clean before pushing.

## If R isn’t available

Manually scan the added text for: - Proper nouns and acronyms (SHA, API, JSON, etc.) - Possessives (`PR's`, `repo's`) - Compound technical terms

Compare against `inst/WORDLIST`. Acronyms and possessives are the usual misses.

## Related

This pattern applies to any R package using the `spelling` package’s GitHub Actions workflow.

This skill only spellchecks text that’s already there. For the broader R-package release workflow it’s one narrow slice of, see [`r-pkg-check`](../../skills/r-pkg-check/SKILL.llms.md) (a full `devtools::check()`/ `R CMD check` sweep), [`r-pkg-news`](../../skills/r-pkg-news/SKILL.llms.md) (drafting a new NEWS.md entry, as opposed to spellchecking one already written), and [`r-pkg-cran-checklist`](../../skills/r-pkg-cran-checklist/SKILL.llms.md) (the full CRAN submission checklist).

Back to top
