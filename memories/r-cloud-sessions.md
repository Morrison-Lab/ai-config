# R & Quarto in Claude Code cloud / web sessions

Running R and Quarto inside a remote container:
toolchain installation, missing binaries, sandbox constraints,
and verifying what a PR preview actually built.
Split out of [`r-quarto.md`](r-quarto.md),
which keeps the R-toolchain and R-package material that applies anywhere.

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
  - the repository owner GitHub-only pkgs → r-universe `https://Morrison-Lab.r-universe.dev`
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
  **One mechanism now pinned down, and it is not the build sandbox: P3M can
  fail to serve an index at all.**
  The paragraph above guesses at a timeout or resource limit inside P3M's
  source build.
  At least one instance is simpler and earlier than that --- no build is ever
  attempted, because the repository index 404s:
  `unable to access index for repository https://p3m.dev/cran/__linux__/noble/latest/src/contrib:
  cannot open URL '.../PACKAGES'`, followed by `packages 'bench', 'profvis'
  are not available for this version of R`, which reads as an R-version
  incompatibility and is nothing of the kind.
  The tell is that the failure is instant rather than slow, and that the
  named packages are ordinary ones no snapshot would genuinely lack.
  Switching `repos` to `https://cloud.r-project.org` installed both plus
  about 30 dependencies in roughly a minute.
  So treat "not available for this version of R" from a P3M repo as a
  reachability symptom first and a compatibility claim second.
  (ai-config#762, 2026-07-28: R 4.6.1 on noble; needed `bench` and `profvis`
  to verify a new skill's commands rather than assert them.)
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
  surfaced. (`Morrison-Lab/rme#1009`, several rounds: a background
  `renv::restore()` in `/tmp/rme-<issue>-worktree` sat at "renv installed,
  nothing else" after the worktree was removed and re-created at the same
  path — verified the actual chapter content instead via this gh-pages
  fetch, twice, once per structural fix.)
- **Plain git is a lighter route to the same PR-preview HTML, and the one to
  reach for when the page structure isn't known in advance.** The
  `get_file_contents` recipe above needs the exact path up front and returns
  that odd pre-decoded array; fetching the branch instead avoids both and lets
  you enumerate first:
  `git fetch --depth=1 origin gh-pages`, then
  `git ls-tree --name-only FETCH_HEAD:pr-preview/pr-<N>/` to see what the site
  actually built, then `git show FETCH_HEAD:pr-preview/pr-<N>/<page>.html`
  piped to `grep`. Nothing is written to the working tree, so it is safe to run
  from a repo checkout mid-task. **Sample every page type, not just
  `index.html`** --- a site can have `index`, `NEWS`, `reference`, `man/*`, and
  `vignettes/*` pages built by different code paths. Expect a `revealjs`
  vignette to legitimately lack website chrome (no Quarto sidebar, so no
  sidebar-related markup at all); confirm it is a slide deck with
  `grep -c 'class="reveal"'` rather than recording it as a gap.
  Match that exact string, not `reveal` or `revealjs`: on one `bcs` article
  built both ways, the non-deck page still hit `reveal` 3 times (the word
  "revealed" in prose) and `revealjs` once (a code listing quoting the format
  key), while `class="reveal"` scored 1 on the deck and 0 on the page.
- **When verifying that a `$VAR`-style placeholder actually resolved in built
  HTML, a grep for the literal variable name false-positives on your own
  changelog prose.** A `NEWS.md` entry that *describes* the migration in a
  backticked span renders into `NEWS.html` as `<code>$ALTDOC_SIDEBAR_FOLD</code>`
  --- indistinguishable from an unresolved placeholder if you only count
  matches. Check the surrounding tags before concluding: a genuinely unresolved
  variable appears as a header include path, not wrapped in `<code>` in body
  text. Cost time twice on the same migration, once per repo, because the
  second occurrence looked like confirmation of the first.
  (`ucdavis/bcs#528`, `UCD-SERG/serocalculator#626`.)
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
  points. (`Morrison-Lab/rme#772`, tracked in `Morrison-Lab/rme#994` and `Morrison-Lab/rme#996`, fixed centrally in
  `Morrison-Lab/gha#241`.)
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
  `Morrison-Lab/altdoc@recursive-qmd-search`: a plain `curl` to
  `api.github.com/repos/Morrison-Lab/altdoc/...` 403'd with `"GitHub access to
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
  `Morrison-Lab/altdoc@recursive-qmd-search`; fixing the consumer's docs build
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
  `curl -L https://codeload.github.com/Morrison-Lab/snapr/tar.gz/refs/heads/main -o /tmp/snapr.tar.gz`
  then in R, install `readr` first (a direct `snapr` `Imports:` dependency):
  `install.packages("readr")`, then
  `install.packages("/tmp/snapr.tar.gz", repos=NULL, type="source")`.
  `snapr::expect_snapshot_data()` silently skips snapshot generation/comparison when
  `NOT_CRAN` is unset (respects the standard CRAN-skip convention):
  `NOT_CRAN=true Rscript -e 'devtools::test()'`.
- The `latex-macros` submodule (Morrison-Lab/macros) is uninitialized on a fresh
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
  **The missing package need not make the tests SKIP -- it can make them ERROR,
  and the prune is identical.**
  The bullet above reads as being about a skip (`vdiffr` absent, so the test
  stands down), which is the tidy case.
  An uninstalled Suggests dependency can instead make the owning tests error
  outright.
  Where the snapshot helper is reached `pkg::`-qualified, that is what happens:
  the namespace lookup fails before any assertion runs, so the test dies at its
  first snapshot call and the cleanup sees exactly the unexercised snapshots a
  skip would have left.
  The mechanism is the same whichever cause starts it -- an errored test never
  reaches its `expect_snapshot_*()` calls -- and here it arrives through the
  missing package rather than through contention.
  So neither a clean skip report nor a loud pile of errors tells you anything
  about your snapshots: check `git status` however the run ended.
  Recovery is unchanged, `git checkout -- tests/testthat/_snaps/`, and it must
  happen **before** staging -- the prunes are ordinary working-tree deletions
  that a bare `git add -A` stages silently, committing the removal of real
  snapshots as though the change had invalidated them.
  (`ucdavis/bcs#732`, measured 2026-08-23: a full-suite run with the `snapr`
  package uninstalled pruned committed `tests/testthat/_snaps/**/*.csv` files.
  How many it pruned was not recorded, so no count is given here.
  Every `.csv` snapshot in that suite is written by a
  `snapr::expect_snapshot_data()` call, so each owning test errored on the
  namespace lookup rather than skipping.
  A concrete instance of `memories/preferences.md`'s never-`git add -A` rule,
  in its less obvious direction -- the sweep stages a deletion rather than an
  unrelated edit.)
  - **Do:** run `git status --short` after any full-suite run in a sandbox
    missing Suggests packages, whether the run reported skips or errors.
  - **Don't:** stage with `git add -A` after such a run -- that commits the
    prune as an ordinary deletion.
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
  (`Morrison-Lab/altdoc#61`, 2026-07-25: two overlapping `test_local()` runs;
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
