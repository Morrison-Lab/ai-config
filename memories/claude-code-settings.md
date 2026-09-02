# Claude Code settings scopes and `enabledPlugins`

How Claude Code resolves a setting that appears in more than one
`settings.json`, and what that means for enabling or disabling a plugin.

Satellite of [`claude-code.md`](claude-code.md), which covers the harness
itself and the marketplace-name half of plugin installation; the scope and
precedence rules live here.

## The user scope is the LOWEST, so `~/.claude/settings.json` cannot override a repo's checked-in settings

**The belief that was wrong:** that `~/.claude/settings.json` acts as a
personal override *over* a repo's checked-in `.claude/settings.json`, so a
user could opt out of a project-enabled plugin by writing
`"<plugin>@<marketplace>": false` into their own user settings.

**The fact that replaced it:** user settings are the **lowest** of the five
scopes, so a `false` there loses to the project's `true`.
The per-user opt-out for a project-enabled plugin is
`.claude/settings.local.json`.

The documented ladder, highest precedence to lowest:

1. **Managed** (highest): can't be overridden by any other scope, apart from
   the exceptions under Settings precedence
2. **Command line arguments**: temporary session overrides
3. **Local**: overrides project and user settings
4. **Project**: overrides user settings
5. **User** (lowest): applies when nothing else specifies the setting

By file, that is
`managed-settings.json` > command line > `.claude/settings.local.json` >
`.claude/settings.json` > `~/.claude/settings.json`.

The `enabledPlugins` docs state the consequence outright:

> Project settings take precedence over user settings, so setting a plugin to
> `false` in `~/.claude/settings.json` does not disable a plugin that the
> project's `.claude/settings.json` enables.
> To opt out of a project-enabled plugin on your machine, set it to `false` in
> `.claude/settings.local.json` instead.

Three facts follow from the same source, and each is easy to get backwards:

- **`enabledPlugins` resolves by scope precedence, not by taking the union of
  the enabled names across scopes.**
  An explicit `false` in a higher scope genuinely disables a plugin a lower
  scope enabled, so any tooling that unions truthy plugin names across
  settings files reports a plugin as enabled when it is not.
- **A plugin force-enabled by managed settings cannot be disabled this way at
  all**: "Plugins force-enabled by managed settings cannot be disabled this
  way, since managed settings override local settings."
  Managed settings can also block a plugin at every scope and hide it from the
  marketplace.
- **An entry at any scope beats the plugin's own `defaultEnabled`, and it
  sticks.**
  "A plugin with no entry at any scope falls back to its `defaultEnabled`
  value", and once an entry is written it "persists across plugin updates and
  reinstalls, so changing `defaultEnabled` in a later release does not flip an
  existing user."

Two adjacent details worth not confusing with the above.
Permission rules are the documented exception to the ladder, because they
"merge across scopes rather than override".
And `pluginConfigs` is the one plugin key that ignores project and local
settings outright, which does **not** generalize to `enabledPlugins`: the same
paragraph says `enabledPlugins` "still honors project and local settings".

- **Do:** put a per-user plugin opt-out in `.claude/settings.local.json`, and
  read the ladder as user-lowest.
- **Do:** resolve a plugin's state by taking the highest scope that names it,
  and treat an explicit `false` there as final.
- **Don't:** expect `~/.claude/settings.json` to override a repo's checked-in
  `.claude/settings.json` --- for `enabledPlugins` or for any other
  precedence-resolved setting.
- **Don't:** union enabled plugin names across scopes; that turns a
  higher-scope `false` into a spurious `true`.

(Read 2026-08-12 from <https://code.claude.com/docs/en/settings>, sections
"How scopes interact" and `enabledPlugins`, and
<https://code.claude.com/docs/en/plugins-reference>, sections "Default
enablement" and "User configuration" --- the `defaultEnabled` and
persistence facts come from the first, and the "still honors project and
local settings" sentence from the second.
Third-party platform behaviour changes, so re-read rather than trusting this
snapshot.
The `.md` source of a docs page, e.g.
`https://code.claude.com/docs/en/settings.md`, fetches in full where `WebFetch`
on the rendered page truncates the settings table before reaching
`enabledPlugins`.)

## Custom subagents vs third-party plugin agents security downgrade

Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236).
Third-party plugin security models evolve across releases;
re-verify before assuming these specific fields are ignored:

- **Local subagents (`.claude/agents/*.md`)**:
  Support full frontmatter fields (`tools`, `disallowedTools`, `skills`, `model`, `effort`,
  `permissionMode`, `hooks`, `mcpServers`, `isolation`, `memory`, `maxTurns`).
- **Plugin agents loaded from third-party marketplaces**:
  Silently ignore `permissionMode`, `hooks`, and `mcpServers` frontmatter fields
  to prevent malicious plugins from auto-elevating permissions or executing arbitrary hook scripts.
  Only local `.claude/agents/` definitions or enterprise managed policies can elevate permissions
  or register agent-scoped hooks.

## Dynamic and conditional skill activation

Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236):

- **Dynamic directory discovery**:
  As files are read, written, or edited during a session,
  parent directories between the file path and `cwd` are dynamically scanned
  for `.claude/skills/` (skipping gitignored paths) and loaded into the active skill pool.
- **Conditional skills (`paths:` frontmatter)**:
  Skills specifying a `paths:` glob pattern in YAML frontmatter remain inert
  until a matching file path is accessed in the session.
- **Subagent forks (`context: fork`)**:
  Skills specifying `context: fork` automatically spawn a subagent
  rather than expanding inline into the current conversation turn.

## A guard that reads `enabledPlugins` must resolve scope, not grep one file

Measured 2026-09-01 on `skills/ai-config-hooks/run-hook.sh` (ai-config#2004):
the first draft decided "is the marketplace plugin enabled" by grepping
`~/.claude/settings.json` alone, the lowest-precedence scope.
The adversarial review caught both failure directions this file already
describes: a `false` in `.claude/settings.local.json` over a user-scope
`true` would have silenced every hook, and a project-scope `true` with no
user entry would have fired every hook twice.
The corrected runner walks local, then project, then user settings and
lets the first file that names an `ai-config@*` entry decide.

- **Do:** walk the scopes in precedence order and stop at the first file
  that names the plugin, honouring an explicit `false` there.
- **Don't:** read one settings file as the answer, or union truthy names
  across files.
