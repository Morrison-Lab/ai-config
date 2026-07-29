Whenever you are working a PR/MR, run the full **ARDI** loop by default, without
being asked: **A**ddress every flagged item, **R**ebut findings that are wrong,
**D**efer out-of-scope items to tracked issues, then **I**terate with a fresh
review --- repeating until the latest review is **fully clean**. Don't stop at
"review-clean, just needs approval" and hand triage back; keep the cycle going
until it's genuinely clean.

**Continuously monitor every PR/MR you are actively working until it reaches
that terminal state.** At every periodic check-in, and again after any push or
base-branch advance, query the current head for all three surfaces: mergeability
(including conflicts), every CI workflow/check run, and both formal reviews and
top-level/inline review comments. A conflict, CI failure, or newly posted
finding is ARDI work immediately --- sync and resolve the conflict, investigate
and fix or track the CI failure, or disposition the finding --- not merely a
status item to hand back to the user. Keep polling while a review or check is
in progress; do not call the PR clean from an earlier head or from green CI
without a current-head review verdict. This applies transitively to PR-driving
workflows such as `gi`, `gii`, and `ardia`; only monitor PRs the session owns or
has explicitly claimed, so the rule does not authorize changing someone else's
work.

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

Because the loop ends there, **the clean verdict is also where `ums` runs** ---
don't hold the pass for the merge, which is on the human's clock rather than
this session's and may land after a `/clear` or not at all.
See `CLAUDE.md`'s "Run UMS proactively, as learnings accumulate";
the merge-time pass in `post-merge` then only has to cover what the merge
itself taught.

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

**A fix is not "pushed" until it is on the PR's head commit --- verify with a
SHA comparison before telling a reviewer you pushed it.** From inside a
session, an edited working tree and a pushed commit feel identical, so a
round that edits the files, writes the reply, and never runs `git push`
produces a reply asserting a fix that does not exist on the branch. Nothing
contradicts it: CI reports green, because it correctly validated the older
head; the next review round reviews code without the fix; and the session's
own recollection of having made the change agrees with the reply. That makes
it worse than an ordinary wrong claim --- it is a false statement about
*state*, which a reviewer has no reason to doubt and no cheap way to check.
Before posting any reply that asserts a push, compare `git rev-parse HEAD`
against the PR's own `head.sha` (`pull_request_read` `get`); if they differ,
push first, then reply naming the real SHA. Run the same comparison in every
periodic check-in on a PR you are babysitting, since the failure is silent
and survives each round until something explicitly looks for it. This is the
[`algorithmatize-checks`](algorithmatize-checks.md) rule applied to your own
claims: two SHAs decide it exactly, so never substitute recollection.
(d-morrison/altdoc#54, 2026-07-25: two review fixes were edited locally and a
PR comment said they were "addressed in the latest push"; the head sat at the
pre-fix commit for over an hour, with 14 green checks validating a branch
carrying neither fix, until a scheduled check-in compared the SHAs.)

**When the change affects downstream consumers, validate it against a real
consumer repo before reporting the PR ready --- a package's own test
fixtures are built to exercise its code, not to resemble the packages that
will actually use it.**
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

**Verify a blocker you assert in a PR body or a reply, with the same rigor
you apply to a reviewer's claims --- a stated blocker becomes a premise
other people build on.**
The reviewer-facing checks above all point outward: verify the suggestion,
verify the literal, verify the push landed.
The inward case is easier to miss, because a limit you hit yourself feels
like an observation rather than a claim.
It is still a claim, and writing it into a PR body publishes it as
settled fact: a reviewer reading "the pinned tool is unavailable in this
sandbox" will reason from it, recommend a follow-up around it, and never
re-test it, so one unverified sentence quietly redirects the review.
Before asserting that something is unavailable, blocked, or impossible
here, actually attempt it once --- an install, a fetch, a single command
--- and say what you tried.
A negative result from one incidental symptom (a failed version query, a
single 403) is evidence the thing is not *already set up*, not evidence
it cannot be.
When a blocker you published turns out to be false, correct it where it
was published, not only in the thread that surfaced it.
(d-morrison/altdoc#76, 2026-07-27: the PR body said roxygen2 8.0.0 --- the
version `DESCRIPTION` pins --- was unavailable, inferred from one failed
`packageVersion()` call with no install attempted. The review built a
"this may need a follow-up" recommendation on top of it. A single
`install.packages()` disproved it, and the regeneration landed in the same
round the finding did.)

