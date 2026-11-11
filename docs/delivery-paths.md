# Delivery paths: how ai-config reaches each harness

This page names the one supported way the rules, skills and hooks reach each harness and session kind ([ai-config#5309](https://github.com/Morrison-Lab/ai-config/issues/5309), step 1).
Anything else that delivers the same files is a leftover, listed under [Leftover paths](#leftover-paths).
A leftover is worse than nothing: it runs older code than `main`, and nothing in a guard's output says which copy fired ([#3094](https://github.com/Morrison-Lab/ai-config/issues/3094), [#3590](https://github.com/Morrison-Lab/ai-config/issues/3590)).
The README's section for each harness carries the setup steps.

Status as of 2026-11-11.

## The supported path for each session kind

| Session kind | Supported path | Rules | Skills | Hooks | Freshness check |
| --- | --- | --- | --- | --- | --- |
| Claude Code on a machine: CLI, desktop app, IDE extension | The `ai-config@Morrison-Lab` plugin at user scope, enabled by [`scripts/wire-user-config.py`](../scripts/wire-user-config.py), which [`bootstrap.sh`](../bootstrap.sh) runs | [`hooks/inject-core-rules.py`](../hooks/inject-core-rules.py) at `SessionStart` | the plugin | the plugin's [`hooks/hooks.json`](../hooks/hooks.json) | [`hooks/warn-stale-plugin-pin.py`](../hooks/warn-stale-plugin-pin.py) at `SessionStart`; [`scripts/check-hook-delivery.py`](../scripts/check-hook-delivery.py) on demand |
| Claude Code over Remote Control | The row above, since the session runs on that machine | as above | as above | as above | as above |
| Claude Code in the cloud: claude.ai/code sessions and project threads, whichever repositories they open, ai-config included | The environment Setup script, pasted from [`references/cloud-setup/cloud-setup.sh`](../references/cloud-setup/cloud-setup.sh), installs or updates the plugin at user scope when the container is built | `inject-core-rules.py` | the plugin | the plugin | [`hooks/refresh-stale-plugin-pin-cloud.py`](../hooks/refresh-stale-plugin-pin-cloud.py) at `SessionStart` |
| Claude Code in CI through `Morrison-Lab/gha`: the `@claude` bot and the review workflow | [`claude.yml`](https://github.com/Morrison-Lab/gha/blob/v2/.github/workflows/claude.yml) and [`claude-code-review.yml`](https://github.com/Morrison-Lab/gha/blob/v2/.github/workflows/claude-code-review.yml) install the plugin when their `use-ai-config` input is true, its default at `@v2` | `inject-core-rules.py` | the plugin | the plugin | none needed: each run installs `main` |
| The `@claude` bot on ai-config itself | The checkout, since [`claude-bot.yml`](../.github/workflows/claude-bot.yml) sets `use-ai-config: false` | `CLAUDE.md` in the checkout | the committed `.claude/skills` symlink | none from the catalog | none needed: `claude-code-action` restores `.claude/` from `main` |
| Codex CLI | No supported path for skills or hooks yet ([#2352](https://github.com/Morrison-Lab/ai-config/issues/2352)); `wire-user-config.py` delivers the rules | `~/.codex/AGENTS.md`, a link to the checkout's `AGENTS.md` | not delivered | not delivered | `git pull` in the checkout, for the rules |
| Gemini CLI and Antigravity | `bootstrap.sh`, which registers the checkout's `skills/` in `~/.gemini/config/skills.json` and stages a plugin that links into the checkout | `~/.gemini/GEMINI.md`, a link to the checkout's `AGENTS.md` | the checkout's `skills/` | the staged plugin's `hooks.json`, rendered by `bootstrap.sh` | `git pull` in the checkout; rerun `bootstrap.sh` after a hook changes |
| Cursor | The Cursor plugin, [`.cursor-plugin/plugin.json`](../.cursor-plugin/plugin.json), installed from GitHub | `cursor-rules/`, the plugin's user-global rules | the plugin | only in an ai-config workspace, through [`.cursor/hooks.json`](../.cursor/hooks.json) | none |
| opencode | `wire-user-config.py`, which adds the checkout's `AGENTS.md` to opencode's `instructions` | the `instructions` entry | not delivered | not delivered | `git pull` in the checkout |
| Cloud agents of other repositories: Codex cloud, Copilot, Jules, Cursor background agents | [`scripts/wire-repo-config.py`](../scripts/wire-repo-config.py), which writes a pointer block into the repository's `AGENTS.md` | a pointer to ai-config's `AGENTS.md` | not delivered | not delivered | none needed: the pointer names `main` |

## What each path cannot deliver

- **No Claude Code plugin delivers instruction files.**
  A plugin has no slot for `AGENTS.md` or `CLAUDE.md`, which is why `inject-core-rules.py` names them at session start ([#4206](https://github.com/Morrison-Lab/ai-config/issues/4206)).
- **A plugin update reaches the next session, not the running one.**
  Claude Code runs a plugin's hooks from the pinned cache snapshot it started with, so a refreshed pin takes effect only after a restart.
- **The local freshness check does not fetch.**
  `warn-stale-plugin-pin.py` compares the pin with the local marketplace clone, and the clone can itself be weeks behind `origin/main` ([#3149](https://github.com/Morrison-Lab/ai-config/issues/3149), [#3437](https://github.com/Morrison-Lab/ai-config/issues/3437)).
  A check against `origin/main` is step 2 of #5309 ([#3589](https://github.com/Morrison-Lab/ai-config/issues/3589), [#1815](https://github.com/Morrison-Lab/ai-config/issues/1815)).
- **A repository's own `SessionStart` hook does not run in a multi-repository cloud session.**
  [#5280](https://github.com/Morrison-Lab/ai-config/issues/5280) measured this with lds's render-toolchain hook, and a hook that installs the plugin is the same kind of hook, so it is not a supported cloud path.
  The Setup script is, because it runs for every session of the environment.
- **The claude.ai account plugin sync has failed since 2026-09-02** ([#3948](https://github.com/Morrison-Lab/ai-config/issues/3948)), so the cloud path installs from the marketplace instead.
  Skills uploaded to claude.ai do not reach Claude Code either way.
- **Codex gets no `SessionStart` hook.**
  [`plugins/ai-config/codex-hooks.json`](../plugins/ai-config/codex-hooks.json) routes only `UserPromptSubmit`, `PreToolUse` and `Stop`, so even a registered Codex plugin would not run `inject-core-rules.py`.
- **Cursor, and the cloud agents of other repositories, have no freshness check.**

## Leftover paths

Each of these delivered ai-config before the current path did, and still runs where it was installed.
Step 3 of #5309 retires them, with a script that reports before it deletes.

| Leftover | What it does now | Tracking |
| --- | --- | --- |
| Hook scripts copied into `~/.claude/hooks` and registered by path in `~/.claude/settings.json`, by `scripts/install-hooks.py --fix` or the old symlink install | Fires a second, usually older, copy of each registered guard; `wire-user-config.py` refuses to enable the plugin while these entries exist | [#3094](https://github.com/Morrison-Lab/ai-config/issues/3094), [#3589](https://github.com/Morrison-Lab/ai-config/issues/3589) |
| More than one enabled `ai-config@*` plugin entry, such as project-scope installs in old worktrees | Can run a pin older than the user-scope one | [#3590](https://github.com/Morrison-Lab/ai-config/issues/3590) |
| A `~/.claude/skills` copy or symlink from a pre-plugin install | Lists every skill twice | [`keep-checkouts-fresh`](../shared/workflow/keep-checkouts-fresh.md), step 2 |
| `~/.claude/shared` or `~/.claude/memories` copies | Serve old text to anything that reads those paths | [#2352](https://github.com/Morrison-Lab/ai-config/issues/2352) |
| A repository's committed `SessionStart` hook that installs the plugin in cloud sessions, which the README's marketplace section still recommends | Runs only when that repository is the session's directory | [#4035](https://github.com/Morrison-Lab/ai-config/issues/4035), [#2344](https://github.com/Morrison-Lab/ai-config/issues/2344) |
| A `.ai-config` submodule in a consumer repository | Pins that repository's skills and rules to an old commit | [#2345](https://github.com/Morrison-Lab/ai-config/issues/2345) |
