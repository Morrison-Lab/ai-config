# MEMORY.md --- index of `memories/`

Index of the cross-project memory files in this directory. When you add a
*new* memory file, register it here so the corpus stays discoverable --- the
`memorize` skill writes the file, then adds a row to the table below.
(Appending a bullet to an existing file needs no change here.)

This index covers only the general, cross-project memories kept in the
ai-config repo. Repo-specific memories live outside the repo, under
`~/.claude/projects/<project-path>/memory/`, each with its own `MEMORY.md`
index in that directory.

| File | Title | Covers |
|------|-------|--------|
| [`preferences.md`](preferences.md) | User preferences (cross-workspace) | Standing working rules: never-assume/always-verify, record learnings as you go, cite sources for tool-behavior claims, issue-first, and the ARDI / fully-clean definitions. |
| [`github.md`](github.md) | GitHub & GitLab CLIs and APIs | The `gh` CLI, the GitHub MCP tools (remote / web sessions), `glab` and the GitLab Discussions API, GitHub access from bash in remote sessions, and PR / issue queue management (the GII startup sweep, stacked-PR pitfalls). |
| [`github-actions.md`](github-actions.md) | GitHub Actions authoring & the `Morrison-Lab/gha` reusable workflows | Workflow authoring gotchas, YAML quoting for Actions, the `Morrison-Lab/gha` reusable workflows and their tag-sliding rules, gha's changelog conventions, and what a repo/org rename does to `uses:` refs. |
| [`claude-bot-workflows.md`](claude-bot-workflows.md) | The `@claude` bot workflows | The bot's own behaviour: what a run does, how it fails, how to recover. The `@claude` CI action, re-triggering the PR review, the self-modification skip guard, `claude-code-action`'s tag vs. agent modes, and gathering prior review context. |
| [`git.md`](git.md) | Git | Git itself: tags, submodule pins, worktrees, stash, merge behavior, branch create / reset, Windows / Git Bash quirks, and the remote-session push proxy. |
| [`r-quarto.md`](r-quarto.md) | R, Quarto & the R toolchain | R and Quarto in cloud sessions, `renv` (lockfiles, per-worktree libraries), the linters (`lintr`, `air`, `jarl`), R-package PR CI gates, Quarto HTML site build / layout gotchas, and `WORDLIST` collation. |
| [`claude-code.md`](claude-code.md) | Claude Code harness & agent tooling | The harness itself: `AskUserQuestion`, the Bash tool (zsh, cwd persistence), `WebFetch`, the schedulers (`ScheduleWakeup` / `CronCreate`) and `Monitor`, custom subagents, `Workflow` `agent()`, `codex`, skill command blocks, and this repo's own memory-file structure. |
| [`tools.md`](tools.md) | Local tools & CLIs | The cross-cutting remainder that fits none of the topical files above: Julia in cloud sessions, `markdownlint`, editing committed Office Open XML files, personal machine setup, and a few standing writing / review habits. |
| [`debugging.md`](debugging.md) | Debugging notes | Debugging practices: real-browser CSS/JS testing (not DOM stubs), VS Code editor-vs-disk desync, ARDI review-polling, portable bash scripting (sed, EOF, robustness), R test/lint CI-only gotchas and snapshot regeneration, and recovery from merge-clobbered or force-pushed PR branches. |
