# `ai-config-hooks`: the hooks-only skills-directory plugin

This folder is not a skill.
It is a [skills-directory plugin](https://code.claude.com/docs/en/plugins-reference#skills-directory-plugins):
any folder under a project's `.claude/skills/` that carries a
`.claude-plugin/plugin.json` loads in place as `<name>@skills-dir`,
with no marketplace and no install step.
`.claude/skills` is a symlink to `skills/`, so this folder is that plugin.

It exists because the canonical hook catalog,
[`hooks/hooks.json`](../../hooks/hooks.json),
reaches Claude Code only through the ai-config marketplace plugin,
and a session that opens this checkout itself
(every remote/web session in ai-config) never installs that plugin,
so every hook is inert there
([#2004](https://github.com/Morrison-Lab/ai-config/issues/2004)).

## Contents

- `.claude-plugin/plugin.json`: the manifest.
  The plugin bundles no skills, so the skills in `skills/`
  are not registered a second time under an `ai-config-hooks:` prefix.
- `hooks/hooks.json`: **generated** by
  [`scripts/gen-hooks-plugin.py`](../../scripts/gen-hooks-plugin.py)
  from the canonical catalog.
  Do not edit it; edit the top-level [`../../hooks/hooks.json`](../../hooks/hooks.json)
  and rerun the script.
  CI runs the script with `--check` and fails when the two drift.
- `run-hook.sh`: every generated command runs through it.
  It exits 0 without running the hook when the marketplace plugin is
  enabled, because that plugin already runs the same catalog
  and the two would otherwise fire every hook twice.
  "Enabled" follows Claude Code's scope precedence for `enabledPlugins`
  (local, then project, then user settings; the highest scope that names
  an `ai-config@<marketplace>` entry decides, and a `false` there wins),
  per [`memories/claude-code-settings.md`](../../memories/claude-code-settings.md).

## How the paths work

The generated commands point at
`${CLAUDE_PLUGIN_ROOT}/../../hooks/<script>`,
which resolves through the `.claude/skills` symlink
to the checkout's own `hooks/` directory.
The hooks that fire are therefore the ones in the working tree,
including uncommitted edits on a PR branch,
rather than a cache snapshot pinned at install time
([#2439](https://github.com/Morrison-Lab/ai-config/issues/2439)).

## Two limits

- A project-scope skills-directory plugin loads only after the workspace
  trust gate, and only from the session's primary working directory.
  Whether a cloud session passes that gate at plugin-scan time
  is settled by starting one on a branch carrying this folder
  and checking that the local-time line appears on the first prompt.
- `hooks/` changes need `/reload-plugins` or a restart;
  only `SKILL.md` edits take effect live.
