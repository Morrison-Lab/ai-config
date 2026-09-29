#!/usr/bin/env bash
# Mint a new Claude OAuth token and install it as an org-level
# CLAUDE_CODE_OAUTH_TOKEN, in one command.
#
# Usage (in a real terminal, not Claude Code's `!`, which gives stdin
# /dev/null so `claude setup-token` can never read its auth code):
#
#   scripts/refresh-claude-org-token.sh [org]     # org defaults to Morrison-Lab
#
# `claude setup-token` runs with its output on the terminal, so it behaves
# normally. Paste the `sk-ant-...` token it prints at the hidden prompt that
# follows; a token that wrapped across lines is rejoined, and anything that
# is not a single token is refused (ai-config#4129). The write then goes
# through rotate-claude-token.py, which rotates the org secret plus any
# repo-level copies in that org and confirms each write landed.
set -euo pipefail

org="${1:-Morrison-Lab}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -t 0 ]; then
  echo "error: stdin is not a terminal; run this in a real terminal, not via Claude Code's '!'." >&2
  exit 1
fi

claude setup-token
python3 "$repo_root/scripts/rotate-claude-token.py" --owners "$org" --apply
