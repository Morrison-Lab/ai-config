#!/usr/bin/env bash
# Summarize every check-run annotation on a commit, for check-pr-fully-clean.py.
#
# Usage: summarize-pr-annotations.sh OWNER/REPO SHA [BASE_SHA]
#
# Prints one tab-separated row per annotation (run id, level, path, first line
# of the message) on stdout. With BASE_SHA, also prints, after a "== not on
# base ==" line, the level/message pairs present on SHA and absent on BASE_SHA,
# so selftest negative controls that also appear on the base branch drop out.
# Last line: the comma-separated run ids to pass to --annotations-read.
#
# lib/annotation_cache.py pages by hand: `gh api --paginate` follows
# numeric-ID Link URLs that the
# cloud-session proxy rejects with HTTP 403 (gha#1432, 2026-11-03).
set -euo pipefail

repo="${1:?usage: $0 OWNER/REPO SHA [BASE_SHA]}"
sha="${2:?usage: $0 OWNER/REPO SHA [BASE_SHA]}"
base="${3:-}"
lib="$(dirname "$0")/lib/annotation_cache.py"

# Completed runs are read through a cache keyed by check-run id
# (ai-config#6032), so re-reading a head, or main's tip once per PR,
# spends no annotation calls. A failed or short read exits non-zero.
annotation_rows() {
  python3 "$lib" rows "$repo" "$1"
}

rows=$(annotation_rows "$sha")
printf '%s\n' "$rows"

if [ -n "$base" ]; then
  echo "== not on base =="
  base_pairs=$(annotation_rows "$base" | cut -f2,4 | sort -u)
  comm -23 <(printf '%s\n' "$rows" | cut -f2,4 | sort -u) <(printf '%s\n' "$base_pairs")
fi

printf '%s\n' "$rows" | cut -f1 | sort -u | paste -sd, -
