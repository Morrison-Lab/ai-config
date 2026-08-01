#!/usr/bin/env bash
# Install the shiva launcher dotfiles by symlinking them out of this checkout
# into ~/bin, ~/.local/bin, and ~/.config/tui-alloc.
#
# Called by bootstrap.sh, and safe to run directly. Refuses to do anything on a
# machine that isn't shiva, so a web container or another workstation running
# bootstrap.sh is unaffected.
#
# Usage:
#   dotfiles/shiva/install.sh [--adopt] [-n|--dry-run]
#
#   --adopt   replace an existing REAL file with a symlink, but only when it is
#             byte-identical to the tracked copy. Needed the first time on a
#             machine where these files already exist on disk unlinked, which is
#             how they got into the repo in the first place.
#   -n        show what would happen, change nothing.
#
# Env:
#   AI_CONFIG_DOTFILES_FORCE=1   install even when this isn't shiva.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"

# shellcheck disable=SC2034  # consumed by the sourced link-one.sh
LINK_ONE_FIX_HINT="remove it, or rerun with --adopt if it is byte-identical"
# shellcheck source-path=SCRIPTDIR/../..
# shellcheck source=scripts/lib/link-one.sh
. "$REPO_ROOT/scripts/lib/link-one.sh"

ADOPT=0
DRYRUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --adopt) ADOPT=1 ;;
    -n|--dry-run) DRYRUN=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "install.sh: unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# --- Host gate -------------------------------------------------------------
# Detect by SLURM ClusterName rather than hostname. A session launched by
# claude-alloc or cnode runs on a compute node, so `uname -n` reports c2/c3/c4
# rather than the login node -- ClusterName reads the same from both.
#
# The `|| cluster=""` is required, not defensive: under `set -e` an assignment
# takes the exit status of its command substitution, and pipefail propagates a
# scontrol failure through the pipe, so an unguarded assignment would abort the
# script on a machine with no SLURM at all -- precisely the case this gate
# exists to handle gracefully.
cluster=""
if command -v scontrol >/dev/null 2>&1; then
  cluster="$(scontrol show config 2>/dev/null \
    | sed -n 's/^ClusterName[[:space:]]*=[[:space:]]*//p' \
    | head -1 | tr -d '[:space:]')" || cluster=""
fi

if [ "${AI_CONFIG_DOTFILES_FORCE:-0}" != "1" ] && [ "$cluster" != "shiva" ]; then
  printf 'skip  dotfiles/shiva (SLURM ClusterName=%s, not shiva)\n' "${cluster:-none}"
  printf '      set AI_CONFIG_DOTFILES_FORCE=1 to install anyway\n'
  exit 0
fi

# --- Install ---------------------------------------------------------------

# Replace a real file with a link only when nothing can be lost by doing so:
# `cmp` decides that exactly, so the destructive branch is gated on a
# deterministic check rather than on judgement.
install_pair() {
  local src="$1" dest="$2" name
  name="$(basename "$dest")"

  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    if cmp -s "$src" "$dest"; then
      if [ "$ADOPT" != "1" ]; then
        printf 'same  %s (real file, byte-identical -- rerun with --adopt to link it)\n' "$name"
      elif [ "$DRYRUN" = "1" ]; then
        printf 'adopt %s (identical; would replace with a link)\n' "$name"
      else
        rm -f "$dest"
        ln -s "$src" "$dest"
        printf 'adopt %s -> %s (replaced an identical real file)\n' "$name" "$src"
      fi
    else
      printf 'DIFF  %s (real file differs from the tracked copy -- not touched)\n' "$name"
      printf '        diff %s %s\n' "$dest" "$src"
    fi
    return
  fi

  if [ "$DRYRUN" = "1" ]; then
    if [ -L "$dest" ]; then
      printf 'ok    %s (already a link)\n' "$name"
    else
      printf 'link  %s -> %s (would create)\n' "$name" "$src"
    fi
    return
  fi

  link_one "$src" "$dest"
}

install_tree() {
  local srcdir="$1" destdir="$2" f
  [ -d "$srcdir" ] || return 0
  [ "$DRYRUN" = "1" ] || mkdir -p "$destdir"
  # dotglob so config/tui-alloc/.zshrc is picked up; nullglob so an empty dir
  # doesn't hand the loop a literal glob.
  shopt -s dotglob nullglob
  for f in "$srcdir"/*; do
    install_pair "$f" "$destdir/$(basename "$f")"
  done
  shopt -u dotglob nullglob
}

printf -- '--- shiva dotfiles (%s) ---\n' "$([ "$DRYRUN" = "1" ] && echo "dry run" || echo "installing")"
install_tree "$HERE/bin"               "$HOME/bin"
install_tree "$HERE/local-bin"         "$HOME/.local/bin"
install_tree "$HERE/config/tui-alloc"  "$HOME/.config/tui-alloc"

# --- ~/.zshrc fragment -----------------------------------------------------
# ~/.zshrc itself is deliberately not tracked (it carries personal credential
# helpers), so the two launcher-critical pieces live in a fragment the user
# sources. This never edits ~/.zshrc; it only reports.
FRAGMENT="$HERE/zshrc-fragment.zsh"
if grep -qF "zshrc-fragment.zsh" "$HOME/.zshrc" 2>/dev/null; then
  printf 'ok    ~/.zshrc sources the launcher fragment\n'
else
  printf '\nTODO  ~/.zshrc does not source the launcher fragment. Add this line:\n'
  printf '        source %s\n' "$FRAGMENT"
  printf '      It puts ~/bin on PATH and installs the ALLOC_CONDA_ENV chpwd hook,\n'
  printf '      without which the launchers are neither on PATH nor env-aware.\n'
fi
