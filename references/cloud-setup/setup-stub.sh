#!/usr/bin/env bash
# Setup-script stub for Morrison-Lab claude.ai cloud environments (ai-config#6004).
# Paste this file into the environment's Setup script field in place of
# cloud-setup.sh: it runs the current cloud-setup.sh from ai-config main, so the
# field never drifts from the repository copy, and then makes sure the ai-config
# plugin is installed and current even if that script failed.
# The field takes at most 100 lines, which cloud-setup.sh is far past.
set -u
url=https://raw.githubusercontent.com/Morrison-Lab/ai-config/main/references/cloud-setup/cloud-setup.sh
tmp="$(mktemp --suffix=.sh)"
if curl -fsSL "$url" -o "$tmp"; then
  bash "$tmp" || echo "WARNING: cloud-setup.sh exited $?; continuing" >&2
else
  echo "WARNING: could not fetch $url" >&2
fi
rm -f "$tmp"
if command -v claude >/dev/null 2>&1; then
  claude plugin marketplace add Morrison-Lab/ai-config \
    || claude plugin marketplace update Morrison-Lab \
    || echo "WARNING: could not add or update the Morrison-Lab marketplace." >&2
  claude plugin install ai-config@Morrison-Lab \
    || claude plugin update ai-config@Morrison-Lab \
    || echo "WARNING: could not install or update the ai-config plugin." >&2
else
  echo "claude: not on PATH at build time; skipping the ai-config plugin." >&2
fi
exit 0
