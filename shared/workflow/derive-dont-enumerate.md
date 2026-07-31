A brief that enumerates work items is a snapshot.
Before dispatching work scoped to a list --- PR numbers, issue numbers, files, hosts --- ask whether that set can grow or change while the work runs.
When it can, do not hand over the list.
Hand over the query that derives it, or run a sweep against the live set on a timer.

The failure this prevents is invisible by construction, which is why it needs a rule rather than more care.
Every agent does its job correctly on the list it was given, so no artifact reports a problem: the PRs that appear *between* the lists are covered by nobody, and coverage is a property of the **set** rather than of any member.
There is no file to grep, no check to go red, and no reviewer whose scope includes it.
Asking "did anyone drop something" cannot be answered by inspecting any of the things that were done.

Note the class this belongs to.
It is the same defect as a status reading that expires when a push lands, or a `mergeable` flag cached from before `main` moved: a fact about a moment, consumed later as though it were current.
[`fully-clean`](fully-clean.md) makes that point about one PR's verdict.
This makes it about the queue.

## The tell

A list is a snapshot whenever something other than you can add to it while you work.
Concretely, treat as derivable rather than enumerable:

- Open PRs and issues, in any repo where another session, a bot, or a human can open one.
- Failing checks, which a later push can add or clear.
- Files matching a pattern, where a merge can introduce another.
- Repos in scope, hosts in a fleet, or members of any set an API already enumerates.

A list is safe to hand over only when it is closed: a fixed set of inputs, frozen at a commit, that nothing can extend mid-flight.

## What to hand over instead

Give the recipient the derivation, not its result:

- **A query.** "Every open non-draft PR" beats "#937, #939, #943, #946", and stays correct when a seventh appears.
- **A predicate.** "Any PR idle past the threshold with an unaddressed finding" beats a list of the ones that were stalled when you looked.
- **A sweep on a timer.** When the work outlives a single pass, the set must be re-derived per pass, not carried forward from the first one.

When you genuinely must name specific items --- a stacked merge order, an exclusion --- say what the list is *for* and that it is a snapshot, so the recipient knows to re-derive rather than trust it.
The distinction is between a list used as an **index** of the work, which rots, and one used as a **constraint** on it, which does not.

## The instrument

`scripts/pr-sweep.py` is this rule's deterministic half for the open-PR case.
It derives the live set for one or more repos and reports which PRs are stalled, with a configurable threshold:

```bash
python3 scripts/pr-sweep.py -R Morrison-Lab/ai-config -R ucdavis/bcs
python3 scripts/pr-sweep.py -R owner/name --stale-minutes 15 --json
```

It always reports what it examined, not only what it found, so a sweep that examined nothing is distinguishable from a clean one.
Per [`algorithmatize-checks`](algorithmatize-checks.md), "which PRs are stalled" has a numeric definition over data the API already returns, so it should not cost model reasoning.

It is **read-only reporting, not authorization**.
[`ardi`](ardi.md) limits its monitoring mandate to PRs a session owns or has explicitly claimed, and a PR appearing in this sweep does not transfer ownership.
Surface an unowned stalled PR to the human, or claim it per [`claim-pr`](claim-pr.md) before driving it.

[`pr-status-all`](../../skills/pr-status-all/SKILL.md) remains the richer per-PR dashboard; this is the cheap standing sweep that says where to point it.

## In review

Flag a brief, a plan, or a skill step that hands an agent a hard-coded list of PR or issue numbers to work through, where the tracker could gain another before the work finishes.
Ask for the query instead.
This is [`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md) applied to work items rather than to documentation: that fragment's "prose enumerations rot unnoticed" section is the same argument about a different artifact, and its remedy is the same one --- replace the list with a pointer, rather than refreshing the list and resetting the clock.

- **Do:** hand over the query that derives the set, and re-derive it once per pass.
- **Do:** state the examined count alongside any finding count, so a sweep that examined nothing is distinguishable from a clean one.
- **Don't:** hand an agent a list of item numbers when something else can add to that set while the work runs.
- **Don't:** treat "every item on my list was handled" as evidence that everything was handled --- that is the claim the list cannot support.

(Morrison-Lab/ai-config#960, 2026-07-30/31: agents were dispatched with enumerated PR numbers, and one brief said "#937, #939, #943, #946 are already CLEAN --- leave them alone", which was true when written.
#943 and #946 each gained an open review thread within minutes, and nothing was watching them for 73 minutes.
#953 and #954 were opened by other sessions afterward, so no brief contained them, and #954 sat with two failing checks for 26 minutes.
#957 was opened later still.
Running the sweep built for this issue at 07:35Z reported #943 and #946 stalled at 83.5 and 81.7 idle minutes with unresolved threads, and #954 stalled with a genuinely failing `validate` --- the three PRs no list contained.)
