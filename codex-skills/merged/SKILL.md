---
name: "merged"
description: "Codex wrapper for the ai-config Claude skill `merged`. Alias for `wrap-up`. Use when asked to 'merged'. In a multi-PR session you can name the PR that just merged (e.g. `/merged #74`) to anchor the summary on it. Use when Codex is asked to use `merged`, `/merged`, or the corresponding ai-config/Claude skill workflow."
---

# merged (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/merged/SKILL.md](../../skills/merged/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/merged/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/merged`, resolve the symlink target for this wrapper directory first, then read `../../skills/merged/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes `mcp__github__*`
tools). Use the GitHub MCP tool below if this Codex session has it; otherwise
run the CLI command. Full per-model reference: [tool-mappings.md](../../tool-mappings.md).

| Operation | Does | CLI (`gh`/`git`) | GitHub MCP tool |
| --- | --- | --- | --- |
| `VIEW_PR` | Read a pull request's details and metadata. | `gh pr view <N>` | `mcp__github__pull_request_read (method=get)` |
| `LIST_PRS` | List pull requests. | `gh pr list` | `mcp__github__list_pull_requests` |
| `SEARCH_PRS` | Search pull requests by keyword / query string. | `gh pr list --search "<query>"` | `mcp__github__search_pull_requests` |
| `DIFF_PR` | Read a pull request's diff. | `gh pr diff <N>` | `mcp__github__pull_request_read (method=get_diff)` |
| `PR_CHECKS` | Read a pull request's CI check / status results. | `gh pr checks <N>` | `mcp__github__pull_request_read (method=get_check_runs)` |
| `READ_PR_COMMENTS` | Read a pull request's top-level (conversation) comments. | `gh pr view <N> --comments` | `mcp__github__pull_request_read (method=get_comments)` |
| `READ_PR_REVIEW_COMMENTS` | Read a pull request's inline review-thread comments (also returns thread ids). | `gh api repos/<owner>/<repo>/pulls/<N>/comments` | `mcp__github__pull_request_read (method=get_review_comments)` |
| `READ_PR_REVIEWS` | Read a pull request's formal reviews (state per reviewer, e.g. APPROVED / CHANGES_REQUESTED / COMMENTED). | `gh pr view "<N>" --json reviews` | `mcp__github__pull_request_read (method=get_reviews)` |
| `REQUEST_COPILOT_REVIEW` | Request a GitHub Copilot code review on a pull request. | `gh api "repos/<owner>/<repo>/pulls/<N>/requested_reviewers" -X POST -f "reviewers[]=copilot-pull-request-reviewer[bot]"` | `mcp__github__request_copilot_review` |
| `CREATE_PR` | Open a new pull request. | `gh pr create` | `mcp__github__create_pull_request` |
| `EDIT_PR` | Edit a pull request (reviewers, labels, base, etc.). | `gh pr edit <N>` | `mcp__github__update_pull_request` |
| `MERGE_PR` | Merge a pull request. | `gh pr merge <N>` | `mcp__github__merge_pull_request` |
| `MARK_PR_READY` | Flip a draft pull request to ready for review. | `gh pr ready <N>` | `mcp__github__update_pull_request (draft=false)` |
| `REOPEN_PR` | Reopen a closed pull request. | `gh pr reopen <N>` | `mcp__github__update_pull_request (state=open)` |
| `COMMENT_PR` | Post a top-level comment on a pull request. | `gh pr comment <N> --body "..."` | `mcp__github__add_issue_comment` |
| `REPLY_REVIEW_COMMENT` | Reply to an inline pull-request review comment. | `gh api (reply to review comment)` | `mcp__github__add_reply_to_pull_request_comment` |
| `RESOLVE_REVIEW_THREAD` | Mark an inline pull-request review thread as resolved. | `gh api graphql (resolveReviewThread)` | `mcp__github__resolve_review_thread` |
| `WATCH_PR` | Subscribe to / unsubscribe from a pull request's activity. | (no CLI equivalent) | `mcp__github__subscribe_pr_activity / mcp__github__unsubscribe_pr_activity` |
| `VIEW_ISSUE` | Read an issue's details. | `gh issue view <N>` | `mcp__github__issue_read` |
| `LIST_ISSUES` | List issues. | `gh issue list` | `mcp__github__list_issues` |
| `SEARCH_ISSUES` | Search issues by keyword / query string. | `gh issue list --search "<query>"` | `mcp__github__search_issues` |
| `READ_ISSUE_COMMENTS` | Read an issue's comments. | `gh issue view <N> --comments` | `mcp__github__issue_read (method=get_comments)` |
| `ISSUE_LINKED_PRS` | List the pull requests cross-referenced from an issue's timeline (i.e. PRs that link or close it). | `gh api --paginate repos/<owner>/<repo>/issues/<N>/timeline` | (no GitHub MCP tool; approximate with SEARCH_PRS) |
| `CREATE_ISSUE` | Open a new issue. | `gh issue create` | `mcp__github__issue_write (method=create)` |
| `COMMENT_ISSUE` | Post a comment on an issue. | `gh issue comment <N> --body "..."` | `mcp__github__add_issue_comment` |
| `CLOSE_ISSUE` | Close an issue with a reason. | `gh issue close <N> --reason "..."` | `mcp__github__issue_write (method=update, state=closed, state_reason=...)` |
| `REOPEN_ISSUE` | Reopen a closed issue. | `gh issue reopen <N> --comment "..."` | `mcp__github__issue_write (method=update, state=open)` |
| `LABEL_ISSUE` | Set an issue's labels. The two behave differently and are not interchangeable: `--add-label` ADDS to the existing set, while the MCP path REPLACES the whole set, so pass the union of existing and new labels there. The MCP path also silently creates an unknown label name instead of rejecting it. | `gh issue edit <N> --add-label "..."` | `mcp__github__issue_write (method=update, labels=[...])` |
| `GET_LABEL` | Read a single label's name, color, and description. There is no MCP tool to create or update a label; use gh label create/edit, or gh api from a workflow. | `gh api repos/<owner>/<repo>/labels/<name>` | `mcp__github__get_label` |
| `LIST_DISCUSSIONS` | List a repository's discussions. Readable over REST; writes are GraphQL-only. | `gh api repos/{owner}/{repo}/discussions` | (no GitHub MCP tool; use gh api REST or graphql) |
| `VIEW_DISCUSSION` | Read a discussion topic and its comment thread. Readable over REST. | `gh api repos/{owner}/{repo}/discussions/{number}[/comments]` | (no GitHub MCP tool; use gh api REST or graphql) |
| `COMMENT_DISCUSSION` | Post a reply on a discussion (top-level or threaded). | `gh api graphql (addDiscussionComment)` | (no GitHub MCP tool; use gh api graphql) |
| `ANSWER_DISCUSSION` | Mark a comment as the accepted answer on a Q&A discussion. | `gh api graphql (markDiscussionCommentAsAnswer)` | (no GitHub MCP tool; use gh api graphql) |
| `CREATE_DISCUSSION` | Open a new discussion in a category. | `gh api graphql (createDiscussion)` | (no GitHub MCP tool; use gh api graphql) |
| `CLOSE_DISCUSSION` | Close a discussion with a reason (RESOLVED, OUTDATED, DUPLICATE). | `gh api graphql (closeDiscussion)` | (no GitHub MCP tool; use gh api graphql) |
| `PUSH` | Push commits to a branch. | `git push -u origin <branch>` | (use git; no GitHub MCP equivalent) |
| `COMMIT` | Record staged changes as a commit. | `git commit -m "..."` | (use git; mcp__github__create_or_update_file commits a single file) |
| `FETCH` | Fetch refs from the remote. | `git fetch origin <branch>` | (use git; no GitHub MCP equivalent) |
| `MERGE_BRANCH` | Merge a branch into the current one. | `git merge origin/<branch>` | (use git; no GitHub MCP equivalent) |
| `CREATE_BRANCH` | Create a new branch (e.g. off the default branch). | `git switch -c <branch> origin/<base>` | `mcp__github__create_branch` |
| `DELETE_REF` | Delete a remote branch or tag ref. | `git push origin --delete <branch> (or git push origin :refs/tags/<tag>)` | (no GitHub MCP tool; use gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>) |
| `READ_FILE` | Read a file's contents from the repo. | `gh api repos/<owner>/<repo>/contents/<path>` | `mcp__github__get_file_contents` |
| `LIST_COMMITS` | List a branch's commits (pass the branch or ref as sha, e.g. sha=gh-pages to see which build a Pages branch currently serves). | `git log <branch> (or gh api repos/<owner>/<repo>/commits -f sha=<branch>)` | `mcp__github__list_commits` |
| `WRITE_FILE` | Create or update file(s) on a branch in a single commit. | `git add <path> && git commit -m "..." && git push` | `mcp__github__create_or_update_file (one file) / mcp__github__push_files (multiple)` |
| `LIST_SECRETS` | List a repo's Actions secrets. Returns name, created_at, and updated_at only; the value is never readable, so this can confirm a secret exists and when it last changed, never what it is or whether it works. | `gh secret list --repo <owner>/<repo>` | (no GitHub MCP tool; use gh api repos/<owner>/<repo>/actions/secrets) |
| `SET_SECRET` | Set an Actions secret. Omit --body so the value is read from stdin, keeping it out of argv (visible in ps) and shell history. Exiting 0 means the value was stored, not that it is valid. | `gh secret set <name> --repo <owner>/<repo>` | (no GitHub MCP tool; use gh) |
| `RUN_WORKFLOW` | Dispatch a workflow_dispatch workflow run on a ref. | `gh workflow run <workflow>.yml --repo <owner>/<repo> --field <key>=<value>` | `mcp__github__actions_run_trigger (method run_workflow)` |
| `LIST_WORKFLOW_RUNS` | List a workflow's recent runs, with conclusion and timestamps. | `gh run list --workflow <workflow>.yml --repo <owner>/<repo>` | `mcp__github__actions_list (method list_workflow_runs)` |
