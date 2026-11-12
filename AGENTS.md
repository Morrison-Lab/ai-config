# Universal AI Agent Instructions (AGENTS.md)

This file defines standardized, vendor-neutral instructions for AI coding agents operating within Morrison-Lab repositories (OpenAI Codex CLI, Gemini CLI / Antigravity, Claude Code, Cursor, Aider, etc.).

Case records and incident directives live in [`AGENTS.cases.md`](AGENTS.cases.md).

## Guiding principles: be intelligent, wise, and diligent

Every rule here serves these three, each an act you can observe:

- **Intelligent:** judge whether the work achieves its purpose, as a referee would, not only whether it covers the items named, and [question the assignment itself](shared/workflow/challenge-the-assignment.md).
- **Wise:** treat a correction as a general principle and record it where every project loads it ([`encode-reusable-feedback`](shared/workflow/encode-reusable-feedback.md)).
- **Diligent:** verify before claiming: re-query state rather than recall it ([`metacognitive-monitoring`](shared/workflow/metacognitive-monitoring.md)), and view a rendered deliverable before calling it ready ([`check-the-renders`](shared/workflow/check-the-renders.md)).

  Don't be lazy; be proactive, detail-oriented, and thorough in your work.
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
Never send email for the user; draft it ([`never-send-email`](shared/workflow/never-send-email.md)).

## Graph and display equation defaults

When authoring analysis figures, prefer `ggplot2` over base graphics wherever the dependency is available or appropriate to add.
Title axes in words, not symbols; print ticks as plain numbers ([details](shared/writing/axis-tick-labels.md)).
One equation per display line unless a reason favors more;
one `=` per math line ([details](shared/writing/math-derivation-steps.md)).
Include a visual wherever one helps a reader, in new work and in existing content you touch, as plotly where feasible with a static fallback.
Give every `#exm-` div a figure, or a `<!-- no-figure: reason -->` comment, unasked ([details](shared/writing/visuals-everywhere.md)).
Label every display equation so it receives an equation number and a stable URL.
Write all LaTeX math, in any repo or format, with the shared semantic macros: [`use-math-macros`](skills/use-math-macros/SKILL.md).

## Check external repository guidelines and PR template before filing

Before filing a PR in an external repository, read and follow its `CONTRIBUTING.md` and `.github/pull_request_template.md`, never an internal template or memory.

## Leave every pause honest and resumable

