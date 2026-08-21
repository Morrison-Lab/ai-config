---
name: test
description: "Run unit or revdep tests."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# Test

Verify an MR's changes by running the appropriate tests — either local unit
tests or a downstream pipeline in a consumer/revdep repo.

## When this fires

- User says "test", "test this", "run tests", "verify this MR"
- User says "test downstream", "check in test.hac", "trigger revdep pipeline"
- After implementing a fix, before declaring it ready to merge

## Procedure

### 1. Determine test strategy

Inspect the repo to decide which testing path applies:

| Signal | Strategy |
|--------|----------|
| Repo has `tests/` or `testthat/` or a test framework | **Unit tests** — run locally |
| Repo is a CI template provider (like HACtions) with no local tests | **Downstream** — trigger pipeline in a revdep |
| Both exist | Run local tests first, then downstream if relevant |

For **HACtions** specifically: there are no local unit tests. The test
strategy is to trigger a pipeline in a revdep like `test.hac` (project 1611)
that exercises the templates.

### 2. Isolate credentials before testing external writes

Before running a script whose success path can mutate an external service (uploads, releases, deployments, secret rotation), inspect every ambient authentication source it can inherit: environment variables, process options, credential helpers, and keyrings.
Omitting the script's explicit login call is not isolation; an earlier session may already have populated one of those sources.

- If the user reserved the authenticated action for themselves, run only parse/lint and credential-free preflight paths.
  Start a clean process that explicitly clears the script's documented auth variables and in-process options, and prove it stops before the network write.
- If end-to-end testing is necessary, get explicit authorization and use a disposable target or a documented dry-run mode.
  Verify the remote state before and after.
- Never treat an unchanged remote version as permission to have contacted the service; disclose any accidental authenticated request immediately.

### 3. Local unit tests (if applicable)

```bash
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

#### Always report SKIP alongside PASS and FAIL

A pass and fail count says nothing about the tests that never executed, so
"43 pass, 0 fail" can be exactly accurate while the suite has not been
verified.
Report all three numbers, and treat a non-zero skip count as an unmeasured
population: say what was skipped and why before citing the run as evidence.

Then ask what made them skip.
A skip is usually keyed on a missing optional dependency
(`skip_if_not_installed()`, `pytest.importorskip`), so an invocation that
bypasses environment setup silently shrinks the suite while leaving the
reported numbers looking healthy.
In an R package, `R_PROFILE_USER=/dev/null` skips `renv/activate.R` and
therefore the project library, so packages the tests gate on are absent and
their tests skip.
The same applies to any `--no-config` flag, a bare interpreter, or a
container built without the optional extras.

Before citing a run as verification, confirm it ran in the project's real
environment.
Re-run without the bypass when the skip count is non-zero.

### 4. Downstream / revdep testing

When the change is to shared infrastructure (CI templates, shared scripts),
test it in a consumer repo.

#### a. Identify the test bed

- Check `REVDEPS.md` for consumer repos
- Prefer a dedicated test bed (e.g., `test.hac`, project 1611) over
  production repos
- If no test bed exists, pick the simplest consumer repo

#### b. Trigger a pipeline on the consumer repo

The consumer must already reference the MR's branch (or the floating tag
must have been slid). Two approaches:

**Option A — Trigger pipeline via API (preferred for template repos):**
```bash
# Trigger a pipeline on the consumer's default branch
glab api --method POST "projects/<CONSUMER_PROJECT_ID>/pipeline" \
  -f "ref=main" 2>&1 | cat
```

**Option B — If the consumer needs to reference the MR branch:**
Create a temporary MR on the consumer that points `include: ref:` to the
feature branch, or use a CI variable override if the consumer supports it.

#### c. Wait for and check results

```bash
# Get the pipeline ID from the trigger response, then poll
glab api "projects/<CONSUMER_PROJECT_ID>/pipelines/<PIPELINE_ID>" \
  --jq '.status' 2>&1 | cat
```

Poll every 30–60 seconds until status is `success`, `failed`, or `canceled`.

### 5. Report results

Summarize what was tested and the outcome:

Always include the skip count for a unit-test run, per step 3.

```
✅ Tests passed:
- devtools::test(): 40 pass, 0 fail, 0 skip
- bash -n syntax check: all scripts OK
- test.hac pipeline #NNNN: success (jobs: lint ✓, check-package ✓, claude-review ✓)

— or —

❌ Tests failed:
- test.hac pipeline #NNNN: failed
- Failing job: lint (exit code 1)
- Error: <summary>
```

If tests fail, investigate the failure and either fix it or report the issue
to the user.

## Edge cases

- **No test infrastructure at all:** Fall back to `bash -n` syntax checks
  for shell scripts, or a dry-run/lint of whatever the repo contains.
- **Consumer repo not on job-token allowlist:** The API trigger will fail
  with 403. Inform the user they need to add the consumer to the allowlist
  (Settings → CI/CD → Job Token Permissions).
- **Floating tag already slid:** If `v2` was already moved to include the
  MR's changes, a simple pipeline trigger on the consumer's `main` will
  pick up the new templates automatically.
- **MR not yet merged:** The consumer can't see the branch unless it's in
  the same project or group. For cross-project testing pre-merge, the
  consumer needs a temporary `include: ref: <branch>` override.

## Known test beds

| Test bed | Project ID | What it exercises |
|----------|-----------|-------------------|
| test.hac | 1611 | HACtions CI templates (lint, check-package, claude-review, etc.) |

> The row above is d-morrison's own test bed; project ID `1611` is specific to
> that GitLab instance. Replace this table with your own downstream revdep
> repos and their project IDs.

## Anti-patterns

- Don't skip testing because "it's just a template change" — template
  changes can break every consumer.
- Don't declare an MR ready to merge without at least one successful
  downstream pipeline if the change touches shared CI infrastructure.
- Don't trigger pipelines on production consumer repos if a test bed exists.
- Don't test an upload or deployment script in a process that may inherit ambient credentials when the user reserved the external write for themselves.
