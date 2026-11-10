# Never assume anything that could be checked empirically

Ezra, 2026-11-09: "cai: never assume anything that could be checked empirically" (ai-config#5215).

Context: the coordinator assumed lds required branches to be up to date without reading the ruleset.
That led to main merges nobody needed, and the merges grew the lds backlog.

Before you state a setting, a state or a capability, or act on one, read it live in that turn.
Settings include a ruleset, a branch protection, an Actions variable, a repo's visibility and a runner label.
State includes a PR's head, checks and merge status.
Capabilities include which tools, hosts and permissions this session has.

- **Do:** make the read, then quote what it returned ("the ruleset's `strict_required_status_checks_policy` is false").
- **Do:** when the read is impossible from this session, say "unverified" in the same sentence as the claim.
- **Don't:** state an unread setting as fact, or plan work around it, when one call would settle it.
- **Don't:** treat memory, documentation or an earlier turn as the read.

This extends `memories/preferences.md`'s "NEVER assume; ALWAYS verify" to settings.
[`verify-the-right-artifact`](verify-the-right-artifact.md) says which artifact to read.
`hooks/warn-hedged-checkable-claim.py` warns on hedged wording, but it cannot tell an unhedged unread claim from a read one.
So this rule is prose until a per-setting reader script exists, as in ai-config#5205.