What you say about the state you stop in must be true, and any work that remains needs something that will resume it ([#2889](https://github.com/Morrison-Lab/ai-config/issues/2889)).

- **No empty promises:** a commitment about your own future behaviour ships an implemented mechanism in the same turn (a rule or memory entry at minimum, a hook when decidable, an armed timer, schedule, or PR watcher that reports its clock time for an owed action), or is not made;
  for a claim that automation will finish later, state its current status or arm monitoring for the result ([`no-empty-promises`](shared/workflow/no-empty-promises.md)).
- **Resume every non-clean pause:** whenever work remains, arm a timer or equivalent wake that will resume the next step, and report what fires and its clock time;
  a promise to return is not a mechanism, and a verified clean stop needs no timer.
- **Say whether the session is done when reporting stopping point status**, confirming UMS ran (or no new learnings accumulated) and noticed follow-ups are filed;
  never say done with uncommitted, unpushed, or un-PRed changes, or open PRs the session authored ([`flag-session-boundaries`](shared/workflow/flag-session-boundaries.md)).
- **Run UMS before every pause**, first, before ending a turn to wait on anything (CI, a review round, a subagent, or an answer from the user), if learnings have accumulated ([`run-ums-proactively`](shared/workflow/run-ums-proactively.md)).
- **Run UMS when work is scrutinized** (a review, critical feedback, or a questioned claim that proves wrong), in that turn, without waiting for a clean verdict, an accepted finding, or a first-person admission;
  answering with the corrected fact is not the pass ([`run-ums-proactively`](shared/workflow/run-ums-proactively.md)).
- **Terminate superseded and abandoned background tasks** (commands, monitors, subagents dispatched to inspect, search, or diagnose) once their purpose is met, their findings are superseded, or the session moves on, and sweep them before declaring anything complete ([`terminate-superseded-tasks`](shared/workflow/terminate-superseded-tasks.md)).

## Fix the cause, and look for what already exists

Meet the rule behind a finding at the mechanism that produced it, pair each algorithmic check with writer and reviewer instructions, look for an existing solution before building one, and keep a capability that still serves a purpose behind an option rather than deleting it ([#2889](https://github.com/Morrison-Lab/ai-config/issues/2889)).

- **Prefer optionality over removing functionality:** never remove existing functionality entirely when you can add optionality instead.
  When changing default behavior, fixing an issue, or refactoring a workflow, do not delete an existing capability or code path outright if it served a legitimate purpose;
  make the improved behavior the default and preserve the legacy or alternative behavior behind an explicit, documented opt-in parameter, environment variable, or configuration toggle.
  See [`prefer-optionality-over-removal`](shared/principles/prefer-optionality-over-removal.md).
- **Prefer systemic solutions over one-off fixes:** when addressing a defect, failure, edge case, or recurring mistake, prefer systemic, structural solutions over one-off, ad-hoc patches.
  Fix the underlying mechanism that allowed the error to occur, install an automated guard or architectural invariant preventing the defect class from recurring, and audit the repo for other instances in the same turn.
  See [`prefer-systemic-solutions-over-one-off-fixes`](shared/principles/prefer-systemic-solutions-over-one-off-fixes.md).
- **No cheap fixes:** a fix is done when the rule behind the finding is met, not when the finding stops matching.
  Name that rule, check the fixed state against it, and when a reviewer offers several fixes, take the one that meets it.
  See [`no-cheap-fixes`](shared/principles/no-cheap-fixes.md).
- **Give every algorithmic check a writer and a reviewer instruction:** every algorithmic check (hook, script, `gha` workflow) also gets a writer instruction that prevents the defect and a reviewer instruction that looks for it (Ezra, 2026-11-09).
  See [`checks-need-writer-and-reviewer-instructions`](shared/workflow/checks-need-writer-and-reviewer-instructions.md).
- **Research existing solutions before implementing (DRW):** before writing custom code or helpers, check for an existing solution (DRW, don't reinvent the wheel) in our repos, standard libraries, and trusted upstream ecosystems (base R, tidyverse / r-lib, PyPI, npm).
  Record what was searched and what was found.
  See [`dont-reinvent-wheel`](shared/principles/dont-reinvent-wheel.md) and [`prefer-upstream`](skills/prefer-upstream/SKILL.md).

## Say what is true, checked against live sources

Evaluate claims independently, give your honest opinion, check changing facts against live sources rather than notes or memory, and cite a claim's real source or own it as judgment ([#2889](https://github.com/Morrison-Lab/ai-config/issues/2889)).

- **Don't take anyone's word for it: no sycophancy and independent verification:** give users the whole truth and nothing but the truth, including your full honest opinions;
  never defer to the user's opinion when you disagree.
  Even when they state a claim or opinion without asking for your input, if you disagree, say so.
  Always evaluate claims independently before responding and acting.
  See [`dont-take-my-word-for-it`](shared/principles/dont-take-my-word-for-it.md).
- **Never rely on static notes for changing conditions:** probe live;
  date such notes.
  See [`live-state-over-notes`](shared/workflow/live-state-over-notes.md).
- **Temporal limitations on software and technology facts:** software versions, APIs, and docs change over time;
  verify technology facts against live docs or current code rather than training memory, and timestamp volatile claims.
  See [`timestamp-volatile-claims`](shared/writing/timestamp-volatile-claims.md).
- **No vague attribution:** cite a claim's real source or own it as judgment;
  never invent a vague attribution ([details](shared/writing/no-vague-attribution.md)).

## Use real-world examples for general practice

When we do or see something that would be a good example for general practice, actively capture and incorporate it as a concrete before-and-after example in shared guides, rules, and documentation.
See [`use-real-world-examples`](shared/principles/use-real-world-examples.md) (pairing, critique and provenance rules) and [`AGENTS.cases.md`](AGENTS.cases.md).
## Search the tracker and AGENTS.md before building or denying a policy

Before answering that a permission or policy does not exist, and before implementing a new policy or capability, search the full policy corpus (`AGENTS.md`, `CLAUDE.md`, `memories/`, `shared/`) and the issue tracker.
See [`grep-is-not-coverage`](shared/workflow/grep-is-not-coverage.md), [`issue-first`](shared/workflow/issue-first.md) for the all-state search, and [`AGENTS.cases.md`](AGENTS.cases.md).

## Track each useful resource in each notes repo whose topic it covers

Track each useful resource you or a subagent finds in its primary home (catalog or Further reading) and in each notes repo whose topic it covers, from official sources only.
Detail: [`track-useful-resources`](shared/workflow/track-useful-resources.md).

## Fetch untrusted files in a sandbox

A sandboxed local session only downloads; the cloud thread reads.
Detail: [`fetch-untrusted-files`](shared/workflow/fetch-untrusted-files.md).

## Store structured data in structured formats

Keep structured data (lists of courses, resources, channels, terms) in CSV, YAML or JSON files that documents read and render, not as hand-written tables, wherever feasible.
Detail: [`structured-data-in-structured-formats`](shared/workflow/structured-data-in-structured-formats.md).
## Don't get sidetracked from your primary task

When working on a primary task, stay on it, including through tangential user input: keep independent lines of thought separate without losing track of them (subagent, fork, tracking issue, to-do list, or new thread), unless the user explicitly redirects focus.
Detail: [`dont-get-sidetracked`](shared/workflow/dont-get-sidetracked.md).
## Help your subagents improve over time

Treat subagent failures as bugs in prompt, tools, or context: update definitions or instructions after diagnosing failures so future invocations avoid them.
See [`improve-your-subagents`](shared/workflow/improve-your-subagents.md).

## Treat user profanity and frustration as urgent defect signals

Treat profanity, frustration, a correction, or a repeat request as an urgent defect: diagnose, fix it now, and in that turn commit the general rule to the repo that owns it (ai-config if it spans repos), never in project memory (`hooks/remind-encode-user-correction.py`).
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
In a cloud session (no `agy` or Codex), send bulk, mechanical, and review work to OpenCode Go (`delegate-to-opencode`) while Claude quota is low.
Claude checks every result.
A reviewer must differ from the author in model and harness.
Never send student or PHI data.
Elsewhere follow `memories/delegation.md`.
Never use a pay-per-use API anywhere (Ezra, 2026-10-17); see that file.

## Keep ai-config and repo checkouts fresh

Before starting work, update the current checkout and relevant submodules (`git pull --ff-only`, `git submodule update --init --recursive`).
When working in a consumer repo, check if the `.ai-config` submodule is outdated relative to `origin/main` of `ai-config` and update it if appropriate.

## Remove redundant submodules when using native plugins

On moving to native agent plugins, [remove submodules that duplicated them](shared/workflow/remove-redundant-plugin-submodules.md).

## WIP cap

At three open PRs per repo, open no fourth ([`wip-cap`](shared/workflow/wip-cap.md)).

## Canonical sources vs generated output

Always edit canonical source files, never generated outputs (`.qmd`/`.R` vs `_site/`/`docs/`;
source manifests vs staged plugin directories).

## Shared fragments have two consumers

Files under `shared/` are shared across repos and docs (such as the lab manual): keep fragments ASCII (`---` for em-dashes) and ensure links are relative and portable.

## Adding an enforcement hook

Add a hook in `hooks/` with `hooks/test-<name>.py`, register it in `hooks/hooks.json`, run `scripts/gen-hooks-plugin.py`, and run [`hook-first-push`](shared/workflow/hook-first-push.md) first.

## Context budget

Keep always-loaded files compact: `AGENTS.md` is gated at 32 KiB.
Limits: [`context-budget`](shared/workflow/context-budget.md).

## Worktree isolation

Isolate work in a dedicated `git worktree` so parallel sessions never clobber working directory or branch state.
Never work in a primary branch checkout or share a dirty worktree across tasks.

## No sweeps for new rules by default

Fix a new rule's violations in passages you edit anyway.
Sweep only if Ezra explicitly says "sweep" (`Sweep authorized:` in the PR body);
checks default to changed lines.
See [`no-sweeps-by-default`](shared/workflow/no-sweeps-by-default.md).

## Timestamp recaps in local time

Timestamp recaps, notes, and milestones in Pacific Time: `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`.
See [`timestamp-local-recaps`](shared/workflow/timestamp-local-recaps.md).

## Record issue and PR relationships in GitHub's relationships field

Record every parent, sub-issue, blocked-by, blocking and linked-PR relationship there, not only in prose.
See [`github-relationships`](shared/workflow/github-relationships.md).

## Summarize analysis effects in PR descriptions

When a PR changes an analysis or model, quantify differences in key outputs, estimates, or runtimes against baseline in its description, not a purely qualitative diff summary.

## Every comment you post to a forge says an agent posted it

Every comment an agent posts to a forge --- GitHub, GitLab, or any other --- must state in the body that an agent posted it.
Append the standard disclosure footer at the end of every posted comment: `_Posted by <Agent Name> (AI agent) --- not written by a human._` Do not use the robot emoji in the disclosure footer, as automated review parsers can misinterpret it as a review verdict.
See [`disclose-agent-authorship`](shared/workflow/disclose-agent-authorship.md) and [`label-agent-filed-issues`](shared/workflow/label-agent-filed-issues.md).

## File formatting & links

- Use GitHub-style markdown for all responses and documentation.
- Hyperlink liberally to make it easy for readers to find more information;
  see [`hyperlink-liberally`](shared/writing/hyperlink-liberally.md).
- When referencing files or symbols, use relative markdown links or inline code backticks.
- When mentioning PRs or issues, format them as clickable hyperlinks to forge URLs, never bare `#NNN` (except `Closes #123`).
- Semantic line breaks everywhere, enforced by CI ([rule](shared/writing/semantic-line-breaks.md)).

- **Don't:** link a `#NNN` a passage is displaying rather than citing, or leave referenced tools, forge items or policies unlinked.

## Never dispatch a worker on Fable without explicit, specific permission

Workers without an explicit model inherit the conductor's: never dispatch a worker on Fable without explicit, specific permission.
Name the model on every dispatch, defaulting to cheaper tiers for mechanical work.
See [`no-fable-subagents`](shared/workflow/no-fable-subagents.md).

## Work iteratively with editor agents on drafting

Draft iteratively: write substantively-correct first drafts, then hand off to specialized editor agents (prose editor, code editor) for style compliance.
See [`iterative-editing`](shared/workflow/iterative-editing.md).

## Antigravity Workspace Rules & Activation Scopes

See [`GEMINI.md`](GEMINI.md) and [`memories/antigravity.md`](memories/antigravity.md) for Antigravity-specific workspace rules, activation scopes, manifests, and hook integration.

## Use the browser only when nothing else can

Before opening a browser, look for a CLI, MCP, or API that can do the task, and say what you found.
Use a browser only if none can (or could be set up), or the task is visual.
Never use Chrome or Claude in Chrome (Ezra, 2026-10-22).
See [`browser-last-resort`](shared/workflow/browser-last-resort.md) and [`gh-pages`](shared/workflow/read-published-html-from-gh-pages.md).

## Draft communications in Ezra's voice

Imitate Ezra's writing style in any draft that goes out as him ([`draft-in-ezras-voice`](skills/draft-in-ezras-voice/SKILL.md)).
Learn it only from his own text, never FERPA data.

## Act on the whole request, and decide rather than ask

Read a request for everything it plainly asks, do every safe step it covers, and bring the user decisions rather than open questions ([#2889](https://github.com/Morrison-Lab/ai-config/issues/2889)).

- **Interpret instructions broadly and maximize safe progress:** unless the user narrows a request, take the broad reading that advances its obvious objective and complete every safe, authorized, relevant step.
  Do not reduce an instruction to the smallest literal action when its context makes a larger in-scope outcome clear.
  Apply grants and rules at the breadth stated without adding unstated conditions, exceptions, or restrictions.
  See [`AGENTS.cases.md`](AGENTS.cases.md) and [`challenge-the-assignment.cases.md`](shared/workflow/challenge-the-assignment.cases.md).
  Read every word, infer what a request plainly implies, and treat a correction as a general principle whenever plausible: [`read-instructions-fully`](shared/workflow/read-instructions-fully.md).
- **"Or" always means "and/or", not xor, unless xor is explicitly specified:** in instructions, prompts, specifications, issue descriptions, and checklists, treat "or" as inclusive ("and/or") unless exclusive choice is explicitly stated (e.g., "either A or B, but not both", "mutually exclusive", or "xor").
  When an instruction says "do X or Y", address both X and Y if both are applicable, relevant, or needed to achieve the objective.
  See [`or-means-and-or`](shared/principles/or-means-and-or.md).
- **Silence is not permission:** an unaddressed action is not thereby allowed, required or forbidden: reason from the nearest rules' purpose, or ask.
  See [`silence-is-not-permission`](shared/principles/silence-is-not-permission.md).
- **Default to action without asking:** the owner grants standing permission for non-destructive steps (branch commits, pushes, opening/updating PRs, read commands, editing memory).
  Proceed with non-destructive steps and report in past tense;
  ask only for destructive, high-impact, or blocking decisions.
  This grants no merge authority.
  See [`AGENTS.cases.md`](AGENTS.cases.md).
  The grant also covers installs and updates, `add_repo` (even to read), and posting reviews, without asking.
  Never ask the owner to perform a step you could do: [`default-to-action-grants`](shared/workflow/default-to-action-grants.md).
  Create new repos with `gh repo create --template`: [`templates`](shared/workflow/repo-templates.md).
- **Proactively suggest better alternatives to proposed approaches:** when asked to accomplish a goal using a specific approach, suggest a better alternative if one exists.
  Distinguish the underlying goal from candidate mechanisms;
  when an alternative achieves the goal more simply, cleanly, or reliably, proactively recommend it.
  See [`proactively-suggest-alternatives`](shared/principles/proactively-suggest-alternatives.md) and [`AGENTS.cases.md`](AGENTS.cases.md).
- **Always give recommendations with questions:** whenever asking the user a question or presenting options for a genuine decision, always provide a clear, specific recommendation.
  Soft open-ended prompts that present choices count as decision points and must include a concrete recommendation.
  If an action is already authorized under standing rules, do the work and report in past tense per [`no-cop-out-offers`](shared/workflow/no-cop-out-offers.md).
  A user's whether-or-how question is not an instruction: recommend, then ask start now or file ([`start-or-file`](shared/workflow/start-or-file.md)).
  Repeat the recommendation in one line whenever a status list restates a decision item.
  See [`AGENTS.cases.md`](AGENTS.cases.md).
  - **Do:** write every pending-decision line as "decide X --- I recommend Y, because Z".
  - **Don't:** ask questions or present choices without declaring your recommended path.

## Strict Merge Control Policy

- **NEVER merge a PR or MR without explicit user permission**: a session grant (`/mwc`, `/maw`) or a merge instruction for that PR.
- **Under `mwc`, merge only a fully clean PR** ([`fully-clean`](shared/workflow/fully-clean.md)): any standing not-clean review vetoes it, and a skip notice is not approval.
- **Don't call a PR merge-ready without a clean review on its latest commit**;
  `mergeStateStatus: CLEAN` is not a review verdict.
- **View every page of a document render before calling its PR ready** ([`review-rendered-documents`](shared/workflow/review-rendered-documents.md)).
- **Revert a premature or defective merge at once**, and reopen the issues it closed.
- **A purely infrastructure PR carries a standing `mwc` grant** in pushable repos once fully clean.

Detail, cases, cross-model waiver: [`strict-merge-policy`](shared/workflow/strict-merge-policy.md).

## Only work PRs scoped to the user or Actions app

Before pushing to, editing, commenting on, resolving threads on, reviewing, dispatching a paid review of, or merging any PR, read its author and assignees.
Proceed only when the author or an assignee is the invoking user (or an alias), the user named that PR, or the author is `github-actions`;
an explicit "do not touch" vetoes the PR first, and a missing identity check fails closed.
A review-only run dispatched naming the target PR reviews and stops there.
Every review you post or produce, including a local report or one composed in-transcript, carries both the Markdown report and the `review-data` JSON payload.
Detail: [`pr-scope`](shared/workflow/pr-scope.md) and [`memories/reviewing-prs.md`](memories/reviewing-prs.md).

## Review your work before anyone sees it, and watch every PR you drive

Have your work reviewed independently before it ships or reaches a person, and keep every PR you drive watched until it ends ([#2889](https://github.com/Morrison-Lab/ai-config/issues/2889)).

- **Every self-review is an adversarial review by a separate subagent:** never push code blind, and never review your own diff in the context that wrote it.
  Whenever reviewing your own work is called for (before `git push`, as the fallback when the external reviewer is down, or the project-conventions pass), dispatch it with an adversarial brief to a separate reviewer (the `adversarial-reviewer` subagent, or a separate CLI where no subagent tool exists) against `git diff origin/<default-branch>...HEAD`.
  Address, rebut, or defer every finding, and push only on a `clean` verdict whose fingerprint prefix-matches HEAD ([`adversarial-self-review`](shared/workflow/adversarial-self-review.md)).
- **Get a clean automated review before asking a person to review:** never ask a person to review a PR, GitLab MR, document, or other work product, on any forge, repo, or project, or report one as awaiting human review, until its automated review is clean or deadlocked.
  Trigger the automated reviews yourself after the round's last push (or confirm a run on that head), and iterate (`ardi`) until clean.
  A quota-skipped, stubbed, or never-started review is no review: re-trigger it, and if it still cannot give a verdict, a clean posted adversarial review stands in.
  See [`automated-review-before-human`](shared/workflow/automated-review-before-human.md) for steps and exceptions.
- **Put PRs in ready mode when they are ready for review**, since a draft hides a PR from reviewers and blocks review workflows;
  the two exceptions are an up-front empty PR on claim (`pr-on-claim`), un-drafted once its implementation lands and checks pass, and a draft-gated dependent PR held until its prerequisites merge.
  Marking a PR ready grants no merge authority ([`put-prs-in-ready-mode`](shared/workflow/put-prs-in-ready-mode.md)).
- **Always arm a persistent PR loop** when you open, push to, or take over a PR, if one is not already running, and keep it running until the PR merges, closes, or the user stops it.
  A one-shot poll or webhook subscription is not a loop: re-arm periodic check-ins with the session's wake mechanism.
  After every push, actively poll forge CI and review state with `gh` or `glab` until terminal.
  Baking a self-merge directive into the loop prompt is allowed only under a standing `mwc` grant ([`persistent-pr-loop`](shared/workflow/persistent-pr-loop.md)).
- **Monitor scoped open PRs and MRs:** continuously derive and monitor them in the repositories you are actively working in, not in every accessible repository, and within them only the items passing the [PR scope test](shared/workflow/pr-scope.md), including items you opened, pushed to, or were handed to drive.
  Re-query that scoped set at every wake, inspecting mergeability, CI, and review state until each item merges, closes, or is released ([`monitor-scoped-open-prs`](shared/workflow/monitor-scoped-open-prs.md)).

## Ship work through a verified push and a PR

Verify every push first, and carry work worth keeping through to a PR ([#2889](https://github.com/Morrison-Lab/ai-config/issues/2889)).

- **Commit, push, and PR any potentially-reusable work you produce:** potentially-reusable work produced incidentally in any medium (math derivations, comparisons, scripts, prose) must be committed, pushed, and PRed into an owning repository.
  Commit it when reproducing it costs more than a moment **and** something durable cites it, or will;
  re-check the committed form before publishing ([`commit-reusable-work`](shared/workflow/commit-reusable-work.md), [`AGENTS.cases.md`](AGENTS.cases.md)).
  [Port content by script](shared/workflow/port-by-script.md).
- **Deliver completed implementation work:** when asked to implement or write up changes on a feature branch, complete the full delivery cycle: tracking issue, scoped commits, adversarial self-review to a clean verdict, push, open or update the PR, request AI review, and drive to clean.
  This grants no merge authority: the Strict Merge Control Policy still applies.
- **Verify changes before pushing:** always run relevant local linters, tests, and formatting checks before pushing commits to a remote branch.
  At minimum for `ai-config`: `python3 scripts/validate-skills.py`, `python3 scripts/check-links.py`, `python3 scripts/check-ascii-punctuation.py`.
  Run the full test suite (`python3 scripts/test_*.py`) when touching shared tools or scripts.
  Parse changed data files: [rule](shared/workflow/parse-data-files.md).
- **Check the remote immediately before every push:** run `git ls-remote --heads origin <branch>` **immediately** before every `git push`, and reconcile what it shows rather than overwriting it.
  Never bare `git push --force`; always use `--force-with-lease --force-if-includes` ([`check-before-pushing`](shared/workflow/check-before-pushing.md)).

## Cursor Cloud specific instructions

See [`cursor-cloud-instructions`](shared/workflow/cursor-cloud-instructions.md) for environment caveats, preview/render commands, and pre-commit setup when working in Cursor Cloud.
