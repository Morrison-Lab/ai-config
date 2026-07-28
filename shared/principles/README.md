# Big-picture principles

The central home for our big-picture development principles.
Each principle gets a short statement here plus links to the specific
rules and skills that operationalize it; a principle with enough depth
gets its own fragment file in this directory.

The specific rules stay authoritative for their own details.
This catalog is the index: it names each principle and shows how the
principles relate, so a new rule can be filed under the principle it
serves instead of floating free.

## The goals the principles serve

The catalog has three layers: these **goals** are the *why*, the
**principles** below are the *how*, and the specific rules and skills
each principle links to are the *what*.
We build code and prose that is:

- **Valid** — correct in logic, math, and claims — and **easy to
  externally validate**: tested, checkable by deterministic instruments
  (see [`algorithmatize-checks`](../workflow/algorithmatize-checks.md)),
  and cited so a reader can verify without re-deriving.
- **Reproducible** — a rerun from the same inputs yields the same
  result: pinned dependencies (`renv` lockfiles), controlled randomness
  (seeds via `withr::with_seed()`), and scripted pipelines rather than
  by-hand steps; the
  [`reproducibility-audit`](../../skills/reproducibility-audit/SKILL.md)
  skill runs the sweep.
- **Highly functional** — it does the whole job it exists for, not an
  approximation of it.
- **Reliable** — behaves correctly on every run, not just the demo run:
  edge cases handled, failures surfaced early and clearly rather than
  silently swallowed, and no flaky tests or race-prone automation.
