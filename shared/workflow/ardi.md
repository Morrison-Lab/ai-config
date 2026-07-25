Whenever you are working a PR/MR, run the full **ARDI** loop by default, without
being asked: **A**ddress every flagged item, **R**ebut findings that are wrong,
**D**efer out-of-scope items to tracked issues, then **I**terate with a fresh
review --- repeating until the latest review is **fully clean**. Don't stop at
"review-clean, just needs approval" and hand triage back; keep the cycle going
until it's genuinely clean.

The loop's terminal action is to **report the PR ready, not to merge it**.
Merging is human-gated --- it happens only on an explicit human "merge it" (the
`merge-it` skill), never as a step ARDI takes on its own. So when you carry a PR
across a `ScheduleWakeup` or `/loop` wait, **never** bake a self-merge directive
like "if clean and CI green, merge it" into the wakeup/loop prompt: a scheduled
prompt fires back as a user-role turn, so a self-authored "merge it" only *looks*
like human approval (and Claude Code's auto-mode classifier will rightly deny it
as a self-authored merge). Drive to fully clean, report ready, and leave the
merge --- and any other destructive one-off, e.g. a `gh workflow run` that
force-pushes --- for explicit human authorization.

The one exception: if the human has explicitly granted the `mwc`
(merge-when-confident) session permission, that grant is a live human
instruction, not a self-authored one, so baking a self-merge step into a
wakeup/loop prompt is fine for the rest of that session. See
[`mwc`](../../skills/mwc/SKILL.md) for the grant's scope and limits.

In the **clear-all family** (`ardia`, `gia`, `gii`, `gip`), "report ready, don't
merge" gates only the merge --- it does **not** pause the sweep. A
clean-but-unmerged PR is not a stop; move to the next item, and stack it when it
isn't naturally independent of that PR. See
[`stack-dont-pause`](stack-dont-pause.md).

**Self-review against the project's own stated conventions before every
push, not just the first --- and don't just re-read the criteria, actually
run the applicable review skills against your own diff and iterate on
what they find, the same ARD cycle you'd run against an external
reviewer's findings.** Don't treat the review bot as the mechanism that
discovers a project's documented conventions --- self-apply them first.
When a project's own `CLAUDE.md` (or equivalent agent doc) already states
specific criteria --- a DRY/no-duplication rule, a doc-sync checklist for a
new input, a changelog-category rule, a citation requirement, a "new logic
needs test coverage" norm, a prose-quality check like `fact-check-prose`,
`fix-forward-references`, or `detect-informal-definitions` --- a first-pass
implementation checked only against feature correctness forces the review
loop to spend a round re-deriving what the project's own docs already
said. Before every push, re-read the project's own stated review criteria
and actually invoke the review skills/checks it names against the diff
(not just recall them from memory), the same way an external reviewer
would apply them. Address every finding your own self-review surfaces ---
fix, rebut, or defer, exactly like the ARD step above --- before the push
goes out; a self-review that finds issues and pushes anyway has only
moved the round to the external reviewer instead of skipping it. Repeat
until your own self-review pass is clean, then push.
([gha#219](https://github.com/d-morrison/gha/issues/219)/[#220](https://github.com/d-morrison/gha/pull/220): one review round surfaced five findings --- a DRY
duplication, an incomplete-coverage doc overclaim, a wrong changelog
category, an uncited claim, and missing test coverage for new logic --- all
catchable this way, since each was a direct match against gha's own
`CLAUDE.md` conventions, not new information the review surfaced.)

**Proactively self-correct a technical claim you already told a reviewer,
the moment further testing shows it was wrong --- don't wait for the
reviewer to catch it.** If you stated a rationale (an approach is safe, a
risk doesn't apply, a backstop exists) and then discover through your own
follow-up verification that it's false, post the correction with the actual
evidence immediately, rather than leaving the stale claim standing until a
review round re-raises it. This keeps the review loop converging instead of
churning on a claim you already know is wrong. ([d-morrison/rme#989](https://github.com/d-morrison/rme/pull/989) /
[ucdavis/epi204#363](https://github.com/ucdavis/epi204/pull/363): after telling both reviewers `references.bib` didn't
share `CLAUDE.md`'s union-merge corruption risk, a follow-up merge
simulation showed it does --- posted the correction with repro steps on
both PRs before either reviewer re-raised it.)

**When the change affects downstream consumers, validate it against a real
consumer repo before reporting the PR ready --- a package's own test
fixtures are built to exercise its code, not to look like the wild.**
Fixtures are minimal by construction and tend to share one shape, so whole
branches of new code can be structurally unreachable from them. A real
consumer brings the input variety fixtures lack, and it is usually one clone
plus one command to check.

Three classes of gap this catches, none of them findable in a fixture:

- **Input shapes no fixture happens to contain.** A real package carries
  metadata the fixtures never needed --- an entry of a different kind, an
  extra tag, an unusual name --- so a branch written for it has never
  actually run on real input.
- **Message formatting under real counts.** Fixtures usually trip the plural
  path; a real repo hitting the same code with exactly one item exercises
  the singular wording, which no test asserted.
- **The migration/upgrade path, as opposed to the fresh-install path.**
  This is the one fixtures can never reach: a fixture is created new by the
  test, so it always gets the current templates. An existing consumer has
  the *old* config, and whether the feature reaches it at all is a different
  question from whether it works. Verify the claim in the changelog by
  running the documented migration step, rather than describing it.

Do it against a throwaway copy and push nothing to the consumer; the
deliverable is evidence in the PR, not a change there. Record what the run
covered in a PR comment, so a reviewer can see which paths real input
reached. (d-morrison/altdoc#34: running the new reference-index generator
against `d-morrison/rpt` covered a `\docType{package}` topic, the singular
form of a missing-topic warning, and the documented "existing settings files
do not pick this up automatically" caveat --- confirmed by the page
generating while `grep -c reference.html docs/index.html` returned `0`. None
of the three were reachable from the repo's own fixture packages.)
