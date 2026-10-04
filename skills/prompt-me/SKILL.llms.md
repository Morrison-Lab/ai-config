# prompt-me

Sweep the conversation for questions that were posed to the user but never answered, rank them by how much they’re blocking, and surface the most pressing one — or a requested number of the most pressing ones. Long sessions bury a question asked several turns back under unrelated work; this skill surfaces it again instead of leaving it stranded.

## When this fires

- Explicit invocation: `/prompt-me`, `/pm`, “prompt me”, “pm”.
- With a count: `/prompt-me 3`, `pm 3`, “prompt me the top 2”.
- The user asks a variant like “what are you waiting on me for?”, “what do you need from me?”, “did you ask me something?”, or “remind me what you asked”.
- For **every** open question with no cap, that’s a different skill: `prompt-me-all` / `pma` — see below.

## Step 1 — Find candidate questions

Scan back through the current conversation (not prior sessions) for anything that reads as a question directed at the user:

- A ❓ **QUESTION** marker, or a bolded question set apart in its own paragraph — the format required by the `CLAUDE.md` “Tag chat output by category so long recaps stay scannable” rule, used when a question is posed inline rather than through `AskUserQuestion`. Treat this as the strongest signal; it was deliberately marked as a question.
- Direct questions in your own prior messages (ending in `?`, or phrased as a request for a decision, confirmation, or missing information).
- Any pending `AskUserQuestion` call that was skipped, dismissed, or never resolved.
- Conditional asks embedded in a longer message (“let me know if…”, “should I… or…”, “confirm before I…”).

Exclude:

- Questions the user already answered, even indirectly (a later message that makes the answer clear moots the question — don’t re-ask it).
- Rhetorical questions or ones you answered yourself in the same message.
- Questions from a different task the user explicitly dropped or superseded.

## Step 2 — Rank by how pressing each one is

Order the surviving questions from most to least pressing:

1.  **Blocking** questions first — ones that stop the next step of active work until answered outrank purely informational asks.
2.  Within the same tier, **more recent** beats older — a question asked moments ago is more likely to still be live than one from many turns back.

## Step 3 — Select and present

- **No argument**: surface only the single most pressing question.
- **Numeric argument `N`**: surface the top `N`, most-pressing-first.
- If the count requested exceeds the number of open questions, just present what exists — don’t pad the list or manufacture filler.

For each item, give enough context to answer cold — don’t just repeat the bare question if the surrounding detail (options, why it matters, what’s blocked on it) got lost upstream.

    Still waiting on you for:
    1. <question>, restated with the context that pins it down

(Add more numbered items only when a count `> 1` was requested.)

If nothing is actually pending, say so plainly (“nothing open right now”) rather than manufacturing a question to fill the list.

## Step 4 — Don’t re-decide anything

This skill only restates; it never guesses an answer or picks a default to unblock itself. If a question turns out to be stale (events since have made it moot), say that instead of listing it, but don’t silently drop a question just because answering it looks hard.

Back to top
