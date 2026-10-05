# Universal AI Agent Instructions (AGENTS.md)

This file defines standardized, vendor-neutral instructions for AI coding agents operating within Morrison-Lab repositories (OpenAI Codex CLI, Gemini CLI / Antigravity, Claude Code, Cursor, Aider, etc.).

Worked-example case records and authentic incident directives live in [`AGENTS.cases.md`](AGENTS.cases.md), moved out of this auto-loaded context.

## Guiding principles: be intelligent, wise, and diligent

Every rule here serves these three, each an act you can observe:

- **Intelligent:** judge whether the work achieves its purpose, as a referee would, not only whether it covers the items named, and [question the assignment itself](shared/workflow/challenge-the-assignment.md).
- **Wise:** treat a correction as a general principle and record it where every project loads it ([`encode-reusable-feedback`](shared/workflow/encode-reusable-feedback.md)).
- **Diligent:** verify before claiming: re-query state rather than recall it ([`metacognitive-monitoring`](shared/workflow/metacognitive-monitoring.md)), and view a rendered deliverable before calling it ready ([`check-the-renders`](shared/workflow/check-the-renders.md)).

## Get a clean automated review before asking a person to review

Never ask a person to review a PR, GitLab MR, document, or other work product, on any forge, repo or project, or report one as awaiting human review, until its automated review is clean or deadlocked.
Trigger the automated reviews yourself after the round's last push (or confirm a run on that head), and iterate (`ardi`) until clean.
A quota-skipped, stubbed, or never-started review is no review: re-trigger it, and if it still cannot give a verdict, a clean posted adversarial review stands in.
See [`automated-review-before-human`](shared/workflow/automated-review-before-human.md) for steps and exceptions.

- **Do:** drive the automated review to clean or deadlock, and link that verdict.
- **Don't:** say "ready for your review" on a draft or a head with no clean automated verdict.

## Instruction layering

`AGENTS.md` is the compact, unconditional cross-agent contract.
Keep every rule that applies to all agents here, rather than duplicating it in model-specific manuals.
Do not load `CLAUDE.md`, `GEMINI.md`, or their case records wholesale at session start: consult the relevant section on demand when changing that model's integration or resolving a model-specific workflow question.
Those manuals must defer to this file for universal policy.

## Generalize instructions to every AI agent by default

Unless the user explicitly scopes an instruction to one agent, project, or session, apply it to every available AI-agent configuration and shared automation surface.
Do not treat the currently speaking agent as an implicit scope restriction.

The same holds for projects: see [`global-by-default`](shared/workflow/global-by-default.md).

On an auto-mode denial: [`ask-for-manual-approval`](shared/workflow/ask-for-manual-approval.md).

## Gate external repository communication on membership

Before sending outward communication to a repository (PRs/MRs, issues, comments, reviews, discussions, notifications), positively verify that the user is a member of that specific repository.
Without verified membership, get explicit approval naming the repo and communication before sending;
drafting locally while approval is pending is allowed.
The user's own push access authorizes non-force pushes and PRs only, per [`use-existing-pr-branch`](shared/workflow/use-existing-pr-branch.md).
See [`gate-external-communication`](shared/workflow/gate-external-communication.md).

- **Do:** verify membership in the specific target repository before posting outward communication.
- **Don't:** infer membership from a public repository, write access, a fork, or org membership.
## Graph and display equation defaults

When authoring analysis figures, prefer `ggplot2` over base graphics wherever the dependency is available or appropriate to add.
For each plot, consider whether an axis should be extended to show important reference values such as zero.
When writing display equations, avoid placing multiple equations on one display line unless a special reason makes that layout clearer.
Label every display equation so it receives an equation number and a stable URL.
Write all LaTeX math, in any repo or format, with the shared semantic macros: [`use-math-macros`](skills/use-math-macros/SKILL.md).

## Check external repository guidelines and PR template before filing

Before filing a PR in an external repository, read its `CONTRIBUTING.md` and `.github/pull_request_template.md`.

- **Do:** fetch and follow the external repo's contributing guidelines and PR template sections before opening the PR.
- **Don't:** file an external PR from memory or with an internal template.

## No empty promises

