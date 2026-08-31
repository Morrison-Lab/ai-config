# VS Code profiles and extension isolation

Use a named VS Code profile when a repository needs a small, persistent
extension allowlist rather than the user's full global extension set.

## Repo-specific extension allowlists

- **Do:** create a named profile, install only the repo-facing extensions into
  it, and open the folder with `code --profile <name> <folder>`.
- **Do:** close the folder or remove it from its current window with
  `code --remove <folder>` before reopening it under the named profile, then
  verify the new window title and extension-host logs.
- **Don't:** expect `--profile` to move a folder that VS Code already owns in
  another window; VS Code may reuse the existing window and keep its profile.
- **Don't:** use launch-only `--disable-extension` flags when the extension
  allowlist must persist across restarts.
- Observed on VS Code 1.135.0 for HACtions (2026-08-30): the named profile
  persisted seven repo extensions and loaded no Azure, Databricks, Foundry,
  Python/Jupyter, GitLens, or alternate-agent providers after the folder was
  removed from its old window and reopened.
