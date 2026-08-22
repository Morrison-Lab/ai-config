# Skills

Skills are markdown files that teach Claude Code a reusable workflow. Each `skills/<name>/SKILL.md` file describes when to invoke the skill, what steps to follow, and which tools it may use. Claude Code discovers skills in `~/.claude/skills/` automatically.

Codex uses generated wrappers in `codex-skills/<name>/SKILL.md`. Those wrappers keep Codex frontmatter strict and point back to the canonical Claude skill in `skills/`, so the workflow stays in one place.

## How to invoke a skill

| Surface | Syntax |
|----|----|
| Local CLI | `/skill-name` or a bare keyword (e.g. `ardi`) |
| Plugin (other repos) | `/ai-config:skill-name` |
| `@claude` bot on PRs | `@claude skill-name` in a PR comment |
| Codex | skill trigger from `${CODEX_HOME:-$HOME/.codex}/skills` |

Most skills also respond to plain-English triggers listed in their `description` field (e.g. “grab an issue”, “drive to clean”, “update memories and skills”).

## Skill categories

### PR / review workflow

| Skill | Aliases | What it does |
|----|----|----|
| [`ardi`](skills/ardi/SKILL.llms.md) | `dc`, `drive`, `clean`, `iterate` | Read the latest review, address/rebut/defer every finding, push, re-request review — loop until clean |
| [`ard`](skills/ard/SKILL.llms.md) | `adr` | Single ARD pass: address, rebut, defer, or acknowledge — without the iterate loop |
| [`resolve-pr-threads`](skills/resolve-pr-threads/SKILL.llms.md) |  | Resolve inline review threads that are already settled, without a full ARD pass |
| [`claim-pr`](skills/claim-pr/SKILL.llms.md) |  | Post a “paws off” comment before a work session; unclaim when done |
| [`request-pr-review`](skills/request-pr-review/SKILL.llms.md) |  | Add a human reviewer and @-mention them with context |
| [`pr-status`](skills/pr-status/SKILL.llms.md) |  | Report the current PR’s CI and review state |
| [`pr-status-all`](skills/pr-status-all/SKILL.llms.md) |  | Report status across all open PRs |
| [`stack-prs`](skills/stack-prs/SKILL.llms.md) |  | Branch a new PR off an unmerged base PR, keep it in sync, and re-target it to `main` once the base merges |

### Issue management

| Skill | Aliases | What it does |
|----|----|----|
| [`brainstorm`](skills/brainstorm/SKILL.llms.md) |  | Socratic clarifying-question loop before any code/issue, ending in a plan file |
| [`start-task`](skills/start-task/SKILL.llms.md) | `st` | File a tracking issue (if none exists), branch, implement, open PR, ARDI to clean |
| [`grab-issue`](skills/grab-issue/SKILL.llms.md) | `gi` | Pick the highest-priority open issue and work it end-to-end |
| [`grab-issues-in-parallel`](skills/grab-issues-in-parallel/SKILL.llms.md) | `gip` | Grab multiple issues and work them in parallel worktrees |
| [`defer-issue`](skills/defer-issue/SKILL.llms.md) |  | File a follow-up issue for something out of scope in the current PR |
| [`cancel-superseded`](skills/cancel-superseded/SKILL.llms.md) | `cb` | Close issues/PRs that a merged PR made redundant |
| [`discussions`](skills/discussions/SKILL.llms.md) |  | Read and respond to GitHub Discussions topics; mark Q&A answers |
| [`migrate-discussion`](skills/migrate-discussion/SKILL.llms.md) |  | Move an item between Discussions and Issues when it fits the other tracker better |

### Branch / sync

