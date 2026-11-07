---
name: advisor
description: "Read-only second opinion from a different model family."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
---

# advisor --- one bounded consult from an independent model

An advisor consult sends one decision point to a model from a different family and brings back an opinion.
The advisor reads and answers.
It does not edit files, implement, or take over the task.
Claude stays the orchestrator and decides what to do with the answer.

The pattern comes from the `advisor` skill in `scdenney/open-science-skills`.
It is CC BY-NC 4.0, so this skill takes the pattern only and copies nothing.

## When this fires

- "advisor", "ask an advisor", "get a second opinion on this decision".
- Before an approach crystallizes, when a wrong choice would be costly to undo.
- Before declaring done, when the claim being made is one you cannot check against a primary source.

Do not use it for a diff review.
Use [`adv`](../adv/SKILL.md) for that.
Do not use it for fan-out reading or drafting.
Use [`delegate-to-opencode`](../delegate-to-opencode/SKILL.md) or [`delegate-to-agy`](../delegate-to-agy/SKILL.md) for that.

## Parameters

Each value below is a parameter with today's default, so a caller can change it without editing this file
([`configurable-parameters`](../../shared/coding/configurable-parameters.md)).

| Parameter | Default | Meaning |
|---|---|---|
| `engine` | `opencode` | The CLI or endpoint that reaches the advisor. `agy` is the other seat. Codex is never a seat, because the lab allows it only in UCDH projects (`bcs`, `hac`) and this skill is for the rest. |
| `model` | the strongest model `engine` offers outside the caller's family | Look it up at call time; do not hard-code a model name in a brief. |
| `effort` | the highest the engine offers | Pinned, not inherited: a cheap consult on a hard question wastes the reason for asking. |
| `briefing_path` | a file in the scratchpad directory | Where the briefing is written before the call. |

## Procedure

### 1. Make the deliverable durable first

A consult takes real time, and a session can end during it.
Write down the work product (commit it, or save the draft) before the call, so the answer has something to attach to.

### 2. Write a self-contained briefing

Nothing carries over from this session except the working directory.
The briefing file states:

- the task and why it matters;
- what has been done so far;
- the current approach, or the exact claim to be checked;
- the precise question, with file paths and line numbers.

"Does this look right?" is not a question.
"Does `shared/workflow/x.md` line 40 contradict the rule at line 12?" is one.
Do not send restricted data (FERPA records, PHI): the briefing leaves the machine.

### 3. Call the advisor read-only

Run the advisor in the engine's read-only or plan mode, with no session persistence where the engine supports it.
Pass `model` and `effort` explicitly.
Engine invocation details are in the delegate skills' memories (`memories/delegation.md`, `memories/antigravity.md`).

### 4. Never fall back to the caller's family

If the chosen model is unavailable, report that and stop, or pick another engine outside the caller's family.
A same-family substitute is not independent, so it defeats the point of asking.
A different model in the caller's own family is a weaker and cheaper option: name it as weaker in the result, and do not call it equivalent.

### 5. Treat the answer as evidence

The advisor's answer is a lead, not a verdict.
A primary source or an observed failure outranks it.
Check each claim against the file or command output before acting on it, and label anything unchecked as an unverified lead (see [`adv`](../adv/SKILL.md#verify-cross-model-findings-before-presenting-them)).
When the advisor and the evidence conflict, state the conflict plainly in one more consult.
Do not settle it by coin flip.

## Not covered yet

[ai-config#884](https://github.com/Morrison-Lab/ai-config/issues/884) tracks the later slices:
a script that enforces steps 3 and 4 mechanically, and whether `context: fork` can replace a separate process (it isolates conversation history but stays on an agent type in this session, so it is not a cross-family consult).
