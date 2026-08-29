#!/usr/bin/env bash
# Upload staged skills to the Anthropic Skills API (POST /v1/skills).
# Idempotent by VERSIONING, not by skipping: a skill whose name already
# exists in the workspace gets a new version (POST /v1/skills/{id}/versions)
# rather than being left frozen at whatever revision it had when first
# uploaded (ai-config#769).
#
# Usage:
#   ANTHROPIC_API_KEY=sk-ant-... ./upload_skills.sh
#
# Env:
#   ANTHROPIC_API_KEY  (required) a *workspace* API key — custom skills are workspace-scoped
#   STAGE              staging dir of <name>/SKILL.md folders (default /tmp/skill_upload)
#   MAP                output TSV of name -> skill_id (default ./skill_ids.tsv)
set -euo pipefail

: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY (a workspace API key) before running}"
API="https://api.anthropic.com/v1/skills"
STAGE="${STAGE:-/tmp/skill_upload}"
MAP="${MAP:-skill_ids.tsv}"
HDRS=(-H "x-api-key: $ANTHROPIC_API_KEY"
      -H "anthropic-version: 2023-06-01"
      -H "anthropic-beta: skills-2025-10-02")

[ -d "$STAGE" ] || { echo "No staging dir: $STAGE" >&2; exit 1; }
: > "$MAP"

# Pull existing skills once, matched on `display_name` -- the field the
# Skills API docs (platform.claude.com/docs/en/api/skills, checked
# 2026-08-29) use throughout the Skill object for both POST /v1/skills and
# GET /v1/skills. The API's own POST /v1/skills body parameter is also
# `display_name`, not `display_title`: this script previously used
# `display_title` on both sides of the match, which as far as we can tell
# means the create call always sent an unrecognized field (silently
# ignored, since the API accepted the upload) and the lookup below always
# matched nothing -- so every "existing skill" read as new, on every run.
# Not independently verified against a live call (no workspace key
# available in this session, per ai-config#769's own caveat); if this is
# wrong, both the -F field below and the jq selector need the same fix
# together, or the lookup silently breaks again.
resp="$(curl -sS -w '\n%{http_code}' "${HDRS[@]}" "$API" 2>/dev/null || true)"
http_code="$(tail -n1 <<<"$resp")"
existing="$(sed '$d' <<<"$resp")"
case "$http_code" in
  200) : ;;
  401|403) echo "ERROR: Skills API auth failed (HTTP $http_code) — check ANTHROPIC_API_KEY (must be a workspace key)" >&2; exit 1 ;;
  "") echo "ERROR: could not reach Skills API at $API" >&2; exit 1 ;;
  *) echo "WARN: unexpected HTTP $http_code listing existing skills; treating workspace as empty" >&2; existing='{"data":[]}' ;;
esac
existing="${existing:-{\"data\":[]}}"

created=0 versioned=0 failed=0
for dir in "$STAGE"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || { echo "WARN no SKILL.md: $name"; continue; }

  if id="$(jq -er --arg n "$name" '.data[]? | select(.display_name==$n) | .id' <<<"$existing" 2>/dev/null | head -1)" && [ -n "$id" ]; then
    resp="$(curl -sS -X POST "$API/$id/versions" "${HDRS[@]}" \
              -F "files[]=@${dir}SKILL.md;filename=${name}/SKILL.md")"
    ver_id="$(jq -r '.id // empty' <<<"$resp")"
    if [ -n "$ver_id" ]; then
      echo "versioned: $name -> $id (version $ver_id)"
      printf '%s\t%s\tVERSIONED\n' "$name" "$id" >> "$MAP"
      versioned=$((versioned+1))
    else
      echo "FAILED (version): $name"
      jq . <<<"$resp" 2>/dev/null || echo "$resp"
      printf '%s\t%s\tFAILED\n' "$name" "$id" >> "$MAP"
      failed=$((failed+1))
    fi
    continue
  fi

  resp="$(curl -sS -X POST "$API" "${HDRS[@]}" \
            -F "display_name=$name" \
            -F "files[]=@${dir}SKILL.md;filename=${name}/SKILL.md")"
  id="$(jq -r '.id // empty' <<<"$resp")"
  if [ -n "$id" ]; then
    echo "created: $name -> $id"
    printf '%s\t%s\tCREATED\n' "$name" "$id" >> "$MAP"
    created=$((created+1))
  else
    echo "FAILED: $name"
    jq . <<<"$resp" 2>/dev/null || echo "$resp"
    printf '%s\t-\tFAILED\n' "$name" >> "$MAP"
    failed=$((failed+1))
  fi
done

echo "----"
echo "created=$created versioned=$versioned failed=$failed  (map: $MAP)"
