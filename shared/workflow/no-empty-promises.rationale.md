# Rationale: No empty promises

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#no-empty-promises) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

[`shared/workflow/no-empty-promises.md`](no-empty-promises.md)

A commitment about my own future behaviour --- "going forward, I will X", "from
now on I won't Y", "I'll always Z", "I won't do that again", "that is owed
by me" --- must ship an
**implemented accountability mechanism in the same turn**, or not be made at
all.
A memory or rule entry is the minimum and is always available; a hook is the
right form when the condition is decidable from the transcript (the "memory +
hook pair" the directive names); a filed issue covers work someone has to
schedule.

The promise is costless to produce and invisible to every instrument --- no file
changes, no check turns red --- while reading exactly like accountability, which
is why it needs a mechanism rather than an intention.
It is worse than silence, too: silence leaves the problem visibly unaddressed,
while a promise closes it on the record so nobody returns to it.

The near-miss is the promise that names its own mechanism in the future tense
("going forward I'll check this --- I'll add a hook for it"), which reads as
compliance and satisfies nothing.
The test is mechanical: if the sentence commits to future behaviour, something
in the same turn must already exist that a later reader could open.

There is no "not mechanizable" escape, unlike
[`no-mistake-without-a-hook.py`](../../hooks/no-mistake-without-a-hook.py) --- the
memory route is always open, so the honest alternative to building a mechanism
is to drop the promise and state the plain fact.
[`hooks/no-empty-promise.py`](../../hooks/no-empty-promise.py) is this rule's own
mechanism: a `Stop` guard that blocks a forward-looking commitment when the turn
wrote nothing durable.

An owed **action** is the case where the mechanism has to *fire* rather than merely record.
"I owe this PR the ARDI loop" commits to one specific next step, and a memory entry documenting that loop does not run it --- so arm the step (a `ScheduleWakeup` carrying it, a cron or scheduled task, a PR watcher) and report what fires and when.
A durable record still clears such a debt, and is right when the debt is somebody else's to schedule.
The implication runs one way only: a timer fires once and dies, so it cannot keep a standing rule.

- **Do:** ship the mechanism in the same turn, and name it in the past tense.
- **Do:** arm the next step, and report its clock time, when what you owe is an action rather than a rule.
- **Do:** drop the promise and state the fact when no mechanism is worth
  building.
- **Don't:** end a turn carrying a promise and no mechanism --- a durable
  artifact for a standing rule, and either that or an armed firing for an
  owed action.
- **Don't:** promise the mechanism itself in the future tense.
- **Don't:** reach for a written record when the owed action is *yours* and
  has a next step you could arm --- documenting an ARDI loop is not running
  one.
  (A record is a valid discharge, and the wrong instinct here; the `Do` above
  says which case is which.)
