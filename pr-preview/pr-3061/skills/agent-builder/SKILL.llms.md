# agent-builder — author a new subagent definition (extend-first)

Create — or, preferably, *reuse* — a `.claude/agents/<name>.md` custom subagent definition for a skill’s fan-out step. This is `skill-builder`’s counterpart for the other kind of file this repo ships: a persistent, harness-registered **subagent persona**, not a user-invocable workflow. The prime directive mirrors `skill-builder`’s: **don’t scaffold a new agent until you’ve confirmed no existing agent should be reused instead**, and a persistent agent file only earns its keep when a plain inline `Agent()` prompt in the calling skill isn’t enough.

## When this fires

- “build an agent”, “create a subagent”, “make a new agent”, “add an agent”, “agent-builder”
- While authoring or extending a heavy, fan-out-shaped skill (see `when-to-orchestrate.md`) and the per-item worker needs a **fixed, narrower tool boundary** than the calling skill itself has — e.g. a detection or audit pass that must not be able to mutate anything, even by accident.
- Proactively, the same way `spot-skill-opportunities` proposes a new skill: notice the pattern, propose scaffolding an agent, don’t build one unasked.

## Step 0 — Reuse or extend before you create (do this FIRST, always)

1.  **List the existing agents and read their roles:**

    ``` bash
    ls .claude/agents/
    ```

    Each one pairs 1:1 with a skill (`dependency-auditor` → `check-dependency-updates`, `hallucination-detector` → `purge-hallucinations`, `community-demand-scout` → `opposition-research`). Check whether an existing role already covers this concern under a different target — often the fix is parameterizing the *calling skill’s* prompt to the existing agent, not building a new persona.

2.  **Ask whether this needs a persistent file at all.** An inline `Agent()` / `agent()` prompt (see `skill-builder`’s “If the skill fans out to subagents” section) is enough unless: (a) more than one skill would spawn the same persona, or (b) the harness-enforced tool restriction is itself load-bearing — e.g. guaranteeing a detection pass *can’t* accidentally write, which an inline prompt can’t guarantee (the calling skill’s own tools still apply).

3.  **Check open PRs too** — another session may already have an in-progress draft agent that never landed as a local branch you’d see. See [`check-open-prs-before-duplicating`](../../shared/workflow/check-open-prs-before-duplicating.md).

4.  **State explicitly: reuse, extend, or new** — and why — before writing a line.

## Anatomy of an agent definition

    .claude/agents/<name>.md

``` yaml
---
name: <name>                 # kebab-case, role-noun compound: <domain>-<role>
description: <what it audits/detects/scouts>, what it lacks (Edit/Write/Bash)
  and why, and which skill spawns it as its fan-out worker
tools: Bash, Read, Grep, Glob, WebFetch    # comma-separated STRING, not a
                                            # YAML list (unlike skills'
                                            # `allowed-tools:`)
---
```

Body shape: an opening line “You are the `<role>` half of the `<skill>` skill.”, a numbered procedure for what to check/verify/mine, an explicit output-shape spec (what to return, in what order), and a closing reminder of exactly which mutating tools are absent and why avoiding shell-based writes with the tools it does have is instruction-level discipline, not harness-enforced. Match the tone and structure of the three existing agents — they read almost as a template.

## Conventions (match the existing family)

- **Naming:** `<domain>-<role>` compound noun (`dependency-auditor`, `hallucination-detector`, `community-demand-scout`) — not a verb phrase, not a generic name like `helper` or `worker`.
- **Default to read-only.** Omit `Edit` and `Write` from `tools:` unless the agent’s entire purpose is to mutate files (rare — none of the three existing agents do). If `Bash` is present without `Edit`/`Write`, say explicitly in the `description` that `Bash` could still write and that avoiding write-capable shell commands is instruction-level, not harness-enforced — `dependency-auditor` and `hallucination-detector` both carry this caveat (they have `Bash`). `community-demand-scout` sidesteps the issue entirely by omitting `Bash` from `tools:` — prefer that when the agent’s job doesn’t need shell access at all.
- **Pair 1:1 with the skill that spawns it.** Name that skill in the opening clause of `description` (“Read-only audit pass for check-dependency-updates (cdu)”).
- **Write the prompt as if the calling skill’s `SKILL.md` doesn’t exist** — a spawned agent never sees it. Restate every needed discipline (the exact query, source priorities, output shape) inside the agent file itself, the same rule `skill-builder`’s subagent-fanning section states for inline prompts.
- **No registry to update.** Agents are auto-discovered from `.claude/agents/` (mirrors skills’ auto-discovery from `skills/`) — adding the file is enough for the harness to expose it as a `subagent_type`. There is currently no `validate-skills.py`-equivalent lint for `.claude/agents/`, so hand-check: `name:` matches the filename, `tools:` is a comma-separated string (not a YAML list), and `description` states the role, its tool limits, and the calling skill.

## Worker-role archetypes (beyond the read-only default)

