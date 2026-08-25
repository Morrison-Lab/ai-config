---
name: record-learnings
description: "Persist insights to memory."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# record-learnings

As you work, actively record what you learn so it's available in future
sessions — both to you and to other AI agents sharing the same config.

## When this fires

- After solving a non-obvious bug (record the diagnosis + fix)
- After discovering a codebase convention (record in repo memory)
- After learning a tool quirk (record in user memory)
- After a failed approach (record what didn't work and why)
- After finding a useful command or pattern (record it)
- When the user says "remember that..." (write it to the memory system directly)

## Where to write

### User-wide memory (`/memories/`)
For facts that apply across all projects:
- Tool quirks (e.g., "gh opens a pager — always pipe to cat")
- Debugging patterns (e.g., "CRLF causes bash EOF errors")
- General preferences
- Cross-project conventions

When you add a *new* file under `/memories/` (not just a bullet to an existing
one), register it in `memories/MEMORY.md` as an index entry.

### Repository-specific facts (that project's own repo)
For facts specific to ONE repo (build quirks, project conventions, CI
behavior), if it's a repo **we own**: commit them to **that repo's own
agent docs** via a PR (`CLAUDE.md`, `.github/copilot-instructions.md`, or
whatever agent-doc infrastructure it already has), so the whole team and
every `@claude` session there can see them. If that repo has no agent-doc
infrastructure yet, write to its local Claude project memory directory
instead — `~/.claude/projects/<project-path>/memory/` — as **short-lived
staging only, not a durable destination**, and flag that a PR adding
agent-doc infrastructure to that repo (plus migrating the staged memory
there) is still needed. The project path is the repo's directory path
with `/` replaced by `-` — e.g. `/Users/you/Documents/GitHub/rme` →
`~/.claude/projects/-Users-you-Documents-GitHub-rme/memory/`. Update
`MEMORY.md` in that directory as an index when you used this local-staging
fallback — not when the fact was committed directly to the owned repo's
own agent docs, which needs no local copy.

For an **external repo we don't own**, never open a direct PR
autonomously — follow [`upstream-issues`](../../shared/workflow/upstream-issues.md):
check its contribution policy first, then draft and get explicit user
approval before posting anything. Stage the fact in local Claude project
memory (short-lived, not durable) until approved, and update that
directory's `MEMORY.md` as an index entry, same as the owned-repo staging
fallback above.

### Shared ai-config skills (`~/.claude/skills/`)
For reusable workflows that other agents should also follow:
- Multi-step procedures (review loops, deployment steps)
- Decision frameworks (when to defer, when to split MRs)
- Tool integration patterns (forge CLI usage)

### CLAUDE.md / copilot-instructions.md
For standing instructions that should always be in context:
- Only for the most critical, always-applicable rules
- Keep these files short — they're loaded every session

## What to record

| Category | Example | Where |
|----------|---------|-------|
| Bug diagnosis | "bash EOF error = CRLF line endings" | `/memories/debugging.md` |
| Tool quirk | "glab has no GITLAB_TOKEN env var" | The matching topical file -- `/memories/github.md` here; see `memories/MEMORY.md` |
| Codebase fact | "CI only runs on branch pushes, not PR events" | That repo's own agent docs (or staging) |
| Workflow | "Always run r-pkg-spellcheck before push" | Skill file |
| Preference | "Always request d-morrison as reviewer" | `/memories/preferences.md` |
| Failed approach | "Don't use merge_request_event with $CI_OPEN_MERGE_REQUESTS" | That repo's own agent docs (or staging) |

## Process

1. **Recognize the learning moment** — you just solved something, discovered
   something, or the user told you something worth remembering
2. **Categorize** — is it user-wide, repo-specific, or a reusable workflow?
3. **Check existing notes** — read the target file first to avoid duplicates
   and maintain organization
4. **Write concisely with temporal qualifications** — bullet points, not
   prose.
   Include the *why* not just the *what*.
   When recording facts about any software, tools, APIs, harnesses, or technologies,
   always attach explicit temporal bounds and provenance
   (e.g. `Measured YYYY-MM against version X / snapshot reference`)
   and state that third-party behavior evolves across releases.
   If you created a *new* file under `/memories/`, also add a row for it to
   `memories/MEMORY.md` (the index)
5. **Deliver, per where step 2/3 routed it:**
   - **Repository-specific fact, a repo we own** — commit it to that repo's
     own agent docs via a PR (`CLAUDE.md`, `.github/copilot-instructions.md`,
     or whatever it already has). If that repo has no agent-doc
     infrastructure yet, write to its local Claude project memory instead as
     short-lived staging only (update that directory's `MEMORY.md` as an
     index entry), and hand off that a PR adding agent-doc infrastructure
     (plus migrating the staged memory there) is still needed.
   - **Repository-specific fact, an external repo we don't own** — never
     open a direct PR autonomously; follow `upstream-issues` (policy check,
     draft, explicit user approval), staging in local project memory
     (update `MEMORY.md` there too) until
     approved.
   - **User-wide memory** --- commit and push to `Morrison-Lab/ai-config`
     (branch + PR if none is open yet).
6. **If it's a skill (or a dedicated fan-out worker)** — hand off to
   `spot-skill-opportunities` to judge whether the pattern is genuinely
   recurring (not a one-off), then to `skill-builder` to scaffold a new
   user-invocable workflow in `~/.claude/skills/` (symlink to the cloned repo;
   discover the repo path with
   `git -C ~/.claude/skills/record-learnings rev-parse --show-toplevel`), or to
   `agent-builder` to scaffold a persistent read-only subagent in
   `.claude/agents/` when the pattern is really a worker persona a heavy
   skill's fan-out step needs.

## Sharing with other agents

The `~/.claude/skills/` directory is a symlink to wherever you cloned
`ai-config` (discover the path with
`git -C ~/.claude/skills/record-learnings rev-parse --show-toplevel`).
Any skill written there is:
- Available to this agent via the skills system
- Shareable with other agents by cloning/pulling the ai-config repo
- Version-controlled and reviewable via PRs

When creating a new skill that other agents should use:
1. Write it in `~/.claude/skills/<name>/SKILL.md`
2. Branch, commit, push, and open a PR on the ai-config repo
3. The skill becomes available locally immediately (via symlink)
4. Other agents get it after the PR merges and they pull

## General guidance = update both skills AND preferences

When the user provides general guidance or a new preference (not just a one-off
instruction), always update **both**:
1. The relevant skill file(s) — so the behavior is encoded in the workflow
2. `/memories/preferences.md` — so it persists and is visible across all contexts

Skills without a matching preference risk being forgotten when the skill isn't
invoked. Preferences without matching skill updates risk being ignored during
skill-driven workflows.

## Always push skill changes

After adding or updating any skill file, always commit and push to origin:
- If a PR/branch for skill changes is already open, push there.
- Otherwise, create a new branch + PR on the ai-config repo.
- Never leave skill edits as local-only uncommitted changes.

## Relationship to other skills

- **`spot-skill-opportunities`** — the dedicated recognition step for the
  "is this a skill?" case in step 6 above; hand off to it rather than judging
  recurrence inline here.
- **`skill-builder`** — scaffolds the `SKILL.md` once `spot-skill-opportunities`
  (or this skill directly) decides a new one is warranted.
- **`agent-builder`** — the same construction step for a dedicated read-only
  fan-out worker (`.claude/agents/<name>.md`) rather than a user-invocable
  skill.
- **`ums`** — the reflective, full-context-sweep counterpart to this skill's
  in-place, fact-at-a-time recording. Both fire proactively, as the learning
  or fact arises; `ums` additionally runs as a backstop before `/clear`.
- **`learn`** — the lower-friction sibling for a candidate you're not yet
  confident enough to commit directly: stage it there instead, and let
  `promote-memory` review it later. Use this skill (or `memorize`) when
  you're already confident the fact belongs in committed memory; use `learn`
  for the genuinely uncertain middle ground.

## Anti-patterns

- ❌ Learning something and not writing it down
- ❌ Writing a long paragraph when a one-line bullet suffices
- ❌ Recording in session memory what should be permanent
- ❌ Updating only a skill OR only preferences when general guidance is given
- ❌ Editing skills locally without committing and pushing to origin
- ❌ Duplicating information already in a skill file
- ❌ Forgetting to check if a note already exists before adding
- ❌ Recording software or technology facts as timeless present-tense truths without temporal bounds (date/version/snapshot)
