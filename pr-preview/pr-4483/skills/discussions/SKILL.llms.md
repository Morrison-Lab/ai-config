# discussions — read and respond to forum topics

Read a repo’s GitHub Discussions and respond to a topic: list open topics, read one with its comment thread, draft a reply, post it, and (on Q&A topics) mark a comment as the accepted answer.

## When this fires

- User says “read the discussions”, “check the discussion board”, “what’s on the forum”
- User says “respond to discussion \#N”, “reply to this topic”, “answer the discussion”
- User says “mark that as the answer”, “accept this answer”
- After a PR/issue thread points at a Discussions board and you need to follow up there

If the topic really belongs in the issue tracker (a concrete, actionable bug or task), hand off to **[migrate-discussion](../../skills/migrate-discussion/SKILL.llms.md)** instead of just replying.

## How Discussions are reached – writes via GraphQL, reads also via REST

**Writing** goes through GraphQL. There is **no `gh discussion` subcommand** and **no `mcp__github__*` Discussions tool**, so posting a comment, creating a topic, or marking an answer all require `gh api graphql`.

**Reading** does not. GitHub serves repository discussions over REST, so these work from any session that can reach `api.github.com` with a token:

``` bash
gh api repos/<owner>/<repo>/discussions                 # list topics
gh api repos/<owner>/<repo>/discussions/<N>             # one topic
gh api repos/<owner>/<repo>/discussions/<N>/comments    # its comments
```

Without `gh`, the same three are a plain `curl` against `https://api.github.com/...` with an `Authorization: bearer` header.

Which path a session has:

- **Local session with `gh`:** everything works. Use `gh api graphql` for writes (shown below) and either form for reads.
- **Remote / web session (MCP only, no `gh`):** the GitHub MCP server exposes no Discussions tools, but the REST reads above still work, so the topic and its comments are readable. Writes need an authenticated GraphQL passthrough – and some sandboxes refuse GraphQL outright while serving REST normally. When the write path is missing, say so and hand the drafted text to the user rather than faking a reply that never posted.

Don’t report a discussion as unreachable without trying the REST read: half of what this skill does is available even where GraphQL is blocked.

`<owner>`/`<repo>` below are the repository; `<N>` is a discussion number. Use `-F` for typed (Int) variables and `-f` for strings.

## Procedure

### 1. Confirm the repo has Discussions enabled

The REST repo object carries this, so the check itself does not need GraphQL:

``` bash
gh api repos/<owner>/<repo> --jq .has_discussions
```

If it is `false`, stop and tell the user – there’s nothing to read or post to.

The GraphQL equivalent is `repository { hasDiscussionsEnabled }`, if you are already making a GraphQL call for another reason. Don’t substitute “the list endpoint returned 200” for either: a repo with Discussions enabled and no topics yet returns an empty `200`, so a 200 does not distinguish enabled-but-empty from anything else.

### 2. List topics

`LIST_DISCUSSIONS` (abstract operation token; resolve to your model’s tool via [`tool-mappings.md`](../../tool-mappings.md) – there is no GitHub MCP tool for Discussions, so every model runs one of the two `gh api` forms below). Prefer REST, since it works in sessions where GraphQL is blocked:

``` bash
gh api repos/<owner>/<repo>/discussions --jq \
  '.[] | {number, title, html_url, updated_at, comments,
          category: .category.name, answer: .answer_html_url}'
```

A non-null `answer_html_url` means a Q&A topic already has an accepted answer. The category object carries `is_answerable`, which marks a Q&A category.

The GraphQL form returns the same fields under different names, and is what to use when you also want node IDs in the same call:

``` bash
gh api graphql -f owner='<owner>' -f repo='<repo>' -f query='
  query($owner: String!, $repo: String!) {
    repository(owner: $owner, name: $repo) {
      discussions(first: 20, orderBy: {field: UPDATED_AT, direction: DESC}) {
        nodes {
          number title url updatedAt
          category { name isAnswerable }
          answerChosenAt
          comments { totalCount }
        }
      }
    }
  }'
```

`answerChosenAt` is the GraphQL spelling of the same accepted-answer signal. Report the list to the user with clickable URLs.

### 3. Read one topic and its thread

To **read** the topic and its thread, REST is enough, and works where GraphQL is blocked (`VIEW_DISCUSSION`):

