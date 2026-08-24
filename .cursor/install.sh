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

# 0. Root / sudo detection guard (matches references/cloud-setup/cloud-setup.sh).
if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  echo "ERROR: not running as root and 'sudo' is not installed; cannot install system packages." >&2
  exit 1
fi

# 1. Vendored sembr-skills plugin submodule. validate-skills.py warns and the
#    plugin-source check only reports its empty-directory branch without it.
git submodule update --init --recursive

# 2. System packages: update apt index and install `python` shim + `python3-pip` if missing.
#    test_compare_shell_forms.py spawns a real bash that invokes `python` (not `python3`).
if ! command -v python >/dev/null 2>&1 || ! command -v pip3 >/dev/null 2>&1; then
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq python-is-python3 python3-pip
fi

# 3. Python tooling: pyyaml (pin derived from validate.yml) and pre-commit.
#    Use python3 -m pip with --break-system-packages for PEP 668 environments.
PYYAML_PIN="$(grep -oE 'pyyaml==[0-9.]+' .github/workflows/validate.yml | head -1 || echo 'pyyaml')"
$SUDO python3 -m pip install --quiet --disable-pip-version-check --break-system-packages \
  "$PYYAML_PIN" pre-commit

# 4. Quarto renders and previews the documentation website. Pinned for
#    reproducibility; the version check keeps the install idempotent.
#    Uses apt-get install on the .deb to automatically resolve dependencies.
QUARTO_VERSION=1.10.18
if [ "$(quarto --version 2>/dev/null || true)" != "$QUARTO_VERSION" ]; then
  arch="$(dpkg --print-architecture)"
  deb="$(mktemp --suffix=.deb)"
  trap 'rm -f "$deb"' EXIT
  curl -fsSL -o "$deb" \
    "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-${arch}.deb"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y --no-install-recommends "$deb"
  rm -f "$deb"
  trap - EXIT
fi

echo "ai-config environment ready: $(python3 --version), quarto $(quarto --version)"
