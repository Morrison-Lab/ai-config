#!/usr/bin/env bash
# Upload staged skills to the Anthropic Skills API (POST /v1/skills).
# Idempotent with change detection: only creates or versions skills whose
# content has changed since the last upload (ai-config#2596, ai-config#769).
# Unchanged skills are skipped, and deleted skills previously managed by this
# script are pruned from the workspace.
#
# Usage:
#   ANTHROPIC_API_KEY=sk-ant-... ./upload_skills.sh
#
# Env:
#   ANTHROPIC_API_KEY  (required) a *workspace* API key — custom skills are workspace-scoped
#   STAGE              staging dir of <name>/SKILL.md folders (default: skills or /tmp/skill_upload)
#   MAP                output TSV of name -> skill_id -> status (default ./skill_ids.tsv)
#   STATE              JSON cache file tracking managed skills and hashes (default ./.skill_state.json)
#   PRUNE              prune deleted managed skills (1 to enable [default], 0 to disable)
#   FORCE              force upload of all skills even if unchanged (1 to enable, 0 [default])
set -euo pipefail

: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY (a workspace API key) before running}"
API="${API:-https://api.anthropic.com/v1/skills}"

if [ -z "${STAGE:-}" ]; then
  if [ -d "skills" ]; then
    STAGE="skills"
  else
    STAGE="/tmp/skill_upload"
  fi
fi

MAP="${MAP:-skill_ids.tsv}"
STATE="${STATE:-.skill_state.json}"
PRUNE="${PRUNE:-1}"
FORCE="${FORCE:-0}"

HDRS=(-H "x-api-key: $ANTHROPIC_API_KEY"
      -H "anthropic-version: 2023-06-01"
      -H "anthropic-beta: skills-2025-10-02")

[ -d "$STAGE" ] || { echo "No staging dir: $STAGE" >&2; exit 1; }
: > "$MAP"

# Helper to compute SHA-256 hash of a directory deterministically.
hash_dir() {
  local d="$1"
  (
    cd "$d"
    find . -type f ! -name ".*" | LC_ALL=C sort | while IFS= read -r f; do
      printf '%s\0' "$f"
      cat "$f"
    done | if command -v sha256sum >/dev/null 2>&1; then sha256sum; else shasum -a 256; fi | awk '{print $1}'
  )
}

# Initialize or load state JSON
STATE_TEMP="$(mktemp "${TMPDIR:-/tmp}/skill_state.XXXXXX.json")"
trap 'rm -f "$STATE_TEMP"' EXIT

if [ -f "$STATE" ] && jq -e '.skills' "$STATE" >/dev/null 2>&1; then
  cp "$STATE" "$STATE_TEMP"
else
  echo '{"version":1,"skills":{}}' > "$STATE_TEMP"
fi

# Pull existing skills once, matched on `display_name` -- the field the
# Skills API docs (platform.claude.com/docs/en/api/skills, checked
# 2026-08-29) use throughout the Skill object for both POST /v1/skills and
# GET /v1/skills.
resp="$(curl -sS -w '\n%{http_code}' "${HDRS[@]}" "$API" 2>/dev/null || true)"
http_code="$(tail -n1 <<<"$resp")"
existing="$(sed '$d' <<<"$resp")"
case "$http_code" in
  200) : ;;
  401|403) echo "ERROR: Skills API auth failed (HTTP $http_code) — check ANTHROPIC_API_KEY (must be a workspace key)" >&2; exit 1 ;;
  "") echo "ERROR: could not reach Skills API at $API" >&2; exit 1 ;;
  *) echo "WARN: unexpected HTTP $http_code listing existing skills; treating workspace as empty" >&2; existing='{"data":[]}' ;;
esac
[ -n "$existing" ] || existing='{"data":[]}'

created=0 versioned=0 unchanged=0 deleted=0 failed=0
staged_names=()