The six existing agents are all one archetype — a **scout**: read-only, reports back to the calling session, no authority to act on its own findings. That’s still the right default (see Conventions above), but three other roles are legitimate reasons to deviate from it:

- **Bounded worker** — granted `Edit`/`Write` to perform one scoped implementation task, not just an investigation. Still rare (see Conventions), but when a task genuinely needs it: name the exact file(s) or path glob it may touch in the `description`, state what it must NOT touch, and have it report back what it changed — the same output-shape discipline a scout uses for findings.
- **Critic** — reviews another agent’s (or the coordinator’s own) output instead of investigating the repo fresh. [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) is this repo’s one named critic, and it cleared the promotion bar below because every self-review routes to it — [`push`](../../skills/push/SKILL.llms.md), [`ardi`](../../skills/ardi/SKILL.llms.md), and the fallback review in [`self-review-fallback`](../../shared/workflow/self-review-fallback.md) ([`adversarial-self-review`](../../shared/workflow/adversarial-self-review.md)). A `Workflow` script’s `pipeline()`/`parallel()` verify stage (see [`when-to-orchestrate.md`](../../shared/workflow/when-to-orchestrate.md)) is the other way this repo gets adversarial review — an inline prompt, not a named persona. Promote a new critic to a `.claude/agents/*.md` file only once more than one skill wants that same critic behavior — Step 0’s reuse-first rule applies here too.
- **Paranoid reviewer** — a critic deliberately run at higher cost/effort (see `select-model` and `when-to-orchestrate.md`’s model/effort routing section) for consequential or subtle work, where a same-family second pass risks repeating the first pass’s own blind spot. For the highest-stakes case, run the critic on a genuinely different model family via [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md) instead of another Claude subagent — that skill’s “verify” step already covers reviewing Claude’s own prior output, not just fresh investigation.

None of this changes the `tools:` frontmatter schema (there is no `model`/`effort` field there, and there shouldn’t be — pin the model/effort choice in the *calling* skill’s `agent()`/`Agent()` invocation instead, so the same persona file stays reusable across tiers).

## Can an agent build another agent?

Mechanically, yes: any subagent granted `Edit`/`Write` (the default `general-purpose` agent, or a custom agent you don’t restrict) can write a new `.claude/agents/*.md` file exactly like any other file — nothing in the harness singles out agent-definition files as unwritable. But this repo doesn’t delegate agent-authoring that way. Building an agent is an *authoring* task, and every authoring task in this corpus — including `skill-builder` itself — runs in the **main session**, not a spawned worker, so a human-in-the-loop stays on the naming, tool-scoping, and reuse-check decisions in Step 0. The fan-out workers this skill creates are deliberately read-only in part so they *can’t* self-modify or spawn siblings unsupervised. Keep authoring inline; reserve spawned agents for the narrow, read-only, single-purpose jobs the existing three model.

## Register the new agent with its calling skill

There’s no central agent list to update (see above) — “registering” a new agent means updating the **one skill** that spawns it, via one of two mechanisms:

