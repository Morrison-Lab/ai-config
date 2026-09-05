# Active Hooks Catalog & Proactive Compliance Guide

`Morrison-Lab/ai-config`'s active hooks are those registered in [`hooks/hooks.json`](../hooks/hooks.json), plus the `monitor-open-prs.py` daemon, which is not registered there.
For the current number run `python3 scripts/check-hook-catalog.py` and add one for the daemon.
No count is written here on purpose: it moves whenever any hook-adding PR merges, so a figure in this file is stale the moment it is written and a reader cannot tell.
This document describes those hooks --- their lifecycle events, triggering conditions, verification mechanisms, and rules for **proactive compliance** so agents can satisfy requirements naturally without tripping guards.
The registry is the authority;
the tables below are still catching up, and two registered hooks have no row yet: `flag-config-deletion-without-ref-check.py` and `warn-stale-review-diff-base.py`.
The gap survives because `scripts/check-hook-catalog.py` compares the registry against README.md rather than against this file.

For agents operating in this repository or consuming its skills, proactive compliance means following these rules by default rather than waiting for a hook to fire or block.

## Overview & Architecture

Hooks in `ai-config` enforce standing repository policies, prevent silent regressions, inject timely context (such as local clock time), and mechanize quality gates.
They are configured natively in [`hooks/hooks.json`](../hooks/hooks.json) (for Claude Code and Cursor Cloud) and mapped across supported AI harnesses (such as [Google Antigravity](../memories/antigravity.md) and [Cursor](cursor.md)).

Hooks fall into four primary lifecycle phases:
1. **`UserPromptSubmit`**: Context injection, background monitor status synchronization, and proactive learning reminders.
2. **`PreToolUse`**: Pre-execution validation for `Bash`, `Agent`, `Task`, `SendMessage`, `Write`, `Edit`, and `mcp__github__.*` tool calls.
3. **`Stop`**: Turn-completion guards that validate output completeness, stopping-point declarations, timestamps, and delivery commitments.
4. **Detached Timers & Services**: Background daemon scripts providing continuous monitoring across sessions.

---

## 1. `UserPromptSubmit` Hooks (Context Injection & Learning Reminders)

These hooks run before a turn begins.
They inject real-time local timestamps, surface detached background monitor state, or provide non-blocking reminders when past turns contained admissions or scrutiny without recorded learnings.

