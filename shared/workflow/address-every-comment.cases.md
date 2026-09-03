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

## "The diagnosis is about the line; the remedy's correctness is about the call path"

(`Morrison-Lab/ai-config#2086`, 2026-08-23: a review correctly found that
`res.stderr.strip()` in `scripts/check-pr-body-figures.py` crashes when the
Windows subprocess reader thread dies and leaves the stream `None`, and
supplied a suggestion block: `(res.stderr or '').strip()`.

The diagnosis is right.
The remedy is inadequate in that file, for a reason the diagnosis gives no hint
of.
`verify_pr_body_figures` wraps its `run_cmd` calls in a broad `except Exception`
and converts the failure into `status="UNVERIFIED"` (`:434`), which `main`
returns as `CLEAN_EXIT` (`:658`, `:683`; `CLEAN_EXIT = 0` at `:37`).
Those positions are as of `origin/main` at `b26bbdfc`, after
[#2086](https://github.com/Morrison-Lab/ai-config/pull/2086) merged.
The suggestion changes only *which* exception is raised, and `except Exception`
catches an `AttributeError` and a `RuntimeError` identically --- so it removes
the crash and leaves an environment failure exiting **0 CLEAN**, which is the
failure mode the PR existed to close.

Measured rather than reasoned, by stubbing `subprocess.run` to return
`CompletedProcess(returncode=1, stdout="", stderr=None)`: the shipped line and
the suggested line both exit `0`, while `die()` exits `2`.
`die()` was the right remedy because `SystemExit` derives from `BaseException`
and escapes that wrapper --- `issubclass(SystemExit, Exception)` is `False`.

Note what the first draft of this record got wrong, since it is the same class
of error: it said the suggestion would turn a loud crash into a silent pass.
There was no loud crash to lose.
The `AttributeError` was already being caught by that same `except Exception`,
so the silent pass predated the suggestion, and the suggestion simply fails to
fix it.

What made it visible was asking where the raised error *goes*, rather than
whether the substitution is safe at the line it sits on.
That is what separates this from its two immediate neighbours, whose suggestions
were each wrong at the line itself --- a nonexistent path, and an anchor that
still truncated the body.
Here the suggested line is locally correct and insufficient two frames up, so no
amount of scrutiny of the diff hunk reaches it.
See [`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s "Changing
which exception a function RAISES is a signature change that fails silently"
for the same underlying fact arriving from the author's side.)

(A third draft of this record cited `:409`, `:633`, and `:658`.
Those were correct before
[#2086](https://github.com/Morrison-Lab/ai-config/pull/2086) merged and wrong by
25 lines after, since that PR inserted guards above them.
The reviewer caught it and gave the right numbers.

The part worth keeping is what happened next.
Checking the reviewer's claim, `grep -n` against a local `main` at `df4676c2`
returned `409`, `633`, `658` --- the original values --- which read as a
refutation of the finding.
`origin/main` was `b26bbdfc`.
The local branch had not fast-forwarded because an unrelated session's
uncommitted files were blocking the pull, so the checkout was three commits
stale, and silently so.

So the same defect recurred **while verifying a report of it**, one step further
out: a line number recalled from a stale copy, then a refutation derived from a
stale copy.
`git grep` against a working tree answers a question about that working tree,
which is not the question when the claim is about `main`.
Resolve a ref explicitly --- `git show origin/main:<path>` --- and say which ref
the numbers are as of, which the citation above now does.

The general form is in
[`verify-the-right-artifact`](verify-the-right-artifact.md): a checkout standing
in for the run.
Recorded here because the artifact substituted was not an exotic one, it was
`main`, and nothing about `grep -n` in a repo announces which commit it read.)

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

## "A reviewer's replacement diffstat summed per-commit churn"

(Morrison-Lab/ai-config#1517, 2026-08-16: a round-2 review correctly found the
PR body's verification table stale, since its figures had been measured at
`0fff7765`, before the round-1 fix commit.
It supplied 81 added and 7 removed as the replacement.
The real figures are 74 and 0.

Summing `git show --numstat` over the branch's two non-merge commits
reproduces the reviewer's numbers exactly, which is what identifies the
method rather than merely contradicting the result:

| commit | added | removed |
| --- | --- | --- |
| `0fff7765` | 59 | 0 |
| `3b5feead` | 22 | 7 |
| summed | **81** | **7** |

`git diff --numstat 0fff7765^ 3b5feead -- shared/workflow/address-every-comment.md`
returns `74  0`, and the GitHub API's own `additions` field on the PR reads 74.
Each of the 7 lines `3b5feead` deletes is absent from the file at the merge
base and present after `0fff7765`, so every deletion removes a line the branch
itself had added.
They cancel against the merge base, which is why the net carries no removals
at all and the reviewer's 7 is churn rather than a net figure.)

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
reusable workflow in `Morrison-Lab/gha` was not visible to it.
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

## Deriving the class is necessary and not sufficient

(2026-08-08, `Morrison-Lab/ai-config#1287` and `#1278`, both round 1 to round 2
inside one hour.

On #1287 a review reported five executable bypasses of the merge guard --- a
leading `!`, `time`, `nohup`, a brace-group body, and a `then` branch body.
The fix widened the keyword enumeration to twelve members, adding `sudo`,
`else`, `do`, `if`, `elif`, `while`, and `until` beyond the reported five, with
fourteen new BLOCK cases and three new ALLOW cases taking the suite to 141 from
124, and the reply said in as many words: "I derived the class rather than
fixing the five reported instances".
Round 2 returned two more, `case`-arm one-liners and function-definition-and-call
one-liners, and named the lever outright --- "the enumeration is still
demonstrably incomplete".

On #1278 a review reported three phrasings misclassified as a clean verdict
(`not ready`, `not approved`, `ready ... once`).
The fix added two word lists, an eight-word negation prefix and an eleven-entry
conditional suffix.
Round 2 produced four more, none of which either list reached: "Ready for merge,
but not until...", "Almost ready for merge...", "Ready for merge -- however...",
and "Ready for merge except for...".
It too named the lever --- "I recognize a regex-based classifier can't achieve
completeness against free-form English".

In both rounds the redirect arrived beside example cases, and in both the
examples were worked while the sentence was read past.
Round 2 on #1287 sharpens why: it quoted this corpus's own "never predict which
case will fail; enumerate the class" and then suggested adding `)` to the
character class --- so its actionable half proposed one more enumeration step
against the lever its diagnostic half had just called incomplete.
Following that review faithfully would have reproduced the bug a third time.

What resolved both was a different axis, chosen by measurement.
On #1287, relaxing the narrow anchor entirely changed exactly seven of 141
cases and all seven were prose inside quotes, which showed the defect was a
**quoting** problem being solved with a **command-position** lever.
The fix keeps the narrow raw-text pass and adds a strictly additive second pass
that blanks inert quoted spans and then treats every position as a command
position --- narrow pass retained because a quoted span is not inert for a
deferred evaluator, since `bash -c`, `eval`, and `trap` all run their quoted
operand.
Twelve of the fourteen resulting cases had never been reported by anyone, which
is the signal that the class closed rather than the members being patched.
On #1278 the lever became positional: require the phrase to be marked as a
verdict by a heading, bold, a bullet, line-initial position, or a `Verdict`
label, which reaches the case no vocabulary can --- a friendly aside mid-sentence
carrying no qualifier at all.
44 passed, up from 34.

The growth rate was available at round 2 in both cases and was not read: five
reported becoming twelve enumerated and then fourteen, three becoming two lists
and then seven.)

## The class is right, and it is enumerated in more than one place

(`Morrison-Lab/ai-config#1287`, 2026-08-08, three rounds: every finding was the
same concept --- text handed to something that runs it --- reached through a
different construct, and each round closed one door rather than the room.
The guard ended up encoding that concept at three separate sites: `EXEC_WRAP`,
which pass 1 uses for programs whose quoted argument is live (`bash -c "..."`,
`eval "..."`); pass 2's blanking of spans judged inert; and `mask_heredocs`,
added in round 1 so prose about the command inside a heredoc body would stop
matching.
Round 3 reported six executable forms that all blocked before the PR and allowed
after it --- `bash <<EOF`, `sh <<EOF`, `bash -s <<EOF`, `ssh myhost <<EOF`,
`ssh -T user@host <<EOF`, and `bash <<'EOF'` --- because `mask_heredocs` blanked
the body before any matching pass could see it.

The review named the duplication itself, in the paragraph explaining why the
existing mechanism did not save the new site: `EXEC_WRAP` "already enumerates
programs whose quoted argument is live ... the same reasoning applies here, but
`mask_heredocs` runs earlier in the pipeline and unconditionally, with no
analogous carve-out".
The resolution was DRY rather than a fourth list: one `EXEC_PROGS` definition
consumed by all three sites, leaving a single reviewable list instead of three
that drift.

The round's premise error is worth keeping beside it, because it explains why
the third door was invisible.
`mask_heredocs` reasoned about the **heredoc** --- its docstring held that a
quoted delimiter "means bash performs no expansion at all in the body, so it is
inert" --- when the question was about the **consumer**.
`<<'EOF'` stops bash expanding a body without stopping bash running it, so a
property of the container had been read as a property of whatever the container
is handed to.
The suite did not catch it for the reason its siblings did not: every heredoc
case in it fed `cat`, `grep`, `echo`, or `gh issue create --body-file -`, and
none fed a shell.)

## "A rebuttal's own evidence is the least-checked claim in a review round"

(`Morrison-Lab/ai-config#1304`, 2026-08-07/08: the case record added by that PR
carried a "Reproducible in one line" command whose backslash count is
load-bearing, and it shipped with four backslashes, which does not reproduce.
A reviewer flagged it twice.
The first response rebutted, citing a measurement showing both the four- and
two-backslash forms printing `\x08`, and asserting the point had been
"confirmed at the argv level".
The reviewer held, ran the four-backslash form itself, and was right.

The rebuttal's measurement had gone through a tool that wraps a command in a
second shell, so the doubled pair collapsed twice and the four-backslash form
arrived at Python as the two-backslash one.
The two forms were therefore indistinguishable TO THAT MEASUREMENT while
differing to a reader, and the argv inspection offered as corroboration had
passed through the same two layers, so it confirmed the artifact.

Re-measured 2026-08-08, each form written to its own file and run as
`bash <file>` so exactly one layer applies:

| form | from a file (1 layer) | typed into the tool (2 layers) |
| --- | --- | --- |
| four backslashes | `requested\\b`, no warning | `requested\x08`, warning |
| two backslashes | `requested\x08`, warning | `requested\x08`, warning |
| one backslash | `requested\x08`, warning | `requested\x08`, warning |

Through the tool all three collapse to the same output; from a file the
four-backslash form separates from the other two, and that separation is the
entire disagreement.
Corrected on that PR's branch in commit `fd109db7`.

Two details are worth keeping.
Python's only diagnostic names the escape that SURVIVED (`SyntaxWarning:
invalid escape sequence '\s'`) rather than the `\b` that became a backspace, so
the warning points away from the corruption.
And while this record was being verified, the instrument's own exit status was
first read from a `... | tail -5` pipeline, which reports the status of `tail`
and showed 0 for a run that really exited 1 --- the pipeline defect
[`errexit-is-not-uniform`](../coding/errexit-is-not-uniform.md) documents,
reproduced while documenting a neighbouring one.)

## A defect whose surface form varies defeats a phrase grep; only a full read finds every instance

(`Morrison-Lab/ai-config#1366`, 2026-08-09/10: a PR split six large `CLAUDE.md`
sections into `shared/workflow/` fragments --- the exact move
[`reorganize-prose.md`](../writing/reorganize-prose.md), added by the same PR,
licenses and warns to sweep for stale self-references.
Round 1's review named three instances --- the inherit-the-enumeration
failure [`address-every-comment.md`](address-every-comment.md)'s "That rule's
scope is 'the same file'" section already describes --- and all three were
fixed.
Round 2 ran the "obvious" fix: grep the moved files for a quoted heading in
`above`/`below` phrasing, per that section's own prescribed remedy.
It missed a fourth instance, found in round 2's own review, because the
target section had never been extracted at all --- it stayed inline in
`CLAUDE.md`, so no quoted fragment heading existed for the pattern to match.
Round 3's review found a fifth: `"...the same too-early flag the UMS rule
above rejects"` names no heading at all, quoted or otherwise --- it alludes
to a rule stated in a different file, in different words, with nothing for a
grep to lock onto.

The fix for round 3 is what broke the cycle, and it did not use a smarter
pattern.
Rather than grep again, it read all six touched files end to end, checked
every `above`/`below`/`bullet`/`paragraph`/`section`/`rule` reference's
actual target by hand, and separately cross-grepped every bold sub-heading
phrase in each file against the other five for a stray unquoted mention.
That pass found a sixth instance no round's grep had, fixed it in the same
push, before round 4's review could name it --- and round 4 confirmed both
fixes and reported no further findings.

The general form is already in
[`address-every-comment.md`](address-every-comment.md)'s "That rule's scope
is 'the same file'" section, in its last "Don't" bullet: "a
differently-worded instance would not have matched."
What this case adds is how differently a defect can be worded when the thing
moving is prose rather than code, and a phrase search is not even the
second-best instrument here --- for a defect class defined by what a sentence
*refers to* rather than by what string it *contains*, the site list cannot be
derived by grep at all.
It has to be derived by reading, because the only reliable test is "does this
reference's target still live where the reference assumes it does," and that
question has no fixed vocabulary.

- **Do:** treat a locative or allusive cross-reference as needing per-instance
  verification of its target, not a phrase-matched sweep, whenever the
  referring wording is free to vary --- which prose self-references always are.
- **Do:** read the whole affected scope end to end once a reviewer has found
  two or more instances of the same reference-target defect; that is the
  signal that the remaining instances are not sharing a phrase either.
- **Don't:** treat a clean grep for the previously-flagged phrasing as
  evidence the class is exhausted --- here, the grep-based fix applied after
  round 1 still left two more rounds' worth of instances for reviewers to
  find, each worded differently enough that the grep never touched it.

**Why a partially-applied fix is harder to spot than an unapplied one.**
The entry above gives the remedy and treats the difficulty as a matching
problem --- the grep missed instances whose wording varied.
There is a second reason it keeps not firing, and it is not about matching at
all: the instances you *did* fix become evidence that the class was handled.

An unapplied fix leaves a defect with nothing around it.
A partially-applied one leaves a defect flanked by corrected siblings, and
those siblings read as a completed sweep --- so re-reading the area confirms
the fix rather than exposing the gap.
The area looks *more* finished than it did before, which is the opposite of
what the remaining instance needs.

Measured on [ai-config#1810](https://github.com/Morrison-Lab/ai-config/pull/1810),
2026-08-21, where the same shape survived three separate rounds in one PR:

| round | the instance left behind | what concealed it |
|---|---|---|
| 2 | one "installed" that should read "available" | its two siblings had already been corrected |
| 3 | `four claim types` in a third file | the two files carrying that count were both swept |
| 4 | "notes, tags ... precisely where the answer lived" | the reflog half of the same sentence was fixed |

Each was found by a reviewer, never by re-reading, and each fix made the next
one less visible rather than more.
The third is the sharpest: half a sentence was corrected and the other half of
the same sentence was not.

The remedy is the entry above's, unchanged --- derive the population and read
it end to end.
What this adds is when to distrust the feeling that you already have: a fix
that touched several instances is exactly the state in which the survivors are
invisible, so the sweep is most owed at the moment it feels least necessary.

- **Do:** re-derive the population after a multi-instance fix, not only after
  a reviewer finds a second instance.
- **Don't:** read corrected siblings as evidence the class is exhausted ---
  they are evidence about themselves and nothing else.

## The unit of repair is the figure, across every artifact carrying the twin

(`Lacaedemon/sparta#1222` and `#1225`, both 2026-08-07, both touching exactly
`.claude/memories/sparta.md` and `test/unit/test_residual_melee_swirl_battle.gd`
--- the twin pair.
Three misses in one PR lineage: #1222 round 2 fixed a reconciliation in one file
only; #1225 round 1 fixed the test header and left the memory copy; and within
that same PR a second wrong figure one sentence away kept its wrong attribution,
in a paragraph that edit had itself reflowed.)

## A body-staleness finding is answered by editing the body

(Morrison-Lab/ai-config#1384, 2026-08-10.
An earlier finding in the same PR was answered with a comment-only correction,
reasoned from the risk of drift in rewriting a long body assembled across
several rounds.
That reasoning was sound about the risk and wrong about the outcome.
The next round re-read the body and raised three stale figures --- a prose
figure its own commit `7fe25776` had corrected, plus a line count and a
diffstat --- and the fix was a body edit carrying a `Corrections to this body`
table, which round 3 then confirmed resolved and cited by name.
The three rounds cost `$11.1760`, `$8.4658`, and `$4.5018`; the last is the
confirming round.)

## A finding's precondition can dissolve before you address it

(`Morrison-Lab/ai-config#1411`, merged 2026-08-13T05:27:13Z as `3bb24610`.
Its round-2 review, posted `2026-08-12T19:43:19Z`, correctly found the
sentence "which is what `Morrison-Lab/ai-config#1413` **then did**" asserting
a merge that had not happened, and proposed hedging it to "proposed in
`#1413`, not yet merged as of this writing".
`#1413` then merged at `2026-08-13T04:47:54Z`, and the fix landed in
`cccb404c` at `04:50:48Z` --- under three minutes later --- so the proposed
hedge would have been false by the time it was typed.
The sentence was instead re-derived to name the merge time and the byte
figures the split produced, each from `git show <sha>:<path> | wc -c`:
`ardi.md` 98,655 to 92,734, and `fail-fast.md` 94,469 to 91,244.)

## A finding's site list spans every branch in the stack

(`ucdavis/bcs`, 2026-08-13: a reviewer flagged issue numbers in source comments, a `CLAUDE.md` violation, on the base PR of a two-PR stack.
All three of that PR's files were swept and fixed; the stacked PR's file carried the same violation, was never in the search space, and was therefore never swept.)

## The fix for a finding reproducing that finding one level up

(`Morrison-Lab/ai-config#1787`, 2026-08-21, reconstructed from that PR's
commit list and posted reviews rather than from recollection.

An early round found a code block whose undefined variables made it silently
degenerate to `HEAD..HEAD` --- a step that looked like it ran and decided
nothing.
A later round found that nothing in the skill's completion checklist gated on
that step, which is the same defect one level up: a step no checklist item
covers can be skipped while the skill is reported complete.
Commit `f2c3fdc1` added the gating bullet --- and wrote it as "if the merge
brought in a hook", a condition the step's own body calls informational and
explicitly says decides nothing.
So the fix for "nothing gates on this step" shipped a gate that excuses the
step, in the same commit, for the same reason the finding existed.
Two rounds later, at `f90e7362`, the reviewer found it, and `99db8414` fixed
it.

What makes this hard to self-catch is that the fix is *written in the
vocabulary of the thing it corrects*, so re-reading it confirms the topic
rather than the claim.
A bullet about not skipping a step, which itself contains a skip condition,
reads as being about skip conditions and therefore as correct.
Distinct from the partially-applied fix above: there the survivors are
elsewhere and the corrected siblings hide them, whereas here the survivor is
inside the correction.

**The first draft of this entry got the chronology backwards, and that is
part of the record.**
It said the bullet was fixed first and the neighbouring step-number citation
found afterwards, and called that citation "the third" of its kind.
Both are false: `f90e7362` fixed the citation **before** `99db8414` fixed the
bullet, and the PR carried exactly two step-number citation errors, not three
--- the bullet's own defect is a gating-conditional bug, not a citation.
A reviewer caught it on the entry itself.
The lesson is narrow and worth keeping: a case record written from memory of
a lifecycle you personally drove is not a record, and the ordering is the
part that memory reshapes, because the fixes feel simultaneous in a way the
commits are not.
Reconstruct the sequence from the commit list before writing it down.)

3rd recorded occurrence, 2026-08-31, `UCD-SERG/shigella#46`.
Priors: the `ai-config#1787` case above, and `Morrison-Lab/gha#745`, whose
own `CLAUDE.md` records the class in the same words --- "a fix for a review
finding is the likeliest place for the next one" --- after a fix for an
unearned clean verdict shipped a fresh unearned clean verdict.
Here two adversarial-review rounds ran against one PR, and round 2's findings
were both located in text written to close round 1's.
A guidance paragraph added to fix an undercounted enumeration documented the
dispatch command in its unconditional form, dropping carve-outs the same
session had applied minutes earlier; see
[`fact-check-prose`](../writing/fact-check-prose.md)'s "A command written
into documentation is a condensation of the code that builds it".

4th recorded occurrence, 2026-09-02, `Morrison-Lab/gha#811`, across six
adversarial pre-push rounds returning 11, 11, 11, 6, 3 and 2 findings ---
counted from the branch's own commit messages, `21751be5` through `0262c1c6`,
rather than from recollection, which had dropped a round of eleven and read the
last round's two prose items as zero.
Two instances, both in fixes for **convention** findings: an over-long-line fix
put its break on a dangling `and` in each of five files, the uniformity
suggesting a single edit applied across them --- an inference, not something the
commits record; and a forward-reference fix reworded the pointer into a new
forward reference of its own, `README.md`'s "the audit described below", added
by `a8a45881`.
Round four's commit attributes two to that fix; only one is, since the other
pointer was introduced a round earlier by `385d4f43`, which fixed no forward
reference --- an over-count inherited here until it was checked against the
tree.

Only the forward-reference instance is a member of this section's class, since
its fix reproduced the very finding it closed.
The line-length one is the adjacent shape: the over-long line was fixed and
stayed fixed, and the fix introduced a *different* convention violation.
It is kept here because the remedy is identical and the class boundary is the
part that goes unnoticed.

A convention finding arrives *with* its instrument, and the corpus already says
to re-run that instrument over your own fix ---
[`ardi.cases.md`](ardi.cases.md)'s "Run the literal-verification check over
your own fix too" calls running the rule against the fix "the entire
mechanism".
Read at that general form it covers both instances; read strictly, its subject
is a literal-verification finding and neither of these is one, which is the
reading that let this session pass over it.

Two neighbouring rules look as though they would have caught these and do not,
which is worth stating so nobody else goes looking there:
[`semantic-line-breaks`](../writing/semantic-line-breaks.md) tells you to
re-run its gate after committing, but that gate enforces two predicates only,
multi-sentence lines and long lines carrying a mid-line semicolon.
A break placed on a dangling conjunction trips neither, and that fragment says
plainly why: detecting a clause boundary needs a syntactic parser the tooling
deliberately does not have;
and [`ardi`](ardi.md)'s added-line scan is scoped to banned punctuation and
multi-sentence lines.
So this occurrence adds no new rule, only a carve-out to the chain's conclusion
and evidence about how those places get missed: the fix is authored while
holding the convention in mind, and therefore feels exempt from it.

The chain above meets
[`deterministic-tools`](../principles/deterministic-tools.md)'s
third-occurrence bar and does not yield an instrument *for the general class*,
which is worth stating rather than leaving as a silent omission.
Whether a fix reproduces the finding it closes is a judgment about meaning,
not a condition decidable over a diff, so no hook can decide it.
The 4th occurrence above carves out a narrower subclass still: a finding whose
detector would also flag the fix.
That held for its forward-reference instance, so the carve-out reads "run the
check the finding came with, when that check can see the fix" --- a subset of a
subclass rather than a general remedy.
The procedural equivalent already exists and simply has to be run: the fix is
"a diff nobody has read", per
[`adversarial-self-review`](adversarial-self-review.md)'s "The review gates
the push, not the work", so brief the reviewer on the **fix** commit rather
than treating the round as closed once the finding is addressed.

## A correction added beside the flagged sentence, which survived

(Morrison-Lab/gha#578, 2026-08-21, review round 2: a source comment overstated
that "the checkout under review stays untouched".
Round 1 had flagged the surrounding block for other reasons.
The fix added an accurate disclaimer a few lines above the overstated
sentence --- "guard rails, NOT a security boundary ... writes wherever the
runner account can" --- and left the overstated sentence itself standing.
Round 2 caught the resulting self-contradiction, and noted that the commit
message's claim to have "drop[ped] the false boundary claim" was only half
true: the claim was contradicted, not dropped.
The eventual fix deleted the overstated sentence outright, and the next
round's grep for its wording returned nothing.)

## A repro that raised only against a newer signature

Measured 2026-08-22 on
[ai-config#1992](https://github.com/Morrison-Lab/ai-config/pull/1992).

A review found that making a helper's argument required forbids omission and
not a wrong value, and demonstrated it with
`_git_config(directory, "--get", key, [])`.
Run against the branch head of
[ai-config#1911](https://github.com/Morrison-Lab/ai-config/pull/1911), that
call raised
`TypeError: _git_config() missing 1 required positional argument: 'env'`,
which read as the reviewer having shipped a broken example.

It had not.
The review named the commit it read, `cf6c47ce`, where the signature was
`(directory, flag, key, argv, as_bool=False)` --- five parameters, four of
them required, so the four-argument call binds:

```
cf6c47ce params: ['directory', 'flag', 'key', 'argv', 'as_bool']
4-arg call BINDS -> no TypeError
```

`51be639e` added `env` as a fifth required parameter.
It was committed at 21:06:09Z, and the review run
([32598271976](https://github.com/Morrison-Lab/ai-config/actions/runs/32598271976))
started at 20:59:25Z --- six minutes and forty-four seconds earlier.
The branch moved under the reviewer.

The finding itself was correct at both commits: `_config_overrides([])`
returns `[]`, so an empty `argv` derives no overrides and reaches a bare
`git config` read.
It was Addressed.

The reply written at the time asserted the reviewer had made an arity slip,
and a first draft of the rule above was built on that reading.
An adversarial review of that draft caught it.
Reproducing at HEAD rather than at the reviewed commit is
[`verify-the-right-artifact`](verify-the-right-artifact.md)'s "a checkout for
the run" substitution --- the artifact in hand was real, was read carefully,
and was not the one the claim was about.

## "A peer's edge cases raised against a different implementation"

Measured 2026-09-02 PT, recorded 2026-09-03.
Re-derivable from four artifacts, named here because the first two drafts of
this record were written from a filed summary instead and were wrong twice:

- `hooks/test-warn-stale-review-diff-base.py` on `main` --- the `git -C` cases.
- `hooks/warn-stale-review-diff-base.py:96` --- the pattern whose bound decides
  what "coverage" means here.
- [ai-config#3014](https://github.com/Morrison-Lab/ai-config/pull/3014)'s
  comment thread --- the peer's flag, and the duplicate-and-revert report.
- `memories/session-2026-09-02-gia-ai-config.md` --- the banked correction.

A peer session flagged two edge cases from an adversarial pass on **its own**
draft of a similar hook, and asked whether they applied here.
Both already passed.

**They were not pinned, and the reason is the more useful half of the record.**
The first instinct was to add regression cases for both shapes.
They were verbatim duplicates.
`hooks/test-warn-stale-review-diff-base.py` already carried four `git -C` cases
--- a temp directory, a path containing spaces, `~/repo`, and a bare basename
--- all introduced by commit `879f2273`, which is #3014's own merge.
The added cases were reverted.

Coverage was established by **mutation** rather than by reading: breaking the
guard turned the pre-existing cases red (78/80 and 79/80), which is what proved
the shapes were covered.
That is the transferable step.
A claim that something is untested is a claim to check, not to act on, and
checking it means breaking the thing and seeing what goes red.

**The path-length framing was wrong on both sides, which is worth more than the
episode itself.**
The peer's concern, and the summary that carried it forward, both turned on a
*long* `git -C <path>` prefix being unpinned.
Path length is not a property the guard can respond to at all:
`warn-stale-review-diff-base.py:96` bounds the prefix by **option count**,
`){0,12}`, with each value matching `\S+`, and its own comment says the cutoff
costs a missed reminder "past 13 `-c k=v` options".
So neither the worry nor the reassurance was about a dimension the code has.
When a peer names the property that makes a shape matter, check that the
implementation can see that property before measuring anything.

**How this record went wrong, stated exactly, since a vaguer version would
teach the wrong lesson.**
Two different errors, from two different sources:

- *Inherited.* The summary this entry was drafted from
  ([ai-config#3059](https://github.com/Morrison-Lab/ai-config/issues/3059))
  says the shape "was previously pinned only with short paths" --- singular,
  about one of the two shapes. It was filed at 02:10Z, and the session that
  discovered the duplication started at 02:27Z, so it is an earlier session's
  summary superseded by a later session's finding, not a session contradicting
  itself.
- *Invented.* The sentence a CI round actually caught --- that a future
  narrowing "now fails a test" --- appears nowhere in that summary. This entry
  wrote it. The first correction described the whole error as reproducing the
  summary unchecked, which was self-favourable: the worst claim was its own.

The CI round caught it by noticing a test claim in a diff that touches no test
file. Four adversarial rounds had not, because all four read the entry against
the summary rather than against the suite.
