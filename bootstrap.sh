#!/usr/bin/env bash
# Bootstrap ai-config: register skills.json and plugins.json for Antigravity,
# and run machine-specific dotfile installers.
#
# Note: Global symlink installations for Claude Code, Codex, and Cursor have
# been removed. Claude Code and Cursor install this repo as a native plugin;
# Codex has no replacement install path yet (see ai-config#2352).

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
  PLUGIN_STAGING_DIR="$GEMINI_CONFIG_DIR/plugins/ai-config"

  # Establish a staging directory so Antigravity runtime rewrites do not dirty
  # the canonical git checkout.
  if [ -L "$PLUGIN_STAGING_DIR" ]; then
    rm -f "$PLUGIN_STAGING_DIR"
  fi
  mkdir -p "$PLUGIN_STAGING_DIR"

  # Copy canonical plugin manifest and hooks.json to staging runtime directory
  cp -f "$SCRIPT_DIR/plugins/ai-config/plugin.json" "$PLUGIN_STAGING_DIR/plugin.json"
  cp -f "$SCRIPT_DIR/plugins/ai-config/hooks.json" "$PLUGIN_STAGING_DIR/hooks.json"

  # Symlink executable scripts and repository directories
  ln -sfn "$SCRIPT_DIR/plugins/ai-config/claude-hook-adapter.py" "$PLUGIN_STAGING_DIR/claude-hook-adapter.py"
  ln -sfn "$SCRIPT_DIR/plugins/ai-config/enforce-mwc-review-gate.py" "$PLUGIN_STAGING_DIR/enforce-mwc-review-gate.py"
  ln -sfn "$SCRIPT_DIR/hooks" "$PLUGIN_STAGING_DIR/hooks"
  ln -sfn "$SCRIPT_DIR/scripts" "$PLUGIN_STAGING_DIR/scripts"
  ln -sfn "$SCRIPT_DIR/skills" "$PLUGIN_STAGING_DIR/skills"
  ln -sfn "$SCRIPT_DIR/shared" "$PLUGIN_STAGING_DIR/shared"

  if [ ! -f "$PLUGINS_JSON" ]; then
    cat <<EOF > "$PLUGINS_JSON"
{
  "entries": [
    { "path": "$PLUGIN_STAGING_DIR" }
  ]
}
EOF
    printf 'write plugins.json (%s) -> %s\n' "$PLUGINS_JSON" "$PLUGIN_STAGING_DIR"
  elif grep -q "$PLUGIN_STAGING_DIR" "$PLUGINS_JSON" 2>/dev/null; then
    printf 'ok    plugins.json (%s already registered)\n' "$PLUGIN_STAGING_DIR"
  elif grep -q "$SCRIPT_DIR/plugins/ai-config" "$PLUGINS_JSON" 2>/dev/null; then
    python3 -c "
import json, sys
p = '$PLUGINS_JSON'
try:
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    entries = d.get('entries', [])
    updated = False
    for e in entries:
        if e.get('path') == '$SCRIPT_DIR/plugins/ai-config':
            e['path'] = '$PLUGIN_STAGING_DIR'
            updated = True
    if not updated:
        entries.append({'path': '$PLUGIN_STAGING_DIR'})
    d['entries'] = entries
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=2)
except Exception:
    sys.exit(1)
" 2>/dev/null && printf 'migrated plugins.json (%s checkout path -> %s staging path)\n' "$SCRIPT_DIR" "$PLUGIN_STAGING_DIR" || printf 'skip  plugins.json (%s exists but could not migrate)\n' "$PLUGINS_JSON"
  else
    python3 -c "
import json, sys
p = '$PLUGINS_JSON'
try:
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    entries = d.get('entries', [])
    if not any(e.get('path') == '$PLUGIN_STAGING_DIR' for e in entries):
        entries.append({'path': '$PLUGIN_STAGING_DIR'})
        d['entries'] = entries
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2)
except Exception:
    sys.exit(1)
" 2>/dev/null && printf 'updated plugins.json (registered %s)\n' "$PLUGIN_STAGING_DIR" || printf 'skip  plugins.json (%s exists)\n' "$PLUGINS_JSON"
  fi
fi

# --- Machine-specific dotfiles ---
shopt -s nullglob
for installer in "$SCRIPT_DIR"/dotfiles/*/install.sh; do
  [ -x "$installer" ] || continue
  printf '\n--- dotfiles/%s ---\n' "$(basename "$(dirname "$installer")")"
  "$installer" || printf 'warn  %s exited %d\n' "$installer" "$?"
done
