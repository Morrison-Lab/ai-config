"Fully clean" is the terminal state the ARDI review loop drives toward.
A PR/MR is **fully clean** when **both** of these hold (and verified via `python3 scripts/check-pr-fully-clean.py <pr-number>`):

Extended rationale --- the mechanism, evidence, and argument behind
each rule below --- lives in
[`fully-clean.rationale.md`](fully-clean.rationale.md),
moved out of the auto-loaded context.
Each rule here keeps its statement and its Do/Don't pair;
read the companion when the reasoning or the evidence is the question.

Worked-example case records for the rules below live in
[`fully-clean.cases.md`](fully-clean.cases.md), moved out of the auto-loaded context.

1. **All CI workflows and check runs are green AND completed.** Every workflow and check run passes --- not just the required checks and not just the review job.

   **`status` itself can be stale, so never infer a job's *duration* from it.**

   - **Do:** read elapsed time from log timestamps whenever the length of a
     run is the thing being judged.
   - **Don't:** conclude a job is still running, or has passed some duration
     threshold, from `in_progress` plus the wall clock.

   **When you are waiting for a job rather than timing one, poll its step list
   instead of its status --- the steps are not subject to the same lag.**

   - **Do:** poll `actions/jobs/<id>`'s `steps[]` when waiting on a specific
     job, and treat its terminal step completing as the signal.
   - **Do:** report which step the job is on, so a stalled job is
     distinguishable from a slow one.
   - **Don't:** poll a check run's `status` in a loop and read repeated
     `in_progress` as evidence the job is still working.

   See [`fully-clean.cases.md`](fully-clean.cases.md),
   "Poll a job's step list, not its check-run status".

   **A `BlobNotFound` / HTTP 404 on the job-log fetch means the job has not completed, not that it has hung.**

   - **Do:** read a 404 / `BlobNotFound` on the job-log endpoint as "the job has not finished", and wait for completion (or read the live UI log) before judging its outcome.
   - **Do:** take a job's real state from its `status`/`conclusion`, since the same 404 covers a still-running job and a completed-with-no-logs one.
   - **Don't:** read a 404 on the log fetch as positive evidence of a hang or a stall --- it is the opposite, evidence the job is still running.
   - **Don't:** file an issue reporting a review job as hung or "no verdict produced" while its log fetch still 404s and its status is `in_progress`.

   **`gh pr checks` is not a complete enumeration of a head's check runs, so
   read the commit check-runs endpoint before deciding that everything has
   finished.**

   **`--paginate` is load-bearing, not tidiness.**

   **The endpoint covers check runs only, so a repo that still uses legacy
   commit statuses needs a second query.**

   **Why the two surfaces disagree is unexplained, so do not assert a
   mechanism for it.**

   - **Do:** take the check-run half of criterion 1 from the paginated
     check-runs endpoint, and add `commits/<sha>/status` where the repo uses
     commit statuses, rather than treating either query as sufficient alone.
   - **Do:** report both counts when the endpoint and the rollup disagree, so
     the gap stays visible to whoever reads the status next.
   - **Don't:** read `0 pending` from `gh pr checks` as evidence that nothing
     is still running.
   - **Don't:** drop `--paginate` --- an unfinished run on page 2 returns the
     same empty result as a finished head.
   - **Don't:** offer a reason for the omission --- none was established.

   **Every subsection above explains a check list that is short for a per-PR
   reason, and a platform outage produces the same shape for a reason none of
   them can reach.**

2. **The latest review is totally clean:** no nits, and every item that wasn't directly **Addressed** is either **Deferred** to a tracked follow-up issue, or **Rebutted with a rebuttal that actually convinced the reviewer** --- i.e. the reviewer did *not* re-raise it on the next round.

**Criterion 2's test is the absence of findings, not the presence of a verdict
line saying so.**

So when the two disagree inside one comment, **the findings win**.
Read to the end of the comment before calling anything clean, and count the
items under every heading, whatever that heading is called ---
[`address-every-comment`](address-every-comment.md) already establishes that
"non-blocking", "nit", "minor", and "optional" are prioritization labels rather
than a pass, and a reviewer files findings under exactly those words in the
section that contradicts its own verdict line.

