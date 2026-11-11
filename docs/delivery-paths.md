# Delivery paths: how ai-config reaches each harness

This page names the one supported way the rules, skills and hooks reach each harness and session kind
([ai-config#5309](https://github.com/Morrison-Lab/ai-config/issues/5309), step 1).
Anything else that delivers the same files is a leftover, listed under [Leftover paths](#leftover-paths) below.
A leftover is worse than nothing: it runs older code than `main`, and nothing in a guard's output says which copy fired
([#3094](https://github.com/Morrison-Lab/ai-config/issues/3094), [#3590](https://github.com/Morrison-Lab/ai-config/issues/3590)).

Status as of 2026-11-11.

## The supported path for each session kind

| Session kind | Supported path | Rules | Skills | Hooks | Freshness check |
| --- | --- | --- | --- | --- | --- |
| Claude Code on a machine: CLI, desktop app, IDE extension | The `ai-config@Morrison-Lab` plugin at user scope, enabled by [`scripts/wire-user-config.py`](../scripts/wire-user-config.py), which [`bootstrap.sh`](../bootstrap.sh) runs | [`hooks/inject-core-rules.py`](../hooks/inject-core-rules.py) at `SessionStart` | the plugin | the plugin's [`hooks/hooks.json`](../hooks/hooks.json) | [`hooks/warn-stale-plugin-pin.py`](../hooks/warn-stale-plugin-pin.py) at `SessionStart`, against the local marketplace clone; [`scripts/check-hook-delivery.py`](../scripts/check-hook-delivery.py) on demand |
| Claude Code over Remote Control | The same as the row above, since the session runs on that machine | as above | as above | as above | as above |
| Claude Code in the cloud: claude.ai/code sessions and project threads | The environment Setup script, pasted from [`references/cloud-setup/cloud-setup.sh`](../references/cloud-setup/cloud-setup.sh), installs or updates the plugin at user scope when the container is built | `inject-core-rules.py` | the plugin | the plugin | [`hooks/refresh-stale-plugin-pin-cloud.py`](../hooks/refresh-stale-plugin-pin-cloud.py) updates the marketplace and the pin at each `SessionStart` |
| Claude Code in CI: the `@claude` bot and the review workflow, through `Morrison-Lab/gha` | gha's `claude.yml` and `claude-code-review.yml` install the plugin from the marketplace when `use-ai-config` is true, its default at `@v2` | `inject-core-rules.py` | the plugin | the plugin | none needed: each run installs `main` |
| The `@claude` bot on ai-config itself | The checkout: `use-ai-config: false` in [`claude-bot.yml`](../.github/workflows/claude-bot.yml), because the plugin would load the same files twice (ai-config's review workflow keeps the default and installs the plugin) | `CLAUDE.md`, read from the checkout | the committed `.claude/skills` symlink, restored from `main` by `claude-code-action` | none from the catalog | none needed: the checkout is the PR's base |
| Codex CLI | The Codex plugin, [`.codex-plugin/plugin.json`](../.codex-plugin/plugin.json) | `~/.codex/AGENTS.md`, written by `wire-user-config.py` | the plugin, through the wrappers in [`codex-skills/`](../codex-skills/) | [`plugins/ai-config/codex-hooks.json`](../plugins/ai-config/codex-hooks.json), after each new or changed hook is trusted in Codex's hook browser | none |
| Gemini CLI and Antigravity | `bootstrap.sh`, which stages `~/.gemini/config/plugins/ai-config` and registers it in `~/.gemini/config/plugins.json` and `skills.json` | `~/.gemini/GEMINI.md`, written by `wire-user-config.py` | the staged plugin | the staged plugin | none: rerun `bootstrap.sh` |
| Cursor | The Cursor plugin, [`.cursor-plugin/plugin.json`](../.cursor-plugin/plugin.json), installed from GitHub | `cursor-rules/`, shipped as the plugin's user-global rules | the plugin | only in an ai-config workspace, through [`.cursor/hooks.json`](../.cursor/hooks.json) | none |
| opencode | `wire-user-config.py`, which adds ai-config to opencode's `instructions` | the `instructions` entries | no supported path | no supported path | none |
| Cloud agents of other repositories: Codex cloud, Copilot, Jules, Cursor background agents | [`scripts/wire-repo-config.py`](../scripts/wire-repo-config.py), which writes a pointer block into the repository's `AGENTS.md` | a pointer to ai-config's `AGENTS.md` | none | none | none |

The README sections for each harness carry the setup steps;
this table only says which path is the supported one.

## What each path cannot deliver

- **No Claude Code plugin delivers instruction files.**
  A plugin has no slot for `AGENTS.md` or `CLAUDE.md`, which is why `inject-core-rules.py` names them at session start
  ([#4206](https://github.com/Morrison-Lab/ai-config/issues/4206)).
- **A plugin update reaches the next session, not the running one.**
  Claude Code runs a plugin's hooks from the pinned cache snapshot it started with,
  so a refreshed pin takes effect only after a restart.
- **The local freshness check does not fetch.**
  `warn-stale-plugin-pin.py` compares the pin with the local marketplace clone,
  and that clone can itself be weeks behind `origin/main`
  ([#3149](https://github.com/Morrison-Lab/ai-config/issues/3149), [#3437](https://github.com/Morrison-Lab/ai-config/issues/3437)).
  A check against `origin/main` is step 2 of #5309
  ([#3589](https://github.com/Morrison-Lab/ai-config/issues/3589), [#1815](https://github.com/Morrison-Lab/ai-config/issues/1815)).
- **A repository's own `SessionStart` hook does not run in a multi-repository cloud session**
  ([#5280](https://github.com/Morrison-Lab/ai-config/issues/5280)),
  so a per-repository install hook is not a supported cloud path.
  The Setup script is, because it runs for every session of the environment.
- **Skills uploaded to claude.ai do not reach Claude Code**,
  and the claude.ai marketplace sync has failed since 2026-09-02
  ([#3948](https://github.com/Morrison-Lab/ai-config/issues/3948)).
- **Codex, Gemini, Antigravity, Cursor and opencode have no freshness check.**
- **opencode has no supported path for skills or hooks.**
  The README's manual copy and the oh-my-openagent bridge are workarounds, not supported paths.
- **`shared/`, `hooks/` and `memories/` have no placement under `~/.claude`**
  since the symlink install was removed ([#2352](https://github.com/Morrison-Lab/ai-config/issues/2352)).
  A plugin session reads them from the plugin's own directory.

## Leftover paths

Each of these delivered ai-config before the plugin did, and still runs where it was installed.
Step 3 of #5309 retires them, with a script that reports before it deletes.

| Leftover | What it does now | Tracking |
| --- | --- | --- |
| Copies of hook scripts in `~/.claude/hooks`, registered by path in `~/.claude/settings.json` (from `scripts/install-hooks.py --fix` or the old symlink install) | Fires a second, usually older, copy of each registered guard beside the plugin's | [#3094](https://github.com/Morrison-Lab/ai-config/issues/3094), [#3589](https://github.com/Morrison-Lab/ai-config/issues/3589) |
| More than one enabled `ai-config@*` plugin entry, such as project-scope installs in old worktrees | Can run a pin older than the user-scope one | [#3590](https://github.com/Morrison-Lab/ai-config/issues/3590) |
| A `~/.claude/skills` copy or symlink from a pre-plugin install | Lists every skill twice | [`keep-checkouts-fresh`](../shared/workflow/keep-checkouts-fresh.md), step 2 |
| `~/.claude/shared` or `~/.claude/memories` copies | Serve old text to anything that reads those paths | [#2352](https://github.com/Morrison-Lab/ai-config/issues/2352) |
| A `.ai-config` submodule in a consumer repository | Pins that repository to an old commit | [#2345](https://github.com/Morrison-Lab/ai-config/issues/2345) |

`scripts/install-hooks.py --fix` remains the supported path only on a machine with no plugin enabled,
and `wire-user-config.py` refuses to enable the plugin on a machine where it has run,
since the two together fire every hook twice.
