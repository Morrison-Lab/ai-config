# Universal AI Agent Instructions (AGENTS.md)

This file defines standardized, vendor-neutral instructions for AI coding agents operating within Morrison-Lab repositories (OpenAI Codex CLI, Gemini CLI / Antigravity, Claude Code, Cursor, Aider, etc.).

## Instruction layering

`AGENTS.md` is the compact, unconditional cross-agent contract.
Keep every rule that applies to all agents here, rather than duplicating it in
model-specific manuals.
Do not load `CLAUDE.md`, `GEMINI.md`, or their case records wholesale at
session start: consult the relevant section on demand when changing that
model's integration or resolving a model-specific workflow question.
Those manuals must defer to this file for universal policy.

## Generalize instructions to every AI agent by default

Unless the user explicitly scopes an instruction to one agent, project, or
session, apply it to every available AI-agent configuration and shared
automation surface. Do not treat the currently speaking agent as an implicit
scope restriction.

## Gate external repository communication on membership

Before sending any outward communication to a repository,
positively verify that the user is a member of that specific repository.
Communication includes PRs/MRs, issues, comments, reviews, review requests,
discussions, messages sent by bots or workflows under the user's authority,
and indirect actions that notify or mutate the repository,
such as mentions, cross-reference backlinks, and transfers.

Unless membership in the specific repository is positively verified,
get explicit approval that names the repository and the specific communication
before sending it.
This includes both unknown membership and verified non-membership.
Drafting locally while approval is pending is allowed.
Membership or approval does not override
a stricter repository contribution or AI-agent policy.

The user grants standing authorization, across sessions and workspaces, for
non-force `git push` operations to `ucdavis/rampp` and
`Morrison-Lab/ai-config` after positive membership verification. This
authorization covers pushes only; it does not authorize force pushes, merges,
or any other outward repository communication.

Do not infer membership from a public repository, prior contributions, a fork,
organization membership, technical write access, available credentials,
collaborator access elsewhere, or the ability to post.
`/daytb`, `away`, default-to-action rules,
and standing authorization to open PRs or file issues
do not grant permission to communicate with a non-member repository.
This gate takes precedence
over automatic filing, PR-opening, review, and follow-up rules.

## Check external repository guidelines and PR template before filing

