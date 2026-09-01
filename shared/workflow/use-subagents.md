When available, use subagents for helpful sidecar work: independent investigation, verification, or disjoint implementation slices.
Keep immediate blocking critical-path edits local so progress does not wait unnecessarily.

**Nothing parallelizable should ever sit "queued."**
Work that does not block the edit in front of you is, by definition, work another agent could already be doing.
Deferring it buys nothing: the serial version finishes no sooner, and the deferred item is the one most likely to be dropped outright when the session ends or the context turns over.

The tell is a phrase, which makes it cheap to catch, because you have to type it before the mistake is complete.
Writing "queued", "next up", "after this", or "I will do that next" into a status recap is the signal that a subagent should already have been running on that item.
Treat the urge to write the word as the trigger to launch, not as an acceptable way to describe the plan.

**Sidecar delegation is pre-authorized, so it is never worth asking about.**
Independent investigation, verification, a disjoint implementation slice, an owed UMS pass, a routed `cai` --- all of these are standing grants.
This section is the user instruction that settles it, so a harness default of the form "do not call the Agent tool unless the user requested it" is already satisfied: the request is here, standing, and does not need restating each session.
Asking anyway costs a round trip and returns the answer already written down.

- **Do:** launch the subagent at the moment you would otherwise have typed "queued", and say in the recap what it is working on.
- **Do:** treat an owed UMS pass or a routed `cai` as delegable sidecar work rather than as a wrap-up step to reach later.
- **Don't:** report an item as queued, next up, or deferred to later in the session when nothing actually blocks it.
- **Don't:** wait for a per-session request before delegating, or ask whether to use a subagent.
- **Don't:** hand off the blocking edit itself --- the critical-path change stays local, so progress never waits on a round trip.

