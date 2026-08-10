# Claude Code self-scheduling: wakeups, `send_later`, `CronCreate`, and Routines

How a session arms a check-in for later, and the several ways that goes quiet.
Every entry here is a scheduler that accepts the call, reports a time, and then
does not necessarily fire --- so the running theme is that a creation receipt is
not a guarantee, and the state has to be re-read from the store rather than
recalled from the response.
Split out of [`claude-code.md`](claude-code.md) (ai-config#694 pattern) at the
1200-line gate.

## ScheduleWakeup is scoped to `/loop` dynamic mode --- use `send_later` for ad-hoc waits

`ScheduleWakeup` requires a `prompt` param and is meant to re-arm a `/loop`
session's next firing (its own docs say to pass the same `/loop` input back,
or the `<<autonomous-loop-dynamic>>` sentinel).
Calling it outside a `/loop`
context --- e.g. to arm a plain "check back on this PR in 5 minutes" wait ---
throws `InputValidationError: prompt is missing`, since there's no `/loop`
input to hand it.
Use `mcp__Claude_Code_Remote__send_later` (or the harness's
plain wakeup tool, if present) for a one-off self check-in instead; reserve
`ScheduleWakeup` for actual `/loop` iterations.
See the `send_later`
mid-session availability bullet in
[`github-mcp-tools.md`](github-mcp-tools.md) for the fallback (`CronCreate`)
if it disappears.
(ai-config#455/gha#216, 2026-07-03.)

**Correction: the validation error is about a missing `prompt`, not about
being outside `/loop` per se.**
In a remote/web session, calling
`ScheduleWakeup` with an explicit, self-written `prompt` string (not the
`/loop` sentinel) for a plain ad-hoc check-in did **not** throw
`InputValidationError` --- it accepted the call, returned a confirmed clock
time, and the wakeup fired as scheduled.
This is a workable fallback when
`send_later` itself is unavailable or repeatedly failing (e.g. an MCP server
mid-reconnect) --- supply your own full prompt text rather than assuming the
tool rejects non-`/loop` calls outright. (ai-config#583/#585 session,
2026-07-16: `mcp__Claude_Code_Remote__send_later` failed three times in a row
with "Tool permission stream closed before response received"; `ScheduleWakeup`
with a custom prompt worked immediately both times it was tried as a fallback.)

## In a plain local Claude Code session, `ScheduleWakeup` can accept an ad-hoc call but silently fail to fire

This is a DIFFERENT harness/observation from the entry above (that one is the `Claude Code Remote`
MCP server's `ScheduleWakeup`;
the "rejects non-`/loop` calls with a validation error" characterization
was corrected by the block above it --- the error is about a missing `prompt`, not the non-`/loop`
context, and a supplied `prompt` works fine there).
In a plain local Claude Code CLI session, `ScheduleWakeup` accepted an arbitrary one-off
`{delaySeconds, prompt, reason}` call with no error and returned a confirmed clock time (e.g.
"Next wakeup scheduled for 08:27:00") -- but the scheduled re-invocation never actually fired.
Observed twice in a row in the same session: the user had to send a message directly each time
before work resumed, well past the confirmed time.
Root cause unconfirmed from inside the
conversation (no introspection into harness wakeup-delivery internals) -- plausible candidates are
a genuine at-least-once delivery gap for ad-hoc (non-`/loop`) wakeups in this session type, or the
pending wakeup being silently superseded/dropped when a real user message arrives first rather than
double-delivering.
Either way: don't treat a confirmed `ScheduleWakeup` result as a guarantee of
resumption in a plain local session -- prefer a `Monitor`/background-Bash wait (which reports back
via the harness's own task-completion notification, not a separately-scheduled wakeup) when the
condition being waited on is itself observable via a command, and treat `ScheduleWakeup` as
best-effort. (Sparta gii-ffdb93 session, 2026-07-14.)

## `CronCreate`'s job store can silently lose a scheduled job mid-session, so it is a weak fallback for a check-in you have promised a time for

The `send_later`-can-become-unavailable-mid-session bullet in
[`memories/github-mcp-tools.md`](github-mcp-tools.md) recommends
`CronCreate` as the fallback when `send_later` disappears.
It works, but its jobs are in-memory and session-only by design, and they can
vanish **before their fire time** with no error and no notification.

Observed twice in one remote/web session (gha#318 / ai-config#733,
2026-07-26).
A job created at 14:15 PDT to fire at 15:22 was already absent at 15:35 ---
`CronDelete` returned `No scheduled job with id`, and `CronList` returned
`No scheduled jobs`.
A second job created at 15:35 to fire at 16:38 was likewise gone by 15:50,
well before it could have fired.
Creation itself is fine: a probe job created immediately afterward appeared in
`CronList` at once, so this is loss after the fact, not a failed write.
The cause is not confirmable from inside the conversation.
The strongest correlate is that the session's MCP servers disconnected and
reconnected several times in between, which fits an in-memory store being
reset, but that is inference, not something the tools report.

What makes this worse than an ordinary flaky tool: both jobs had already been
reported to the user as a specific clock time, per `CLAUDE.md`'s "State the
actual time when reporting a scheduled check-in" rule.
Stating a time implies a commitment the mechanism silently dropped, and
nothing surfaces the loss --- the check-in simply never arrives.

So:

- Prefer `mcp__Claude_Code_Remote__send_later` whenever its server is
  reachable.
  The two tools' own descriptions say opposite things about durability:
  `send_later`'s reads "Delivery survives container restarts", while
  `CronCreate`'s has a "Session-only" section saying jobs live only in the
  current session, nothing is written to disk, and "the job is gone when
  Claude exits".
  Read them in the tool schemas themselves rather than inferring durability
  from this corpus.
- When you do fall back to `CronCreate`, say so in the same breath as the
  time: name it as a session-only, best-effort check-in rather than letting
  "I'll check back at 16:38" read as a guarantee.
- Re-verify with `CronList` before relying on a job you armed earlier ---
  a one-call check that decides it exactly, rather than trusting the
  creation receipt.
  This is [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
  applied to your own scheduling: the store either lists the job or it does
  not.
- Where the thing being waited on is observable by a command, a
  `Monitor`/background-Bash wait is sturdier than any scheduler, for the same
  reason the `ScheduleWakeup` entry above gives --- it reports through the
  harness's own task-completion path instead of a separate delivery
  mechanism.

## `update_trigger` with only a `prompt` does not reschedule a fired one-shot Routine

A one-shot Routine --- one carrying `run_once_at`, which is what `send_later`
builds --- retires itself once it fires.
Passing `update_trigger` a new `prompt` and nothing else replaces the prompt
and leaves the schedule where firing left it, roughly 24 hours out.
The call returns success either way.

Measured 2026-08-10 on `trig_016EUTjMyS4V7AsTJotyKsbY`, a self-bind trigger
created by `send_later`:

| step | `next_run_at` afterwards |
| --- | --- |
| fired; `last_fired_at` `2026-08-10T03:32:42Z` | --- |
| `update_trigger` with `prompt` only, ~03:35Z | `2026-08-11T03:32Z` |
| `update_trigger` with `run_once_at: 2026-08-10T03:58:00Z` | `2026-08-10T03:58:00Z` |

So the near-term check-in that call was meant to arm was still a day away, and
supplying a fresh `run_once_at` is what actually scheduled it.

**Two states are reachable here, and the second is the dangerous one.**
A fired one-shot that nobody has touched is *retired*: it carries
`ended_reason: "run_once_fired"` and no `enabled` field at all, so its
`next_run_at` is cosmetic and nothing will fire.
The trigger above, read after the prompt-only update, instead carried
`enabled: true` and **no** `ended_reason` --- a live Routine scheduled a day
late.
On that reading the update did not merely fail to reschedule; it revived a
retired one-shot without setting a near-term time, so the check-in arrives
once, roughly 24 hours after it was wanted, in a session that has long since
moved on.

Treat that second shape as a single observation rather than as settled.
The retired shape is verified --- every fired, never-updated one-shot in two
`list_triggers` reads 20 minutes apart showed `ended_reason` with no `enabled`
field.
The revived shape rests on one reading of one trigger, and it is no longer
reproducible: that trigger has since been updated again, so the intermediate
state is gone.

**The check that catches both shapes is `next_run_at` against the time you
intended --- not `ended_reason`.**
Reading `ended_reason` distinguishes retired from live, and that is the wrong
axis: in the revived shape it is absent and `enabled` is `true`, so both fields
report a healthy Routine while the schedule is a day wrong.
Only comparing the returned time against the time you asked for separates "this
will fire when I wanted" from either failure.

**The failure is silent, and its output is indistinguishable from success.**
Nothing in the prompt-only response says the schedule was untouched --- the
call succeeds and echoes a populated, plausible timestamp rather than an empty
field, which is what makes reading it as confirmation easy.
That is [`fail-fast`](../shared/principles/fail-fast.md)'s figure of a check
whose failure path and pass path print the same thing, arriving in a scheduling
receipt.
It compounds with `CLAUDE.md`'s "State the actual time when reporting a
scheduled check-in", the same way the `CronCreate` entry above does: the
returned `next_run_at` is the value you would quote to the user, so the wrong
one gets reported as a commitment.

**The 24-hour value is what firing leaves behind, not something the update
produced.**
Every fired one-shot in the account's trigger list carries it, and none of the
others was prompt-updated, which rules the update out as its cause.
Across the 18 fired one-shots on the first `list_triggers` page,
`next_run_at` minus `last_fired_at` was 24 hours in all 18, within a quarter of
a second.
It anchors on `last_fired_at` rather than on `run_once_at`: measured against
`run_once_at + 24h` the same rows are off by 40 to 151 seconds, tracking each
trigger's firing latency.
Derive both rather than trusting these figures, since the page slides as
triggers fire, and note that page reported `has_more: true`, so 18 is a page
rather than the population:

```python
# mcp__Claude_Code_Remote__list_triggers, over rows carrying ended_reason
(parse(next_run_at) - parse(last_fired_at)).total_seconds()  # 86399.77 .. 86399.86
(parse(next_run_at) - parse(run_once_at)).total_seconds()    # 86440 .. 86551
```

**Why a retired one-shot gets a `next_run_at` a day out at all is
unexplained.**
Nothing here establishes it, and no mechanism should be asserted for it --- a
well-formed guess would be a prediction rather than a finding.
What is measured is the roll-forward, its anchor, its independence from the
update, and the remedy.

Note what is *not* the finding, since the adjacent fact is documented while
this one is not.
`update_trigger`'s own schema says that setting `run_once_at` clears
`cron_expression` (and any `ended_reason`) and that setting `cron_expression`
clears `run_once_at`.
It says nothing about what a prompt-only update does to a one-shot that has
already fired.

- **Do:** pass a fresh `run_once_at` whenever you re-arm a fired one-shot, in
  the same call that updates its prompt.
- **Do:** compare the returned `next_run_at` against the time you intended, and
  treat any large gap as the update not having scheduled what you asked for.
- **Don't:** update only the `prompt` and read the returned `next_run_at` as
  confirmation that the Routine is re-armed --- it is populated either way, and
  on a fired one-shot it is a day out.
- **Don't:** rely on `ended_reason` or `enabled` to tell you a Routine is
  scheduled correctly; in the revived shape both look healthy while the time is
  wrong.
- **Don't:** quote a check-in time to the user from a prompt-only update's
  response.
- **Don't:** attribute the 24-hour value to the update; it is what firing
  leaves behind, anchored on `last_fired_at`.
