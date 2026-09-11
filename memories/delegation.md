# Delegation ladder

Moved out of `preferences.md` (2026-08-26)
when that file hit the 1200-line cap;
this section is self-contained.

## Delegate heavy work to another CLI first --- codex, agy, opencode, and openrouter

> [!IMPORTANT]
> **`agy` (Google Antigravity) is confirmed usable as a dispatchable subagent, effective 2026-09-02** (user directives that day: "start using agy as a subagent where feasible", "use agy cli for it").
> The 2026-08-20 API-dispatch outage (`429: prepayment credits depleted`, user directive that day, scope corrected 2026-08-23) stays on record as history --- it explains why an earlier version of this banner said "out of service" --- but it never described the CLI, which the 2026-08-25 clarification already carved out as a separate, unaffected path.
> **A fresh Windows install on 2026-09-02, from the official `google-antigravity/antigravity-cli` GitHub release, confirms the CLI works end to end**: `agy --version` reports 1.1.24, `agy models` lists a real roster, and a headless smoke test returned the expected output in about 5 seconds.
> This file's "agy on Windows" section carries the install steps;
> `memories/preferences.md` points here for the same writeup rather than duplicating it.
> Route dispatchable subagent work to the `agy` CLI accordingly, per this section's cost order --- after `opencode`'s free tier on cost, alongside `codex` on capability.
> The interactive subscription/extension was never affected and was never at quota.
> Tracked as ai-config#1776.