for dir in "$STAGE"/*/; do
  [ -d "$dir" ] || continue
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || { echo "WARN no SKILL.md: $name"; continue; }

  staged_names+=("$name")
  cur_hash="$(hash_dir "$dir")"

  # Collect all files in the skill directory
  file_args=()
  while IFS= read -r f; do
    rel="${f#$dir}"
    rel="${rel#/}"
    file_args+=(-F "files[]=@${f};filename=${name}/${rel}")
  done < <(find "$dir" -type f ! -name ".*" | LC_ALL=C sort)

  if id="$(jq -er --arg n "$name" '.data[]? | select(.display_name==$n) | .id' <<<"$existing" 2>/dev/null | head -1)" && [ -n "$id" ]; then
    cached_hash="$(jq -r --arg n "$name" '.skills[$n].hash // empty' "$STATE_TEMP" 2>/dev/null || true)"
    cached_id="$(jq -r --arg n "$name" '.skills[$n].id // empty' "$STATE_TEMP" 2>/dev/null || true)"

    if [ "$FORCE" -eq 0 ] && [ "$cached_hash" = "$cur_hash" ] && [ "$cached_id" = "$id" ]; then
      echo "unchanged: $name -> $id (cached)"
      printf '%s\t%s\tUNCHANGED\n' "$name" "$id" >> "$MAP"
      unchanged=$((unchanged+1))
      continue
    fi

    resp="$(curl -sS -X POST "$API/$id/versions" "${HDRS[@]}" "${file_args[@]}")"
    ver_id="$(jq -r '.id // empty' <<<"$resp")"
    if [ -n "$ver_id" ]; then
      echo "versioned: $name -> $id (version $ver_id)"
      printf '%s\t%s\tVERSIONED\n' "$name" "$id" >> "$MAP"
      now="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")"
      jq --arg n "$name" --arg id "$id" --arg h "$cur_hash" --arg v "$ver_id" --arg t "$now" \
        '.skills[$n] = {id: $id, hash: $h, version_id: $v, updated_at: $t}' "$STATE_TEMP" > "${STATE_TEMP}.new" && mv "${STATE_TEMP}.new" "$STATE_TEMP"
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
            "${file_args[@]}")"
  id="$(jq -r '.id // empty' <<<"$resp")"
  if [ -n "$id" ]; then
    ver_id="$(jq -r '.latest_version_id // .latest_version // empty' <<<"$resp")"
    echo "created: $name -> $id"
    printf '%s\t%s\tCREATED\n' "$name" "$id" >> "$MAP"
    now="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")"
    jq --arg n "$name" --arg id "$id" --arg h "$cur_hash" --arg v "$ver_id" --arg t "$now" \
      '.skills[$n] = {id: $id, hash: $h, version_id: $v, updated_at: $t}' "$STATE_TEMP" > "${STATE_TEMP}.new" && mv "${STATE_TEMP}.new" "$STATE_TEMP"
    created=$((created+1))
  else
    echo "FAILED: $name"
    jq . <<<"$resp" 2>/dev/null || echo "$resp"
    printf '%s\t-\tFAILED\n' "$name" >> "$MAP"
    failed=$((failed+1))
  fi
done

# Deletion propagation: prune skills that were previously managed by this repo/script
# but are no longer in STAGE.
if [ "$PRUNE" -eq 1 ]; then
  cached_names="$(jq -r '.skills | keys[]' "$STATE_TEMP" 2>/dev/null || true)"
  for c_name in $cached_names; do
    [ -n "$c_name" ] || continue
    is_staged=0
    for s_name in "${staged_names[@]}"; do
      if [ "$s_name" = "$c_name" ]; then
        is_staged=1
        break
      fi
    done

    if [ "$is_staged" -eq 0 ]; then
      c_id="$(jq -r --arg n "$c_name" '.skills[$n].id // empty' "$STATE_TEMP" 2>/dev/null || true)"
      if [ -n "$c_id" ]; then
        if jq -e --arg id "$c_id" '.data[]? | select(.id==$id)' <<<"$existing" >/dev/null 2>&1; then
          del_resp="$(curl -sS -w '\n%{http_code}' -X DELETE "${HDRS[@]}" "$API/$c_id" 2>/dev/null || true)"
          del_code="$(tail -n1 <<<"$del_resp")"
          case "$del_code" in
            200|202|204)
              echo "deleted: $c_name -> $c_id"
              printf '%s\t%s\tDELETED\n' "$c_name" "$c_id" >> "$MAP"
              deleted=$((deleted+1))
              jq --arg n "$c_name" 'del(.skills[$n])' "$STATE_TEMP" > "${STATE_TEMP}.new" && mv "${STATE_TEMP}.new" "$STATE_TEMP"
              ;;
            404)
              echo "deleted (already absent remotely): $c_name -> $c_id"
              jq --arg n "$c_name" 'del(.skills[$n])' "$STATE_TEMP" > "${STATE_TEMP}.new" && mv "${STATE_TEMP}.new" "$STATE_TEMP"
              ;;
            *)
              echo "FAILED (delete): $c_name -> $c_id (HTTP $del_code)"
              printf '%s\t%s\tFAILED_DELETE\n' "$c_name" "$c_id" >> "$MAP"
              failed=$((failed+1))
              ;;
          esac
        else
          jq --arg n "$c_name" 'del(.skills[$n])' "$STATE_TEMP" > "${STATE_TEMP}.new" && mv "${STATE_TEMP}.new" "$STATE_TEMP"
        fi
      else
        jq --arg n "$c_name" 'del(.skills[$n])' "$STATE_TEMP" > "${STATE_TEMP}.new" && mv "${STATE_TEMP}.new" "$STATE_TEMP"
      fi
    fi
  done
fi

# Save state
cp "$STATE_TEMP" "$STATE"

echo "----"
echo "created=$created versioned=$versioned unchanged=$unchanged deleted=$deleted failed=$failed  (map: $MAP)"

if [ "$failed" -gt 0 ]; then
  exit 1
fi