1.  **Inline fan-out call**, when the skill only needs the agent for one step and continues afterward in the calling session — add `Agent(subagent_type: "<name>", ...)` in that step, or inside a `Workflow` script, `agent(prompt, {agentType: "<name>"})`.
2.  **Declarative `context: fork`**, when the agent’s own procedure covers the skill’s *entire* body end to end — add `context: fork`, `agent: <name>`, and (usually) `background: false` to the skill’s own frontmatter, per the [Run skills in a subagent](https://code.claude.com/docs/en/skills#run-skills-in-a-subagent) docs section. See `skill-audit`/`find-overlap` for the pattern.

**The two are not interchangeable, and picking the wrong one silently breaks a write step.** With `context: fork`, tool access comes from the `agent:` type, not the skill’s own `allowed-tools` — the whole skill body becomes the forked subagent’s task, so there is no way to fork only a sub-step. A skill whose procedure mixes a read-only detect phase with a **main-session-only** write/PR/interactive-confirmation follow-through (`reproducibility-audit`, `purge-hallucinations`, `fact-check-prose`, `check-info-quality` all do this — see \#914) cannot use mechanism 2 without restructuring into two skills first: forking the whole thing to a read-only custom agent would strip the write access the follow-through needs, not replace it declaratively. Reach for mechanism 2 only when every step in the skill needs no more than the agent’s own `tools:` list — confirm this by reading the skill’s full procedure, not by assuming a skill that already pairs with a read-only agent is automatically eligible.

Either way:

1.  Name the `.claude/agents/<name>.md` path explicitly in the skill body (grep `check-dependency-updates`, `purge-hallucinations`, or `opposition-research` for the inline pattern; `skill-audit` or `find-overlap` for the declarative one).
2.  If the skill’s procedure names a GitHub MCP tool the agent will call, register it in `tool-mappings.yml` per `skill-builder`’s rule — the same possible-hallucination risk applies to agent-spawning skills.

## Ship it

Agent files and skills both live in the ai-config repo — never local-only. Branch + PR + ARDI, the same flow as `skill-builder`.

> **In a worktree session, the same hazard applies as in `skill-builder`’s ship-it:** the repo toplevel below is the MAIN checkout, not your worktree. The plugin install or checkout points to the main `ai-config` checkout, so `${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/agent-builder rev-parse --show-toplevel 2>/dev/null || pwd)}` returns the main repo root — often on another session’s branch. Don’t `cd` there and don’t pass that path to Write/Edit. Author `.claude/agents/<name>.md` and the calling skill’s `SKILL.md` in your **worktree’s own** checkout instead, and confirm with `git branch --show-current` before committing. See `skill-builder`’s ship-it section for the full explanation.

``` bash
cd "${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/agent-builder rev-parse --show-toplevel 2>/dev/null || pwd)}"   # ai-config root — NOTE: the MAIN checkout, NOT your worktree (see caveat above)
git fetch origin main && git checkout -b add-<name>-agent origin/main   # FETCH, CREATE_BRANCH
# write .claude/agents/<name>.md, and update the one calling skill's SKILL.md
# The `validate` CI job runs these four — run all four locally before pushing,
# same as skill-builder — since this also touches the calling skill's SKILL.md:
python3 scripts/validate-skills.py   # sanity-checks skills/, not agents/ yet — still run it
python3 scripts/check-links.py       # relative links in the updated calling skill
python3 scripts/check-vendored-drift.py
npx --yes markdownlint-cli2@0.22.1   # markdown style on the updated skill's SKILL.md
git add .claude/agents/<name>.md skills/<calling-skill>/SKILL.md   # stage only what you touched
git commit -m "agents: add <name> — <summary>"   # COMMIT
git push -u origin HEAD && gh pr create --fill   # PUSH, CREATE_PR
```

Then, as explicit steps:

1.  **Request the reviewer:** `gh pr edit --add-reviewer <reviewer>` (`EDIT_PR`; see `request-pr-review`).
2.  **Drive to clean:** run `ardi` on the new PR until the verdict has zero findings.

## A second consumer: agent-team teammate roles

An agent definition has a use beyond the fan-out subagent it is built for: it also doubles as an **agent-team teammate role**. When a user asks a team lead to spawn a teammate “using the `<name>` agent type”, the definition’s `tools` allowlist and `model` apply and its body is appended to the teammate’s system prompt — but its `skills` and `mcpServers` frontmatter are **not** applied (a teammate loads those from project and user settings), and `SendMessage` plus the task-management tools are always available regardless of `tools`. So write the persona and tool boundary to stand on their own, and don’t rely on a definition’s `skills` reaching a teammate. See [`agent-teams`](../../shared/workflow/agent-teams.md) for when a team is the right primitive at all — it is user-gated and experimental, so this is a reuse property of the file, never a thing this skill or its agents spawn.

## Relationship to other skills

- **`skill-builder`** — the skill-authoring sibling; this is its subagent-file counterpart. Use `skill-builder` when the new capability is a user-invocable workflow; use this one when it’s a read-only fan-out worker a skill spawns.
- **`spot-skill-opportunities`** — recognizes when a *skill* is needed; the same in-the-moment recognition applies to noticing a heavy skill’s fan-out step would benefit from a dedicated persona instead of an inline prompt — hand off here for that case.
- **`ums` / `record-learnings`** — when a session reveals that a fan-out step needs a tighter, reusable worker persona (not just a skill gap), route here instead of, or alongside, `skill-builder`.
- **`heal-skill`** — repairs a skill that misfired; if the root cause is actually the spawned agent’s prompt or tool-scoping (wrong persona, too-loose tools), fix the `.claude/agents/*.md` file via this skill’s conventions rather than editing the calling skill.
- **`link-skills`** — the cross-link auditor for skills, though it currently scans only `skills/` and doesn’t check `.claude/agents/`. Until it’s extended to cover agent files, manually verify that a skill naming a custom agent is named back in that agent’s `description`.
- **`config-ai`** — the broader router this skill is one destination for: when a request names a capability but not a mechanism, `config-ai` decides whether it’s a subagent (→ here), a skill, a memory, a hook, or a `gha` capability, then hands off accordingly.

## Anti-patterns

- ❌ Creating a new agent when an existing persona, parameterized differently, would do.
- ❌ Not checking open PRs → building a second draft of an agent someone already pushed and opened a PR for, instead of redirecting to it.
- ❌ Giving a read-only fan-out worker `Edit`/`Write` “just in case.”
- ❌ Writing the agent’s system prompt assuming it inherits the calling skill’s text — restate every needed discipline explicitly.
- ❌ `tools:` written as a YAML list — agent frontmatter uses a plain comma-separated string, unlike skills’ `allowed-tools:`.
- ❌ Delegating the authoring itself to a spawned agent instead of doing it in the main session — naming, tool-scoping, and the reuse-check need a human-in-the-loop.
- ❌ Leaving the new agent unreferenced by any skill — an orphaned `.claude/agents/*.md` file with nothing to spawn it.
- ❌ Leaving the change local-only, or pushing straight to main.

Back to top
