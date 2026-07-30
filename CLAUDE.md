# User-wide Claude Code instructions

<!--
Some sections below pull their body from a fragment in `shared/` via Claude
Code's `@path` import (e.g. `@shared/writing/plain-prose.md`). Those fragments
are the single source of truth for guidance shared with the UCD-SERG lab manual,
which transcludes the same files. Edit the fragment, not the inlined copy, and
keep fragments ASCII (write `---` for em-dashes) so the manual's character check
passes. See README.md, "Shared content".
-->

## Run UMS proactively, as learnings accumulate

Don't wait for `/clear` or the end of a task to run `ums` (Update Memories and Skills).
As soon as a learning worth saving shows up during a session — a corrected mistake, a new preference, a tool quirk, a workflow gap — run UMS right then, interleaved with the main work, rather than batching it for a wrap-up step at the end.

Still run UMS before `/clear` too, as a final catch-all for anything accumulated since the last proactive pass — but treat that as a backstop, not the trigger to wait for.

**In a multi-PR/multi-issue session (GII-style), treat each PR merge as a concrete proactive-UMS checkpoint, not just "whenever a learning happens to surface."** "As learnings accumulate" is easy to defer indefinitely during heads-down execution across several PRs, since no single moment feels like the obvious trigger — a merge is a natural, unmissable boundary to pause at instead. (Corrected in a sparta `gii-mwc` session, 2026-07-19: three PRs merged back-to-back with real, worth-saving learnings at each one — a subagent-resume/restart pattern, a diff-scoped-check no-op, a stale benchmark baseline — and UMS never ran until the user asked why `/clear` was suggested with UMS still outstanding, which is exactly the failure mode this fragment exists to prevent.)

**A PR's clean review verdict is a proactive-UMS checkpoint in its own right, and it fires strictly earlier than the merge -- run the pass there rather than holding it until the PR lands.**
The bullet above picked the merge because it is unmissable, and it is; the problem is that it may never arrive on this session's clock.
Merging is human-gated: [`ardi`](shared/workflow/ardi.md)'s terminal action is to report the PR ready, never to merge it.
So a clean-but-unmerged PR can sit for hours, for days, or across a `/clear`, and the review lifecycle's learnings sit with it in conversation state that may not survive the wait.
Waiting buys nothing either, because by the time the verdict is clean every finding has already been Addressed, Rebutted, or Deferred -- the review has taught everything it is going to teach, and the merge adds only whatever the merge itself surfaces.
So run UMS when the verdict comes back clean, and treat the merge-time pass as a top-up rather than the trigger.

**Offering to run UMS is not running it.**
Everything above rules out *deferring* the pass to a wrap-up step.
It has to rule out the adjacent move as well, because that one reads as compliance rather than evasion: surface the learning now, and run the pass once the user says go.

An offer to run UMS is worth exactly what an unrecorded learning is worth, since both live only in the conversation and both die with it.
The two asymmetries that decide it are already written down, for issues rather than for learnings, in [`report-mistakes-proactively`](shared/workflow/report-mistakes-proactively.md)'s "Filing is not gated on approval" section: a redundant entry is cheap while a lost one is not, and only the user can say a thing is not worth keeping --- which they can do after it is written, not only before.
Read that section rather than re-deriving the argument here.
The pattern is identical, and only the artifact differs.

What stays genuinely worth asking is **where** a learning belongs when the destination is unclear, never **whether** to record it --- the same split that fragment draws around its own dupe-check step.
Write it down first, then ask.
(Corrected 2026-07-28: a flag reading "worth running `ums` before this session ends" named a real, specific learning and still produced no pass, until the user said "you should have run ums already.")

**A new instruction arriving at a checkpoint does not cancel the checkpoint.**
The bullet above covers the pass you *announce* and never run; this is the one you never announce at all, because something else arrived first.
A merge or clean verdict is usually the exact moment I report back, so it is also the moment the next request lands.
That request then reads as the live task, and the checkpoint silently evaporates -- never refused, never deferred out loud, just never performed.
Note the asymmetry with the deferral the earlier bullets describe: there no moment feels like the trigger, whereas here a moment *did* fire and was preempted.
The remedies differ, and the preempted case cannot be fixed by naming more checkpoints.

The fix is cheap, because the pass is short.
When a request arrives at a checkpoint, either run UMS first and then start the request, or say in the same reply that the pass is owed and when it will run -- the latter being a real commitment, per the bullet above, not an offer.

The same skip has a second route worth checking, since several skills end in a UMS step ([`post-merge`](skills/post-merge/SKILL.md), [`ardi`](shared/workflow/ardi.md), [`wrap-up`](skills/wrap-up/SKILL.md)).
Reporting one of those skills complete asserts that its final step ran, so before calling a merge wrapped up, confirm the UMS pass actually happened rather than only the steps before it.
(Same 2026-07-28 session as the correction above: three checkpoints passed -- two merges and a clean verdict -- each immediately followed by a new user request, plus a `post-merge` run reported done whose UMS step never executed.)

**A merge you discover rather than perform is still a checkpoint, and it is the one that never feels like a moment.**
Every bullet above describes a checkpoint that *happens* while you are watching: you push, the verdict lands, the PR merges, you report back.
The merge someone else performs while you are away arrives differently --- as a row in a status table, hours later, alongside a dozen other rows.
Nothing about reading `MERGED` in a poll resembles the event the rule was written for, so the checkpoint passes without ever presenting itself as one.

The asymmetry is worth naming because it inverts the usual risk.
A checkpoint you witness is at least *available* to be skipped.
This one is never noticed to begin with, and the more of them arrive at once, the less any single one reads as an occasion to stop.
A status poll that flips several PRs from open to merged is therefore a strong UMS trigger, not a weak one.

So treat any transition **to** merged as the trigger, whoever performed it and whenever you learn of it.
The cheap check is the poll you are already running: if a PR you were driving reads merged now and did not last time you looked, the pass is owed.

- **Do:** run the pass when a status query first shows a PR merged, exactly as if you had merged it yourself.
- **Do:** treat a batch of merges discovered together as one checkpoint carrying all of their learnings, rather than as background news.
- **Don't:** require that you witnessed the merge for it to count.
- **Don't:** let a poll that reports several merges roll straight into the next task because no single row felt like an event.

(Corrected 2026-07-29: eight PRs from a multi-repo migration merged overnight and were discovered in a morning status check.
The session read the table, reported 14 of 22 done, and continued driving the remaining PRs for several more turns before the user said "you should have done the ums pass already.")

**Recommending that the session end is itself a UMS trigger, and it is the one route where skipping the pass destroys the learnings rather than merely delaying them.**
The three bullets above all describe a pass that is *postponed*: no moment felt like the trigger, or a moment fired and was announced, or a moment fired and was preempted.
In each of those the material survives in the conversation, so a later pass can still recover it.
This route closes that door.
Proposing `/clear`, a fresh session, or a handoff while the pass is owed is proposing to discard exactly what the pass exists to save, and the recommendation reads as responsible precisely because it is framed as tidying up.

Disclosing the owed pass in the same message as the `/clear` flag is not enough either.
That is the *offer* failure one level up: it names the debt in the same breath as recommending the action that voids it, which leaves the user to notice the contradiction.
So invert the order.
Run the pass, then flag the stopping point.
A flag that has to mention an owed UMS is a flag raised too early.

