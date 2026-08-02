# config-ai — route AI-capability requests to the right implementation (ca, cai)

This skill doesn’t build anything itself. It figures out *what kind* of thing a capability request needs, then hands off to the skill (or repo convention) that actually builds it — with a repo-access-aware fallback so a request never gets silently dropped just because the current session can’t push to `ai-config` or `gha`.

## When this fires

- “config-ai”, “ca”, “cai”
- “extend AI capabilities”, “add an AI capability for X”, “teach Claude to X”, “give Claude the ability to X”, “make Claude able to X”, “wire this up so Claude always/automatically does X”
- A request names a desired behavior without naming a mechanism — that’s the tell that this skill, not a specific builder skill, is the right entry point.

## Step 0 — Restate the capability, not the mechanism

State in one sentence what the requester wants Claude (or Codex, or the `@claude` bot, or a `gha` consumer’s CI) to be able to do. Don’t presuppose the implementation yet — “add a hook that reminds me to X” is already half an answer the requester may not have meant.

Then check it’s actually reusable, not a one-off. A single favor for right now doesn’t need infrastructure — just do it. `config-ai` is for capability that should persist beyond this conversation.

## Step 1 — Pick the implementation form

Work down this table; stop at the first row that fits. Each row hands off to the skill or convention that owns that mechanism — this skill does not duplicate their build steps.

| The capability is… | Form | Home | Hand off to |
|----|----|----|----|
| A repeatable, multi-step procedure a user (or the `@claude` bot) invokes on demand | Skill | `ai-config` `skills/<name>/` | `skill-builder` |
| A persistent, read-only fan-out worker persona a heavy skill spawns | Subagent | `ai-config` `.claude/agents/<name>.md` | `agent-builder` |
| A standing fact, preference, or behavioral rule Claude should just know | Memory / `CLAUDE.md` section | `ai-config` `memories/`, `CLAUDE.md`, or a `shared/<category>/<name>.md` fragment | `memorize` (working repo is `ai-config`) or `push-memory` (working repo is something else) |
| An automated action the harness itself must trigger on an event Claude doesn’t control the timing of (session start, before/after a tool call, on stop) | Hook | `ai-config` `.claude/settings.json` (project-level; a user-level hook goes in `~/.claude/settings.json` instead, which is not synced from this repo) | the harness’s built-in `update-config` skill (not part of this repo’s `skills/` tree) |
| Reusable text shared verbatim across multiple skills or docs — not itself a rule | Shared prompt fragment | `ai-config` `shared/<category>/<name>.md`, referenced with `@shared/...` | no builder skill owns this; follow the existing `shared/` layout (`coding/`, `vendored/`, `workflow/`, `writing/`) and wire the `@shared/...` reference into `CLAUDE.md` and/or the skill(s) that need it |
| A capability *other repos’* CI should be able to call — a composite action a workflow step runs, or a `workflow_call` reusable workflow consumers pin to `@v1` | GitHub Action | `gha` repo root composite + `.github/workflows/<name>.yml` wrapper + `examples/<name>.yml` | follow `gha`’s own `CLAUDE.md` “Layout” section: composite (+ helper script if R/Python) → wrapper → example stub → `README.md`/`website/` doc sync (see its “new `workflow_call` input” doc-sync-site list) |
| A change to how the `@claude` bot itself behaves when invoked on a PR/issue — not what it can do for consumers, how *it* runs | Bot CI workflow | `gha` `.github/workflows/claude.yml` or `claude-code-review.yml` | `claude-agent-workflow` (agent/action workflow) or `claude-review-workflow` (PR review workflow) |

If more than one row plausibly fits (common: “always check X before Y” could be a memory *or* a hook), prefer the **least mechanism**: memory over hook (a hook needs harness config that can silently stop firing if `settings.json` drifts; a memory just needs Claude to read `CLAUDE.md`), a skill over a subagent (a subagent only earns its keep when reused across call sites or the tool boundary is load-bearing — see `agent-builder`’s step 2), and a shared fragment over a new skill when the content already lives inside another skill’s procedure and a new skill would just duplicate it.

