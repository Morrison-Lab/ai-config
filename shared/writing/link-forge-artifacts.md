# Link PRs in tables

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#link-prs-in-tables) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When listing PRs in a table (or anywhere they could be clickable), make each PR number a markdown link to the PR URL --- `[#237](https://github.com/<owner>/<repo>/pull/237)`.
The plain text form forces the user to copy/paste; the linked form lets them open the PR in one click.

**The same rule covers any item I reference, not just a PR number in a table.**
Telling the user I replied to a comment, filed an issue, posted a review, kicked off a run, opened a GitLab MR, published a page, or wrote a file --- in a table or in ordinary chat prose --- and naming it without a link leaves them to go find it themselves, which is the exact cost the table-only version of this rule already removes for PR numbers.
A comment has no number to recognize the way a PR does, so its link is the *only* way the user can locate it without re-deriving the search themselves.
Give the direct link (a URL, or a clickable path for a file) in the reply that mentions the item, never a description of where to find it.

- **Do:** link every comment, review, issue, PR, MR, run, published page, or file I mention having posted, created, or acted on, wherever the mention occurs --- table or prose.
- **Don't:** report "I replied to that", "posted the referee report on the MR", or "filed the issue" as a bare fact with no link attached.

**Resolve whether a bare number is a PR or an issue before linking it.**
GitHub numbers PRs and issues from one sequence, and the path segment names the type: `/pull/N` for a PR, `/issues/N` for an issue.
One query answers it, and the ways to run it are already recorded:
`git ls-remote origin refs/pull/<N>/head` in a clone
([`memories/git.md`](../../memories/git.md#classify-a-bare-nnnn-as-issue-or-pr-with-git-ls-remote-origin-refspullnnnnhead)),
or the `pull_request` key from the issues API
([`memories/gh-cli.md`](../../memories/gh-cli.md), the bullet "Whether `#N` is an issue or a PR is decided by the `pull_request` key").
The MCP `issue_read` tool (method `get`) also answers it: its `html_url` carries the right path for a PR number too.

- **Do:** look the number up and link it with the path the forge returns.
- **Don't:** default every unresolved number to `/issues/N` because checking looked costly.
  A batch of links made that way labels each PR as an issue
  ([ai-config#4401](https://github.com/Morrison-Lab/ai-config/pull/4401), 2026-10-08).

See [`hyperlink-liberally`](hyperlink-liberally.md) for the general principle covering tools, internal rules, and technical terms.

(Directive from the user, 2026-09-09: telling them a reply had been posted without linking it made them go find it themselves.)
(Directive from the user, 2026-10-02, after a referee report was posted on a GitLab MR without a link: "give me the link" --- "always".)
