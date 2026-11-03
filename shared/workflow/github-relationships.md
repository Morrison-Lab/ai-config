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
