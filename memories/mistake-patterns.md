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
- **Canonical Rule**: [`fully-clean.md`](../shared/workflow/fully-clean.md) and [`AGENTS.md`](../AGENTS.md) ("Strict Merge Control Policy").
  A fallback self-review or reviewer skip notice does NOT grant approval or satisfy `mwc`.
- **Fix**: Run `scripts/check-pr-fully-clean.py` (or verify all its criteria) before ever declaring a PR fully clean.
  Only report clean when all CI checks pass AND an automated AI review evaluating the exact HEAD SHA has posted an approved / ready verdict with zero open findings.

## Pattern 5g: Dropping Background PR Check Timers While PRs Are In-Flight
- **Mistake**: Reporting intermediate status and ending a turn without leaving an active check timer or recurring cron schedule running, letting PR monitoring go dormant while awaiting CI or review outcomes.
- **Example**: 2026-08-25 session (`Morrison-Lab/ai-config#2226`): after pushing fixes and verifying local status, ended turn without an armed background timer, requiring the user to explicitly remind the agent to keep a check timer running.
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

## Pattern 12: Arming Auto-Merge While Review Findings Are Still Open
- **Mistake**: Running `gh pr merge --auto` (or any deferred/auto merge) on a PR that still has open review findings or no verdict at head.
  Treating the arming as harmless because CI is red ignores that the robot fires later,
  the moment checks go green,
  with no re-check of review state.
- **Example**: 2026-08-26 on `ai-config#2226`:
  armed `--squash --auto` while round-1 findings were open and the reviewer was quota-skipping.
  Hours later a push turned `validate` green,
  auto-merge fired at 04:30Z,
  and it merged over an explicit Needs-more-work verdict ---
  requiring revert (#2268) plus reland-with-fixes (#2269).
- **Canonical Rule**: [`fully-clean.md`](../shared/workflow/fully-clean.md).
  See also [`check-before-pushing.md`](../shared/workflow/check-before-pushing.md):
  the remote can act between your commands,
  and an armed automation is exactly such an action you scheduled against yourself.
- **Fix**: Never arm `gh pr merge --auto` on a PR whose merge gate includes a posted review verdict, which is every PR here.
  Auto-merge fires server-side the moment CI passes,
  so a review landing seconds later cannot block it,
  and no reactive disable can win that race.
  Branch protection does not substitute either:
  it gates native approvals, not verdicts posted as comments.
  Merge synchronously instead,
  only after `scripts/check-pr-fully-clean.py <N>` exits clean ---
  CI green and the all-clear verdict both verified at the shipping head.
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
  The design that survived review, proposed in PR #2448 and still open at the time of writing, is a one-sentence authoring convention --- backtick a quoted verdict phrase --- as a 37-line addition to `ard`'s summary-comment step, with zero checker code change.
- **Canonical Rule**: [`metacognitive-monitoring.md`](../shared/workflow/metacognitive-monitoring.md)'s cause claim-type ("what else explains it") and [`deterministic-tools.md`](../shared/principles/deterministic-tools.md)'s recurrence test, applied one level earlier: recurring *refutation* of a design is itself the signal to stop designing and measure.
- **Fix**: After the second refutation of the same classification problem, stop proposing new discriminators.
  Execute the classifier (or the equivalent instrument) over the actual failing input's constituent parts and read which feature produces the output, before writing a third design.
  Consider whether the fix belongs at the author's end (a convention change) rather than in the instrument at all --- the instrument's own vocabulary can already handle a correctly-written input.

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
