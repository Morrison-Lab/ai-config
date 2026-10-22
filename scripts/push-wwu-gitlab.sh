#!/usr/bin/env bash
# Push the gla and glr checkouts to the private WWU GitLab test projects
# (Ezra, 2026-10-22: Claude Code's auto mode denies this push from a session,
# so Ezra runs this script). Idempotent: pushing an unchanged HEAD is a no-op.
# Usage: bash push-wwu-gitlab.sh [github-dir]   (default: ~/Documents/GitHub)
set -euo pipefail

base="${1:-$HOME/Documents/GitHub}"
host="https://gitlab.cs.wwu.edu/morri313"

for repo in gla glr; do
  echo "== $repo"
  git -C "$base/$repo" -c credential.helper='!glab auth git-credential' \
    push "$host/$repo.git" HEAD:main
done
