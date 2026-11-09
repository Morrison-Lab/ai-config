Before a reply says "I can't", "I'm unable to" or "only you can", check the tools you have, deferred ones included.

Ezra, 2026-11-09 (Data 571 runner thread): a runner told him "I can't, only you control that" about switching its own permission mode.
It had a mode-switch tool and used it once he insisted.
The coordinator repeated the same claim.
Ezra: "never forget to check your available tools" and "make sure we don't get that behavior from a runner again".

Do this before any such claim:

- Read your visible tool list for a tool that does the action.
- Call `ToolSearch` with the action's keywords (for example `permission mode`, `add repo`, `remote control`), because a deferred tool appears only by name until it is searched for.
- If a tool fits, use it.
  Example: `mcp__ccd_session_mgmt__set_session_permission_mode` switches the permission mode.
  A stricter mode needs no approval card, and a looser one shows Ezra a card.
- If none does, say what you searched, so the claim is checkable.

Never tell a user, or relay to a thread, that someone did something unless that person said so.
The coordinator misrelayed that Ezra had switched the mode himself.
Quote the message or say you do not know.

The real limits stay:

- Never edit permission rules in settings files on your own.
  Change them only through a prompt Ezra approves.
- Switching to a stricter permission mode when asked is fine.

Why the check does not read the reply's wording: whether a reply claims an inability to act cannot be decided by a lexical rule.
A Stop hook that matched "can't" plus an action verb and a capability noun was tried and withdrawn after six review rounds, each finding a new idiom or literal sense it matched.
`hooks/flag-reply-without-tool-search.py` ([ai-config#5140](https://github.com/Morrison-Lab/ai-config/issues/5140)) decides from structure instead: it warns once per message when a turn replied and made no other tool call and no `ToolSearch`.
A plain answer to a question has the same shape, so it also gets one notice.
See also [no-cant-from-session-excuses.md](no-cant-from-session-excuses.md).