**That "harness default of the form" is not a hypothetical: Claude Code shipped one, model-gated and undisclosed, as of v2.1.219 (July 2026).**
[anthropics/claude-code#80988](https://github.com/anthropics/claude-code/issues/80988) documents it: a dynamic system-prompt section (`heron_brook`) injecting "Do not call the AgentTool unless the user requested it" and "Do not use workflows or deep-research unless the user requested it", enabled by default for Claude Opus 5 sessions only (capability flag `opus_5_prompt_bundle`), with no documented opt-out.
The standing grant above works *with* that line rather than against it: the injected default defers to a user request, and this section is that request, so dispatching sidecar subagents under this grant satisfies the injected line's own condition.
The injection's second line needs no overruling either: its workflow clause is what [`when-to-orchestrate`](when-to-orchestrate.md)'s opt-in gate already enforces, and its deep-research clause is covered by neither the grant nor that gate --- and needs no disposition, since no corpus rule mandates deep-research.

Whether a given session carries the section is a checkable state claim, not a guess, and the artifact to check is the session's own system prompt: search it for the injected line.
The serving model is only a proxy --- an inference through the issue's flag-to-model snapshot, which a later Claude Code version can silently change in either direction --- and a tool description can corroborate the dispatch-encouraging default without ever showing a system-prompt section present or absent.
(Verified 2026-08-27 on a Fable 5 remote session, Claude Code 2.1.247: no such line present in the session's system prompt;
the Agent tool's description there directs dispatch, and the harness's only default restriction was the `Workflow` tool's documented opt-in gate.
User directive the same day: the ban is overruled wherever it does appear.
Tracked as [ai-config#2380](https://github.com/Morrison-Lab/ai-config/issues/2380).)

- **Do:** keep dispatching per this section in a session whose harness carries the injected line, since the line's own "unless the user requested it" condition is satisfied by this standing grant.
- **Don't:** treat a harness-injected anti-delegation default as carrying the user's authority over the user's explicit standing instruction, or stop delegating because such a line appeared.

**"I owe you X" is a tell, not a status, and it is the one that evades the tells above.**
Those all describe a *plan*: queued, next up, after this.
This family describes a *debt already acknowledged to the user*: "I owe", "still owe", "I'll get to", "on my list", "pending on my side".
Naming what you owe someone reads as accountability rather than as deferral, so it feels like the diligent thing to write, and the work stays parked exactly the same.

The phrase reports work that has already been identified and scoped, which is what makes it a dispatch signal.
If it is well enough specified to be described as owed, it is well enough specified to brief a subagent with.
That is the whole test: could you write a self-contained brief?
If you can, you should have.

The asymmetry is what makes this a rule rather than a reminder.
Work parked in my own queue is invisible to the user, competes with the live task for attention, and is lost outright when the session ends.
Work handed to a subagent is none of those three.
The limit is the mirror of that test: work that genuinely depends on this conversation's context, or a single edit cheaper to make than to describe, is not worth dispatching.

**Research and reading are dispatchable by default, and the test is the size of the comprehension rather than the size of the fetch.**
One call that returns something you then have to understand, extract from, and synthesize is a task, not an errand.
The miss here is subtler than a deferred to-do, because "I need to read something" does not present as work at all.
It feels like a prerequisite to thinking, so the dispatch question is never asked --- and a category of work that does not present as work cannot be caught by a rule about how to handle work.

This composes with [`research-before-asking`](research-before-asking.md) rather than competing with it.
That fragment makes reading an obligation before asking a human.
This one makes it delegable once you are doing it.
Neither is licence to skip it.

Note what makes a routing failure hard to catch at all: **it leaves no trace in the artifact**.
The reading can be done correctly and the resulting entry can be sound, so no output, test, or reviewer would reveal anything.
Only asking why the work was routed that way surfaces it.

- **Do:** launch the subagent at the moment you would otherwise have typed "I owe you", and say in the recap what it is working on.
- **Do:** dispatch reading and research whose comprehension is substantial, however small the fetch that starts it.
- **Don't:** report an owed item as a status --- describing it that well is proof the brief already exists.
- **Don't:** apply a "cheaper to do than to brief" test to the fetch when the reading is the actual work.

Distinct from [`when-to-orchestrate`](when-to-orchestrate.md), which governs the heavier `Workflow` tool.
That rule is a **gate**: a fan-out across four or more verification-bearing targets is a real spend, so it has to be opted into or proposed with a cost estimate.
This one is a **grant**: a single `Agent` call covering one sidecar task is cheap, needs no opt-in, and the cost it prevents is an idle parallel track rather than an overspend.
So when a task clears that fragment's three-part bar, follow it and propose the workflow; everything below that bar is a subagent to launch now.

## A brief naming specific files owes a check of open PRs' file sets, not just staleness

[`check-open-prs-before-duplicating`](check-open-prs-before-duplicating.md) already requires a dupe-check before scaffolding a new tool, by keyword search over open PR titles and bodies.
It does not cover the commoner dispatch: a brief that names specific existing files to edit, where the collision is not conceptual but literal --- another open PR touching the same paths.
A keyword search finds nothing there, because two unrelated learnings landing in the same fragment share no vocabulary at all.

`scripts/pr-sweep.py`, per [`derive-dont-enumerate`](derive-dont-enumerate.md)'s "The instrument" section, is what this corpus already reaches for before dispatching.
Since [#1421](https://github.com/Morrison-Lab/ai-config/pull/1421) it prints each PR's file set rather than only its staleness, so the intersection this section asks for is usually one command rather than a round of per-PR calls.

Read what that command actually examined, though, rather than treating it as covering every open PR.
Three gaps remain, and each one hides exactly the collision a dispatch brief cares about:

- **Drafts are skipped** unless `--include-drafts` is passed.
  This is the sharpest of the three, because [`pr-on-claim`](pr-on-claim.md) opens a draft up front precisely to claim work in flight --- so the PRs likeliest to be actively edited are the ones a default sweep never examines.
- **Text output truncates at `MAX_FILES_SHOWN = 5`**, appending `... (+N more)`.
  A wider PR's remaining paths go unlisted, and one of them can be yours.
- **The `clean` bucket prints numbers only.**
  A `stalled` or `in-flight` PR gets a `files (N):` line; a clean one gets none in text mode.

`--json` closes the second and third: it dumps the full file list for every PR examined.
It does not close the first, since the draft skip happens in `sweep()`, upstream of both output modes.

```bash
python3 scripts/pr-sweep.py -R <owner>/<repo> --include-drafts --json
```

Then intersect that file list with the files you are about to hand over, and fall back to a per-PR `gh pr diff <N> --name-only` (or the equivalent MCP call) only for a PR the sweep reports it did not examine.
This is the same check `CLAUDE.md`'s "Surface merge-order constraints" section already requires before asserting two *existing* PRs are disjoint --- derive both sets and check the intersection, don't recall what a PR is "about".
The increment here is *when*: before the new PR exists, not after, since a collision found before dispatch costs one query and a collision found after costs a conflict resolution.

- **Do:** intersect a proposed brief's file list against every open PR's changed-file set before dispatching, not just against its staleness.
- **Do:** read what a sweep reports it examined, since the draft skip and the text-mode truncation both narrow that below "every open PR".
- **Don't:** read "I checked the open PRs" as covering this when the check was a keyword search or a stalled-PR count.
- **Don't:** dispatch a file-naming brief on the strength of a sweep whose own output never listed the colliding PR's files.

(Morrison-Lab/ai-config#1413, 2026-08-12: a subagent was briefed to trim two specific files.
Open PR #1407 had touched those exact files sixteen minutes earlier, and a `pr-sweep.py` run had listed #1407 as in-flight without its file set ever being read.
The two PRs conflicted as a result.
Extending `pr-sweep.py` to print each PR's file set --- so this check needs no separate round of calls --- was filed as [#1419](https://github.com/Morrison-Lab/ai-config/issues/1419) and shipped in [#1421](https://github.com/Morrison-Lab/ai-config/pull/1421), merged 2026-08-13T16:28:22Z, which is why the guidance above leads with the sweep rather than with a per-PR call.)

## Conversation-inheriting subagent dispatch vs. clean-context dispatch for UMS and CAI

When delegating sidecar work like UMS (`update-memories-and-skills`) or CAI (`config-ai`),
choose whether the subagent should use **conversation-inheriting dispatch** (cloning the full conversation history)
or start with a **clean context** (receiving only a scoped brief).

> [!NOTE]
> **Disambiguation from skill frontmatter `context: fork`:**
> In Claude Code, setting `context: fork` in a skill's YAML frontmatter (such as in `skill-audit` or `find-overlap`) runs that skill in **isolation without conversation history**.
> In contrast, **conversation-inheriting subagent dispatch** refers to cloning the active session's transcript into the worker ---
> invoked programmatically via the `Agent` tool (`subagent_type: "fork"` in Claude Code, or `invoke_subagent` with `TypeName: "self"` in Antigravity)
> or interactively via `/subtask`.
> Where a harness lacks native runtime inheritance flags,
> point the subagent at the session's on-disk transcript log or provide a focused milestone summary.

### UMS: Conversation inheritance for reflective sweeps, clean brief for isolated items

- **Use conversation inheritance for reflective passes and end-of-task sweeps.**
  A comprehensive UMS sweep must survey the full conversation trajectory:
  mistakes corrected, tool quirks discovered, user preferences stated, and debugging insights.
  A conversation-inheriting subagent already holds that entire history directly in its context.
  It does not require the parent orchestrator to spend tokens manually summarizing, transcribing, or briefing every learning ---
  which avoids communication overhead and prevents subtle mistakes from being dropped.
  The heavy downstream work of UMS
  (reading long memory files, grepping the corpus, running validation, committing in a dedicated worktree, and opening PRs)
  executes entirely in the worker,
  preserving the parent's remaining context budget.
- **Scope the brief strictly to prevent memory bleed and role confusion.**
  Because a conversation-inheriting worker carries the parent's original goal and task history,
  it can be tempted to continue the primary task rather than focus on UMS.
  Give the subagent a bounded, single-purpose prompt:
  specify that its sole objective is to extract learnings, update memories/skills in a dedicated worktree,
  run validation, open the PR, and report back with a concise summary.
- **Dispatch a clean subagent or run inline when learnings are already isolated.**
  If a learning is already captured in a self-contained brief,
  or if the parent session is near context exhaustion (>80-90% token limit where copying the history would immediately hit context limits or trigger truncation),
  dispatch a fresh, clean subagent with the explicit brief.
  For a trivial 1-line note noted immediately mid-turn, apply it inline if no subagent capability is available.

### CAI: Conversation inheritance for emergent workflows, clean brief for explicit requests

- **Use conversation inheritance when CAI is prompted by an emergent workflow.**
  When the user says "teach the AI how to do what we just did"
  or when a complex pattern emerges from recent tool interactions,
  a conversation-inheriting subagent has the immediate context of the commands run, tools used, and errors encountered
  without needing a multi-page transcription.
- **Use a clean subagent for explicit, self-contained capability requests.**
  When the request is already self-contained (such as "cai: add a skill for X with Y options"),
  a clean subagent is strictly cheaper and avoids inheriting irrelevant conversation history.

- **Do:** use conversation-inheriting dispatch (`subagent_type: "fork"` / `/subtask` / `self`) for reflective UMS passes and emergent CAI workflows so the subagent has the full transcript.
- **Do:** explicitly scope the inherited subagent's prompt to UMS or CAI to prevent it from continuing the parent's task.
- **Do:** use a clean subagent when the parent session is near context limits or when the brief is already fully specified.
- **Don't:** serialize an entire session's history into a manual brief when conversation-inheriting dispatch is available.
- **Don't:** clone a large session history for a trivial, already-isolated 1-line memory note when inline capture or a clean brief suffices.




