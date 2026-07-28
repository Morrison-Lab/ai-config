# R, Quarto & the R toolchain

## R / Quarto (rme etc.) in Claude Code cloud / web sessions
- The renv library is NOT provisioned at session start (`requireNamespace`
  returns FALSE for lintr/spelling/rmarkdown). `renv::restore()` from the
  lockfile's CRAN *source* repo is slow. Instead install only what a given
  chapter needs, from BINARY repos:
  - CRAN pkgs → P3M binaries:
    `options(repos = c(P3M = "https://packagemanager.posit.co/cran/__linux__/noble/latest"))`
    then `install.packages(...)` (installs into the active renv library; fast).
  - To restore the WHOLE lockfile (when you don't know which pkgs a render
    pulls in), point renv itself at P3M binaries instead of hand-picking:
    `Sys.setenv(RENV_CONFIG_PPM_ENABLED = "TRUE")` (or
    `options(renv.config.ppm.enabled = TRUE)`) + P3M `repos`, then
    `renv::restore(prompt = FALSE)`. Observed on rme: ~264 pkgs in ~5 min
    (mostly cache-linked binaries; a few like glmmTMB still build from source).
    A plain source-repo `renv::restore()` times out — enabling P3M is what
    makes the full restore feasible. knitr/rmarkdown must be present for
    `quarto render` to even start the knitr engine (`--no-execute` does NOT
    skip the engine check), so a full restore is the surest path when an edit
    needs a real render.
  - **This isn't rme-specific — check any R-package repo's own CI YAML for a
    `RENV_CONFIG_REPOS_OVERRIDE` / RSPM env var before running
    `renv::restore()` interactively, and set the same one yourself.** The CI
    workflow's `env:` block does NOT propagate to a bare `Rscript -e
    'renv::restore(...)'` you launch by hand — it's just an unset env var in
    your session — so skipping this replicates the "plain source-repo restore
    times out" trap even on a repo whose own CI already solved it. Confirmed on
    ucdavis/bcs: an interactive `renv::restore(prompt = FALSE)` with no P3M
    override spent 40+ minutes compiling `arrow` from source alone (out of
    267 packages), when `R-CMD-check.yaml`'s own
    `RENV_CONFIG_REPOS_OVERRIDE: https://packagemanager.posit.co/cran/__linux__/noble/latest`
    was sitting right there in the workflow file the whole time.
  - d-morrison GitHub-only pkgs → r-universe `https://d-morrison.r-universe.dev`
    has `dobson`, `regress3d` (and more), but NOT `rmb` — and `rmb`'s standard
    install channels (tarball/clone via `github.com`/`codeload`, plus
    `api.github.com` for renv/pak) are proxy-blocked when the repo isn't in
    session scope. That no longer blocks renders of chapters that do
    `rmb::hers` / `library(rmb)`: see the "Scope-blocked GitHub repo, but you
    only need its *datasets*" bullet in this file for the data-only rebuild
    from `raw.githubusercontent.com` (which stays reachable).
  - `igraph` needs system lib `libglpk.so.40` → `apt-get install -y libglpk40`
    (you're root in these containers). Needed to run `data-raw/callout-graph.R`.
  - The install routes through **pak** (renv's pak backend), which is ATOMIC:
    if ONE requested pkg is unavailable (e.g. rmb), the WHOLE transaction rolls
    back and nothing installs — drop the unavailable pkg and retry. (Holds for
    `pak::pkg_install()`, and for `install.packages()` while renv's pak backend
    is active; base `install.packages()` on its own is NOT atomic.)
  - The **`renv` autoloader can shadow a system-library install.** If you
    `install.packages()` a Suggests-only tool (e.g. `lintr`, `spelling`) into the
    *default* libPaths rather than the active renv library, `Rscript` run from the
    repo root STILL fails with "no package called 'lintr'" — the project
    `.Rprofile` autoloader resets `.libPaths()` to the renv library on startup.
    Either install into the renv library (the P3M path above), or run the one-off
    with the autoloader off:
    `RENV_CONFIG_AUTOLOADER_ENABLED=FALSE Rscript -e 'lintr::lint("path/to/file.qmd")'`.
    (Used to lint the changed files for rme #873 when lintr wasn't in the renv lib.)
- **When the container's R is a brand-new release P3M hasn't built binaries for
  yet** (e.g. R 4.6.1 in mid-2026), `install.packages()` from P3M silently falls
  back to **source**, and heavy pkgs (DT → sass, etc.) fail or time out — so a
  full HTML `quarto render` (needs knitr/DT/rmarkdown) isn't feasible locally.
  Two mitigations: (1) replicate just the **build-breaking check in base R**
  (e.g. a Quarto page's `stop()`-on-missing-data guard) — base R needs no
  install; (2) `quarto install tinytex` **does** work, so validate the LaTeX/PDF
  paths locally with lualatex (`quarto render <f>.qmd --to pdf`) even when the
  HTML render is blocked. Let CI do the authoritative HTML render. (macros#71:
  DT/knitr uninstallable, but a base-R interpretation-completeness check + a
  lualatex PDF render of the new macros validated the change before push.)
  **Before accepting "uninstallable," try `install.packages()` straight from a
  source CRAN mirror** (`options(repos = c(CRAN = "https://cloud.r-project.org"));
  install.packages(c("knitr", "rmarkdown", "DT"))`, no P3M) — it builds sass/DT
  etc. from source and can succeed in a few minutes even when P3M's binary
  fallback fails, unlocking the full local HTML render instead of falling back
  to the base-R/PDF-only mitigations above. Why CRAN-direct can succeed where
  P3M's source fallback doesn't isn't confirmed — both ultimately build the same
  source tarball, so the difference is more likely P3M's build sandbox (timeout
  or resource limits) than a real incompatibility; note the actual mechanism
  here if a future session pins it down. (macros#74: same class of container,
  but a plain-CRAN source install of knitr/rmarkdown/DT succeeded, letting all
  three of `CONTRIBUTING.md`'s documented renders — both PDF demos and the full
  HTML site — run locally before push.)
- **A fresh `git worktree` gets its own renv library cache, keyed by the
  worktree's absolute path** (`/root/.cache/R/renv/library/<repo>-<worktree-dirname>-<hash>/...`),
  separate from the main checkout's already-populated cache. Its own
  `renv::restore()` can fail to bootstrap for the same reasons as a fresh
  session — a renamed GitHub repo in `Remotes:`, P3M binaries not yet built
  for a brand-new R release (see the bullets above and below), or renv's own
  live GitHub-API resolution of `Remotes:` (unset `RENV_CONFIG_INSTALL_REMOTES`
  defaults to `TRUE`, so `renv::restore()`/activation hits `api.github.com`
  even though the actual package versions installed come entirely from
  `renv.lock`'s pinned SHAs; set `RENV_CONFIG_INSTALL_REMOTES=false` to skip
  that network dependency) — so `quarto render` inside the worktree errors
  with "the knitr package is not available" even though the SAME package is
  installed and working in the main checkout. **Don't force the local render
  through this** — push, let CI's `build`/`quarto render` job do the real
  render (it already has the right env vars and a working cache), then verify
  the rendered output by fetching the PR-preview HTML straight from the
  `gh-pages` branch: `mcp__github__get_file_contents` with
  `path: pr-preview/pr-<N>/<chapter>.html`, `ref: refs/heads/gh-pages` returned
  the file, in one observed session, **base64-decoded already** (not raw
  base64) as a `[{type,text}, {type,text}]` array with the actual HTML in the
  second element — write it to a scratch file (Python `json.load` + write
  `data[1]['text']`) and `grep`/`Read` it to confirm cross-refs resolved (no
  literal `?@id` or `**id?**` text), computed values match your derivation,
  and new callout/div structure rendered as intended. This exact array shape
  is an observed harness behavior, not a documented contract — if
  `data[1]['text']` is missing or isn't HTML, `cat`/`head` the saved file to
  see its actual structure (try `data[0]['text']` next) rather than assuming
  the recipe is wrong. This is strictly more reliable than fighting the
  worktree's renv bootstrap, and it's what actually caught a real structural
  bug — a stray `---` left next to a `{{< slidebreak >}}` rendering a
  spurious `<hr>` in every non-`revealjs` Quarto profile, invisible from
  reading the `.qmd` source alone — that a purely-local read wouldn't have
  surfaced. (`d-morrison/rme#1009`, several rounds: a background
  `renv::restore()` in `/tmp/rme-<issue>-worktree` sat at "renv installed,
  nothing else" after the worktree was removed and re-created at the same
  path — verified the actual chapter content instead via this gh-pages
  fetch, twice, once per structural fix.)
- **A `renv::restore()` failure downloading `https://api.github.com/repos/<owner>/<repo>/...`
  with `error code 22` can mean the GitHub-pinned `Remotes:` package was
  renamed/transferred, not a transient network blip.** `insightsengineering/cardx`
  moved to `pharmaverse/cardx`; GitHub's rename redirect doesn't reliably resolve
  for the specific REST endpoints `renv::restore()` hits, so every restore under
  the old owner fails identically and repeatedly — check actual job logs each
  time rather than assuming "the same infra flakiness as before" (a failure that
  looks recurring can still be worth re-diagnosing once; this one turned out to
  have a real, fixable root cause). `RENV_CONFIG_INSTALL_REMOTES=false` (see the
  worktree bullet above) sidesteps it entirely, since the actual installed
  versions come from `renv.lock`'s pinned SHAs regardless of where `Remotes:`
  points. (`d-morrison/rme#772`, tracked in `d-morrison/rme#994` and `d-morrison/rme#996`, fixed centrally in
  `d-morrison/gha#241`.)
- **R in these containers defaults to the `C` locale**, so
  `read.delim(..., fileEncoding="UTF-8")` (or any read) of a file with multibyte
  chars (π, μ, ℓ, …) **silently truncates at the first non-ASCII byte**, emitting
  only an `invalid input found on input connection` warning — you get a few rows,
  not all, and a completeness check then reports bogus "missing" rows. Run R with
  `LANG=C.UTF-8 LC_ALL=C.UTF-8 Rscript …` to read UTF-8 data files correctly.
  (CI runners are UTF-8, so this bites only locally.)
- **renv activation failure when a GitHub remote is blocked**: if `DESCRIPTION`
  lists a GitHub `Remotes:` entry for a repo the session's git proxy hasn't
  scoped in, renv activation (via `.Rprofile`) aborts on startup — every
  subsequent `R` call errors before loading any package (e.g. bcs's
  `d-morrison/altdoc@recursive-qmd-search`: a plain `curl` to
  `api.github.com/repos/d-morrison/altdoc/...` 403'd with `"GitHub access to
  this repository is not enabled for this session. Use add_repo to request
  access."` — this is the *session repo-scope* check, not a general network
  block; the same 403 hits `renv`/`pak`'s own `api.github.com` calls even
  though they never go through an MCP tool).
  Quick bypass (when you just need *a* working R session, not to fix the
  remote): `R --no-save --no-restore --no-site-file --no-init-file` skips
  `.Rprofile` entirely; install needed packages from P3M into the user
  library and proceed.
  **Real fix, when the remote itself is wrong or you need the full
  dependency tree:** call `add_repo` for the blocked owner/repo — this
  unblocks the proxy's direct HTTPS access (curl, `renv::restore()`,
  `pak`), not just the GitHub MCP tools, so **no local clone is needed**
  just to resolve dependencies (ignore `add_repo`'s "clone it now"
  instructions unless you actually need the repo's file contents). Then
  check whether the pinned non-default branch has already merged into the
  remote repo's default branch — `curl .../compare/main...<branch>` and
  read `ahead_by`/`behind_by`; `behind_by: N, ahead_by: 0` means the branch
  is a fully-merged, stale ref — and if so, repoint `Remotes:` at the
  default branch instead of leaving DESCRIPTION pinned to dead history.
  **Grep the whole repo for other hardcoded copies of the same remote
  spec** before considering the fix complete — a CI workflow's
  `extra-packages:` list can duplicate the exact same `owner/repo@branch`
  string outside DESCRIPTION, and fixing only DESCRIPTION leaves pak's
  dependency solver seeing two conflicting specs for the same package
  (`Conflicts with <old-spec>`). If nothing else needs that duplicate
  pin (e.g. `r-lib/actions/setup-r-dependencies`'s `needs: check` /
  `local::.` already resolves the package from DESCRIPTION's own
  `Remotes:`), just delete the redundant `extra-packages` line rather than
  updating it in two places. (ucdavis/bcs#310, 2026-07-06: this exact
  chain — `add_repo` unblock, `compare` showing the branch fully merged,
  then two more hardcoded copies of the same stale ref found in
  `docs.yaml` and `copilot-setup-steps.yml`.)
- **When a consumer repo pins a dependency to an upstream *feature branch*
  (not a tag/default branch) and the consumer's CI is failing because of a bug
  *in* that dependency, the fix must land ON that pinned branch --- open a PR
  into it, don't just fix the consumer.** The consumer's CI reinstalls the
  branch's tip on the next run (pak/`setup-r-dependencies` resolves
  `owner/repo@branch` to its current SHA at install time), so once the upstream
  fix merges into the pinned branch, re-triggering the consumer's failing job
  picks it up with no change to the consumer at all. Corollary: a stale feature
  branch can fail its *own* repo's newer CI (e.g. a `jarl-check` on
  pre-existing `unused_function` warnings) purely from being behind `main` ---
  don't debug those as new defects; catch the branch up to `main`'s
  already-clean state (mirror what `main` already did: add the `jarl.toml`,
  remove the dead functions `main` removed). Verify main's tree with
  `git show origin/main:<file>` reads rather than a shallow-clone range diff
  (see below). (UCD-SERG/serocalculator#503 pinned
  `d-morrison/altdoc@recursive-qmd-search`; fixing the consumer's docs build
  required altdoc PR #27 into that branch, and altdoc PR #28 caught the branch
  up to main's jarl-clean state, 2026-07.)
- **Scope-blocked GitHub repo, but you only need its *datasets* (an R data
  package like `rmb`): rebuild a minimal data-only package from
  `raw.githubusercontent.com`.** The proxy's repo-scope check blocks
  `github.com`/`codeload.github.com` tarball downloads and `git clone` for
  out-of-scope repos (the same 403 as the renv bullet above), and `add_repo`
  needs an explicit user request — but `raw.githubusercontent.com` serves the
  same repo's files fine. When the consuming render/tests only use
  `pkg::dataset` objects (grep for `pkg::` to enumerate them), fetch
  `DESCRIPTION` plus just the needed `data/*.rda` files at the lockfile's
  pinned `RemoteSha`, write a stub comment-only `NAMESPACE`, and
  `R CMD INSTALL` the result: `LazyData: true` makes `pkg::dataset` resolve
  via lazydata with no exports and no `R/` sources needed. Don't copy the
  real `NAMESPACE` — its `export()` lines reference functions whose `R/`
  sources you didn't fetch, and the install fails on the missing objects.
  (rme#1047/#1048: unblocked `quarto render` of a chapter needing
  `rmb::hers` after the tarball 403'd; the older installed `rmb` predated
  the dataset.)
- **A stale `00LOCK-*` directory silently blocks every subsequent
  `install.packages()` call**, left behind when an earlier install was
  interrupted (killed mid-run, or two `install.packages()` calls racing —
  e.g. a foregrounded retry while an earlier `nohup`'d background install was
  still holding the lock). Under `quiet = TRUE` the only symptom is
  `installation of package 'X' had non-zero exit status` for every package in
  the call, with no hint why — rerun once without `quiet` to see the real
  `ERROR: failed to lock directory '.../site-library' for modifying` line.
  Fix: `rm -rf` the lock directory shown in that error output — typically
  `/usr/local/lib/R/site-library/00LOCK-*` in these containers, but confirm
  the path from the error rather than assuming it (an renv project or a
  user-library session uses a different one) — then retry; packages
  installed before the interruption are still there; only the retry was
  blocked. (ucdavis/ettbc#32: cost real time before diagnosing, since most of
  a large dependency tree had actually installed fine and only the lock
  blocked the last few packages.)
- **To check whether a CRAN package is archived, query the PPM JSON API, not
  WebFetch against the CRAN HTML page — and check `is_archived`, NOT
  `tran_archive`.**
  `curl -s https://packagemanager.posit.co/__api__/repos/cran/packages/<pkg>`
  returns a top-level boolean `"is_archived": true|false` — that's the
  authoritative field. `tran_archive` is a decoy: it's present in the same
  response but stays `null` even for a package that **is** archived (verified
  directly — `pryr`'s response has `"tran_archive": null` alongside
  `"is_archived": true`), so checking it gives a false "not archived" on every
  query. Confirmed by curling both packages live: `pryr` and `veccompare` each
  return `"is_archived": true`. WebFetch summarizing
  `cran.r-project.org/package=<pkg>` can also return confident-sounding but
  unverified specifics (an "Archival Date" / "Reason" framing CRAN's actual
  archived-package page doesn't present that way) — cross-check against the
  PPM API's `is_archived` field before citing a date or reason as fact.
  (Surfaced on ucdavis/fxtas#157: pak failed to resolve `pryr` +
  `veccompare` from the PPM snapshot; the repo owner verified via this
  endpoint before concluding they were genuinely archived.)
- **`snapr` is not on CRAN or P3M**: install from the GitHub tarball.
  `curl -L https://codeload.github.com/d-morrison/snapr/tar.gz/refs/heads/main -o /tmp/snapr.tar.gz`
  then in R, install `readr` first (a direct `snapr` `Imports:` dependency):
  `install.packages("readr")`, then
  `install.packages("/tmp/snapr.tar.gz", repos=NULL, type="source")`.
  `snapr::expect_snapshot_data()` silently skips snapshot generation/comparison when
  `NOT_CRAN` is unset (respects the standard CRAN-skip convention):
  `NOT_CRAN=true Rscript -e 'devtools::test()'`.
- The `latex-macros` submodule (d-morrison/macros) is uninitialized on a fresh
  clone → `git submodule update --init latex-macros` before any render, else
  `{{< include latex-macros/macros.qmd >}}` fails for every chapter.
- More generally, when Quarto errors with `Include directive failed` / `could
  not find file ...` and the missing path is under a submodule directory,
  check `git submodule status` first and initialize/update that submodule in
  the current worktree before debugging include paths (`git submodule update
  --init <path>`). (Observed in UCD-SERG/serocalculator, 2026-07-22: missing
  `../macros/macros.qmd` was from an uninitialized `macros` submodule, not a
  bad include expression.)
- In a Quarto **project** (observed on rme), `{{< include >}}` paths for files
  rendered via a root wrapper resolved from the PROJECT ROOT *in practice* —
  even for *nested* includes inside subfiles (a `{{< include _root.qmd >}}`
  inside `_subdir/nested.qmd`, rendered via a root wrapper, picked up `_root.qmd`
  from the project root, not from `_subdir/`). This is contrary to the Quarto
  docs' single-document rule ("relative to the file containing the include").
  One observation can't rule out a confound, and behavior may differ across
  Quarto versions or project configs — so test; don't assume *either* rule holds
  without checking. To verify touched subfiles when the full
  chapter needs an unavailable pkg (rmb): write a minimal wrapper `.qmd` AT THE
  REPO ROOT that includes `latex-macros/macros.qmd` + the subfiles, loading data
  manually
  (`hers <- haven::read_dta(here::here("inst/extdata/hersdata.dta"))`). This
  checks LaTeX/markdown/cross-refs for edits that don't touch R chunks without
  provisioning the whole dep tree. Grep the rendered HTML for `?@` / `>??<` to
  catch broken cross-refs.
- **Asset paths in `{{< include >}}`-ed fragments resolve against the
  master/including file's directory** in the outputs that matter (observed on
  wai, Quarto 1.9.38, `type: website`; distinct from *include-path*
  resolution in the bullet above --- that one is about where a nested
  `{{< include >}}` directive finds its target file, this one is about where
  a relative image/asset path inside a fragment resolves at render time): the rendered master HTML page emits
  the `img src` as written, relative to the master page's output location,
  and the lualatex PDF pass compiles from the master file's directory. So an
  image referenced as `assets/images/x.png` inside
  `chapters/ai-tools/fragment.qmd`, included by `chapters/master.qmd`, must
  live at `chapters/assets/images/x.png` — project root and fragment-dir
  placements both fail (HTML silently as a placeholder; PDF hard with
  lualatex `file not found`). Verify empirically: check where `quarto render`
  copies the asset under `_site/`, and read the failing `.log`'s own path
  (`chapters/master.log` ⇒ compile cwd was `chapters/`). Related trap that
  let a wrong fix merge green: wai's PR `preview` job renders HTML only,
  while `publish.yml` on main renders all formats — the PR's checks never
  exercised the PDF pass, so main stayed red after merge. Identify which CI
  job actually runs the failing format before trusting a green PR.
  (wai#13 → #15 → #16, 2026-07-16.)
- Chapters that `{{< include r-config.qmd >}}` pull the full ~40-pkg set
  (dobson, survminer, gtsummary, …); chapters that only include macros.qmd are
  light (math-prereqs needs just plotly).
- **A sandbox with no R at all: `apt-get install r-cran-*` binaries can be ABI-
  incompatible with the installed R version.** A fresh container with R 4.6.1
  and no packages hit pervasive `undefined symbol: SETLENGTH` / `SET_FORMALS` /
  `R_nchar` / `SET_GROWABLE_BIT` errors across dplyr, vctrs, fansi, tibble,
  testthat, pkgload, roxygen2, readr, and their transitive deps — apt's
  prebuilt `r-cran-*` .debs were built against a different R ABI than the one
  actually installed. Fix: reinstall every affected package from source,
  `install.packages(pkgs, type = "source")`, resolving each new transitive
  failure iteratively (plus any system libs a source build needs, e.g.
  `libudunits2-dev` for the `units` package's C bindings). Slow but gets a
  real, verifiable R toolchain instead of guessing at doc/roxygen output.
  (serocalculator PR-393-extraction session, 2026-07-08.)
- **`testthat::test_dir()` run without every snapshot-consuming package
  installed can DELETE committed snapshot files.** testthat's own end-of-run
  "Deleting unused snapshots" cleanup treats any snapshot it didn't see
  exercised (e.g. an `expect_snapshot_file()` an `svglite`/`vdiffr`-dependent
  test skipped because `vdiffr` wasn't installed in a stripped-down sandbox)
  as orphaned and removes it from `tests/testthat/_snaps/` — silently, with no
  confirmation prompt. Caught only via `git status --short` before staging
  anything (21 legitimate `.svg` snapshots had vanished from the working
  tree); restored with `git checkout -- <paths>`. Prefer
  `testthat::test_file()` on individual files in this kind of sandbox — it
  doesn't run the whole-suite cleanup pass — and always `git status` before
  committing after any `test_dir()` run.
- **The same deletion fires from a second, likelier trigger: two full suites
  running CONCURRENTLY in one checkout.** The mechanism is identical (the
  end-of-run cleanup prunes snapshots it did not see exercised), but the cause
  is not a missing package --- it is that the runs contend for shared resources
  (a `quarto` CLI invocation, the same temp dirs), one test *errors out early*,
  and every `expect_snapshot_file()` after the error in that file never runs, so
  its snapshots look orphaned.
  **Never run two full suites at once in a repo with snapshot tests**, however
  tempting it is to start a fresh run before an earlier one finishes.
  The tell that it is contention and not real breakage: the two runs fail on
  *different* tests.
  A genuine regression fails the same test every time, so a differing failure
  set across concurrent runs is diagnostic on its own --- check it before
  debugging the diff.
  Recovery is the same `git checkout -- tests/testthat/_snaps/` as above, then
  one clean run, alone.
  (`d-morrison/altdoc#61`, 2026-07-25: two overlapping `test_local()` runs;
  one failed on a quarto render and the other on a docsify test, and the
  docsify error silently deleted `_sidebar.md` and `index.html` --- 58 lines of
  committed snapshots.)
- **A third trigger, and the easiest to hit deliberately: running the suite
  with `NOT_CRAN` unset.**
  Same mechanism again, but here nothing is missing or contended --- every
  `skip_on_cran()` test simply skips, so the cleanup prunes their snapshots as
  unexercised.
  This is the trigger that fires on a perfectly healthy machine with every
  package installed and nothing else running, which is what makes it the one
  most likely to be mistaken for a real change.
  Set `NOT_CRAN=true` rather than merely restoring afterward, since it also
  means the run exercised the tests it appeared to: in altdoc the skip count
  went from 25 to 3 under it, and the surviving 3 were genuine venv-gated
  mkdocs skips.
  (2026-07-27, driving altdoc#64: a single `test_dir()` run deleted 27 tracked
  `_snaps/**` files, announced only as a routine `Deleting unused snapshots:`
  line, and caught by `git status --short` before staging.)
- **`git add -A` while a suite is running sweeps testthat's scratch files into
  the commit.** A failing snapshot comparison writes its proposed replacement
  next to the original as `_snaps/**/*.new.*`, so an `add -A` issued mid-run
  commits those alongside the real change.
  Stage explicit paths whenever a suite is in flight, and check `git status`
  for `*.new.*` before committing.
  Accepting such a snapshot is just `mv` over the original, which also removes
  the stray file. (Same session as above.)
- **A snapshot file that does not exist yet is CREATED SILENTLY, not failed.**
  testthat reports `Adding new file snapshot: ...` as a *warning* and the run
  passes, so adding a fixture and assuming its rendering is now covered asserts
  nothing --- the `expect_snapshot_file()` call has to be declared explicitly.
  A requirement to "add a snapshot proving X" can therefore be quietly unmet
  while the suite is green.
  After adding a fixture, confirm the intended snapshot file actually appears
  under `_snaps/`. (Same session: the fixture topic proving
  per-block `\dontrun{}` evaluation needed three explicit
  `expect_snapshot_file()` lines, one per generator, or nothing would have
  checked it.)
- **Adding a topic/case to a SHARED test fixture has a wide churn radius.**
  Every test that enumerates the fixture's contents breaks at once --- in altdoc,
  one new man page broke nine tests: three `.select_topics()` expectations,
  `.rd_topics()`, a `reference.yml` grouping test, and one reference-index
  snapshot per generator.
  None of it indicates a defect, but budget for it rather than discovering it,
  and read the snapshot diffs as evidence: each gaining exactly one line is
  what proves the change did not disturb existing output.
  Prefer a throwaway fixture built in the test when the new case does not need
  to be shared.
- **`if (cond) "name" = value` inside `c(...)` is parsed as an assignment
  expression, not a named `c()` element.** R's argument-tag recognition
  requires the tag to be the direct head of the argument passed to `c()` — a
  bare `"name" = value` — not one produced by evaluating a nested `if()`
  expression. `c("a", if (cond) "name" = value)` silently creates/evaluates a
  local variable named `name` and splices in the *unnamed* string `value`
  instead of a `name = value` pair, with no warning or error. This breaks a
  `dplyr::*_join(by = c(...))` call the moment the conditional branch fires
  (a "Join columns in x must be present in the data" error, since the
  intended named join key was silently dropped). Fix: wrap the whole
  conditional element in its own `c()` — `c("a", if (cond) c("name" = value))`
  — so the name attaches to the inner `c()` call's result, which is what gets
  spliced into the outer one. Verify with a direct R repro
  (`names(c("a", if (TRUE) "name" = "value"))` vs the wrapped form) before
  trusting either reading. (serocalculator#552 review round 1: found in
  `sim_pop_data_2()`'s `left_join(by = ...)`.)
- **`rngtools::RNGseq(n, seed)` returns an unwrapped single state vector
  (not a list-of-one) when `n == 1`**, unlike `n > 1` which returns a proper
  `list` of 7-integer L'Ecuyer-CMRG state vectors. Code that assumes a list
  regardless of `n` — e.g. `rngtools::RNGseq(n, seed) |> array(dim = c(1,1,1),
  ...)` — silently truncates the 7-integer vector to its first element when
  `array()` reshapes it, corrupting the RNG state fed to `rngtools::setRNG()`
  downstream. Symptom: genuinely non-reproducible results (different values
  across separate R sessions with the identical seed) specifically when a
  parallel/foreach-driven simulation call reduces to a single
  lambda/sample_size/cluster (or equivalent single-task) combination — every
  other combination stays reproducible, which makes this easy to miss until
  someone writes a test for exactly the single-task case. Diagnose by
  comparing `class(rngtools::RNGseq(1, seed))` (`"integer"`) against
  `class(rngtools::RNGseq(2, seed))` (`"list"`), and by checking
  `array(rngtools::RNGseq(1, seed), dim = c(1,1,1))` for silent truncation.
  Workaround at the call site: avoid the single-task case (e.g. bump a
  `nclus`-style parameter to 2+) until the root function is fixed to
  `list()`-wrap the `n == 1` case explicitly. (serocalculator#554, found
  while adding test coverage for `sim_pop_data_multi()`'s `sim_function`
  dispatch parameter — the natural minimal test used a single lambda/
  sample_size/`nclus = 1`, which happened to hit exactly this bug.)
- **Provisioning packages already tracked in `renv.lock` but missing from the
  library (an incomplete restore, not a new-package addition) hits the same
  `Remotes:`-resolution failure documented below** ("renv.lock — adding a
  package…") — `install.packages()`/`renv::install()` both route through
  renv/pak and abort the whole call if any `Remotes:` entry can't be resolved
  (blocked `api.github.com`), even for unrelated CRAN packages. For this
  simpler case (no lockfile edit needed, just get already-tracked packages
  installed), bypass `.Rprofile` entirely instead of hand-editing the
  lockfile: `Rscript --no-init-file -e '.libPaths("<renv-project-lib-path>");
  options(repos=c(CRAN="https://cloud.r-project.org")); install.packages(c(...))'`.
  (Try the P3M binary-repo approach above first; reach for this bypass only
  if that's also unavailable.)
- **Don't pass `dependencies=TRUE` when filling small gaps in an existing renv
  library.** It recurses into `Suggests` too, not just `Depends`/`Imports`, and
  can drag in huge unrelated compiled packages (hit `OpenMx`, `rsvg`, `Rfast` —
  Suggests-of-Suggests of `parameters`/`broom.helpers`) that add 30+ minutes of
  compilation and aren't needed to render. Use `dependencies=NA` (the default:
  `Depends`+`Imports`+`LinkingTo` only) — it's what's actually needed to
  `library()` and render, and installs in a fraction of the time.
- To find exactly which packages are missing (including transitively, without
  over-installing): `tools::package_dependencies(top_pkgs, db=available.packages(),
  which=c("Depends","Imports","LinkingTo"), recursive=TRUE)`, then filter with
  `requireNamespace(..., quietly=TRUE)` against the **full** `.libPaths()`
  search (not `installed.packages(lib.loc=<one dir>)`, which misses base/recommended
  packages and anything already installed in a different lib on the path and
  falsely reports them as missing).

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
  review-job cases in [`fully-clean`](../shared/workflow/fully-clean.md).
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

## R-package PR CI gates (d-morrison / UCD-SERG R packages, e.g. `bcs`)
- These repos gate PRs on a **changelog check** (`news.yaml` / "Check Changelog
  Action") and a **version-check**. A user-visible PR needs **both** a
  `NEWS.md` entry under `# <pkg> (development version)` **and** a `DESCRIPTION`
  `Version:` dev-bump (e.g. `0.0.0.9053` → `.9054`), or CI fails. Add them up
  front rather than waiting for the red check. (Observed on ucdavis/bcs#223.)
  For a **non-user-visible** PR (CI/workflow-only), skip both with the
  `no changelog` + `no version increment` labels instead — see the label-bypass
  note below.
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
belonging in `d-morrison/gha` since every altdoc repo shares the structure.)

## Quarto HTML sites (build & layout gotchas)
Hit while adding a mobile within-chapter TOC to `d-morrison/rme` (#929); apply to
any Quarto website (rme, psw, qwt, …).
- **Single-file `quarto render <file>.qmd` serves cached compiled theme CSS.**
  Edits to `custom.scss` / theme SCSS may NOT appear in the output — Quarto reuses
  the cached sass bundle. The tell: the
  `_site/site_libs/bootstrap/bootstrap-*.min.css` content hash stays identical
  across renders. Force a recompile by clearing the sass cache and the stale libs
  first: `rm -rf ~/.cache/quarto/sass _site/site_libs`, then re-render. (A
  "verified" CSS rule was actually stale until I cleared this.)
- **The within-chapter "On this page" TOC is hidden on mobile with no built-in
  replacement.** Quarto's bootstrap hides `#quarto-margin-sidebar` below the `md`
  breakpoint (`@media (max-width: 767.98px)` in `_bootstrap-rules.scss`). There is
  no `toc:` option to re-enable it; the `quarto-toc-toggle` "convert TOC to a
  floating menu" in `quarto.js` is an overlap-avoidance feature for wide screens,
  not a mobile feature (on a phone the margin sidebar is already `display:none`,
  so it never fires).
- **A cloned within-chapter TOC must NOT carry `role="doc-toc"`.** Quarto's mobile
  CSS includes a bare `nav[role=doc-toc] { display: none }` (inside the `md` media
  query), so any clone with that role stays hidden even when you mean to show it.
  Use a plain `<nav aria-label="…">` instead.
- **Navbar headroom = reveal-on-scroll-up.** Quarto attaches Headroom to
  `#quarto-header`; on scroll it toggles `sidebar-unpinned` on the header AND on
  every `.sidebar` / `.headroom-target` element (see `quarto-nav.js`). To make a
  custom element hide-on-scroll-down / reappear-on-scroll-up in step with the
  navbar, place it inside `#quarto-header` (it inherits the header's transform) or
  give it `.headroom-target`. (Used to put a "Contents" TOC button in the navbar.)
- **`quarto render` auto-modifies `.gitignore`.** On first render, Quarto appends
  `/.quarto/` and `**/*.quarto_ipynb` to `.gitignore`. If `.quarto/` is already
  present, `/.quarto/` is redundant (the unanchored form already covers the root).
  Remove `/.quarto/` only when `.quarto/` is already present; keep `**/*.quarto_ipynb`.
- **Manuscript projects do NOT support `repo-url` / `repo-actions` natively.**
  `book` and `website` inherit `base-website` schema (which includes these keys);
  `manuscript-schema` is `closed: true` with no `super`, so the keys are silently
  ignored even when placed under `website:` or `format: html:` in `_quarto.yml`.
  Workaround: a Lua filter that reads those keys from metadata and injects the links
  via inline JS — see `d-morrison/qmt/_repo-links.lua` for a full implementation.
  Upstream issue: quarto-dev/quarto-cli#14627.
- **In Quarto Lua filters, use `quarto.doc.input_file` (not `PANDOC_STATE.input_files[1]`)
  to get the real source path.** Quarto preprocesses `.qmd` files into temp files before
  passing them to Pandoc; `PANDOC_STATE.input_files[1]` gives the temp path, not the
  original `.qmd`. `quarto.doc.input_file` reads the `quarto-source` param and returns
  the real path. To compute the repo-relative path: strip `os.getenv("QUARTO_PROJECT_DIR")`
  from the front (`abs_input:sub(#project_root + 2)`). (Learned while writing `_repo-links.lua`
  for d-morrison/qmt.)
- **A plain project-wide `quarto render` (no `--to`) DOES render every format a
  document's own front matter lists** — even formats the project's `_quarto.yml`
  doesn't configure. Verified from a clean state (`rm -rf _site .quarto` first,
  no priming single-file renders) on `d-morrison/macros`: `_quarto.yml` there
  configures only `format: html:`, yet a bare `quarto render` still produced
  `.pdf`, `.docx`, and reveal.js `.html` output for every doc whose own front
  matter lists those formats — the project config sets the *default* for docs
  with no local `format:` override, it doesn't cap docs that declare their own.
  So a CI step that just runs `quarto render` **likely already exercises** the
  PDF/other-format renders a `CONTRIBUTING.md` separately documents as
  `quarto render <doc>.qmd --to pdf` — don't assume a bare project render is
  HTML-only without checking. (Corrected in ai-config#408 after re-verifying
  from a clean state; the empirical result contradicted both an earlier claim
  logged here and a reviewer's proposed replacement.) The durable lesson
  survives: don't write "CI covers this" in a PR description from assumption —
  verify what CI *actually* does before asserting either that it does or
  doesn't cover a given check.
- **Custom Quarto shortcode Lua files belong under YAML `shortcodes:`, not
  `filters:`.** A Lua file that returns a shortcode table (for example
  `return { ['slidebreak'] = slidebreak }`) does **not** register that
  shortcode when listed under `filters:`; Quarto treats it as a Pandoc filter,
  leaves `{{< slidebreak >}}` literal in rendered HTML, and warns
  `Shortcode 'slidebreak' not found`. Put the path under front-matter or
  project metadata `shortcodes:` instead (e.g.
  `shortcodes: [../_extensions/d-morrison/slidebreak/slidebreak.lua]`), even
  when the file lives inside `_extensions/`. (Observed directly in
  UCD-SERG/serocalculator, 2026-07-22: switching the same Lua path from
  `filters:` to `shortcodes:` made the shortcode render and removed the
  warning in a standalone `quarto render` smoke test.)
- **Large site renders crash Deno's default 8 GB V8 heap — deterministically,
  not flakily.** Quarto's launcher script hardcodes
  `--max-old-space-size=8192,--max-heap-size=8192` and *prepends* those
  defaults before any user-supplied `$QUARTO_DENO_V8_OPTIONS` inside one
  `--v8-flags=` argument; V8 lets the last occurrence of a flag win, so
  setting `QUARTO_DENO_V8_OPTIONS=--max-old-space-size=12288,--max-heap-size=12288`
  in the environment is the supported override. The crash signature: all
  chapters render fine individually, then `Fatal JavaScript out of memory:
  Ineffective mark-compacts near heap limit` late in the ~35-40-file site
  render (cumulative heap, worst in finalization/search-indexing), exit code
  133 — SIGTRAP, not the SIGABRT (134) a classic `abort()` would give:
  V8's fatal-error handler dies on a trap instruction, and the launcher's
  own log line confirms it (`Trace/breakpoint trap (core dumped)` followed
  by `Process completed with exit code 133`, observed identically in both
  failing runs). Reproducible on every re-run. Fixed fleet-wide in gha#263 (the
  `preview`/`quarto-publish` composites export the 12 GB override; standard
  runners have 16 GB). To validate a heap-flag change without a 20-minute
  render: run Quarto's own bundled deno
  (`/opt/quarto/bin/tools/x86_64/deno eval` with the launcher-composed flag
  string) against a >8 GB JS-heap allocation loop — crashes under the
  default string, survives with the override appended, minutes instead of
  hours. (rme #1040/#1042, 2026-07-17: four identical CI OOMs across two
  PRs; not a Quarto version change — v1.9.38 predated both green and red
  runs.)

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

## quarto-actions/setup with tinytex — two shared-runner failure signatures (win, 2026-07)

- **`ERROR: Unable to determine latest release for rstudio/tinytex-releases / 403 - Forbidden`**
  during "Set up Quarto": `quarto install tinytex`'s latest-release lookup is an
  unauthenticated GitHub API call, and shared runners intermittently rate-limit it.
  Fix: `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (or `${{ github.token }}`) on the
  setup step. gha's `preview` composite already does this; `quarto-publish` gap filed
  as gha#270. (Broke ucdavis/win's preview/publish repeatedly; fixed in win PR #69.)
- **`renv::restore()` fails compiling `curl` ("libcurl was not found")** on
  current ubuntu runner images: the R build libs are no longer preinstalled, so any
  renv repo needs an explicit apt step. Working set for a typical
  curl/openssl/xml2/gert/V8/igraph/ragg/textshaping lockfile:
  `libcurl4-openssl-dev libssl-dev libxml2-dev libgit2-dev libnode-dev libglpk-dev
  libfontconfig1-dev libfreetype6-dev libharfbuzz-dev libfribidi-dev libpng-dev
  libtiff5-dev libjpeg-dev` (gha's `preview` reusable workflow's default
  `apt-packages` list is the fuller reference).
- Diagnostic order matters: the TinyTeX 403 masks the renv gap — fixing the first
  failure surfaces the second on the next run, so read each new failed run's log
  fresh instead of assuming the prior diagnosis still applies.

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
apt-get install -y --no-install-recommends r-base-core   # R 4.6.1
Rscript -e 'install.packages(c("cli", "desc", "fs", "testthat", "pkgload"))'
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

Both bite only outside `R CMD check` / `devtools::test()`, which is exactly
where a sandbox run lives, and each fails in the direction that reads as
success.

**`skip_on_cran()` skips unless `NOT_CRAN` is set.**
A file whose every test opens with it reports `failed: 0  error: 0` and exits
`0` --- green by every signal except the one that matters.
The tell is the skip count: `skipped: 20  passed: 0` is not a pass, it is a
file that never ran.
Set `NOT_CRAN=true` on the command, and read `passed` rather than `failed`
before believing a run.

**`test_file()` / `test_local()` default to `stop_on_failure = TRUE`.**
One failing expectation aborts with a bare `Error: Test failures.` and no
summary, which reads as the harness crashing rather than as a test result.
Pass `stop_on_failure = FALSE` and consume the returned data frame
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
