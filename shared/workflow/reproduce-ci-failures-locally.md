# Reproduce a CI failure locally before pushing again

When a CI build fails and the same step passes in a local single-page render, stop pushing.
Each push costs a full CI run, and a guess that does not reproduce the failure tests nothing you can read.

## The rule

- Reproduce the failure first, with the CI's tool versions, extensions, formats and command.
  For a Quarto site, that means the whole-project `quarto render` in every format the CI builds, not one page in one format.
- Bisect locally, then push once.
- Treat each CI-only difference as a suspect: a restored cache (such as `_freeze`), environment variables, heap limits, the format list, and the runner's package versions.
- If the failure does not reproduce locally, say so, and name the CI-only differences you could not test.
  Then use one planned CI control, such as removing the suspect file or bypassing the cache, instead of a string of guesses.

## Cheap ways to test the cache theory

- A repo's label that bypasses the cache for one run (`clear freezer` in the notes repos) is the cheapest test.
  It leaves the source unchanged.
- A control commit that removes only the suspect include shows whether the content is the trigger at all.
  Revert it afterwards.

## Checks before trusting a local reproduction

- Confirm the local render ran every format the CI runs.
  A PDF step that stops for lack of TeX ends the run before any HTML is built, so a "pass" or "fail" says nothing.
  Skip the format the way the CI does.
- A JavaScript out-of-memory error locally is a different failure from the CI's, so raise the heap and run again.
- A `git commit -a` after a local render sweeps in the working-copy changes the pre-render scripts made.
  Stage the file you meant.

## Example

On `Morrison-Lab/mds` #623 (2026-11-04) a new 3D figure failed the CI render five times in a row, with a Quarto filter error ("got table") at the last file.
Every local single-page render passed, and each guess was pushed blind.
Afterwards a local full-project render also passed, a control commit without the include built green, and the same head built green again with the freeze cache bypassed.
So the restored cache, not the figure, caused the failure.
The coordinator's correction is the origin of this rule: reproduce first, then push.

See also [`check-the-renders`](check-the-renders.md), whose stale-freeze-cache case is the same family, and [`check-before-pushing`](check-before-pushing.md).
