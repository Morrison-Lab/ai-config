# User-wide Claude Code instructions

`AGENTS.md` is the authoritative, auto-read cross-agent contract.
It owns universal freshness, worktree, delivery, timestamp, formatting, merge,
and review rules; this manual adds Claude-specific workflows.
Consult it on demand rather than loading this entire manual for another
agent's session.

Worked-example case records for the rules below live in
[`CLAUDE.cases.md`](CLAUDE.cases.md), moved out of this auto-loaded context.

<!--
Some sections below summarize a fragment in `shared/` and link it rather than
`@`-importing it, since every import counts toward Claude Code's always-loaded
instruction limit (see scripts/check-context-closure.py). Those fragments
are the single source of truth for guidance shared with the UCD-SERG lab manual,
which transcludes the same files. Edit the fragment, not the inlined copy, and
keep fragments ASCII (write `---` for em-dashes) so the manual's character check
passes. See README.md, "Shared content".
-->

## Run UMS proactively, as learnings accumulate

[`shared/workflow/run-ums-proactively.md`](shared/workflow/run-ums-proactively.md) (linked, not imported: read it whenever a pass may be owed)

Don't wait for `/clear`, a wrap-up step, or a merge to run `ums` (Update Memories and Skills) --- run it the moment a learning shows up: a corrected mistake, a new preference, a tool quirk, a workflow gap.
The fragment walks through the specific moments this gets skipped even by someone trying to follow the rule --- an offer to run it standing in for running it, a new instruction preempting an owed pass, a recommendation to `/clear` or start fresh while a pass is still owed, a PR-count worry used to justify deferring it, a corrected belief or a corrected false state-claim that never gets banked because nothing merged, reading a review and treating ARD work as the pass, answering a questioned claim ("are you sure about that?") with the corrected fact so nothing looks like an admission, and a pause that ends the turn with the pass still owed, waiting on CI, a review round, or an answer from the user --- and gives the fix for each: run the pass now, delegate it as pre-authorized sidecar work, and report it in the past tense rather than announcing an intention.

## Record both the pattern and the anti-pattern

