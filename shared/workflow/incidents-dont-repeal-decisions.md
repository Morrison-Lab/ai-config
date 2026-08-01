When an incident makes you stop doing something you had decided to do, either re-argue the decision explicitly or fix the misuse.
Never just change the behaviour.

A deliberate reversal leaves a trail.
Someone argues it, someone records it, and the next reader can find out why.
This kind leaves none.
The practice simply stops, and the moment of stopping is not a moment at all -- there is no message where anyone decided, so there is nothing to disagree with later.

## Why nothing catches it

Every other guard in this corpus inspects an artifact.
A reviewer reads a diff, a test exercises a function, a hook fires on a tool call, a linter reads a file.
A repealed decision changes none of them.
The work still gets done, the diffs still look right, and the checks stay green, because the thing that changed is which options were considered before the work started.

So the only detector is someone who remembers the decision.
That is a person, it is not reliable, and it degrades with every session boundary, which is the argument for writing the decision down somewhere a machine can check it rather than trusting that it will be noticed.

## Why it is more dangerous than ordinary drift

Drift by neglect is a practice nobody was thinking about.
This is a practice you *were* thinking about, right up until an incident handed you an apparent reason to stop.

That reason is what makes it durable.
From the inside it does not feel like lapsing.
It feels like having learned something, which is the one interpretation that will not prompt a review.
An unexamined reason is also unfalsifiable, because it was never stated: no one can rebut an argument that was never made, and the incident's authority carries the conclusion without ever supplying the premises.

The tell is retrospective and simple.
If you cannot point at the message where the decision was reversed, it was not reversed.
It lapsed.

## Fixing the misuse is usually the right branch, and it is the one skipped

An incident proves that something went wrong.
It does not, on its own, say which part.
The two candidates are almost always the decision itself and the way the decision was being carried out, and the second is both more likely and less appealing, since it means the incident was your fault rather than the policy's.

So separate them before concluding anything:

- **What exactly failed?** Name the mechanism, not the outcome.
- **Would the decision, correctly applied, have produced this?** When the answer is no, you have found a misuse, and abandoning the decision fixes nothing while removing whatever the decision was buying.
- **What did the decision buy, and is that still wanted?** If it is, the reversal needs to say what replaces it.

A reversal that cannot answer the third question is not a reversal.
It is a gap with a story attached.

## The worked example

We had decided that subagent worktrees are **assigned by the orchestrator** -- `isolation` set on the `Agent` call -- rather than left to each agent to organize for itself.

Then `isolation: "worktree"` reclaimed an agent's worktree mid-run and nearly lost two commits.
After that the parameter silently stopped being passed.
No decision was made to stop.
It surfaced only when the maintainer asked "I thought we decided assigned is better than self-organized?"

Measured with the parameter no longer passed, on 2026-07-30: 8 concurrent agents, 7 of which created their own worktrees and 1 of which did not.
That one took the main shared checkout, switched its branch away from a PR branch being actively pushed to, and left uncommitted work there.
Nothing failed.
The only signal was `git worktree list`, which also showed 34 worktrees scattered across `/tmp`, a scratchpad, and `~/Projects`.

The collision then did real damage.
A commit belonging to one PR landed on another PR's branch, so the second PR's diff carried a byte-identical copy of the first's entire change.
Had it merged first, the original PR would have gone empty.
Separating them took a history rewrite and a force-push.

**And the reason for stopping does not survive being stated**, which is the whole point of making it state itself.
The worktree looked unchanged to the auto-clean because that agent was committing into *other* worktrees, not its own.
The auto-clean measured correctly.
The agent was in the wrong place.
So the incident was a misuse, and the remedy is to brief agents to stay inside their assigned worktree, not to stop assigning worktrees.

Belt and braces, since a brief is not a guarantee: agents should **push early**.
A pushed commit survives anything that happens to a working tree, and in that same incident the two commits survived precisely because they had been pushed.

## Is this automatable?

Partly, and the honest split matters more than the ambition.

**A general registry of standing decisions, checked by something, is not feasible as usually imagined**, for a reason that is circular rather than technical.
A standing decision has no canonical artifact: it is established in conversation, and nothing writes it anywhere.
Building the registry therefore requires recording each decision at the moment it is made, which is precisely the discipline whose absence causes the problem.
A corpus that reliably recorded its decisions would already notice when it stopped following them, and would not need the registry.

**A decision with a mechanizable surface is fully automatable**, and that is the branch worth taking.
The worked example above is decidable from a single field of a single tool call, so it is a hook rather than a rule to remember, per [`algorithmatize-checks`](algorithmatize-checks.md) and the stronger form in [`deterministic-tools`](../principles/deterministic-tools.md) -- an algorithm can be read before it runs and re-run to the same answer, which is why it beats a rule even when the model would usually follow the rule.
`hooks/hooks.json` is already a de facto registry of exactly this subset: each entry's `why` field names the decision it mechanizes.

So the operative move is a timing change, not a new system.
**When you make a standing decision, ask in the same breath whether it has a mechanizable surface, and build the check then** -- not after the lapse.
The asymmetry is large: the hook is an hour, and discovering the lapse cost a history rewrite.

**Retrospective detection is also feasible, and cheaper than it sounds.** A lapse in a decision about tool use is visible in the transcripts, which record every tool call with its arguments.
Counting is enough: 121 real `Agent` launches on this machine, 60 of them write-capable with no `isolation`, is a number a periodic audit can produce without any judgment at all.
That is a real follow-up rather than a hypothetical one, because the count above was produced that way.

What stays genuinely manual is a decision with no mechanizable surface -- about how to argue, what to prioritize, when to escalate.
For those the prose rule is the whole mechanism, and saying so plainly is better than pretending a checker is coming.

## Do and don't

- **Do:** when an incident makes a decided practice look wrong, name what actually failed and check whether the decision, correctly applied, would have produced it.
- **Do:** write the reversal down as a reversal, saying what replaces what the decision was buying, so a later reader can disagree with it.
- **Do:** ask whether a new standing decision has a mechanizable surface at the moment it is made, and build the check then.
- **Don't:** stop doing the thing and carry on.
  This is the near-miss the rule exists for, and it is not refusal or disagreement -- it is silence, and it reads from the inside as having learned from an incident.
- **Don't:** treat an incident as evidence against the decision when it is evidence of a misuse.
  Abandoning the decision fixes nothing and removes whatever it was buying.
- **Don't:** rely on someone remembering.
  Recollection is the only detector this failure has, and it does not survive a session boundary.

## Relationship to other rules

The nearest neighbour is
[`flag-practice-slippage`](flag-practice-slippage.md), which merged as
ai-config#959 on 2026-07-31.
It is a different rule.
It covers drift by **neglect** -- a sweep skipped, a check run against a stale checkout -- and its remedy is to say so, in a form the user can act on.
This fragment covers drift caused by an **incident that supplied an apparent reason**, which that rule will not fire on, because from the inside it does not present as neglect at all.
Read them together: that one asks you to notice, this one says what the correct response is, and specifically that "stop doing it" is not among the options unless it has been argued.

[`report-mistakes-proactively`](report-mistakes-proactively.md) governs a mistake you notice in an artifact and files an issue about.
The failure here has no artifact to notice, which is why it needs its own entry rather than a bullet there.
