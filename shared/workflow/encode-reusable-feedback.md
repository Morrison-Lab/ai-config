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
- **Don't:** file a general lesson in one project's memory (a Claude Project's memory, a repo's notes) because that is where it came up;
  every lesson defaults to the most general home that fits (owner directive, 2026-10-02).
- **Don't:** keep any memory in a project memory store (a Claude Project's shared memory directory and its `MEMORY.md`) or in session-local auto-memory.
  Every memory lives in a version-controlled file.
  A store outside version control cannot be reviewed, is invisible to other tools, and silently loses concurrent writes.
  See [`project-memory-store`](../../memories/project-memory-store.md) (owner directive, 2026-10-16).
- **Do:** put each memory where it fits best, usually in one home:
  the project's primary repository for a fact or decision true of that project alone
  (a dev-facing file such as `.claude/project-memory.md`, kept out of any rendered site),
  `ai-config` for a global rule or lesson,
  and a repository's own `CLAUDE.md` or instructions for a repo-specific rule.
  Use several homes only when the memory applies in each.
- **Do:** leave a project memory store, where one still exists, holding no more than pointers to those files.
- **Don't:** write anything sensitive into a repository that is or may become public: student information, private third-party materials, permission requests.
- **Don't:** offer to upstream it, or ask which repo --- decide and do it, surfacing the choice only when it is genuinely ambiguous or architecturally significant.
