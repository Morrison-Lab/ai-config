# R, Quarto & the R toolchain

## Conda activation before Quarto validation

- **Activate the conda environment before checking a project toolchain; `conda
  run` is not equivalent.** In this environment `conda run -n bcs quarto ...`
  found and started `quarto` --- the executable is on `PATH` under `conda run`
  --- but Quarto then failed to locate its own **bundled Deno helper**, dying
  with `bin/tools/x86_64/deno: No such file or directory`.
  The failure is in activation-dependent helper resolution, not in executable
  lookup, and the distinction matters because it points debugging somewhere
  different: `which quarto` succeeds and tells you nothing.
  Activate properly instead, deriving conda's own base rather than hard-coding
  one host's layout:
  ```bash
  source "$(conda info --base)/etc/profile.d/conda.sh" && conda activate bcs
  quarto --version
  ```
  `conda run` can still suit a self-contained R invocation, but it is not a
  substitute for full shell activation when the tool shells out to its own
  bundled helpers.

  An R package check that compiles native code is one such self-contained
  invocation: run it as
  `conda run -n bcs env R_PROFILE_USER=/dev/null Rscript -e '...'` rather than
  calling the environment's `Rscript` by absolute path.
  The latter loads R libraries but does not add the environment's compiler
  drivers to `PATH`, so `pkgbuild::check_build_tools(debug = TRUE)` reports a
  missing compiler even after the compiler package is installed.
  Install the toolchain with `conda install -n bcs -c conda-forge compilers
  --yes`, then repeat that diagnostic through `conda run` before rerunning
  `devtools::check()`.
  - **Do:** activate, then re-run the failing command, before reporting a
    toolchain broken.
  - **Do:** derive the conda base with `conda info --base`, since `conda` is
    already on `PATH` if you got as far as `conda run`.
  - **Don't:** describe the Quarto/Deno case as the executable being off
    `PATH` --- that
    records a failure model the observed error contradicts.
  - **Don't:** paste an absolute `/home/<user>/miniconda3/...` path into a
    recorded recovery command; it fails for every other user and install
    location.

  [`growth-mindset`](../shared/workflow/growth-mindset.md) owns the incident
  this comes from and the broader rule (do not accept a tool as broken on one
  invocation); this entry is the operational half.

## renv.lock — adding a package that's only referenced via another package's Suggests

Using a function that requires an **optional** dependency of an already-locked
package (e.g. `lintr::cyclocomp_linter()`, which needs the `cyclocomp` package —
listed only inside `lintr`'s own embedded `Suggests` metadata in `renv.lock`,
never as its own top-level `Packages` entry) breaks CI silently: `renv::status()`
looks clean beforehand, but `renv::restore()` never installs it, and the first
run that actually calls the function errors at runtime (for `cyclocomp_linter()`:
"disabled due to lack of the cyclocomp package"). Before relying on a new
function that pulls in an optional dep like this, check with
`jsonlite::fromJSON("renv.lock")$Packages` (or grep the lockfile) that the
package has its own top-level entry — its name appearing SOMEWHERE in the file
(inside another package's `Suggests` list) is not sufficient.

**Fixing it: do NOT run `renv::snapshot()` (even scoped via `packages = c(...)`)
in an environment that can't fully restore the lockfile's existing package set.**
`renv::snapshot(packages = "cyclocomp")` in a sandboxed/offline container pruned
~4000 unrelated lines from a real `renv.lock` (every package not physically
installed in the local renv library got dropped) and mangled Unicode author
names into octal-escaped bytes in surviving entries — collateral damage far
outside the intended one-package addition. `renv::install()` has the same
blast radius: it tries to resolve the WHOLE project's `Remotes:` field (e.g. a
GitHub pin like `rstudio/bookdown`), which fails outright if GitHub API access
is blocked, even though the failure has nothing to do with the CRAN package
being installed. **`install.packages()` hits the identical failure while renv
is active**, because renv's autoloader shims `install.packages()` to route
through `renv::install()` internally (confirmed by the traceback: a plain
`install.packages("cyclocomp")` call showed `renv::install("cyclocomp")` as
a parent frame) — so avoid both, not just the namespaced call.

**A second, more severe occurrence: a full, unscoped `renv::snapshot()` (no
`packages =` arg) in a Claude Code Bash sandbox that had NO project R packages
installed at all (only base R) truncated a real `renv.lock` from ~300 package
entries down to ~6 base-R packages** — not a partial prune, essentially the
whole lockfile. The mistake was made trying to "refresh" a lockfile that
looked stale (a pinned GitHub remote's commit SHA 404'd); running
`renv::snapshot()` felt like the obvious fix but, per the rule above, is
never safe unless the environment can actually restore the full existing
package set first. It went unnoticed at push time (the diff just looked like
"a smaller lockfile") and was only caught because a *downstream* CI job
(`lint-changed-files`) failed on a missing `gh` R package that the lockfile
no longer had — prompting a diff review that revealed the near-total
truncation. **Before trusting any regenerated lockfile, diff old-vs-new
package *counts*** (e.g. `jq -r '.Packages|keys[]' old.json | sort >
/tmp/old.txt`, same for `new.json`, then `comm -23 /tmp/old.txt
/tmp/new.txt` to list dropped packages) and treat a dramatic shrink as a red
flag requiring revert, not a "cleanup." (`d-morrison/rme#1017`: reverted via `git revert`, then fixed the
actual root cause — see the repo-move 404 entry above — with a minimal
hand-edit instead.)

The safe fix is a **surgical hand-edit of the lockfile JSON**: install the
missing package locally just to read its DESCRIPTION metadata (e.g.
`install.packages("cyclocomp", lib = <renv project lib>)`,
`packageDescription("cyclocomp")`), then copy the exact field style of a
neighboring `Packages` entry (`Package`, `Version`, `Source: "Repository"`,
`Title`, `Authors@R`, `Description`, `License`, `URL`, `BugReports`,
`Imports`/`Suggests` as arrays, `NeedsCompilation`, `Author`, `Maintainer`,
`Repository: "CRAN"`) and insert it alphabetically with the Edit tool. Verify
with `jsonlite::fromJSON("renv.lock")` that it still parses and
`git diff --stat renv.lock` shows only the intended additive lines — a diff in
the thousands means the wrong approach was used; `git checkout -- renv.lock`
and redo it by hand. (UCD-SERG/lab-manual#381: `lint-project` failed on
`cyclocomp_linter is disabled due to lack of the cyclocomp package`; the
snapshot approach was tried first and reverted before the hand-edit.)

## renv.lock --- repointing an existing GitHub package's org (relocation)

Distinct from the "adding a package" case above: here a package the lockfile
already pins is still installed, but its GitHub repo moved orgs (e.g.
`cards`/`cardx` from `insightsengineering` to `pharmaverse`), so the pinned
`RemoteSha` no longer resolves and CI's `renv::restore()` fails on the dead ref.
The instinct is a minimal hand-edit repointing `RemoteUsername` and
`RemoteSha` to the new org's repo, and it is not enough.

