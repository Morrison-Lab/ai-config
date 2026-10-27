#!/bin/bash
# usage: post.sh owner/repo PR  -- posts the agy output as a structured PR comment (open PRs only)
# Format: agent marker, review heading naming the sha, Verdict heading, VERDICT line, Reviewed-Commit line.
repo=$1; pr=$2
d=$(cd "$(dirname "$0")" && pwd)
f="$d/out-${repo//\//_}-$pr.txt"
[ -e "$d/skip-${repo//\//_}-$pr" ] && { echo "SKIP $repo#$pr (dropped by request)"; exit 0; }
head=$(sed -n 's/^HEAD: //p' "$f" | head -1)
[ -n "$head" ] || { echo "no HEAD line in $f; not posting"; exit 3; }
state=$(gh pr view "$pr" -R "$repo" --json state,headRefOid --jq '.state+" "+.headRefOid') || { echo "gh pr view failed for $repo#$pr; not posting"; exit 3; }
cur=${state#* }; st=${state%% *}
if [ "$st" != OPEN ]; then echo "SKIP $repo#$pr state=$st"; exit 0; fi
body=$(awk 'NR>2' "$f" | awk '/^VERDICT: /{exit} {print}' | grep -v -E '^\*\*(Stopping Point|Status)')
verdict=$(grep -o '^VERDICT: [A-Z]*' "$f" | tail -1); verdict=${verdict#VERDICT: }
case "$verdict" in CLEAN|FINDINGS) ;; *) echo "NO VERDICT in $f; not posting"; exit 3;; esac
[ "$(grep -o '^VERDICT: [A-Z]*' "$f" | sort -u | wc -l)" -eq 1 ] || { echo "conflicting VERDICT lines in $f; not posting"; exit 3; }
if grep -q -E 'AGY_ERROR|RESOURCE_EXHAUSTED' "$f"; then echo "AGY ERROR in $f; not posting"; exit 3; fi
if [ "$verdict" = CLEAN ] && { echo "$body" | grep -q -i 'non-blocking' || [ "${#body}" -gt 80 ]; }  # same 80-character rule as CLEAN_NOTE_CHARS in bigread.py; then echo "CLEAN with listed notes in $f; not posting"; exit 4; fi
if [ "$verdict" = CLEAN ] && [ -e "$f.truncated" ]; then echo "CLEAN from a truncated diff ($(cat "$f.truncated") chars) in $f; not posting (use bigread.py)"; exit 4; fi
note=""
[ "$cur" != "$head" ] && note="
The PR head has moved since this review (reviewed ${head:0:7}); a later read of the current head supersedes this one."
label=${MODEL_LABEL:-Argon: Gemini via Antigravity \`agy\` 1.3.5}
hdr="### 🤖 Antigravity agent report

### Cross-harness review ($label, read-only plan mode) at ${head:0:7}"
if [ "$verdict" = CLEAN ]; then
  txt="$hdr

Checked for correctness, Quarto syntax and crossrefs, consistency with the PR description, lost or duplicated content, and style, from the diff alone. Not checked: the rendered page.$note"
else
  txt="$hdr

These come from the other model and I have not independently verified each one against the files, so treat them as leads. The review used the diff only (long diffs are truncated at 24000 characters); nothing was rendered.$note

### Findings

$body"
fi
txt="$txt

### Verdict

VERDICT: $verdict

Reviewed-Commit: $head"
printf '%s\n\n_Posted by Claude Code (AI agent) --- not written by a human._\n' "$txt" > "$d/comment-${repo//\//_}-$pr.md"
gh pr comment "$pr" -R "$repo" --body-file "$d/comment-${repo//\//_}-$pr.md"
