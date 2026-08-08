# reproducibility-audit — checklist audit of a project’s reproducibility posture

Audit whether a project reproduces reliably from a clean checkout, not whether its pinned dependencies are current. A project can be fully up to date and still fail to reproduce — an absolute path baked into a script, an env var nobody documented, a build artifact that hides non-determinism. This skill finds those gaps with a checklist scoped to the project’s type.

## When this fires

- “reproducibility audit”, “audit reproducibility”, “check reproducibility”, “is this project reproducible”
- “find hidden dependencies”, “find hardcoded paths”, “check environment assumptions”
- “can this be reproduced from scratch”, “audit for a replication package”, “check output traceability”
- Before archiving a project (OSF/Dryad, per the lab manual’s reproducibility norms) or submitting it alongside a manuscript.
- Periodically on a long-lived analysis repo, the same cadence `check-dependency-updates` uses for freshness audits.

## What to audit

Run the checks that apply to the project’s type. Sections 1-3 are project-type-specific; sections 4-6 apply to every project.

### 1. R package

- **`renv.lock` completeness.** `renv::status()` — does the lockfile cover every package actually loaded (`renv::dependencies()` diffed against the lockfile), not just the ones someone remembered to snapshot?
- **Captured `sessionInfo()`.** Does the repo (or its README/vignette) record the R version and platform a result was generated under? A lockfile pins package versions but not the R version itself.
- **`DESCRIPTION` completeness.** Every `library()`/`::` call has a matching `Imports`/`Suggests` entry — grep `R/` and `vignettes/` for `library(` and `::` and diff against `DESCRIPTION`.

### 2. Quarto book/site

- **`_freeze`/`.quarto` determinism.** Does a clean `quarto render` (freeze cache deleted) reproduce the committed output, or does the committed `_freeze/` mask a render that no longer succeeds from scratch? (`reprexes`’ R/Quarto specifics section already covers build artifacts as confounders for render bugs — this check is the whole-project version of that same concern.)
- **Pinned Quarto/R versions.** Is the Quarto CLI version and R version used to render pinned somewhere (`_quarto.yml`, a CI workflow, a README badge), or does the render depend on whatever happens to be installed?
- **External data/asset fetches.** Does the render pull any file from a URL or absolute path outside the repo, silently breaking a clone elsewhere?

### 3. General script repo

