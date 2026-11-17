# WIP cap: three open PRs in a repo means no fourth

An owner thread with three or more open PRs in a repository opens no new PR in that repository
(ai-config#5213, 2026-11-09).
The number is 3 because the coordinator recommended it and Ezra answered "daytb" (2026-11-10 23:22Z),
so 3 is his grant of the coordinator's pick, not a number he typed.
The original cap of 2 was never a number Ezra chose: ai-config#5213 and ai-config#5210 carry it from a relayed coordinator rule,
and his own 2026-11-09 words there were only a question about merging main into every PR branch.
Every open PR costs a CI run and a review round on each push, and the cost multiplies when `main` moves.
On 2026-11-09 the lds queue reached 676 runs while owners kept opening PRs behind ones still waiting on review.

- **Do:** before `create_pull_request` or `gh pr create`, list your open PRs in that repo.
  At three or more, push to one of them, close one, or file an issue.
  A stacked PR is still a PR, so [`stack-prs`](../../skills/stack-prs/SKILL.md) is not a way around the cap.
- **Do:** count only PRs you opened or drive, in that repository.
  Another repo's PRs do not count against this one.
- **Don't:** open a fourth PR in a repo while three wait on review or CI.
- **Don't:** split one concern into extra PRs to get around the cap.
  That defeats `split-concerns` from the other side.

The cap never stops filing: an issue filed and left unclaimed opens no PR ([`freezes-allow-filing`](freezes-allow-filing.md)).

The cap is on open PRs, not on distinct concerns, so a mechanical split in the middle of a stack still counts.

**The cap wins over the batch skills.**
`gii`, `gia` and `gip` keep grabbing issues while earlier PRs wait for a human merge, so left alone they open a fourth PR.
Under this cap they hold new grabs in a repo at three open PRs and treat that as a wave boundary.
They resume when one of the three merges or closes.
`gip` grabs at most as many issues as the repo has room for under the cap.
This tie-break is explicit because "specific beats general" would otherwise favor the skill.

This is prose because the deny form needs a live API count of the owner's open PRs and a definition of "owner" that no hook has yet.
The hook is a follow-up on ai-config#5213.