| Hook Script | Matcher | Type | Trigger / Purpose | Proactive Compliance Rule |
|---|---|---|---|---|
| [`inject-local-time.sh`](../hooks/inject-local-time.sh) | None | Inject | Injects local Pacific time (`America/Los_Angeles`) and UTC time into turn context. | Read the injected timestamp or run `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` fresh before stating recaps. Never guess or recall local time from memory. |
| [`ensure-open-pr-monitor.py`](../hooks/ensure-open-pr-monitor.py) | None | Background Service | Ensures the detached timer monitoring all open GitHub PRs and GitLab merge requests authored by the user is running. | Infrastructure daemon; no manual agent action required. |
| [`inject-pr-monitor-status.py`](../hooks/inject-pr-monitor-status.py) | None | Inject | Injects changed PR status or consecutive monitor error alerts from the detached PR poller. | When status updates are injected, acknowledge them and address any CI failures or review findings immediately. |
| [`remind-ums-after-error.py`](../hooks/remind-ums-after-error.py) | None | Warn / Reminder | Reminds when an admitted mistake has no subsequent memory or skill write. | When admitting an error, immediately follow up with an explicit UMS pass (`skills/ums`) to persist the correction to `memories/` or `skills/`. |
| [`no-mistake-without-a-hook.py`](../hooks/no-mistake-without-a-hook.py) | None | Warn / Reminder (also Stop) | Reminds when an admitted, mechanizable mistake lacks an accompanying hook implementation. | Whenever a mistake is mechanizable, author an enforcement hook in `hooks/` with test suite and manifest entry in the same session. |
| [`remind-deserialize-before-binary-claim.py`](../hooks/remind-deserialize-before-binary-claim.py) | None | Warn / Reminder | Reminds when an escalation or claim names a binary artifact (`.rds`, `.rda`, `.parquet`, etc.) that was never deserialized in the session. | Always deserialize and inspect the contents of binary artifacts (e.g. `readRDS()`, Python reader) in the same turn before making claims about their values or diffs. |
| [`remind-learn-from-review.py`](../hooks/remind-learn-from-review.py) | None | Warn / Reminder | Reminds when an accepted external reviewer finding has no recorded learning or mechanism following it. | When agreeing with an external review finding, record the underlying principle in `memories/` or update skills before closing out the PR. |
| [`remind-ums-on-scrutiny.py`](../hooks/remind-ums-on-scrutiny.py) | None | Warn / Reminder | Reminds when work was scrutinized (review read, questioned claim) without an explicit UMS pass. | Proactively invoke the `ums` skill whenever reading critical review feedback or when answering a questioned claim that proved incorrect. |
| [`remind-retry-before-declaring-blocked.py`](../hooks/remind-retry-before-declaring-blocked.py) | None | Warn / Reminder | Reminds when an auto-mode permission-classifier denial has no later re-attempt of the same command; scoped to the classifier's own denial, never a user's rejection or a deterministic rule/hook refusal. | Re-run a classifier-denied command once before treating the path as closed, and report "denied N times so far" rather than "cannot" -- a denial is a sample, and stopping destroys the evidence that would refute it. |
| [`remind-both-sides-from-git.py`](../hooks/remind-both-sides-from-git.py) | None | Warn / Reminder | Reminds when a revision-qualified git blob (e.g. `git show <ref>:<path>`) is compared against the uncommitted working-tree copy. | When comparing across revisions or checking regression diffs, extract both operands from explicit git revisions into `/tmp/` so neither operand relies on dirty or unswitched working tree state. |
| [`remind-ci-crosscheck-sim-verdict.py`](../hooks/remind-ci-crosscheck-sim-verdict.py) | None | Warn / Reminder | Reminds when a verdict-shaped figure or claim follows a local simulation run without checking CI logs. | Cross-check local simulation and test results against CI run artifacts or logs before publishing final conclusions. |

---

## 2. `PreToolUse` Hooks (Pre-Execution Validation)

PreToolUse hooks intercept tool invocations before execution.
Blocking hooks deny execution (exit code 2), while warning hooks emit actionable guidance without aborting.

### 2.1 Bash Tool Interceptors

