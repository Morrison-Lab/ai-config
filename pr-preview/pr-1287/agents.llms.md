# Agents

Agents are custom **subagents** that Claude Code can delegate a task to via its built-in `Agent` tool. Each `.claude/agents/<name>.md` file gives a subagent a system prompt, a `description` (what Claude Code matches invocations against), and a restricted `tools` list. Claude Code discovers agents in `.claude/agents/` automatically — like skills, no separate registration step is needed once this repo is bootstrapped.

## Why read-only fan-out workers

Several skills fan a task out across many independent targets — one competitor community per research pass, one dependency pin per audit, one claim per fact-check — and want each target checked in parallel without risking a stray worker writing a file, filing an issue, or running a destructive command. Every agent in this repo omits `Edit` and `Write` from its `tools` list, so it can never call those tools to change a file — that restriction is **harness-enforced**. Three of the four agents also keep `Bash`, which *can* run write-capable shell commands (`git push`, `rm`, a redirect); for those, staying read-only is instruction-level discipline, not a harness guarantee (see the note below the table). Each agent returns a report; only the calling session, which keeps full tool access, applies fixes or writes anything, on the user’s go-ahead.

## Agents in this repo

| Agent | Tools | Used by | What it does |
|----|----|----|----|
| [`community-demand-scout`](https://github.com/d-morrison/ai-config/blob/main/.claude/agents/community-demand-scout.md) | `WebSearch`, `WebFetch`, `Read`, `Grep`, `Glob` | [`opposition-research`](skills/opposition-research/SKILL.llms.md) (`oppo`) | Mines one competitor community surface — an issue tracker, feature-request board, subreddit, Q&A site, forum, or review site — for user-demanded features, and reports each with demand evidence and a source link |
| [`dependency-auditor`](https://github.com/d-morrison/ai-config/blob/main/.claude/agents/dependency-auditor.md) | `Bash`, `Read`, `Grep`, `Glob`, `WebFetch` | [`check-dependency-updates`](skills/check-dependency-updates/SKILL.llms.md) (`cdu`) | Surveys pinned GitHub Actions tags/SHAs, `renv.lock` versions, pre-commit revs, Quarto/tool versions in CI, and submodules for available upgrades, reads changelogs, and reports what each bump would buy |
| [`hallucination-detector`](https://github.com/d-morrison/ai-config/blob/main/.claude/agents/hallucination-detector.md) | `Bash`, `Read`, `Grep`, `Glob`, `WebFetch` | [`purge-hallucinations`](skills/purge-hallucinations/SKILL.llms.md) (`ph`) | Verifies concrete, checkable references — files, functions, action refs, URLs, citations, config keys — against ground truth and sorts each into Resolves / Fabricated / Unverifiable |
| [`prose-fact-checker`](https://github.com/d-morrison/ai-config/blob/main/.claude/agents/prose-fact-checker.md) | `Bash`, `Read`, `Grep`, `Glob`, `WebFetch`, `WebSearch` | [`fact-check-prose`](skills/fact-check-prose/SKILL.llms.md) (`fcp`) | Checks one factual claim, reasoning step, or computed value/figure against domain knowledge, an external source, or a rendered artifact, and returns a verdict naming the exact source it checked |

`dependency-auditor`, `hallucination-detector`, and `prose-fact-checker` all keep `Bash` for read-only checks (`grep`, `gh api`, `git submodule status`, `test -e`) — avoiding a write-capable shell command (`renv::update()` without `check = TRUE`, `pre-commit autoupdate`) is instruction-level discipline for those three, not a harness-enforced restriction the way the missing `Edit`/`Write` is.

## How they’re invoked

The calling skill fans work out to one of these agents through Claude Code’s `Agent` tool, passing a scope line — what to check, against what — rather than letting the agent pick its own scope. To use one standalone rather than through its usual skill, invoke the `Agent` tool with `subagent_type` set to the agent’s name and describe the single target to check.

Back to top
