Triage a new ask against the current backlogs before acting on it, so it joins the work that already owns it instead of spawning parallel work.

Ezra, 2026-10-29: "when I give you (the orchestrator) tasks to work on, you should triage them against the current backlogs".
This applies to every orchestrator and coordinator, in every project, by default.

## The pass

Before starting a thread, a subagent, an issue or a PR for a new ask, check these, in this order:

- the open issues and PRs in every repo the ask touches, with a search that includes closed ones (see [`issue-first`](issue-first.md));
- the active threads or sessions, so a second session does not take on work a live one owns;
- project memory, for standing decisions that bear on the ask.

Then decide which of these applies, and say so in one line when routing or starting:

- **duplicate**: the work already exists, so link it and stop;
- **extends**: fold the ask into the owning issue, PR or thread, and message that thread instead of spawning one;
- **conflicts**: name the conflicting item and the ask's resolution;
- **blocks / is blocked by**: link the item and order the work accordingly;
- **new**: start it, with a priority (`P1`, `P2`, `P3`) set relative to what is open.

## What triage must not do

- It does not delay the acknowledgement: acknowledge first, triage in the same turn.
- It does not add questions for the user: a triage outcome the orchestrator can decide is decided, per [`default-to-action-grants`](default-to-action-grants.md).
- It does not replace the weekly backlog pass in [`triage-backlog`](triage-backlog.md), which labels open issues.
  That pass triages issues already filed; this one triages an ask on arrival.

## Mechanism

`hooks/warn-agent-spawn-without-backlog-check.py` warns, never blocks, when a write-capable `Agent` or `Task` launch has no tracker query earlier in the session.
A lexical scan shows that a query ran, never that its result shaped the routing, so the one-line routing statement above is the part only the orchestrator can supply.

Hooks do not run in cloud and web sessions ([#2004](https://github.com/Morrison-Lab/ai-config/issues/2004)), and a cloud coordinator starts threads with tools no local transcript shows.
For those sessions no hook can enforce this, so the rule lives in this fragment and in the `triage` skill's "New asks" section.
