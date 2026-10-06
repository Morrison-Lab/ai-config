# Always arm a persistent PR loop

When you open, push to, or are handed a PR, arm a persistent monitoring loop if one is not already running.
Keep it running until the PR merges, closes, or the user says stop.
This applies in any repo, not only Morrison-Lab ones.

A one-shot status poll is not babysitting.
A PR-activity subscription is not a loop.
PR-activity webhooks (`subscribe_pr_activity`) do not deliver CI success, new pushes, or merge / merge-conflict transitions.
Subscribe when that tool exists, and re-arm a periodic check-in using whatever wake mechanism this session has:
Claude Code: `/loop`, `send_later`, `CronCreate`, or a `schedule` timer;
Antigravity: `schedule` one-shot timer or cron;
other harnesses: their own scheduler or timer.
A question like "are you monitoring that PR?" is a status check, not a reason to stay idle.
Start the loop if it is not already running, then answer.

## Turn on Auto-fix in the Claude desktop app

In the Claude desktop app's Code tab, turn on the PR's **Auto-fix** switch (the CI popover's checkbox, or `mcp__ccd_pr__set_monitor` with `auto_fix: true`) right after opening or binding a PR (owner directive, 2026-10-05).
There it is the loop:
the app wakes the session with a `<ci-monitor-event>` on CI failures, merge conflicts and review comments,
and its own instructions forbid self-scheduled CI polling, so do not also arm a timer to poll checks.
If the switch can't be turned on (the tool is missing, or a permission check refuses it), say so and ask the user to tick it;
do not fall back to polling.

An Auto-fix wake is a prompt to check the PR's real state, not an order to push.
Fix only what your changes caused:
leave pre-existing failures alone and note them in the PR description,
don't weaken a check to get green (a spelling exception, `--allow-skips`, a loosened threshold) unless the flagged item is really correct,
and hand a failure that turns on content or reasoning back to the reviewer instead of patching it.
Comments that carry no finding, like a quota refusal or a preview-URL sticky, need no reply or push
(see `memories/claude-code.md`).

## Forge polling after push

After every push to a PR/MR, actively poll the forge until the current head's CI/pipeline and review reach a terminal state.
Use `gh` for GitHub and `glab` for GitLab when those CLIs are available;
query the PR/MR, current-head checks or pipeline, and review comments or notes rather than assuming an event-triggered reviewer completed.
Re-arm the poll while work remains.

Baking a self-merge directive into the loop/wakeup prompt is allowed only under a standing merge-when-confident (`mwc`) session grant.
A one-off "merge this PR" instruction authorizes merging the current head once.
It never licenses a later wake to self-merge a different head.

- **Do:** arm a persistent loop in the same turn you open, push to, or take over a PR, and skip starting a second one if a loop is already running.
- **Do:** after every push, actively query the current head's CI/pipeline and review state with `gh` or `glab` until that round is terminal.
- **Do:** in the Claude desktop app, turn on the PR's Auto-fix switch instead of arming a polling timer.
- **Don't:** treat a subscription or a one-shot poll as watching, treat event-triggered automation as evidence of completion, or refuse to start a loop because the latest message only asked about status.
