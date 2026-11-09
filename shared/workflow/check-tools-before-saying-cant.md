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

Why a hook backs this: `hooks/flag-cant-without-tool-check.py` warns once per message when the final reply claims an inability or says only the user can, and the turn made no `ToolSearch` call.
It warns and does not deny, because whether a tool exists is not decidable from a transcript, and some limits are real.
The "someone did X" half cannot be checked lexically, so it is prose only.
See also [no-cant-from-session-excuses.md](no-cant-from-session-excuses.md).
