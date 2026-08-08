# Setup

## Local setup

**Requirements:** git, [Claude Code CLI](https://claude.ai/code), and/or Codex.

``` sh
git clone https://github.com/d-morrison/ai-config.git ~/ai-config
bash ~/ai-config/bootstrap.sh
```

`bootstrap.sh` symlinks Claude assets into `~/.claude/` and generated Codex wrappers into `${CODEX_HOME:-$HOME/.codex}/skills`. Run it again any time you add a new top-level dir to the repo.

### Verify the install

``` sh
ls -l ~/.claude/skills ~/.claude/commands ~/.codex/skills
scripts/inventory.sh                         # live counts of skills/wrappers/commands/docs
```

In a Claude Code session, type `/` and confirm skills appear (e.g. `/ardi`, `/scout-peers`).

In Codex, the wrappers appear as skills from `${CODEX_HOME:-$HOME/.codex}/skills`. Each wrapper reads the matching canonical workflow from `skills/<name>/SKILL.md` and adapts Claude-specific metadata/tools to Codex.

## Web (cloud) sessions — this repo

In cloud sessions (claude.ai or remote environments), `bootstrap.sh` can’t run at startup because the repo isn’t on disk yet. The committed `SessionStart` hook (`.claude/settings.json` → `.claude/hooks/session-start.sh`) runs `bootstrap.sh` once the repo is checked out, symlinking `skills/` and `commands/` into `~/.claude/`. The hook is a no-op outside remote sessions (`CLAUDE_CODE_REMOTE`) and is idempotent.

The hook also installs **Julia** (via `juliaup`) on first start, if allowed by the environment’s network policy. See [`docs/julia-setup.md`](https://github.com/d-morrison/ai-config/blob/main/docs/julia-setup.md).

## Plugin marketplace — other repos

To load these skills when a **different** repo is open in a cloud session, add this to that repo’s `.claude/settings.json`:

``` json
{
  "extraKnownMarketplaces": {
    "d-morrison": {
      "source": { "source": "github", "repo": "d-morrison/ai-config" }
    }
  },
  "enabledPlugins": {
    "ai-config@d-morrison": true
  }
}
```

Claude Code installs the plugin at session start. Skills are namespaced: `/ai-config:ardi`, `/ai-config:reprexes`, etc.

Or try it interactively in any Claude Code session:

``` text
/plugin marketplace add d-morrison/ai-config
/plugin install ai-config@d-morrison
```

## `@claude` bot on PRs

The bot that runs `claude-code-action` on this repo’s PRs reads skills from `.claude/skills/`. The `.claude/skills → ../skills` symlink is committed to `main`, so `restoreConfigFromBase` always restores it — even on PR branches. Comment `@claude ardi` (or any skill name) on a PR and the bot can run it.

## Deconflicting parallel local sessions

When several AI sessions share one local checkout, they can clobber each other. The `session-lock` skill (alias `deconflict-sessions`) keeps a machine-local registry of active sessions under `.git/ai-sessions/`. Sessions can refuse to share a working tree and isolate into a `git worktree`. See [`docs/local-session-deconfliction.md`](https://github.com/d-morrison/ai-config/blob/main/docs/local-session-deconfliction.md).

Back to top