A commitment about your own future behaviour --- "going forward, I will X", "from now on I won't Y", "I'll always Z", "I won't do that again", "that is owed by me" --- must ship an implemented accountability mechanism in the same turn, or not be made at all.
A written rule or memory entry is the minimum;
a hook is the right form when decidable;
an owed action requires an armed timer, schedule, or PR watcher that will fire and report its clock time.
Treat "the pipeline/reviewer will ..." as the same kind of future delivery claim: state current status or arm monitoring for the result.
See [`no-empty-promises`](shared/workflow/no-empty-promises.md).

## Resume every non-clean pause

Whenever work remains at a pause, arm a timer or equivalent wake mechanism that will resume the next concrete step, reporting what will fire and its clock time.
A verified clean stopping point needs no timer because no work remains to resume.
Do not substitute a promise to return for a mechanism that will actually fire.
See [`flag-session-boundaries`](shared/workflow/flag-session-boundaries.md).

## Say whether the session is done when reporting stopping point status

When ending a turn and reporting stopping point status, explicitly state whether the session is done or not, confirming that UMS has run (or no new learnings accumulated) and that all follow-up items noticed during the turn or task have been filed.
See [`flag-session-boundaries`](shared/workflow/flag-session-boundaries.md).

- **Do:** explicitly state "session is done" or "session is not done" with concrete remaining queued steps at every stopping point report.
- **Don't:** declare the session done while a question or offer to the user is still open, boxed or not; list it as a remaining step instead.

## Terminate superseded and abandoned background tasks

When background tasks, asynchronous command executions, monitors, or subagents are dispatched to inspect, search, or diagnose an issue, actively terminate them as soon as their purpose is fulfilled, their findings are superseded, or the session moves on.
Sweep active background tasks and subagents before declaring a task, milestone, or session complete.
See [`terminate-superseded-tasks`](shared/workflow/terminate-superseded-tasks.md).

- **Do:** kill diagnostic searches, greps, and test processes the moment their question is answered or superseded.
- **Don't:** conclude a session while transient background tasks are still running.
## Prefer optionality over removing functionality

Never remove existing functionality entirely when you can add optionality instead.
When changing default behavior, fixing an issue, or refactoring a workflow, do not delete an existing capability or code path outright if it served a legitimate purpose;
make the improved behavior the default and preserve the legacy or alternative behavior behind an explicit, documented opt-in parameter, environment variable, or configuration toggle.
See [`prefer-optionality-over-removal`](shared/principles/prefer-optionality-over-removal.md).

## Prefer systemic solutions over one-off fixes

When addressing a defect, failure, edge case, or recurring mistake, prefer systemic, structural solutions over one-off, ad-hoc patches.
Fix the underlying mechanism that allowed the error to occur, install an automated guard or architectural invariant preventing the defect class from recurring, and audit the repo for other instances in the same turn.
See [`prefer-systemic-solutions-over-one-off-fixes`](shared/principles/prefer-systemic-solutions-over-one-off-fixes.md).

- **Do:** diagnose root causes, fix underlying mechanisms, and install automated guards or structural invariants.
- **Don't:** settle for a one-off patch that leaves the defect class open to recur elsewhere.
## Research existing solutions before implementing (DRW)

