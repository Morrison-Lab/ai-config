# Check a thread's model, and any capability, before claiming it

Two rules from one exchange in a Claude project (Machine Learning course, 2026-11-12).
The coordinator told Ezra that every thread had been moved off Fable,
and one thread, "Plan development for each lab repo", was still on `claude-fable-5-2`.
Corrected, the coordinator then said it could not see each thread's live model.
It could.

## Read every thread's model with `get_session` before saying anything about it

`mcp__claude-code-remote__get_session` on a thread's session (thread `cse_X` is `session_X`) returns three model fields:
`configured_model` (stored at creation),
`session_context.model` (what the session is set to run now, after any switch),
and `external_metadata.last_served_model` (what the latest turn actually ran on, including a turn-scoped fallback).
List the threads with `list_threads` (every page and every state, as the bulk-action rule in [`claude-app-projects`](../../memories/claude-app-projects.md) requires),
call `get_session` on each one,
and report what the calls returned.
A switch you remember making is not evidence of the model a thread runs:
a switch can fail, miss a thread, or be undone by a fallback.

- **Do:** call `get_session` on every thread, then write "all N threads report `session_context.model` claude-opus-5-5".
- **Don't:** write "every thread is off Fable" from the list of switches you sent.

`hooks/no-thread-model-claim-without-get-session.py` denies the first reply in a turn that names a thread or session together with a model when no `get_session` call follows the last user message.
It cannot tell a claim from a mention, so the retry is allowed.

## Check for a capability before saying it is missing

Before writing that you cannot see, reach or do something, look for the tool, field or endpoint that would do it:
the deferred-tool list (ToolSearch), the tool's own description, and one trial call.
"I can't see each thread's live model" was written without reading `get_session`'s description, which lists all three fields.
This is the chat-side case of [`verify-the-right-artifact`](verify-the-right-artifact.md) and of AGENTS.md's "Don't take anyone's word for it";
`hooks/warn-unmeasured-capability-claim.py` covers the same claim in a forge write,
and no hook covers it in chat, because a missing-capability claim has too many phrasings to match
(widening that hook to reply tools is tracked separately).

- **Do:** search the tools, make the call, and report what it returned, or say "I have not checked".
- **Don't:** state that a capability is missing because you do not remember having it.

## Run UMS the moment either mistake is noticed

Both mistakes were admitted in a reply, and no UMS pass ran until Ezra asked why
([`run-ums-proactively`](run-ums-proactively.md), from ai-config#5481, already required it).
The admission went out through `post_message`, and the two admission hooks read only assistant text blocks, so neither fired.
Both now read reply-tool text too, and `hooks/remind-ums-after-error.py` also blocks the turn's end, once, until the pass runs.
