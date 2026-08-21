# prompt-me-all

Sweep the conversation for every question that was posed to the user but never answered, and restate all of them together in one place — the uncapped counterpart to `prompt-me` / `pm`, which surfaces only the single most pressing one (or a requested top N).

## When this fires

- Explicit invocation: `/prompt-me-all`, `/pma`, “prompt me all”, “promptmeall”, “pma”.
- The user wants the full backlog of open questions, not just the most pressing one — e.g. “what are ALL the things you’re waiting on me for?”.

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

## Step 2 — Restate them all as a single list

List every surviving question, most pressing first (blocking questions ahead of purely informational ones, more recent ahead of older within the same tier), but group by topic when several questions share the same task. For each item, give enough context to answer cold — don’t just repeat the bare question if the surrounding detail (options, why it matters, what’s blocked on it) got lost upstream.

    Still waiting on you for:
    1. <question>, restated with the context that pins it down
    2. <question>, ditto

Don’t cap the list — this skill exists specifically to show everything, in contrast to `prompt-me` / `pm`, which caps at one (or a requested N).

If nothing is actually pending, say so plainly (“nothing open right now”) rather than manufacturing a question to fill the list.

## Step 3 — Don’t re-decide anything

This skill only restates; it never guesses an answer or picks a default to unblock itself. If a question turns out to be stale (events since have made it moot), say that instead of listing it, but don’t silently drop a question just because answering it looks hard.

Back to top
