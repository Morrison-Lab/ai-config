# Practices from the Machine Learning course project threads

Rules Ezra and the coordinator gave in the course project, 2026-10-12 to 2026-10-16, that are not already in [`claude-app-projects`](claude-app-projects.md) (link both PR and thread, broadcast to all threads, launch sessions yourself, check previews yourself, never merge over a wrong gate).

## File a follow-up when you notice it

Ezra asked "are those issues filed?" and "why not?"
(2026-10-13) after a thread closed with two actionable items listed as "open items for you" and no issue behind either (lds#818 and pds#128 were filed late).
A line in a reply is not tracked and no other session can find it.

- **Do:** file the issue in the owning repo in the same turn and link it in the sentence that mentions the follow-up.
- **Don't:** write "open item", "left to Ezra" or "unchecked" about something actionable, or close a thread, with no issue number beside it.
- **Do:** read the post-merge runs of every merged PR before saying a stopping point is clean.

## Paywalled or institution-only content goes through a VPN session

Rule (Ezra, 2026-10-12): try the UC Davis VPN or the WWU VPN to get the content.
One of his registered devices is on the Davis VPN, and a WWU VPN is available through his work Linux machine.
The AdamW, Adam and He et al. statements in lds#599 to #602 were first written from memory, and the fact-check (lds#628) found three that did not match the papers.

- **Do:** start a Remote Control session with `start_rc_session` on a `list_devices` folder that is on a VPN.
- **Do:** tell it to save downloads outside any git repo (such as `~/Downloads/<topic>/`) and to commit and push nothing.
- **Do:** ask for verbatim quotes with section and page, so the thread does the fact-check.
- **Do:** send follow-up briefs through `start_rc_session` again (it returns `running` and delivers them), and `stop_rc_session` when done.
- **Don't:** put paper text in any repo (copyright);
  a one-sentence quote in a PR is fine.
- The Linux machine did not appear in `list_devices` on 2026-10-12;
  if a task needs the WWU VPN, ask Ezra to connect it.
- The standing fetch route is in [`fetch-untrusted-files`](../shared/workflow/fetch-untrusted-files.md).

## Track a resource in every repo whose topic it covers

Ezra's rule (2026-10-13): track any resource relevant to any of our repos or projects, not only the course in hand (for example later Deep Learning or RL courses).
Before adding a course or channel link, check the directory CSV for the channel's row and extend it rather than adding a duplicate (lds#775, Pieter Abbeel's Berkeley playlists).
The general rule is [`track-useful-resources`](../shared/workflow/track-useful-resources.md).

## Delegation lanes

Delegate only to flat-rate subscriptions or free tiers;
never to pay-as-you-go API keys (Ezra, 2026-10-13).
This is recorded in [`delegation`](delegation.md) and [`manage-quota`](../shared/workflow/manage-quota.md) (ai-config#4491, #4495).

## ai-config's own context gate

CLAUDE.md and AGENTS.md sit at their size caps (100,000 characters total for the CLI gate with margin 5 on 2026-10-16, and the 32,768-byte Codex cap for AGENTS.md).
A new `## section` failed `validate` by 347 characters on the branch for ai-config#4569.
Put new rules in `shared/workflow/<name>.md` or a `memories/` file, fold at most a one-line pointer into an existing section, and run `python3 scripts/check-context-closure.py` before pushing.
A red main is a request for the fix, not a reason to wait on Ezra (2026-10-16;
see [`red-main`](../shared/workflow/red-main.md)).

## Confirm which thread owns a PR before fixing a relayed finding

On 2026-11-11 (Pacific) the coordinator relayed Flash verdicts on three PRs to one thread.
That thread fixed all three, but gha#1930 belonged to another thread, which had pushed its own answer minutes earlier.
The first thread's fix was dropped.

- **Do:** before editing for a relayed finding, run `git ls-remote origin <branch>` and read the PR's latest comments (`gh pr view <n> --comments`).
- **Do:** if this thread did not open the PR, or another session pushed or commented since the reviewed head, ask the coordinator which thread owns the PR.
  An owner still working locally leaves no trace on the remote, so a quiet branch does not prove the PR is yours.
- **Don't:** treat every PR named in a relayed message as yours to fix.

## An idle-thread sweep pages every state and skips threads with an open PR

Ezra, 2026-11-17: "all 37 are in this project", and the coordinator resolved "Add psw rule for choosing result div types" while its PR (lds#2623) was still open ([ai-config#5806](https://github.com/Morrison-Lab/ai-config/issues/5806)).
An idle thread is any unresolved thread, not only one in `review_ready` or `blocked`.

- **Do:** page `list_threads` with `state=done` (every cursor), `review_ready` and `blocked`, with `include_pull_requests`, and collect every row not marked resolved.
- **Do:** skip any thread whose row shows an open or draft PR, and resolve a thread only when it shows none.
- **Don't:** say a thread belongs to another project without checking the project's own listing.
- **Mechanism:** `hooks/require-pr-read-before-resolve.py` denies `set_thread_resolved` unless that read ran this turn, and when the row shows an open or draft PR.
- **Do:** from a thread session, read PR state with `list_prs`, since a thread's `list_threads` has no `include_pull_requests` and errors on any value ([ai-config#5812](https://github.com/Morrison-Lab/ai-config/issues/5812)).
- **Do:** call `send_later` with `message` and exactly one of `delay_minutes` or `at`, `subscribe_pr_activity` with `pullNumber`, and set a PR assignee through `issue_write` with method `update`.
- **Do:** expect every GitHub comment write from a cloud thread, by MCP or REST, to end with `---` and `_Generated by [Claude Code](https://claude.ai/code)_` after the agent marker;
  `check-pr-fully-clean.py` accepts that shape.
- **Don't:** edit a comment to differ from its current body only by that footer;
  the edit is a silent no-op and `updated_at` does not change.
- **Do:** answer a multi-finding review with bare dispositions, such as "- **Blocking, `file.qmd:21`** -- fixed.", and put explanations in a separate paragraph.
- **Don't:** write a disposition with a free-word label, such as "**Blocking, line breaks**", or an explained "fixed" or "kept";
  the checker keeps that line in its verdict scan and reads the reply as not-clean ([ai-config#5819](https://github.com/Morrison-Lab/ai-config/issues/5819)).
- **Don't:** pass `delaySeconds` to `send_later`, `pr_number` to `subscribe_pr_activity`, or `assignees` to `update_pull_request`; each errors on the first call.

## A stacked base whose findings are fixed only in its child cannot pass the gate

The final-head gate judges each head on its own.
When review findings on a base PR at the size cap went into its stacked child, the base's own head could never get a clean line: the runner could not send [ai-config#5974](https://github.com/Morrison-Lab/ai-config/pull/5974) for one (2026-11-19).

- **Do:** when the combined diff fits the cap (20 files, 600 lines), retarget the child to `main`, rewrite its body to cover the whole combined diff, and land only the child with a merge commit, as [ai-config#5976](https://github.com/Morrison-Lab/ai-config/pull/5976) did;
  GitHub marks the base merged once its head reaches `main`.
  Comment on the base that it must not merge alone.
- **Don't:** plan "base first, then child" while the base still carries findings fixed only in the child.
- **Do:** settle the structure before asking for agy, so agy reviews the head that will land.
- **Don't:** write a lesson as a file in the project memory store;
  `hooks/block-project-memory-write.py` denies it, and the lesson belongs in a tracked file such as this one.
- **Don't:** chain a `>>` append with `git commit` in one cloud Bash call;
  `hooks/no-chained-edit-and-commit-in-cloud.py` denies it, so edit with the Edit tool and commit separately.
