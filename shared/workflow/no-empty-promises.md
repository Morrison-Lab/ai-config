A promise about my own future behaviour is not work.
It is a claim that work will happen later, made in a conversation that will not
outlive it.

So: **no empty promises.**
Every commitment of the form "going forward, I will X", "from now on I won't Y",
"I'll always Z", "I won't do that again", "that is owed by me" must ship an **implemented
accountability mechanism in the same turn** --- or not be made at all.

## Why this needs a rule rather than more care

A promise is composed at the exact moment a correction lands, which is the
moment the corpus is not being read.
It arrives feeling like the corrective action rather than like a substitute for
one, because it is responsive, specific, and stated in the first person ---
everything an actual fix would be, minus the fix.

Nothing downstream detects it.
No file changes, so review cannot see it; no check turns red, so CI cannot; and
the reply reads as accountable, so the user cannot either.
That combination --- costless to produce, invisible to every instrument, and
indistinguishable from having done something --- is what makes it worth a rule
instead of an intention.

It is also strictly worse than saying nothing, and that is the part the promise
conceals.
Silence leaves the problem visibly unaddressed.
A promise leaves it addressed *on the record*, so nobody returns to it, and the
next recurrence reads as a fresh event rather than as the second instance of a
known one.

## What discharges it

Any durable, inspectable artifact, written in the same turn as the promise.
Three, in ascending cost:

- **A memory or rule entry** --- a `memories/` file, a `CLAUDE.md` or
  `AGENTS.md` section, a `shared/` fragment.
  The minimum, and always available: a promise can always be converted into a
  written rule, whatever else is or is not possible.
- **A hook**, when the condition is decidable from the transcript.
  This is the "memory + hook pair" the directive names, and
  [`deterministic-tools`](../principles/deterministic-tools.md) is the argument
  for it: a rule is consulted at read time and broken at composition time, so a
  guard that fires at the boundary is the only thing that reaches the moment
  the rule fails.
- **A filed issue**, when the mechanism is real work someone has to schedule.

**There is no "not mechanizable" escape here**, unlike
[`no-mistake-without-a-hook`](../../hooks/no-mistake-without-a-hook.py), which
needs one because a one-off factual slip has no decidable condition to key a
hook on.
The memory route above is always open, so the honest alternative to building a
mechanism is not to promise anyway --- it is to **drop the promise and state the
fact**.
"I was wrong about X, and here is Y" costs the user nothing and claims nothing.

## The near-miss

The move this rule has to rule out is not the bare promise, which is obvious
once named.
It is the promise that *names* its own mechanism in the future tense: "going
forward I'll check this --- I'll add a hook for it."

That reads as compliance from the inside, and it satisfies nothing.
The mechanism is still hypothetical, the turn still ends with nothing durable in
it, and the sentence has now spent the reader's attention on an accountability
step that has not happened.
It is the same shape
[`run-ums-proactively`](run-ums-proactively.md) rejects for the announced UMS
pass and
[`report-mistakes-proactively`](report-mistakes-proactively.md) rejects for the
offered issue: naming the work is not the work, and moving the gate from
*whether* to *when* does not change that.

The test is mechanical, so apply it rather than judging the tone: **if the
sentence commits to future behaviour, something in the same turn must already
exist that a later reader could open.**
A path, an issue number, a diff.
Not a plan to produce one.

## Its own mechanism

This rule is itself a promise about future behaviour, so a version of it
shipping as prose alone would be an instance of what it forbids.
[`hooks/no-empty-promise.py`](../../hooks/no-empty-promise.py) is the mechanism:
a `Stop` guard that blocks a reply carrying a forward-looking first-person
commitment when the same turn wrote nothing durable.

It blocks rather than reminds, which is the opposite call from
[`remind-ums-after-error.py`](../../hooks/remind-ums-after-error.py), and the
reason inverts cleanly.
An error admission is right to send, so blocking it would suppress an honest
correction.
An undischarged promise is wrong to send, and delivering it first buys nothing
--- the mechanism was the whole point of the promise.

## Do / Don't

- **Do:** ship the mechanism in the same turn as the promise, and name what you
  shipped, in the past tense.
- **Do:** default to the memory or rule entry when nothing heavier fits --- it
  is always available, so "there was no mechanism to build" is never the reason.
- **Do:** drop the promise and state the plain fact when the mechanism is not
  worth building.
- **Don't:** promise a *standing rule* and leave the turn with no durable
  artifact in it.
  An owed **action** is the one case where an armed firing substitutes for the
  durable artifact --- see the debt section below, which is the only exemption
  and does not widen to rule promises.
- **Don't:** promise the *mechanism* in the future tense ("I'll add a hook for
  this") --- that is the same empty promise one level down.
- **Don't:** read an apology, an explanation, or a restatement of the rule as a
  mechanism.
  None of them survives the conversation.

## The debt phrasing is the same promise, and it reads as bookkeeping

