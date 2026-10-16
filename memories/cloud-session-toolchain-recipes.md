# Cloud-session toolchain recipes (render, LaTeX, R)

Measured in claude.ai cloud sessions, 2026-10-12 to 2026-10-16.
Earlier TinyTeX and R findings are in [`r-cloud-sessions`](r-cloud-sessions.md); this file adds what was missing.
A coordinator rule applies: do not skip a check because a tool is missing, and do not leave the PDF check to CI.

## When the SessionStart toolchain install dies

The render-toolchain hook's background install can stall with no done marker and a frozen log (2026-10-12, 2026-10-15).
Check `Rscript -e 'requireNamespace("knitr")'` and install by hand rather than waiting.

- `typos`: `cargo install typos-cli` finished in a few minutes (cargo is on the box).
- A page with no heavy chunks (a syllabus) renders with only `knitr rmarkdown yaml jsonlite readr dplyr rlang reticulate` from `https://packagemanager.posit.co/cran/__linux__/noble/latest` (binary installs, under a minute), plus `git submodule update --init latex-macros`.
  Then `R_LD_LIBRARY_PATH="$(R RHOME)/lib" quarto render chapters/syllabus.qmd --to html`.
- The agent proxy blocks uv's download (`releases.astral.sh`), so reticulate cannot provision Python.
  Make a venv with numpy, pandas and matplotlib (plus `plotly` for big-ideas) and set `RETICULATE_PYTHON`.
- `rsvg-convert` comes from `apt-get install librsvg2-bin`.
  `quarto render <page>.qmd --to latex` needs it and reproduces PDF-only crossref and LaTeX failures cheaply, without TinyTeX.
- A full PDF needs TinyTeX: `CLAUDE_CODE_REMOTE=true bash <repo>/.claude/hooks/render-toolchain.sh` takes about 10 minutes, then `PATH="$HOME/.TinyTeX/bin/x86_64-linux:$PATH"`.

## TinyTeX by hand

`quarto install tinytex` fails (GitHub API 403) and `mirror.ctan.org` is denied by the proxy.
Two routes worked:

- `Rscript -e 'install.packages("tinytex"); tinytex::install_tinytex(force=TRUE)'`, then `tlmgr option repository https://ctan.math.illinois.edu/systems/texlive/tlnet`, `tlmgr update --self` (2026-10-12).
- Download the release asset by tag (`github.com/rstudio/tinytex-releases/releases/download/v2026.03/TinyTeX-1-v2026.03.tar.gz`), unpack into `~`, point `tlmgr` at `https://mirrors.mit.edu/CTAN/systems/texlive/tlnet`, and run that mirror's `update-tlmgr-latest.sh -- --update` once, since the tarball is TeX Live 2025 and `tlmgr` refuses to install across releases (macros#164, 2026-10-16).

## Checks that need a particular environment

- The macros repo `macros-table.qmd` reports every macro as "Missing interpretation" under the C locale.
  Export `LANG=C.UTF-8 LC_ALL=C.UTF-8` and install the R package `DT` (binary from packagemanager.posit.co noble).
  The "fails on main too" table-build error was environmental, so file no issue for it.
- `tools/check_latex.py` needs `pdflatex`, so install TinyTeX first.
  It does not exercise a new macro, so also render a test `.qmd` that includes `macros.qmd` via `include-in-header` and uses the macro with a subscript and an exponent (`\condE{...}{...}^2`).
  An unbraced `\paren{}^2` leaves the script on an empty atom (macros#151), so brace a macro body that ends in a delimiter macro (macros#152, 2026-10-15;
  Ezra had pushed back on "no LaTeX").
- Pushing to a second repo needs `add_repo` with `access: "push"` first.
- The gha `check-new-line-breaks` check flags a bold lead-in followed by text on one line (`**Fitting.** We find ...`), long lines with a mid-line semicolon, and packed sentences.
  Three lds pushes each failed on one such line (2026-10-14), and the CI log names only the first offender.
  Run it locally first: `git clone --depth 1 --branch v3 https://github.com/Morrison-Lab/gha.git`, then from the repo checkout run `NLB_BASE_REF=origin/main NLB_GLOBS='*.md *.qmd' NLB_PATHS_IGNORE='_extensions/**,lectures/**,chapters/outtakes/**' NLB_FAIL=true NLB_CLAUSE_BREAKS=true NLB_CLAUSE_MIN_LENGTH=80 python3 gha/check-new-line-breaks/check-new-line-breaks.py`.
  Put it in the brief of any worker editing prose.

## R in a cloud session: never declare it unrestorable

On rme#1326 (2026-10-14) "R can't be restored in this container" was my mistake, not a limit, and Ezra rejected it.
Three causes stacked:

- `pkill -f install.packages` killed my own shell and left a stale `/usr/local/lib/R/site-library/00LOCK-*` directory, so later installs died with "failed to lock directory".
- The repo's `.Rprofile` loads renv, whose sandbox library hides the system site-library, so knitr and rmarkdown looked missing.
- GitHub tarball URLs (codeload, API tarball, archive) return 403, so `renv::restore` and `remotes::install_github` die on GitHub-only packages.

- **Do:** `rm -rf /usr/local/lib/R/site-library/00LOCK*`, run installs from `/tmp` with `Rscript --no-init-file`, and install CRAN dependencies with `install.packages(..., lib="/usr/local/lib/R/site-library")`.
- **Do:** for a GitHub-only package, `git clone` it (git works through the proxy), check out the SHA pinned in DESCRIPTION `Remotes`, then `remotes::install_local()`.
- **Do:** render with `RENV_CONFIG_AUTOLOADER_ENABLED=FALSE` and `R_LD_LIBRARY_PATH="$(R RHOME)/lib"`.
- **Don't:** `pkill -f` a pattern that can match your own shell.
- **Don't:** tell Ezra a tool is unavailable before a second, different attempt.

## Reading a private PR preview

The private Pages URL returns 404 to curl.
Read the built files from the branch instead (Ezra, 2026-10-12: "remember you can always inspect the gh-pages branch directly"): `git fetch origin gh-pages`, then `git show origin/gh-pages:pr-preview/pr-N/chapters/<page>.html`.
Check that new ids exist and no `?@` unresolved cross-reference appears.
The preview is built from the head at build time, so re-check after a push.
For behaviour a file cannot show (an embed), open the deployed preview in Playwright Chromium;
a local `file://` render can fail where the https preview works.
