# find-reproducibility-gaps — read-only reproducibility checklist

The *audit* half of `reproducibility-audit`, factored out so it runs forked ([ai-config#914](https://github.com/Morrison-Lab/ai-config/issues/914)). It checks whether a project reproduces reliably from a clean checkout and returns a table of gaps. It changes nothing: `reproducibility-audit` files the tracking issue and drives the fix PR in the main session afterward, and you can run this skill on its own for a report with no follow-through.

## Step 1 — Resolve the target and its type

Audit the project the user named, or the current repository when none is named. A forked run cannot ask the user, so when the target is ambiguous, take the narrowest reasonable reading and state at the top of the report which reading you chose.

Detect the project’s type: an R package has a `DESCRIPTION`; a Quarto book or site has a `_quarto.yml`; anything else is a general script repo. A project can be more than one type (an R package with a Quarto site); run every section that applies.

## Step 2 — Run the checklist

Run the checks that apply to the project’s type. Sections 1-3 are project-type-specific; sections 4-6 apply to every project.

### 1. R package

- **`renv.lock` completeness.** `renv::status()` — does the lockfile cover every package actually loaded (`renv::dependencies()` diffed against the lockfile), not just the ones someone remembered to snapshot?

  ``` bash
  Rscript -e 'renv::status()'
  ```

- **Captured `sessionInfo()`.** Does the repo (or its README/vignette) record the R version and platform a result was generated under? A lockfile pins package versions but not the R version itself.

- **`DESCRIPTION` completeness.** Every `library()`/`::` call has a matching `Imports`/`Suggests` entry — grep `R/` and `vignettes/` for `library(` and `::` and diff against `DESCRIPTION`:

  ``` bash
  rg -no 'library\([a-zA-Z0-9.]+\)|[a-zA-Z0-9.]+::' R/ vignettes/ | sort -u
  ```

### 2. Quarto book/site

- **`_freeze`/`.quarto` determinism.** Does a clean `quarto render` (freeze cache deleted) reproduce the committed output, or does the committed `_freeze/` mask a render that no longer succeeds from scratch? (`reprexes`’ R/Quarto specifics section already covers build artifacts as confounders for render bugs; this check is the whole-project version of that same concern.) Run it against a scratch copy, so the render writes nothing into the audited checkout:

  ``` bash
  quarto render --no-cache
  ```

- **Pinned Quarto/R versions.** Is the Quarto CLI version and R version used to render pinned somewhere (`_quarto.yml`, a CI workflow, a README badge), or does the render depend on whatever happens to be installed?

- **External data/asset fetches.** Does the render pull any file from a URL or absolute path outside the repo, silently breaking a clone elsewhere?

### 3. General script repo

- **Hardcoded absolute paths.** Grep for the tells: `/home/`, `/Users/`, `C:\`, `setwd(`, a bare drive letter, or any string that names a specific machine’s directory layout:

  ``` bash
  grep -rnE '(/home/[a-zA-Z0-9_.-]+|/Users/[a-zA-Z0-9_.-]+|[A-Za-z]:\\{1,2}|setwd\()' \
    --include='*.R' --include='*.py' --include='*.sh' --include='*.qmd' .
  ```

  Skip a path inside a gitignored scratch or cache directory that never ships; report paths in code a fresh clone would run.

- **Undocumented env vars.** Grep for env-var reads (`Sys.getenv(`, `os.environ`, `os.getenv(`, `$VARNAME` in shell) and confirm each one is documented somewhere a new user would find it (README, `.env.example`, a setup script), not just referenced in code:

  ``` bash
  rg -n 'Sys\.getenv\(|os\.environ|os\.getenv\(|\$[A-Z_]{2,}' .
  ```

- **Undocumented prerequisites.** Does the repo state what has to be installed *before* the package manager runs — a system library, a specific interpreter version, a CLI tool the scripts shell out to? Grep for `system(`, `subprocess`, `shell_exec`, or backticked shell calls and confirm each invoked binary is named as a prerequisite:

  ``` bash
  rg -n 'system\(|subprocess|shell_exec|`[^`]+`' .
  ```

### 4. Output traceability (all project types)

For each output artifact a project ships (a figure, a table, a rendered report, a results file), can it be traced back to the **exact script:line** that produced it? Check for:

- A caption, filename, or header comment naming the generating script.

- A single entry-point script/Makefile target that regenerates every output from source, rather than outputs having been produced once by hand and never regenerated since.

- Seeds captured for anything stochastic (`set.seed(`, `random.seed(`, `np.random.seed(` or a `withr::with_seed()` call per the `prefer-packaged-functions` coding convention). An unseeded random process makes a result strictly non-reproducible, not just hard to trace:

  ``` bash
  rg -n 'set\.seed\(|random\.seed\(|np\.random\.seed\(|withr::with_seed\(' .
  ```

### 5. Undocumented prerequisites and environment assumptions (all types)

Beyond the general-script-repo grep in section 3: does the project assume a specific OS, shell, locale, or timezone that isn’t stated? Look for OS-specific path separators, shell-specific syntax (`bash`-only constructs in a script with a `#!/bin/sh` shebang), or a locale-dependent operation (date parsing, string sorting) with no documented assumption.

### 6. Hidden/undocumented dependencies (all types)

A dependency is “hidden” when the project runs today only because of something already present in the current environment that the manifest doesn’t declare: a globally-installed CLI tool, a system library, a package loaded via a side-effect (`require()` inside another package’s code) rather than a direct import. Test by checking what the project’s own manifest (`DESCRIPTION`, `requirements.txt`, `package.json`, `_quarto.yml` engine config) declares against what the code actually calls. This is the same diff-the-manifest-against-actual-usage method as section 1’s `DESCRIPTION` check, generalized to non-R manifests.

## Step 3 — Return the report

Return the report only, one row per gap, mirroring `check-dependency-updates`’s and `check-info-quality`’s report-table convention:

    | Check | Finding | Location | Evidence | Severity |
    |-------|---------|----------|----------|----------|
    | Hardcoded path | absolute path to a local data dir | analysis.R:14 | `setwd("/home/alice/proj")` | blocking |
    | Traceability | no script named for this figure | fig3.png | no caption/header comment names a generator | minor |
    | Env assumption | undocumented env var | ingest.py:8 | `os.environ["API_KEY"]` not in README | blocking |

Say which sections you ran and, for a clean render or build, whether you actually attempted it: “looks reproducible” inferred from a lockfile alone is not a finding. Do not edit or write anything, even with `Bash`.

## Runs forked; `background: false` for synchronous return

This whole skill runs isolated as the `reproducibility-auditor` custom agent (`context: fork` + `agent: reproducibility-auditor`), as `detect-hallucinations` does with `hallucination-detector`. Every step above needs only that agent’s tools (`Bash`, `Read`, `Grep`, `Glob`, `WebFetch`), so nothing is lost by forking the whole procedure. The harness gives the fork no Edit or Write tool; the agent keeps `Bash` for its checks, so avoiding a write-capable shell command is still instruction-level. `background: false` returns the report before the caller continues, because `reproducibility-audit` acts on it.

## Relationship to other skills

- **`reproducibility-audit`** — the act half: runs this skill, then files the tracking issue, fixes on a branch and drives the PR with `ardi`.
- **`reprexes`** — isolates a **single bug** into a minimal runnable snippet; this skill audits whether the **whole project** reproduces.
- **`check-dependency-updates` (`cdu`)** — asks whether a pin is current; this skill asks whether the current pin, whatever version it is, reproduces a result.

Back to top
