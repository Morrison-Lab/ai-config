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

## Link a branch to its issue when you create the branch

Ezra, 2026-11-11 (`cai:`, ai-config#5299): "when you create a branch to address an issue, link that issue to that branch using the Development field ... also link the PR once it's created, but link the branch immediately."

- **Do:** create the branch through GitHub, already linked, before the first commit lands on it: `gh issue develop <n> --repo <owner>/<repo> --name <branch> --base main`, or the GraphQL mutation `createLinkedBranch` (`issueId`, `oid`, `name`).
  Then fetch the branch and push your commits onto it.
- **Do:** link the PR once it exists, with a closing keyword (`Closes #N`) in its body.
  A PR that must not close the issue can be linked only by hand in the issue's Development field;
  say so in the thread.
- **Don't:** create the branch with `git push` and plan to link it afterwards.
  GitHub links a branch only when it creates it, and no mutation links an existing branch.
  On an existing name, `createLinkedBranch` returns null and `gh issue develop --name` fails
  (tested 2026-11-11, and [community discussion #155339](https://github.com/orgs/community/discussions/155339)).

A branch already pushed unlinked and with no PR yet: read its head SHA, delete the remote branch, and recreate it at once with `createLinkedBranch` at that SHA, so no commit is lost.
Leave a branch that already has a PR alone and link the PR instead.

Cloud sessions get HTTP 403 on every GraphQL call, so they can do neither step themselves.
Hand the branch creation (issue, repository, branch name, base or SHA) to a local runner, a Remote Control session on Ezra's machine, before the first push, and push onto the branch once it exists.
If no local runner is reachable, say in the thread that the branch is unlinked and why, rather than skipping the step silently.

No hook yet: a hook cannot tell from a push which issue a branch addresses, and a cloud session cannot query the link (ai-config#5303 tracks a mechanism).
