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

