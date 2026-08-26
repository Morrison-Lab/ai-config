#!/usr/bin/env bash
# link_one -- symlink a repo path into a consumer location, never clobbering
# whatever is already there.
#
# Sourced by bootstrap.sh (which installs into ~/.claude, ~/.codex, ~/.gemini)
# and by the per-machine installers under dotfiles/ (which install into ~/bin,
# ~/.local/bin, ~/.config/...). It lives here so those two callers share one
# implementation rather than each carrying a copy that can drift.
#
# Usage:
#   LINK_ONE_FIX_HINT="how to resolve a collision in this context"   # optional
#   . "<repo>/scripts/lib/link-one.sh"
#   link_one /abs/path/in/repo /abs/path/at/destination [hint]
#
# An optional third argument overrides LINK_ONE_FIX_HINT for that call.
# The hint is a parameter because callers resolve a collision differently:
# bootstrap.sh passes scripts/check-install.py --fix only for ~/.claude
# links. That script's --consumer-dir retargets a whole Claude-style
# manifest, so the same hint is wrong for Codex, Gemini, Copilot, and
# Cursor (ai-config#2286). Those callers inherit this file's default
# (remove it or replace it with a link manually). Dotfiles installers
# set their own LINK_ONE_FIX_HINT; shiva's is the --adopt path.

# Advice printed when a real (non-symlink) path blocks the link. Overridable by
# the caller or by a per-call third argument; the default says nothing
# tool-specific.
: "${LINK_ONE_FIX_HINT:=remove it or replace it with a link manually}"

link_one() {
  local src="$1" dest="$2" name
  local hint="${3:-${LINK_ONE_FIX_HINT:-remove it or replace it with a link manually}}"
  name="$(basename "$dest")"

  if [ -L "$dest" ]; then
    local current
    current="$(readlink "$dest")"
    if [ "$current" = "$src" ]; then
      printf 'ok    %s (already linked)\n' "$name"
    else
      printf 'skip  %s (symlink points elsewhere: %s)\n' "$name" "$current"
    fi
    return
  fi

  # A real (non-symlink) path is already here: never clobber it. In a per-child
  # merge this also means a tracked skill/command whose name collides with a
  # built-in already in ~/.claude (e.g. skills/) is skipped -- it can't shadow
  # the built-in in remote sessions. Rename ours if that's not what you want.
  if [ -e "$dest" ]; then
    printf 'skip  %s (real path exists at %s -- %s)\n' \
      "$name" "$dest" "$hint"
    return
  fi

  ln -s "$src" "$dest"
  printf 'link  %s -> %s\n' "$name" "$src"
}