| Skill | Aliases | What it does |
|----|----|----|
| [`sync-pr-branch`](skills/sync-pr-branch/SKILL.llms.md) | `sync`, `merge-main`, `resync-branch` | Fetch origin, merge main into the branch, push |
| [`merge-it`](skills/merge-it/SKILL.llms.md) | `merged` | Squash-merge a ready PR, then run post-merge cleanup |
| [`mwc`](skills/mwc/SKILL.llms.md) | `merge-when-confident`, `maw`, `merge-at-will` | Grant session-scoped permission to merge fully-clean PRs without asking per PR |
| [`post-merge`](skills/post-merge/SKILL.llms.md) |  | After a merge: checkout main, pull, delete branch, run UMS |
| [`clean-branches`](skills/clean-branches/SKILL.llms.md) | `cb`, `prune` | Delete local branches already merged or closed |
| [`clean-worktrees`](skills/clean-worktrees/SKILL.llms.md) | `cw`, `prune-worktrees` | Remove dead git worktrees left behind by merged PRs and ended sessions |
| [`clean-git`](skills/clean-git/SKILL.llms.md) |  | Sweep dead worktrees then dead branches in one pass, in the order that works |
| [`resolve-conflicts`](skills/resolve-conflicts/SKILL.llms.md) | `rmc` | Resolve merge/rebase/cherry-pick conflicts by consolidating the best of both branches |

### Memory and skills maintenance

| Skill | Aliases | What it does |
|----|----|----|
| [`ums`](skills/ums/SKILL.llms.md) | `update-memories-and-skills` | Capture learnings from the session into memory files and skill definitions |
| [`memorize`](skills/memorize/SKILL.llms.md) | `remember`, `always` | Save a specific fact or preference to memory |
| [`push-memory`](skills/push-memory/SKILL.llms.md) |  | Push a general-purpose memory into ai-config from a session working in another repo — on a branch + PR |
| [`record-learnings`](skills/record-learnings/SKILL.llms.md) |  | Structured post-mortem: extract lessons from a completed task |
| [`consolidate-memory`](skills/consolidate-memory/SKILL.llms.md) |  | Merge or deduplicate memory files that have drifted |
| [`skill-audit`](skills/skill-audit/SKILL.llms.md) |  | Report which skills actually fire (and how often) vs. dead weight, and recommend pruning candidates |
| [`learn`](skills/learn/SKILL.llms.md) |  | Stage a candidate learning without yet deciding if it’s durable enough to commit |
| [`promote-memory`](skills/promote-memory/SKILL.llms.md) |  | Review staged learnings and promote the durable ones into committed memory |

### Writing and style

| Skill | Aliases | What it does |
|----|----|----|
| [`use-preferred-style`](skills/use-preferred-style/SKILL.llms.md) | `style` | Apply the plain-prose writing guide to a draft |
| [`find-ai-tells`](skills/find-ai-tells/SKILL.llms.md) | `ai-tells` | Scan text for AI-sounding patterns and flag them |
| [`fact-check-prose`](skills/fact-check-prose/SKILL.llms.md) | `fcp` | Check prose claims, reasoning, and computed values against sources and rendered output |
| [`fix-forward-references`](skills/fix-forward-references/SKILL.llms.md) | `ffr` | Detect and rearrange/reword forward-pointing references (“see below”) in prose |
| [`detect-informal-definitions`](skills/detect-informal-definitions/SKILL.llms.md) |  | Find concepts defined with definitional precision that never got wrapped in a formal definition div |
| [`detect-hypothetical-examples`](skills/detect-hypothetical-examples/SKILL.llms.md) |  | Find worked examples using invented numbers when a real dataset is already available |
| [`use-math-macros`](skills/use-math-macros/SKILL.llms.md) | `macroize` | Rewrite manuscript math onto the shared d-morrison/macros submodule |
| [`tidy`](skills/tidy/SKILL.llms.md) |  | Clean up code or prose without changing behavior |
| [`simplify`](skills/simplify/SKILL.llms.md) |  | Reduce a file or function to its essential parts |

### Repo / CI utilities

