# Case records: use-mcp-servers

Worked-example case records for the rules in
[`use-mcp-servers.md`](use-mcp-servers.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "Prefer the typed tool over the shell, once one exists"

(2026-08-29: establishing context at session start, an agent ran `which gh glab`
bundled into its initial bash call before using `mcp__github__*` for every
subsequent operation.
Because GitHub MCP tools were registered, the rule preferred MCP regardless of
whether `gh` was present on `PATH`.
The probe tested a fact whose outcome could not change the next action,
encoding a CLI-first check that inverted the rule's default.)

## "When a rule names a mechanism this session does not have"

(2026-07-29: an entire session ran `gh pr checks` polling loops because
`subscribe_pr_activity` was absent.
The GitHub MCP server's `notifications` toolset --- carrying
`manage_notification_subscription` and a `list_notifications` call that covers
every subscribed thread across every repo in one request --- was present the
whole time, switched off.
Those are the **server's own** tool names, as returned by a `tools/list` call
against `github-mcp-server` 1.7.0.
A harness that namespaces MCP tools surfaces them prefixed, which is why this
repo's other references spell them `mcp__github__list_notifications`; ask the
server rather than grepping our docs when you need to know what a toolset
actually contains.
The same session had already hit the shadowed-plugin and 400-vs-401 traps
[`use-mcp-servers.md`](use-mcp-servers.md) documents, which is why they are
recorded.)