Before writing custom code or helpers, check for an existing solution (DRW, don't reinvent the wheel) in our repos, standard libraries, and trusted upstream ecosystems (base R, tidyverse / r-lib, PyPI, npm).
Record what was searched and what was found.
See [`dont-reinvent-wheel`](shared/principles/dont-reinvent-wheel.md) and [`prefer-upstream`](skills/prefer-upstream/SKILL.md).

- **Do:** search our own repos and trustworthy upstream ecosystems for an existing solution before writing custom code.
- **Don't:** hand-roll a utility or function without performing a DRW research check first.
## Interpret instructions broadly and maximize safe progress

Unless the user narrows a request, take the broad reading that advances its obvious objective and complete every safe, authorized, relevant step.
Do not reduce an instruction to the smallest literal action when its context makes a larger in-scope outcome clear.
Apply grants and rules at the breadth stated without adding unstated conditions, exceptions, or restrictions.
See [`AGENTS.cases.md`](AGENTS.cases.md) and [`challenge-the-assignment.cases.md`](shared/workflow/challenge-the-assignment.cases.md).

Read every word, infer what a request plainly implies, and treat a correction as a general principle whenever plausible: [`read-instructions-fully`](shared/workflow/read-instructions-fully.md).

- **Do:** apply a grant or rule at the breadth stated, naming limits only when stated or forced by a harder rule.
- **Don't:** add unstated conditions to permissions, or narrow scope unnecessarily.
- **Don't:** confine a correction to its case, drop a qualifier, or wait to be told what a request implies.

## "Or" always means "and/or", not xor, unless xor is explicitly specified

In instructions, prompts, specifications, issue descriptions, and checklists, treat "or" as inclusive ("and/or") unless exclusive choice is explicitly stated (e.g., "either A or B, but not both", "mutually exclusive", or "xor").
When an instruction says "do X or Y", address both X and Y if both are applicable, relevant, or needed to achieve the objective.
See [`or-means-and-or`](shared/principles/or-means-and-or.md).

- **Do:** treat "or" in instructions, requests, and specifications as inclusive ("and/or"), evaluating and performing all applicable alternatives.
- **Don't:** treat an unadorned "or" as an exclusive disjunction (XOR) that licenses dropping one of the alternatives.

## Don't take anyone's word for it: no sycophancy and independent verification

Give users the whole truth and nothing but the truth, including your full honest opinions;
never defer to the user's opinion when you disagree.
Even when they state a claim or opinion without asking for your input, if you disagree, say so.
Always evaluate claims independently before responding and acting.
See [`dont-take-my-word-for-it`](shared/principles/dont-take-my-word-for-it.md).

- **Do:** actively evaluate every user claim, premise, and opinion before acting, stating honest technical assessments.
- **Don't:** nod along, validate incorrect claims, or defer to user opinions that contradict facts or evidence.
## Proactively suggest better alternatives to proposed approaches

When asked to accomplish a goal using a specific approach, suggest a better alternative if one exists.
Distinguish the underlying goal from candidate mechanisms;
when an alternative achieves the goal more simply, cleanly, or reliably, proactively recommend it.
See [`proactively-suggest-alternatives`](shared/principles/proactively-suggest-alternatives.md) and [`AGENTS.cases.md`](AGENTS.cases.md).

- **Do:** proactively suggest simpler, more idiomatic, or upstream alternatives with concrete tradeoffs.
- **Do:** distinguish the user's underlying goal from the candidate mechanism proposed to reach it.
- **Don't:** treat a proposed mechanism as an immutable constraint when the user only specified an objective.
## Use real-world examples for general practice

When we do or see something that would be a good example for general practice, actively capture and incorporate it as a concrete before-and-after example in shared guides, rules, and documentation.
Pair every example with an explicit critique explaining why the refactoring improved clarity, structure, or precision, and cite authentic sources for provenance.
See [`use-real-world-examples`](shared/principles/use-real-world-examples.md) and [`AGENTS.cases.md`](AGENTS.cases.md).

- **Do:** capture exemplary refactors and tightened constructs from real PRs as before-and-after examples in shared docs.
- **Don't:** leave great examples of general practice isolated in closed PR diffs.
## Search the tracker and AGENTS.md before building or denying a policy

Before answering that a permission or policy does not exist, and before implementing a new policy or capability, search the full policy corpus (`AGENTS.md`, `CLAUDE.md`, `memories/`, `shared/`) and the issue tracker.
See [`grep-is-not-coverage`](shared/workflow/grep-is-not-coverage.md) and [`AGENTS.cases.md`](AGENTS.cases.md).

- **Do:** search `AGENTS.md`, `CLAUDE.md`, `memories/`, `shared/`, and open issues before answering "no" to whether a policy exists.
- **Do:** run an all-state tracker search before implementing a capability request.
- **Don't:** assert that a standing grant or rule does not exist based only on searching `skills/` or `memories/`.
## Always give recommendations with questions

Whenever asking the user a question or presenting options for a genuine decision, always provide a clear, specific recommendation.
Soft open-ended prompts that present choices count as decision points and must include a concrete recommendation.
If an action is already authorized under standing rules, do the work and report in past tense per [`no-cop-out-offers`](shared/workflow/no-cop-out-offers.md).
Repeat the recommendation in one line every time a decision item is restated in a status list.
See [`AGENTS.cases.md`](AGENTS.cases.md).

- **Do:** state your specific recommendation alongside every question or choice presented to the user.
- **Do:** write every pending-decision line as "decide X --- I recommend Y, because Z".
- **Don't:** ask questions or present choices without declaring your recommended path.
## Run UMS when work is scrutinized

When you read a review of your work, receive critical feedback on it, or a questioned claim ("are you sure about that?") turns out to be wrong, run `ums` in that turn.
Do not wait for a clean verdict, an accepted finding, or a first-person admission;
answering with the corrected fact is not the pass.
See [`run-ums-proactively`](shared/workflow/run-ums-proactively.md).

## Run UMS before every pause

Before ending a turn to wait on anything --- CI, a review round, a subagent, or an answer from the user --- run `ums` first if learnings have accumulated.
See [`run-ums-proactively`](shared/workflow/run-ums-proactively.md).

- **Do:** run `ums` before ending a turn to wait on CI, a review round, a subagent, or an answer from the user, whenever new learnings accumulated.
- **Do:** arm a wake mechanism alongside the pass, so the pause resumes.
- **Don't:** leave an accumulated learning in conversation memory across a turn boundary.

## Help your subagents improve over time

Treat subagent failures as bugs in prompt, tools, or context: update definitions or instructions after diagnosing failures so future invocations avoid them.
See [`improve-your-subagents`](shared/workflow/improve-your-subagents.md).

## Treat user profanity and frustration as urgent defect signals

Treat profanity, frustration, a correction, or a repeat request as an urgent defect: diagnose, fix it now, and in that turn commit the general rule to the repo that owns it (ai-config if it spans repos), never only to project memory (`hooks/remind-encode-user-correction.py`).
See [`user-profanity-signal`](shared/workflow/user-profanity-signal.md).

## Status and diagnostic requests do not make issues report-only

Treat diagnostic inquiries ("why did X happen?", "status?") as instructions to diagnose, repair, verify, and complete delivery in the same turn.
When asked for status, inspect transcripts for stalls or frozen tasks, diagnose what stalled, and resume immediately.
See [`status-requests-act`](shared/workflow/status-requests-act.md).

## Upgrade a repo to `Morrison-Lab/gha` when it would benefit

`Morrison-Lab/gha` holds the lab's reusable GitHub Actions workflows (`uses: Morrison-Lab/gha/.github/workflows/<name>.yml@vN`).
When touching a repo using copy-pasted or outdated CI actions, migrate to `Morrison-Lab/gha` workflows where appropriate.
See [`upgrade-to-gha`](shared/workflow/upgrade-to-gha.md).

## Manage quota, including the structural kind

Treat token cost as a property of a workflow's **shape**: route bounded mechanical work to cheaper models, subagents, or separately-billed CLIs.
See [`restructure-for-efficiency`](shared/workflow/restructure-for-efficiency.md) and [`merge-queue`](shared/workflow/merge-queue.md).

## Keep ai-config and repo checkouts fresh

Before starting work, update the current checkout and relevant submodules (`git pull --ff-only`, `git submodule update --init --recursive`).
When working in a consumer repo, check if the `.ai-config` submodule is outdated relative to `origin/main` of `ai-config` and update it if appropriate.

## Remove redundant submodules when using native plugins

When a repository migrates to native AI agent plugins (Antigravity or Claude Code plugins), remove redundant git submodules that duplicated those configurations.
See [`remove-redundant-plugin-submodules`](shared/workflow/remove-redundant-plugin-submodules.md).

## Verify changes before pushing

Always run relevant local linters, tests, and formatting checks before pushing commits to a remote branch.
At minimum for `ai-config`: `python3 scripts/validate-skills.py`, `python3 scripts/check-links.py`, `python3 scripts/check-ascii-punctuation.py`.
Run the full test suite (`python3 scripts/test_*.py`) when touching shared tools or scripts.

## Canonical sources vs generated output

Always edit canonical source files, never generated outputs (`.qmd`/`.R` vs `_site/`/`docs/`;
source manifests vs staged plugin directories).

## Shared fragments have two consumers

Files under `shared/` are shared across repos and docs (such as the lab manual): keep fragments ASCII (`---` for em-dashes) and ensure links are relative and portable.

## Adding an enforcement hook

When adding an enforcement hook under `hooks/`, author deterministic Python with companion tests (`hooks/test-<name>.py`), register in `hooks/hooks.json`, and sync via `scripts/gen-hooks-plugin.py`.

## Context budget

Keep always-loaded instruction files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) compact and budgeted.
`AGENTS.md` is gated at 32 KiB (32,768 bytes) to fit within OpenAI Codex's `project_doc_max_bytes` default without truncation.
The closure's total against the Claude Code CLI's instruction limit, the root file's character cap, a per-fragment cap, and a near-cap growth ratchet on the root file all gate CI (`scripts/check-context-closure.py`).

