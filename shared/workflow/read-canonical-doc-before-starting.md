When a repo's own `CLAUDE.md` (or an equivalent short orientation file) names
a fuller document as the actual authority --- `.github/copilot-instructions.md`,
`CONTRIBUTING.md`, a linked style guide --- read that fuller document
**before starting work**, not merely before pushing.
`CLAUDE.md` itself is frequently a short pointer that says as much in its own
opening lines; treat that pointer as a thing to follow immediately, not a
fact to file away.

## Why the short file is not enough on its own

A short orientation file exists to be readable in one pass, so it summarizes
rather than enumerates.
The pre-PR requirements that actually gate CI --- a version-bump convention,
a changelog-fragment format, a required label, a spellcheck wordlist --- live
in the document the short file defers to, and a session that stops at the
short file never sees them.
Nothing about that omission is visible from inside the short file: it reads
as complete, because summarizing is what it is for.

The cost lands at the worst possible time.
A session that skips the canonical doc writes its diff, pushes, and only
then learns about the missing requirement from a **red CI check** ---
converting a one-line addition into a second commit and a second review
round for something that was knowable from the first read.

## Distinct from ardi's pre-push self-review

[`ardi`](ardi.md)'s "Self-review against the project's own stated
conventions before every push" section governs a different moment: it
assumes the conventions are already known, and asks whether the diff about
to be pushed actually follows them.
This rule governs the moment before that one even applies --- reading the
canonical doc **at the start of work**, so there is something to self-review
against by the time a push is imminent.
A session that has never read the canonical doc has nothing to check its
diff against, however carefully it re-reads the diff itself.

## Front-load the pre-PR housekeeping

Once the canonical doc is read, fold its housekeeping requirements into the
**first** commit rather than the one that answers a failing check:

- an R package's `NEWS.md`/changelog-fragment entry and `DESCRIPTION`
  dev-version bump (see [`memories/r-quarto.md`](../../memories/r-quarto.md)'s
  "R-package PR CI gates" section for the mechanics, which vary by repo),
- a required label or PR-template field,
- a formatting or spellcheck convention the short file never mentions.

- **Do:** read the repo's full canonical contributor doc before the first
  edit, whenever the orientation file names one.
- **Do:** put every pre-PR requirement the canonical doc names into the
  first commit, not a follow-up fix for a red check.
- **Don't:** treat a short `CLAUDE.md` as sufficient once it has pointed
  elsewhere for the details --- the pointer is the instruction, not a
  courtesy.
- **Don't:** wait for CI to enumerate a repo's own requirements; CI is the
  fallback for a doc that went unread, not the intended discovery path.

(`UCD-SERG/serocalculator#661`, 2026-08-10: `serocalculator/CLAUDE.md` opens
by naming `.github/copilot-instructions.md` "the **source of truth** for
repository-specific style and workflow" and calling itself "a short
orientation."
Only the short file was read before work began, so a docs-only PR shipped
with no `DESCRIPTION` dev-version bump, and `version-check.yaml` caught it
--- `copilot-instructions.md` line 645 states the requirement outright:
"**ALWAYS** increment dev version number to be one ahead of main branch
before requesting PR review."
A second commit fixed the CI failure that a first read would have avoided.

The rule itself already existed, word for word, at
[`memories/preferences.md`](../../memories/preferences.md)'s "Before opening
a PR, read the repo's own agent/contributor instructions" bullet.
It went unconsulted because `memories/` files are not auto-loaded into a
session's context the way `CLAUDE.md` and its `@shared/...` fragments are
--- see [`keep-checkouts-fresh.md`](keep-checkouts-fresh.md)'s "a bare
citation is invisible to an agent that doesn't take the extra step of
reading the fragment on demand."
This fragment exists so the rule is wired into the auto-loaded surface
instead of sitting one grep away from every session that needed it.)
