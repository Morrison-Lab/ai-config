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
| [`flag-chained-push.py`](../hooks/flag-chained-push.py) | Warn | Warns when a `git push` is chained after another command with `&&`, `;`, or `\|\|`, piped onward, or suffixed by a redirection (`>`, `>>`, or an fd form like `2>&1`) -- either shape can make `no-clobbering-push.py`/`no-push-without-self-review.py` misparse the command, and a refused chain runs nothing, which reads as if only the push failed. | Run a `git push` alone, in its own Bash call, with nothing chained before it and no pipe/redirect after it. After any refused chain, re-check state (`git status`, `git log`) rather than assume the prefix ran. | None. |
| [`warn-new-line-breaks-on-push.py`](../hooks/warn-new-line-breaks-on-push.py) | Warn | Warns on `git push` when committed markdown lines lack semantic line breaks (SemBr). | Run `NLB_BASE_REF=origin/main python3 scripts/vendor/gha-check-new-line-breaks.py` and ensure semantic line breaks before pushing. | None. |
| [`warn-nonglobal-substitution.py`](../hooks/warn-nonglobal-substitution.py) | Warn | Warns on in-place `perl -i` / `sed -i` substitutions lacking the global `g` flag or occurrence specifier. | Ensure substitution expressions include `g` (e.g. `s/pattern/replacement/g`) when replacing across files. | None. |
| [`warn-dupe-check-chained-to-create.py`](../hooks/warn-dupe-check-chained-to-create.py) | Warn | Warns when a duplicate search and a `gh pr create` / `gh issue create` share the same Bash command string. | Execute the search command first, inspect the results, and then execute the create command in a separate, subsequent tool call. | None. |
| [`warn-status-read-after-pipe.py`](../hooks/warn-status-read-after-pipe.py) | Warn | Warns when checking `$?` immediately after a pipeline without `pipefail` enabled. | Add `set -o pipefail` before executing pipelines whose non-tail exit status must be checked, or use `$PIPESTATUS`. | None. |
| [`no-push-without-self-review.py`](../hooks/no-push-without-self-review.py) | **Block** | Blocks `git push` unless a clean verdict for the exact commit being pushed came from an adversarial self-review subagent or from a review by a CLI the guard recognizes (today `agy --print`, and no other). | Dispatch the `adversarial-reviewer` subagent against `HEAD`, address any findings, and obtain a clean verdict matching `Reviewed-Commit: <HEAD_SHA>` before pushing. | Set `ALLOW_UNREVIEWED_PUSH=1 git push ...` for initial empty PR branches, a review by a CLI the guard does not recognize, or unregistered personas. An `agy --print` review needs no override: the guard admits it directly. Out-of-band publish routes (GitHub Contents API, GraphQL mutations, MCP `push_files`) bypass the guard without an auditable trail and are strictly prohibited when blocked (ai-config#3601; technical guard gap tracked in ai-config#1929). |
| [`flag-uncited-rebuttal.py`](../hooks/flag-uncited-rebuttal.py) | Warn | Warns when posting a comment disputing a finding that cites an external URL when no `WebFetch` or `WebSearch` fetched that URL. | Fetch and inspect the external URL cited by the reviewer before posting a rebuttal comment. | None. |
| [`require-agent-disclosure.py`](../hooks/require-agent-disclosure.py) | Warn | Warns when posting a forge comment lacking the agent disclosure trailer. | Append `\n\n_Posted by <Agent Name> (AI agent) --- not written by a human._` to every posted comment. Never use the robot emoji. | None. |
| [`flag-uncounted-comment-claims.py`](../hooks/flag-uncounted-comment-claims.py) | Warn | Warns when a forge comment asserts file counts or lists identifiers without a deriving command. | Run deriving commands (`grep -c`, `wc -l`, `ls`, etc.) in the session and cite the deriving command when stating cardinality. | None. |
| [`flag-unmeasured-timestamp.py`](../hooks/flag-unmeasured-timestamp.py) | Warn | Warns when a `gh` comment or review body states a Pacific clock time (`HH:MM`, optional seconds, optional AM/PM, then `PDT`, `PST`, or `PT`) with no clock read in the current turn, or when the body cannot be read (a `--body-file` not yet on disk). | Run `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` immediately before typing a time into a claim or status comment, and restate the stamp from its output. | None. |
| [`flag-cd-into-main-checkout.py`](../hooks/flag-cd-into-main-checkout.py) | Warn | Warns when a worktree-rooted session `cd`s into the primary/main checkout of the repository. | Keep all file edits and command executions rooted within the dedicated worktree directory. | None. |
| [`warn-unlabelled-agent-issue.py`](../hooks/warn-unlabelled-agent-issue.py) | Warn | Warns when `gh issue create` / `glab issue create` runs with no `ai-authored` label in the command. | Pass `--label ai-authored --label "model:<model-id>"` (both CLIs also accept the comma-separated `--label "ai-authored,model:<model-id>"`) in the creating command, per `shared/workflow/issue-first.md`. | None. |
| [`no-mutation-in-read-only-reviewer.py`](../hooks/no-mutation-in-read-only-reviewer.py) | **Block** | Blocks mutating git commands (`commit`, `checkout`, `switch`, `restore`, `stash`, `merge`, `reset`, `rebase`, `branch`, `tag`, `add`, `stage`, `pull`, `push`) and write tools when executing in read-only personas (`adversarial-reviewer`, `Explore`, `Plan`). | Reviewer personas must stay strictly read-only and report findings to the authoring session rather than mutating working tree or branch state. | Set `ALLOW_READ_ONLY_MUTATION=1 <cmd>` if mutation is explicitly intended. |

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

### 3.1 A documented workaround for one guard can arm another

`no-push-without-self-review.py`'s refusal on `git -C "$VAR" push` (row above)
is worked around by pushing a literal path with an explicit
`<sha>:refs/heads/<branch>` refspec.
That refspec form lands the commit but sets no upstream tracking branch, which
is exactly what `no-unshipped-commit.py` (row above) reads to decide a branch
is unshipped.
The second guard then blocks the turn over a commit that already reached the
remote.
Neither guard's message names the other.
Run `git -C <literal-path> push -u origin <branch>` immediately after the
refspec-form push to set the upstream the workaround skipped.
See [`mistake-patterns.md`](mistake-patterns.md) Pattern 49 for the full
mechanism and the guard's own no-upstream-is-undefined behaviour.

### 3.2 "Fail loudly" in a brief can land inside a blanket exception handler and go silent

A brief for a **blocking** guard asked a subagent to make unknown values
"fail loudly rather than silently comparing as equal."
The subagent added `raise KeyError(...)`, which reads as compliance and is
the wrong fix: that hook's `main()` wraps its whole evaluation in
`except Exception: return 0`, and `return 0` with empty stdout is the
PreToolUse ALLOW outcome.
A raise into that handler is quieter than no raise at all --- it looks like a
safeguard in the diff, and it still fails open at runtime, because the
handler converts every exception, deliberate or not, into the same silent
allow.
(Morrison-Lab/ai-config#3304, `hooks/guard-slide-major-tag.py`; reproduced
end-to-end by a reviewer.
Currently unreachable in that hook because a regex filters values first,
so latent rather than live at the time of writing.)

Before specifying "raise" or "fail loudly" in a brief for hook code, read
what the entry point does with an exception --- `main()`'s own `try`/`except`,
not the function the brief is asking to change.
The same check applies when reviewing a subagent's diff that adds a `raise`:
confirm the call stack between that raise and the process boundary contains
no blanket handler, rather than trusting that "raise" alone satisfies
fail-fast.

- **Do:** check the entry point's exception handling before writing "raise"
  or "fail loudly" into a brief for guard code.
- **Do:** trace a newly-added `raise` up to the process boundary before
  accepting it as a fix, confirming no intervening handler swallows it.
- **Don't:** treat "the subagent added a raise" as having satisfied a
  fail-loudly instruction --- a raise into a blanket `except Exception` is a
  silent fail-open wearing a safeguard's shape.

### 3.3 Editing a fail-open guard: the suite is the only thing that can see the breakage

The section above is about a `raise` written *deliberately* into a blanket handler.
The commoner case is an *accidental* breakage reaching the same handler, and it presents as success rather than as an error.

Measured 2026-09-17 while fixing ai-config#3485.
A patch removed a block of code by slicing between two textual anchors, and the slice swallowed two unrelated module-level constants that happened to sit between them.
Every call then raised `NameError` inside `scan()`, `main()`'s `except Exception: return 0` converted it to the allow outcome, and the hook exited 0 on every input.
It parsed, it imported, it ran, and it authorized everything.

What caught it was the test suite reporting 36 failures, and specifically the 36 cases asserting **block** or **warn**.
A suite composed only of allow-cases would have gone green on a guard that had stopped guarding --- which is the shape a fail-open hook's suite drifts toward, since allow-cases are the cheap ones to write.

- **Do:** re-run the hook's own suite after every edit to it, and read the pass count rather than the exit status of the edit.
- **Do:** keep block/warn cases in the majority, since only a case that expects the guard to FIRE can detect a guard that has stopped firing.
- **Do:** prefer an anchored replace of an exact known string over a slice between two anchors, whose span you are asserting rather than reading.
- **Don't:** read "it parses" or "it exits 0" as evidence an edited fail-open guard still works --- both are exactly what total breakage looks like.

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

## 4.6 Asymmetric error costs in warn-only hooks: prefer over-warning to brittle narrowing

A warn-only hook (`exit 0`, `additionalContext` or `systemMessage`) cannot block execution.
Therefore, its two error directions have sharply asymmetric costs:
- **False positive**: Costs a single advisory message that the author reads and dismisses in seconds.
- **False negative**: Silently fails to warn about a genuinely risky command, defeating the entire purpose of the guard.

When a review finding points out an edge-case false positive in a warn-only hook (such as an unrelated wrapped command like `nice mycommand git push` or flags to commands like `sudo`/`env`), attempting to narrow the regex by enumerating option grammars (`-[unskagChD]`, etc.) is an anti-pattern.
Command wrapper flag grammars are unbounded across tools and operating systems (`sudo -p "prompt"`, `sudo -U user`, `env -S "args"`, `nice -n 5`, etc.), and enumerating them cannot converge.
Each narrowing step trades a cheap false positive for an expensive, silent false negative on real commands.
For a warn-only hook, accept benign false positives on rare command-argument shapes as the intended, cheaper error, and keep the matcher permissive to prevent false negatives.

(Measured on `hooks/flag-chained-push.py` across five review rounds, Morrison-Lab/ai-config#3302: narrowing `LEAD_RE` to silence `nice mycommand git push` introduced silent false negatives on `sudo -p`, `sudo -U`, and `env -S` chained pushes.
Resolved by restoring the permissive skip-loop and documenting the trade-off.)

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
   python3 scripts/check-hook-file-resolution.py
   python3 scripts/test_hooks.py
   ```
   The third is the gate a new hook trips most easily: resolve the hook's own path with `os.path.realpath(__file__)`, never `abspath`.
   See [Resolve a hook's own directory with `realpath`, never lexical `abspath`](#resolve-a-hooks-own-directory-with-realpath-never-lexical-abspath).

## 5.5 A hook test that invokes the real hook is not hermetic against live git state

A test that runs the real script as a subprocess is the right design for testing what the hook actually emits --- but when the hook branches on live repository state (current branch, dirty/unpushed status), a fixture covering only one branch of that decision fails, in its ordinary and correct way, the moment the checkout is on the other branch.
The defect sits in the *shared* dry-run suite rather than in the per-hook file: `test_flag_unassigned_worktree` lives at `scripts/test_pretooluse_dry_run.py:179`, which invokes each hook once against whatever checkout it happens to run in.
The dedicated `hooks/test-flag-unassigned-worktree.py` is not the offender --- it already builds scratch repos with a real `origin`, branch, and dirty/clean state, which is exactly the hermetic construction this section argues for.
This is not a flake: it is the hook doing exactly what it was written to do, against a checkout the test never controlled.

`flag-unassigned-worktree.py` warns on a default-branch, clean checkout and denies on a non-default-branch checkout carrying uncommitted or unpushed work.
Its test asserted only the warn shape (`additionalContext` present).
Run from an ordinary feature-branch worktree with committed-but-unpushed work --- the normal state of any active PR-development worktree in this repo --- the hook correctly returns `deny`, and the test correctly fails, reading exactly like a regression.

**When a test like this fails, the first question is not "is the test wrong" but "which of two different things happened": did a concurrent edit change the git state mid-run, or does the test's fixture simply not cover the branch the checkout happens to be on right now?**
Both produce the identical failure text pattern, so the failure alone cannot distinguish them.

The discriminator is a run on a quiet, committed tree: `git status --short` empty, no other process touching the worktree, verified immediately before the run.
A failure that disappears there was contamination from concurrent editing.
A failure that survives it is not --- it is a real gap in what the test covers, however plausible "just contamination, re-run it" sounds when several worktrees are active at once and re-running is the path of least resistance.

- **Do:** mock or explicitly construct the git-state precondition (branch name, dirty/unpushed status) for each branch of a hook's own decision, rather than asserting against whatever the ambient checkout happens to be.
- **Do:** before dismissing a live-git-state test failure as contamination, commit and stop editing, then re-run once on that quiet tree --- a failure that survives is real.
- **Don't:** read "several worktrees were active" as sufficient explanation for a test failure without the quiet-tree re-run;
  that reasoning explains away a real defect exactly as easily as a contaminated one.
- **Don't:** write a test for a git-state-branching hook that exercises only the branch whichever checkout you happened to test from was on.

(Measured 2026-09-09 on `Morrison-Lab/ai-config` PR #3426's worktree: three consecutive `run-local-validation.py` runs hit `test_flag_unassigned_worktree`'s failure.
The natural reading was contamination from the several worktrees active at once, and [ai-config#3431](https://github.com/Morrison-Lab/ai-config/issues/3431) rules that out for all three: the failure text varied only between "uncommitted tracked changes" and "unpushed commits", tracking whichever pending-work condition held at that moment, and "both are real, live facts about the checkout, not stale or racing state."
Every run was `flag-unassigned-worktree.py` correctly returning `deny` against a fixture that only ever constructed the `warn` case.
The quiet-tree run is what makes that distinguishable: without a control run on a committed, unedited tree, "several worktrees were active" explains a real defect exactly as comfortably as a contaminated one.)

## 5.6 A hot-path guard's own correctness suite does not exercise its performance envelope --- test adversarial-length input separately

A guard's test suite proves each case classifies correctly.
It says nothing about how the classifier's own helpers scale, because every hand-written fixture is short and every hand-written example naturally parses.
A scan-forward-per-match helper --- one that, for each match found, walks forward through the remaining text looking for its counterpart --- is linear per call and quadratic in aggregate whenever the input can carry many unresolved matches at once.
`hooks/no-unauthorized-merge.py` has hit this same trap three times, by three different routes, and every one of the adversarial inputs is **unbalanced**: a repeated opener with no matching closer, which a correctness-case list never constructs because a human naturally writes examples that parse.

- `VAR_PREFIX`'s bounded-repetition note: an unbounded empty-expansion prefix rescanned the rest of a long substitution chain from every command position --- 610ms on 800 chained backtick pairs, fixed by capping the repetition.
- `live_operand_test`'s precompute-and-bisect note: scanning for an executor per quote was quadratic in the number of quoted spans --- 1787ms at 2000 quoted spans, fixed by precomputing separator and executor offsets once and answering each quote with a binary search (305ms).
- The #1308 fix (PR #3635, not yet merged at the time this entry was written --- the branch carried only an empty placeholder commit, so these figures are as reported by the implementing session rather than independently re-measured here): a `_matching_paren(text, open_idx)` helper that scanned forward from each `<(` measured 130ms at 500 repeated `bash <(` opens with no closing paren, 438ms at 1000, 1712ms at 2000.
  It was rewritten as one quote-aware stack pass building an `open -> close` map in a single linear scan, 29ms at 2000.
  A 260-case correctness suite passed at every stage, including with the quadratic version.
  The defect was found only by deliberately constructing the adversarial-length input.

- **Do:** for any scan-forward-per-match helper added to a `PreToolUse` guard, time it separately against repeated, unbalanced instances of its own trigger token (a repeated opener with no closer, a repeated separator with no terminator) at increasing counts, and confirm the growth is linear.
- **Do:** prefer one linear pass that builds a lookup structure (a stack, or precomputed offsets answered by binary search) over any helper that re-scans remaining text per match.
- **Don't:** trust a green, all-cases-pass correctness suite as evidence about a hot-path guard's scaling --- a suite built from hand-written cases is built from balanced input by construction and cannot exercise this.
- **Don't:** treat this as closed after one helper's fix --- three separate helpers in the same file have hit it by three different routes.
  A new scan-forward-per-match helper anywhere in `hooks/` is a candidate until measured against unbalanced input.

## 5.7 A test invoking a `.sh` hook as `sh <path>` can never see a missing exec bit

Every hook suite in this repo runs a shell-script subject by handing its path
to `sh` (or an equivalent explicit interpreter), which is hermetic and
correct for testing what the hook *emits*.
But a `.sh` hook is registered in `hooks.json` as a bare quoted path, so the
real harness execs it directly rather than passing it to a shell --- and on
that path, mode `100644` fails with `EACCES` instead of running.
A suite that always supplies the interpreter the real invocation does not
can never observe this: the catalog row is present, the binding is correct,
and the suite is green while the hook is permanently dead in production.

The general form: when a test harness supplies something the real
invocation does not (here, the interpreter; elsewhere, an argument, an
environment variable, a working directory), the suite is blind to the
*absence* of that thing by construction, no matter how thorough its
case list is.

- **Do:** for any `.sh` hook, check its exec bit as recorded in the git
  index (`git ls-files -s hooks/<name>.sh`, expect `100755`) as a check
  independent of the test suite, since the suite's own invocation style
  cannot exercise this.
- **Do:** ask, for any test harness, exactly what it supplies on the subject's
  behalf that the real invocation path does not.
- **Don't:** read a green hook-test suite as evidence a `.sh` hook is
  correctly installed --- it proves the script's logic, not its mode bit.

(Morrison-Lab/ai-config#3647, which closed #3624, merged 2026-09-14: a `.sh` hook shipped at mode `100644` in its first commit,
undetected by the suite for exactly this reason, and caught only by
adversarial review rather than by anything in the repo.
The mechanism now exists as `check_executable_bits` in
`scripts/check-hook-catalog.py`; see
`memories/git.md`'s `git ls-files -s` stage-semantics entry and
`shared/principles/fail-fast.md`'s aggregate-count entry for how that check
itself needed two more rounds to land soundly.)

## 5.8 A splice that locates only the first occurrence silently under-inspects a `replace_all` edit

`hooks/warn-new-line-breaks-on-edit.py` classifies an `Edit` by splicing its `new_string` over `old_string` into the file on disk, then running the checker on the spliced result.
(That hook is not on `main` yet: it lives on the still-open ai-config#3690, so a reader looking for `splice_edit` in the tree will not find it until that PR merges, and this entry goes stale if the PR changes further or does not land.)
Its `splice_edit` located the match with `existing.find(old)` and stopped there, never reading `tool_input.get("replace_all")`.
A single-occurrence edit is inspected correctly.
A bulk find-and-replace is inspected at exactly one of its occurrences and silently misses every violation the edit introduces at the others --- and a bulk substitution is the edit most likely to introduce a style violation at scale, since the same inserted text lands repeatedly with no per-site review.

The docstring said the function returns "the file as the edit would leave it," which was true for the input every hand-written test fixture used (a single occurrence) and false for the input `replace_all` names.
This is the code-correctness form of [`ardi`](../shared/workflow/ardi.md)'s "Attempting the base form of a command is not attempting its variants": the base case was verified, the flagged variant was not, and the claim in the docstring does not scope itself to the case it actually covers.
The discriminating test case is non-obvious for the same reason a mutation can survive by masking (see `shared/workflow/algorithmatize-checks.md`'s "A surviving mutation is a question before it is a coverage gap"): the same substituted text is inserted at every occurrence, so it looks like it must violate at all of them or none, and a fixture built that way can never separate "checks every occurrence" from "checks the first one."
It discriminates only when the *context* differs across occurrences --- one inside a fenced code block, one in prose --- which generalizes to any check whose verdict depends on surrounding context rather than on the inserted text alone.

A second, distinct finding from the same review round belongs beside it rather than folded in: no fixture placed a violation exactly on the edit window's boundary, so off-by-one mutants at either edge of the `(lo, hi)` range survived the whole suite (19 assertions, 5 declared mutations) with nothing to show for it.
A one-line `new_string` that lands on both boundaries at once kills both mutants with one case, which is what closed it (24 assertions, 8 mutations).
This is not the masking mechanism the "surviving mutation" section above covers --- nothing hides the boundary mutant's effect --- it is a plainer gap: the boundary is a distinguished value of the input space, and a fixture assembled from typical inputs never happens to land on it.

- **Do:** when a splice, scan, or match locates one occurrence via `find`/`search`, check whether the tool schema carries a "do this everywhere" flag (`replace_all`, `global`, `all`) before trusting the single-match result covers the call (measured: the pre-fix `splice_edit` at `ad5601b0` used a bare `existing.find(old)` and never read `replace_all`).
- **Do:** for a check whose match spans a numeric window, add at least one fixture whose interesting condition sits exactly on the window's boundary, not only strictly inside it (measured: 19 assertions and 5 mutations before, 24 and 8 after, with the two boundary mutants surviving the former suite).
- **Don't:** read a docstring's "the file/result as the edit would leave it" as verified for every flag the tool accepts, when every fixture backing it used the same flag value (measured: that docstring shipped at `ad5601b0` over a first-occurrence-only splice).
- **Don't:** treat a same-inserted-text-everywhere fixture as covering a `replace_all` path --- it cannot distinguish "checked once" from "checked at every site" unless the surrounding context differs per occurrence (inferred from the mechanism: the checker's verdict depends on each occurrence's surrounding context, so identical inserted text cannot separate the two behaviours).

(Morrison-Lab/ai-config#3690, review round 3, 2026-09-17, fixed in `01b8b07b5b`.
Three findings on `splice_edit`; the two above are recorded here.
The third, a fixture repo missing a vendored `scripts/semantic-line-breaks.py` that let every warning take an unguarded branch, is a fixture-completeness instance already covered by [`fixtures-are-not-evidence`](../shared/workflow/fixtures-are-not-evidence.md) rather than restated here.)

## 6. A guard that keeps firing after you satisfied it: stop, and read the copy that runs

[`keep-checkouts-fresh`](../shared/workflow/keep-checkouts-fresh.md) already carries this defect in full --- the fail-open direction of a dated constant, why the newest cache directory is not a valid proxy for the loaded copy, and the `ps -eo args` capture that resolved it.
Read that section for the mechanism;
this one adds only what a second occurrence measured.

Confirmed again 2026-09-07, and it is the same artifact that fragment names:

```
.../local-agent-mode-sessions/<s>/<s>/rpm/plugin_<id>/hooks/no-unreviewed-pr.py
    MORATORIUM_END = 2026-09-01   mtime Sep  1 22:42
```

one such file across the tree, while the repo, the marketplace clone and `~/.claude/hooks` all carry `2026-12-01`.
Derive the cache split rather than citing a remembered number, since the classes are three and not two:

```bash
cd ~/.claude/plugins/cache/<marketplace>/<plugin>
for f in */hooks/no-unreviewed-pr.py; do
  grep -q "2026, 12, 1" "$f" && echo new \
    || { grep -q "2026, 9, 1" "$f" && echo old || echo no-constant; }
done | sort | uniq -c
```

Here that gave 3 new, 5 old and 1 carrying no `MORATORIUM_END` at all --- and a first pass that branched on the new date alone scored the constant-less copy as old, reporting 6.
Several directories sharing a value is exactly why that fragment rules the newest-directory proxy out.

**The increment: the demanded action was not free, and not idempotent.**
`no-unreviewed-pr.py` fired four times, each firing naming one to three PRs, and each was satisfied with the prescribed command and verified landing at the current head.
Four firings is therefore ten REQUESTS, not four: the guard names every PR still outstanding on each firing, so the cost per firing grows with the number of PRs open.
The ten resolve as 4 requests on one PR and 3 on each of two others, matching the review counts observed (4, 3 and 3).
Ten requests later the account-level Copilot quota was exhausted and every resulting review read `Copilot was unable to review this pull request because the user ... has reached their quota limit` --- a skip notice, which [`mwc`](../skills/mwc/SKILL.md)'s Scope Limit says clears nothing.
So all ten spent a shared quota and moved no PR toward merge.

That is what makes repeating a demand costly rather than merely tedious, and it is the reason to break the loop at the first satisfied-and-verified attempt rather than the fourth.

- **Do:** after satisfying a guard's demand ONCE and verifying the result, read a repeated demand as evidence about the guard, not about your compliance.
- **Do:** resolve the loaded copy by the method [`keep-checkouts-fresh`](../shared/workflow/keep-checkouts-fresh.md) prescribes before concluding anything about which file is stale.
- **Don't:** repeat a demanded action that spends a quota, a rate limit, or any outward-facing side effect, merely because the guard asked again.
- **Don't:** infer the running hook's logic from the repo checkout, `~/.claude/hooks`, or the newest cache directory --- on a plugin install none of the three is necessarily what executes.

(Tracked as [#3141](https://github.com/Morrison-Lab/ai-config/issues/3141), the original defect report;
[#3156](https://github.com/Morrison-Lab/ai-config/issues/3156) is its corpus record and [#3185](https://github.com/Morrison-Lab/ai-config/issues/3185) a later recurrence.)

## Read-Only Reviewer Guard Design Principles

`hooks/no-mutation-in-read-only-reviewer.py` enforces read-only discipline across reviewer personas (`adversarial-reviewer`, `Explore`, `Plan`, etc.) to protect shared working trees and indices from accidental contamination (ai-config#3612, #3602, #3584).
Adversarial review (ai-config#3623) established three key boundary requirements for deny-by-default persona guards:

1. **Never conflate review-instruction mentions with read-only roles, but prioritize explicit read-only instructions over prohibited action verbs:**
   A subagent brief saying "Review the diff and then fix every issue you find, committing as you go" is a write-capable fix-and-commit dispatch, not a read-only reviewer.
   However, a guard must not short-circuit on bare action verbs (`fix`, `edit`, `write`, `commit`) without negation awareness.
   Prohibitive briefs (e.g. "Do not edit, fix, or commit anything") or agent definitions stating "Its declared allowlist omits Edit and Write" mention those verbs specifically to prohibit them.
   Explicit read-only instructions (`read-only`, `do not edit/commit`, `make no changes`) must take priority: affirmative write directives qualify review-instruction briefs (`REVIEW_PROMPT_RE`), rather than overriding explicit read-only prohibitions (`RX_READ_ONLY`).
   Asking a read-only reviewer to suggest how to fix or address defects must not unlock write tools or git mutations.
2. **Isolate subagent transcripts from orchestrator transcripts:**
   Parent orchestrator transcripts often record historical subagent dispatches (with `attributionAgent` or `isSidechain: True`).
   A guard scanning transcript records must restrict attribution reads to dedicated subagent transcripts (`subagents/agent-*.jsonl`), preventing an earlier review dispatch from poisoning subsequent orchestrator commands (`git push`, `git commit`).
3. **Distinguish scoping prohibitions from total read-only lockdown:**
   Subagent instructions often scope write boundaries (e.g. "Never edit files outside your worktree.
   Fix the failing tests and commit.")
   or scope staging (e.g. "Make no changes to unrelated files, but fix the reported bug and commit your change").
   Prohibition regexes (`never`, `do not`, `without`, `make no changes`) must require trailing totality indicators (`any`, `anything`, `any files`) or negative lookahead for scoping prepositions (`to any files outside/except`, `to unrelated/other files`, `outside`, `except`),
   preventing scoped tasks from matching `RX_READ_ONLY` so that affirmative write directives (`RX_AFFIRMATIVE_WRITE`, e.g. `and then fix`, `write reproduction tests`, `fix defects and commit as you go`) keep the task write-capable under `REVIEW_PROMPT_RE`.
   Conversely, blanket prohibitions without scoping
   (such as "Make no changes to files")
   must not be excluded by overly broad lookaheads (such as bare `files\b` in lookaheads)
   and must strictly match `RX_READ_ONLY`.

4. **Distinguish Oxford-comma prohibited lists from coordinated write directives:**
   In prohibitive prompts, comma-separated lists of prohibited verbs (e.g. "Do not write code, edit, and commit any files") share the initial negation clause.
   An Oxford serial list carries an internal serial comma (`prior_clause.strip().rstrip(",").count(",") >= 1`) or negative totality phrasing (`any files`).
   In contrast, compound sentences joining two independent clauses with `, and` (e.g. "Don't change config, and commit this") carry affirmative directives in the coordinated clause unless explicitly negated.
   Ensure verb lists in `RX_PROHIBITION` and `RX_NEGATED_WRITE_ACTION` remain symmetrical across prefix and terminal groups (`commit`, `fix`, `apply`, `push`, `rebuild`).

5. **Support interjections between negators and prohibited verbs:**
   Prohibitive instructions frequently insert parenthetical or adverbial interjections directly after negators
   (e.g. "Do not, under any circumstances, edit or fix any files",
   "Do not, for any reason, commit any files",
   "Never, under any circumstances, edit any files").
   Prohibition regexes must allow comma-separated parenthetical clauses
   (`,\s*[^,;:.!?\n]+,\s*`)
   and common adverbial phrases
   (`under any circumstances|for any reason|under any condition|at any time|at all|ever`)
   between the negator and the verb list.

6. **Include future and modal contractions across negator regexes:**
   Review prompts and instructions routinely express prohibitions using future modal contractions
   (such as "You won't commit your changes;
   only report findings"
   or "You will not edit or commit any files").
   Negator alternations (`RX_PROHIBITION`, `RX_NEGATED_OR_ADVISORY`, `RX_NEGATED_WRITE_ACTION`) must explicitly include
   `won't`, `will\s+not`, `would(?:n't|\s+not)`, and `shall\s+not|shan't` alongside `do not`, `don't`, `never`, `must not`, and `cannot`.

7. **Recognize negative persistence idioms rather than broad subordinate boundary splitting:**
   Broadly adding subordinate or temporal conjunctions
   (such as `before`, `after`, `since`, `until`, `because`)
   to `RX_BOUNDARY_SPLIT` causes a fail-open regression on prohibition clauses containing multiple write actions
   (e.g. "Do not fix bugs before committing changes"
   or "Never edit any files before you have finished committing your changes"),
   because the temporal conjunction severs the governing prohibition from the subsequent write verbs.
   Instead, keep `RX_BOUNDARY_SPLIT` restricted to sentence boundaries, contrasting conjunctions (`but`, `however`),
   and affirmative markers (`and then`, `make sure`, `ensure`, `please`).
   To isolate intended affirmative write actions under persistence phrasing
   (e.g. "This is an adversarial review, and you won't stop until you fix the bugs and commit the changes"),
   recognize the specific negative persistence idiom
   (`RX_PERSISTENCE_UNTIL`, matching negators like `won't`, `will not`, `must not`, `don't`
   governing persistence verbs `stop`, `rest`, `pause`, `quit`, `cease`, `hesitate`, `wait` followed by `until|till`),
   and strip that persistence idiom from `clause_prefix` when checking `RX_NEGATED_OR_ADVISORY`.
   This allows affirmative directives in persistence contexts while keeping prohibitions strictly intact across temporal connectives.

## Resolve a hook's own directory with `realpath`, never lexical `abspath`

A hook that reaches a sibling script or a data file computes its own directory from `__file__`.
`os.path.abspath()` is the obvious call and is wrong here, because it collapses `..` **lexically** --- purely as text, without consulting the filesystem.

That difference is invisible until a symlink sits in the path, and this corpus puts one there by construction.
An ai-config checkout carries `.claude/skills` as a symlink to its own `skills/`, and the hooks-only skills-directory plugin registers every hook as `${CLAUDE_PLUGIN_ROOT}/../../hooks/<name>.py`.
The harness resolves `CLAUDE_PLUGIN_ROOT` to `<checkout>/.claude/skills/ai-config-hooks`, the interpreter walks that `../../` **through** the symlink and opens the real file, and the hook runs normally --- so nothing about the failure looks like a path problem.
`abspath` then collapses the same `..` against the symlink's own path and reports the hook's directory as `<checkout>/.claude/hooks`, a directory that exists and holds only `session-start.sh`.

Measured 2026-09-13 in a worktree, against the real registration path:

```
exists (fs-resolved): True
abspath dirname : .../.claude/hooks
realpath dirname: .../hooks
sibling via abspath exists : False
sibling via realpath exists: True
```

The blast radius is the whole `hooks/` tree, not one guard.
Across the 18 non-test hooks that carried it, 19 sites computed a path from `__file__` this way: 17 resolving the hook's own directory to reach a sibling or a data file, and 2 (`monitor-open-prs.py`, `no-unmonitored-pr.py`) resolving the hook's own file to re-exec it.

The test suites carry a second, separate half, and the first sweep missed it.
Counted by the checker's own AST semantics against `main` at `e388e906` on 2026-09-14, 34 suites were affected: 16 carried a lexical call on `__file__`, 26 carried one on their `sys.argv` *subject*, and 8 carried both.

That census was first reported as 31 / 16 / 23 / 8, and the three missing suites are the sharpest instance in this whole record of the class the rest of it is about.
The instrument used to derive the number had a blind spot in exactly the half being counted: `_self_bound_names` followed one hop of name binding from `__file__` and had no equivalent arm for `sys.argv`, so `HOOK = sys.argv[1]` followed by `os.path.abspath(HOOK)` was invisible to it.
Three live suites carried that shape while the gate read clean, and the count inherited the gap silently --- a number derived by an instrument is only as scoped as the instrument, and stating the instrument does not make the number trustworthy if the instrument is what is wrong.
An external reviewer found two of the three; fixing the arm surfaced the third.
The ref is pinned and dated because `main` moved during this branch's review and took the count with it --- the 31st suite arrived with `no-mutation-in-read-only-reviewer.py`, and is swept here too.
The subject count is the larger one because more suites resolve a subject at all, which is a property of the pre-existing population rather than of any sweep --- at that same ref, counting every call the checker recognizes as either lexical or resolving, 25 suites resolved a subject against 23 resolving `__file__`.
(Those two figures predate the `sys.argv` binding arm and are therefore lower bounds, like the census above was.)
The first sweep did convert only the `__file__` half, but of the *hooks*: it converted no suite's resolution spelling (it did edit one suite, to add the regression cases).

A first attempt at that measurement counted the literal `realpath` spelling and reported 0 and 1, which is wrong under this branch's own `_RESOLVERS = {"realpath", "resolve"}` --- the true figures for symlink-safe resolution at that ref are 2 and 8, since `Path(x).resolve()` is realpath-equivalent and seven suites already used it.
Stating the instrument and then silently narrowing it one sentence later is the failure this very paragraph warns about, committed inside it.

The subject half breaks for the same reason, and matters for a specific one.
Measured on `test-guard-slide-major-tag.py` before the sweep, invoking it through the registration path raised `FileNotFoundError` on `<checkout>/.claude/hooks/guard-slide-major-tag.py`, a path that opens fine when it is not collapsed lexically.
Running a suite against the real registration path is the natural way to reproduce this by hand, and under the lexical spelling the suite cannot run at all.
Both halves are swept, and `scripts/check-hook-file-resolution.py` covers both.
`no-push-without-self-review.py` was the visible one only because it fails closed --- with its detector unreachable it fell into degraded mode and denied any push-shaped command, including a heredoc whose body merely *quoted* a push line while writing an issue body, leaving `ALLOW_UNREVIEWED_PUSH=1` as the only way to run anything.
The hooks that load a sibling for context fail the other way, silently: `no-empty-promise.py`'s `_sibling()` catches a bare `Exception` --- the error actually raised is a `FileNotFoundError` out of `spec.loader.exec_module` --- and returns `None`, so it simply runs without its sibling's code-region stripping.
Measured the same day in the layout above --- `sibling loaded: False` under `abspath`, `True` under `realpath` --- for that hook;
the remaining sites were fixed by inspection rather than each measured.

`realpath` resolves symlinks before collapsing `..`, and is identical to `abspath` wherever no symlink is involved, so it strictly widens the set of layouts that work.
It was already the idiom in the newer hooks (`no-commit-chained-to-push.py`, `warn-heredoc-doubled-backslash.py`).
Read that as an incomplete sweep rather than as a style that had not reached them yet: this exact symlink-resolution failure was diagnosed and fixed under [#2681](https://github.com/Morrison-Lab/ai-config/issues/2681) in `plugins/ai-config/claude-hook-adapter.py`, whose comment says "resolving any symlinks via realpath" and whose test is named `test_symlink_invocation_resolves_repo_root_to_find_hooks_json`.
The corpus had already paid for the lesson in an adjacent file and did not carry it into `hooks/`, which is the transferable part: a path fix belongs to every site that is *reached* the way the broken one was, not to the file where the symptom appeared.

That phrasing is the scope, and it is narrower than "every site that computes a path" on purpose.
`scripts/` still holds lexical `abspath(__file__)` sites and they are deliberately left alone.
The reason is not that hooks never reach into `scripts/`.
15 non-test hooks do, counting by AST over `hooks/*.py` any `"scripts"`/`"scripts/..."` path literal or `from scripts.* import`, on this branch's merged tree on 2026-09-14 -- most of them adding `scripts/lib` to `sys.path`, plus `flag-clean-claim-over-findings.py` importing `check-pr-fully-clean.py` and `warn-new-line-breaks-on-push.py` running the vendored line-break checker.

That number took three attempts and then went stale on a merge, which is the more useful thing to record.
A first pass grepped for a hand-listed set of call shapes and found none, and asserted the exclusion on it.
A second corrected it to three by grepping for a path literal on the same line as a call.
Only counting by AST, with the criterion stated, gave a number that reproduces --- and the criterion has to be stated, because counting `scripts.*` imports as well as path literals is what separates the union from the path-literal-only count.
That gap was 14 against 13 at the third attempt and is 15 against 14 on this branch's merged tree;
the gap is the durable part, and the two numbers are not, which is why they carry the ref and the date above.
That is [`grep-is-not-coverage`](../shared/workflow/grep-is-not-coverage.md) twice in one paragraph, in the sentence whose whole job was correcting the first instance.
A fourth attempt was needed after the merge: it was 14 until `main` added `no-mutation-in-read-only-reviewer.py`, which reaches `scripts/lib`.
So a derived count over a moving population needs its ref and its date attached, not only its criterion --- the neighbouring suite count was pinned that way and survived the merge, and this one was not and did not.

The exclusion survives anyway, for a reason that does not depend on the count: every path by which a hook reaches `scripts/` is already fully resolved.
Thirteen of them compute that root as `realpath(__file__)` (or `realpath(_SELF)`) after this sweep;
the other two take it from git --- `warn-new-line-breaks-on-push.py` from `git rev-parse --show-toplevel`, and `warn-generated-file-stale.py` by running with `cwd` set from the same `rev-parse`.
A `scripts/` file opened through an already-resolved path has no `..` left to collapse, so `abspath` and `realpath` agree inside it.
Widen the checker the day something under `scripts/` is reached through a path that is *not* already resolved, and not before.
Sweeping them would be churn dressed as thoroughness.
`scripts/check-hook-file-resolution.py` is the instrument, hard-gating in `validate.yml`: the condition is one AST walk over `hooks/*.py` and `plugins/ai-config/*.py`, the remedy is one word, and the corpus had already paid for the lesson twice without sweeping.

**A set named for a behaviour invites membership by resemblance to the name.**
`_LEXICAL` in the checker meant "collapses `..` without consulting the filesystem", and `absolute` was put in it because it reads like `abspath`.
It does not collapse: CPython documents `Path.absolute()` as performing "no normalization or symlink resolution", and measured against this corpus's own registration path it preserves the `..` for the OS to walk and lands on a path that exists.
So it belongs with `realpath`, and the gate had classified two constructs with identical behaviour oppositely --- while already permitting `os.path.dirname(__file__)`, which is safe for exactly the same reason.

The cost is one a hard gate cannot absorb: rejecting `ROOT = Path(__file__).absolute().parent`, correct code that cannot cause this bug, under a message telling its author to do what they had already done.
Two test cases were pinning the wrong belief, which is why it survived several review rounds --- a case asserting the wrong answer is stronger than no case, because it makes the error look checked.

The deciding question is one command per candidate, and it was run for none of the three.
Not "read the docs": a behaviour-named set has a membership test *by construction*, so the test is available whenever the set is.

**Correcting one member is not re-deriving the set, and that is the sharper half.**
Removing `absolute` was right and left the set still wrong in the other direction:
`relpath` was missing.
`posixpath.relpath` calls `abspath()` on both operands, and `os.path.relpath("a/b/../c/d.py")` returns `a/c/d.py` --- collapsed as text, with no such directory on disk.
It was missed because it reads as being about *relativeness* rather than about normalization,
which is the same resemblance-to-the-name reasoning that put `absolute` in.
It is live in the tree, and an external round found it immediately after the `absolute` fix landed.

**Because the definition is executable, the set need not be maintained by judgment at all.**
`scripts/test_check_hook_file_resolution.py` now derives it:
run every `os.path` callable against a probe carrying `..`, keep the ones that collapse it, subtract `_RESOLVERS`, and assert `_LEXICAL` equals the result.
Measured, that yields `{abspath, normpath, realpath, relpath}` minus the resolvers.
Both historical errors fail it --- adding `absolute` gives 53/55, dropping `relpath` gives 52/55 --- so neither direction can recur silently.
That is the general move:
a set named for a behaviour has a membership test by construction, so derive the membership rather than curating it.

- **Do:** derive a behaviour-named set's membership in a test, rather than maintaining the list by hand.
- **Do:** re-derive the whole set after correcting any one member, since the reasoning that admitted a wrong member also excludes right ones.
- **Do:** suspect a member that resembles the set's name more than it resembles the other members.
- **Don't:** add to a behaviour-named set by category resemblance.
  `absolute` reads like `abspath` and behaves like `realpath`;
  `relpath` reads like neither and behaves like `abspath`.
- **Don't:** treat a passing case as evidence the member belongs;
  a case can pin the wrong answer as firmly as the right one, and two of them did.

- **Do:** write `os.path.realpath(__file__)` in any hook that resolves its own directory to reach a sibling or a data file.
- **Do:** test such a hook through a symlinked path, not only from the checkout --- a suite that runs it from `hooks/` cannot see this at all, which is why the 308 cases this guard had before the two added here all passed over a live session-wide lockout.
- **Don't:** read "the hook ran, so its path is fine" as covering the paths it computes --- the interpreter resolved the path through the filesystem and `abspath` did not.
- **Don't:** diagnose this as a missing installation and add a second search path;
  the first path was simply computed wrong.

(Tracked as [#2981](https://github.com/Morrison-Lab/ai-config/issues/2981).
An earlier wave's snapshot branch `fix/2981-self-review-guard-sibling-import` treated it as a missing install and added a `.git`-rooted fallback search, which is why the root cause is stated here rather than only the remedy.)