- **Secure and private** — no leaked secrets or PHI (the `check-phi`
  capability in
  [`d-morrison/gha`](https://github.com/d-morrison/gha) scans for it),
  third-party dependencies vetted and SHA-pinned, and borrowed code
  license-gated with attribution
  ([`scout-peers`](../../skills/scout-peers/SKILL.md)).
- **Efficient** — economical with compute, memory, and people's time
  (CI minutes, review rounds); performance tuning beyond that needs a
  demonstrated hot spot, not speculation.
  [`use-memoisation`](../coding/use-memoisation.md) is that trade in
  miniature: it buys speed with memory, so it needs the hot spot too.
- **Maintainable** — the next change is cheap: one home per fact, small
  units, no accumulated complexity debt.
- **Extensible** — new capability slots in without rework, because the
  units are composable and the abstractions are real ones.
- **Human- and AI-readable** — a reader (including future us) can
  follow it without archaeology: plain prose, idiomatic code.
  Equally legible to AI agents: conventions stated where agents load
  them (`CLAUDE.md`, shared fragments), greppable naming, and context
  that doesn't depend on out-of-band knowledge.
- **Reusable** — built once, usable across our repos; and conversely,
  built on what already exists rather than duplicated (DRW).

When a proposed rule or review finding doesn't clearly serve one of
these goals, question the rule rather than the code.

## KISS — keep it simple, stupid

Prefer the simplest construct that does the job, and treat added
complexity as a cost that needs justification.
The umbrella statement lives in `CLAUDE.md` ("KISS is the umbrella
principle"); when a case arises that no enumerated rule covers, apply
KISS directly.

Operationalized by:
[`challenge-unnecessary-complexity`](../workflow/challenge-unnecessary-complexity.md)
(the review side),
[`avoid-nesting`](../coding/avoid-nesting.md),
[`tidy-code`](../coding/tidy-code.md), and
[`per-operation-grouping`](../coding/per-operation-grouping.md).

## YAGNI — you aren't gonna need it

Build for the requirement in front of you, not a speculated future one.
Speculative generality — an abstraction layer with one user, a config
option nothing sets, a general result no caller needs — is complexity
debt taken on before any payoff.
KISS's counterpart on a different axis: KISS bounds *how simply* to
build what's needed; YAGNI bounds *whether* to build it at all.

Operationalized by:
[`challenge-unnecessary-complexity`](../workflow/challenge-unnecessary-complexity.md)
(flags an unnecessarily general result when a simpler equivalent
exists) and the premature-abstraction caution in "How the principles
relate" below.

## DRY — don't repeat yourself

Every fact and every piece of logic gets exactly one home; a second
copy is a sync bug waiting to happen, because updating one copy should
have updated the other and eventually won't.
Also known as the single-source-of-truth rule.

Operationalized by:
[`challenge-redundant-content`](../workflow/challenge-redundant-content.md)
(the review side),
[`reuse-docs-and-args`](../coding/reuse-docs-and-args.md),
[`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md),
and the `find-overlap` / `consolidate-skills` / `consolidate-memory`
skills (the corpus-wide sweep).

## DRW — don't reinvent the wheel

Before implementing a new function or feature, check whether it has
already been done — in one of our own repos, or in a trustworthy
external source we could depend on, fork, or contribute to instead.

Full statement: [`dont-reinvent-wheel`](dont-reinvent-wheel.md).
Operationalized by:
[`prefer-packaged-functions`](../coding/prefer-packaged-functions.md)
(the R-function special case),
[`use-memoisation`](../coding/use-memoisation.md) (one instance of it:
cache with `memoise::memoise()`, don't hand-roll a cache environment),
the
[`prefer-upstream`](../../skills/prefer-upstream/SKILL.md) skill (the
search procedure), and the
[`scout-peers`](../../skills/scout-peers/SKILL.md) skill (license-gated
borrowing from peer repos).

## Modularity — small, single-purpose, composable units

Favor small, single-purpose functions and reusable units over long
monolithic blocks, so each piece can be found, tested, documented, and
reused on its own.
The formal names: the single-responsibility principle and separation of
concerns.

Operationalized by:
[`one-function-per-file`](../coding/one-function-per-file.md),
[`decompose-to-functions`](../coding/decompose-to-functions.md),
[`configurable-parameters`](../coding/configurable-parameters.md) (a unit
composes across call sites only when what varies between them is exposed
as a parameter, not buried as a literal), and the
"highly modular and idiomatic" review priorities in
[`gha`'s `CLAUDE.md`](https://github.com/d-morrison/gha/blob/main/CLAUDE.md)
(favor small, single-purpose functions over long monolithic blocks;
flag duplicated logic, functions that do too much, and steps that
should be extracted and named).

## Least astonishment (POLA)

Prefer the construction a knowledgeable reader expects: idiomatic R
(tidyverse), idiomatic YAML/GitHub Actions, and naming and structure
that match the surrounding file and the ecosystem's conventions.
Surprise is a cost paid by every future reader, so a clever construct
has to earn it.

Operationalized by:
[`tidy-code`](../coding/tidy-code.md) and the "idiomatic" half of the
review priorities in
[`gha`'s `CLAUDE.md`](https://github.com/d-morrison/gha/blob/main/CLAUDE.md)
(the Modularity entry above carries the "modular" half), following the
[SERG lab manual](https://ucd-serg.github.io/lab-manual/) and the
[tidyverse style guide](https://style.tidyverse.org/).

## Purity — no hidden side effects

Prefer pure functions: outputs determined by inputs, with no mutation
of global state and no I/O buried inside computation.
Isolate the side effects a program genuinely needs (file writes,
network, RNG, options) at its edges, and restore any temporarily
changed state rather than leaking it — e.g. `withr::with_seed()`
restores the RNG stream (the example in
[`prefer-packaged-functions`](../coding/prefer-packaged-functions.md))
and `withr::local_options()` restores session options.

In review: flag `<<-`, functions that read or write globals they don't
own, and computation interleaved with I/O that a pure core plus a thin
I/O shell would separate.

## Self-documenting code

Let naming and structure carry the intent: descriptive object and
function names, small named functions in place of comment-labeled
blocks, and interface documentation (roxygen) on every function.
Reserve comments for what code cannot say — a constraint, a why, a
citation — not a restatement of what the next line does.

Operationalized by:
the [SERG lab manual's coding-style conventions](https://ucd-serg.github.io/lab-manual/coding-style.html)
(naming, comments),
[`decompose-to-functions`](../coding/decompose-to-functions.md)
(a named function replaces a comment-labeled chunk), and
[`reuse-docs-and-args`](../coding/reuse-docs-and-args.md)
(inherited docs stay true to the code they describe).

## Fail fast — no silent failures

Detect bad state as early as possible and stop with a clear error,
rather than proceeding and letting the failure surface later — or
never — as silently wrong output.

Full statement: [`fail-fast`](fail-fast.md), including the review-side
check (flag swallowed errors, silent fallbacks, and CI steps that
can't fail).

## Algorithmatize checks — instruments over judgment

Never spend LLM or human reasoning on a check a deterministic
algorithm can decide: build the instrument once, wire it into CI, and
let reviewers consume its verdicts.
Serves the "easy to externally validate" goal directly.

Full statement:
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md)
(predates this catalog, so it lives in `shared/workflow/`).

## The 3Rs lens — reduce, reuse, recycle

The environmental mnemonic maps cleanly onto the catalog, and makes a
compact checklist to run over any new piece of work:

- **Reduce** — write less: build only what's needed (YAGNI), in the
  simplest form that works (KISS), and prune what no longer earns its
  place (the `tidy` and `simplify` skills).
- **Reuse** — don't rebuild what exists: depend on our own repos or
  trustworthy upstream (DRW), keep one home per fact (DRY), and
  inherit docs, arguments, and workflows instead of retyping them.
- **Recycle** — when something close-but-not-exact exists, transform
  it rather than discarding it: fork or contribute upstream (DRW's
  fork-or-contribute preference), borrow with the license gate and
  attribution ([`scout-peers`](../../skills/scout-peers/SKILL.md)),
  extract inline logic into reusable units, and consolidate
  overlapping content (`consolidate-skills` / `consolidate-memory`).

This is a lens over KISS/YAGNI, DRY, and DRW — not a separate
principle; use whichever framing communicates better in a given
review.

## How the principles relate — and where they pull against each other

KISS is the umbrella for the complexity-cost family: most of the
specific coding rules are special cases of "the simplest construct that
does the job".
YAGNI is its what-to-build counterpart, bounding scope the way KISS
bounds construction.

DRY and modularity overlap KISS but are **siblings, not subsets**.
Deduplicating or decomposing adds indirection — an extracted
abstraction, another file, another call hop — that a narrow KISS
reading resists, in exchange for one-home maintenance, testability,
and reuse.
When they conflict, judgment decides case by case: don't abstract
prematurely (a wrong abstraction costs more than a little duplication;
wait for a pattern to actually recur before extracting it), but once
the same fact or logic has two hand-maintained copies, DRY wins.

DRW is the outward-facing sibling: KISS, DRY, and modularity govern the
code we write; DRW asks first whether we should be writing it at all,
or reusing, forking, or contributing to something that already exists.

The remaining principles serve the goals directly: least astonishment
and self-documenting code serve readability the way modularity serves
maintainability; purity and fail-fast serve reliability — a pure core
is easier to test, and a loud failure is easier to catch than a silent
one; algorithmatize-checks serves external validatability.
The 3Rs lens sits above the families as a mnemonic, not a member.

## Adding a principle

When a new big-picture principle emerges (from review feedback, a
correction, a recurring pattern), add it here: a short statement, links
to whatever operationalizes it, and — if it needs more than a
paragraph — its own fragment file in this directory, wired into
`CLAUDE.md` with an `@shared/principles/...` reference.
