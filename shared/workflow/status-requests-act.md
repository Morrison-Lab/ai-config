# Status requests do not make issues report-only

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#status-requests-do-not-make-issues-report-only) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

Treat a request for status as a request to inspect live state and finish every
safe, in-scope, concrete action that inspection reveals. A report is the recap
after the work, not a substitute for it. When an issue cannot be fixed
directly, carry it forward with an actual next action. **Every issue noticed,
however small or outside the current task's scope, must at minimum be filed in
the owning GitHub, GitLab, or equivalent tracker.** File it before reporting
it; use the correct private tracker and redact sensitive details when needed.

A status report never lists a PR or MR as waiting on human review without a clean automated review on its latest commit;
when that review has not run, start it under the conditions in [`automated-review-before-human`](automated-review-before-human.md).

## Examine the transcript for stalls, freezes, and dropped balls

When a user asks for a "status update", "status?", or "how is it going", the inquiry is often prompted because the agent stopped responding, lost momentum, or paused unexpectedly.
Never limit a status check to passive reporting or live forge polling alone: examine the conversation transcript and turn history to determine if the agent got stuck, frozen, or dropped the ball.

Check for these dropped-ball patterns in recent turns:
1. **Unhandled tool failure or denial:** A command or tool call errored (e.g. auth failure, rate limit, permission denial, syntax error) and the agent stopped without diagnosing, fixing, or retrying it.
2. **Abandoned background task or subagent:** An asynchronous task or subagent was launched or notified, but was never polled, checked, or integrated into the main pipeline.
3. **Unarmed pause:** The session paused or returned control to the user without arming a timer or wake mechanism while work remained queued.
4. **Unfulfilled commitment:** An assistant turn announced an intended step (e.g. "I will push after review", "Starting on X") but stopped without executing it.
5. **Passive status repetition:** The agent previously repeated that something was in progress without inspecting whether it had completed, stalled, or failed.

When a stall or dropped ball is discovered:
- **Diagnose the failure:** Name what failed and why progress halted.
- **Resume immediately:** Do not ask for permission to continue or end the turn with a passive status report.
  Perform the dropped or next concrete action in that very same turn.

- **Do:** examine recent transcript turns and tool results to detect whether previous turns froze, errored, or dropped the ball before reporting status.
- **Do:** resume stalled or dropped work immediately in the same turn instead of waiting for a separate user prompt.
- **Do:** fix an actionable CI defect, review finding, or configuration gap
  before reporting it as status; revalidate and continue the sweep.
- **Do:** turn an issue outside current authority into a filed/routed blocker,
  not an unowned observation.
- **Do:** file every noticed issue in its owning tracker, even when it is
  trivial, already fixed locally, or outside the active task.
- **Don't:** treat "status update" as passive report-only when the transcript reveals a dropped ball or an unhandled failure.
- **Don't:** repeat cached or previous status without checking whether the in-flight step finished, stalled, or crashed.
- **Don't:** interpret "status" as report-only after discovering a concrete,
  safe, in-scope repair.
- **Don't:** end with "this failed" or "this needs a fix" when the fix is
  available to perform in the same turn.
- **Don't:** leave a noticed issue as chat prose because it seems too small or
  too far outside the current scope to track.
