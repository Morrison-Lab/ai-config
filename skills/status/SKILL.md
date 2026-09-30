---
name: status
description: "Diagnose stalls, resume dropped work, and report status."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# status (Status Update and Recovery)

Inspect conversation history, active processes, and live repository/forge state to deliver an authentic status update. If the agent became stuck, frozen, or dropped the ball in previous turns, diagnose the stall and resume the dropped work immediately.

## When this fires

- "status", "status update", "progress update", "what's the status", "where are we"
- "are you stuck", "are you frozen", "did you drop the ball", "what happened"
- Any general inquiry about the state of ongoing work or current turn progress

## Procedure

### 1. Inspect the transcript for stalls and dropped balls

Before polling forge or CI state, review recent session turns in the conversation transcript (`transcript.jsonl` or conversational turn history):
1. **Unhandled tool failure:** Did a command, API call, or script return an error, auth failure, rate limit, or denial that was never diagnosed or retried?
2. **Abandoned or forgotten subagent/task:** Was a subagent dispatched or background job started that completed or hung without the conductor processing the result?
3. **Unarmed pause:** Did the agent end its previous turn without arming a wake mechanism (timer or monitor) while work remained queued?
4. **Unfulfilled commitment:** Did the agent announce an action ("I'll start on X", "I will push after review") but stop without doing it?
5. **Frozen or silent stall:** Did execution pause mid-stride without completing the planned task?

If any dropped ball or stall occurred:
- State what failed or where execution paused.
- **Resume immediately:** In this very same turn, re-run the failed step, resolve the error, or continue the interrupted workflow. Never make status report-only when work was dropped.

### 2. Inspect live workspace and git state

Run local git checks:
```bash
git status --short
git log -n 3 --oneline
git worktree list
```
Verify whether any uncommitted edits, unpushed commits, or detached worktrees exist.

### 3. Inspect live forge and CI state

If working on a PR or issue:
- Check if the PR is still open:
```bash
gh pr view <N> --json state,title,headRefOid
```
- Check CI status:
```bash
gh pr checks <N>
```
- Parse the latest review comments on HEAD to ensure no unresolved findings remain.

### 4. Advance work and arm a wake mechanism if waiting

- If concrete actions are ready (tests to run, review findings to fix, branch to push, PR to merge), execute them in the same turn.
- If legitimately waiting for external automation (e.g. CI running, remote review in progress), ensure an active wake timer or monitor is armed with `schedule`.

### 5. Report concise, dated status

Conclude with:
- What was diagnosed and resumed (if a stall occurred).
- Current live state (PR#, CI state, review verdict).
- Clock time in Pacific Time (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`).
- Explicit `**Stopping Point**` declaration stating whether the session is done or ongoing.

- **Do:** check the transcript for unhandled errors, forgotten subagents, or unarmed pauses before reporting status.
- **Do:** resume stalled or dropped work immediately in the same turn.
- **Do:** report fresh live state rather than echoing stale cached facts.
- **Don't:** treat a status request as report-only when the agent previously froze or dropped the ball.
- **Don't:** ask the user for permission to resume work that was already queued or promised.
