Search for and install plugins proactively.
When a task would benefit from specialized domain tooling,
external service integrations,
linters,
or workflow automations,
search for and install existing plugins
rather than writing one-off bash workarounds or building custom tools from scratch.

Like MCP servers,
plugins provide structured, first-class capabilities.
The failure their absence causes is silent:
the work still gets done with extra turns and less safety,
while better tools remain quietly unused.

## When to search for and install plugins

Search for available plugins proactively when:

- A task requires domain-specific tooling or integrations
  (e.g. GitHub PR management, cloud provider CLIs, browser automation, database queries, container management).
- A workflow demands standard linters, formatters, or verification checkers that exist in maintained ecosystems.
- A user request asks for a capability that is general-purpose rather than repository-specific.

## Where and how to search across harnesses

Different AI agent harnesses manage plugins through distinct discovery and marketplace mechanisms:

### Claude Code

Claude Code supports plugins distributed via Git marketplaces and official registries.

1. **List registered marketplaces and installed plugins:**

   ```sh
   claude plugin marketplace list
   claude plugin list
   ```

2. **Discover available plugins:**
   Update registered marketplaces and inspect declared plugins:

   ```sh
   claude plugin marketplace update <marketplace-name>
   ```

   Inspect marketplace manifests under `~/.claude/plugins/marketplaces/<marketplace-name>/`
   or use the interactive `/plugin` Discover tab to browse available plugins and capabilities.

3. **Install and enable:**

   ```sh
   claude plugin install <plugin-name>@<marketplace-name>
   ```

   For web/cloud sessions or repository-level defaults,
   declare the plugin under `enabledPlugins` in `.claude/settings.json` or `~/.claude/settings.json`,
   and register external repositories under `extraKnownMarketplaces`.
   Always read the marketplace name from the source `.claude-plugin/marketplace.json` manifest
   rather than inferring it from the URL.

### Antigravity / Gemini CLI

Antigravity discovers plugins and skill bundles via configuration manifests:

1. **Inspect workspace and global plugin configuration:**
   Check `.agents/plugins.json` and `.agents/skills.json` at the repository root,
   or global settings in `~/.gemini/config/plugins.json`.

2. **Register plugin bundles:**
   Add plugin paths to `plugins.json` pointing to directories containing a valid `plugin.json` manifest.
   Running `bootstrap.sh` in `ai-config` registers local plugin bundles automatically
   without requiring fragile symlinks.

### Codex CLI

Codex discovers and manages plugins via marketplace repositories:

1. **List marketplaces and plugins:**

   ```sh
   codex plugin marketplace list --json
   codex plugin list --json
   ```

2. **Add a marketplace and install a plugin:**

   ```sh
   codex plugin marketplace add <owner/repo> --json
   codex plugin add <plugin-name>@<marketplace-name> --json
   ```

3. **Upgrade or migrate:**
   If a marketplace is renamed upstream,
   remove the old plugin and marketplace entries before re-adding under the new declared name
   (see [`memories/tools.md`](../../memories/tools.md) for rename migration details).

### Cursor

Cursor manages capabilities via `.cursor-plugin/marketplace.json` and workspace configuration.
Inspect `.cursor-plugin/` or workspace settings to check available extensions and hooks.

## Evaluating plugins before installation

Before installing and enabling a plugin, verify:

1. **Provenance and trust:**
   Prefer official marketplaces (`claude-plugins-official`),
   vetted organization repositories (`Morrison-Lab`),
   or well-maintained upstream packages.
2. **Permission scope:**
   Inspect what permissions the plugin requires
   (e.g. bash execution, network access, environment variable read access).
3. **Collision and redundancy:**
   - Avoid installing a plugin both natively and as a vendored git submodule or symlink
     (see [`remove-redundant-plugin-submodules.md`](remove-redundant-plugin-submodules.md)).
   - Check for conflicting hook events or colliding skill names before activating multiple bundles.
4. **Transport and credential setup:**
   - If the plugin wraps an MCP server,
     check whether it connects over local stdio or remote HTTP
     (see [`use-mcp-servers.md`](use-mcp-servers.md)).
   - Verify that required authentication tokens or environment variables are provided via dynamic launch wrappers
     rather than plain-text configs.

## Verify installation and activation

1. **Verify live registration:**
   Run the harness listing command (`claude plugin list`, `codex plugin list`, etc.)
   to confirm the plugin was recognized.
2. **Test tool execution:**
   Execute a simple read-only tool call or invoke a skill
   to confirm the plugin runs without permission or credential errors.
3. **Account for harness restarts:**
   Plugins loaded mid-session may require a session restart or harness reload
   before new tool definitions or hooks become active in the agent prompt context.

- **Do:** search official and lab plugin marketplaces before hand-rolling complex external integration tooling.
- **Do:** verify marketplace names against the source `marketplace.json` manifest rather than guessing from repo URLs.
- **Don't:** keep duplicate git submodules alongside native plugin configurations.
- **Don't:** assume a plugin registered mid-session is active without confirming tool availability or restarting the session when needed.
