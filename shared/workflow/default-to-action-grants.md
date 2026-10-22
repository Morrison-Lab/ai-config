# Default to action without asking: installs, `add_repo`, and your own steps

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
For a permission-classifier or approval-mode denial, follow [`ask-for-manual-approval`](ask-for-manual-approval.md).
For a proxy `403` or other forge policy rejection, follow [`use-existing-pr-branch`](use-existing-pr-branch.md) and report it to the owner.

Owner directive, 2026-10-22, given while moving mlg CI to the WWU GitLab.
Tracked in [ai-config#4683](https://github.com/Morrison-Lab/ai-config/issues/4683).
[ai-config#3562](https://github.com/Morrison-Lab/ai-config/issues/3562) is the earlier case: an agent told the owner to start a fresh session it could have scheduled itself.

- **Do:** run the check or the command yourself, or take another route around a technical block, and report the result in the past tense.
- **Don't:** tell the owner to run a step a tool in your session could run.
- **Don't:** treat a policy denial or a failing check as a technical block to route around.