When a `cai` or `ums` entry records a correction, write both sides as a labelled pair: the behaviour to adopt (**Do**) and the specific near-miss to stop (**Don't**), each an action a later reader could observe.
Detail, rationale, and cases: [`shared/writing/record-pattern-and-anti-pattern.md`](shared/writing/record-pattern-and-anti-pattern.md).

## No empty promises

A commitment about your own future behaviour ships an implemented mechanism in the same turn (a memory entry at minimum, a hook, a filed issue, or an armed wake for an owed action), or is not made;
`hooks/no-empty-promise.py` guards it.
Detail, rationale, and cases: [`shared/workflow/no-empty-promises.md`](shared/workflow/no-empty-promises.md).

## Generalize instructions to every AI agent by default

Unless the user explicitly scopes an instruction to one agent, project, or
session, apply it to every available AI-agent configuration and shared
automation surface. A Claude-only implementation is incomplete when Codex,
Gemini, Antigravity, or another installed agent can encounter the same rule.

- **Do:** update the shared source and every applicable agent-specific entry
  point; prefer an agent-independent service for operational behavior.
- **Don't:** treat the name of the agent currently speaking as an implicit
  scope restriction.

## Interpret instructions broadly and maximize safe progress

Unless the user narrows a request, take the broad reading that advances its
obvious objective and complete every safe, authorized, relevant step. Do not
reduce an instruction to the smallest literal action when its context makes a
larger in-scope outcome clear.

- **Do:** inspect for adjacent actionable work, resolve it, verify it, and
  carry it through the normal PR/review/monitoring lifecycle.
- **Don't:** stop at a narrow literal reading that leaves the requested outcome
  only partially achieved.

## Status requests do not make issues report-only

A request for status means examine the transcript to check if the agent got stuck, frozen, or dropped the ball, inspect live state, finish every safe, in-scope fix it reveals before reporting, resume stalled work immediately, and file every noticed issue, however small, in its owning tracker.
Detail, rationale, and cases: [`shared/workflow/status-requests-act.md`](shared/workflow/status-requests-act.md).

## Flag good moments to `/clear` in long-running sessions

[`shared/workflow/flag-session-boundaries.md`](shared/workflow/flag-session-boundaries.md) (linked, not imported: read it before declaring a stopping point)

Every message that ends a turn or a stretch of work states `**Stopping Point**: Clean stopping point reached --- session done; UMS executed; no follow-up items pending` or `**Stopping Point**: Not a clean stopping point / work remains queued: session not done; ...`.
State explicitly whether the session is done or not, confirm UMS pass, and confirm noticed follow-up items are filed.
Before every non-clean pause, arm a timer or other wake that resumes the next step, and report when it fires.
Exception: when a harness posts the final message somewhere and no person reads the session turn by turn (a CI or `@claude` workflow run), put the declaration inside the substantive reply or omit it, never after it, since the harness keeps only the last message ([rme#1081](https://github.com/d-morrison/rme/issues/1081)).
Proactively flag a good stopping point with the `⚠️ **FLAG** ---` tag.
This could be a checkpointed or wrapped multi-step task, a PR merged with no other in-flight work on this conversation, or an open question answered with nothing pending.
Place the tag at the natural end of that turn's recap (or immediately before a `wrap-up` report) rather than mid-task.
A clean stopping point requires that something actually finished, and the fragment's disqualifier list cannot tell you whether anything did --- so name the thing that finished, and read a turn that only explored as having completed nothing however few blockers it trips.
Hold the flag while any PR this session opened or pushed to is still unmerged, per the bright line the fragment states in full; run `wrap-up`'s state sweep first rather than trusting memory, since a bot-opened PR or a leftover branch never entered the conversation.
Default to archive-and-start-new over a bare `/clear` whenever the session might be worth revisiting, and to `/compact` when the next work continues the same loose thread; the fragment covers each option's tradeoff and the same menu applied at the moment of opening a *new* PR, not only at a stopping point.

## Flag good moments to run `compress-session`, too

The mid-task counterpart is covered in [`flag-session-boundaries`](shared/workflow/flag-session-boundaries.md#flag-good-moments-to-run-compress-session-too)'s section of the same name.
Don't wait for automatic compaction to guess what matters.
Flag it yourself (using the same `⚠️ **FLAG** ---` tag) once a session has grown large with a live task still in flight.
This applies when there are many tool calls, long tool outputs no longer needed, or a session is already through one auto-compaction.
Use `/clear`'s menu when there is nothing left to carry forward; use `compress-session` when there is.

## Actively manage quota usage: models, compaction, and workflow structure

Manage quota continuously with three levers, unasked: route each dispatched agent's model tier per [`when-to-orchestrate`](shared/workflow/when-to-orchestrate.md) and recommend a conductor-tier change rather than ignore a mismatch;
compress or recommend `/clear` under visible usage pressure;
and fix a procedure that is expensive by construction in its own issue or PR.
Local and on-device models are prohibited.
Detail, rationale, and cases: [`shared/workflow/manage-quota.md`](shared/workflow/manage-quota.md).

## Keep a running on-disk session lab notebook

Keep a dated, append-only `session-YYYY-MM-DD[-slug].md` notebook in the project auto-memory directory, and append a timestamped entry at every state change worth resuming from, so an interruption with no clean exit loses nothing.
Detail, rationale, and cases: [`shared/workflow/session-lab-notebook.md`](shared/workflow/session-lab-notebook.md).

## Keep ai-config and repo checkouts fresh

[`shared/workflow/keep-checkouts-fresh.md`](shared/workflow/keep-checkouts-fresh.md)

Four freshness checks to run each session: the ai-config checkout itself (on `main`, pulled --ff-only, with a safe recovery path for a diverged/orphaned local `main`), the consumer install (Claude Code and Cursor load this repo as a native plugin that auto-updates, so confirm the plugin is enabled and not doubled --- any leftover `~/.claude` copies of `shared/`, `hooks/`, or `memories/` predate the symlink-install removal and want a content diff;
sweep for a leftover `~/.claude/skills` too, in symlink form as well as copy, whose symptom is a doubled skill listing rather than drift --- a symlink into the checkout diffs clean --- and which must not be deleted on presence or on a name match, with `install-hooks.py` answering only the registration half), the working repo's own `main` checkout, and (where a consumer repo vendors ai-config as a git submodule) the `.ai-config` pin.
The fragment above carries the mechanics, the failure modes each check catches, and the case records.

## Timestamp recaps in local time

[`shared/workflow/timestamp-local-recaps.md`](shared/workflow/timestamp-local-recaps.md)

A status recap or summary carries a timestamp in the user's local zone, so "as of when" is unambiguous when they read it later.
That is the obligation;
the rest of this section governs where the time comes from.
Every clock time you write down --- that recap, a date typed into a file, a time stamped on a forge comment, a session-notebook heading --- comes from a reading taken **in that moment**, in the user's zone (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`).
A reading expires immediately, and the thing that most reliably licenses an invented stamp later is the memory of having honestly measured one earlier: the clock keeps moving while a count of elapsed tool calls does not, so the two drift apart and the drift compounds across comments posted in sequence.
The risk peaks after about 17:00 Pacific, once UTC has already rolled over.

**Print the reading.**
A reading captured into a shell variable whose only destination is a heredoc never reaches the transcript, so the next stamp you type still comes from a sense of elapsed work --- a reading you cannot quote is not a reading.
The fragment carries the platform mechanics (Git Bash silently falls back to GMT, so check the `%Z`, and use the PowerShell form when it does), every surface the drift reaches, and the measured cases.

- **Do:** run the clock command on its own, immediately before typing a time anywhere, and quote what it returned.
- **Do:** derive a time written into a file from a `date` read in the same command that writes it.
- **Don't:** infer a clock time from how many tool calls or actions have happened since the last real reading.
- **Don't:** treat an earlier honest measurement as still valid, or a reading the session never observed as one it did.

`hooks/no-unmeasured-clock-claim.py` reads the reply at `Stop` and `hooks/flag-unmeasured-timestamp.py` reads a comment body at `PreToolUse`;
both warn, never block, when a Pacific clock time appears with no clock read in the transcript since the turn began (ai-config#2903).

## State the actual time when reporting a scheduled check-in

When reporting a scheduled wakeup or check-in, state the clock time it fires at in Pacific time ("I'll check back at 08:22 PT (~4 min)"), not only the delay.
Detail, rationale, and cases: [`shared/workflow/state-check-in-time.md`](shared/workflow/state-check-in-time.md).

## Bare keyword directives

Three families of slash skill read as directives when I write them **without** the leading slash: the **queue commands** that amend the task list, the **judgment grants** that hand a decision back to you, and the **orchestration commands** that cap a run already in flight.

### Queue commands

I maintain a family of slash skills for managing the task queue and amending requests: `/also`, `/first`, `/next`, `/before`, `/last`, `/and`, `/remember`, `/always`, and `/cascade`.
When I write one of these keywords **without the leading slash** as a directive — e.g. "also fix the test", "remember that ...", "always link PRs in tables", "and bold it", "next, run the spellcheck", "first, revert that" — interpret it using the corresponding skill's semantics rather than as ordinary prose. (`/remember` and `/always` both route to the `memorize` skill; "cascade" means merge stacked PRs' base branches into the PRs stacked on top of them — including main into unstacked PRs — never the PRs into main; see the `cascade` skill.)
When the word is genuinely just part of a sentence (ambiguous), fall back to the plain reading.

### Judgment grants

The same bare-keyword reading applies to the judgment-grant keywords, which are not queue commands and differ from each other in scope.
`daytb` ("do as you think best", and its longhand `do-as-you-think-best`) hands back **one** decision: choose what you would have recommended, act, and report the choice in the past tense -- it expires with that task.
`away` is the session-scoped version, presuming I am not there to answer at all, and `back` revokes it.
`mwc` is the separate grant covering merge authority, which none of the others extend to.
Read a bare "do as you think best" as `daytb`, not as `away` -- the session-wide reading suspends clarifying questions long after I expected them back.
`dmmhyh` ("don't make me hold your hand") is a correction rather than a proactive grant: it fires when I'm asking for more guidance than the moment calls for.
It resolves the pending item like `daytb`, raises the decide-vs-ask threshold for the rest of the session like `away`'s judgment-call test, and -- unlike either -- writes the correction down as a memory entry so it doesn't have to be re-taught next session.
See [`dmmhyh`](skills/dmmhyh/SKILL.md).

### Orchestration commands

`fw` ("finish the current wave but don't start a new one", longhand `finish-wave`) caps an orchestration run at the wave already in flight.
It bounds *issue grabs* only, so the review rounds, fixes, and the owed UMS pass that finish the wave's PRs all run under it.
See [`finish-wave`](skills/finish-wave/SKILL.md).

- **Do:** read a bare "finish the current wave" as `fw`, hold every new grab, and drive the wave's open PRs to a terminal state.
- **Don't:** read it as "open no more PRs" --- a UMS PR or a follow-up issue is not a grab from the backlog.

## Link PRs in tables

Link every PR, issue, comment, review, or run you mention having acted on, in tables and chat prose alike, e.g. `[#237](https://github.com/<owner>/<repo>/pull/237)`.
Detail, rationale, and cases: [`shared/writing/link-forge-artifacts.md`](shared/writing/link-forge-artifacts.md).

## Tag chat output by category so long recaps stay scannable

Box (a `===` line above and below) only what the user is waiting on: ❓ **QUESTION**, 💡 **OFFER**, 🛑 **BLOCKER**, ✅ **ANSWER**, 🧭 **RECOMMENDATION**, and `### 🔀 MERGE ORDER` as a heading.
Prefix without a box the informational ones: 📊 **UPDATE**, ⚠️ **FLAG**, ✔️ **DONE**, 🟢 **ALL CLEAR**.
Detail, rationale, and cases: [`shared/writing/tag-chat-output.md`](shared/writing/tag-chat-output.md).

## Never close a reply by offering to do work you are already allowed to do

[shared/workflow/no-cop-out-offers.md](shared/workflow/no-cop-out-offers.md)

"Say the word and I'll push."
"Want me to kick off the re-run?"
Each reads as courtesy and delivers nothing: the work does not happen, you
spend a turn, and the reply reported nothing.

The phrase is not the defect --- asking before a merge, a force-push, or a
deletion is correct, and those sentences look identical.
What decides it is whether the action was **already authorized**, by a
standing instruction, a `daytb`/`away` grant, or your having asked for the
outcome earlier.
When it was, the offer is avoidance wearing courtesy, and the cost is
asymmetric: an unwanted action is cheap to revert, while an unanswered offer
leaves no branch, no PR, no issue --- nothing another session could find.

`hooks/flag-cop-out-offer.py` is the instrument.
It warns rather than blocks, because authorization is not lexically decidable.

- **Do:** perform the authorized action and report it in the past tense.
- **Do:** ask plainly, with no offer wording, when the action is genuinely
  unauthorized and destructive or outward-facing.
- **Don't:** attach a user-conditional to work a standing instruction covers.
- **Don't:** close a status recap with an offer --- that is where this hides.

## Always produce a reply --- never end a turn silently

End every turn with user-visible prose, however short: after an interruption, on resuming from a context-window summary, on a no-change tick, and even when a harness wake says to re-arm silently.
Never reply with a placeholder such as `No response requested.` (`hooks/no-placeholder-reply.py` blocks it).
Detail, rationale, and cases: [`shared/workflow/always-reply.md`](shared/workflow/always-reply.md).

## Surface merge-order constraints

When merge order changes the outcome, say so where it will be acted on: the `### 🔀 MERGE ORDER` chat marker, a `> [!IMPORTANT]` alert leading each affected PR body, and draft-gating only as a last resort.
Derive file-set overlap with `python3 scripts/pr-overlap.py` rather than recalling it, and check dependencies separately, since an empty overlap cannot see them.
Detail, rationale, and cases: [`shared/workflow/surface-merge-order.md`](shared/workflow/surface-merge-order.md).

## Present decisions one at a time

Pose only the single most pressing decision, say how many more are queued, and fold each answer into the next, unless the user asks for the whole backlog (`prompt-me-all`).
Detail, rationale, and cases: [`shared/workflow/present-decisions-one-at-a-time.md`](shared/workflow/present-decisions-one-at-a-time.md).

## Title Claude sessions with the PR/issue number

Name each Claude Code session (the title shown in the web/app session sidebar) `#NNN brief description` — the number of the PR or issue the session is working, then a short description.
Don't prefix it with "PR" or "Issue"; just the bare `#NNN`.
So `#316 session title convention`, not `PR #316 session title convention` or `PR session title convention`.

## Re-check for latest review findings before reporting PR status

Before reporting on a PR, pull every review round, formal review state and body, and inline comment fresh;
green checks, a login-filtered query, or a later clean bot verdict over a human's `CHANGES_REQUESTED` are not a clean review.
(A specific case of the standing **never assume;
always verify** rule in `memories/preferences.md` --- confirm the verdict with a fresh query, don't recall it.)
Detail, rationale, and cases: [`shared/workflow/recheck-review-findings.md`](shared/workflow/recheck-review-findings.md).

## Post in-chat feedback to the PR

Paraphrase the user's in-chat feedback about an in-scope PR as a one-to-three-sentence PR comment that carries the agent-authorship marker.
Detail, rationale, and cases: [`shared/workflow/post-feedback-to-pr.md`](shared/workflow/post-feedback-to-pr.md).

## Subscribe to PR updates automatically

When opening or taking over a PR in any repo, subscribe/watch that PR's activity immediately using the available GitHub notification/subscription mechanism.
Subscribe only after the PR creation call returns, using the returned number or URL --- never batch subscription with creation or predict the number.
If the current session's tools cannot subscribe, say so explicitly and fall back to active polling for reviews, comments, and checks during the session.

## Monitor every pushed PR head to completion

After a push you end a turn on, arm a timer that polls that head until CI and the current-head review are fully clean, falling back to self-review when the reviewer fails.
Then keep the lower-frequency PR watch running until merge or close, and restart the head poll on any regression.
Detail, rationale, and cases: [`shared/workflow/monitor-pushed-heads.md`](shared/workflow/monitor-pushed-heads.md).

## Claim a GitHub PR/issue before working on it

[`shared/workflow/claim-pr.md`](shared/workflow/claim-pr.md)

The `claim-pr` skill operationalizes this (the exact claim wording, when it applies, and the closing/unclaim comment).

## Every comment you post to a forge says an agent posted it

[shared/workflow/disclose-agent-authorship.md](shared/workflow/disclose-agent-authorship.md)

A comment posted through `gh`/`glab` under the account holder's credentials carries **their** login and reads as `type: User`, so nothing in the API distinguishes it from a comment they typed --- `memories/gh-cli.md` records auditors mistaking exactly that.
The forge cannot say it, so the body must: end every agent-posted comment with

```
_Posted by Claude Code (AI agent) --- not written by a human._
```

The marker deliberately avoids the robot emoji, which `scripts/check-pr-fully-clean.py` matches as a `REVIEW_BODY_MARKERS` entry --- a disclosed claim comment would otherwise scan as a finding-free **review**.
The fragment carries the rest: the two exemptions, the comment-bodies-only scope, and the queries that verify a marker or a bot identity.

- **Do:** append the marker to every claim, release, status, reply, and self-review comment, including ones whose prose already names the session.
- **Don't:** use the robot emoji in it, or put it in a commit message, a title, an issue body, or a PR body.

## Read a repo's canonical contributor doc before starting work, not just before pushing

[shared/workflow/read-canonical-doc-before-starting.md](shared/workflow/read-canonical-doc-before-starting.md)

When a short `CLAUDE.md` names a fuller document as the actual authority --- `.github/copilot-instructions.md`, `CONTRIBUTING.md`, a linked style guide --- read that document before the first edit, and front-load its pre-PR requirements into the first commit rather than discovering them via a red CI check.

## Open a PR immediately after claiming an issue

[`shared/workflow/pr-on-claim.md`](shared/workflow/pr-on-claim.md)

The strong form of the claim: after claiming an issue you're about to work, open the PR right away — before implementing — from an empty commit, kept as a draft until the implementation lands.
An open PR is the visible in-flight signal other sessions check, so opening it up front stops parallel duplicates.
The `gi`, `gii`, `gip`, and `st` skills operationalize this.

## Every self-review is an adversarial review by a separate subagent

[shared/workflow/adversarial-self-review.md](shared/workflow/adversarial-self-review.md)

Whenever reviewing your own work is called for --- before a push, as the fallback when the external reviewer is down, or the project-conventions pass --- dispatch it to the [`adversarial-reviewer`](.claude/agents/adversarial-reviewer.md) subagent (foreground, read-only) against `git diff origin/<default-branch>...HEAD`, and treat its findings as findings.
The authoring session cannot do it inline: it knows what the change was *meant* to say, so it reads the diff and recovers the intent, which is confirmation rather than review.
Brief the reviewer with the diff and the standards, never with the rationale for the change --- handing over your account of it is what makes the reviewer agree with you.
`hooks/no-push-without-self-review.py` gates the pre-push case on Claude Code.
The fragment covers the rest, including why a same-vendor subagent buys independence of *intent* and not of blind spot.

## Open a PR for every pushed feature branch

After pushing a feature branch, create its PR
unless an existing PR already represents that branch
or the user explicitly says not to.
Don't treat a successful push as the handoff:
the PR is the reviewable unit and the durable visible record of the work.

## Use the existing PR branch, not the harness-specified branch

[`shared/workflow/use-existing-pr-branch.md`](shared/workflow/use-existing-pr-branch.md)

## Skills that call gh/glab: fall back to tool-mappings.md in remote sessions

Many skills under `skills/` name concrete `gh`/`glab` CLI commands (e.g. `gh pr comment`, `gh issue create`).
In a remote/web session where `gh`/`glab` isn't on `PATH`, substitute the equivalent GitHub MCP tool from [`tool-mappings.md`](tool-mappings.md) instead of failing or improvising.
That registry is the single source of truth for the gh/glab-to-MCP mapping in this repo --- don't inline a separate translation table into individual skills; point to `tool-mappings.md` and let it stay the one place to update. (GitLab operations have no MCP equivalent listed there; `glab` stays CLI-only.)

## Install and use MCP servers proactively

[shared/workflow/use-mcp-servers.md](shared/workflow/use-mcp-servers.md)

The section above is about substituting an MCP tool for a CLI command when the CLI is missing.
This one is the other direction: when a server would help, install and register it rather than waiting to be asked --- including locally, where `tool-mappings.md`'s per-model table describes the default rather than a limit.
Covers reading `claude mcp list` for transport rather than name (a plugin's remote server can shadow the local one you meant), 400-versus-401 on an uninterpolated credential, supplying tokens by launch wrapper instead of storing them, opt-in toolsets whose selection *replaces* the default, and verifying by a real call rather than by the tool listing.
Its last section generalizes past MCP: when a standing rule names a mechanism this session doesn't have, look for the local equivalent instead of silently degrading to a worse fallback.

## Search for and install plugins proactively

[shared/workflow/use-plugins.md](shared/workflow/use-plugins.md)

Proactively discover, evaluate, and install plugins across Claude Code (`claude plugin marketplace list`, `claude plugin marketplace update`, `claude plugin install`), Antigravity (`.agents/plugins.json`, `~/.gemini/config/plugins.json`), Codex (`codex plugin marketplace add`, `codex plugin add`), and Cursor when a task would benefit from specialized domain tooling or workflow automation.
Covers marketplace verification, permission review, avoiding redundant submodules, and testing live tool activation.

## File an issue before starting a new task

[`shared/workflow/issue-first.md`](shared/workflow/issue-first.md) (linked, not imported: read it before filing or deferring)

Before branching, editing, or opening a PR for new work, search the tracker across all states (`gh issue list --state all --search`, `glab issue list --all --search`) and file an issue if none covers the task;
surface a closed match and confirm rather than redoing the work.
Label every agent-filed issue `ai-authored` and `model:<model-id>` in the creating command.
The `st` (Start Task) skill operationalizes this; `gi` (Grab Issue) is the path when the issue already exists.

Its last section is the mirror, and it covers requests that arrive rather than work you go looking for: a request the user makes mid-flight may be deferred on your own judgment when it would grow the change past what it set out to do, provided the deferred item is filed as an issue in the same reply and the reply says what was deferred and why.
The grant is latitude rather than an instruction, and the tracking issue is the whole of what licenses it --- an untracked deferral is a dropped request wearing the vocabulary of scope discipline.
Read the fragment's boundary with `dont-incur-technical-debt` before invoking it, since a defect inside your own diff stays yours to fix now.

## Issue or discussion? Pick the venue by best practice, not by precedent

[shared/workflow/choose-issue-or-discussion.md](shared/workflow/choose-issue-or-discussion.md)

The companion to issue-first above: that rule settles *whether* something is tracked before work starts, this one settles *where* it lands.
Actionable work is an issue.
An open-ended policy question whose deliverable is a decision, and which has a real do-nothing option, is a discussion --- in an answerable category (`Q&A`) so the resolution can be marked as the answer.
Its second half is the general principle: best practice outranks repo precedent when choosing venue or method, and "the board is unused, so nobody would find it there" is circular reasoning that can never permit anyone to start using it.

## Triage the backlog weekly; closing as not-planned is licensed

[shared/workflow/triage-backlog.md](shared/workflow/triage-backlog.md)

The counterweight to the filing rules around it.
Every open issue ends the weekly pass carrying one of `P1`, `P2`, `P3`, or closed, and a bare aphorism, a filing-mechanism test, or a duplicate may be closed as not-planned on the pass's own judgment.
A new symptom of a tracked defect family is a comment on that family's issue, not a new issue.
`scripts/triage-backlog.py` is the instrument and the `triage` skill runs it.
(Measured 2026-09-03: 15 to 410 open issues in six weeks with 14 not-planned closes in the repo's history, ai-config#3134.)

## If you see something, say something --- file an issue for every noticed mistake, concern, or idea, your own mistakes included

[shared/workflow/report-mistakes-proactively.md](shared/workflow/report-mistakes-proactively.md)

The proactive counterpart to issue-first above: when a mistake shows up in any medium (code, prose, AI-config files, `gha` workflows, or other generated files),
even if it is out of scope for the current task, flag it in chat (`⚠️ **FLAG** ---`),
and file a tracking issue immediately, in a repo we administrate.
Never file autonomously in an external repo; the upstream-issues ladder governs that case.
The `defer-issue` skill covers the user-initiated version of this; this rule is self-initiated.

## Say when a practice is slipping, not only when an artifact is wrong

[shared/workflow/flag-practice-slippage.md](shared/workflow/flag-practice-slippage.md)

The counterpart to the rule above, for *practice* rather than for artifacts: that one governs a mistake in a thing and its deliverable is a filed issue, this one governs how the work is being done and its deliverable is one sentence at the moment it is actionable.
The outward direction is already covered by the review fragments and needs no restatement.
The two that need stating are inward, unprompted and outside any review loop, and **upward** --- telling me when *my* practice is slipping, which will not happen by default because deference costs nothing at the moment it is chosen and reads as politeness.
Name the specific practice and gap, cite the rule or label the opinion as an opinion, say it before the action rather than in the retrospective, and say it once --- the decision stays mine, and this is not a licence to relitigate it.

## Learn from every reviewer finding you accept, not only from your own admissions

[shared/workflow/learn-from-review-findings.md](shared/workflow/learn-from-review-findings.md)

The external-correction counterpart to the UMS triggers at the top of this file: those fire on a first-person admission ("I was wrong"), which is why `hooks/remind-ums-after-error.py` deliberately excludes correcting someone else.
Agreeing with a reviewer is the commoner case and the one that machinery misses --- you admit nothing, you accept a finding --- so an accepted finding is a first-push miss to record and, where a decidable condition exists, to algorithmatize, per the goal that every PR gets a clean review on the first push.
`hooks/remind-learn-from-review.py` is that trigger;
like its sibling it only ever adds context and never blocks.
It is registered in `hooks/hooks.json`,
which binds it on the plugin path
and is what `install-hooks.py --fix` binds on the non-plugin path.

## Tracking issues in upstream repos

[shared/workflow/upstream-issues.md](shared/workflow/upstream-issues.md)

The `sup` / `send-upstream` skill operationalizes steps 1--2 (the PR path, including fork-if-needed, and the issue path) and the link-back.
Step 3 (own-repo fallback) is not covered by `sup`; use `gh issue create` in the current repo and ask the user to transfer it.

## Wrap up a merged PR with UMS

When a PR you drove merges, run `post-merge` (verify the merge, tidy the branch, confirm follow-up issues, then UMS) without asking;
a bare "merge it" runs `merge-it`, which chains into `post-merge`.
Detail, rationale, and cases: [`shared/workflow/wrap-up-merged-pr.md`](shared/workflow/wrap-up-merged-pr.md).

## When you revert a merge, reopen its issue

[`shared/workflow/revert-merge.md`](shared/workflow/revert-merge.md)

GitHub does not automatically reopen the issue a reverted PR closed.
Reopen it explicitly (`gh issue reopen <issue-number>`).

## What "fully clean" means

[`shared/workflow/fully-clean.md`](shared/workflow/fully-clean.md)

Escalate a deadlock via the `request-pr-review` skill, which resolves `<reviewer>` from the repository's configured human reviewer or its CODEOWNERS entry rather than from a name written here, and surface the open item to me.

## Always run ARDI on PRs you touch

[`shared/workflow/ardi.md`](shared/workflow/ardi.md)

The `ardi` / `iterate` skill family runs this loop. (See *What "fully clean" means* above; the mechanics for each step are in the sections around here.)

## Do the review yourself when the @claude workflow doesn't produce a verdict

[`shared/workflow/self-review-fallback.md`](shared/workflow/self-review-fallback.md)

When the `@claude` review workflow fails to produce a usable verdict --- quota-skipped, a stub review with no stated `### Verdict`, or no review workflow configured at all --- don't stall ARDI waiting for it: post a self-review at the same standard the bot would apply (including the prose fact-check, not just structural checks), request any other reachable reviewer in parallel, and keep driving to fully-clean.
A fallback self-review is easy to under-scrutinize precisely because it feels like a stopgap; the fragment names the specific gap (structure checked, fact-check skipped) and holds the fallback to the bot's own bar.

## Watch and ARDI every PR you touch --- don't ask first

Subscribe to and ARDI-loop every PR you drive, unasked, until it merges or closes, re-arming a wake because webhooks miss CI success and merge state.
After a push, don't also post "@claude review again";
and on a PR you were asked only to review, leave findings without pushing, iterating, or merging.
Detail, rationale, and cases: [`shared/workflow/watch-and-ardi.md`](shared/workflow/watch-and-ardi.md).

## Babysit PRs efficiently — batch pushes, trust CI's own reports, skip redundant lookups

[shared/workflow/efficient-pr-babysitting.md](shared/workflow/efficient-pr-babysitting.md)

A long babysitting session accumulates avoidable tool calls and CI runs otherwise:
trickled single-item pushes each re-trigger CI and race each other's reviews,
a local re-run can rediscover a gap CI's own comment already named,
and a pure re-post webhook event doesn't need fresh analysis.

## Address every in-scope review comment, even non-blockers

[`shared/workflow/address-every-comment.md`](shared/workflow/address-every-comment.md)

If you and the reviewer reach an impasse on a single item (your rebuttal didn't convince them and their re-raise didn't convince you), escalate that item to a **human reviewer** — request human review via the `request-pr-review` skill (or `gh pr edit <N> --add-reviewer <reviewer>`) and `@`-mention them with the impasse — for the final call rather than looping.

## Request review and drive every started PR to clean

Whenever starting or working on a Pull Request:
1. **Trigger AI review when done pushing**: In repositories where reviews do not auto-trigger, request an AI review (`@claude review` comment, or dispatch `claude-review.yml`) **after completing all code pushes** for the round, not when the PR is first opened and empty.
   In repos that automatically trigger review on PR events (`pull_request` synchronize, opened, ready_for_review), do NOT manually trigger a redundant review if an automated review is already running or queued.
2. **Drive to clean**: Run `ardi` / the review-and-iterate loop to ensure CI passes and all review findings are addressed until the PR reaches a clean verdict.
3. **Request human review only after AI approval or deadlock**: Per [`copilot-review-before-human.md`](shared/vendored/copilot-review-before-human.md), request human review (configured repo reviewers per `skills/request-pr-review/SKILL.md`) **only after** the AI review produces a clean/approved verdict, or if an impasse/deadlock occurs.

- **Do:** Trigger AI review (or let the automated PR review run) after completing code pushes, and request human review only after the AI review is clean/approved (or upon an impasse).
- **Don't:** Manually trigger a redundant `@claude review` comment when an automated review is already running or triggered by the push/ready event.
- **Don't:** Request human review when the PR is first opened empty, before code pushes are complete, or before the AI review has passed / produced a clean verdict.


## Check the remote immediately before every push

[`shared/workflow/check-before-pushing.md`](shared/workflow/check-before-pushing.md)

Take a fresh `git ls-remote` reading of the branch immediately before every `git push` --- not at the start of the round, not when you last synced, not when you opened the PR.
The branch you cut and whose PR you opened is the one you are *least* likely to check, because ownership makes the check read as ceremony rather than as a question with an unknown answer.
`claim-pr` records three ways it gains another agent's commits anyway (the `@claude` agent's `main`-sync, a second CLI session, a human), and every recovery procedure there runs *after* the collision.
An earlier fetch is a measurement of a moment that has passed, and it expires exactly the way a clock reading does.

`--force-with-lease` alone is not the safe form, which no site in this corpus previously said: the lease compares against your remote-tracking ref, so any background fetch silently satisfies it over the very commits it was protecting.
Always pair it with `--force-if-includes` (added in Git 2.30.0), and note that pairing `--force` *with* the lease is not a middle ground --- git documents `-f, --force` as one that "disables that check, the other safety checks in PUSH RULES below, and the checks in `--force-with-lease`".
A `stale info` refusal is not a reason to force either.
It reports only that your remote-tracking ref no longer matches the remote, and never why --- the branch may have been deleted (which recurs on this repo's flow, after a squash-merge with auto-delete), a peer may have pushed, or you may never have fetched it.
`git ls-remote --heads origin <branch>` settles existence and nothing further: empty means deleted.
Non-empty means the branch is live, so compare its tip against the ref you are pushing before choosing a remedy --- an ancestor tip fast-forwards, and only a diverged one needs a reconcile.
When it is empty, query `gh pr list --state all --head <branch>` before a plain push.
MERGED means auto-delete, not a first publish: do not recreate
(see [`check-before-pushing`](shared/workflow/check-before-pushing.md)).
Otherwise a plain push is the fix.
`ALLOW_FORCE_PUSH=1` is an escape valve for a case the guard did not foresee, and using it means stating why.
`hooks/no-clobbering-push.py` is the mechanism: it refuses a bare force push, whose remedy costs one word, and only warns on a divergence, whose significance it cannot judge.

## Keep PR branches synced with main

[`shared/workflow/sync-with-main.md`](shared/workflow/sync-with-main.md)

(Another instance of **never assume; always verify** — `git fetch` to check main's actual position instead of assuming the branch is current.
The `sync-pr-branch` / `merge-main` skill runs this.)

## Batch merge and resolve, always

The section above is one branch against `main`.
When **several** open PRs need syncing or conflict resolution, do them together in one pass rather than chasing each one's conflict flag as it appears.
The batch pass is the default, not a recovery step for when serial chasing has already failed.

[`shared/workflow/batch-merge-and-resolve.md`](shared/workflow/batch-merge-and-resolve.md)

The key points, restated here because a bare pointer is invisible to a consumer that doesn't load the fragment:

- **Serial chasing cannot converge when the base's merge interval is shorter than a review round.**
  Both are measurable, so compare them rather than judging: `git log origin/main --first-parent -10 --format='%ct'` for the merge rate, and the review check's own `startedAt`/`completedAt` for the round.
  Count **first-parent** commits, not merge commits --- `git log --merges` reports nothing in a squash-merging repo.
- **A `DIRTY` flag means stale or defective, and only the second is a defect.**
  A PR whose content is clean but whose base moved is stale rather than broken.
  Staleness resolves once, at merge time, so re-syncing it eagerly spends a CI cycle and a review round on a state that expires within one merge interval.
- **A conflict your sweep found is not a conflict your merge caused.**
  Attribution is a second axis, and it runs before the claim: intersect the merge's own deleted and renamed paths (`git diff --name-status -M "$merge^1" "$merge" | grep -E '^(D|R)'`) with each conflict, and report conflicts caused alongside conflicts found.
  `git show --name-status <merge>` cannot supply that set for a **true** (two-parent) merge --- it prints no file list at all there, and grepping its header for `^[ADMR]` returns three phantom paths.
  It does diff a squash merge normally, so whether it works depends on how the repo merges rather than on the commit in front of you.
  A conflict you caused on a PR that fails `memories/reviewing-prs.md`'s scope test is a report to the user, not a comment or a push.
- **Independent per-PR checking cannot see pair collisions.**
  Every PR can be clean against `main` while two of them conflict with each other.
  Only a pairwise `git merge-tree` between PR heads finds that.
- **Any sweep needs a negative control**, run first.
  A zero matrix is indistinguishable from a detector that never ran, and `merge-tree` has two ways of producing one: the legacy three-arg form always exits 0, and its conflict markers are diff-indented, so `grep '^<<<<<<<'` misses them.
  Report how many pairs were examined, not only how many conflicted.
- **`merge=union` raises the stakes rather than lowering them**, since it resolves append collisions with no conflict to review.
- **"No conflict" is not an all-clear.**
  Version parity and Markdown list-item splices both arrive through cleanly-resolved merges with nothing red to point at.
  The transferable lesson: when a defect can be introduced by **deleting** a line, any instrument keyed on added lines is unsound for it --- use a count delta across the merge instead.

## Move referenced assets along with content that migrates or gets removed

<!-- Not yet shared with the lab manual; edit shared/workflow/migrate-referenced-assets.md, not here. -->
[shared/workflow/migrate-referenced-assets.md](shared/workflow/migrate-referenced-assets.md)

## Fixing your own mistakes is always top priority

[shared/workflow/fixing-mistakes-is-top-priority.md](shared/workflow/fixing-mistakes-is-top-priority.md)

Remediating mistakes, bad merges, regressions, broken tests, or policy violations is the absolute top priority, superseding feature development and backlog work.
Immediately after reverting or fixing the mistake, creating or repairing a mechanical prevention system is the unconditional next priority.

## Prioritize internal infrastructure work slightly over feature work

[shared/workflow/pr-prioritization.md](shared/workflow/pr-prioritization.md)

A tie-breaker for `ardia`'s PR-ordering step and `gi`'s (and `gii`/`gip`'s) issue-priority table when candidates are otherwise close in priority.
The fragment also sets the default direction for the age factor: among several open PRs, take the **older** one first unless you have more specific instructions.

## Use subagents when helpful --- and delegate rather than queue

[shared/workflow/use-subagents.md](shared/workflow/use-subagents.md)

Nothing parallelizable should ever sit "queued" --- writing "queued", "next up", "I owe you X", or "still need to" into a status recap is the trigger to launch a subagent on it right then, not a way to describe the plan.
Sidecar delegation (independent investigation, verification, a disjoint slice, an owed UMS pass, a routed `cai`) is pre-authorized and never worth asking about; keep only the blocking critical-path edit local.
Research and reading are dispatchable too, sized by how much comprehension the result needs rather than by how small the fetch looks --- the fragment above covers why that category of work is easy to route wrong without anything in the artifact showing it.

## Never launch a subagent on Fable without explicit, specific permission

Pass `model` on every `Agent` call and `Workflow` `agent()` call, and never launch a subagent on Fable without the user's explicit permission for that launch (`hooks/no-fable-subagent.py`;
`FABLE_SUBAGENT_OK=1` on the approved command only).
Detail, rationale, and cases: [`shared/workflow/no-fable-subagents.md`](shared/workflow/no-fable-subagents.md).

## Derive a set of work items; never hand over an enumeration of it

The section above governs *whether* to dispatch.
This governs how to **scope** what you dispatch.
A brief that lists PR or issue numbers is a snapshot, stale the moment it is written.
Before dispatching work scoped to a list, ask whether that set can grow or change while the work runs.
When it can, hand over the query that derives it rather than the list itself.

The failure is invisible by construction, which is why it needs a rule rather than more care.
Every agent does its job correctly on the list it was given, so the items that appear *between* the lists are covered by nobody, and no artifact reports it --- coverage is a property of the set rather than of any member.
`scripts/pr-sweep.py` is the deterministic half for open PRs, and reports what it examined rather than only what it found.

[`shared/workflow/derive-dont-enumerate.md`](shared/workflow/derive-dont-enumerate.md)

## Help your subagents improve over time

[`shared/workflow/improve-your-subagents.md`](shared/workflow/improve-your-subagents.md)

The brief, the memory a dispatched agent can read, and the loop that feeds findings back to it are the orchestrator's, so the agent's mistake rate is too.
`AGENTS.md` carries the rule;
the fragment carries the mechanisms (a per-agent mistake ledger prepended to every brief, a loop change after every fix round, rounds-to-clean as the measure, promotion into skills and hooks).

## Subagent worktrees are assigned, and an incident never silently repeals a decision

Set `isolation` on every `Agent` call or decide explicitly that it needs none, brief isolated agents to stay in their worktree and push early, and ask an agent before touching its worktree.
More generally, when an incident makes you stop doing something you decided to do, re-argue the decision or fix the misuse;
never just change the behaviour.
Detail, rationale, and cases: [`shared/workflow/assign-subagent-worktrees.md`](shared/workflow/assign-subagent-worktrees.md).

## Non-destructive actions

Standing grant, recorded universally in `AGENTS.md` ("Default to action without asking"): proceed with non-destructive steps without asking, and ask only for destructive, ambiguous, high-impact, or genuinely blocking choices.

## Auto-orchestration: always look for Workflow opportunities

The heavy, parallelizable skills (`ardia`, `ardiaei`, `gia`, `gip`, `grade-work`, `opposition-research`, `find-overlap`) decide on their own whether a task warrants multi-agent orchestration via the `Workflow` tool --- so I don't have to type `ultracode` every time.
The `Workflow` tool stays opt-in-gated for bare prompts; an invoked skill is itself the sanctioned opt-in.
Launch a workflow directly when an opt-in signal is already present (`ultracode`, a `+Nk` budget, or "use a workflow"), otherwise propose one with a one-line cost estimate and wait.
The PR/issue-iteration skills stay serial where pushes collide on shared review runners (see the fragment's shared-runner exception).

More generally --- not just inside the named heavy skills --- always look for opportunities to automate work via the `Workflow` tool.
When a task turns out to be workflow-shaped (decomposable, verification-bearing, and at a scale that earns it --- see the fragment's criteria), say so and propose a workflow even if no skill mandated one.
The same opt-in gate still applies: propose with a cost estimate and wait unless an opt-in signal is already present.

[`shared/workflow/when-to-orchestrate.md`](shared/workflow/when-to-orchestrate.md) (linked, not imported) carries the criteria, the shared-runner exception, and per-agent model and effort routing;
read it before launching or proposing a workflow, and before choosing a dispatched agent's model.

## Agent teams: a third parallelism primitive, human-gated and advisory

The corpus governs two primitives a session invokes itself --- a single `Agent` call ("Use subagents when helpful", above) and the `Workflow` tool ("Auto-orchestration", just above).
An **agent team** is the third: several separate Claude Code sessions (a lead plus teammates, each its own context window) that coordinate through a shared task list and a mailbox and **message each other directly**, rather than only reporting back.
Unlike the other two, a session cannot form one on its own, so the corpus's role is only to *recommend* it.

The discriminator across all three is one question: **do the workers need to communicate with each other, or does a human want to steer individual workers mid-run?**
No to both --- a subagent or a `Workflow` sweep, per the rules above.
Yes --- an agent team, and only if it is enabled.

**Never assume a team is available, and never author a step that spawns one.**
Agent teams are experimental and off by default (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), and are spawned by the *user* in natural language and steered through an interactive agent panel --- not invoked by an autonomous or headless session.
So a recommendation to the user is the only correct output; a skill or `Workflow` step that forms a team is a bug.
The one concrete reuse angle: a `.claude/agents/<name>.md` subagent definition doubles as a teammate role (its `tools` and `model` apply, and its body is appended to the teammate's prompt), but its `skills`/`mcpServers` frontmatter is not applied to a teammate.

[shared/workflow/agent-teams.md](shared/workflow/agent-teams.md)

## Algorithmatize checks: instruments over LLM reasoning

Never spend LLM reasoning on a check a deterministic algorithm can decide:
build or run the instrument (a repo script, a CI step, a state dump plus a
threshold) and consume its verdicts, reserving model judgment for the
genuinely semantic remainder.
When you catch yourself (or a reviewer) re-deriving numbers by hand, or
eyeballing an artifact for a property with a numeric definition, that check
wants to be an instrument --- see the fragment for the procedure and tells.
Apply this in review too: a hand-run check where an instrument is possible,
or a threshold asserted rather than derived, is a review finding, the same
weight as any other standing review check.

[`shared/workflow/algorithmatize-checks.md`](shared/workflow/algorithmatize-checks.md)

## Automate everything: deterministic tools over work done by hand

Never do by hand any work that can be automated.

The section above governs *checks*.
This is the same instinct over the work itself: prefer deterministic,
inspectable algorithms to model reasoning wherever one will serve, and where
none exists, build it.
Read "work" broadly --- the rule is not about judgment but about doing by hand
what something else already computes,
which includes work carrying no judgment at all.
A hand-typed section number is nobody's decision;
it is a value the renderer already produces, kept in a second place by hand,
and it goes wrong the moment anything enables the real generator.
One principle with two faces, both binding at once --- a **constraint** on the
task in front of you (use the instrument that exists) and a **goal** over time
(build the one that does not, so the constraint gets cheap to obey).
The observable trigger is recurrence: after doing the same judgment task
twice, the third time is a tool.

The argument the checks fragment does not make is **inspectability**.
An algorithm can be read before it runs, reviewed by someone who does not
trust its author, diffed, and re-run to the same answer; model reasoning is
none of those.
That is why a hook beats a rule even when the model would usually follow the
rule.
Applies in every repo, research code included --- a hand-run analysis step or
an eyeballed validation is the same shape as a hand-composed status line.
Design and genuine judgment remain, but as the residue not yet automated
rather than a fixed reserve.

[shared/principles/deterministic-tools.md](shared/principles/deterministic-tools.md)

## Checklists: Do-Confirm, Read-Do, pause points, killer items

Where a check is mechanical but no instrument can decide it -- because it
spans several unrelated observations at one moment, like a pre-push sweep --
the instrument is a **checklist**, and the same discipline applies.

Add one only where a failure is repeatable, expensive, and mechanically
observable, then get four things right:

- **Type.** *Do-Confirm* (work freely, then stop and confirm) is the default.
  Use *Read-Do* (read each item and perform it in order) only when
  reordering the steps changes the answer, or when a step cannot be undone --
  a merge, a release, session-start freshness.
- **Pause point.** State the moment it fires as an observable event ("before
  `git push`", "before reporting the PR ready"), not a topic.
  A checklist with no trigger is read only by whoever was already careful.
- **Killer items.** Mark the one or two steps most often skipped and most
  costly to skip, since a flat list gets triaged under pressure and the
  dropped item is usually the one that looks like bookkeeping.
  The known ones: the UMS pass ending `post-merge`/`ardi`, and `wrap-up`'s
  state sweep.
- **Length.** Five to nine items, action plus evidence.
  Past that it has started teaching; move the explanation into the prose
  above it.

Treat every checklist as a draft until it has been run on real work, and
treat UMS as its revision loop: when a checklist was followed and the failure
happened anyway, the finding is about the checklist, not only the incident.
Don't checklist-ize skills that are mostly design judgment, exploratory
research, or one-off improvisation.

[`shared/workflow/skill-checklists.md`](shared/workflow/skill-checklists.md)

## Never pattern-match blindly: check the purpose transfers

Before reusing a structure --- a template, a working script, a neighbouring
file's shape, a pattern from another tool --- state what the original was
**for** and what the new one is **for**, and confirm those are the same kind
of thing.
Structural fit is necessary and never sufficient.

The tell is that every check you naturally run after adapting a template asks
whether the *mechanism* works, and none asks whether the *purpose* survived
the substitution: same interface, passing tests, and the thing now does the
opposite of what it should.
A template you wrote yourself recently gets the least scrutiny, because
reusing something you just verified feels like consistency rather than like
assuming --- which inverts the scrutiny the situation warrants.
This is not an argument against reuse; it is the check that makes reuse safe.

[`shared/workflow/check-purpose-before-reusing.md`](shared/workflow/check-purpose-before-reusing.md)

## Avoid false dichotomies

When laying out alternatives, test whether they are actually exclusive before
presenting them as such.
The tell is a question posed as either/or and answered with "both" --- which
means the exclusivity was constructed rather than found.

The observable action: before presenting alternatives, state what would be
lost by taking more than one.
If the answer is nothing, they are not alternatives --- enable multi-select,
or present them as composable steps with an order.
Genuinely exclusive options exist (two incompatible designs, a merge strategy,
a name), and presenting those as combinable is its own error; the target is
the unexamined default, not the act of choosing.
Composes with "Present decisions one at a time" above, which governs how many
questions to ask rather than how one question's options relate.

[shared/workflow/avoid-false-dichotomies.md](shared/workflow/avoid-false-dichotomies.md)

## Metacognition: monitor claims by type, and distrust the fluent ones

The two rules above supply instruments and checklists for work that is already
recognized as needing checking.
This one covers the assertion that never raised the question --- and the
regulation step nothing prompts.

Monitor your own claims at **composition time**, as each sentence is written,
rather than in a retrospective afterwards.
Confidence cannot be the trigger, because it runs inversely to accuracy, so key
on claim **type** instead: a claim about **state** gets re-queried, one about
**scope** gets checked against the population, one about **cause** gets asked
what else explains it, and an unexamined **default** gets named and decided.
An answer that arrived with no deliberation owes an alternative you can name
and reject.

[`shared/workflow/metacognitive-monitoring.md`](shared/workflow/metacognitive-monitoring.md)

## Question the assignment, not only the claims

The rule above governs **claims** --- the ones you generate as much as the ones
you are handed.
This one governs what you are asked to **do** --- a brief, an issue body, a
plan, a convention document, or the option set in a posed question.
None of those assert anything, so no claim-checking rule fires on them, and
adopting one feels like compliance rather than like skipping a step.
A wrong claim spoils a sentence; a wrong assignment spoils the whole task,
while every step inside it stays correct and checks green.

Two written lines bound the check: before starting, name the premise the work
rests on and what would show it false; in the report, name one thing in the
assignment you actually checked.
For a posed choice, state what its options presuppose before answering within
them.

It binds the **author** of an assignment too, and that half has no other rule
pointed at it: writing a brief feels like instructing rather than asserting,
so nothing fires on a premise stated inside one.
When a brief you write asserts corpus state --- a file's contents, a rule's
location, a site count --- run the deriving query and paste it beside the
claim, rather than leaving the recipient's discretionary premise check as the
only detector.

[`shared/workflow/challenge-the-assignment.md`](shared/workflow/challenge-the-assignment.md)

## Check for merge conflicts on every merge in an ultracode session

[shared/workflow/ultracode-merge-conflicts.md](shared/workflow/ultracode-merge-conflicts.md)

## Big-picture principles: KISS, DRY, DRW, modularity, and friends

The catalog in `shared/principles/` maps each principle to its purpose,
operational rules, and trade-offs.
When adding a coding or review rule, place it under the principle it serves.

[shared/principles/README.md](shared/principles/README.md)

## Don't reinvent the wheel (DRW) --- in dev and in review

Universal DRW policy is in `AGENTS.md` ("Research existing solutions before implementing (DRW)").

[shared/principles/dont-reinvent-wheel.md](shared/principles/dont-reinvent-wheel.md)

The `prefer-upstream` skill runs the search; the `prefer-packaged-functions` fragment below is the R-function special case; the `scout-peers` skill gates borrowed code by license.

## If a repo isn't using `gha` and would benefit, upgrade it

[shared/workflow/upgrade-to-gha.md](shared/workflow/upgrade-to-gha.md)

The CI-specific, proactive case of DRW above.
`Morrison-Lab/gha` ships the lab's reusable workflows, called from a consumer as `uses: Morrison-Lab/gha/.github/workflows/<name>.yml@vN`.
When a repo you are working in hand-maintains a workflow gha already provides, migrate it --- the upgrade is the deliverable, not the observation.
The corpus's other gha triggers each wait for an event (a bug to patch, a port to close out, new CI to write), so none fires on the commonest case: nothing is broken, and the duplicate has simply sat there absorbing none of gha's fixes.
Candidates are duplication, drift, a named missing fix, or a directory that already calls gha for some workflows and not others.
Not candidates are repo-specific logic gha does not model, a repo deliberately pinned off gha, and a repo we cannot merge a PR to.
The fragment carries the rest: taking the inventory from gha's README table rather than its directory listing, pinning per capability, filing the migration as its own issue and PR, the private-consumer access precondition, the `permissions:` and `concurrency:` traps, and how to confirm the self-edit guard when a migration PR gets no review.
Its "new repo" counterpart: a brand-new repository gets gha-backed CI (the baseline set, plus whatever fits the repo type) in the same first PR that creates it, never deferred to later.

## Don't incur technical debt

[shared/principles/dont-incur-technical-debt.md](shared/principles/dont-incur-technical-debt.md)

## Dead code is technical debt

[shared/principles/dead-code-is-tech-debt.md](shared/principles/dead-code-is-tech-debt.md)

## Fail fast — no silent failures

Detect bad state early and stop with a clear error rather than proceeding on it.
Never swallow an error into a silent fallback (a bare `except:`, a `tryCatch` returning `NULL`, a shell `|| true`).
A genuinely wanted fallback must be explicit, bounded, and observable.
Error handling that hides failure is a review finding, with the same weight as any other standing review check.

[`shared/principles/fail-fast.md`](shared/principles/fail-fast.md)

## Specific beats general

When two instructions, policies, configurations, or design rules apply to the same decision, the narrower, more specific rule wins: explicit user instructions over repository defaults, subsystem configs over repo-wide policies, targeted handlers over generic catch-alls.

[`shared/principles/specific-beats-general.md`](shared/principles/specific-beats-general.md)

## Think outside the box --- distinguish real from artificial limitations

Do not assume a limitation is real without checking: test whether it is a hard architectural, mathematical, security, or physical bound, or an artificial one (inherited convention, unexamined default, local scoping trap).
When a design becomes awkward, reframe the problem rather than building a workaround inside an unnecessary box.

[`shared/principles/think-outside-the-box.md`](shared/principles/think-outside-the-box.md)

## Don't take anyone's word for it --- independent verification and constructive pushback

Never accept factual assertions, technical recommendations, or stated preferences blindly --- everyone makes mistakes, humans and AI models alike.
Investigate independently via deterministic queries, source inspection, or clarifying questions, and push back when you suspect an error.

[`shared/principles/dont-take-my-word-for-it.md`](shared/principles/dont-take-my-word-for-it.md)

## Get under the hood --- inspect source code and raw output

To understand a process, diagnose a failure, or determine a tool's behavior, inspect the actual source code, raw logs, job output, and live execution paths rather than treat it as an opaque black box.

[`shared/principles/get-under-the-hood.md`](shared/principles/get-under-the-hood.md)

## No gameable rules --- loopholes, perverse incentives, monkey-paw phrasing

A rule, metric, or hook condition must target the outcome it cares about, so no behaviour can satisfy its letter while defeating its purpose --- key it to the state (noticed, true, done), not a visible proxy (mentioned, reported).

[`shared/principles/no-gameable-rules.md`](shared/principles/no-gameable-rules.md)

## Coding: KISS is the umbrella principle

Apply KISS to code and prose: use the simplest construct that does the job,
and justify added complexity.
The rules below and `challenge-unnecessary-complexity` are concrete cases,
not an exhaustive list.

## Coding: use the least-flexible construct that does the job

<!-- Not yet shared with the lab manual; edit shared/coding/least-flexible-tool.md, not here. -->
[shared/coding/least-flexible-tool.md](shared/coding/least-flexible-tool.md)

## Coding style: avoid nesting; follow the lab manual

Follow the SERG lab manual (https://ucd-serg.github.io/lab-manual/) for coding and collaboration conventions.

<!-- Shared with the lab manual; edit shared/coding/avoid-nesting.md, not here. -->
[shared/coding/avoid-nesting.md](shared/coding/avoid-nesting.md)

## Coding: single-indent multi-line function signatures

<!-- Not yet shared with the lab manual; edit shared/coding/function-signature-style.md, not here. -->
[shared/coding/function-signature-style.md](shared/coding/function-signature-style.md)

## Coding: prefer existing packaged functions over rolling your own

<!-- Shared with the lab manual; edit shared/coding/prefer-packaged-functions.md, not here. -->
[shared/coding/prefer-packaged-functions.md](shared/coding/prefer-packaged-functions.md)

## Coding: memoise pure, expensive, repeatedly-called functions

<!-- Not yet shared with the lab manual; edit shared/coding/use-memoisation.md, not here. -->
[shared/coding/use-memoisation.md](shared/coding/use-memoisation.md)

## Coding: prefer per-operation grouping over persistent grouping (dplyr)

<!-- Shared with the lab manual; edit shared/coding/per-operation-grouping.md, not here. -->
[shared/coding/per-operation-grouping.md](shared/coding/per-operation-grouping.md)

## Coding: prefer type-stable calls; never `sapply()` outside the console

<!-- Not yet shared with the lab manual; edit shared/coding/type-stable-outputs.md, not here. -->
[shared/coding/type-stable-outputs.md](shared/coding/type-stable-outputs.md)

## Coding: preallocate, `seq_along()`, and `[[i]]` in for loops

<!-- Not yet shared with the lab manual; edit shared/coding/loop-hygiene.md, not here. -->
[shared/coding/loop-hygiene.md](shared/coding/loop-hygiene.md)

## Coding: restore global state your function changes

<!-- Not yet shared with the lab manual; edit shared/coding/restore-global-state.md, not here. -->
[shared/coding/restore-global-state.md](shared/coding/restore-global-state.md)

## Coding: `set -e` is not uniform; tolerate expected non-zero exits explicitly

<!-- Not yet shared with the lab manual; edit shared/coding/errexit-is-not-uniform.md, not here. -->
[`shared/coding/errexit-is-not-uniform.md`](shared/coding/errexit-is-not-uniform.md)

## Coding: an empty bash associative-array subscript is fatal, not a miss

<!-- Not yet shared with the lab manual; edit shared/coding/bash-associative-arrays.md, not here. -->
[`shared/coding/bash-associative-arrays.md`](shared/coding/bash-associative-arrays.md)

`${arr["$k"]:-}` tolerates a missing key and not an empty one, so the `:-`
default cannot guard a validator whose key is derived (`"${stem##*.}"`, a
`cut` field, a regex capture) --- it dies on exactly the malformed input it
exists to reject.
Test the key for emptiness first in an `||` chain, so short-circuiting
prevents the expansion.

## Coding: avoid hard-coding data with an external source of truth

<!-- Shared with the lab manual; edit shared/coding/avoid-hardcoding-external-data.md, not here. -->
[shared/coding/avoid-hardcoding-external-data.md](shared/coding/avoid-hardcoding-external-data.md)

## Coding: make every parameter configurable

<!-- Not yet shared with the lab manual; edit shared/coding/configurable-parameters.md, not here. -->
[shared/coding/configurable-parameters.md](shared/coding/configurable-parameters.md)

## Coding: write tidy code; prefer tidyverse over base R/rlang for it

<!-- Not yet shared with the lab manual; edit shared/coding/tidy-code.md, not here. -->
[shared/coding/tidy-code.md](shared/coding/tidy-code.md)

Apply this both when writing code and when reviewing it — flag base R or
`{rlang}` verbosity in review the same way `per-operation-grouping` flags a
persistent `group_by()` that `.by` would replace.

## Coding: reuse function documentation and argument lists

<!-- Not yet shared with the lab manual; edit shared/coding/reuse-docs-and-args.md, not here. -->
[shared/coding/reuse-docs-and-args.md](shared/coding/reuse-docs-and-args.md)

## Coding: one function per file

<!-- Not yet shared with the lab manual; edit shared/coding/one-function-per-file.md, not here. -->
[shared/coding/one-function-per-file.md](shared/coding/one-function-per-file.md)

Apply this both when writing new code and when reviewing it — a new function
added inline to an existing multi-function file is a review finding, the
same weight as the other modularity checks above.

## Coding: no em-dashes or non-ASCII punctuation in source files

<!-- Not yet shared with the lab manual; edit shared/coding/ascii-punctuation-in-source.md, not here. -->
[shared/coding/ascii-punctuation-in-source.md](shared/coding/ascii-punctuation-in-source.md)

## Coding: decompose complex code into functions, not .qmd chunks

<!-- Not yet shared with the lab manual; edit shared/coding/decompose-to-functions.md, not here. -->
[shared/coding/decompose-to-functions.md](shared/coding/decompose-to-functions.md)

## Coding: avoid catastrophic backtracking in regular expressions

<!-- Not yet shared with the lab manual; edit shared/coding/regex-backtracking-pitfalls.md, not here. -->
[`shared/coding/regex-backtracking-pitfalls.md`](shared/coding/regex-backtracking-pitfalls.md)

## Coding: a test harness reading embedded script from a YAML block scalar must not re-strip indentation

<!-- Not yet shared with the lab manual; edit shared/coding/yaml-embedded-script-double-dedent.md, not here. -->
[`shared/coding/yaml-embedded-script-double-dedent.md`](shared/coding/yaml-embedded-script-double-dedent.md)

`yaml.safe_load` already dedents a `run: |` block relative to its own first
content line; a harness that also strips a fixed number of leading spaces on
top of that double-dedents, corrupting any line shallower than the fixed
width and producing an `IndentationError` that reads as a bug in the
workflow file rather than in the harness.

## Writing style: plain, direct prose

<!-- Shared with the lab manual; edit shared/writing/plain-prose.md, not here. -->
[shared/writing/plain-prose.md](shared/writing/plain-prose.md)

The `use-preferred-style` skill (alias `style`) spells out the procedure, the PSW chapter links, and a filler/jargon swap table; the `find-ai-tells` skill (alias `ai-tells`) is the scan-after detector counterpart.

## Writing style: name the referent, so no pronoun is ambiguous

A specific case of the plain-prose rule above, and the one self-review is worst at catching.
The tell is a pronoun or demonstrative --- `it`, `this`, `that`, `which`, `they` --- whose **nearest grammatical antecedent is not its intended referent**.
A pronoun with no clear referent makes a reader pause and re-read, so the cost is a moment.
A pronoun whose *wrong* referent sits closer reads perfectly well, so the reader takes away the wrong fact without ever being unsure.
The remedy is to replace the pronoun with the noun, not to reword around it.

[shared/writing/ambiguous-reference.md](shared/writing/ambiguous-reference.md)

This is distinct from [`challenge-ambiguous-terminology`](shared/workflow/challenge-ambiguous-terminology.md), which governs a word whose **meaning** is unresolved rather than a word whose **antecedent** is.
Apply it wherever `code-review`/`ard`/`ardi` already reviews a prose diff, alongside the other prose-review rules in this file.

## Writing style: don't build a model only to retract it

A "rug-pull" presents a model, claim, or picture and a sentence or two later
retracts or replaces it --- "X.
However, the implementation actually Y."
Every sentence can be individually true and cited; the defect is in the
order, which no fact-check or read-through inspects.
It is also the natural shape to write when the facts were discovered in
that order, which is why it survives self-review: the prose narrates the
author's own path rather than exposing the subject to a reader who never
walked it.
Lead with what is actually the case, and present an idealization or a
prior approach afterward as an extension, not a correction --- except when
the **reader** already holds the wrong model and the passage exists to
correct it, in which case presenting it first is the point.

[shared/writing/no-rug-pulls.md](shared/writing/no-rug-pulls.md)

Check this at composition time, not only in review: drafting fixes the order,
and a read-through inspects sentences, not the sequence.

## Writing style: semantic line breaks in prose

[`shared/writing/semantic-line-breaks.md`](shared/writing/semantic-line-breaks.md)

## Quarto: div syntax for figure/table labels and captions

[`shared/writing/quarto-figure-captions.md`](shared/writing/quarto-figure-captions.md)

## Manuscript layout: floats at the end, captions with their floats

In a journal-submission manuscript, unless the journal's instructions say otherwise, put main-text figures and tables after the main text and references and before the supplement, insert a page break before the supplementary-material header, keep each caption on its float's page (page breaks between floats, not split captions), and give every float a numbered caption rendered as a caption, never as a heading.
Check these on the rendered layout, not only its text and numbers.

[`shared/writing/manuscript-float-layout.md`](shared/writing/manuscript-float-layout.md)

## Quarto: style div boxes in revealjs as well as HTML

[`shared/writing/quarto-revealjs-div-styling.md`](shared/writing/quarto-revealjs-div-styling.md)

## Quarto: remarks for commentary on the math, callouts for guidance to the reader

[`shared/writing/quarto-remarks-vs-callouts.md`](shared/writing/quarto-remarks-vs-callouts.md)

## Quarto: put typed content in a div or callout wherever one fits

[`shared/writing/quarto-divs-for-typed-content.md`](shared/writing/quarto-divs-for-typed-content.md)

Every block with a type --- definition, result, proof, example, exercise, solution, remark, warning, tip, note --- goes in the div or callout of that type, in every repository with Quarto content.
A recurring kind of block with no matching category gets a new custom div or callout type rather than staying in plain prose.
Connective narrative stays unboxed, and one theorem-type div does not go inside another.

## Writing style: a grouping level must earn its place

[`shared/writing/grouping-levels.md`](shared/writing/grouping-levels.md)

A heading, or a navbar dropdown, is only meaningful when it has a sibling ---
a lone child heading, or a navbar reduced to "Home" plus one catch-all
dropdown that groups everything else on the site, adds structure the reader
gains nothing from.
Several topical dropdowns (or dropdowns alongside flat items) are fine; the
defect is one dropdown with no sibling of its own kind, not a dropdown's
mere presence.
The inverse case is a single page carrying two topics that never earned
sharing one grouping in the first place --- length alone doesn't say so, but
two independent nouns joined by "and", a vague catch-all title, or
non-building sections do.
Covers the Quarto-specific consequences too: `title` is already the page's
h1, `revealjs` slide boundaries move with heading levels, and a
fragment-repo's `{#sec-...}` ids must survive a restructure or a page split.
The navbar test is structural (does this dropdown have a sibling), never a
question of screen width or how much room the bar has.

## Challenge ambiguous phrasing and terminology in review

[shared/workflow/challenge-ambiguous-terminology.md](shared/workflow/challenge-ambiguous-terminology.md)

The `ard`/`ardi` skill family and `use-preferred-style`/`find-ai-tells` operationalize this in their respective review contexts.

## Challenge redundant content in review

[shared/workflow/challenge-redundant-content.md](shared/workflow/challenge-redundant-content.md)

The `ard`/`ardi` skill family and `code-review` apply this in PR/MR review; `find-overlap` (and its `consolidate-skills`/`consolidate-memory` actors) is the corpus-wide counterpart when redundancy spans more than the current diff.

## Never assert a corpus gap from a grep

The rule above catches redundant content once it is written.
This one catches the belief that produces it: a phrase grep returning nothing is not evidence the corpus lacks a concept, because grep matches strings while coverage is a claim about ideas.
Report the query and its result, not the conclusion.

[`shared/workflow/grep-is-not-coverage.md`](shared/workflow/grep-is-not-coverage.md)

Fires wherever a search decides whether to author something new --- `skill-builder`'s step 0, `ums`'s step 3, and `find-overlap`, whose own instrument scores this repo's canonical same-idea pair at 0.019 phrase similarity.

## Writing style: scan for AI tells

The detector counterpart to the plain-prose guide above.

<!-- Shared with the lab manual; edit shared/writing/ai-tells.md, not here. -->
[shared/writing/ai-tells.md](shared/writing/ai-tells.md)

The `find-ai-tells` skill (alias `ai-tells`) runs this same catalog on demand against any target text.

## Writing style: an example of a checked pattern is itself checked

[shared/writing/examples-are-scanned.md](shared/writing/examples-are-scanned.md)

When a document explains a mechanically-enforced convention, its illustrative
example sits inside the file the checker scans -- so writing the example the
natural way can trip the rule the passage is describing, and implicate the one
passage meant to prevent it.
Whether it does turns on the checker: backticks and fenced blocks shield
nothing from a line-oriented scanner, and everything from a structure-aware
one, so read it rather than assuming either way.
Teach the checker about code regions when you own it (this repo's
`scripts/lib/fences.py` is that fix), render the example so it cannot match
when you do not, and either way run the detector rather than re-reading --
self-review confirms the claim, which was never the defect.

## Writing style: cite sources thoroughly

[`shared/writing/citations.md`](shared/writing/citations.md)

## Check the renders, not just the source

[shared/workflow/check-the-renders.md](shared/workflow/check-the-renders.md)

For a document whose deliverable is a file (Word, PDF, slides, a manuscript), viewing the render is a hard merge gate: no "ready" and no merge, under any grant, until every page of the render at the current head has been viewed and the evidence posted on the PR.
Procedure: [`review-rendered-documents`](shared/workflow/review-rendered-documents.md).

A repo that publishes a website or book has the rendered page as its
deliverable; a correct source diff is not evidence the published page is
correct.
An unexpanded macro, a citation key pandoc renders as `key?`, a crossref
resolving to nothing, a list that lost its blank line, a swallowed KaTeX
error --- none shows in the diff, none makes CI red.
The worst case is a fixed source over an unfixed deployed page from a stale
render cache, which every other check here passes.
`python3 scripts/check-rendered-page.py <url-or-file>` checks the pattern
failures, given a preview URL, a published URL, or a local `_site/` file; it
cannot detect staleness (a relation between page and commit, not a page
property) --- for that, grep the render for the diff's added/removed text.

- **Do:** check the rendered page, and the deployed preview rather than only a
  local render where the repo caches renders.
- **Don't:** read a correct source diff as evidence about the published page.

(Directive from the user, 2026-09-07: "for repos that render websites and
books, always check the renders".)

## Fact-check prose and internal reasoning in review

[`shared/writing/fact-check-prose.md`](shared/writing/fact-check-prose.md)

Apply this during `code-review`/`ard`/`ardi` review of a prose diff, alongside the normal review.
Those skills don't name it, but this directive still governs.

## Writing style: timestamp factual claims about conditions that can change

The complement to the fact-check above: a *true* claim decays into a
confident falsehood when stated as timeless present-tense fact but its truth
is time-dependent (a package's CRAN status, a "current" version, a count).
Attach the time it was true so a later reader knows to re-verify it.

[shared/writing/timestamp-volatile-claims.md](shared/writing/timestamp-volatile-claims.md)

## Writing style: math --- include every step; keep each equation simple

[`shared/writing/math-derivation-steps.md`](shared/writing/math-derivation-steps.md)

Three axes.
*Between* displayed lines, write out every step, and flag gaps in review.
*Within* one line, decompose complicated internal structure out into extra
notation, then reapply that until each line carries one operation.
Apply the second thoroughly rather than per equation: name the concept where
it first enters the document, since an unnamed concept is one that gets
silently duplicated across sections.
Stop unfolding at a modeled quantity the reader already accepts at that point
in the argument, which is a test against the exposition rather than a class
of expression.
*Whether a line is displayed at all*: ask this explicitly for every equation written or edited,
rather than inheriting the form of the nearest neighbouring equation ---
display when the prose returns to it or it carries the argument,
inline when it is a grammatical constituent of its own sentence,
and the same form as its counterpart for any equation meant to be compared against another.
A display equation running into its own introducing sentence is ambiguous between two causes with opposite fixes ---
check the markup before changing anything.
Format-general: applies to `$...$` versus `$$...$$`/an `equation` environment in Quarto/LaTeX,
exactly as it applies to `<m:oMath>` versus `<m:oMathPara>` in Word/OOXML.

When running `code-review` or the `ard`/`ardi` loop on a diff that touches
math, apply this in addition to the fact-check above.

## Writing style: models vs. inference methods

[`shared/writing/models-vs-inference.md`](shared/writing/models-vs-inference.md)

A model is never "Bayesian"; only how it is fitted is.

## Hyperlink liberally: make it easy for readers to find more information

Connect referenced concepts, external packages, internal rules, and forge artifacts to clickable URLs rather than leaving them as plain text.
Detail, rationale, and cases: [`shared/writing/hyperlink-liberally.md`](shared/writing/hyperlink-liberally.md).

## Hyperlink technical terms and results; no forward references

[shared/writing/definition-crossrefs.md](shared/writing/definition-crossrefs.md)

Applies wherever `code-review`/`ard`/`ardi` already reviews a prose diff, alongside the fact-check and ambiguous-terminology checks above.

`python3 scripts/check-bare-fragment-mentions.py` is the instrument for this corpus's own version of the miss: a fragment linked once and then named as plain prose further down the same file.
Advisory, always exits 0, and wired into `validate.yml` as a non-gating step.

- **Do:** run it over a prose diff that names a fragment more than once.
- **Don't:** link a fragment on its first mention and then repeat the basename bare further down.

## Remove forward-pointing phrases from prose, not just crossref divs

The section above covers this repo's own linked-once-then-bare miss, and formal Quarto crossref-div ordering for term/result definitions.
The same problem shows up more broadly as plain-text signposting — "as discussed below", "in the following section", "we'll cover this later" — pointing at content the reader hasn't reached yet, in any prose (not just documents with crossref divs).

[shared/writing/forward-references.md](shared/writing/forward-references.md)

Unlike `definition-crossrefs.md` above, `forward-references.md` has a dedicated actionable skill: the `fix-forward-references` skill (alias `ffr`) detects these with a grep-for-directional-word heuristic and rearranges (or rewords) the prose to fix them.
Run it — or apply its check inline — wherever `ard`/`ardi` reviews a prose diff, alongside the other prose-review rules in this file.

## Rearranging sections, paragraphs, and content across documents is part of editing prose

[shared/writing/reorganize-prose.md](shared/writing/reorganize-prose.md)

Moving a section, subsection, paragraph, or sentence --- within a document, or in a multi-document repo (a website, a book, a manuscript) across documents --- is in scope for a prose edit whenever it improves flow, fixes a forward reference, removes duplicate content, or reunites related content split across distant locations.
A move is authorship, not a no-op: sweep for stale self-references and count-based back-references, bring the relocated lines into compliance with the line-level checks above, migrate any referenced assets, and prove nothing was lost or accidentally added with a bidirectional content comparison.

## Detect concepts defined only in prose, never formalized

`definition-crossrefs.md` above assumes a formal-definition div already exists and checks that mentions link to it in the right order.
A distinct, easy-to-miss gap: a concept stated with full definitional precision --- a bolded name, an equation, an `\eqdef` --- that never became a formal div at all, so it has no stable id and nothing downstream can cite it (or the concept rides along inside a *different* definition's div instead of getting its own).

[shared/writing/informal-definitions.md](shared/writing/informal-definitions.md)

Like `forward-references.md`, this has a dedicated actionable skill: `detect-informal-definitions`.
Run it --- or apply its check inline --- wherever `ard`/`ardi` reviews a diff that introduces new technical content, alongside the other prose-review rules in this file.

## Detect hypothetical examples where real data is already available

A worked example can be a perfectly well-formed `{#exm-...}` div and still reach for invented, round-number quantities --- "suppose 20% of the exposed group..." --- when the document already loads a real dataset it uses elsewhere.
That's a distinct gap from the informal-definitions check above: it isn't a missing div, it's a missed chance to ground the illustration in real data that was already available.

[shared/writing/hypothetical-examples.md](shared/writing/hypothetical-examples.md)

This has a dedicated actionable skill: `detect-hypothetical-examples`.
Run it --- or apply its check inline --- wherever `ard`/`ardi` reviews a diff that introduces or edits a worked example, alongside the other prose-review rules in this file.
Fixing isn't mechanical substitution: a real dataset's effect size is often much less dramatic than an invented one, so weigh whether the real numbers still make the teaching point before publishing them.

## Fact-check code logic and math in review

<!-- Not yet shared with the lab manual; edit shared/coding/fact-check-code-logic.md, not here. -->
[`shared/coding/fact-check-code-logic.md`](shared/coding/fact-check-code-logic.md)

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

[shared/workflow/fixtures-are-not-evidence.md](shared/workflow/fixtures-are-not-evidence.md)

Distinct from `ardi`'s fixture bullets, which are about coverage (a fixture
too thin to reach a branch) rather than about the inference drawn from one
that works fine.

## Verify the artifact the claim is about, not an adjacent one

Three rules in this corpus each name one adjacent artifact that stands in for
the real one: the fixture rule directly above,
`metacognitive-monitoring`'s neighbouring step read for a failure's cause, and
`fact-check-prose`'s published build read for the branch that produced it.
The substitution is general, and outside those three situations none of the
three loads.

It is not lazy verification but thorough verification of the wrong object, so
the evidence is real, the reasoning from it is sound, and nothing feels like a
guess.
The fragment names four recognizable shapes --- a cached copy for the origin, a
checkout for the run, one half of a mechanism for the whole, a neighbour for
the target --- and one test that works where confirming the claim cannot:
ask what would have to be true for the claim to be **false**, and whether the
artifact in hand could show it.

[shared/workflow/verify-the-right-artifact.md](shared/workflow/verify-the-right-artifact.md)

## Challenge unnecessary complexity in review

[shared/workflow/challenge-unnecessary-complexity.md](shared/workflow/challenge-unnecessary-complexity.md)

When running `code-review`, `ard`/`ardi`, or any prose review (`use-preferred-style`, `find-ai-tells`, `fact-check-prose`), apply this alongside the normal review — those skills don't name it internally, so this CLAUDE.md directive governs regardless. It's distinct from `simplify` (a dead-code-after-refactor sweep) and `tidy` (a separate on-demand audit).

## Drop any review finding that cannot quote the passage it is about

[shared/workflow/quotable-findings.md](shared/workflow/quotable-findings.md)

A mechanical pre-filter on findings you produce, not findings you receive --- the mirror of `address-every-comment.md`'s reviewer-verification checks.
Applies wherever this corpus produces or verifies review-shaped findings: `ard`/`ardi`'s self-review step, `code-review`, the prose-review skills, `grade-work`, and any `Workflow` adversarial-verify pattern, ahead of its expensive judgment vote.
An absence finding (a missing test, an uncited claim) is exempt from quoting and instead names the location the missing thing belongs.

## Useful prompt formats for coding agents

<!-- Vendored from Morrison-Lab/wai; edit there, not here. See README, "Shared content". -->
[shared/vendored/prompt-formats.md](shared/vendored/prompt-formats.md)

## Review with Copilot before requesting human review

This is shared lab guidance on getting an automated review before asking a human reviewer.
When *I* iterate a PR, the ARDI loop above is the mechanism — it already addresses whatever the `@claude` or Copilot reviewer flags — so read this as the lab-member-facing statement of the same principle, not a second loop to run.

<!-- Vendored from Morrison-Lab/wai; edit there, not here. See README, "Shared content". -->
[shared/vendored/copilot-review-before-human.md](shared/vendored/copilot-review-before-human.md)

## Growth mindset: seek resources rather than accept limitations

<!-- Edit shared/workflow/growth-mindset.md, not here. -->
[shared/workflow/growth-mindset.md](shared/workflow/growth-mindset.md)

## Research before asking a human

<!-- Edit shared/workflow/research-before-asking.md, not here. -->
[shared/workflow/research-before-asking.md](shared/workflow/research-before-asking.md)

## Encoding reusable feedback into ai-config

Commit feedback that outlives the session to the repo that owns it in the same stride, choosing the form yourself;
never park it in session-local auto-memory or offer to upstream it instead.
Detail, rationale, and cases: [`shared/workflow/encode-reusable-feedback.md`](shared/workflow/encode-reusable-feedback.md).

## PowerShell CLI Command Safety

Never pass backtick-carrying text inside a double-quoted string in any shell: use `--body-file`, `-F body=@<file>`, or `git commit -F <file>`.
Detail, rationale, and cases: [`shared/coding/powershell-cli-safety.md`](shared/coding/powershell-cli-safety.md).

## Tool transport collapses doubled backslashes

[`shared/coding/heredoc-backslash-collapse.md`](shared/coding/heredoc-backslash-collapse.md)

The sibling of the backtick hazard above, and the same class: content silently transformed between what you type and what the interpreter receives.
On some transports a doubled `\\` inside a Bash-tool heredoc body arrives as a single `\`, **even with a quoted delimiter** that should make the body literal.

It fails silently and plausibly: the worst case is not a failed assert but a corrupted regex with no syntax error and a green suite.

**It is a property of the environment, not of heredocs**, so measure yours rather than trusting either answer --- it reproduced on Windows MINGW64, and did not reproduce either in a GitHub Actions Linux runner or in a Linux remote Claude Code container --- two different environments, and the second is where many sessions actually execute.
Knowing the rule also does not stop you tripping it, since nothing about typing an escape sequence announces itself as the trigger.

**So the default is not to carry content in a heredoc at all.**
Write it with the Write tool (Edit for an existing file) to a uniquely named scratchpad file, and hand the command the path (`git commit -F`, `--body-file`, `python3 script.py`).
The Write tool passes bytes unchanged, and it cannot be silently skipped the way a heredoc inside a hook-denied Bash call is.

- **Do:** use Write or Edit for any content with a backslash, a backtick, code, or more than a few lines.
- **Do:** where a heredoc is genuinely unavoidable, build the character with `chr(92)` or a placeholder token before it enters the body, and print `repr()` of the constructed string.
- **Do:** parse-check or read back any file a heredoc just wrote with escapes in it.
- **Don't:** embed a patch script, regex, commit message or PR body in a heredoc.
- **Don't:** type a doubled backslash directly inside a heredoc body, quoted delimiter or not.
- **Don't:** treat having read this rule as the check --- it was loaded, and the collapse happened anyway.

`hooks/warn-heredoc-doubled-backslash.py` scans a command's heredoc bodies at `PreToolUse` and names the offending line (ai-config#1923, #3362).

## Strict Merge Control Policy

- **NEVER merge any Pull Request or Merge Request without explicit user permission.**
  Creating, opening, updating, or driving a PR to clean CI/review does NOT grant permission to merge it.
  Merging a PR is strictly forbidden unless the user explicitly grants session permission (e.g. via `/mwc` or `/maw`) or explicitly issues a merge instruction for that specific PR (e.g. `/merge-it` or "merge this PR").
- **Never merge over open review findings or treat skip notices as approval.**
  Under `mwc`, a PR must be fully clean across CI and all review findings.
  A reviewer skip notice (e.g. for workflow edits or quota limits) never clears or supersedes prior review findings.
  All findings across the PR history must be fully Addressed, Rebutted, or Deferred before merge.
  A disagreement among reviews is not fully clean: any standing not-clean
  --- nits included --- vetoes merge even with `mwc` active
  (ai-config#2274).
- **Another session's PR needs a second condition: clean, and clean for more than twenty minutes --- then warned.**
  Every other rule here settles *when* a PR may be merged;
  this one settles *whose*.
  A peer may have further commits planned, so merging one that just went clean can destroy work it was about to push --- and that is exactly the case where the peer's PR unblocks yours and the temptation is strongest.
  Start the clock at the clean verdict on the current head, which a push resets, rather than at the PR's `updatedAt`, which any comment bumps.
  The threshold is an inference, so confirm it: message the owning session directly when `ListAgents` reaches it, and otherwise post a comment saying you intend to merge and wait a further five minutes for a hold-off.
  The path applies only to a peer PR that passes `memories/reviewing-prs.md`'s scope test (a peer session under your own login satisfies the author arm).
  Another lab member's PR that fails the test gets neither the comment nor the merge.
  [`mwc`](skills/mwc/SKILL.md)'s "Another session's PR" section carries the derivation and the pattern/anti-pattern pair (ai-config#2460).

**One standing exception: PRs targeting `Morrison-Lab/ai-config` or the shared math-macros repo (`d-morrison/macros`) carry a standing `mwc` grant**, with no per-session re-issue and no `enable-mwc` step --- `hooks/no-unauthorized-merge.py` reads the merge's target repo off the command.
[`mwc`](skills/mwc/SKILL.md)'s Scope Limit binds in full, so it covers a **fully clean** PR (see [`fully-clean`](shared/workflow/fully-clean.md)) and nothing else.
It is scoped to the **target**, so a merge from an ai-config checkout into another repo is unaffected.

- **Do:** merge a fully-clean ai-config PR without asking, and say in the same reply that you did and why it qualified.
- **Don't:** read it as covering a PR that is not fully clean, or another repo's PR merged from an ai-config checkout.
