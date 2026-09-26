# ai-config

Portable AI agent config --- skills, memories, and commands
synced across machines via git.
Works with Claude Code, Codex, [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Cursor](https://cursor.com), VS Code Copilot, and any agent that reads markdown instruction files.

Claude Code, Codex, and Cursor install this repo's skills natively as plugins (see each harness's section below);
`bootstrap.sh` handles what a plugin install can't: Gemini CLI / Antigravity config and per-machine dotfiles.

## Setup on a new machine

```sh
git clone --recurse-submodules https://github.com/Morrison-Lab/ai-config.git ~/ai-config
bash ~/ai-config/bootstrap.sh
```

Rerun `bootstrap.sh` any time a new top-level dir is added to the repo.

`--recurse-submodules` populates `shared/sembr-skills`, the vendored
[sembr/skills](https://github.com/sembr/skills) plugin.
In a clone that predates it, run
`git submodule update --init -- shared/sembr-skills` instead.
Skipping it is not fatal: `bootstrap.sh` prints a `skip` line and
`scripts/validate-skills.py` warns, so everything else still installs.

### Verify the install

After bootstrapping, confirm the Gemini/Antigravity registration and the skill catalog are in order:

```sh
cat ~/.gemini/config/skills.json ~/.gemini/config/plugins.json
scripts/inventory.sh                         # live counts of skills/wrappers/commands/docs
```

In a Claude Code or Cursor session with the plugin installed (see each harness's section below), type `/` and confirm the skills appear (e.g. `/scout-peers`, `/ardi`).

### Antigravity & Gemini CLI

`ai-config` natively integrates with **Google Antigravity** (`agy` CLI, Antigravity IDE, and Antigravity 2.0) and **Gemini CLI**:

- **Global Plugin**: `bootstrap.sh` stages the plugin layout under `~/.gemini/config/plugins/ai-config` and writes `~/.gemini/config/plugins.json` and `skills.json` (registering the staged `plugins/ai-config` path and the checkout's `skills/` path directly).
- **Workspace Plugin**: Opening this repository directly in Antigravity automatically discovers `.agents/skills.json` and `.agents/plugins.json` to load all skills, rules (`AGENTS.md`), and plugin features.

### opencode

[opencode](https://opencode.ai) has no skills-bundle "plugin" --- its `plugin` config field loads JavaScript/TypeScript event-hook modules, not skills, rules, or agents.
opencode instead reads ai-config through its ordinary config fields plus convention-based discovery (`.claude/skills/`, `.agents/skills/`, `.opencode/agents/`):

- **This repo.**
  The root [`opencode.json`](opencode.json) wires opencode when you run it inside ai-config: `instructions` loads `AGENTS.md`/`CLAUDE.md`, `skills.paths` adds `skills/` and the vendored `shared/sembr-skills/skills`, `references` exposes `shared/` and `memories/`, and the subagents in [`.opencode/agents/`](.opencode/agents) are auto-discovered.
- **Another repo (consumer).**
  A project that vendors ai-config at `.ai-config/` (as [`Lacaedemon/sparta`](https://github.com/Lacaedemon/sparta) does via `tools/bootstrap-ai-config.sh` + a pinned `.ai-config-ref`) can point its own `opencode.json` at that checkout --- the opencode analogue of the Claude plugin and the `.agents/*.json` Antigravity/Gemini config:

  ```json
  {
    "$schema": "https://opencode.ai/config.json",
    "instructions": ["AGENTS.md", "CLAUDE.md", ".ai-config/AGENTS.md", ".ai-config/CLAUDE.md"],
    "skills": {
      "paths": [".ai-config/skills", ".ai-config/shared/sembr-skills/skills"]
    },
    "references": {
      "shared":   { "path": ".ai-config/shared",   "description": "ai-config shared fragments" },
      "memories": { "path": ".ai-config/memories", "description": "ai-config memories" }
    }
  }
  ```

  To make ai-config available to opencode in **every** project, copy or symlink `skills/` into `~/.config/opencode/skills/` and add `instructions` entries to `~/.config/opencode/opencode.json`.

  Enforcement hooks reach opencode sessions too,
  through oh-my-openagent's Claude-hooks bridge,
  when the non-plugin Claude install carries the catalog:
  see [docs/opencode-hook-mapping.md](docs/opencode-hook-mapping.md).

### Codex wrappers

The canonical workflow bodies stay in `skills/` for Claude Code. The
generated `codex-skills/` tree contains thin Codex-compatible wrappers with
strict `name`/`description` frontmatter. Each wrapper tells Codex to read the
matching canonical skill from `skills/<name>/SKILL.md` and adapt Claude-only
metadata or tools to the current Codex session.

Codex can load this repository as a plugin through [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json).
The plugin manifest explicitly routes hooks to `plugins/ai-config/codex-hooks.json`, avoiding Codex's default discovery of the Claude catalog at `hooks/hooks.json`.
That Codex hook manifest routes the canonical catalog through `plugins/ai-config/codex-hook-adapter.py`.
The first session opening a new or changed hook must review and trust it in Codex's hook browser before it runs.
For a user-global install, register the plugin with Codex for skills and hooks.
After adding or editing a canonical skill, regenerate the wrappers:

```sh
python3 scripts/sync-codex-skill-wrappers.py
```

### Cursor

Cursor reads this repo as a workspace and as a plugin.

**This repo as a workspace.**
Opening the clone in Cursor loads:

- `AGENTS.md` (and `CLAUDE.md`, for compatibility)
- project rules in [`.cursor/rules/`](.cursor/rules/)
- skills from `skills/` once a Cursor plugin install is live
- project hooks in [`.cursor/hooks.json`](.cursor/hooks.json), which run the `hooks/` catalog through [`.cursor/hooks/adapt-claude-hooks.py`](.cursor/hooks/adapt-claude-hooks.py) (see [Cursor hook mapping](docs/cursor-hook-mapping.md))

**User-global rules.**
`bootstrap.sh` no longer places [`cursor-rules/`](cursor-rules/) under `${CURSOR_HOME:-$HOME/.cursor}/rules` (see its header comment), but installing the Cursor plugin below already covers this: `.cursor-plugin/plugin.json`'s `rules` field ships `cursor-rules/` as the plugin's user-global rules, so they apply in every other Cursor workspace once the plugin is installed.
Files that exist in both `cursor-rules/` and `.cursor/rules/` must stay identical (`scripts/test_cursor_rules_sync.py`).

**Skills in other workspaces.**
Install this repo as a Cursor plugin from GitHub (`Morrison-Lab/ai-config`).

To load the plugin from a local checkout without GitHub:

```sh
mkdir -p ~/.cursor/plugins/local
ln -s /path/to/ai-config ~/.cursor/plugins/local/ai-config
```

Then reload the Cursor window.
On Windows, Git Bash `ln -s` may copy instead of linking;
prefer the GitHub marketplace install there.

`.cursor-plugin/plugin.json` is the Cursor Plugin manifest
(skills, user-global rules from `cursor-rules/`, commands).
Project-only rules stay in [`.cursor/rules/`](.cursor/rules/)
and are not shipped through the plugin.
The Cursor plugin `hooks` field is deliberately not pointed at
Claude Code's [`hooks/hooks.json`](hooks/hooks.json); that file is a
foreign schema ([#1934](https://github.com/Morrison-Lab/ai-config/issues/1934)).
Project Cursor hooks live in [`.cursor/hooks.json`](.cursor/hooks.json) instead.
Claude Code keeps using `.claude-plugin/`.

### Tool mappings

The canonical skills name concrete tools — mostly `gh`/`git` commands. So a
non-Claude model knows what to run, [`tool-mappings.yml`](tool-mappings.yml)
maps each canonical operation (e.g. `VIEW_PR`, `CREATE_ISSUE`, `PUSH`) to its
GitHub MCP equivalent, with a per-model resolution rule (Codex, Copilot, and a
generic CLI fallback). The sync script above renders the full reference at
[`tool-mappings.md`](tool-mappings.md); wrappers link to that single reference
instead of duplicating its table.
Edit the `.yml`, then rerun the script — CI fails if either output is stale.

A handful of the highest-traffic skills (`ard`, `ardi`, `claim-pr`,
`pr-status`) go a step further and name the operation token inline next to the
concrete command (e.g. `` gh pr comment <N> ... # COMMENT_PR ``), so a
non-Claude wrapper can resolve by token instead of pattern-matching the `gh`
command. This is a pilot (ai-config#195) — the rest of the corpus still names
only concrete commands. `scripts/validate-skills.py` lints every such token
against the registry, so a typo'd token fails CI instead of silently not
resolving for other models.

## Claude Code on the web

In cloud (web) sessions you can't run `bootstrap.sh` by hand, and the environment "Setup script" runs at build time *before* this repo is checked out --- so it can't reference `bootstrap.sh` either.
Skills and commands need no such step, though: this repo is a native Claude Code plugin (`.claude-plugin/plugin.json`), so a web session working in ai-config itself discovers `skills/` and `commands/` directly.
The committed `SessionStart` hook (`.claude/settings.json` → `.claude/hooks/session-start.sh`) instead runs `bootstrap.sh` once the repo is on disk, for its remaining job: Gemini CLI / Antigravity config and per-machine dotfiles.
The hook is a no-op outside remote sessions (`CLAUDE_CODE_REMOTE`) and idempotent, so local machines are unaffected.

The same hook also installs **Julia** (via `juliaup`) on the first session
start, since the base web image ships none. The install is guarded (a no-op
once Julia is present) and non-fatal — it only succeeds if the environment's
network policy allowlists the Julia download hosts. See
[`docs/julia-setup.md`](docs/julia-setup.md) for the allowlist and a
build-time alternative.

### Hooks in this repo's own web sessions (`plugins/ai-config-hooks/`)

The paragraph above covers skills and commands.
Hooks are different: `hooks/hooks.json` reaches Claude Code only through the
ai-config **plugin**, and a session that opens this checkout itself never
installs that plugin, so every enforcement hook was inert in ai-config's own
web sessions ([#2004](https://github.com/Morrison-Lab/ai-config/issues/2004)).

[`plugins/ai-config-hooks/`](plugins/ai-config-hooks/README.md) holds a
hooks-only plugin meant to close that gap.
It used to live in `skills/`, where it loaded in place as
`ai-config-hooks@skills-dir` through the `.claude/skills` symlink.
It is parked outside `skills/` because a plugin manifest there is the
suspected cause of the claude.ai marketplace sync failing since 2026-09-02,
which dropped ai-config from every cloud session;
`scripts/validate-skills.py` now refuses one.
So the gap is open again until the plugin has a home that does not ship
inside `skills/`.
Its `hooks/hooks.json` is still generated from the canonical catalog by
`scripts/gen-hooks-plugin.py` (CI fails when the two drift), and each
command runs through `run-hook.sh`, which stands down when an `ai-config@*`
plugin is enabled under Claude Code's scope precedence (local, project, then
user settings) so no hook fires twice on a machine that has the marketplace
install.

## Use these skills in another repo's web sessions (plugin marketplace)

The `SessionStart` hook above only fires when **ai-config itself** is the open
project. To get these skills when a **different** repo is open in a cloud
session — where that repo's hooks know nothing about ai-config, `~/.claude`
starts empty, and skills uploaded to claude.ai/customize do **not** cross over
into Claude Code — this repo also publishes itself as a **plugin marketplace**.

The repo is simultaneously:

- the marketplace — `.claude-plugin/marketplace.json`
- a single plugin — `.claude-plugin/plugin.json` with `source: "./"`, which
  bundles the existing top-level `skills/` and `commands/` (no duplication;
  `skills/` and `commands/` are auto-discovered at the plugin root).

To load these skills in another repo's cloud sessions, commit this to **that
repo's** `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "Morrison-Lab": {
      "source": { "source": "github", "repo": "Morrison-Lab/ai-config" }
    }
  },
  "enabledPlugins": {
    "ai-config@Morrison-Lab": true
  }
}
```

Claude Code installs the plugin at session start (needs network access to reach
GitHub). Plugin skills are namespaced, e.g. `/ai-config:reprexes`,
`/ai-config:grade-work`.

Locally (or to try it), run these as slash commands inside a Claude Code
session (or prefix with `claude ` to run them in a terminal):

```
/plugin marketplace add Morrison-Lab/ai-config
/plugin install ai-config@Morrison-Lab
```

No `version` is pinned, so every commit to this repo counts as a new version —
sessions with marketplace auto-update pick up the latest automatically.

## Use these skills with this repo's own `@claude` bot

The two mechanisms above cover the **CLI** (the Claude Code plugin, or Gemini CLI / Antigravity via `bootstrap.sh`) and **other repos' cloud sessions** (the plugin marketplace).
The third surface is the `@claude` **CI bot** running on *this* repo's PRs/issues (`.github/workflows/claude-bot.yml`).

That bot runs `claude-code-action`, which does **not** auto-discover skills from `~/.claude` (the runner's home is fresh) or from a plugin unless it's installed.
It *does* load **project** skills from `.claude/skills/` in the checked-out
repo.

The `.claude/skills → ../skills` symlink is **committed** to this repo. It
works via a subtle two-step mechanism:

1. `claude-code-action` has a security feature called `restoreConfigFromBase`
   that, for every PR, restores `.claude/` from the **base branch** (`main`)
   using `git checkout origin/main -- .claude`. This prevents malicious PR
   branches from injecting hooks or settings.
2. Because `.claude/skills` is committed to `main`, `restoreConfigFromBase`
   always restores the symlink — even if the PR branch doesn't have it.
3. `git checkout origin/main -- .claude` correctly materializes the symlink on
   disk (unlike `gh pr checkout`, which dropped it due to `core.symlinks`
   handling — a separate failure mode that was the original blocker).

Once the symlink is in place every top-level skill becomes available to the bot
by **bare name**. Comment **`@claude ardi`** (or any other skill trigger) on a
PR or issue and the bot can invoke the `ardi` skill, exactly like the local CLI
does. No duplication (`skills/` stays the one source of truth) and new skills
are picked up automatically.

> **Note:** On PRs that predate the merge of this feature to `main`, the
> symlink is absent (`restoreConfigFromBase` restores from the `main` at the
> time Claude runs). Skills become available to the bot for all sessions after
> this PR merges.

## Deconflicting parallel local sessions

When several AI sessions have the **same local checkout** open at once (two
Claude Code tabs, a CLI + the IDE extension, two terminals) they can clobber
each other — branch switches under uncommitted edits, racing pushes, duplicate
builds.
The **`session-lock`** skill is the
local-filesystem counterpart to `claim-pr`: a small registry CLI
(`skills/session-lock/scripts/ai-session.sh`) keeps a machine-local list of
active sessions under `.git/ai-sessions/`, so sessions can see each other,
refuse to share a working tree, isolate into a `git worktree`, and auto-recover
after a crash. There's an optional `SessionStart` hook for hands-off
registration. See [`docs/local-session-deconfliction.md`](docs/local-session-deconfliction.md).

## Configuration

Settings this repo's own tooling reads from the environment.

| Variable | Effect |
| :--- | :--- |
| `AI_CONFIG_PR_REVIEWERS` | Comma-separated GitHub logins to request as reviewers on a PR the orchestrator opens. **Unset means no reviewer is requested**, which is deliberate: this repo is used by people other than its author, so there is no login that could be a correct default. Before this existed the value was hardcoded, and every request named a login that exists for nobody (ai-config#2627). |
| `AI_CONFIG_DOTFILES_FORCE` | Install dotfiles on a machine that fails the environment gate --- see [`dotfiles/shiva/README.md`](dotfiles/shiva/README.md). |
| `ALLOW_FORCE_PUSH` | Escape valve for `hooks/no-clobbering-push.py`, for a case the guard did not foresee. Using it means stating why. |
| `ALLOW_COMMIT_AND_PUSH` | Escape valve for `hooks/no-commit-chained-to-push.py`, which otherwise refuses a `git commit` and a `git push` in one Bash call. Using it means saying why the call could not be split. |
| `ALLOW_BREAKING_SLIDE` | Escape valve for `hooks/guard-slide-major-tag.py`, recording a deliberate override when a reusable workflow permission addition has already been prepared in consumers. |

`scripts/check-reviewer-placeholders.py` gates the first of these: it fails
CI when a person-shaped name is written into a value position --- an `owner:`
argument, a `--reviewer` flag, a `reviewers[]=` field --- rather than read
from configuration.
It keys on **position**, not on any particular name, so an ordinary role
reference in prose ("request the repository owner as reviewer") is untouched;
that phrasing is the user-agnostic form the corpus should keep using.

## Quality gates

Two lightweight checks keep the skill catalog well-formed:

- **CI** (`.github/workflows/validate.yml`) runs `scripts/validate-skills.py`
  (every `SKILL.md` has valid frontmatter, `codex-skills/` is in sync, and the
  manifests are valid JSON) and `scripts/check-links.py` (no broken relative
  markdown links) on every push and PR.
- **Pre-commit** (`.pre-commit-config.yaml`) adds local secret-scanning
  ([gitleaks](https://github.com/gitleaks/gitleaks)) plus the same two
  validators. Enable once with `pre-commit install`.

Run them by hand any time:

```sh
python3 scripts/validate-skills.py
python3 scripts/check-links.py
```

### Context budget (`scripts/check-context-closure.py`)

`CLAUDE.md` and the transitive closure of its `@path` imports are loaded **in full at launch**, so their size is an unconditional per-session cost.
A per-file line count cannot see it -- no single fragment is unreasonable, and the total is -- and splitting a fragment into more imports does not help, since [imports load at launch too](https://code.claude.com/docs/en/memory).
Only moving content *out* of the closure reduces what is loaded.

```sh
python3 scripts/check-context-closure.py            # this repo's closure
python3 scripts/check-context-closure.py --base ../consumer-repo
```

The `--budget` total is advisory: it reports and exits 0 over it, serving as a trend line on every PR rather than a gate.
Three things do gate, all without `--strict`.
The root file's hard character cap (`--root-char-cap`, 150,000 -- the harness's own limit, past which the file is not loaded whole) and the per-fragment byte cap (`--fragment-cap`) both fail on the level.
The **growth ratchet** fails on the delta: under `--baseline REV`, once the root file sits at or above `--root-growth-gate-fraction` of its cap (0.90 by default), the branch may not grow it at all.
Below that line the ratchet is inactive and reports so;
`--no-root-growth-gate` turns it off for a caller whose baseline is not a merge base.
A dangling **anchored** import (one written on its own line) does exit non-zero, being a defect rather than a size finding.
An unresolved **inline** `@token` is reported but does *not* fail, since most are prose (`@claude` mentions, email addresses) rather than mistyped imports --- so don't rely on this command to gate those.

For a repo that vendors ai-config as a `.ai-config` submodule, `--compare` answers what a pin bump would cost.
The import list is fixed; what changes is what those files weigh:

```sh
python3 scripts/check-context-closure.py --base ../consumer-repo --compare origin/main
```

Measured on `ucdavis/bcs` at a three-day-old pin, the same 33 imports had grown **+62%**, arriving silently since a bump's gitlink diff is one line (ai-config#1028).

### Lead-in counts (`scripts/check-leadin-counts.py`)

Prose here introduces a list with a spelled-out count --- "Two lightweight checks keep the skill catalog well-formed:", "Three things the new observation adds" --- and then enumerates the items below it.
A later edit that splits or merges one item leaves the count stale, and a reader who counts along stops at the stated number and never reaches the last item.
Nothing else catches it: there is no broken link, the lines are well formed, and the prose reads fluently either way.

```sh
python3 scripts/check-leadin-counts.py                 # every tracked markdown file
python3 scripts/check-leadin-counts.py memories/foo.md # just these files
```

Exit `0` every lead-in count matches, `1` at least one mismatch, `2` the scan examined no files (a check that examined nothing reports clean otherwise).

Gated in `validate.yml`, over every tracked markdown file.
The corpus reads clean at 0 findings;
the checker prints the population it examined on every run.
The one stale count the checker found on its first run --- `memories/claude-code-permissions.md` said two above three bullets --- is fixed in the same commit that gates it.

False positives, rather than recall, are what bound the design: a checker that flagged every numeral would be switched off, taking the real cases with it.
So it reads only spelled-out counts that open the last sentence above the enumeration, or sit behind at most two function words ("There are two ...").
It reads that sentence only when it is its own one-line paragraph, so a count closing a multi-line paragraph is never examined.
It skips a lead-in ending on a conditional subordinator, since "Two changes are independent if:" enumerates the conditions rather than the changes.
And it discounts a bold-header run that overshoots the stated count by more than one, since body prose between such headers gives that shape no structural end.

Those bounds are positional rather than semantic, so one shape stays a known false positive: a count that opens its sentence and then names a property of itself ("Two variables at once is hard:").
No bound separates that from "Three answers are legitimate, and only the first is ...", which is a genuine lead-in of the same shape.
The simplest alternative, a rule "keyed on the copula alone" that just requires `is`/`are`/`was`/`were` to appear somewhere in the sentence, suppresses the large majority of the lead-ins the shipped implementation accepts, most of them genuinely real, so it is not a workable substitute.
No exact count is quoted: the total moves as prose lands, and three hand measurements while the checker was written gave three different totals, so derive it fresh rather than trusting a number.
`scripts/test_check_leadin_counts.py` pins it as accepted rather than claiming coverage it does not have.

- **Do:** run it over a file whose bulleted or bold-header sections you have just split or merged.
- **Don't:** read a clean result as proof that every count in the file is right --- the bounds above trade recall for a quiet enough report to act on.

### Attributed quotes (`scripts/check-user-quote.py`)

Shows every transcript record containing a phrase you are about to attribute to the user, with its provenance --- record shape, `origin.kind`, flags, `userType` --- so you can read them and judge.

```sh
python3 scripts/check-user-quote.py "the sentence you are about to quote"
```

**It does not decide who wrote the phrase**, and that is the design rather than a gap.

Exit `0` candidates found and printed, `1` none found in any record, `2` the search was degraded or impossible.
`1` and `2` are kept apart so a search that did not happen is never reported as an absence.
Pass `--root` on an agent whose transcripts live elsewhere.

[`shared/writing/citations.md`](shared/writing/citations.md) carries the argument, and the eleven certification fail-opens that produced it.

Ideas borrowed from comparable projects (and their licenses) are recorded in
[`CREDITS.md`](CREDITS.md); see the `scout-peers` skill for the survey behind
them.

## Enforcement hooks (`hooks/`)

A few rules in this corpus cannot be enforced by writing them down, because
the rule is consulted when it is *read* and broken when a message is
*composed*.
`hooks/` ships the harness hooks that close those gaps.
Claude Code loads them from [`hooks/hooks.json`](hooks/hooks.json).
Cursor Cloud loads that catalog through [`.cursor/hooks.json`](.cursor/hooks.json)
and [`.cursor/hooks/adapt-claude-hooks.py`](.cursor/hooks/adapt-claude-hooks.py),
which translates Cursor events, tool names, and transcript JSONL.
Three scripts that fail closed without a `tool_result` are skipped there,
because Cursor JSONL omits tool output (Cursor staff, 2026-04-13;
re-verify on a harness bump):
`no-push-without-self-review.py`, `no-unreviewed-pr.py`, and
`no-unmonitored-pr.py`.
Reconstructing `tool_result` from Cursor `postToolUse.tool_output` is
[#2241](https://github.com/Morrison-Lab/ai-config/issues/2241).
The event mapping is [docs/cursor-hook-mapping.md](docs/cursor-hook-mapping.md).
OpenCode runs the same catalog where the
[oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent) plugin is
installed and the non-plugin Claude install carries it:
OMO's Claude-hooks bridge reads `~/.claude/settings.json`
and runs the catalog inside OpenCode sessions.
The payload gaps that remain and the per-guard status are in
[docs/opencode-hook-mapping.md](docs/opencode-hook-mapping.md).

| hook | event | enforces |
|---|---|---|
| `inject-local-time.sh` | `UserPromptSubmit` | supplies the real local time, so a recap timestamp is never recalled |
| `warn-python3-cannot-read-hooks.sh` | `UserPromptSubmit` | names the interpreter when the `python3` on `PATH` cannot read the directory the hooks live in -- a condition that denies `Bash`, `Edit`, `Write` and `Agent` at once (every tool a `PreToolUse` matcher names; `Read` and `Grep` are unaffected), while each denial names a hook rather than the interpreter. Shell, not Python: in the failure this hook reports, no Python hook can run. Silent when the interpreter is fine; see the hook's own header for the mechanism (ai-config#3624) |
| `require-gh-repo-flag.py` | `PreToolUse` (Bash) | blocks a mutating repo-scoped `gh` command that omits `-R` |
| `no-offer-to-file.py` | `Stop` | blocks a reply that *offers* to file or record instead of doing it |
| `no-redundant-push-pr-authorization.py` | `Stop` | blocks a request for routine push or PR/MR authorization already covered by the standing grant; deliberately leaves merge, force-push, and unverified external-membership questions alone |
| `no-empty-promise.py` | `Stop` | blocks a reply committing to future behaviour when the same turn shipped no mechanism: a rule ("going forward, I will/won't") needs a durable write, an owed action ("I owe #N the ARDI loop") needs that or an armed timer/watcher |
| `no-unfiled-finding.py` | `Stop` | blocks the *declarative* "worth its own issue" that leaves no filing behind |
| `flag-unfiled-issue.py` | `Stop` | warns, never blocks, when a reply reports a known gap as "is/was still unfiled", "hasn't been filed", or similar RETROSPECTIVE status wording, with no issue-create or issue-comment call after it; distinct from `no-unfiled-finding.py`'s forward "worth an issue" phrasing, which this misses entirely --- reporting the gap again is not tracking it, however many replies it gets repeated across |
| `no-unread-issue-claim.py` | `Stop` | warns, never blocks, when the final message reports a specific issue as open work, blocked, awaiting a decision, or waiting on the user, and no command in the session read THAT issue's comments; a body-only read (`--json body`) does not discharge it, and neither does reading a different issue's comments. An issue body is frozen at filing time while its comments carry the measurement that already ran, the PR that already shipped half of it, and the decision already taken. The cue and the issue reference must share a sentence, and fenced blocks (via `scripts/lib/fences.py`, so a nested fence is handled), blockquotes and code spans are all stripped, so quoting the trigger phrasing is not asserting it. Measured twice on `Lacaedemon/sparta` (ai-config#3823): the second time a decision already taken and documented was reported to the user as theirs to make across several turns, with two unrelated issues described as blocked behind it --- the escalating shape, unlike claiming and redoing merged work, collides with nothing and so survives until a human reads it |
| `flag-blocker-without-retry.py` | `Stop` | warns, never blocks, when the final message pairs a blocker/handoff marker (a boxed BLOCKER, "needs you to", "not routing around", "I cannot") with an explicit attribution to a permission/classifier denial, and the transcript's most recent classifier denial has no later attempt of a command with the same normalized shape (a leading env-var prefix, a trailing pipeline, and redirections are stripped before comparing, so `ALLOW_MERGE=1 gh pr merge 5 ...` and `gh pr merge 5 ...` count as the same attempt). The Stop-side sibling of `remind-retry-before-declaring-blocked.py` (ai-config#2994), one turn earlier: that hook injects a reminder on the NEXT prompt, after the escalating reply has already gone out. Measured 2026-09-22 (ai-config#3389): a BLOCKER reply saying a merge "needs you to merge it" because "the permission classifier denied my merge, and I'm not routing around it" was followed, one turn later, by the byte-identical command succeeding with no settings change. Anchored on the ATTRIBUTION side, since "I cannot" alone is common in this corpus for reasons unrelated to a permission classifier; fenced code, blockquotes, and inline code spans are stripped first, so a reply quoting the classifier's own denial text in backticks does not self-trigger |
| `no-announced-start-without-starting.py` | `Stop` | blocks a reply that ends by announcing work it has not begun -- an unconditional present-progressive or immediate-future claim ("I'll start on it", "I'm starting it now") with no tool call toward the thing named. Distinct from `no-empty-promise.py`, which asks whether a MECHANISM shipped: a turn that filed an issue and wrote two memory entries answers that yes and still starts nothing, so the two guards ask different questions of different sentences. Measured four times in one session (2026-09-22, ai-config#3886), once followed by five hours of silence. A conditional cue in the same sentence -- once, when, after, if, unless, pending, awaiting, until, as soon as -- exempts it, so "I'll push once the review lands" passes; that exemption is load-bearing, since without it the guard would push authors toward saying less about sequencing. Deliberately narrow, and narrowed twice by review: it matches "start on" and bare "start the" but not "start with", which is expository ("I'll start with the easy part: the data looks clean" says where an explanation begins, not that work is about to be done), and it no longer matches "next, I'll ...", an ordinary narrative transition. False negatives are cheap here; a guard that blocks correct sentences gets switched off and takes the real cases with it. Only the reply's TAIL is inspected (its last two sentences, after a trailing Stopping Point block is stripped), because the rule is about how a reply ENDS: a reply that announces work and then does it has content after the announcement, which pushes it out of the window. Fenced code and inline code spans are stripped first, so a reply quoting the banned phrasing does not self-trigger |
| `no-stale-pr-status.py` | `Stop` | blocks a reply asserting a PR's check state from a reading older than the last push |
| `no-incomplete-check-enumeration.py` | `Stop` | blocks a reply declaring a PR clean when the only reading is `gh pr checks` or `statusCheckRollup` (short surfaces, not the complete instrument); also warns on broader merge-readiness vocabulary, on a claim resting solely on a subagent's own report, and on a claim about a PR no complete read in the transcript actually names (the read's argument, not just its shape) |
| `remind-ums-after-error.py` | `UserPromptSubmit` | reminds, never blocks, when an admitted error has no recorded learning after it |
| `remind-ci-crosscheck-sim-verdict.py` | `UserPromptSubmit` | reminds, never blocks, when a verdict-shaped figure follows a LOCAL sim/transcript run with no CI-side read in between -- the same clip and seed have been measured reading FAIL locally and PASS on CI |
| `no-mistake-without-a-hook.py` | `UserPromptSubmit, Stop` | blocks after an admitted, mechanizable mistake or recognized redundant prose/content with no mechanism decision, capped once per trigger phrase within a short transcript window |
| `remind-learn-from-review.py` | `UserPromptSubmit` | reminds, never blocks, when an accepted reviewer finding has no learning or mechanism after it |
| `remind-ums-on-scrutiny.py` | `UserPromptSubmit` | reminds, never blocks, when a review of your work was read, or a questioned claim was then corrected, with no explicit UMS after it |
| `remind-retry-before-declaring-blocked.py` | `UserPromptSubmit` | reminds, never blocks, when an auto-mode permission-classifier denial has no later re-attempt of the same command -- ai-config#2994 measured a byte-identical command succeeding after three denials (2026-09-02), so a denial is a sample rather than a wall; scoped to the classifier's own denial, never a user's rejection or a deterministic rule/hook refusal |
| `flag-unchanged-test-sibling.py` | `PreToolUse` (Bash) | warns, never blocks, when a `git commit` stages a file whose conventionally-named test sibling in the same directory is left unstaged, naming the test file so it gets opened rather than reasoned about. Folds `-` and `_` when matching stems, since 43 of this corpus's 118 same-directory test-to-subject pairs spell the separator differently on the two sides (`test_validate_skills.py` tests `validate-skills.py`) |
| `no-move-without-inbound-sweep.py` | `PreToolUse` (Bash) | warns, never blocks, when a `git commit` stages a cross-file content move out of a PROSE file (12+ non-trivial lines removed from one `.md`/`.qmd`/`.txt`-family file and added to another, renames excluded) and no repo-wide search naming the source file's basename ran this session. A moved passage leaves every file that cited the SOURCE pointing at a file which no longer holds it, and nothing else sees that: the link still resolves so `check-links.py` stays green, and a phrase search over the moved content only finds the citing sites that quote it verbatim (ai-config#3501) |
| `flag-unassigned-worktree.py` | `PreToolUse` (Agent) | warns, never blocks, on a write-capable Agent launch with no `isolation`. DENIES instead (2026-09-04, ai-config#3204) when the launch also has no isolation on a Bash-capable agent (READ_ONLY roles included -- see the module docstring), the session is off the repository's resolved default branch, and it has uncommitted tracked changes or unpushed commits a stray checkout would strand; clears with `ALLOW_UNISOLATED_AGENT_LAUNCH=1` on the single approved launch |
| `no-fable-subagent.py` | `PreToolUse` (Agent, Task, Workflow) | denies an Agent launch that names Fable or that omits `model` while the session itself runs on Fable (inheriting is how the violation happens), unless `FABLE_SUBAGENT_OK=1` records the user's explicit grant for that launch; warns on a Workflow launch in a Fable session, whose `agent()` calls it cannot inspect -- user directive 2026-09-01 (ai-config#2927), after 8 of 10 launches in one session inherited Fable and the account hit its usage limit |
| `no-unreviewed-pr.py` | `Stop` | blocks a reply ending a session after a PR was opened or readied with no reviewer requested, or after a push re-headed it with no reviewer requested since; deferred by draft status, by the PR having merged or closed once that transition is visible in the transcript (a terminal action, or a single-PR status read through `gh` or `pull_request_read`), or on a redaction PR by a `no-ai-review` label or an `ALLOW_UNREVIEWED_REDACTION_PR=1` assertion; wholly inert until its `MORATORIUM_END` (2026-12-01) while the standing directive forbids the Copilot request it would demand |
| `no-unshipped-commit.py` | `Stop` | blocks a completion reply while the session's branch carries unpushed commits (derived from `git rev-list --count @{u}..HEAD`; a dropped commit no longer blocks) |
| `no-report-unfixed-hook-test.py` | `Stop` | blocks a status-only reply after CI identifies a missing hook test, until that exact test is written |
| `no-unmonitored-pr.py` | `Stop` | starts a detached two-minute `gh` poller when no model scheduler was used; blocks only when neither works |
| `inject-pr-monitor-status.py` | `UserPromptSubmit` | injects changed state from a detached PR poller on the next prompt, and surfaces once a monitor whose last 3 polls all errored with the same text; local pollers cannot wake a terminated model session |
| `ensure-open-pr-monitor.py` | `UserPromptSubmit` | ensures the agent-independent all-open-PR monitor service (GitHub PRs and GitLab merge requests) is running when an agent session begins |
| `monitor-open-prs.py` | detached timer | reconciles every open GitHub PR the authenticated user opened or is assigned to, plus every one the `github-actions` app opened under an owner that user works under, and every GitLab merge request they authored, every two minutes, including ones opened outside the current session; needs `gh` or `glab`, and polls whichever is installed |
| `no-heavy-work-on-head-node.py` | `PreToolUse` (Bash) | blocks a heavy R/Quarto command run on a cluster's login node; inert off a cluster |
| `no-rm-live-render-intermediate.py` | `PreToolUse` (Bash) | denies `rm`/`trash`/`find ... -delete`/`git clean` of a Quarto/knitr render intermediate (`*.rmarkdown`, `*.knit.md`, `*.knit.qmd`, `*_files/`, `*.quarto_ipynb`, `.quarto/`) only when a live `quarto render`/`preview` or `Rscript`/`R` process running `knitr`/`rmarkdown`/`rmd_render` is also found, since Quarto recreates these at the START of every render and a gitignored one can look like an orphaned leftover while a render is using it; clearable with `ALLOW_RM_RENDER_INTERMEDIATE=1` on the same command |
| `remind-brief-premises.py` | `PreToolUse` (Agent, Task, SendMessage) | reminds, never blocks, when a brief asserts corpus state that nothing derived --- including a `SendMessage` follow-up to a running agent, where corrections and new premises land; also on the one PATHLESS count it can decide, an aggregate over `[FINDINGS_COUNT: N]` values already printed in the transcript that no command naming that token read back, and whose figure is not itself one of the printed values (ai-config#3117) |
| `remind-both-sides-from-git.py` | `UserPromptSubmit` | reminds, never blocks, when a revision-qualified blob is compared against the working-tree copy of that path |
| `remind-deserialize-before-binary-claim.py` | `UserPromptSubmit` | reminds, never blocks, when an escalation names a serialized artifact nobody deserialized |
| `flag-unchained-branch-switch.py` | `PreToolUse` (Bash) | warns, never blocks, when a branch switch and a later mutating git command are not joined by `&&` |
| `flag-unattributable-reviewer-request.py` | `PreToolUse` (Bash) | warns, never blocks, when a reviewer request is not the LAST command in the call. `no-unreviewed-pr.py` credits a request by the WHOLE call's exit status, so a request piped into `tail` or followed by a verify read shares that status with the trailing command and cannot be attributed -- its discharge is withheld even though the request succeeded and a review landed. Reuses that hook's own `undischargeable_requests()` rather than re-matching, since a prediction that disagrees with the thing predicted is worse than none. A non-last request is legitimate when one call requests reviewers for several PRs, which is why this warns rather than blocks |
| `flag-stale-branch-mutation.py` | `PreToolUse` (Bash) | warns, never blocks, when a mutating git command or a `git push` naming a branch runs while the actually-checked-out branch has drifted from what THIS session most recently, explicitly selected via `git checkout`/`git switch` -- tracked in a small per-session, per-repository state file so the check survives across SEPARATE Bash calls, unlike `flag-unchained-branch-switch.py`'s single-invocation scan (ai-config#3204) |
| `flag-cd-into-main-checkout.py` | `PreToolUse` (Bash) | warns, never blocks, when a worktree-rooted session `cd`s into the MAIN checkout of its own repository, where every edit and every check silently succeeds against another branch |
| `flag-add-a-outside-pathspec.py` | `PreToolUse` (Bash) | warns, never blocks, when `git add -A`/`--all`/`.` sweeps in an untracked file its own exclusion pathspec does not cover |
| `flag-indirect-gnu-grep-flag.py` | `PreToolUse` (Bash) | warns, never blocks, when a BSD-rejected `grep` flag (`-P`/`--perl-regexp`) is reached through a child-process boundary that runs it -- `xargs`, `find -exec`, `parallel`, `sh -c` -- where the name resolves by PATH past any shell function or alias; the rejection prints to stderr with empty stdout, and `xargs` launders grep's rc=2 into rc=1, which is also an honest no-match, so a false zero reads as a pass (ai-config#3541) |
| `flag-reset-hard-uncommitted-work.py` | `PreToolUse` (Bash) | warns, never blocks, when `git reset --hard`, `git checkout <pathspec>`, or `git restore <pathspec>` is about to discard tracked, uncommitted changes. The two path forms revert the named paths to the INDEX, or to an explicit source when one is given (`<tree-ish> --` or `-s <ref>`, which this hook also matches), so any edit made since the last `git add` is destroyed silently at exit 0 -- the shape that bit a mutation-testing restore step twice in one session (ai-config#2524). Also warns, at whole-tree scope, on a FORCED `git checkout` that resolves to no pathspec (`-f`/`--force`, with or without a ref): forcing removes the refusal, and the ref-less `git checkout -f` reverts every tracked file to HEAD with no output at all. Silent on an UNFORCED branch switch (`git checkout <ref>`), which git refuses when it would clobber local changes and otherwise carries them across, and on `git restore --staged` without `--worktree`, which rewrites only the index. NOT covered, and destructive: `git switch -f`/`--discard-changes <ref>`, which discards tracked working-tree changes silently at exit 0 -- `git switch` is a fourth command this guard does not read |
| `warn-paginate-without-slurp.py` | `PreToolUse` (Bash) | warns when `gh api --paginate` feeds an aggregating `jq` filter (`last`, `length`, `max_by`, ...) with no `-s`, which silently answers once per page; warns rather than denies, since a streaming filter is correct |
| `no-handrolled-verdict-parse.py` | `PreToolUse` (Bash) | blocks matching a verdict phrase against a PR's review comments when `check-pr-fully-clean.py` has not answered for that PR; a filter file given by `-f`/`--from-file` is read too |
| `warn-pr-create-without-dupe-check.py` | `PreToolUse` (Bash, mcp__github__.*) | warns when a command creates a PR or an issue and no earlier command in the session could have surfaced an existing one; issue discharge requires `--state all --search` (or `gh search issues` / MCP search_issues), not `--state open`; warns rather than blocks, since a duplicate is cheap to close and a blocked creation is not |
| `warn-unlabelled-agent-issue.py` | `PreToolUse` (Bash, mcp__github__.*) | warns when `gh issue create` / `glab issue create` / `mcp__github__issue_write` (`method: create`) files an issue with no `ai-authored` label; `disclose-agent-authorship.md` excludes an issue body from its marker line, so the labels are the only thing distinguishing an agent-filed issue from one the maintainer typed; warns rather than blocks, since the rule is scoped to repos we administrate and this hook cannot tell which repo is ours |
| `warn-unmeasured-capability-claim.py` | `PreToolUse` (Bash, mcp__github__.*) | warns, never blocks, when a forge write about to post carries an ABSOLUTE claim that a capability is absent (`is unavailable`, `isn't available`, `is not possible`, `unbuildable`, `impossible`, `there is no way to`, `cannot be parsed`, `never fires`, `no X can/could Y`, `no X will/would Y` excluding a following `be`) within 400 characters of a tooling noun (harness, guard, hook, dispatch, transcript, agent, classifier, CI... each pluralizable). Surfaces: the MCP post tools `require-agent-disclosure.py` names, plus `issue_write`/`update_pull_request`/`create_pull_request`, and on Bash the comment shapes `flag-uncited-rebuttal.py` parses (`gh issue\|pr comment`, `gh api .../comments`, `gh api .../replies`) plus `gh pr review`, `gh issue\|pr create\|edit` and `glab issue\|mr note`. A negative-capability claim names no artifact, so unlike a positive claim it cannot be checked by opening the thing it is about, and so gets inferred from an adjacent observation and published as established. Requiring both factors narrows the field rather than separating system claims from prose -- measured at `6a870ecc`: 88 of 2010 non-overlapping 2000-character chunks of this repo's own `shared/` fire, 4.38% -- which is why it warns: an exhaustively measured claim is lexically identical and is the valuable one. Chat replies are out of scope because the cost guarded against is durability, not wrongness (ai-config#3707, #3739; measured 2026-09-17: two such claims posted within an hour, both retracted in public) |
| `warn-deferred-closing-keyword.py` | `PreToolUse` (Bash, mcp__github__.*) | warns when a PR description, issue description or commit message places a GitHub closing keyword next to an issue reference *mid-line* inside a sentence carrying a deferral or negation cue (`later`, `follow`, `will`, `not`, `instead`); GitHub's parser is purely lexical, so "...follow in a data PR that closes #923" closes #923 on merge, as measured on ai-config#1718/#1717, Morrison-Lab/gha#460/#322 and ucdavis/bcs#982/#923; a bare `Closes #N` line never fires, and it warns rather than blocks since the guard cannot read intent |
| `warn-stale-review-diff-base.py` | `PreToolUse` (Bash, Agent, Task, SendMessage) | warns when a `git diff`/`log`/`merge-base` range names a bare local branch as its base; a base behind its remote widens the diff so the review runs on already-merged work, and one that is ahead of or diverged from its remote in commits the head branch also carries narrows it so part of the change is never reviewed at all; warns rather than blocks, since a local base is correct for an ordinary local comparison |
| `flag-config-deletion-without-ref-check.py` | `Stop` | warns, never blocks, when a reply recommends deleting files under a configuration directory (`~/.claude`, `~/.config`, `~/.codex`, ...) and no earlier command read a manifest there to see what references them; staleness is a property of a file, safety-to-delete a property of the graph around it |
| `no-unmeasured-clock-claim.py` | `Stop` | warns, never blocks, when a reply states a Pacific clock time and no clock read appears since the previous message; a read whose output is only captured into a variable does not count |
| `no-unchecked-empty-pr-claim.py` | `Stop` | warns, never blocks, when a reply characterizes a pull request as abandoned, or as empty and disposable, near a pull-request number, and no commit-list query naming that number was issued this session; `pr-on-claim.md` has this repo open pull requests against an empty commit on purpose, so `changed_files: 0` is the expected reading on a live claim and on a thread whose commits cannot be pushed as well as on a dead branch, and only the last is closeable. Evidence must name every pull request the claim names, comes from an allowlist of query-bearing tools (never a message body, a file read, or a tool result), and excludes the mergeability query that returns the field. A reply naming the convention is exempt, and a close whose sentence states another basis (superseded, already merged) is exempt for that close only |
| `flag-stale-clean-tree-claim.py` | `Stop` | warns, never blocks, when a message asserts a clean working tree or clean stopping point after a path-writing git command (`git checkout <ref> -- <path>`, `git restore`, `git stash pop`, `git apply`) ran without an intervening `git status` or `git diff` check (ai-config#3821) |
| `no-unauthorized-merge.py` | `PreToolUse` (Bash, mcp__github__.*) | blocks a PR/MR merge command (`gh pr merge`, `glab mr merge`, `gh api .../merge`, or GitHub MCP merge tools) unless an explicit `ALLOW_MERGE=1` assertion or active /mwc accompanies it |
| `no-whole-file-punct-replace.py` | `PreToolUse` (Bash) | blocks a whole-file glyph replace, which converts pre-existing glyphs on untouched lines and buries the real change in a mechanical diff |
| `no-find-root-on-windows.py` | `PreToolUse` (Bash) | blocks a find command starting at `/` or bare drive roots (`/c`, `C:/`, `C:\`, `/cygdrive/c`) in Git Bash / MSYS on Windows, preventing whole-system traversals that crash paging and spawn long-running orphaned processes (ai-config#3897); bypassable with `ALLOW_FIND_ROOT=1` |
| `flag-cop-out-offer.py` | `Stop` | warns when a reply *closes* on an offer to do work (`say the word`, `want me to`, `unless you'd rather`), so the author answers whether the action was already authorized; warns rather than blocks because authorization is not lexically decidable and asking before a merge or force-push is correct, and is tail-anchored because the failure is a recap that closes on an offer |
| `no-placeholder-reply.py` | `Stop` | blocks a reply whose whole content is a placeholder (`No response requested.`, `N/A`, a bare acknowledgement), anchored on the whole message since this corpus quotes the banned string constantly, and deliberately silent on a claim about the *work* (`Nothing to report.`), which the same rule requires |
| `no-clean-stop-with-live-agent.py` | `Stop` | blocks a **clean** stopping-point declaration when a subagent was dispatched in the session and no liveness check (`ListAgents`, or a `git worktree list` query) appears after both the most recent task-notification and the most recent dispatch. Keying on the notification alone left it silent in the standard sidecar shape -- dispatch, read the result, check liveness, dispatch a sidecar, declare clean -- where the sidecar is live and has never notified, so the guard fired only once that agent had finished. A completion notification is not terminal -- the harness fires one each time an agent stops with no live children, and the same task-id may notify more than once -- so a session can act on a notified result, merge the resulting PR, and declare the session finished while the agent runs on and opens another PR (ai-config#3689, measured). Neither sibling catches it: `require-stopping-point.py` only checks that a declaration exists, and `no-unshipped-commit.py` sees nothing because the agent's commits sit in its own worktree on its own branch. A count of outstanding notifications also cannot decide it, since in the measured case every agent HAD already notified; what was missing was a check taken *after* the last one. Identifies a notification by the record's `origin.kind`, never by the literal marker text appearing in a block -- substring matching is spoofable, and self-spoofing is not hypothetical here, since this row, the hook's source, and its test file all contain that string, so reading any of them would otherwise reset the baseline and falsely block a correctly-checked declaration (the reuse `no-push-without-self-review.py` had already made for the same reason). Monitors are deliberately out of scope: a monitor watching an already-merged PR is not outstanding work, and a guard that fires on one gets switched off. `Not a clean stopping point` never fires it. Fails open on any parse trouble |
| `warn-stale-test-claim.py` | `Stop` | warns, never blocks, when a reply claims tests/cases/checks pass and a source-file edit happened after the most recent recognized test-suite invocation in the transcript, or none ever ran -- a session reported "All 25 probe cases pass" from an ad-hoc probe while the real suite, un-run since the edit, actually had 2 of 297 failures (ai-config#3318). Matches VISIBLE prose only (fences, blockquotes, inline code stripped), so a reply quoting this rule's own example phrases in backticks does not self-trigger. Recognizes only a small explicit list of test-suite shapes (pytest, `test-*.py`, `devtools::test`, `npm test`, `cargo test`, and similar), every one anchored to a command position (start of the command, or right after a shell separator, with a small wrapper allowance for `timeout`/`sudo`/`env`/`nohup`), rejecting a partial/adjacent target name (`npm run test:unit`, `mvn test-compile`) so a lint-only or watch-mode run does not read as the full suite, and matched against the command with quoted strings and heredoc bodies blanked out first so a MENTION of the shape inside an `echo`, a commit message, a `#` comment, or a heredoc body does not read as a run -- five adversarial rounds progressively closed that gap. Also recognizes a `sed -i`/`perl -i` in-place edit of a source file (not just a redirect or the Edit tool) as a source-code change, and matches a passing claim in present tense, past tense, or the copula form alike ("cases pass", "cases passed", "tests are passing", "the suite is green"). A disclosed nearby failure count ("12 passed, 3 failed") is exempted so an honest partial report is never told it violated the rule |
| `warn-title-only-issue-edit.py` | `Stop` | warns, never blocks, when a `gh issue edit` / `glab issue update` (or an `mcp__github__issue_write` update) sets a title with no body change, and no later call in the transcript sets a body for the same issue -- Morrison-Lab/gha#839 retitled an issue after a review corrected its derivation but never touched the body, so the body's own superseded "Scope" section stood uncorrected while a PR later claimed the issue had been fixed "with the flawed derivation and its replacement written up there." Deliberately `Stop` rather than `PreToolUse`: a title-only edit followed by a body edit for the SAME issue in a later command must stay silent, which only a hook reading the whole turn (or session) after the fact can tell apart from the incident it exists to catch. Matches only actual `tool_use` invocations, never assistant prose, so this rule's own docstring quoting the command does not self-trigger |
| `require-stopping-point.py` | `Stop` | blocks a final reply lacking an explicit clean or non-clean stopping-point declaration |
| `flag-stale-adjacent-comment.py` | `PreToolUse` (Bash) | warns, never blocks, when a `git commit` changes a literal value while an unchanged comment within ten lines still asserts the old one |
| `no-delete-branch-under-stacked-pr.py` | `PreToolUse` (Bash) | warns when `gh pr merge --delete-branch` or `gh pr close --delete-branch` would delete a branch that is an open PR's base. GitHub's documented behaviour is to retarget such a PR, but a measured case closed it instead, and a closed PR can be neither retargeted nor reopened while its base is gone. Silent when nothing is stacked, when the query fails or returns an unexpected shape, when `gh` is absent, when the command carries no `-R` or PR target, and on `--delete-branch=false` |
| `no-clobbering-push.py` | `PreToolUse` (Bash) | refuses a bare `git push --force`/`-f`, whose remedy (`--force-with-lease --force-if-includes`) costs one word. Warns on every other push whose remote tip a live, read-only `git ls-remote` shows is not an ancestor of the ref being pushed (which is `HEAD` only when the refspec says so, resolved in the directory the push runs in rather than the session's -- a `cd`, scoped to its subshell but not to a brace group, and declined where a compound statement's body, a short-circuited alternative, or a fork into a background job or a pipeline means the pushing shell never takes its effect, then the push's own `-C`, declined in turn when the shell would have had to expand it), names that directory and qualifies its remediation commands with `git -C` when it is not the call's own, declines the reading when the directory is indeterminate or `--git-dir`/`--work-tree`/`GIT_DIR=` redirected the repository, and stays silent on a fast-forward |
| `no-commit-chained-to-push.py` | `PreToolUse` (Bash) | denies a Bash call that chains a `git commit` into a later `git push`. A PreToolUse deny rejects the whole invocation, so a guard refusing the push discards the commit too while its message speaks only about the push (ai-config#2992). Denies rather than warns because the refusal stops the chain reaching the sibling guards at all, and its remedy -- two Bash calls -- is always available. Clearable with `ALLOW_COMMIT_AND_PUSH=1`, either prefixing the commit or push or as the call's own leading assignment (a subshell or short-circuited one sets nothing and does not count). Matches over an argv split (`scripts/lib/shellcmd.py`), so a quoted commit message, a heredoc body and `git commit-tree` cannot trip it, while `timeout 60 git push`, `/usr/bin/git push` and `{ git commit; } && git push` all resolve -- the guard has to fire wherever its siblings would. There is no exemption for a `--dry-run` or `--delete` command: one was written and removed after a review measured `git commit ... && git push --force --delete` and `... --dry-run --no-dry-run --force` both going silent while `no-clobbering-push.py` denied them |
| `flag-chained-push.py` | `PreToolUse` (Bash) | warns, never blocks, when a `git push` is chained after another command with `&&`, `;`, or `\|\|`, piped onward with `\|`, or suffixed by a redirection (`>`, `>>`, or an fd form like `2>&1`). `no-clobbering-push.py` and the plugin's own `no-push-without-self-review.py` push policy both parse the WHOLE command text for a push rather than the isolated segment, so a trailing `2>&1` hands either parser a bare `2` sitting where a commit-ish token would sit in other shapes, and a chained prefix reads as part of the same invocation; a refused chain runs NOTHING, which the refusal naming only the push invites the author to misread as the prefix having succeeded. Measured on Lacaedemon/sparta, 2026-09-05: three refusals in one session |
| `warn-generated-file-stale.py` | `PreToolUse` (Bash) | warns, never blocks, when a `git push` changes a generated file's SOURCE while the repo's own generator reports its output stale. Runs `scripts/gen-hooks-plugin.py --check` and consumes its exit status rather than re-deriving the comparison, per `algorithmatize-checks`. The gap it closes is timing rather than detection: `validate.yml` runs the same check, so the mismatch is already caught -- minutes later, in CI, having spent a review round. Silent unless the push's own diff touches the source, so drift the push did not cause does not fire it. Added after ai-config#3524 pushed a hand-edited `hooks/hooks.json` and went red on both `validate` runs |
| `no-underived-required-check.py` | `PreToolUse` (Bash) | warns, never blocks, when a `gh api` command sets required status checks on a repository or organization ruleset, or on classic branch protection. A context string is matched against a check-run name exactly, so one no workflow emits sits as `Expected` forever and blocks every merge, silently. Detects lexical shapes only, so its silence is never evidence that contexts were derived. Carries no discharge condition: every candidate (a run-jobs read, a branch-scoped `gh run list`, any transcript scan) was satisfiable by a pull request's own run or by typing the string |
| `flag-aborted-patch-script.py` | `PreToolUse` (Bash) | warns, never blocks, before a `git commit` when a file-writing command earlier in the same commit window ended in a Python traceback and no later writing command has run clean. A traceback means the script STOPPED, so every edit after the raise silently did not happen and leaves no trace -- no error, no empty diff, no failing check -- while the edits that did land look correct. Cleared only by a later clean command whose WRITING segments name every path the failed one did, so repairing one of three files does not discharge the warning for the other two, and an announcing segment (an `echo` summary listing the files it believes were fixed) never contributes a path of its own, so a command that only announces clears nothing. Its presence also disables the whole-command fallback that recovers a heredoc's targets, so re-running a heredoc'd patch script AND echoing a summary clears nothing either, even though it genuinely rewrote every target. What still clears is a command whose writer segments name the paths themselves (a `sed` per file), summary line or not. Paths are recognized by file extension, so a failed command naming only extensionless targets records none and clears on the next write -- erring toward clearing, which for a warn-only guard beats warning forever. Decides `git commit` from argv via `scripts/lib/shellcmd.py`, so `git commit-tree` and a quoted mention in an `echo` cannot trip it; excludes commands composed only of read-only programs, so a `grep` for these very patterns is not read as a write; and a REJECTED commit does not close the window |
| `flag-dispatch-over-uncommitted.py` | `PreToolUse` (Agent, Task) | warns, never blocks, when a write-capable `Agent` launch targets a worktree that already holds uncommitted work. The agent cannot distinguish your changes from its own scratch edits: a review agent permitted to mutate files "provided it restores them" resolved that with `git checkout -- .` and destroyed a round of verified fixes. Candidate paths are every absolute path named in the prompt (a cross-repo dispatch identifies its target there, and the incident's target was in a different repo from the cwd) plus the session cwd. Untracked-only dirt does NOT trigger it: `git checkout -- .` cannot destroy untracked files, so warning about a stray log would cite a mechanism inapplicable to what triggered it. Silent on any `isolation` value (`worktree` gets a fresh tree, `remote` runs elsewhere) and on a brief declaring the agent read-only in unscopeable terms -- a bare "do not edit" is not enough, since "do not edit the tests, only the source" narrows rather than forbids |
| `no-misattributed-quote.py` | `Stop` | blocks a reply attributing a quoted phrase to a corpus file that does not contain it, when that phrase is in the file's `.rationale.md`/`.cases.md` sibling; stays silent when the phrase is found nowhere else, since a bare "not found" is the invented-quote misread |
| `warn-nonglobal-substitution.py` | `PreToolUse` (Bash) | warns, never blocks, on an in-place `perl -i`/`sed -i` substitution whose flags carry neither `g` nor a digit -- the shape that silently changes only the first occurrence, which bit mutation testing four times in one session |
| `warn-duplicate-key-blind-verification.py` | `PreToolUse` (Bash) | warns, never blocks, when a Bash command actually executes python code (a `-c` argument, a heredoc piped to python's stdin, or a heredoc that writes a `.py` file the same command then runs) that calls `yaml.safe_load`/`load`/`full_load` and then asserts something about the parsed mapping's keys or their count -- PyYAML's non-strict loader silently keeps the LAST of a duplicate key, so that combination cannot detect a duplicate-key defect. Parses the extracted script with `ast` rather than text search, so a phrase merely quoted in a string literal cannot trip it, and stays silent when a registered `add_constructor` already guards the load. Measured on gha#839: a sweep using exactly this shape reported 1 broken caller stub where the true count, under a duplicate-rejecting loader, was 5 |
| `warn-heredoc-doubled-backslash.py` | `PreToolUse` (Bash) | warns, never blocks, when a Bash-tool heredoc body carries a doubled backslash; on this Windows/MINGW64 transport a doubled backslash inside a heredoc body -- even with a quoted delimiter, which should be fully literal -- can arrive at the interpreter as a single backslash rather than surviving as typed (measured ai-config#1923; recurred ai-config#3362), which fails silently: a match/assert against the intended text fails and reads as a slightly-wrong anchor, or a regex/escape sequence written this way is silently corrupted with no syntax error. Warns rather than blocks because a doubled backslash destined for content that will itself be re-escaped downstream is a legitimate case this hook cannot distinguish from the mistake |
| `warn-partial-validation-before-push.py` | `PreToolUse` (Bash) | warns, never blocks, when a push follows hand-run repo checkers with no `scripts/run-local-validation.py` anywhere in the session. That script derives the check list from `.github/workflows/validate.yml`, which is what `memories/preferences.md` means by taking the list from the workflow rather than from memory. The failure is not a session that skipped checking: it is one that checked repeatedly using whichever checkers the FIRST round happened to need, never widening the set while the diff moved on, so every run stays green and the green means less each time. Measured twice in one session (ai-config#3629, an invalid `\s` escape after ten rounds of re-running the tests and the ASCII check; then ai-config#3696, a lead-in count caught by a checker the session had never run). Stays silent when NO checker ran, which is a different failure that `no-push-without-self-review.py` already sits on, and silent for a subagent's commands. Warns rather than blocks because the full sweep takes minutes and a claim commit or a one-character fix should not wait for it; blocking those would teach the operator to switch the guard off. KNOWN LIMIT: a transcript record carries a command's text and not its cwd, so the sweep is credited session-wide and a run in one worktree silences the guard for a push from another worktree of the same repo (documented in the hook's `LIMITS` section, pinned by a test, and tracked as ai-config#3698) |
| `warn-blanket-worktree-force-remove.py` | `PreToolUse` (Bash) | warns, never blocks, when a Bash command force-removes a git worktree via a `\|\|` fallback (a plain `git worktree remove` chained to a forced retry) or inside a `for`/`while`/`until` loop. `skills/clean-worktrees/SKILL.md` step 5 says a removal refusal is a safety net signalling misclassification -- do not blindly `--force` it -- and a blanket fallback defeats that signal by forcing without reading why the plain attempt refused. Self-hit during a `clean-git` session on 2026-09-10, caught by `no-mistake-without-a-hook.py`. Warns rather than blocks because the skill documents one legitimate single-shot `--force` (a genuinely clean worktree that merely contains a submodule, which refuses with a different error) that this hook cannot distinguish from the mistake at command-text time; matches on the tokenized argv, not raw text, so a quoted or documented instance of the pattern cannot trip it |
| `warn-dupe-check-chained-to-create.py` | `PreToolUse` (Bash) | warns, never blocks, when a tracker search and a create of the same object kind share one Bash call, so the check runs at the same instant as the action it gates and gates nothing. Detects one lexical shape only, which means its silence is evidence that two commands were not in one string and never that a dupe-check was consulted |
| `warn-status-read-after-pipe.py` | `PreToolUse` (Bash) | warns, never blocks, when an expandable `$?` sits in the segment immediately after a pipeline carrying no `pipefail`, so the status read belongs to the trailing formatter rather than to the command. Excludes single-quoted spans, heredoc bodies and `#` comments so the corpus's own documentation of the bug cannot trip it, which also means a `bash -c '...'` one-liner gets no warning |
| `warn-stderr-suppressed-then-parsed.py` | `PreToolUse` (Bash) | warns, never blocks, when a command both suppresses stderr (`2>/dev/null`, `2>>/dev/null`, or `2>&-`) and consumes its own stdout (piped, captured, or redirected), because silencing the one channel carrying a failure turns a diagnosable error into an empty result indistinguishable from a legitimately empty one (measured ai-config#2998) |
| `warn-verdict-line-filter.py` | `PreToolUse` (Bash) | warns, never blocks, when a review round is read through a verdict-line jq filter that drops non-blocking findings in the body and in the review-data JSON findings array (ai-config#3493, 2026-09-09) |
| `no-push-without-self-review.py` | `PreToolUse` (Bash) | blocks `git push` unless a clean verdict whose `Reviewed-Commit:` fingerprint matches the commits the push would ship (refspec resolved) came either from a separate `adversarial-reviewer` subagent's own call result or from a `Bash` call matching the guard's external-reviewer pattern, which today recognizes `agy --print` and none of the other delegation CLIs, or unless the push itself is prefixed with `ALLOW_UNREVIEWED_PUSH=1`, or unless every URL the push resolves to is one of the repositories in its `EXEMPT_REPOS` constant (today `Morrison-Lab/mln`, `mlg` and `mlr`); a verdict quoted anywhere else --- in another file, or in this guard's own denial --- does not count |
| `flag-uncited-rebuttal.py` | `PreToolUse` (Bash) | warns, never blocks, when a PR/issue comment about to be posted disputes a finding whose most recently fetched citation named an external URL that no earlier `WebFetch`/`WebSearch` in the transcript touched -- ai-config#2070's wrong rebuttal, retracted two rounds later once the URL was finally fetched |
| `warn-claim-without-comments-read.py` | `PreToolUse` (Bash) | warns, never blocks, when `gh issue comment <N>` / `glab issue note <N>` posts a claim-shaped body ("claiming", "is working on this", "picking this up", "grabbing this", "please hold off") and no earlier command in the transcript read that issue's COMMENTS (`gh issue view <N> --comments`/`--json comments`, `glab issue view\|show <N> --comments`, `gh api .../issues/<N>/comments` GET, or a GitHub MCP `issue_read` with `method=get_comments`) -- a plain `gh issue view <N>` with no comments flag does NOT discharge it, since reading the body alone was the measured failure: Lacaedemon/sparta#1544 (2026-09-18), where a claim posted after reading only the issue's body missed a diagnosis already merged and an escalation already recorded in its comments, wasting the claim and a draft PR |
| `require-agent-disclosure.py` | `PreToolUse` (Bash, mcp__github__.*) | warns, never blocks, on a `gh`/`glab` command or MCP call that posts a forge comment without the agent-disclosure marker -- such a comment carries the account holder's own login and reads as `type: User`, indistinguishable from one they typed. Three verdicts, not one: the marker is missing, the body is somewhere the check cannot read (`--body-file`, `--editor`, `$BODY`) so it says so rather than accusing, or the body discloses with the robot emoji, which `check-pr-fully-clean.py` matches as a review-body marker |
| `flag-uncounted-comment-claims.py` | `PreToolUse` (Bash) | warns, never blocks, on a `gh pr comment`/`gh issue comment`/`gh api .../comments` body about to post an unverified count (`grep -c`/`wc -l`-shaped discharge) or a hand-typed enumerated list of hyphenated identifiers with no deriving command beside it in the body or elsewhere in the same Bash call -- `remind-brief-premises.py`'s cardinality/enumeration heuristic extended to forge-comment bodies, since that hook's own PATH clause is anchored to this corpus and a comment can be about any repo (ai-config#2377's sparta file-list incident) |
| `flag-unmeasured-timestamp.py` | `PreToolUse` (Bash, mcp__github__.*, Write, Edit, NotebookEdit) | warns, never blocks, when a `gh pr comment`/`gh issue comment`/`gh pr review`/`gh api .../comments` body, or an MCP comment tool body, or a `Write`/`Edit`/Bash append to a session notebook (`session-*.md`) or memory file (`memory/*.md`), about to execute states a Pacific clock time (or `ish` suffix) and no clock read appears in the transcript since the current turn began, or the stamp runs ahead of the harness's injected reading (ai-config#2900, #2903, #2947) |
| `flag-self-authored-verdict-echo.py` | `PreToolUse` (Bash, mcp__github__.*) | warns, never blocks, when a forge comment about to post or be edited (read from `--body-file`, an inline `--body`, or the heredoc that writes either) classifies as a NOT-CLEAN verdict by `scripts/check-pr-fully-clean.py`'s own `classify_verdict()` while carrying ARD disposition vocabulary that no negator or hedge grammatically reaches (bounded by `flag-clean-claim-over-findings.py`'s own `_ATTACHES`, and by BRACKETED asides blanked from the window first, so a negator in a neighbouring clause does not silence it and a negator inside a parenthetical does not govern the sentence -- a comma span is blanked from the connector only, because its extent is a guess and the wrong guess deletes the sentence's own subject, so a negator inside a lone comma appositive is an accepted miss: ai-config#3947) and no `review-data:` payload of its own; the three MCP surfaces a review is SUBMITTED through are subtracted in the script, so a formal not-clean review SUBMITTED through one of them is left alone (a fallback self-review posted as a plain comment still warns --- ai-config#3938) --- the shape of a reply that ANSWERS findings rather than a review that states them, which on Morrison-Lab/mln#49 gave its own author a standing not-clean verdict (unsupersedable per ai-config#2274) on a head with 14 check runs green and a live clean review verdict; blockquoting the echoed line and wrapping it in a backtick code span were both measured and neither exempts it, so the message says to describe the call rather than reproduce it |
| `flag-unmeasured-digest.py` | `PreToolUse` (Bash, mcp__github__.*) | warns, never blocks, when a body about to leave through `gh` (a comment, or an issue or PR being created or edited), `glab` (`-d`/`--description`), an MCP comment tool, or a `cat >>` append to a session notebook or memory file cites a digest-shaped token -- 7 to 64 hex characters bounded on both sides with at least one `a`-`f`, at a canonical length (32/40/64), truncated with an ellipsis, or near a boundary-anchored digest word -- that no prior `user` transcript record contains as a prefix, so a legitimate abbreviation of a measured hash stays quiet while an invented one does not. Reads the body from `--body-file`, `-b`, `-F`, `-d`, or a heredoc in the same command (ai-config#3779). Carries a second, independent surface for a **pinning argument** -- `expected_head_sha`, `expectedHeadSha`, or `--match-head-commit` -- which needs none of the digest shaping above, since the flag already establishes the value is a commit SHA, so it warns on any such value the transcript never observed and names the padded prefix where one was. Matched against shell **words** after heredoc and comment stripping, so a `--body` that merely quotes a pin is prose rather than a pin, and evaluated independently of any body with no fire-once sentinel, since a pinning SHA cannot legitimately originate outside the session (ai-config#3392) |
| `flag-unread-commit-citation.py` | `PreToolUse` (Bash, mcp__github__.*, Write, Edit, NotebookEdit) | warns, never blocks, when a forge comment/review body about to post, or a `Write`/`Edit`/`NotebookEdit` to a non-scratch prose file (`.md`/`.markdown`/`.txt`/`.rst`/`.qmd`/`.rmd`/`.ipynb`), cites a commit SHA and no command reading that commit (`git show`/`git diff`/`git cat-file -p`/`git log -p`/`gh api .../commits/<sha>`/`gh api .../pulls/N/commits`/`mcp__github__get_commit`) appears in the transcript since the current turn began -- a `git log --oneline`, or a `git show -s`/`--stat` printing no patch, does not count, nor does a position-report phrasing ("pushed at `X`", "MERGED (squash, `X`)") that reports the artifact's own state rather than asserting what the commit did (ai-config#3471) |
| `flag-unsourced-term-attribution.py` | `PreToolUse` (Write, Edit, NotebookEdit) | warns, never blocks, when new content pins a term-and-year to an unread document file |
| `flag-partial-put-to-resource-root.py` | `PreToolUse` (Bash, mcp__claude-in-chrome__javascript_tool) | warns, never blocks, when a PUT targets a REST resource ROOT (`/api/v<n>/<collection>/<id>` with no further path segment) and the call does not snapshot and diff the whole resource around it -- an API may treat omitted fields as "leave alone" or as "clear", and both return 200 (ai-config#3935) |
| `warn-stale-issue-edit.py` | `PreToolUse` (Write, Edit, NotebookEdit) | warns, never blocks, when an issue-driven `Write`/`Edit` has no fresh VIEW_ISSUE and remote/default-branch check after the request that named the issue, or when the latest view shows the issue closed |
| `warn-new-line-breaks-on-push.py` | `PreToolUse` (Bash) | warns, never blocks, before a `git push` carrying newly-added Markdown lines that violate semantic line breaks against the default base branch (e.g. `origin/main`), naming the file and line to fix before pushing |
| `warn-new-line-breaks-on-edit.py` | `PreToolUse` (Write, Edit) | warns, never blocks, before a `Write`'s full `content` or an `Edit`'s `new_string` composes a `.md`/`.markdown` prose line packing more than one sentence/clause onto one line -- catches the violation at composition time, ahead of `warn-new-line-breaks-on-push.py`'s own push-time check. Reuses that hook's target-repo checker resolution via the same sibling-import pattern, so it shares its limitation: a repo that only consumes `Morrison-Lab/gha`'s `check-new-line-breaks` reusable workflow with no locally vendored checker script gets no warning from either hook -- which includes `Morrison-Lab/qbt`, whose 2026-09-14/15 incident (a PR's own fix commit for 6 such lines introduced fresh ones while narrating the fix) motivated this hook and would not have been caught by it (`ai-config#3747` tracks closing that gap) |
| `flag-positional-figure-in-commit-message.py` | `PreToolUse` (Bash) | warns, never blocks, when a `git commit` message about to be written states a positional figure about text --- "13 lines above", "39 lines below", "77 lines earlier", "~130 lines later" --- since a commit message is permanent history and the count is re-derived by nobody: true when typed, false as soon as anything above it changes. The warning says to DELETE the number rather than correct it, naming the target instead of counting to it. Measured on this repository's own history (2026-09-03, roughly 2400 commits): 14 occurrences across 13 commit messages, every one decoration. A bare `N characters`/`N chars`/`N words` with no positional word is deliberately NOT matched --- that shape appears in 53 commits, overwhelmingly legitimate measured facts such as a context budget or GitHub's comment cap, of which 3 also carry a positional figure and so fire on that arm anyway. A `\d+-to-\d+ range` arm was measured and dropped: its only match in the whole history was a misfire |
| `guard-slide-major-tag.py` | `PreToolUse` (Bash) | refuses a `gh workflow run slide-major-tag.yml` dispatch when `git diff <tag>..origin/<default>` adds a job-level or workflow-level permission to a reusable workflow (`workflow_call:` in its `on:` block). A called workflow job cannot request permissions that its caller does not grant, so sliding the tag breaks every un-updated consumer with `startup_failure` (as in Morrison-Lab/gha#830 breaking ucdavis/bcs#966). The remedy is to land caller grants in every consumer first, then slide. Clearable with `ALLOW_BREAKING_SLIDE=1` |
| `flag-clean-claim-over-findings.py` | `Stop` | warns, never blocks, when a reply states a clean-claim phrase (`Ready for merge`, `Verdict: Clean/Approved/Ready`, ...) and, earlier in the same transcript, a review body fetched by an actual review-fetch call (or a saved-and-reread body) was scored -- via `check-pr-fully-clean.py`'s OWN `classify_verdict()`/`_unresolved_finding_pattern()`, not a re-derived heuristic -- as stating a clean verdict while still carrying an unresolved finding (Morrison-Lab/ai-config#3578: a session read exactly such a body and reported the round "Ready for merge", reading the verdict line and not the findings list -- backwards per `fully-clean.md`, whose test is the ABSENCE of findings). Only the MOST RECENT such hazard is consulted. Discharged when the reply itself acknowledges findings vocabulary, or when `check-pr-fully-clean.py` has already been run for that PR (reusing `no-handrolled-verdict-parse.py`'s own `checked_prs()`). Deliberately narrow so a message merely quoting `Ready for merge`/`### Verdict` while discussing this rule cannot self-trigger: no hazard is ever recorded from a local file read, and a backtick-quoted mention of the phrase is stripped before matching. A third discharge path, beyond the reply acknowledging findings and the checker having been run: a later review fetch of the same PR coming back genuinely clean supersedes the hazard, which is what keeps the guard quiet through the ordinary fetch, fix, re-fetch, report loop. |
| `no-mutation-in-read-only-reviewer.py` | `PreToolUse` (Bash, Write, Edit, NotebookEdit) | blocks mutating git commands (`commit`, `checkout`, `switch`, `restore`, `stash`, `merge`, `reset`, `rebase`, `revert`, `clean`, `add`, `stage`, `pull`, branch/tag mutations, `push`) and write tools in read-only personas (`adversarial-reviewer`, `Explore`, `Plan`), preventing shared checkout or stash contamination (Morrison-Lab/ai-config#3612, citing #3602 and #3584); clearable with `ALLOW_READ_ONLY_MUTATION=1` |
| `warn-cross-drive-toolchain-move.py` | `PreToolUse` (Bash\|PowerShell) | warns, never blocks, when a relocation verb (`robocopy`, `xcopy`, `rsync`, `Copy-Item`, `Move-Item`, `cp`, `mv`, `wsl --import`/`--move`) at a command position moves a package library, depot, or VM/container disk image across two drive letters (except the `wsl --import`/`--move` arm, which needs neither a second drive nor a recognised toolchain path -- the verb supplies both -- and whose SOURCE tar is exempt from the backup narrowing as well, so an export into a backup directory does not silence the import beside it) and no media-type query (`Get-PhysicalDisk`, `Get-Disk`, `lsblk ... ROTA`, `smartctl`) appears earlier in the session or in the same command. A size-ranked "free space on `C:`" sweep moved a 7.7 GB Julia depot, a 14 GB R library and (next) a 19.5 GB WSL2 `ext4.vhdx` from an NVMe SSD onto a 7200rpm platter, where random small-file reads run roughly two orders of magnitude slower and NOTHING FAILS to say so. Narrowed four ways so it cannot cry wolf on the copies an HDD is the right destination for, or on commands that move nothing: a cross-drive copy naming no toolchain path is silent (documents, media, game installs), and so is one whose path tokens name a backup, archive, snapshot or cold-storage location, even when the source is a depot. Path tokens and rehearsal flags come from the relocator's OWN command segment, so a size survey chained to an unrelated move neither warns nor names the directory it merely measured; every relocation verb in the command is considered, not just the first; and a rehearsal (`/L`, `-WhatIf`, `rsync -n`) is silent. Direction is deliberately not inferred -- the note asks which of the two named drives is the SSD rather than asserting one |
| `warn-irreplaceable-under-cache-label.py` | `PreToolUse` (AskUserQuestion) | warns, never blocks, when an option's LABEL promises reversibility (`cache`, `temp`, `regenerable`, `disposable`, "safe to delete") while the same option names irreplaceable storage -- a VM or WSL disk image by extension (`.vhdx`, `.vmdk`, `.qcow2`), `ext4`, a named docker volume, `pgdata`, or a home directory -- or names `uncommitted` work, the one entry that is not storage. An option labelled "Clear its caches only" bundled a Temp directory, an npm cache, browser caches and ollama models with a WSL2 distribution's 26 GB of storage, and was approved: the label is the part that carries consent, so the approval was uninformed even though the description listed the item honestly. Keyed on disk-image extensions and volumes and never on the bare words `docker`, `container`, `image`, `wsl` or `vm`, so "clear the Docker build cache" -- a correct, common phrase -- stays silent; the reversible word is read from the label alone, so an option whose description merely mentions a cache does not fire. Polarity is checked per sentence: an option that NAMES an irreplaceable item in order to say it is safe ("your ext4.vhdx is untouched") is silent, unless something destructive is said about that item first in the same sentence ("purges the ext4.vhdx, leaving Windows files unaffected") |
| `warn-bash-command-for-powershell-user.py` | `Stop` | warns, never blocks, when a reply hands the user a fenced command carrying a construct Windows PowerShell 5.1 cannot run (`&&`, `\|\|`, an MSYS/Unix absolute path, an inline `VAR=value command` prefix, `2>/dev/null`, a bash heredoc) while the session's environment brief says their shell is PowerShell. A command in a fenced block is addressed to the USER'S shell, which is a different program from the one the Bash tool runs. The hard part is separating a command handed over from one QUOTED while explaining a failure, and prose framing provably cannot do it -- retrospective wording marks the true positive and the false ones identically, because a message can hand over a command and discuss a failure in the same breath, so suppressing on it would remove the only real incident. The separation is done on the block's SHAPE instead: at most 8 non-blank lines, no shell prompt, no non-shell language tag, with `PROMPT` carrying almost all of that load. Evidence is deliberately stated as constructed rather than harvested: the corpus under `~/.claude/projects` holds ONE genuine incident (3 firings, 0 false positives across 500 in-scope assistant messages), which establishes only that the matcher is quiet on the other 13 fenced messages in it -- the real evidence is the suite's built negatives (a Dockerfile `RUN` line, a Make recipe, a git alias, a CI step, a `user@host:~$` session, a heredoc named in a comment), every one of which fired against the first implementation. The language tag is used ONLY to exclude (`json`, `dockerfile`, `console`, ...) and never to include, since the harness tells you to tag runnable blocks ```bash for the Run button; a block tagged `powershell` containing `&&` is the bug itself. Known limits include an UNTAGGED build/CI body and any command meant for a remote host or container shell |
| `no-binary-file-read.py` | `PreToolUse` (Bash) | warns, never blocks, when `cat`/`head`/`tail`/`less`/`more` is applied to a path argument that exists on disk and whose first ~8KB contain a NUL byte -- a whole-file read of a binary file, which dumps raw bytes into the conversation for no benefit. A session `cat`'d a Windows executable to identify it and got roughly 10KB of binary garbage in return. `strings` is deliberately NOT flagged -- it is the correct tool for exactly this case -- and `head -c N`/`tail -c N` (a BYTE bound) are exempt as an already-bounded read; `-n` (a LINE count) does not exempt, since a binary file with few newlines can still dump its entire contents under `-n 5`. An extension match (`.exe`, `.png`, ...) flags a file on its own, with no sniff; the NUL sniff decides only for a file whose extension is not on that list. A path argument is resolved the way the shell would resolve it: a leading `/` is absolute regardless of host OS, an MSYS/WSL drive spelling (`/c/...`, `/mnt/c/...`) is translated to native form on Windows, a redirection target (`> out.bin`) is excluded, and a matched glob is expanded rather than silently missed like an unmatched one. Degrades silently on a missing file, a permission error, a directory, an unmatched glob, a device/pseudo-filesystem path (`/dev`, `/proc`), or a command it cannot parse (ai-config#3771) |

For agent-independent monitoring across all projects and sessions, install the
user service after the hook files are installed:

```bash
python3 scripts/install-pr-monitor.py
```

The service polls every open GitHub PR and GitLab merge request authored by the
authenticated user every two minutes, through whichever of `gh` and `glab` is
installed.
It does not depend on Claude, Codex, Gemini, or a project session
remaining open. If a user systemd bus is unavailable, the installer starts the
monitor immediately and installs an equivalent per-user cron `@reboot` entry.
It copies the monitor to `~/.local/share/ai-config/hooks/`, so neither path
depends on a temporary worktree or an individual agent's hook directory.

On Windows the same command registers a Task Scheduler job
(`ai-config-pr-monitor`, every five minutes) instead of systemd/cron, and
`python3 scripts/install-pr-monitor.py --status` / `--uninstall` manage it.
The task inherits your user environment and runs only while you are logged
on, so sleep and logout pause polling --- acceptable for a secondary backstop
host ([#2082](https://github.com/Morrison-Lab/ai-config/issues/2082)), not
for a primary one.

### Writing a warn-only hook: emit `systemMessage`, not `reason`

A `Stop` hook's `reason` is read **only** alongside `"decision": "block"`.
So a hook meant to *warn* rather than block, emitting `reason` by itself,
prints valid JSON that reaches nobody --- a detector that fires silently, which
is indistinguishable from one that never fires.
That is the worst possible defect for a guard, and nothing catches it: the
hook runs, exits 0, and its tests pass if they only assert that *something* was
printed.

Most warn-only hooks here emit `systemMessage`, and the `PreToolUse` ones pair
it with `hookSpecificOutput.additionalContext`;
the blocking `Stop` hooks pair `reason` with `decision`.
The trap is that a blocking hook is the natural model to copy, and it uses
`reason` correctly.
"Most" rather than all, derived over `hooks/hooks.json` rather than recalled:
every registered warn-only `Stop` hook emits `systemMessage`, and so does
every registered warn-only `PreToolUse` hook but one (measured 2026-09-04).
The exception is `warn-pr-create-without-dupe-check.py`, which emits
`additionalContext` alone --- accepted by the `PreToolUse` rule below, since
that channel is surfaced on its own.
Stated as a property rather than as a tally, because a tally goes stale on
any unrelated hook addition: `no-underived-required-check.py` and
`flag-config-deletion-without-ref-check.py` landed on the same day and moved
the counts from 19 warn-only `PreToolUse` hooks to 20 and from two warn-only
`Stop` hooks to three.

So when adding a warn-only hook:

- emit `systemMessage`, and confirm by reading the printed payload rather than
  by checking that output is non-empty
- have its test assert the payload **shape** --- `bool(out)` cannot tell a
  surfaced warning from a discarded one
- mutation-check it: revert `systemMessage` to `reason` and require the suite to
  fail

`scripts/check-hook-output-shape.py` is a hard gate enforcing this on every run: it verifies that
warn-only hooks never emit `reason` alone, that warn-only `Stop` hooks emit
`systemMessage`, that warn-only `PreToolUse` hooks emit `additionalContext` or
`systemMessage`, and that their test suites inspect the payload shape rather than
checking non-empty output.

The `PreToolUse` half was added after `flag-cd-into-main-checkout.py` shipped
printing its warning to stderr and exiting 0
([#3068](https://github.com/Morrison-Lab/ai-config/issues/3068)).
On exit 0 stderr reaches the `--debug` log alone, and `PreToolUse` plain stdout
is not surfaced either, so the guard fired correctly and warned nobody.
A hook with *neither* channel used to fall through both rules above: the
`Stop` rule does not apply, and the test-side rule only inspects hooks that
already emit one of the two.
`UserPromptSubmit` is deliberately out of scope, since its plain stdout is
added to the context.
"Warn-only" here means the hook neither emits a blocking decision nor exits
with status 2, matching the derivation in that issue:
a `PreToolUse` hook that exits 2 denies the tool call and has its stderr fed
back to Claude, so it already has a surfaced channel and the rule leaves it
alone.
The exemption is deliberately narrow, because writing a non-zero status
somewhere does not show that a hook blocks.
It reads status 2 alone, since every other non-zero status is a non-blocking
error and the near-universal "bail out on an unreadable payload" branch would
otherwise exempt almost every hook.
It ignores a status raised inside an `except` handler, which reports that the
hook itself broke rather than that it denied a tool call.
And it reads literal statuses only, since `sys.exit(main())` passes a computed
one.

The `except`-handler narrowing keys on the handler and nothing wider, so an
error-path `return 2` written outside one still reads as a block and exempts
the hook.
Measured against the shipped checker on 2026-09-04, `blocks_by_exit_2` returns
`True` for `if not path.exists(): return 2` and `False` for the same statement
inside an `except` clause.
Exactly one registered hook writes a literal status 2, and it is
`flag-stale-adjacent-comment.py` inside an `except OSError` clause,
so the exit-2 route exempted no registered hook when this was measured
(2026-09-04).
A hook that emits a blocking `decision` is exempt through the other arm of
the same condition, which this narrowing does not touch.

- **Do:** give a warn-only `PreToolUse` hook
  `hookSpecificOutput.additionalContext`, and confirm it by reading the
  printed payload.
- **Don't:** treat an error-path `return 1` as a blocking channel --- the
  checker reads status 2 alone.

A second hard gate covers how a hook finds its own files.
`scripts/check-hook-file-resolution.py` refuses `os.path.abspath(__file__)` and
the other lexical spellings (`normpath`, `relpath`) across
`hooks/*.py` and `plugins/ai-config/*.py`, including a test suite resolving its
`sys.argv` subject.

So when adding a hook, resolve its own path with `os.path.realpath(__file__)`
(or `Path(__file__).resolve()`), never `abspath`.
`abspath` collapses `..` as text without consulting the filesystem, and this
repo's `.claude/skills` is a symlink to its own `skills/`, so a hook reached
through the skills-directory plugin registration computes its directory as
`<checkout>/.claude/hooks` --- a directory that exists and holds only
`session-start.sh`, none of the Python hooks a sibling import would look for.
A fail-closed guard then denies every command it can no longer classify, and a
fail-open one silently runs without its sibling's helpers.
See `memories/hooks.md` and ai-config#2981.

A **`PreToolUse`** hook that emits **both** channels should gate its
`systemMessage` on `ANTIGRAVITY_AGENT` being unset.
The event decides this, and the adapter is where to read it off.
`plugins/ai-config/claude-hook-adapter.py`'s `PreToolUse` branch prints
`hookSpecificOutput.additionalContext` to stderr as `Warning from <hook>: ...`
and separately prints every collected `systemMessage` as
`claude-hook-adapter [allow]: ...`, so a `PreToolUse` payload carrying both
prints the warning twice there.
Its `Stop` branch instead collapses the two into one, taking the first channel
present through
`msg = hook_out.get("systemMessage") or hook_out.get("additionalContext") or nested_context`
and appending a single entry, so a warn-only `Stop` hook carrying both
surfaces its warning once and owes no gate.
A hook emitting one channel alone is unaffected on either event.
Driving the shipped adapter with a synthetic hook that emits both channels
returns those two stderr lines for a `PreToolUse` payload and the single
`{"systemMessage": ...}` object for a `Stop` payload (measured 2026-09-04).
Nothing enforces the gate, and several registered `PreToolUse` hooks do not
yet carry it.
That census is derived over `hooks/hooks.json` rather than recalled ---
registered scripts whose source names both channels and never *gates* on
`ANTIGRAVITY_AGENT`.
It keys on the channels rather than on the event, so a `Stop` hook can appear
in its output without owing the gate;
`flag-config-deletion-without-ref-check.py` is registered under `Stop` alone
and is there for that reason.
Read the membership off the query below rather than off this paragraph, and
check each name's registered event before acting on it.
No sentence here states the count, because a tally in prose goes stale on any
unrelated hook addition, and this one went stale twice in two days
(output pasted below the snippet, measured 2026-09-04):

```python
import json, pathlib
d = json.load(open("hooks/hooks.json"))
s = {h["script"] for e in d["hooks"].values() for g in e for h in g["hooks"]}
print(sorted(x for x in s if (pathlib.Path("hooks") / x).is_file()
             and all(k in (pathlib.Path("hooks") / x).read_text()
                     for k in ("additionalContext", "systemMessage"))
             and 'environ.get("ANTIGRAVITY_AGENT")' not in
                 (pathlib.Path("hooks") / x).read_text()))
# ['flag-add-a-outside-pathspec.py',
#  'flag-config-deletion-without-ref-check.py', 'no-fable-subagent.py',
#  'no-underived-required-check.py', 'warn-stale-review-diff-base.py']
```

The test is the gating **expression**, not the bare name, and the difference
is not cosmetic.
Keying on the name alone counts a hook that merely *mentions* the variable ---
`warn-stale-review-diff-base.py`'s own docstring says it lacks the gate ---
so the disclosure would delete that hook from the census disclosing it.
That is what happened here: the name-keyed query printed two names under a
paragraph naming three.

- **Do:** gate a `PreToolUse` hook's `systemMessage` whenever the same payload
  also carries `additionalContext`.
- **Do:** key a census like this one on the expression that does the work, and
  paste the output beside the query.
- **Don't:** state the gate as repo-wide fact, or read the census off the
  prose --- re-run the query and check each name's registered event, since
  only its `PreToolUse` members warn twice under Antigravity.
- **Don't:** gate a warn-only `Stop` hook --- the adapter's `Stop` branch
  picks one channel through an `or` chain, so only a `PreToolUse` payload
  carrying both warns twice.
- **Don't:** key it on a bare identifier --- prose about the absence of a gate
  reads as the gate itself.

### A guard's prescribed remedy is a claim about every other guard

A blocking hook usually tells you how to comply: state the pending work,
re-run the query, name the input.
That sentence is not advice about the world --- it is an assertion that the
form it prescribes trips nothing else, and nothing in this repo checks it.
The hooks are written one at a time, by whoever met the failure that motivated
one, and several bind the same event.
So two of them can be individually correct and jointly unsatisfiable.

Measured 2026-09-24, on two `Stop` hooks that both read the reply text.
`no-incomplete-check-enumeration.py` prescribes its remedy by example:

> `"13 pass, 5 pending"` trips nothing

`no-stale-pr-status.py`'s `RX_ASSERT` matched `13 pass` inside that exact
string, so writing the form the first hook asks for produced a block from the
second.
The trap is that the block reads as a finding about the reply rather than as a
collision, and conceding it means retracting a claim the evidence supports ---
see [`challenge-the-assignment`](shared/workflow/challenge-the-assignment.md)'s
"A guard's own blocking message" shape.
The fix was on the second hook: a bare count alongside a disclosed pending
state is now exempt **on the branch that fires when a query returned a
failing state**, and its message names the sibling by file, so a reader who
meets the collision again is pointed at the rule rather than left to
re-derive it.
That scope is the whole of it, and an earlier revision of this paragraph
stated the exemption without it (round 8, finding 6).
"Disclosed" is narrower than it first reads, too.
A state the message names outright --- not fully clean, still failing, not a
clean stopping point --- exempts on its own, because none of those phrases
has a sense that is not about the work.
The pending vocabulary does: `pending`, `queued`, `in progress`, `in flight`
and `still running` are ordinary English about anything at all, so each needs
a count or a check noun beside it before it discloses anything about a check.

It is narrower in a second way, added in round 14: the disclosure has to be
affirmative and non-zero.
A denial names the same vocabulary --- "0 checks queued", "no checks
pending", "checks pending: 0" --- while asserting the opposite of a
disclosure, so reading one as exempt switches the guard off on exactly the
clean claim it exists to surface.
The negator is looked for on both sides of the phrase and never inside it,
which is what keeps "not yet clean" working while "checks pending 0" does
not.
The trailing side has to be ANCHORED to the phrase, though: scanning the rest
of the clause let "3 checks pending with zero drama" read as a denial, so a
progress report that disclosed pending work was silenced by the second half of
its own sentence (round 15, finding 3).
What keeps that case out is not the connector list but the COPULA: a word may
sit in front of the negator only when a copula follows it, so "pending today
are none" is a denial and "pending with zero drama" is not.
Round 16 attributed it to the list instead, which reads as a reason to keep
enumerating (round 17, finding 6).
The list itself is a colon, an equals sign, an opening paren, a run of hyphens
of any length, and the two Unicode dashes.
The run is unbounded because spelling it as exactly two missed this corpus's
own dominant spaced dash by a factor of eight: counted at `7b9fb345`, the
merge base for this change, over its 746 tracked `*.md` files,
`grep -hoE ' --- '` returns 9604 and `grep -hoE ' -- '` 1200.
The count is taken at a commit rather than in a working tree because
documenting the ratio adds dashes and moves it
(round 17, finding 1).
And an explicit COUNT is never retracted by any of them.
The trailing negator supplies a quantity the phrase left open, which a count
does not leave open, so applying it to "3 checks pending -- zero drama"
refused four honest progress reports at once (round 17, finding 6).
The miss that buys is the self-contradicting "3 checks pending -- none", which
now reads as the disclosure of three.
When the pending count has genuinely drained to zero, a disclosed failing
count ("14 pass, 1 fail, 0 pending") is what carries the exemption instead;
when nothing is pending and nothing is failing, there is no progress to
report and re-querying is the escape.
Without that, "Merge pending your approval" and "Her application is pending"
each turned a bare count into an exempt progress report, and a false
exemption is the expensive direction here, since the exemption is what stops
the guard firing (round 9, finding 6).
The same hook's *staleness* branch --- the one that fires when the last
query predates the last push --- is deliberately not exempt, because
disclosing pending work answers the first branch's question and not the
second's: a count taken before a push may describe a commit that is no
longer the head whatever the message says about it.
That branch names its own escape, which is to re-query and state the head
SHA, so the two guards are not jointly unsatisfiable there --- which is the
property this section is about, and it is a weaker claim than exemption.

Two properties make this hard to notice.
A guard's prescribed form is **prose**, so no test asserts it --- the suite
tests what the hook fires on, never what its message recommends.
And the collision only appears when one hook's remedy is actually written,
which happens in a live session rather than in a test.

- **Do:** run a new hook's own prescribed form through every other hook bound
  to the same event, before shipping the message that prescribes it.
- **Do:** name the sibling by filename in the message when a collision is
  resolved, so the next reader meets the rule rather than the symptom.
- **Don't:** treat a guard's remedy sentence as advice --- it asserts
  satisfiability, and that assertion is untested.
- **Don't:** concede a block whose premise you have not checked; the guard
  compared its own inputs, which may not reach your claim.

Every hook must ship a companion `test-<name>.py` beside it in the same change before pushing;
`scripts/test_hooks.py` runs
every such suite (pairing each with its subject) and also checks the reverse
direction --- it enumerates the hooks and flags any that lack a test --- so a
*tested* guard cannot regress unnoticed and an *untested* one cannot hide.
Each suite has a 900-second deadline
(override with `HOOK_TEST_SUITE_TIMEOUT`);
a hung suite reports FAIL rather than stalling the sweep.
The runner gates `validate` and pre-commit.
Every hook ships a test since
[#1080](https://github.com/Morrison-Lab/ai-config/issues/1080) closed;
the `KNOWN_UNTESTED` allowlist stays, empty, so a new hook without a test
fails the runner rather than being noted.

That runner compares hooks against their *tests*.
`scripts/check-hook-catalog.py` compares them against their *bindings*:
it asserts that the table above and
[`hooks/hooks.json`](hooks/hooks.json) name the same hooks, and that each row's
stated event and matcher match what the manifest actually binds.
It gates `validate` and pre-commit too.
The two sets had drifted apart in both directions
([#1206](https://github.com/Morrison-Lab/ai-config/issues/1206)), and the
dangerous direction is a row for a hook that is *not* registered --- an inert
guard and a guard with nothing to block look identical, because neither ever
produces output, so the row becomes positive evidence for something that never
fires.
A hook that is deliberately documented-but-inert says **not registered** in its
own row and sits in an explicit `KNOWN_UNREGISTERED` allowlist, so the state is
asserted rather than merely true.
A mapped tracker that has closed, or that does not exist, fails the check,
so a closed activation issue cannot keep a hook silently inert
([#2302](https://github.com/Morrison-Lab/ai-config/issues/2302)).
When the issue cannot be fetched (offline, timeout, or rate limit), the
check prints `SKIP` and does not fail --- that skip is the documented
offline path, not a silent pass.
It also fails a script bound twice for the same event and the same tool
([#2535](https://github.com/Morrison-Lab/ai-config/issues/2535)),
whenever some tool name `hooks.json` itself spells out fires both matchers:
the row comparison folds a script's several matcher groups into one
comma-joined string, so a hook bound once and a hook bound twice were
indistinguishable there, while the harness runs every group whose matcher
fires.
Deciding that needs the harness's own matcher semantics, which
[`memories/claude-code-hooks.md`](memories/claude-code-hooks.md) records:
a plain name is compared by equality, an alternation by membership, and only
anything else is an unanchored regex.
It decides that over the tool names `hooks.json` itself spells out, so a pair of
two regexes is beyond it only when no such name fires both;
such a pair is printed as a `NOTE` and excluded from the compared count, though
the run still exits 0, so a green catalog check does not by itself rule that
pair out.

The Claude Code plugin (`.claude-plugin/plugin.json`, `source: "./"`) is the supported path for the full catalog: its loader auto-discovers [`hooks/hooks.json`](hooks/hooks.json) at the plugin root and registers every hook it names, no separate step needed.

`bootstrap.sh` no longer places `hooks/` under `~/.claude` (see its header comment), so the non-plugin path below only helps on a machine that already has the scripts there from an install predating that change, or where they were placed some other way:

```sh
python3 scripts/install-hooks.py         # report what is registered
python3 scripts/install-hooks.py --fix   # register the missing ones
```

`--fix` backs `settings.json` up first, preserves any hooks already there, and
is idempotent.
Hooks connect at session start, so restart before expecting a newly registered
one to fire.

**The two paths are mutually exclusive --- don't use both on one machine.**
If the ai-config plugin is enabled, it already loads every hook in
`hooks/hooks.json`, so also running `install-hooks.py --fix` there registers
each hook a second time.
The two registrations carry different command strings ---
`${CLAUDE_PLUGIN_ROOT}/hooks/<script>` for the plugin,
`$HOME/.claude/hooks/<script>` for `--fix` --- so Claude Code keeps both, and
every hook fires twice: the `UserPromptSubmit` hooks inject their context twice
per turn, and the `Stop` guards' fire-once `/tmp` sentinel becomes a
check-then-create race between the two copies.
So pick one path: the plugin (the supported route on a fresh machine), or `install-hooks.py --fix` for a non-plugin install whose `~/.claude/hooks` already holds the scripts some other way.
`install-hooks.py` warns when it detects the plugin already enabled in the
`settings.json` it edits (best-effort --- it cannot see a project-level
enablement).

Bindings live in [`hooks/hooks.json`](hooks/hooks.json), in the native Claude
Code plugin-hooks schema (`hooks` keyed by event) --- a script cannot declare
its own event, so the file names the event, matcher, and, as tolerated extra
keys, the `script` and the rule each one enforces.
The file is dual-purpose: the plugin loader reads it directly when the ai-config plugin is enabled, and `install-hooks.py` reads the same file to register the hooks into `~/.claude/settings.json` for a non-plugin install.

**A hook that misfires is worse than a missing one**, since it trains everyone
to work around the guard.
Keep the matchers narrow, and test both directions before adding one: the
cases it must block *and* the near-misses it must let through.
`require-gh-repo-flag.py` is the cautionary example --- its first version
fired on any command whose text merely contained a gated `gh` invocation,
including a heredoc documenting one.

**Never activate a new hook before its PR merges.**
Writing the script into `hooks/` and testing it is *authoring*, and needs no
permission.
There are two activation paths, and merge gates both.
For a plugin install, the hook's entry in `hooks/hooks.json` activates it: the
plugin loader reads that entry wherever the ai-config plugin is enabled, so the
hook reaches consumers as soon as the entry lands on `main`.
For a non-plugin install, `install-hooks.py --fix` registers it in
`~/.claude/settings.json` as a per-machine opt-in.
Neither reaches anyone else before merge --- a branch's `hooks/hooks.json`
never reaches a consumer, and `--fix` only edits the running machine --- so the
*script* existing is harmless while merging its entry is activation.

**`hooks/hooks.json` has a generated mirror, and registering in one without the other fails CI.**
`plugins/ai-config-hooks/hooks/hooks.json` is generated from it by `scripts/gen-hooks-plugin.py`, and `validate` runs that script with `--check`.
So the registration step is two files, not one:

```bash
python3 scripts/gen-hooks-plugin.py          # regenerate the mirror
python3 scripts/gen-hooks-plugin.py --check  # confirm; exits 1 when out of sync
```

Never hand-edit the generated copy --- run the script, which is also the fix when `--check` fails.

Worth stating here rather than leaving to the check, because the check is the only thing that says so and it speaks after a push.
The paragraphs above describe `hooks/hooks.json` as *the* plugin activation path, which reads as complete;
a first-time hook author follows it exactly, registers correctly, and still burns a red CI cycle on a file the instructions never mentioned.
Measured 2026-09-23 while adding `flag-unsourced-term-attribution.py` (ai-config#3915): the hook, its tests and its `hooks.json` entry were all correct, and `validate` failed on the mirror alone.

On the plugin path a hook now behaves like a skill --- both go live on merge.
[`record-learnings`](skills/record-learnings/SKILL.md) lists "the skill becomes available locally immediately" as a feature.
That described a symlinked non-plugin skill install, which `bootstrap.sh` no longer performs (see *Use these skills* above), so it no longer applies to a fresh machine.
A hook stays inert either way until its entry merges and, on the non-plugin hook path, someone runs `install-hooks.py --fix`.
Either way the hazard the gate addresses is the same --- pre-merge
self-activation --- and neither path allows it.

CI already takes this position.
`claude-code-action`'s `restoreConfigFromBase` restores `.claude/` from `main`
on every PR precisely so a branch cannot inject hooks or settings, so a hook
that has not merged is one the bot already refuses to honour.
This gate is the local-session counterpart of a rule the CI side enforces
mechanically.

A hook is unlike anything else this repo ships, in two ways that make
self-activation worse than merging an unreviewed skill.
It runs **automatically and invisibly**, on every matching event, with no
invocation anyone chose --- a bad skill is inert until called, while a bad hook
is already running.
And a `Stop` hook sits **between the model and the user**, so a wrong one
changes what the user is told: the mechanism that would normally surface the
mistake is the mechanism that is broken.

- **Do:** author the script, write its test, run both directions, open the PR,
  and register it only after that PR merges.
- **Do:** say in the PR which event it binds to and what it does when it fires,
  since a reviewer cannot tell blocking from advisory by reading the manifest.
- **Don't:** run `install-hooks.py --fix` for a hook whose PR is still open.
- **Don't:** treat a passing test suite as authorization --- the tests
  establish that the mechanism works, never that it should exist.

**The gate expires at the merge, and something has to say so.**
A prohibition read before the PR opens has its matching action after the PR
merges, on every consumer machine, at a moment nothing local announces.
So "do not activate yet" without a matching "activate now" is not caution ---
it is a deferred step with no owner, and the corpus measured it costing
sixteen of thirty-one hooks on one machine
([#1786](https://github.com/Morrison-Lab/ai-config/issues/1786), 2026-08-20),
one of which would have caught a credential swept into a pushed commit that
same session.

[`post-merge`](skills/post-merge/SKILL.md)'s step 3.75 is that owner.
On the non-plugin path it runs `install-hooks.py --fix`, which is the call that
registers what the gate had been holding back --- the bare invocation only
reports.
`--fix` binds only what is already in `hooks/hooks.json`.
A hook still on the catalog allowlist of documented-but-inert hooks
needs its registration PR first.
That merge is when 3.75 can bind it.
On a plugin-enabled machine nothing is owed, and `--fix` there double-registers
every hook rather than helping, per the mutually-exclusive section above.

- **Do:** register the hook as part of the post-merge sweep, in the session
  that merged it.
- **Don't:** read the merge as the activation **on the non-plugin path** ---
  there, merging places a file and merges a manifest entry, and only a binding
  in `settings.json` makes it fire.
  On the plugin path the merge genuinely is the activation, as the plugin
  section above already says, and no registration is owed.

(Corrected 2026-07-30: a `Stop` hook was written into `~/.claude/hooks/` and
registered in `settings.json` before its PR was opened, so a guard able to
block outgoing messages ran on the user's machine unreviewed.
The user's correction was "all new hooks must go through pr review before being
activated.")

## What's tracked

- `skills/` --- reusable workflow skills (Claude Code and Cursor via plugin install, and Gemini/Antigravity via the `skills.json` registration `bootstrap.sh` writes against the checkout's own `skills/` path)
- `codex-skills/` --- generated Codex wrappers
- `.codex-plugin/` --- Codex plugin manifest for generated wrappers
- `plugins/ai-config/codex-hooks.json` --- Codex plugin hook registration that dispatches the canonical catalog
- `cursor-rules/` --- user-global Cursor rules (shipped by the Cursor plugin's `rules` field, `~/.cursor/rules/`)
- `.cursor/rules/` --- project Cursor rules for this repo as a workspace
- `.cursor/hooks.json` --- Cursor-native project hooks (Cloud agents load these)
- `.cursor/hooks/` --- adapter that runs the Claude `hooks/` catalog under that schema
- `.cursor-plugin/` --- Cursor Plugin manifest (skills, rules, commands)
- `.cursorignore` / `.geminiignore` --- keep local worktree and Aider residue
  out of Cursor and Gemini search (same paths `.gitignore` already excludes)
- `AGENTS.md` --- universal vendor-neutral instruction file for all coding agents
- `tool-mappings.yml` / `tool-mappings.md` — cross-model tool registry and its
  generated reference (see *Tool mappings* above)
- `commands/` --- slash commands (Claude Code via plugin install)
- `memories/` — persistent notes & preferences.
  No longer symlinked into the VS Code Copilot memory dir --- that install path was removed along with the rest of the global symlink logic ([#2229](https://github.com/Morrison-Lab/ai-config/pull/2229));
  Copilot has no replacement install path yet.
- `references/` — reviewed reference material / worked examples (e.g. a cloud
  Setup script). Documentation only: `bootstrap.sh` skips it, so it is **not**
  symlinked into `~/.claude`.
- `shared/` — single-topic guidance fragments shared with the UCD-SERG lab
  manual (see below).

## Shared content (`shared/`)

`shared/` holds small, single-topic markdown fragments for guidance that lives
in **both** this repo and the [UCD-SERG lab
manual](https://ucd-serg.github.io/lab-manual/) (coding style, writing style,
PR/agent workflow). Each fragment is the one source of truth for its topic, and
two consumers pull it in:

- **`CLAUDE.md`** imports it with Claude Code's `@path` syntax (e.g.
  `@shared/writing/plain-prose.md`). Harness-only specifics (skill names, queue
  keywords) stay inline in `CLAUDE.md` around the import.
- **The lab manual** transcludes the same file with `{{< include
  .ai-config/shared/<area>/<topic>.md >}}` (e.g.
  `.ai-config/shared/writing/plain-prose.md`), via its `.ai-config` git
  submodule (this repo). Manual-specific framing stays in the `.qmd` around the
  include.

Conventions for fragments:

- Write in an **audience-neutral** voice that reads correctly for both a lab
  member and an agent. Keep first-person and harness/skill references out of the
  fragment body.
- Keep them **ASCII** — write `---` for em-dashes and straight quotes — so the
  lab manual's non-standard-character check passes when it includes them.

A session working in this repo's own checkout resolves `@shared/...` imports against the repo root directly (as `CLAUDE.md` does for this very session).
A **global** `~/.claude/CLAUDE.md` that imports these fragments needs `~/.claude/shared/` to exist, which `bootstrap.sh` no longer places there (see its header comment) --- until a replacement lands ([#2352](https://github.com/Morrison-Lab/ai-config/issues/2352)), symlink `shared/` there by hand.
Symlink rather than copy: a symlink tracks the checkout, while a copy goes stale with nothing to say so.
When an ai-config plugin is enabled, `python3 scripts/doctor.py` follows that split: it reports a `~/.claude/shared` copy as a leftover and exempts a symlink that resolves into an ai-config checkout.
It skips the sweep entirely otherwise, since a `~/.claude` copy may then be the machine's only install.
The `@claude` CI bot reads `shared/` from the repo root.

### Vendored from wai (`shared/vendored/`)

A few fragments are authored in **[Morrison-Lab/wai](https://github.com/Morrison-Lab/wai)**
instead (prompt formats, the Copilot-review workflow) — that repo hosts the
UCD-SERG lab's "Working with AI" notes, migrated out of the lab manual once
they outgrew a single chapter. This repo can't add wai as a submodule — wai
already submodules this repo, and a mutual submodule would recurse — so
it keeps a pinned **copy** under `shared/vendored/`, recorded in
`shared/vendored/MANIFEST.json` (source repo, per-file commit, and content
`sha256`). `CLAUDE.md` `@`-imports the copies the same way as any other fragment.

Don't edit the vendored copies here — edit them in wai.
`scripts/check-vendored-drift.py` (run by `validate.yml`) recomputes each copy's
hash and fails CI if it stops matching the manifest. The `Sync from wai`
workflow (`.github/workflows/sync-from-wai.yml`) refreshes them weekly —
via `Morrison-Lab/gha`'s `sync-shared-fragments` — and opens a PR when the upstream
files change.

Add more fragments by creating a top-level dir here (e.g., `agents/`, `output-styles/`).
`bootstrap.sh` no longer has a generic per-directory symlink step to rerun (see its header comment), so wire a new dir into whichever install path (plugin manifest, or `bootstrap.sh` itself) needs to know about it.

## What's deliberately NOT tracked

These are either machine-specific, sensitive, or pure session state:

- `settings.json` / `settings.local.json` — permission allowlists and
  `additionalDirectories` bake in absolute paths and per-machine choices.
  (This is the *user-level* `~/.claude/settings.json`. The repo-root
  `.claude/settings.json` is a different thing — project-level hooks config
  for the web `SessionStart` hook above — and is intentionally tracked.)
- `sessions/`, `history.jsonl`, `tasks/`, `plans/`, `projects/` — session
  and per-CWD memory state, keyed by absolute home path.
- `cache/`, `shell-snapshots/`, `file-history/`, `ide/`, `telemetry/`,
  `backups/`, `downloads/`, `session-env/` — ephemera.
- `plugins/` (in `~/.claude`) --- managed by Claude Code itself from marketplaces. (Note: The top-level `plugins/` directory in this repo contains Antigravity plugin manifests.
  `bootstrap.sh` stages `plugins/ai-config` into `~/.gemini/config/plugins/ai-config` and registers it in `~/.gemini/config/plugins.json`.)

If a per-machine variation appears that's worth syncing (e.g., a global `CLAUDE.md`), add it as a top-level entry here and wire it into whichever install path (plugin manifest, or `bootstrap.sh` itself) needs to know about it.

## Similar projects

Other AI coding-agent skill and config repos worth a look for ideas or
comparison:

- [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) --
  production-grade engineering skills for AI coding agents (Claude Code,
  Codex, Cursor, and others).
