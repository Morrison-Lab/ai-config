# Encoding reusable feedback into ai-config

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#encoding-reusable-feedback-into-ai-config) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When the user gives feedback, corrections, or guidance that applies beyond the current session (a standing rule, style preference, workflow change, or behavioral note), decide on your own how to encode it --- don't ask.
Choose the right form (memory bullet in CLAUDE.md, update to a shared fragment in `shared/`, new or revised skill, etc.) and commit the change.
Only surface the choice if it's ambiguous or touches something architecturally significant.

**Put the memory in the repo where it belongs, and don't wait for confirmation to do it.**
Session-local auto-memory is a scratchpad, not a home.
A learning parked there is invisible to every other session and to everyone else, so a reusable one has to land in a version-controlled repo --- `ai-config` for a cross-cutting rule, the specific repo for a repo-specific gotcha.
And "decide on your own --- don't ask" above rules out the adjacent move too.
*Offering* to upstream a learning is not upstreaming it, and it spends a round trip to hear an answer already written here.
Open the PR.

- **Do:** commit a reusable learning to the repo that owns it, in the same stride you notice it.
- **Do:** pick the home by scope --- an `ai-config` shared fragment, `CLAUDE.md`, or `memories/` for a cross-repo rule;
  the specific repo's own docs for a repo-specific one.
- **Don't:** leave a reusable learning in session-local auto-memory as a substitute for committing it.
- **Don't:** offer to upstream it, or ask which repo --- decide and do it, surfacing the choice only when it is genuinely ambiguous or architecturally significant.
