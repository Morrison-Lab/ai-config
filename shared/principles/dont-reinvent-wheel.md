Don't reinvent the wheel (DRW).
Before implementing a new function or feature, check that it hasn't
already been done — either in one of our own repos, or in a trustworthy
external source we could depend on instead.
Prefer reusing, depending on, forking, or contributing to an existing
implementation over building a new one from scratch.

This is both a development principle (run the check before writing) and
a review principle (flag hand-rolled equivalents in a diff — see "In
review" below).

## Where to look

- **Our own repos**: the lab packages (e.g. `{bcs}`, `{ettbc}`), the
  shared reusable workflows and actions in `d-morrison/gha`, and this
  `ai-config` corpus's skills and fragments.
  Packages can depend on each other, so reuse across our repos is fine.
- **Trustworthy external sources**: base R; the
  [r-lib](https://github.com/r-lib) and
  [tidyverse](https://github.com/tidyverse) organizations; a focused,
  well-maintained CRAN package; [rOpenSci](https://github.com/ropensci);
  CRAN Task Views for topic surveys; and the analogous ecosystems
  elsewhere (PyPI, npm, the GitHub Actions marketplace).

## Placing new tooling, not just searching for existing tooling

DRW also runs forward, not just backward: when the tooling you're about
to *build* is generic CI/lint/project infrastructure rather than
agent-behavior/config, ask whether it belongs in `d-morrison/gha`'s
reusable-actions layer instead of ai-config's own `scripts/` --- even
when the immediate need surfaced from ai-config's own corpus.
`scripts/` should stay scoped to checks specific to *this* repo's own
content (its skills/memories prose, its manifest structure); a
capability other project repos would also want (a semantic-line-break
drift checker, a non-ASCII-punctuation scanner) belongs in gha so every
consumer repo benefits, not just ai-config. Building it in ai-config
first is fine when the immediate need is local, but check gha for an
existing equivalent before assuming none exists, and flag a port when
none does exist. (ai-config#682/#684, 2026-07-24: built
`scripts/check-new-line-breaks.py` in ai-config first, since the
drift it caught was in ai-config's own corpus; a direct check of gha's
`lint-markdown`/`lint-qmd` afterward confirmed neither has an
equivalent, even though every gha-consuming Quarto/R-package repo with
MD013 disabled for the same corpus-drift reason would benefit from the
same diff-scoped check.)

The [`prefer-upstream`](../../skills/prefer-upstream/SKILL.md) skill is
the search procedure (where to look per ecosystem, and the
build-vs-use decision criteria);
[`prefer-packaged-functions`](../coding/prefer-packaged-functions.md)
is the R-function special case of this principle.

## Prefer forking or contributing over re-building

When an existing external source is close but not exact — it does most
of the job but is missing the piece we need — prefer extending it over
re-building the functionality from scratch:

- **Contribute upstream** when the missing piece is general-purpose:
  a PR adding it, or an issue with a reprex, per
  [`upstream-issues`](../workflow/upstream-issues.md) — read the
  upstream repo's contribution policy first, and never post to an
  external repo autonomously.
- **Fork** when we need the change now, or the change is too
  lab-specific for upstream to want.
  Still offer the general parts upstream where they fit, so the fork
  can eventually retire instead of becoming a permanently diverged
  maintenance burden.
- **Borrowing code** (copying rather than depending) goes through the
  [`scout-peers`](../../skills/scout-peers/SKILL.md) license gate:
  verify the license first, record attribution in `CREDITS.md`.

Re-building from scratch is the last resort, for when nothing close
enough exists or every existing option is unfit.

## When rolling our own is right

This is a default, not an absolute rule.
Build custom when the problem is genuinely project-specific, the
existing option is unmaintained or license-incompatible, its API is
wrong for the need, or the dependency is far heavier than the job
(a heavy package for a one-liner).
When you do build custom, note in the PR (or a code comment) that you
checked and nothing fit, so the next reader doesn't re-run the search
— and so the reviewer's DRW check below has its answer up front.

## In review

For each new function or feature a diff adds, ask whether that
functionality already exists in our own repos or a trustworthy
dependency.
A hand-rolled equivalent of something a maintained package (or our own
code) already provides is a review finding, the same weight as any
other standing review check: name the existing implementation, and
propose depending on, forking, or contributing to it instead.
Accept the custom version when one of the escape hatches above
genuinely applies — and ask for the "checked, nothing fit" note when
it's missing.