**"I am low on context" does not exempt it, and that claim needs the same test any other asserted blocker does** (see [`ardi`](shared/workflow/ardi.md)'s "Verify a blocker you assert").
It is the one blocker that is never tested, because it feels like introspection rather than a claim, and it is self-serving in a way the others are not: it excuses the work while sounding diligent.
The asymmetry also runs the wrong way for caution.
A pass that records the top three learnings in a few edits is worth far more than a thorough one that never runs, so shrink the pass rather than deferring it, and say what got left out.
If context genuinely runs out mid-pass, the entries already written are durable and the session ends having banked most of the value.
(Corrected 2026-07-28, this session: a `gia` run flagged the owed pass three times, then recommended starting a fresh session to run it, citing exhausted context.
The correction was "you should have run ums before telling me to start a fresh session".
The pass then ran to completion in the same session, which is the evidence that the blocker was never real.)

- **Do:** run the pass, then flag the stopping point, then let the user decide how to end the session.
- **Do:** shrink a pass you genuinely cannot finish, record the top items first, and say what was left out.
- **Don't:** recommend `/clear`, a fresh session, or a handoff while a pass is owed, however clearly the debt is disclosed alongside it.
- **Don't:** cite remaining context as a reason to defer, without having attempted the pass.

## Record both the pattern and the anti-pattern

When I tell you what to do, or what not to do, in a `cai` or `ums` statement, write down **both** sides: the behaviour to adopt and the behaviour to stop.
Record them explicitly, as a labelled pair, not as a paragraph that leaves one side implied.

Both halves carry information the other cannot.
A rule stated only as the anti-pattern says what to stop without saying what replaces it, which invites a second wrong behaviour that merely avoids the named one.
A rule stated only as the pattern is the more common failure and the harder one to notice: it reads as complete, but the specific move that prompted the correction usually *looks* like compliance from the inside, so the next reader has to re-derive which near-miss was actually being ruled out.
The near-miss is the whole content of the correction.
Naming it is what makes the entry falsifiable rather than merely agreeable.

Keep the pair concrete enough to check against.
"Do: run the pass before flagging a stopping point" and "Don't: recommend a fresh session while a pass is owed" both name an observable action, whereas "be diligent about UMS" names nothing and cannot be violated.
Where a correction only ever surfaced as one side, derive the other rather than omitting it, and say which side came from the user and which you inferred.

This applies to how the entry is *written*, so it composes with whatever the entry is about.
It also applies to this entry: below is its own pair.

- **Do:** state the adopted behaviour and the retired one, labelled, in every `cai`/`ums` entry that records a correction.
- **Do:** make each side an action a later reader could observe you taking or not taking.
- **Don't:** write only the corrected behaviour and leave the reader to infer which specific move it displaced.
- **Don't:** state the pair so abstractly that no concrete action would violate it.

## Flag good moments to `/clear` in long-running sessions

Proactively tell me — don't wait to be asked — when a session has grown long and hits a natural stopping point: a multi-step task or loop (GII/ARDIA/GIP, a research pass) just checkpointed or fully wrapped, a PR merged with no other in-flight work riding on this conversation, or an open question just got answered with nothing left pending.
Use the `⚠️ FLAG` tag from this file's chat-output-tagging convention, one line, at the natural end of that turn's recap — don't interrupt mid-task to say it.

Don't suggest it when there's still live state only this conversation holds: a background agent or CI run still in flight that I'm tracking, a PR I'm actively babysitting this session (waiting on CI, a review round, or a pending push), an unanswered question, or a mid-investigation train of thought that would be expensive to reconstruct.
`/clear` wipes conversation state outright (unlike compaction, which summarizes) — anything not already durable (in `CLAUDE.md`, a memory file, or a tracked issue/PR) is gone.
If UMS hasn't run recently, run it *before* raising the flag rather than disclosing the debt inside it, per "Recommending that the session end is itself a UMS trigger" above.

**Run `wrap-up`'s state sweep *before* flagging a stopping point, not after the user asks for one.**
The paragraph above says not to flag while live state remains; it doesn't say how to know.
Answering that from memory only covers the PRs and branches *this conversation* created, which is exactly the blind spot: a bot-opened PR, a leftover branch from the harness or an earlier session in the same container, or another session's PR in the same repo never entered the conversation, so nothing about them feels outstanding.
Run the sweep --- open PRs and issues per repo, `git status`, local branches, worktrees --- and let its output decide, the same way [`fully-clean`](shared/workflow/fully-clean.md) insists a PR's readiness comes from a fresh query rather than a cached verdict.
(gha#318/ai-config#733/#736, 2026-07-26: a clean stopping point was flagged twice on the strength of "my three PRs are merged."
The `wrap-up` sweep the user then asked for found a stale draft PR (`gha#316`, a bot claim-commit for an issue closed hours earlier) and an unused harness-assigned branch still sitting in the `gha` checkout.)

**Two mechanical details about that leftover-branch case, one of which reads as the opposite of what it is.**
The harness assigns its branch name in *every* scoped repo and leaves each one checked out on it, including repos the session never opens.
So the sweep finds the branch sitting in places nothing in the conversation points at, and two things follow from that.

Point 3 of the "Keep ai-config and repo checkouts fresh" section quietly does nothing in those repos.
It fast-forwards `main` only when `main` is the checked-out branch, and here it never is, so a repo you never opened stays as stale as the container left it.

And `git branch -D` refuses, with `cannot delete branch 'X' used by worktree at '<path>'`.
That message names a worktree, which reads as a second checkout holding live parallel work --- the one condition that would genuinely make deleting the branch unsafe.
It is almost always just that repo's ordinary checkout sitting on the branch.
So the cautious reading is the wrong one here, and acting on it leaves a dead branch in place for the next session to re-discover and re-adjudicate.

Settle liveness from the branch's own commits rather than from the error text, and settle it before deleting anything.
Zero commits in `origin/main..<branch>`, plus absence from the remote, together mean there is nothing to lose.
Resist adding an ancestry check beside the first of those.
An empty `origin/main..<branch>` range is the same fact as `git merge-base --is-ancestor <branch> origin/main` succeeding, so running both confirms one thing twice rather than two things once.
Once liveness is settled, switch that repo to `main` --- which is what the refusal is really asking for --- and then delete.

- **Do:** run the sweep across every scoped repo, not only the ones this session worked in.
- **Do:** settle liveness first, then `git checkout main` in that repo, then `git branch -D`.
- **Don't:** read `used by worktree` as evidence that a separate live worktree exists.
- **Don't:** assume a repo the session never opened is on `main`.

(2026-07-29/30, this session: after gha#376 and ai-config#849 merged, the sweep found the assigned branch `claude/gha-pr-374-cf7138` checked out in the `altdoc` and `rpt` clones, neither of which the session ever touched.
Both carried 0 unique commits, were ancestors of `origin/main`, and were absent from the remote.
`altdoc`'s pointed two merged PRs behind its own `origin/main`.
The first `git branch -D` failed with the worktree message, and `git worktree list` showed one entry --- the main checkout itself.)

**When flagging a good moment to `/clear`, offer archiving as the default alternative.** Whenever there's a meaningful chance I'd want to come back to this conversation later, recommend leaving the session alone and starting a fresh one for the next task, instead of `/clear`ing it -- the old session stays fully retrievable (nothing to lose), at the cost of a small navigation step to reopen it. Reserve a bare `/clear` recommendation for when nothing in the session is worth revisiting; when in doubt, default to the archive-and-start-new option since it's strictly safer.

## Flag good moments to run `compress-session`, too

The mid-task counterpart to the section above: don't wait for the automatic compaction to guess what matters, and don't wait to be asked.
Proactively flag (same `⚠️ FLAG` tag) when a session is still mid-task but has grown large — many tool calls, long tool outputs (test/CI logs, big diffs) no longer needed once their conclusions are captured, or a session that's already been through one automatic compaction and is heading for another.
Then run `compress-session` yourself: write the focused distillation and, if compaction looks imminent, trigger `/compact focus on <what matters>` rather than leaving it to the automatic pass.

Use this instead of the `/clear` flag above when there's still live state worth carrying forward (an unfinished task, a PR being babysat, an open question) — `/clear` is for a clean task boundary with nothing left to carry; this is for continuing the same work with a lighter context.

## Keep a running on-disk session lab notebook

Maintain a "lab notebook" for each session — a dated, append-only file written to *as work happens*, not only when pausing — so that if the session is interrupted with no clean exit (compaction, a forced `/clear`, a crash, a SLURM walltime death), the trail is already on disk and a later session (or I) can pick it up.
The whole point is surviving an interruption that never gives you a clean stop, so the file must live on disk and be updated frequently, not held in context and flushed at the end.

**Where.** In the session's project auto-memory directory, as a `session-YYYY-MM-DD[-slug].md` file, with a one-line pointer added to that directory's `MEMORY.md` like any other memory.
One notebook per session; start it near session start and keep appending.

**Cadence — frequently, and to disk right away.** Append a short, timestamped entry at each state change worth resuming from: a task or subtask started, a decision made or a question I answered, a PR/issue opened, a branch cut, a job launched (SLURM/background/CI, with its id), a blocker hit, a checkpoint reached.
Not every tool call — that's noise — but every step whose loss would cost real reconstruction.

**What each entry carries.** Enough for a cold reader to resume without this conversation: what we're doing and why, what's done versus in flight (branches, open PRs/issues, running jobs and their ids), open questions and decisions, and the next concrete step.

**Relationship to the pause-time and context conventions.** The notebook is the *running recorder*; the others are point-in-time:

- `handoff` writes a single snapshot *when you pause cleanly* — the notebook is its always-current substrate, so a handoff can finalize or point at the notebook instead of rebuilding state from scratch.
- `compress-session` distills the *conversation context* to survive compaction — the notebook is a durable on-disk trail, not a context-window optimization.
- The `/clear` flag above is about *choosing* a clean stop — the notebook is insurance for the stops you don't choose.

Fold a finished session's notebook into durable memory (or prune it) during UMS once its content is captured elsewhere, so the memory directory doesn't accumulate stale logs.

## Keep ai-config and repo checkouts fresh

In every session — at session start, and again periodically during long sessions — refresh the local state that goes stale as PRs merge elsewhere:

1. **The ai-config checkout.** Check that the local ai-config clone is on `main` — not a leftover work branch from an earlier session — and run `git pull --ff-only`.
   Only switch back to `main` when the working tree is clean; leave a dirty tree or another session's in-flight work alone and flag it instead.
   **If `pull --ff-only` fails with "diverged" rather than a dirty-tree error**, don't assume unpushed work is at risk — a fresh container can seed local `main` from a stale/orphaned snapshot (e.g. a pre-history-rewrite state) whose commits never landed on `origin/main` at all.
   Confirm the working tree is clean (`git status --short`) and spot-check a couple of the "unique" local commit messages against `git log origin/main` — if they don't appear there either (not even under a different hash), the divergent commits are orphaned, not real work, and it's safe to realign: `git checkout -B main origin/main`.
   Still flag it rather than force if the tree is dirty or the messages *do* look like genuine unpushed work.
   **If `main` isn't the currently checked-out branch** (the session is already working on a feature branch), skip the checkout dance entirely — `git branch -f main origin/main` realigns the ref in place without touching the working tree or switching away from the branch you're actively on.
2. **The `~/.claude` consumer copies.** On symlink-capable systems the children of `~/.claude` (`skills/`, `shared/`, `commands/`, `memories/`) are symlinks into the checkout, so the pull alone refreshes them; rerun `bootstrap.sh` only when the repo gained a new top-level dir.
   On Windows, Git Bash `ln -s` silently falls back to **real copies**, so a pull does NOT propagate there — copy-sync every file whose repo version changed into `~/.claude`.
   Before overwriting, check for edits made directly in `~/.claude` (a diff that adds prose the repo lacks) and upstream the genuine ones into the repo first; never clobber an un-upstreamed local edit.
   Don't rely on mtime to spot local edits — git operations reset mtimes on checkout, so it false-positives right after a `pull`, the case this check most needs to handle correctly.
   **Don't read "symlink-capable system" as "therefore all four children are symlinks" -- verify per child, because the split can fall inside one `~/.claude`.**
   In a remote/web container, a subset of `~/.claude/skills/` ends up as real directories holding older content, which shadow the repo for the whole session.
   `shared/`, `memories/`, `commands/`, and `CLAUDE.md` symlink normally in the same container, which is what makes this hard to spot: the child that silently doesn't refresh is the one carrying the procedures you are about to follow.
   `git pull` cannot fix it, because the loaded file is a copy rather than a link.
   Don't sweep this by hand.
   Run the instrument, which compares whole trees rather than `SKILL.md` alone and repairs what it finds, backing up every displaced copy:
   ```bash
   python3 ~/.claude/scripts/check-install.py          # report
   python3 ~/.claude/scripts/check-install.py --fix     # repair
   ```
   It reports `stale` (a real copy that has drifted -- the active defect), `unlinked` (a real copy that matches today but won't track the next pull), `missing`, `misdirected`, and `foreign`.
   **`~/.claude/scripts/` can itself be absent, and then that command is unreachable in exactly the container it diagnoses -- run the repo's own copy instead of concluding there is no instrument.**
   The path above assumes `~/.claude` links back to the checkout; a container can ship `~/.claude` holding **only** a real-copy `skills/`, with no `scripts/`, `shared/`, `memories/`, `commands/`, or `CLAUDE.md` at all, which is a strictly worse shape than the partial split described above.
   `$HOME` need not be anywhere near the checkout either (`/root` versus `/home/user/ai-config`), so a `~`-relative path is the wrong instrument for finding the repo at all.
   Run `python3 <ai-config-checkout>/scripts/check-install.py` against the checkout the session actually has.
   **Point 1 is a precondition for this one, not merely an earlier item in a list.**
   The instrument compares installed copies against the checkout, so a checkout that has not been pulled makes every report suspect -- both by measuring drift against stale reference content, and by hiding the script itself when it landed in a commit you do not have yet.
   Pull first, then measure, and re-read any figure taken before the pull as unreliable rather than merely approximate.
   (2026-07-28, an altdoc `gii` session: `~/.claude` held one real-copy `skills/` and nothing else, and the local checkout was 13 commits behind -- so `scripts/check-install.py` did not exist on disk at either path and a hand sweep against the stale checkout was run instead, reporting counts that changed once the pull landed.
   That hand sweep was also the approach this very entry had already retired, which is the failure mode the staleness causes rather than a separate mistake.)
   **`foreign` is reported but never removed, and is not a synonym for "deleted from the repo".**
   The category mixes skills we deleted with Anthropic-provided built-ins that were never ours (`docx`, `pdf`, `pptx`, `xlsx`, `skill-creator`), and deleting those would remove working harness functionality.
   Git history cannot separate the two, because remote containers check the repo out **shallow** -- `git log --diff-filter=D -- skills/<name>` returns nothing for either case -- so the call stays human.
   The repo's `UserPromptSubmit` hook runs the repair once per session, so this is normally already done by the time you would think to check.
   **The clobber happens after `bootstrap.sh`, not before it, so don't diagnose this as bootstrap skipping a pre-seeded copy.**
   Measured in one container: at `07:25:00.084` bootstrap reported 527 `already linked` and zero skips, so every skill was still a symlink; `~/.claude/skills` was then modified at `07:25:01.608`, leaving 53 real directories.
   The upstream cause is `upload_skills.sh`, which is idempotent by **skipping** any skill already in the workspace (`skip (exists)`) rather than adding a version, so the workspace copy the harness syncs down stays frozen at whatever revision was first uploaded.
   That is why a repair wired into `SessionStart` would run before the damage and report a clean install every time.
   (ai-config#755, 2026-07-28: 42 of 172 skills were stale in a web session, most at under half their real length -- `ardi` 80 lines vs 403, `ums` 94 vs 365, `ard` 134 vs 308 -- plus 3 latent unlinked copies the old `SKILL.md`-only sweep counted as identical.
   Caught only because a `ums` step contradicted a change known to have merged.
   The damage stayed small because `CLAUDE.md` itself was symlinked and restates most operative rules inline, which is the concrete argument for keeping local restatements alongside citations rather than trimming to bare pointers.)
3. **The working repo's main checkout.** Fast-forward the `main` checkout of whatever repo the session is working on (`git fetch origin`, then `git pull --ff-only` when `main` is checked out) — it goes stale as the session's own PRs and other sessions' PRs merge.
   **The same "diverged" failure from point 1 above can hit any repo's `main`, not just ai-config's own** — a fresh container's checkout isn't guaranteed fresh for every repo it holds. Apply the same recovery: confirm the working tree is clean, then check whether the local tip's commit is actually reachable from `origin/main` (`git merge-base --is-ancestor <local-tip> origin/main`) before force-realigning with `git checkout -B main origin/main`. Don't rely on a commit-message grep alone to decide safety — the same message can appear under a *different hash* after a squash-merge or rebase (so the grep matches but the underlying commits differ, the milder case in point 1), and `git log origin/main` only reflects whatever your local remote-tracking ref last fetched (so a check run before fetching in this session can miss commits that already landed). Re-run `git fetch origin main` immediately beforehand and use the hash-based ancestry check as the authoritative signal. A clean working tree plus a non-ancestor local `main` tip is still safe to realign in the common case (the checkout is stale, not carrying real work), since realigning only moves a local branch ref — the discarded commits stay recoverable via `git reflog` regardless. (Hit in both `ai-config` and `gha` checkouts in the same session, 2026-07-06: `gha`'s local `main` tip commit didn't match `origin/main` by hash *or* message at all — unlike the milder "same content, rewritten hash" case documented in point 1 — but was still just a stale checkout snapshot with nothing of value, confirmed once the working tree was verified clean.)
4. **The `.ai-config` submodule pin, in any repo that vendors ai-config as a git submodule** (check `.gitmodules` for a `.ai-config` entry — not every repo has one; most consume ai-config only via the Plugin Marketplace, which doesn't need this). Compare the pinned commit against ai-config's current `origin/main`: `git rev-parse HEAD:.ai-config` for the pin's SHA, then `git -C <path-to-a-local-ai-config-clone> rev-list --count <pin>..origin/main` for how far behind it is.
   A pin more than a few weeks or dozens of commits stale is worth refreshing: file a tracking issue, bump it (`git submodule update --init --remote .ai-config` from the parent repo handles both init and fetch in one step; or, if already checked out, `git fetch origin` inside the submodule before `git checkout origin/main`), then `git add .ai-config` in the parent repo to record the new gitlink, verify the parent repo's own checks still pass, and open a PR.
   Before assuming this is risk-free, check whether the parent repo's CI actually reads the submodule's checked-out content (vs. treating it as inert until a dev runs `git submodule update --init` locally) — a pin bump is a pure pointer change with no functional surface only when nothing reads it. (First done on `Lacaedemon/sparta` [PR #651](https://github.com/Lacaedemon/sparta/pull/651): the pin was 325 commits (~9 days) stale, unreferenced by CI, and not checked out by default.)
   **When the current checkout isn't `main` itself** (a feature branch or a worktree), `HEAD:.ai-config` only reflects that branch's own pin — it can look badly stale purely because the branch was cut before a bump PR merged into `main`, not because the project's actual pin needs refreshing. Also check `origin/main:.ai-config` (the pin as recorded on the base branch) against ai-config's `origin/main`; if that one is already fresh, no bump PR is needed — the branch's own pin resolves itself on its next merge/rebase. On Windows Git Bash, that comparison command hits an MSYS gotcha — see `memories/git.md`. (Re-discovered on `Lacaedemon/sparta`'s `claude/infallible-lewin-5841e9` branch, 2026-07-04: the branch's own pin read 344 commits stale while `main`'s was only 19 commits behind.)
   **When *adding a new citation* to an ai-config shared fragment inside a submodule-consuming repo's own `CLAUDE.md`, verify — don't assume — that the citation already resolves.** It only does once BOTH (a) the source PR has merged into ai-config's `main`, and (b) that repo's own `.ai-config` pin has been bumped to a commit containing the path — the pin doesn't auto-follow `main`. Check with `git show <pin>:<path>` (or `ls` inside the checked-out submodule) before writing the citation in present tense; if either gate hasn't cleared, hedge to future/conditional tense instead of asserting settled fact — mirroring the "proposed in ai-config#N — once merged, the fragment lives at ..." convention `gha`'s own `CLAUDE.md` already uses for citing its still-open companion PRs. Once the citation does resolve, keep the local **restatement** of the rule's key points alongside the citation rather than trimming to a bare pointer — unlike a skill distributed via the Plugin Marketplace (point 4's own preamble), `.ai-config`'s `shared/`/`memories/` fragments aren't auto-loaded into agent context — they only enter it when a `CLAUDE.md` explicitly restates or `@`-references them — so a bare citation is invisible to an agent that doesn't take the extra step of reading the fragment on demand. (`rme`#988/`epi204`#362: both cited `shared/writing/math-derivation-steps.md` in present tense while `ai-config`#502 was still open and each repo's `.ai-config` pin predated it — flagged as a dangling reference by review in both, fixed by bumping the pin once #502 merged and hedging the still-open `gha`#228 half of the same citation.)

## Timestamp recaps in local time

When printing a status recap or summary, include a timestamp in the user's local time zone (Pacific Time, `America/Los_Angeles` — get it from `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`; the explicit `TZ` enforces PT on a machine set to any other zone).
This makes "as of when" unambiguous when the user reads the recap later.

**Check the `%Z` in the output.** On Windows Git Bash the `TZ` override silently falls back to GMT (any IANA zone name does), so the command above prints GMT, not PT.
If the suffix isn't PDT/PST, fall back to plain `date` when the machine's system zone is already Pacific.
Otherwise use PowerShell: `[System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Pacific Standard Time')`.
Note the output format differs from the bash command — it's a raw `DateTime` with no timezone-abbreviation field, so format it yourself if you need the `PDT`/`PST` suffix or a compact form.

## State the actual time when reporting a scheduled check-in

When telling the user I've scheduled a wakeup or check-in (`ScheduleWakeup`, or an equivalent poll-later mechanism), state the clock time it fires at, not just the relative delay or a bare "I scheduled a check-in."
The tool result already returns a clock time (e.g. "Next wakeup scheduled for 08:22:00") — surface that time in the chat reply instead of dropping it, converting to Pacific local time per the "Timestamp recaps in local time" section above if the returned time is in a different zone.
"Scheduled a check-in to continue monitoring both" leaves the user unable to tell whether that's one minute away or twenty; "I'll check back at 08:22 PT (~4 min)" does not.

## Bare queue-command keywords

I maintain a family of slash skills for managing the task queue and amending requests: `/also`, `/first`, `/next`, `/before`, `/last`, `/and`, `/remember`, `/always`, and `/cascade`.
When I write one of these keywords **without the leading slash** as a directive — e.g. "also fix the test", "remember that ...", "always link PRs in tables", "and bold it", "next, run the spellcheck", "first, revert that" — interpret it using the corresponding skill's semantics rather than as ordinary prose. (`/remember` and `/always` both route to the `memorize` skill; "cascade" means merge stacked PRs' base branches into the PRs stacked on top of them — including main into unstacked PRs — never the PRs into main; see the `cascade` skill.)
When the word is genuinely just part of a sentence (ambiguous), fall back to the plain reading.

## Link PRs in tables

When listing PRs in a table (or anywhere they could be clickable), make each PR number a markdown link to the PR URL — `[#237](https://github.com/<owner>/<repo>/pull/237)`.
The plain text form forces the user to copy/paste; the linked form lets them open the PR in one click.

## Tag chat output by category so long recaps stay scannable

Recaps get long across many parallel tracks, so tag categories of output with a stable marker and let the eye jump straight to what needs the user's attention.
Terminal markdown can't force text color, so the emoji plus the `===` frame plus the bold label *is* the signal.
Readers skim past a question or a flag buried mid-paragraph; a marked, set-apart block is harder to miss.

Reserve a **`===` box** for the output a user is waiting on — something they must respond to (a question, an offer, a blocker) or the headline answer they asked for — and use a lighter **emoji-prefix** (bold label, no box) for informational categories they can skim.
Boxing everything defeats the purpose, so keep the box meaningful.

Boxed (a `===` line above and below the labeled block):

- ❓ **QUESTION** — need the user's input. For a real either/or, prefer the AskUserQuestion picker over a boxed question. When a question is posed inline in chat prose rather than through a box, still set it apart — its own paragraph (blank line before and after, since a bare newline collapses back into the surrounding paragraph), in bold.
- 💡 **OFFER** — optional work I can do if they want it.
- 🛑 **BLOCKER** — stopped; need their call.
- ✅ **ANSWER** — the headline answer to a question they asked (put nuance below the box).
- 🧭 **RECOMMENDATION** --- the course of action I think they should take,
  when the decision is theirs.
  Distinct from the two categories it is most easily confused with:
  an ✅ **ANSWER** reports what is true,
  and a 💡 **OFFER** proposes work I would do.
  A recommendation is a judgment about what *they* should do,
  including about things I will not be doing ---
  which PR to merge first, which option to decline, whether to stop.
  Lead the box with the action and put the reasoning below it,
  so the box holds the call rather than the argument for it.
  It boxes because it feeds a decision they are waiting to make;
  an opinion nobody was waiting on is a 📊 **UPDATE** with a view in it,
  and stays unboxed.
  - **Do:** box the recommendation, lead with the action,
    keep the reasoning under the box.
  - **Don't:** bury it in a closing paragraph,
    or fold it into an ✅ **ANSWER** box
    so a factual claim and a judgment read as one thing.
- 🔀 **MERGE ORDER** --- several PRs are ready,
  and merging them in the wrong order would produce a wrong result.
  The one category labeled with a markdown **heading** (`### 🔀 MERGE ORDER`) rather than bold text,
  since a heading is the only "large font" lever a terminal has.
  List the PRs in the order to merge, each linked per "Link PRs in tables" above,
  naming what each one's position depends on.
  The PR-side and draft-gating surfaces live in the "Surface merge-order constraints" section.

Prefixed, no box (informational, frequent):

- 📊 **UPDATE** — status or progress.
- ⚠️ **FLAG** — non-blocking heads-up or risk.
- ✔️ **DONE** — a completed action.
- 🟢 **ALL CLEAR** — nothing needs the user right now; work continues in the background. The recap's standing sign-off.

Keep the markers stable so they become muscle memory.
The set-apart ❓ **QUESTION** format also gives the `prompt-me` / `prompt-me-all` skills a reliable signal to key off when they sweep the transcript for unanswered questions later.
The user may tune the emoji set; the full taxonomy and rationale live in `memories/preferences.md`.

## Surface merge-order constraints

When two or more PRs are open and merging them in the wrong order would produce a wrong result,
say so where I'll act on it, not in ordinary prose I'll skim past.
Three surfaces, escalating in strength; use as many as the situation earns.

1. **In chat** --- the boxed `### 🔀 MERGE ORDER` marker above.
2. **On the PRs** --- lead each affected PR's body with a `> [!IMPORTANT]` alert
   naming that PR's position and its prerequisite,
   e.g. "Merge [#N](url) first --- this PR is stacked on its branch."
   Update or drop the alert once the prerequisite merges.
3. **Draft-gating** --- hold the dependent PR as a draft until its prerequisite merges,
   then mark it ready.
   GitHub won't merge a draft,
   so this makes the wrong action unavailable rather than merely discouraged.

Draft-gating is the last resort, not the default, because it costs something real:
converting a ready PR to draft **drops auto-merge and merge-queue membership**,
and a draft doesn't trigger the `@claude` review bot (see `shared/workflow/pr-on-claim.md`),
so drafting an unreviewed PR stalls its own ARDI loop.
Drive the PR to fully clean first, and draft-gate only if the prerequisite still hasn't merged.
Say in chat and on the PR that it's being held and why,
and un-draft promptly once the prerequisite lands.
A silent draft is never a substitute for stating the order.

This fires only when order changes the outcome:
a stacked PR whose base is another open PR,
a PR that would conflict or show a misleading diff if the other landed first,
a migration that must precede its consumer.
Two PRs touching disjoint files have no constraint,
and saying so plainly is the right answer, not an occasion for the marker.
The rationale behind each surface lives in `memories/preferences.md`,
alongside the rest of the taxonomy.

## Present decisions one at a time

When more than one decision needs my input, go through them one at a time:
pose the single most pressing question, wait for my answer, then pose the next.
Don't batch several decisions into one message or one multi-question `AskUserQuestion` call.

Two reasons.
The answer to the first question often changes or moots the later ones, so a batch makes me answer against stale premises.
And a wall of questions invites a partial reply that leaves the rest silently unanswered — the exact failure mode `prompt-me` / `prompt-me-all` exist to recover from.

Mechanics:

- Rank by how blocking each decision is, most pressing first (the same ranking `prompt-me` uses), and pose only the top one — via a single-question `AskUserQuestion` call for a real either/or, or one boxed ❓ **QUESTION** otherwise.
- Say how many more are queued behind it ("2 more decisions after this one"), so the backlog is visible without being posed.
- Fold each answer into the framing of the next question, and silently drop any queued question the answer mooted.
- Keep working on whatever the pending decision doesn't block while waiting.

This changes how decisions are *posed*, not whether to ask at all: `research-before-asking` still gates each question, and an `away` grant still means don't block on questions — resolve them by judgment, or skip-and-note, per that skill's scope.
And it yields to an explicit request for the full backlog — `prompt-me-all` / "ask me everything at once" is the user opting into a batch view.

## Title Claude sessions with the PR/issue number

Name each Claude Code session (the title shown in the web/app session sidebar) `#NNN brief description` — the number of the PR or issue the session is working, then a short description.
Don't prefix it with "PR" or "Issue"; just the bare `#NNN`.
So `#316 session title convention`, not `PR #316 session title convention` or `PR session title convention`.

## Re-check for latest review findings before reporting PR status

**Before** reporting status on a PR (especially "clean" / "ready to merge"), re-read the **most recent** review comment on the PR.
Don't trust an earlier "verdict" you've cached — a new review may have been posted since (by the @claude bot, by a human, or by a re-trigger), and that newer review may contain findings the old one missed.

Specifically: when scanning checks (`gh pr checks`) shows green or "no failures", that's about CI state, **not** review verdict.
Always pull the latest claude comment (`gh pr view N --json comments --jq '[.comments[] | select(.author.login == "claude")] | last | .body'`) and parse it for any "Findings", "Issues", "Remaining" sections before declaring a PR ready.

**Also check formal GitHub reviews, not just issue-style comments — a human's `CHANGES_REQUESTED` can be invisible to a comments-only scan.** A review submitted via GitHub's review UI (as opposed to a plain PR comment) shows up in `gh pr view N --json reviews`, and its top-level `body` is frequently **empty** — the actual finding lives entirely in a per-line inline comment, which only appears via `gh api repos/<owner>/<repo>/pulls/N/comments` (a different endpoint from issue comments). Checking `--json comments` alone can miss the review's existence entirely. Before declaring a PR ready, also run:
```
gh pr view N --json reviews --jq '.reviews[] | select(.state == "CHANGES_REQUESTED") | "\(.author.login) \(.submittedAt)"'
gh api repos/<owner>/<repo>/pulls/N/comments --jq '.[] | "\(.path):\(.line // .original_line // "?") \(.user.login) \(.body)"'
```
A `CHANGES_REQUESTED` state is blocking regardless of whether an automated re-review later says "Ready for merge" — that bot verdict doesn't clear a human's own review state, which only the human (or an explicit dismissal) can resolve.

(A specific case of the standing **never assume; always verify** rule in `memories/preferences.md` — confirm the verdict with a fresh query, don't recall it.)

## Post in-chat feedback to the PR

When the user gives feedback, corrections, or guidance in the CLI or chat while working a PR, paraphrase it and post it as a PR comment:

```
gh pr comment <N> --body "..."
```

One to three sentences is enough.
Don't quote verbatim — paraphrase so it reads naturally in the PR thread.
Skip trivial acknowledgments or conversational exchanges with nothing to act on.

This makes context visible to future @claude sessions, other reviewers, and contributors who only see the PR thread.

## Subscribe to PR updates automatically

When opening or taking over a PR in any repo, subscribe/watch that PR's activity immediately using the available GitHub notification/subscription mechanism. If the current session's tools cannot subscribe, say so explicitly and fall back to active polling for reviews, comments, and checks during the session.

## Claim a GitHub PR/issue before working on it

<!-- Shared with the lab manual; edit shared/workflow/claim-pr.md, not here. -->
@shared/workflow/claim-pr.md

The `claim-pr` skill operationalizes this (the exact claim wording, when it applies, and the closing/unclaim comment).

## Open a PR immediately after claiming an issue

@shared/workflow/pr-on-claim.md

The strong form of the claim: after claiming an issue you're about to work, open the PR right away — before implementing — from an empty commit, kept as a draft until the implementation lands.
An open PR is the visible in-flight signal other sessions check, so opening it up front stops parallel duplicates.
The `gi`, `gii`, `gip`, and `st` skills operationalize this.

## Open a PR for every pushed feature branch

After pushing a feature branch, create its PR
unless an existing PR already represents that branch
or the user explicitly says not to.
Don't treat a successful push as the handoff:
the PR is the reviewable unit and the durable visible record of the work.

## Use the existing PR branch, not the harness-specified branch

The Claude Code on the web harness injects a "Git Development Branch Requirements" section that assigns a session-unique branch name (e.g. `claude/abc123`) as the default for each repo.
**That branch is a fallback for brand-new work with no existing PR.**

When a task involves an existing PR or branch, work on that PR's branch instead:

1. Find the branch name: call `mcp__github__pull_request_read` (`method: get`) or (in CLI sessions) `gh pr view <N> --json headRefName -q .headRefName`.
2. Check it out or create a worktree from `origin/<branch>`.
3. Push back to that branch and update the existing PR --- do not open a new one.

Use the harness-specified branch only when starting work with no existing PR and no existing branch to continue.

**Treat a PR-preview URL as an explicit PR target.**
If the user points to a page under a path like
`.../pr-preview/pr-436/...`,
interpret that as "work on PR #436" by default:
check out that PR's branch,
push updates to it,
and update that same PR.
Do not open a separate PR unless the user explicitly asks for one.

**Exception --- the session can only push to its own branch.** Some web/remote sessions are scoped so the agent proxy allows pushing *only* to the harness-assigned branch; a push to any other branch (the existing PR's branch included) is rejected with `HTTP 403`.
When that happens you cannot follow step 3.
Don't retry the 403 --- it's a policy denial, not a transient error.

**Prefer stacking the fix, not superseding the PR.** When the work is an incremental fix to an existing, still-open PR (a review finding, a small addition) rather than a full rebuild, push the fix to the assigned branch and open it as a PR **stacked on** the original --- `base` set to the original PR's own branch, per the [`stack-prs`](skills/stack-prs/SKILL.md) skill --- rather than superseding it. Comment on the original PR pointing to the stacked one, and note the dependency ("stacked on this branch — either merge #N into this branch first, or merge this PR and #N will retarget to `main`"). This keeps the diff to just the incremental change instead of re-litigating the whole original PR's content, and it composes correctly regardless of how the maintainer merges it: they can merge the stacked PR straight into the original's branch (folding the fix in before the original PR itself merges) or merge the original first and let the stacked PR retarget to `main` per that skill's step 4.
Reserve the supersede path (below) for when stacking doesn't fit --- the original branch/PR is abandoned, or the fix amounts to a full rebuild rather than an incremental addition.
(Corrected on ai-config#493 → #498, 2026-07-05: first reflex was to supersede per the fallback below; the user redirected to stacking, and the maintainer then merged the stacked PR directly into #493's branch, folding the fix in before #493 itself merged --- exactly the outcome stacking was meant to produce.)

**Supersede fallback, when stacking doesn't apply:** push the fix to the assigned branch, open a **new** PR off `main` that supersedes the original (say "Supersedes #N" in the body and rebuild as a single clean commit so no sensitive history leaks through), comment on the original PR pointing to the replacement, and close the original once the new PR merges.

**Rebuilding the single clean commit: diff against `main`, don't cherry-pick from the write-protected branch.** `main` usually doesn't yet contain the original PR's changes, so cherry-picking just your incremental fix commit conflicts --- it was written against the PR branch's state, not `main`'s.
Instead, diff the whole file set and apply it fresh:
```bash
git diff origin/main <old-branch> -- <changed-files> > /tmp/rebuild.diff
git checkout -B <assigned-branch> origin/main
git apply /tmp/rebuild.diff
git add <changed-files> && git commit -m "..." && git push -u origin <assigned-branch>
```
(Seen on ai-config#372 → #380: the assigned branch could push, `sync-freshness-rule` could not.)

**Check whether the branch's own PR merged before adding more commits to it.** If a PR on this branch merged via **squash** (common in repos that enforce it), the branch's old commits are no longer ancestors of `main`'s new tip — `git merge-base --is-ancestor <old-commit> origin/main` returns false.
Committing follow-up work on top of that stale branch and pushing looks fine locally, but the resulting PR's diff shows the *entire prior PR's changes again* against `main`, confusing reviewers and re-litigating already-merged content.
Before adding commits to a branch you didn't just create, fetch `origin/main` and check ancestry first.
If the branch's own PR already merged, don't build on top of it — start clean: `git checkout -b <branch> origin/main`, then `git cherry-pick` only the genuinely new commit(s).
If you've already pushed a bloated diff, the same fix applies retroactively: rebuild the branch from `origin/main` plus a cherry-pick of the new work, then `git push --force-with-lease`. (Seen on gha#161 → gha#162 and ai-config#344 → ai-config#354, both squash-merged.)

**A live variant of the same check: the human can merge the branch's PR out from under an in-flight push, not just leave a stale branch to discover later.** Pushing a commit right as its own PR merges lands in a race in repos that auto-delete head branches on merge: GitHub deletes the head branch, and the in-flight push silently recreates it under the same name --- but now as a brand-new, orphaned branch with no PR, built on top of commits that (for a real merge commit, unlike the squash case above) *are* ancestors of `main`'s new tip. `git status`/`git push` report success --- but the push is not quite silent, and its one tell is worth knowing, because it fires at the moment of the race rather than hours later. A push onto a branch that still exists prints a SHA range (`f7bf71f..899e5de  <branch> -> <branch>`); a push that *recreates* a deleted branch prints `* [new branch]      <branch> -> <branch>` instead. Seeing `* [new branch]` for a branch you have already been pushing to means the remote branch was deleted underneath you, which on a PR branch means the PR merged. Read the push output rather than only its exit status, and run the ancestry check immediately when that line appears. Recovery is the same ancestry check as above (`git merge-base --is-ancestor <branch-tip> origin/main`), then cherry-pick the orphaned commit onto a fresh branch off the new `origin/main`; note that this check's *answer* depends on the repo's merge strategy and so is not itself the signal --- it comes back true where the PR merged as a real merge commit (the serocalculator case below) and false in a squash-merge repo, where `main` carries a new single commit your branch never saw. Either answer leaves the recovery the same, and in the squash case the orphaned commit is genuinely absent from `main`, so check whether its content actually landed (`git show origin/main:<path> | grep`) rather than inferring it from the merge notification; delete the stray local and (if push-permitted) remote branch. If the orphaned commit is genuinely new work --- not a fix that belongs in the now-merged PR --- treat this as the natural start of a new, stacked issue + PR rather than trying to reopen or append to the merged one. (`UCD-SERG/serocalculator#568` → `#572`, 2026-07-20: pushed a `Var(y_obs | y_true)` derivation commit just as #568 merged; recovered by cherry-picking it onto a new branch off `main`, filing #571 to track the follow-on `Var(y_obs | T=t)` derivation it was a prerequisite for, and opening #572 stacked on nothing but current `main`.) (`ai-config#778` → `#783`, 2026-07-28: the squash-merge counterpart. A commit fixing a review nit was mid-push when #778 merged; `git push` printed `* [new branch]`, `git merge-base --is-ancestor` returned false, and `git show origin/main:<path>` confirmed the fix was absent from `main` --- so a PR comment claiming the nit was addressed would have been false. Recovered by cherry-picking onto a fresh branch off current `main` and opening #783, with a comment on #778 saying which of its findings did not ship in that merge.)

**The harness-assigned branch name itself can already exist locally, pointing at unrelated stale content from an earlier session in the same container.** A fresh container doesn't guarantee a fresh local branch state --- `git checkout -b <harness-branch> origin/<existing-PR-branch>` can fail with "a branch named `<harness-branch>` already exists" if a prior session in this container created one under that same name and left it pointing at old work. Don't assume it's safe to reuse or that it reflects the actual PR: check `git merge-base --is-ancestor <local-tip> origin/main` first --- if the local tip is already an ancestor of `main` (i.e. it was old, already-merged content, not in-flight work), it's safe to discard by force-checking out the real PR branch under that same name with `git checkout -B <harness-branch> origin/<existing-PR-branch>` (uppercase `-B` resets the branch in place instead of erroring). (ai-config#481: the assigned branch name `claude/resolve-pr-481-conflicts-dz9v4w` already existed locally, pointing at a commit that turned out to be an ancestor of `main` from an earlier session --- switched to the actual PR branch instead, per this section's own primary rule.)

**A PR whose head branch lives in a different repo entirely (not just a scope-restricted push) always needs the supersede path --- there's no fix-in-place option to prefer over it.** A cross-fork "sync upstream into main" PR --- opened by comparing `<upstream-owner>/<repo>:main` against `<fork-owner>/<repo>:main` --- has its head ref owned by the upstream repo, not the fork. When that PR shows a real conflict (`mergeable_state: dirty`), the fork has no push access to the head branch at all, regardless of what the harness's own push-scope policy allows elsewhere in the session --- so the stacking preference above doesn't apply here; go straight to superseding. Fetch both remotes, merge upstream's branch into a fork-local branch off the fork's own `main`, resolve conflicts there, open a same-repo PR ("Supersedes #N" in the body), and close the original once the replacement merges. (`d-morrison/altdoc#20` → `#22`, 2026-07-14: `#20` compared `etiennebacher/altdoc:main` against the fork's `main` and hit a real `NEWS.md`/`tests/testthat/helper.R` conflict with no push access to fix it on that PR; `#22` redid the sync from a fork-local branch and merged clean.)

## Skills that call gh/glab: fall back to tool-mappings.md in remote sessions

Many skills under `skills/` name concrete `gh`/`glab` CLI commands (e.g. `gh pr comment`, `gh issue create`).
In a remote/web session where `gh`/`glab` isn't on `PATH`, substitute the equivalent GitHub MCP tool from [`tool-mappings.md`](tool-mappings.md) instead of failing or improvising.
That registry is the single source of truth for the gh/glab-to-MCP mapping in this repo --- don't inline a separate translation table into individual skills; point to `tool-mappings.md` and let it stay the one place to update. (GitLab operations have no MCP equivalent listed there; `glab` stays CLI-only.)

## Install and use MCP servers proactively

@shared/workflow/use-mcp-servers.md

The section above is about substituting an MCP tool for a CLI command when the CLI is missing.
This one is the other direction: when a server would help, install and register it rather than waiting to be asked --- including locally, where `tool-mappings.md`'s per-model table describes the default rather than a limit.
Covers reading `claude mcp list` for transport rather than name (a plugin's remote server can shadow the local one you meant), 400-versus-401 on an uninterpolated credential, supplying tokens by launch wrapper instead of storing them, opt-in toolsets whose selection *replaces* the default, and verifying by a real call rather than by the tool listing.
Its last section generalizes past MCP: when a standing rule names a mechanism this session doesn't have, look for the local equivalent instead of silently degrading to a worse fallback.

## File an issue before starting a new task

<!-- Shared with the lab manual; edit shared/workflow/issue-first.md, not here. -->
@shared/workflow/issue-first.md

The `st` (Start Task) skill operationalizes this; `gi` (Grab Issue) is the path when the issue already exists.

## If you see something, say something — file an issue for every noticed mistake

@shared/workflow/report-mistakes-proactively.md

The proactive counterpart to issue-first above: when a mistake shows up in any medium — code, prose, AI-config files, `gha` workflows, snapshot and other generated files, or anything else — even out of scope for the current task, flag it in chat (`⚠️ FLAG`) and file a tracking issue immediately, in a repo we administrate.
Never file autonomously in an external repo; the upstream-issues ladder governs that case.
The `defer-issue` skill covers the user-initiated version of this; this rule is self-initiated.

## Tracking issues in upstream repos

<!-- Shared with the lab manual; edit shared/workflow/upstream-issues.md, not here. -->
@shared/workflow/upstream-issues.md

The `sup` / `send-upstream` skill operationalizes steps 1--2 (the PR path, including fork-if-needed, and the issue path) and the link-back.
Step 3 (own-repo fallback) is not covered by `sup`; use `gh issue create` in the current repo and ask the user to transfer it.

## Wrap up a merged PR with UMS

When a PR/MR you were working on **merges**, run the `post-merge` skill: verify the merge actually landed, tidy the local branch (checkout `main`, pull, `git branch -d`), confirm any deferred items have follow-up issues, then run **UMS** to capture what the PR's review lifecycle taught — recurring review findings, corrections, and guidance given along the way.
A merge is the natural checkpoint to bank lessons before the context is lost.

This is not the *first* checkpoint, though, and it should rarely be the one carrying the whole backlog.
Per "Run UMS proactively" above, the pass already ran when the review verdict came back clean, so `post-merge`'s UMS covers what the merge itself taught -- a conflict resolved on the way in, a check that only fires on `main`, a squash that reshaped the history.
Run it regardless: a short pass that finds nothing new is the expected outcome when the verdict-time pass did its job, not a reason to skip the step.

"merge it" / "merge this" / "merge the PR" as bare directives (no slash) trigger the `merge-it` skill: when the PR isn't merged yet, it merges the ready PR (squash by default) **then** chains straight into `post-merge` (tidy + UMS); when the PR is already merged it goes directly to `post-merge`.
Either way the post-merge wrap-up — including the UMS follow-up PR — runs **automatically, without asking**.
If the phrase is clearly part of ordinary prose rather than a standalone directive, treat it as such.

## What "fully clean" means

<!-- Shared with the lab manual; edit shared/workflow/fully-clean.md, not here. -->
@shared/workflow/fully-clean.md

Escalate a deadlock via the `request-pr-review` skill (human reviewer `d-morrison`, or `gh pr edit <N> --add-reviewer d-morrison`), and surface the open item to me.

## Always run ARDI on PRs you touch

<!-- Shared with the lab manual; edit shared/workflow/ardi.md, not here. -->
@shared/workflow/ardi.md

The `ardi` / `iterate` skill family runs this loop. (See *What "fully clean" means* above; the mechanics for each step are in the sections around here.)

## Do the review yourself when the @claude workflow doesn't produce a verdict

When a PR you're managing has its `@claude` review workflow fail to produce a usable verdict — whether because it was **skipped for quota** or because it **ran to completion but never stated a verdict** (a "stub review") — don't stall the ARDI loop waiting for it — **do the review yourself and post it** as a PR comment.
Apply the same review standards the bot would (the SERG lab manual and d-morrison's modular/idiomatic priorities), then keep iterating to fully-clean on your own findings.
Neither failure mode is an approval — an unreviewed PR stays unreviewed regardless of why the bot didn't weigh in.

**Quota-skipped:** surfaces as a bot comment — either `Claude review skipped — API quota exhausted` (the review workflow) or `You've hit your org's monthly spend limit` (the `@claude` agent workflow).
Both mean no bot will respond on this run; re-running the workflow only helps once the quota actually resets.

**Stub review:** the review job reports success (`is_error: false`, real cost/turns logged) but the posted comment never states a `### Verdict` — the run genuinely executed but got cut short before reaching a conclusion (e.g. by escalating permission denials on tool calls it needed). This looks superficially fine (green check, a comment exists) so it's easy to mistake for a real review — read the comment body for an actual verdict section before trusting it. Re-running the same workflow can reproduce the same stub pattern repeatedly rather than self-resolving; if a retry doesn't help within a round or two, treat it as this failure mode and self-review rather than continuing to re-trigger. (Hit repeatedly on gha#193/gha#198, where `claude-review` produced escalating permission-denial-driven stub reviews across many runs before the actual fix — a same-prompt retry composite, gha#201 — landed.)

**Post the self-review before doing anything else — don't stall the PR waiting for the bot. Then, before writing the check off as permanently broken, try one manual re-run of the failed job — even after the workflow's own built-in same-run retry (e.g. gha#185's stub-retry) also stubbed.** Two stubs back to back is a stronger signal than one, but it's still not conclusive: a separately-triggered re-run (`rerun_failed_jobs` via the GitHub Actions API/MCP tool, not just re-reading the same run) is an independent LLM invocation, and the failure modes behind stubs (permission-denial spirals, timing) don't always repeat. If the check is a **required** one, spend the one manual re-run before reporting the workflow as broken for that PR. (`ucdavis/epi204`#361: attempt 1 and its automatic same-run retry both stubbed; self-reviewed and posted a verdict; a manual `rerun_failed_jobs` on that same workflow run then produced a genuine review — and it wasn't a rubber stamp, it caught a real one-sentence-per-line violation the self-review's own added text had introduced.)

Either way: don't wait on the bot indefinitely — do the review yourself and keep driving to fully-clean.

**Self-review is the immediate fallback so the PR never stalls --
but declaring the PR clean still requires an external verdict whenever one is reachable.**
Don't wait to self-review: post it right away, same as above.
But also check, the same round, whether a *different* configured reviewer is reachable
(e.g. Copilot code review, if the repo/org has it) --
not just whether the `@claude` bot specifically produced a verdict,
since the two can fail independently (one quota-exhausted, the other working fine, or vice versa) --
and request it in parallel with posting the self-review, not after.
Re-check reachability every round:
a reviewer that was ineligible/quota-exhausted a few pushes ago (a missing license, a temporary rate limit)
can become reachable mid-session.
Before reporting a PR **fully clean** / **ready** (ARDI's own terminal-state terms -- see `fully-clean.md`),
confirm a genuine all-clear review is posted at the current head from an external reviewer, if one is reachable --
a self-review alone, or a clean state you inferred yourself from green CI and resolved threads,
doesn't satisfy this once an external verdict is obtainable.

## Watch and ARDI every PR you touch — don't ask first

When you open (or are handed) a PR/MR in **any** repo, subscribe to its activity and run the ARDI loop to clean **automatically** — never ask "should I watch this?" or "should I iterate it?" first.
That answer is a standing yes across all PRs and all repos.
Subscribe with the `subscribe_pr_activity` tool (provided by the GitHub MCP server in remote/web sessions) or babysit locally, drive every review round to fully-clean, and re-arm a periodic check-in since webhooks don't deliver CI-success or merge-conflict transitions.

This webhook-driven loop never formally invokes the `ardi` skill, so read `skills/ardi/SKILL.md` step 6 for the re-request-review mechanics before pushing a fix: after a push, the push itself already triggers the review — don't also post "@claude review again" in the same round.
On workflows with `concurrency: cancel-in-progress`, the two triggers race and cancel each other, leaving the latest commit's review canceled and `require-review` red for no code reason.
Only post the mention when a round pushed no code (all Rebut/Defer). (Hit on ai-config#406: posting the mention right after a push canceled the review and cost three extra polling rounds to recover.)

Surface to me only when an item is ambiguous, architecturally significant, or deadlocked (the escalation rule above still applies), or when the PR is clean.
Stop watching only when the PR merges or closes, or I tell you to back off.

## Babysit PRs efficiently — batch pushes, trust CI's own reports, skip redundant lookups

@shared/workflow/efficient-pr-babysitting.md

A long babysitting session accumulates avoidable tool calls and CI runs otherwise:
trickled single-item pushes each re-trigger CI and race each other's reviews,
a local re-run can rediscover a gap CI's own comment already named,
and a pure re-post webhook event doesn't need fresh analysis.

## Address every in-scope review comment, even non-blockers

<!-- Shared with the lab manual; edit shared/workflow/address-every-comment.md, not here. -->
@shared/workflow/address-every-comment.md

If you and the reviewer reach an impasse on a single item (your rebuttal didn't convince them and their re-raise didn't convince you), escalate that item to a **human reviewer** — request `d-morrison` via the `request-pr-review` skill (or `gh pr edit <N> --add-reviewer d-morrison`) and `@`-mention them with the impasse — for the final call rather than looping.

## Keep PR branches synced with main

<!-- Shared with the lab manual; edit shared/workflow/sync-with-main.md, not here. -->
@shared/workflow/sync-with-main.md

(Another instance of **never assume; always verify** — `git fetch` to check main's actual position instead of assuming the branch is current.
The `sync-pr-branch` / `merge-main` skill runs this.)

## Move referenced assets along with content that migrates or gets removed

<!-- Not yet shared with the lab manual; edit shared/workflow/migrate-referenced-assets.md, not here. -->
@shared/workflow/migrate-referenced-assets.md

## Prioritize internal infrastructure work slightly over feature work

<!-- Shared with the lab manual; edit shared/workflow/pr-prioritization.md, not here. -->
@shared/workflow/pr-prioritization.md

A tie-breaker for `ardia`'s PR-ordering step and `gi`'s (and `gii`/`gip`'s) issue-priority table when candidates are otherwise close in priority.
The fragment also sets the default direction for the age factor: among several open PRs, take the **older** one first unless you have more specific instructions.

## Use subagents when helpful

When available, use subagents for helpful sidecar work: independent investigation, verification, or disjoint implementation slices. Keep immediate blocking critical-path edits local so progress does not wait unnecessarily.

## Non-destructive repo and memory actions

The user gives general permission to proceed with non-destructive actions such as setting up PRs, reading GitHub repository data through the API, running non-destructive Git and Perl commands, and editing shared `CLAUDE.md` memory. This includes pushing branches and opening PRs against the ai-config repo. Default to action without confirmation for reasonable non-destructive steps; ask only for destructive, ambiguous high-impact, or genuinely blocking choices. Destructive operations still require explicit instruction.

## Auto-orchestration: always look for Workflow opportunities

The heavy, parallelizable skills (`ardia`, `ardiaei`, `gia`, `gip`, `grade-work`, `opposition-research`, `find-overlap`) decide on their own whether a task warrants multi-agent orchestration via the `Workflow` tool --- so I don't have to type `ultracode` every time.
The `Workflow` tool stays opt-in-gated for bare prompts; an invoked skill is itself the sanctioned opt-in.
Launch a workflow directly when an opt-in signal is already present (`ultracode`, a `+Nk` budget, or "use a workflow"), otherwise propose one with a one-line cost estimate and wait.
The PR/issue-iteration skills stay serial where pushes collide on shared review runners (see the fragment's shared-runner exception).

More generally --- not just inside the named heavy skills --- always look for opportunities to automate work via the `Workflow` tool.
When a task turns out to be workflow-shaped (decomposable, verification-bearing, and at a scale that earns it --- see the fragment's criteria), say so and propose a workflow even if no skill mandated one.
The same opt-in gate still applies: propose with a cost estimate and wait unless an opt-in signal is already present.

<!-- Shared with the lab manual; edit shared/workflow/when-to-orchestrate.md, not here. -->
@shared/workflow/when-to-orchestrate.md

## Algorithmatize checks: instruments over LLM reasoning

Never spend LLM reasoning on a check a deterministic algorithm can decide:
build or run the instrument (a repo script, a CI step, a state dump plus a
threshold) and consume its verdicts, reserving model judgment for the
genuinely semantic remainder.
When you catch yourself (or a reviewer) re-deriving numbers by hand, or
eyeballing an artifact for a property with a numeric definition, that check
wants to be an instrument --- see the fragment for the procedure and tells.

@shared/workflow/algorithmatize-checks.md

## Check for merge conflicts on every merge in an ultracode session

@shared/workflow/ultracode-merge-conflicts.md

## Big-picture principles: KISS, DRY, DRW, modularity, and friends

Our big-picture principles are cataloged centrally in `shared/principles/` — the overall dev goals they serve (code and prose that is valid and easy to externally validate, reproducible, highly functional, reliable, secure, efficient, maintainable, extensible, human- and AI-readable, and reusable), each principle's statement (KISS, YAGNI, DRY, DRW, modularity, least astonishment, purity, self-documenting code, fail fast, algorithmatize checks — plus the reduce/reuse/recycle lens over them), the specific rules and skills that operationalize each, and how the principles relate and trade off.
When encoding a new coding/review rule, file it under the principle it serves (and add a new principle to the catalog when one emerges) rather than leaving either the rule or the principle floating free.

@shared/principles/README.md

## Don't reinvent the wheel (DRW) — in dev and in review

Before implementing a new function or feature, check that it hasn't already been done — in one of our own repos, or in a trustworthy external source we could depend on instead (base R, r-lib, tidyverse, a well-maintained CRAN package).
Prefer forking and/or contributing to an existing external source over re-building the functionality from scratch.
Apply this in review too: a hand-rolled equivalent of functionality that already exists is a review finding, the same weight as any other standing review check.

@shared/principles/dont-reinvent-wheel.md

The `prefer-upstream` skill runs the search; the `prefer-packaged-functions` fragment below is the R-function special case; the `scout-peers` skill gates borrowed code by license.

## Fail fast — no silent failures

Detect bad state early and stop with a clear error rather than proceeding on it; never swallow an error into a silent fallback (a bare `except:`, a `tryCatch` returning `NULL`, a shell `|| true`), and make any genuinely wanted fallback explicit, bounded, and observable.
Apply this in review too: error handling that hides failure is a review finding, the same weight as any other standing review check.

@shared/principles/fail-fast.md

## Coding: KISS is the umbrella principle

Follow the KISS principle (keep it simple, stupid) in code and prose alike:
prefer the simplest construct that does the job, and treat added complexity
as a cost that needs justification.
The specific coding rules below --- every fragment under `shared/coding/`,
indexed by the principle it serves in the catalog above --- and the
review-side
`challenge-unnecessary-complexity` policy are special cases of this
principle — they exist because a bare "keep it simple" isn't concretely
reviewable, but when a case arises that none of them covers, apply KISS
directly rather than treating the enumerated rules as exhaustive.

## Coding: use the least-flexible construct that does the job

<!-- Not yet shared with the lab manual; edit shared/coding/least-flexible-tool.md, not here. -->
@shared/coding/least-flexible-tool.md

## Coding style: avoid nesting; follow the lab manual

Follow the SERG lab manual (https://ucd-serg.github.io/lab-manual/) for coding and collaboration conventions.

<!-- Shared with the lab manual; edit shared/coding/avoid-nesting.md, not here. -->
@shared/coding/avoid-nesting.md

## Coding: single-indent multi-line function signatures

<!-- Not yet shared with the lab manual; edit shared/coding/function-signature-style.md, not here. -->
@shared/coding/function-signature-style.md

## Coding: prefer existing packaged functions over rolling your own

<!-- Shared with the lab manual; edit shared/coding/prefer-packaged-functions.md, not here. -->
@shared/coding/prefer-packaged-functions.md

## Coding: memoise pure, expensive, repeatedly-called functions

<!-- Not yet shared with the lab manual; edit shared/coding/use-memoisation.md, not here. -->
@shared/coding/use-memoisation.md

## Coding: prefer per-operation grouping over persistent grouping (dplyr)

<!-- Shared with the lab manual; edit shared/coding/per-operation-grouping.md, not here. -->
@shared/coding/per-operation-grouping.md

## Coding: prefer type-stable calls; never `sapply()` outside the console

<!-- Not yet shared with the lab manual; edit shared/coding/type-stable-outputs.md, not here. -->
@shared/coding/type-stable-outputs.md

## Coding: preallocate, `seq_along()`, and `[[i]]` in for loops

<!-- Not yet shared with the lab manual; edit shared/coding/loop-hygiene.md, not here. -->
@shared/coding/loop-hygiene.md

## Coding: restore global state your function changes

<!-- Not yet shared with the lab manual; edit shared/coding/restore-global-state.md, not here. -->
@shared/coding/restore-global-state.md

## Coding: `set -e` is not uniform; tolerate expected non-zero exits explicitly

<!-- Not yet shared with the lab manual; edit shared/coding/errexit-is-not-uniform.md, not here. -->
@shared/coding/errexit-is-not-uniform.md

## Coding: avoid hard-coding data with an external source of truth

<!-- Shared with the lab manual; edit shared/coding/avoid-hardcoding-external-data.md, not here. -->
@shared/coding/avoid-hardcoding-external-data.md

## Coding: make every parameter configurable

<!-- Not yet shared with the lab manual; edit shared/coding/configurable-parameters.md, not here. -->
@shared/coding/configurable-parameters.md

## Coding: write tidy code; prefer tidyverse over base R/rlang for it

<!-- Not yet shared with the lab manual; edit shared/coding/tidy-code.md, not here. -->
@shared/coding/tidy-code.md

Apply this both when writing code and when reviewing it — flag base R or
`{rlang}` verbosity in review the same way `per-operation-grouping` flags a
persistent `group_by()` that `.by` would replace.

## Coding: reuse function documentation and argument lists

<!-- Not yet shared with the lab manual; edit shared/coding/reuse-docs-and-args.md, not here. -->
@shared/coding/reuse-docs-and-args.md

## Coding: one function per file

<!-- Not yet shared with the lab manual; edit shared/coding/one-function-per-file.md, not here. -->
@shared/coding/one-function-per-file.md

Apply this both when writing new code and when reviewing it — a new function
added inline to an existing multi-function file is a review finding, the
same weight as the other modularity checks above.

## Coding: no em-dashes or non-ASCII punctuation in source files

<!-- Not yet shared with the lab manual; edit shared/coding/ascii-punctuation-in-source.md, not here. -->
@shared/coding/ascii-punctuation-in-source.md

## Coding: decompose complex code into functions, not .qmd chunks

<!-- Not yet shared with the lab manual; edit shared/coding/decompose-to-functions.md, not here. -->
@shared/coding/decompose-to-functions.md

## Writing style: plain, direct prose

<!-- Shared with the lab manual; edit shared/writing/plain-prose.md, not here. -->
@shared/writing/plain-prose.md

The `use-preferred-style` skill (alias `style`) spells out the procedure, the PSW chapter links, and a filler/jargon swap table; the `find-ai-tells` skill (alias `ai-tells`) is the scan-after detector counterpart.

## Writing style: semantic line breaks in prose

<!-- Shared with the lab manual; edit shared/writing/semantic-line-breaks.md, not here. -->
@shared/writing/semantic-line-breaks.md

## Quarto: link packages on first mention

**Link packages up front.** Package names in `.qmd` prose take the
`[{pkg}](url)` link form on first mention in a section (e.g.
`[{dplyr}](https://dplyr.tidyverse.org/)`). Add those links as you write the
section — the review bots flag every unlinked package name, one round at a time.

## Quarto: div syntax for figure/table labels and captions

In Quarto `.qmd` files, label and caption figures and tables with **div syntax**, not chunk-option syntax.
Wrap the code chunk in a `::: {#fig-...}` / `::: {#tbl-...}` fenced div and put the caption as the last line before the closing `:::`:

```
::: {#fig-stage-at-dx}

```{r}
#| label: stage-at-dx-fig
#| code-fold: true

plot_stage_at_dx(pt_data)
```

Stage at diagnosis by screening frequency
:::
```

Don't use the chunk options `#| label: fig-...` / `#| fig-cap: "..."` for the cross-reference id and caption.
The div id (`#fig-`/`#tbl-`) carries the cross-reference; the chunk `label` stays a plain code label.
This keeps figures consistent with tables, which already use div syntax.

## Challenge ambiguous phrasing and terminology in review

<!-- Shared with the lab manual; edit shared/workflow/challenge-ambiguous-terminology.md, not here. -->
@shared/workflow/challenge-ambiguous-terminology.md

The `ard`/`ardi` skill family and `use-preferred-style`/`find-ai-tells` operationalize this in their respective review contexts.

## Challenge redundant content in review

<!-- Shared with the lab manual; edit shared/workflow/challenge-redundant-content.md, not here. -->
@shared/workflow/challenge-redundant-content.md

The `ard`/`ardi` skill family and `code-review` apply this in PR/MR review; `find-overlap` (and its `consolidate-skills`/`consolidate-memory` actors) is the corpus-wide counterpart when redundancy spans more than the current diff.

## Writing style: scan for AI tells

The detector counterpart to the plain-prose guide above.

<!-- Shared with the lab manual; edit shared/writing/ai-tells.md, not here. -->
@shared/writing/ai-tells.md

The `find-ai-tells` skill (alias `ai-tells`) runs this same catalog on demand against any target text.

## Writing style: cite sources thoroughly

<!-- Shared with the lab manual; edit shared/writing/citations.md, not here. -->
@shared/writing/citations.md

## Fact-check prose and internal reasoning in review

<!-- Shared with the lab manual; edit shared/writing/fact-check-prose.md, not here. -->
@shared/writing/fact-check-prose.md

When running `code-review` or the `ard`/`ardi` loop on a diff that touches prose, apply this policy in addition to the normal review — those skills don't name it internally, but this CLAUDE.md directive governs regardless.

## Writing style: timestamp factual claims about conditions that can change

The complement to the fact-check above: a claim can be *true* yet still decay
into a confident falsehood if it's stated as timeless present-tense fact when
its truth is time-dependent (a package's CRAN status, a "current" version, a
count). Attach the time the claim was true so a later reader knows to
re-verify it.

@shared/writing/timestamp-volatile-claims.md

## Writing style: math derivations — include every step; flag gaps in review

<!-- Shared with the lab manual; edit shared/writing/math-derivation-steps.md, not here. -->
@shared/writing/math-derivation-steps.md

When running `code-review` or the `ard`/`ardi` loop on a diff that touches
math, apply this in addition to the fact-check above.

## Hyperlink technical terms and results; no forward references

@shared/writing/definition-crossrefs.md

Applies wherever `code-review`/`ard`/`ardi` already reviews a prose diff, alongside the fact-check and ambiguous-terminology checks above.

## Remove forward-pointing phrases from prose, not just crossref divs

The section above covers formal Quarto crossref-div ordering for term/result definitions specifically.
The same problem shows up more broadly as plain-text signposting — "as discussed below", "in the following section", "we'll cover this later" — pointing at content the reader hasn't reached yet, in any prose (not just documents with crossref divs).

@shared/writing/forward-references.md

Unlike `definition-crossrefs.md` above, `forward-references.md` has a dedicated actionable skill: the `fix-forward-references` skill (alias `ffr`) detects these with a grep-for-directional-word heuristic and rearranges (or rewords) the prose to fix them.
Run it — or apply its check inline — wherever `ard`/`ardi` reviews a prose diff, alongside the other prose-review rules in this file.

## Detect concepts defined only in prose, never formalized

`definition-crossrefs.md` above assumes a formal-definition div already exists and checks that mentions link to it in the right order.
A distinct, easy-to-miss gap: a concept stated with full definitional precision --- a bolded name, an equation, an `\eqdef` --- that never became a formal div at all, so it has no stable id and nothing downstream can cite it (or the concept rides along inside a *different* definition's div instead of getting its own).

@shared/writing/informal-definitions.md

Like `forward-references.md`, this has a dedicated actionable skill: `detect-informal-definitions`.
Run it — or apply its check inline — wherever `ard`/`ardi` reviews a diff that introduces new technical content, alongside the other prose-review rules in this file. (Found by hand on `d-morrison/rme#706`: a "conditional predicted risk" quantity introduced only as plain prose right before two definitions that depended on it, and a "collapsibility bias" concept defined in one sentence crammed inside a *different* concept's definition div.)

## Detect hypothetical examples where real data is already available

A worked example can be a perfectly well-formed `{#exm-...}` div and still reach for invented, round-number quantities --- "suppose 20% of the exposed group..." --- when the document already loads a real dataset it uses elsewhere.
That's a distinct gap from the informal-definitions check above: it isn't a missing div, it's a missed chance to ground the illustration in real data that was already available.

@shared/writing/hypothetical-examples.md

This has a dedicated actionable skill: `detect-hypothetical-examples`.
Run it — or apply its check inline — wherever `ard`/`ardi` reviews a diff that introduces or edits a worked example, alongside the other prose-review rules in this file. Fixing isn't mechanical substitution: a real dataset's effect size is often much less dramatic than an invented one, so weigh whether the real numbers still make the teaching point before publishing them. (Found by hand on `d-morrison/rme#706`: a logistic-regression chapter's worked examples used invented covariate-specific risks and made-up exposure proportions throughout, even though the chapter already loads and fits models on its real running WCGS dataset elsewhere.)

## Fact-check code logic and math in review

<!-- Not yet shared with the lab manual; edit shared/coding/fact-check-code-logic.md, not here. -->
@shared/coding/fact-check-code-logic.md

The code counterpart to the prose fact-check above --- catches strategic
mistakes (wrong algorithm or approach), tactical mistakes (wrong
implementation of a right approach), and math/statistics errors (wrong
formula or method, verified against a source), not just prose claims and
derivations.

## A test fixture is not evidence about the system it imitates

The two fact-check rules above assume you can tell a source from a
non-source.
A test fixture defeats that assumption: it lives in the repo, it is named
after real output, and its own comment often vouches for being verbatim ---
so reasoning from its behaviour back to the real system feels like checking
rather than guessing, and the resulting claim arrives dressed as a test
result.

@shared/workflow/fixtures-are-not-evidence.md

Distinct from `ardi`'s fixture bullets, which are about coverage (a fixture
too thin to reach a branch) rather than about the inference drawn from one
that works fine.

## Challenge unnecessary complexity in review

<!-- Shared with the lab manual; edit shared/workflow/challenge-unnecessary-complexity.md, not here. -->
@shared/workflow/challenge-unnecessary-complexity.md

When running `code-review`, `ard`/`ardi`, or any prose review (`use-preferred-style`, `find-ai-tells`, `fact-check-prose`), apply this alongside the normal review — those skills don't name it internally, so this CLAUDE.md directive governs regardless. It's distinct from `simplify` (a dead-code-after-refactor sweep) and `tidy` (a separate on-demand audit).

## Useful prompt formats for coding agents

<!-- Vendored from d-morrison/wai; edit there, not here. See README, "Shared content". -->
@shared/vendored/prompt-formats.md

## Review with Copilot before requesting human review

This is shared lab guidance on getting an automated review before asking a human reviewer.
When *I* iterate a PR, the ARDI loop above is the mechanism — it already addresses whatever the `@claude` or Copilot reviewer flags — so read this as the lab-member-facing statement of the same principle, not a second loop to run.

<!-- Vendored from d-morrison/wai; edit there, not here. See README, "Shared content". -->
@shared/vendored/copilot-review-before-human.md

## Growth mindset: seek resources rather than accept limitations

<!-- Edit shared/workflow/growth-mindset.md, not here. -->
@shared/workflow/growth-mindset.md

## Research before asking a human

<!-- Edit shared/workflow/research-before-asking.md, not here. -->
@shared/workflow/research-before-asking.md

## Encoding reusable feedback into ai-config

When the user gives feedback, corrections, or guidance that applies beyond the current session (a standing rule, style preference, workflow change, or behavioral note), decide on your own how to encode it --- don't ask.
Choose the right form (memory bullet in CLAUDE.md, update to a shared fragment in `shared/`, new or revised skill, etc.) and commit the change.
Only surface the choice if it's ambiguous or touches something architecturally significant.

## PowerShell CLI Command Safety

- **Never pass backtick-containing content in PowerShell double-quoted strings**: PowerShell treats `` ` `` as its escape character — `` `b `` (Backspace, 0x08), `` `n ``, `` `t ``, `` `r ``, etc. — so Markdown code spans and other backtick-containing text will be silently corrupted. Use single-quoted strings (`'...'` / `@'...'@`) for inline content, or write to a file and pass `--body-file` for multi-line PR descriptions.
- **Use body files for GitHub PR descriptions**: Write multi-line PR descriptions to a temp file and pass `--body-file <file>` to `gh pr create`/`gh pr edit`, or `gh api -F body=@<file>` for raw API calls. This avoids terminal string-escaping corruption for any content with backticks or other shell-special characters.
