# Test

Verify an MR’s changes by running the appropriate tests — either local unit tests or a downstream pipeline in a consumer/revdep repo.

## When this fires

- User says “test”, “test this”, “run tests”, “verify this MR”
- User says “test downstream”, “check in test.hac”, “trigger revdep pipeline”
- After implementing a fix, before declaring it ready to merge

## Procedure

### 1. Determine test strategy

Inspect the repo to decide which testing path applies:

| Signal | Strategy |
|----|----|
| Repo has `tests/` or `testthat/` or a test framework | **Unit tests** — run locally |
| Repo is a CI template provider (like HACtions) with no local tests | **Downstream** — trigger pipeline in a revdep |
| Both exist | Run local tests first, then downstream if relevant |

For **HACtions** specifically: there are no local unit tests. The test strategy is to trigger a pipeline in a revdep like `test.hac` (project 1611) that exercises the templates.

### 2. Local unit tests (if applicable)

``` bash
# R package
Rscript -e 'devtools::test()'

# Python
pytest

# Node
npm test

# Shell (bash -n syntax check at minimum)
for f in scripts/*.sh scripts/lib/*.sh; do bash -n "$f"; done
```

Report pass/fail. If tests fail, investigate and fix before proceeding.

### 3. Downstream / revdep testing

When the change is to shared infrastructure (CI templates, shared scripts), test it in a consumer repo.

#### a. Identify the test bed

- Check `REVDEPS.md` for consumer repos
- Prefer a dedicated test bed (e.g., `test.hac`, project 1611) over production repos
- If no test bed exists, pick the simplest consumer repo

#### b. Trigger a pipeline on the consumer repo

The consumer must already reference the MR’s branch (or the floating tag must have been slid). Two approaches:

**Option A — Trigger pipeline via API (preferred for template repos):**

``` bash
# Trigger a pipeline on the consumer's default branch
glab api --method POST "projects/<CONSUMER_PROJECT_ID>/pipeline" \
  -f "ref=main" 2>&1 | cat
```

**Option B — If the consumer needs to reference the MR branch:** Create a temporary MR on the consumer that points `include: ref:` to the feature branch, or use a CI variable override if the consumer supports it.

#### c. Wait for and check results

``` bash
# Get the pipeline ID from the trigger response, then poll
glab api "projects/<CONSUMER_PROJECT_ID>/pipelines/<PIPELINE_ID>" \
  --jq '.status' 2>&1 | cat
```

Poll every 30–60 seconds until status is `success`, `failed`, or `canceled`.

### 4. Report results

Summarize what was tested and the outcome:

    ✅ Tests passed:
    - bash -n syntax check: all scripts OK
    - test.hac pipeline #NNNN: success (jobs: lint ✓, check-package ✓, claude-review ✓)

    — or —

    ❌ Tests failed:
    - test.hac pipeline #NNNN: failed
    - Failing job: lint (exit code 1)
    - Error: <summary>

If tests fail, investigate the failure and either fix it or report the issue to the user.

## Edge cases

- **No test infrastructure at all:** Fall back to `bash -n` syntax checks for shell scripts, or a dry-run/lint of whatever the repo contains.
- **Consumer repo not on job-token allowlist:** The API trigger will fail with 403. Inform the user they need to add the consumer to the allowlist (Settings → CI/CD → Job Token Permissions).
- **Floating tag already slid:** If `v2` was already moved to include the MR’s changes, a simple pipeline trigger on the consumer’s `main` will pick up the new templates automatically.
- **MR not yet merged:** The consumer can’t see the branch unless it’s in the same project or group. For cross-project testing pre-merge, the consumer needs a temporary `include: ref: <branch>` override.

## Known test beds

| Test bed | Project ID | What it exercises |
|----|----|----|
| test.hac | 1611 | HACtions CI templates (lint, check-package, claude-review, etc.) |

> The row above is d-morrison’s own test bed; project ID `1611` is specific to that GitLab instance. Replace this table with your own downstream revdep repos and their project IDs.

## Anti-patterns

- Don’t skip testing because “it’s just a template change” — template changes can break every consumer.
- Don’t declare an MR ready to merge without at least one successful downstream pipeline if the change touches shared CI infrastructure.
- Don’t trigger pipelines on production consumer repos if a test bed exists.

Back to top
