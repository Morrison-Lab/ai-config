# defer-issue

When the user decides to push something out of the current scope, file a new issue in the appropriate forge that captures the deferred work cleanly enough for them (or a future Claude) to pick it up cold.

## When this fires

User says something like:

- “let’s defer this”
- “defer this for later”
- “create a followup issue for X”
- “we’ll handle that in a separate PR”
- “make this its own issue”

Don’t fire just because something looks unfinished. The user must explicitly defer.

## Procedure

### 1. Identify the forge

``` sh
git remote get-url origin
```

| Host                              | CLI                      |
|-----------------------------------|--------------------------|
| `github.com`                      | `gh issue create`        |
| `gitlab.com` / self-hosted GitLab | `glab issue create`      |
| Bitbucket / Gitea / other         | ask the user how to file |

If the matching CLI isn’t installed, surface that and stop — don’t try to file via the raw HTTP API without confirming.

### 2. Gather context

From the current conversation, identify:

- **What is being deferred** (one sentence — becomes the title)
- **Concrete work needed** (what change, which files, what “done” looks like)
- **Why deferring** (out of scope, needs design discussion, blocked on X)
- **Where the deferral was raised** (PR number, commit SHA, file:line, review thread)

If any of these are unclear from context, ask the user briefly before filing. A vague follow-up issue is worse than no issue.

### 2b. Search for an existing issue first — including CLOSED ones

Before filing, check the tracker so you don’t create a duplicate. Search **both open and closed** issues by keyword — deferred review findings are often pre-filed by an earlier session or the review bot and may already be **closed** (e.g. as a duplicate, or decided), which an open-only search misses:

``` sh
gh issue list --state all --search "<keywords>" --json number,title,state   # SEARCH_ISSUES
# GitLab: glab issue list --all --search "<keywords>"   # --all (-A) = open + closed
```

- If an **open** issue already covers it, link that one instead of filing — report its URL and stop.
- If a **closed** issue covers it, surface it to the user (it may have been closed as a duplicate pointing elsewhere, or closed as decided) and confirm whether to reopen it, file fresh, or treat the matter as settled — don’t blindly file a second one.

This is the **never assume; always verify** rule applied to issue filing: a quick search beats leaving two issues tracking the same work.

### 3. Compose the issue

**Title:** short, imperative, specific. Good: `Refactor session_env merge logic to handle nested overrides`. Bad: `Followup`, `TODO from PR #42`.

**Body template:**

``` markdown
## Context

Deferred from <source: e.g., PR #42, commit abc1234, review on path/to/file.R:120>.

<1–2 sentences on why this work is being split off from the current change>

## What to do

<concrete description: what change, which files, what success looks like>

## Why not now

<reason for deferring — out of scope, needs design, blocked, etc.>
```

### 4. Create the issue

**GitHub:**

``` sh
gh issue create \
  --title "..." \
  --body "$(cat <<'EOF'
...
EOF
)"   # CREATE_ISSUE
```

- Defaults to the current repo (whatever `gh` resolves from remotes / `gh repo set-default`).
- If filing into a different repo than the current one, pass `--repo <owner>/<repo>` and confirm with the user first.
- Check `gh label list` for an existing `followup`, `deferred`, or `tech-debt` label and add it with `--label`. **Don’t fabricate labels that don’t exist** — `gh` will fail and you’ll have to retry.
- Don’t add `🤖 Generated with Claude Code` attribution to the issue body unless the user asks. Issue attribution isn’t covered by the global `attribution` setting.

**GitLab:**

``` sh
glab issue create --title "..." --description "$(cat <<'EOF'
...
EOF
)"
```

### 5. Report back and offer the cross-link

Print the new issue’s number and URL as a **bare URL** (so it’s clickable in the user’s terminal — markdown links render as label-only and lose the URL). Example:

    Filed followup: https://github.com/owner/repo/issues/123

If the deferral originated in an open PR or issue, **offer** to add a `Followup: #<new-issue>` reference to that source thread — don’t do it unprompted. The user may want different wording or may not want a cross-reference at all.

## Edge cases

- **Not in a git repo / no remote:** stop and tell the user. Don’t try to invent a target repo.
- **Forked PR (head repo != base repo):** file the issue in the **base** repo by default — that’s where the work will actually land — and confirm if it’s ambiguous.
- **Different tracker entirely** (Linear, Jira, repo-specific issue tracker): ask the user where to file. Don’t assume GitHub/GitLab just because the source is hosted there.

Back to top