| Skill | Aliases | What it does |
|----|----|----|
| [`convert-repo-format`](skills/convert-repo-format/SKILL.llms.md) | `crf` | Convert a repo between the lab’s template formats (R package, Quarto website/book/manuscript) |
| [`scout-peers`](skills/scout-peers/SKILL.llms.md) |  | Survey comparable repos for ideas and conventions |
| [`check-dependency-updates`](skills/check-dependency-updates/SKILL.llms.md) | `cdu` | Check for outdated dependencies and propose updates |
| [`dependabot`](skills/dependabot/SKILL.llms.md) |  | Add or update Dependabot config for a repo |
| [`send-upstream`](skills/send-upstream/SKILL.llms.md) | `sup` | Open a PR or issue in an upstream repo for a bug found here |
| [`reprexes`](skills/reprexes/SKILL.llms.md) |  | Build minimal reproducible examples for a bug |
| [`r-pkg-spellcheck`](skills/r-pkg-spellcheck/SKILL.llms.md) |  | Spell-check an R package’s documentation |
| [`r-pkg-check`](skills/r-pkg-check/SKILL.llms.md) |  | Run `devtools::check()`/`R CMD check` and triage the results |
| [`r-pkg-news`](skills/r-pkg-news/SKILL.llms.md) |  | Draft a new NEWS.md entry for an R package |
| [`r-pkg-cran-checklist`](skills/r-pkg-cran-checklist/SKILL.llms.md) |  | Walk through the standard CRAN submission checklist |
| [`reproducibility-audit`](skills/reproducibility-audit/SKILL.llms.md) |  | Audit a project for reproducibility gaps: hidden deps, hardcoded paths, undocumented prerequisites, output traceability |
| [`measure-performance`](skills/measure-performance/SKILL.llms.md) | `perf`, `benchmark` | Profile R code to find the real bottleneck, microbenchmark only that, then confirm the win survives end to end |
| [`refresh-claude-token`](skills/refresh-claude-token/SKILL.llms.md) | `rct` | Rotate `CLAUDE_CODE_OAUTH_TOKEN` across the repos that carry it, without `/install-github-app`’s workflow scaffolding, then verify the new token authenticates |

### Session management

| Skill | Aliases | What it does |
|----|----|----|
| [`session-lock`](skills/session-lock/SKILL.llms.md) | `deconflict-sessions` | Register/deregister this session to prevent parallel clobbering |
| [`handoff`](skills/handoff/SKILL.llms.md) |  | Snapshot work state (branch, jobs, open decisions) so the next session can resume cleanly |
| [`wrap-up`](skills/wrap-up/SKILL.llms.md) | `done`, `merged` | Verify true PR/issue/branch state, report a linked summary, then run UMS |
| [`select-model`](skills/select-model/SKILL.llms.md) | `model-fit`, `assess-model-fit` | Choose the right Claude model for the task at hand |
| [`away`](skills/away/SKILL.llms.md) |  | Grant session-scoped permission to stop asking clarifying questions, pick confident work, and consult a stronger model instead of blocking |
| [`back`](skills/back/SKILL.llms.md) |  | Cancel the `away` grant and surface a decision log of what was resolved unattended |
| [`daytb`](skills/daytb/SKILL.llms.md) | `do-as-you-think-best` | Decide the question at hand yourself and report the choice – scoped to that task, unlike `away`’s whole-session grant |
| [`delegate-to-codex`](skills/delegate-to-codex/SKILL.llms.md) | `dtc` | Offload heavy read/draft/verify work to the `codex` CLI before spending Claude quota, with Claude fallback |
| [`delegate-to-opencode`](skills/delegate-to-opencode/SKILL.llms.md) | `dto` | Offload mechanical work to opencode’s free hosted or fully local models, and route anything that must stay on the machine to the local tier |
| [`prompt-me`](skills/prompt-me/SKILL.llms.md) | `pm` | Surface the single most pressing open question (or top N) waiting on user input |
| [`prompt-me-all`](skills/prompt-me-all/SKILL.llms.md) | `pma` | Restate every open question still waiting on user input, uncapped |
| [`pending-decisions`](skills/pending-decisions/SKILL.llms.md) | `pd` | Sweep issues/PRs (not just this conversation) for ones waiting on a decision from you, and ask about them one at a time |
| [`checkpoint`](skills/checkpoint/SKILL.llms.md) |  | Save a deliberate mid-task snapshot without ending the session |
| [`compress-session`](skills/compress-session/SKILL.llms.md) |  | Distill the session into auto memory before context fills up |
| [`permission-check`](skills/permission-check/SKILL.llms.md) |  | Diagnose why Claude Code is (or isn’t) prompting for permission on an action |

## Full skill list

All 181+ canonical skills are in [`skills/`](https://github.com/Morrison-Lab/ai-config/tree/main/skills) on GitHub. Generated Codex wrappers live in [`codex-skills/`](https://github.com/Morrison-Lab/ai-config/tree/main/codex-skills). Each canonical `SKILL.md` has a `description` field that lists the trigger phrases and a full procedure.

Back to top
