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

Advanced R makes the same move a formal step of its optimization procedure
--- [Checking for existing
solutions](https://adv-r.hadley.nz/perf-improve.html#already-solved) sits
between organizing the code and changing any of it --- and adds a practical
warning about why the search is hard:

> the challenge is describing your bottleneck in a way that helps you find
> related problems and solutions.
> Knowing the name of the problem or its synonyms will make this search much
> easier.
> But because you don't know what it's called, it's hard to search for it!

So a search that came up empty is weak evidence when the thing being
searched for has an established name you happen not to know.
Ask someone before concluding nothing exists, and record what you searched
for --- the terms are what the next reader needs in order to extend the
search rather than repeat it.
The section also asks for something the build-vs-use decision below needs:
record *every* candidate found, not only the ones that look best at first
glance, since a slower or partial option can turn out to be the easier one
to build on.

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

**Close the loop once the port lands: retire the local copy, don't just
leave both.** Flagging the port isn't the finish line --- once gha ships
the shared capability, migrate the original consumer to it and delete the
local duplicate, or the two copies drift independently (a fix to one
never reaches the other). (gha#300 shipped `check-new-line-breaks` as a
composite action + reusable workflow; ai-config#702/#703 then retired
`scripts/check-new-line-breaks.py` in favor of calling
`d-morrison/gha/.github/workflows/check-new-line-breaks.yml@v2` from
`validate.yml`.)

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

## Check the upstream's CURRENT state before writing a fix for it

DRW's search step is usually framed around features.
It applies just as much to **bug fixes in someone else's repo**, where the
thing already built may be the fix itself.

The trap is specific to how a consumer sees an upstream: you read the
version you are pinned to.
A repo consuming `@v2` (or any moving tag, or a vendored copy) reads a
*snapshot*, and reasoning from it as though it were `main` produces a
confident patch for a bug fixed weeks ago.
Nothing in the snapshot signals that it is stale.

So before diagnosing, reproducing, or patching an upstream bug: fetch
that repo's default branch and grep for the symptom.
Two lines, and the usual outcome is either "already fixed, just slide the
tag" or a much better-informed patch.

Two further reasons this is worth the check rather than a formality.
The upstream fix has usually been through that repo's own review, so it
covers cases an outside patch written from the symptom will miss.
And when it *is* already fixed on `main` but not in the tag you consume,
the real deliverable is a tag slide or pin bump --- a different, smaller
action than the patch you were about to write.

(`UCD-SERG/serocalculator#614`, 2026-07-27: a raw `gh pr comment` heredoc
posted as a review body was diagnosed against the `@v2` snapshot, then
reproduced and patched locally. `d-morrison/gha`'s `main` already carried
the fix (`gha#318`), and it handled three cases the local patch did not:
`<<-` heredocs, unquoted tags, and CRLF transcripts --- that last one a
bug the local patch would have shipped, since normalizing `\r` only for
the terminator comparison leaves stray carriage returns in the posted
body. `v2` had since been slid, so consumers already had it.)

**The mirror direction, where the remedy above becomes the cause.**
Everything above assumes you are fixing a bug going forward, so reading
`main` is right.
When you are instead explaining a **run that already happened**, reading
`main` is the mistake: the run used whatever ref it was pinned to, and a
file read at `main` may describe code that never executed.

What makes this survive scrutiny is that no individual step is wrong.
The file is real, you read it rather than recalling it, and you quoted it
correctly, so every "did you actually check this?" prompt fires and passes.
The error is entirely in the **join**: the run belongs to one ref, the file
was read at another, and neither artifact mentions the other.
Nothing you are looking at can tell you the evidence and the subject are
different versions of the same thing.

So split the trigger by what you are producing.
A fix for the future reads the default branch.
An explanation of a past run resolves that run's ref **first**, then reads
the file at it.
For a reusable workflow, `referenced_workflows[].sha` on the run gives the
resolved commit directly (`actions_get`, `get_workflow_run`); for a pinned
action, the caller's own `uses:` line at that commit does.
Then `git show REF:path`, never the working tree's current branch.

Note the conclusion can survive the join being wrong, which is why getting a
plausible answer is not evidence that the ref was right.

- **Do:** resolve the ref a run used before opening any file from the
  dependency, and read the file at that ref.
- **Do:** keep reading the default branch when the deliverable is a fix
  rather than an explanation.
- **Don't:** quote a dependency's `main` as the mechanism behind a run pinned
  to a tag, however carefully you read it.
- **Don't:** treat a mechanism that explains the observed behaviour as
  confirmation that you read the right version.

(`Morrison-Lab/gha#391` / `Morrison-Lab/ai-config#984`, 2026-07-31: a review
guard's control flow was quoted from `check-review-execution.sh`, read from a
local `gha` checkout sitting on `main`, and published as the explanation for
CI failures in a repo pinned at `@v1`.
`git cat-file -e v1:.github/workflows/scripts/check-review-execution.sh`
fails and the `v2` equivalent succeeds, because at `@v1` the guard is inline
in `claude-code-review.yml` and carries no verdict test at all.
The conclusion held anyway, since both versions fail an errored run without
asking whether a verdict was posted, which is precisely why the wrong ref
went unnoticed.
The attribution was retracted on gha#391.)

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