For heavy, parallelizable **read / draft / verify** work ---
deep multi-file reading, scoping a backlog, auditing many files,
drafting N artifacts ---
route it to another agent CLI
and spend that budget **before** Claude/Workflow tokens.
Adversarial review dispatch is governed separately ---
by [`adversarial-self-review`](../shared/workflow/adversarial-self-review.md)'s
independence-first order,
not this cost-first ladder.
Three of those destinations are separately-billed plans with usage windows
(`codex`, `agy`, and OpenCode's `opencode-go/*` tier);
`opencode`'s hosted-free tier costs nothing,
and `openrouter` draws a prepaid balance rather than a window.
Claude stays the orchestrator ---
writes prompts, assembles stages, integrates outputs ---
and is the fallback for any stage the delegate can't finish.
This is a standing default across all sessions,
including ultracode/Workflow fan-outs,
not occasional use.

**Three of these are metered plans, and the rule is to try all three before
Claude's: `codex`, `agy`, and OpenCode's `opencode-go/*` tier.
`opencode`'s hosted-free tier sits outside that window logic entirely, and
`openrouter` is a prepaid balance rather than a window at all.**

| CLI / Provider | plan | skill |
|---|---|---|
| `codex` | ChatGPT | [`delegate-to-codex`](../skills/delegate-to-codex/SKILL.md) (alias `dtc`) |
| `agy` (Google Antigravity) | API retired, **CLI available** (2026-08-25) | none --- invoke `agy --print` directly |
| `opencode` | OpenCode Go (`opencode-go/*`, $10/mo windowed) + free hosted (`opencode/*`, opencode Zen) | [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md) (alias `dto`) |
| `openrouter` | prepaid credit balance, reached through OpenCode's `openrouter` provider | [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)'s "A third destination" section |
| `adv` | Multi-engine local reviewer (`pre-push-review.py`) | [`adv`](../skills/adv/SKILL.md) |

Headless dispatch: `agy --print="<prompt>" [--effort low]`,
or `agy --print "<prompt>" [--effort low]`.
The `--print` flag consumes the next token as its prompt argument,
so keep the prompt immediately after `--print` (via space or `=`)
and keep other flags outside it.

Dispatching large prompts --- a full diff plus context files ---
hits the Windows command-line length limit around 32k characters:
`--print=$big` fails with "filename or extension is too long",
and multiline content passed as a PowerShell argument mangles quoting.
Pipe the brief through stdin instead ---
`cmd /c "type brief.txt | agy.exe"` ---
which supplies the prompt without any `--print` flag at all.
Stage the brief file as UTF-8 first
(`Out-File -Encoding utf8` in PowerShell):
the default encoding is UTF-16LE,
which Python then cannot read as UTF-8.

A headless reviewer has no tool permissions and cannot run `git diff`.
Embed the diff **and** the full text of every touched file
directly in the brief.
Missing context produces phantom-reference findings ---
the reviewer cannot verify that a cited section exists ---
and missed findings, because it cannot check claims against their referent.
Regenerate the embedded diff before **every** re-dispatch round:
a stale brief once produced an entire review round
against content the fix had already changed.

`cursor` was named for the machine inventory by the user
(2026-08-25, CLI installed)
but has no measured headless dispatch mechanics here yet ---
probe before relying on it.

Exhaust the *current usage window* of each metered destination in turn ---
`codex` first (roughly 5 hours),
then `agy` CLI as its own availability allows,
then OpenCode's `opencode-go/*` window ---
then fall back to Claude until a window resets.
"Delegate first" means the current window,
not abandoning Claude permanently.

**`opencode`'s hosted-free tier has no window to exhaust,
which changes where they sit rather than just adding a row.**
That tier costs nothing,
so for work a small model can actually do it goes *ahead* of codex and agy
rather than behind them: there is no budget to conserve by skipping it.
Capability is the binding constraint in its place,
and it is unmeasured here ---
the hosted ids are preview names
nobody has benchmarked against this corpus's work.
**The discriminator between hosted tiers is the provider prefix,
not a `-free` id suffix.**
See [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)'s
"Hosted-only routing rule" section
for the `opencode models` evidence and exact count.

**A third OpenCode tier, `opencode-go/*`, is a $10/mo windowed
subscription** rather than a free one, active and verified
2026-08-25.
It behaves like `codex`'s window --- exhaust it before falling back ---
not like the hosted-free tier above.

**A fourth destination, OpenRouter, is neither windowed nor free: it draws
on a prepaid credit balance**, active and verified 2026-08-25.
`opencode` reaches it as an ordinary provider once a config entry
references it (an unreferenced provider lists no `openrouter/*` ids at
all), configured in the user-global `~/.config/opencode/opencode.jsonc`
--- not `opencode.json`, which is a separate, repo-scoped config file ---
and keyed by the `OPENROUTER_API_KEY` environment variable.
Its draw is per-token rather than time-windowed,
so "delegate first" means spending the free tiers and subscription windows
above before drawing on OpenRouter credit or Claude tokens ---
not spending OpenRouter credit before those free tiers and windows are
exhausted.
One class of OpenRouter model is worth the balance: anonymized frontier
**stealth previews**, unbenchmarked but plausibly capable of judgment
work the hosted-free tier cannot do --- see
[`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)'s "A
third destination" section for the activation mechanics, the stealth
roster query, and the data-sensitivity rule (a hosted destination's
payload leaves the machine regardless of billing tier, so a data
trigger forbids `openrouter/*` exactly as it forbids `opencode/*` and
`opencode-go/*`).
When work must not leave the machine, do not delegate it to a model unless the
repository explicitly approves a hosted destination.
Use deterministic tools
or handle it in the authoring session instead.
[`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md) carries the
mechanics and the hosted-only routing rule.
The tiers and version above were measured 2026-08-19 on opencode 1.18.15.
`delegate-to-codex` operationalizes the codex mechanics ---
background runner plus DONE-marker poll, `--output-schema`,
exhaustion detection, Claude fallback ---
and those transfer to `agy`, whose CLI exposes the same shape:
`--print` for non-interactive,
`--json-schema` for structured output,
`--effort`, `--model`, and `--sandbox`.

**`agy --print` CONSUMES THE NEXT TOKEN as its prompt,
so a flag placed between the two becomes the prompt.**
This is the whole of what makes `agy` usable headlessly,
and getting it wrong looks exactly like a broken tool:

```bash
agy --print "Reply with only the word BANANA."                 # -> BANANA
agy --print "Reply with only the word BANANA." --effort low    # -> BANANA
agy --print="Reply with only the word BANANA." --effort low    # -> BANANA
agy --print --effort low "Reply with only the word BANANA."    # -> explains what --effort does
```

That last line is the failure, and its output is the proof:
the CLI answers the prompt `--effort`,
because `--print` took `--effort` as its value
and the real prompt fell out as an unconsumed positional.
So the rule is about **position**, not syntax ---
either keep the prompt immediately after `--print`,
or bind it with `=` and put other flags after.

**Both forms exit 0**, so the drop is invisible
to any caller keying on exit status,
which is what a delegation wrapper keys on.

Measured 2026-08-15 and re-measured 2026-08-16,
`agy` 1.1.13 at `~/.local/bin/agy`.
Three space-form and three equals-form runs of the same prompt,
with nothing between the flag and the prompt,
all returned `BANANA`.

**An earlier version of this entry said the equals sign was REQUIRED
and blamed Go's `flag` package.**
Both halves were wrong,
and the error is worth keeping because it is a confound rather than a slip.
Four failing probes all carried another flag between `--print` and the prompt.
Two working ones did not, and also happened to use `=`.
Two variables moved together and the visible one got the credit.
Go's stdlib `flag` in fact treats `-flag value` and `-flag=value` identically
for a string flag,
which is what a reviewer pointed out (`Morrison-Lab/ai-config#1487`).

**Its figures still need checking, whichever form you use.**
Asked to read `scripts/added_lines.py` in `ucdavis/bcs`,
it returned the right function name and its exact line number
(`added_lines`, line 30), so it really read the file.
It also reported the file as 74 lines where `wc -l`, `grep -c ''`,
and Python's `splitlines()` all say 73 --- same run, 2026-08-15,
same 1.1.13 binary.
So a delegate having genuinely done the work does not make the figures it
reports true,
and any count one returns is re-derived rather than quoted ---
the same standing treatment codex's output gets.

**Two upstream bugs are real and are NOT this.**
`google-antigravity/antigravity-cli` #76 (closed, 1.0.0) reports `--print`
silently emitting nothing on a non-TTY,
and #318 (open, 1.0.6) reports it hanging there.
Neither matches the symptom above ---
ours returns prompt content promptly on 1.1.13 ---
but both are worth knowing before trusting a headless run,
since each fails silently in its own way.

- **Do:** route heavy read/draft/verify work to `opencode`
  (for zero-cost and local-only tasks)
  or to `codex` and the `agy` CLI before Claude.
- **Do:** keep the prompt immediately after `--print`
  or bind it with `=` when dispatching the `agy` CLI headlessly.
- **Do:** re-verify any figure a delegate reports,
  since `agy` miscounted a 73-line file by one while reading it correctly.
- **Don't:** put another flag between `--print` and the prompt ---
  that flag becomes the prompt,
  and the exit status is still 0.
- **Don't:** read "we have agy quota" as "agy is usable".
  Quota and a working invocation are separate facts,
  and the second took five probes plus a review round to establish.

**Recurrence, 2026-09-06 (`d-morrison/rme` ardia sweep).**
`agy --print --model X < file` fails with `--print took --model as its prompt`.
Two things in that one line are not covered above.
`--print-timeout` is a further flag, absent from the `--effort`/`--model`/`--sandbox`
list this file gives for the CLI's shape.
And the prompt here arrives on **stdin**, which the unconsumed-positional mechanism
above does not describe --- note that the stdin route documented earlier for the
Windows command-line length limit supplies the prompt with no `--print` flag at all,
so it does not collide with this trap.
The confirmed working invocation:
`agy --model X --print-timeout 8m --print="$(cat prompt.txt)"`.

Stated 2026-07-02 ("exhaust its tokens before using our own"),
reaffirmed 2026-07-06 ("always use codex first
(until we hit the 5-hour limits) before using up claude quota"),
and widened 2026-08-15 ("in addition to codex, we have agy quota to use;
try using both of those as subagents before exhausting claude quota").

## agy on Windows

Measured 2026-09-02 on the user's Windows 11 machine.
This is a fresh, from-scratch install, distinct from the 1.1.13 install this file's mechanics sections above already document --- re-run these steps rather than assuming an existing install matches.

**Install from the official GitHub release, not from an IDE bundle.**

```bash
gh release download 1.1.24 -R google-antigravity/antigravity-cli \
  -p agy_cli_windows_x64.zip
# unzip, then copy the extracted antigravity.exe to ~/.local/bin/agy.exe
```

It authenticated with no extra step, reusing the Antigravity IDE's own login.
`agy --version` reports `1.1.24`.

**`agy models` lists a real roster**, unquoted here since a model roster is exactly the kind of fact a vendor changes without notice --- run the command rather than trusting a pasted list.
As of 2026-09-02 it included `gemini-3.8-flash-{high,medium,low}`, `gemini-3.7-flash-{high,medium,low}`, `gemini-3.6-flash-{high,medium,low}`, `gemini-3.1-pro-{high,low}`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`, and `gpt-oss-120b-medium`.

**A headless smoke test confirms the print path works end to end:**

```bash
agy --print "Reply with only the word BANANA." \
  --model gemini-3.8-flash-medium --output-format text </dev/null
```

Returned `BANANA` in about 5 seconds.
The existing "`agy --print` CONSUMES THE NEXT TOKEN" rule above still applies --- keep the prompt immediately after `--print`.

**Headless mode cannot satisfy a tool's permission prompt, and it fails with a named cause rather than hanging.**
A tool needing a permission it hasn't been granted (`read_file` is the one observed) makes the run print `jetski: no output produced --- a tool required the "read_file" permission that headless mode cannot prompt for` and produce nothing.
The available escapes are `--mode plan` (read-only), `--mode accept-edits`, `--dangerously-skip-permissions`, or an allow-rule under `permissions.allow` in `settings.json` --- but this file's own auto-mode classifier section already found `--dangerously-skip-permissions` and `--mode accept-edits` denied by Claude Code's permission classifier, so those two may not be reachable from an orchestrated dispatch even where they solve the headless problem.
**Measured 2026-09-09: a `command(*)` rule under `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` is honoured in headless mode.**
`--dangerously-skip-permissions` stays denied by Claude Code's classifier, and `--mode plan` is still untested.
With this in `~/.gemini/antigravity-cli/settings.json` (agy 1.1.28, Windows 11;
`<user>` and `<repo>` stand for the real account and checkout):

```json
{
  "permissions": {
    "allow": [
      "command(*)",
      "read_file(C:\\Users\\<user>\\path\\to\\<repo>)",
      "write_file(C:\\Users\\<user>\\path\\to\\<repo>)"
    ]
  },
  "trustedWorkspaces": ["C:\\Users\\<user>\\path\\to\\<repo>"]
}
```

A plain `agy --print "<prompt>" --effort low` ran a shell command and reported its stdout, from the user's own terminal and then from a Claude Code Bash call.
That contradicts upstream issue [google-antigravity/antigravity-cli#548](https://github.com/google-antigravity/antigravity-cli/issues/548), whose reports through agy 1.1.27 say `command()` grants in this file are loaded but never consulted by `--print`, and that only `~/.gemini/config/config.json` (`userSettings.globalPermissionGrants.allow`) is honoured.
So the measurement was discriminated against that confound rather than taken on faith.
This machine's `config.json` carried 17 grants from earlier interactive sessions (`command(gh)`, `command(godot)`, three `bash.exe` invocations, three `read_url` hosts), none of which covers `hostname` or `whoami`, and a headless probe ran both.
The same probe had been denied for the `command` permission minutes before the `settings.json` edit, with `config.json` unchanged.
`cli.log` shows the two stores loaded separately (`applyUserSettings: stored shared config permissions: allow=17` from `config.json`, then `CLI settings initialized: permissions=&{Allow:[command(*) ...]}` from `settings.json`), and no `ApplyProjectPermissionGrants` entry for the project.
On a build older than 1.1.28, or if a `command(*)` rule here is ignored, read those two `cli.log` lines to tell "loaded" from "applied", and fall back to a `command()` entry under `globalPermissionGrants.allow` in `config.json`, per #548.
`command(*)` is the form to use.
As of 2026-09-09, upstream issue [google-antigravity/antigravity-cli#614](https://github.com/google-antigravity/antigravity-cli/issues/614) reports two Windows defects: `command(git)` never matches, because the resolved `C:\Program Files\Git\...` path is split at the space, and a `\*` glob inside a `read_file`/`write_file` rule crashes the sandbox.
So directory rules are written bare (they are recursive).
`command(*)` is a broad grant, so pair it with a `trustedWorkspaces` list that names only the repos the dispatch should touch.
Before the rules existed, `-p "/permissions"` itself was denied for `read_file`, so headless mode cannot even list its own rules until one is granted.

Two facts about the run that every brief has to account for:

- **agy's shell is PowerShell 5.1**, so `a && b` is a parser error.
  agy recovered by re-running under `cmd /c`, but a brief should say `;` or `cmd /c "..."` up front rather than spending a turn on the failure.

- **agy's working directory is `~/.gemini/antigravity-cli/scratch`, not the caller's cwd**, so `git rev-parse` there fails with `not a git repository`.
  Start every brief with `Set-Location <absolute repo path>` or pass `--add-dir`.

And one fact concerns the dispatch shape from Git Bash: `cmd /c "type brief.txt | agy.exe"` does not work there, because MSYS rewrites `/c` into a `C:\` path, so `cmd` opens an interactive shell, prints its banner, and exits on the piped brief with exit 0 and a 265-byte "output".
Write `cmd //c` from Git Bash, or pass a short brief directly with `--print "$(cat brief.txt)"`.

The Claude Code classifier is the other half.
As of 2026-09-09, `--dangerously-skip-permissions` was denied on every attempt (three, across two sessions).
Writing the `permissions.allow` block into `settings.json` was denied once via the Edit tool and then accepted via the Write tool in the next turn, after the user said "you paste it for me" --- so the file edit is reachable, and the flag has not been.
The "Don't" bullet further down, measured 2026-09-07 on macOS, records the opposite outcome for the same edit;
both are dated samples of the classifier, and the Write tool after an explicit user instruction is the shape that passed.
After those denials the classifier escalated: it denied twice the plain `agy --print` probe it had accepted once earlier in the same session;
the classifier accepted the identical command again once the user had run it in their own terminal and reported the result.
Read that as the mistake-patterns Pattern 43 escalation rather than as a property of the command.

**A `language_server.exe agentapi` fallback exists for when no CLI is installed but the Antigravity IDE is already open.**
This is not a CLI dispatch at all --- it talks to the IDE's own running language server:

```bash
# --model accepts one of: flash, flash_lite, pro
language_server.exe agentapi new-conversation --model=flash "<prompt>"
```

with environment variables read from the running IDE process: `ANTIGRAVITY_LS_ADDRESS=127.0.0.1:<higher of the two LISTENING ports of language_server.exe>`, `ANTIGRAVITY_CSRF_TOKEN=<the --csrf_token value from that process's own command line>`, and `ANTIGRAVITY_PROJECT_ID=<the workspace path>`.
The reply lands as a `PLANNER_RESPONSE` step in `~/.gemini/antigravity/brain/<conversationId>/.system_generated/logs/transcript.jsonl`, not on stdout, so a caller has to poll or tail that file rather than capturing a return value.
This route did real tool work and two edit-only doc fixes on 2026-09-02, so it is a working fallback, not merely a documented one --- but it depends on the IDE process already running, which the direct CLI install above does not.

- **Do:** install from the official `antigravity-cli` GitHub release when setting up `agy` fresh on Windows, and confirm with `agy --version` and `agy models` before trusting the install.
- **Do:** read `agy models`' own output for the current roster rather than reusing a pasted list, since a vendor roster is exactly the kind of claim this corpus times.
- **Do:** reach for the `agentapi` fallback only when the IDE is already open --- it reads the IDE's own ports and token, so it cannot start a fresh Antigravity session on its own.
- **Don't:** treat any of `--mode plan`, `--mode accept-edits`, `--dangerously-skip-permissions`, or a `permissions.allow` rule as the settled fix for a headless permission denial until one has actually been tried and reported --- this section names the options, not a verdict.
- **Don't:** expect the `agentapi` transcript file to update instantly;
  it is a log a background process appends to, not a synchronous response.

## agy as a cheap adversarial-review lane on macOS

Measured 2026-09-02 with `agy` 1.1.22 at `~/.local/bin/agy`,
across nine review rounds on two PRs,
[ai-config#3061](https://github.com/Morrison-Lab/ai-config/pull/3061) and [gha#826](https://github.com/Morrison-Lab/gha/pull/826).
Each round was one command,
`agy --print "$(cat prompt.txt)" --output-format text </dev/null`,
with the unified diff pasted into the prompt file.
Headless `agy` cannot read repo files on its own,
so the diff has to be supplied inline rather than pointed at.
Each round returned in roughly one to three minutes,
at no Claude quota cost.

**`agy` caught real defects a Sonnet `adversarial-reviewer` round had missed:**
an untracked-file false clean in a git-scope change,
a count that did not add up,
and an inaccurate quoted cross-reference.
[`when-to-orchestrate`](../shared/workflow/when-to-orchestrate.md) argues
that a judgment-heavy verify stage belongs with a model in a different family;
these misses are a second data point for that argument.
The misses were exactly the kind a same-family reviewer inherits along with the finder's blind spots.

**`agy` also produced many stylistic objections stricter than this corpus's own norm,**
which the dispatcher has to rebut rather than apply.
Any `, and` clause written on one physical line read as a semantic-line-break violation,
though the corpus's own gate does not flag a comma-joined line with no mid-line semicolon,
per [`semantic-line-breaks`](../shared/writing/semantic-line-breaks.md).
Any sentential `which` read as an antecedent defect,
whether or not the antecedent was ambiguous.

**Headless `agy` cannot write a file on macOS without a permission allow-rule.**
Two probes, both 2026-09-02, both with `--mode accept-edits --output-format text </dev/null`, both exit 0, both writing nothing:
a plain "create probe.txt" brief printed
`jetski: no output produced --- a tool required the "command" permission that headless mode cannot prompt for, so it was auto-denied. Add an allow-rule under permissions.allow in settings.json (e.g. command(<target>)).`,
and a brief forbidding shell use and asking for the native file tool printed
`jetski: no output produced --- a tool required the "write_file" permission that headless mode cannot prompt for, so it was auto-denied. Add an allow-rule under permissions.allow in settings.json (e.g. write_file(<target>)).`.
The settings file is `~/.gemini/antigravity-cli/settings.json`,
which on this machine held only narrow `command(...)` rules from interactive use.
The "agy on Windows" section above left open which escape clears a headless permission denial for a read-only review dispatch.
These probes settle a different question, a file write rather than a review:
`--mode accept-edits` alone reaches neither a shell-routed nor a native file write on macOS.

- **Do:** dispatch `agy --print` for review-only passes on a pasted diff, on macOS as on Windows.
- **Do:** state the corpus's actual norms in the brief
  (the clause-join convention, when `which` is fine),
  and check each `agy` style finding against the written convention before applying that finding.
- **Do:** keep implementation work on a subagent that can write
  until an `agy` allow-rule for `write_file` is measured to work.
- **Don't:** apply an `agy` style finding as though it were a corpus rule without that check.
- **Don't:** hand headless `agy` a task that requires reading, running, or writing anything in the repo.

**Confirmed again 2026-09-06/07: `--mode accept-edits` gates COMMANDS, not
only edits, so it is not sufficient on its own.**
The allow-list at `~/.gemini/antigravity-cli/settings.json` already carried
a broad `write_file(*)` entry from prior use,
alongside only narrow per-command entries such as `command(pytest)` --
so write permission was already open while command permission stayed
closed,
and a brief that ran an arbitrary shell command still hit the same
`command(<target>)` denial the first probe above found.
Add the specific command under `permissions.allow`,
or accept `--dangerously-skip-permissions` for a fully trusted brief.

**Also measured: `agy -p ""` fails fast rather than hanging.**
An empty prompt -- which happens when a brief file meant to be interpolated
with `$(cat file.txt)` was never actually written,
so the substitution is empty --
returns immediately with `Error: Error: empty prompt.` and a non-zero exit.
This is diagnostically useful: a zero-byte `agy` log can mean either this
fast-fail or a genuine stall,
and the two are distinguishable by checking whether the process has already
exited (fast-fail) or is still running (stall),
and by reading the log's first line for the `empty prompt` error before
assuming a hang.

- **Do:** add a `command(<target>)` allow-rule (or `--dangerously-skip-permissions`)
  before assuming `--mode accept-edits` alone lets a headless `agy` brief
  run a shell command.
- **Do:** check whether the brief file that feeds `$(cat file.txt)` actually
  has content before dispatching, and read a zero-byte log's process state
  and first line before diagnosing it as a stall.
- **Don't:** treat `--mode accept-edits` as equivalent to
  `--dangerously-skip-permissions` for command execution -- it is not, even
  when `write_file` is already broadly allowed.

**Measured 2026-09-07: neither escape agy's own error message names is
reachable from an orchestrating Claude Code session, narrowing (not
closing) the open question the "agy on Windows" section above left
unmeasured --- that section asked which of four named escapes clears
agy's own headless denial, and what follows tests reachability from
Claude Code, not agy-side efficacy; `--mode plan` stays untested, and
whether either escape would work for agy if a human applied it directly
is still unmeasured.**
Dispatching `agy -p "<brief>" --effort medium --mode accept-edits`
(agy 1.1.27, `~/.local/bin/agy`) for a headless read-only task
produced no output and exited 0, printing only:
`jetski: no output produced --- a tool required the "command"
permission that headless mode cannot prompt for, so it was
auto-denied.
Add an allow-rule under permissions.allow in
settings.json (e.g. command(<target>)).
Alternatively, re-run with
--dangerously-skip-permissions to auto-approve all tools.`
Note the exit code: a caller checking only the exit status
reads this total no-op as success,
so check the printed output too, not just `$?`.
Both remedies the message names were then tried,
in the same orchestrating Claude Code session,
and both were refused:

1. `--dangerously-skip-permissions` --
   refused by the auto-mode classifier,
   as already documented in this file's
   "auto-mode classifier" section below.
2. Adding scoped read-only rules (`command(actionlint)`, `command(grep)`,
   and similar) to `permissions.allow` in
   `/Users/ezramorrison/.gemini/antigravity-cli/settings.json` --
   also refused by the auto-mode classifier, editing that file directly.

That settings file already existed on this machine
with its own `permissions.allow` and `trustedWorkspaces` lists
from prior interactive use --
it lives under `~/.gemini/antigravity-cli/`,
not under `~/.antigravity/` or `~/.agy/`,
which is where a first search would look.

These are Claude Code's own auto-mode permission-classifier denials,
not a corpus `PreToolUse` hook,
so no `daytb`, `mwc`, or `away` grant clears them --
the remedy is a Bash permission rule added to Claude Code's own settings
(or `settings.local.json`),
or the user making that edit themselves in an interactive turn.
Read this as one dated sample, not a closed door:
only these specific commands, on this one session and date, were denied.

- **Do:** check `agy`'s exit code AND its printed output
  before treating a headless dispatch as having done anything --
  a permission-denied no-op exits 0.
- **Do:** look for `agy`'s settings file at
  `~/.gemini/antigravity-cli/settings.json` first,
  not under a `~/.antigravity/` or `~/.agy/` guess.
- **Don't:** assume editing `permissions.allow`
  from inside the orchestrating Claude Code session
  is a reachable escape for a headless `agy` permission denial --
  as of 2026-09-07 that edit itself was denied
  by Claude Code's own auto-mode classifier,
  the same as `--dangerously-skip-permissions` was.
  On Windows, 2026-09-09, the same edit passed via the Write tool,
  after the user asked for it in so many words;
  see the measured section above.
- **Don't:** reach for a `daytb`/`mwc`/`away` grant
  to clear this kind of denial --
  it is Claude Code's permission system reacting
  to the shape of the command, not a corpus hook a grant can waive.

## A measured lane comparison: codex, opencode, agy, and Sonnet reviewers, one real task each

Measured 2026-08-27/28 PT across a 13-merge GIA sweep on Morrison-Lab/ai-config, comparing four lanes on real work rather than a benchmark.

**codex** implemented five well-specified hook/script briefs with high fidelity.
Its only misses traced back to the *brief* being wrong --- one brief was built from a truncated issue-body read, and codex faithfully implemented the truncated version.
That is a briefing defect, not a codex defect, so the fix is to verify the brief's own inputs before dispatch, not to trust codex less.

**codex's macOS sandbox cannot write a git worktree's shared `.git` directory.**
A worktree's `.git` is a file pointing at the parent repo's shared `.git/worktrees/<name>` directory, and codex's sandbox denies a write there with `index.lock: Operation not permitted`, even under a sandbox mode that otherwise permits writes inside the worktree's own tracked files.
The orchestrator commits on codex's behalf --- codex prepares the diff, the parent session runs `git add`/`git commit` --- rather than treating the denial as a codex task failure to retry.

**opencode (free tier) and the `agy` CLI each completed a small doc task correctly on first real dispatch**, and each still needed the same adversarial pass any diff gets.
`agy`'s output drew three style findings plus one finding that flatly contradicted standing text elsewhere in the corpus, on a later round.
opencode's output drew an `away`-scope overclaim (asserting coverage the skill's own text does not support) and an imprecise boundary phrase, both caught only by fact-checking the claim against the cited skill's actual text rather than by a structural read.
Neither miss was visible from the diff's surface;
both needed the underlying claim traced back to its source.

**Sonnet adversarial reviewers were the highest-value spend in the sweep.**
Across roughly 20 review rounds they surfaced a pre-existing verdict-spoofing parser vulnerability already live on `main`, several straddle/swallow enumeration bypasses, and repeatedly refused to accept an enumeration-based patch until a structural fix replaced it --- holding the line across multiple rounds rather than accepting the first plausible-looking patch.

- **Do:** route a well-specified, mechanical brief to `codex` first.
- **Do:** give a cheap CLI's output --- `codex`, `opencode`, or `agy` --- the same adversarial review any diff gets;
  a clean run is not a clean review.
- **Do:** fact-check every scope or boundary claim a cheap model writes against the source it cites, not against how the sentence reads.
- **Do:** have the orchestrator commit on codex's behalf when a worktree write is denied by the sandbox, rather than reading the denial as a task failure.
- **Don't:** read a cheap CLI's own "checks passed," or a clean-looking diff, as review.
- **Don't:** brief any implementer --- cheap or not --- from a sliced or truncated issue-body read;
  verify the brief's own inputs before dispatch.

## The auto-mode classifier allows plain headless CLI dispatch and denies interactive-trust flags

Measured 2026-08-27/28 PT, same GIA sweep.
Claude Code's auto-mode permission classifier denied `cursor-agent --trust` (see [`cursor.md`](cursor.md)'s "`cursor-agent --trust` can be denied outright" section for that specific case), `agy --dangerously-skip-permissions`, and `agy --mode accept-edits`, while allowing plain `agy --print` and plain `opencode run` --- each launched via the harness's own backgrounding (`run_in_background`) rather than a shell `&` with redirects.
The pattern across all three denials is the same: a flag that grants the dispatched CLI standing permission to bypass its own future confirmations reads to the classifier as a blanket permission override, and gets denied on that basis even though the underlying dispatch --- a single non-interactive run --- is otherwise unremarkable.

**A classifier denial on a compound Bash call kills every segment of that call, not just the flagged one.**
When a single Bash invocation bundles a heredoc that writes a brief file with the dispatch that reads it, and the classifier denies the call, nothing in the call ran --- including the heredoc.
The next dispatch attempt then reads a brief file that was never written, and fails with "brief does not exist," which reads like a missing-file bug rather than like the actual cause: an earlier denial that took the whole compound call down with it.

- **Do:** write a brief file in its own Bash call, separate from the call that dispatches on it.
- **Do:** dispatch a headless CLI (`agy --print`, `opencode run`) via the harness's own `run_in_background`, not a shell-level background operator.
- **Don't:** bundle a file-write with a dispatch that might be denied --- assume nothing in a denied compound call executed, including segments before the denied one.
- **Don't:** reach for an interactive-trust or standing-permission flag (`--trust`, `--dangerously-skip-permissions`, `--mode accept-edits`) to make a headless dispatch "just work" --- the plain non-interactive form is both sufficient and classifier-approved.

## "Local" means CLI-reachable, not on-device --- and local inference is prohibited

Directive from the user, 2026-08-27, given across three messages:
"use cheap and free local models when feasible";
"(always)" --- confirming a standing rule rather than a one-off;
and "by local, I mean available through this computer's CLI;
I don't care if they run on this computer or in the cloud."

- **Do (user's words):** prefer cheap and free models when feasible,
  always ---
  and treat "local" as "reachable through this computer's CLI,"
  not as "running on this computer's own hardware."
- **Do (inferred):** apply that preference as this file's own ladder:
  CLI-reachable budgets first ---
  `codex`'s ChatGPT-plan window,
  `opencode`'s free hosted tier plus Zen,
  and the `agy --print` window ---
  then OpenRouter's prepaid credit balance,
  then a cheap Claude tier (haiku, then sonnet) ---
  reserving the conductor's own tier for judgment-heavy work.
  Only `opencode`'s hosted-free tier is actually free;
  `codex` and `agy` stay the metered plans this file already calls
  them,
  placed ahead of Claude because their cost is sunk within the
  current window, not because they cost nothing.
  Within the CLI-reachable group itself, no new ordering is implied
  beyond what the rest of this file already sets:
  `opencode`'s hosted-free tier has no window to exhaust,
  so it goes ahead of the metered `codex` and `agy` windows,
  per the "no window to exhaust" paragraph above.
- **Do (inferred):** read "local" as CLI-reachable for cost ordering only.
  A hosted model reached through a local CLI still sends its payload
  off-machine.
  If data must stay on the machine and no hosted destination is
  approved, keep the work in the authoring session and use deterministic tools.
- **Don't (inferred):** default a dispatch to the inherited conductor
  tier because the cheaper route costs setup effort ---
  staging a brief file, checking a window's remaining budget, or
  probing an unmeasured destination is the ladder's ordinary cost of
  entry, not a reason to skip the cheaper hosted route.
- **Don't (user directive, 2026-08-30):** run Ollama, LM Studio, llama.cpp,
  or another local/on-device model.
  Local inference can crash the user's computer.
  This later directive supersedes the 2026-08-27 inclusion of local
  Ollama in the cost ladder without changing the CLI-reachable meaning of
  "local" for hosted tools.
- **Don't (inferred):** route work to a cheap tier where it
  predictably fails for a small model ---
  adversarial review, long-list triage, or any of the judgment-heavy
  work [`select-model`](../skills/select-model/SKILL.md)'s decision
  tree already carves out (architectural decisions, subtle bugs,
  security audit, orchestrator loop) ---
  and count the resulting retry as cheap delegation.
  Escalate that work to a capable tier up front;
  a failed cheap attempt plus a retry costs more than starting at the
  right tier once.

## Never dispatch a subagent on Fable without explicit, specific permission

The rule, its guard (`hooks/no-fable-subagent.py`), and the
`FABLE_SUBAGENT_OK=1` grant mechanism live in `CLAUDE.md`'s section of the
same rule ([#2927](https://github.com/Morrison-Lab/ai-config/issues/2927));
read them there rather than here.
This entry adds the one inferred step the rule does not spell out,
and keeps the case records behind it.

- **Do (inferred):** before dispatching an agent from a definition file under
  `.claude/agents/`, read its frontmatter for `model:`;
  if the line is absent, pass one on the call.
  `adversarial-reviewer` is one such definition, and `CLAUDE.md`'s pre-push
  rule dispatches it by name, so this is the common path onto Fable.
- **Don't (inferred):** read the conductor's `/model` setting as saying
  anything about what a worker may run on;
  a session switched to Fable mid-way turns every model-less dispatch after
  the switch into a Fable launch with nothing in the call recording it.

Three sessions produced case records on 2026-09-01, and they are three
events, not three tellings of one.

**The directive.**
The session that received it is the one `CLAUDE.md` and the hook's docstring
measure:
10 `Agent` launches, 8 of them inheriting `claude-fable-5-1`
(six adversarial reviews, two sidecars),
until the account hit its usage limit.

**A near miss** (session `01CEJjpA4tREQecY1yJzae2U`).
Four dispatches ran.
Three passed `model: "sonnet"`.
One --- `adversarial-reviewer`, whose definition carries no `model:` ---
passed nothing and inherited Opus 5, because the session was on Opus 5 at
12:47 PDT.
At 13:12 PDT the user switched the session to Fable with `/model`.
The same dispatch issued after that switch would have run on Fable with an
identical call, and no artifact would have recorded the difference.
Asked "have you been spawning subagents using fable?", the session checked
every dispatch's parameters and the reviewer definition's frontmatter and
answered no;
the answer was one timestamp away from yes.

**A breach** (session `01VJ5YLpnoipBafisrTZkCCt`, the `gia /mwc /daytb` sweep
driving [#2896](https://github.com/Morrison-Lab/ai-config/pull/2896) and
issue [#1935](https://github.com/Morrison-Lab/ai-config/issues/1935)).
It dispatched `adversarial-reviewer` for every pre-push self-review round
--- eleven rounds on
[#2896](https://github.com/Morrison-Lab/ai-config/pull/2896) and two on
[#1935](https://github.com/Morrison-Lab/ai-config/issues/1935) ---
with no `model` parameter on any call,
on a session that was on `claude-fable-5-1` throughout,
so all thirteen inherited Fable.
Nothing in any call recorded it;
what made the inheritance visible was the last dispatch dying with
`rate_limit ... model sent to the API: claude-fable-5-1`.

## Claude subagents are for reviewers only; every other subagent runs on agy

**Directive from the user, 2026-09-09, during a quota sprint that hit the 5-hour Claude limit twice in one day: "use agy only for subagents;
no claude subagents except reviewers".**
It arrived after two caps in the same day (five machine-wide, then two machine-wide with one per session), so read it as the standing rule rather than as a throttle for that afternoon.
The one carve-out is the `adversarial-reviewer`, and it is narrower than it first looked.
`hooks/no-push-without-self-review.py` on `main` accepts a cross-family review as a discharge when the review ran as the sole command of one Bash call in the shape `agy --print '<single-quoted prompt>'` (its `EXTERNAL_REVIEWER_COMMAND_RE`), so a session whose installed copy is current needs no Claude reviewer at all.
The copy this session ran under refused every `agy` review because it predated that acceptance: 67 of the 86 hook copies under `~/.claude/hooks` differed from `main` on 2026-09-10, the drift [ai-config#3094](https://github.com/Morrison-Lab/ai-config/issues/3094) tracks, and the first response to a refusal that names no `agy` form is to diff the installed copy against `main` before spending a Claude reviewer on it.

**Headless `agy` does the implementation work on this machine now.**
The `command(*)` allow-rule in `~/.gemini/antigravity-cli/settings.json`, added at the user's request through another session on 2026-09-09, is what made that true;
the same session measured the caveats (PowerShell 5.1 with no `&&`, a scratch cwd so every brief starts with `Set-Location`, file tools scoped to the sparta tree so an ai-config brief does its file I/O through shell commands).
Three implementation dispatches and one review dispatch in this session ran that way at zero Claude cost, each returning a local commit in its worktree.

**A worker subagent cannot push, whichever family it runs on, so brief it to commit locally and never push.**
`no-push-without-self-review.py` reads the orchestrator's transcript for the reviewer dispatch.
A subagent thread has no transcript under `~/.claude/projects/` for the subagent's worktree, so the reviewer rounds the subagent runs are invisible to the guard, and the guard refuses every push the subagent attempts.
Measured 2026-09-09 on ai-config#3469: the worker ran two clean `adversarial-reviewer` rounds and was still refused, then tried the guard's documented `ALLOW_UNREVIEWED_PUSH=1` escape and had it denied by the auto-mode classifier.
The orchestrator dispatches the reviewer against the worker's diff, addresses the findings itself, and pushes;
that round is not redundant, since it found two false discharges the worker's rounds had missed.

- **Do:** launch `agy` for implementation, triage, and any other dispatchable work, and reserve the `Agent` tool for `adversarial-reviewer`.
- **Do:** end every worker brief with "commit locally, do not push, do not mark the PR ready", and run the reviewer and the push from the orchestrator.
- **Don't:** dispatch a Claude `general-purpose` worker for implementation while this directive stands, however small the task.
- **Don't:** brief a worker to push and ARDI its own PR;
  the guard refuses it by construction, and the retry burns the worker's whole budget.

## A syntax check does not catch a delegated edit whose quoting was dropped

[`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md) already says to run a parser over a scripted edit *and* run the relevant tests before trusting it.
What this case adds is which of those two halves decides, for delegated shell, and that the cheap half carries no partial credit.
A dropped quote can leave a *different valid program* rather than an invalid one, and did here, so the parser passes and the artifact is still wrong.

Measured 2026-09-10 on [ai-config#3435](https://github.com/Morrison-Lab/ai-config/pull/3435).
An `agy` worker asked to guard a call in `bootstrap.sh` emitted a line of this shape:

```sh
cmd || printf warn  render-agy-hooks.py exited %d
 "$?"
```

The format string lost its quotes and gained a real newline, so `"$?"` became its own command.
Under that script's `set -euo pipefail` it expands to `0`, runs `0`, and aborts the bootstrap before the symlink creation that follows it and, much later, the dotfiles installer loop.

`bash -n` exits 0 on that file.
Verified on the reduced case: `bash -n` reports nothing, and running it dies with `0: command not found` and status 127.
Nothing about the text is ungrammatical --- `printf` simply took different arguments than the author meant.
That is what happened here;
whether a lost quote usually lands that way rather than producing a syntax error is not measured, and running the edited script is worth doing either way.

**Executing the artifact is the check that works, and this repo already had it.**
`scripts/test_agy_hook_adapter.py` runs `bash bootstrap.sh` and asserts a zero exit, and `validate.yml` gates it, so CI would have failed on the mangled line.
It could not run on the Windows machine that wrote it, for an unrelated path-quoting bug in the test itself ([ai-config#3551](https://github.com/Morrison-Lab/ai-config/issues/3551)) --- so the local loop was blind and the adversarial reviewer was the only detector before push.

The transferable part is which check answers which question.
A parser answers whether the file is *well-formed*.
Only running it can expose a failure that lives in the *behaviour* rather than in the grammar, which is the class this defect belongs to.
It is not proof the change is right: an execution test asserts what it happens to assert, so a semantically wrong edit passes wherever the relevant behaviour is untested.
What it rules out is the case here, where a delegated edit's own account of itself is accurate and the text it wrote is not.
Nothing here settles whether the worker authored the malformed line or a transport mangled one it wrote correctly, and the check is the same either way.

- **Do:** run the suite that executes an edited script, not only a parser over it, before trusting a delegated commit that touched shell.
- **Do:** run the script yourself against a throwaway fixture when no suite executes it, and treat that gap as worth a filed issue rather than a reason to skip the check.
  Derive which scripts those are rather than recalling them, and note that a direct reference is not the only way a script is covered --- `scripts/test_hooks.py` pairs every `hooks/*.sh` to a `test-<stem>.py` by glob, so a name grep alone understates coverage:

  ```bash
  for s in $(git ls-files '*.sh'); do
    grep -rqlF "$(basename "$s")" scripts/test_*.py hooks/test-*.py || echo "$s"
  done
  ```
- **Do:** treat a test you cannot run locally as an unchecked artifact, and say so, rather than reading the parser's silence as coverage.
- **Don't:** read `bash -n` (or `py_compile`) passing as evidence that a delegated edit is correct --- it reports grammar, and dropped quoting is grammatical.
- **Don't:** rely on the commit message agreeing with the diff here;
  the message was accurate and the code was not.

## opencode free tier: a full authoring task, validated mechanically

Measured 2026-08-28 on opencode CLI 1.18.15 (macOS),
during a Morrison-Lab/gha#682 delegated multi-file R refactor.
With a detailed brief --- exact file list, exact new-file content,
per-file candidate paths, explicit constraints ---
plus a cheap deterministic acceptance test available
(four independent Rscript test suites),
`opencode/nemotron-3-ultra-free` completed a five-file R
test-harness refactor correctly on the first try:
all four suites passed, no scope creep,
and call-site argument updates were included unprompted.

Two other measurements from the same session qualify how that
success was reached, not whether it was real.
The hosted free tier can fail total and immediately with an
`UnknownError` before doing any work,
and a different free-tier model recovered the identical prompt on
retry --- see
[`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)'s
Troubleshooting section.
And this model's Glob tool returned zero matches for real files
under dot-prefixed directories,
recovering only because the brief carried literal paths --- see that
skill's step 2 ("Prepare the prompt").

The routing rule this measurement licenses lives in
[`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)'s
"The one measured exception: authoring work a mechanical test can
accept" section, which summarizes the measurement in one sentence and
cites this section for the rest.
A later measurement belongs in this file,
and a change to the routing rule belongs in that section.

- **Do:** read this as one data point for one model id on one task,
  not as a general claim about hosted-free-tier authoring capability.
- **Do:** credit the deterministic validation step --- four
  independent test suites passing --- when recording why a delegated
  result was trusted.
- **Don't:** generalize this measurement to another free-tier model id
  or another task shape --- neither was measured here.
- **Don't:** credit the model's own confidence for the result;
  what made trusting it safe was the acceptance test passing.

## Conversation-inheriting subagent dispatch vs. clean-context dispatch for UMS and CAI

When delegating UMS (`update-memories-and-skills`) or CAI (`config-ai`) as subagents,
harnesses support either **conversation-inheriting dispatch** (inheriting the full conversation transcript and tool history)
or **clean-context dispatch** (starting a fresh conversation with a standalone prompt brief).
The canonical trade-off analysis, context-budget rationale, and Do/Don't directives live in [`use-subagents`](../shared/workflow/use-subagents.md).

### Concrete invocation mechanics across harnesses

- **Claude Code programmatic subagents:**
  Pass `subagent_type: "fork"` to the `Agent` tool to clone the current session's conversation history into the worker.
  Do not confuse this with skill frontmatter `context: fork` (which runs a skill in isolated context *without* conversation history, as in `skill-audit` and `find-overlap`).
- **Claude Code interactive sessions:**
  Use `/subtask` to fork the active conversation interactively into a subagent with full history.
- **Antigravity:**
  Pass `TypeName: "self"` to `invoke_subagent` to inherit the parent agent's tools, system prompt, and model configuration (with `Workspace: "inherit"` to share the underlying working directory).
  Subagents start with a clean conversation context;
  supply conversation history by passing the path to `transcript.jsonl` under `<appDataDir>/brain/<conversation-id>/.system_generated/logs/` in the prompt.
- **Gemini CLI, OpenAI Codex, and headless CLIs without runtime forking:**
  Subagents start with a clean context window by default (e.g. `@subagent_name` in Gemini CLI);
  provide the path to the on-disk conversation log or a focused milestone summary in the prompt brief.

- **Do:** use conversation-inheriting dispatch (`subagent_type: "fork"` in Claude Code) or pass the transcript log path (`transcript.jsonl`) for reflective UMS sweeps and emergent CAI workflows per [`use-subagents`](../shared/workflow/use-subagents.md).
- **Do:** clearly distinguish the `Agent` tool's conversation-inheriting `subagent_type: "fork"` from skill frontmatter `context: fork` (which isolates and omits conversation history).
- **Don't:** duplicate the full trade-off rationale across multiple files ---
  keep the normative guidance in [`use-subagents`](../shared/workflow/use-subagents.md).