**Every DESCRIPTION-derived field in the record drifts when `RemoteSha`
changes, not just the two you meant to touch.**
A GitHub lockfile record is snapshotted from the DESCRIPTION at the pinned
commit, so `Version`, `Authors@R`, `Description`, `Imports`, `URL`,
`BugReports`, `Config/Needs/website`, and `Config/roxygen2/version` (upstream
had replaced `RoxygenNote` with the latter) can all differ at the new SHA ---
plus the derived `Author` field, which is expanded from `Authors@R`.
Repointing only `RemoteUsername`/`RemoteSha` leaves the record internally
inconsistent: it claims a commit whose real metadata it no longer matches.

The robust fix is `renv::restore()` then `renv::snapshot()`, which re-derives
every field from the actually-installed package --- **but only where the
environment can fully restore the lockfile's existing package set**, which is
exactly the precondition the "do NOT run snapshot in a sandboxed/offline
container" warning above protects.
So the two rules compose: restore-then-snapshot on a full dev machine, and the
surgical hand-edit as the sandbox fallback.
To verify a hand-edit is drift-free without a full restore, fetch
`https://raw.githubusercontent.com/<org>/<repo>/<sha>/DESCRIPTION` and diff each
field against the record, **excluding the install-time-only fields** `Author`,
`Maintainer`, and `Remote*` (absent from an upstream DESCRIPTION), then confirm
`renv::lockfile_read()` still parses the result.

- **Do:** prefer `renv::restore()` + `renv::snapshot()` on any machine that can
  restore the full package set, and fall back to a hand-edit only where it
  cannot.
- **Do:** sync every DESCRIPTION-derived field against the raw DESCRIPTION at
  the new pinned SHA, then confirm `renv::lockfile_read()` parses.
- **Don't:** repoint only `RemoteUsername`/`RemoteSha` and treat the record as
  fixed --- the SHA change silently invalidates every field the DESCRIPTION
  owns.
- **Don't:** diff `Author`/`Maintainer`/`Remote*` against the upstream
  DESCRIPTION; those are install-time-only and absent there.

**A lockfile record's `Remotes` field is INERT during `renv::restore()`, so do
not hand-repoint the `Remotes` strings of OTHER packages that reference the
relocated one.**
Verified against renv 1.2.4 source (`renv_retrieve_successful`): restore reads
a downloaded package's remotes from the tarball's own DESCRIPTION
(`desc <- renv_description_read(path); remotes <- desc$Remotes`), never from the
lockfile record.
Resolution is wrapped in `catch()` (`renv_retrieve_remotes_impl_one` warns
`failed to resolve remote '%s'; skipping` and returns, never errors), and a
package that already has a non-plain lockfile record ---
`!identical(record, list(Package = package, Source = "Repository"))` --- is
skipped outright.
So a sibling package like `gtsummary` or `rme` whose `Remotes` string names the
relocated package should keep the value matching its OWN unchanged pinned
`RemoteSha` (what a genuine `renv::snapshot()` records), not be edited to point
at the new org.
This is distinct from the sandbox install-time failure in
[`r-cloud-sessions.md`](r-cloud-sessions.md), which is about a GitHub
dependency's own install channels --- tarball/clone via `github.com` or
`codeload`, plus `api.github.com` for renv/pak --- being proxy-blocked when the
repo isn't in the session's scope, rather than the per-package `Remotes` field
in a lockfile record.

- **Do:** leave other packages' `Remotes` strings at whatever a real snapshot
  recorded; only the top-level relocated package's `Remote*`/DESCRIPTION fields
  change.
- **Don't:** cascade the org rename into every `Remotes` string that mentions
  the package --- those are inert on restore, and a hand-repoint just
  introduces a claim no real snapshot would make.

**Regenerate the derived `Author` field from `Authors@R` in R with
`tools:::.expand_package_description_db_R_fields()`, and `unname()` the input
first.**
`read.dcf(...)[i, "Authors@R"]` returns a NAMED character value (name
`"Authors@R"`); passing it named mangles the expander's input key so it returns
an output with NO `Author` field at all --- verified on this runtime: the named
form's output has zero named fields, so indexing `[["Author"]]` throws
subscript-out-of-bounds, while `unname()` yields `Jane Doe [aut, cre]` for a
known input.

```r
x <- read.dcf("DESCRIPTION")[1, "Authors@R"]
tools:::.expand_package_description_db_R_fields(c("Authors@R" = unname(x)))[["Author"]]
# -> the expanded Author string
```

Validate the function byte-reproduces a known `(Authors@R -> Author)` pair from
an existing record before trusting it on new input.

- **Do:** `unname()` the `Authors@R` value before handing it to
  `.expand_package_description_db_R_fields()`.
- **Don't:** pass the raw `read.dcf()` result named --- the named key silently
  suppresses the `Author` field rather than erroring where you would notice.

(`ucdavis/epi204#375`, 2026-08-16: fixed CI broken by `cards`/`cardx`
relocating from `insightsengineering` to `pharmaverse`.
Two `@claude` review rounds flagged that the initial hand-edit repointed only
`RemoteUsername`/`RemoteSha`, leaving every DESCRIPTION-derived field stale
against the new commit.
The renv-source and `unname()` mechanisms were re-verified here against renv
1.2.4 --- newer than the 1.2.0 the PR author checked --- and base R `tools:::`
on this runtime.)

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
`lms::function_length_linter()` in UCD-SERG/lab-manual#381.)

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