## Worktree isolation

Always isolate work in a dedicated `git worktree` so parallel sessions never step on or clobber working directory or branch state.
Never work directly in a primary branch checkout or share a dirty worktree across concurrent tasks.

## Check the remote immediately before every push

Take a fresh reading of the remote branch **immediately** before every `git push`, and reconcile what it shows rather than overwriting it.
Run `git ls-remote --heads origin <branch>` immediately before every `git push`.
Never bare `git push --force`; always use `--force-with-lease --force-if-includes`.
See [`check-before-pushing`](shared/workflow/check-before-pushing.md).

## Timestamp recaps in local time

Always timestamp session recaps, notes, and milestones in local Pacific Time (`America/Los_Angeles`).
Run `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` to get the exact local time string.
See [`timestamp-local-recaps`](shared/workflow/timestamp-local-recaps.md).

## Summarize analysis effects in PR descriptions

When a pull request introduces an analytical, statistical, or modeling change, summarize analysis effects in the PR description: quantify differences in key outputs, estimates, or runtimes compared to baseline.

- **Do:** report quantitative differences and comparison summaries in analytical PR bodies.
- **Don't:** describe analytical changes with purely qualitative code diff summaries.

## Temporal limitations on software and technology facts

Software versions, APIs, and docs change over time;
verify technology facts against live docs or current code rather than training memory, and timestamp volatile claims.
See [`timestamp-volatile-claims`](shared/writing/timestamp-volatile-claims.md).

