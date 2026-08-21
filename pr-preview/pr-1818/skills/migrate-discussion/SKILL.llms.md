# migrate-discussion — move items between Discussions and Issues

Move a topic to the tracker where it belongs: a discussion that turned into a concrete bug/task should become an **Issue**; an issue that’s really a question, idea, or support request should become a **Discussion**. Migration is a judgement call — the “when helpful” part matters as much as the mechanics.

## When this fires

- User says “convert this issue to a discussion”, “move \#N to Discussions”
- User says “this discussion is really a bug — make it an issue”, “open an issue from discussion \#N”
- While triaging: an issue is generating open-ended debate with no actionable scope, or a discussion has converged on a concrete task someone will do

Don’t migrate just because a thread is long. Migrate only when the item is clearly in the wrong tracker.

## Decide first — is a move actually warranted?

| Move it **discussion → issue** when… | Move it **issue → discussion** when… |
|----|----|
| It’s a concrete, reproducible bug | It’s an open-ended question or support request |
| It’s an actionable task with a clear “done” | It’s brainstorming / a feature idea with no decision |
| Maintainers have decided to act on it | It needs community input before any work |
| It needs an assignee, label, milestone, or board | It has no actionable scope and no owner |

Leave it where it is when it’s borderline, when both trackers fit, or when the thread is active and a move would disrupt it. When unsure, ask the user — don’t migrate on a hunch.

## Prefer GitHub’s native convert feature

GitHub has built-in one-click conversions, and they’re the **best** path because they preserve the original author, the full comment thread, and post an automatic cross-reference:

- **Issue → Discussion:** on the issue, use the **“Convert to discussion”** menu item (issue sidebar / `...` menu), pick a category.
- **Discussion → Issue:** on the discussion, use **“Create issue from discussion”** (discussion `...` menu).

There is **no GraphQL mutation or `gh` subcommand** for either conversion — they are UI-only. So when you (or the user) can reach the web UI, that’s the move: point the user at the button, or walk them through it, and you’re done.

Use the recreate procedure below only when the native UI path isn’t usable (scripted/headless context, or the user explicitly wants it rebuilt).

## Fallback — recreate and cross-link

When you can’t use the native convert feature, create the new item by hand, preserve attribution, cross-link both ways, and close the original with a pointer. Get the user’s approval on the drafted new item before creating it — this is outward-facing and hard to reverse.

### Discussion → Issue

1.  Read the source discussion (see the **[discussions](../../skills/discussions/SKILL.llms.md)** skill’s read query) to capture its title, body, author, URL, and key comments.

2.  Create the issue, quoting the original and linking back so authorship and context aren’t lost:

    ``` bash
    gh issue create \
      --title '<original title>' \
      --body 'Migrated from discussion <url> (opened by @<author>).

    <original body, quoted>

    Key points from the discussion thread:
    - @<login>: <summary>'   # CREATE_ISSUE
    ```

    In a remote/web session, use `mcp__github__issue_write` (`method: create`) with the same body instead of `gh`.

3.  Comment on the discussion pointing at the new issue, then close it:

    ``` bash
    gh api graphql -f discussionId='<discussion-id>' -f body='Moved to <issue-url> to track the actionable work.' -f query='
      mutation($discussionId: ID!, $body: String!) {
        addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
          comment { url }
        }
      }'   # COMMENT_DISCUSSION

    gh api graphql -f discussionId='<discussion-id>' -f query='
      mutation($discussionId: ID!) {
        closeDiscussion(input: {discussionId: $discussionId, reason: OUTDATED}) {
          discussion { url closed }
        }
      }'   # CLOSE_DISCUSSION
    ```

    `closeDiscussion` reasons are `RESOLVED`, `OUTDATED`, or `DUPLICATE`; use `OUTDATED` for a plain move.

### Issue → Discussion

1.  Read the source issue (`gh issue view <N>` — `VIEW_ISSUE` — or `mcp__github__issue_read`) for its title, body, author, URL, and comments.

2.  Look up the repository node ID and the target category ID (only certain categories exist per repo):

    ``` bash
    gh api graphql -f owner='<owner>' -f repo='<repo>' -f query='
      query($owner: String!, $repo: String!) {
        repository(owner: $owner, name: $repo) {
          id
          discussionCategories(first: 20) { nodes { id name isAnswerable } }
        }
      }'
    ```

3.  Create the discussion, quoting the original and linking back:

    ``` bash
    gh api graphql -f repositoryId='<repo-id>' -f categoryId='<category-id>' -f title='<original title>' -f body='Migrated from issue <url> (opened by @<author>).

    <original body, quoted>' -f query='
      mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
        createDiscussion(input: {repositoryId: $repositoryId, categoryId: $categoryId, title: $title, body: $body}) {
          discussion { number url }
        }
      }'   # CREATE_DISCUSSION
    ```

4.  Comment on the issue pointing at the new discussion, then close the issue as not planned:

    ``` bash
    gh issue comment <N> --body 'Moved to <discussion-url> — this is better suited to Discussions.'   # COMMENT_ISSUE
    gh issue close <N> --reason 'not planned'   # CLOSE_ISSUE
    ```

    In a remote/web session, use `mcp__github__add_issue_comment` and `mcp__github__issue_write` (`method: update`, `state: closed`, `state_reason: not_planned`).

## Report back

Give the user both links (old and new) as clickable markdown links, say which direction the migration went, and confirm the original was closed with a pointer.

## Relationship to other skills

- **[discussions](../../skills/discussions/SKILL.llms.md)** — reads/answers discussion topics; this skill reuses its read query and hands topics back to it when a reply (not a move) is the right response.
- **[defer-issue](../../skills/defer-issue/SKILL.llms.md)** — files a fresh follow-up issue for out-of-scope work; this skill *moves* an existing item between trackers.
- **[sup](../../skills/sup/SKILL.llms.md)** — routes a report to the right destination (issue vs Discussions) on an *upstream* repo; same tracker-fit judgement, other people’s repo.

## Anti-patterns

- ❌ Hand-rebuilding when the native **“Convert to discussion”** / **“Create issue from discussion”** button would do it — the native path keeps authorship, the thread, and cross-links; the fallback loses per-comment authorship.
- ❌ Migrating without cross-linking both ways — always leave a pointer on the original and reference the original in the new item.
- ❌ Closing the original **before** the new item exists — create first, link, then close, so nothing is orphaned.
- ❌ Creating the new item without the user’s approval — outward-facing and hard to reverse.
- ❌ Migrating a borderline item on a hunch — when both trackers fit, leave it and ask.

Back to top
