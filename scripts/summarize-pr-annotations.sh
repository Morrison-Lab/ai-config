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
# Pages by hand: `gh api --paginate` follows numeric-ID Link URLs that the
# cloud-session proxy rejects with HTTP 403 (gha#1432, 2026-11-03).
set -euo pipefail

repo="${1:?usage: $0 OWNER/REPO SHA [BASE_SHA]}"
sha="${2:?usage: $0 OWNER/REPO SHA [BASE_SHA]}"
base="${3:-}"
max_pages=10

annotated_run_ids() {
  local commit="$1" page got
  for page in $(seq 1 "$max_pages"); do
    got=$(gh api "repos/$repo/commits/$commit/check-runs?per_page=100&page=$page" \
      --jq '.check_runs[] | select(.output.annotations_count > 0) | .id')
    [ -z "$got" ] && break
    printf '%s\n' "$got"
  done
}

annotation_rows() {
  local commit="$1" id page out
  for id in $(annotated_run_ids "$commit"); do
    for page in $(seq 1 "$max_pages"); do
      out=$(gh api "repos/$repo/check-runs/$id/annotations?per_page=100&page=$page" \
        --jq ".[] | [\"$id\", .annotation_level, .path, (.message | split(\"\n\")[0] | .[0:140])] | @tsv")
      [ -z "$out" ] && break
      printf '%s\n' "$out"
    done
  done
}

rows=$(annotation_rows "$sha")
printf '%s\n' "$rows"

if [ -n "$base" ]; then
  echo "== not on base =="
  base_pairs=$(annotation_rows "$base" | cut -f2,4 | sort -u)
  comm -23 <(printf '%s\n' "$rows" | cut -f2,4 | sort -u) <(printf '%s\n' "$base_pairs")
fi

printf '%s\n' "$rows" | cut -f1 | sort -u | paste -sd, -