- **Hardcoded absolute paths.** Grep for the tells: `/home/`, `/Users/`, `C:\`, `setwd(`, a bare drive letter, or any string that names a specific machine’s directory layout.

  ``` bash
  grep -rnE '(/home/[a-zA-Z0-9_.-]+|/Users/[a-zA-Z0-9_.-]+|[A-Za-z]:\\{1,2}|setwd\()' \
    --include='*.R' --include='*.py' --include='*.sh' --include='*.qmd' .
  ```

- **Undocumented env vars.** Grep for env-var reads (`Sys.getenv(`, `os.environ`, `os.getenv(`, `$VARNAME` in shell) and confirm each one is documented somewhere a new user would find it (README, `.env.example`, a setup script) — not just referenced in code.

- **Undocumented prerequisites.** Does the repo state what has to be installed *before* the package manager runs — a system library, a specific interpreter version, a CLI tool the scripts shell out to? Grep for `system(`, `subprocess`, `shell_exec`, or backticked shell calls and confirm each invoked binary is named as a prerequisite.

### 4. Output traceability (all project types)

For each output artifact a project ships (a figure, a table, a rendered report, a results file), can it be traced back to the **exact script:line** that produced it? Check for:

- A caption, filename, or header comment naming the generating script.
- A single entry-point script/Makefile target that regenerates every output from source, rather than outputs having been produced once by hand and never regenerated since.
- Seeds captured for anything stochastic (`set.seed(`, `random.seed(`, `np.random.seed(` or a `withr::with_seed()` call per the `prefer-packaged-functions` coding convention) — an unseeded random process makes a result strictly non-reproducible, not just hard to trace.

### 5. Undocumented prerequisites and environment assumptions (all types)

Beyond the general-script-repo grep in §3: does the project assume a specific OS, shell, locale, or timezone that isn’t stated? Look for OS-specific path separators, shell-specific syntax (`bash`-only constructs in a script with a `#!/bin/sh` shebang), or a locale-dependent operation (date parsing, string sorting) with no documented assumption.

### 6. Hidden/undocumented dependencies (all types)

A dependency is “hidden” when the project runs today only because of something already present in the current environment that the manifest doesn’t declare — a globally-installed CLI tool, a system library, a package loaded via a side-effect (`require()` inside another package’s code) rather than a direct import. Test by checking what the project’s own manifest (`DESCRIPTION`, `requirements.txt`, `package.json`, `_quarto.yml` engine config) declares against what the code actually calls, the same diff-the-manifest-against-actual-usage method as §1’s `DESCRIPTION` check, generalized to non-R manifests.

## Reporting and follow-through

1.  **Report a table**, one row per gap, mirroring `check-dependency-updates`’s and `check-info-quality`’s report-table convention:

        | Check | Finding | Location | Evidence | Severity |
        |-------|---------|----------|----------|----------|
        | Hardcoded path | absolute path to a local data dir | analysis.R:14 | `setwd("/home/alice/proj")` | blocking |
        | Traceability | no script named for this figure | fig3.png | no caption/header comment names a generator | minor |
        | Env assumption | undocumented env var | ingest.py:8 | `os.environ["API_KEY"]` not in README | blocking |

2.  **File a tracking issue** for the gaps worth fixing (issue-first, per this repo’s `st`/`gi` workflow). Group related gaps under one issue (e.g. all hardcoded-path fixes together); don’t open one issue per one-line fix.

3.  **Fix on a branch**, run the project’s standard checks, and open a PR. Follow with `ardi` to drive it to clean.

## Custom agent for the audit phase

The “What to audit” checklist needs no Edit/Write access — every check is a grep, a read, or a read-only command (`renv::status()`, `renv::dependencies()`, `quarto render` against a scratch copy). Delegate it to the `reproducibility-auditor` custom agent (`.claude/agents/reproducibility-auditor.md`) for a harness-enforced guarantee against Edit/Write before the report is reviewed, matching the pattern `dependency-auditor` sets for `check-dependency-updates`. Run the “Reporting and follow-through” steps (issue, branch, PR, ARDI) in the main session afterward.

## Relationship to other skills

- **`reprexes`** — isolates a **single bug** into a minimal runnable snippet, for debugging or filing upstream; this skill audits whether the **whole project** reproduces reliably (pinned deps, captured seeds and session info, deterministic renders). Different scope (one bug vs. whole-repo posture) and different cadence (on-demand debugging aid vs. periodic audit). `reprexes` is often invoked *within* an investigation this skill’s findings trigger — e.g. a traceability gap this skill flags can turn into a `reprexes` session once someone tries to isolate why a specific output doesn’t regenerate. For the R/Quarto specifics of capturing `sessionInfo()` and treating `_freeze`/build artifacts as confounders, see `reprexes`’ own “R / Quarto specifics” section rather than duplicating that content here. (`reprexes` currently has no “Relationship to other skills” section of its own — noted here as an observation, not fixed in this PR, to keep this change scoped to the new skill.)
- **`check-dependency-updates` (`cdu`)** — asks “is this pinned dependency current” (is there a newer version available); this skill asks “is the current pin, whatever version it is, sufficient to reproduce a result deterministically” (freshness is irrelevant to that question). Run `cdu` for upgrades, run this skill for reproducibility gaps — a project can fail either audit independently of the other.
- **`check-info-quality` (`ciq`)** — its check A (out-of-date information) can flag a stale “how to install” doc; this skill’s §3/§5 checks go further, verifying prerequisites and env assumptions are documented **at all**, not just current.
- **`st` / `gi` / `defer-issue`** — file the tracking issue and drive the fix PR.
- **`convert-repo-format` (`crf`)** — establishes the lab’s template layout a repo should follow; this skill checks whether a given repo, in whatever layout it already has, actually reproduces.

## Anti-patterns

- ❌ Treating “dependencies are up to date” (`cdu`’s job) as the same question as “dependencies are reproducible” (this skill’s job) — a freshly bumped pin can still be undocumented or hidden.
- ❌ Flagging every absolute path without checking whether it’s inside a gitignored scratch/cache directory that never ships — focus on paths that appear in code a fresh clone would run.
- ❌ Silently fixing a hardcoded path or undocumented env var instead of reporting it — propose the fix, don’t bulk-edit without review, the same discipline `check-info-quality` and `find-ai-tells` already use.
- ❌ Auditing only the project-type-specific sections and skipping output traceability — a project can have a pristine lockfile and still ship a figure nobody can regenerate.
- ❌ Reporting “looks reproducible” without actually running a clean render/build — verify by attempting the reproduction, don’t infer it from the presence of a lockfile alone.

Back to top
