# Delivery paths: how ai-config reaches each harness

This page names the one supported way the rules, skills and hooks reach each harness and session kind, and the one fallback the cloud keeps ([ai-config#5309](https://github.com/Morrison-Lab/ai-config/issues/5309), step 1).
Anything else that delivers the same files is a leftover, listed under [Leftover paths](#leftover-paths), except a vendored `.ai-config` submodule, which [#2345](https://github.com/Morrison-Lab/ai-config/issues/2345) decides.
A leftover is never a supported path, even where it is the only one, as for opencode's hooks on a machine with the Claude Code plugin.
At worst it runs older code than `main`, and nothing in a guard's output says which copy fired ([#3094](https://github.com/Morrison-Lab/ai-config/issues/3094), [#3590](https://github.com/Morrison-Lab/ai-config/issues/3590)).
The README's section for each harness carries the setup steps.

Status as of 2026-11-11.

## The supported path for each session kind

| Session kind | Supported path | Rules | Skills | Hooks | Freshness check |
| --- | --- | --- | --- | --- | --- |
| Claude Code on a machine: CLI, desktop app, IDE extension | The `ai-config@Morrison-Lab` plugin at user scope, enabled by [`scripts/wire-user-config.py`](../scripts/wire-user-config.py), which [`bootstrap.sh`](../bootstrap.sh) runs | [`hooks/inject-core-rules.py`](../hooks/inject-core-rules.py) at `SessionStart` | the plugin | the plugin's [`hooks/hooks.json`](../hooks/hooks.json) | [`hooks/warn-stale-plugin-pin.py`](../hooks/warn-stale-plugin-pin.py) at `SessionStart`; [`scripts/check-hook-delivery.py`](../scripts/check-hook-delivery.py) on demand |
| Claude Code over Remote Control | The row above, since the session runs on that machine | as above | as above | as above | as above |
| Claude Code in the cloud: claude.ai/code sessions and project threads, whichever repositories they open, ai-config included | The environment Setup script, pasted from [`references/cloud-setup/cloud-setup.sh`](../references/cloud-setup/cloud-setup.sh), which installs or updates the plugin at user scope when a container is built; a repository hook that installs the plugin is a fallback only for an environment whose Setup script does not, and only in a session that opens that one repository, acting only when `CLAUDE_CODE_REMOTE` is `true`; both need network access to GitHub | `inject-core-rules.py` | the plugin | the plugin | [`hooks/refresh-stale-plugin-pin-cloud.py`](../hooks/refresh-stale-plugin-pin-cloud.py) at each `SessionStart` |
| Claude Code in CI through `Morrison-Lab/gha`: other repositories' `@claude` bot, and every repository's review workflow, ai-config's included | [`claude.yml`](https://github.com/Morrison-Lab/gha/blob/v2/.github/workflows/claude.yml) and [`claude-code-review.yml`](https://github.com/Morrison-Lab/gha/blob/v2/.github/workflows/claude-code-review.yml), which install the plugin when their `use-ai-config` input is true, its default at `@v2` | `inject-core-rules.py` | the plugin | the plugin | none needed: each run installs `main` |
| The `@claude` bot on ai-config itself | The checkout, since [`claude-bot.yml`](../.github/workflows/claude-bot.yml) sets `use-ai-config: false` | `CLAUDE.md` in the checkout | the committed `.claude/skills` symlink | none from the catalog | none needed: the run reads the checkout it was triggered on |
| Codex CLI | The Codex plugin, [`.codex-plugin/plugin.json`](../.codex-plugin/plugin.json), registered by hand with Codex; `wire-user-config.py` links the rules | `~/.codex/AGENTS.md`, a link to the checkout's `AGENTS.md` | the plugin, through the wrappers in [`codex-skills/`](../codex-skills/) | [`plugins/ai-config/codex-hooks.json`](../plugins/ai-config/codex-hooks.json), with no `SessionStart` hook | none; `git pull` in the checkout updates it |
| Gemini CLI and Antigravity | `bootstrap.sh`, which registers the checkout's `skills/` in `~/.gemini/config/skills.json` and stages a plugin under `~/.gemini/config/plugins/` that links into the checkout | `~/.gemini/GEMINI.md`, whose import block reads `~/.gemini/ai-config-AGENTS.md`, a link to the checkout's `AGENTS.md` | the checkout's `skills/` | Antigravity only: the staged plugin's `hooks.json`, which `bootstrap.sh` renders | none; `git pull` in the checkout updates it, and `bootstrap.sh` must be rerun after `hooks/hooks.json` changes |
| Cursor | The Cursor plugin, [`.cursor-plugin/plugin.json`](../.cursor-plugin/plugin.json), installed from GitHub | `cursor-rules/`, the plugin's user-global rules | the plugin | only in an ai-config workspace, through [`.cursor/hooks.json`](../.cursor/hooks.json) | none |
| opencode | `wire-user-config.py`, which adds the checkout's `AGENTS.md` to opencode's `instructions` | the `instructions` entry | by hand: a link from `~/.config/opencode/skills/`, as the README describes | not delivered by a supported path on a machine with the Claude Code plugin (see the bullets that follow) | none; `git pull` in the checkout updates it |
| Cloud agents of other repositories: Codex cloud, Copilot, Jules, Cursor background agents | [`scripts/wire-repo-config.py`](../scripts/wire-repo-config.py), which writes a pointer block into the repository's `AGENTS.md`, and into a `CLAUDE.md` that does not import it; the marketplace entry it also writes, and the plugin entry `--enable-plugin` adds, reach only Claude Code, covered by the rows above | a pointer to ai-config's `AGENTS.md` on `main` | not delivered | not delivered | none needed: the pointer names `main` |

## What each path cannot deliver

- **No Claude Code plugin delivers instruction files.**
  A plugin has no slot for `AGENTS.md` or `CLAUDE.md`, which is why `inject-core-rules.py` names them at session start ([#4206](https://github.com/Morrison-Lab/ai-config/issues/4206)).
- **A plugin update reaches the next session, not the running one.**
  Claude Code runs a plugin's hooks from the pinned cache snapshot it started with, so a refreshed pin takes effect only after a restart.
- **The local freshness check does not fetch.**
  `warn-stale-plugin-pin.py` compares the pin with the local marketplace clone, and the clone can itself be weeks behind `origin/main` ([#3149](https://github.com/Morrison-Lab/ai-config/issues/3149), [#3437](https://github.com/Morrison-Lab/ai-config/issues/3437)).
  A check against `origin/main` is step 2 of #5309 ([#3589](https://github.com/Morrison-Lab/ai-config/issues/3589)).
- **A repository's own `SessionStart` hook does not run in a session that opens several repositories.**
  [#5280](https://github.com/Morrison-Lab/ai-config/issues/5280) measured this with lds's render-toolchain hook.
  A repository hook that installs the plugin, such as rme's `install-ai-config.sh`, has the same limit, so the supported cloud path is the Setup script, which runs however many repositories a session opens, and such a hook is only its fallback.
  The Setup script runs once per container, and `refresh-stale-plugin-pin-cloud.py` keeps the plugin current in the sessions that reuse the container.
- **The claude.ai account plugin sync has failed since 2026-09-02** ([#3948](https://github.com/Morrison-Lab/ai-config/issues/3948)).
  The cloud path does not depend on it, because the Setup script installs from the marketplace.
  Skills uploaded to claude.ai do not reach Claude Code at all.
- **Codex runs no `SessionStart` hook**, since `codex-hooks.json` routes only `UserPromptSubmit`, `PreToolUse` and `Stop`, so `inject-core-rules.py` never runs there.
  No script registers the Codex plugin, and `bootstrap.sh`'s header still says Codex has no install path for skills, which this row contradicts ([#2352](https://github.com/Morrison-Lab/ai-config/issues/2352)).
- **opencode gets skills only by hand, and hooks only through a leftover on a machine with the Claude Code plugin.** oh-my-openagent's Claude-hooks bridge runs the catalog only from `~/.claude/settings.json` entries that `install-hooks.py --fix` writes ([`docs/opencode-hook-mapping.md`](opencode-hook-mapping.md)), and those entries are a leftover wherever the plugin is enabled.
- **Codex, Gemini CLI, Antigravity, Cursor and opencode have no freshness check.**
- **ai-config's own review workflow loads ai-config twice.**
  [`claude-review.yml`](../.github/workflows/claude-review.yml) keeps gha's `use-ai-config` default, so the plugin installs on top of the checkout.
  [`claude-bot.yml`](../.github/workflows/claude-bot.yml) turns its own `use-ai-config` input off to avoid the same double load in the bot's runs.
- **A repository that vendors ai-config as a `.ai-config` submodule is pinned to one commit.**
  The README's opencode consumer setup uses one, and [#2345](https://github.com/Morrison-Lab/ai-config/issues/2345) decides which repositories keep theirs.

## Leftover paths

Each of these either delivered ai-config before the current path did or duplicates it, and still runs where it was installed.
Step 3 of #5309 retires them, with a script that reports before it deletes.

| Leftover | What it does now | Tracking |
| --- | --- | --- |
| Hook scripts in `~/.claude/hooks`, left by the old symlink install or a manual copy, and registered by path in `~/.claude/settings.json` by `scripts/install-hooks.py --fix`, on a machine whose Claude Code has the plugin | Fires a second, usually older, copy of each registered guard; `wire-user-config.py` refuses to enable the plugin while these entries exist | [#3094](https://github.com/Morrison-Lab/ai-config/issues/3094), [#3589](https://github.com/Morrison-Lab/ai-config/issues/3589) |
| More than one enabled `ai-config@*` plugin entry, such as project-scope installs in old worktrees | Can run a pin older than the user-scope one | [#3590](https://github.com/Morrison-Lab/ai-config/issues/3590) |
| A `~/.claude/skills` copy or symlink from a pre-plugin install | Lists every skill twice | [`keep-checkouts-fresh`](../shared/workflow/keep-checkouts-fresh.md), step 2 |
| `~/.claude/shared` or `~/.claude/memories` copies | Serve old text to anything that reads those paths | [#2352](https://github.com/Morrison-Lab/ai-config/issues/2352) |
| A repository hook that installs the plugin, in a cloud environment whose Setup script also installs it | Adds nothing: in a session that opens only its repository, a hook that checks for the plugin first, as rme's does, finds it installed and exits, and in a session that opens several it does not run | [#5280](https://github.com/Morrison-Lab/ai-config/issues/5280) |
