# A red main is a request for the fix

When a check on `main` fails after a change an agent merged or enabled, fixing it is already requested.
Find the root cause and open the fix without waiting for the user to say so (Ezra, 2026-10-16, sds#249).

This holds even when the failure is a pre-existing defect that a new check exposed.
The check exists to be green, so the defect it found is the work.

- **Do:** read the failing source lines, find the cause, and fix it where it lives, in a shared macro or a workflow when that is the root, and on the pages otherwise.
- **Do:** open the fix PRs, subscribe to them, drive them to fully clean, and report the links.
- **Do:** file or update the tracking issue first, so another session sees the work is claimed.
- **Don't:** post "which fix do you prefer?" and stop.
  Pick the root-cause fix, say which, and keep going.
- **Don't:** treat the missing merge grant as a reason to wait on the fix.
  Merging still needs the user's `mwc` where the repository has no standing grant, but the PR does not.

Example: the new equation-render check found 80 "Double subscripts" errors on sds `main` ([sds#249](https://github.com/Morrison-Lab/sds/issues/249)).
The cause was one macro, `\vecf`, whose `\underset` output took the subscript.
The root-cause fix was one change in the macros repository ([macros#172](https://github.com/Morrison-Lab/macros/pull/172)), not 80 edits on the pages.
