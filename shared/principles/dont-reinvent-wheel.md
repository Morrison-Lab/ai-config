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
  shared reusable workflows and actions in `the repository owner/gha`, and this
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
agent-behavior/config, ask whether it belongs in `the repository owner/gha`'s
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
`the repository owner/gha/.github/workflows/check-new-line-breaks.yml@v2` from
`validate.yml`.)

The [`prefer-upstream`](../../skills/prefer-upstream/SKILL.md) skill is
the search procedure (where to look per ecosystem, and the
build-vs-use decision criteria);
[`prefer-packaged-functions`](../coding/prefer-packaged-functions.md)
is the R-function special case of this principle.

## A stale, un-migrated local copy is the least reliable place to fix a bug

Before patching a bug in a repo's own CI/workflow file --- or any other
piece of shared-shaped infrastructure: a lint script, a review harness,
a build pipeline --- ask whether that file duplicates a canonical shared
implementation the repo just never migrated to.
This is a sharper case than the ordinary DRW search above: the duplicate
is not a candidate you might build, it is one you are about to spend
real diagnostic effort fixing *in place*, one file over from where the
close-the-loop paragraph above already warns you to look.

Distinguish it from "Check the upstream's CURRENT state" below: that
section is about a bug in code we do **not** own, read through a stale
pinned snapshot.
This is about a bug in code we **do** own, that duplicates something we
also own elsewhere and never migrated to consume.

The tell is structural, not something you have to search for.
Check `.github/workflows/` (or the equivalent) for other files that
already `uses: .../gha/.github/workflows/...@v2` --- a repo that has
migrated *some* capabilities to a shared reusable workflow and left
others standalone is the strongest signal, because the standalone ones
are exactly the ones nobody has revisited since the shared version
absorbed that capability.

Read the candidate canonical version's own comments before writing a
fix.
A mature reusable workflow accumulates its hard-won incident history
directly in its source --- issue numbers, root causes, mechanisms tried
and rejected --- and reading it is usually faster than re-diagnosing
from the symptom.
It can also reveal that your first-guess mechanism is wrong before you
commit to it.

- **Do:** before patching a bug in a repo's own CI/workflow file, check
  whether the repo pins a shared-workflow repo and whether that repo has
  a same-purpose reusable workflow.
- **Do:** read the canonical version's own comments for a prior incident
  matching your symptom before diagnosing from scratch.
- **Don't:** patch a stale local copy in place without first checking
  whether it should be migrated to the canonical version instead.
- **Don't:** trust your own plausible-sounding first-guess mechanism over
  a canonical version's documented, tested history of the same failure.

(Morrison-Lab/wai#49/#50, 2026-08-08: diagnosed and patched a
`claude-review` stub bug in wai's own hand-rolled `claude-code-review.yml`
--- adding `Task` to its allowedTools --- before checking whether wai
even used `Morrison-Lab/gha`.
It does, for four other workflows.
gha's own canonical `claude-code-review.yml` turned out to be a direct
port FROM this exact file, one of three source repos its own header
names, with 15+ documented incidents fixing the same stub-review problem
through a different, more robust mechanism.
The `Task` fix was verified empirically to be a no-op; the actual fix
was migrating to the canonical version.)

Both this section and the close-the-loop paragraph above wait for an event --- a bug to patch, or a capability you just ported.
[`upgrade-to-gha`](../workflow/upgrade-to-gha.md) carries the unprompted case, where nothing is broken and the duplicate has simply sat there, and it reuses the structural tell above as one of its four candidate conditions.

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
reproduced and patched locally. `the repository owner/gha`'s `main` already carried
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

## A constraint your own change authored is not evidence against an upstream

The escape hatches above are all statements about the world: nothing close
enough exists, the API is wrong, the dependency is too heavy, the package is
unmaintained.
Each is a fact you could have found before starting.

A different kind of reason shows up in practice and reads exactly like those:
a constraint the change itself created.
The script has to run somewhere the package is not installed.
The helper cannot take a new dependency because this PR decided it would not.
The CI job installs nothing, so nothing can be imported.
Reasoning from one of those is circular --- the change creates the constraint,
and the constraint then licenses the change --- and the circle closes inside a
single diff, so no reviewer reading that diff sees anything missing.

**The circularity is invisible because the constraint is real and checkable.**
This is what makes the failure survive scrutiny rather than a sloppier one.
The CI job genuinely installs nothing, and you can verify that against the
workflow file in one read, so the verdict feels measured and empirical rather
than convenient.
Every "did you actually check this?" prompt fires and passes.
The question never asked is whether the measured constraint should have
existed at all, and that is a question about the assignment rather than about
the facts --- see
[`challenge-the-assignment`](../workflow/challenge-the-assignment.md).

So before a DRW verdict rests on a constraint, classify it:

- **External** --- a platform limit, an upstream API, a license, a policy, a
  requirement from outside our control.
  Not merely outside *this* change: a constraint an earlier change of ours
  chose is still self-imposed.
  Reasoning from an external one is fine.
- **Self-imposed** --- a choice made in this change, or in an earlier one of
  ours.
  Challenge it, and usually relax it: add the dependency, install it in CI,
  widen the environment.
  Only after the relaxation is shown to be genuinely unavailable does the
  constraint become evidence.

