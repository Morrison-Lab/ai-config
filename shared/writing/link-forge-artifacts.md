# Link PRs in tables

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#link-prs-in-tables) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When listing PRs in a table (or anywhere they could be clickable), make each PR number a markdown link to the PR URL --- `[#237](https://github.com/<owner>/<repo>/pull/237)`.
The plain text form forces the user to copy/paste; the linked form lets them open the PR in one click.

**The same rule covers any item I reference, not just a PR number in a table.**
Telling the user I replied to a comment, filed an issue, posted a review, kicked off a run, opened a GitLab MR, published a page, or wrote a file --- in a table or in ordinary chat prose --- and naming it without a link leaves them to go find it themselves, which is the exact cost the table-only version of this rule already removes for PR numbers.
A comment has no number to recognize the way a PR does, so its link is the *only* way the user can locate it without re-deriving the search themselves.
Give the direct link in the reply that mentions the item, never a description of where to find it.
That holds for items I only read, fetched, or inspected too, not only ones I created:
naming "the preview page" or "the example subfile" without a URL makes the user search for the thing they asked about.

The scope is items the reply names for the user to open.
It does not reach a private repository's file in a context the user cannot see, where [`media-links-beside-content`](media-links-beside-content.md) governs.

- **Do:** link every comment, review, issue, PR, MR, run, check, PR preview, published page, or file I mention, wherever the mention occurs --- table or prose, created by me or only read.
- **Do:** give a preview page as its preview URL (with a `#anchor` where one exists).
- **Do:** give a file as its blob URL on the branch once it is pushed, and as a clickable path while it exists only locally.
- **Don't:** report "I replied to that", "posted the referee report on the MR", or "filed the issue" as a bare fact with no link attached.
- **Don't:** answer a question about a rendered page or a source file by naming it in plain text.

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
(Directive from the user, 2026-10-08, after an answer named a PR preview page and two source files with no links: "haven't I told you to always provide links?")

## Link a PR's project thread too

When a message names a PR, link both the PR by its full URL and the project thread it belongs to, wherever a thread exists and is relevant.
In a Claude Projects chat or thread message, write the thread link as `[thread title](#cmsg_…)`, which the app resolves.
Outside the app, such as in a GitHub comment or a PR body, a bare fragment goes nowhere, so write the full thread URL as a link, `[project thread](https://claude.ai/code/project/<project id>?thread=<cmsg id>)`, the form the PR attribution block uses.

- **Do:** write the PR as `[#4516](https://github.com/Morrison-Lab/ai-config/pull/4516)` followed by its thread link.
- **Don't:** name a PR with only its number, or link the PR and leave the user to find the thread.

(Directive from the user, 2026-10-14: "when you mention PRs, always link to both the PR and the corresponding thread (if relevant)".)

## Link the rendered section of a content change too

When a report describes a content change, link the PR, its project thread, and the rendered section that changed.
Use the PR preview URL with the section's `#anchor`.
If no preview exists yet, use the published URL with the anchor.
If the change has no rendered section, such as an infrastructure change, the PR and thread links suffice.

- **Do:** write `[PR](…/pull/N)`, then the thread link, then `[section](https://preview.example/page.html#sec-id)`.
- **Don't:** report a content change with only the PR link and leave the user to find the section.

(Directive from the user, 2026-10-16: "always link me to the relevant section as well as the relevant pr", then corrected to include the thread.)

## Link every session you mention

Whenever a message names a session, such as a Claude Code session, a project thread or a Remote Control session, link it in the sentence that names it.
Write `[session](https://claude.ai/code/session_…)` for a Claude Code session, or the thread link above for a project thread.

- **Do:** write the session as a link the user can open.
- **Don't:** name a session by title or id alone.

(Directive from the user, 2026-10-16: "anytime you mention a session, you must provide a link".
Tracked in [ai-config#4570](https://github.com/Morrison-Lab/ai-config/issues/4570).)
