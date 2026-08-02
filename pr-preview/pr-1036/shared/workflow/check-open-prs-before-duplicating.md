Before scaffolding a new AI tool — a skill, an agent, or any other
harness-registered file (`skills/<name>/SKILL.md`, `.claude/agents/<name>.md`,
etc.) — check **open PRs**, not just local branches and worktrees, for an
in-progress draft that already covers the concern.

A local branch/worktree scan misses work another session already pushed and
opened a PR for. Check both this repo's and (when the corpus spans repos, as
`d-morrison/ai-config`'s skills do) any sibling repos in scope:

```bash
gh pr list --state open --search "<keywords> in:title,body"
```

In a remote/web session without `gh`, use the GitHub MCP equivalent
(`mcp__github__list_pull_requests` / `mcp__github__search_pull_requests` —
see `tool-mappings.md`).

If an open PR already adds or extends the thing you were about to build,
**don't duplicate it.** Instead:

- If the PR looks stalled or abandoned, offer to pick it up and finish it
  (check it out, continue the work, push to the same branch) rather than
  opening a competing one.
- If it's clearly active (recent commits, an assigned session), redirect the
  caller to that PR — name it, link it, and stop. Don't build a second draft
  of the same tool.

This is the open-PR counterpart to the branch/worktree scan: a branch can be
unpushed and invisible to `gh pr list`, but a PR can also be pushed and
invisible to a branch-only scan if you never fetch it. Do both checks.
