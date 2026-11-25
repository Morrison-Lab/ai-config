# Shipping a hook PR: conflicts, review sha, and reply-hook rules

Measured 2026-11-07 while shipping ai-config#5089, #5091, #5092 and #5094 from one project thread (all merged).

## Two hook PRs conflict additively in three files

Two hook PRs open at once conflict in `README.md`, `hooks/hooks.json` and `plugins/ai-config-hooks/hooks/hooks.json`.
Each side added a README row and a matcher block, so nothing is in dispute.
Keep both rows and both blocks, then regenerate the mirror with `python3 scripts/gen-hooks-plugin.py` and confirm with `--check` and `scripts/check-hook-catalog.py`.

- **Do:** resolve hunk by hunk, keep both additions, regenerate the plugin mirror, and run the catalog check.
- **Don't:** take one side of `hooks/hooks.json` whole, or hand-edit the mirror.

## The review's `commit_sha` is not the PR head

The Claude review's JSON block reported `commit_sha` 7a4b5de for head 7863c93, and 43c24bc for head 5a4bf48.
Each is the review workflow's merge-with-base commit.
The comment's "Reviewed commit" line and the PR's check runs name the real head.

- **Do:** match the head by the "Reviewed commit" line and the PR's `head.sha`, and say in the handoff that the JSON sha differs.
- **Don't:** treat a differing JSON `commit_sha` as a stale review, or as a Clean verdict on another head.

## Reply hooks refuse on the first try

`mcp__hearthbot__post_message` is denied for a bare `#N`, for naming the coordinator or a session without a link, and for a "still open" claim with no live PR read that turn.
`send_later` needs both `message` and `delay_minutes`.

- **Do:** write every PR as `[owner/repo#N](url)`, link the coordinator session, and read the PR in the same turn before saying it is open.
- **Don't:** draft a status message from the previous turn's state.

The same hook also fires on the plain words "the thread" and "coordinator" when no session or thread link sits in the same paragraph or list item, and on a bare `repo#N` inside the Stopping Point line (measured 2026-11-18, ai-config#5830).
Other first-try refusals from that run: a Python heredoc with a backslash, and `update_pull_request` with `reviewers` on a PR whose author is the requested reviewer.

- **Do:** link the session once per paragraph or rephrase ("this work", "the brief"), link every PR even in the Stopping Point line, edit scripts with Edit or Write instead of a heredoc, and assign (not request review from) a PR author.
- **Don't:** retry the same wording or form after a refusal.

## A stacked base whose findings are fixed only in its child cannot pass the gate

The final-head gate judges each head on its own.
When agy findings on a hook PR at the size cap went into its stacked child, the base's own head could never get a clean line: the runner could not send [ai-config#5974](https://github.com/Morrison-Lab/ai-config/pull/5974) for one (2026-11-19).
The fix chosen was to retarget the child, [ai-config#5976](https://github.com/Morrison-Lab/ai-config/pull/5976), to `main` with the whole combined diff, to land alone (both still open when this was written).

- **Do:** when the combined diff fits the cap (20 files, 600 lines), retarget the child to `main`, rewrite its body to cover the whole combined diff, and land only the child with a merge commit;
  GitHub marks a PR merged once its head commit reaches its base branch.
  Comment on the base that it must not merge alone.
- **Don't:** plan "base first, then child" while the base still carries findings fixed only in the child.
- **Do:** settle the structure before asking for agy, so agy reviews the head that will land.
- **Don't:** write a lesson as a file in the project memory store;
  `hooks/block-project-memory-write.py` denies it, and the lesson belongs in a tracked file such as this one.
- **Don't:** chain a `>>` append with `git commit` in one cloud Bash call;
  `hooks/no-chained-edit-and-commit-in-cloud.py` denies it, so edit with the Edit tool and commit separately.

## Opening a PR never needs Ezra's words, but weakening a PR gate does

Ezra, 2026-11-20 09:16 PST: "i shouldn't need to approve opening PRs".
[ai-config#6142](https://github.com/Morrison-Lab/ai-config/pull/6142) exempts every Morrison-Lab GitHub repo from `no-unnamed-repo-pr.py`, and the classifier allowed that edit.
On the same day's follow-up (2026-11-25), the classifier denied turning `no-unrequested-sweep-pr.py`'s 10-PR cap from a deny into a warning as "Undermining Oversight".

- **Do:** after one such denial, stop, stash the half-applied edit (`git stash push -- <paths>`), and give Ezra the exact line to type in the thread, in a fenced block.
- **Don't:** reword the denied edit or split it across tools.
  Each new shape is the same action.
- **Do:** in a cloud ai-config checkout, read and search files with Read, Grep and Edit (`replace_all` for a bulk rename);
  `prefer-dedicated-tools-over-bash` denies `sed`, `grep`, `tail` and `cat` on files, and `prefer-mcp-over-bash-in-cloud` denies `gh api repos/...` (only `gh api search/...` passes).
- **Don't:** retry a refused GitHub read unchanged: the refused attempt still counts for `no-tight-github-polling`, so the retry needs `ALLOW_REPEAT_GITHUB_READ=1`.
- **Do:** make a second branch with `git worktree add`.
  Switching the main checkout's branch is refused.
