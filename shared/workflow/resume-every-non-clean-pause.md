Whenever work remains at a pause, arm a timer, scheduled job, background monitor, or equivalent wake mechanism that will resume the next concrete step.
A pause is any point where the agent yields the turn to the user or waits on external processes (CI checks, code review, test suites, subagents).

## The Core Rule

- If work remains queued or in flight, **it is not a clean stopping point**.
- State `**Stopping Point**: Not a clean stopping point / work remains queued: <details>` in the reply.
- **Arm a wake mechanism before ending the turn.** Report the concrete mechanism armed and the exact clock time it will fire in local time (Pacific Time).
- A verified clean stopping point (`**Stopping Point**: Clean stopping point reached`) needs no timer because no work remains to resume.

## Why this rule exists

Stopping a session while work is unfinished without an armed wake mechanism turns an automated agent into an abandoned process.
The agent goes silent, and hours can pass before a human notices that a test run completed, a PR passed checks, or review comments arrived.
An armed timer or scheduled trigger guarantees that the harness will wake up and resume the next step autonomously.

## Do / Don't

- **Do:** arm a timer (`schedule`, `ScheduleWakeup`, `CronCreate`, or background poller) whenever yielding a turn before all tasks are complete.
- **Do:** report the exact clock time the wake mechanism will fire in local time (`TZ=America/Los_Angeles`).
- **Do:** declare `**Stopping Point**: Not a clean stopping point / work remains queued: ...` whenever any task, PR, review, or CI run is incomplete.
- **Don't:** yield the turn with a message like "waiting for tests to complete" or "waiting for CI" without arming a wake mechanism in that same turn.
- **Don't:** substitute a promise to return ("I'll check back") for an armed mechanism that actually wakes the session.
