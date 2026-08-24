#!/usr/bin/env bash
# Cloud Agent install script for ai-config.
#
# Idempotent, non-interactive dependency refresh run after the repo is checked
# out. With environment builds it runs once at build time and is baked into the
# snapshot; without a build it runs while the agent is prepared. Keep it safe to
# rerun.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 1. Vendored sembr-skills plugin submodule. validate-skills.py warns and the
#    plugin-source check only reports its empty-directory branch without it.
git submodule update --init --recursive

# 2. `python` shim. test_compare_shell_forms.py spawns a real bash that invokes
#    `python` (not `python3`); six of its subtests fail without the shim.
if ! command -v python >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python-is-python3
fi

# 3. Python tooling: pyyaml for the validators (CI pins 6.0.2), pre-commit for
#    the secret-scanning hook. pip installs pre-commit under ~/.local/bin.
pip install --quiet --disable-pip-version-check pyyaml==6.0.2 pre-commit

# 4. Quarto renders and previews the documentation website. Pinned for
#    reproducibility; the version check keeps the install idempotent.
QUARTO_VERSION=1.10.18
if [ "$(quarto --version 2>/dev/null || true)" != "$QUARTO_VERSION" ]; then
  arch="$(dpkg --print-architecture)"
  deb="$(mktemp --suffix=.deb)"
  curl -fsSL -o "$deb" \
    "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-${arch}.deb"
  sudo dpkg -i "$deb"
  rm -f "$deb"
fi

echo "ai-config environment ready: $(python3 --version), quarto $(quarto --version)"
