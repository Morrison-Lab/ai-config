# ai-config

Portable AI agent config — skills, memories, and commands synced across
machines via git. Works with Claude Code, Codex, [Gemini CLI](https://github.com/google-gemini/gemini-cli), VS Code Copilot, and any
agent that reads markdown instruction files.

Each top-level subdir is symlinked into the appropriate consumer directory
by `bootstrap.sh`.

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

After bootstrapping, confirm the symlinks resolved and the skills are visible:

```sh
ls -l ~/.claude/skills ~/.claude/commands ~/.codex/skills ~/.gemini/skills ~/.gemini/config/plugins/ai-config
scripts/inventory.sh                         # live counts of skills/wrappers/commands/docs
python3 scripts/check-harness-installs.py    # audit every installed harness
```

In a Claude Code session, type `/` and confirm the skills appear (e.g.
`/scout-peers`, `/ardi`).

### Antigravity & Gemini CLI

`ai-config` natively integrates with **Google Antigravity** (`agy` CLI, Antigravity IDE, and Antigravity 2.0) and **Gemini CLI**:

- **Global Plugin**: `bootstrap.sh` symlinks `plugins/ai-config` to `~/.gemini/config/plugins/ai-config` and registers `~/.gemini/config/plugins.json` and `skills.json`.
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

### Codex wrappers

The canonical workflow bodies stay in `skills/` for Claude Code. The
generated `codex-skills/` tree contains thin Codex-compatible wrappers with
strict `name`/`description` frontmatter. Each wrapper tells Codex to read the
matching canonical skill from `skills/<name>/SKILL.md` and adapt Claude-only
metadata or tools to the current Codex session.

`bootstrap.sh` links those wrappers into `${CODEX_HOME:-$HOME/.codex}/skills`.
After adding or editing a canonical skill, regenerate the wrappers:

```sh
python3 scripts/sync-codex-skill-wrappers.py
```

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

In cloud (web) sessions you can't run `bootstrap.sh` by hand, and the
environment "Setup script" runs at build time *before* this repo is checked
out — so it can't reference `bootstrap.sh` either. Instead, the committed
`SessionStart` hook (`.claude/settings.json` → `.claude/hooks/session-start.sh`)
runs `bootstrap.sh` once the repo is on disk, symlinking `skills/` and
`commands/` into `~/.claude/`. The hook is a no-op outside remote sessions
(`CLAUDE_CODE_REMOTE`) and idempotent, so local machines are unaffected.

The same hook also installs **Julia** (via `juliaup`) on the first session
start, since the base web image ships none. The install is guarded (a no-op
once Julia is present) and non-fatal — it only succeeds if the environment's
network policy allowlists the Julia download hosts. See
[`docs/julia-setup.md`](docs/julia-setup.md) for the allowlist and a
build-time alternative.

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

### The plugin install and the symlink install are alternatives, not complements

Both routes serve the same corpus,
so a machine that ran `bootstrap.sh` (bare names, `/ardi`) **and** enables an
`ai-config@*` plugin (prefixed names, `/ai-config:ardi`) lists every skill
twice.
The skill listing is budgeted at roughly 1% of the context window,
and past that budget descriptions are truncated and skill routing degrades ---
measured ~3.8x over budget on one doubly-installed machine (ai-config#1409).
Pick one route.
The checked-in catalog is capped at 9,000 characters (about 2,250 tokens) by
`scripts/validate-skills.py`.
Keep descriptions concise and put procedural detail in the skill body.
That cap is a stopgap rather than headroom: the budget is consumed by entry
count, not by verbose descriptions, so the lever that scales is fewer entries
(ai-config#1852).
On a `bootstrap.sh` machine, leave the plugin disabled;
the symlinked copy already serves every skill.

For Codex, `bootstrap.sh` detects an enabled `ai-config@*` plugin, skips the
bare wrappers, and removes only stale wrapper symlinks that point to the same
checkout. Re-run it after enabling or disabling the plugin.

The same goes for enabling the plugin from **more than one marketplace**:
both `Morrison-Lab/ai-config` and `d-morrison/ai-config` publish a plugin
named `ai-config` from the same repo, so only one entry can own the
`ai-config:` namespace and the rest are no-op collisions.
Enable at most one.

`bootstrap.sh` runs `scripts/check-plugin-overlap.py` at the end of an
install and warns when it detects either overlap;
run it standalone any time to re-check a machine.

A consumer repo's checked-in `.claude/settings.json` marketplace block (the
JSON above) is correct for a teammate cloning fresh with no ai-config
checkout, and redundant for anyone who ran `bootstrap.sh`.
The latter group opts out in **`.claude/settings.local.json`**, not in
`~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "ai-config@Morrison-Lab": false
  }
}
```

The file matters, and the intuitive choice is the wrong one.
Claude Code resolves settings
managed > command line > `.claude/settings.local.json` > `.claude/settings.json` > `~/.claude/settings.json`,
so the **user** scope is the lowest of the five rather than a personal
override --- a `false` there loses to the repo's checked-in `true`.
`enabledPlugins` resolves by precedence rather than by union, so the `false`
in the local file does switch the plugin off.
(See [Claude Code settings](https://code.claude.com/docs/en/settings),
"How scopes interact" and `enabledPlugins`; read 2026-08-12.
A plugin force-enabled by enterprise managed settings cannot be disabled this
way at all.)

## Use these skills with this repo's own `@claude` bot

The two mechanisms above cover the **CLI** (`~/.claude/skills` via `bootstrap.sh`)
and **other repos' cloud sessions** (the plugin marketplace). The third surface
is the `@claude` **CI bot** running on *this* repo's PRs/issues
(`.github/workflows/claude-bot.yml`).

That bot runs `claude-code-action`, which does **not** auto-discover skills from
`~/.claude` (the runner's home is fresh) or from a plugin unless it's installed.
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
builds. The **`session-lock`** skill (alias `deconflict-sessions`) is the
local-filesystem counterpart to `claim-pr`: a small registry CLI
(`skills/session-lock/scripts/ai-session.sh`) keeps a machine-local list of
active sessions under `.git/ai-sessions/`, so sessions can see each other,
refuse to share a working tree, isolate into a `git worktree`, and auto-recover
after a crash. There's an optional `SessionStart` hook for hands-off
registration. See [`docs/local-session-deconfliction.md`](docs/local-session-deconfliction.md).

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

Advisory: it reports the total against `--budget` and exits 0 over it, so it serves as a trend line on every PR rather than a gate.
A dangling **anchored** import (one written on its own line) does exit non-zero, being a defect rather than a size finding.
An unresolved **inline** `@token` is reported but does *not* fail, since most are prose (`@claude` mentions, email addresses) rather than mistyped imports --- so don't rely on this command to gate those.

For a repo that vendors ai-config as a `.ai-config` submodule, `--compare` answers what a pin bump would cost.
The import list is fixed; what changes is what those files weigh:

```sh
python3 scripts/check-context-closure.py --base ../consumer-repo --compare origin/main
```

Measured on `ucdavis/bcs` at a three-day-old pin, the same 33 imports had grown **+62%**, arriving silently since a bump's gitlink diff is one line (ai-config#1028).

Ideas borrowed from comparable projects (and their licenses) are recorded in
[`CREDITS.md`](CREDITS.md); see the `scout-peers` skill for the survey behind
them.

## Enforcement hooks (`hooks/`)

A few rules in this corpus cannot be enforced by writing them down, because
the rule is consulted when it is *read* and broken when a message is
*composed*.
`hooks/` ships the harness hooks that close those gaps:

| hook | event | enforces |
|---|---|---|
| `inject-local-time.sh` | `UserPromptSubmit` | supplies the real local time, so a recap timestamp is never recalled |
| `require-gh-repo-flag.py` | `PreToolUse` (Bash) | blocks a mutating repo-scoped `gh` command that omits `-R` |
| `no-offer-to-file.py` | `Stop` | blocks a reply that *offers* to file or record instead of doing it |
| `no-empty-promise.py` | `Stop` | blocks a reply committing to future behaviour ("going forward, I will/won't") when the same turn wrote no durable mechanism |
| `no-unfiled-finding.py` | `Stop` | blocks the *declarative* "worth its own issue" that leaves no filing behind |
| `no-stale-pr-status.py` | `Stop` | blocks a reply asserting a PR's check state from a reading older than the last push |
| `no-incomplete-check-enumeration.py` | `Stop` | blocks a reply declaring a PR clean when the only reading is `gh pr checks`, which omits check runs (not registered -- see ai-config#1717) |
| `remind-ums-after-error.py` | `UserPromptSubmit` | reminds, never blocks, when an admitted error has no recorded learning after it |
| `no-mistake-without-a-hook.py` | `UserPromptSubmit, Stop` | blocks after an admitted, mechanizable mistake until hook work follows it |
| `remind-learn-from-review.py` | `UserPromptSubmit` | reminds, never blocks, when an accepted reviewer finding has no learning or mechanism after it |
| `flag-unassigned-worktree.py` | `PreToolUse` (Agent) | warns, never blocks, on a write-capable Agent launch with no `isolation` |
| `no-unreviewed-pr.py` | `Stop` | blocks a reply ending a session after a PR was opened or readied with no reviewer requested, or after a push re-headed it with no reviewer requested since; deferred by draft status, or on a redaction PR by a `no-ai-review` label or an `ALLOW_UNREVIEWED_REDACTION_PR=1` assertion; wholly inert until its `MORATORIUM_END` (2026-09-01) while the standing directive forbids the Copilot request it would demand |
| `no-unshipped-commit.py` | `Stop` | blocks a completion reply after a commit with no later push or PR creation |
| `no-report-unfixed-hook-test.py` | `Stop` | blocks a status-only reply after CI identifies a missing hook test, until that exact test is written |
| `no-unmonitored-pr.py` | `Stop` | starts a detached two-minute `gh` poller when no model scheduler was used; blocks only when neither works |
| `inject-pr-monitor-status.py` | `UserPromptSubmit` | injects changed state from a detached PR poller on the next prompt; local pollers cannot wake a terminated model session |
| `ensure-open-pr-monitor.py` | `UserPromptSubmit` | ensures the agent-independent all-open-PR monitor service is running when an agent session begins |
| `monitor-open-prs.py` | detached timer | reconciles every open PR authored by the authenticated user every two minutes, including PRs opened outside the current session |
| `no-heavy-work-on-head-node.py` | `PreToolUse` (Bash) | blocks a heavy R/Quarto command run on a cluster's login node; inert off a cluster |
| `remind-brief-premises.py` | `PreToolUse` (Agent, Task, SendMessage) | reminds, never blocks, when a brief asserts corpus state that nothing derived --- including a `SendMessage` follow-up to a running agent, where corrections and new premises land |
| `remind-both-sides-from-git.py` | `UserPromptSubmit` | reminds, never blocks, when a revision-qualified blob is compared against the working-tree copy of that path |
| `remind-deserialize-before-binary-claim.py` | `UserPromptSubmit` | reminds, never blocks, when an escalation names a serialized artifact nobody deserialized |
| `flag-unchained-branch-switch.py` | `PreToolUse` (Bash) | warns, never blocks, when a branch switch and a later mutating git command are not joined by `&&` |
| `flag-add-a-outside-pathspec.py` | `PreToolUse` (Bash) | warns, never blocks, when `git add -A`/`--all`/`.` sweeps in an untracked file its own exclusion pathspec does not cover |
| `flag-reset-hard-uncommitted-work.py` | `PreToolUse` (Bash) | warns, never blocks, when `git reset --hard` is about to discard tracked, uncommitted changes |
| `no-handrolled-verdict-parse.py` | `PreToolUse` (Bash) | blocks matching a verdict phrase against a PR's review comments when `check-pr-fully-clean.py` has not answered for that PR |
| `warn-pr-create-without-dupe-check.py` | `PreToolUse` (Bash, mcp__github__.*) | warns when a command creates a PR and no earlier command in the session could have surfaced an already-open one; warns rather than blocks, since a duplicate PR is cheap to close and a blocked creation is not |
| `no-unmeasured-clock-claim.py` | `Stop` | warns, never blocks, when a reply states a Pacific clock time and no clock read appears since the previous message |
| `no-unauthorized-merge.py` | `PreToolUse` (Bash, mcp__github__.*) | blocks a PR/MR merge command (`gh pr merge`, `glab mr merge`, `gh api .../merge`, or GitHub MCP merge tools) unless an explicit `ALLOW_MERGE=1` assertion or active /mwc accompanies it |
| `no-whole-file-punct-replace.py` | `PreToolUse` (Bash) | blocks a whole-file glyph replace, which converts pre-existing glyphs on untouched lines and buries the real change in a mechanical diff |
| `flag-cop-out-offer.py` | `Stop` | warns when a reply *closes* on an offer to do work (`say the word`, `want me to`, `unless you'd rather`), so the author answers whether the action was already authorized; warns rather than blocks because authorization is not lexically decidable and asking before a merge or force-push is correct, and is tail-anchored because the failure is a recap that closes on an offer |
| `no-placeholder-reply.py` | `Stop` | blocks a reply whose whole content is a placeholder (`No response requested.`, `N/A`, a bare acknowledgement), anchored on the whole message since this corpus quotes the banned string constantly, and deliberately silent on a claim about the *work* (`Nothing to report.`), which the same rule requires |
| `require-stopping-point.py` | `Stop` | blocks a final reply lacking an explicit clean or non-clean stopping-point declaration |
| `flag-stale-adjacent-comment.py` | `PreToolUse` (Bash) | warns, never blocks, when a `git commit` changes a literal value while an unchanged comment within ten lines still asserts the old one |
| `no-misattributed-quote.py` | `Stop` | blocks a reply attributing a quoted phrase to a corpus file that does not contain it, when that phrase is in the file's `.rationale.md`/`.cases.md` sibling; stays silent when the phrase is found nowhere else, since a bare "not found" is the invented-quote misread |
| `warn-nonglobal-substitution.py` | `PreToolUse` (Bash) | warns, never blocks, on an in-place `perl -i`/`sed -i` substitution whose flags carry neither `g` nor a digit -- the shape that silently changes only the first occurrence, which bit mutation testing four times in one session (not registered -- see ai-config#1900) |

For agent-independent monitoring across all projects and sessions, install the
user service after the hook files are installed:

```bash
python3 scripts/install-pr-monitor.py
```

The service polls every open PR authored by the authenticated GitHub user every
two minutes. It does not depend on Claude, Codex, Gemini, or a project session
remaining open. If a user systemd bus is unavailable, the installer starts the
monitor immediately and installs an equivalent per-user cron `@reboot` entry.
It copies the monitor to `~/.local/share/ai-config/hooks/`, so neither path
depends on a temporary worktree or an individual agent's hook directory.

### Writing a warn-only hook: emit `systemMessage`, not `reason`

A `Stop` hook's `reason` is read **only** alongside `"decision": "block"`.
So a hook meant to *warn* rather than block, emitting `reason` by itself,
prints valid JSON that reaches nobody --- a detector that fires silently, which
is indistinguishable from one that never fires.
That is the worst possible defect for a guard, and nothing catches it: the
hook runs, exits 0, and its tests pass if they only assert that *something* was
printed.

Warn-only hooks here emit `systemMessage` (the `PreToolUse` ones pair it with
`hookSpecificOutput.additionalContext`); the four blocking `Stop` hooks pair
`reason` with `decision`.
The trap is that a blocking hook is the natural model to copy, and it uses
`reason` correctly.

So when adding a warn-only hook:

- emit `systemMessage`, and confirm by reading the printed payload rather than
  by checking that output is non-empty
- have its test assert the payload **shape** --- `bool(out)` cannot tell a
  surfaced warning from a discarded one
- mutation-check it: revert `systemMessage` to `reason` and require the suite to
  fail

`scripts/check-hook-output-shape.py` enforces this on every run: it verifies that
warn-only hooks never emit `reason` alone, that warn-only `Stop` hooks emit
`systemMessage`, and that their test suites inspect the payload shape rather than
checking non-empty output.

Every hook must ship a companion `test-<name>.py` beside it in the same change before pushing;
`scripts/test_hooks.py` runs
every such suite (pairing each with its subject) and also checks the reverse
direction --- it enumerates the hooks and flags any that lack a test --- so a
*tested* guard cannot regress unnoticed and an *untested* one cannot hide. It
gates `validate` and pre-commit. Two hooks are untested today
(`no-offer-to-file.py`, `inject-local-time.sh`), carried in an explicit
`KNOWN_UNTESTED` allowlist and tracked in
[#1080](https://github.com/Morrison-Lab/ai-config/issues/1080).

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

`bootstrap.sh` symlinks `hooks/` into `~/.claude` like any other top-level
directory, so the scripts arrive with no extra step.
Registering them is separate and deliberately opt-in --- bootstrap is a pure
symlinker and never edits `settings.json`, since silently rewriting harness
config while installing skills is the wrong default:

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
So pick one path: the plugin for a plugin install, `install-hooks.py --fix` for
a non-plugin (bootstrap-symlink) install.
`install-hooks.py` warns when it detects the plugin already enabled in the
`settings.json` it edits (best-effort --- it cannot see a project-level
enablement).

Bindings live in [`hooks/hooks.json`](hooks/hooks.json), in the native Claude
Code plugin-hooks schema (`hooks` keyed by event) --- a script cannot declare
its own event, so the file names the event, matcher, and, as tolerated extra
keys, the `script` and the rule each one enforces.
The file is dual-purpose: the plugin loader reads it directly when the
ai-config plugin is enabled, and `install-hooks.py` reads the same file to
register the hooks into `~/.claude/settings.json` for a non-plugin
(bootstrap-symlink) install.

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

On the plugin path a hook now behaves like a skill --- both go live on merge ---
so the distinction [`record-learnings`](skills/record-learnings/SKILL.md) draws
for a new skill, where "the skill becomes available locally immediately (via
symlink)" is listed as a feature, narrows to the non-plugin path.
There a symlinked skill is live at once, whereas a hook stays inert until
someone runs `install-hooks.py --fix`.
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

- `skills/` --- reusable workflow skills (`~/.claude/skills/`, `~/.gemini/skills/`)
- `codex-skills/` --- generated Codex wrappers (`~/.codex/skills/`)
- `cursor-rules/` --- Cursor AI rules in `.mdc` format (`~/.cursor/rules/`)
- `.cursorignore` / `.geminiignore` --- keep local worktree and Aider residue
  out of Cursor and Gemini search (same paths `.gitignore` already excludes)
- `AGENTS.md` --- universal vendor-neutral instruction file for all coding agents
- `tool-mappings.yml` / `tool-mappings.md` — cross-model tool registry and its
  generated reference (see *Tool mappings* above)
- `commands/` — slash commands (`~/.claude/commands/`)
- `memories/` — persistent notes & preferences (symlinked into VS Code Copilot memory dir)
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

`bootstrap.sh` symlinks `shared/` into `~/.claude/`, so `@shared/...` imports
resolve in local CLI sessions; the `@claude` CI bot reads `shared/` from the
repo root.

### Vendored from wai (`shared/vendored/`)

A few fragments are authored in **[d-morrison/wai](https://github.com/d-morrison/wai)**
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

Add more by creating a top-level dir here (e.g., `agents/`,
`output-styles/`) and rerunning `bootstrap.sh`.

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
- `plugins/` (in `~/.claude`) — managed by Claude Code itself from marketplaces. (Note: The top-level `plugins/` directory in this repo contains Antigravity plugin manifests and is linked into `~/.gemini/config/plugins/`.)

If a per-machine variation appears that's worth syncing (e.g., a global
`CLAUDE.md`), add it as a top-level entry here and update `bootstrap.sh`
only if it needs special handling beyond a directory symlink.

## Similar projects

Other AI coding-agent skill and config repos worth a look for ideas or
comparison:

- [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) --
  production-grade engineering skills for AI coding agents (Claude Code,
  Codex, Cursor, and others).
