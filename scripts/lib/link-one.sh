#!/usr/bin/env bash
# link_one -- symlink a repo path into a consumer location, never clobbering
# whatever is already there.
#
# Sourced by the per-machine installers under dotfiles/ (which install into
# ~/bin, ~/.local/bin, ~/.config/...). bootstrap.sh itself no longer sources
# this -- it stopped placing anything under ~/.claude, ~/.codex, or
# ~/.cursor in favor of native plugin installs (see its header comment).
# This helper lives in its own file so multiple dotfiles installers can share
# one implementation rather than each carrying a copy that can drift.
#
# Usage:
#   LINK_ONE_FIX_HINT="how to resolve a collision in this context"   # optional
#   . "<repo>/scripts/lib/link-one.sh"
#   link_one /abs/path/in/repo /abs/path/at/destination
#
# The hint is a parameter because each caller resolves a collision
# differently for its own destination directory.

# Advice printed when a real (non-symlink) path blocks the link. Overridable by
# the caller; the default says nothing tool-specific.
: "${LINK_ONE_FIX_HINT:=remove it or replace it with a link manually}"

link_one() {
  local src="$1" dest="$2" name
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
      "$name" "$dest" "$LINK_ONE_FIX_HINT"
    return
  fi

  ln -s "$src" "$dest"
  printf 'link  %s -> %s\n' "$name" "$src"
}
