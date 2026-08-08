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
| [`github.md`](github.md) | GitHub & GitLab CLIs and APIs | The `gh` CLI, `glab` and the GitLab Discussions API, GitHub access from bash in remote sessions, and PR / issue queue management (the GII startup sweep, stacked-PR pitfalls). |
| [`github-mcp-tools.md`](github-mcp-tools.md) | GitHub MCP tools (Claude Code remote/web sessions) | The GitHub MCP tool surface used when `gh` is unavailable: tool selection, scope and owner-string quirks, review/comment/thread mechanics, and per-tool failure modes. Split out of `github.md` (ai-config#694 pattern) pre-emptively at 1199 lines, just under the 1200-line gate. |
| [`github-actions.md`](github-actions.md) | GitHub Actions authoring & the `Morrison-Lab/gha` reusable workflows | Workflow authoring gotchas, YAML quoting for Actions, the `Morrison-Lab/gha` reusable workflows and their tag-sliding rules, gha's changelog conventions, and what a repo/org rename does to `uses:` refs. |
| [`github-actions-outages.md`](github-actions-outages.md) | GitHub Actions platform outages, and their lookalikes | Detecting a live incident (absent rather than failing checks, the `githubstatus.com` JSON endpoints, the plural-versus-single tell), ruling one out when a shared-config change fails every repo at once instead (and building that timeline from merges rather than commit dates), and cleaning up after one (a swallowed push versus jobs cancelled mid-flight, and why zero recorded steps is the discriminator). Split out of `github-actions.md` (ai-config#694 pattern) at the 1200-line gate. |
| [`claude-bot-workflows.md`](claude-bot-workflows.md) | The `@claude` bot workflows | The bot's own behaviour: what a run does, how it fails, how to recover. The `@claude` CI action, re-triggering the PR review, the self-modification skip guard, `claude-code-action`'s tag vs. agent modes, and gathering prior review context. |
| [`git.md`](git.md) | Git | Git itself: tags, submodule pins, stash, merge behavior, branch create / reset, ref-pattern vs pathspec matching, diff-range selection, Windows / Git Bash quirks, and the remote-session push proxy. |
| [`git-worktrees.md`](git-worktrees.md) | Git worktrees | Worktree-specific behavior: `worktree add`/`remove` gotchas, submodules inside a worktree, `checkout -B` bypassing the already-checked-out guard, pushing by refspec when a branch is checked out elsewhere, two worktrees sharing one branch ref, and the harness's own subagent worktree, which `isolation: "worktree"` places in the session's primary repo rather than in a repo the brief names. Split out of `git.md` (ai-config#694 pattern) at the 1200-line gate. |
| [`r-quarto.md`](r-quarto.md) | R, Quarto & the R toolchain | `renv` (lockfiles, per-worktree libraries), the linters (`lintr`, `air`, `jarl`), R-package PR CI gates, Quarto HTML site build / layout gotchas, and `WORDLIST` collation. |
| [`r-cloud-sessions.md`](r-cloud-sessions.md) | R & Quarto in Claude Code cloud / web sessions | Running R and Quarto inside a remote container: toolchain installation, missing binaries, sandbox constraints, and verifying what a PR preview actually built (split out of `r-quarto.md`). |
| [`claude-code.md`](claude-code.md) | Claude Code harness & agent tooling | The harness itself: `AskUserQuestion`, the Bash tool (zsh, cwd persistence), `WebFetch`, the schedulers (`ScheduleWakeup` / `CronCreate`) and `Monitor`, custom subagents, `Workflow` `agent()`, `codex`, skill command blocks, and this repo's own memory-file structure. |
| [`claude-code-hooks.md`](claude-code-hooks.md) | Claude Code hooks: manifest, registration, and install failures | How hooks reach a machine and how that goes wrong: the native `hooks/hooks.json` schema versus the flat `install-hooks.py` view, the bind-versus-place split across `install-hooks.py` and `check-install.py`/`bootstrap.sh`, double registration when the plugin is also enabled, and the two routes to a registered-but-absent hook that takes the whole `Bash` tool down. |
| [`tools.md`](tools.md) | Local tools & CLIs | The cross-cutting remainder that fits none of the topical files above: Julia in cloud sessions, `markdownlint`, editing committed Office Open XML files, personal machine setup, and a few standing writing / review habits. |
| [`debugging.md`](debugging.md) | Debugging notes | Debugging practices: real-browser CSS/JS testing (not DOM stubs), VS Code editor-vs-disk desync, ARDI review-polling, portable bash scripting (sed, EOF, robustness), R test/lint CI-only gotchas and snapshot regeneration, and recovery from merge-clobbered or force-pushed PR branches. |
