# TS — Test + Slide

Run the appropriate tests for the current repo state, and **only if they pass**, slide the floating version tag (e.g., `v2`) to the current main HEAD. This is the safe post-merge workflow: verify before publishing.

## When this fires

- User says “ts”, “test and slide”, “test then slide”
- User says “verify then bump the tag”, “test before sliding v2”
- After merging an MR when the user wants gated tag advancement

## Procedure

### 1. Ensure we’re on main and up to date

``` bash
git checkout main && git pull origin main
```

### 2. Run tests (invoke the `test` skill logic)

Follow the full test procedure from the `test` skill:

- **Local tests** if the repo has them (syntax checks, unit tests)
- **Downstream pipeline** if this is a template/infrastructure repo

For HACtions: run `bash -n` on all scripts, then trigger a pipeline on `test.hac` (project 1611) and wait for it to succeed.

### 3. Gate on results

- **All tests pass → proceed to slide** (step 4)
- **Any test fails → STOP.** Report the failure to the user. Do NOT slide the tag. The user must fix the issue first.

### 4. Slide the tag (invoke the `slide-tag` skill logic)

Follow the slide-tag procedure:

``` bash
git fetch origin main --tags   # FETCH
echo "Current v2: $(git log --oneline -1 v2)"
echo "Target:     $(git log --oneline -1 origin/main)"
git log --oneline v2..origin/main | head -20

git tag -d v2
git tag v2 origin/main
git push origin :refs/tags/v2   # DELETE_REF
git push origin v2              # PUSH

echo "Confirmed: $(git log --oneline -1 v2)"
```

### 5. Report

    ✅ Test + Slide complete:
    - Tests: <summary of what passed>
    - Tag: v2 moved from <old> to <new> (<N> commits)
    - Consumers pinned to v2 will pick up changes on next pipeline run

    — or —

    ❌ Test + Slide BLOCKED:
    - Tests failed: <summary>
    - Tag NOT moved — fix the failure first

## Determining the tag

- Default: `v2` (d-morrison’s HACtions floating tag — substitute your repo’s floating tag name if different)
- If the user specifies a different tag (e.g., “ts v3”), use that instead
- If the repo doesn’t use floating tags, skip the slide step and just report test results (effectively degrades to the `test` skill)

## Edge cases

- **Tag already at main HEAD:** Report “v2 already at main HEAD, nothing to slide” after tests pass. Still run the tests.
- **Multiple tags to slide:** If the user says “ts v2 v3”, slide each one after tests pass.
- **Downstream pipeline slow:** Wait up to 10 minutes. If it hasn’t finished, report the pipeline URL and let the user decide whether to wait or slide optimistically.

## Anti-patterns

- Never slide a tag when tests are failing — that publishes broken templates to every consumer.
- Never skip the test step “because we just ran tests in the MR pipeline” — post-merge main may differ (merge commit, other MRs merged between).
- Don’t slide without pulling main first — you might tag a stale local ref.

Back to top
