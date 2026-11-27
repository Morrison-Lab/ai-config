#!/usr/bin/env bash
# Cloud VM environment setup for Morrison-Lab/ai-config.
#
# Invoked from the repository root via .agents/environment.json on new cloud
# VMs. Idempotent and non-interactive: installs user-scoped tooling under
# $HOME/.local so packages persist across / resets while /home is retained.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 1. Ensure $HOME/.local/bin is on PATH for non-interactive shells that source
#    ~/.bashrc via BASH_ENV.
mkdir -p "$HOME/.local/bin"
touch "$HOME/.bashrc"
sed -i '/case \$- in/,/esac/d' "$HOME/.bashrc" 2>/dev/null || true
grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc" \
  || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
export PATH="$HOME/.local/bin:$PATH"

# 2. Initialize vendored submodules (shared/sembr-skills).
git submodule update --init --recursive

# 3. Install Python validation dependencies pinned in validate.yml.
PYYAML_PIN="$(grep -oE 'pyyaml==[0-9.]+' .github/workflows/validate.yml | head -1 || true)"
PYTEST_PIN="$(grep -oE 'pytest==[0-9.]+' .github/workflows/validate.yml | head -1 || true)"
MARKDOWN_IT_PIN="$(grep -oE 'markdown-it-py==[0-9.]+' .github/workflows/validate.yml | head -1 || true)"
PYYAML_PIN="${PYYAML_PIN:-pyyaml==6.0.2}"
PYTEST_PIN="${PYTEST_PIN:-pytest==8.3.5}"
MARKDOWN_IT_PIN="${MARKDOWN_IT_PIN:-markdown-it-py==3.0.0}"

PIP_USER_FLAG=()
if [ -z "${VIRTUAL_ENV:-}" ]; then
  PIP_USER_FLAG=(--user)
fi
python3 -m pip install "${PIP_USER_FLAG[@]}" --no-input --quiet --disable-pip-version-check \
  "$PYYAML_PIN" "$PYTEST_PIN" "$MARKDOWN_IT_PIN"

# 4. Install markdownlint-cli2 (pinned in .pre-commit-config.yaml) under
#    $HOME/.local so `npx --no-install markdownlint-cli2` works offline and
#    persists in /home.
if command -v npm >/dev/null 2>&1; then
  MDLINT_PIN="$(grep -oE 'markdownlint-cli2@[0-9.]+' .pre-commit-config.yaml | head -1 || true)"
  MDLINT_PIN="${MDLINT_PIN:-markdownlint-cli2@0.22.1}"
  MDLINT_VER="${MDLINT_PIN#*@}"
  npm config set prefix "$HOME/.local"
  if ! command -v markdownlint-cli2 >/dev/null 2>&1 \
    || ! markdownlint-cli2 --help 2>/dev/null | head -1 | grep -qF "v${MDLINT_VER}"; then
    npm install -g --no-audit --no-fund --silent "$MDLINT_PIN"
  fi
fi

# 5. Wire Antigravity plugin staging and user-level agent config.
bash "$REPO_ROOT/bootstrap.sh"
