# Slide Tag

Force-move a floating Git tag to a new target commit. Used for repos where consumers pin to a major-version tag (e.g., `v2`) that advances with each release.

## When this fires

- User says “slide v2”, “slide the tag”, “move tag to main”
- User says “update the v2 tag”, “bump the floating tag”
- After merging work to main when the repo uses floating version tags

## Never ask before sliding an infra tag

Ezra, 2026-11-20: “never ask me before sliding an infra tag; always just do it” ([ai-config#6052](https://github.com/Morrison-Lab/ai-config/issues/6052)). A floating tag in an infrastructure repo (gha’s `v3`, any lab repo whose consumers pin a major tag) moves forward without anyone’s leave. Whichever agent finishes an infra PR, by merging it or by hearing that it merged, slides the tag once the gates in step 3 pass. That agent does not hand the slide to a runner thread, the coordinator or the user, and does not wait for a typed “slide v3”. A gate that fails is a hold, not a question: say which gate failed, fix or wait on it, and slide when it clears. Two agents sliding at once are safe, because gha’s `slide-major-tag.yml` takes `expected_sha` and refuses a commit nobody checked. `hooks/no-ask-to-slide-tag.py` denies a message that asks leave to slide a tag or hands the slide to someone else.

- **Do:** dispatch the slide yourself after the gates pass, then report the old SHA, the new SHA and the PRs the tag now carries.
- **Don’t:** end a turn with “want me to slide v3?” or “the runner thread slides v3” after merging an infra PR.

A merge ends the PR’s activity subscription, so nothing wakes you when CI on the merge commit finishes. After the merge, poll that commit’s runs in a background loop that exits when they are all terminal, and slide as soon as it exits. A fixed one-shot timer does not do this job: on gha#2180 (2026-11-21) main went green within minutes, while a 15-minute timer left the slide undone until Ezra asked why.

- **Do:** start a polling loop on the merge commit’s workflow runs right after the merge.
- **Don’t:** arm a fixed-delay reminder and treat the wait as covered.

Moving a tag **backward** is not covered: it still needs explicit confirmation (see “Edge cases”).

## Procedure

### 1. Determine tag and target

- **Tag:** from user input (e.g., “slide v2” → tag is `v2`)
- **Target:** defaults to `origin/main` unless user specifies otherwise

### 2. Fetch and validate

``` bash
git fetch origin main --tags   # FETCH
```

Confirm the tag exists:

``` bash
git tag -l '<tag>'   # should output the tag name
```

If the tag doesn’t exist yet, create it fresh (skip the delete steps):

``` bash
git tag <tag> <target>
git push origin <tag>   # PUSH
```

### 3. Show what’s moving

Display the before/after, so the report can name what moved (this is a record, not a request for approval):

``` bash
echo "Current: $(git log --oneline -1 <tag>)"
echo "Target:  $(git log --oneline -1 <target>)"
echo "Commits being added:"
git log --oneline <tag>..<target> | head -20
```

Before sliding, confirm that every review this session requested or is waiting on for those commits’ PRs has returned a verdict, and that no review check run on them is still pending. A PR can be merged by another session while this one is still waiting on its review, and a slide publishes that unreviewed change to every consumer of the tag; see [`revert-premature-merge`](../../shared/workflow/revert-premature-merge.md)’s pending-review section. The gate applies however the slide is done: Morrison-Lab/gha slides by dispatching its `slide-major-tag.yml` workflow rather than by the `git push` in step 4, and gha’s own `CLAUDE.md` tag-slide bar does not yet carry this gate ([Morrison-Lab/gha#977](https://github.com/Morrison-Lab/gha/issues/977)).

### 4. Slide the tag

``` bash
git tag -d <tag>
git tag <tag> <target>
git push origin :refs/tags/<tag>   # DELETE_REF
git push origin <tag>              # PUSH
```

**Why delete+recreate instead of `git push --force`?** Some GitLab/GitHub instances have protected-tag rules that block force-push but allow delete+create. The delete+recreate pattern works universally.

### 5. Confirm

``` bash
git log --oneline -1 <tag>
```

Report the new tag position to the user.

## Edge cases

- **Tag doesn’t exist yet:** Skip delete, just create and push.
- **Target is behind current tag:** Warn the user — this would move the tag backward. Proceed only if confirmed.
- **Protected tag on remote:** If delete fails with a permission error, the tag is protected. Inform the user they need to unprotect it in the repo settings first (Settings → Repository → Protected Tags on GitLab).

## Examples

    User: "slide v2"
    → moves v2 to origin/main

    User: "slide v2 to abc123"
    → moves v2 to commit abc123

    User: "slide v3 to the release branch"
    → moves v3 to origin/release (or whatever the release branch is)

## Anti-patterns

- ❌ Using `git push --force origin <tag>` without trying delete first
- ❌ Sliding without fetching first (tag might already be at target)
- ❌ Sliding without reporting what commits were added
- ❌ Asking anyone’s leave for a forward slide, or leaving it to a runner thread
- ❌ Moving a tag backward without explicit confirmation

## Relationship to other skills

**“Slide the `<x>` submodule” is a different operation from this skill** — this skill moves a floating *tag* (e.g. `v2`) to a new commit; a submodule pin is a gitlink entry in the parent repo pointing at a specific commit of a different repo. Bumping a submodule pin means: fetch the submodule’s upstream, check out its new commit, `git add <submodule-path>` in the parent repo, and commit — no tag involved. `check-dependency-updates` (`cdu`)’s “Git submodules” step covers this; `use-math-macros` covers it specifically for the `d-morrison/macros` submodule as part of a broader macro-conversion pass. Don’t reach for `slide-tag` on a “slide the submodule” request — the name similarity is coincidental. (Confirmed on ai-config’s own session history: sliding the `macros` submodule pin in `d-morrison/rme`\#983 and `ucdavis/epi204`\#361 was done by hand, `slide-tag` doesn’t apply.)

Back to top
