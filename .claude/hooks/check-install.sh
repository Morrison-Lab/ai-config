#!/usr/bin/env bash
#
# UserPromptSubmit hook: repair the installed config if anything has replaced a
# symlink into this repo with a real copy.
#
# Why this is NOT in the SessionStart hook, where bootstrap.sh already runs:
# the clobber happens *after* SessionStart. Measured in the container for
# ai-config#755 (all times UTC, same session):
#
#   07:25:00.084  SessionStart hook runs bootstrap.sh, which reports 527
#                 "already linked" and zero skips -- so every skill is a
#                 symlink into the repo at this instant
#   07:25:01.608  ~/.claude/skills is modified, leaving 53 entries as real
#                 directories holding older content
#
# A repair wired into SessionStart would therefore run before the damage and
# report a clean install every time. By the first user prompt, startup has
# settled, so the check runs here instead.
#
# Runs once per session: after the first repair every entry is a symlink, and
# check-install.py classifies a symlink without reading any file, so a repeat
# run would be cheap -- but not free enough to pay a subprocess for on every
# prompt.
#
# Never fatal. A broken check must not take a session down with it.

# -e is deliberately omitted: see "Never fatal" in the header above. A failing
# command here must not abort the hook and take the session's prompt with it.
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$HOOK_DIR/../.." && pwd)"
CHECK="$REPO_DIR/scripts/check-install.py"

[ -f "$CHECK" ] || exit 0

# Claude Code delivers a JSON payload on stdin; session_id keys the guard so a
# resumed or parallel session in the same container still gets one check. The
# fallback keeps the hook working if the payload is absent or unparseable.
payload="$(cat 2>/dev/null || true)"
session_id="$(printf '%s' "$payload" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("session_id",""))' \
  2>/dev/null || true)"

# Known limitation of the `shared` fallback: if two sessions in one container
# both fail to parse a session_id, they share this marker and only the first
# gets repaired. Accepted because the fallback is already the unexpected path,
# and the cost is a missed repair rather than a wrong one -- the next session
# that does parse an id repairs the install for everyone.
marker="${TMPDIR:-/tmp}/ai-config-install-checked-${session_id:-shared}"
[ -e "$marker" ] && exit 0
: > "$marker"

if ! output="$(python3 "$CHECK" --fix 2>&1)"; then
  printf 'warning: ai-config install check failed (see scripts/check-install.py)\n'
  printf '%s\n' "$output" | tail -5
  exit 0
fi

# Quiet when clean, loud when it had to change something. The one-line summary
# always prints, so silence can never be mistaken for "examined nothing" --
# the ambiguity shared/principles/fail-fast.md warns about.
if printf '%s' "$output" | grep -q '^repaired '; then
  printf '%s\n' "$output"
else
  printf '%s' "$output" | grep '^checked ' || true
fi

exit 0