**A blocker that was true when you published it can stop being true while
the PR is open, and withdrawing it is your job, not the reviewer's.**
The bullet above covers a blocker that was never true.
This is the harder case, because the caveat was correct and diligent when
written, so nothing about it reads as a defect later --- and a sentence
saying "this could not be checked" is one nobody re-checks, least of all
the reviewer, who has no way to know the environment moved.
It keeps steering the review regardless: a verdict can repeat the caveat
back as an accepted limitation, which makes the stale claim look
corroborated.
So when the cause of a blocker changes --- a host unblocked, a tool
installed, a quota reset, a dependency published --- re-run the check and
withdraw the caveat where it was published, saying explicitly that it is
withdrawn rather than quietly deleting the sentence.
A reader who saw the original needs to know it was retested, not be left
wondering whether it was ever true.
(ai-config#774, 2026-07-28: the PR body said four `adv-r.hadley.nz` anchors
could not be verified because the host was egress-blocked, which was
accurate when written.
The host was unblocked mid-session, and all 16 URLs then verified 200 with
every anchor resolving.
The review had already absorbed the caveat --- it listed those anchors as
"unverified per the PR body's own caveat ... not a new finding" --- so
leaving it would have shipped a limitation that no longer existed, blessed
by a reviewer who could not have known.)

**An instruction's own suggested code is not exempt from the
project-conventions self-review above.**
The self-review rule assumes you wrote the diff; a snippet handed to you
in an issue, a task description, or a design doc slips past it, because
adopting someone else's suggestion does not feel like authoring.
It is authoring --- once pushed, it is your diff, and the project's
conventions bind it exactly as they bind anything you wrote yourself.
Run the same convention check over borrowed code before pushing it,
especially when the suggestion is a plausible-looking one-liner and the
convention it breaks is documented rather than linted.
(d-morrison/altdoc#73: the issue proposed ending a function with a bare
trailing `hashes`, which reads as a fix for the fragility it names but is
still an implicit return, so a statement added after it silently becomes
the return value. The lab manual asks for an explicit `return()`
regardless. Review caught it; the project's own stated convention would
have, one step earlier.)

**When the code path under test has a staging or transform step between
input and output, a passing unit suite is not evidence it works ---
exercise the real path once.**
Fixtures instantiate the shape the test author had in mind, so a wrong
assumption about *where* the code runs is invisible to every one of them:
the tests and the bug share the assumption.
This is the same gap the downstream-consumer rule above covers, one level
in --- there the missing variety is the consumer's input, here it is the
pipeline's own directory layout, timing, or intermediate representation.
One real invocation is usually cheap, and it tests the assumption the
fixtures encode rather than re-confirming it.
(d-morrison/altdoc#76: a guard checked for the copied logo under `docs/`,
but the `quarto_website` path stages into `_quarto/` first, so the logo
line was dropped on every render of the one generator the feature wired
up. Seventeen unit assertions passed throughout; one throwaway render
found it immediately.)

