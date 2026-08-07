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
[`fully-clean`](fully-clean.md)'s fifth case was handed over with a completion
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
