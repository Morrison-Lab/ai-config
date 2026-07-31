#!/usr/bin/env bash
set -euo pipefail

export GPG_TTY="$(tty)"

HOSTS=~/.config/gh/hosts.yml
OUT=~/.gh-token.gpg

if [[ ! -f "$HOSTS" ]]; then
  echo "no $HOSTS -- nothing to encrypt" >&2
  exit 1
fi

if [[ -f "$OUT" ]]; then
  echo "$OUT already exists. Move or remove it first." >&2
  exit 1
fi

awk '/oauth_token:/ {print $2; exit}' "$HOSTS" \
  | tr -d '\n' \
  | gpg --symmetric --cipher-algo AES256 --output "$OUT"

chmod 600 "$OUT"
echo "wrote $OUT"
