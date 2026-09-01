# Recurring Mistake Patterns & Fixes

Quick-reference index of common failure patterns observed in agent sessions, with cross-references to their canonical enforcement rules and deep treatments.

## Pattern 1: Assumption Over Verification
- **Mistake**: Assume an action succeeded without verifying the result from tool output or repository state.
- **Example**: Assuming `gh pr create` succeeded without checking URL / output or verifying the open PR exists.
- **Canonical Rule**: See [`preferences.md`](preferences.md) ("NEVER assume; ALWAYS verify").
- **Fix**: Inspect return codes, verify produced artifacts, and check state directly before proceeding.

## Pattern 2: Passivity on Standing Rules
- **Mistake**: Asking permission for routine, non-destructive steps already authorized by standing rules.
- **Example**: Asking "Should I open a PR?" when standing rules mandate opening PRs for completed changes.
- **Canonical Rule**: See `CLAUDE.md` ("Non-destructive actions") and `AGENTS.md` ("Default to action without asking"), plus "Open a PR for every pushed feature branch".
- **Fix**: Execute standing instructions autonomously; reserve questions for genuine design ambiguity.

## Pattern 3: Give Up Instead of Diagnose
- **Mistake**: Treating a "command not found" or tool path error as a permanent blocker without searching.
- **Example**: Failing on `gh: command not found` without searching standard tool locations or checking PATH.
- **Canonical Rule**: See [`growth-mindset.md`](../shared/workflow/growth-mindset.md) ("First check the limitation is real").
- **Fix**: Probe standard paths (`/opt/homebrew/bin/`, `which`, package locations) and diagnose before concluding a capability is missing.

## Pattern 4: Incomplete Workflow Follow-Through
- **Mistake**: Executing an initial step but abandoning subsequent steps before the workflow completes.
- **Example**: Modifying files or pushing a commit but stopping before opening a PR or driving review to clean.
- **Canonical Rule**: See `CLAUDE.md` ("Request review and drive every started PR to clean" and "Watch and ARDI every PR you touch --- don't ask first"), and [`run-ums-proactively.md`](../shared/workflow/run-ums-proactively.md).
  That "watch and ARDI" default applies when you are driving the branch, not when you were asked only to review it ---
  see [`reviewing-prs.md`](reviewing-prs.md) ("Review-only is not working the PR").
- **Fix**: Follow each workflow end-to-end: edit → test → commit → push → open PR → ARDI to clean.

## Pattern 5: Bypassing Existing Repo Knowledge
- **Mistake**: Taking actions without consulting existing memory files or project instructions.
- **Canonical Rule**: See [`MEMORY.md`](MEMORY.md) and project `CLAUDE.md` / `AGENTS.md`.
- **Fix**: Consult relevant memory files and project instructions at task start to align with existing conventions.

