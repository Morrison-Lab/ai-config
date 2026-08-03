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
ls -l ~/.claude/skills ~/.claude/commands ~/.codex/skills ~/.gemini/skills
scripts/inventory.sh                         # live counts of skills/wrappers/commands/docs
```

In a Claude Code session, type `/` and confirm the skills appear (e.g.
`/scout-peers`, `/ardi`).

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
generic CLI fallback). The sync script above embeds this table into every Codex
wrapper and renders the full reference at [`tool-mappings.md`](tool-mappings.md).
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
| `no-unfiled-finding.py` | `Stop` | blocks the *declarative* "worth its own issue" that leaves no filing behind |
| `no-stale-pr-status.py` | `Stop` | blocks a reply asserting a PR's check state from a reading older than the last push |
| `remind-ums-after-error.py` | `UserPromptSubmit` | reminds, never blocks, when an admitted error has no recorded learning after it |
| `no-mistake-without-a-hook.py` | `UserPromptSubmit` | reminds, never blocks, that an admitted mistake owes a *mechanism*, not just a note |
| `remind-learn-from-review.py` | `UserPromptSubmit` | reminds, never blocks, when an accepted reviewer finding has no learning or mechanism after it |
| `flag-unassigned-worktree.py` | `PreToolUse` (Agent) | warns, never blocks, on a write-capable Agent launch with no `isolation` |

A hook can ship a `test-<name>.py` beside it; `scripts/test_hooks.py` runs
every such suite (pairing each with its subject) and also checks the reverse
direction --- it enumerates the hooks and flags any that lack a test --- so a
*tested* guard cannot regress unnoticed and an *untested* one cannot hide. It
gates `validate` and pre-commit. Two hooks are untested today
(`no-offer-to-file.py`, `inject-local-time.sh`), carried in an explicit
`KNOWN_UNTESTED` allowlist and tracked in
[#1080](https://github.com/Morrison-Lab/ai-config/issues/1080).

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

Bindings live in [`hooks/hooks.json`](hooks/hooks.json) --- a script cannot
declare its own event, so the manifest names the event, matcher, and the rule
each one enforces.

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
Adding the entry to `~/.claude/settings.json` --- by hand or via
`install-hooks.py --fix` --- is *activation*, and it waits for review.
That line is what makes this checkable rather than a general instruction to be
careful: the file existing is harmless, the registration is not.

This makes hooks the deliberate exception to the ordering
[`record-learnings`](skills/record-learnings/SKILL.md) states for a new skill,
where "the skill becomes available locally immediately (via symlink)" is
listed as a feature.
The mechanism is what separates them, and it is what makes the exception cheap
to honour: a skill goes live by symlink whether you like it or not, whereas a
hook goes live only when someone deliberately runs `install-hooks.py --fix`.
Declining to run it is the entire cost of compliance.

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

(Corrected 2026-07-30: a `Stop` hook was written into `~/.claude/hooks/` and
registered in `settings.json` before its PR was opened, so a guard able to
block outgoing messages ran on the user's machine unreviewed.
The user's correction was "all new hooks must go through pr review before being
activated.")

## What's tracked

- `skills/` — reusable workflow skills (`~/.claude/skills/`)
- `codex-skills/` — generated Codex wrappers (`~/.codex/skills/`)
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
- `plugins/` — managed by Claude Code itself from marketplaces.

If a per-machine variation appears that's worth syncing (e.g., a global
`CLAUDE.md`), add it as a top-level entry here and update `bootstrap.sh`
only if it needs special handling beyond a directory symlink.

## Similar projects

Other AI coding-agent skill and config repos worth a look for ideas or
comparison:

- [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) --
  production-grade engineering skills for AI coding agents (Claude Code,
  Codex, Cursor, and others).
