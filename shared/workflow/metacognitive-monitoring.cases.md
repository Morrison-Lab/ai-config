# Case records: metacognitive-monitoring

Worked-example case records for the rules in
[`metacognitive-monitoring.md`](metacognitive-monitoring.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## A premise you were handed is still a claim

(2026-07-30, auditing Claude token provenance: the user offered "this account
was out of tokens since Sunday I think?" and an entire repo classification was
built on it -- any review succeeding after that Sunday must belong to the other
account.
The hedge went unread.
The user then posted their usage chart, showing continuous usage across the
whole week and peaking the day after the supposed cutoff, which refuted the
premise and voided the classification.
The chart was one screenshot away the entire time.)

## The source need not be the user --- a reviewer's finding

(2026-08-01, a six-PR session in this repo: four findings were read,
dispositioned, and reported to the user as established fact, each without the
one cheap check that would have confirmed it, and the user re-sent the same
link three times before one was run.
A fifth surfaced while this entry was being drafted, so five were checked in
the end.
Across those five the conclusion held in five of five and the particulars were
wrong in five of five -- a guard whose failure was broader than reported, a
script that was not the one running, a cited line number with nothing at it, a
hardcoded-value scope that named 2 of 6 sites, and
a two-command failure whose first command failed with an error the finding
never mentioned.
The shape then recurred while this entry was being written, and took two
further passes to settle.
The observation recorded in
[`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s fifth case was
handed over with a completion
time of `04:08:13Z`, corrected here to `04:50:41Z`, and then retracted in that
file as an invented particular, on the grounds that `#1008` carried no
Copilot-attributable check run at all.
Re-measured 2026-08-03, the retraction is the step that was wrong: check run
`91327863807` on that head is named `copilot-pull-request-reviewer` and reads
`completed_at: 2026-08-01T04:50:41Z`, `conclusion: success`.
So the first correction held, and so did the conclusion drawn from it, a green
reviewer check with no review behind it.
It was the verification of the verification that carried a false particular
forward.

That does not rescue the pattern so much as relocate it.
The retraction came from querying a surface that omits this check run ---
[`fully-clean`](fully-clean.md)'s criterion 1 now names which surface, and
records that the reason for the omission is still unestablished --- and
nothing about the zero it returned announced that it was answering a narrower
question than the one asked.
A verification inherits the scope of whatever instrument it reaches for, so
"I checked and it is not there" stays a claim about the instrument until the
instrument's own coverage has been established.)

## A subagent's report arrives in the same position

(2026-08-05/06, a `ucdavis/bcs` session driving several parallel agents: two
subagent particulars were relayed to the user as established fact without the
one query that settles each.

A subagent reported `claude-review` "failing repo-wide in `Morrison-Lab/ai-config`
with `API Error: Usage credits required for 1M context`", and that was published
to the user as a boxed FLAG.
`gh run list -R Morrison-Lab/ai-config --workflow claude-review.yml --limit 60
--json conclusion,status` returns **36 success, 21 cancelled, 3 in flight, and 0
failures**, so the workflow was never failing at all.
The report's true neighbour is what made it survive: a review workflow *was*
failing repo-wide across the same window, but it was `Antigravity Code Review`,
4 failures, and its log gives a Google AI Studio 429 reading "Your project has
exceeded its monthly spending cap" -- a different workflow, a different vendor,
and a different error from the one reported.
So a spot check confirming that "a reviewer is down" would have confirmed the
wrong claim.

The second was flatter: an array job was described as "a 500-task array" across
several messages, inherited from an earlier framing.
`data-raw/msm-vs-truth.sbatch` reads `--array=1-100%3`.

**Provenance of the two sides.**
The **Don't** side came from the session itself rather than from a directive:
no user correction was issued, and the first claim was caught only when a later
subagent contradicted the first, forcing a retraction.
The **Do** side -- run the deriving query before relaying, and name it -- is
inferred, by carrying the reviewer-finding rule above onto the commissioned-report
case.
A search at the time found the general rule cited but never written:
`memories/preferences.md` appeals to "the standing `verify agent reports with
unfakeable asks` rule", and `unfakeable` occurs nowhere else in the corpus, so
only that rule's commit-SHA instance had ever been recorded.)

## Verifying ONE particular from a report does not transfer to the one beside it

(`Lacaedemon/sparta` #1281, 2026-08-16: an exploration subagent's report opened
a session with "`_default_loadout()` --- `scripts/Battle.gd:829-836` (four
entries: Spearmen, Infantry, Archers, Cavalry)".
Two independent particulars, one sentence.
The entry count was checked directly and found to be five, with two
byte-identical `Cavalry` entries, a real derivation returning a real answer.
The docstring claim was never checked, and "five entries, not the four types its
docstring describes" was published in that PR's body, inventing a contradiction
between the code and a comment nobody had read.
`scripts/Battle.gd:781` opens "The default battle loadout: spearmen, infantry,
archers, cavalry, cavalry", and `git log -S` dates that wording to #478, so the
docstring had never been wrong.

Both halves were one `sed` away, which rules out the reachable-half reading,
and they were separate claims rather than one claim restated, which rules out
the true-neighbour reading.
What carried the error was that they shared a sentence.

The review then confirmed the verified half in as many words, "the 'two
byte-identical Cavalry entries' claim is exactly what's in
`Battle._default_loadout()` today", which is true and silent on the docstring.
The clean verdict consequently read as corroborating the whole sentence.
Caught only when a later UMS pass re-derived the docstring claim while writing
the artifact-level entry, and reported the brief's own premise as false.)

## A hedge you attach for one audience is owed to the other

(Morrison-Lab/ai-config#1299, 2026-08-08: a timing relationship measured on that
PR was read as showing that a verdict comment's timestamp can postdate commits
the review never saw.
The conclusion was stated to the user in chat as a flat finding, and put into a
subagent brief minutes later with an explicit instruction to verify it, saying
the ordering was the whole point.

The subagent verified it and the field was wrong.
`created_at` is `18:08:08Z` and *predates* both commits, `a60d967f` at
`18:10:48Z` and `d426bf83` at `18:11:44Z`, so it is a sound anchor.
`updated_at` is `18:26:27Z`, and GraphQL reports the comment `isMinimized: true`
with `minimizedReason: "outdated"` -- a later run collapsed it, which is what
moved that field.
So the claim is false of the field anyone would anchor on and true only of one
nobody does.

```bash
gh api repos/Morrison-Lab/ai-config/issues/comments/5227428537 \
  --jq '{created_at, updated_at}'
gh api repos/Morrison-Lab/ai-config/pulls/1299/commits \
  --jq '.[] | {sha: .sha[0:8], date: .commit.committer.date}'
```

The brief's own hedge is what caught it, so this is also a case of
[`challenge-the-assignment`](challenge-the-assignment.md)'s authoring-side rule
working rather than being skipped -- and it is the reason the asymmetry was
visible at all.
The delegated copy carried a detector; the copy the user acted on did not.)

## An action you recommend is a claim about state

(2026-08-02, this repo: a boxed RECOMMENDATION advised merging `#1058` and
`#1064` "whenever you like", calling them independent and both carrying clean
verdicts.
Both had already merged, `#1064` at `2026-08-03T02:34:40Z` and `#1058` at
`2026-08-03T02:34:49Z`, roughly four minutes earlier, by a second account
rather than by that session.
`gh pr view 1058 --json state` returns `MERGED` and settles it in one call.
Because the recommendation carried no status word,
`hooks/no-stale-pr-status.py` could not fire on it either: its `ASSERT` list
is entirely state vocabulary and holds no imperative form, and its staleness
condition is anchored to a push of *ours*, which a third party's merge does
not produce.
Both halves are tracked in ai-config#1072.)

## Calling your own note stale is a state claim about that note

(2026-08-07, a `Lacaedemon/sparta` session: a Godot binary path failed, and the
session told the user that its memory note on that path was stale.
The note --- `reference-godot-binary-path-windows.md`, under this machine's
`~/.claude/projects/C--Users-dougm-Documents-Github-sparta/memory/` --- was
correct.
It gives the `Downloads` path that the failure had just shown to be the right
one, and it documents the very trap the session had fallen into one command
earlier: that `ls` on the folder path "succeeds" and prints the two exe names
while running the binary fails.
It had never been opened.
The path had been inferred from where the repo lives, and that note's
`MEMORY.md` index line names the folder-shaped exe name, the `_console`
variant, and the `C:/` form, but not the directory the note is about, so the
index alone could not have settled it either.
The file was accurate as written and needed no edit; only the claim about it
did.)

## Verification of the reachable half does not transfer to the unreachable half

(UCD-SERG/lab-manual#452, 2026-08-04: every claim about the cluster was
established empirically --- a loopback `ssh -X` probe, `ldd`, `capabilities()`,
`module avail`, `getent group sudo`.
Every claim about the reader's own computer was written from memory, in the
same table, and the Linux row asserted "your desktop session is already an X
server", which is false on the many distributions now defaulting to Wayland.
Review caught it; nothing in the verified half could have.)

## Search for the artifact instead of arguing about whether it would exist

(2026-08-01, `UCD-SERG/ucd-serg.github.io#89`: a review workflow's
`pull-requests` permission was narrowed to `read`, justified by the argument
that "the action posts with its own app token, so the workflow token does not
need write".
The argument was wrong, and two Copilot reviews restated it without objection.
One query --- whether a `claude`-authored comment existed on any earlier PR ---
returned zero across the workflow's entire month of operation, which settled
both the mechanism and the fact that reviews had never once posted.
Nobody ran it until a fourth PR was opened to fix the consequence.)

## Ask whether a candidate can produce the effect at all

(`Lacaedemon/sparta#1222`, merged 2026-08-07 as `320fe3b2`: two regiments locked
in melee rotated about each other by 56 degrees over 700 ticks (56.14 headless
Windows, 58.0 Linux), and the rotation was attributed to `Unit._press_into()`.
That function is six lines, and the operative one is
`position += to.normalized() * move_speed * MELEE_PRESS_FRACTION * delta`,
over `var to: Vector2 = point - position`, called from its one call site as
`_press_into(enemy.position, delta)`.
That displacement lies along the line joining the two regiments, so it changes
the separation's length and never its bearing --- it cannot rotate the pair
however large it is, and reading those six lines would have said so for
nothing.
The one qualification is the two `clampf` lines that close the function, which
bound `position.x` and `position.y` against `field_bounds` independently and so
can truncate one component at a field edge; the measured pair was mid-field,
where they never fire.
Instead the candidate was instrumented, credited, published, and refuted in
review, and the corrected attribution puts `_press_into` at 0.002 degrees of
bearing rotation against `SoldierBodies.couple`'s -59.163 of that run's -59.16
total.
The confirming evidence had been that the two bodies' contributions were
exactly anti-symmetric --- which is what a central pair looks like, and so was
the disproof.
Checked here against `origin/main` at `320fe3b2`, and against the identity
`dtheta = cross(r_hat, dr) / |r|`, which returns exactly zero for a radial `dr`
and matches the exact bearing change to five decimals for a tangential one.)

## A correction inherits its instrument, so a second reading is not a check

(2026-08-05/06, `ucdavis/bcs#587`: cluster CPU efficiency was reported to the
user as "~35-40%, each task reserves 24 cores and uses a third", filed into the
issue, and then corrected in a comment to "~87%, the nodes are well utilized".
Both figures came from `sinfo`'s `CPU_LOAD`, and the instrument was never
questioned in either direction.
A mechanism was also offered for the higher figure --- that co-resident tasks
interleave, one task's serial phase filling another's parallel phase --- which
the partition forbids: `SelectTypeParameters = CR_CORE_MEMORY`,
`TaskPlugin = task/affinity`, and `OverSubscribe=NO`, so cores are exclusive
and pinned.

`CPU_LOAD` is a value `slurmd` last pushed rather than a live reading.
Measured on node `c2` by polling `sinfo -h -n c2 -o %O` against that node's own
`/proc/loadavg` every 5s: it held `21.07` across 49 consecutive samples, 245
seconds, while the live 1-minute load fell monotonically from 24.49 to 1.83,
then stepped to `12.22` and held while the live figure fell to `0.81` at the
last logged sample.
A separate 12-sample run caught the opposite error, `17.86` against a live
24.35-24.45.
That the errors run in both directions is what rules out treating it as a
biased-but-usable gauge, and it is why two samples of it minutes apart produced
contradictory conclusions with neither being a correction of the other.

The near-miss worth recording is the cross-check that would not have helped.
On a read taken moments after the poll stopped,
`scontrol show node c2` reports `CPULoad=12.22` at the same moment
`sinfo -o %O` reports `12.22` and `/proc/loadavg` reports `0.65`, so the
obvious second command prints the same cache.
Only a different kind of source --- the file the daemon samples, rather than the
daemon's copy of it --- settled it.

Recorded for that cluster in `ucdavis/bcs#592` / `#593`; the correction to
`#587` had to reach both the issue body and its comment thread, because by then
the retracted figure and its retracted replacement were in different places on
the page.)

## A re-measurement with a different instrument

(2026-08-12, `ucdavis/bcs#615`: a PHI-count figure was published as a
correction when it was a second measurement.

`.github/workflows/check-phi.yml` there pins
`Morrison-Lab/gha/.github/workflows/check-phi.yml@v2`.
`git rev-parse v2` in `gha` is `e7291ccd7171e2f0ac8eb730707ca916795e737e`,
which is PR #445's own merge commit, while `origin/main` is
`695fbf56cf65d7779123e24782a40d80782386e1`.
The two differ in the operator alternation of `check-phi/check-phi.py`'s
`_STUDY_ID_RE`: `v2` has
`(?:\s*(?:<<-|<-|!=|==|=|:)\s*|\s+(?:eq|ne)\s+)`, and `main` adds
`|\s+(?:not\s+)?in\s*\(\s*` from gha#454.

Both revisions extracted and run whole-tree (`PHI_BASE_REF` empty) against
clean worktrees:

| detector | tree | allowlist | findings | files |
|---|---|---|---|---|
| `v2` | bcs `origin/main` `d638c05` | absent | 93 | 19 |
| `main` | bcs `origin/main` `d638c05` | absent | 99 | 21 |
| `v2` | bcs#615 head `3f529db` | real | 0 | 0 |
| `main` | bcs#615 head `3f529db` | real | 0 | 0 |
| `v2` | bcs#615 head `3f529db` | empty | 92 | 19 |
| `main` | bcs#615 head `3f529db` | empty | 98 | 21 |

Diffing the two annotation streams shows the whole delta is SAS's membership
form: 6 findings, every one of them on a line matching `(?i)\bin\s*\(`, at 6
sites across 4 files.
The summary's file count moves 19 to 21 rather than to 23 because 2 of those 4
files were already flagged under `v2` --- so "6 sites in 4 files" and "a
2-file delta" are two different quantities, both correct, which is the
labelling hazard `algorithmatize-checks` warns about arriving inside the
evidence for this one.

Neither figure retires the other.
93 is what that repository's CI reports today, because it pins `@v2`.
99 is what it will report once `v2` slides past gha#454.

The round-4 comment nonetheless said "I earlier told the maintainer that
`main` carried **93** findings.
The derived figure is **99**.
I had not run that measurement when I first stated it, and the number was
wrong."
Both halves are false: an earlier comment on the same PR had derived 93
explicitly, showing `git rev-parse v2` first, and 93 remains correct for the
pinned revision.

The aggravating detail is where the qualifier survived.
That same comment's table was correctly captioned "Measured with `gha`
`main`'s detector", and the Correction paragraph three lines below it dropped
the qualifier.
The honest caption and the misleading claim were in one comment, and the
quotable paragraph was the wrong one.

Retracted in a later comment on the same PR.
That retraction then misattributed the governing rule to `fail-fast.md`,
corrected in a follow-up once
`git grep -n "A correction inherits its instrument" -- shared/` was actually
run --- which is the same read-versus-recall failure one artifact over.)

## Writing is the instrument, when the claim can be wrong

(Same session: writing a docstring that had to state precisely how a correction
behaved across two study arms is what exposed the claim "relative error is
identical across arms" as false, because the precision forced a computation
that contradicted it.
Tabulating the node types in a diagram is what exposed that four of them sat on
three different scales.
Against that, most of that hour's writing was post-hoc recaps: well organized,
tabulated, and incapable of surfacing anything, since everything in them was
settled before composition began.
The user corrected roughly every three minutes throughout, several times on the
same underlying failure, while the polished output continued.)

## Stripping is the part that tests

(2026-07-30, this task's own brief: long, complete, and carrying several false
claims about this corpus that survived precisely because writing it required
justifying nothing.
One --- "model on the two existing `Stop` hooks" --- would have had to earn its
place under a stripping pass, and one `ls` settles it.)

## Relationship to neighbouring rules --- the five confidently-wrong claims

(2026-07-30, a `ucdavis/bcs` session: the five most confidently asserted claims
were all wrong, and each was one command from being settled.
A leaked credential was described as having gone into a *public* PR, when the
repository is private with three direct accounts.
This corpus was said to ship no hooks, from a grep against a checkout 27
commits behind.
A PR was reported green and conflict-free from a query returning 11 passing and
4 pending, taken before three of that PR's own later pushes.
A changelog count of ten was reported as nine, because the regex matched only
one of two link forms.
And a blocking `Stop` hook was called the right shape for a new rule, when it
would have suppressed error admissions.
The directives were "cai: use metacognition", "cai: think before you speak;
question yourself", and "cai: question your generative intuitions".)

## Key on claim type --- a "blocked" assertion is a state claim

(2026-08-07/08, this repo: a status report called
`Morrison-Lab/ai-config#1278` blocked, on the grounds that it appends to
`shared/workflow/fully-clean.md`, "already 1304 lines against a 1200-line gate".
No part of that was checked.
`scripts/check-memory-file-size.py` defaults to `--directory memories`, so run
plain it prints "No memory file exceeds 1200 lines." and exits 0; issue #1236,
cited as the gate, describes it as "the advisory 1200-line gate" and had to pass
`--directory shared/workflow` explicitly to produce a number at all.
`validate` passes on that branch with the file at 1453 lines.
The line count was wrong in both directions too --- 1397 on `main`, 1453 on the
branch, 1279 when #1236 was filed --- so the figure matched nothing.
A blocker is a claim about a gate's current state, and one command settles it:
run the checker, then read the check's own result on the PR.

Drafting the correction produced the mirror error, which is the more useful
half.
Reading the size gate's test with a truncated `grep ... | head -20` returned
only lines from its synthetic-fixture helper, which supported concluding that
the test never touches the real corpus and that issue #1221's "the next addition
will fail `validate`" was itself false.
It is not false.
`scripts/test_check_memory_file_size.py` asserts at module level that "this
repo's own memories/ is under the 1200-line default", `validate.yml` runs it,
and that is why `memories/git.md` sitting at 1199 lines has headroom of exactly
one.
The first claim came from never running the query; the second from running one
whose scope `head` had cut off --- the same failure with an instrument in front
of it, per "Illusions of knowing have an exact software form" in
[`metacognitive-monitoring.md`](metacognitive-monitoring.md).)

## The asymmetry inverts for a reviewer's incidental all-clear

(`Morrison-Lab/ai-config#1278`, 2026-08-08, cost two rounds.
Round 1's review was reporting a different finding when it noted in passing that
"the `Verdict:\s*(?:Clean|Approved|Ready)\b` pattern is safe because it requires
immediate adjacency after `Verdict:`", with the evidence attached: "verified:
`classify_verdict("Verdict: Not Ready")` correctly returns `''`, not
`'clean'`".
Both halves are true.
The measurement is reproducible, and it varies the qualifier on one side only ---
`Not` precedes the phrase, and adjacency to a label does constrain what precedes
it.

The round-2 comment repeated the conclusion as though it covered trailing
qualifiers too, and a code exemption was written around it, `if pat in
BARE_CLEAN_PATTERNS`, so the labelled pattern skipped the position, negation, and
conditional checks the same rounds had just built.
Round 3 reproduced `Verdict: Ready for merge, but not until it addresses the
following` and `Verdict: Ready for merge once the following items are addressed`
as clean --- the one path in the function that had been declared safe in
writing, and, as the review put it, the one "surviving through the one code path
that was assumed safe without evidence".

The test suite reproduced the same scope error rather than catching it: the only
case touching that pattern was named "'Verdict: Ready' needs no guard (adjacency
already binds it)" and asserted the bare label with nothing following it.
Note the shape is the two-sided qualifier error from `fail-fast.md` one level up:
there a guard covered the before-side and missed the after-side, here a
*premise* did, and the premise then licensed skipping the guard entirely.)

## A symptom that both a mechanism and its opposite predict

(Morrison-Lab/ai-config#1395 / #1407, 2026-08-12: two false mechanism claims
landed in `scripts/test_ai_session.py` during one PR.
The second is the one recorded above.

A helper needed a reliably dead PID, so it orphaned a child, killed it, and
polled `kill -0` until that failed.
The loop did not terminate promptly, and a comment was written to justify the
design around that: PID 1 in this container "does not reap", so a killed orphan
"stays a zombie" permanently, and `wait` from a non-owning shell is "a no-op".

Both halves are false, and both were decidable by one probe.
Re-measured for this entry, 2026-08-12, `uname -sr` = `Linux 6.18.5-fc-v20`:

| probe | result |
|---|---|
| `ps -o comm= -p 1` | `process_api` |
| immediately after the kill | `stat=Z`, `ppid=1`, `kill -0` returns **0** |
| `wait <pid>` from a shell that never owned it | `pid N is not a child of this shell`, rc **127** |
| poll `kill -0` at 5 ms until it fails | reaped after 225 polls, **1573 ms** |

So PID 1 does reap, at roughly 1.6 to 2.0 seconds, and `wait` on a non-child
errors rather than doing nothing.
A companion entry, "`kill -0` reports an unreaped zombie as alive", is proposed
in #1407 --- once merged, it lives in `memories/claude-code.md` and owns those
container facts and their volatility caveat.

The methodological point is that **the symptom could not have told anyone which
mechanism was operating.**
A poll loop that keeps seeing `kill -0` succeed is exactly what "PID 1 never
reaps" predicts, and exactly what "PID 1 reaps asynchronously, about two seconds
from now" predicts too.
The true mechanism was the opposite in kind --- reaping happens, and the loop
was losing a millisecond-scale race, re-losing it on each retry because every
retry spawned a fresh PID --- and no amount of re-reading the comment, or
re-running the failing loop, would have separated the two.
The discriminating observation was the same one held longer.

The direction of the error is the part worth carrying: the immediate look
supported the stronger claim, permanence, and the cheaper observation was the
one that would have refuted it.)

## A retraction is only as good as the instrument's reach

(`Morrison-Lab/ai-config#1281`, 2026-08-07: a review cancelled with no verdict
was explained by `concurrency: cancel-in-progress`, correctly.
Asked to check, the session grepped the **caller** workflow,
`.github/workflows/claude-review.yml`, found no `concurrency` block, and
retracted the explanation to the user as something carried over from another
repo's setup without checking.
That caller is 68 lines and delegates to
`Morrison-Lab/gha/.github/workflows/claude-code-review.yml@v2`, which declares
the group at job level, line 328 of 1091, beneath a 25-line comment describing
this exact race.
The grep was sound and covered 68 lines of a call chain over 1150 lines long,
so it could not have returned a hit whether or not the claim was true.
`memories/github-actions.md`'s "A caller with no `concurrency:` block can still
have its runs cancelled" had recorded the same fact two days earlier, from
PR #1224, and was not consulted.)

## "Unresolved between two sources" is a place to stop checking, not a finding

(Morrison-Lab/ai-config#1238, 2026-08-07: a reviewer's `gh pr view --json
comments` reported a comment's `author_association` as `COLLABORATOR`; this
session's own tool call reported `MEMBER` for the identical comment id.
Rather than run one more check, the memory being edited was corrected to
state both readings as an unresolved cross-surface disagreement -- which
was itself wrong, and became the review's next finding.
A third check, `list_repository_collaborators`, resolved it in one call: the
account held a direct collaborator grant, matching `COLLABORATOR` and
explaining the `MEMBER` reading as this session's own tool's outlier.
The "unresolved" framing cost a full review round it did not need to.)

## A cause read off the step next to the one that failed

`Morrison-Lab/ai-config#1583`, 2026-08-17.
A `claude-review` job completed its review and then failed at step 20, "Post
review comment", one second later.

Step 20's own log was not read.
A sibling step running one second earlier printed an env block showing
`PR_NUMBER:` empty, and that was reported as the likely cause --- a plausible
story, since a posting step with no PR number would indeed fail instantly.

Reading step 20's own log refuted it.
Its env showed `PR_NUMBER: 1583`, and the actual error was
`HTTP 503: No server is currently available to service your request.
(https://api.github.com/graphql)` from `gh pr comment`, followed by
`##[error]Process completed with exit code 1.`
The empty variable belonged to a different step, which had **succeeded** with
`outcome=success;conclusion=success;duration_ms=39`.

Two details are what make it a case record rather than one bad guess.

The wrong diagnosis was **more specific** than the right one would have been at
that moment, and specificity is what made it persuasive: it named a variable,
a value, and a timestamp, all of them real.

And the two diagnoses made **opposite predictions** about the remedy.
An empty `PR_NUMBER` is a configuration defect, so a plain re-run would
reproduce it and the fix would be a dispatch or workflow-input change.
A 503 is transient, so a re-run should simply work.
A single `rerun_failed_jobs` recovered the run and the verdict posted, which
the 503 diagnosis predicted and the `PR_NUMBER` diagnosis ruled out.

## Five sound measurements, five claims beside them

`ucdavis/bcs`, 2026-08-19/20.
One session produced the same error five times, across five distinct claims
--- instances 2 and 3 arose within the same investigation, the rest in
unrelated domains --- each instance surviving self-review.
The recurrence is what makes it a case record: per
[`deterministic-tools`](../principles/deterministic-tools.md)'s third-occurrence
bar, a third instance is the point at which the shape gets written down rather
than fixed one more time.
The fourth and fifth arrived while this entry was being written, which is
itself evidence about how easily the shape passes self-review.

**Instance 1 --- a verified mechanism, an unverified instance.**
Roxygen prose claimed that this repo's own symbol tracer beats
`codetools::findGlobals()`, because "a bare `map()` relies on the standalone
import, which `data-raw/` does".
The mechanism half was measured: code was run confirming that `findGlobals()`
drops namespace-qualified call heads, so `purrr::map()` never reaches the
standalone `map()`.
The instance half was not.
The one `data-raw/` file carrying bare `map()` calls has `library(purrr)` above
them, so it does not rely on the standalone import at all.
A reviewer caught it.
The measurement establishes a fact about `findGlobals()`.
The claim was about the contents of a directory.

**Instance 2 --- a freshness check that settled the model, reported as
settling the data.**
An analysis artifact was regenerated, and its freshness was verified by
checking that its coefficient terms matched the current model specification ---
`age_monthly` present, the obsolete `age2` and `age75` absent.
That check is sound, and it proves the artifact came from the current
**model**.
The numbers were then reported as "verified".
The check says nothing about which **population** was fed in, and the
population was the live question.
One measurement, two axes, and only one of them measured.

**Instance 3 --- a measured difference, read as a measured direction.**
Following on from instance 2, two candidate data extracts were compared, and
the comparison was run correctly: they are different populations, differing in
sites and by roughly 410,000 participants, with neither a subset of the other.
From that, the session concluded the analysis had run on the *wrong* extract
and publicly retracted the numbers.
The comparison establishes only that the two **differ**.
Which one is current is a separate fact the session did not hold, and the
maintainer confirmed the extract actually used was the correct one --- the
documentation relied on for the retraction was the stale half.

Instance 3 is the one that fixes the shape as an inference error rather than
as optimism.
Here the overreach ran toward **alarm**: it retracted a true result, in public,
on the strength of a sound measurement of something else.
A rule watching for over-claiming would have passed it, and the act of
retracting made it feel more careful than the claim it replaced.

**Instance 4 --- a complete enumeration of branches, reported as an
enumeration of refs.**
A commit carrying a leaked credential (`5da971a1`) was squash-merged and its
PR closed.
`git branch -r --contains 5da971a1` returned nothing, and that was reported to
the maintainer as the commit being "no longer reachable from any remote ref",
with the exposure closed as far as git could close it.
`check-secrets` flagged the same six findings on the next PR.

This is the sharpest of the five, because the measurement has no defect at all.
`git branch -r --contains` correctly enumerates the branches containing a
commit, and it returned the right answer for that question.
The claim was about **refs**.
Branches are a proper subset of refs, and the excluded subset is the one that
decides this particular question: GitHub retains `refs/pull/<N>/head`
permanently, and closing a PR or deleting its branch does not remove it.
The default fetch refspec is `+refs/heads/*:refs/remotes/origin/*`, so
`refs/pull/*` is never fetched and `git branch -r` cannot see it whatever the
repository state.
The other instances admit an argument that the measurement was incomplete.
Here it was complete and correct for its own scope, and the scope was silently
widened by one word in the sentence that reported it.

The consequence was operational rather than only epistemic.
The conclusion licensed a recommendation *against* adding `.gitleaksignore`
entries, on the reasoning that squashing would clear the finding.
It does not, so the repository carries a permanently red security check until
the allowlist lands --- the opposite of what was advised.

Writing the population into the sentence is the whole fix, and it costs one
word.
"No branch contains it" and "no ref contains it" differ by one word, and the
first is what the command established.

**Instance 5 --- an accurate pass and fail count, reported as the suite
passing.**
A default path was changed, the affected test files were run, and "43 pass, 0
fail" was reported as evidence the change was safe.
A reviewer then found a test the change had broken.

The count was accurate.
The **skip** count was never read: 15 tests were skipped, and the skipped set
contained exactly the broken test.
It skipped because `skip_if_not_installed("arrow")` fired, and `arrow` was
absent because the verification command carried `R_PROFILE_USER=/dev/null` ---
a habit picked up as a workaround for an unrelated renv startup failure.
Measured both ways in `ucdavis/bcs` on 2026-08-20:

```
R_PROFILE_USER=/dev/null : requireNamespace("arrow") -> FALSE
renv active              : requireNamespace("arrow") -> TRUE
```

Re-running with renv active, after fixing the test, gave 40 pass, 0 fail, 0
skip.
The two runs' totals are not comparable --- 43 passed plus 15 skipped is 58,
against 40 --- and this record does not establish what changed between them,
so the load-bearing figure is the 0 skip rather than either pass count.
Reporting them as comparable would be this section's own error committed
inside its own case record.
A suite in which roughly a quarter of the tests did not execute (15 of 58) has
not reported that they pass.

The second lesson is in *why* the skip happened.
`R_PROFILE_USER=/dev/null` is a documented workaround in that project, and its
side effect is invisible at the call site.
It changes which packages are available, hence which tests run, while changing
nothing about the number that gets reported.
That generalizes past R.
Any flag that skips environment setup --- a `--no-config`, a bare interpreter,
a container built without the optional extras --- can shrink what is being
measured without shrinking the figure reported.
The shrunken run is usually the faster one, so the habit is self-reinforcing.