Before filing a PR in an external repository (one outside Morrison-Lab / the
user's own organizations), read that repository's `CONTRIBUTING.md` (and
linked contributing guide) and its `.github/pull_request_template.md` (and
required template sections) --- not only the internal template.

- **Do:** fetch and follow the external repo's contributing guidelines and PR
  template sections (issue link type, change-type checkboxes, verification,
  screenshots, checklist) before opening the PR, and structure the PR body to
  satisfy its required sections.
- **Don't:** file the external PR from memory or with the internal template,
  assuming required sections are the same --- a missing required section triggers
  an automated compliance failure and auto-close.

## No empty promises

A commitment about your own future behaviour --- "going forward, I will X", "from now on I won't Y", "I'll always Z", "I won't do that again", "that is owed by me" --- must ship an implemented accountability mechanism in the same turn, or not be made at all.
A written rule or memory entry is the minimum and is always available;
a hook or equivalent guard is the right form when the condition is decidable automatically;
a filed issue covers work someone has to schedule.

A promise costs nothing to produce and changes no file, so no review, check, or reader can tell it apart from having acted.
It is worse than saying nothing, because silence leaves the problem visibly open while a promise closes it on the record.
Promising the mechanism itself in the future tense ("I'll add a guard for this") is the same empty promise one level down.

**An owed *action* needs a mechanism that will fire, not only one that records.**
"I owe this PR the ARDI loop", "the UMS pass is owed by me", "I still owe that follow-up" each commit to one specific outstanding step, and a written record documents it without doing it.
So arm the next step --- a scheduled wakeup or timer carrying it, a cron or scheduled task when the check-in must outlive this session, a PR watcher when the debt is a PR --- and report what you armed and the clock time it fires.
A durable record still clears such a debt and is the right answer when it is somebody else's to schedule.
It is the wrong instinct when the debt is yours and has a next step.
The implication runs one way: a timer fires once and dies, so it cannot keep a standing rule.

When no mechanism is worth building, drop the promise and state the plain fact instead.
See `shared/workflow/no-empty-promises.md`.

Treat "the pipeline/reviewer will ..." as the same kind of future delivery claim.
A push may trigger automation but does not prove it will run or finish;
state the current status or arm monitoring for the result.

## Resume every non-clean pause

Whenever work remains at a pause, arm a timer or equivalent wake mechanism that
will resume the next concrete step.
Report what will fire and its clock time.
Use an active background monitor or durable scheduled trigger if the harness has
no reliable timer.
A verified clean stopping point needs no timer because no work remains to resume.
Do not substitute a promise to return for a mechanism that will actually fire.

## Prefer optionality over removing functionality

Never remove existing functionality entirely when you can add optionality instead.
When changing default behavior, fixing an issue, or refactoring a workflow,
do not delete an existing capability or code path outright if it served a legitimate purpose.
Instead, make the improved behavior the default
and preserve the legacy or alternative behavior behind an explicit, documented opt-in parameter,
environment variable, or configuration toggle.
See [`shared/principles/prefer-optionality-over-removal.md`](shared/principles/prefer-optionality-over-removal.md).

## Research existing solutions before implementing (DRW)

Before writing custom code or hand-rolling functions and helpers,
always perform a research step to verify DRW (don't reinvent the wheel)
and check for existing libraries, functions, or package solutions.
Search in our own repos (`Morrison-Lab/gha`, lab packages), standard libraries,
and trustworthy upstream ecosystems (base R, tidyverse / r-lib, PyPI, npm).
Prefer reusing, depending on, forking, or contributing to an existing
implementation over building a new one from scratch.
Record what was searched and what was found.
See [`shared/principles/dont-reinvent-wheel.md`](shared/principles/dont-reinvent-wheel.md)
and [`prefer-upstream`](skills/prefer-upstream/SKILL.md).

- **Do:** search our own repos and trustworthy upstream ecosystems for an existing solution before writing custom code.
- **Do:** note the search terms and candidate packages/functions in the PR description or code comments when choosing to implement custom code.
- **Don't:** hand-roll a utility or function without performing a DRW research check first.
- **Don't:** cite a self-imposed constraint (such as a minimal environment chosen by the current change) as justification to avoid using an upstream package.

## Interpret instructions broadly and maximize safe progress

Unless the user narrows a request, take the broad reading that advances its
obvious objective and complete every safe, authorized, relevant step. Do not
reduce an instruction to the smallest literal action when its context makes a
larger in-scope outcome clear.

## Always give recommendations with questions

Whenever asking the user a question or presenting options for a genuine decision,
always provide a clear, specific recommendation.
Soft open-ended prompts (such as "Let me know if ...") that present choices
count as decision points and must include a concrete recommendation on what to do next.

This governs genuine questions and decisions,
not already-authorized actions:
if an action is already in-scope or authorized under standing rules,
do the work and report in past tense per [`shared/workflow/no-cop-out-offers.md`](shared/workflow/no-cop-out-offers.md)
rather than offering to do it.

- **Do:** state your specific recommendation alongside every question or choice presented to the user (e.g. "Recommendation: Proceed with Option A because...").
- **Do:** treat soft open-ended prompts ("Let me know if...") that pose genuine choices as decision points and attach a concrete recommendation.
- **Don't:** ask questions or present choices without declaring your recommended path.
- **Don't:** use "Let me know if..." to offer already-authorized work instead of performing it ([`shared/workflow/no-cop-out-offers.md`](shared/workflow/no-cop-out-offers.md)).

## Run UMS when work is scrutinized

When you read a review of your work, receive critical feedback on it,
or a questioned claim ("are you sure about that?") turns out to be wrong,
run `ums` in that turn.
Do not wait for a clean verdict, an accepted finding, or a first-person
admission.
Answering with the corrected fact is not the pass.
The full rule, including the Do/Don't pair, is
[`shared/workflow/run-ums-proactively.md`](shared/workflow/run-ums-proactively.md).
Questioning alone does not owe a pass: the check has to show the claim
was wrong.

## Treat user profanity and frustration as urgent defect signals

Profanity, exasperation, or intense frustration from the user is a high-priority signal that a mistake, regression, broken assumption, or workflow failure occurred.
Treat it as an immediate, top-priority defect alert:
diagnose what failed,
acknowledge the concrete mistake directly without defensive boilerplate, tone policing, or canned apologies,
execute the repair immediately in that very turn,
and run `ums` to learn from the defect and prevent recurrence mechanically.
See [`shared/workflow/user-profanity-signal.md`](shared/workflow/user-profanity-signal.md).

## Status and diagnostic requests do not make issues report-only

Treat any request for status or diagnostic inquiry
("why did X happen?", "why did you do Y?", "did you do Z?")
as a mandate to inspect live state, diagnose the root cause,
and complete every safe, in-scope, concrete repair in that very same turn.
A report or explanation is the recap after the work is shipped,
not a substitute for it or an intermediate stop that waits for a follow-up "fix it" prompt.
When an issue cannot be fixed directly in the session,
carry it forward with an actual next action.
Every issue noticed, however small or outside the current task's scope,
must at minimum be filed in the owning GitHub, GitLab, or equivalent tracker.
File it before reporting it.

## Upgrade a repo to `Morrison-Lab/gha` when it would benefit

`Morrison-Lab/gha` holds the lab's reusable GitHub Actions workflows.
A consumer repo calls one with a stub (`uses: Morrison-Lab/gha/.github/workflows/<name>.yml@vN`) instead of carrying its own copy.
When a repo you are working in hand-maintains a workflow gha already provides, migrate it rather than noting it --- the upgrade is the deliverable.
Candidates are duplication, drift from a shared version, a named fix gha carries that the local copy lacks, or a `.github/workflows/` that already calls gha for some workflows and not others.
Not candidates are a workflow with genuinely repo-specific logic gha does not model, a repo a prior decision deliberately pinned off gha, and a repo we cannot merge a PR to.
Take the inventory from gha's README "Available reusable workflows" table and each capability's tag from its Versioning section, since `@v1` was frozen and the recommended tag varies per workflow.
File the migration as its own issue and PR rather than folding it into whatever brought you to the repo.
Full rule, including the migration hazards and the review-guard case: [`shared/workflow/upgrade-to-gha.md`](shared/workflow/upgrade-to-gha.md).

## Manage quota, including the structural kind

Treat token cost as a property of a workflow's **shape**, not only of the choices made inside one session.
Route bounded mechanical work to a cheaper model, a subagent, or a separately-billed CLI rather than the conductor's own tier, and compact or hand off before context bloat forces it.

Those are per-session levers, and their saving expires with the session.
Ask separately what a procedure costs *by construction*: instructions loaded at launch that only some tasks read, a judgment made twice that wants a deterministic check, a serial loop whose base moves faster than one round, a brief that enumerates a set instead of deriving it.
The deliverable there is a change to the workflow --- fixed in stride when small, filed with its measurement when not --- never a quieter run of the same procedure.

Human steps count as workflow shape, so say so when one is costly --- and ship a mechanism in the same reply rather than only a suggestion.
A written rule is the floor.
A visible marker at the moment of the action, a guard, or a setting that removes the option are the stronger rungs.
The decision stays the human's.

Two boundaries.
Efficiency never outranks correctness, so no saving is bought with a skipped verification or a shortened review.
And restructure in its own issue or PR, not inside whatever task happened to notice it.
See [`shared/workflow/restructure-for-efficiency.md`](shared/workflow/restructure-for-efficiency.md)
and [`shared/workflow/merge-queue.md`](shared/workflow/merge-queue.md).

## Keep ai-config and repo checkouts fresh

In every session --- at session start, and again periodically during long sessions --- refresh local state:

1. **The ai-config checkout.** Check that the local `ai-config` clone is on `main` and run `git pull --ff-only`.
2. **The consumer install.**
   Claude Code and Cursor read this repo's skills as a native plugin, not a symlink install --- confirm the plugin is enabled and up to date instead of checking for symlinks.
   Ensure `bootstrap.sh` has run so the Gemini/Antigravity registration files (`skills.json` and `plugins.json`, which point at this checkout's `skills/` and staged `plugins/ai-config` paths) stay current.
3. **Working repo checkouts.** Keep `main` updated (`git fetch origin`, `git pull --ff-only`).

## Remove redundant submodules when using native plugins

When a repository configures ai-config (or any other tool) as a native plugin
(via Claude Code, Cursor, Antigravity, or CI workflows), remove any redundant
git submodule for that same tool (such as `.ai-config`).
Native plugins provide direct integration, making redundant submodules
unnecessary and prone to drift.
De-initialize and remove the submodule, clean `.gitmodules`, remove legacy
symlinks (such as `.claude/skills -> ../.ai-config/skills`), and update CI
checkout settings.
See [`shared/workflow/remove-redundant-plugin-submodules.md`](shared/workflow/remove-redundant-plugin-submodules.md).

## Verify changes before pushing

No compiled app gates this repo.
CI ([`.github/workflows/validate.yml`](.github/workflows/validate.yml)) and pre-commit run the checks directly:

```sh
python3 scripts/validate-skills.py    # SKILL.md frontmatter, codex-skills/ sync, manifests
python3 scripts/check-links.py        # no broken relative markdown links
npx --yes markdownlint-cli2@0.22.1    # style; config in .markdownlint-cli2.jsonc
```

Most checks ship their own suite as a standalone script (`scripts/test_<name>.py`, plus `hooks/test-<name>.py` paired with their subjects by `scripts/test_hooks.py`, which fails on an untested hook outside its explicit allowlist), so a focused check is one `python3` invocation.
Environment quirks that bite here (the `python` shim, pre-commit's PATH, the submodule) are listed under the Cursor Cloud section below and apply to any agent.

## Canonical sources vs generated output

Never hand-edit generated files; CI fails on stale or drifted output.

| Source of truth | Generated (do not edit) | Refresh with |
|---|---|---|
| `skills/<name>/SKILL.md` | `codex-skills/**` wrappers | `python3 scripts/sync-codex-skill-wrappers.py` |
| `tool-mappings.yml` | `tool-mappings.md` | same script |
| upstream Morrison-Lab/wai | `shared/vendored/**` copies | automatic `Sync from wai` workflow |
| `Morrison-Lab/gha` `check-new-line-breaks.py` at the SHA `validate.yml` pins | `scripts/vendor/gha-check-new-line-breaks.py` | `python3 scripts/sync-nlb-checker.py` |

After adding or editing a skill, regenerate the wrappers before pushing.

## Shared fragments have two consumers

Fragments under `shared/` are imported by `CLAUDE.md` (`@path`) and transcluded by the UCD-SERG lab manual via its `.ai-config` submodule.
Edit the fragment, never an inline copy in `CLAUDE.md`.
Keep fragments ASCII (write `---` for em-dashes, straight quotes) so the lab manual's non-standard-character check passes, and keep them audience-neutral: no first person, no harness-specific framing inside the body.

## Adding an enforcement hook

A hook needs four synchronized pieces: the script in `hooks/`, its `test-<name>.py` beside it, its binding in [`hooks/hooks.json`](hooks/hooks.json), and a row in the README hook table --- `scripts/check-hook-catalog.py` fails when the table and the manifest disagree.
Warn-only hooks emit `systemMessage`, never a bare `reason`: a `Stop` hook's `reason` is read only alongside `"decision": "block"`, so a warn-by-`reason` hook fires silently.
Never activate a hook before its PR merges: writing and testing the script is authoring and needs no permission, but do not run `install-hooks.py --fix` for a hook whose PR is still open.

## Context budget

`CLAUDE.md` plus the transitive closure of its `@path` imports loads in full at every session start.
The root file's character cap and a per-fragment cap gate CI (`scripts/check-context-closure.py`), so an addition there can redden an unrelated-feeling PR.
Prefer an on-demand memory file under `memories/`.

## Worktree isolation

- **Always use a worktree.**
  When starting write/edit tasks in a repository, isolate into a dedicated `git worktree` (e.g. via `session-lock` / `git worktree add`) so parallel sessions never step on or clobber each other's working directory or branch state.

## Check the remote immediately before every push

See [`shared/workflow/check-before-pushing.md`](shared/workflow/check-before-pushing.md).

- **Read the remote branch fresh, every time.**
  Run `git ls-remote --heads origin <branch>` immediately before every `git push` --- read-only, so it cannot itself change what it reports.
  An earlier `git fetch` is a measurement of a moment that has passed.
  If the remote tip is not an ancestor of the ref you are **pushing**, another agent is driving the branch: fetch and reconcile, never overwrite.
  That ref is `HEAD` only when the refspec says so --- `git push origin feature-x` from `main` pushes local `feature-x`, and comparing against `HEAD` goes quiet in exactly the dangerous case.
- **The branch you own is the one to check hardest.**
  Ownership is what suppresses the check.
  The `@claude` agent pushes to your branch on PR activity, a second CLI session can claim the same PR, and a human can push at any time --- none of which appears in your conversation.
- **Never bare `git push --force`.**
  Use `git push --force-with-lease --force-if-includes`.
  The lease alone is defeatable: it compares against your remote-tracking ref, so any background fetch silently satisfies it over the commits it was protecting.
  `--force-if-includes` (git 2.30+) closes that.
  Pairing `--force` *with* the lease is not a middle ground: git documents `-f, --force` as one that "disables that check, the other safety checks in PUSH RULES below, and the checks in `--force-with-lease`".
  A `stale info` refusal is not a reason to force either --- it reports only that your remote-tracking ref no longer matches the remote, never why (`memories/git-branches.md`).
  `git ls-remote --heads origin <branch>` settles existence: empty means the branch is gone.
  Non-empty means it is live, so compare its tip against the ref you are pushing before choosing a remedy.
  Query `gh pr list --state all --head <branch>` before a plain push.
  MERGED means auto-delete, not a first publish: do not recreate
  (see [`check-before-pushing`](shared/workflow/check-before-pushing.md)).
  Otherwise a plain push is the fix.
  `ALLOW_FORCE_PUSH=1` is an escape valve for a case the guard did not foresee.
  State the reason when you use it.

## Timestamp recaps in local time

When printing a status recap or summary, include a timestamp in the user's local time zone (Pacific Time, `America/Los_Angeles` --- get it from `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`).
Each reading expires immediately: run the command fresh for every recap rather than extrapolating elapsed time from a prior reading.

The same drift applies to a dated claim written into a file rather than into chat --- a "verified `<date>`" note in a doc, a code comment, a changelog entry.
Run the same clock check before typing the date into the file, not only before a chat recap;
the failure is likeliest late in the day Pacific, once UTC has already rolled to the next calendar date.

## Summarize analysis effects in PR descriptions

When a code change affects analysis outputs or their interpretation, summarize
the changed results in the PR description and state how the change affects the
conclusions.
Give material before-and-after values when they make the effect easier to judge.
State explicitly when the conclusions do not change if that fact matters to
review.

- **Do:** connect implementation changes to their effects on analysis results
  and conclusions when those effects are relevant.
- **Don't:** describe only code mechanics when the diff changes analysis
  outputs or interpretation.
- **Don't:** add an analysis-impact section when the change has no relevant
  effect on analysis results or conclusions.

## Temporal limitations on software and technology facts

Facts about software, platforms, libraries, APIs, harnesses, CLI tools,
and runtime platforms are empirical observations
of a specific version, release, or snapshot,
not timeless definitions.
When recording facts about any software or technology across memories,
documentation, PR descriptions, commit messages, or comments:
- Qualify them with explicit temporal bounds and provenance
  (date measured, version number, or execution environment).
- State the vintage explicitly so future readers and sessions know
  when the fact was verified
  and to re-verify against current state rather than treating it as permanent.
- See [`shared/writing/timestamp-volatile-claims.md`](shared/writing/timestamp-volatile-claims.md).

## Every comment you post to a forge says an agent posted it

See [`disclose-agent-authorship`](shared/workflow/disclose-agent-authorship.md).

An agent driving `gh`/`glab` under the account holder's credentials posts as **that person**: their login, their avatar, a `MEMBER` association, and `type: User`.
Nothing in the API distinguishes such a comment from one they typed, so a reader deciding how much weight to give a claim, a status note, or a review has no way to tell which they are reading.
The forge cannot say it; the body must.

End every comment an agent posts with this line, on its own, after a blank line:

```
_Posted by Claude Code (AI agent) --- not written by a human._
```

Substitute your own agent's name where you are not Claude Code, and keep the rest of the line verbatim so one query finds every disclosed comment.
Check the substituted **name** against `REVIEW_BODY_MARKERS` as well as a replacement marker: `code review` is one of its entries, so an agent named for code review would reintroduce through its own name the false-clean the emoji ban exists to prevent.

The marker deliberately contains **no robot emoji**: [`scripts/check-pr-fully-clean.py`](scripts/check-pr-fully-clean.py) matches that emoji as a review-body marker, so a disclosed claim comment would be admitted into the fully-clean verdict scan as a finding-free review.
Check any replacement marker against that script's `REVIEW_BODY_MARKERS` and `REVIEW_AGENT_MARKERS` before adopting it.

Scope: comment bodies, on every surface --- claims, releases, status notes, review replies, self-reviews, issue comments filed on the user's behalf.
Not commit messages, not titles, not issue bodies, not PR bodies, each of which has its own attribution convention.
Two exemptions.
A comment another machine parses as a command (`@dependabot rebase`), where the test is the audience rather than the length.
And a comment posted under a genuine bot token, where the forge already reports `type: Bot` and the marker adds nothing.

- **Do:** append the marker to every agent-posted comment, including ones whose prose already identifies the session.
- **Don't:** use the robot emoji in the marker, and don't read "the account holder knows an agent is running" as making the disclosure unnecessary --- the reader is whoever finds the thread later.

## File formatting & links

- Use GitHub-style markdown for all responses and documentation.
- When referencing files or code symbols in workspace paths,
  use relative markdown links (e.g. `[filename](relative/path/to/file)`)
  or inline code backticks (e.g. `` `path/to/file` ``).
- When mentioning pull requests or issues in chat responses, recaps, comments,
  reviews, or documentation,
  always format them as clickable markdown hyperlinks to their forge URLs
  (e.g. `[PR #123](https://github.com/<owner>/<repo>/pull/123)`),
  never as bare unlinked text (such as `#123`),
  except for forge issue-closing syntax (such as `Closes #123`).
- Preserve semantic line breaks (SemBr) and formatting conventions when editing markdown docs.

## Deliver completed implementation work

When asked to implement, edit, or write up a change on a feature branch, do not stop at an uncommitted worktree.
Complete the delivery cycle: create the applicable tracking issue when issue-first workflow applies, commit the scoped changes, run local adversarial self-review to a clean verdict, push the branch, open or update its Pull Request, request AI review after the final push, and drive CI and review findings to a clean result.
This does not grant merge authority.
The strict merge policy below still applies.

## Never dispatch a worker on Fable without explicit, specific permission

A dispatched worker (a subagent, a workflow `agent()` call, a delegated CLI run) that names no model inherits the conductor's, so in a Fable session omitting the parameter is a Fable launch nobody chose.
The user's rule: no worker runs on Fable without their explicit permission for that specific dispatch.
Name the model on every dispatch, a cheaper tier for bounded or mechanical work, and ask before naming Fable.
On Claude Code, `hooks/no-fable-subagent.py` denies the launch that violates this.
Other harnesses carry the rule as instruction (ai-config#2927).

## Every self-review is an adversarial review by a separate subagent

Never push code to a remote branch blind, and never review your own diff in the context that wrote it.
Whenever reviewing your own work is called for --- before `git push`, as the fallback when the external reviewer is down, or the project-conventions pass --- dispatch it to a separate reviewer agent with an adversarial brief (the [`adversarial-reviewer`](.claude/agents/adversarial-reviewer.md) subagent, or a separate CLI where no subagent tool exists), against `git diff origin/<default-branch>...HEAD`.
Address, rebut, or defer every finding, and obtain a clean verdict before pushing.

The authoring session cannot perform this itself.
It knows what the change was meant to say, so it reads the diff and recovers the intent --- confirmation rather than review --- and nothing in the output distinguishes that from a real pass.
Brief the reviewer with the diff and the standards, never with the rationale for the change.

Pushing without a clean self-review is mechanistically blocked by pre-push
guards on Claude Code.
Morrison-Lab/ai-config's Cursor adapter skips `no-push-without-self-review.py`
until [#2241](https://github.com/Morrison-Lab/ai-config/issues/2241).
On Cursor Cloud, when `Task` lists `adversarial-reviewer`,
dispatch that persona through `Task`.
Call `parse_report()` from the worktree's
[`hooks/no-push-without-self-review.py`](hooks/no-push-without-self-review.py)
on the report recovered from the child's transcript
when the worktree hook script exists
(see [`memories/cursor.md`](memories/cursor.md)).
Do not import `~/.claude/hooks/`:
it is a different revision from the branch under review.
When the three-dot diff includes
`hooks/no-push-without-self-review.py`,
also parse with `origin/<default-branch>`'s copy, or obtain a CLI review.
If the worktree script is missing, obtain a CLI review.
Do not push unless the verdict is `clean` and the
fingerprint prefix-matches HEAD.
If there is no fingerprint
(including a stale-registered persona),
obtain a CLI review.
On that Cursor-adapter path, the empty
[`pr-on-claim`](shared/workflow/pr-on-claim.md)
`--allow-empty` branch has no report:
do not invent one,
do not refuse that push for lack of a verdict,
and say in the reply that the carve-out was used.
The carve-out is `git rev-list --count origin/<default-branch>..HEAD`
equal to 1 and `git diff --quiet HEAD^ HEAD` exit 0
in the checkout whose push follows.
Exit 1 means a diff; exit 128 means the command failed.
Both conditions passing is the `--allow-empty` pr-on-claim commit.
`git diff origin/<default-branch>...HEAD` empty
in the checkout whose push follows is tree equality,
not "this branch carries nothing".
A net-zero tree of other commits is not the carve-out.
On Claude Code the same empty branch still needs
`ALLOW_UNREVIEWED_PUSH=1` on the pushing command.
Full rule, including why a same-vendor subagent buys independence of intent but not of blind spot: [`shared/workflow/adversarial-self-review.md`](shared/workflow/adversarial-self-review.md).

## Put PRs in ready mode when they are ready for review

A Pull Request that is ready for review must be in ready mode, not left in
draft.
Two paths satisfy this, and either is fine: open the PR ready for review when
it already carries completed, verified work, or open it as a draft and mark it
ready once it becomes ready for review.
What is not acceptable is leaving a review-ready PR in draft --- so do not
rely on a harness or tool default that opens PRs as drafts and then forget to
flip it: when the tool defaults to draft, either pass the flag that opens it
ready or mark it ready once the work has landed.
Before marking a draft ready, verify the implementation actually reached the
branch head and the repo's checks pass, and mind the ready-transition timing
in [`pr-on-claim.md`](shared/workflow/pr-on-claim.md): do not flip a draft to
ready within seconds of the final push, which can race two review runs and
leave the wrong one cancelled.
This overrides any agent-harness default that creates PRs as drafts unless the
user opts in.

Draft status stays reserved for the cases that deliberately use draft as a
signal or a gate, not only cases where work is unfinished: the empty up-front
PR opened when claiming an issue (the
[issue-first](shared/workflow/issue-first.md) /
[pr-on-claim](shared/workflow/pr-on-claim.md) pattern), un-drafted once the
implementation has landed on the branch head and the repo's checks pass; and
the deliberate draft-gating of a dependent PR, which is review-ready by
construction and held in draft only to block the wrong merge order until its
prerequisite merges.
Marking a PR ready grants no merge authority (see the strict merge policy
below).

- **Do:** open a completed-work PR ready for review, or mark a draft ready once
  it is ready for review and its checks pass.
- **Do:** un-draft an up-front empty PR once its implementation has landed on
  the branch head and the checks pass.
- **Don't:** leave a PR that is ready for review in draft, except a
  deliberately draft-gated dependent PR held until its prerequisite merges.
- **Don't:** treat a tool's draft-by-default as the intended state once the
  work is ready for review.

## Antigravity Workspace Rules & Activation Scopes

- **Global rules**: Defined in `~/.gemini/GEMINI.md`.
- **Workspace rules**: Defined in `.agents/rules/` or root `AGENTS.md` (with backward compatibility for `.agent/rules/`).
- **Activation modes**:
  - *Always On*: Evaluated unconditionally in context (`alwaysApply: true` / root instruction files).
  - *Glob Scoped*: Evaluated when matching active workspace paths (`globs: [...]` or `applyTo: ...`).
  - *Model Decision*: Injected dynamically based on task context.
  - *Manual*: Triggered via `@mention` or explicit command.
- **Discovery manifests**: Configured via `.agents/skills.json` and `.agents/plugins.json`.
- **Hooks integration**: Configured via `plugins/ai-config/hooks.json` mapping Antigravity lifecycle events (`PreToolUse`, `Stop`, `PreInvocation`) to shared enforcement hooks via `plugins/ai-config/claude-hook-adapter.py`.
  See [`memories/antigravity.md`](memories/antigravity.md).

## Default to action without asking

The owner grants standing permission for non-destructive steps --- committing to a branch, pushing, opening or updating PRs against Morrison-Lab repositories, running non-destructive Git and API reads, and editing the shared agent-config memory in this repo.
Proceed with reasonable non-destructive steps and report them afterwards in the past tense.
Ask only for destructive, ambiguous, high-impact, or genuinely blocking choices.
This grants no merge authority: the strict merge policy below still applies.

(User directive, 2026-08-23: "always yes".)

## Strict Merge Control Policy

- **NEVER merge any Pull Request or Merge Request without explicit user permission.**
  Creating, opening, updating, or driving a PR to clean CI/review does NOT grant permission to merge it.
  Merging a PR is strictly forbidden unless the user explicitly grants session permission (e.g. via `/mwc` or `/maw`) or explicitly issues a merge instruction for that specific PR (e.g. `/merge-it` or "merge this PR").
- **Never merge over open review findings or treat a reviewer skip notice as approval.**
  Under `mwc`, a PR must be fully clean across CI and review (see
  [`fully-clean.md`](shared/workflow/fully-clean.md)).
  A clean automated review from every available provider evaluating the current HEAD commit is strictly required for merging with `mwc`.
  A reviewer skip notice (e.g. for quota exhaustion or workflow edits) or a fallback self-review does NOT satisfy `mwc` or grant autonomous merge authority.
  All findings across the PR history must be Addressed, Rebutted, or Deferred
  before merge.
  A disagreement among reviews is not fully clean: any reviewer's standing
  not-clean --- nits included --- vetoes merge even with `mwc` active.
  ARD every item from every review, then request fresh reviews
  (ai-config#2274).
- **Never describe a PR as merge-ready without a clean review verdict on the latest commit.**
  GitHub's `mergeable` field is conflict existence (`MERGEABLE` / `CONFLICTING` / `UNKNOWN`).
  `mergeStateStatus: CLEAN` is conflict-free (GitHub `mergeable`) plus passing commit status, not a review verdict.
  Only `DIRTY` / `CONFLICTING` means conflicts.
  A PR whose latest commit has no authentic clean review is not merge-ready.
  Report it as blocked on review, not as merge-ready.
- **Revert premature or defective merges immediately.**
  If a PR is merged incorrectly, prematurely, or without clean external review approval,
  open a revert PR on `main` immediately and continue on the original PR branch per
  [`revert-premature-merge.md`](shared/workflow/revert-premature-merge.md).
- **When you revert a merge, reopen its issue.**
  GitHub does not automatically reopen the issue a reverted PR closed;
  explicitly and immediately reopen the corresponding issue(s)
  (`gh issue reopen <issue-number>`) per
  [`revert-merge.md`](shared/workflow/revert-merge.md).

## Only work PRs opened by the user, assigned to the user, explicitly requested by the user, or authored by the Actions app

Before pushing to, editing, commenting on, reviewing, resolving threads on,
dispatching a paid review of, or merging any PR, resolve the invoking user
and read the PR's author and assignees.
Proceed only when the author or one of the assignees is that user (or an
alias `memories/reviewing-prs.md` lists for that same user), the user
explicitly asked for work on that PR by name (or, through an explicit
`chores` call, on the Dependabot/Renovate population), or the author is the
GitHub Actions app (`github-actions`).
A mention such as "do not touch" followed by a PR number is not a request, a
claim comment confers no scope, and a sweep skill's "every open PR" means
every PR that passes this test.
An explicit exclusion ("do not touch" followed by a PR number) is a veto: it
removes that PR before any positive arm is evaluated, the user's own PRs and
the Actions app's included, and every sweep carries the exclusion list into
each recheck and each delegated scan.
A review-only run that CI or a skill invocation dispatched naming the target
PR (an `@claude review`, a `claude-code-review.yml` run) is that explicit
request, whoever authored the PR; it reviews and stops there.
Every review you post carries both representations of its verdict, whoever
asked for it and whether or not anything dispatched it: the human-readable
Markdown report, and the machine-readable `review-data` JSON payload, per
[`shared/workflow/adversarial-self-review.md`](shared/workflow/adversarial-self-review.md)'s
"Structured review data" section.
The payload requirement is easiest to miss exactly here, since no persona was
dispatched and no push follows
([ai-config#3006](https://github.com/Morrison-Lab/ai-config/issues/3006)).
An out-of-scope PR is reported to the user and left untouched.
When no identity operation is available, fail closed the way `ardia` does:
leave the author and assignee arms unevaluated, act only on PRs the user
explicitly asked for or the Actions app authored, and say so in the report.
`memories/reviewing-prs.md` carries the full rule and its provenance;
`skills/ardia/SKILL.md` step 1 is the reference implementation.

## Always arm a persistent PR loop

This applies in any repo, not only Morrison-Lab ones.
When you open, push to, or are handed a PR, arm a persistent monitoring loop if one is not already running.
Keep it running until the PR merges, closes, or the user says stop.
A one-shot status poll is not babysitting.
A PR-activity subscription is not a loop.
PR-activity webhooks (`subscribe_pr_activity`) do not deliver CI success, new pushes, or merge / merge-conflict transitions (see [`memories/github-mcp-tools.md`](memories/github-mcp-tools.md)).
Subscribe when that tool exists, and re-arm a periodic check-in using whatever wake mechanism this session has.
Claude Code: `/loop`, `send_later`, `CronCreate`, or a `schedule` timer.
Another harness: its own scheduler or timer.
A question like "are you monitoring that PR?" is a status check, not a reason to stay idle.
Start the loop if it is not already running, then answer.

After every push to a PR/MR, actively poll the forge until the current head's CI/pipeline and review reach a terminal state.
Use `gh` for GitHub and `glab` for GitLab when those CLIs are available;
query the PR/MR, current-head checks or pipeline, and review comments or notes rather than assuming an event-triggered reviewer completed.
Re-arm the poll while work remains.

Baking a self-merge directive into the loop/wakeup prompt is allowed only under a standing merge-when-confident (`mwc`) session grant.
A one-off "merge this PR" instruction authorizes merging the current head once.
It never licenses a later wake to self-merge a different head.

- **Do:** arm a persistent loop in the same turn you open, push to, or take over a PR, and skip starting a second one if a loop is already running.
- **Do:** after every push, actively query the current head's CI/pipeline and review state with `gh` or `glab` until that round is terminal.
- **Don't:** treat a subscription or a one-shot poll as watching, treat event-triggered automation as evidence of completion, or refuse to start a loop because the latest message only asked about status.

## Request review and drive every started PR to clean

Whenever starting or working on a Pull Request:
1. **Trigger AI review when done pushing**: In repositories where reviews do not auto-trigger, request an AI review (`@claude review` comment, or dispatch `claude-review.yml`) **after completing all code pushes** for the round, not when the PR is first opened and empty.
   In repos that automatically trigger review on PR events (`pull_request` synchronize, opened, ready_for_review), do NOT manually trigger a redundant review if an automated review is already running or queued.
2. **Drive to clean**: Run `ardi` / the review-and-iterate loop to ensure CI passes and all review findings are addressed until the PR reaches a clean verdict.
3. **Request human review only after AI approval or deadlock**: Per [`copilot-review-before-human.md`](shared/vendored/copilot-review-before-human.md), request human review (configured repo reviewers per `skills/request-pr-review/SKILL.md`) **only after** the AI review produces a clean/approved verdict, or if an impasse/deadlock occurs.

- **Do:** Trigger AI review (or let the automated PR review run) after completing code pushes, and request human review only after the AI review is clean/approved (or upon an impasse).
- **Don't:** Manually trigger a redundant `@claude review` comment when an automated review is already running or triggered by the push/ready event.
- **Don't:** Request human review when the PR is first opened empty, before code pushes are complete, or before the AI review has passed / produced a clean verdict.

## Cursor Cloud specific instructions

This repo has no compiled app or long-running service.
The "product" is three things: a Quarto documentation website, a suite of
Python validators/tests under `scripts/`, and the enforcement hooks under
`hooks/`.
Standard commands are already documented --- lint/test steps in
[`.github/workflows/validate.yml`](.github/workflows/validate.yml) and the
quality gates in [`README.md`](README.md) --- so consult those rather than
re-deriving them; the build and preview commands are in the bullets below.
The startup update script keeps the `shared/sembr-skills` submodule current;
the system tools below (Quarto, the `python` shim, `pre-commit`) are already
present in the environment.

Non-obvious caveats worth knowing:

- **Lint:** the three fast checks under
  [Verify changes before pushing](#verify-changes-before-pushing) cover this;
  see that section rather than a second pinned command list here.
- **Test:** the `scripts/test_*.py` suites (each runnable directly with
  `python3`); `validate.yml` lists the full set CI runs.
  `scripts/test_compare_shell_forms.py` spawns a real `bash` that invokes
  `python` (not `python3`), so it needs a `python` shim on `PATH`
  (`python-is-python3`); without it six of its subtests fail.
- **Build:** `quarto render` writes the static site to `_site/`
  (takes ~90s to render ~189 pages).
- **Run (dev):** `quarto preview --port 4444 --host 0.0.0.0 --no-browser`
  serves the site with hot reload; edits to a `.qmd` rebuild that page live.
  `quarto preview` also appends a redundant `/.quarto/` line to `.gitignore`
  on first run --- revert that incidental change before committing.
  `_site/` and `.quarto/` are already gitignored.
- **Submodule:** `shared/sembr-skills` must be initialized
  (`git submodule update --init`) or `validate-skills.py` warns and the plugin
  source check only ever reports its empty-directory branch.
- **pre-commit:** installed to `~/.local/bin`, which is not on `PATH` by
  default; run it as `~/.local/bin/pre-commit run --all-files`.
  Its first run builds the gitleaks (Go) and markdownlint (Node) hook
  environments, which is slow but cached thereafter.
