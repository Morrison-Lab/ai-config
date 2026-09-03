# Session notebook --- 2026-09-03 --- GIA (`mwc daytb`)

Invocation: `gia mwc daytb`.
Grants active: `mwc` (merge when confident) and `daytb` (decide judgment calls myself).
Remote Claude Code session, with **no `gh`/`glab` CLI**.
Forge work therefore goes through the GitHub MCP tools per `tool-mappings.md`.

Repos in scope for this session: `Morrison-Lab/ai-config` and `UCD-SERG/serocalculator`.

## Scope decision (daytb)

GIA clears **one** repo's queue and two are in reach, so the choice was mine to make.
Chose **`Morrison-Lab/ai-config`**:

- Its queue is 5 open PRs, all authored by `d-morrison`, all opened within the last day --- a live, in-scope queue.
- `serocalculator` has 28 open PRs, but most fail `gia`'s scope filter (authored by
  `kristinawlai`, `kaiemjoy`, the Copilot app `copilot-swe-agent`, or the Codex app
  `openai-code-agent` --- none of which is `github-actions`, and none assigned to the user).
  The in-scope remainder there is stale by months to years (#666, #555, #518, #369, #53).
- `CLAUDE.md`'s "Prioritize internal infrastructure work slightly over feature work" breaks the
  near-tie toward the infra repo.
- ai-config also carries the **standing `mwc` grant** for fully-clean PRs targeting it.

`serocalculator` is reported at the end rather than swept; revisit if the wave finishes early.

## Continuity with 2026-09-02

Yesterday's notebook (`memories/session-2026-09-02-gia-ai-config.md`) ran GIA over the same repo.
Its Phase 1 outcome, in four groups.
Merged: #3056, #3014, #3058, #3044.
Pushed and awaiting review: #3023, #3024, #3070.
Left to a peer session: #3061 and #3037.
Untouched: #3060.
Since then #3070, #3061 and #3037 have left the open list, so they landed.
Still open from that run: **#3023, #3024, #3060**.
New since: **#3084, #3089**.

The account session limit that blacked out `claude-code-review` yesterday reset at 21:50 PDT.
It is now past that, so review rounds should be obtainable again --- to be confirmed by a real
verdict rather than assumed.

## Running log

- 2026-09-02 23:30 PDT --- session start (clock read fresh).
  Local `ai-config` `main` already at `origin/main` (`63e92534`); checkout fresh, no pull needed.
  Clone is **shallow** (`git rev-parse --is-shallow-repository` -> `true`),
  so `scripts/check-stale-records.py`'s age bucket carries no information until `git fetch --unshallow`.
- Phase 1 survey dispatched (read-only subagents, `sonnet`): open-PR state, and issue-backlog triage.
- **Pairwise file-set collisions across the 5 open PRs** (derived, not recalled).
  Negative control first --- file-set sizes `{3089: 4, 3084: 1, 3060: 0, 3024: 2, 3023: 12}`,
  so the detector demonstrably sees files and a zero is a real zero.
  10 pairs examined, 2 collided:
  - **#3089 x #3023** --- `.github/workflows/validate.yml`
  - **#3084 x #3023** --- `shared/workflow/adversarial-self-review.md`
  Every other pair is disjoint.
  This is a *collision* derivation only.
  It cannot see a dependency (one PR asserting what another makes true), which needs a separate read.
- **#3060 still has an empty diff (0 files changed)**, exactly as yesterday's notebook recorded.
  A draft opened per `pr-on-claim` and never filled in.
  It needs a decision, not an ARDI round.

## Phase 1 --- what each open PR needed

Survey dispatched read-only and cross-checked rather than trusted.
**The survey reported one unresolved review thread on #3023.**
**The live query showed all six resolved.**
Worth recording as a subagent-report miss: the number was wrong in the direction that would have created work, not skipped it, but a report of PR state is exactly the kind of claim `metacognitive-monitoring` says to re-query rather than accept.

- **#3024** --- clean at head `14817d4b` (round 6 of 6), 19 checks green, `mergeable_state: clean`.
  Two items still standing, both dispositioned:
  - The `request_ident()` first-match gap --- **Defer** to #3071, thread replied to and resolved.
  - Round 5's non-blocking nit claiming a duplicated word (`That is\nis indistinguishable`) --- **Rebut**.
    The file at head reads `# ... it away. That` / `# is indistinguishable, ...`, i.e. one correctly-placed `is` across a line break.
    **The reviewer misread the wrap.**
    Acting on the nit would have *introduced* the duplication it described, which is the sharpest form of why a nit gets verified against the bytes rather than trusted.
- 2026-09-02 23:41 PDT --- **MERGED #3024** (squash, `462de02b`), under the standing ai-config `mwc` grant plus the peer-PR path (announced intent, held five minutes, `ListAgents` reached no peer).
- **#3023** --- announced merge intent at 23:36 PT on head `64c4e97`.
  **Re-checked before acting, and the head had moved to `6aa021b5`.**
  A peer merged `origin/main` in (`ced93f69`) and dropped the report-trailer case record as superseded by #3084 (`6aa021b5`), at 06:38Z --- minutes into my own five-minute hold.
  A push resets the clean clock, so the round-5 verdict no longer covers the head.
  Withdrew the intent on the PR and left the PR to its peer.
  **This is the third consecutive session in which the pre-merge re-check caught a peer collision** (#3037 and #3024 yesterday, #3023 today).
  The rule is not ceremony on this repo; it fires roughly every time.
- **#3084** --- Claude verdict clean on head `6f10014`, but a **Copilot review landed an hour later** with a real finding the Claude round never saw.
  That ordering is the case `CLAUDE.md`'s "Re-check for latest review findings" section exists for: the newest *Claude* comment read clean while a newer *Copilot* review sat open.
  Finding confirmed by reading the passage: line 456 said "A conforming report puts the payload last, needs no sentinel, and is what #3050 has to settle:" and then introduced a **sentinel-bearing** block with that colon.
  Fixed on branch `docs/subagent-report-trailer` (**not yet pushed** at the time of writing --- see the note below): split the sentence, name what the block is before showing it, scope the unconditional `Do:` bullet to the reordered tail, and add the paired `Don't`.
- **#3060** --- the empty draft turned out to be a fully-specified UMS pass (#3059) that yesterday's session opened and never wrote.
  Written on branch `claude/ums-load-adversarial-peer` (**not yet pushed** at the time of writing): three entries across `algorithmatize-checks.md`, `adversarial-self-review.md` (two subsections) and `address-every-comment.md`.
  **One part of #3059 was deliberately not written**: its item 2 also described rounds each introducing the next round's defect, which `learn-from-review-findings.md` already covers at length under "A later round can find a defect in the FIX".
  Only the missing half --- an instrument for deciding when to *stop* --- was added.

## Collision matrix, re-derived on current heads

The first derivation is already stale, which is the point of re-deriving it.
After #3023's drop commit its net diff no longer touches `adversarial-self-review.md` at all, so the #3023 x #3084 collision **dissolved without anyone resolving it**.
Meanwhile #3060 gained that same file, creating a pair the first matrix could not have shown.

Sizes `{3089: 4, 3084: 1, 3060: 3, 3023: 11}`; 6 pairs examined, 1 collided (#3023 x #3089, on `.github/workflows/validate.yml`).

**A file-set intersection is not a conflict**, so the pairs were simulated --- with a **positive control built for the purpose**, since a zero matrix and a detector that never ran look identical:

```
POSITIVE CONTROL ctl-A x ctl-B exit=1   (two throwaway branches editing README.md's only line)
3060 x 3084                    exit=0
3023 x 3089                    exit=0
```

So the detector demonstrably fires, and neither real pair conflicts.
No merge-order constraint from conflicts.
Checked separately for *dependency* (one PR asserting what another makes true), which no intersection can see: `main` does not carry the report-trailer section and #3084 is the only open PR adding it, so #3023 dropping it loses nothing whichever order they land in.

## A peer session is driving this repo concurrently --- the division that settled

Not inferred from `ListAgents`, which reaches only this machine and reported no peers all session.
Inferred from the PRs themselves, which is the only channel that works here:

- **#3023** gained `ced93f69` (merge of `origin/main`) and `6aa021b5` (drop the report-trailer record) at 06:38Z, *during* my own five-minute merge hold.
- **#3089** was a draft with `validate` in progress when surveyed;
  by 06:43Z it was **un-drafted** and its head had moved from `e1f5fd03` to `8f1ca761`.

Both are live peer work, minutes old, so both stay theirs --- no pushes, no merges, no review-driving from me.
The one thing I owed #3023 was withdrawing the merge intent I had already announced on it, which is done.

**Mine to drive:** #3084 (report-trailer block), #3060 (the #3059 UMS pass), #3093 (this notebook).
**Theirs:** #3023, #3089.

The lesson is not new but it is now three-for-three: on this repo `ListAgents` is not the instrument for peer detection.
The PR's own `updated_at` and head SHA are.
A peer that shares the login is invisible to every agent-listing tool and visible in every forge query.

## Reviews

- #3084 round 2 (adversarial) returned **5 findings, all real**, all Addressed on branch `docs/subagent-report-trailer` (**not yet pushed** at the time of writing):
  1. The fenced block claimed to show verdict and fingerprint *after the payload* while containing **no payload**, so the ordering was asserted over the artifact rather than visible in it.
     Fixed by making the payload's closing marker the block's first line.
  2. The corpus sweep's `0` was being read as confirming its own conclusion while a **known-real instance sat outside its reach** --- a failed positive control, not a corroboration.
     Now stated as such, with what the `334` establishes separated from what the `0` does not.
  3. The "Two caveats" paragraph gave #3050 a scope the corrected sentence fourteen lines above had already ruled out, and blamed the sentinel for a tension the *reordering* causes on its own.
  4. A forward reference (`the same zero`) pointing across a paragraph break and a code fence at a value first shown below it.
  5. `The measured occurrence` --- "measured" applied to the one datum the measurement did **not** find, and singular against "observed twice".
- Finding 2 is the one worth carrying past this PR.
  It is the same shape as this session's own merge-simulation control, arriving in prose: a zero from a detector with a known blind spot reads exactly like a zero from a working one, and the passage asserting it had itself been written to argue "measured rather than assumed".

## CI caught a check I ran on part of my own diff

`new-line-breaks` failed on #3093's `50cf2863` with six violations, every one of them in this notebook file.

The checker had been run three times that hour --- on #3084's edit, on #3060's three entries, and again after each fix --- and each run came back clean.
None of them covered the notebook, because I ran the checker **from the branch whose corpus files I had just edited**, and the notebook lives on a different branch.

So the gap is not that a check was skipped.
It is that a check was run against a *subset* of what the session was pushing, and a clean result over that subset reads exactly like a clean result over all of it.
That is the same shape as this session's two other control problems --- the merge-simulation zero, and the trailer sweep's zero --- arriving a third time in a different disguise: **an instrument that examined less than you think it did reports the same thing as one that found nothing.**

The contributing cause is worth naming because it is not laziness.
A lab notebook reads as *bookkeeping*, not as corpus prose, so it does not feel like the kind of file a style gate applies to.
The gate does not draw that distinction.
`memories/*.md` is inside the `*.md` glob, and the file is exactly the kind of hurried prose that packs two sentences onto a line.

Fixed in `b439713c` --- reproduced locally with `NLB_BASE_REF=origin/main`, six lines broken, re-run to green, then pushed.

- **Do:** run the repo's checkers once per branch you are about to push, not once per editing session.
- **Do:** treat a notebook, a `.cases.md`, or any prose written in a hurry as in scope for the same gates as the corpus.
- **Don't:** carry a clean checker result across a branch switch --- it was a measurement of the other branch.

## A private SHA is unresolvable to anyone but this container

Caught by #3093's own review round, and it is the sharpest finding of the session because it is about the notebook's *purpose* rather than its content.

The review checked `92304aeb`, `264f76f7` and `e3d3646e` with `git cat-file -e`, a `git log --all` grep, and a fresh fetch of `refs/pull/3084/head`, and found none of them.
It concluded the work had never happened.
It had: all three commits exist, on branches this session is deliberately holding unpushed while `no-push-without-self-review` waits for each branch's adversarial verdict.

So the finding's **inference** is wrong and its **finding** is exactly right, and only the second one matters.
A notebook exists to be the record a later reader trusts after an interruption that gave no clean stop.
That reader has the remote and does not have this container.
A SHA that resolves only here is therefore worse than no SHA at all: it reads as checkable, invites the check, and fails it --- and the natural reading of that failure, as the review demonstrates, is that the work was fabricated.

The push gate makes this the *normal* state rather than an unlucky one, which is what makes it worth a rule.
Any session that reviews before pushing will, for the whole window between commit and push, hold work whose SHAs are private.
A notebook written during that window cites them by default.

- **Do:** name the branch and the change rather than the SHA while the commit is private, since the branch name survives a rebase and resolves the moment the branch is pushed.
- **Do:** say the work is not yet pushed and what is gating the push, so a reader who checks and finds nothing has the explanation in hand.
- **Don't:** write a bare SHA into a record meant for a reader who only has the remote --- it is a checkable-looking claim that fails the check.
- **Don't:** read a reviewer's "this commit does not exist" as a fabrication finding without checking whether it is merely unpushed;
  the observation is sound either way, and the diagnosis is not.

**A second round on #3093 caught that the fix above did not apply its own remedy.**
The rule it states is to prefer the branch name over the SHA, and the first fix marked the SHAs `local only, unpushed` and kept them --- which discharges the honesty half and not the usability half.
A marked SHA still cannot be looked up;
a branch name can be fetched the moment the branch exists.
So the three sites now name `docs/subagent-report-trailer` and `claude/ums-load-adversarial-peer` instead.

Worth recording as its own small pattern: a rule written and applied in the same commit is exactly where the application gets checked least, because writing the rule *feels* like the work.
The reviewer that catches it is reading the two as one artifact, which the author cannot.