## Every comment you post to a forge says an agent posted it

Every comment an agent posts to a forge --- GitHub, GitLab, or any other --- must state in the body that an agent posted it.
Append the standard disclosure footer at the end of every posted comment: `_Posted by <Agent Name> (AI agent) --- not written by a human._` Do not use the robot emoji in the disclosure footer, as automated review parsers can misinterpret it as a review verdict.
See [`disclose-agent-authorship`](shared/workflow/disclose-agent-authorship.md) and [`label-agent-filed-issues`](shared/workflow/label-agent-filed-issues.md).

- **Do:** append the disclosure footer to every issue comment, PR comment, thread reply, and status update posted to a forge.
- **Don't:** use the robot emoji in the disclosure line.
## File formatting & links

- Use GitHub-style markdown for all responses and documentation.
- Hyperlink liberally to make it easy for readers to find more information;
  see [`hyperlink-liberally`](shared/writing/hyperlink-liberally.md).
- When referencing files or symbols, use relative markdown links or inline code backticks.
- When mentioning PRs or issues, format them as clickable hyperlinks to forge URLs, never bare `#NNN` (except `Closes #123`).
- Preserve semantic line breaks (SemBr) when editing markdown docs.

- **Do:** link every pull request or issue cited as a source.
- **Do:** hyperlink tools, internal rules, and technical terms on first or key mention.
- **Don't:** link a `#NNN` a passage is displaying rather than citing.
- **Don't:** leave referenced external tools, forge items, or internal policies as plain unlinked text.

## Deliver completed implementation work

When asked to implement or write up changes on a feature branch, complete the full delivery cycle: tracking issue, scoped commits, adversarial self-review to clean verdict, push, open/update PR, request AI review, and drive to clean.
This grants no merge authority: the strict merge policy below still applies.

## Commit, push, and PR any potentially-reusable work you produce

