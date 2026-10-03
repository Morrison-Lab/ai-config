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

See [`hyperlink-liberally`](hyperlink-liberally.md) for the general principle covering tools, internal rules, and technical terms.

(Directive from the user, 2026-09-09: telling them a reply had been posted without linking it made them go find it themselves.)
(Directive from the user, 2026-10-02, after a referee report was posted on a GitLab MR without a link: "give me the link" --- "always".)