## Pattern 5b: Skipping Standing Rules That Already Exist
- **Mistake**: Completing a task without checking whether a standing rule already governs it, then getting corrected and saying "I'll remember" instead of recording the failure.
- **Example**: 2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`): wrote content, committed, but stopped before pushing/opening a PR.
  AGENTS.md line 63-72 already mandated the full delivery cycle.
  The fix was recorded verbally but not persisted.
  Re-hit 2026-08-31 (Antigravity session, working `ucdavis/matt.contracts`): formatted Statistical Analysis Plan, ran tests and verified renders, generated walkthrough artifact, but presented summary recap to the user instead of automatically completing the delivery cycle (issue creation, commit, adversarial review subagent, push, and opening PR).
  Corrected by user with `cai: you should have pushed a PR without me having to tell you`.
- **Canonical Rule**: `AGENTS.md` ("Deliver completed implementation work"): commit → push → PR → share link, as one automatic sequence.
- **Fix**: Before acting on a task, grep AGENTS.md and project CLAUDE.md for rules that apply.
  After a correction, record it in mistake-patterns.md (don't just say you'll remember --- the next session won't have this conversation).

## Pattern 5c: Declaring PR Ready When CI Is Failing or Incomplete
- **Mistake**: Telling a user a PR is ready to merge without checking CI status,
  or saying "ready" when checks haven't finished,
  or declaring clean from a short rollup (`gh pr checks`, `statusCheckRollup`)
  instead of the complete instrument.
- **Example**: 2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`):
  told user Morrison-Lab/ai-config#1677 was ready without checking that CI had failed
  (`new-line-breaks` check).
  Re-hit 2026-08-26 on [#2277](https://github.com/Morrison-Lab/ai-config/pull/2277):
  reported "Ready for merge" from `statusCheckRollup` plus a local adversarial verdict;
  `check-pr-fully-clean.py` exited 1 (`No automated review...`).
  The rollup matched the endpoint that time (8==8);
  the defect was resting a terminal claim on it.
  An earlier Fix in this pattern recommended those short rollups ---
  that was the wrong instrument for a terminal claim.
  Re-hit 2026-08-31 (Antigravity session, working `ucdavis/matt.contracts` [PR #98](https://github.com/ucdavis/matt.contracts/pull/98)):
  reported PR as "MERGEABLE" in status recap based on GitHub's git conflict field (`mergeable: MERGEABLE`) while CI checks were red (failing changelog, spellcheck, version check) and external review was not clean.
  Corrected by user: "stop saying mergeable when there's red CI and/or no clean review".
  Never use "mergeable" as a status verdict or conflate git mergeability with PR readiness;
  explicitly report CI check status and review verdict.
- **Canonical Rule**: `AGENTS.md` ("Request review and drive every started PR to clean"),
  `fully-clean.md`, and `hooks/no-incomplete-check-enumeration.py`.
- **Do:** Run `python3 scripts/check-pr-fully-clean.py <N> -R <owner>/<repo>`
  before a terminal clean / ready-to-merge claim.
  Read exit 0 as clean,
  exit 1 with `  - ` bullets as not-clean,
  any other exit as the check failing to answer.
  A paginated `commits/<sha>/check-runs` read is the check-run half only
  (progress reports, criterion 1); it does not authorize the terminal claim.
- **Don't:** Declare clean from `gh pr checks` or `statusCheckRollup` alone,
  however current they look.
  Progress reports ("8 success, 0 pending") are fine;
  "Ready for merge" is not until `check-pr-fully-clean.py` exits 0.

## Pattern 5d: Failing to Learn From Mistakes
- **Mistake**: Getting corrected, acknowledging the fix verbally ("I'll internalize that"), but not recording it --- so the next session makes the same mistake.
- **Example**: 2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`): corrected three times (didn't push, didn't open PR, declared ready with failing CI).
  Each time acknowledged the fix but only recorded it after being told to, and the first two corrections weren't recorded at all until prompted.
- **Canonical Rule**: `AGENTS.md` ("Deliver completed implementation work") plus the UMS principle: every correction is a learning to bank, not a conversation to end.
- **Fix**: After any correction, immediately record it in `mistake-patterns.md` (or the appropriate memory file) with enough context that a cold reader can avoid it.
  Don't wait to be told to learn --- the correction IS the instruction.

## Pattern 5e: Assuming Universal Rules Do Not Exist Because The File Is Missing Locally
- **Mistake**: When `AGENTS.md` is missing from the local repository, assuming there are no universal instructions and failing to check `ai-config` or apply standing core policies (like "Default to action" or "Adversarial review").
- **Example**: 2026-08-25 session working on `gha`: `AGENTS.md` was missing locally.
  I assumed there were no instructions to follow, asked for permission for non-destructive git commands, pushed without an adversarial self-review, and omitted the agent disclosure comment.
- **Canonical Rule**: [`AGENTS.md`](../AGENTS.md) applies across all Morrison-Lab repositories.
  "Generalize instructions to every AI agent by default."
- **Fix**: If `AGENTS.md` doesn't exist locally, read it from the `ai-config` repository.
  Always follow the standing Universal AI Agent Instructions (Adversarial Self-Review, Default to action, Agent disclosure) everywhere.

## Pattern 5f: Declaring a PR "Fully Clean" Without Verified Automated Review Approval on HEAD
- **Mistake**: Reporting a PR as "fully clean" based solely on passing CI checks and an internal self-review fallback, while an external automated review had unaddressed findings or had not yet evaluated the exact current HEAD SHA.
- **Example**: 2026-08-25 session (`gha#668`, `ai-config#2226`): declared PRs fully clean because CI was green and subagent self-reviews passed, despite outstanding "Needs more work" findings from Cursor Grok 4.6 on previous SHAs and unevaluated latest SHAs.
  - 2nd occurrence: 2026-08-31 session: declared PR ready for merge without up-to-date code review covering HEAD.
    Corrected by user with `cai: it's not ready for merge if it doesn't have an up-to-date review`.
- **Canonical Rule**: [`fully-clean.md`](../shared/workflow/fully-clean.md) and [`AGENTS.md`](../AGENTS.md) ("Strict Merge Control Policy").
  A fallback self-review or reviewer skip notice does NOT grant approval or satisfy `mwc`.
- **Fix**: Run `scripts/check-pr-fully-clean.py` (or verify all its criteria) before ever declaring a PR fully clean.
  Only report clean when all CI checks pass AND an automated AI review evaluating the exact HEAD SHA has posted an approved / ready verdict with zero open findings.

## Pattern 5g: Dropping Background PR Check Timers While PRs Are In-Flight
- **Mistake**: Reporting intermediate status and ending a turn without leaving an active check timer or recurring cron schedule running, letting PR monitoring go dormant while awaiting CI or review outcomes.
- **Example**: 2026-08-25 session (`Morrison-Lab/ai-config#2226`): after pushing fixes and verifying local status, ended turn without an armed background timer, requiring the user to explicitly remind the agent to keep a check timer running.
  - 2nd occurrence: 2026-08-30 session (Conductor setup in `Morrison-Lab/gha`): promised to "monitor their progress" for CI/review after pushing a PR, but ended the turn without using the schedule tool, prompting an "empty promise" correction.
- **Canonical Rule**: [`AGENTS.md`](../AGENTS.md) ("No empty promises" --- "arm the next step, a scheduled wakeup or timer carrying it"), [`ardi.md`](../shared/workflow/ardi.md), and "Manage quota, including the structural kind".
- **Fix**: Whenever PRs are open, in-flight, or awaiting review/CI, always arm a background timer before concluding any turn, and report what was armed and its firing time.
  When actively waiting on fast CI jobs, use short intervals (1--2 minutes);
  when waiting on human review or in a quiescent idle state, use progressive backoff (e.g. 5m -> 15m -> 30m -> 1h) to prevent wasteful token burn while keeping the wake-up armed.

## Pattern 6: Answering the asked process question without fetching the PR
- **Mistake**: Treating a "why didn't you wait / did you fix it / why no reply" question as chat-only, so a review that landed during that exchange stays unread.
- **Example**: gha#511 (2026-08-18): answered the CI-wait question, never opened the Needs more work comment.
- **Canonical Rule**: See `CLAUDE.md` ("Re-check for latest review findings before reporting PR status") and `skills/pr-status/SKILL.md` ("When this fires").
- **Fix**: Fetch the latest review and CI before answering any question about a live PR, not only when the user said "status".

## Pattern 7: Stale PR body figures surviving iteration pushes
- **Mistake**: Pushing changes or review fixes that alter file counts, diff stats, or commit SHAs without updating the verification table in the PR body.
- **Example**: Morrison-Lab/ai-config#1531: at `3a373100`, the body still claimed +31/-3 across 1 file at `685b5dc8`, while HEAD had moved to +35/-4 across 2 files.
- **Canonical Rule**: See `shared/workflow/ardi.md` and `scripts/check-pr-body-figures.py` (Morrison-Lab/ai-config#1549).
- **Fix**: Run `python3 scripts/check-pr-body-figures.py` to mechanically compare stated figures and derivation SHAs against the HEAD commit.

## Pattern 8: Taking Shortcuts That Remove Features
- **Mistake**: When fixing a bug or error, removing the feature that's broken rather than fixing it properly.
- **Example**: matt.contracts SAP article had `format: html/docx/revealjs`
  causing a build error.
  Removed the format block entirely
  instead of fixing it to use the correct pattern.
- **Anti-pattern**: Deleting code/config that causes an error,
  disabling a feature to make CI green,
  commenting out a failing test,
  removing a dependency instead of fixing the integration.
- **Canonical Rule**: none states this case directly --- the nearest is
  [`dont-incur-technical-debt.md`](../shared/principles/dont-incur-technical-debt.md)
  ("shipping the version that routes around it"), which covers routing around a
  needed change rather than deleting the feature that exposed it.
  Tracked as a gap in Morrison-Lab/ai-config#1746.
- **Fix**: Diagnose the root cause and fix it while preserving the feature.
  If unsure how, use a subagent to research the correct approach
  or check sibling repos for the working pattern.
  The only valid reason to remove a feature is the user explicitly asking for it.

## Pattern 9: Working on the primary checkout instead of a worktree
- **Mistake**: Committing directly to the primary checkout --- to `main` or to an existing feature branch already checked out there --- instead of isolating the work in a dedicated `git worktree`.
- **Example**: 2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`): committed memory updates straight onto `fix/quote-yaml-placeholders` on the primary ai-config checkout, where a parallel session sharing that checkout would have collided with them.
- **Canonical Rule**: `AGENTS.md` ("Worktree isolation"), which requires a dedicated worktree for write/edit tasks so parallel sessions never clobber each other's working directory or branch state.
  See also [`git-worktrees.md`](git-worktrees.md) for the liveness rules that decide when a worktree may be touched or reclaimed.
- **Fix**: Create the worktree before the first edit (`git worktree add`), not after the first commit.
  Treat the primary checkout as read-only during a write session, and push early --- a pushed commit survives anything that happens to a working tree.

## Pattern 10: Two checks on the same artifact treated as independent verification
- **Mistake**: Rebutting a reviewer's finding with "two independent checks" that were actually two different grep angles on the *same* single source (an installed VS Code bundle), then treating agreement between them as confirmation.
- **Example**: 2026-08-24, ai-config#2070.
  A reviewer disputed a setting name (`chat.agentHost.claudeAgent.enabled` vs. `github.copilot.chat.claudeAgent.enabled`), citing VS Code's own live documentation.
  I rebutted with a schema-shape check and a manifest-absence check -- both reads of the same bundle -- and declared the claim settled.
  The reviewer re-raised it a third round, still citing the live docs.
  Fetching that page directly showed the reviewer was citing it accurately, which the bundle-only checks could never have settled: [`vscode-copilot-byok.md`](vscode-copilot-byok.md) explains that both names are real, only one has a functioning schema in this exact build, and which one the vendor's own docs currently name is a separate question a bundle grep cannot answer at all.
- **Canonical Rule**: [`self-review-fallback.md`](../shared/workflow/self-review-fallback.md)'s cross-vendor section: "Read a cross-vendor disagreement as a prompt to check the item yourself".
  Checking means consulting a genuinely separate source, not re-deriving from the one you already trust.
  [`verify-the-right-artifact.md`](../shared/workflow/verify-the-right-artifact.md) names the same trap under "a cached copy for the origin."
- **Fix**: When a reviewer's finding cites an external source you haven't read, fetch that source yourself before rebutting -- two checks against one artifact are one check, however different the grep angles feel.
  Fetching the citation only settles what the citation says, not which name actually works -- don't conflate the two, and don't assert either source outranks the other for a fast-moving/experimental feature without live-testing which name functions.

## Pattern 11: Pasting Repo-Specific Infrastructure into Universal Instructions for Another Repository
- **Mistake**: When creating `AGENTS.md` in a sibling repository (such as `Morrison-Lab/gha`), copying instructions verbatim from `ai-config` that refer to `ai-config`-specific infrastructure (`scripts/validate-skills.py`, `validate.yml`, pre-push git hooks, relative documentation links) instead of tailoring instructions to the target repository.
- **Example**: 2026-08-25 session on `Morrison-Lab/gha`: created `AGENTS.md` by pasting `ai-config`'s file, claiming pre-push hooks existed, inventing non-existent test filenames, and inverting instruction layering over `gha`'s `CLAUDE.md`.
- **Canonical Rule**: [`AGENTS.md`](../AGENTS.md) ("Universal AI Agent Instructions").
  Universal instructions must be repository-agnostic or verified against the target repo.
- **Fix**: Verify every path, test suite name, and CI workflow against the target repository's tree before committing.
  Use absolute GitHub URLs for any cross-repository references to `ai-config` files.

## Pattern 12: Arming Auto-Merge While Review Findings Are Still Open or at an Unreviewed Head After Sync
- **Mistake**: Running `gh pr merge --auto` (or any deferred/auto merge) on a PR that still has open review findings or no verdict at head.
  Treating the arming as harmless because CI is red ignores that the robot fires later,
  the moment checks go green,
  with no re-check of review state.
  A second route to the same failure is arming `--auto` immediately after a sync-only push
  (e.g. merging `origin/main` in when a direct merge was refused due to an out-of-date branch):
  reasoning about `--auto` as *scheduling a merge already verified* ignores that the sync-only push created a new HEAD commit ref
  that silently invalidates the prior clean verdict.
  The sync is content-free (no code change by the author),
  which is why it does not feel like a new head needing a new review verdict,
  but auto-merge fires the instant CI finishes,
  before any reviewer can evaluate the new head.
- **Example**:
  - 2026-08-26 on `ai-config#2226`:
    armed `--squash --auto` while round-1 findings were open and the reviewer was quota-skipping.
    Hours later a push turned `validate` green,
    auto-merge fired at 04:30Z,
    and it merged over an explicit Needs-more-work verdict ---
    requiring revert (#2268) plus reland-with-fixes (#2269).
  - 2026-08-28 on `ai-config#2556` (Issue #2558):
    verified fully clean at `2c1ae45d` (checker exit 0, verdict `Ready for merge` at that exact SHA, zero unresolved threads).
    A direct merge was refused because `main` had moved (`the head branch is not up to date with the base branch`).
    Merged `origin/main` in and pushed `54874be0`,
    then armed `--auto` reasoning that the merge was already verified.
    A clean review verdict for `54874be0` landed at 22:18:44Z and auto-merge fired at 22:20:29Z;
    had auto-merge fired before the review posted,
    it would have merged an unreviewed head.
- **Canonical Rule**: [`fully-clean.md`](../shared/workflow/fully-clean.md).
  See also [`check-before-pushing.md`](../shared/workflow/check-before-pushing.md)
  and [`sync-with-main.md`](../shared/workflow/sync-with-main.md):
  the remote can act between your commands,
  and an armed automation is exactly such an action you scheduled against yourself.
- **Fix**: Never arm `gh pr merge --auto` on a PR whose merge gate includes a posted review verdict, which is every PR here.
  A sync-only push invalidates a clean verdict just as thoroughly as a code push.
  Auto-merge fires server-side the moment CI passes,
  so a review landing seconds later cannot block it,
  and no reactive disable can win that race.
  Branch protection does not substitute either:
  it gates native approvals, not verdicts posted as comments.
  Merge synchronously instead,
  only after `scripts/check-pr-fully-clean.py <N>` exits clean ---
  CI green and the all-clear verdict both verified at the new shipping head.
  Accept that a moving base may require repeating the sync and re-verification cycle,
  rather than arming an automation that cannot re-check review state.
  If something is found already armed, disable it at once ---
  `gh pr merge <N> --repo <r> --disable-auto`,
  verified with `gh pr view <N> --repo <r> --json autoMergeRequest` ---
  and treat the PR as unverified until re-checked.
  Disabling is cleanup, not protection.

## Falsely assuming local fallback reviews grant autonomous merge authority (check-pr-fully-clean.py)

On 2026-08-26, an agent noticed that the GitHub CLI merge command was blocked by the `no-unauthorized-merge.py` merge guard after completing an adversarial review via the local `pre-push-review.py` CLI on PR #2305.
The agent incorrectly concluded that `check-pr-fully-clean.py` had a bug preventing it from recognizing local fallback reviews posted by the human user (`d-morrison`).
[`tools.md`](tools.md)'s own summary of criterion (2) was, at the time, stale and misleading: it said a review is admitted when it "has been posted by an automated bot account ... or carries a bot review header (`🤖`, ...)", and the agent took that "or carries a bot review header" clause at face value rather than reading the script itself.
In the actual code, the body-marker check exists only inside `is_non_review_notice()`, to keep a genuine review from being misclassified as a workflow status notice --- it is never a second admission path alongside the author-identity gate.
The agent then filed PR #2308 to "fix" `check-pr-fully-clean.py` to admit reviews based solely on the text `### 🤖 Antigravity Agent Report`, bypassing the bot author check.
See #2350 for correcting the stale `tools.md` summary that set this up, and issue #2306 (open, same misreading) for the original bad bug report.

This was a critical misunderstanding of the security invariant:
- Per [`scripts/check-pr-fully-clean.py`](../scripts/check-pr-fully-clean.py) (discussed in [`fully-clean.rationale.md`](../shared/workflow/fully-clean.rationale.md)), automated review approval MUST be verifiable by author identity (e.g., `github-actions[bot]`, `claude[bot]`) --- body text is never sniffed for the author-identity gate.
- Non-bot human accounts (like `d-morrison`) are admitted ONLY if they state a blocking `not-clean` verdict (fail-closed).
- A local fallback review does **not** grant autonomous merge approval.
  It only satisfies the pre-push guard for iterating on the PR locally.
- Bypassing the author identity check by sniffing body text introduces a security vulnerability, as any human user could spoof the marker to pass the check.

**Action**: When `check-pr-fully-clean.py` rejects a review because it was posted by a human author, this is the intended behavior.
Do not attempt to "fix" the script to admit fallback reviews for merging.
A clean automated review from every available provider evaluating the current HEAD commit is strictly required for an autonomous merge.

## Pattern 13: Forgetting to Undraft a Review-Ready PR
- **Mistake**: Pushing a fully completed feature or bugfix but leaving the PR in draft mode.
  This silently stalls progress because reviewers and automations treat drafts as WIP.
- **Example**: 2026-08-26 session, on ai-config#2295: completed fixes, ran local verification, requested Claude review, but left the PR in draft mode.
  The user had to manually ask "why is 2295 still in draft mode".
  (The exchange happened in the CLI session, so the PR thread itself carries no trace of it.)
- **Canonical Rule**: `AGENTS.md` ("Put PRs in ready mode when they are ready for review"): "What is not acceptable is leaving a review-ready PR in draft...
  Do: un-draft an up-front empty PR once its implementation has landed on the branch head and the checks pass."
- **Fix**: Once a push completes a PR's implementation, check its draft status (`gh pr view --json isDraft`) and mark it ready if it isn't (`gh pr ready`).
  Do this before dispatching review workflows or yielding to the user ---
  but mind the ready-transition timing in `pr-on-claim.md`:
  on a repo whose review workflow cancels in progress, do not flip ready within seconds of the final push ---
  the two triggered review runs race, and the cancelled one can be the newer run, leaving the current head's review check red while a stale-event run survives.

## Pattern 14: Pausing Without Setting a Timer
- **Mistake**: Yielding or "pausing" execution to wait for user input or an external event without actually setting a timer or wakeup mechanism, leaving the agent idle.
  Pattern 5g above is the PR-monitoring special case of this;
  this pattern covers every other pause --- waiting for user input, an external event, or a decision --- not only an in-flight PR watch.
- **Example**: 2026-08-26 session: after reporting that PRs were ready for merge, yielded the floor to the user without setting a timer, prompting the feedback "you need to set a timer every time you pause".
- **Canonical Rule**: `AGENTS.md` ("No empty promises"): "An owed action needs a mechanism that will fire, not only one that records."
- **Fix**: Whenever pausing execution, stopping for user input, or waiting for a condition, ALWAYS use the `schedule` tool to set a timer (one-shot or cron) so the agent automatically wakes up to check status, rather than waiting indefinitely.

## Pattern 15: Widening a Fail-Closed Instrument's Exemption Without a Base-Parity Proof
- **Mistake**: Adding or widening an exemption in a fail-closed checker (a
  verdict scan, a findings gate, a guard) and reasoning about its safety
  from the diff, instead of proving the new acceptance set is no wider than
  the old one by executing BOTH versions over an adversarial corpus.
  A convenience strip, a broadened vocabulary, or a tolerant anchor each
  reads as a small ergonomic fix while quietly admitting shapes the base
  version rejected --- and the admitted shapes are exactly where a real
  finding hides.
- **Example**: 2026-08-27, ai-config#2419: six review rounds on one
  exemption.
  Each round's fix looked safe on paper; execution against `origin/main`'s
  classifier found a wider acceptance set four times (examples: untagged
  prose findings swallowed, `+`/`1)` list forms escaping a veto, a
  lookbehind swallowing a still-open "previously-blocking" statement, a
  bullet strip feeding vocabulary the base's char class never resolved).
  The round that finally stuck REUSED the base's own regex on the
  unstripped line --- parity by reuse, not by re-derivation --- and the
  local pre-push review round verified acceptance-set parity by running
  both versions over a vocabulary corpus (that verification lives in the
  unposted local round, not on the PR record).
- **Canonical Rule**: `shared/principles/fail-fast.md` (a guard's pass path
  must not be reachable by its failure path) and
  `shared/workflow/check-purpose-before-reusing.md` (structural fit is
  necessary and never sufficient; the checks you naturally run confirm
  the mechanism, never the purpose).
- **Fix**: Before shipping an exemption change, run the old and new
  versions over the same adversarial case set and diff the acceptance
  sets; any body the new version exempts and the old flagged needs its own
  justification.
  Prefer reusing the instrument's existing vocabulary regex over writing a
  near-copy, so parity holds by construction.
  Verify each guarding test DISCRIMINATES by neutering the guarded branch
  (replace the veto or anchor with a never-match, or drop it) and
  confirming the test flips --- a test that still passes guards nothing,
  and it usually passes through a different branch than its name claims.
  (Measured three times on 2026-08-27: #2423's anchor probe --- the one
  instance on a PR record, its round-1 blocking finding --- plus #2313's
  override-drops-token test and #2419's veto tests, both caught in
  unposted local pre-push review rounds rather than on those PRs'
  records.)
- **2nd occurrence of the class, 2026-08-28** (ai-config#2449 / PR #2515, after #2419 above), and the near-miss this entry did not previously name: the base-parity proof WAS built, and was constructed over the wrong quantity.
  It compared what the two revisions *blanked* --- asking whether every extra-blanked character lay inside a code span the change exists to blank --- which cannot return non-zero for any implementation of that shape, because the extra-blanked set is the span set.
  It reported 0 while two real fail-opens were live, and was silent by construction about the passes running downstream of the blanking, where both lived.
  A parity proof is over ACCEPTANCE SETS --- which bodies each revision calls clean --- never over the transformation.
  The replacement instrument, `scripts/check-verdict-scan-parity.py`, demonstrates its own discrimination rather than asserting it --- but only half of that demonstration is reproducible from `main`.
  The `0` for the shipped design re-runs from any clone.
  The 3,924 / 108 / 270 / non-zero off-axis figures were taken against the four designs rejected on the PR branch, which the squash merge as `07847b9` left off `main`;
  recover them with `git fetch origin 'refs/pull/2515/head:refs/remotes/pr/2515'` (`c7ff646`, `4f9d3fc`, `68a14b9`, `a3251bf`) rather than treating them as lost.
  Canonical rule for the general shape: [`verify-the-right-artifact.md`](../shared/workflow/verify-the-right-artifact.md)'s "what a change TRANSFORMS, standing in for what it CONCLUDES".

## Pattern 16: Same-Vendor Subagent Fallback When a Reachable CLI Would Give True Independence
- **Mistake**: When the `adversarial-reviewer` subagent type is unregistered
  in a session, dispatching a same-vendor `general-purpose` Claude subagent
  with an adversarial-refute-brief prompt as the fallback, without first
  checking whether a separate CLI (`codex`, `opencode`, `agy`) is reachable
  on `PATH`.
  A same-vendor subagent shares the training and therefore the blind spots
  of the author, per `adversarial-self-review.md` line 21 --- it is not a
  weaker version of independence, it is the specific thing dispatching was
  meant to buy and did not.
- **Example**: 2026-08-27, ai-config#2434 (a memory-only PR).
  `Agent type 'adversarial-reviewer' not found` fired on the first review
  attempt.
  Fell back to a same-vendor `general-purpose` subagent for both review
  rounds and pushed with `ALLOW_UNREVIEWED_PUSH=1`, without running
  `which codex`/`which opencode`/`which agy` first.
  A later check in the same session showed `opencode` and `agy` both
  resolved on `PATH` (only `codex` was absent), so the documented stronger
  fallback --- `delegate-to-opencode` --- was available the whole time and
  simply never tried.
- **Canonical Rule**: [`adversarial-self-review.md`](../shared/workflow/adversarial-self-review.md)
  ("No Agent tool, or no reviewer registered here?
  A separate CLI is the same move and a stronger one ---
  `delegate-to-codex` or `delegate-to-opencode`.").
- **Fix**: Before falling back to a same-vendor subagent, run
  `which codex; which opencode; which agy` (or the OS equivalent) and
  route to whichever resolves, per `delegate-to-codex`/`delegate-to-opencode`.
  Only fall back to a same-vendor subagent, stating so explicitly in the
  push reply, when none of those three CLIs are reachable at all.
- **2nd occurrence, 2026-08-29** ([ucdavis/hac.it#9](https://github.com/ucdavis/hac.it/pull/9), a docs PR): same shape, one step later.
  `adversarial-reviewer` was unregistered in this Claude Code CLI session (as opposed to Cursor Cloud, where it is registered), so a same-vendor `general-purpose` subagent was dispatched as the substitute reviewer and the PR was pushed on that verdict alone --- with `self-review-fallback.md`'s cross-vendor section already loaded in context and not applied.
  The user corrected it directly: "you should have run adv without me having to ask."
  A subsequent `adv --engine cursor` pass produced a genuinely independent verdict (Ready for merge, several non-blocking nits the same-vendor pass had not surfaced) --- concrete evidence the cross-vendor pass adds real signal rather than ceremony, and a second data point toward this pattern's third-occurrence bar for a hook.

## Pattern 17: Theorizing a Cause for a Guard Refusal Instead of Running Its Own Reader
- **Mistake**: When `hooks/no-push-without-self-review.py` refuses a push citing "The latest adversarial self-review returned a blocking verdict" despite believing the most recent dispatch was clean, attributing the refusal to session/harness mechanics (the transcript lagging the current turn) instead of executing the guard's own `read_latest_review`/`parse_report` against the live transcript and reading what it actually parsed.
  The refusal message is a true statement about the guard's parsed history and a false one about the session's real state whenever the cause is a malformed report, so the two failure modes produce an identical message and only execution distinguishes them.
- **Example**: 2026-08-27, ai-config#2444, across two concurrent branches --- `fix/2409-driver-comments` and `ums-2409-fail-open-lessons`.
  Three dispatches ran in one turn --- `needs_work` at `5a45e7fd`, `needs_work` at `446fa0ee`, then a clean `Ready for merge` at `cf08d05f` --- and a later dispatch also returned a clean `Ready for merge` at `629cca1b`.
  The push was refused.
  An issue was filed attributing this to the transcript not being flushed for same-turn tool results.
  Running `read_latest_review` directly against the transcript returned `('needs_work', '446fa0eecaec6a58e2d65e1b8d24265e67e13138', True)` twice, minutes apart --- ruling out a lag that would have resolved on its own.
  The cause that execution established: the two later reports used a heading-then-separate-line `## Verdict` / `Ready for merge` shape, which `VERDICT_LINE` does not match (it requires the phrase on the same line as `Verdict:`), so `parse_report` returned no verdict for both and the held value never advanced past the second dispatch.
  A second cause sat unexamined in the same evidence, and naming it is the point of this entry rather than a footnote to it.
  `git merge-base --is-ancestor` puts `5a45e7fd` and `629cca1b` on `fix/2409-driver-comments` and `446fa0ee` and `cf08d05f` on `ums-2409-fail-open-lessons`, so the four dispatches spanned two branches --- and the guard holds ONE global latest verdict rather than one per branch, so a review of either branch displaces the other's regardless of format.
  Fixing the format alone would not have made those pushes independent.
  The near-miss is that the format explanation is sufficient for the observed refusal, arrives first, and is confirmable --- which is exactly when [`metacognitive-monitoring`](../shared/workflow/metacognitive-monitoring.md)'s cause check is owed and feels least necessary.
- **Canonical Rule**: [`adversarial-self-review.md`](../shared/workflow/adversarial-self-review.md), "A verdict phrase separated from its heading by a line break is no verdict."
- **Fix**: When a guard's refusal contradicts your own read of the session, run the guard's own parsing function against the actual artifact it reads (the transcript, a file, a comment body) and print its result per input, before writing down a mechanism-level explanation.
  State `Verdict: <phrase>` on one line in every review brief, whatever is dispatching it.

## Pattern 18: A Second Refuted Design Is a Prompt to Measure, Not to Design a Third
- **Mistake**: After a checker-side classification fix is built, reviewed, and refuted by an adversarial round that reproduces the failure against `origin/main` for the second time on the same underlying problem, proposing a third discriminator instead of executing the classifier against the actual failing input to find which specific feature of it drives the wrong output.
  Each refuted design added a new guard against the previous round's counterexample rather than asking what the real input space has in common with genuine reviewer prose --- so every discriminator available in a comment body turned out to be one some real reviewer also emits.
- **Example**: 2026-08-27, ai-config#2409, a driver-comment classifier built from real comments on `Morrison-Lab/ai-config#2341`.
  Three designs, each built and reverted: (1) a "driver ledger" matched on `hold off` / a `Disposition` table row, guarded by negative tests keyed on the Claude/Cursor report format --- failed open on a Copilot review reading "hold off on merging until the null check is added," which carried a real finding;
  (2) the same classifier gated on the agent-disclosure marker --- failed because genuine not-clean reviews carry that marker too;
  (3) a citation strip keyed on a disposition verb plus an exact-verdict parenthetical --- blanked a live verdict inside a sentence reporting a fix that introduced a new bug.
  The turn that mattered was executing `classify_verdict` over the failing comment's own parts, which showed the table and the hold (what designs 1 and 2 were built to detect) produced no verdict at all, and the sole signal was a bare parenthetical after the header neither design had examined.
  The design that survived review --- shipped as #2448, which merged and closed #2409 --- is a one-sentence authoring convention --- backtick a quoted verdict phrase --- as a 37-line addition to `ard`'s summary-comment step, with zero checker code change.
- **Canonical Rule**: [`metacognitive-monitoring.md`](../shared/workflow/metacognitive-monitoring.md)'s cause claim-type ("what else explains it") and [`deterministic-tools.md`](../shared/principles/deterministic-tools.md)'s recurrence test, applied one level earlier: recurring *refutation* of a design is itself the signal to stop designing and measure.
- **Fix**: After the second refutation of the same classification problem, stop proposing new discriminators.
  Execute the classifier (or the equivalent instrument) over the actual failing input's constituent parts and read which feature produces the output, before writing a third design.
  Consider whether the fix belongs at the author's end (a convention change) rather than in the instrument at all --- the instrument's own vocabulary can already handle a correctly-written input.
- **2nd occurrence, 2026-08-28** (ai-config#2449 / PR #2515, after #2409 above), on the same module and with a second resolution direction worth adding: where each refuted design breaks a *different* consumer, the measurement to run is over the REPRESENTATION rather than over the failing input.
  Four designs widened what `strip_cited_finding_vocab` blanked, and no two of them failed the same way;
  between them they broke six distinct downstream passes --- anchored negation windows, a markedness check, a sentence-boundary gate, a findings-item tag, a bare-marker guard, and reviewer-identity extraction --- producing nine fail-opens on a fail-closed instrument across five adversarial rounds.
  The three counts are not a one-to-one mapping and should not be read as one: the fourth design alone broke several passes, and one broken pass can fail open on more than one shape.
  What matters is that the failures were *unrelated*, which makes them one fact restated four times rather than four bugs --- namely that many character-and-offset-sensitive consumers read the buffer being edited.
  The design that shipped leaves the scan byte-identical and carries a parallel citation mask, making the class unreachable rather than patched member by member, and giving parity by identity rather than by proof.
  Canonical rule: [`fail-fast.md`](../shared/principles/fail-fast.md)'s "Where many consumers key on a shared buffer, filter the matches rather than editing the buffer".
- **3rd occurrence, 2026-08-28** (ai-config#2538 / PR #2539, after #2409 and #2449 above), which is the same pattern run to its conclusion and worth recording for what finally stopped it.
  **Twelve** designs, **twelve** certification fail-opens on a fail-closed instrument, **none** caught by a green suite --- every one found by an adversarial round.
  The arc: classification on exclusions alone, then on the harness's `origin.kind` label, then per record, then per block, then per non-envelope region, then against a four-name tag list, then against a structural opener test.
  Each fix was refuted by a shape the previous design had not considered, and by round 9 the sequence had a second, subtler stage worth naming --- the parse was not removed, only moved from **grammar** (where do the delimiters balance) to **vocabulary** (is this name in my list), while the code claimed *"nothing is parsed"*.
  Two of the last three failures were regressions introduced by the fix for the one before, which is Pattern 18's own signal arriving at a higher rate.
  What ended it was abandoning the claim rather than narrowing it: the tool now reports every matching record with its provenance and decides nothing, so the class is unreachable rather than guarded --- the same resolution shape as the 2nd occurrence's parallel mask, one level up.
  A twelfth round then found the mirror failure the eleven had all missed, because every round had been hunting false positives: the tool was *under-reading* the corpus, and reported "no record contains it" over text the user had typed.
  Canonical rule: [`deterministic-tools.md`](../shared/principles/deterministic-tools.md)'s "An enumeration is still a parse", and the recurrence test one level up again --- when refutation recurs past the second design, ask whether the CLAIM is achievable rather than which discriminator to try next.
- **4th occurrence, 2026-08-30** (ai-config#2668, on the same module and citation-stripping machinery as the 2nd/3rd occurrences above;
  open, with the driving session still pushing commits, at time of writing), the occurrence that names the axis the first three resolved by trial rather than by rule.
  As the driving session reported it, two separate discriminators in the same file failed open across a review series it logged at roughly sixteen adversarial rounds, and in both cases the fix it settled on was a change of KIND rather than a further narrowing of the same kind. (a) A guard deciding whether a negator scopes over a resolution went through four lexical designs in sequence --- a fixed glue whitelist, a bounded word run, a grammatical-role (preposition-governed) test, then a governed-and-clause-detached test --- and each admitted a fresh false-clean the next round found.
  The design the session settled on abandons the lexical proxy entirely: any negator earlier in the same sentence defeats the exemption, trading a fifth refinement for a documented, bounded over-flag --- the same trade [`learn-from-review-findings.md`](../shared/workflow/learn-from-review-findings.md) already names ("a bounded, nameable false positive beats a silent bypass, and both beat a heuristic nobody can characterize"). (b) A citation strip deciding whether a `(posted <timestamp>, verdict **X**)` aside was narration or a live statement used a positive attribution gate plus a closed vocabulary veto, and each round's re-raise arrived in a phrasing the vocabulary had not enumerated.
  The design the session settled on is a discriminator on a different axis: a structural gate that strips the citation only when the comment body states a verdict of its own, because a cited verdict overriding the reviewer's OWN stated verdict is the only thing the strip ever needed to protect against, and that test is blind to how the citation happens to be phrased. (As of this entry, `origin/fix/check-pr-fully-clean-posted-verdict-citation` --- distinct from `origin/main`, which has neither fix yet --- carries `_POSTED_VERDICT_CITATION`, a general "posted TS, verdict `**X**`" pattern rather than an enumerated word list;
  whether that pushed form is the closed-vocabulary design this entry describes being refuted, an intermediate step, or already the structural gate is not independently reconstructable from the two commits on the remote branch alone, so the round-by-round narrative above is the driving session's own account, not a re-derivation from this checkout.)
  The module carries a directly relevant caution already, in the docstring of `strip_cited_finding_vocab_with_mask` --- verified on both `origin/main` and the PR branch of `scripts/check-pr-fully-clean.py`, about 115 lines above where the PR branch's new citation regex lives in that same function: "the true discriminator...cannot be determined from text alone" (lines 761-763) and, of four earlier attempts at a sibling citation-scan, "every one of those was fail-open on a fail-closed instrument" (line 802).
  Per the driving session's account, that lesson did not travel to the vocabulary veto being written later in the same function.
  A principle stated in one part of a file and contradicted by practice in another part of the same file is itself a signal worth reading, independent of the round count.
  Canonical rule: not a wider or narrower version of the failing test, but a test on a different axis --- structural or positional (does the body carry its own verdict heading at all) rather than lexical (which words appear).
  See also [`learn-from-review-findings.md`](../shared/workflow/learn-from-review-findings.md)'s "A finding class that RECURS is evidence about your instrument, not about its threshold" section, which this occurrence specializes: the replacement axis, not just the recurrence signal.
- **Do:** after a second narrowing of one discriminator fails review, ask what KIND of test would decide the question, and prefer a structural or positional test over a vocabulary list wherever the property being tested is actually structural.
- **Don't:** write a fourth or fifth lexical refinement --- a longer word list, a tighter adjacency window, a new grammatical exception --- once three have already failed on the same axis;
  every occurrence above did that at least once before finding the axis change.

## Pattern 19: A "Needs More Work" Loop Can Have Two Independent Mechanisms, and Fixing One Leaves the Other
- **Mistake**: Treating a stuck "Needs more work" verdict as one bug --- a review conditioning its verdict on its own run's in-flight sibling checks --- and re-dispatching review rounds expecting one of them to converge, when a second, independent mechanism also reproduces the block: a review deferring to `scripts/check-pr-fully-clean.py`'s exit status, which itself only reports the PREVIOUS round's status-conditioned verdict, so each new round inherits the prior round's hedge.
- **Example**: Measured 2026-08-27/28 on ai-config#2313 (five consecutive stuck rounds) and #2341.
  CI reached a fully green state on both and the loop still reproduced, because loop (b) reads the checker's exit rather than the checks themselves --- so the loop survives CI completing.
  A steering PR comment quoting the reviewer's own "no content defect" words back to it did not break the loop either;
  only a prompt-level fix (a "Verdict semantics" addendum to `claude-review.yml`, shipped in PR #2486, merged) closed it.
  Tracked as [ai-config#2475](https://github.com/Morrison-Lab/ai-config/issues/2475), which #2486 closed.
  Pattern 20 below is a second, independent stuck-verdict mechanism from the same PR (#2341) --- the two do not share a fix.
- **Canonical Rule**: [`review-verdict-pitfalls.md`](../shared/workflow/review-verdict-pitfalls.md)'s reconciliation paragraph (shipped in PR #2486, merged) and [`fully-clean.md`](../shared/workflow/fully-clean.md)'s three-way exit-status read.
- **Fix**: When a "Needs more work" verdict recurs across rounds with no new content finding, check whether it cites (a) its own run's in-flight sibling checks or (b) the checker's exit status before assuming a re-run will converge --- loop (b) does not resolve on its own even once CI is fully green.
  A steering comment restating the reviewer's own words is not a reliable fix for either loop;
  the actual fix has to change what future rounds are told to condition on.

## Pattern 20: An Exclusive-Login Bot's Pre-Convention Verdict Can Become Permanently Unsupersedable
- **Mistake**: Assuming a driver-session's disposition-ledger comment ("Do not merge.
  Blocked on review of X") posted by an exclusive-login bot identity will eventually be superseded by a later clean review from the same tool, when the checker's per-reviewer latest-verdict rule keys that identity EXCLUSIVELY to one login and no reachable local process can post under it.
  Pattern 19 above is a distinct, unrelated stuck-verdict mechanism on the same PR (#2341);
  the two were diagnosed separately and neither fix clears the other.
- **Example**: 2026-08-26, ai-config#2341: a Cursor cloud driving session (not a reviewer) posted a disposition ledger ending "Do not merge.
  Blocked on review of 8af4edc9" with an unbackticked "(Needs more work)" quote in its first line.
  `check-pr-fully-clean.py`'s `EXCLUSIVE_BOT_IDENTITY` rule (#2274) admits it as Cursor's standing not-clean verdict and will only accept a comment from the `cursor` login to supersede it.
  That session's claim expired and it is gone;
  the `cursor-agent` CLI posts under the user's own login, bucketed separately, so no reachable process can ever supersede the ledger.
  Tracked as [ai-config#2482](https://github.com/Morrison-Lab/ai-config/issues/2482).
- **Canonical Rule**: [`fully-clean.md`](../shared/workflow/fully-clean.md)'s per-reviewer latest-verdict rule (Criterion 2, `EXCLUSIVE_BOT_IDENTITY`).
- **Fix**: When a not-clean verdict belongs to an exclusive-login bot whose posting session is gone, do not dispatch further same-tool or cross-vendor reviews expecting supersession --- escalate to a human immediately (per `fully-clean.md`'s deadlock rule), citing #2482.

## Pattern 21: A Piped or Redirected `git push` Is Parsed as a Commit-ish by the Self-Review Guard
- **Mistake**: Appending `2>&1 | tail -3` (or any redirection/pipe) to a `git push` command in a repo guarded by `hooks/no-push-without-self-review.py`, then reading the guard's "`2` could not be resolved to a commit" refusal as a real review-state problem and re-dispatching a review that already exists.
- **Example**: 2026-08-27, ai-config#2477: `git push origin cursor/ums-wrap-2272-32a3 2>&1 | tail -3` was blocked twice by the hook tokenizing the raw shell command line and treating the `2` from `2>&1` as a commit-ish push argument.
  The identical push with the redirection/pipe stripped succeeded immediately against an existing clean verdict.
- **Canonical Rule**: [`no-push-without-self-review.py`](../hooks/no-push-without-self-review.py) parses the raw Bash command line, not the resolved push arguments.
- **Fix**: Run a bare `git push origin <branch>` with no `2>&1`, no pipe, and no trailing redirection in a guarded repo.
  Before assuming the review state itself is stale, read the guard's refusal for a resolution error naming a suspicious token (a bare digit, a stray file target).

## Pattern 22: A Background-Dispatched Review Verdict Is Invisible to the Push Guard
- **Mistake**: Dispatching the final adversarial-reviewer round with `run_in_background: true` (or resuming a completed reviewer via `SendMessage`) and then pushing on the strength of its clean report, when `hooks/no-push-without-self-review.py` only scans the FOREGROUND transcript for verdicts and never sees a report that arrived as a background task notification.
- **Example**: 2026-08-27, ai-config#2483: a fresh "Ready for merge / Reviewed-Commit: 6d1e7ace..." report arrived via a task notification, and the very next push of that exact commit was refused with "The clean verdict is for commit 0825a859..." --- a stale earlier verdict --- forcing an `ALLOW_UNREVIEWED_PUSH` override for a genuinely reviewed head.
- **Canonical Rule**: [`adversarial-self-review.md`](../shared/workflow/adversarial-self-review.md) (dispatch to a separate subagent) plus [`no-push-without-self-review.py`](../hooks/no-push-without-self-review.py)'s transcript scan.
- **Fix**: Dispatch the round whose verdict you intend to push on in the FOREGROUND (`run_in_background: false`), not as a background task.
  If a background or resumed verdict is the only one available, push with `ALLOW_UNREVIEWED_PUSH=1` and state the reason (verdict landed via background notification, guard cannot see it) rather than re-diagnosing a stale-verdict refusal as a review-state regression.

## Pattern 23: Implementing From a Truncated Issue-Body Read
- **Mistake**: Briefing an implementer (a subagent, or yourself) from a sliced issue body --- e.g. `gh issue view --jq '.body[0:2200]'` --- instead of the full body and its comments.
  The slice is silent about what it dropped, so the brief inherits the truncation invisibly and the implementation ships only the requirements that survived the cut.
- **Example**: 2026-08-27/28, ai-config#2371: a `.body[0:2200]` slice dropped the issue's point 4 ("empty estate must be an error").
  The implementation shipped points 1-3;
  a `Closes #2371` would have silently closed the issue without the self-described load-bearing requirement.
  The bot review on PR #2478 caught the gap.
- **Canonical Rule**: [`issue-first.md`](../shared/workflow/issue-first.md)'s splitting rule --- a `Closes #N` closes the whole issue including every item the diff never addressed --- applies with equal force to an item dropped by truncation as to one dropped by scope-splitting.
  [`github-actions-secrets.md`](github-actions-secrets.md)'s "Changing a secret's scope breaks tooling keyed on the old topology" section carries the root-cause bug (#2371) this pattern and Pattern 24 below were both fixing.
- **Fix**: Read the full issue body (and its comments) before implementing;
  a body slice is for triage only, never for briefing an implementation.
- **Algorithmatizable?**
  Borderline, and not yet built.
  A hook could warn when a `.body[0:` (or equivalent) slice feeds a step that goes on to implement, but this is a single occurrence --- the third-occurrence bar in [`deterministic-tools.md`](../shared/principles/deterministic-tools.md) is not met, so this stays a judgment-class entry for now rather than a guard.

## Pattern 24: An Error Message That Asserts Scope It Did Not Check
- **Mistake**: Adding a terminal error/exit branch without re-deriving every caller path that reaches it, and reusing wording from a wider-scope branch that claims a check the current path never ran.
  This is [`fail-fast.md`](../shared/principles/fail-fast.md)'s pass-path-equals-failure-path shape one level up: two different code paths converge on one message, and the message is true for only one of them.
- **Example**: 2026-08-27/28, ai-config#2371 / PR #2478: the first fix for point 4 printed "found in NO scope --- neither org-level nor any repo copy" on the `--repos`-only code path, where the org-level sweep never ran.
  The reviewer reproduced the false claim directly.
- **Canonical Rule**: [`fail-fast.md`](../shared/principles/fail-fast.md) (a guard's pass path must not be reachable by its failure path, applied here to a message's claimed scope rather than to a boolean outcome).
  This pattern was found on #2371 / PR #2478, the same issue as Pattern 23 above;
  [`github-actions-secrets.md`](github-actions-secrets.md) carries the root-cause bug tracked as #2371 (it predates PR #2478 and does not cite it).
- **Fix**: When adding an error/exit branch, enumerate the flag combinations that can reach it and word the message to name only what was actually examined on that path.
  Never reuse a full-sweep message on a narrowed path.
- **Algorithmatizable?**
  No decidable condition established.
  "Does this message's claimed scope match what this code path actually examined?" requires reading the branch's semantics, not a pattern match --- same class as `learn-from-review-findings.md`'s own "did the sweep cover the diff's own added lines?" example of a non-algorithmatizable finding.

## Pattern 25: Pushing Prose Without Running the Diff-Scoped `new-line-breaks` Check First
- **Do**: Before pushing any commit that adds or edits Markdown prose in this repo, run `NLB_BASE_REF=origin/main python3 scripts/vendor/gha-check-new-line-breaks.py` (or `scripts/semantic-line-breaks.py <file> --write` to auto-fix) against the **committed** diff, and only push once it reports clean.
- **Don't**: Push a prose commit on the strength of having written it carefully, skipping the local gate check because the change "is just one sentence" or "is obviously fine" --- and don't check an uncommitted/staged version, since the diff-scoped tool reads `origin/main...HEAD` and cannot see anything not yet committed (see this repo's own `CLAUDE.md`, "Running that check locally before a push proves nothing about files you have not committed yet").
- **Example**: 2026-08-29 GIA session, wave 2 (`Morrison-Lab/ai-config`): hit twice in one session, on two different PRs, despite this exact check being one of the most extensively documented pre-push habits in this repo's own `CLAUDE.md`.
  PR #2583 (`shared/principles/fail-fast.md`, closes #978): a newly-added cross-reference paragraph packed two sentences on one line;
  CI's `new-line-breaks` job failed, diagnosed via `mcp__github__get_job_logs`, fixed with `scripts/semantic-line-breaks.py shared/principles/fail-fast.md --write` and a follow-up commit.
  PR #2585 (`README.md`, closes #1136): the identical failure shape, same session, same fix procedure, on the very next prose-editing PR.
  In both cases the fix took under a minute once diagnosed --- the cost was the CI round-trip and the recurrence itself, not the remedy.
- **Canonical Rule**: `CLAUDE.md`'s "About this repo" section (in `gha`, ported here as a general lesson) and the check's own diff-scoping behavior described above;
  this repo's `scripts/vendor/gha-check-new-line-breaks.py` is the same checker CI runs.
- **Fix**: Add "run the diff-scoped `new-line-breaks` check against the committed diff" as a mechanical step of every prose-touching commit in this repo, immediately before `git push`, not as a thing recalled from having read about it once.
- **Algorithmatizable?**
  Yes, and worth building rather than relying on memory a third time: a pre-push git hook (or a `hooks/` PreToolUse guard on `git push` in this repo specifically) that runs `NLB_BASE_REF=origin/<default-branch> python3 scripts/vendor/gha-check-new-line-breaks.py` and warns (never blocks, per the fail-open convention this repo's own hooks use) when it finds a violation the pending push would carry.
  Not yet built --- filed as [ai-config#2590](https://github.com/Morrison-Lab/ai-config/issues/2590) rather than left as an unrecorded intention, per `no-empty-promises.md`.

## Pattern 26: Running the `new-line-breaks` Check Against a Stale Local `origin/main`
- **Do**: Run `git fetch origin main` (or `origin <default-branch>`) immediately before `NLB_BASE_REF=origin/main python3 scripts/vendor/gha-check-new-line-breaks.py`, in any session where other PRs may be merging to the base branch concurrently --- a multi-PR wave session is exactly that case, since each PR's own merge advances the ref every other open branch diffs against.
- **Don't**: Trust a "clean" result from a check run earlier in the session against whatever `origin/main` pointed to at the time, once any merge has landed since --- the check is base-relative, so its answer decays the same way a cached `mergeable_state` does, and it decays silently: the tool's own output looks identical whether the base is fresh or hours stale.
- **Example**: 2026-08-29 GIA session, wave 4 (`Morrison-Lab/ai-config`), PR #2604 (`shared/writing/citations.md`, closes #882): the check reported "No lines missing semantic breaks" against a local `origin/main` at `aa94c131`, which was correct at the time.
  By the time the branch was pushed, an unrelated PR (#2597) had merged, advancing `origin/main` to `9124943f`.
  CI's `new-line-breaks` job, diffing against the real current base, failed on 10 lines the stale local check had never seen as "added" because they weren't part of the diff against the base it was actually checking.
  Re-running the identical command locally after `git fetch origin main` reproduced CI's 10 findings exactly, confirming the check itself was never wrong --- only the input ref was.
- **Canonical Rule**: Pattern 25 above establishes running the check at all;
  this pattern is the freshness precondition that pattern's own example does not need, because its two PRs did not straddle an intervening merge to the base branch.
  [`check-before-pushing.md`](../shared/workflow/check-before-pushing.md) makes the identical argument for the PR's *own* remote branch (fetch immediately before acting, not once at the start of a round) --- this is the same argument applied to the *base* branch a diff-scoped local check reads against.
- **Fix**: Treat any diff-scoped local check (`new-line-breaks`, and by the same reasoning any other `NLB_BASE_REF`/`origin/<default-branch>`-relative tool) as needing a fresh fetch of the base ref immediately before each run, not once per session --- cheapest as a habit in a multi-PR session, where the base moves under you by construction.
- **Algorithmatizable?**
  Yes, and narrower than Pattern 25's proposed hook: a pre-push guard could `git fetch origin <default-branch>` (or compare the local `origin/<default-branch>` SHA against a live `ls-remote`) before invoking the diff-scoped checker, rather than trusting whatever ref happens to be cached locally.
  Not yet built.

## Pattern 27: Trusting an Earlier Clean `new-line-breaks` Run After the Diff Grew
- **Do**: Re-run the diff-scoped `new-line-breaks` check immediately before the actual `git push`, against the diff as it will be pushed --- not once, mid-task, against whatever the diff happened to contain at that point.
  If any file is added or edited after the check last ran clean (a changelog fragment, a doc paragraph, a Tests-section writeup), that result no longer describes the diff being pushed and buys nothing.
- **Don't**: Treat a clean result from earlier in the session as still valid once more files have been written, on the reasoning that the check "already passed" for this task --- the check answers for the diff it examined, not for the task as a whole, and a diff that keeps growing after a scoped, capable machine has confirmed it clean is a diff nobody has actually looked at completely, not one that stays vouched-for by inertia.
- **Example**: 2026-08-29 GII session (`Morrison-Lab/gha`, not `ai-config` --- confirming this generalizes past the repo Pattern 25/26 were recorded in), wave of 3 PRs, hit identically on all three, each caught only by CI rather than by re-checking before push:
  PR #731 (`assemble-news`, closes #727): the check ran clean partway through implementation, then a changelog fragment was written afterward and pushed unchecked --- CI's `new-line-breaks` job flagged one two-sentence line in it.
  PR #732 (`ai-code-review`, closes #729): identical shape, two multi-sentence lines in that PR's own changelog fragment.
  PR #735 (`audit_capability_versioning_docs`, closes #730): the check ran clean against the script and its tests, then a `CLAUDE.md` Tests-section paragraph and a changelog fragment were both written afterward --- four multi-sentence lines across the two files, all unchecked before push.
  Each was diagnosed from the CI job log, reproduced locally, fixed with a semantic-line-break pass, and confirmed clean by re-running the same command --- the fix was fast each time, but three CI round-trips in one session were paid for a check that had already been run once, just not against the diff that actually shipped.
- **Canonical Rule**: Pattern 25 establishes running the check at all.
  Pattern 26 establishes running it against a fresh base ref.
  This is the third axis: freshness of the **diff itself**, not the base it's compared against or whether the check ran at all.
  `gha`'s own `CLAUDE.md` ("Running that check locally before a push proves nothing about files you have not committed yet") already states the committed-vs-uncommitted half of this.
  It does not name the mid-task-diff-growth half explicitly, which is the gap this pattern closes.
- **Fix**: Run the check as the last local step before `git push`, after every file for that push is written and staged --- never earlier in the sequence, however natural a mid-task checkpoint feels.
  In a multi-file PR, that means one run per push, positioned after the *last* file (docs, changelog fragment, test) is added, not after the code.
- **Algorithmatizable?**
  Yes, and the same instrument Pattern 25 already proposes (a pre-push guard running the diff-scoped checker) closes this pattern too, for free: a guard that fires immediately before `git push` sees the diff as it will actually be pushed by construction, which is exactly the freshness this pattern is missing when the check is instead run by hand at an arbitrary earlier point.
  No separate hook is needed.
  Pattern 25's proposed guard (ai-config#2590) already covers this axis once built.

## Pattern 28: Trusting Both Sides' Test Suites After a Merge That United Two Independently Grown Versions of One File
- **Do**: When merging two independently grown versions of a file (whether resolved through a merge conflict or merged cleanly by git's auto-merge heuristics) --- one side's structure extended or modified alongside the other side's changes --- write adversarial tests against the **union** itself before trusting it: negated forms, failing (non-matching) inputs, and combinations that exercise one side's extensions inside the other side's structure.
  Also check that alternation branches under a shared quantifier stay disjoint on their first character, so no starting position offers the engine more than one branch to try.
- **Don't**: Read "both sides' full suites pass" or "git auto-merged with no conflict" as evidence the union is sound --- each suite covers only its own side's cases by construction, and defects live in the cross terms neither side had any reason to test.
- **Example**: 2026-08-30, `Morrison-Lab/ai-config` PR [#2668](https://github.com/Morrison-Lab/ai-config/pull/2668): the PR and main's #2684 had both rewritten the same two regexes in `scripts/check-pr-fully-clean.py` (`RESOLVED_BLOCKING_SUFFIX` and `_is_resolved_blocking_mention`'s prefix).
  In the session driving that PR, the conflict was resolved as a union: main's tense-checked, sentence-scoped structure extended with the PR's prefixes (`earlier`, `round-\d+`), plural verbs (`are`/`were`), and a parenthesized-aside branch in the clause scan. (As of this entry's date the resolution lived in that session's working tree, not yet on the PR's pushed head --- verify the specifics against PR #2668 as merged before citing them as its content.)
  The union passed both sides' full suites (344 tests, as counted in that session's united suite) yet carried two defects, both found only by adversarial probes against the union: (1) a negation fail-open --- "None of the earlier blocking findings were resolved." was exempted as a resolved mention, so `classify_verdict` lost a not-clean verdict;
  in the union the exemption passes main's tense-checked structure only via two PR-side extensions, the prefix `earlier` and the plural verb `were`;
  the same input also fails open on the PR side alone, whose suffix check requires no verb and whose negation test covers only suffix forms (`not (yet) X`, `remains open`), so a quantifier negator preceding `blocking` escapes it --- the union thus inherited a vulnerability main's structure alone would have blocked;
  fixed with a negator check (`none|no|not|never|neither|nothing`) on the prefix window before the past-state marker;
  (2) catastrophic backtracking (51 seconds measured) --- the new paren-aside branch `\([^()\n]{0,120}\)` overlapped the char-class branch `[^,:;.!?]` (both could consume `(`), so a failing enumeration input like `"(1) " * 24` was exponential;
  fixed by excluding `()` from the char class so the branches are disjoint --- a stray unmatched paren then fails the clause scan, which fails safe (the mention stays blocking).

  2026-08-31, `Morrison-Lab/ai-config` PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736): merge `80398b90` auto-merged `scripts/check-pr-fully-clean.py` with **no conflict at all** (359 lines from `main`, 109 from the branch);
  the only conflicted path in that merge was `memories/mistake-patterns.md` itself.
  Yet the post-merge adversarial review of the cleanly merged files (`scripts/check-pr-fully-clean.py` and `scripts/pre-push-review.py`, commit `cea1a533`) returned twelve findings, five of them letting not-clean artifacts score clean across the newly combined review-matching, payload-extraction, and disclosure-footer mechanisms (admitting all comments with Claude Code disclosure footers as automated reviews, first-payload-wins admitting quoted prompt templates with clean verdicts, unmasked code spans/blocks, unclosed details tags, and stripped HTML comments ignoring NOT_CLEAN payloads).
- **Canonical Rule**: [`batch-merge-and-resolve.md`](../shared/workflow/batch-merge-and-resolve.md)'s "Five silent failure modes arrive through a merge nothing flags" section establishes that defects arrive through cleanly-resolved merges and clean auto-merges;
  this pattern covers both the case where the conflict *was* seen and resolved, and the clean auto-merge where no conflict was raised.
  [`fact-check-code-logic.md`](../shared/coding/fact-check-code-logic.md) covers verifying the implementation rather than trusting its green suite.
- **Fix**: Treat a union resolution or clean auto-merge of independently grown logic as new code with zero targeted coverage: derive probes from the cross product of the two sides' extensions (each new prefix with each new verb with each new branch), include negated and failing inputs, and time the regex on a pathological non-matching input before committing.
- **Algorithmatizable?**
  Partially.
  The first-character-disjointness check on alternation branches under a quantifier is mechanically decidable and would have caught the backtracking defect;
  regex-timeout linters (or a bounded `re` probe in the test suite) catch the symptom generically.
  Union-level adversarial test *generation* stays judgment.
  The negator and disjointness fixes were made in that driving session's resolution (see the caveat in the Example above about verifying them against PR #2668 as merged).

## Pattern 29: Claiming formal completion of an admin tracking step without actually modifying the tracking file
- **Do**: When announcing that an administrative, tracking,
  or orchestration step is "formally closed out" or "complete"
  (e.g., closing a Conductor track, checking off a checklist item),
  actively verify that the corresponding tracking file
  (e.g. `tracks.md`, `plan.md`)
  has been explicitly modified and saved in the repository to reflect that status.
- **Don't**: Claim a tracking step is "formally closed out"
  just because the underlying implementation work (like merging a PR) is done,
  without actually opening and updating the tracking file itself.
- **Example**: 2026-08-30 session (`Morrison-Lab/gha`):
  The agent successfully squash-merged a PR delivering the `conductor` orchestration setup
  and announced, "This successfully completes the delivery of the Conductor orchestration scaffolding
  and formally closes out this implementation track."
  However, `conductor/tracks.md` remained entirely empty;
  the agent had not registered or closed the track in the file.
  The user correctly flagged this as an "empty promise"
  because the agent claimed a tracking closure on the record
  without shipping the corresponding file change.
- **Canonical Rule**: [`no-empty-promises.md`](../shared/workflow/no-empty-promises.md)
  establishes that a promise leaves a problem addressed *on the record*
  without changing any files, concealing the unaddressed state.
  Claiming an administrative file update without writing to the file
  falls under this exact definition of a false record.
- **Fix**: Open the administrative file (`tracks.md` or `plan.md`),
  make the explicit string change (e.g., adding the track row with `Closed`),
  and commit it.
- **Algorithmatizable?**
  Partially.
  A post-completion verification check could grep the tracking file
  for the target track name to ensure it exists before allowing the session to claim closure.

## Pattern 30: Stopping at Uncommitted Worktree After Implementation Instead of Completing Delivery Cycle
- **Do**: When executing implementation work on a branch, complete the full delivery cycle automatically: run tests, commit scoped changes, run adversarial self-review, check remote branch, push, open/update PR, and request AI review.
- **Don't**: Stop after writing files or tests and report "done" or wait for a follow-up prompt to commit and open a PR.
- **Example**: 2026-08-30 session (`Morrison-Lab/ai-config` on branch `structured_review_bot_output`): implemented structured review JSON parsing in `check-pr-fully-clean.py` and updated reviewer prompts, verified all tests pass, wrote walkthrough artifact, but stopped without committing, pushing, or opening a PR until the user prompted "where's my PR? ums".
- **Canonical Rule**: `AGENTS.md` ("Deliver completed implementation work"): "When asked to implement, edit, or write up a change on a feature branch, do not stop at an uncommitted worktree.
  Complete the delivery cycle: create the applicable tracking issue when issue-first workflow applies, commit the scoped changes, run local adversarial self-review to a clean verdict, push the branch, open or update its Pull Request, request AI review after the final push, and drive CI and review findings to a clean result."
- **Fix**: Never terminate an implementation turn at uncommitted files or a local-only commit.
  Complete the full chain (commit -> self-review -> push -> PR -> review request) in that same turn.

## Pattern 31: Self-Ambiguous Alternative Under Repetition Causing Catastrophic Backtracking
- **Do**: When writing a repeated pattern `(A|B)*` or quantifier, verify that alternation branches are strictly disjoint and cannot match prefixes or subsets of each other.
  Replace nested or self-ambiguous quantifiers (like `(={3,}|\s*)*` or duplicated whitespace inside a group with leading whitespace) with linear scans by construction (line scans, string slicing) that cannot backtrack.
  Time the regex on pathological failing inputs (e.g. runs of 40-60+ characters followed by non-matching text).
- **Don't**: Assume that because every branch consumes at least one character, catastrophic backtracking is impossible --- an alternative that is self-ambiguous (like `={3,}` under `*`, which partitions N `=` characters in exponentially many ways) or overlapping branches reintroduce exponential backtracking on non-matching inputs.
- **Example**: 2026-08-31, `Morrison-Lab/ai-config` PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736) (`scripts/pre-push-review.py`): In round 1, removing an empty `\s*` alternative from the fingerprint anchor's `*` quantifier was necessary and not sufficient;
  round 2 revealed `={3,}` under an outer `*` still backtracked exponentially on the tool's own `"=" * 60` report separator followed by non-matching text (0.50s at 36, 4.01s at 42, 14.18s at 45).
  Fixed by replacing the nested-quantifier regex with a linear line scan (0.36ms at 4000 `=`).
- **Canonical Rule**: [`regex-backtracking-pitfalls.md`](../shared/coding/regex-backtracking-pitfalls.md) and [`fact-check-code-logic.md`](../shared/coding/fact-check-code-logic.md).
- **Fix**: Replace repeated ambiguous quantifiers with linear scans
  or enforce strict disjointness between alternatives under repetition;
  measure execution time on long pathological inputs.
- **Algorithmatizable?**
  Yes --- static regex linters and timeout probes
  ([ai-config#2768](https://github.com/Morrison-Lab/ai-config/issues/2768)).

## Pattern 32: Treating a Sampling Instrument's Zero as a Result Without Verifying Arm Reach
- **Do**: When using a corpus-sampling or generator-based instrument (such as `scripts/check-verdict-scan-parity.py`) to verify parity or absence of regressions, explicitly report and verify the **reach** of newly added arms or branches (e.g., confirming the new arm was actually executed and reached, and reporting the number of cases evaluated).
  Place newly added arms where generators and limit/stride logic will not skip or truncate them.
- **Don't**: Accept a sampling instrument reporting "0 widened, 0 narrowed" as evidence of correctness when the new arm was never reached (e.g. truncated by `--limit`, skipped by strided sampling, bypassed by an earlier deciding branch, or missing from the corpus entirely).
- **Example**: 2026-08-31, `Morrison-Lab/ai-config` PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736) (`scripts/check-verdict-scan-parity.py`): Across rounds 2, 3, and 4, the instrument repeatedly reported 0 widened / 0 narrowed as a coverage statement rather than a verification:
  (1) round 2 yielded the payload arm last at index 241,920 where `--limit` truncated it before execution;
  (2) yielding it first in round 2 was still lost because `--limit` used strided sampling selecting only 1 of 57 bodies;
  (3) in round 3 (`cfdedd9c`), generated payload bodies carried a prose `## Verdict:` line that decided before `payload_is_clean` was ever reached (reached 0 of 32 times), fixed in that round by generating payload-only bodies;
  (4) in round 4 (`3a7648a7`), the arm still reported 0/0 because `--limit`'s strided sample skipped the first-yielded payload bodies.
  Fixed in round 5 (`fbf50a69`) by appending the arm after `--limit`, revealing 1 widening and 5 narrowings previously hidden.
- **Canonical Rule**: [`fact-check-code-logic.md`](../shared/coding/fact-check-code-logic.md) ("A sampling instrument's zero is a coverage statement unless the new arm's reach is reported") and [`fail-fast.md`](../shared/principles/fail-fast.md).
- **Fix**: Measure and report reach counts (e.g. "reached M of N times") on every arm of a sampling instrument, and ensure new arms are appended after sampling limits.
- **Algorithmatizable?**
  Yes --- test runners asserting non-zero generator arm execution counts
  ([ai-config#2769](https://github.com/Morrison-Lab/ai-config/issues/2769)).

## Pattern 33: Cross-Artifact Comment Staleness During Multi-Commit PRs
- **Do**: When modifying an invariant, data format, layout, or implementation across commits in a PR, grep across the entire repository (including tests, documentation, helper scripts, and sister modules) for comments and docstrings that assert the state or layout of the modified artifact.
- **Don't**: Rely on adjacent-comment linters (e.g. 10-line single-file windows) or memory of modified files to catch stale assertions about other artifacts;
  comments asserting facts about *another* file expire when that other file changes.
- **Example**: 2026-08-31, `Morrison-Lab/ai-config` PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736): Round 5 (`fbf50a69`) restored the structured `commit_sha` term in `scripts/check-pr-fully-clean.py` and changed prompt/persona rendering from 3-space indentation to flush-left.
  Round 6 (`c725c449`) found two stale cross-artifact comments left behind by round 5's changes: (1) `scripts/test_check_pr_fully_clean.py` still contained a comment claiming `commit_sha` "was REMOVED as provably dead", pointing readers away from the test pinning it;
  (2) `scripts/lib/review_payload.py` still stated that prompts and personas render the payload 3 spaces in.
  Neither was in the diff or within 10 lines of the changed code in their respective files.
- **Canonical Rule**: [`fact-check-code-logic.md`](../shared/coding/fact-check-code-logic.md) ("A comment asserting the state of ANOTHER artifact is a claim with an expiry across commits").
- **Fix**: Grep for tokens and cross-references
  when changing a cross-module contract or layout;
  audit test comments when reverting or restoring implementation logic.
- **Algorithmatizable?**
  Partially.
  Cross-file comment scanning can detect file-name citations and literal quotes,
  but semantic claims require reading.

## Pattern 34: Claiming Subsumption Proofs Over Raw Text Without Accounting for Transformations
- **Do**: When arguing that a structured extraction or parsing branch is redundant and subsumed by a raw text search (e.g. raw substring or regex match), verify whether any transformation (JSON escape decoding like `\u0061`, URL decoding, character set normalization, or whitespace normalization) occurs between the raw text and the parsed value.
- **Don't**: Delete a parser disjunct or term as "provably dead" based on a raw-text subsumption proof that assumes the parsed value appears byte-for-byte in the unparsed body.
- **Example**: 2026-08-31, `Morrison-Lab/ai-config` PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736): In round 4 (`3a7648a7`), the structured `commit_sha` check in `scripts/check-pr-fully-clean.py` was deleted as "provably inert" under the belief that `payload.get("commit_sha") == head_sha` was subsumed by raw substring checks on `head_sha` in the body.
  In round 5 (`fbf50a69`), this had to be restored: `json.loads` resolves Unicode escapes (e.g. `"commit_sha": "\u0061bc1234..."`), so a payload with escaped characters matches the parsed SHA while escaping the raw substring disjuncts.
- **Canonical Rule**: [`fact-check-code-logic.md`](../shared/coding/fact-check-code-logic.md) ("A subsumption proof over raw text must account for every transformation before claiming a disjunct is dead").
- **Fix**: Construct adversarial test fixtures with escaped, decoded, or transformed representations to test whether raw text matching and structured value matching can diverge before deleting extraction logic.

## Pattern 35: Unbounded Subset Overlap in Fuzzy Matching Defeating Negative Controls
- **Do**: When implementing fuzzy or token-overlap matching to tolerate subtitles or minor variations, enforce length and density proportionality (e.g. bounded character/token length ratio or Jaccard similarity threshold) alongside token containment.
- **Don't**: Accept full subset containment (`overlap_coef == 1.0`) of a short needle in a long haystack without bounding the relative lengths or densities;
  a short 2-token title (e.g. "Causal Inference") is a 100% token subset of an arbitrarily long, unrelated review title (e.g. "A Review of Causal Inference Methods in Epidemiology and Public Health Policy"), defeating the tool's fabrication-detection purpose.
- **Example**: 2026-08-31, `Morrison-Lab/ai-config` PR [#2797](https://github.com/Morrison-Lab/ai-config/pull/2797) (`scripts/check_doi_bib.py`): Round 1 implemented `fuzzy_match_title` with an `(overlap_coef == 1.0 and len(intersection) >= 1)` branch intended for subtitle variations.
  Review identified that for short generic titles (2 tokens), this branch matched completely unrelated long review papers with a 1.0 score and classified fabricated citations as `MATCH`.
  Fixed in round 2 by replacing the raw overlap with bounded Jaccard similarity and length proportionality (`jaccard >= 0.60 and len_ratio >= 0.60`), and adding negative control tests for short title containment.
- **Canonical Rule**: [`fixtures-are-not-evidence.md`](../shared/workflow/fixtures-are-not-evidence.md) and [`fact-check-code-logic.md`](../shared/coding/fact-check-code-logic.md).
- **Fix**: Require length ratio constraints and bounded Jaccard thresholds for fuzzy matching, and always test negative controls with short generic strings contained in long unrelated targets.
- **Algorithmatizable?**
  Yes --- unit test suites asserting negative control rejection of short subset inputs against long distractor strings.

## Pattern 35: Fixing the Admitting Site But Not the Branching Site
- **Do**: When handling a new condition, trigger, or input case, verify both the **admitting site** (the gate deciding whether the code runs) and the **branching site** (the logic deciding what the code does once it runs).
  Find branching sites by searching for the conditions or variables they test *instead of* the new condition (e.g., variables that go empty, unset, or defaulted in the new case).
  Test admitted cases by running the actual execution logic against realistic fixtures.
- **Don't**: Stop after updating the admitting rule named in the issue or finding without auditing downstream branching logic;
  a fix that admits a case into downstream code that doesn't handle it creates a false sense of completion while silently executing the wrong path.
- **Example**: 2026-08-29 on `health-analytics-core/HACtions!47` (internal GitLab):
  A reviewer noted tag pipelines were excluded from a CI job.
  The fix added `- if: $CI_COMMIT_TAG` to the job's `rules:`, admitting tags.
  However, the job's downstream script still evaluated `if [ "${CI_COMMIT_BRANCH:-}" = "${CI_DEFAULT_BRANCH:-}" ]` to determine whether to perform a whole-tree scan or a diff against `main`.
  Because `CI_COMMIT_BRANCH` is empty on tag pipelines, tags took the diff branch against `main` (which tags have no branch relationship to) instead of the intended whole-tree scan.
  CI was green because CI never ran a tag pipeline in that MR, giving a false appearance of completion until re-reviewed.
- **Canonical Rule**: [`admitting-vs-branching-site.md`](../shared/principles/admitting-vs-branching-site.md) and [`fail-fast.md`](../shared/principles/fail-fast.md).
- **Fix**: Identify all downstream branching points that depend on context variables,
  update branching logic to handle the new case explicitly (e.g. `[ -n "$CI_COMMIT_TAG" ] || [ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ]`),
  and add execution tests against fixtures simulating the new input state.
- **Algorithmatizable?**
  Partially per-domain (e.g. static analyzers checking that CI jobs admitting `$CI_COMMIT_TAG` do not rely exclusively on `CI_COMMIT_BRANCH` in their scripts).
  General case requires behavioural fixture tests.