**Both criteria are per-PR, and a stack is where that stops being automatic.**
Everything above reads as being about "the PR" because a session normally has one.
Two stacked PRs are one unit of *work* and two units of *evidence*, so every check here is owed twice --- and the phrase "I read the review" silently becomes ambiguous the moment a second PR exists.

The failure needs no carelessness, only adjacency.
Stacked PRs are reviewed within seconds of each other by the same reviewer, their comments look alike, and they are usually open in the same status sweep.
So an impression formed from one PR's verdict transfers to the other without anything asserting it, and the transferred impression is *correct about a real review* --- just not that PR's.

Two things make it survive the round.
A reviewer that refuses on one PR looks like an answer for the pair, whereas [`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s fifth case already establishes that reviewers fail independently --- and the same independence holds across PRs, so one reviewer's refusal on the stacked PR says nothing about whether a different reviewer posted there.
And the stacked PR is the one whose evidence gets skipped, because the base is what the session is attending to.

Settle it per PR, from the `**Claude finished` body marker rather than from recollection, and say which PR each verdict came from when reporting the pair:

```bash
for n in <A> <B>; do
  printf '%s: ' "$n"
  gh api "repos/<owner>/<repo>/issues/$n/comments" --paginate \
    | jq -s '[.[][] | select(.body | startswith("**Claude finished"))] | length'
done
```

- **Do:** derive a verdict per PR number, and name the PR beside each one.
- **Do:** treat a refusal from one reviewer on one PR as evidence about that reviewer on that PR, and nothing else.
- **Don't:** report a stack's review state from a single read --- "I read the review" is a per-PR claim, and the stack is what makes it read as a claim about the work.

(`ucdavis/bcs`, 2026-08-13: two stacked PRs were reviewed 82 seconds apart, `16:26:16Z` on the stacked PR and `16:27:38Z` on its base.
The base's verdict was read, a Copilot quota refusal was seen on the stacked PR, and the pair was reported as one verdict plus one refusal.
The stacked PR's own review had posted and sat unread for 12 hours; the next round re-raised both of its findings and noted the file was byte-identical across the three intervening commits.)

**The disagreement is measurable, and it is not a wording problem.**

**A reviewer's own verification block can be wrong while its verdict is
right.**

- **Do:** re-derive a posted verification's groups, not just its total.
- **Do:** fix the wording that invited a wrong reconstruction, even when
  nothing in the diff was false.
- **Don't:** let the word "verification" stand in for having verified.
- **Don't:** read a table that sums as one that partitions correctly.

**A clean verdict can ratify an enumeration instead of testing it, and then it
reads as independent corroboration of a false scope claim.**

- **Do:** derive any enumeration you publish with a command, and publish the
  command beside it.
- **Do:** treat a reviewer restating your count as that count still being
  unverified.
- **Don't:** read a clean verdict as evidence that a scope claim in the diff is
  complete --- a reviewer can only check the members you named.
- **Don't:** count a reviewer's agreement as independent when its population
  came from your own prose.

**What "an approving review" means here is not a review state.**

- **Do:** read the whole review comment and count findings under every heading
  before calling a PR clean.
- **Do:** establish approval from the findings and thread lists, since `.state`
  is `COMMENTED` on every review this repo receives.
- **Don't:** quote a **Ready for merge** line as the clean signal while the same
  comment lists findings.
- **Don't:** wait for a formal `APPROVED` review, or read `COMMENTED` as a
  defect in the reviewer.

**Findings hide on several surfaces,
and no single check sees all of them --- so read the verdict body,
any suppressed-comments block,
the inline comments,
the thread list,
and the verdict's own conclusion every round.**

- **An out-of-diff finding never becomes a thread.**
  A finding about a line the diff did not touch cannot be attached as an
  inline comment, so it appears only in the body --- reviewers say so
  explicitly ("inline comments were unavailable for out-of-diff lines").
  A thread count therefore cannot see it.
  Zero unresolved threads is not evidence of zero findings.
- **An empty body hides the mirror case.**
  A review can post a completely empty top-level body and carry its entire
  finding in one inline comment, so a body-only read finds nothing to act on
  and concludes there is nothing.
- **A clean overview can hide a collapsed findings block.**
  Copilot can say it "generated no new comments"
  and create zero inline comments
  while placing substantive findings inside a collapsed
  `<details>` suppression block in the review body.
  The heading moves,
  so match case-insensitively on `suppressed` **inside the `<summary>`
  heading**, not anywhere in the body:
  PR #660 emitted `Comments suppressed due to low confidence (3)`,
  while PRs #1029 and #1031 emitted `Suppressed comments (4)`.
  A literal grep for either exact phrase can return a false zero.
  A body-wide match over-corrects the other way and can permanently reject a
  genuinely clean review, since ordinary overview prose can also contain the
  word --- review 4837572117's summary table read "suppressed Copilot
  findings" outside any collapsed block.
  A body read that stops at the overview is therefore not a body read, and a
  match against the whole body is not the right instrument either.
- **"No verdict" is its own state, distinct from "a verdict with no
  findings".**
  A review job can fail having posted *nothing* --- not a stub, not an empty
  comment.
  Zero findings and zero review are indistinguishable by any count, and they
  call for opposite responses: one is done, the other needs a self-review and
  a re-run.
  Read the job's step outcomes when a review is missing rather than inferring
  from the absence of comments.

- **Do:** read all review surfaces before calling a PR clean,
  every round,
  including collapsed suppressed-comments blocks.
- **Do:** distinguish "no findings" from "no verdict" explicitly, and treat
  the latter as unreviewed.
- **Don't:** report clean on a zero thread count, however many checks are
  green.
- **Don't:** treat an empty review body as an all-clear without checking the
  inline comments.
- **Don't:** treat a "generated no new comments" overview as an all-clear
  until every `<summary>` heading has been checked case-insensitively for
  `suppressed` --- not until the whole body has, which flags ordinary
  overview prose that merely mentions suppressed findings.
- **Don't:** read a reviewer's silence as a verdict --- a job that posted
  nothing leaves the same zero counts as a job that found nothing.

**A comment can be evidence-dense, correct throughout, and state no verdict at
all --- and its density is what gets read as the conclusion.**

**A later comment stating no verdict does not supersede an earlier one.**

- **Do:** identify the last statement that actually states a verdict, and treat
  that as the standing one.
- **Do:** scan the whole review history for it, not only items matching HEAD.
- **Don't:** read a verification section, however rigorous, as an approval ---
  it is evidence, and a verdict is a conclusion about evidence.
- **Don't:** treat a later comment's silence on the verdict as superseding an
  earlier "Needs more work".

See [`fully-clean.cases.md`](fully-clean.cases.md),
"A later comment stating no verdict does not supersede an earlier one".

**Another surface,
and the one that defeats the gate itself:
the review check can pass on a blocking verdict.**

- **Do:** grep the verdict body for its own conclusion, and treat a
  `require-review` pass as orthogonal to whether the PR is clean.
- **Don't:** let a green review-gate check stand in for reading what the
  review said.

**`check-pr-fully-clean.py` itself has the mirror false positive: it can report
NOT clean over a clean verdict.**

- **Do:** read the verdict's own conclusion when the script reports findings
  against a review whose prose merely discusses finding vocabulary.
- **Don't:** treat a `contains findings (matched pattern ...)` line as a real
  finding without reading the verdict body it matched.

**A verdict comment quotes verdict phrases, so a phrase search identifies
nothing --- and it misreads in both directions at once.**

- **Do:** call `check-pr-fully-clean.py` for a sweep's verdict column, exactly
  as [`ardi`](ardi.md) requires for one PR.
- **Do:** anchor on the last `### Verdict` heading when parsing by hand, after
  selecting candidates on the `**Claude finished` marker.
- **Don't:** take the first verdict phrase in a body as that body's verdict ---
  quoting other verdicts is part of what a review comment does.
- **Don't:** assume such a misread has a safe direction; one sweep produced a
  false-clean and a false-blocked.

**A review comment's header SHA can be stale, so take the reviewed commit from
the run's own `head_sha`.**

- **Do:** follow the job link in the comment and read that run's `head_sha`.
- **Don't:** treat the SHA in a comment's heading as the commit reviewed.

**That remedy assumes the run checked out the PR head, and a `workflow_dispatch`-triggered review run does not.**

- **Do:** check a `workflow_dispatch` review's `event` field before reaching for `head_sha` --- on that trigger type the field names the dispatch ref, not the reviewed commit.
- **Do:** cross-check a stale-suspected verdict's specific claims against the file directly, rather than only against run metadata.
- **Don't:** trust `head_sha` as "the commit reviewed" on a workflow-dispatch-triggered run --- that guarantee only holds for push/pull_request-triggered runs, which check out the PR head by construction.

**A third surface names a commit the run never read, and unlike the two above
it points the confident direction: the run object's own
`pull_requests[].head.sha`.**

- **Do:** settle which commit a review read from a discriminating claim in its
  own body, since that is the only surface separating the candidates.
- **Do:** read `pull_requests[].head.sha` as a fact about the PR's current
  head, useful for nothing else.
- **Don't:** read that field naming your latest commit as evidence the review
  covered it --- it names the current head unconditionally.
- **Don't:** read an empty `pull_requests` as evidence about the run; the array
  empties when the PR closes.

See [`fully-clean.cases.md`](fully-clean.cases.md), "`pull_requests[].head.sha`
named a commit pushed after the run started".

**`check-pr-fully-clean.py` uses the same unreliable body-text surface, and
whichever SHA that text happens to contain --- present, absent, or wrong ---
is incidental to which head the run actually reviewed.**

- **Do:** read a flagging run's `event`, `head_branch`, and `head_sha`
  before treating "no review at this HEAD" as a genuine gap.
- **Do:** treat the script's discharge as the likely reading, since the
  withholding direction dominates in practice, but not as a certified one.
- **Don't:** re-dispatch a review, or fall back to self-review, on this
  signal alone when the flagging run's own metadata already shows it
  evaluated the current head.
- **Don't:** read a body's SHA, present or absent, as evidence about which
  head a review covered --- it is evidence about what the prose happened to
  discuss.
- **Don't:** conclude that reviewers citing their head SHA more consistently
  would fix this; a body can already cite a SHA and still be citing the
  wrong one.

**A clean CI run and a clean review verdict are a snapshot, not a standing
guarantee of mergeability.** `main` can advance after your last check ---
including gaining its own independent addition that collides with yours
(see `sync-with-main.md`'s "two PRs append the same numbered subsection" case)
--- so re-verify the branch still merges cleanly against current `main`
before reporting a PR ready, not just trust the last green run.

**Re-check version parity in that same sweep, not only conflict-freedom.**

**Threads:** at fully-clean, every **inline** review thread is resolved, and the only conversation left open is the final all-clear exchange --- the reviewer's all-clear comment and your reply to it. (The all-clear is usually a top-level PR comment, not an inline thread.)

**One finding can own two threads, so sweep by thread id rather than by
finding.**

**Deadlock -> escalate to a human.** If you and the reviewer(s) can't reach consensus on an item (a rebuttal was exchanged and neither side is budging), don't loop forever and don't unilaterally override the reviewer --- request a **human reviewer**, `@`-mention them in a comment summarizing the impasse, and surface the open item.

**An automated reviewer's verdict on a disputed factual/technical claim is not stable across independent runs, even with identical evidence available each time.** Don't treat one round's "settled, no need to keep arguing" as durable: the very same review job, re-triggered later with no new code changes, can re-raise a claim it previously retracted --- and then retract it again on a subsequent run --- purely from re-deriving the question differently each time, not from anything changing in the PR. This means a rebuttal thread's outcome (however many rounds of citations and counter-citations) doesn't itself resolve a genuine deadlock the way a human's decision does; only escalating per the bullet above actually settles it. The one thing that DOES help going forward: fold the authoritative citation/evidence directly into the code or doc being reviewed (a comment, not just a PR conversation reply) --- a fresh reviewer run re-deriving the claim from scratch is more likely to find the citation sitting right next to what it's evaluating than to dig through prior thread history for it, though even that is not a guarantee against a bot that ignores context already in front of it.
