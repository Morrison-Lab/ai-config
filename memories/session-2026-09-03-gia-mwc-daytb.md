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


## Phase 1 outcome, and the one pattern the whole night was about

Merged: [#3024](https://github.com/Morrison-Lab/ai-config/pull/3024), [#3093](https://github.com/Morrison-Lab/ai-config/pull/3093).
Driven to clean and pushed: [#3084](https://github.com/Morrison-Lab/ai-config/pull/3084) (`23933b1b`), [#3060](https://github.com/Morrison-Lab/ai-config/pull/3060) (`c851d68f`).
Left to the concurrent peer: [#3023](https://github.com/Morrison-Lab/ai-config/pull/3023), [#3089](https://github.com/Morrison-Lab/ai-config/pull/3089).
Filed: [#3098](https://github.com/Morrison-Lab/ai-config/issues/3098).
Annotated out-of-diff: [#3050](https://github.com/Morrison-Lab/ai-config/issues/3050) (carries a claim [#3084](https://github.com/Morrison-Lab/ai-config/pull/3084) retracted), [#3083](https://github.com/Morrison-Lab/ai-config/issues/3083) (a second symptom of the stop hook), [#3089](https://github.com/Morrison-Lab/ai-config/pull/3089) (a fifth occurrence of the false-clean its bump fixes).

Findings per round, which is the number worth keeping:

| PR | rounds | findings |
|---|---|---|
| [#3084](https://github.com/Morrison-Lab/ai-config/pull/3084) | 6 | 1, 5, 7, 3, 2, **0** |
| [#3060](https://github.com/Morrison-Lab/ai-config/pull/3060) | 5 | 11, 7, 2, 3, **0** |
| [#3093](https://github.com/Morrison-Lab/ai-config/pull/3093) | 3 | 3, 2, **0** |

**Every one of those was caught before the remote saw it**, because `no-push-without-self-review` held each branch until its head had a clean verdict.
The stop hook spent that whole hour telling me to push.

### The pattern, stated once

Nearly every substantive finding this session was one shape: **an instrument reported an absence, and the absence was read as a fact about the world rather than about the instrument's reach.**
Seven instances, in the order they arrived:

1. A merge-conflict matrix of zero, which needed a purpose-built positive control to distinguish from a detector that never ran.
2. A corpus sweep returning zero concatenated trailers, read as confirming its conclusion while a known-real instance sat outside its population.
3. My correction to (2), which called it a *failed* positive control --- also wrong, because the sighting was an in-context render and the sweep read stored JSONL.
   Different artifacts.
4. A line-break checker reporting clean over eight real violations, because the tree was dirty and it takes line numbers from the commit and content from the tree.
5. A prescribed verification query that returned null under every explanation it was offered to distinguish.
6. My fix to (5), which re-aimed *the same matcher* --- and the first explanation is precisely that this matcher is blind.
7. A CI negative control reporting that it could not discriminate, because load compressed the ratio it measures.

The recurring sub-shape is (3) and (6): **the repair reproduces the defect.**
When the fault is "this instrument cannot see what you are asking it", the natural repair re-aims the same instrument, which changes the target and not the blindness.
Knowing the general principle did not prevent any of these.
In (4) I had read the rule, quoted it earlier the same hour, and broke it twice within twenty minutes.

What did work, every time, was an outside reader with the artifact in hand.

### Two rules the reviews produced, already merged in [#3093](https://github.com/Morrison-Lab/ai-config/pull/3093)

- A SHA that resolves only in the authoring container is worse than no SHA in a record meant for a reader who has only the remote: it reads as checkable, invites the check, and fails it.
  Name the branch and say what gates the push.
- A rule written and applied in the same commit is where the application gets checked least, because writing the rule feels like the work.

## 01:28 PDT --- state re-derived after the compaction

Re-queried rather than recalled, per the state-claim rule.

| PR | head | state |
|---|---|---|
| [#3084](https://github.com/Morrison-Lab/ai-config/pull/3084) | `bf558244` | pushed, 14 checks success and 1 skipped (a superseded `new-line-breaks` run), `review / require-clean-verdict` success, both threads resolved |
| [#3060](https://github.com/Morrison-Lab/ai-config/pull/3060) | remote `c851d68f`, local `0daed144` | round 6 committed, unpushed, awaiting a push-gate verdict |
| [#3023](https://github.com/Morrison-Lab/ai-config/pull/3023) | `6aa021b5` | open, the peer's |
| [#3089](https://github.com/Morrison-Lab/ai-config/pull/3089) | `8f1ca761` | **merged 06:51Z**, not by me --- `merged_by` is the shared login, so the API cannot say by whom; the branch itself is agent-authored |
| [#3100](https://github.com/Morrison-Lab/ai-config/pull/3100) | `3acc79bd` | new since the last sweep, agent-authored, not mine |
| [#3101](https://github.com/Morrison-Lab/ai-config/pull/3101) | `d8c88486` | new since the last sweep, agent-authored, not mine |

Two things the re-derivation changed.

**[#3089](https://github.com/Morrison-Lab/ai-config/pull/3089) merged while I was not watching, which the earlier row called "left to the peer" and never revisited.**
It carries the fix for the dirty-tree false-clean that cost this session two of its own errors:
the bumped checker widens `auto` scope to the working tree when tracked matching files are dirty,
and prints `Examined N added line(s) across M file(s) (scope: ...)` ahead of its verdict.
So the instrument that reported an absence about lines it never examined now reports its own reach.
That is the session's recurring pattern getting an instrument rather than a rule, and someone else built it.

**The peer's PR count grew by two while this session was compacting.**
`ListAgents` reported no peers all session and still does.
The instrument that actually settles it is the commit trailer, not `updated_at`, which cannot separate a peer from any other actor pushing under the same login:
the tip of [#3023](https://github.com/Morrison-Lab/ai-config/pull/3023) carries a `Claude-Session:` URL differing from this session's, which is decisive;
the tips of [#3089](https://github.com/Morrison-Lab/ai-config/pull/3089), [#3100](https://github.com/Morrison-Lab/ai-config/pull/3100) and [#3101](https://github.com/Morrison-Lab/ai-config/pull/3101) carry no trailer, the human's authorship, and a `Co-Authored-By: Claude ...` line, which is consistent with a local session rather than with a person typing that line, and does not settle it.
Banked as a rule in `memories/git-worktrees.md` on [#3060](https://github.com/Morrison-Lab/ai-config/pull/3060)'s branch.

## The merge gate, re-probed rather than recalled

`shared/workflow/adversarial-self-review.md` on `origin/main` --- not on either of my branches, which edit that file ---
requires for a merge "a reviewer differing from the authoring session in **both** model and harness",
and says plainly that where none is reachable "the merge waits --- 'blocked on reviewer availability' is the honest status".

Re-probed at 01:28 PDT: `codex`, `opencode`, `agy`, `cursor`, `cursor-agent`, `gemini`, `aider`, `crush` all absent from `PATH`,
and no provider API key is set in the environment.
The CI `claude-review` job does not close the gap, and my first statement of why was asserted rather than derived.
I wrote that it "differs in harness and not in model".
Nothing reachable establishes that: `.github/workflows/claude-review.yml` passes no `model:` input, and the reusable workflow it calls documents that input as empty by default, falling through to `claude-code-action`'s own default, which no memory file here pins.
The derivable reason does not need the model at all.
The gate requires "the **author-dispatched** cross-model, cross-harness reviewer's 100% all-clear adversarial verdict at the shipping head", and a workflow triggered by the push is not author-dispatched whatever model it runs.

So [#3084](https://github.com/Morrison-Lab/ai-config/pull/3084) is finished except for a gate no reachable reviewer can satisfy, and it waits.
The standing ai-config `mwc` grant does not help, because the gate is a condition on the *verdict*, not on authorization.

## 02:06 PDT --- [#3060](https://github.com/Morrison-Lab/ai-config/pull/3060) pushed at `ae58121f`, and what four rounds cost

The table above is a snapshot of 01:28 and stays one;
PR [#3060](https://github.com/Morrison-Lab/ai-config/pull/3060) is now pushed at `ae58121f`, six commits past the local head that table records, and thirteen past the remote one.
`git rev-list --count` is where both figures come from, rather than a count typed from memory.

Four review rounds landed in that stretch.
Two generalisations about them were written here and both were false, which is worth more than either would have been.
The first --- that each round's findings were about the previous round's *fix* --- was refuted by the table printed directly beneath it.
The second --- that the branch never stopped growing, so every round found defects in material added since the last one --- was not on the page and took one query per row to refute.

There is no single shape, because the four rounds split into two:

- **Rounds 6 and 7 found content that was already in the tree an earlier round had reviewed.**
  Derived: `git show c851d68f:shared/workflow/algorithmatize-checks.md | grep -F 'command not found'` returns the line round 7 flagged, and the same query over `adversarial-self-review.md` for `What ended the series` returns the line round 6 flagged.
  Note the weaker claim that supports: `c851d68f` is not round 7's immediate predecessor head, since eight commits separate it from `b94767dd`.
  Round 6's reviewing head is not derivable at all --- it was a local dispatch that left no artifact --- so that half rests on recollection, like round 9's.
  What is established is that the passages predate an earlier review of their own files, not that the round immediately before each one read those lines.
  That earlier CI round was itself `NOT_CLEAN`, so "passed clean over them" is wrong twice over;
  it returned a finding elsewhere and said nothing about these.
- **Round 8 found material that did not exist at the previous round's head.**
  Derived: every entry its fixes touched postdates round 7's head `b94767dd`, though the files themselves all existed at it --- `git show b94767dd:memories/git-worktrees.md | grep -c Claude-Session` returns 0 against 7 afterwards, and the `address-every-comment.md`, `markdownlint.md` and `algorithmatize-checks.md` entries all arrive later.
  **Round 9's half rests on recollection, not derivation**, and cannot be checked: rounds 8 and 9 were two passes whose fixes squashed into one commit, so no intermediate head exists to query.

So the transferable statement is not about pace or about fix quality.
It is that **a verdict is not evidence about the material it did not flag** --- twice here, a passage sat in a file a round had in front of it and was flagged only later.
Two instances cannot support "never", and the weaker form is the useful one anyway: it says convergence is not a stopping signal, which is the opposite of what an empty round feels like.

A query goes some of the way and it is worth stating what it does not settle: `git show <previous-round-head>:<file> | grep -F '<flagged text>'`.
Present means the text predates that head.
**Absent does not mean it was added since**, which is what I first wrote here and this branch's own history refutes --- `What ended the series` is absent at `b94767dd` because the commit *named* for rewording it removed the phrase, not because it arrived later.
That cause is structurally expected in a converging series, since each round's fix rewrites the text the next round would have searched for --- though one instance is not a frequency, and one instance is all this is.
Use `-F` as cheap insurance, and note that my first reason for it was wrong.
I cited `#3059`, `){0,12}` and `<cmd>` as strings a regex would misread.
Measured: `#` and `<` are metacharacters in neither BRE nor ERE, so two of the three behave identically with and without `-F`, and the third differs only under `-E` while the recipe above is plain `grep`.
The real hazard is a flagged string carrying `.`, `*` or `[`, which this corpus's prose produces constantly.

| round | reviewer | findings | what they were about |
|---|---|---|---|
| 6 | adversarial subagent | 0, plus an out-of-scope note | a line the note said was pre-existing, which the diff carried as an addition |
| 7 | CI `@claude` | 1 | a claim billed as measured that does not reproduce where a `time` binary exists |
| 8 | adversarial subagent | 6 here, 7 counting the notebook | a false gap claim, a spliced list, and four claims billed as measured that were inferred |
| 9 | adversarial subagent | 1 | a hedge applied to one instance of a claim and not to its two siblings |

Three lessons, each of which cost a round.

**An out-of-scope note is a scope claim, and one `git diff` query settles it.**
Round 6's note was correct about the defect and wrong about whose it was, because the reviewer located the line by reading the file at `HEAD` and read untouched surrounding text as provenance.
Banked in `address-every-comment.md`, and the entry had to be rewritten in round 8 because that file already carried the rule --- my dupe-check grepped `out of scope` spaced where the rule writes `out-of-scope` hyphenated.
A phrase grep decided a coverage question, which is what `grep-is-not-coverage` says never to let it do.

**Two reviewers can measure the same command and disagree, and the mechanism is the only durable record.**
CI got exit 0 with `TIMEFORMAT` ignored;
this container gets `time: command not found`.
Both are right: an assignment prefix demotes `time` from reserved word to a command word, so a `PATH` lookup follows, and the symptom depends on whether a `time` binary is installed.
The one-command check --- put an executable named `time` on `PATH` and compare the bare and prefix forms --- is now in the entry, so the next reader settles it locally rather than trusting either report.

**A hedge is an incomplete sweep by default.**
Round 9 found the same claim in three places, one hedged in prose and two left flatly asserted in a table.
The prose fix reads as complete from the inside precisely because it is the instance you were thinking about.

`markdownlint-cli2` runs here via `npx` at CI's pinned version in seconds, which would have caught the MD018 failure before the push and now catches the recurrences I keep producing.
What is checkable: one CI-recorded failure, job `100580631907`, which is what prompted the rule --- and note the rule and that fix landed in the same commit, `eb0cf15e`, so the occurrence predates its own rule rather than following it.
What is self-reported and leaves no artifact: two further occurrences afterwards, both caught by the local run before they could reach a commit.
A reader can verify the first and has only my word for the other two, which is worth saying in a sentence that would otherwise read as evidence.
Recorded in `memories/markdownlint.md` alongside the rule itself.

## 12:20 PDT --- Phase 2 wave launched under the go-all-out-until-1pm directive

User: quota at 74% of weekly, resetting 13:00 PDT.
Directive, verbatim: "until 1pm pacific, go all out with subagent workflows;
grab a bunch of new issues and drive PRs".
Model switched to Fable 5.1.
Every `agent()` call passes `model: 'opus'`.
Not Fable, which CLAUDE.md forbids for a subagent without explicit per-launch permission.
Not the cheap tier either, which `when-to-orchestrate` prescribes for mechanical work, because implementing an issue and refuting an implementation are judgment-heavy.
The quota cost of at least twenty-one Opus dispatches was accepted on the reset at 13:00.
One workflow run over seven issues, each with one primary target file, all seven distinct.
That set was derived from the issue bodies rather than from worktree file sets, which did not exist yet, so re-derive it with `scripts/pr-overlap.py` once the PRs are open:

- [#3095](https://github.com/Morrison-Lab/ai-config/issues/3095) `scripts/sync-nlb-checker.py`
- [#3068](https://github.com/Morrison-Lab/ai-config/issues/3068) `hooks/flag-cd-into-main-checkout.py`
- [#3086](https://github.com/Morrison-Lab/ai-config/issues/3086) `hooks/no-unreviewed-pr.py`
- [#3062](https://github.com/Morrison-Lab/ai-config/issues/3062) `plugins/ai-config/enforce-mwc-review-gate.py`
- [#3117](https://github.com/Morrison-Lab/ai-config/issues/3117) `hooks/remind-brief-premises.py`
- [#3102](https://github.com/Morrison-Lab/ai-config/issues/3102) `scripts/check-memory-file-size.py`
- [#3113](https://github.com/Morrison-Lab/ai-config/issues/3113) `scripts/check-pr-fully-clean.py`

Each issue: implement in a worktree on `fix/<N>-<slug>` off `origin/main`, then two Opus refuters, a fix round, and a recheck.
Claims posted on all seven issues at 12:20 PDT.
The two unpushed branches, `fix/ums-step3-corpus-scope` ([#3123](https://github.com/Morrison-Lab/ai-config/issues/3123)) and `fix/2465-rollup-cause` (Refs [#2465](https://github.com/Morrison-Lab/ai-config/issues/2465)), wait on an adversarial verdict.
Push both branches once that verdict lands.

## 12:38 PDT --- a correction to an earlier entry, and a corrected belief

**[#3084](https://github.com/Morrison-Lab/ai-config/pull/3084) merged, and no entry since recorded it.**
The merge-gate section's last word on [#3084](https://github.com/Morrison-Lab/ai-config/pull/3084) was that it waits on a gate no reachable reviewer can satisfy.
It merged at 2026-09-03T16:25:36Z under the shared login, and got the same never-revisited treatment the 01:28 entry records for [#3089](https://github.com/Morrison-Lab/ai-config/pull/3089).
Whether the cross-model gate was satisfied for that merge is not derived here.
The three prose defects it merged ahead of are tracked as [#3109](https://github.com/Morrison-Lab/ai-config/issues/3109), closed by [#3115](https://github.com/Morrison-Lab/ai-config/pull/3115).

**A corrected belief, recorded at the correction.**
Belief: a squash-merging repo's three-dot diff excludes a merge commit's content, so a re-add made while resolving a merge is invisible to review.
Fact: `git diff main...feature` is a merge-base-to-tip tree diff and lists the re-add as an added line.
What omits the merge patch is `git log -p`, unless given `-m` or `--diff-merges=on`.
The query that settles it, run 2026-09-03 on git 2.43.0 in a scratch repo whose merge resolution re-added a paragraph:
`git diff main...feature | grep '^+SHARED'` printed the line,
`git log -p main..feature | grep -c '^+SHARED'` printed 0,
and the same `git log` with `-m` printed 2.
The false version had been written into `fix/ums-step3-corpus-scope`.
The round-one adversarial verdict on the two held branches caught it, alongside five other findings: a headline universal resting on that mechanism sentence, an n=2 "most", a bare `#605` resolving to the wrong repository, a bullet list coalescing with its host section's list, and a case record asserting an underived cause inside the subsection that forbids exactly that.
All six are fixed on the two branches, and a round-two verdict is running.
Wants promotion to `memories/git.md` when this notebook is folded.

## 13:48 PDT --- part 2 merged; two PRs driven; the merge subsection deleted

[#3129](https://github.com/Morrison-Lab/ai-config/pull/3129) merged as the squash on `main` titled "docs(memories): session notebook for 2026-09-03, part 2 (#3129)", fully clean at its final head: CI green, claude-review CLEAN, Copilot approval recommended, Jules approve, adversarial verdict.
Five adversarial rounds and one Copilot round went into it after the 12:20 entry.
Every round's findings were claims one step wider than their evidence,
and the round that cleared was the one that deleted the clause rather than rewording it.
This file continues here on `docs/session-notebook-2026-09-03-part3`, so the merged part stays reviewed once.

[#3135](https://github.com/Morrison-Lab/ai-config/pull/3135) (`fix/2465-rollup-cause`, Refs [#2465](https://github.com/Morrison-Lab/ai-config/issues/2465)) is open: claude-review CLEAN and Jules approve on every head so far, and Copilot has asked for one change per pass across three passes (a self-contradicting clause, clause-boundary line breaks, then the bold lead-in's line break), each addressed by deletion or reflow with the token sequence unchanged.
Copilot's Lite reviews find one item per round, so on a still-growing file the review request waits for the final head.

`fix/ums-step3-corpus-scope` ([#3123](https://github.com/Morrison-Lab/ai-config/issues/3123)) reached its fourth adversarial round with eight findings, five of them inside the merge-time subsection that had produced findings in every round since the three-dot claim.
Decision taken under the three-rounds-without-consensus signal ([#3110](https://github.com/Morrison-Lab/ai-config/issues/3110)): delete that subsection outright rather than patch it a fifth time.
It sits outside #3123's stated fix, the corpus's own review read (`git diff origin/main...HEAD`) shows a merge-commit re-add, and its one durable learning is the corrected belief recorded in the 12:38 entry, now being promoted to `memories/git.md` on `ums/2026-09-03-merge-visibility`.

Four workflows run on: 40 issues claimed, 30 implementations committed at the 13:13 reading, refuter stages in progress, nothing from them pushed yet.

## 13:52 PDT --- #3135 merged

[#3135](https://github.com/Morrison-Lab/ai-config/pull/3135) merged as the squash on `main` titled "docs(fully-clean): naming a cause an aggregate rollup never confirmed (#3135)", fully clean at its final head: CI green, claude-review CLEAN, Copilot approval recommended, Jules approve, adversarial verdict.
Squash body written by hand, because an intermediate commit message on the branch asserted the underived cause the file no longer states.

What the lifecycle taught: Copilot's Lite pass on prose returns one item per round, and the three rounds here were a self-contradicting clause, clause-boundary line breaks, and the bold lead-in's line break.
The CI gate enforces sentence breaks and mid-line semicolons only, so a clause-boundary reflow pass before the first Copilot request would have saved two rounds.
Wants a pre-request checklist line in `shared/writing/semantic-line-breaks.md` when this notebook is folded.

## 14:13 PDT --- session limit hit at 13:56 PDT; resumed at 14:12 PDT

The account's session limit (HTTP 429, reset 14:10 PDT) ended every in-flight subagent at once:
the git-memory UMS agent, branch P's round-5 verdict,
and the refuter, fix, and recheck stages of all four waves.
All 40 implementations had already committed, and every first-round refuter that finished had refuted (2 to 7 findings each), so no wave branch reached verified state before the cut.
The user asked to continue from where I left off.

Resumed: waves 1 and 2 from their run ids (completed agents replay from cache, failed ones re-run), the UMS agent from its transcript, and a fresh round-5 verdict on branch P.
Waves 3 and 4 are held until 1 and 2 finish, two workflows at a time rather than four,
since four at once is what spent the limit in an hour.
The Workflow tool refused the persisted script paths for waves 2 to 4 as unreadable;
a copy under the scratchpad resumed with the same run id.
Open PRs on the repo are all peer sessions' (#3137, #3101, #3060);
none of this session's remain open.
Check-in re-armed for 14:58 PDT.

User directive at 14:13 PDT: keep to 5 subagents max.
Two resumed workflows run 2 agents each on this 4-CPU container, so one of the two single agents (the UMS writer) is stopped until a wave finishes, and waves 3 and 4 wait their turn.

The git-memory UMS agent finished before it could be stopped:
`ums/2026-09-03-merge-visibility` carries the merge-visibility entry in `memories/git-diffing.md` (which owns diff-range selection, so not `git.md`) and the `refs/pull/N/head` classifier in `memories/git.md`.
Its reproduction gives `git log -p -m` a count of 3 where the 12:38 entry in part 2 said 2, a repo-specific figure, so that entry's "wants promotion" note is discharged and its count is not a general one.
It waits for a verdict and a push under the five-subagent cap.

User directive at 14:19 PDT: do not grab any more new issues in this session.
The 40 issues already claimed across waves 1 to 4 are the current wave and run to completion;
no new claim is posted from here on, and the check-in prompt no longer resumes anything beyond those four runs.

## 15:17 PDT --- branch P through eight review rounds

Rounds 5 to 8 on `fix/ums-step3-corpus-scope` after the merge with `main`: 5, 8, 9, then 2 findings.
Round 6 was answered by cutting the subsection to its heading, one orienting sentence, the case record, and the Do/Don't pair, and step 3 to the query and a two-line reason.
Round 7 showed that round 6's own suggested fix, pinning the query to `origin/main`, would blind the dupe check to unmerged work;
the query now searches the resolved checkout's working tree behind a fail-closed guard, in a fenced block.
Round 8 left two convention items, both applied by hand with their ancestry re-derived;
round 9 is running.
The lesson for the fold: a reviewer's suggested fix is a claim like any other, and the one at round 6 was refuted one round later.

## 15:29 PDT --- #3154 opened for branch P; Jules blocked on the PR body

[#3154](https://github.com/Morrison-Lab/ai-config/pull/3154) opened at `3084b58d` after round 9 returned Ready for merge;
it closes #3123.
Jules blocked it on the PR description: the merging note ("write the squash body by hand") and the phrase naming the last adversarial verdict read to it as instructions to the reviewer.
Accepted: a PR body states facts about the branch, never an imperative or a verdict for a reviewer to defer to;
the body was rewritten with no file change,
and Jules was re-requested.
Its second item, that `git grep` with a hardcoded path list fails when a directory is removed, was rebutted with a measurement on git 2.43.0: a missing pathspec is a silent miss (exit 1), not an error.
Lesson for the fold: the same note on #3135 passed Jules earlier today, so the trigger is the wording, not the practice;
keep squash-body guidance in the merge step, not in the PR body.

## 16:10 PDT --- resumed after a compaction; #3160 filed; UMS branch through round 2

Filed [#3160](https://github.com/Morrison-Lab/ai-config/issues/3160): `scripts/check-pr-fully-clean.py`'s `classify_verdict()` returns no verdict for Jules's `VERDICT: approve` (its pattern needs `Approved`) and its marker table knows only `verdict: block`,
so a superseded block stands as that reviewer's latest verdict;
the reprex is in the issue.
The claude-review run on #3154 at `94244eb5` had found the same gap and left it unfiled because that session was review-only.

Round 2 on `ums/2026-09-03-merge-visibility` returned four findings, each re-measured before applying:
`git ls-remote` exits 128 with empty output for an unreachable host and for a repository the credentials cannot read, so the classifier now stops on a non-zero exit;
the quoted `batch-merge-and-resolve` command carries `-c`, restored;
the combined-diff anchor `^[ +-]*\+` matched whichever column is last, so on the rebuilt scratch merge it counted the copy `main` already had, and it is a quantifier under GNU BRE, where `grep -c '^[ +-]*\+SHARED'` gives 2 while the review reported 1 (an ERE reading), so the entry now anchors on `^[+][+]` and states both counts;
the `refs/pull/N/head` premise now points at the `git-branches.md` section that owns it.
Committed as `3011644c` with every gate green;
round 3 is queued behind the five-subagent cap.
Lesson for the fold: a reviewer's count is a measurement under the reviewer's own tool, so re-run it with the tool the entry names before writing the number down.

The pre-push verdict for #3154's local head `cc5e0f7d` went into the slot the round-2 reviewer freed;
waves 1 and 2 were still running (four live agents) at the reading above.

## 16:20 PDT --- #3154 round 10: two fixes, one deferral

The verdict for `cc5e0f7d` returned three findings.
Two are applied at `cee70344`:
the Anti-patterns entry in `skills/ums/SKILL.md` still summarized step 3 as grepping the whole target file,
and the Don't bullet in `grep-is-not-coverage.md` quoted step 3's retired wording without the `3935bfff` pin the earlier quotation carries.
The third, that `skills/memorize/SKILL.md` step 3 keeps the file-scoped dupe check, is deferred to [#3161](https://github.com/Morrison-Lab/ai-config/issues/3161) and named in the PR body under a Deferred heading,
per `issue-first`'s deferral rule and the shrink-the-diff lesson from rounds 5 to 9.
CI on the remote head `94244eb5` is green across all 21 check runs;
`git merge-tree --write-tree origin/main HEAD` exits 0 at `2156b439`, five commits ahead of the merge base, with no main-side change to either file.
The verdict for `cee70344` is running in the one free slot.

## 16:34 PDT --- 16:31 check-in: #3146 is a peer session's PR with half a quorum

The sweep found two open PRs in ai-config: #3154 (this session) and [#3146](https://github.com/Morrison-Lab/ai-config/pull/3146), opened at 14:35 PDT from a branch this session never pushed and closing an issue (#3128) this session never claimed.
Its head `2b735663` has green CI and a clean claude-review verdict since 14:39 PDT and no Copilot or Jules review, so it is not fully clean by the quorum bar and the standing grant does not reach it.
`ListAgents` listed no peer session, so the `mwc` peer-PR path's message-the-owner step had nowhere to go;
Copilot was requested and `@jules review` posted, with a status comment naming this session and the twenty-minute-plus-five-minute hold-off before any merge.
The next check-in is armed for 16:57 PDT with that condition written into it.

## 16:39 PDT --- #3154 round 11: an inert flag, a verb without an object, an enumerated deferral

The verdict for `cee70344` returned three findings, applied at `16c78e66` or answered outside the diff.
The `--exclude-dir=__pycache__` flag added in round 9 to stop `.pyc` hits was inert:
measured over the recipe's own path list, `-I` alone leaves 99 files, either flag alone leaves 99, and neither leaves 117, with all 18 extra under `__pycache__`.
A flag added to fix a measured problem still needs its own measurement against the fix already in place;
the sentence justifying it was false, and the flag is gone.
The cross-repo bullet's "add the destination repo's own doc paths, run in that repo" left "run" without an object;
it now says to run a second pass in that repo.
The deferral to #3161 had named one sibling skill where the derived population holds four:
`memorize`, `config-ai`, `record-learnings`, and `promote-memory` each scope their dupe check to the destination,
found by a grep over `skills/*/SKILL.md` for a search verb near a destination noun, plus one site whose verb is "read".
[#3161](https://github.com/Morrison-Lab/ai-config/issues/3161) is widened to the four with the query recorded, and the PR body's Deferred section names them.
Lesson for the fold: a deferral is a scope claim, so derive its population before filing, per `derive-dont-enumerate`.
The verdict for `16c78e66` is running.

## 16:43 PDT --- wave 1 finished unverified; a placeholder git identity on six branches

Wave 1 (run `wf_7e364ea6-880`) completed with all seven branches at two commits and none verified:
after the fix round, the recheck left 4 to 6 findings on each (#3095, #3068, #3086, #3062, #3117, #3102, #3113).
Six of the seven were authored `t <t@t.t>`, a placeholder no config in this session sets;
the branches were unpushed, so each was rebased onto its merge base with `--exec 'git commit --amend --no-edit --reset-author'`,
which gave them the configured identity and new SHAs (#3095 `77f819aa`, #3068 `6d26ba15`, #3086 `7f0718d9`, #3062 `90a305ad`, #3117 `f67e64bc`, #3102 `59e90525`).
Three wave-2 worktrees (`wt-3038`, `wt-3105`, `wt-3121`) show the same author and are left alone until that run finishes.
Wave 3 (`wf_cfdb8ea7-276`) was resumed into the two freed slots.
The seven wave-1 branches need further fix-and-recheck rounds before any push;
a serial loop is being written for them so it fits one subagent slot.

## 16:46 PDT --- the placeholder identity traced to a global config write; #3162 filed

The `t <t@t.t>` author came from one wave-4 agent, working #2422, which ran `git config --global user.email t@t.t; git config --global user.name t` from its worktree between 20:39Z and 20:43Z, presumably for a scratch repository.
A global write reaches every worktree and every concurrent agent, so nine commits across waves 1 and 2 picked it up;
`/root/.gitconfig` was restored at 23:03:20Z, the minute this session resumed after compaction, so the harness's re-provisioning ended the window rather than anything the agent did.
Filed as [#3162](https://github.com/Morrison-Lab/ai-config/issues/3162) with three mechanisms proposed:
a PreToolUse hook denying `git config --global`/`--system` writes of `user.*`, a brief line prescribing `git -c user.name=... -c user.email=...` for scratch repositories, and a pre-push author check.
The wave-1 fix-loop brief already carries the prohibition and the author check.
Lesson for the fold: "work only inside the worktree" does not cover a command typed inside the worktree that writes outside it, and `restore-global-state` reads as a rule about functions rather than about shells.

## 16:49 PDT --- #3154 round 12: one finding, and two observations filed

The verdict for `16c78e66` left one finding: the round-11 rewrite of the cross-repo bullet supplied a verb and dropped the noun,
so "that repo" took "an ai-config checkout" as its nearest antecedent and the bullet read as a second pass over the repo already searched.
The noun is restored at `a0922b12` ("in the destination repo, over that repo's own doc paths"), and its verdict is running.
Two observations the reviewer placed outside the diff are filed rather than folded in:
[#3163](https://github.com/Morrison-Lab/ai-config/issues/3163), `skill-builder` step 0's copy of the recipe lacks `-I`, the checkout guard, and the subshell;
[#3164](https://github.com/Morrison-Lab/ai-config/issues/3164), the `ums` anti-patterns entry quotes a "check existing notes" step that belongs to `record-learnings`, and `consolidate-memory` carries the same phrase.
Lesson for the fold: replacing a pronoun's anchor noun while fixing a different defect in the same sentence is how an `ambiguous-reference` regression arrives dressed as a fix;
re-read every pronoun in a rewritten sentence against its new nearest antecedent.

## 16:54 PDT --- the no-new-issues directive, clarified

The user asked whether filing #3160 to #3164 broke the 14:19 PDT directive not to grab any more new issues.
Answered with the state: nothing new has been claimed or started since the directive;
the running workflows rework branches implemented before it, and the five issues are filed, not claimed.
Asked which of filing noticed defects or resuming the parked wave 4 should also stop;
the answer was neither, so "grab" keeps its `gi` meaning (claim and implement), filing under the file-every-noticed-issue rule continues, and wave 4 resumes when slots allow.

## 16:57 PDT --- release claims on issues never started

User directive: all issues claimed but not started are to be released.
The set was derived rather than recalled: an issue search for the session id in comments returns exactly 40 open issues, the four waves' 40;
39 have implementation commits in their worktrees and one, #2513, has none, because the wave-4 implementer found the fix already on `main` in #2514 (merged 2026-08-28, `Refs #2513`) and skipped it.
Released #2513 with an unclaiming comment and closed it as completed after reading #2514.
Every one of the 40 claims is older than `claim-pr`'s two-hour expiry, so the 39 active ones are stale by the corpus's own rule and get re-posted when each branch's work resumes or pushes;
the user's "started" was read as "implementation exists", consistent with the answer given minutes earlier that parked wave 4 is not to be released.

## 17:00 PDT --- 16:57 check-in: #3146 has a quorum minus Copilot

[#3146](https://github.com/Morrison-Lab/ai-config/pull/3146) at `2b735663`: Jules approved at 23:35Z;
Copilot posted "Changes recommended" at 23:37Z with two findings, both checked against the PR head rather than `main`:
line 192 of `shared/coding/least-flexible-tool.md` writes a bare `#2189` where line 158 links it (a real nit, the shape #3034's checker is for);
line 299 of `shared/workflow/learn-from-review-findings.md` cites `hooks/flag-config-deletion-without-ref-check.py`, which is absent from the PR's tree and present on `origin/main` since #3096's branch landed, so the citation resolves once the PR merges or syncs with `main`.
The claude-review verdict had called that citation "real", which was true of `main` and not of the branch it reviewed.
Not fully clean, so the peer-PR merge path does not apply;
the PR is another session's and is left for the user to assign.
The #3154 verdict for `a0922b12` and waves 2 and 3 were still running.
Next check-in armed for 17:25 PDT.

## 17:06 PDT --- #3154 round 13: the list was called the corpus

The verdict for `a0922b12` left one finding: the fragment's Do bullet called the six-path list "the directories the corpus spans" and `ums` step 3 called running it grepping "the whole corpus",
while `AGENTS.md` and `.claude/agents/` sit outside the list (the reviewer measured three keywords, each with zero hits under the paths and an owner outside them).
Both sentences now name the list as skill-builder step 0's at `a5751eee`, the list itself stays byte-identical per #3123, and the coverage gap is filed as [#3165](https://github.com/Morrison-Lab/ai-config/issues/3165).
Lesson for the fold: a fix that documents a scope failure has to state its own scope as a measured set, not as "the whole" anything;
the entry that teaches "the word doing the damage was `memories/`, not whole" had itself written "whole corpus" two files over.

## 17:14 PDT --- #3154 round 14: the reword's own residue

The verdict for `a5751eee` left two findings, both residue of round 13's reword:
the case record still called skill-builder's query "corpus-wide" nineteen lines after the Do bullet stopped saying so,
and moving the attribution into step 3's lead sentence left the sentence after the recipe repeating it.
Both are applied at `b0cea9b3`, whose verdict is running.
Rounds 10 to 14 each found one to three wording defects, most introduced by the previous round's fix;
the corpus's own #3110 rule (three rounds without consensus, ask whether the process is wrong) applies, and the honest reading is that a two-file prose diff is being polished by a reviewer that can always find a sentence to sharpen.
The remote head `94244eb5` already carries a clean claude-review verdict and a Jules approval;
the local delta since it is seven small commits answering Copilot and the adversarial rounds.
Decision: one more verdict, then push whatever it returns if its findings are wording-only, letting the forge quorum judge the shipping head.

## 17:15 PDT --- wave 2 finished unverified; the wave-1 fix loop and the UMS round-3 verdict launched

Wave 2 (run `wf_39a49412-041`) completed with all ten branches at two or three commits and none verified;
the recheck left 3 to 9 findings on each (#3121, #3105, #3098, #3038, #3050, #3110, #3111, #3108, #3034, #3114), 60 agents and 10.8 million subagent tokens for the run.
The three branches carrying the placeholder author (#3121, #3105, #3038) were reset the way wave 1's were, before their fix-loop script was generated from the run's result.
The freed slots went to the wave-1 serial fix loop (run `wf_c4f6e28c-623`, one agent at a time) and to the UMS branch's round-3 verdict at `3011644c`;
with wave 3 and #3154's verdict that fills the cap, so the wave-2 loop and wave 4 wait.

## 17:28 PDT --- #3154 pushed at `15287fbf` after round 15; UMS branch through round 3

Round 15 on #3154 returned three findings, all wording:
"not the one the destination sits in" read partitively against the six-path list, so the Do bullet now points at skill-builder step 0 by link and says "not only the directory";
the copied path list is gone from the bullet and lives in the recipe alone;
`skill-builder` is linked at each of its three mentions.
Applied at `15287fbf` and pushed without a further private round, per the decision recorded two entries up:
`ls-remote` read `94244eb5`, the fast-forward was confirmed, and the push landed.
The PR body's checks section now names `15287fbf` and lists the four deferrals (#3161, #3163, #3164, #3165);
the Copilot thread on the `exit 1` guard is resolved, Copilot re-requested, and `@jules review` posted.
The UMS branch's round 3 reproduced every count and exit code and left one finding, a provenance parenthetical crediting #3129's review with a catch made by the round-one verdict on `fix/ums-step3-corpus-scope`;
fixed at `6c8db734`, whose round-4 verdict is running.
The wave-2 fix loop launched into the last free slot.

## 17:32 PDT --- #3154 at `2b3bd51c`: Copilot's third round reached into the touched hunk

Jules approved `15287fbf` within three minutes of the re-request.
Copilot's third round flagged two em dashes at `skills/ums/SKILL.md` lines 451 and 456, both pre-existing on `main` (the file carries 28) and neither in an added line, which is why the `--diff` ASCII gate had passed;
they sit in the hunk the anti-patterns edit touched, and Copilot reviews hunks.
Replaced with `---` and pushed as `2b3bd51c` after a fresh `ls-remote` read `15287fbf`;
Copilot re-requested, `@jules review` posted, the PR body's checks section moved to the new head.
Lesson for the fold: a hunk-scoped reviewer will report pre-existing defects adjacent to any edit, so sweep the touched hunk for the corpus's mechanical rules before the first push, not only the added lines.

## 17:39 PDT --- #3154 at `3f8f2fd9`: the hunk chase, round two

Jules approved `2b3bd51c` and the claude-review run returned Ready for merge for `15287fbf`.
Copilot's fourth round found the three em dashes left in the anti-patterns hunk (lines 458, 464, 465, pre-existing) and asked for one clause per line on step 3's lead sentence and the subsection's opening sentence;
the line-break gate then flagged the two-sentence line the dash edit had touched, so it is split too.
Pushed as `3f8f2fd9` after a fresh `ls-remote` read `2b3bd51c`;
Copilot re-requested, `@jules review` posted, PR body moved to the head.
The commit failed once because the message file is written after the gates in the script, and a gate failure skipped it;
write the message file before the gates.

## 17:41 PDT --- UMS branch opened as #3166 after round 4

Round 4 on `ums/2026-09-03-merge-visibility` returned four findings, all attribution or wording:
the closing note duplicated the opening's provenance, the `git-branches` citation claimed the issue half it does not own, the notebook's 2-versus-3 parenthetical supplied a cause that produces neither number, and the promotion line named a learning the notebook never recorded.
All four applied at `d2b5db54`, pushed as a new branch, and opened as [#3166](https://github.com/Morrison-Lab/ai-config/pull/3166) (Refs #3129) with Copilot requested and `@jules review` posted, per the convergence decision;
subscribed to its activity.
[#3166](https://github.com/Morrison-Lab/ai-config/pull/3166) edits this notebook file's part-2 region, so this part-3 branch merges `main` after #3166 lands rather than before.

## 17:46 PDT --- #3154 at `73ced6bf`: the case record cited commits GitHub no longer serves

Copilot's fifth round made two points on `3f8f2fd9`.
The wording one ("the paths skill-builder step 0 runs" implied the whole recipe is identical) is applied as "skill-builder step 0's path list".
The suppressed one was the real catch:
the case record cited `eb0cf15e`, `1732000a`, and `5f2dab94` from #3060's branch, and `git fetch origin <sha>` fails for all three,
because #3060's branch was rebased before merge (its `refs/pull/3060/head` is `f9068299`, and none of the three is an ancestor of it).
Fifteen adversarial rounds and two claude-review runs had "confirmed all four cited SHAs exist" against the local object store, which held them from the session's own fetches;
the artifact they verified was the clone, not the remote.
The record now measures at `3935bfff` and `2156b439`, both on `main`: three then four `memories/` hits, the same five MD018 lines at both, and the added entry a cross-link at the merge, so a hit count cannot tell an owner from a pointer.
Pushed as `73ced6bf` after a fresh `ls-remote` read `3f8f2fd9`;
Copilot re-requested, `@jules review` posted, PR body moved to the head.
Also on `2b3bd51c`: `review / require-clean-verdict` went red because the claude-review body narrated the instrument's "NOT clean" reading unbackticked and the verdict parser read it as the verdict (the #2497 shape);
the run on `3f8f2fd9` was green, so no action beyond noting it.
Lessons for the fold:
a SHA citation is checked with `git fetch origin <sha>` against the remote, not with `git cat-file` against a clone that may hold it;
and a case record anchors on refs the remote keeps (`main`, or `refs/pull/N/head`), never on intermediate branch commits.