**A limit in a repo we administrate is self-imposed, however far upstream it
sits**, and the word "upstream" in the external list above is what obscures
that.
A shared action, a reusable workflow, a lab package: each is upstream of the
change in front of you and none of them is outside our control, so a
compromise accepted to fit one is a decision rather than a requirement.

The near-miss is sharper than the ordinary case, because the constraint is
genuinely external **to this repository**.
Nothing about the verification is wrong --- the shared tool really does support
only the options it supports, and one read of its source confirms that --- so
the classification passes every empirical check while landing in the wrong
bucket.
It also arrives disguised as scope discipline: extending the shared tool looks
like widening the task, and accepting its limit looks like staying inside it.

What settles the classification is who can merge a change to the tool.
A repo we administrate takes a PR from us directly, so relaxing the constraint
costs one more PR on a queue we control, where a genuine external upstream may
decline it or never look at it at all.
That asymmetry is the whole difference, and it is a question about the
repository rather than about the constraint --- so ask it before reaching for a
workaround.
[`upstream-issues`](../workflow/upstream-issues.md) governs what to do once you
have decided to send something upstream; it deliberately applies the same
courtesy to repos we administrate, so it settles the etiquette rather than this
classification.

Relaxing it is normally cheap, which is the other half of why the excuse does
not hold: adding a package to a CI job is a smaller change than the
reimplementation it was being used to justify.
[`growth-mindset`](../workflow/growth-mindset.md) is the general form ---
go get the resource rather than accepting the limitation --- and this is that
rule at the moment it is hardest to apply, because here the limitation is
documented, verified, and yours.

- **Do:** name the constraint a "keep ours" verdict rests on, and say in the
  same sentence whether it is external or self-imposed.
- **Do:** relax a self-imposed constraint --- add the dependency, fix the CI
  job --- and re-run the DRW comparison against the relaxed environment.
- **Don't:** cite an environment your own change or an earlier one of ours
  chose as proof that an upstream package does not fit.
- **Do:** open the upstream PR when the constraint lives in a repo we
  administrate, and hold the consumer until it lands, rather than shipping the
  compromise the constraint would force.
- **Don't:** classify a limit as external because it sits in another
  repository; ask who can merge a change to it.

(Morrison-Lab/gha#563 / ucdavis/bcs#699, 2026-08-21: `gha`'s `assemble-news`
action hard-coded four changelog headings, and `bcs` was adopting its fragment
workflow with an eleven-section taxonomy of its own.
The plan proposed was to accept the flattening and file the mapping as a
nice-to-have, on the reasoning that the limit lived in another repository.
The maintainer's instruction was to send a `headings` input upstream first,
which took one PR against a repo we administrate.)
- **Don't:** treat having verified the constraint as having justified it.
  Confirming that the CI job installs nothing is the near-miss here: it looks
  like the check, and it answers a question nobody was disputing.

## Review is the wrong layer to catch a missed DRW pass

The line at the top of this fragment --- a development principle and a review
principle --- is easy to read as two chances at the same catch.
They are not equivalent, and the review half is the weaker one by a wide
margin.

A reviewer sees the functions in front of it and asks whether each is correct,
idiomatic, tested, and documented.
Asking instead whether the whole file should exist requires a search of an
ecosystem the diff never mentions, and nothing in the diff prompts it.
Four AI review rounds on the case below raised nothing, and the miss was
caught by a maintainer reading the merged package.

So treat the pre-write pass as the load-bearing one, and make it produce a
written record: run [`prefer-upstream`](../../skills/prefer-upstream/SKILL.md)
before writing a generic-looking helper, and put what you searched for and
what you found in the PR body.
The "checked, nothing fit" note that "When rolling our own is right" asks for,
just above, is that record.
Its absence is the one DRW signal a reviewer *can* see without doing the
search itself, which makes it worth flagging on its own.

- **Do:** run the DRW search before writing a helper that is not
  project-specific, and record the search terms and every candidate found in
  the PR body.
- **Do:** flag a missing "checked, nothing fit" note in review, as a finding
  in its own right.
- **Don't:** rely on review to catch a reimplementation --- a clean review is
  evidence that the code is good, not that it should exist.
- **Don't:** read a helper's small size as exempting it.
  The near-exact duplicates in the case below were one-liners, which is why
  writing them felt cheaper than searching.

(`ucdavis/bcs#641`, 2026-08-19: the PR merged 30 hand-rolled static-analysis
helpers into an R package --- an AST flattener, a symbol collector, a
top-level-definition index, a call-graph reachability closure, and small
call-introspection helpers `call_name`, `drop_call_head`, `is_call_to`,
`named_args`, and `unnamed_args`.
`rlang::call_name()` and `rlang::call_args()` are near-exact duplicates of two
of them, and `rlang` was already in the package's `Imports`.
`codetools::walkCode()` duplicates the AST walker, and `codetools` is a
recommended package that ships with R.
`foodwebr`, already in `Suggests`, and `funspotr` cover the call-graph and
per-file-symbol halves.
No DRW pass was run before writing them, and four AI review rounds did not
raise it.
The whole PR was reverted, at 66 files and 2010 deletions.
The DRW audit run afterwards returned "keep ours" for several helpers on the
grounds that the check script had to run on a bare R with no packages
installed, so `rlang` was unreachable --- a constraint that same PR had
authored.
The maintainer's answer was "don't make excuses, install the packages needed"
and "fix the CI job".)

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
