When you find a bug or issue that belongs in an **upstream or external
repository** (a dependency, a reusable workflow, an action you call, etc.),
work through this escalation path.

**First, before drafting anything, read that repo's contribution policy and
respect it.** External repos are not ours — their rules bind us, and getting
them wrong can get the user's account banned. Check, in the upstream repo:

- **`CODE_OF_CONDUCT.md`** — some projects (e.g. `quarto-dev/quarto-cli`)
  explicitly **ban issues/PRs from autonomous AI agents acting without human
  oversight**, and treat it as account-bannable on the first offense. If the
  repo bans AI-agent submissions, **do not file.** Hand the draft to the user
  and let *them* decide whether and how to submit it themselves.
- **`CONTRIBUTING.md`** and the **issue/PR templates** (`.github/ISSUE_TEMPLATE/`,
  `.github/PULL_REQUEST_TEMPLATE.md`) — follow the required template and fill in
  every required field. Don't post a free-form body when a template exists.
- **Where the item belongs.** Many projects route **feature requests and
  questions to a Discussions board**, not the issue tracker. File bugs as
  issues only if that's what the guidelines say; otherwise use Discussions.
  The same judgment applies to repos we administrate, rather than being a
  courtesy owed only to strangers --- see
  [`choose-issue-or-discussion`](choose-issue-or-discussion.md).

Beyond what you read in those files: **never open an upstream issue/PR
autonomously.** Draft it, show the user the full text, and **get explicit
approval before posting** — the user is the human contributor who reviews and
verifies the submission, as most AI-contribution policies require.

When the policy allows AI-assisted contributions with human review, proceed
through the escalation path:

1. **Open a PR** in the upstream repo if you have a fix ready.
   Push directly if you have write access; fork first if you don't.
2. **File an issue** in the upstream repo if you have access to the tracker
   but no fix ready, or if a PR would be premature. Link back to the current
   PR/issue for context.
3. **File an issue in your own repo** if you can't file an issue in the upstream
   repo either (e.g. the tracker is closed, the MCP tools can't reach it, or you
   lack any access). Write it clearly enough that it could stand on its own, then
   **ask the user to transfer it** to the upstream repo using GitHub's
   *Transfer issue* feature.

In all cases, reply to the review comment (or note in the PR) with a link to
whatever issue or PR you filed, so the upstream root cause is tracked and
visible.

Apply any reasonable local mitigation regardless of which path you took, but
don't let the upstream root cause go unrecorded.
