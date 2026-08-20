# check-dependency-updates — audit dependencies for available upgrades

Find dependencies that have moved on without you. The goal is to surface upgrades worth taking — bug fixes, new features, security patches — not to bump everything to latest. Audit first, report what each update buys, then take the ones that pass tests.

This is the maintenance-time counterpart to `prefer-upstream`: that skill picks a well-maintained upstream dependency at write time; this one keeps the dependencies you already chose current.

## When this fires

- “check dependency updates”, “cdu”, “audit dependency freshness”
- “are my dependencies stale?”, “check for outdated dependencies”
- “should I bump the workflow SHAs?”, “are there newer versions of my pinned actions?”
- “update the renv lockfile”, “are my R packages out of date?”
- Periodically on a maintained repo — a good cadence is at the start of a maintenance pass, or after a long gap since the last update.

## What to audit

Run the checks that apply to the repo. The two headline cases are GitHub Actions pins and `renv.lock`; the rest are common in this user’s R/Quarto repos.

### 1. GitHub Actions pins (`.github/workflows/*.yml`)

List every action and how it’s pinned:

``` bash
grep -rnE '^\s*uses:' .github/workflows/ .github/actions/ 2>/dev/null
```

Pins come in two forms:

- **Tag pin** — `uses: actions/checkout@v4`. Check the latest release:

  ``` bash
  gh api repos/actions/checkout/releases/latest --jq '.tag_name'
  # no releases? fall back to tags:
  gh api repos/actions/checkout/tags --jq '.[0].name'
  ```

- **SHA pin with a version comment** — `uses: actions/checkout@<sha> # v4.1.1` (the secure form for third-party actions). Resolve the latest tag back to its commit SHA so you can compare:

  ``` bash
  latest=$(gh api repos/actions/checkout/releases/latest --jq '.tag_name')
  gh api "repos/actions/checkout/commits/${latest}" --jq '.sha'   # handles annotated tags
  ```

  If the SHA differs, update **both** the SHA and the trailing `# vX.Y.Z` comment together — a stale comment next to a fresh SHA is its own bug.

A `.github/dependabot.yml` with the `github-actions` ecosystem automates this sweep. Recommend it if the repo has none; this skill is the on-demand / one-off audit and the catch-all for what Dependabot misses.

### 2. renv lockfile (`renv.lock`)

In the project, with renv active:

``` r
renv::status()              # confirm library, lockfile, and DESCRIPTION agree first
renv::update(check = TRUE)  # PREVIEW available updates without installing anything
```

`check = TRUE` reports which packages are behind without touching the library or the lockfile. To actually take updates (do this on a branch):

``` r
renv::update()              # install the newer versions
renv::snapshot()            # write them into renv.lock
```

Then inspect `git diff renv.lock`, run the package’s tests/checks, and keep only the updates that pass.

### 3. pre-commit hooks (`.pre-commit-config.yaml`)

``` bash
pre-commit autoupdate        # rewrites each hook's `rev:` to the latest tag
git diff .pre-commit-config.yaml
```

Inspect the diff and run the hooks once before committing.

### 4. Quarto and other tool versions pinned in CI

Workflows often pin `quarto-version:`, an R version, or a Pandoc version. Compare each against the latest upstream release, e.g. for Quarto:

``` bash
gh api repos/quarto-dev/quarto-cli/releases/latest --jq '.tag_name'
```

### 5. Git submodules

``` bash
git submodule status
# for each submodule, see whether upstream has moved:
git -C <submodule-path> fetch && git -C <submodule-path> log HEAD..FETCH_HEAD --oneline
```

### 6. Other manifests, if present

- `DESCRIPTION` version floors (`Imports:` / `Remotes:`) — usually covered by the renv check; `old.packages()` lists CRAN packages with newer versions.
- `package.json` — `npm outdated`.
- `Dockerfile` base images / pinned apt or pip versions.

## Reporting and follow-through

1.  **Read the changelog before recommending each bump.** Fetch and skim the release notes / NEWS / CHANGELOG (use `WebFetch` on the upstream releases or NEWS page), especially across a major version, so you can say what the update buys and catch breaking changes.
2.  **Report a table**, one row per dependency: current pin, latest available, and what the update buys, with the changelog linked. Flag security fixes — those are the highest-value rows.
3.  **File a tracking issue** for the updates worth taking (issue-first, per the repo’s workflow — see `st` / `gi`). Group related bumps; don’t open one issue per trivial patch.
4.  **Apply on a branch**, run the repo’s standard checks (render / lint / spell / tests), and open a PR. Keep unrelated bumps in separate PRs so a single bad update is easy to revert.
5.  **ARDI the PR to clean** (see `ardi`).

## Cautions

- **Newer isn’t automatically better.** A bump can introduce a breaking change or a regression. Tests are the gate; read the changelog first.
- **Respect deliberate pins.** SHA-pinning a third-party action is a security choice, and a major-version floor in `DESCRIPTION` may be intentional. Refresh the pin to a newer *vetted* version; don’t remove the pinning in the name of freshness.
- **Update SHA and comment together** (see §1, GitHub Actions pins above).
- **`renv.lock` is not a trivial file.** Editing it changes what every collaborator and CI job installs — treat a lockfile bump like any other code change: branch, test, review.

## Custom agent for the audit phase

The “What to audit” and changelog-reading steps have no need for Edit/Write access. Delegate them to the `dependency-auditor` custom agent (`.claude/agents/dependency-auditor.md`) for a hard, harness-enforced guarantee against Edit/Write tool use before the report is reviewed — tighter than this skill’s own instruction-only discipline, though the agent retains `Bash` for read-only checks, so avoiding a write-capable shell command (`renv::update()` without `check = TRUE`, `pre-commit autoupdate`) is still instruction-level. Run the “Reporting and follow-through” steps (issue, branch, PR, ARDI) in the main session afterward.

## Relationship to other skills

- **`chores`** — the processing counterpart. This skill *finds* stale pins (and recommends a `dependabot.yml`); once Dependabot opens the resulting bump PRs, `chores` triages and merges/flags them.
- **`prefer-upstream`** — the write-time counterpart: choose a maintained upstream dependency instead of hand-rolling. This skill keeps those choices current over time.
- **`workaround-watcher`** — watches one specific upstream blocker and auto-drafts the revert when it’s fixed. This skill is the broad periodic sweep across all pins.
- **`claude-agent-workflow` / `claude-review-workflow`** — where the action pins this audit checks actually live.
- **`st` / `gi` / `defer-issue`** — file the tracking issue and drive the update PR.
- **`release-notify`** — the opposite direction: you ship a breaking change and notify the repos that depend on you.

## Anti-patterns

- ❌ Bumping everything to latest without reading changelogs or running tests.
- ❌ Updating a SHA pin but leaving the stale `# vX.Y.Z` comment beside it.
- ❌ One giant PR mixing unrelated dependency bumps — impossible to bisect or revert cleanly.
- ❌ Removing a deliberate security/reproducibility pin to “stay fresh”.
- ❌ Reporting “everything’s current” without actually querying upstream — verify each pin against the real latest version, don’t assume.

Back to top