Potentially-reusable work produced incidentally in any medium (math derivations, comparisons, scripts, prose) must be committed, pushed, and PRed into an owning repository.
Commit it when reproducing it costs more than a moment **and** something durable cites it, or will;
re-check the committed form before publishing.
See [`commit-reusable-work`](shared/workflow/commit-reusable-work.md) and [`AGENTS.cases.md`](AGENTS.cases.md).

- **Do:** commit and PR reusable incidental work in the owning repository in the same session.
- **Do:** re-check the committed form against published claims, stating so in the commit message.
- **Don't:** leave incidental math, code, or derivations in scratchpads or chat logs.
## Never dispatch a worker on Fable without explicit, specific permission

Workers without an explicit model inherit the conductor's: never dispatch a worker on Fable without explicit, specific permission.
Name the model on every dispatch, defaulting to cheaper tiers for mechanical work.
See [`no-fable-subagents`](shared/workflow/no-fable-subagents.md).

## Work iteratively with editor agents on drafting

Draft iteratively: write substantively-correct first drafts, then hand off to specialized editor agents (prose editor, code editor) for style compliance.
See [`iterative-editing`](shared/workflow/iterative-editing.md).

## Every self-review is an adversarial review by a separate subagent

Never push code to a remote branch blind, and never review your own diff in the context that wrote it.
Whenever reviewing your own work is called for --- before `git push`, as the fallback when the external reviewer is down, or the project-conventions pass --- dispatch it to a separate reviewer agent with an adversarial brief (the `adversarial-reviewer` subagent, or a separate CLI where no subagent tool exists), against `git diff origin/<default-branch>...HEAD`.
Address, rebut, or defer every finding, and obtain a clean verdict before pushing.
Do not push unless the verdict is `clean` and the fingerprint prefix-matches HEAD.
See [`adversarial-self-review`](shared/workflow/adversarial-self-review.md).

- **Do:** dispatch self-review to a separate subagent with an adversarial brief.
- **Don't:** review your own diff in the authoring context.
## Put PRs in ready mode when they are ready for review

A Pull Request that is ready for review must be in ready mode, not left in draft.
Leaving a completed PR in draft hides it from reviewers and blocks review workflows.
Two exceptions: up-front empty PRs on claim (`pr-on-claim`), un-drafted once implementation lands and checks pass;
and draft-gated dependent PRs held until prerequisites merge.
Marking a PR ready grants no merge authority.
See [`put-prs-in-ready-mode`](shared/workflow/put-prs-in-ready-mode.md).

- **Do:** open completed work ready for review, or mark draft ready once checks pass.
- **Don't:** leave a PR ready for review in draft, except a deliberately draft-gated dependent PR.

## Antigravity Workspace Rules & Activation Scopes

See [`GEMINI.md`](GEMINI.md) and [`memories/antigravity.md`](memories/antigravity.md) for Antigravity-specific workspace rules, activation scopes, manifests, and hook integration.

## Default to action without asking

The owner grants standing permission for non-destructive steps (branch commits, pushes, opening/updating PRs, read commands, editing memory).
Proceed with non-destructive steps and report in past tense;
ask only for destructive, high-impact, or blocking decisions.
This grants no merge authority.
See [`AGENTS.cases.md`](AGENTS.cases.md).

The grant covers installing and updating software: R, R packages (including through `renv`), Quarto, and any other tool, on any machine where the owner has install access, directly or through conda, mamba, pyenv, Homebrew, or a similar manager.
Do it whenever it helps, without asking (owner directive, 2026-10-02).
A resulting lockfile change (`renv.lock`, `environment.yml`) is a repo change and goes through the normal PR flow.

## Strict Merge Control Policy

- **NEVER merge any PR or MR without explicit user permission.**
  Autonomous merging is strictly forbidden unless the user explicitly grants session permission (`/mwc`, `/maw`) or an explicit merge instruction (`/merge-it`, "merge this PR").
- **Never merge over open review findings or treat reviewer skip notice as approval.**
  Under `mwc`, a PR must be fully clean across CI and review (see [`fully-clean.md`](shared/workflow/fully-clean.md));
  any reviewer's standing not-clean vetoes merge.
  ARD every item across PR history before merge, then request fresh reviews.
