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
  [`loop-hygiene`](../coding/loop-hygiene.md) covers three common
  `for`-loop defects in R, two of which surface only on input a fixture
  rarely contains (an empty vector, a classed vector) while the third
  degrades quadratically as the input grows.
- **Secure and private** — no leaked secrets or PHI (the `check-phi`
  capability in
  [`Morrison-Lab/gha`](https://github.com/Morrison-Lab/gha) scans for it),
  third-party dependencies vetted and SHA-pinned, and borrowed code
  license-gated with attribution
  ([`scout-peers`](../../skills/scout-peers/SKILL.md)).
- **Efficient** — economical with compute, memory, and people's time
  (CI minutes, review rounds); performance tuning beyond that needs a
  demonstrated hot spot, not speculation.
  The [`measure-performance`](../../skills/measure-performance/SKILL.md)
  skill is how that hot spot gets demonstrated: profile first, then
  microbenchmark only what the profile implicated, then confirm the win
  survives end to end.
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
[`least-flexible-tool`](../coding/least-flexible-tool.md) (the general
form: prefer the construct that can do least),
[`avoid-nesting`](../coding/avoid-nesting.md) (and its prose/math
counterpart,
[`informal-definitions`](../writing/informal-definitions.md#this-is-kiss-applied-to-definitions-not-a-separate-rule) ---
don't nest one definition inside another, or name two concepts in one
heading with only one getting a citable id),
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

## Don't incur technical debt

When the right way to do the work in front of you needs a change you
have not made yet, make that change as part of the work.
The moment debt is incurred is the moment you defer a fix you have
already diagnosed, and a filed tracking issue records that debt rather
than paying it.
The rule bounds new work only: adding a copy to un-migrated code is
yours, the un-migrated code itself is not.

Full statement:
[`dont-incur-technical-debt`](dont-incur-technical-debt.md), including
the case where duplicated logic corrupts its own tests, and why this
does not conflict with YAGNI.
Operationalized by:
[`dont-reinvent-wheel`](dont-reinvent-wheel.md) (the search that comes
one step earlier) and
[`report-mistakes-proactively`](../workflow/report-mistakes-proactively.md)
(file the issue -- necessary, not sufficient).
Contrast with, rather than apply,
[`address-every-comment`](../workflow/address-every-comment.md)'s Defer
disposition: it governs a finding on code that already exists, and
licenses nothing about a defect inside the diff you are about to push.

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
[`gha`'s `CLAUDE.md`](https://github.com/Morrison-Lab/gha/blob/main/CLAUDE.md)
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
[`gha`'s `CLAUDE.md`](https://github.com/Morrison-Lab/gha/blob/main/CLAUDE.md)
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

Operationalized by:
[`restore-global-state`](../coding/restore-global-state.md) --- when a
mutation is genuinely required, register the restore beside it
(`on.exit(add = TRUE)`, or the `withr::local_*()` family) so it runs on
every exit path, including the ones that throw.

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
can't fail) and the rule that a handler must select a condition by its
class rather than by matching its message text.

Operationalized by:
[`type-stable-outputs`](../coding/type-stable-outputs.md) --- the same
principle applied to shape rather than to errors, since a type-unstable
call returns a plausible object of the wrong kind instead of failing ---
[`errexit-is-not-uniform`](../coding/errexit-is-not-uniform.md), which
covers the shell case where `set -e` silently stops applying, so a script
either aborts on an expected non-zero exit or fails to, depending on the
call site,
and [`regex-backtracking-pitfalls`](../coding/regex-backtracking-pitfalls.md),
which covers regular expressions that fail by backtracking exponentially
on non-matching inputs, and prescribes linear scans by construction.

## Algorithmatize checks — instruments over judgment

Never spend LLM or human reasoning on a check a deterministic
algorithm can decide: build the instrument once, wire it into CI, and
let reviewers consume its verdicts.
Serves the "easy to externally validate" goal directly.

Full statement:
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md)
(predates this catalog, so it lives in `shared/workflow/`).

## Automate everything -- and build the missing instruments

Never do by hand any work that can be automated.
Prefer deterministic, inspectable algorithms over model reasoning, and
where none exists, build one.
One principle with two faces: a **constraint** binding now (use the
instrument that exists) and a **goal** over time (build the one that
does not, so the constraint gets cheap to obey).
The observable trigger is recurrence -- after doing the same judgment
task twice, the third time is a tool.

Read "work" broadly.
Model judgment is the motivating case and the hardest to displace, but
the rule is about doing by hand what something else already computes,
which includes work carrying no judgment at all.
Three instances: model judgment displaced by an algorithm, data with an
external source of truth
([`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md)),
and a value the toolchain already derives from the artifact itself --
generated section numbers, a table of contents, a resolved
cross-reference.
The third is the easiest to miss, because nothing about typing a section
number feels like a decision, and it fails by silent divergence: while
the tool's generator stays off, the hand-written copy looks
authoritative.

Extends the entry above on two axes: **scope**, from verification to
agentic work generally, and **inspectability** -- an algorithm can be
read before it runs, diffed, and reproduced, which model reasoning
cannot.
Applies to every repo we work in, research code included, not only to
tooling.

Full statement: [`deterministic-tools`](deterministic-tools.md).
Operationalized by:
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) (the
checks-shaped special case), the `hooks/` directory (rules made
mechanical), and
[`skill-checklists`](../workflow/skill-checklists.md) (the pause-point
instrument where no script can decide).

## Don't use LLMs for algorithmic thinking --- use validated algorithmic software

Never use probabilistic language models for algorithmic operations:
counting, arithmetic, symbolic algebra, calculus (derivatives and integrals),
linear algebra, sorting, or mathematical proof verification.
Delegate computation to validated deterministic software (e.g. Computer Algebra
Systems, theorem provers, numerical packages, standard CLI tools),
or write and validate the software yourself before consuming its output.

Full statement: [`no-llm-algorithmic-thinking`](no-llm-algorithmic-thinking.md).

## Specific beats general

When two instructions, policies, configurations, or design rules apply
to the same decision, the narrower, more specific rule takes precedence
over the broader, more general one.
General policies define default baselines for the standard case;
specific instructions express intentional decisions for the concrete case at hand.
Explicit human user instructions in a session override general repository defaults,
narrow subsystem and file configs override repository-wide policies,
and targeted types and condition handlers beat generic catch-alls.

Full statement: [`specific-beats-general`](specific-beats-general.md).
Operationalized by:
[`fail-fast`](fail-fast.md) (specific condition classes over catch-alls),
[`least-flexible-tool`](../coding/least-flexible-tool.md) (narrowest construct for the job),
and [`challenge-the-assignment`](../workflow/challenge-the-assignment.md) (clarifying ambiguity vs resisting explicit direction).

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

Don't-incur-technical-debt is the *timing* member of that family.
KISS, DRY, and DRW each say what the right shape is;
this one says when you have to adopt it, which is now.

It looks like it contradicts YAGNI and does not, because the two
never fire on the same object.
YAGNI governs a speculated future requirement, whose defining
property is that you cannot yet tell whether it is real.
This governs a present, diagnosed defect in code you are writing now.
Feeling both at once usually means you are holding a suspicion rather
than a diagnosis, and the way out is to settle which it is.

Deterministic-tools, algorithmatize-checks, and no-llm-algorithmic-thinking
form a three-part family against model reasoning:
algorithmatize-checks governs *verification* and is the narrower
statement;
deterministic-tools governs the *work itself* and adds the argument
from inspectability and tooling over time;
and no-llm-algorithmic-thinking strictly forbids in-context algorithmic
computation (arithmetic, algebra, calculus, linear algebra, sorting,
proof verification), mandating execution of validated software.

Deterministic-tools also sits in the same relation to YAGNI that
don't-incur-technical-debt does, and resolves it the same way.
YAGNI governs a tool for a task that has happened once, whose recurrence
is still speculation.
The goal half fires only on the third occurrence, by which point
recurrence is observed rather than predicted.
Feeling both at once usually means the count is one or two, and the way
out is to wait rather than to argue.

Specific-beats-general governs precedence across the entire catalog:
it resolves conflicts between layers by establishing that explicit user
instructions outrank repository defaults, scoped subsystem configs
outrank top-level policies, and specific types and handlers outrank
generic fallbacks in code.

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
