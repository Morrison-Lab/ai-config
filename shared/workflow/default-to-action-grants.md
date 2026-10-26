# Default to action without asking: installs, `add_repo`, posting reviews, and your own steps

Detail for [`AGENTS.md`'s "Default to action without asking"](../../AGENTS.md), moved here to keep `AGENTS.md` under Codex's byte cap.

The grant covers installing and updating software: R, R packages (including through `renv`), Quarto, and any other tool, on any machine where the owner has install access, directly or through conda, mamba, pyenv, Homebrew, or a similar manager.
Do it whenever it helps, without asking (owner directive, 2026-10-02).
A resulting lockfile change (`renv.lock`, `environment.yml`) is a repo change and goes through the normal PR flow.

It covers attaching any repository (`add_repo`) whenever that helps, even only to read it.
Posting there still passes the membership gate in `AGENTS.md`;
where it does, file or fix without offering first.

- **Do:** attach a repository as soon as it would help.
- **Don't:** ask first, or write "would need `add_repo`" and wait (ai-config#4337).

## Never hand the owner a step you could do yourself

Before asking the owner to *perform* a step, as opposed to *decide* something, check whether any tool available to you performs it.
The tell is an imperative aimed at the owner that contains no choice: "run this command", "open that page", "start a fresh session".
A read-only check (a scan, a listing, a diff) is one of those steps: run it before answering rather than offering to run it ([`no-cop-out-offers`](no-cop-out-offers.md)).
When a path is blocked for a technical reason (a missing CLI, a tool that cannot do the step), take another route to the same goal.
A failing check or gate is not such a block: fix what it reports rather than going around it.

A policy denial is not a technical block, and you never route around one.
For a permission-classifier or approval-mode denial of an authorized action, follow [`ask-for-manual-approval`](ask-for-manual-approval.md).
For a denial of an action nothing authorizes, ask the owner whether to do it at all, as `ask-for-manual-approval`'s "When to ask" says.
For a proxy `403` on a push, follow [`use-existing-pr-branch`](use-existing-pr-branch.md), which says to report it to the owner rather than retry.

Owner directive, 2026-10-22, given while moving mlg CI to the WWU GitLab.
Tracked in [ai-config#4683](https://github.com/Morrison-Lab/ai-config/issues/4683).
[ai-config#3562](https://github.com/Morrison-Lab/ai-config/issues/3562) is the earlier case: an agent told the owner to start a fresh session it could have scheduled itself.

- **Do:** run the check or the command yourself, or take another route around a technical block, and report the result in the past tense.
- **Don't:** tell the owner to run a step a tool in your session could run.
- **Don't:** treat a policy denial or a failing check as a technical block to route around.

## Posting reviews

The grant covers posting reviews without asking, from any session, including a Remote Control session on the owner's machine (owner directive, 2026-10-26: "you can always post reviews").
A review here is any of these on a PR or MR:

- an adversarial or cross-model review report
- a self-review report
- review findings from a review-only request
- a reply on a review thread

Post a review report with `gh pr comment` (an MR note on GitLab).
Never post it with `gh pr review --approve` or `--request-changes`, which set GitHub's formal `APPROVED` or `CHANGES_REQUESTED` review state, a decision that the owner has not made.
Do not post a report with `gh pr review --comment` either, because `scripts/check-pr-fully-clean.py` ignores a `COMMENTED` review from a user login unless its body names another agent, so a self-review or a marker-free report posted that way would not count, clean or not.
The grant gives no approval or merge authority.

Every review report follows [`adversarial-self-review`](adversarial-self-review.md#post-every-independent-review-on-the-pr-or-mr-it-reviewed), which also covers the separate dispositions comment:

- post the reviewer's report verbatim, or page-numbered findings for a referee read of a rendered document
- include a `Reviewed-Commit:` line and a `### Verdict` heading on every code or PR review, as that fragment requires
- include the `review-data` JSON payload on every review, as [`AGENTS.md`](../../AGENTS.md) requires
- for a branch that has no PR yet, wait until the PR exists before posting

A reply on a review thread is an ordinary comment, so it needs no `Reviewed-Commit:` line, verdict, or `review-data` payload.
Every comment posted under the owner's login carries the disclosure footer from [`disclose-agent-authorship`](disclose-agent-authorship.md), which also states the bot-identity exemption.
Your reply to the owner links each posted comment, review reports and thread replies alike, per [`link-forge-artifacts`](../writing/link-forge-artifacts.md).

The grant does not widen which PRs you act on.
Scope follows [`memories/reviewing-prs.md`](../../memories/reviewing-prs.md) and [`pr-scope`](pr-scope.md), which admit a PR when:

- the owner opened it or is assigned to it
- the owner asked for it by name
- the `github-actions` app authored it

An explicit exclusion such as "do not touch #N" vetoes every one of those arms.
On any other PR, post a review only when asked to review that PR.
In a repository where the owner's membership is not positively verified, posting is still subject to the membership gate in [`AGENTS.md`](../../AGENTS.md) and [`gate-external-communication`](gate-external-communication.md), as the `add_repo` grant above is.

A standing grant does not clear a permission-classifier denial.
When the classifier or approval mode blocks the post, follow [`ask-for-manual-approval`](ask-for-manual-approval.md).
Retry the identical command once.
Then, when `mcp__ccd_session_mgmt__set_session_permission_mode` is available, switch the session to `default` yourself, rerun the command once, and request `auto` again.
Without that tool, ask the owner to leave auto mode.
A managed-settings `permissions.deny` denial applies in every mode, so report that denial and do not ask to switch modes.
Never ask whether to post the review, because the grant has answered that question.
The durable fix is an `autoMode` `allow` entry that covers `gh pr comment` and MR notes.
The entry goes in `~/.claude/settings.json` or in managed settings, never in a repository's settings.
A cloud session reads no `~/.claude/settings.json`, so managed settings are the only durable route for cloud sessions (see [`use-existing-pr-branch`](use-existing-pr-branch.md)).
Tracked in [ai-config#4756](https://github.com/Morrison-Lab/ai-config/issues/4756).
On [Morrison-Lab/ids#26](https://github.com/Morrison-Lab/ids/pull/26), a finished all-clear cross-model verdict stayed unposted until the owner wrote "post it".

- **Do:** post the review with `gh pr comment` as soon as both the review and the PR exist, and report it in the past tense with its link.
- **Don't:** hold a finished review and ask whether to post it, or post it as an approve, request-changes, or `gh pr review --comment` review.

## "Don't wait" and "decide it yourself"

When a coordinator or the user says "don't wait" or "decide it yourself", act in the same turn.
Hold a step for a person only when it is irreversible or needs their own word, such as a merge.
A rule learned from such a correction is global ([`global-by-default`](global-by-default.md)): record it the same turn, never as a later to-do.
A sandbox denial of the step is a reason to report the denial, not to skip recording the rule.
Case: [ai-config#4696](https://github.com/Morrison-Lab/ai-config/issues/4696).
