#!/usr/bin/env bash
# Bootstrap ai-config: symlink skills, commands, top-level files, and memories
# into their respective consumer directories (Claude Code, Codex, VS Code
# Copilot, etc.).
#
# For each top-level subdir (skills/, commands/, ...):
#   - if ~/.claude/<name> doesn't exist yet, symlink the whole dir (so new
#     files added to the repo later appear automatically);
#   - if ~/.claude/<name> already exists as a real dir (e.g. cloud/web
#     sessions pre-populate ~/.claude/skills with built-in skills), merge by
#     symlinking each child into it instead of trying to replace the whole dir.
#
# Safe to rerun. Never clobbers a real (non-symlink) file/dir already in place.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
GEMINI_DIR="${GEMINI_HOME:-$HOME/.gemini}"
GEMINI_CONFIG_DIR="${GEMINI_CONFIG_HOME:-$GEMINI_DIR/config}"

# VS Code Copilot memory directory (macOS default; override with COPILOT_MEMORY_DIR)
COPILOT_MEMORY_DIR="${COPILOT_MEMORY_DIR:-$HOME/Library/Application Support/Code/User/globalStorage/github.copilot-chat/memory-tool/memories}"

mkdir -p "$CLAUDE_DIR"

# Symlink $src -> $dest unless something is already there. Shared with the
# per-machine installers under dotfiles/, so both resolve collisions the same
# way; the hint below is the part that differs, since check-install.py only
# knows about ~/.claude.
# shellcheck disable=SC2034  # consumed by the sourced link-one.sh
LINK_ONE_FIX_HINT="run scripts/check-install.py --fix to replace it with a link, or merge manually"
# shellcheck source=scripts/lib/link-one.sh
. "$SCRIPT_DIR/scripts/lib/link-one.sh"

