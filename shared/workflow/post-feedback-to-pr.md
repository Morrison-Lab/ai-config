# Post in-chat feedback to the PR

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#post-in-chat-feedback-to-the-pr) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When the user gives feedback, corrections, or guidance in the CLI or chat while working a PR, paraphrase it and post it as a PR comment:

```
gh pr comment <N> --body "<paraphrase>

_Posted by Claude Code (AI agent) --- not written by a human._"
```

One to three sentences is enough.
The trailing marker is required, per [`disclose-agent-authorship`](disclose-agent-authorship.md): this comment paraphrases the user in the user's own voice under the user's own login, which is the shape most easily read as their own writing.
Don't quote verbatim --- paraphrase so it reads naturally in the PR thread.
Skip trivial acknowledgments or conversational exchanges with nothing to act on.
Post it only on a PR that passes `memories/reviewing-prs.md`'s scope test.
Feedback about an out-of-scope PR, such as a request not to touch it, stays in chat and the session notebook rather than on that PR.

This makes context visible to future @claude sessions, other reviewers, and contributors who only see the PR thread.
