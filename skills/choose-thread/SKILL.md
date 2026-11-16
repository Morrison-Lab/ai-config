---
name: choose-thread
description: "Decide new thread or existing thread, and the model."
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
---

# choose-thread -- new thread or existing thread, and which model

Run this before giving new work to an existing thread, and before starting a thread.
A message cannot change a running thread's model, so continuing in an old thread also fixes its model and its accumulated context ([`require-model-choice.py`](../../hooks/require-model-choice.py) enforces the pause;
Ezra, 2026-11-16).

## Procedure

Answer each criterion from live state (the thread's latest message, its open PRs, its files), not from memory.

1. **Topic ownership.**
   Does an existing thread already own this topic, issue or PR?
   Yes: continue there, because a second thread on the same item collides with the first.
2. **File overlap with in-flight work.**
   Do the files the new work touches overlap a thread's open branch or PR?
   Yes: continue in that thread, or stack on its branch after it finishes.
   No overlap: a new thread can run in parallel.
3. **Context size.**
   Is the existing thread's context large, stale or mostly irrelevant to the new work?
   Yes: start a new thread with a brief that carries only what the work needs.
   No, and the new work needs what that thread already learned: continue.
4. **Model mismatch.**
   Does the new work need a different tier from the thread's model, by [`select-model`](../select-model/SKILL.md)?
   Yes: start a new thread on the right model.
   Examples: a bounded edit sent to an Opus thread, or a large content pass sent to a Sonnet thread.
5. **Decide and record.**
   - New thread: start it with `model` set (or a `Model-fit: <model> -- <why>` line).
   - Existing thread: add `Why-not-new-thread: <the criterion that decided it>` to the message.

Never choose Fable without the user's explicit permission for that launch ([`no-fable-subagents`](../../shared/workflow/no-fable-subagents.md)).

## Example

An owner thread is mid-PR on `lds` chapter X on Opus.
The new request is a typo fix in an unrelated chapter.
Topic differs, no file overlap, and the work is bounded, so start a new Sonnet thread.
The reverse, a follow-up review fix on the same PR, continues in the owner thread with `Why-not-new-thread: same PR and files, context needed`.
