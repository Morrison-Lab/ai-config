# Case records: address-every-comment

Worked-example case records for the rules in
[`address-every-comment.md`](address-every-comment.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "Noise is per-item, not per-round"

(rme#706 ran
100+ review rounds: each round's *new* findings --- a missing derivation step,
a missing i.i.d. hypothesis, an unverified citation locator --- got fixed
every time; the one recurring file-length flag got a single reply-and-hold
each round until the user weighed in.)

## "That rule's scope is 'the same file'" --- deriving the site list

(`Morrison-Lab/gha#398`, 2026-08-03: round 1 flagged an unquantified
superlative, "the corpus's most common paragraph opener", and named three sites
--- `CLAUDE.md`, a `changelog.d/` fragment, and a code comment in
`check-new-line-breaks/check-new-line-breaks.py`.
Commit `698d0af` touched exactly those three files, and the reply read "in all
three spots you named".
Round 4 then found a fourth site, a comment block in
`check-new-line-breaks/tests/test_check_new_line_breaks.py`.
Its finding opened "Fourth site with the same unquantified-superlative issue,
missed by the two rounds that fixed the other three" --- the reviewer's words,
not the code comment's, which says nothing about review rounds.
The sweep was available in round 1 and would have closed it there:
`git diff origin/main...e0e08e2 | grep -E 'most common|single most|house style'`,
run against round 1's own head, returns five hits across all four files.
The same grep at the fixed head returns no further hit for that pattern, which
is the other half of the check --- though only for that pattern, since a
superlative worded differently would not match it.)

## "The mirror case: the enumeration was complete and the fix was not"

(`Lacaedemon/sparta` PR #1199, 2026-08-05: the review verdict flagged
`website/combat.qmd` for reproducing "the *old* equation ... and old prose" at
lines 88-97, quoting both.
Commit `57d24b33` changed the equation, and the round-1 disposition table
reported the finding Addressed while the prose two lines below still read
"$\lambda$ is how much a shield ($b_D$) adds to a defence you can actually bring
to bear" --- the exact skill-independent framing the PR existed to remove.
Fetching the PR-preview build and reading the rendered page caught it: the
equation had updated correctly, and a second `b_D` on the same page was the tell.
Grepping the whole file for the concept then found two further stale statements
the review had never mentioned --- the stat-list entry for `b`, and an "Armour
and shields buy time" tactical bullet --- fixed together in `a9fff0d8`.)

## "When a prose fix changes wording that's also paraphrased elsewhere" --- syncing the CHANGELOG

(ai-config#373: fixed "routing/dispatch site" in the skill
per review, but the CHANGELOG entry still said it until a follow-up commit.)

## "When syncing copies, search the diff for the claim"

(Morrison-Lab/ai-config#981, round 2 commit `f616dc5a`, did both.
A count fix followed this section's rule in name, but ran
`grep -rn "122" hooks/*.py`, scoped to the two files already open.
That missed `hooks/hooks.json:56` and
`shared/workflow/incidents-dont-repeal-decisions.md:94`, so round 3 found the
PR still disagreeing with itself: 121 in two places and 122 in two others for
one unrecountable measurement.
The round 3 fix `05486216` used the diff as the scope; after committing, the
counts were `122: 0` and `121: 5`.
The same round retired a rationale that `Explore` and `Plan` were exempt
because they lacked `Edit`, `Write`, and `NotebookEdit`, while `Bash` was the
hole in that role contract.
Searching only for `Bash` missed a nearby code comment and two test labels that
still said the agents were read-only "by definition".
Those were corrected to the harness's declared read-only role, and both review
threads were resolved.)

## "The PR description is on that list"

(ai-config#829, 2026-07-29: a review nit led to correcting a gha#350
attribution in `memories/github-actions.md`.
Both reviewers then approved, and the PR body still carried the original
wrong claim verbatim --- "`continue-on-error` there, the dropped implicit
`success()` here" --- because it had been written before the correction and
was not part of the diff either reviewer read.
Caught only while assembling the ready-for-merge summary.)

## "Following that 'state it as history' advice" --- past tense reads as current

(Morrison-Lab/ai-config#843, 2026-07-30: the maintainer asked for a fourth
tool on an allowlist that had shipped with three.
Jules blocked twice.
The first was an ordinary stale snapshot --- its run started at `02:56:28Z`,
two seconds before the body was corrected.
The second re-ran at `03:00:31Z` against the corrected body, with a new
session id and a different cited line number, read the reversal-history
section, and praised the description for "explicitly documenting which
permissions should be intentionally excluded" while demanding the requested
tool be removed.
`claude-review` saw the same inconsistency at the same stale head and graded
it a minor, explicitly non-blocking prose note.
Escalated; the human merged past it.)

## "The same sync is needed when the review fix is to CODE BEHAVIOR"

(d-morrison/altdoc#78, 2026-07-27: review round 2 established that mkdocs
serves `/man/foo/`, not `/man/foo.html`; the code and the PR body were
corrected that round, while `NEWS.md` kept saying links point at `.html` under
"`mkdocs` and `quarto_website`" through two further clean review rounds.
Caught by a `main`-sync merge conflict that happened to land in that entry ---
not by any review, and not by any check.)

## "Tighter still: a changelog entry can contradict its own commit message"

(`ucdavis/bcs#463`, 2026-07-30: `a0f4113d`'s commit body said `update_trigger`
"can set `enabled: false` and rewrite a routine's prompt and cron outright".
The `NEWS.md` entry edited by that same commit justified excluding a different
tool on the grounds that the allowed set only changes *when* routines run ---
which the commit body directly refutes, and which is wrong about
`create_trigger` too, since it authors a whole new routine.
Caught by `claude-review` as an inline finding, not by any check, and the
correct framing turned out to be deferred versus immediate effect.)

## "One step further back" --- squash-merge commit-message check

(Checked this way on this repo, 2026-07-30: `5670f9f`, the squash of
[#855](https://github.com/Morrison-Lab/ai-config/pull/855), carries that PR's
commit message rather than its body.
So here the weaker copy is the one that persists.)

## "One step further back" --- ucdavis/bcs#465 pin-bump figure

(`ucdavis/bcs#465`, 2026-07-30: a submodule-pin bump whose PR body said
`CLAUDE.md` resolves 33 `@.ai-config/...` imports and whose commit message,
written minutes apart, said 25.
33 came from a script; 25 came from the tracking issue, written from
recollection.
Review named the mechanism exactly --- inherited from the issue rather than
re-checked against the file --- and graded it non-blocking on the grounds that
it was already permanent, which was the one part that was not yet true.)

## "A corollary for checking any of this in a semantic-line-break corpus"

(Same day, verifying that
[#855](https://github.com/Morrison-Lab/ai-config/pull/855) had landed: two of
three greps reported present and the third reported absent, purely because
that phrase happened to straddle a line break.)

## "Inline markup breaks the same search"

(Morrison-Lab/ai-config, 2026-07-30: `skills/ums/SKILL.md:109` cites
`memories/preferences.md`'s worktree-by-default rule, and a literal grep for
the quoted title returned only the citation, which was reported as a
dangling reference.
The rule is at `memories/preferences.md:264`, differing from the quotation by
two backticks; a backtick-normalized search found both files.)

## "Apply whatever normalization you choose to the search term"

(Morrison-Lab/ai-config, 2026-07-30, verifying #919 on `main`: a probe
collapsing backticks, asterisks, underscores, and whitespace in the file
alone reported `SH_WORD_SPLIT` ABSENT, while `git grep -c` found it.
The same needle normalized reported present.
That was the third normalization-caused false negative of the session, and
the first produced by the remedy rather than by the raw search.)

## "A flagged item that came in via a `main`-sync merge, is still a Defer"

(`UCD-SERG/serocalculator#503`: a review flagged `.Rbuildignore`'s `^\.posit/assistant$` as redundant with the existing `^\.posit$` pattern above it --- both lines had landed together in an already-merged `main` commit (#579), picked up via a routine `main`-sync merge, not introduced by #503's own diff. Deferred to `main` instead of fixed on the branch.)

## "This generalizes to a skill's own inline restatement of a fragment it links to"

(`ai-config#507`:
fixing `forward-references.md`'s regex left `fix-forward-references/SKILL.md`'s
own `description` field and Step 2 summary describing the old, already-fixed
approach --- caught in a second review round.)

## "A bot that re-raises an item as 'not addressed'" --- check timestamps

(d-morrison/altdoc#34: a `\pkg{}` rendering rebuttal
carrying a `pandoc` run that disproved the finding's implied hazard was
posted about a minute before the follow-up review job started; that review
reported the item "wasn't addressed in `9398d5d`" and re-posted the
identical suggestion.)

## "Reply-first collides with citing the fix's SHA"

(ai-config#871, 2026-07-30: a four-finding round with three Addresses and one
Rebut was pushed first and replied to about a minute later, so the round-2
review run started before the rebuttal was visible to it.
It happened to engage the rebuttal anyway --- the evidence was in the diff as
well as the thread --- but that was luck, not the ordering working.)

## "A finding can be right while its `suggestion` block is wrong"

(ai-config#726: a review correctly flagged that a `<path>` placeholder
didn't say where a script came from, but suggested
`<path-to-gha-checkout>/check-new-line-breaks.py` --- one directory level
too high, since the composite action's directory and the script inside it
share a name. `git ls-files` in the gha checkout settled it in one command.
Applying the suggestion verbatim would have documented a nonexistent path
in the entry whose whole purpose is getting someone to run that script.)

## "The same check applies to a fix a reviewer describes in prose"

(gha#318, 2026-07-26: a review correctly found that a heredoc-terminator
regex lacked an end-of-line anchor, and suggested adding one.
Tested against the reviewer's own indented-`EOF` example, the suggested
anchor still truncated the body, because the terminator's leading `[ \t]*`
accepted a space-indented closing line real bash rejects.
Matching whole lines against the tag -- how bash itself ends a heredoc --
removed the whole lazy-quantifier/anchor failure mode instead of narrowing
it; the reply carried the failing output of the suggested form.)

## "A reviewer's corrected citation is another factual claim"

(Morrison-Lab/ai-config#971 round 2, 2026-08-01: a review correctly found that
PR #955 did not cover a "default nobody chose" case record.
It then proposed #951 as the source because #951's `memories/tools.md` entry
used the word "default" and merged the same day.
That was the wrong default and the wrong file: #951 did not touch
`shared/workflow/metacognitive-monitoring.md`.
`git log -S "An unexamined default" -- shared/workflow/metacognitive-monitoring.md`
identified #947 as the source for the default half, while #955 supplied the
handed-premise half in the same fragment.)

## "The highest-yield version of that check" --- edge case named in the same comment

(Morrison-Lab/ai-config#868, 2026-07-30: a review correctly found that
`git merge-base --is-ancestor` prints nothing and answers by exit status, and
its second paragraph noted the command exits 2 or higher when the ref has
been pruned away.
Its suggested `... && echo "ancestor" || echo "not ancestor"` maps that exit
onto the `not ancestor` branch, since `&&` fails on any non-zero status --- so
the fix printed a confident verdict for precisely the broken-check case the
comment itself had raised, which is the shape
[`fail-fast`](../principles/fail-fast.md) names.
A three-arm `case $?` was used instead, reporting `0`, `1`, and `2+`
distinctly.)

## "A quieter variant: the suggestion restates the line above it"

(Morrison-Lab/ai-config#896, 2026-07-30: a review correctly called a test's
`"user-invocable" not in body` sentinel fragile, and suggested
`"---" not in body.lstrip()[:3]`.
Evaluated against the real body, that is the same predicate as the
`not body.lstrip().startswith("---")` assertion directly above it --- both
test the first three characters, both returned `True` --- so adopting it would
have left one property checked twice and the other not at all.
A synthetic fixture replaced the corpus coupling instead, plus a third
assertion that body prose *survives* stripping, which neither the original nor
the suggestion covered.
Tracked as #905.)

## "A finding can be right, and its fix adequate, while the reason it supplies is too weak to ship"

(Morrison-Lab/ai-config#873, 2026-07-30: a review correctly found a `CC-BY-ND`
table row that called verbatim copying allowed and then concluded idea-only with
no bridge.
Its suggested reason, "MIT grants modification rights; ND does not", frames the
conflict as two grants differing in scope --- which licenses the workaround of
keeping the file under its own notice inside the MIT repo, since on that framing
no conflict arises.
SPDX `license-list-data`'s `CC-BY-ND-4.0.txt` §2(a)(1) grants a
**non-sublicensable** license, so the material cannot be re-offered under MIT at
all, which is exactly what vendoring does.
The conclusion was right, and its stated reason stopped short of the provision
that actually forecloses the workaround.)

## "And the mirror case: a finding can be wrong on its stated grounds"

(ai-config#756, 2026-07-28: a review held that `[\x{2014}]` is valid PCRE
and so could not produce the "code point value too large" error the fragment
described, and proposed an out-of-range `[\x{110000}]` instead.
Running it showed the original failing exactly as written -- the cause is
the locale, since PCRE in non-UTF mode rejects any `\x{}` above `0xFF`, and
the same command succeeds under `LC_ALL=C.UTF-8`.
The proposed replacement would have been worse, failing unconditionally and
hiding that environment-dependence, which is the whole reason the swallowed
error is dangerous.
The reviewer's actual worry -- that a reader might not reproduce it -- was
right, and sharper than stated.)

## "A third direction" --- agreeing with a finding and then escalating it

(Morrison-Lab/ai-config#1056, 2026-08-02: Copilot found that the
`LIST_SECRETS` row promised `created_at`, which `gh secret list` does not
expose, and that finding was correct and correctly scoped to one field.
The session ran `gh secret list --repo <owner>/<repo> --json 2>&1 | head -3`,
read the two field names that survived its own truncation, and replied that
the CLI failed on two of three fields rather than one, writing that into
`tool-mappings.yml` as measured fact.
On gh 2.96.0 that usage message lists five fields: `name`,
`numSelectedRepos`, `selectedReposURL`, `updatedAt`, and `visibility`.
A usage line plus the first two of those is exactly what `head -3` returns, so
`updatedAt` was reachable all along and only `created_at` was not.
A later round caught it, and the correction had to be posted to the original
thread.

Note which instrument was the wider one, because it is the reverse of what
escalating assumes.
The reviewer's report named one field and its instrument showed all five,
while the escalation named three fields on a view of two.
The defect was truncating a full-scope instrument rather than choosing a
narrow one, which is why the remedy is coverage of your own claim rather than
a probe wider than the reviewer's.)

## "When a finding cites a source, read the cited source before reproducing anything"

(ai-config#762, 2026-07-28: a review held that
`htmlwidgets::saveWidget(selfcontained = TRUE)` no longer needs pandoc,
citing htmlwidgets 1.6.0 as having "switched to `base64enc::dataURI()`", and
supplied a suggestion block deleting the `rmarkdown::pandoc_available()`
gate.
`grep -inE 'pandoc|base64'` over that NEWS file returned six pandoc hits and
zero base64 hits, and the 1.6.0 entry says the path "now uses the
`{rmarkdown}` package to discover and call pandoc" -- so the citation
established the opposite of the finding, and incidentally made the gate the
*same lookup* htmlwidgets performs rather than a proxy for it.
Applying the suggestion would have removed the only warning before a hard
error, in the one step that exists for running headless.
The reviewer accepted the rebuttal on the next round and called its own prior
claim a hallucination.)

## "When a reviewer hedges a finding because it depends on code it cannot see"

(`UCD-SERG/serodynamics#274`, 2026-07-28: a review flagged possible
duplicate review dispatch at moderate confidence, explicitly because the
reusable workflow in `d-morrison/gha` was not visible to it.
That repo was cloned locally.
Reading both matchers showed the reusable fires on `@claude[[:space:]]+review`
and the local job on a punctuation-tolerant superset, so the plainest
phrasing --- `@claude review` --- matches both and dispatches twice.
The follow-up issue could then record the exact overlap table and note
that the upstream gap motivating the local job had since been closed,
making "broaden upstream, delete the local job" a real option.)

## "Timestamp the evidence before rebutting a finding with it"

(gha#351, 2026-07-28: a PR correctly diagnosed that Actions had stopped
resolving `uses:` after a repo transfer.
Its premise was disputed on the strength of two run logs showing the
workflow resolving fine --- logs from 45 and 30 minutes before the PR was
opened, spanning the cutover.
Re-running one of those very workflows reproduced `startup_failure`
immediately, and the retraction had to be published in the same thread.)

## "A finding built on a negative result" --- search-scope claims

(`Morrison-Lab/gha#338`, 2026-07-28: a review reported a cited section as
nonexistent, having "checked ai-config's full tree (`shared/workflow/*.md`,
`skills/`, `codex-skills/`)".
The heading was an H2 in that repo's **root** `CLAUDE.md`, the one directory
those three paths skip.
The reviewer had even found the phrase in `shared/workflow/fully-clean.md`
and read it as pointing at a *consuming* repo's `CLAUDE.md`.
The rebuttal carried the one-line grep; the underlying point was real
anyway, since citing a section title without naming its file is what sent
the search to the wrong directories, so the citation was fixed to name and
link the file.)

## "A note the reviewer declined to raise is still a claim"

(`Lacaedemon/sparta#1222`, merged 2026-08-07 as `320fe3b2`: a review round
noted, while explicitly declining to flag it, that the PR's claim "only two
things write `position`" was loose because `Unit._separate()` also writes it.
The session staged a caveat, checked first, and concluded the note was stale
--- `sparta#1109` is titled "Convert `Unit._separate()` regiment overlap
resolution from position push to velocity impulse", so the write was taken to
be gone.
It is not.
At `320fe3b2` that function ends
`_separation_velocity += step_vel` / `position += step_vel * delta`, and its
own comment says it expresses the push "as a velocity ... and integrate[s]
that" --- the velocity is how the per-tick displacement is **capped**, not what
replaced the write.
So the declined note was correct and the refutation was not, and the refutation
rested on the PR title rather than on the function.
Holding was still the right call, and the caveat was never added, so nothing
false shipped: a normalized search of `.claude/memories/` at `320fe3b2` finds
neither the caveat nor the "only two things write `position`" claim it would
have qualified.
Re-measured here against `origin/main` at `320fe3b2` after a `git fetch` ---
the local checkout was 1 commit behind and did not contain the merge, which
would have made any answer read off it a claim about a different tree.)
