#!/usr/bin/env bash
# Audit, and optionally apply, a branch ruleset on every Morrison-Lab repo.
#
# For each non-archived, non-fork repository the script finds the template the
# repo was created from (the `template_repository` field GitHub records), reads
# that template's example ruleset(s) from `.github/rulesets/*.json`, and falls
# back to `base.json` beside this script when the repo has no template or the
# template has no example.
# A repo that already has any ruleset is reported "ok" and
# is not touched, because a live ruleset can be stricter than the example.
#
# Default is a dry run that only prints a table.
# `--apply` creates the missing rulesets.
# Applying needs repo admin, so run it from a Remote Control session on a
# machine with an authenticated `gh` (a cloud session gets 403 on repo settings).
#
# Usage: examples/branch-rulesets/apply-all.sh [--apply] [--org ORG] [repo[=template] ...]
#   With repo names given, only those repos are checked.
#   `repo=template` names the template for a repo GitHub records none for
#   (for example `mcs=qwt`).
# Requires: gh, jq.

set -euo pipefail

org="Morrison-Lab"
apply=0
repos=()
declare -A over   # repo=template overrides, for repos GitHub records no template for
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) apply=1 ;;
    --org) shift; org="$1" ;;
    *=*) over["${1%%=*}"]="${1#*=}"; repos+=("${1%%=*}") ;;
    *) repos+=("$1") ;;
  esac
  shift
done

here="$(cd "$(dirname "$0")" && pwd)"

if [ ${#repos[@]} -eq 0 ]; then
  mapfile -t repos < <(gh repo list "$org" -L 500 --no-archived --source \
    --json name --jq '.[].name')
fi

printf '%-28s %-10s %-8s %s\n' repo template status action
for name in "${repos[@]}"; do
  full="$org/$name"
  tmpl=$(gh api "repos/$full" --jq '.template_repository.name // ""' 2>/dev/null || true)
  [[ "$tmpl" =~ ^[A-Za-z0-9._-]+$ ]] || tmpl=""
  tmpl="${over[$name]:-$tmpl}"
  live=$(gh api "repos/$full/rulesets" --jq '[.[].name] | join(",")' 2>/dev/null || echo "?")
  if [ "$live" = "?" ]; then
    printf '%-28s %-10s %-8s %s\n' "$name" "${tmpl:--}" "unreadable" "need admin"
    continue
  fi
  if [ -n "$live" ]; then
    printf '%-28s %-10s %-8s %s\n' "$name" "${tmpl:--}" "ok" "has: $live"
    continue
  fi

  # Pick the example: the template's .github/rulesets/*.json, else base.json.
  src="$here/base.json"
  label="base.json"
  work=$(mktemp -d)
  if [ -n "$tmpl" ]; then
    f=$(gh api "repos/$org/$tmpl/contents/.github/rulesets" \
      --jq '[.[] | select(.name | endswith(".json")) | .name][0] // ""' 2>/dev/null || true)
    if [[ "$f" =~ ^[A-Za-z0-9._-]+[.]json$ ]]; then
      gh api "repos/$org/$tmpl/contents/.github/rulesets/$f" \
        -H 'Accept: application/vnd.github.raw' > "$work/ruleset.json"
      src="$work/ruleset.json"
      label="$tmpl/$f"
    fi
  fi

  if [ "$apply" -eq 1 ]; then
    gh api -X POST "repos/$full/rulesets" --input "$src" >/dev/null
    printf '%-28s %-10s %-8s %s\n' "$name" "${tmpl:--}" "MISSING" "applied $label"
  else
    printf '%-28s %-10s %-8s %s\n' "$name" "${tmpl:--}" "MISSING" "would apply $label"
  fi
  rm -rf "$work"
done
