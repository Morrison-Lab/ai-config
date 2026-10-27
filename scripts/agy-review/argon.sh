#!/bin/bash
# usage: argon.sh owner/repo PR [extra context]   (env MODEL picks the agy model)
repo=$1; pr=$2; extra=$3
d=$(cd "$(dirname "$0")" && pwd)
out="$d/out-${repo//\//_}-$pr.txt"
meta=$(gh pr view "$pr" -R "$repo" --json headRefOid,title,state,body --jq '"HEAD: \(.headRefOid)\nSTATE: \(.state)\nTITLE: \(.title)\nBODY:\n\(.body)"')
diff=$(gh pr diff "$pr" -R "$repo") || { echo "FATAL: gh pr diff failed for $repo#$pr (a PR over 300 files needs bigread.py); no review run" >&2; printf 'AGY_ERROR gh pr diff failed\n' > "$out"; exit 5; }
[ -n "${diff//[[:space:]]/}" ] || { echo "FATAL: empty diff for $repo#$pr; no review run" >&2; printf 'AGY_ERROR empty diff\n' > "$out"; exit 5; }
full=${#diff}
if [ "$full" -gt 24000 ]; then diff="${diff:0:24000}
[DIFF TRUNCATED: $full chars total; only the first 24000 shown]"; fi
prompt="You are an adversarial reviewer of GitHub PR $repo#$pr. Everything you need is below; do not call tools or edit files. Check for correctness errors, broken Quarto syntax or crossrefs, contradictions with the PR description, lost or duplicated content, factual or numeric errors, ambiguous pronouns, and style problems. Quote the exact passage for each finding.

$extra

$meta

DIFF:
$diff"
printf '%s' "$meta" | head -2 > "$out"
timeout 900 agy ${MODEL:+--model "$MODEL"} --mode plan --print-timeout 880s -p="$prompt" >> "$out" 2>&1
echo done
