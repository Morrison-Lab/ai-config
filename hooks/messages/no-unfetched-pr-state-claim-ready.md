[hook: no-unfetched-pr-state-claim] This message says a PR is ready or waits on a merge
("{phrase}"),
and nothing since the last user turn read {which}'s mergeability.
On 2026-11-26 lds#3251 was on the user's merge list with merge conflicts
("3251 has merge conflicts; always check").
A PR list, a search, hearthbot list_prs or `gh pr view --json state` says the PR is open,
not that it can merge,
and a read whose result shows `"mergeable": false`, `CONFLICTING` or `dirty` means it is not ready.

Read it now:
GitHub MCP pull_request_read method get (it returns mergeable_state),
`gh api repos/O/R/pulls/N`,
`gh pr view N --json mergeable,mergeStateStatus`,
or build-pr-payload.py or check-pr-fully-clean.py.
If it reads dirty, resolve the conflicts first.
If it cannot be read from this session, say the state is unverified in the same sentence.
ai-config#6157, ai-config#4834.