**“Least mechanism” is a tiebreaker between two forms that would produce the *same behavior*, not a default toward the cheaper form when the request’s own phrasing signals something more active.** A request built around a verb — “go through X”, “trigger Y”, “sweep Z for W”, “check for V” — is naming a repeatable, on-demand *action*, which is what a Skill is for; reading it as a passive standing preference just because memory is the lighter mechanism produces an artifact that does something different from what was asked, not a cheaper version of the same thing. When it’s genuinely unclear which the user means, and the two readings would build materially different artifacts (not just the same content in a different location), ask before committing — one clarifying question costs far less than a full build-and-PR cycle spent on the wrong mechanism. (ai-config#583 vs. #585, 2026-07-16: “go through the decisions you need from me one at a time” was built as a `CLAUDE.md` standing rule about presentation — least mechanism, but the wrong reading. The user meant a skill that actively sweeps GitHub issues/PRs for decisions waiting on them; the `CLAUDE.md` rule turned out to be a useful, real, but *different* capability from the one asked for, requiring a second full issue → PR cycle to build the one actually requested.)

**The “Skill” row’s `ai-config skills/<name>/` home assumes the capability is reusable *across* repos.** When the capability only makes sense for one project’s own domain (game-specific terminology, a codebase’s own internal tooling) — especially when that project already has a precedent skill of its own under its `.claude/skills/` — extend or add to *that project’s* skill directory via a PR in that repo instead, the same way a project-specific memory goes in the project’s own docs rather than `ai-config`’s `memories/`. `skill-builder`’s own Step 0 reuse-check is scoped to the `ai-config` repo only, so run an equivalent check against the *project’s* own `skills/` dir by hand first — don’t rely on `skill-builder` to catch this case for you. (`Lacaedemon/sparta`, 2026-07-14: a request to check every demo for specific simulation-defect patterns — terminology with no meaning outside that one game — extended the project’s existing `.claude/skills/verify-via-state-dump/SKILL.md` rather than creating a new `ai-config` skill.)

## Step 2 — Reuse-check before building anything

Every mechanism above already has its own extend-first check; run it rather than scaffolding cold:

- Skill / subagent → `skill-builder` step 0 / `agent-builder` step 0 (search `skills/`, scan every branch and worktree, check open PRs).
- Memory → grep `memories/*.md` and `CLAUDE.md` for the same fact before adding a new bullet.
- Shared fragment → grep `shared/**/*.md` for the same content before writing a new file.
- `gha` capability → `ls` the repo root for an existing composite that’s adjacent, and check `examples/` for a stub that already covers it.
- Bot workflow → read the existing `claude.yml` / `claude-code-review.yml` end to end first; both skills document the load-bearing patterns not to break.

## Step 3 — Check push access to the target repo, then ship

The target repo is `ai-config` for the first five rows above, `gha` for the last two.

1.  **Can this session push to the target repo?** Check the session’s GitHub scope (the “Repository Scope” list in a remote/web session’s system prompt, or a `git remote -v` / `gh repo view <owner>/<repo>` probe locally), and whether a push would actually be accepted — a scoped session may be able to push only its own harness-assigned branch (see `CLAUDE.md`’s “Use the existing PR branch” 403 exception).
    - **Yes** → proceed normally: branch off `main` in the target repo, build via the skill/convention chosen in Step 1, open a PR, request review, `ardi` to clean. The common case; nothing extra needed from this skill.
2.  **No push access, but the session can still read the target repo and open issues on it** (GitHub MCP scope or `gh`/API access, just not write access to code) → don’t lose the request. File one fully-specified issue on the target repo describing: the capability in one sentence, the implementation form chosen in Step 1 and why, the target file(s)/path(s), and enough detail that a future `gi`/`grab-issue` session — which does have push access — can build it unattended. Don’t claim it (`claim-pr`’s “paws off” comment is for a session about to implement); leave it open for whoever picks it up.
3.  **No access to the target repo at all** (not in the session’s GitHub scope, no network path, issue creation itself fails) → file the issue in the **current** repo instead — whatever repo the session is actually working in. Write it standalone, since a future reader won’t have this conversation’s context: state plainly that it’s really a request for `ai-config`/`gha` and needs to move there. Ask the user to use GitHub’s **Transfer issue** feature once a session with access is available. This mirrors `shared/workflow/upstream-issues.md`’s own-repo fallback (its step 3), applied here because `ai-config`/`gha` are just as “upstream” of a differently-scoped session as any external dependency is.

Never silently drop a capability request because the current session happens to lack push access to the target repo — one of these three always applies.

## Relationship to other skills

- **`skill-builder`**, **`agent-builder`** — the construction steps for the first two rows of the decision table; this skill is the router that decides *which* of them (or a different mechanism entirely) applies, then gets out of the way.
- **`spot-skill-opportunities`** — proactively notices, mid-task, when a *skill or agent* specifically is warranted; narrower than this skill (only those two forms) and unprompted (it doesn’t wait for the user to name a capability). `config-ai` is the explicit, user-invoked entry point across the *full* mechanism set — memory, hooks, shared fragments, and `gha` Actions/bot-workflow tuning included, not just skills/agents.
- **`memorize`** / **`push-memory`** / **`ums`** — own the memory/preference row; `push-memory` is specifically the delivery mechanism when the working repo isn’t `ai-config` but the session still has API/branch access to it — narrower than this skill’s Step 3, which also covers the case where even that access is missing.
- **`claude-agent-workflow`**, **`claude-review-workflow`** — own the bot-CI-tuning row; both already document the load-bearing patterns in `claude.yml`/`claude-code-review.yml` this skill doesn’t repeat.
- **`upstream-issues`** (`shared/workflow/upstream-issues.md`) — the general escalation pattern (PR → issue on target → issue on own repo, ask for transfer) this skill’s Step 3 specializes for the `ai-config`/`gha` case, where the “external” repos are the user’s own but may still be out of the current session’s scope.
- **`issue-first`** (`shared/workflow/issue-first.md`) / **`st`** — the issue-before-PR discipline Step 3’s normal push-access path still follows once a form is chosen.

## Anti-patterns

- ❌ Picking a form and building it without running Step 2’s reuse/extend check — `skill-builder`/`agent-builder`/etc. already require it; this skill doesn’t get an exemption.
- ❌ Reaching for a hook when a `CLAUDE.md` memory would do — a hook adds harness-config surface area a memory doesn’t need.
- ❌ Applying “least mechanism” to a verb-first request (“go through X”, “trigger Y”, “sweep Z”) and building a passive memory rule when the phrasing named a repeatable on-demand action — that’s a Skill, not a cheaper restatement of one. Ask first when the two readings would build genuinely different artifacts.
- ❌ Building a `gha` capability as an `ai-config` skill (or vice versa) because it’s the repo the session happens to be in — the mechanism’s home is fixed by what it serves (Claude/Codex behavior vs. other repos’ CI), not by convenience.
- ❌ Silently dropping a request when the session lacks push access instead of running Step 3’s fallback ladder.
- ❌ Filing the fallback issue in the current repo without explicitly asking for a GitHub “Transfer issue” — an untransferred issue is a request nobody will ever see again.
- ❌ Duplicating a builder skill’s procedure inline instead of handing off to it.

Back to top
