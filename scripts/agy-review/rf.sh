#!/bin/bash
# usage: rf.sh owner/repo pr "extra prompt"
# Tries agy models in order (Gemini Argon first now that its quota is back, then Opus, then GPT-OSS),
# posts the first read that is a real review: a verdict as last line, no agy error, not a plan.
d=$(cd "$(dirname "$0")" && pwd); cd "$d"
slug=$1; pr=$2; extra=$3
tail_note=" Do not write a plan, do not create artifacts, do not ask questions or request approval: answer in one pass with the review itself. List every finding, wording and style nits included, each in at most 3 lines with the quoted passage. Keep the answer under 3000 characters. The last line must be exactly VERDICT: FINDINGS if you list any finding at all, or exactly VERDICT: CLEAN if there is none (then say only that nothing was found)."
f="out-${slug//\//_}-$pr.txt"
real_read() {
  grep -q '^VERDICT: ' "$f" || return 1
  grep -q -E 'AGY_ERROR|RESOURCE_EXHAUSTED' "$f" && return 1
  body=$(awk 'NR>2' "$f")
  if grep -q '^VERDICT: FINDINGS' "$f"; then [ "${#body}" -ge 200 ] || return 1; else [ "${#body}" -ge 30 ] || return 1; fi
  echo "$body" | grep -q -i -E 'awaiting (your )?(approval|confirmation)|please (approve|confirm)|implementation plan|should I proceed|do you want me to|let me know (if|whether)' && return 1
  last=$(echo "$body" | grep -v '^\s*$' | grep -v -E '^\*\*(Stopping Point|Status)' | tail -1)
  case "$last" in "VERDICT: CLEAN"|"VERDICT: FINDINGS") return 0;; esac
  return 1
}
for spec in "gemini-4-argon-medium|Argon: Gemini 4 Argon (Medium) via Antigravity \`agy\` 1.3.5" "claude-opus-5-5-medium|Claude Opus 5.5 via Antigravity \`agy\` 1.3.5, standing in" "gpt-oss-120b-medium|GPT-OSS 120B via Antigravity \`agy\` 1.3.5"; do
  model=${spec%%|*}; name=${spec#*|}
  MODEL=$model bash argon.sh "$slug" "$pr" "$extra$tail_note" >/dev/null 2>&1
  if real_read; then
    post_out=$(MODEL_LABEL="$name" bash post.sh "$slug" "$pr"); post_rc=$?
    echo "$post_out"
    if [ "$post_rc" -eq 4 ]; then echo "model $model read refused by post.sh (notes or truncated diff); trying the next model"; continue; fi
    [ "$post_rc" -eq 0 ] || { echo "post.sh failed (exit $post_rc) for $slug#$pr; read not posted"; exit 1; }
    case "$post_out" in SKIP*) echo "read not posted for $slug#$pr"; exit 2;; esac
    echo "model=$model head=$(sed -n 1p $f | cut -c7-13) verdict=$(grep -o '^VERDICT: [A-Z]*' $f | tail -1)"
    exit 0
  fi
  echo "model $model gave no real review: $(grep -o 'short_error[^,]*' $f | head -1)"
done
echo "ALL MODELS FAILED for $slug#$pr"
exit 1
