# A whether-or-how question gets a recommendation and a start-or-file ask

When the user asks whether to do something, or how to do it, answer with a recommendation and stop before implementing.
End the answer with one question: start now, or file an issue for later, with your recommendation between the two.
Start implementing at once only when the user gives a declarative instruction.

## What counts as a question

Read "etc." in the directive as the whole category of asking for advice, not only its two named forms:

- whether: "should we ...?", "is it worth ...?", "would it make sense to ...?";
- how: "how should we ...?", "what's the best way to ...?";
- the rest of the category: "can we ...?", "what do you think about ...?", "any ideas for ...?", "what if we ...?".

A declarative instruction names the work to do: "add X", "fix Y", "cai: make Z a rule".
A question mark on a request that is plainly an order ("can you push that?") is still an instruction.
When one message holds both, the instruction starts now and the question waits.

## What may run before the answer

Research that forms the recommendation runs at once:
reading files, searching the tracker and memory, and running read-only commands.
Implementation waits for the answer:
edits, commits, pushes, PRs, issues, Canvas or forge writes, and spawning workers to build.
Filing the issue is itself one of the two options, so it waits too.

## How this fits the action-by-default rules

AGENTS.md "Default to action without asking" and [`read-instructions-fully`](read-instructions-fully.md) say not to ask permission for what a request implies.
A whether-or-how question is not yet a request, so it implies no implementation;
asking start-or-file is the answer it calls for, not a cop-out offer.
AGENTS.md "Always give recommendations with questions" still applies: the start-or-file question carries its own recommendation.

`hooks/remind-start-or-file-on-question.py` reminds, never blocks, when a prompt reads as a question.
No deny can work: question versus instruction is a reading of intent.
The [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md#work-started-on-a-question) checklist looks for the same defect in review.

- **Do:** answer "should we X?" with a recommendation and its reason,
  then "start now or file it for later?" with a recommendation between those two.
- **Do:** act at once on a declarative reply: "yes, do it" starts the work, and "file it" files the issue and stops.
- **Don't:** open a PR in answer to "how should we handle X?".
- **Don't:** ask start-or-file after a declarative instruction.

(User directive, 2026-11-10, ai-config#5287:
"when I ask you whether we should do something or how we should do something, etc, come up with a recommendation, but before implementing, ask me if you should start now or file it for later (with your recommendation). only start immediately if I give you a declarative instruction.")
