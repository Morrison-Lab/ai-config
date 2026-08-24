#!/bin/bash
# /pr-on-claim — Open a draft PR immediately after claiming an issue
# Usage: pr-on-claim <issue#> [title-override]

set -e

ISSUE_NUM="${1:?Issue number required: pr-on-claim <issue#>}"
TITLE_OVERRIDE="${2:-}"

# Fetch issue details
echo "Fetching issue #${ISSUE_NUM}..."
ISSUE_TITLE=$(gh issue view "$ISSUE_NUM" --json title --jq '.title')
BRANCH_SLUG=$(echo "$ISSUE_TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')

# Infer type from title (fix vs feat)
if [[ "$ISSUE_TITLE" =~ ^[Ff]ix|^[Bb]ug ]]; then
    TYPE="fix"
else
    TYPE="feat"
fi

BRANCH_NAME="${TYPE}/${BRANCH_SLUG}"
PR_TITLE="${TITLE_OVERRIDE:-$ISSUE_TITLE}"

echo "Creating branch: $BRANCH_NAME"
git fetch origin main -q
git checkout -B "$BRANCH_NAME" origin/main

echo "Creating empty commit..."
git commit --allow-empty -m "start: $ISSUE_TITLE (closes #$ISSUE_NUM)"

echo "Pushing branch..."
git push -u origin HEAD

echo "Opening draft PR..."
gh pr create \
    --title "$PR_TITLE" \
    --body "Closes #$ISSUE_NUM

WIP — opened up front to claim the issue; implementing now." \
    --draft

echo "Posting claim comment on issue..."
gh issue comment "$ISSUE_NUM" --body "Claude Code CLI (local session) is working on this — please hold off until I'm done.

_Posted by Claude Code (AI agent) --- not written by a human._"

echo "✓ PR opened and issue claimed."
git log --oneline -1
