# back — end the away grant

The explicit counterpart to [`away`](../../skills/away/SKILL.llms.md): revoke that session-scoped grant right now and hand the user a scannable record of what happened while it was active, instead of leaving them to reconstruct it from the transcript.

`away` itself already says the grant is “revocable immediately” on any “stop”/“ask me from now on” — `back` is the **named** form of that revocation, worth its own trigger so it’s easy to invoke without recalling the exact wording `away` documents.

## When this fires

- “back”, “I’m back”, “I’m back now”
- “stop away mode”, “end away mode”, “cancel away”, “turn off away”
- “ask me again”, “you can ask me questions again”

## Procedure

1.  **Check whether `away` is actually active this session.** If it was never granted (or was already revoked), say so in one line and stop — nothing to cancel, no decision log to show.
2.  **Revoke the grant immediately.** From this point on, a judgment call that `away` would have resolved unattended goes back to being a normal blocking question (or an `AskUserQuestion` prompt), exactly as if `away` had never been invoked.
3.  **Surface the decision log `away`’s procedure asked you to keep** — every judgment call resolved on the user’s behalf (what the question was, what you decided, why, whether a stronger model was consulted) and every candidate skipped or deferred as too ambiguous to guess at. This is the whole point of `back`: hand back a reviewable list, not just a “done, trust me.” If the log is empty (no judgment calls actually came up while `away` was active), say that plainly instead of padding the report.
4.  **Point out anything still open.** A skipped/deferred item from the log is now fair game to resolve normally — ask about it, or use `prompt-me`/`prompt-me-all` if there are enough of them that a single inline recap would be unwieldy.
5.  **Leave `mwc` (or any other separately-granted permission) untouched.** `back` only cancels `away`’s question-suppression grant. If the user also wants to revoke merge authority or another standing permission granted separately this session, that needs its own explicit phrase (`mwc`’s own “stop merging on your own”) — don’t silently bundle it in.

## Relationship to other skills

- **`away`** — the grant this cancels. Read that skill’s Scope and limits and Procedure sections for exactly what was suppressed and what log format to expect; `back` doesn’t duplicate that content here.
- **`prompt-me` / `prompt-me-all`** — the right tool once `back` has surfaced a skipped/deferred list longer than fits in a quick recap; `back`’s own job is producing that list, not re-implementing the sweep-and-restate mechanics those skills already own.
- **`mwc`** — a separate, narrower session-scoped grant (merge authority only) with its own revocation phrase; `back` deliberately doesn’t touch it, per Procedure step 5.

## Anti-patterns

- ❌ Treating `back` as a no-op status check — it must actually revoke the grant, not just report on it.
- ❌ Reporting “done, all clear” with no decision log when `away` was active and judgment calls did come up — the log is the deliverable.
- ❌ Silently also revoking `mwc` or another unrelated grant because it happened to be active alongside `away`.
- ❌ Fabricating log entries when nothing was actually decided unattended — an honest “nothing came up” beats padding the report.

Back to top
