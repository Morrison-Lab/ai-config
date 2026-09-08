# R linting and formatting

Split out of [`r-quarto.md`](r-quarto.md) when that file reached two lines of
headroom under the 1250-line gate (ai-config#1306, ai-config#2003). The three
tools here answer one question --- what shape must R source be in before CI
accepts it --- so they were the seam that leaves both halves coherent rather
than merely shorter.

`r-quarto.md` keeps everything else about the R toolchain, including the
spell-check and WORDLIST material, which is a different kind of check.

Every pull request and issue cited below is a clickable link, per
[AGENTS.md](../AGENTS.md)'s "File formatting & links" rule, whose
illustrative-token exception is what leaves `#629` in the
`commented_code_linter` entry bare.

## lintr — no built-in function-length (line-count) linter; custom-linter pattern

`{lintr}` has no built-in linter that flags functions by raw line count — it's
a long-standing unimplemented upstream feature request
([r-lib/lintr#361](https://github.com/r-lib/lintr/issues/361)). The closest
built-in is `lintr::cyclocomp_linter()`, which flags branching/decision
complexity (via `{cyclocomp}`), not line count — a reasonable proxy but not
the same metric. When a repo wants an actual `<N`-lines heuristic enforced,
write a custom linter.

Working pattern (verified against lintr 3.3.0):

```r
function_length_linter <- function(length_limit = 150L) {
  xpath <- "//FUNCTION/parent::expr | //OP-LAMBDA/parent::expr"

  lintr::Linter(linter_level = "expression", function(source_expression) {
    if (!lintr::is_lint_level(source_expression, "expression")) {
      return(list())
    }
    xml <- source_expression$xml_parsed_content
    fun_defs <- xml2::xml_find_all(xml, xpath)
    n_lines <- as.integer(xml2::xml_attr(fun_defs, "line2")) -
      as.integer(xml2::xml_attr(fun_defs, "line1")) + 1L
    lintr::xml_nodes_to_lints(
      fun_defs[n_lines > length_limit],
      source_expression = source_expression,
      lint_message = sprintf("Function spans more than %d lines.", length_limit),
      type = "warning"
    )
  })
}
```

The XPath `//FUNCTION/parent::expr | //OP-LAMBDA/parent::expr` catches both
`function(...)` and `\(...)` lambda syntax; `line1`/`line2` are XML attributes
from `xmlparsedata` on the matched node, so line span is `line2 - line1 + 1`.
`linter_level = "expression"` + the `is_lint_level()` guard is `lintr`'s own
documented pattern (see `vignette("creating_linters", package = "lintr")`).
Needs `lintr (>= 3.1.2)` for the `linter_level` argument. (Landed as
`lms::function_length_linter()` in [UCD-SERG/lab-manual#381](https://github.com/UCD-SERG/lab-manual/pull/381).)

## lintr's `commented_code_linter` truncates at the SECOND `#`, so `# text #NNN` can flag as commented-out code

`commented_code_linter` strips a comment's leading `#` and tries to
`parse()` what remains, flagging the line when parsing succeeds (the
premise being that valid R syntax left in a comment is probably disabled
code).
R's own comment rule stops at the *first* unescaped `#` it meets, so a
comment carrying a second `#` --- an inline issue reference like `#629` ---
is truncated there when the linter re-parses it: `# Before #629 the ...`
strips to `Before`, which is a bare symbol and therefore valid R, so the
whole comment gets flagged as commented-out code.

Any comment whose text *before* an inline `#NNN` reference reduces to a
single valid R symbol trips this --- a lone identifier, a lone number, a
short assignment-shaped fragment.

- **Do:** reword so the fragment before the issue number is not a bare,
  parseable symbol on its own (add a verb, a preposition, anything that
  fails to `parse()`), or move the issue reference elsewhere in the
  sentence.
- **Don't:** treat a `commented_code_linter` hit on a comment containing an
  issue reference as a false positive to suppress --- reword it instead,
  since the same truncation will re-trigger on the next reviewer's re-run.

([`UCD-SERG/serocalculator#668`](https://github.com/UCD-SERG/serocalculator/pull/668), 2026-09-01.)

## air (R formatter) vs lintr's `indentation_linter` — keep `indent-width` aligned

- `air`'s `air.toml` `[format]` table has a configurable `indent-width`
  (default 2). Air indents a multi-line function *definition*'s arguments by a
  *single* level (one `indent-width`), NOT the styler/tidyverse-style-guide
  "double indent". lintr's default `indentation_linter` also expects a single
  2-space indent there. So air's default output and lintr agree at 2 --- but a
  repo that sets `air.toml` `indent-width = 4` (as `d-morrison/altdoc` does)
  will have air-formatted signatures that a *different* repo's lintr (default
  2) rejects.
- **Practical failure:** old styler-formatted code (4-space double-indent
  function signatures) sitting in a repo whose `.lintr` uses
  `lintr::linters_with_defaults()` passes CI only until a PR *touches* that
  file --- `lint-changed-files` then flags `[indentation_linter] Indentation
  should be 2 spaces but is 4 spaces`. Fix by reformatting the signature to a
  single 2-space indent (de-indent the arg block by 2), and set/confirm
  `air.toml` `indent-width = 2` so a future `air format` keeps it lintr-clean.
  (Only the *first* mis-indented line of a block is reported; de-indent the
  whole signature block, not just the flagged line, or the next line flags on
  the next run.) ([UCD-SERG/serocalculator#503](https://github.com/UCD-SERG/serocalculator/pull/503), 2026-07.)
- **Recurred on [UCD-SERG/serocalculator#672](https://github.com/UCD-SERG/serocalculator/issues/672), 2026-09-01, from the lab's own
  4-space continuation indent rather than from leftover styler output**: a
  PR touching one R file whose function signatures already used that indent
  turned `lint-changed-files` (whole-file `lintr::lint_package()` scope) red
  on lines the PR never wrote, while `lint / lint-changed-lines` (the
  diff-scoped job) stayed green, because it only lints lines the diff
  actually touched.
  The two jobs disagreeing on the same PR is not a contradiction to resolve
  --- it is the intended difference in scope --- but only the line-scoped
  job asks a question the PR's author can actually answer (should *this*
  diff fix it); the whole-file job asks about pre-existing content the PR is
  not responsible for.
- **A `lint-changed-files`-style workflow that calls `gh::gh()` (or any
  GitHub API) to list the PR's changed files can flake with `403 API rate
  limit exceeded for <IP>` when it runs *unauthenticated*.** The R `gh`
  package reads its token from `GITHUB_PAT` then `GITHUB_TOKEN`; if the
  workflow sets `env: GITHUB_PAT: ${{ secrets.GITHUB_PAT }}` and that custom
  secret isn't configured in the repo, the value is empty and the call runs
  anonymously (low shared-IP rate limit). Fix:
  `GITHUB_PAT: ${{ secrets.GITHUB_PAT || secrets.GITHUB_TOKEN }}` --- falls
  back to the always-present built-in token (`permissions: read-all` already
  covers the read). It's a flake (passes most runs), so a red
  `lint-changed-files` with no R lint output and a `gh_error`/`rate limit`
  traceback is this, not a code problem. ([UCD-SERG/serocalculator#503](https://github.com/UCD-SERG/serocalculator/pull/503), 2026-07.)
- **The same `lint-changed-files` shape has two silent blind spots that make a
  green run weaker evidence than it looks --- both absent from
  `lint-changed-lines`.** Neither produces an error; the check just passes
  without having looked.
  1. **Unpaginated `gh::gh()` reads only the first 30 changed files.** The
     `/pulls/{n}/files` endpoint defaults to 30 per page and `gh::gh()` doesn't
     follow `Link: rel="next"` unless asked, so on a larger PR every file past
     the 30th lands in the `setdiff(all_files, changed_files)` **exclusion**
     list.
     Fix: pass `.limit = Inf`.
  2. **`lintr::lint_package()` never scans repository-root scripts.** It covers
     `R/`, `tests/`, `inst/`, `vignettes/`, `data-raw/`, and `demo/` --- so a
     root-level `app.R` (a Shiny launcher, a deploy script) is unreachable no
     matter how the exclusion list comes out.
  `lint-changed-lines` computes its file set from the git diff, so it has
  neither cutoff --- an independent argument for the branch-protection switch
  beyond the incremental-adoption one. Don't treat a local
  `lint_package()` run as equivalent to CI in either direction.
  ([UCD-SERG/serocalculator#392](https://github.com/UCD-SERG/serocalculator/pull/392), 2026-07-25: a 38-file PR silently skipped 8
  files, missing two real `line_length_linter` hits in its own new test file;
  `lint-changed-lines` separately caught an `undesirable_function_linter` hit
  in root `app.R` that a local `lint_package()` had reported clean.
  Filed as [UCD-SERG/serocalculator#608](https://github.com/UCD-SERG/serocalculator/issues/608).)
- **`air format . --check` passing is NOT the claim "no line exceeds
  `air.toml`'s `line-width`" --- air does not reflow string literals.**
  A long `cli::cli_abort()` / `cli_alert_*()` message, a URL, or any other
  single string token stays exactly as written, so a 98-character line sails
  through a green `--check` in a repo configured at `line-width = 80`.
  The formatter's guarantee is "this file is already in the shape air would
  produce", which is weaker than the width setting suggests.
  Check the width separately, since one line decides it:
  ```bash
  awk 'length > 80 {print FILENAME":"FNR": "length" chars"}' $(git ls-files '*.R')
  ```
  Fix a flagged string by splitting it across implicit-concatenation
  arguments (`cli`'s `...` joins them) rather than widening `line-width`.
  This is another green-check-does-not-mean-clean-content case, alongside
  `check-new-line-breaks` in
  [`semantic-line-breaks`](../shared/writing/semantic-line-breaks.md) and the
  review-job cases in
  [`review-verdict-pitfalls`](../shared/workflow/review-verdict-pitfalls.md).
  Note that `lintr`'s `line_length_linter` DOES catch these, so a repo
  running air without lintr (d-morrison/altdoc) has no gate at all.
  ([d-morrison/altdoc#78](https://github.com/d-morrison/altdoc/pull/78), 2026-07-27: two `cli` strings in new code ran to 93
  and 98 characters with `air format . --check` clean throughout.)

## jarl (Just Another R Linter) — `jarl.toml` fields lag the published docs
- `jarl` (`etiennebacher/jarl`, installed via `etiennebacher/setup-jarl@vX` in
  CI) is a fast Rust-based R linter, a sibling to `{flir}` by the same author
  (both are `etiennebacher` projects; `{air}`, the R formatter jarl builds on,
  is a separate Posit project by Davis Vaughan and Lionel Henry, not the same
  author). Its `unused_function` rule flags any function jarl's static analysis
  can't find a call site for — including functions in **fixture/test-data R
  packages** (e.g. a `tests/testthat/examples/testpkg.*/R/*.R` tree copied and
  rendered as test input), which are genuine false positives: nothing in the
  outer package is ever meant to "call" fixture content.
- **The `jarl.toml` config schema in the repo's `CHANGELOG.md`/docs can
  describe a feature not yet in the released version CI actually installs.**
  `[lint.per-file-ignores]` (scope a rule to specific files/globs) appears in
  jarl's `CHANGELOG.md` on `main`, but `jarl check` itself is the source of
  truth for what the *installed* version accepts — it errors immediately with
  `Invalid configuration ... Unknown field 'per-file-ignores' in '[lint]'.
  Expected one of: select, extend-select, ignore, fixable, unfixable, exclude,
  default-exclude, include, check-roxygen, fix-roxygen` when the field isn't
  supported yet (hit against jarl 0.5.0 via `setup-jarl@v0.1.0`, no version
  pin -> latest). The error message's "Expected one of" list is authoritative;
  don't trust changelog/docs-site prose for what a *pinned or auto-latest* CI
  install actually accepts, since "on `main`" doc content can be ahead of the
  latest tagged release.
- **Fallback when the wanted field isn't supported: `[lint] exclude = ["<dir>/"]`**
  (full path/glob exclusion — coarser than `per-file-ignores`, silences ALL
  jarl rules for that directory, not just the one false-positive rule) rather
  than editing fixture file content to appease the linter (fixture bytes often
  feed snapshot/rendering tests, so editing them risks unrelated test
  breakage). File a follow-up issue to narrow `exclude` to `per-file-ignores`
  once the installed jarl version supports it. ([`d-morrison/altdoc#18`](https://github.com/d-morrison/altdoc/pull/18), [#19](https://github.com/d-morrison/altdoc/issues/19).)
- **There is no `.jarlignore` file — jarl has never supported one.** Don't
  assume jarl follows the `.gitignore`/`.eslintignore`-style convention of a
  dotfile-per-tool; its only exclusion mechanism is `jarl.toml`'s `[lint]`
  table (`exclude` / `per-file-ignores`, above). A `.jarlignore` file is
  silently inert — `jarl check` never reads it, so violations inside the
  "excluded" paths still fire, and no error or warning flags the unsupported
  config. This is easy to miss because CI can still look green: pairing the
  fake `.jarlignore` with `continue-on-error: true` on the lint step (to
  paper over the failures it doesn't actually suppress) hides the breakage
  entirely, and a bot review can approve the change on the false premise that
  `.jarlignore` works, since nothing about the diff itself is wrong-looking.
  Verify a suppression file is real by checking the tool's own config-file
  reference (or just removing `continue-on-error` and running the check) —
  not by pattern-matching on other tools' ignore-file conventions.
  ([`d-morrison/altdoc#7`](https://github.com/d-morrison/altdoc/pull/7): `continue-on-error: true` masked a `.jarlignore`
  that did nothing; removing the flag immediately reproduced the
  `unused_function` failure it was supposed to prevent.)