Every example above is a **modal**: "I will", "I won't", "I'll always", "I'm going to".
A commitment can drop the modal entirely and state itself as an outstanding debt instead --- "the UMS pass is owed by me", "I owe you a hook for this", "I still owe that follow-up".

Those commit to future behaviour exactly as the modal forms do, and they are harder to catch from the inside.
The sentence reads as bookkeeping rather than as a pledge, so naming the debt feels like the diligent move --- which is what an unbacked promise always feels like at the moment of making it.
The trade is the one this rule already rejects, and it is arguably worse here: costless to produce, invisible to every instrument, and it closes the item on the record so nobody returns to it.

Ship the mechanism in the same turn and name it in the past tense, or drop the debt language and state the plain fact --- that the work was not done, and whether anything tracks it.

**What the mechanism IS, though, is not unchanged, and that is the half this section originally got wrong.**
A rule promise is kept by something **durable**, because it has to survive into every future occasion it covers.
A debt is one specific outstanding action, so what keeps it is something that will actually **fire**: a `ScheduleWakeup` carrying the next step, a `CronCreate` or scheduled task for a check-in that must outlive this session, the `schedule` or `loop` skill (both harness-provided rather than in this repo), [`workaround-watcher`](../../skills/workaround-watcher/SKILL.md), or the repo's own detached poller (`python3 hooks/monitor-open-prs.py`) when the debt is a PR to watch.

The durable record still clears a debt, and deliberately so.
It is the always-available floor this fragment insists on everywhere else, and it is the *right* answer when the debt is somebody else's to schedule --- a filed issue is exactly how you hand work to whoever will do it.
It is the wrong instinct when the debt is yours and has a next step.
A memory entry saying "#1937 needs an ARDI round" documents an outstanding loop.
It does not run one, and nothing wakes the session when the re-review lands.

That gap is what made the debt phrasing worth a rule of its own rather than a footnote to the modal one.
Before it was named, the cheapest way past a blocked "I owe #1937 the ARDI loop" was to write a memory entry and re-send the same sentence --- leaving the debt documented, closed on the record, and still undelivered, which is the exact failure this whole fragment exists to prevent, now wearing the remedy's clothes.

**The implication runs one way only.**
A timer does not keep a rule promise.
It fires once and dies, so treating an arming as sufficient there would let an unrelated wakeup launder "going forward I'll always X".
Durable clears both; scheduled clears only the debt.

**Report the firing, not just the arming.**
Per `CLAUDE.md`'s "State the actual time when reporting a scheduled check-in", say the clock time the timer returns rather than the delay, and say what fires --- otherwise the arming is itself an unverifiable claim, which is the shape this rule is about.

- **Do:** arm the next step when the debt is yours and has one, and report what you armed and when it fires.
- **Do:** file the issue instead when the debt is somebody else's to schedule.
- **Don't:** answer an owed **action** with a written record and call it discharged --- documenting an ARDI loop is not running one.
- **Don't:** count a timer as keeping a standing rule --- it cannot outlive the one firing.

(Directive from the user, 2026-08-22: "phrases with 'owe' ... should be triggers for our no-empty-promises guards;
the models should be pushed or forced to create and report a mechanism for delivering on what they owe, such as scheduling a timer or other PR-watcher to trigger the next step of the ardi loop when it is time".
Tracked as ai-config#1946.)

[`hooks/no-empty-promise.py`](../../hooks/no-empty-promise.py) matches this form too, anchored on a first-person **owner** rather than on the word alone, and applies the debt discharge set above to it rather than the rule one.
That anchoring is load-bearing rather than fussy: this corpus says "an owed UMS pass" and "the pass is owed" in ordinary rule prose, so a matcher keyed on bare `owed` would block every reply that cites those rules --- the trap [`hooks/no-placeholder-reply.py`](../../hooks/no-placeholder-reply.py) avoids by anchoring on the whole message rather than a substring.
So "an owed UMS pass" stays clean, and "owed by me" does not.

- **Do:** file the issue, write the memory, arm the next step, or do the work, then say the debt is discharged.
- **Do:** say plainly that something was not done, and name what tracks it, when nothing durable followed.
- **Don't:** write "owed by me", "I owe", or "I still owe" into a turn that shipped neither a durable artifact nor an armed firing.
- **Don't:** read the absence of a modal as the absence of a promise.

(Directive from the user, 2026-08-20: "'Owed by me' is another phrase indicating a broken promise".
Tracked as ai-config#1792.)

(Directive from the user, `cai`, 2026-08-19: "no empty promises; every promise
('going forward, I will/won't' etc) must be accompanied by an implemented
mechanism for ensuring accountability (for example, a memory + hook pair)".
Dupe-checked at the time over `*.md` and `*.py`: `empty promise` returned 0
hits, `going forward` returned 4 incidental prose hits and no rule, `promise`
returned 19 files all in the JavaScript/GitHub-API sense or about a closed PR's
promised follow-up work, and `accountab` returned one unrelated hit in
[`use-subagents`](use-subagents.md).
Tracked as ai-config#1723.)
