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
CURSOR_DIR="${CURSOR_HOME:-$HOME/.cursor}"

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
    # cursor-rules/ is linked into ~/.cursor/rules below, not ~/.claude.
    # plugins/ is an Antigravity plugin manifest bundle linked into ~/.gemini/config/plugins below, not ~/.claude.
    # dotfiles/ is machine-specific shell tooling installed into ~/bin and
    # friends by its own per-machine installer at the bottom of this script.
    .git|node_modules|references|codex-skills|cursor-rules|dotfiles|plugins) continue ;;

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

# --- Codex skill wrappers: plugin and symlink installs are alternatives ---
if [ -d "$SCRIPT_DIR/codex-skills" ]; then
  printf '\n--- Codex skill wrappers ---\n'
  mkdir -p "$CODEX_DIR/skills"
  if python3 "$SCRIPT_DIR/scripts/codex-plugin-enabled.py" \
      --config "$CODEX_DIR/config.toml"; then
    # A Codex plugin supplies the same catalog under its namespace. Leaving
    # these bare wrapper links in place doubles every entry in Codex's skill
    # routing prompt. Remove only links that this checkout created; never
    # touch real paths or links owned by another checkout.
    removed=0
    for src in "$SCRIPT_DIR"/codex-skills/*; do
      [ -d "$src" ] || continue
      dest="$CODEX_DIR/skills/$(basename "$src")"
      if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
        rm "$dest"
        removed=$((removed + 1))
      fi
    done
    printf 'skip  Codex wrappers (ai-config plugin is enabled; removed %d stale wrapper link(s))\n' "$removed"
  else
    for src in "$SCRIPT_DIR"/codex-skills/*; do
      [ -d "$src" ] || continue
      link_one "$src" "$CODEX_DIR/skills/$(basename "$src")"
    done
  fi
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
    # Derive the alias set rather than hard-coding it. An alias skill declares
    # `description: "→ ..."` (or `Alias for ...`) in its frontmatter and is a thin pointer to
    # its canonical skill, so the set is enumerable from the repo itself. A
    # hand-maintained list drifts silently in both directions: a newly added
    # alias eats budget until the banner returns, and a skill that stops being
    # an alias disappears from Antigravity entirely.
    ALIAS_PATTERNS=""
    for _skill_dir in "$SCRIPT_DIR"/skills/*/; do
      [ -f "$_skill_dir/SKILL.md" ] || continue
      _skill_name=$(basename "$_skill_dir")
      if head -8 "$_skill_dir/SKILL.md" | grep -qiE '^description: *"?([→]|->|Alias for\b)'; then
        [ -z "$ALIAS_PATTERNS" ] || ALIAS_PATTERNS="$ALIAS_PATTERNS,