``` bash
gh api repos/<owner>/<repo>/discussions/<N>            # the topic
gh api repos/<owner>/<repo>/discussions/<N>/comments   # its thread
```

The topic object carries `node_id` (e.g. `D_kwDOS6B1yM4AoI39`), which is the `discussionId` step 5’s top-level-reply mutation wants – so a REST read is sufficient to post a top-level comment.

Use the GraphQL form when you need a **comment’s** node id, for a threaded reply (`replyToId`) or to mark an answer. Whether REST’s comment objects also expose `node_id` is unverified: every discussion in this org currently has zero comments, so there was nothing to check it against. Verify it on a thread that has comments before relying on REST for those two mutations.

``` bash
gh api graphql -f owner='<owner>' -f repo='<repo>' -F number=<N> -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      discussion(number: $number) {
        id title body url
        author { login }
        category { name isAnswerable }
        answerChosenAt
        comments(first: 50) {
          nodes {
            id body isAnswer
            author { login }
            replies(first: 20) { nodes { id body author { login } } }
          }
        }
      }
    }
  }'
```

Note the discussion’s `id` (for a top-level reply) and any comment `id` (to reply in-thread or mark as the answer).

### 4. Draft the response — then get approval before posting

Posting to a public forum is outward-facing and hard to unsay. Draft the reply first, show it to the user, and wait for explicit approval before posting. Apply the plain-prose style (`use-preferred-style`): answer the actual question, be direct, no filler. If the answer isn’t clear from context, ask the user rather than guessing on a public thread.

### 5. Post the reply

Top-level comment on the discussion (uses the discussion `id` from step 3, `COMMENT_DISCUSSION`):

``` bash
gh api graphql -f discussionId='<discussion-id>' -f body='<reply text>

_Posted by Claude Code (AI agent) --- not written by a human._' -f query='
  mutation($discussionId: ID!, $body: String!) {
    addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
      comment { id url }
    }
  }'
```

Threaded reply to a specific comment — add `replyToId` (the comment `id`, also `COMMENT_DISCUSSION`):

``` bash
gh api graphql -f discussionId='<discussion-id>' -f replyToId='<comment-id>' -f body='<reply text>

_Posted by Claude Code (AI agent) --- not written by a human._' -f query='
  mutation($discussionId: ID!, $replyToId: ID!, $body: String!) {
    addDiscussionComment(input: {discussionId: $discussionId, replyToId: $replyToId, body: $body}) {
      comment { id url }
    }
  }'
```

### 6. Mark an answer (Q&A topics only)

Only categories where `isAnswerable` is true accept an answer. Mark a comment (usually one you just posted, or an existing one the user points to, `ANSWER_DISCUSSION`):

``` bash
gh api graphql -f commentId='<comment-id>' -f query='
  mutation($commentId: ID!) {
    markDiscussionCommentAsAnswer(input: {id: $commentId}) {
      discussion { url answerChosenAt }
    }
  }'
```

Use `unmarkDiscussionCommentAsAnswer` with the same input shape to undo it.

### 7. Report back

Give the user the posted comment’s URL as a clickable link, and note whether an answer was marked.

## Relationship to other skills

- **[migrate-discussion](../../skills/migrate-discussion/SKILL.llms.md)** — when a topic is really an actionable bug/task (belongs in Issues) or an issue is really an open-ended question (belongs in Discussions), migrate it instead of replying.
- **[use-preferred-style](../../skills/use-preferred-style/SKILL.llms.md)** — apply the plain-prose guide to the reply before posting.
- **[sup](../../skills/sup/SKILL.llms.md)** — files issues/PRs (or Discussions) on an *upstream* repo; this skill responds on a repo you already work in.
- **[defer-issue](../../skills/defer-issue/SKILL.llms.md)** — files a follow-up issue for out-of-scope work; reach for it if a discussion surfaces a task to track.

## Anti-patterns

- ❌ Posting to a public discussion **without showing the draft and getting approval** — outward-facing and hard to retract.
- ❌ Assuming `gh discussion ...` exists — it doesn’t; use `gh api graphql`.
- ❌ Reporting a reply as posted in a remote/MCP session that can’t actually reach Discussions — verify the mutation ran, or say it didn’t.
- ❌ Marking an answer in a non-Q&A category — only `isAnswerable` categories accept one; the mutation errors otherwise.
- ❌ Guessing at a technical answer on a public thread — ask the user when the answer isn’t clear from context.

Back to top
