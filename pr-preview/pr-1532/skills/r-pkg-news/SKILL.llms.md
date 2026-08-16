# r-pkg-news

Drafts a new `NEWS.md` entry for an R package, matching the package’s existing entry style and format — as opposed to `r-pkg-spellcheck`, which only spellchecks `NEWS.md` text that’s already there and never helps author it.

**Why this exists:** most R packages track user-facing changes in `NEWS.md`, one entry per release or per notable change, but the exact format (bullet style, whether entries are grouped under a version heading, whether they reference issue/PR numbers) varies package to package. Writing a new entry that doesn’t match the existing style creates visible inconsistency the next release notices.

## Procedure

1.  **Confirm this is an R package.** Check that `DESCRIPTION` exists at the repo root, and that `NEWS.md` (or `NEWS`) exists. If either is missing, skip — this skill doesn’t apply, or the package needs to add `NEWS.md` first (a one-line file with a version heading and no entries is enough to start).

2.  **Read the existing style.** Look at the last 2–3 entries in `NEWS.md` and note:

    - Whether entries sit under a version heading (`# pkgname 1.2.3`) that’s already there for the in-progress version, or need a new one.
    - Bullet format (`*`, `-`), sentence case vs. lowercase lead word, whether entries end with a period.
    - Whether entries cite the author, an issue number, or a PR number (e.g. `(#123)`, `(@username)`), and where in the sentence that citation goes.

3.  **Gather what changed.** Pull recent commits since the last tagged release (`git log <last-tag>..HEAD --oneline`) or the PR description supplied by the user, and identify the user-facing changes worth an entry — skip pure-internal refactors, CI-only changes, and typo fixes that don’t affect behavior unless the project’s own style includes those too (check step 2’s precedent).

4.  **Draft the entry** matching the style read in step 2, one bullet per user-facing change, in plain, direct language (what changed and why it matters to a user — not an internal implementation narrative). Add it under the current in-progress version heading, creating that heading if this is the first entry for the next version.

5.  **Spellcheck the new text** — hand off to [`r-pkg-spellcheck`](../../skills/r-pkg-spellcheck/SKILL.llms.md) before finishing, since new NEWS.md prose is exactly the case that skill exists to check before `git push`.

## Related

- [`r-pkg-spellcheck`](../../skills/r-pkg-spellcheck/SKILL.llms.md) spellchecks `NEWS.md` text against `inst/WORDLIST`; run it after drafting a new entry here.
- [`r-pkg-check`](../../skills/r-pkg-check/SKILL.llms.md) and [`r-pkg-cran-checklist`](../../skills/r-pkg-cran-checklist/SKILL.llms.md) both expect an up-to-date `NEWS.md` entry for the release under check — this skill is the step that produces it.

Back to top
