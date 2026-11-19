# configure-repo: set a repository up for agent work

Make a repository ready for agents from any harness: point its `AGENTS.md` at ai-config, give it the lab’s baseline CI, and add the review workflows, all in one PR ([ai-config#2238](https://github.com/Morrison-Lab/ai-config/issues/2238)). Each step below runs a tool or skill that already exists; this skill only puts them in order.

## When this fires

- “configure this repo for agents”, “set up ai-config here”, “onboard this repo”
- A new Morrison-Lab repository, in the same PR that adds its first content ([`upgrade-to-gha`](../../shared/workflow/upgrade-to-gha.md), “new repo”).
- A repository whose `AGENTS.md` has no `ai-config:begin` block, which `python3 scripts/wire-repo-config.py --check <repo-dir>` reports.

It does not fire inside ai-config itself, which `wire-repo-config.py` refuses.

## Procedure

Use two checkouts: an up-to-date ai-config checkout, which supplies the scripts, and a new branch of the target repository, which receives every change. Step 2 runs from the ai-config checkout and names the target’s directory as `<repo-dir>`. Every other step reads, edits and commits in the target’s checkout.

1.  **Read the target’s own instructions first:** its `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md` and `.github/` directory, so that nothing below overwrites a rule the repository already states ([read-canonical-doc-before-starting](../../shared/workflow/read-canonical-doc-before-starting.md)).
2.  **Wire the agent instructions:** `python3 scripts/wire-repo-config.py <repo-dir>`. It writes the marked ai-config block into `AGENTS.md` (and into a `CLAUDE.md` that does not import `AGENTS.md`), registers the marketplace in `.claude/settings.json`, and adds `.Rbuildignore` entries in an R package. Pass `--enable-plugin` only for a repository whose sessions get the plugin no other way, since a second copy fires every hook twice (the script’s docstring explains). Then run it again with `--check`, which must exit 0.
3.  **Add the baseline CI** that [`upgrade-to-gha`](../../shared/workflow/upgrade-to-gha.md#the-baseline-set) lists, and the callers the repository’s type needs, taking each pin from gha’s README table. For the review pair, follow [`claude-review-workflow`](../../skills/claude-review-workflow/SKILL.llms.md) and [`claude-agent-workflow`](../../skills/claude-agent-workflow/SKILL.llms.md). Skip any workflow the repository already has, and upgrade a hand-maintained one per `upgrade-to-gha`.
4.  **Write what is specific to this repository** in its own `AGENTS.md` or `CLAUDE.md`, outside the managed block: how to build and test, what the directories hold, and any rule that applies only here. Leave cross-project rules to ai-config, which the block already points at.
5.  **Open one PR** with all of it, and drive it to clean ([`ardi`](../../skills/ardi/SKILL.llms.md)). The PR’s own CI is the first run of the new workflows, so read each new check’s log rather than trusting a green badge.

## Checks before calling it done

- `python3 scripts/wire-repo-config.py --check <repo-dir>` exits 0.
- Every baseline workflow exists, or the PR body says why it was left out.
- The repository’s own instructions name its build and test commands.

Back to top
