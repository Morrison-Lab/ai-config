# GitHub Actions authoring

Generic Actions material: YAML authoring and the gotchas that bite any workflow.
Reusable-workflow catalog: [`gha-reusable-workflows.md`](gha-reusable-workflows.md).
The `@claude` bot's own behaviour lives in
[`claude-bot-workflows.md`](claude-bot-workflows.md).

## YAML authoring (GitHub Actions / workflow files)
- **Regex values with backslashes: prefer single-quoted YAML, but document both forms
  correctly.** YAML double-quoted scalars process escapes, so you must double each
  backslash there (e.g. `"foo\\.bar"` for a single literal backslash before `.`).
  Single-quoted scalars preserve backslashes as-is (e.g. `'foo\.bar'` for that same
  single backslash), which is usually easier to reason about in workflow templates.
  This applies to `branches-or-tags-to-list` / regex inputs in reusable-workflow YAML.
  (d-morrison/altdoc#30.)
- **YAML scalar escaping in composite action metadata:** Output descriptions in `action.yml`
  (and workflow inputs) containing single quotes inside single-quoted strings (e.g.
  `'description: 'true' if head repo...'`) fail strict YAML parsing in GitHub Actions unless
  block scalars `>-` or proper escaping are used. (Morrison-Lab/gha#482.)
- **Script injection prevention in inline shell scripts:** Never expand context outputs directly
  in bash `run:` text via `${{ steps.*.outputs.* }}`. Always map context values into step `env:`
  variables (`env: PR_BRANCH: ${{ steps.pr-info.outputs.branch }}`) and reference them as shell
  variables (`"$PR_BRANCH"`) inside inline scripts to prevent script injection vulnerabilities.
  (Morrison-Lab/gha#482.)

## GitHub Actions workflow authoring gotchas

- **`${{ env.PATH }}` evaluates to an empty string in step `env:` context.**
  Setting `env: PATH: ${{ github.workspace }}/bin:${{ env.PATH }}` in Actions
  step context overwrites `PATH` with only that directory (dropping
  `/usr/bin`, `/bin`, etc.), causing `command not found` (exit code 127).
  Use `echo "${GITHUB_WORKSPACE}/bin" >> "$GITHUB_PATH"` in a setup step to
  safely prepend to `PATH` while preserving system directories.
- **A bare `devtools::test()` in a gating CI step never fails the job.**
  `devtools::test()`'s signature sets `stop_on_failure = FALSE` and forwards
  it to `testthat::test_local()` — overriding `test_local()`'s own `TRUE`
  default (verified in `r-lib/devtools` `R/test.R`) — so under
  `shell: Rscript {0}` the step exits 0 even when tests fail. Pass
  `stop_on_failure = TRUE` explicitly in any step whose purpose is to gate.
  (gha#272: `update-snapshots.yml`'s post-`snapshot_accept()` verification
  re-run shipped this way for the capability's whole released life — a
  still-failing suite exited 0 and the broken snapshots were committed and
  pushed anyway; surfaced only when the new reference page's description of
  the gate was fact-checked against the implementation in review.)
- **`GITHUB_TOKEN`-driven pushes create no workflow runs — except on PRs,
  where the runs now appear in an approval-required state instead of not at
  all.** The long-standing no-retrigger rule has a github.com-live exception
  for `pull_request` `opened`/`synchronize`/`reopened`: when a workflow's
  `GITHUB_TOKEN` creates or updates a PR, the resulting runs are created
  approval-required, and a write-access user starts them via "Approve
  workflows to run" in the PR merge box. A `GITHUB_TOKEN` push to a plain
  branch still triggers nothing. (Verified via the `github/docs` source:
  `data/reusables/actions/actions-do-not-trigger-workflows.md`, gated by
  `data/features/actions-github-token-pull-request-approval.yml` with
  `fpt: '*'` and `ghec: '*'` (GHES commented out). Used on gha#272's
  update-snapshots reference page.)
- **Local composite refs (`./`) in reusable workflows resolve relative to the HOST repo.**
  A `workflow_call` reusable workflow living in gha cannot call `./path/to/composite` from
  a CALLER's repo — `./` always resolves to gha itself. Workaround: pass the data the
  composite would have consumed as a plain input (e.g. an `apt-packages` string). Learned
  while extracting `update-snapshots` (gha#103): bcs's `install-system-deps` composite
  couldn't be called; the package list was passed as a string input instead.
- **The inverse gotcha: `actions/checkout` (no explicit `repository:`) inside a
  `workflow_call` reusable workflow checks out the CALLER's repo, not the reusable
  workflow's own.** A `run:` step that then references a script by a
  `GITHUB_WORKSPACE`-relative path (e.g.
  `bash "${GITHUB_WORKSPACE}/.github/workflows/scripts/foo.sh"`) silently assumes the
  checked-out tree is the reusable workflow's own repo — true only when a repo calls its
  own workflow (dogfooding), false for every other consumer, which gets
  `No such file or directory`. A step inside `claude-code-review.yml` (the CALLEE) read
  `${{ github.workflow_ref }}` and it evaluated to
  `d-morrison/gha/.github/workflows/claude-review.yml@refs/pull/191/merge` — the
  CALLER's stub file (`claude-review.yml`), not the callee's own
  (`claude-code-review.yml`) — confirmed straight from the job's log output (gha#191,
  run 28628848306, job 84901231352, the `selfmod` step's `WORKFLOW_REF` env dump). This
  contradicts a naive reading of GitHub's docs (which describe `workflow_ref` simply as
  "the ref path to the [running] workflow" without spelling out the reusable-workflow
  case), so trust the log evidence over the doc summary if they seem to disagree.
  (d-morrison/gha#190/#191: `claude-code-review.yml`'s fail-check guard broke
  for every consumer after its logic was extracted from inline shell into a standalone
  script, landing right after the last known-good run.)
  **`github.job_workflow_ref` is NOT a reliable fix for this — correcting an earlier
  entry here that claimed otherwise.** #191's fix resolved the callee's own repo/ref via
  `github.job_workflow_ref`, parsed it, and checked that ref out into a side directory
  before running the script; at the time this looked "empirically verified" because the
  CI job went green afterward. It wasn't: on real consumer runs (a genuinely fresh
  `pull_request: reopened` event on a cross-repo consumer, well after the tag moved to
  the fix commit) `github.job_workflow_ref` evaluated to an **empty string** at that call
  site, crashing the step with a bare `usage: ...` error (gha#196). The earlier "green CI
  = confirmed working" inference was wrong — the green run just hadn't exercised the
  cross-repo path yet. A second, independent investigation (gha#194, a same-repo
  dogfooding failure on `d-morrison/gha` reviewing its own PR) found a documented
  explanation: per [github/community discussions #31054](https://github.com/orgs/community/discussions/31054)
  and [github/community discussions #45342](https://github.com/orgs/community/discussions/45342),
  `github.job_workflow_ref` is a **known no-op for a SAME-repository**
  reusable-workflow call — it only reliably populates for a genuine cross-repo
  `owner/repo/...@ref` call. That explains the same-repo dogfooding failure cleanly, but
  doesn't fully explain gha#196's original *cross-repo* failure (`Lacaedemon/sparta`
  calling `d-morrison/gha`) — so treat "populates correctly for cross-repo, no-op for
  same-repo" as the documented claim, not as fully reconciled with every observed
  failure; don't re-litigate it, just don't rely on the value being non-empty in ANY
  case. **The robust fix:** don't resolve-and-checkout at all — move the logic into a
  composite action and reference its own files via `${{ github.action_path }}`. A
  composite action's own files are always reachable through `github.action_path`
  regardless of how the calling reusable workflow was invoked (`workflow_call`, a
  re-dispatched `workflow_dispatch`, automatic `pull_request`, same-repo or cross-repo),
  with no conditional branching on `job_workflow_ref` needed. (d-morrison/gha#197,
  `.github/actions/run-review-guard/`.)
  **The checkout half of this recurred in a brand-new reusable workflow, not
  an existing one that broke in production.** A `workflow_call` reusable
  workflow's own job step -- not a nested composite -- assumed the same
  thing: `version-check.yml`'s "Compare versions" step ran
  `Rscript working/.github/workflows/scripts/check-dev-version.R` straight
  after `actions/checkout` steps with no `repository:` input, so the script
  path would never exist on any real consumer's checkout, since those
  checkouts are the CALLER's repo, never gha's own.
  Caught by self-review before merge rather than by a live consumer
  failure, and fixed the same way: route through the already-built
  `check-dev-version` composite
  instead of hand-rolling the `Rscript` call, so the script resolves via
  `github.action_path` regardless of what `workflow_call` checked out.
  (Morrison-Lab/gha#390, 2026-07-31.)
- **A fix that's only unit-tested against the extracted logic in isolation, never against
  the actual `uses:` invocation, can ship a broken integration point undetected.** #191's
  own test (`parse-workflow-ref/tests/run-tests.sh`) fed hardcoded ref strings straight to
  the sed-parsing script and proved the parsing logic correct — but never exercised
  whether GitHub actually populates `github.job_workflow_ref` with a non-empty value at
  the real call site, so the regression above (gha#196) shipped and went undetected until
  a live consumer run hit it. The fix (gha#197) closed this gap by adding a selftest step
  that invokes the new composite action itself via a real `uses: ./.github/actions/<name>`
  step against a canned fixture — the same category of gap `sync-with-main.md`'s "derived
  artifacts" and "extracted copy" entries describe, but for a composite action's runtime
  resolution specifically rather than a checked-out script's content.
- **A nested `uses: ./...` composite-action reference INSIDE another composite action
  resolves against `$GITHUB_WORKSPACE` (the top-level workflow's own checkout), not
  against the repo the enclosing composite was itself fetched from -- a distinct failure
  mode from the `job_workflow_ref` case just above, but the same underlying lesson.**
  Confirmed via [`actions/runner#1348`](https://github.com/actions/runner/issues/1348)
  ("Local composite actions always relative to top level repository"). Extracting a new
  shared composite (e.g. a base-URL-derivation helper) and having two sibling composites
  reach it via a local `uses: ./.github/actions/<new-composite>` step looks correct and
  even passes selftest when the selftest job happens to check out the same repo the
  composite lives in (masking the bug) -- but breaks for every real consumer, whose own
  checkout doesn't contain that path. I stated the opposite claim confidently in a code
  comment ("a same-repo local path resolves against the repository this action was
  fetched from") before a later review round caught it -- a wrong belief stated as fact,
  not just a missed check. **Fix: reach the sibling composite's script directly via
  `${{ github.action_path }}/../other-composite/script.py`, never via a nested `uses:`**
  -- `github.action_path` is correct regardless of caller context, the same principle
  #197 (above) established for `job_workflow_ref`. (d-morrison/gha#284, rounds 1-3 fixed
  other genuine bugs first; this one wasn't caught until round 4.)
- **An unrelated open PR can independently patch the same root cause as an incidental,
  second commit — without ever linking the issue — surfacing only as a merge conflict
  after your own fix lands.** `post-merge`'s cascade-conflict-scan step (1.5) is what
  catches this, not `check-history` or issue cross-referencing: neither would have
  flagged it, since the other PR (gha#194, primarily a `gh`-subcommand-allowlist fix)
  never mentioned or linked the job_workflow_ref issue it happened to also patch as a
  bundled "second, unrelated fix" commit. When resolving the resulting conflict, prefer
  the more general/robust fix over a narrower band-aid patching the same symptom (here:
  keep the composite-action fix, drop the other PR's `if: job_workflow_ref != ''`
  same-repo-only conditional and its now-inaccurate changelog fragment describing a fix
  that no longer ships) — and explain the resolution and why in a PR comment, since it's
  discarding another author's already-committed work.
- **`secrets: inherit` is NOT needed when the reusable workflow only uses `github.token`.**
  `github.token` auto-injects the caller's token via `permissions:` — not via `secrets:`.
  `secrets: inherit` is only needed for named secrets (`secrets.MY_PAT`, etc.). Automated
  reviewers (claude-bot, Copilot) routinely flag this as a false positive — rebut it by
  confirming the callee has no `secrets:` inputs.
- **A reusable workflow's job permissions are checked against the caller's grant at
  graph-build time — `if:`-skipped jobs are NOT exempt.** A called workflow's job that
  declares `permissions: contents: write` makes the WHOLE call fail with
  `startup_failure` (instant, <1s, no jobs created) if the caller grants only
  `contents: read` — even when that job has `if: inputs.deploy` evaluating false and
  never runs. Consequence: you canNOT offer a "deploy: false ⇒ caller needs only read"
  optimization in a reusable workflow whose deploy job statically requests write; the
  caller must grant write regardless. Keep the read-only work in a separate
  `contents: read` build job (it downscopes its own token), but the caller still grants
  the union (write). Cost me two red CI rounds on gha#118. To debug a `startup_failure`
  with `total_jobs: 0`: it's a graph/permission/parse error, not a runtime one — check
  the called workflow's permission ceilings first.
- **An OMITTED key in a caller's explicit `permissions:` block defaults to `none`, not
  "inherit" — so the caller must enumerate EVERY permission the callee's jobs request.**
  Same `startup_failure` failure mode as above, but the trap is silence: gha's
  `claude-code-review.yml@v1` job requests `actions: read` (for the `github_ci` MCP
  server), and ai-config's caller granted `contents`/`pull-requests`/`issues`/`id-token`
  but never listed `actions` — which then defaulted to `none`, so every review run died
  at `startup_failure` (`The nested job is requesting actions: read, but is only allowed
  actions: none`) and no review ever posted. When wiring a caller stub for a gha reusable
  workflow, copy the `permissions:` block from the matching `examples/<name>.yml` verbatim
  rather than hand-picking keys, and re-diff against it when the stub drifts. (ai-config#224.)
- **Detached HEAD on `pull_request` events.** `actions/checkout` without an explicit `ref`
  on a PR event checks out a synthetic merge commit in detached HEAD — `git push` then
  fails. Fix: pass `ref: ${{ github.head_ref }}` so the branch name is checked out, not the
  merge commit SHA. Required for any reusable workflow that needs to `git push` from a PR
  caller.
- **`always()` + optional upstream job needs an explicit result guard.** The pattern
  `if: ${{ always() && !cancelled() && needs.X.result == 'success' }}` keeps the job
  running when X is *skipped* (non-PR events), but also lets it run when X *fails* —
  causing noise from a job that depended on work that didn't land. Full guard:
  `(needs.X.result == 'success' || needs.X.result == 'skipped')`. (Fixed in bcs#226.)
- **The same `always()` gap exists one level down: a STEP gated `if: always()` that
  reads `env: FOO: ${{ steps.earlier.outputs.bar }}` still runs -- with `FOO` empty --
  if `earlier` failed, not just when an upstream JOB failed.** `always()` on a step
  means "run regardless of prior step outcome," so an earlier step's failure to
  write its output (script errored before the `>> "$GITHUB_OUTPUT"` line) silently
  hands the later step an empty string, not a skip. If that empty value feeds a
  command with real effects (a `--ref ""` on `gh workflow run`, a `--branch ""` on
  some other CLI), the failure mode ranges from a confusing CLI error to a
  misdirected action, not a clean no-op. Guard explicitly: `if [ -z "$FOO" ]; then
  echo "::warning::..."; else <the real command>; fi` -- don't assume the value is
  always populated just because the step that sets it "should" have run first.
  (gha#286, Copilot review finding: three `always()`-gated steps in `claude.yml`
  read `PR_BRANCH: ${{ steps.pr_checkout.outputs.branch }}` for a `gh workflow run
  --ref "$PR_BRANCH"` call, unguarded against `pr_checkout` having failed.)
- **Canonical GitHub privacy-safe noreply email is `<numeric-id>+<username>@users.noreply.github.com`.**
  The bare `<username>@users.noreply.github.com` is not privacy-safe and can match a real inbox.
  For `issue_comment` events, the actor's numeric ID is in `github.event.comment.user.id`:
  `committer-email: ${{ github.event.comment.user.id }}+${{ github.actor }}@users.noreply.github.com`.
- **The whole per-PR dev-version-bump chore below is obsolete once a repo
  adopts `Morrison-Lab/gha`'s new `bump-dev-version`/`version-check`
  capabilities (gha#390, tracking gha#388).** Those replace the "bump
  `DESCRIPTION` above `main`, re-bump after every merge" convention with an
  auto-bump-on-`main`-merge workflow plus an inverted `version-check` that
  fails a PR if it touches `Version:` at all --- so once a repo migrates,
  every bullet below about bumping, re-bumping, or the `no version increment`
  label bypass no longer applies to that repo. Not deleted here because most
  repos (bcs, serocalculator, serodynamics included) haven't migrated yet;
  check whether the repo in front of you has adopted the new workflow before
  following this chore.
- **Both bcs PR gates have a label bypass for non-user-visible changes.** `version-check`
  (`version-check.yaml`, derived from RMI-PACTA's R-semver-check) does a pure version
  comparison and fails if the PR branch version ≤ main's, **but** it skips when the
  `no version increment` label is present. The changelog check (`news.yaml` ->
  gha `check-news.yml`) skips with the `no changelog` label. Both workflows trigger on
  `labeled`/`unlabeled`, so adding the labels re-runs and clears them with no push. For a
  CI-only / workflow-only PR (no user-visible R-package change), apply **both** labels
  rather than bumping `DESCRIPTION` and editing `NEWS.md`. (Verified on ucdavis/bcs#236 —
  corrects an earlier note that claimed `version-check` had no bypass.)
- **That bypass is per-repo, not a property of the shared workflow.**
  `UCD-SERG/serocalculator`'s `version-check.yaml` gates every later step on a
  `check_label` step reading `no version increment`, and bcs has the bypass per the
  note above (its mechanism not checked here).
  `UCD-SERG/serodynamics`'s copy of the same RMI-PACTA-derived workflow has no
  such step at all, so its `stopifnot(working_version > compare_version)` is
  unconditional and a CI-only PR there **must** bump `DESCRIPTION`.
  The files look alike enough that the difference is easy to miss, so run
  `grep -c check_label .github/workflows/version-check.yaml` in the repo you are
  actually in before reaching for the label.
- **A workflow-only PR is the one that forgets the bump**, because nothing in the
  diff is about the package.
  The familiar failure is main advancing past you into parity; this one never
  bumps at all, so the branch sits at parity from its first commit and
  `version-check` goes red on a diff containing no R code.
  Compare `grep ^Version DESCRIPTION` against
  `git show origin/main:DESCRIPTION | grep ^Version` before pushing, whatever the
  diff contains.
  (2026-07-31: `serodynamics#282` and `serocalculator#627`, both
  `.github/workflows/`-only, both red for this reason.)
- **bcs `docs` build (altdoc) EXECUTES the rendered man-page examples.** altdoc
  renders each `man/*.Rd` to a `man/*.qmd` and runs the example chunk, so
  `@examplesIf FALSE` does NOT protect an example — the code still runs and a
  data-dependent call fails the `docs` job (`object 'pt_a' not found`). For any
  example that needs the protected/real cohort, use `\dontrun{}` (altdoc renders
  it without evaluating), matching the existing convention (e.g.
  `R/calc_ip_weights.R`). Runnable examples with self-contained synthetic data
  are fine and do execute. (Hit on ucdavis/bcs#238.)
- **altdoc's `$ALTDOC_MAN_BLOCK` sidebar placeholder is grouped and
  internal-aware as of 2026-07; the hand-authored workaround it used to need
  is retired.** It formerly flat-listed every `man/*.Rd` under one ungrouped
  "Reference" section with `@keywords internal` topics included, which is why
  consuming repos hand-wrote `section:`/`contents:` entries pointing at
  `man/<topic>.qmd` in `altdoc/quarto_website.yml` (`UCD-SERG/serocalculator#575`).
  altdoc now reads an `altdoc/reference.yml` and builds BOTH surfaces from it
  --- the reference index page and the sidebar --- so the grouping is declared
  once and there is nothing left to keep in step. `.select_topics()` aborts the
  render on a topic name with no backing `.Rd`, and warns by name for any
  exported topic no section claims while dropping it into a trailing `Other`
  section; an internal topic is excluded unless explicitly named, and naming it
  opts it back in. `sidebar_labels: name-and-title` prefixes each entry with the
  function name --- titles alone are genuinely ambiguous in practice, e.g.
  serocalculator's `as_pop_data`/`load_pop_data` rendered as two adjacent
  identical lines. Migrating off the hand-written pair is a net deletion: drop
  `altdoc/reference.qmd`, replace the `Reference` block in
  `quarto_website.yml` with `$ALTDOC_MAN_BLOCK`, and move the grouping into
  `reference.yml`. Verify by generating the index from the new config and
  diffing section names, topic order, and count against the deleted
  `reference.qmd` --- eyeballing the built site will not catch a reordering.
  (`UCD-SERG/serocalculator#625`.)
- **A vendored copy of a docs feature drifts within days --- prefer altdoc's
  own `$ALTDOC_*` variable, and remember `sidebar_fold` sets the fold control's
  starting state without creating the control.** The sidebar-fold button began
  as a hand-written `altdoc/sidebar-fold.html` plus a matching `styles.css`
  block copied into two repos; within a week one repo had changed its copy to
  start folded and the other never heard about it. altdoc now ships it:
  `include-in-header: $ALTDOC_SIDEBAR_FOLD` under `format: html:` stages the
  snippet into `_quarto/` at render time with script and style in one file.
  The starting state is separate --- `sidebar_fold` in `altdoc/reference.yml`,
  valid values `expanded` (the default) and `collapsed`. **Omitting it on a
  repo that previously started folded silently reverts to open**: the site
  renders fine and nothing warns, so a repo carrying non-default behavior must
  set it explicitly during the migration. `check_altdoc()` reports a
  `sidebar_fold` set with no settings file referencing `$ALTDOC_SIDEBAR_FOLD`
  (and one set for a non-`quarto_website` generator), which is the check that
  catches the half-wired case --- but it is opt-in, so it will not fire during
  an ordinary `render_docs()`. An unrecognized `$ALTDOC_*` variable is left in
  the settings file verbatim rather than dropped, so pointing
  `include-in-header` at one before the altdoc pin supports it fails the Quarto
  build outright rather than degrading. (`d-morrison/altdoc#103`/`#104`,
  `ucdavis/bcs#528`, `UCD-SERG/serocalculator#626`.)
- **`NEWS.md` section headers need a blank line before them.** A bullet that ends
  immediately before a `## Next-section` heading (no blank line) can cause
  `utils::news()` to misparse adjacent sections. Always leave one blank line
  between the last bullet of a section and the next `##` heading. (bcs#275:
  `## Internal` bullet → `## Tests` with no blank line; bot caught it.)
- **`merge_group:` trigger — guard PR-context workflows at the job level.**
  When adding `merge_group:` to a workflow's `on:` block so the GitHub merge
  queue fires CI checks, any job that uses `github.event.pull_request.*`
  context needs `if: github.event_name == 'pull_request'` at the job level —
  otherwise the job errors on merge-group commits where that context is absent.
  A job with a false `if:` counts as skipped (passing) for branch-protection
  purposes. Also update matrix-selection shell conditions that branch on
  `pull_request` to cover `merge_group` too (use release-only matrix for both).
  Affected jobs in bcs: `version-check`, `news`, `lint-changed-files`, and the
  `R-CMD-check` matrix selector. (bcs#275.)
- **bcs `test-coverage` (codecov) is NOT a required check.** A coverage drop
  leaves the PR `mergeable_state: unstable` (not `blocked`) and does not block
  the merge — `docs`, `version-check`, the R-CMD-check matrix, lint, and
  spellcheck are the required ones. So a PR that adds integration code only
  exercisable against protected data (which inherently lowers coverage) can
  still merge once the required checks are green. (Verified merging #238.)
- **During a long review, re-bump `DESCRIPTION` after every `main` merge.**
  `version-check` compares the PR version to *current* main; if main advances
  (another PR bumps `0.0.0.905x`) and you merge main in, the PR's version is no
  longer strictly greater and version-check flips to failing even though it
  passed before. Bump again (e.g. `9057` -> `9058`). (Hit on #238 after main
  moved to 9057.)
- **bcs object-name lint (`.lintr.R` custom `snake_case_ACROs1` rex regex)**
  rejected study/protocol codes like `ab507bs` (a lowercase segment with letters
  *after* digits) until the lowercase branch was widened to
  `some_of(lower), zero_or_more(one_of(lower, digit))`. As of #238 such
  alphanumeric codes are valid name components; before that they failed
  `lint-changed-files` with `object_name_linter`.
- **Sync vignette captions with R-source axis labels after a label fix.**
  A `plot_*()` function's y-axis label and its vignette figure caption often
  carry the same phrase. Changing the axis label in the R source without
  updating the caption leaves a stale inconsistency that the next review round
  will catch. After fixing an axis label, grep the vignette:
  `grep -r "old phrase" vignettes/` to find and update matching captions.
  (bcs#253 round 3.)
- **Check the column's scale before writing an axis label.**
  A `prep_*()` column computed as `mean(...) * 100` is a 0–100 percentage;
  the axis label must say `%`, not `"Probability of …"` (which implies 0–1).
  Inspect the prep function's body or roxygen `@returns` to confirm the scale.
  (bcs#253: `pct_annual` was 0–100, not 0–1 — label was wrong.)
- **Use `geom_point() + geom_errorbar()` for data with a meaningful non-zero minimum.**
  `geom_col()` draws bars from 0; for enrollment-age data (40–70+) this wastes
  most of the chart area and makes ±SD intervals visually tiny. Use
  `geom_point(size = 3) + geom_errorbar(...)` when 0 is not a meaningful
  reference point. (bcs#253: `plot_results_baseline` switch from `geom_col`.)
- **Use `helper-*.R` for shared testthat setup.**
  testthat 3 auto-sources `tests/testthat/helper-*.R` before any tests run.
  Put shared setup (e.g. `make_pt_data()`) in a `helper-*.R` rather than
  repeating it across test files. One test file per source file is the bcs
  convention — `test-plot_fn.R` for `R/plot_fn.R`. (bcs#253.)
- **A push can trigger ZERO check-runs on a `pull_request`-triggered workflow — not a
  quota skip, not an error, just total silence.** Symptom: `gh pr checks <N>` shows
  stale/old results or "no checks reported"; `gh api repos/<o>/<r>/commits/<sha>/check-runs`
  (the new commit's SHA) returns an **empty** `check_runs` array — confirms literally
  nothing was dispatched for that push, distinct from a job that ran and failed/skipped.
  `gh run list --branch <branch>` likewise shows no new run after the push timestamp.
  This hit on an otherwise-healthy repo (sparta) mid-ARDI: a normal `git push` to an
  open PR's branch produced no CI activity for 15+ minutes. Recovery — manually dispatch
  every required workflow rather than waiting longer or re-pushing (a re-push doesn't
  reliably fix it either): for any `workflow_dispatch`-enabled workflow keyed off the
  branch, `gh workflow run <file>.yml --ref <branch>`; for a PR-number-keyed review
  workflow (e.g. `claude-code-review.yml` with a `pr_number` input — see the
  `workflow_dispatch` re-trigger pattern above), `gh workflow run <file>.yml -f
  pr_number=<N>`. Poll the dispatched run's own ID (`gh run view <id> --json
  status,conclusion`), not the (still-empty) push-event check list. If a workflow has
  no `workflow_dispatch` trigger, that one specific check stays stuck — note it and ask
  the user rather than silently treating the PR as green without it.
- **`workflow_call` input `default:` must be a static literal — it cannot reference
  `${{ ... }}` expressions.** A reusable workflow's `inputs.<name>.default` is parsed
  before any context is available, so an input can't default straight to
  `${{ github.event_name == 'pull_request' && ... }}` (or any other expression) to
  mirror an existing composite/job heuristic. Use a sentinel default instead (e.g.
  `'auto'`) and resolve the real expression where the input is consumed (a `with:`/`env:`
  value or a step), treating `'auto'` as "apply the heuristic" while `'true'`/`'false'`
  are explicit overrides. (gha#148: `test-coverage.yml`'s `fail-ci-if-error` input.)
- **A composite action `action.yml` input default overrides shell script fallback logic, so default to empty string `''` when delegating ref/branch resolution to a helper script.**
  If `action.yml` specifies `default: 'HEAD'`, passing it via `env: TARGET_REF: ${{ inputs.target-ref }}` to a script using `${1:-$DEFAULT_REF}` always passes `"HEAD"`, bypassing fallback chains (`origin/main` -> `main` -> `HEAD`) needed on PR checkouts. Defaulting `target-ref: ''` in `action.yml` allows the helper script to apply its fallback resolution dynamically when unsupplied. (gha#512: `check-tag-drift` composite action.)
- **A numeric version check in shell should validate that the parsed version string is numeric (`^[0-9]+$`) before evaluating `-lt` or `-gt`.**
  Inside an `if [ "$NODE_MAJOR" -lt 18 ]; then ... fi` condition block, if `NODE_MAJOR` is non-numeric (e.g. unparseable output or empty string), `[` returns exit status 2.
  Because `[` is evaluated as the condition of an `if` statement, `set -e` does not abort on failure;
  instead, bash skips the `then` block and execution silently falls through to exit status 0 (passing the check).
  Validate `[[ "$NODE_MAJOR" =~ ^[0-9]+$ ]]` first and exit 1 on parse failures. (gha#283: `check-node-version.sh`.)
- **An `if:` that names a status-check function (`always` / `failure` /
  `cancelled`) replaces the default `success()`.**
  GitHub auto-applies `success()` when the condition has no such function
  (expressions docs, read 2026-08-26).
  The older claim that *any* explicit step `if:` discards that default is
  false ([ai-config#2307](https://github.com/Morrison-Lab/ai-config/issues/2307)).
  Keep writing `success() &&` so a later `failure()` copy cannot fail-open
  the step.
  The default condition on a step is `success()`, which is why a failing step
  normally ends a job's useful work.
  Adding `if: steps.guard.outputs.blocked != 'true'` does not discard that
  default, because it names no status-check function.
  A later `failure()` or `always()` on that same `if:` would override it,
  and a fail-closed output write is the second layer for the case the guard
  dies before writing.

  What makes a later `failure()` / `always()` copy hard to catch is that a
  fail-closed write usually **masks** it.
  A guard written to fail closed writes its output before exiting
  (`echo "blocked=true" >> "$GITHUB_OUTPUT"; exit 1`), and outputs are captured
  from failed steps too, so the condition happens to evaluate correctly.
  Every test passes, and the protection is entirely accidental --- it evaporates
  the moment the guard fails *before* reaching that write, which is exactly what
  a rate limit, a network error, or a `set -e` abort produces.
  That evaporate story is not true of a non-status `if:`: GitHub still
  auto-applies `success()`, so a failed guard already skips those steps.

  So spell out both halves: `if: success() && steps.guard.outputs.blocked != 'true'`.
  And prefer `!= 'true'` over `== 'false'` for the output test, because a guard
  gated on an event type is *skipped* on other events, and a skipped step's
  output is the empty string rather than `'false'`.

  - **Do:** include `success()` explicitly in any step condition that also reads
    a guard's output.
  - **Do:** treat a fail-closed output write as the second layer, and say so in
    the comment, so nobody later "simplifies" the condition on the strength of it.
  - **Don't:** rely on a non-zero exit alone to skip steps whose `if:`
    names `always()` or `failure()`.
  - **Don't:** infer from a passing test that the condition is right, when a
    fail-closed write could be doing the work instead.

  **The sibling failure, and the reason to keep the two apart.**
  gha#350 has the same *outcome* --- a guard's verdict never reaches the
  decision it was written to gate --- by the opposite route, and conflating
  them costs you the diagnosis:

  - **gha#350: the guard never ran.**
    `claude-code-review.yml`'s quota-exhaustion guard carried
    `if: steps.claude-review.outcome == 'success'`, and quota exhaustion is
    precisely what fails `claude-review`.
    So the guard was *skipped*, `quota_exhausted` was never written, and the
    resolve step read a literal `"skipped"` where the verdict belonged.
    Note what this rules out: adding `continue-on-error: true` to the watched
    step does **not** fix it, because `outcome` reports the status *before*
    `continue-on-error` is applied --- only `conclusion` reflects it.
    Nothing was swallowed; there was no output to swallow.
  - **Here: the older writeup said the guard ran, failed, and was ignored.**
    That diagnosis assumed the false lead; see #2307.
    Restore an explicit `success() &&` so a later `failure()` cannot
    fail-open the step, not because a non-status `if:` already did.

  So the diagnostic question differs.
  For #350 you ask "can this guard's own gate be true in the scenario it
  guards against?"; here you ask "does anything downstream still respect this
  guard's failure?"
  A fix aimed at the wrong one leaves the bug in place.

  (gha#357 round 5, self-caught while writing the comment that claimed the
  opposite: a ported fork/Dependabot guard in `gemini-code-review.yml` gated
  its checkout and review steps on the output alone.
  The #350 contrast above was itself corrected in review on ai-config#829,
  which is worth recording: the first draft attributed #350 to
  `continue-on-error`, the exact fix #350's own body lists under "Two things
  that look like fixes but are not".)

## Changelog section ordering in d-morrison/gha

- **The established order in `CHANGELOG.md` is: Added → Changed → Fixed → Security.**
  Match this when adding new `## [Unreleased]` entries or when resolving merge
  conflicts in the changelog. Caught in gha#134 review (Fixed appeared before Changed).

## A repo/org rename breaks Actions `uses:` refs -- and repointing the owner is not the fix

`d-morrison/gha` moved to `Morrison-Lab/gha` (2026-07-28), and the same shape
recurs for any renamed owner.
GitHub Actions does **not** follow repository-rename redirects when resolving a
`uses:` ref, so every caller naming the old owner fails at run preparation,
before any job starts.
Git and plain HTTP *do* follow the redirect, so clones, submodules, and raw
fetches keep working -- which is why the breakage looks selective and arrives
with no warning from the repo that moved.

Three things to know, in the order they bite.

- **A tag can RESOLVE while its own contents still name the old owner.**
  Repointing the caller's owner is not sufficient on its own.
  `Morrison-Lab/gha@v1` resolved fine as a tag, but that tag's
  `claude-code-review.yml:155` and `claude.yml:288` still called
  `d-morrison/gha/.github/actions/checkout-submodules@v1`, so both workflows
  failed identically after the "fix".
  Read what the pinned tag *contains* --
  `curl -sS https://raw.githubusercontent.com/<new-owner>/<repo>/<tag>/<path> | grep -n 'uses:'`
  -- rather than confirming only that the pin resolves.
  Where a `@v2` exists with updated internals the fix is owner **and** tag, and
  a major bump means checking each caller's inputs against the new
  `workflow_call` signature instead of swapping the string blind.
- **A workflow run that completes as `failure` with ZERO jobs is the signature
  of an unresolvable reusable-workflow ref**, not a real test failure.
  `get_job_logs` with `failed_only: true` answers "no failed jobs found"
  because no job was ever created.
  This is the same zero-job shape as the `startup_failure` permission error
  documented earlier in this file, so the two are told apart by cause rather
  than by appearance: check the ref's owner and tag before the permission
  ceilings when a repo has just been renamed.
  The *action*-level case looks different and names itself -- a job that does
  start, then dies in ~3s with
  `##[error]Unable to resolve action. Repository not found: <old-owner>/<repo>`.
- **Sweep by grep, and re-grep after every fix.**
  A partial rename leaves the repo worse off than before, because the workflows
  that do run make it look repaired.
  `git grep "<old-owner>/<repo>" -- .github/` returning nothing is the check; a
  memory of which files you edited is not.

Before any blanket find-and-replace, establish **which** repos actually moved --
see `github.md`'s note on `raw.githubusercontent.com` following rename
redirects, which is the probe that answers it.
In the ucdavis/bcs sweep exactly two of nine `d-morrison/*` references had
moved, so a blanket replace would have broken the other seven.
Historical references in a changelog are a separate case: they record what was
true when written, so leave them alone.

(ucdavis/bcs#451/#453, 2026-07-28.
The first fix repointed all 15 `uses:` refs but kept `@v1`, and `claude-review`
went on failing in 3 seconds with the action-level error above.)

## A marker an action writes into consumer repos is a wire format, not a label

An action that edits a consumer's file often leaves a marker behind so a later
run can find its own block again.
That string looks like a comment, so renaming it looks like a docs change.
It is closer to a serialization format: the copies already sitting in consumer
repos were written by an older release, and the new release has to keep
reading them.

The failure is silent and lands downstream.
The consumer's next docs build does not error --- the read simply fails to
match, the action concludes it has never run on that file, and it appends a
second copy of whatever it generates beside the first.
Nothing in the action's own repo is wrong at that point, and its tests pass,
because every fixture was written by the current release.

Two properties turn the rename from awkward into breaking, and both are worth
checking before touching such a string:

- **The match is exact.** `if line.strip() == GENERATED_MARKER` admits no
  drift, so one character is as fatal as a full rename.
- **The marker is often the *only* anchor left.** Where the generator's first
  run consumes the human-written anchor it keyed on --- replacing a
  `- text: Versions` line with a rendered version label --- the fallback path
  cannot fire on a file the action has already rewritten.
  A rename therefore strands exactly the population it was safe to ignore in
  testing: the already-migrated ones.

So treat the old spelling as input the code must keep accepting.
Read every historical spelling, write only the current one, and cover the old
one with a regression test built from a pre-change fixture:

```python
GENERATED_MARKER = "# Generated by <action> (<new-owner>/<repo>); ..."
_LEGACY_GENERATED_MARKERS = ("# Generated by <action> (<old-owner>/<repo>); ...",)

def _is_generated_marker(line):
    stripped = line.strip()
    return stripped == GENERATED_MARKER or stripped in _LEGACY_GENERATED_MARKERS
```

The same reasoning covers any identifier an action leaves in someone else's
tree: a branch name it looks up, a PR-body sentinel it greps for, a label it
filters on, a cache key.
An org rename is the likeliest trigger, since a bulk find-and-replace reaches
all of them at once and none of them announce that they are read back.
(Morrison-Lab/gha#374, 2026-07-29: `generate-altdoc-version-dropdown`'s
`GENERATED_MARKER` carried the pre-move owner into every consumer's navbar
config.
Renaming it alone would have stacked a second version dropdown on each one at
their next docs build.
The regression test was verified to fail against the pre-fix code ---
`find_versions_entry` returned `None`, so the caller raised `TypeError` ---
rather than merely added.)

## An action that hard-gates on the event name can still be driven from another event

A third-party action can refuse every event but the one it was written for,
before it reads any of its own inputs:

```js
// sanjay3290/jules-pr-reviewer, src/index.ts:37 (at the pinned SHA)
if (ctx.eventName !== 'pull_request') {
  core.setFailed(`Unsupported event: ${ctx.eventName}. Use on: pull_request.`);
  return;
}
```

That reads like a hard constraint on the trigger, and it usually gets treated
as one: the obvious conclusions are "this capability cannot be made
on-demand" or "fork the action".
Neither is necessary.
`@actions/github`'s `Context` hydrates itself entirely from environment
variables, so both halves of the gate are caller-supplied:

```js
if (process.env.GITHUB_EVENT_PATH) {
  if (existsSync(process.env.GITHUB_EVENT_PATH)) {
    this.payload = JSON.parse(readFileSync(process.env.GITHUB_EVENT_PATH, ...));
  }
}
this.eventName = process.env.GITHUB_EVENT_NAME;
```

Step-level `env:` on a `uses:` step does **not** override those.
GitHub documents `GITHUB_*` as reserved
(https://docs.github.com/en/actions/reference/workflows-and-actions/variables,
checked 2026-08-26):
"You can't overwrite the value of the default environment variables named
`GITHUB_*` and `RUNNER_*`."
The runner still *prints* the YAML `env:` values in the step log, so the wrap
looks applied.
Measured 2026-08-26 on
[run 32942088643](https://github.com/Morrison-Lab/ai-config/actions/runs/32942088643):
the `uses: sanjay3290/jules-pr-reviewer` step logged
`GITHUB_EVENT_NAME: pull_request` and then failed with
`Unsupported event: issue_comment`.
That was the wrap #857 shipped, and every `@jules` mention since has failed
the same way (#2280).

The override that actually reaches `Context()` is `env(1)` on a `run:` step
that starts `node dist/index.js` as a child.
`env(1)` sets the child's environment after the runner's reserved-name merge.
A workflow triggered by `issue_comment` can still present the action with
`pull_request` this way.
For a `pull_request` gate the payload is close to one API call, because
`GET /repos/{owner}/{repo}/pulls/{n}` returns nearly the shape the event
delivers --- near enough to work, not near enough to skip the field check
below:

```yaml
      - name: Resolve the PR into a pull_request event payload
        run: |
          gh api "${{ github.event.issue.pull_request.url }}" \
            | jq '{pull_request: .}' > "$RUNNER_TEMP/pr_event.json"

      - name: Fetch the action at the pinned SHA
        run: |
          dest="$RUNNER_TEMP/the-action"
          git init --quiet "$dest"
          git -C "$dest" remote add origin https://github.com/owner/the-action.git
          git -C "$dest" fetch --depth 1 origin <sha>
          git -C "$dest" checkout --quiet --detach FETCH_HEAD

      - name: Run the action under a synthetic pull_request event
        env:
          INPUT_SOME_INPUT: value
          SYNTHETIC_EVENT_PATH: ${{ runner.temp }}/pr_event.json
          ACTION_DIR: ${{ runner.temp }}/the-action
        run: |
          env \
            GITHUB_EVENT_NAME=pull_request \
            GITHUB_EVENT_PATH="$SYNTHETIC_EVENT_PATH" \
            node "$ACTION_DIR/dist/index.js"
```

`action.yml` defaults are applied only by a `uses:` step.
A `run: node dist/index.js` invocation must set every `INPUT_*` the JS reads,
including the ones a `uses:` step would have inherited.

Two things make this safe rather than merely clever, and both need checking
before relying on it:

- **Read the action's own source for what it consumes past the gate**, and
  confirm the synthesized payload covers it.
  Everything after the gate in the case above read only the `pull_request`
  object, so nothing else had to be faked.
  A field the action reads and the API omits is the failure this check
  catches; `labels` was the near-miss, and it survived only because the action
  guards it as `(pr.labels || [])`.
- **`ctx.repo` is unaffected**, since it prefers `GITHUB_REPOSITORY`, which
  Actions always sets.

Note what the override does **not** change: the token's permissions, and the
security properties of the real trigger.
An `issue_comment` run executes in the base repo with a write token even for a
fork PR, so a gate the original event enforced implicitly (fork PRs get no
secrets under `pull_request`) has to be re-established explicitly.

- **Do:** read the pinned action's own code for how it reads `eventName` and
  `payload` before concluding its trigger is fixed --- `src/` for a legible
  version of the gate, and `dist/` to confirm what the pinned SHA actually
  runs, since the bundle is what Actions executes and it can lag `src/`.
- **Do:** invoke the action from a `run:` step with `env(1)` setting
  `GITHUB_EVENT_NAME` and `GITHUB_EVENT_PATH` on the node child, and set
  every `INPUT_*` the JS reads because `action.yml` defaults will not apply.
- **Do:** pin Node to the interpreter GitHub actually runs for that
  `runs.using`, not the label in `action.yml`.
  Measured 2026-08-26 on run 32942088643:
  this action declares `node20` and was forced onto Node 24.
- **Do:** write `success()` on wrap steps even though GitHub auto-applies
  it when `if:` has no status-check function.
  The could-not-start notifier uses `failure()`, which overrides that
  default, and a copy onto the node step would spawn node after a failed pin.
- **Do:** keep wrap preflight (`test -f` on the synthetic payload and the
  bundle) in its own step so a "could not start" comment can gate on it.
  Assertions left on the `jules` step fail before the process assigns
  `commentId`, and the notifier that excludes that step will not fire.
- **Do:** gate a wrap checker on the `node ... dist/index.js` invocation
  line, not a substring comments also contain.
- **Don't:** spawn `env` from Python without `shutil.which("env")`.
  Windows Python outside Git Bash has no `env` on PATH, so the call raises
  `FileNotFoundError` before the suite can print its tally, and local
  pre-commit goes red while ubuntu CI stays green.
- **Don't:** set `INPUT_RULES_FILE` to a path and then comment that the
  rules-file input is deliberately unused.
  The empty string is the documented disable value.
- **Do:** fetch a checker at the SHA the calling workflow **pins** when
  reproducing a diff-scoped CI gate locally, not the action's default branch.
  The first Do pins when *auditing* an action; the same applies when
  *running* one to validate a fix pre-push, where a shallow default-branch
  clone yields a plausible script with no sign it is the wrong one.
  Measured 2026-08-19: `ai-config`'s `validate.yml` pins
  `Morrison-Lab/gha/.github/workflows/check-new-line-breaks.yml@209bfb76`,
  whose `check-new-line-breaks.py` differs from that repo's default branch by
  **339 lines**, so validating against the default branch would have exercised
  a different checker and reported a result about nothing.
  Run `git fetch --depth 1 origin <sha>`, then `git diff --stat FETCH_HEAD --
  <subdir>/` (empty output means the pin is current) *before*
  `git checkout FETCH_HEAD -- <subdir>/`, which makes that question
  unanswerable.
- **Do:** re-derive any safety property the original event was providing for
  free, once the event is synthesized.
- **Don't:** fork an action, or abandon the feature, on the strength of an
  `eventName` guard alone.
- **Don't:** assume the API response is a drop-in payload without checking
  every field the action reads.
- **Don't:** treat a `uses:` step's logged `env:` as evidence the process
  received those values --- reserved `GITHUB_*` names are printed and then
  ignored.

(Morrison-Lab/ai-config#857, 2026-07-30: making the Jules reviewer on-demand
needed an `issue_comment` trigger, which its pinned action rejects outright.
Both files were read at the pinned SHA rather than assumed --- `src/index.ts`
for the gate quoted above, `dist/index.js` for the `Context` constructor that
makes the override work --- and then this PR's own API object, for field
coverage.
The line number above was `:38` when first written, and a review round caught
it: it is `:37`.
Worth noting how, since it is the cheap lesson here.
The reviewer inferred the citation was unverifiable because the case note named
only `dist/`, which was the wrong reason --- but a `grep -n` settled the real
question in one command, and the same off-by-one had already shipped into the
workflow comment that makes the same claim.
The wrap this case shipped --- YAML `env:` on the `uses:` step --- did not
work.
Measured 2026-08-26 on run 32942088643 / #2280: the step logged the override
and the action still saw `issue_comment`.
The working form is `env(1)` around `node dist/index.js`, recorded in
`.github/workflows/jules-review.yml` and gated by
`scripts/check-jules-review-workflow.py`.)

## A SHA pin on a reusable workflow freezes the caller, not what the caller runs

The bullet above says to fetch a checker at the SHA the calling workflow
**pins**, and names this repo's own
`Morrison-Lab/gha/.github/workflows/check-new-line-breaks.yml@209bfb76` as the
worked example.
That instruction is right about the danger it names --- a default-branch clone
is the wrong script --- and it is not sufficient, because a **reusable
workflow** is not a script.
It is a caller, and a pin freezes the caller's own text while saying nothing
about the refs that text resolves at run time.

The pinned workflow above delegated in turn to
`d-morrison/gha/check-new-line-breaks@v2`: a **floating tag**, in what was then
a different org, so neither the SHA nor the ownership boundary held.
Measured 2026-08-24, the two artifacts were 340 lines with four knobs and 637
lines with a clause-break rule on by default, and on one branch they gave
opposite verdicts --- exit 0 with no findings against exit 1 with 8.

What makes this worse than an ordinary stale read is that every check you would
run to catch a stale read passes.
The pinned artifact exists, it fetches at the named SHA, it is legible, and it
runs clean.
Nothing about it announces that it is not the thing CI executed, so reading it
to predict CI gives a confident wrong answer rather than an obviously missing
one.
This is
[`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md)'s
"one half of a mechanism for the whole" arriving through a pin, which is the
construct that exists to prevent exactly this.

**Follow the delegation chain to its end, and count the hops.**
A pin is worth what the *last* hop is worth, so one unpinned `uses:` anywhere
below it voids every pin above:

```bash
gh api "repos/<owner>/<repo>/contents/<path>/action.yml?ref=<sha>" \
  -H 'Accept: application/vnd.github.raw' | grep -n 'uses:'
```

Every ref that command prints must itself be a SHA.
A composite **action** whose steps nest no `uses:` at all is the terminal case,
and calling one directly is what makes a pin reach the script --- which is the
fix this repo took ([ai-config#2165](https://github.com/Morrison-Lab/ai-config/issues/2165)),
recorded in `.github/workflows/validate.yml`'s own `new-line-breaks` comment.

- **Do:** grep the pinned artifact for nested `uses:` before treating the pin
  as reaching the code, and require a SHA on every hop.
- **Do:** prefer pinning the composite action over the reusable workflow that
  wraps it, since removing the hop is what removes the question.
- **Don't:** read "I fetched it at the pinned SHA" as having read what runs ---
  that is true of the caller and says nothing about the callee.
- **Don't:** treat a cross-org boundary as adding safety here.
  It adds a second party who can move the tag.

## A job's step list identifies which version of a reusable workflow ran

The `referenced_workflows[].sha` field ([`gha-reusable-workflows.md`](gha-reusable-workflows.md))
answers "which commit did this
run resolve", and it is the right instrument when you have it.
A job's own **step list** answers the same question independently, from a
different endpoint, and needs no reasoning about re-run modes: `actions_get`
`get_workflow_job` returns the `steps` array, and the steps are whatever that
version of the workflow defines.

Prefer step **names** to a step **count**.
A count drifts with every step added; a name present in one version and absent
from the other keeps working.
For `Morrison-Lab/gha`'s `claude-code-review.yml`, measured against the tags
on 2026-07-31 with `git show v1:.github/workflows/claude-code-review.yml` and
the same for `v2`:

- **`@v1` only:** `Fail the check if the review did not complete` (unsuffixed).
- **`@v2` only:** `Fail the check if the review did not complete (attempt 1)`,
  `Fail the check if the retry also did not complete`,
  `Parse caller workflow ref`, `Install packages`,
  `Resolve and upload execution file path` (twice, one per attempt),
  `Retry Claude Code Review after a stub result`, `Sum attempt costs`, and
  `Resolve final review outcome`.

The fail-check name is the cheapest single tell: `@v1` has one such step,
`@v2` splits it into an attempt-1 step plus a retry counterpart.
Gross size is a usable first glance --- `@v1` defines 12 named steps against
`@v2`'s 25 --- but read a runtime count as approximate, since a job's `steps`
array also carries the runner's own setup and teardown entries and so will not
equal the file's named-step count.

- **Do:** key on a distinguishing step name when you need to know which
  version ran.
- **Do:** treat this as independent corroboration of
  `referenced_workflows[].sha`; two endpoints agreeing is a stronger answer
  than either alone.
- **Don't:** key on a raw step count without allowing for runner-injected
  steps and for the file's own step count changing between releases.

(2026-07-31: `Morrison-Lab/ai-config` review runs were diagnosed against
`@v2`'s behaviour while actually running `@v1`, which is what explained a
missing execution artifact --- see
[`claude-bot-workflows.md`](claude-bot-workflows.md).)

## Grepping a run log matches the echoed script, not its output

`gh run view <id> --log` prints each step's **script body** as well as that
step's output, so a grep for any string appearing in the command matches the
command.
The result is a false positive shaped exactly like verification: you searched
the log for the thing, and the log contains the thing.

The body is echoed **twice** for an inline shell step --- once in the
`##[group]Run <script>` header, and once immediately after, wrapped in colour
codes.

Measured on `Morrison-Lab/ai-config` run `31069525412` (`validate`), gh 2.92.0:
grepping that log for `check-context-closure.py` returns exactly **2** lines,
and **both are command echoes**.
**Zero** are output --- that step's real output reports a file and byte count
and never names the script.
So "I grepped the log and found it, therefore it ran" establishes only that the
workflow *contains* that step, not that it executed or what it printed.

The two echoes are not one per step: that run carries 25 `##[group]Run` headers
against 19 colour-wrapped bodies, because a step invoking an action gets the
header with no inline script to echo.

**The colour codes are a literal `^[` two-character sequence here, not a real
ESC byte, so the usual strip is a no-op.**
Counted across two runs in that repo, `31069525412` and `31062830292`: real
`0x1b` bytes number **0** in both, against **38** and **88** occurrences of a
literal `^[[`.
`sed 's/\x1b\[[0-9;]*m//g'` therefore removes nothing while appearing to work,
since most greps tolerate the noise --- an anchored pattern will not.

Filtering on the echo markers is sturdier than stripping colour at all:

```bash
gh run view <id> -R <owner>/<repo> --log \
  | grep -vE '##\[group\]Run |\^\[\[36;1m' \
  | grep -E "<pattern>"
```

On that run the filter takes the `check-context-closure.py` hit count from 2 to
**0**, correctly reporting that the name never appears in output.
Its negative control passes too: it removes exactly 44 of 1143 lines --- the
25 headers plus the 19 echoes --- and genuine output lines survive, so it is
not simply deleting everything.

**Do not filter with `grep -v 'echo "'`.**
That drops any real output line containing `echo "`, which includes a script
printing shell examples and any tool quoting a command back at you --- trading
a visible false positive for a silent false negative.
Excluding the two echo markers targets the mechanism instead of a string that
legitimately occurs in output.

- **Do:** exclude the `##[group]Run` header and the colour-wrapped script echo
  before concluding a log line is output.
- **Do:** settle which colour-code form a log actually carries with a byte
  count rather than by eye, before trusting any strip.
- **Don't:** read a grep hit on a script, flag, or message name as evidence
  that the step ran, or as evidence of what it printed.
- **Don't:** filter on `echo "`, which keys on a string that appears in real
  output.

(Verified 2026-08-06 on gh 2.92.0, with output piped to a file rather than to a
terminal.
Whether another gh version or a TTY emits real ESC bytes was **not** tested,
which is the reason to handle both forms rather than pick one.)

## Which ref a workflow runs from decides whether a trigger change takes effect before merge

Editing a workflow's `on:` block has different reach depending on which event
you are adding or removing, and the asymmetry is easy to state backwards.

- **`pull_request` runs from the PR's own head ref.**
  So *removing* a `pull_request` trigger takes effect on that branch
  immediately: the workflow simply stops running on the PR that removes it.
- **`issue_comment`, `push` on the default branch, `schedule`, and
  `workflow_dispatch` run from the default branch.**
  So *adding* one of those is inert until merge, however correct the file is.

A PR that swaps one for the other therefore half-works while it is open, and
saying which half is a claim worth testing rather than reasoning about.
`list_workflow_runs` filtered to the branch settles it: a run list that stops
at the pre-change commit is the removal having taken effect, and the absence
of a run for the new event is the addition being inert rather than broken.

- **Do:** state which half of a trigger swap is demonstrable on the PR and
  which cannot be, and name the check that will confirm the rest after merge.
- **Don't:** write that "the old trigger still applies to this PR" when the
  old trigger was `pull_request` --- the branch's own file is what runs.

(Morrison-Lab/ai-config#857, 2026-07-30: the PR body first claimed the old
`pull_request` trigger would still review the PR.
`list_workflow_runs` for that workflow on the branch returned exactly one run,
at the empty claim commit predating the change, and none for the
`ready_for_review` event the old file would have fired on.)

**The same head-ref rule governs the `uses:` line, not just the `on:` block,
so a pin-bump PR self-tests before it merges.**
A `pull_request`-triggered run reads the **caller** workflow file from the PR
branch, and that file is where the `uses: .../<workflow>.yml@<ref>` line
lives.
So a PR that changes a call from `@v1` to `@v2` exercises `@v2` in its own
pre-merge run, with no tag slide and no merge required.
That is the reverse of the reusable-workflow bootstrapping gap
[`gha-reusable-workflows.md`](gha-reusable-workflows.md) describes, and it is
worth knowing in both directions.

- **Do:** treat a pin-bump PR's own run as a real test of the new pin, and
  read its step list to confirm which version answered, per the section
  above.
- **Don't:** read a step list from such a run as evidence about what the
  **base** branch is pinned to --- the branch's own file is what ran.

(`Morrison-Lab/ai-config#998`, 2026-07-31: the PR repointing `claude-review`
from the frozen `@v1` to `@v2` showed `@v2`'s step shape on its own run before
merging.)

## A caller with no `concurrency:` block can still have its runs cancelled

Grepping a caller workflow for `concurrency` and finding nothing does not mean its runs are safe from cancellation.
The group can live in the **reusable workflow the caller invokes**, and then it governs every caller equally while appearing in none of them.

`Morrison-Lab/ai-config`'s `.github/workflows/claude-review.yml` is the worked case: no `concurrency:` block of its own, calling `Morrison-Lab/gha/.github/workflows/claude-code-review.yml@v2`, which carries

```yaml
concurrency:
  group: claude-review-${{ github.event.pull_request.number || inputs.pr-number }}
  cancel-in-progress: true
```

Note what that group is keyed on: the **PR number**, not the branch, the ref, or the event.
So repeated `workflow_dispatch` runs for one PR all land in a single group and chain-cancel, whatever `--ref` each was given, and only the last survives.
Reviews for *other* PRs dispatched in the same window are untouched, which is the observation that distinguishes a per-PR group from a global one.

**The trap is attribution rather than cancellation, and it is why this is worth recording.**
You retry a cancelled dispatch, you change something on the retry, the retry succeeds, and whatever you changed looks like the remedy.
It co-varied with the one thing that actually decided the outcome: being last.
Any variable would look causal under this design, so the retry that worked is the weakest possible evidence about *why* it worked.

Measured on PR #1224, 2026-08-06, with all four runs confirmed `PR_NUMBER: 1224` from their own `gather-context` job logs:

| run | dispatched with | dispatched | ended | outcome |
| --- | --- | --- | --- | --- |
| 31135612152 | no `--ref` (ran from `main`) | 00:43:10 | 00:45:06 | cancelled |
| 31135679096 | `--ref <pr-branch>` | 00:44:20 | 00:49:39 | cancelled |
| 31135937709 | no `--ref` (ran from `main`) | 00:48:54 | 00:54:15 | cancelled |
| 31136199829 | `--ref <pr-branch>` | 00:53:30 | 00:59:25 | success |

Each cancellation follows the next dispatch for the same PR by 46, 45, and 45 seconds --- a lag consistent enough to be mechanical rather than coincidental.
The second row settles it: a run dispatched **with** `--ref <pr-branch>` was cancelled too, by a later one dispatched **without** it.
So `--ref` predicts survival in neither direction, and the surviving run is simply the one nothing followed.
Three other PRs' reviews dispatched inside the same window (`31135656213`, `31135680911`, `31135682673`) all succeeded untouched.

Pass `--ref` anyway, for the unrelated reason the section above gives --- `workflow_dispatch` reads the workflow file from the ref you name, defaulting to the default branch.
Just do not read a run's survival as evidence that you passed it.
[#1707](https://github.com/Morrison-Lab/ai-config/pull/1707) restored ai-config's `pull_request` trigger on 2026-08-20, so a dispatch now CAN race a push-triggered run here --- measured that day on [#1724](https://github.com/Morrison-Lab/ai-config/pull/1724), where run `32345965633` (`pull_request`) was cancelled by run `32345990687` (`workflow_dispatch`), leaving `review / require-review` red.
See [`claude-review-dispatch.md`](claude-review-dispatch.md)'s "`ai-config` auto-reviews on push as of 2026-08-20, and did not before".

- **Do:** read the reusable workflow a caller invokes before concluding a cancellation is unexplained.
- **Do:** check a cancelled run's end time against the next dispatch for the same key --- a consistent short lag across several runs is the signature of a `cancel-in-progress` group rather than of anything you changed.
- **Don't:** infer that a change made on the successful retry caused the success.
  Under such a group, being last is sufficient on its own.
- **Don't:** read an absent `concurrency:` block in a caller as meaning its runs cannot be cancelled.

## Python Execution in Runner Environments

- **Add `from __future__ import annotations` when a built-in generic type (`list[str]`, `dict[str, Any]`) appears in a function or variable annotation.**
  Standard generic syntax (e.g. `def f() -> list[str]:`) in a standalone Python helper called by an action or workflow raises `TypeError: 'type' object is not subscriptable` under Python < 3.9.
  Default runners (e.g. `ubuntu-latest`) use Python 3.10+ (as of 2026-08), but adding `from __future__ import annotations` keeps the script compatible across custom `setup-python` versions.
  That future import defers **annotations only** (PEP 563), so a runtime use of the same syntax -- a type alias (`Rows = list[str]`), a class base (`class C(list[str])`), or a `cast()` call -- still raises the error under Python < 3.9.
  For those runtime uses, import `List`/`Dict` from `typing`, which work in every position.
  (Morrison-Lab/gha#412, 2026-08-05).

## Actions outages

Detecting a live platform incident, and cleaning up the two shapes of wreckage
it leaves behind, live in
[`github-actions-outages.md`](github-actions-outages.md).

## A listener workflow's own error is not the dispatched workflow's verdict

A comment-triggered listener workflow (`claude-bot.yml` here, gated on an
`@claude` mention via `issue_comment`) can fail its own conversational step
and still successfully hand off to the workflow that actually produces a
review. `claude-bot.yml` can post `API Error: Usage credits required for 1M
context · turn on usage credits at claude.ai/settings/usage, or use --model
to switch to standard context` as its own comment. Read without checking run
history, that reads as "the review is broken" -- the false conclusion
issue #1197 already recorded (a subagent's repo-wide-failure report; the
real history showed 36 success, 21 cancelled, 0 failures).

What the error actually is: `claude-bot.yml`'s own conversational-response
step hitting a credit gate on **its** invocation, not on the review it goes
on to dispatch.
Two genuine `@claude review` comments on one PR each produced this error,
and both `claude-bot.yml` runs they triggered still reported workflow
**`conclusion: success`** (`list_workflow_runs` on `claude-bot.yml`) -- the
error is caught and posted, not a crash.
Separately, each comment also triggered a `workflow_dispatch` run of
`claude-review.yml` (visible via `list_workflow_runs` on `claude-review.yml`,
`event: workflow_dispatch`, timed within seconds of the comment) -- the
workflow this repo's review actually depends on, per
[`claude-review-dispatch.md`](claude-review-dispatch.md)'s trigger table.

**A third `claude-bot.yml` run followed, and it may have been self-triggered
rather than a new human request.**
The upstream gate (`Morrison-Lab/gha`'s `claude.yml@v1`) fires on `contains(github.event.comment.body, '@claude')` without stripping code spans.
A self-review comment containing `` `@claude` `` triggered the gate (ai-config#1242).
That `workflow_dispatch` run's `head_branch`/`head_sha` reflect `main`, not the PR branch (`ai-config#635`).
Dispatch directly with an explicit `pr_number` input and `ref: <PR-branch>`.

- **Do:** treat a listener's own error comment as evidence about that step only, and check the dispatched workflow's run history before concluding a review failed.
- **Do:** dispatch the review workflow directly rather than relying on a mention comment to relay through the listener.
- **Do:** avoid writing an unescaped `@claude` substring into a PR comment on a repo whose bot gates on `contains()`.
- **Don't:** re-derive "the review workflow is broken repo-wide" from one PR's comments without checking `list_workflow_runs` first.
- **Don't:** count a listener's own error as one of the retries in [`review-verdict-pitfalls`](../shared/workflow/review-verdict-pitfalls.md)'s "retry once, then treat as unreachable" rule.
(2026-08-07, `Morrison-Lab/ai-config#1238`.)

## A job log's findings ride on `##[error]` annotation lines --- filtering annotations deletes the findings

Reading a failed check's job log through `grep -v` on `##[` (the natural move,
since `##[group]`/`##[endgroup]` noise dominates the log)
also deletes the `##[error]` lines,
which is where `check-new-line-breaks.py`-style checkers print each finding.
The summary count line ("2 line(s) need a semantic break") survives the filter,
so the log reads as a check that reported a total and withheld the specifics ---
inviting a guess at what was flagged.
(Measured 2026-08-23 on ai-config#2060:
two CI rounds were spent fixing guessed findings
because the filter ate the two `##[error]` lines naming the real ones.)

- **Do:** hunt a failure's specifics by grepping the log FOR `##[error]` and `##[warning]`,
  or dump the failing step's segment raw (`sed -n '/step marker/,/end marker/p'`).
- **Don't:** strip `##[`-prefixed lines while looking for what a checker flagged ---
  that filter removes annotations, and annotations are the findings.
