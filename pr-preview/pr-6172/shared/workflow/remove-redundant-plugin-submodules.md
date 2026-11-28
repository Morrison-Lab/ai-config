Native plugin integration is the primary mechanism for consuming AI tools and skills across Claude Code, Cursor, Antigravity, and GitHub Actions workflows (via `Morrison-Lab/gha`).

Historically, some consumer repositories vendored `ai-config` (or other toolsets) as a git submodule (such as `.ai-config/`) alongside a committed symlink (`.claude/skills -> ../.ai-config/skills`) or path references.

When a repository configures or consumes a tool natively as a plugin, keeping a git submodule for that same tool is redundant and harmful.

## Why dual integration is harmful

- **Drift and stale state**: The submodule pin remains frozen at a specific commit while the plugin auto-updates or tracks current capabilities.
- **Double loading / registration**: Having both can cause harnesses to register skills twice (e.g. bare `ums` beside `ai-config:ums`), crowding skill listings and degrading routing.
- **Cloning and CI overhead**: Submodules require recursive cloning, extra network fetches, and authentication tokens in CI workflows that are unnecessary when plugins are loaded directly.
- **Worktree and shallow clone friction**: Submodules complicate worktree cleanup (`fatal: working trees containing submodules cannot be moved or removed`) and degrade shallow-clone merge operations.

## Policy

If a repository uses `ai-config` (or any other tool) as both a native plugin and a git submodule, **remove the submodule**.

## Migration steps

When auditing or maintaining a consumer repository with dual integration:

1. **Verify native plugin integration:**
   Confirm the plugin is configured or available in the environment (e.g. via `.claude-plugin/`, `.cursor-plugin/`, `.agents/plugins.json`, global plugin config, or `Morrison-Lab/gha` reusable workflows in `.github/workflows/`).
2. **De-initialize and remove the submodule:**
   ```bash
   git submodule deinit -f <submodule-path>
   git rm -rf <submodule-path>
   rm -rf .git/modules/<submodule-path>
   ```
3. **Clean up `.gitmodules`:**
   Remove the submodule section from `.gitmodules`.
   If `.gitmodules` contains no other submodules, remove the file entirely (`git rm .gitmodules`).
4. **Remove legacy symlinks and directory shims:**
   Remove any committed symlink that pointed into the vendored submodule, such as `.claude/skills -> ../.ai-config/skills`.
5. **Update `.gitignore`:**
   Remove any ignore carve-outs or exceptions that were added solely for the submodule or its symlinks (e.g. `!.claude/skills`).
6. **Update CI workflows:**
   If `.github/workflows/` configured `submodules: true` or `checkout-submodules: true` solely for the removed submodule, update the checkout step to omit unnecessary submodule recursion.
7. **Clean up documentation and include citations:**
   If `CLAUDE.md`, `AGENTS.md`, or documentation transcluded fragments via the submodule path (e.g. `@.ai-config/shared/...`), update citations to point to canonical paths or rely on plugin-provided context.
