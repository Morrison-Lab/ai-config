# Gate external repository communication on membership

Before sending any outward communication to a repository,
positively verify that the user is a member of that specific repository.

Communication includes PRs/MRs, issues, comments, reviews, review requests,
discussions, messages sent by bots or workflows under the user's authority,
and indirect actions that notify or mutate the repository,
such as mentions, cross-reference backlinks, and transfers.

Unless membership in the specific repository is positively verified,
get explicit approval that names the repository and the specific communication
before sending it.
This includes both unknown membership and verified non-membership.
Drafting locally while approval is pending is allowed.
Membership or approval does not override
a stricter repository contribution or AI-agent policy.

After positive membership verification, the user grants standing authorization
across sessions and workspaces for normal, non-destructive GitHub and GitLab
forge operations in that repository, including non-force pushes, issue and PR
or MR comments, opening or updating issues and PRs or MRs, requesting reviews,
and other ordinary repository workflow actions.
This does not authorize force pushes or merges; merge
authority remains governed by the strict merge policy.

Do not infer membership from a public repository, prior contributions, a fork,
organization membership, technical write access, available credentials,
collaborator access elsewhere, or the ability to post ---
with one exception: for non-force pushes and PRs only, the user's own push access does count,
per [`use-existing-pr-branch`](use-existing-pr-branch.md)'s standing permissions (user grant, 2026-09-28).
That exception does not extend to comments, issues, or other communication,
which still need membership or explicit approval.
`/daytb`, `away`, default-to-action rules,
and standing authorization to open PRs or file issues
do not grant permission to communicate with a non-member repository.
This gate takes precedence
over automatic filing, PR-opening, review, and follow-up rules.

- **Do:** verify membership in the specific target repository before posting any comment, issue, PR, review, or backlink.
- **Do:** draft locally and ask for explicit approval naming the repo and communication when membership is not positively verified.
- **Don't:** infer membership from write permissions, public repo status, existing forks, or collaborator access in parent orgs.