# --- Top-level files (CLAUDE.md, etc.) ---
shopt -s nullglob
for src in "$SCRIPT_DIR"/*.md; do
  [ -f "$src" ] || continue
  fname="$(basename "$src")"
  [[ "$fname" == "README.md" ]] && continue   # don't symlink repo README
  link_one "$src" "$CLAUDE_DIR/$fname"
done

# --- Directories (skills, commands, memories, etc.) ---
for src in "$SCRIPT_DIR"/*/; do
  src="${src%/}"
  name="$(basename "$src")"
  case "$name" in
    # references/ is documentation/example material, not consumable config, so
    # it is deliberately NOT symlinked into ~/.claude.
    # codex-skills/ is linked into ~/.codex/skills below, not ~/.claude.
    # dotfiles/ is machine-specific shell tooling installed into ~/bin and
    # friends by its own per-machine installer at the bottom of this script.
    .git|node_modules|references|codex-skills|dotfiles) continue ;;
  esac

  dest="$CLAUDE_DIR/$name"

  # A real directory already lives at the target (not our symlink): merge by
  # linking each child rather than skipping the whole group. dotglob links
  # hidden entries too (parity with the whole-dir symlink below) and, unlike
  # "$src"/.*, never expands to . or .. ; it's scoped so the outer loop keeps
  # ignoring .git/.github.
  if [ -d "$dest" ] && [ ! -L "$dest" ]; then
    shopt -s dotglob
    for child in "$src"/*; do
      link_one "$child" "$dest/$(basename "$child")"
    done
    shopt -u dotglob
  else
    link_one "$src" "$dest"
  fi
done

# --- Codex skill wrappers: symlink individual generated wrappers into Codex ---
if [ -d "$SCRIPT_DIR/codex-skills" ]; then
  printf '\n--- Codex skill wrappers ---\n'
  mkdir -p "$CODEX_DIR/skills"
  for src in "$SCRIPT_DIR"/codex-skills/*; do
    [ -d "$src" ] || continue
    link_one "$src" "$CODEX_DIR/skills/$(basename "$src")"
  done
fi

# --- Memories: symlink individual .md files into VS Code Copilot memory dir ---
if [ -d "$SCRIPT_DIR/memories" ] && [ -d "$COPILOT_MEMORY_DIR" ]; then
  printf '\n--- VS Code Copilot memories ---\n'
  for src in "$SCRIPT_DIR"/memories/*.md; do
    [ -f "$src" ] || continue
    link_one "$src" "$COPILOT_MEMORY_DIR/$(basename "$src")"
  done
else
  printf '\nskip  memories/ (dir not found or Copilot memory dir missing)\n'
fi

# --- Gemini CLI & Antigravity skills: symlink skills and register skills.json ---
if [ -d "$SCRIPT_DIR/skills" ]; then
  printf '\n--- Gemini CLI & Antigravity skills ---\n'
  mkdir -p "$GEMINI_DIR/skills"
  for src in "$SCRIPT_DIR"/skills/*; do
    [ -d "$src" ] || continue
    link_one "$src" "$GEMINI_DIR/skills/$(basename "$src")"
  done
  if [ -d "$SCRIPT_DIR/shared/sembr-skills/skills" ]; then
    for src in "$SCRIPT_DIR"/shared/sembr-skills/skills/*; do
      [ -d "$src" ] || continue
      link_one "$src" "$GEMINI_DIR/skills/$(basename "$src")"
    done
  else
    printf 'skip  sembr-skills (submodule not checked out -- run: git submodule update --init -- shared/sembr-skills)\n'
  fi

  # Antigravity/Gemini CLI customization spec (https://github.com/google-gemini/gemini-cli):
  # skills.json in customization root accepts {"entries": [{"path": "..."}], "inherits": [...], "exclude": [...]}.
  mkdir -p "$GEMINI_CONFIG_DIR"
  SKILLS_JSON="$GEMINI_CONFIG_DIR/skills.json"
  if [ ! -f "$SKILLS_JSON" ]; then
    cat <<EOF > "$SKILLS_JSON"
{
  "entries": [
    { "path": "$GEMINI_DIR/skills" }
  ]
}
EOF
    printf 'write skills.json (%s) -> %s/skills\n' "$SKILLS_JSON" "$GEMINI_DIR"
  elif grep -q "$GEMINI_DIR/skills" "$SKILLS_JSON" 2>/dev/null; then
    printf 'ok    skills.json (%s/skills already registered)\n' "$GEMINI_DIR"
  else
    printf 'skip  skills.json (%s exists but does not register %s/skills)\n' "$SKILLS_JSON" "$GEMINI_DIR"
  fi

  # Antigravity global customizations root (~/.gemini/config/skills)
  link_one "$GEMINI_DIR/skills" "$GEMINI_CONFIG_DIR/skills"
fi


if [ -f "$SCRIPT_DIR/GEMINI.md" ]; then
  mkdir -p "$GEMINI_DIR" "$GEMINI_CONFIG_DIR"
  link_one "$SCRIPT_DIR/GEMINI.md" "$GEMINI_DIR/GEMINI.md"
  link_one "$SCRIPT_DIR/GEMINI.md" "$GEMINI_CONFIG_DIR/GEMINI.md"
fi

# --- Machine-specific dotfiles ---
# Each dotfiles/<machine>/install.sh gates on its own host and exits quietly
# when this isn't that machine, so running them all here is safe anywhere.
# They install outside ~/.claude (~/bin, ~/.local/bin, ~/.config/...), which is
# why dotfiles/ is excluded from the directory loop above.
shopt -s nullglob
for installer in "$SCRIPT_DIR"/dotfiles/*/install.sh; do
  [ -x "$installer" ] || continue
  printf '\n--- dotfiles/%s ---\n' "$(basename "$(dirname "$installer")")"
  # Don't let one machine's installer abort the whole bootstrap.
  "$installer" || printf 'warn  %s exited %d\n' "$installer" "$?"
done