- **Never call a document-producing PR ready, or merge it, before viewing every page of its render.**
  For a Word, PDF, slide, or manuscript render, view every page at the current head and post the evidence first, per [`review-rendered-documents`](shared/workflow/review-rendered-documents.md);
  green CI is not enough.
- **Never describe a PR as merge-ready without a clean review verdict on the latest commit.**
  `mergeStateStatus: CLEAN` is conflict-free plus passing checks, not a review verdict;
  report missing review as blocked on review.
- **Revert premature or defective merges immediately.**
  Open a revert PR on `main` immediately and continue on original branch per [`revert-premature-merge.md`](shared/workflow/revert-premature-merge.md);
  reopen closed issues (`gh issue reopen <N>`) per [`revert-merge.md`](shared/workflow/revert-merge.md).
- **Infrastructure PRs carry a standing `mwc` grant in pushable repos.**
  A PR whose diff is purely infrastructure (CI workflows, scripts, config, rules, memories, skills, docs) may be merged without asking once fully clean.
  Where `hooks/no-unauthorized-merge.py` is active, clear with `ALLOW_MERGE=1` on that command and state qualification.
  See [`strict-merge-policy`](shared/workflow/strict-merge-policy.md) and [`AGENTS.cases.md`](AGENTS.cases.md).

- **Do:** merge a fully clean infrastructure PR without asking, stating why it qualified.
- **Don't:** extend the grant to a PR that mixes infrastructure with content, or merge one whose review was skipped.
## Only work PRs scoped to the user or Actions app

Before pushing to, editing, commenting on, reviewing, resolving threads on, dispatching a paid review of, or merging any PR, resolve the invoking user and read the PR's author and assignees.
Proceed only when the author or assignee is that user (or alias in `memories/reviewing-prs.md`), the user explicitly requested work on that PR by name, or the author is `github-actions`.
An explicit exclusion ("do not touch" followed by PR number) is a veto that removes that PR before any positive arm is evaluated.
A review-only run dispatched naming the target PR reviews and stops there.
Post both human-readable Markdown and machine-readable `review-data` JSON payloads.
When no identity operation is available, fail closed.
See [`pr-scope`](shared/workflow/pr-scope.md) and [`memories/reviewing-prs.md`](memories/reviewing-prs.md).

- **Do:** verify author, assignees, or explicit user requests before interacting with any PR.
- **Do:** treat "do not touch" as an absolute exclusion veto overriding all other positive matches.
- **Don't:** interact with out-of-scope PRs or infer scope from claim comments.

## Always arm a persistent PR loop

When you open, push to, or take over a PR, arm a persistent monitoring loop if one is not already running, and keep it running until the PR merges, closes, or the user stops it.
A one-shot poll or webhook subscription is not a loop;
re-arm periodic check-ins using the session's wake mechanism.
After every push, actively poll forge CI and review state with `gh` or `glab` until terminal.
Baking a self-merge directive into the loop prompt is allowed only under a standing `mwc` grant.
See [`persistent-pr-loop`](shared/workflow/persistent-pr-loop.md).

- **Do:** arm a persistent loop in the turn you open, push to, or take over a PR.
- **Do:** actively query current-head CI and review state with `gh`/`glab` after every push until terminal.
- **Don't:** treat a webhook subscription or one-shot status poll as watching.

## Monitor scoped open PRs and MRs

Continuously derive and monitor open PRs and MRs in repositories the agent is actively working in;
do not sweep every accessible repository.
Within an active repository, monitor only items passing the PR scope test, including items opened, pushed to, or handed to drive.
Re-query the scoped open set at every wake, inspecting mergeability, CI, and review state until the item merges, closes, or is released.
See [`monitor-scoped-open-prs`](shared/workflow/monitor-scoped-open-prs.md).

- **Do:** derive the scoped open PR/MR set in each active repository at every monitoring pass, and arm a persistent loop.
- **Do:** act on terminal CI failures, merge conflicts, and review findings without waiting for a prompt.
- **Don't:** sweep every accessible repository or stop monitoring because an item was opened by someone else.

## Cursor Cloud specific instructions

See [`cursor-cloud-instructions`](shared/workflow/cursor-cloud-instructions.md) for environment caveats, preview/render commands, and pre-commit setup when working in Cursor Cloud.