**When new code branches on a third-party tool's behavior, read that tool's
own config or docs for the specific behavior --- don't infer it from what
the tool broadly does.**
The bullet above covers your own pipeline's layout; this one covers the
tools that pipeline drives.
An inference of the form "it builds HTML, so link to `.html`" is exactly
the shape that feels too obvious to check, and a tool's defaults routinely
contradict it.
Two properties make this worse than an ordinary wrong guess.
The inference usually lands in a branch your own fixtures cannot reach ---
you have no fixture for someone else's renderer --- so the test suite
agrees with you.
And it produces output that is well-formed and plausible (a link, a path, a
flag), so a reviewer skimming the diff has nothing to catch, and the
failure surfaces only in a consumer's published site.
Name the setting you are relying on, and check its actual default before
writing the branch.
(d-morrison/altdoc#78, 2026-07-27: a generator-to-extension map gave mkdocs
`.html`, reasoning that mkdocs compiles Markdown to HTML. Its
`use_directory_urls` default is `TRUE`, so it serves `/man/foo/` and never
`/man/foo.html` --- every reference link the feature emitted for that
generator would have 404'd. Caught in review, not by the 39 tests.)

**A regression test written alongside a fix can lock the bug in rather than
catch it --- assert the two paths that diverge, not the one you just
touched.**
A test authored in the same pass as the code tends to record what the code
*does*, because you run it, see it pass, and move on.
That is usually harmless.
It becomes a lock when the fixture is thin enough that the buggy and the
correct path produce the *same* output: the assertion then encodes the
degraded result as intent, and every later reviewer reads a green suite as
evidence the behavior was chosen.
The next round's finding lands on your test, not just your code.

The tell is the same each time: **a fixture missing the input variety that
makes the two paths differ.**
So when a bug is an asymmetry --- nested versus top-level, second render
versus first, one generator versus another --- build the fixture so both
sides are present and assert them together.
Either side alone is unfalsifiable, since the case that reveals the bug is
the *comparison*.
Then prove it: revert the fix and confirm the new test actually fails.
A regression test never seen to fail is a guess about what it covers.
(d-morrison/altdoc#78, 2026-07-27: twice.
A `.pdf` vignette test asserted
the entry's extension but never its label, so an extension leaking into the
label passed; and a nested-article test built no source tree, so top-level
and nested resolved identically and a nested-only title bug was pinned as
expected output.
Both were found by review reading the test, not the code.)

**A systematic audit done by skimming is worse than the one-at-a-time
version it replaces.**
Batching a check --- "rather than wait for the next round to find divergence
number four, compare all four at once" --- is the right instinct, and it
inverts if each lookup gets less care than it would have alone.
Two things make the batched form more dangerous, not less.
Its output is usually a claim recorded somewhere durable (a comment, a
doc, a table), so an error is published rather than merely held; and it
arrives labelled *audited*, which is precisely the word that stops the next
reader from checking.
A wrong comment in a block written to prevent a specific future change
invites that change while appearing to forbid it.
Concretely: when the thing being audited is a function, grep for the
function, not for a pattern in its file --- a file with several functions
will hand you the first match, which is often not the one you mean.
Name the function in whatever you write down, so the claim stays checkable.
(d-morrison/altdoc#78, 2026-07-27: a commit written to get ahead of a
one-finding-per-round loop claimed mkdocs' sidebar matched only `\.md`.
It matches `\.md$|\.pdf$`; the grep had returned a different function 120
lines above the sidebar builder in the same file.
Caught by the very next review round.)

**Adding an explanation supersedes whatever the file already said about the
same thing, so re-read the older passage --- your own diff is the likeliest
source of a contradiction nobody flags.**
The sync rules in
[`address-every-comment`](address-every-comment.md) all fire on an external
trigger: a reviewer quotes a phrase, or behavior changes and a changelog goes
stale.
This one has no trigger at all.
You add a paragraph explaining that something was misunderstood, and the note
recording the original misunderstanding sits a few lines below, still stating
it as fact.
Nothing conflicts, no check fires, and both passages read plausibly on their
own --- but a reader who reaches the older one first comes away with exactly
the belief the new text was written to remove.

The tell is a diff that adds an explanation, a correction, or a "what this
actually means" paragraph near existing prose.
Re-read the surrounding passage as a whole rather than diffing your addition
in isolation, and treat a historical record ("we observed N of X") as a claim
your explanation may have just falsified.
When the older passage recorded a *different* session's observation, correct
it with reasoning that stands on its own rather than restating it as though
you had seen it --- an inference presented as an observation is the same
defect one level up.
(ai-config#770, 2026-07-28: an added explanation established that seven
reported orphans were misclassifications, while the note two lines below went
on calling them "already deleted from the repo."
Caught by review, in the same hunk as the text that contradicted it.)

**The same rule applies within a single diff, and there nothing prompts the
check at all.**
The version above compares your addition against the *existing* file, so
re-reading the surrounding passage catches it.
The harder case is a diff that both adds an explanation arguing against some
older wording **and** rewrites that wording, in the same changeset.
Then the argument survives while its target does not, and every file still
reads plausibly on its own: the new prose is coherent, the rewritten passage
is coherent, and only the cross-reference between them is stale.
There is no older text to go back and re-read, which is the cue the other
version relies on.

So when a diff rewrites a passage, grep the rest of the diff for references to
what that passage used to say, not just for references to the file.
A rebuttal of the form "the section below already says X" is the shape to
watch, since it pins the argument to wording the same commit may be deleting.
Prefer stating the anti-pattern directly over citing another section as the
thing being argued against; a self-contained sentence cannot go stale when its
neighbour changes.
(ai-config#801, 2026-07-28: a new UMS entry argued against the `/clear`
section's "disclose the owed pass in the flag" line while the same PR rewrote
that line to say the opposite.
Review caught it before merge; the fix was to drop the cross-reference and
state the point inline.)

**And when the explanation you add is a *mechanism* claim, test the class it
distinguishes, not just the sample in front of you.**
The bullet above is about contradicting old text; this is about the new text
being unfalsifiable on the evidence you gathered.
A classifier validated on a population containing no positive instance of the
class it is supposed to catch will report a clean result either way, so
"it returned zero" is not evidence it works --- it is the same
missing-input-variety tell the regression-test bullet above describes, moved
from a fixture to a diagnostic.
Ask what a true positive would look like, confirm one exists in what you
tested, and if none does, say so instead of claiming the mechanism separates
the cases.
(ai-config#770, same day: a `git log -- skills/<name>` probe was said to
separate "deleted from the repo" from "never ours" *exactly*, on the evidence
that it reported zero false orphans.
The repo contained no deleted-but-still-installed skill at all, so there was
nothing for it to get wrong; and `git rev-parse --is-shallow-repository`
returned `true`, meaning anything deleted before the shallow boundary would
have been silently misread as harness-provided.
The claim went into a PR reply before either check was run, and ai-config#765
had independently reached the correct conclusion.)