(`UCD-SERG/serocalculator#668`, 2026-09-01.)

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
  the next run.) (UCD-SERG/serocalculator#503, 2026-07.)
- **Recurred on UCD-SERG/serocalculator#672, 2026-09-01, from the lab's own
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
  traceback is this, not a code problem. (UCD-SERG/serocalculator#503, 2026-07.)
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
  (UCD-SERG/serocalculator#392, 2026-07-25: a 38-file PR silently skipped 8
  files, missing two real `line_length_linter` hits in its own new test file;
  `lint-changed-lines` separately caught an `undesirable_function_linter` hit
  in root `app.R` that a local `lint_package()` had reported clean.
  Filed as UCD-SERG/serocalculator#608.)
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
  (d-morrison/altdoc#78, 2026-07-27: two `cli` strings in new code ran to 93
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
  once the installed jarl version supports it. (`d-morrison/altdoc#18`, #19.)
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
  (`d-morrison/altdoc#7`: `continue-on-error: true` masked a `.jarlignore`
  that did nothing; removing the flag immediately reproduced the
  `unused_function` failure it was supposed to prevent.)

## R-package PR CI gates (the repository owner / UCD-SERG R packages, e.g. `bcs`)
- These repos gate PRs on a **changelog check** (`news.yaml` / "Check Changelog
  Action") and a **version-check**. Historically a user-visible PR needed
  **both** a `NEWS.md` entry under `# <pkg> (development version)` **and** a
  `DESCRIPTION` `Version:` dev-bump (e.g. `0.0.0.9053` → `.9054`), or CI
  failed. Add them up front rather than waiting for the red check. (Observed
  on ucdavis/bcs#223.) For a **non-user-visible** PR (CI/workflow-only), the
  `no changelog` + `no version increment` labels may skip both, but that
  bypass is per-repo and serodynamics has none: see the label-bypass note in
  `memories/github-actions.md`.
  **This per-PR dev-bump convention is what `Morrison-Lab/gha`'s new
  `bump-dev-version`/`version-check` capabilities (gha#390, tracking gha#388)
  exist to retire** --- both were engineered as a direct fix for the
  merge-conflict-on-`DESCRIPTION` problem this convention structurally
  guarantees (every PR bumping the same `Version:` line collides with every
  other open PR doing the same). Once a repo migrates: `DESCRIPTION`'s
  `Version:` is bumped automatically by a bot PR after every merge to `main`,
  never by hand in a feature PR; `version-check` inverts to fail a PR if its
  `DESCRIPTION` differs from `main`'s **at all** (rather than requiring it to
  exceed `main`'s), with the same `no version increment` label as an escape
  hatch for a genuine manual release-version bump
  (`usethis::use_version()`, which still exists outside this automation);
  and the whole "bump above main, re-bump after every merge" chore described
  above and in `memories/github-actions.md`/`memories/claude-bot-workflows.md`
  no longer applies. As of this writing (2026-07-31) no lab repo has migrated
  yet --- check a given repo's own `.github/workflows/version-check.yml` /
  `version-check.yaml` before assuming which regime it's under. The
  `news.yaml`/changelog-entry half above is unaffected until a separate
  `news.d`-fragment capability ships (deferred; see gha#388).
- **`read.dcf()` does not error on a DCF file with a duplicate top-level
  field; it silently keeps whichever occurrence comes LAST.** Confirmed with
  a live call, not assumed: a two-line `Version: 1.2.3` / `Version: 1.2.4`
  stanza parses cleanly and returns `1.2.4`.
  This is the general fact behind `configure-gitattributes`'s
  never-`merge=union`-on-`DESCRIPTION` row
  (`skills/configure-gitattributes/SKILL.md`) --- a union-merged
  `DESCRIPTION` with two `Version:` lines is not a loud parse failure, it's
  a silent pick of one side, which is worse.
  Watch for the same trap anywhere else a merged or hand-edited DCF file
  (`DESCRIPTION`, a `Packages` index) gets read back: a check that assumes
  malformed DCF would be caught by the parser is assuming the wrong
  failure mode.
  (ai-config#979, 2026-07-31: an earlier draft of that SKILL.md row claimed
  a duplicate `Version:` field "breaks every DCF parser (`read.dcf()`,
  ...)", which a live `Rscript` call showed to be backwards.)
- The **Spellcheck** job (`spelling::spell_check_package()`) fails on any word
  not in `inst/WORDLIST`. For one-off non-dictionary words in NEWS/prose, prefer
  rewording (e.g. "uncaptioned" → "without captions") over polluting WORDLIST;
  add to WORDLIST only for real domain terms you'll reuse.
  - **When the offending token is a code identifier or a literal log/warning
    message** (e.g. quoting `non-integer #successes in a binomial glm!` in a
    NEWS entry, which tripped on `glm`), wrap it in backticks as inline code
    instead — the spellcheck parses markdown and skips code spans, and
    backticking a `pkg::fn()`/identifier/message is the correct markdown style
    anyway. Cleaner than both rewording and a WORDLIST add. (ucdavis/ettbc#30.)
  - **Cross-repo issue refs and bare domain names are spellable-token sources
    too, not just code identifiers.** The checker splits on punctuation, so an
    unbackticked `d-morrison/altdoc#26` flags `morrison`, and `rdrr.io` flags
    both `rdrr` and `io`. Backtick them (existing NEWS entries already backtick
    cross-repo refs, so this matches convention), and reword genuinely-prose
    words instead of listing them (`undiscoverable` → "cannot discover").
    (ucdavis/bcs#375: four tokens flagged from one NEWS entry, fixed with zero
    WORDLIST additions.)
  - **A Quarto `{{< include >}}` path is a spellable-token source too, and the
    backtick remedy above cannot be applied to it.**
    The two bullets above are both tokens someone typed as prose;
    an include path is machinery,
    so the natural assumption is that the checker skips it.
    It does not.
    Hunspell splits on hyphens,
    so every dash-separated segment of a kebab-case filename becomes a word:
    `{{< include methodology/_checking-nlm-convergence.qmd >}}` flags `nlm`.
    Backticking the shortcode would disable the transclusion,
    so where a repo's convention is underscore-prefixed kebab-case subfiles
    (as in UCD-SERG repos and the lab manual's
    "Using Includes for Modular Content"),
    the **filename itself** has to be composed of dictionary words.
    Prefer renaming the subfile over adding the token to `inst/WORDLIST`,
    which puts a path artifact into a word list
    and then silently permits that bare token everywhere else in the prose.
    (UCD-SERG/serocalculator#635, 2026-08-07:
    `nlm` failed Spellcheck at `methodology.qmd:1014`.
    Every other `nlm` in that article sat inside backticks or a code chunk,
    so the only bare occurrence came from a filename
    rather than from anything the prose said.
    Renamed to `_checking-convergence-codes.qmd`, with no WORDLIST addition.)
  - **When a whole page is a stack of includes, strip the shortcode lines
    before checking instead of renaming.**
    `spelling::spell_check_files()` (2.3.x) parses `.qmd` as Markdown and
    skips code spans, so a sweep over `chapters/**/*.qmd` works --- but a
    chapter file that is forty `{{< include ai-tools/<slug>.qmd >}}` lines
    reports `ai`, `qmd`, `claude`, and every other path segment dozens of
    times, and there is nothing to rename.
    Copy the files to a temp dir, drop lines matching
    `^\s*\{\{<.*>\}\}\s*$`, and check the copies.
    (Morrison-Lab/wai#177, 2026-09-01: 191 raw hits on the chapters, of which
    the include paths were the bulk; `spell_check_package()` had never scanned
    them because they are not vignettes.)
- **Regenerating `man/*.Rd`: run `devtools::document()` (or
  `roxygen2::roxygenise()`) --- never hand-edit the `.Rd`.** A `docs-check` /
  `R-check-docs` job runs `roxygenize()` then `git diff --exit-code man/`, so a
  roxygen edit with a stale `man/*.Rd` fails; the fix is to regenerate, not to
  hand-write the `.Rd`. **If the toolchain looks missing** (a bare-R cloud/web
  sandbox with no `devtools`/`roxygen2`), install it ---
  `install.packages("roxygen2")` plus the package's own `Imports` so
  `pkgload::load_all()` can load it --- and run `roxygen2::roxygenise()`
  (`devtools::document()` if `devtools` is also installed). Treat "no R
  toolchain" as a resource to obtain (growth-mindset), not a reason to edit
  `.Rd` by hand. (Corrected 2026-07-20: on serocalculator#562 I hand-edited two
  `.Rd` files instead of installing roxygen2 and running `document()`; the
  user's rule is to run the generator.)
  - **An UNTRACKED file in `R/` silently poisons the generated `NAMESPACE`,
    and the damage lands in a tracked file.**
    `document()` reads the working tree, not the index,
    so a `.R` file that git does not track still gets roxygenized:
    its `@export` becomes an `export()` line in `NAMESPACE`,
    and its `.Rd` appears in `man/`.
    Only the `NAMESPACE` edit is to a tracked file,
    so `git status` shows one innocuous-looking modification
    while the source backing it is invisible to every other checkout.
    Local `R CMD check` passes, since the file is on disk.
    CI fails instead, or --- worse --- the export merges
    and `main` names a function nobody else has.
    The tell is an `export()` line in a `document()` diff
    for a function this change never touched.
    Before committing a regenerated `NAMESPACE`,
    run `git status --short R/` and account for every `??`.
    This is the R case of the general hazard
    that a generator's input set is the working tree rather than the commit.
    (`ucdavis/bcs`, 2026-08-02: an untracked `R/prep_adherence_by_month.R`,
    sitting in the tree since Jul 21,
    put `export(prep_adherence_by_month)` into a `document()` commit
    on a PR branch.
    It never reached `main` only because that commit was never pushed.)
  - **Match the package's pinned roxygen2 version before trusting generated output.**
    Different roxygen2 versions can rewrite the same `.Rd` differently,
    so a local version that differs from the one CI uses can produce a misleading diff.
    Install and verify the version recorded by the project's lockfile (or otherwise used by CI),
    regenerate, and inspect the resulting diff before pushing. (ucdavis/bcs#448, 2026-07-28.)
  - **Avoid `@inheritParams` or `@inheritDotParams` from packages with dynamic/transitive documentation.**
    Inheriting documentation from wrappers like `gtsummary::tbl_summary` pulls in transitive `cards::ard_tabulate` parameter descriptions whose text varies between upstream package versions.
    When local and CI package versions differ, `roxygen2::roxygenise()` generates unexpected diffs that fail CI `docs_check`.
    Write explicit `@param` tags (and document `#' @param ... Additional arguments passed to [pkg::fn]`) for wrapper functions instead of inheriting dynamic dot-params.
- **Hand-editing `.Rd` is a genuine last resort, only when installing the
  toolchain truly fails** (offline / locked-down sandbox). If forced to it, keep
  the edit safe: roxygen copies `@format`/`@param`/`@return` prose verbatim into
  the `.Rd` and `roxygenize()` is deterministic, so a **same-length word swap**
  (e.g. `biannual`->`biennial`) reproduces exactly what `document()` would
  generate. For a larger edit, first verify the transform empirically --- diff an
  existing `\item{}` block's roxygen source (stripped of its `#'` prefix) against
  its rendered `.Rd` lines; roxygen with `markdown = TRUE` preserves line breaks
  and converts `` `x` `` to `\code{x}` (and `**bold**` to `\strong{}`, `[text](url)`
  to `\href{}{}`) --- then validate your hand-edit with a scripted
  transform-and-diff (`` perl -pe 's/`([^`]+)`/\\code{$1}/g' `` piped to `diff`
  against the `.Rd`). Watch `@inheritParams`/`@inherit`: editing one function's
  roxygen also changes every inheriting function's `.Rd`, so grep `man/` for the
  changed sentence. (bcs#225; serocalculator#562 --- but prefer installing the
  toolchain over all of this.)
- **Codoc mismatch with escaped-dot defaults: limit the lesson to the observed case.**
  In d-morrison/altdoc#30, changing the default regex from an escaped dot (`\\.`) to
  a bracket expression (`[.]`) resolved an `R CMD check` codoc mismatch for
  `setup_github_actions()`. Keep this note scoped to that concrete escaped-dot case;
  avoid generalizing to other escape sequences without direct evidence.
  (d-morrison/altdoc#30, 2026-07-22.)
- **Internal helper functions as default argument values appear literally in `.Rd` usage
  blocks.** If you write `foo = .helper_default()` as a parameter default, the roxygen
  `\usage{}` section shows `.helper_default()` verbatim — which is confusing to users
  copy-pasting the signature. Inline the literal value directly in the function
  signature instead. (d-morrison/altdoc#30.)

## R test/lint gotchas that only surface in CI
Also from ettbc#13/#14:
- **`lintr::object_usage_linter` flags package datasets used inside a *named*
  helper function in a test file** (`no visible binding for global variable
  'cohort'`). The same dataset used directly inside a `test_that()` block is
  fine. So reference lazy-loaded data at file scope or inside the test blocks,
  not inside a top-level helper. The repo's `lint-changed-files` job runs
  `R CMD INSTALL .` before `lint_package`, so cross-file *internal* functions
  (e.g. a helper defined in another `R/` file) resolve — a single-file
  `lintr::lint()` can't see them and will false-flag them.
- **`lintr::object_usage_linter` can't see a variable used only inside a
  formula** — including every `~` in `dplyr::case_when()` / `case_match()`.
  `codetools` doesn't walk formula bodies, so
  `x <- f(y); dplyr::case_when(x %in% c(...) ~ "1", ...)` reports
  `local variable 'x' assigned but may not be used` even though `x` is plainly
  used. Don't suppress it: rewrite so the variable is referenced outside a
  formula — a named lookup vector indexed by the variable (`bins[x]`) replaces
  a `case_when` chain cleanly, and usually reads better anyway.
  This is **not** a CI-only lint (verified: a plain single-file
  `lintr::lint(f, linters = lintr::object_usage_linter())` reproduces it) — but
  it is easy to *believe* it is, because an intervening local run can come back
  clean off a stale loaded namespace and then CI flags it again. If a lint
  disappears without you changing the thing it flagged, distrust the clean run.
  (ucdavis/bcs#351.)
- **`spelling::spell_check_package()` locally over-reports vs CI** on accented
  hyphenated names: line-wrapped `García-Albéniz`/`Hernán` in `.Rd` files
  tokenize as `Garc`/`niz`/`Hern`, which the CI spellcheck action does not flag
  (main passes with them). Trust CI's misspelled count; add only the genuinely
  new words to `inst/WORDLIST`.
- **The ettbc `review / claude-review` check fails/skips org-wide when the
  Anthropic org spend limit is hit** (`github-actions[bot]` posts "monthly spend
  limit"). It's environmental, non-blocking, and unfixable from a content PR
  (the bot can't edit `.github/workflows`). Stand in with a manual self-review
  rather than chasing it.
- **Adding a new hidden top-level dotfile/dir to an R package (a `.claude`
  config dir, a `.ai-config` git submodule, any new `.<name>`) fails
  `R CMD check` with `checking for hidden files and directories ... NOTE`
  unless it's listed in `.Rbuildignore`.** A repo whose `R-CMD-check` job sets
  `error_on = "note"` (common per this corpus's own review-guideline citations)
  turns that NOTE into a hard CI failure on every platform the check runs —
  it isn't Linux/macOS/Windows-specific, since the check runs identically on
  all of them. Add an anchored entry (`^\.claude$`) matching the existing
  `.Rbuildignore` style (e.g. the `^\.github$` line most repos already have)
  proactively, in the same commit that adds the new dotfile/dir, rather than
  waiting for CI to name it. A submodule whose content isn't checked out in CI
  (the common case — `actions/checkout` doesn't init submodules by default)
  can dodge the NOTE by luck — the CI build log's own `R CMD build` step
  ("checking for empty or unneeded directories") reported
  `Removed empty directory '<pkg>/.ai-config'`, so the uninitialized submodule
  never reached `R CMD check` at all — but exclude it in `.Rbuildignore`
  anyway rather than relying on that accident of checkout config.
  (`UCD-SERG/serodynamics#265`: adding `.claude/settings.json` failed
  `ubuntu-latest`/`macos-latest`/`windows-latest` (all `release`) plus
  `ubuntu-latest (oldrel-1)` R-CMD-check
  simultaneously with this exact NOTE; the sibling `.ai-config` submodule
  added in the same PR happened not to trigger it, for the empty-dir reason
  above.)
- **A VISIBLE new top-level file needs the same treatment, and trips a
  different NOTE that the entry above will not match on.** That one is scoped
  to hidden dotfiles and to `checking for hidden files and directories`, so a
  reader adding `CLAUDE.md`, `AGENTS.md`, `TODO.md`, or a stray `notes.qmd`
  greps for "hidden", finds nothing that applies, and ships it. The check they
  actually hit is `checking top-level files ... NOTE: Non-standard file/directory
  found at top level`, which under `error_on = "note"` fails CI exactly as the
  hidden-file NOTE does. `R CMD check` allows only a fixed set of top-level
  names, so anything outside it needs an anchored `.Rbuildignore` entry
  (`^CLAUDE\.md$`) in the same commit that adds the file. This is worth knowing
  specifically because `/init` writes `CLAUDE.md` to the repo root and does not
  touch `.Rbuildignore`, so running it in any R package leaves a build that
  will fail on the next push unless you add the line yourself.
  (`ucdavis/mic.sim#49`, 2026-08-06: added `^CLAUDE\.md$` alongside the
  `^\.claude$` line the entry above calls for, and all five R-CMD-check
  platforms passed.)


## altdoc keeps its reference topics in two independent hand-maintained lists

An altdoc site lists each reference topic in two independent places, neither
generated from the other:

1. `altdoc/reference.qmd` --- the "Package index" page body.
2. the `Reference` section of `altdoc/quarto_website.yml` --- the sidebar nav.

Adding a function to one and not the other renders perfectly cleanly: the
topic shows on the index page but is unreachable from navigation (or the
reverse). No check catches it --- not `docs-check`, not the docs build, not
lint. The pkgdown -> altdoc migration makes this especially easy to hit,
since the old `pkgdown/_pkgdown.yml` held a *single* reference list, so
porting entries off it naturally updates only one of the two successors.

Cross-check mechanically rather than by eye
(the [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
rule): extract `](man/<topic>.qmd)` from `reference.qmd` and `- man/<topic>.qmd`
from `quarto_website.yml`, assert an empty symmetric difference, and assert a
backing `man/<topic>.Rd` exists for every entry. A stricter version flags
exported functions in `NAMESPACE` that appear in neither list.

To verify against the *rendered* output, count occurrences of a topic name in
the built `reference.html`: an established topic appears **3** times (sidebar
entry + index link + index text), a sidebar-missing one only **2**.

(`UCD-SERG/serocalculator#392`, 2026-07-25: six new decay-curve topics were
ported into `reference.qmd` only; caught before merge, fixed, and confirmed
2 -> 3 occurrences each in the deployed preview.
`UCD-SERG/serocalculator#610` proposes the cross-check as CI, possibly
belonging in `Morrison-Lab/gha` since every altdoc repo shares the structure.)

## renv — each git worktree gets its own (empty) project library

renv keys the project library path on the project directory name, so a
fresh `git worktree` of an renv project starts with an EMPTY library even
though the main checkout's is fully restored — the first render fails with
"package not available" (rmarkdown, etc.). In the Claude Code cloud
containers this lands at `~/.cache/R/renv/library/<dirname>-<hash>/…`
(renv 1.2.2, with NO `RENV_PATHS_*` env vars set — verified); the exact
root is version/config-dependent, so locate it portably with
`Rscript -e 'renv::paths$library()'` from each checkout rather than
assuming the pattern. Fastest fix when the worktree is same-machine and
same-lockfile: symlink the worktree's hashed library dir to the main
checkout's (`ln -s <main-lib-parent> <wt-lib-parent>` after removing the
empty one) instead of re-running `renv::restore()`. Note `RENV_PATHS_LIBRARY`
did NOT take effect for this (renv still bootstrapped its own path); the
symlink did. Also: renv intercepts `install.packages` and resolves ALL of
`DESCRIPTION`'s GitHub remotes first — in a proxy-restricted session that
403s on out-of-scope `api.github.com` calls, even a plain CRAN install
fails; bypass with `R_PROFILE_USER=/dev/null Rscript -e
'.libPaths("<lib>"); install.packages(...)'`. That bypass works even from
inside the project directory — R's user-profile search checks the CURRENT
directory for `.Rprofile` before the home directory (see `?Startup`), so
the project `.Rprofile` occupies the user-profile slot and
`R_PROFILE_USER` overrides it (verified empirically: renv unloaded with
the override, loaded without). `Rscript --no-init-file` is an equivalent
alternative. (rme OOM investigation, 2026-07-17.)

## WORDLIST alphabetization — Copilot vs claude reviewer collation conflict

`spelling`-package WORDLISTs sort in **two case-grouped blocks**
(uppercase-leading then lowercase-leading), each **case-insensitively** sorted
within the block — the order `spelling::update_wordlist()` emits under a UTF-8
locale. The claude reviewer enforces that order; Copilot sometimes flags the
same lines wanting ASCII/byte order (e.g. claiming `PP` must precede
`Positivity`). Don't flip-flop between the two: keep the case-insensitive
convention, verify each block **separately** with `sort -f -c`
(e.g. `grep '^[A-Z]' inst/WORDLIST | sort -f -c` for the uppercase block —
a whole-file `sort -f -c` false-fails at the block boundary even when the
file is correctly formatted), and rebut Copilot citing the
tool's own emitted order — the rebuttal stuck (Copilot dropped it on
subsequent rounds; ucdavis/win#69, 2026-07-16).

## CI failure on untouched files: diff the installed-package line between last-green and first-red logs

When a CI job fails on files the PR never touched, suspect toolchain drift
and make the version comparison the FIRST diagnostic: fetch the last
passing run's job log and the failing run's, and grep each for the suspect
package's sessioninfo line. A dev-tracking install (`extra-packages:
r-lib/lintr` in r-lib/actions) makes this a recurring class, and the log
line pins it exactly. Two 2026-07 instances in ucdavis/rampp: (1) `lint`
red on 31 untouched files — `lintr 3.3.0.9000 Github(@4579471)` green on
07-13 vs `3.4.0.9000 Github(@178882f)` red on 07-16 (lintr 3.4.0 dropped
double-indent formals, r-lib/lintr#2830); fixed by restyling, since the new
style is valid under both versions. (2) `macos-latest` R CMD check red
repo-wide — flextable 0.10.0 hit CRAN with no macOS binary yet, forcing a
source build that needs XQuartz libs the runner lacks; self-healed when the
binary appeared ~7h later, so the right move was retry-later
(`rerun_failed_jobs`), not a code change.

**The decisive test is re-running the operation at unmodified base, not
diffing logs.**
Log-diffing localizes the drift; a clean worktree checked out at `origin/main`
with the operation re-run there *settles attribution* --- if
`roxygen2::roxygenise()` rewrites the same two files on untouched `main`, the
red check is not a regression from the diff, and no amount of reading that
diff can establish it.
This is the R-toolchain instance of the negative-control rule in
`shared/principles/fail-fast.md`: the control has to enter at the real input,
which here means a separate checkout rather than a `git stash`, since stashing
leaves you in the very tree whose contribution you are trying to rule out.

**When someone cites "the last N runs on `main` are green" as proof your diff
caused it, check those runs' DATES against the suspected cause's release
date.**
A wall of green is evidence only about the interval it covers.
Ten green runs that all predate a dependency's release say nothing about a
failure that release caused --- and the claim is persuasive precisely because
the count is large and independently checkable, so the field that makes it
worthless is the one nobody reads.
`gh run list --workflow <name> --branch main --json createdAt,conclusion` puts
the dates beside the conclusions.

- **Do:** compare the green runs' timestamps against the release date of
  whatever you suspect, before making or accepting a regression attribution.
- **Do:** re-run the operation in a clean worktree at `origin/main` when
  attribution is disputed --- one command outranks any amount of log reading.
- **Don't:** treat a run count as evidence without its date range; "10/10
  green" and "10/10 green, all before the release" are different claims.

(`UCD-SERG/serocalculator` #635, 2026-08: a red `docs-check` was asserted to be
"a regression introduced by this PR's diff" on the strength of 10/10 green
`main` runs, every one of which predated the roxygen2 8.1.0 release;
`roxygenise()` in a clean `origin/main` worktree changed the same two files.)

## Editing a generated `README.md` when the R toolchain is unavailable

`README.md` is generated from `README.Rmd`, and the standing rule is not to
hand-edit it. But a remote/web session often has neither `rmarkdown` nor
`knitr` installed, so `rmarkdown::render()` isn't an option -- while `pandoc`
usually *is* on `PATH`. For a prose-only edit (no R code in the changed
chunk), the rendered form can be reproduced directly. Copy the affected
paragraph out of `README.Rmd` into a scratch file -- `para.md` below -- keeping
its source line breaks exactly, then run:

```bash
pandoc para.md -f markdown -t gfm --wrap=auto --columns=72
```

**Validate the invocation before trusting it: run it against the UNMODIFIED
paragraph first and confirm it reproduces the currently-committed `README.md`
text byte-for-byte.** That check is what turns a guess about wrap width into
evidence -- if the flags are wrong, the unmodified text won't round-trip, and
you find out before writing anything. Only then apply the same command to the
corrected source and commit its output.

Two scope limits. This works only where the edit touches no evaluated R code
(otherwise the chunk output matters and pandoc alone can't produce it), and
the repo's own `check-readme` job is still the real verification -- say so in
the PR rather than claiming the render was run. Note that `check-readme` (as
configured in `UCD-SERG/serocalculator`) only asserts that
`rmarkdown::render("README.Rmd")` *succeeds*; it does not diff the result
against the committed `README.md`, so a stale README is not hard-gated and
staying in sync is on the author.

(`UCD-SERG/serocalculator#605`, 2026-07-25: a one-sentence README link fix,
verified this way and merged; the reviewer independently confirmed the two
files stayed consistent.)

## Rex + base regex engines in R

- `rex::rex()` patterns often emit PCRE constructs; do not pass those directly to APIs that use POSIX regex defaults (for example `list.files(pattern = ...)`). List/filter in two steps and match with `grepl(..., perl = TRUE)` (and similarly `gregexpr`/`gsub` with `perl = TRUE`) when using rex-built patterns.
- `rex` shortcut symbols (`any_spaces`, `spaces`, `capture`, etc.) are not exported as `rex::name`; either keep them unqualified within `rex::rex(...)` and register shortcuts for R CMD check, or build explicit fragments with exported APIs (`rex::regex`, `rex::escape`) so static analysis does not depend on shortcut registration side effects.

## R does not fall back to a callee's default for a forwarded missing argument

When a function forwards an argument it never received, R propagates the
missingness into the callee and errors when the value is forced, so the
callee's own default does **not** apply:

```r
g <- function(path = ".") paste("saw:", path)
f <- function(source_file, target_dir, path) g(path)
f("a", "b")
#> Error: argument "path" is missing, with no default
```

This matters when writing or reviewing argument guards.
Seeing `path = "."` on the callee makes an unguarded forward look safe, so a
missing guard reads as deliberate rather than as an oversight.

The invalid-value case is worse than the missing one, and easier to miss,
because it produces no raw R error at all.
In altdoc, `.rd2qmd(rd, dir, path = "foo")` reached `.doc_type("foo")`, found
no settings file under a directory that does not exist, and aborted with
`No documentation tool detected. Please run the setup_docs() function.`
That message is confident, actionable, and pointing at the wrong problem.
Check both the missing and the invalid case when guarding a forwarded
argument, not only the one the issue reports.
(d-morrison/altdoc#64.)

## A container with no R at all is not a blocker: apt for R, P3M for the packages, a tarball for Quarto

The bullets above assume R already exists and only its *packages* are
missing --- the renv-session case.
A remote/web container can have no R, no Quarto, and no `gh`, which reads as
"tests cannot run here, push and let CI check it."
It is worth about ten minutes to disprove instead, and the difference is
large: pushing test assertions you have never executed versus deriving them
from a real run.

The recipe that worked end to end (Ubuntu 24.04 noble container, root):

```bash
# The version apt gives you depends on a precondition worth checking first:
#   grep -r cran /etc/apt/sources.list.d/
# This container already had CRAN's own repo wired up
# (/etc/apt/sources.list.d/cran-r.list -> cloud.r-project.org, noble-cran40),
# which is where the R 4.6.1 below came from. Ubuntu's own noble repo carries
# a much older R, so on an image without that file, add the CRAN repo rather
# than assuming a version.
apt-get install -y --no-install-recommends r-base-core   # R 4.6.1, here

# P3M rather than the default mirror, per the rest of this file --- the very
# next paragraph is what happens when something in the list needs compiling.
Rscript -e 'options(repos = c(P3M = "https://packagemanager.posit.co/cran/__linux__/noble/latest")); install.packages(c("cli", "desc", "fs", "testthat", "pkgload"))'

curl -sSLo q.tar.gz https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.27/quarto-1.8.27-linux-amd64.tar.gz
tar xzf q.tar.gz && ln -sf "$PWD"/quarto-*/bin/quarto /usr/local/bin/quarto
```

**The P3M-vs-CRAN-direct choice runs in both directions.**
The "before accepting uninstallable, try CRAN-direct" bullet above records
source-CRAN succeeding where P3M's fallback did not.
The same session hit the mirror image: a plain CRAN source install of
`quarto` and `rmarkdown` failed building their `sass` dependency
(`make: *** [Makefile:4: sass.ts] Error 3`), while P3M's noble binaries
installed all four packages in one call with no compilation.
So neither repo is the reliable one --- when the first fails on a build
step, switch and retry before concluding a package is unavailable.
(`d-morrison/altdoc` #82/#83/#84, 2026-07-28: this turned "assert the output
tree and hope" into rendering each generator, listing its published `docs/`
tree, and deriving the assertions from what was actually there.)

## testthat run by hand: two defaults that make a broken run look like a clean one

Both bite a **bare `Rscript` call** --- which is what a sandbox run is --- and
each fails in the direction that reads as success.

`devtools::test()` sets `NOT_CRAN = "true"`, and so does a
`rcmdcheck`-driven CI run: `d-morrison/altdoc`'s `R-CMD-check` reports
`FAIL 0 | WARN 1 | SKIP 6 | PASS 406`, and none of those six skips is
`On CRAN`, so its `skip_on_cran()`-guarded render tests genuinely run there.
But do not read that as "`R CMD check` protects you": CRAN's own runs leave
`NOT_CRAN` unset, which is the entire point of the function.
What sets it is the harness around the check, not the check.

**`skip_on_cran()` skips unless `NOT_CRAN` is set.**
A file whose every test opens with it reports `failed: 0  error: 0` and exits
`0` --- green by every signal except the one that matters.
The tell is the skip count: `skipped: 20  passed: 0` is not a pass, it is a
file that never ran.
Set `NOT_CRAN=true` on the command, and read `passed` rather than `failed`
before believing a run.

It is not a plain env-var test, and the difference explains why the trap is
specific to scripted runs.
`testthat:::on_cran()` is:

```r
env <- Sys.getenv("NOT_CRAN")
if (identical(env, "")) !interactive() else !isTRUE(as.logical(env))
```

So with the variable unset, an interactive console *runs* the tests while a
non-interactive `Rscript` skips them --- reproducing it by hand in a REPL
will therefore not show you the bug.

**`test_file()` / `test_local()` abort on the first failure --- but
`formals()` will not tell you so.**
Neither signature carries a literal default: in testthat 3.3.2 both
`formals(testthat::test_file)$stop_on_failure` and the `test_local()`
equivalent are `NULL`, and the aborting behavior comes from `test_dir()`,
whose own default is `TRUE`.
So inspecting the signature and concluding the argument is unset, or that the
two functions differ, is the wrong reading ---
a review of this entry made exactly that inference from the documentation,
and `formals()` is what settles it.
What the behavior actually is: one failing expectation aborts a manual
`test_local(".")` with a bare `Error: Test failures.` and no summary, which
reads as the harness crashing rather than as a test result.
Pass `stop_on_failure = FALSE` explicitly and consume the returned data frame
(`as.data.frame(...)`, then `sum(r$failed)` and `r$test[r$failed > 0]`) to
get which test failed rather than only that something did.

**A hand-rolled harness invents failures; use the real loader.**
`source()`-ing every file in `R/` into the global environment is the obvious
way to reach dot-prefixed internals without installing the package, and it
produced five spurious errors that vanished under `pkgload::load_all(".")`
--- tests reaching code that resolves paths through `system.file()` need the
package's own installed structure.
`pkgload` is a small dependency and worth installing before trusting any
failure a `source()` harness reports.
Either way, baseline a failure against unmodified `main` (`git stash`,
re-run, `git stash pop`) before treating it as yours: two of this session's
apparently-new failures were pre-existing and environmental.

**And hold every parameter constant except the branch, or the baseline is
not one.**
The tempting shortcut is to compare the full suite on your branch against a
*filtered* run on clean `main` --- the filtered run is faster, and you already
know which files you care about.
The two numbers are then not comparable, and the difference reads as damage
you did: a full-suite 8 against a filtered 1 says "I broke 7", while the
identical filter on both sides said 4 against 1.
Same filter, same env vars (`NOT_CRAN`), same harness, same seed --- only the
branch differs.

- **Do:** run the identical command on both sides, and say which command it
  was when reporting the delta.
- **Don't:** compare a full run against a filtered one, or a `devtools::test()`
  run against a bare `Rscript` one --- per the `NOT_CRAN` trap above those two
  do not even execute the same tests.

## `pkgload::load_all()` cannot serve a PSOCK cluster, and a mutation test that never ran can look identical to one that did

`parallel::parLapplyLB()` (and any `%dopar%` backend that spins up a PSOCK
cluster) starts worker processes that `require()` the **installed** package
by name --- they have no access to the calling session's `load_all()`
environment, since that environment exists only in the parent process.
A test that reaches a PSOCK cluster therefore errors under
`devtools::load_all()` / `pkgload::load_all()` with something like
`object 'my_internal_fn' not found`, and passes cleanly once the package is
actually installed (`R CMD INSTALL`, or `devtools::install()`).
serocalculator's own source carries a comment noting this gets out of sync
in development, which is the tell that the package's authors already knew.

**This turns a mutation test that should fail into one that never runs at
all, and the two look the same from the summary line.**
The standard regression-test check --- revert the fix, re-run the test,
confirm it now fails --- assumes the test executes under both states.
Under `load_all()`, reverting a fix to a function a PSOCK worker calls does
not make the guard test fail; it makes the whole file **error** before
reaching any assertion, because the workers cannot find the function at
all, fixed or broken.
`testthat`'s summary line can then read `FAILED: 0` in both the before and
after runs, which reads as "the fix changed nothing" when the true story is
"this test never executed either time".

- **Do:** install the package for real (`R CMD INSTALL .` or
  `devtools::install()`) before running or mutation-testing any test that
  spins up a parallel cluster.
- **Do:** treat identical before/after counts from a mutation test as
  uninformative rather than reassuring, and check for `ERROR`/`SKIP` on the
  specific test before trusting a `FAILED: 0` either way.
- **Don't:** trust a green (or an unchanged) `testthat` summary for a
  cluster-using test run under `load_all()`.

**A related, separate platform trap: `doParallel::registerDoParallel(cores = 1)`
does not mean "run serially in the calling process" on every OS.**
On Unix it registers a multicore backend, and `%dopar%` with a multicore
backend still runs in the calling process (it forks rather than spawning a
cluster), so any RNG or global-state mutation inside the loop leaks back to
the caller even at `cores = 1`.
On Windows the same call builds a one-worker PSOCK cluster instead, which
runs in a separate process, so the identical mutation does **not** leak
there.
A test written to guard against the Unix-side leak passes vacuously on
Windows, for a reason that has nothing to do with the fix being tested ---
check which backend a test's own `num_cores`/`cores` argument resolves to
on the platform running it, rather than assuming the guarded code path was
exercised.

(`UCD-SERG/serocalculator#668`, 2026-09-01: a snapshot-change prediction was
derived from which `RNGseq_seed()` branch each call would take, without
checking what `num_cores` those calls actually ran under in CI.
They used the multi-core default and forked, so the leak the PR fixed never
reached them, and the prediction --- sound reasoning applied to an
unchecked population --- did not hold.
See [`metacognitive-monitoring`](../shared/workflow/metacognitive-monitoring.md)'s
"A sound measurement does not license the claim standing next to it".)

**A third, adjacent trap in the same package-loading machinery: `load_all()` and `library()` produce differently-locked bindings, and a patch or mutation harness that patches a package's own functions is sensitive to which one it got.**
Built a throwaway one-function package and loaded it with `pkgload::load_all(export_all = FALSE)`:

```r
ns.locked = TRUE    attached.locked = FALSE    identical(ns, attached) = FALSE
assign("fmt", mutant, envir = as.environment("package:tstpkg"))   #> SUCCEEDED
```

Installed packages loaded with `library()` lock **both** environments.
Measured across `jsonlite`, `rlang`, `cli`, `glue`, and `stats` (all `ns.locked=TRUE attached.locked=TRUE`), and the equivalent `assign()` fails there with `cannot change value of locked binding for '<name>'`.
A peer session independently reproduced this on `cli`, `flextable`, and `knitr` installed, against `hac.sap` under `load_all()`. (Verified 2026-09-02, R 4.6.0 / macOS.)

Three consequences, in descending order of how long they stay useful:

1. **A patch or mutation harness written against `load_all()` can fail once the package is installed, and it fails quietly.**
   A dead harness reports every mutation as undetected, which is indistinguishable from a suite that genuinely catches nothing.
   So a harness must assert liveness on every path it runs on --- development and `R CMD check` --- not only the one it was authored against: an invocation counter, or a mutation known to be caught, run in the same invocation.
2. **`unlockBinding()` against the attached environment is a no-op under `load_all()`**, because that binding was never locked there.
   It is load-bearing only against the namespace.
3. **When comparing the two environments, take an exported name.**
   `ls(asNamespace(pkg))[1]` returns internal symbols that are absent from the attached environment, which produces spurious skips rather than a real comparison.
   The peer hit exactly this and reported five bogus SKIPs before switching to exported names.

- **Do:** assert a mutation harness is live (an invocation counter, or a known-caught mutation) in every environment it runs in, not only the one it was authored against.
- **Do:** unlock (or patch) the namespace binding, not the attached one, when the target might be running under `load_all()`.
- **Do:** compare `ns`/`attached` locking (or membership) using an exported name, never `ls(asNamespace(pkg))[1]`.
- **Don't:** trust a mutation-testing harness's "all mutations caught" verdict without confirming it ran the same way under `load_all()` and under an installed package.

([ucdavis/hac.sap#27](https://github.com/ucdavis/hac.sap/issues/27), a mutation-testing investigation where eight exported formatters accepted a `"MUTANT"` return with the suite still reporting 31/31 passing.)

## `{cli}` glue-interpolates every message string, and the two brace forms fail differently

`cli_ul()`, `cli_alert_*()`, `cli_abort()` and the rest run each string
through cli's glue engine, so any `{` a caller did not intend as markup is
interpreted --- and the two cases do **not** behave alike, with the
harmless-looking one being the dangerous one.
Verified against cli 3.6.6:

```r
cli::cli_ul("a \\name{} b")   #> * a \name b        <- no error, braces DELETED
cli::cli_ul("a {foo} b")      #> Error: Could not evaluate cli `{}` expression: `foo`.
```

An **empty** `{}` does not raise: glue evaluates the empty expression and the
braces vanish from the output, silently corrupting the message (a user reads
`\name` where the source said `\name{}`).
A **non-empty** `{foo}` hard-errors on the missing object, taking down the
whole call.
Which one applies is easy to get backwards --- a review of
`d-morrison/altdoc#87` predicted the crash for the empty form, and the
opposite is true.

This matters wherever a message carries text the code did not author:
a forwarded `conditionMessage()`, a file path, a URL from `DESCRIPTION` or
`pkgdown.yml`, a user-supplied name.
Escape braces (double them) first, or use `cli::cli_verbatim()` per item
when the surrounding formatting allows it.

Two consequences for testing it.
A regression test built on the *empty* form passes vacuously against
unescaped code, since that path never errored --- pick a fixture carrying a
populated brace (`https://x.org/{version}/` reaching a URL check works).
And assert the brace survives somewhere, not merely that nothing raised.

Where to look is not where you would guess: cli does not hand back the text
it formatted, and `cli_ul()` returns the element **id** (`"cli-10293-1"`), so
inspecting its return value yields a plausible scalar that never held the
message.
Use the enclosing function's return value when it hands back the strings it
printed (altdoc#87 asserts on `check_altdoc()`'s invisible findings),
`testthat::expect_output()` when nothing is returned, or
`conditionMessage()` for `cli_abort()`.

## Quarto chapter frontmatter and site wiring

Adding a new top-level chapter (`chapters/*.qmd`) requires four mechanical steps,
and missing any one is flagged as blocking:

1. YAML frontmatter `format:` block
(`html`/`revealjs`→`<slug>-slides.html`/`pdf`→`<slug>-handout.pdf`/`docx`→`<slug>.docx`)
--- without it the revealjs output collides on the literal `{stem}-slides.html` path.
2. Navbar entry in `_quarto-website.yml` `navbar.Chapters.menu`.
3. Homepage bullet in `index.qmd` `## Chapters`.
4. WORDLIST entries for new proper nouns in `inst/WORDLIST`
(add, don't reword to dodge).

Lychee link check: authenticated MCP endpoints quoted as prose
(`https://mcp.granola.ai/mcp`, `https://api.githubcopilot.com/mcp`) are not browsable pages;
exclude them in `lychee.toml` rather than treating the check failure as a broken link (wai#133).

## Inline R: avoid scientific notation with `formatC(..., format="d", big.mark=",")`

`format(200000, big.mark=",")` renders as `2e+05` under default `scipen`.
Use `formatC(..., format="d", big.mark=",")` (or `prettyNum(..., scientific=FALSE)`)
so derived figures like `192,000` render with commas in Quarto inline R.
Hit on wai#128 (byok ITPM/budget figures).

## Statistical Analysis Plans (SAPs) and reporting documents

- **Audience scope**: An SAP is a formal statistical design document for stakeholders,
  investigators, and reviewers.
  Maintain statistical rigor in the narrative (estimands, modeling assumptions,
  variance estimation, operating characteristics) and avoid implementation/tutorial
  commentary or discussing internal code/function names in the narrative body.
- **Don't Reinvent the Wheel (DRW)**: Do not define custom utility operators
  (such as `%||%`) when standard packages already imported or suggested
  (`rlang::%||%`) provide them.
- **Place document formatting functions in `R/`**: Table formatting functions used
  across reports/vignettes should be standard package functions in `R/` with full
  roxygen2 documentation and unit test coverage in `tests/testthat/`, rather than
  orphan vignette scripts.

