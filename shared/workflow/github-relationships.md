# Record relationships among issues and PRs in GitHub's relationships field

Ezra, 2026-11-03 (`cai:`, ai-config#4907): use GitHub's relationships field for **every** relationship among issues and PRs.
Prose such as "Blocked by #N", "Stacked on #N" or "Part of #N" is a label for a reader, not a record: GitHub, the sub-issue tree and every tool that reads dependencies see nothing.
Write the prose if it helps a reader, and make the relationship call as well.

| Relationship | How to record it |
| --- | --- |
| Parent and sub-issue | MCP `sub_issue_write`, or `parent_issue_number` on `issue_write` `create`, or `POST /repos/{owner}/{repo}/issues/<parent>/sub_issues` with `{"sub_issue_id": <id>}` |
| Blocked by | `gh issue edit <n> --add-blocked-by <m>` (gh 2.94.0 or later), or `POST /repos/{owner}/{repo}/issues/<n>/dependencies/blocked_by` with `{"issue_id": <id>}` |
| Blocking | `gh issue edit <n> --add-blocking <m>`, or the same endpoint on the blocked issue |
| PR closes issue | A closing keyword (`Closes #N`) in the PR body; REST has no other way to set the link |
| Stacked PR | Blocked by the base PR (a PR is an issue there), and a `> [!IMPORTANT]` note in the body |

`<id>` is the numeric `id` from `GET /repos/{owner}/{repo}/issues/<n>`, not the issue number.
Use the REST API, not GraphQL, which cloud sessions block.

Mechanism: `hooks/flag-prose-relationship-without-link.py` blocks the stop once per turn when the turn created or edited an issue or PR whose body states one of these relationships in prose and no relationship call followed.
It does not sweep existing issues.
Related: [`issue-first`](issue-first.md), [`stack-prs`](../../skills/stack-prs/SKILL.md).

## Attach sub-issues and set issue types in bulk

Measured on 2026-11-11, when two planning threads each attached well over a hundred existing issues from cloud sessions.
The sub-issue measurements are in [ai-config#5318](https://github.com/Morrison-Lab/ai-config/issues/5318).
The issue-type measurements come from the rme triage, [rme#1459](https://github.com/Morrison-Lab/rme/issues/1459).
In a cloud session the MCP tools are the only route, since `gh` there cannot write.

Each successful `sub_issue_write` `add` call returns the whole parent issue, about 12 KB.
An `issue_write` `update` that sets only `type` returns about 80 bytes and keeps the issue's labels.

- **Do:** for more than about ten sub-issue links, write one line per link to a file and dispatch Haiku workers in batches of about 30, at most six at once.
  Give each line the parent's number, the child's number and the child's numeric `id`, and name the columns in a header line.
  The rme thread ran nine workers at once and saw "too many requests" on about 1 call in 10.
  The ai-config thread ran six at once and saw none.
- **Do:** verify the links afterwards with `gh api -X GET search/issues -f q='repo:OWNER/REPO is:issue is:open no:parent-issue' --paginate`, and intersect its numbers with the planned list.
  An empty intersection means every link landed.
- **Do:** read `get_parent` on an issue that refuses with "Sub issue may only have one parent", and leave the existing parent in place unless told to replace it.
- **Do:** set issue types the same way, with workers that pass only `type` to `issue_write` `update`, 4 calls per message.
  On rme, six workers set 298 types in about 2.5 minutes with no rate-limit error.
- **Do:** verify types by summing the `type:<name>` search counts against the count of open issues.
  Take the names from `list_issue_types`, so that no type is left out of the sum.
- **Don't:** make bulk `sub_issue_write` calls in the conducting session: 179 links would put about 2 MB of JSON into its context.
- **Don't:** trust a worker's success count.
  Workers on rme reported success while two links were missing.
- **Don't:** verify with `parent-issue:OWNER/REPO#N`, which returned 0 for a parent with 11 sub-issues, or with `no:type`, which returned all 310 open issues on rme after each had a type.

## Link a branch to its issue when you create the branch

Ezra, 2026-11-11 (`cai:`, ai-config#5299): "when you create a branch to address an issue, link that issue to that branch using the Development field ... also link the PR once it's created, but link the branch immediately."

- **Do:** create the branch through GitHub, already linked, before the first commit lands on it: `gh issue develop <n> --repo <owner>/<repo> --name <branch> --base main`, or the GraphQL mutation `createLinkedBranch(input: {issueId, oid, name, repositoryId})`.
  `repositoryId` is optional and defaults to the issue's repository.
  Then fetch the branch and push your commits onto it.
- **Do:** link the PR once it exists, with a closing keyword (`Closes #N`) in its body.
  A PR that must not close the issue can be linked only by hand in the issue's Development field;
  say so in the thread.
- **Don't:** create the branch with `git push` and plan to link it afterwards.
  GitHub links a branch only when it creates it, and no mutation links an existing branch.
  On an existing name, `createLinkedBranch` returns null and `gh issue develop --name` fails
  (tested 2026-11-11, and [community discussion #155339](https://github.com/orgs/community/discussions/155339)).

A branch already pushed unlinked and with no PR yet: read its head SHA, delete the remote branch, and recreate it at once with `createLinkedBranch` at that SHA, so no commit is lost.
The branch is briefly absent between the two calls, so do this only when no other session pushes to it.
Leave a branch that already has a PR alone and link the PR instead.

Cloud sessions get HTTP 403 on every GraphQL call, so they cannot create a linked branch themselves;
`Closes #N` in a PR body still works there.
Hand the branch creation (issue, repository, branch name, base or SHA) to a local runner, a Remote Control session on Ezra's machine, before the first push, and push onto the branch once it exists.
If no local runner is reachable, say in the thread that the branch is unlinked and why, rather than skipping the step silently.

No hook yet: a hook cannot tell from a push which issue a branch addresses, and a cloud session cannot query the link (ai-config#5303 tracks a mechanism).