"
        ALIAS_PATTERNS="$ALIAS_PATTERNS$(printf '        "^%s$"' "$_skill_name")"
      fi
    done
    cat <<EOF > "$SKILLS_JSON"
{
  "entries": [
    {
      "path": "$GEMINI_DIR/skills",
      "exclude": [
$ALIAS_PATTERNS
      ]
    }
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

if [ -d "$SCRIPT_DIR/plugins/ai-config" ]; then
  printf '\n--- Antigravity plugins ---\n'
  mkdir -p "$GEMINI_CONFIG_DIR/plugins"
  link_one "$SCRIPT_DIR/plugins/ai-config" "$GEMINI_CONFIG_DIR/plugins/ai-config"
  PLUGINS_JSON="$GEMINI_CONFIG_DIR/plugins.json"
  if [ ! -f "$PLUGINS_JSON" ]; then
    cat <<EOF > "$PLUGINS_JSON"
{
  "entries": [
    { "path": "$GEMINI_CONFIG_DIR/plugins/ai-config" }
  ]
}
EOF
    printf 'write plugins.json (%s) -> %s/plugins/ai-config\n' "$PLUGINS_JSON" "$GEMINI_CONFIG_DIR"
  elif grep -q "$GEMINI_CONFIG_DIR/plugins/ai-config" "$PLUGINS_JSON" 2>/dev/null; then
    printf 'ok    plugins.json (%s/plugins/ai-config already registered)\n' "$GEMINI_CONFIG_DIR"
  else
    printf 'skip  plugins.json (%s exists but does not register %s/plugins/ai-config)\n' "$PLUGINS_JSON" "$GEMINI_CONFIG_DIR"
  fi
fi

if [ -f "$SCRIPT_DIR/GEMINI.md" ]; then
  mkdir -p "$GEMINI_DIR" "$GEMINI_CONFIG_DIR"
  link_one "$SCRIPT_DIR/GEMINI.md" "$GEMINI_DIR/GEMINI.md"
  link_one "$SCRIPT_DIR/GEMINI.md" "$GEMINI_CONFIG_DIR/GEMINI.md"
fi

if [ -f "$SCRIPT_DIR/AGENTS.md" ]; then
  mkdir -p "$GEMINI_DIR" "$GEMINI_CONFIG_DIR" "$CODEX_DIR"
  link_one "$SCRIPT_DIR/AGENTS.md" "$GEMINI_DIR/AGENTS.md"
  link_one "$SCRIPT_DIR/AGENTS.md" "$GEMINI_CONFIG_DIR/AGENTS.md"
  link_one "$SCRIPT_DIR/AGENTS.md" "$CODEX_DIR/AGENTS.md"
fi

# --- Cursor rules: plugin or ~/.cursor/rules, not two ---
# User-global rules live in cursor-rules/ (every workspace). Project rules
# live in .cursor/rules/ (this repo as a Cursor workspace) and are not
# copied here --- 002-use-repo-skills.mdc is this-repo-only.
# A marketplace/local Cursor plugin already ships cursor-rules via
# .cursor-plugin/plugin.json, so linking ~/.cursor/rules on top doubles
# the catalog (same class as ai-config#1409 / #2291). Claude skill
# installs do not ship these rules, so they are not a skip here.
if [ -d "$SCRIPT_DIR/cursor-rules" ]; then
  printf '\n--- Cursor rules ---\n'
  skip_cursor_rules=""
  if command -v python3 >/dev/null 2>&1; then
    set +e
    skip_cursor_rules="$(python3 "$SCRIPT_DIR/scripts/cursor-plugin-enabled.py" \
      --rules \
      --cursor-dir "$CURSOR_DIR" \
      --repo-root "$SCRIPT_DIR")"
    skip_cursor_rc=$?
    set -e
    if [ "$skip_cursor_rc" -eq 0 ]; then
      # Same care as the skills skip: remove leftover ~/.cursor/rules
      # symlinks that resolve into this checkout or a sibling worktree.
      # Never clobber a real file or a foreign link.
      removed=0
      if [ -d "$CURSOR_DIR/rules" ]; then
        stacked_paths="$(python3 "$SCRIPT_DIR/scripts/cursor-plugin-enabled.py" \
          --print-stacked-rules \
          --cursor-dir "$CURSOR_DIR" \
          --repo-root "$SCRIPT_DIR")"
        while IFS= read -r dest; do
          [ -n "$dest" ] || continue
          if [ -L "$dest" ]; then
            rm "$dest"
            removed=$((removed + 1))
          fi
        done <<EOF
$stacked_paths
EOF
      fi
      printf 'skip  Cursor rules (%s; removed %d stale rule link(s))\n' \
        "$skip_cursor_rules" "$removed"
    else
      skip_cursor_rules=""
    fi
  fi
  if [ -z "$skip_cursor_rules" ]; then
    mkdir -p "$CURSOR_DIR/rules"
    for src in "$SCRIPT_DIR"/cursor-rules/*; do
      [ -f "$src" ] || [ -d "$src" ] || continue
      link_one "$src" "$CURSOR_DIR/rules/$(basename "$src")"
    done
  fi
fi

# --- Cursor skills: plugin or ~/.claude/skills or ~/.cursor/skills, not two ---
# Cursor discovers ~/.claude/skills for compatibility, so a live Claude
# symlink install already serves this catalog. A marketplace/local Cursor
# plugin does too. Linking ~/.cursor/skills on top of either doubles the
# listing (ai-config#1409).
if [ -d "$SCRIPT_DIR/skills" ]; then
  printf '\n--- Cursor skills ---\n'
  skip_cursor_skills=""
  if command -v python3 >/dev/null 2>&1; then
    set +e
    skip_cursor_skills="$(python3 "$SCRIPT_DIR/scripts/cursor-plugin-enabled.py" \
      --cursor-dir "$CURSOR_DIR" \
      --claude-dir "$CLAUDE_DIR" \
      --repo-root "$SCRIPT_DIR")"
    skip_cursor_rc=$?
    set -e
    if [ "$skip_cursor_rc" -eq 0 ]; then
      # Same as the Codex plugin path: a skip that leaves this repo's
      # bare links in place stacks two catalogs (ai-config#1409). Remove
      # any ~/.cursor/skills symlink that resolves into this checkout or
      # a sibling worktree, not only an exact readlink of $SCRIPT_DIR.
      removed=0
      if [ -d "$CURSOR_DIR/skills" ]; then
        stacked_paths="$(python3 "$SCRIPT_DIR/scripts/cursor-plugin-enabled.py" \
          --print-stacked \
          --cursor-dir "$CURSOR_DIR" \
          --repo-root "$SCRIPT_DIR")"
        while IFS= read -r dest; do
          [ -n "$dest" ] || continue
          if [ -L "$dest" ]; then
            rm "$dest"
            removed=$((removed + 1))
          fi
        done <<EOF
$stacked_paths
EOF
      fi
      printf 'skip  Cursor skills (%s; removed %d stale skill link(s))\n' \
        "$skip_cursor_skills" "$removed"
    else
      skip_cursor_skills=""
    fi
  fi
  if [ -z "$skip_cursor_skills" ]; then
    mkdir -p "$CURSOR_DIR/skills"
    for src in "$SCRIPT_DIR"/skills/*; do
      [ -d "$src" ] || continue
      link_one "$src" "$CURSOR_DIR/skills/$(basename "$src")"
    done
    if [ -d "$SCRIPT_DIR/shared/sembr-skills/skills" ]; then
      for src in "$SCRIPT_DIR"/shared/sembr-skills/skills/*; do
        [ -d "$src" ] || continue
        link_one "$src" "$CURSOR_DIR/skills/$(basename "$src")"
      done
    else
      printf 'skip  sembr-skills (submodule not checked out -- run: git submodule update --init -- shared/sembr-skills)\n'
    fi
  fi
fi



# --- Stacked-install warning ---
# The symlink install this script just made and a marketplace plugin install
# are ALTERNATIVES, not complements: both serve the same skills, so a machine
# with an `ai-config@*` plugin enabled lists every skill twice and blows the
# skill-listing context budget (ai-config#1409). Advisory and best-effort --
# a machine without python3 skips it rather than failing the bootstrap.
if command -v python3 >/dev/null 2>&1; then
  printf '\n--- plugin-overlap check ---\n'
  python3 "$SCRIPT_DIR/scripts/check-plugin-overlap.py" \
    --consumer-dir "$CLAUDE_DIR" --repo-root "$SCRIPT_DIR" \
    || printf 'warn  check-plugin-overlap.py exited %d\n' "$?"
else
  printf '\nskip  plugin-overlap check (python3 not found)\n'
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
