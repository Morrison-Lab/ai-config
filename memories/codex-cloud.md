# Codex Cloud workspace policy and GitHub integrations

## Do not present personal workspaces as a bypass for organization policy

- When documenting alternatives to an administrator-disabled cloud feature,
  scope any personal-workspace path to personally owned repositories.
- Do not advise connecting organization-owned repositories through a personal
  workspace; that bypasses workspace governance and moves code outside the
  organization's controls.
- Treat repository authorization and workspace policy as separate gates; both
  must permit the integration.

(Learned from the review of Morrison-Lab/wai#85 on 2026-08-23; the corrected
guidance received a clean review on 2026-08-24.)
