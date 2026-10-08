# Present decisions one at a time

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#present-decisions-one-at-a-time) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When more than one decision needs my input, go through them one at a time:
pose the single most pressing question, wait for my answer, then pose the next.
Don't batch several decisions into one message or one multi-question `AskUserQuestion` call.

Two reasons.
The answer to the first question often changes or moots the later ones, so a batch makes me answer against stale premises.
And a wall of questions invites a partial reply that leaves the rest silently unanswered --- the exact failure mode `prompt-me` / `prompt-me-all` exist to recover from.

Mechanics:

- Rank by how blocking each decision is, most pressing first (the same ranking `prompt-me` uses), and pose only the top one --- via a single-question `AskUserQuestion` call for a real either/or, or one boxed ❓ **QUESTION** otherwise.
- Say how many more are queued behind it ("2 more decisions after this one"), so the backlog is visible without being posed.
- Fold each answer into the framing of the next question, and silently drop any queued question the answer mooted.
- Keep working on whatever the pending decision doesn't block while waiting.

This changes how decisions are *posed*, not whether to ask at all: `research-before-asking` still gates each question, and an `away` grant still means don't block on questions --- resolve them by judgment, or skip-and-note, per that skill's scope.
And it yields to an explicit request for the full backlog --- `prompt-me-all` / "ask me everything at once" is the user opting into a batch view.

## Say where the user will see it

When work needs the user (a merge word, a decision, an answer to a question), say so where they read first, not only inside the thread that needs it (Ezra, 2026-10-08).
In a project with a coordinator session, a thread session asks the coordinator to post the request in the main project chat, and the coordinator posts it there.
Name the thread, say exactly what is needed, and link the item (PR, issue or question).
A request that sits only in a thread can wait unseen for hours.

- **Do:** post the ask in the main project or channel chat, with a link to the thread.
- **Don't:** leave "waiting on you" only in a thread reply or a status checklist.
