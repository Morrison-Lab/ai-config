#!/usr/bin/env bash
# Bootstrap ai-config: register skills.json and plugins.json for Antigravity,
# and run machine-specific dotfile installers.
#
# Note: Global symlink installations for Claude Code, Codex, and Cursor have
# been removed in favor of native plugin configuration architectures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEMINI_DIR="${GEMINI_HOME:-$HOME/.gemini}"
GEMINI_CONFIG_DIR="${GEMINI_CONFIG_HOME:-$GEMINI_DIR/config}"

# Note: scripts/lib/link-one.sh (the symlink helper) is not sourced here.
# Nothing below uses it -- each dotfiles/*/install.sh that needs it sources
# its own copy with its own LINK_ONE_FIX_HINT, since a collision at
# e.g. ~/bin needs different advice than one under ~/.gemini would.

# --- Gemini CLI & Antigravity skills: register skills.json ---
if [ -d "$SCRIPT_DIR/skills" ]; then
  printf '\n--- Gemini CLI & Antigravity skills ---\n'
  mkdir -p "$GEMINI_CONFIG_DIR"
  SKILLS_JSON="$GEMINI_CONFIG_DIR/skills.json"
  if [ ! -f "$SKILLS_JSON" ]; then
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
      "path": "$SCRIPT_DIR/skills",
      "exclude": [
$ALIAS_PATTERNS
      ]
    }
  ]
}
EOF
    printf 'write skills.json (%s) -> %s/skills\n' "$SKILLS_JSON" "$SCRIPT_DIR"
  elif grep -q "$SCRIPT_DIR/skills" "$SKILLS_JSON" 2>/dev/null; then
    printf 'ok    skills.json (%s/skills already registered)\n' "$SCRIPT_DIR"
  elif grep -q "$GEMINI_DIR/skills" "$SKILLS_JSON" 2>/dev/null; then
    printf 'skip  skills.json (%s still names the old %s/skills symlink destination -- delete it and rerun to migrate to the checkout path)\n' "$SKILLS_JSON" "$GEMINI_DIR"
  else
    printf 'skip  skills.json (%s exists but does not register %s/skills)\n' "$SKILLS_JSON" "$SCRIPT_DIR"
  fi
fi

if [ -d "$SCRIPT_DIR/plugins/ai-config" ]; then
  printf '\n--- Antigravity plugins ---\n'
  mkdir -p "$GEMINI_CONFIG_DIR"
  PLUGINS_JSON="$GEMINI_CONFIG_DIR/plugins.json"
  if [ ! -f "$PLUGINS_JSON" ]; then
    cat <<EOF > "$PLUGINS_JSON"
{
  "entries": [
    { "path": "$SCRIPT_DIR/plugins/ai-config" }
  ]
}
EOF
    printf 'write plugins.json (%s) -> %s/plugins/ai-config\n' "$PLUGINS_JSON" "$SCRIPT_DIR"
  elif grep -q "$SCRIPT_DIR/plugins/ai-config" "$PLUGINS_JSON" 2>/dev/null; then
    printf 'ok    plugins.json (%s/plugins/ai-config already registered)\n' "$SCRIPT_DIR"
  elif grep -q "$GEMINI_CONFIG_DIR/plugins/ai-config" "$PLUGINS_JSON" 2>/dev/null; then
    printf 'skip  plugins.json (%s still names the old %s/plugins/ai-config symlink destination -- delete it and rerun to migrate to the checkout path)\n' "$PLUGINS_JSON" "$GEMINI_CONFIG_DIR"
  else
    printf 'skip  plugins.json (%s exists but does not register %s/plugins/ai-config)\n' "$PLUGINS_JSON" "$SCRIPT_DIR"
  fi
fi

# --- Machine-specific dotfiles ---
shopt -s nullglob
for installer in "$SCRIPT_DIR"/dotfiles/*/install.sh; do
  [ -x "$installer" ] || continue
  printf '\n--- dotfiles/%s ---\n' "$(basename "$(dirname "$installer")")"
  "$installer" || printf 'warn  %s exited %d\n' "$installer" "$?"
done