| Hook Script | Type | Trigger / Purpose | Proactive Compliance Rule | Override / Escape Valve |
|---|---|---|---|---|
| [`require-gh-repo-flag.py`](../hooks/require-gh-repo-flag.py) | **Block** | Blocks mutating repo-scoped `gh` commands lacking `-R <owner>/<repo>`. | Always pass `-R <owner>/<repo>` explicitly on mutating `gh` calls (`gh pr create -R ...`, `gh issue comment -R ...`, `gh pr edit -R ...`, `gh release create -R ...`). | None (always provide `-R`). |
| [`no-unauthorized-merge.py`](../hooks/no-unauthorized-merge.py) | **Block** | Blocks unauthorized PR/MR merge commands (`gh pr merge`, `glab mr merge`, `gh api .../merge`). | Do not run merge commands without explicit user instruction or an active `/mwc` session. | Set `ALLOW_MERGE=1 <cmd>` when explicitly authorized. |
| [`no-whole-file-punct-replace.py`](../hooks/no-whole-file-punct-replace.py) | **Block** | Blocks whole-file punctuation/glyph replacement scripts that obscure real changes in diffs. | Scope punctuation fixes to touched lines or targeted files using AST linters or targeted regexes instead of whole-file sweeps. | Set `ALLOW_WHOLE_FILE_PUNCT=1 <cmd>` if whole-file replacement is intentional. |
| [`flag-unchained-branch-switch.py`](../hooks/flag-unchained-branch-switch.py) | Warn | Warns when a branch switch and a subsequent mutating git command are not chained with `&&`. | Always chain `git checkout` / `git switch` with `&&` before subsequent operations (e.g. `git checkout -b fix && git commit ...`), or execute branch switching in its own separate call. | None. |
| [`no-heavy-work-on-head-node.py`](../hooks/no-heavy-work-on-head-node.py) | **Block** | Blocks CPU-heavy R/Quarto/test commands on SLURM cluster login/head nodes. | Run heavy computation and test suites via `sbatch` or within `salloc` interactive compute nodes. | Inert off cluster head nodes. |
| [`flag-add-a-outside-pathspec.py`](../hooks/flag-add-a-outside-pathspec.py) | Warn | Warns when `git add -A` / `git add .` sweeps in untracked files not covered by explicit exclusion pathspecs. | Run `git status` first and stage explicit paths (`git add <path>`) rather than blanket staging. | None. |
| [`flag-reset-hard-uncommitted-work.py`](../hooks/flag-reset-hard-uncommitted-work.py) | Warn | Warns when `git reset --hard`, `git checkout <pathspec>`, or `git restore <pathspec>` is about to discard tracked, uncommitted modifications. The two path forms revert the named paths to the index, or to an explicit source when one is given (`<tree-ish> --` or `-s <ref>`, which this hook also matches), so an edit made since the last `git add` is destroyed silently at exit 0 (ai-config#2524). Also warns, at whole-tree scope, on a FORCED `git checkout` that resolves to no pathspec (`-f`/`--force`, with or without a ref): forcing removes the refusal, and the ref-less `git checkout -f` reverts every tracked file to HEAD with no output at all. Silent on an UNFORCED branch switch (`git checkout <ref>`), which git refuses when it would clobber local changes and otherwise carries them across, and on `git restore --staged` without `--worktree`, which rewrites only the index. Not matched, and destructive: `git switch -f`/`--discard-changes <ref>`, which discards tracked working-tree changes silently at exit 0 -- `git switch` is a fourth command this guard does not read. | Inspect `git status` before resetting or restoring, scoping it to the paths the command names (`git status --porcelain -- <path>`). Commit or `git stash -u` the work you mean to keep before invoking `git reset --hard`, `git checkout <pathspec>`, `git restore <pathspec>`, a forced `git checkout -f`/`--force` (with or without a ref), or `git switch -f`/`--discard-changes` -- the hook warns on every form but the last, so the forced `git switch` needs that check by hand. | None. |
| [`no-handrolled-verdict-parse.py`](../hooks/no-handrolled-verdict-parse.py) | **Block** | Blocks ad-hoc grep/regex evaluation of review comments for cleanliness. | Always use `python3 scripts/check-pr-fully-clean.py <pr>` as the definitive authority for PR review cleanliness. | Set `ALLOW_HANDROLLED_VERDICT_PARSE=1 <cmd>` when querying raw comments for other purposes. |
| [`warn-pr-create-without-dupe-check.py`](../hooks/warn-pr-create-without-dupe-check.py) | Warn | Warns when creating a PR or issue without an earlier search query in the session to check for duplicates. | Run `gh pr list --state all --search "<keywords>"` or `gh issue list --state all --search "<keywords>"` in a separate command before creating a PR or issue. | None. |
| [`flag-stale-adjacent-comment.py`](../hooks/flag-stale-adjacent-comment.py) | Warn | Warns when a `git commit` modifies a numeric/string literal while an adjacent comment within 10 lines retains the old value. | Check nearby comments when modifying constants, thresholds, or counts, and update comments to match the new code values. | None. |
| [`no-delete-branch-under-stacked-pr.py`](../hooks/no-delete-branch-under-stacked-pr.py) | Warn | Warns when merging or closing a PR with `--delete-branch` while child PRs are stacked on top of it. | Check whether dependent PRs are stacked on the head branch before deleting. Pass `--delete-branch=false` if stacked PRs exist. | None. |
| [`no-clobbering-push.py`](../hooks/no-clobbering-push.py) | **Block** on bare `-f`; Warn on divergence | Denies bare `git push --force`/`-f`. Warns when remote tracking tip has diverged from local branch. | Run `git ls-remote --heads origin <branch>` immediately before every push. Use `git push --force-with-lease --force-if-includes`. Reconcile diverged remotes via fetch and rebase. | Set `ALLOW_FORCE_PUSH=1 git push ...` if lease is unsatisfiable and reason is documented. |
| [`warn-new-line-breaks-on-push.py`](../hooks/warn-new-line-breaks-on-push.py) | Warn | Warns on `git push` when committed markdown lines lack semantic line breaks (SemBr). | Run `NLB_BASE_REF=origin/main python3 scripts/vendor/gha-check-new-line-breaks.py` and ensure semantic line breaks before pushing. | None. |
| [`warn-nonglobal-substitution.py`](../hooks/warn-nonglobal-substitution.py) | Warn | Warns on in-place `perl -i` / `sed -i` substitutions lacking the global `g` flag or occurrence specifier. | Ensure substitution expressions include `g` (e.g. `s/pattern/replacement/g`) when replacing across files. | None. |
| [`warn-dupe-check-chained-to-create.py`](../hooks/warn-dupe-check-chained-to-create.py) | Warn | Warns when a duplicate search and a `gh pr create` / `gh issue create` share the same Bash command string. | Execute the search command first, inspect the results, and then execute the create command in a separate, subsequent tool call. | None. |
| [`warn-status-read-after-pipe.py`](../hooks/warn-status-read-after-pipe.py) | Warn | Warns when checking `$?` immediately after a pipeline without `pipefail` enabled. | Add `set -o pipefail` before executing pipelines whose non-tail exit status must be checked, or use `$PIPESTATUS`. | None. |
| [`no-push-without-self-review.py`](../hooks/no-push-without-self-review.py) | **Block** | Blocks `git push` unless an adversarial self-review subagent produced a clean verdict for the exact commit being pushed. | Dispatch the `adversarial-reviewer` subagent against `HEAD`, address any findings, and obtain a clean verdict matching `Reviewed-Commit: <HEAD_SHA>` before pushing. | Set `ALLOW_UNREVIEWED_PUSH=1 git push ...` for initial empty PR branches, external CLI reviews, or unregistered personas. |
| [`flag-uncited-rebuttal.py`](../hooks/flag-uncited-rebuttal.py) | Warn | Warns when posting a comment disputing a finding that cites an external URL when no `WebFetch` or `WebSearch` fetched that URL. | Fetch and inspect the external URL cited by the reviewer before posting a rebuttal comment. | None. |
| [`require-agent-disclosure.py`](../hooks/require-agent-disclosure.py) | Warn | Warns when posting a forge comment lacking the agent disclosure trailer. | Append `\n\n_Posted by <Agent Name> (AI agent) --- not written by a human._` to every posted comment. Never use the robot emoji. | None. |
| [`flag-uncounted-comment-claims.py`](../hooks/flag-uncounted-comment-claims.py) | Warn | Warns when a forge comment asserts file counts or lists identifiers without a deriving command. | Run deriving commands (`grep -c`, `wc -l`, `ls`, etc.) in the session and cite the deriving command when stating cardinality. | None. |
| [`flag-unmeasured-timestamp.py`](../hooks/flag-unmeasured-timestamp.py) | Warn | Warns when a `gh` comment or review body states a Pacific clock time (`HH:MM`, optional seconds, optional AM/PM, then `PDT`, `PST`, or `PT`) with no clock read in the current turn, or when the body cannot be read (a `--body-file` not yet on disk). | Run `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` immediately before typing a time into a claim or status comment, and restate the stamp from its output. | None. |
| [`flag-cd-into-main-checkout.py`](../hooks/flag-cd-into-main-checkout.py) | Warn | Warns when a worktree-rooted session `cd`s into the primary/main checkout of the repository. | Keep all file edits and command executions rooted within the dedicated worktree directory. | None. |
| [`warn-unlabelled-agent-issue.py`](../hooks/warn-unlabelled-agent-issue.py) | Warn | Warns when `gh issue create` / `glab issue create` runs with no `ai-authored` label in the command. | Pass `--label ai-authored --label "model:<model-id>"` (both CLIs also accept the comma-separated `--label "ai-authored,model:<model-id>"`) in the creating command, per `shared/workflow/issue-first.md`. | None. |

### 2.2 Agent, Task & SendMessage Interceptors

| Hook Script | Matcher | Type | Trigger / Purpose | Proactive Compliance Rule |
|---|---|---|---|---|
| [`flag-unassigned-worktree.py`](../hooks/flag-unassigned-worktree.py) | `Agent` | Warn | Warns when a write-capable subagent is launched without worktree isolation. | Specify `isolation: "worktree"` (or workspace branch) when launching subagents that perform file modifications. |
| [`no-fable-subagent.py`](../hooks/no-fable-subagent.py) | `Agent`, `Task`, `Workflow` | Block | Denies an Agent launch on Fable, explicit or inherited from a Fable session, without the user's grant; warns on a Workflow launch in a Fable session. | Pass `model: sonnet` (or `haiku`) on the call, or, once the user has approved that specific launch, run it with `FABLE_SUBAGENT_OK=1` for that one command. Set `FABLE_SUBAGENT_OK=1` for the one approved launch only; never export it for a session. |
| [`remind-brief-premises.py`](../hooks/remind-brief-premises.py) | `Agent`, `Task`, `SendMessage` | Warn / Reminder | Reminds when subagent briefs assert corpus facts or file counts not derived in the session. | Include verified derivation commands or concrete file paths in subagent briefs rather than unverified assertions. |

### 2.3 MCP Tool Interceptors (`mcp__github__.*`)

| Hook Script | Type | Trigger / Purpose | Proactive Compliance Rule |
|---|---|---|---|
| [`no-unauthorized-merge.py`](../hooks/no-unauthorized-merge.py) | **Block** | Blocks `merge_pull_request` MCP calls without authorization. | Do not invoke MCP merge tools without explicit permission or active `/mwc`. |
| [`warn-pr-create-without-dupe-check.py`](../hooks/warn-pr-create-without-dupe-check.py) | Warn | Warns when creating PRs/issues via MCP without a prior search query. | Run `search_issues` or `search_pull_requests` before creating items via MCP tools. |
| [`warn-unlabelled-agent-issue.py`](../hooks/warn-unlabelled-agent-issue.py) | Warn | Warns when `mcp__github__issue_write` (`method: create`) files an issue with no `ai-authored` label. | Pass `labels: ["ai-authored", "model:<model-id>"]` on the create call. |
| [`require-agent-disclosure.py`](../hooks/require-agent-disclosure.py) | Warn | Warns when posting comments via MCP without the disclosure trailer. | Include `\n\n_Posted by <Agent Name> (AI agent) --- not written by a human._` in the `body` argument of MCP comment tools. |
| [`flag-unmeasured-timestamp.py`](../hooks/flag-unmeasured-timestamp.py) | Warn | Warns when the `body` of any `mcp__github__` comment tool that `require-agent-disclosure.py` covers states a Pacific clock time with no clock read in the current turn. | Run `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` before typing a time into the `body` argument of MCP comment tools. |

### 2.4 Write, Edit & NotebookEdit Interceptors

| Hook Script | Type | Trigger / Purpose | Proactive Compliance Rule |
|---|---|---|---|
| [`warn-stale-issue-edit.py`](../hooks/warn-stale-issue-edit.py) | Warn | Warns when editing code for an issue without a fresh `VIEW_ISSUE` and remote default-branch check. | Run `gh issue view <N>` (or `VIEW_ISSUE`) and check `git fetch origin main` / `origin/main` before modifying files for an issue. |
| [`flag-unmeasured-timestamp.py`](../hooks/flag-unmeasured-timestamp.py) | Warn | Warns when editing or writing to session notebooks (`session-*.md`) or memory files (`memory/*.md`) stating a Pacific clock time without a date reading in the turn. | Run `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` before writing or appending timestamps to session notebooks or memory files. |

---

## 3. `Stop` Hooks (Completion & Output Validation)

`Stop` hooks evaluate the agent's response before it is delivered to the user.
Blocking hooks prevent the turn from ending until the missing artifact or requirement is satisfied.

| Hook Script | Type | Trigger / Purpose | Proactive Compliance Rule | Override / Escape Valve |
|---|---|---|---|---|
| [`no-offer-to-file.py`](../hooks/no-offer-to-file.py) | **Block** | Blocks responses that offer to file an issue, update memory, or write a skill instead of doing it. | Perform authorized actions directly: file the issue (`gh issue create -R ...`) or commit the memory/skill update in the same turn, and report what was completed. | None. |
| [`no-empty-promise.py`](../hooks/no-empty-promise.py) | **Block** | Blocks replies committing to future behavior without an implemented mechanism in the same turn. | When committing to a rule or action, ship the written rule/memory/hook in the current turn, arm a scheduled timer/monitor for owed actions, or state plain facts without future-tense promises. | None. |
| [`no-unfiled-finding.py`](../hooks/no-unfiled-finding.py) | **Block** | Blocks declarative statements that an issue or finding is "worth filing" without having filed it. | File the tracking issue immediately before concluding the turn. | None. |
| [`no-stale-pr-status.py`](../hooks/no-stale-pr-status.py) | **Block** | Blocks replies declaring PR check status based on readings taken prior to the latest push. | Always query fresh PR status (`gh pr checks <N> -R ...`) after any `git push` before stating check results. | None. |
| [`no-incomplete-check-enumeration.py`](../hooks/no-incomplete-check-enumeration.py) | **Block** | Blocks declaring a PR fully clean based solely on surface rollup checks (`gh pr checks`). | Run `python3 scripts/check-pr-fully-clean.py <pr>` to evaluate full CI run logs and reviewer verdicts. | None. |
| [`no-unreviewed-pr.py`](../hooks/no-unreviewed-pr.py) | **Block** | Blocks ending a turn after creating/updating a PR without requesting an AI reviewer. | Request a review on opened/updated PRs (`gh pr create` with reviewer request, or request review via forge tools). | Set `ALLOW_UNREVIEWED_REDACTION_PR=1` on redaction PRs or use `no-ai-review` label. |
| [`no-unshipped-commit.py`](../hooks/no-unshipped-commit.py) | **Block** | Blocks ending a turn when unpushed commits remain on the local branch. | Push all commits (`git push`) or cleanly drop temporary exploratory commits before ending the turn. | None. |
| [`no-report-unfixed-hook-test.py`](../hooks/no-report-unfixed-hook-test.py) | **Block** | Blocks status replies reporting a missing hook test identified by CI without writing the test. | Implement the companion `hooks/test-<name>.py` test suite in the same turn before reporting status. | None. |
| [`no-unmonitored-pr.py`](../hooks/no-unmonitored-pr.py) | **Block** | Ensures a PR poller or model scheduler is armed when a PR remains open. | Arm an explicit timer or rely on the detached PR monitor service. | None. |
| [`no-unmeasured-clock-claim.py`](../hooks/no-unmeasured-clock-claim.py) | Warn | Warns when stating a local Pacific clock time without a clock query in the same turn. | Execute `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` fresh before including timestamps in replies or recaps. | None. |
| [`no-placeholder-reply.py`](../hooks/no-placeholder-reply.py) | **Block** | Blocks placeholder replies (`N/A`, `No response requested.`, bare acknowledgments). | Always provide substantive, informative recaps explaining completed work and current state. | None. |
| [`flag-cop-out-offer.py`](../hooks/flag-cop-out-offer.py) | Warn | Warns when a response closes with a passive offer on already-authorized work ("let me know if you'd like me to..."). | Execute in-scope authorized tasks directly. If a genuine decision is required, present concrete options accompanied by an explicit recommendation. | None. |
| [`no-misattributed-quote.py`](../hooks/no-misattributed-quote.py) | **Block** | Blocks attributing a quote to a main rule file when the text resides in a `.rationale.md` or `.cases.md` companion file. | Confirm the exact file path where quoted passages reside before citing them. | None. |
| [`require-stopping-point.py`](../hooks/require-stopping-point.py) | **Block** | Blocks final completion replies lacking an explicit stopping-point declaration. | Conclude summaries with an explicit stopping-point statement: `**Stopping Point**: Clean stopping point reached` or `**Stopping Point**: Not a clean stopping point --- [reason]`. | None. |

---

## 4. Detached Timers & Monitoring Services

- **[`monitor-open-prs.py`](../hooks/monitor-open-prs.py)**: Background daemon reconciling every open GitHub PR the authenticated user opened or is assigned to, plus every one the `github-actions` app opened under an owner that user works under, and every GitLab merge request they authored, every two minutes (`gh` and/or `glab`).
- **Detached Execution**: Automatically started and verified via `ensure-open-pr-monitor.py` on session start.

---

## 4.5 A warn-only hook that fires and is ignored is not automatically a hook that should block

The checklist below covers building a hook.
This section covers the question that arrives afterwards, when a warn-only
guard fires on the same mistake several times in one session and the mistake
happens anyway: does the recurrence license escalating it to a block?

**Usually not, and recurrence alone never settles it.**
[`deterministic-tools`](../shared/principles/deterministic-tools.md)'s
third-occurrence bar decides whether an instrument should *exist*.
It says nothing about strength, and reading it as an escalation trigger is a
category error --- the bar counts occurrences of the mistake, while the
strength question turns on how often the guard's condition is satisfied by
*correct* behaviour.

Three questions decide it, in order, and only the third is about the
recurrence.

1. **Is the condition decisive, or only suggestive?**
   A blocking guard on a suggestive condition refuses correct work, and the
   corpus's own repeated finding is that such a guard gets switched off ---
   which costs every true positive it would ever have caught, not just the
   false ones.
   Where the information needed to decide is *not in the artifact the hook can
   see*, no amount of recurrence makes it decisive.
2. **Does the warning already name the concrete remedy?**
   A note that says "this is wrong" and a note that supplies the exact
   rewrite are different instruments.
   Escalating before the note is actionable escalates the wrong thing.
3. **Only then: did it fire, get read, and get ignored?**
   If 1 and 2 both hold and the mistake still recurs, the failure is in
   reading rather than in detection, and a `PreToolUse` `additionalContext`
   note is structurally weak against it --- the note arrives alongside a tool
   call the model has already composed, so it argues against a decision
   already made.
   That is a real limit, and a limit of the *class* rather than a defect in
   the individual hook.

- **Do:** ask whether the condition is decisive before treating a recurrence as
  an escalation signal.
- **Do:** record a recurrence-under-warning even when the answer is that no
  stronger guard is warranted --- the stated reason is what stops the question
  being reopened from scratch next time.
- **Don't:** read `deterministic-tools`'s third-occurrence bar as a bar for
  strength; it decides existence.
- **Don't:** escalate a suggestive condition to a block --- a guard that
  refuses correct work gets disabled, and its true positives go with it.

(Morrison-Lab/ai-config#3180's session, 2026-09-04: reading `$?` immediately
after a pipeline --- so the status read is `tail`'s rather than the command's
--- recurred three times, with
[`warn-status-read-after-pipe.py`](../hooks/warn-status-read-after-pipe.py)
warning each time.
Assessed against the three questions and left warn-only.
Its condition is suggestive by construction, which its own docstring states:
the read is correct under `pipefail` and correct whenever the last stage is
the one meant, and *which* the author wants is not in the command string, so
no lexical instrument can decide it.
Its note already names both remedies with concrete rewrites --- `rc=$?` before
the pipe, and `${PIPESTATUS[0]}` --- along with the `SIGPIPE` reason not to
reach for `pipefail` first.
So both earlier questions hold and the residue is question 3, which is the
class limit above rather than something this hook can fix.
The mechanism is owned by
[`errexit-is-not-uniform`](../shared/coding/errexit-is-not-uniform.md)'s "A
pipe discards the status of everything left of it"; the separate `&&`-chain
shape the guard does not reach is recorded there and tracked separately.)

---

## 5. Adding & Modifying Hooks: Checklist

When authoring a new hook:
1. Place the implementation script in `hooks/<name>.py` (or `.sh`).
2. Add comprehensive unit tests in `hooks/test-<name>.py`.
3. Register the hook in [`hooks/hooks.json`](../hooks/hooks.json) under the correct event and matcher.
4. Add a row to the README hooks table in [`README.md`](../README.md#enforcement-hooks-hooks).
   The row's matcher list must equal the `hooks.json` groups for that script joined by `, `, in file order:
   `check-hook-catalog.py` concatenates the groups as it meets them and compares the string, so `(Agent, Task, Workflow)` fails against a manifest that lists `Task` before `Agent`.
   Write the manifest first, then copy its order into the row (measured 2026-09-01, ai-config#2930).
   An alternation matcher such as `Write|Edit|NotebookEdit` is ONE group, so it occupies one item of that list;
   its pipes must be backslash-escaped in the README cell (`Write\|Edit\|NotebookEdit`), because a bare `|` ends a markdown table cell.
   A bare pipe makes the row fail to parse at all, which surfaces as the unrelated-sounding "registered but undocumented" failure rather than as a row-syntax complaint (ai-config#2535).
5. Update this catalog in [`memories/hooks.md`](hooks.md).
6. Validate with:
   ```bash
   python3 scripts/check-hook-catalog.py
   python3 scripts/check-hook-output-shape.py
   python3 scripts/test_hooks.py
   ```
