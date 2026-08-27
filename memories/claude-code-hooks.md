# Claude Code hooks: manifest, registration, and install failures

How this repo's hooks reach a machine and how that goes wrong --- the native `hooks/hooks.json` schema, the split between `install-hooks.py` (which binds) and the plugin loader or a manual copy (which places), and the two routes to a registered hook whose script is absent, one of which takes the whole `Bash` tool down.
`check-install.py`, this file's original placement instrument, was removed along with the symlink install it verified.
[ai-config#2352](https://github.com/Morrison-Lab/ai-config/issues/2352) tracks a replacement, so read every reference to it below as historical.

Split out of [`claude-code.md`](claude-code.md), which had reached the
1200-line advisory threshold; the harness behaviour that is not about hooks
stays there.

## Plugin hooks ship in a native `hooks/hooks.json`, NOT the `install-hooks.py` array format

A marketplace plugin auto-loads hooks from `hooks/hooks.json` at the plugin
root, but that file must be the **native** plugin-hooks schema, which is a
different shape from ai-config's bespoke `install-hooks.py` manifest:

- Native: `{"hooks": {"<Event>": [ {"matcher"?: "...", "hooks": [ {"type":
  "command", "command": "...", "timeout"?: N} ]} ]}}`.
  `hooks` is an **object keyed by event**, and commands use
  `${CLAUDE_PLUGIN_ROOT}`.
- Bespoke (install-hooks.py): `{"hooks": [ {"script", "event", "matcher"?,
  ...} ]}`.
  `hooks` is a flat **array**.

Feed the loader the array form and it silently ships zero hooks.
`claude plugin validate` prints
`x hooks: Invalid input: expected record, received array` and fails, and at
runtime the debug log carries `[ERROR] Failed to load hooks ... error type:
hook-load-failed`.
The failure is isolated: skills still load and the session does not crash, so a
plugin can carry broken hooks indefinitely without any visible symptom.

**Extra keys are tolerated.**
The native schema ignores unknown keys, verified with `claude plugin validate`,
so metadata can live co-located on each hook entry (`script`, `why`, doc
`_note` arrays) plus a top-level `_comment`.
That lets one file serve both the plugin loader and `install-hooks.py`, which
reads the same file and keys off the preserved `script` to build its own
`~/.claude/settings.json` command.

**Activation differs by path.**
The plugin loads its hooks whenever the plugin is *enabled*, so merging a hook
entry activates it for every plugin-enabled consumer.
The `install-hooks.py --fix` path into `~/.claude/settings.json` stays a
separate per-machine opt-in.
The two paths are **mutually exclusive on one machine** -- enable the plugin,
or run `install-hooks.py --fix`, not both.
Claude Code does not dedup a hook across them, because their command strings
differ (`${CLAUDE_PLUGIN_ROOT}/hooks/<script>` vs `$HOME/.claude/hooks/<script>`),
so registering both fires every hook twice, and a `Stop` guard's fire-once
`/tmp` sentinel (`exists()`-then-`open()`) then races between the two copies.

### Testing plugin hooks locally, without publishing to a marketplace

- **Schema:** `claude plugin validate <plugin-dir>` deep-checks
  `hooks/hooks.json`.
  It needs `.claude-plugin/plugin.json` present; a `marketplace.json` is not
  required, so point it at a single-plugin dir.
- **Firing:** `echo "<prompt>" | claude -p --plugin-dir <dir> --debug-file
  <log>`.
  A `UserPromptSubmit` hook that injects a sentinel line proves it fired; grep
  the debug log for `Read hooks.json for plugin <name>` and confirm
  `hook-load-failed` is absent.
- **Gotcha:** `claude --debug [filter]` takes an optional positional filter, so
  `claude --debug -p "prompt"` mis-parses the prompt as the filter.
  Pass the prompt on **stdin** and capture the log with `--debug-file <path>`.

(Morrison-Lab/ai-config discussion #1123 / PR #1125, 2026-08-04: ai-config's
plugin had shipped its hooks in the install-hooks array format ever since they
were added, so `claude plugin validate` failed and the plugin loaded zero
hooks -- the skills half of the plugin worked the whole time, which is why it
went unnoticed.
PR #1125 converts the file to native schema, keeping the metadata as extra
keys, and reduces `install-hooks.py` to flattening the native structure back
into the entry list it already consumed.)

## A registered hook whose file is MISSING blocks EVERY call it matches, not just its target action

The double-registration case above is about a hook that fires twice.
This is the opposite failure of the same `settings.json` machinery: a hook that cannot fire at all, because the file it points at is gone.

`install-hooks.py --fix` writes a `PreToolUse` command into `~/.claude/settings.json` of the form `python3 $HOME/.claude/hooks/<script>.py`.
If the repo later removes or renames that script, the settings.json line keeps pointing at a path that no longer exists.
`python3` cannot open the file, so it exits with **code 2**: the `can't open file '.../hooks/<script>.py': [Errno 2] No such file or directory` startup error always exits `2` (verified).
That matters because exit code 2 is specifically Claude Code's block signal, not a generic non-zero exit --- [`claude-code.md`](claude-code.md)'s "A `PreToolUse` hook denies on stdout and still exits 0" section records that "Exiting 2 is a genuine blocking mechanism in Claude Code", documented in [`permission-check`](../skills/permission-check/SKILL.md).
An ordinary crash *inside* a hook that has already started exits `1`, which that same section marks `# a bug, not a block`, and does not stop Bash.
So the missing file blocks every Bash call not because any hook crash blocks, but because `python3`'s missing-file startup failure happens to exit with `2`, the one code that does.

The scope is the surprising part.
A `PreToolUse` `Bash` matcher runs on *every* Bash call, so a merge-guard hook whose file is missing blocks all Bash, not merely a `git merge`.
Nothing else runs either, since the session cannot execute a single shell command until the stale reference is cleared.

Diagnose with `Read` alone, because `Bash` is down:

- Read `~/.claude/settings.json` and find the `PreToolUse` command whose script path is the one named in the error.
- Read the `~/.claude/hooks/` directory to confirm it holds other hook files but not the referenced one.
- Read the checkout's `hooks/hooks.json` to confirm the hook is absent from the current set, so the settings.json entry is stale rather than the checkout being incomplete.

An enabled `ai-config` plugin makes this likelier, not less likely.
The plugin and `install-hooks.py --fix` are mutually exclusive on one machine (per the section above), so running both leaves settings.json carrying a reference the plugin's own `hooks.json` may no longer include.

**The fix can be classifier-denied, so surface it rather than working around it.**
Editing `~/.claude/settings.json` to drop the stale line is a hooks-config change, which Claude Code's auto-mode classifier can DENY.
When it does, STOP and ask the user to make the edit, rather than routing around the denial.
Two immediate unblock alternatives exist, if the user prefers: the user removes the stale line themselves, or someone recreates a no-op pass-through file at the referenced path so `python3` finds something to run.
Prefer restoring the file for an *immediate* unblock.
The hook *command* re-runs on every call, so a restored file unblocks at once, whereas a settings.json edit may not take effect until a Claude Code restart, because hooks load at session start.

- **Do:** read a non-zero `python3: can't open file` error on every Bash call as a registered hook whose file is missing.
- **Do:** diagnose with Read (settings.json, the hooks dir, the checkout's `hooks/hooks.json`) while Bash is blocked.
- **Do:** surface the settings.json edit to the user when the classifier denies it, and name the restart caveat and the restore-the-file alternative.
- **Don't:** read "a merge guard blocked my command" as meaning only merges are blocked --- a missing `PreToolUse` `Bash` hook blocks every Bash call.
- **Don't:** work around a classifier-denied hooks-config edit yourself.

(2026-08-05, Morrison-Lab/ai-config: `~/.claude/settings.json` referenced a removed `no-unauthorized-merge.py` hook, so every Bash call failed with `python3: can't open file '.../hooks/no-unauthorized-merge.py'`.
The hook was absent from `main`'s `hooks/hooks.json` (which #1157 has since added, merged 2026-08-06), the `ai-config` plugin was also enabled, so the same hooks were double-registered, and the settings.json edit to remove the stale line was classifier-denied, so it was surfaced to the user.)

### The same block arrives by a second route, and there `install-hooks.py --fix` is the proximate cause

The section above reaches that state by **drift**: the registration was valid when written, and the repo later removed or renamed the script out from under it.
The second route needs no drift and no elapsed time at all.
The script was **never** at the target path, and `--fix` registered it anyway, in the same command that broke the shell.

That inverts where to look.
Drift invites reading the settings.json line as a leftover from some earlier state, so the diagnosis is archaeological.
Here there is no earlier state: the entry is seconds old, and the tool that wrote it is the last thing you ran.

**The two halves of "arm these hooks" live in different scripts, and each does only its half.**
`install-hooks.py` writes `~/.claude/settings.json` and never places a file --- its own docstring says `bootstrap.sh` "gets the *scripts* onto the machine and stops there", and that `check-install.py` "is the sibling for the other half: it decides whether the installed *files* match the repo, and knows nothing about `settings.json`."
`check-install.py --fix` is what places them, repairing its `missing` status,
which its docstring defines as a path the repo ships and the consumer directory does not have.
So running only `install-hooks.py --fix` on a machine whose `~/.claude/hooks/` lacks the scripts does the binding half and skips the placement half, which is strictly worse than doing neither: an unregistered guard is inert, while a registered-but-absent one is an active `PreToolUse` failure.

**The script already computes the fact that would have stopped it, on a branch it does not reach.**
`classify()` returns `stale` when a settings.json entry names a script missing from the hooks dir --- `if not (hooks_dir / entry["script"]).exists()`.
`--fix` then refuses to touch a `stale` row, printing that it is left alone and that the install is what needs fixing rather than settings.json.
That existence test runs only after `find_entry` has already found the entry.
A hook classified `missing` (declared in the manifest, absent from settings.json) is registered with no existence check at all, so `--fix` manufactures precisely the `stale` state the same run would have refused to write.

**The warning exists and `--fix` does not print it.**
The note naming the division of labour is inside the `if not args.fix:` branch (wording as of the ai-config#2229 rewrite):

```
Note --fix only edits settings.json and never places the scripts themselves. On a fresh machine, install the Claude Code plugin instead (it registers the full catalog with no separate step); this path only helps if ~/.claude/hooks already holds the scripts some other way.
```

A plain run prints it; the `--fix` run that causes the damage does not.
So the operator sees it one command before it matters and never at the moment it applies.

**`--fix` registers everything missing, not the hooks you had in mind.**
It walks the whole manifest, so a hook merged days earlier and never registered rides along with the two you just merged.

**Recovery: `/reload-plugins` places the symlinks, and is better than the alternatives above.**
The parent section prefers restoring the file to a settings.json edit, and is right, but hand-creating a no-op pass-through is not the way to do it when the scripts exist in the checkout.
`/reload-plugins` re-runs the install and links every declared hook at once, so all the broken entries become valid together rather than one path at a time.
It also needs no Bash, which matters because Bash is exactly what is down.
Confirm it worked by reading `~/.claude/hooks/` and seeing symlinks into the checkout, timestamped at the reload.
That confirms the link is **placed**, and not that the guard behind it is current: a symlink resolves through the checkout's working tree, so it serves whatever branch that checkout has out.
`CLAUDE.md`'s "Keep ai-config and repo checkouts fresh" carries that case, including why `check-install.py` cannot report it.

The transferable half is not about hooks.
**A tool that succeeds at its own narrow job can leave the system worse than before it ran, and its success message reports the narrow job.**
`--fix` did exactly what it promised and said so.
The operation the operator wanted was composite, it needs two tools, and half of it is worse than none.
That is [`fail-fast`](../shared/principles/fail-fast.md)'s "partial is worse than absent" one layer out: there the guard is partially *written*, here the guard is complete, correct, and partially *installed*.

- **Do:** confirm `~/.claude/hooks/<script>` exists before running `install-hooks.py --fix` for it --- there is no automated placement instrument for this any more (see the top of this file), so verify by hand or use the Claude Code plugin path instead, which places and binds together. (Inferred from the incident, not given as a user directive.)
- **Do:** read a tool's success line as covering that tool's own scope, and name the other half of a composite operation yourself.
- **Do:** reach for `/reload-plugins` when registered hooks point at absent scripts that do exist in the checkout.
- **Don't:** run `install-hooks.py --fix` as the whole of "arm these hooks" --- it binds, it never places.
- **Don't:** expect `--fix` to warn you about this.
  It prints that note only when run *without* `--fix`.
- **Don't:** read a `PreToolUse` breakage minutes after a `--fix` as drift from an earlier state --- check whether the entry is one you just wrote.

(2026-08-05 ~23:24 PDT / 2026-08-06 06:24Z, `the repository owner`'s machine, the same `settings.json` as the incident above.
`install-hooks.py --fix` registered three hooks --- `remind-deserialize-before-binary-claim.py`, `remind-both-sides-from-git.py`, and `no-unauthorized-merge.py` --- none of which were in `~/.claude/hooks/`.
The third is `PreToolUse` on `Bash`, so every subsequent Bash call died.
All three were legitimately on `main` by then: `no-unauthorized-merge.py` from #1157 (merged 00:45:42Z), `remind-both-sides-from-git.py` from #1186 (03:37:06Z), and `remind-deserialize-before-binary-claim.py` from #1181 (06:18:11Z, six minutes before the incident) --- so only two were the newly-merged pair the operator had in mind, and the third rode along.
The settings.json repair was classifier-denied, correctly: dropping a `no-unauthorized-merge.py` entry from a Bash matcher is indistinguishable from disabling a merge guard.
With Bash also down there was no scripted way out, so the natural repair and the scripted repair were blocked at once.
The user ran `/reload-plugins`.
`ls -la ~/.claude/hooks` then showed all three as symlinks into the repo, timestamped at the reload.
No user correction was given --- the finding is inferred from the incident.
Verified against the scripts rather than recalled: the docstrings quoted above, `classify()`'s existence test, and the note's placement inside the non-`--fix` branch.)

2nd occurrence, 2026-08-26, Morrison-Lab/ai-config#2292 post-merge on
Cursor Cloud: `install-hooks.py --fix` ran while `check-install.py`
reported 15 missing including `hooks`, writing 47 bindings into a
newly created `~/.claude/settings.json` that pointed at
`$HOME/.claude/hooks/` before that directory existed.
`check-install.py --fix` immediately afterwards placed the 15
symlinks, and a later `install-hooks.py` report was
`registered=47 missing=0 stale=0`.
Cursor Cloud does not load Claude `PreToolUse` hooks, so Bash in that
session did not die; the settings.json was still the
registered-but-absent state the 2026-08-05 incident produced.
The order in the Do bullet above is the recovery as well as the
prevention.

## A hook's deny rejects the WHOLE call, so a compound command's setup segments never run either

The two sections above are about *which calls* a hook blocks.
This is about *how much of one call* a block throws away, and the answer is all of it.

A `PreToolUse` hook decides over `tool_input.command` --- one string, one verdict.
A guard may **match** per segment, and several here deliberately do, but the decision it emits has no per-segment field, so the harness rejects the tool call rather than the offending segment.
Every `cd`, `git checkout -b`, `mkdir`, and `export` earlier in that command is silently absent afterward, and the next command runs against whatever state was actually there.

Measured 2026-08-17 against `no-whole-file-punct-replace.py`, whose docstring states it evaluates "per segment rather than over the whole command".
Fed `cd ... && git checkout -q -b fix/x && python3 -c "<glyph replace>"`, it matched only the third segment and returned:

```
permissionDecision: deny
keys in hookSpecificOutput: ['hookEventName', 'permissionDecision', 'permissionDecisionReason']
```

No segment index, no offset --- so per-segment matching buys a precise *reason*, never a partial execution.

**Nothing downstream reports the missing setup.**
The natural mental model is "the blocked step didn't run", which is true and incomplete.
Re-running only the blocked part under its documented override then operates on the un-switched branch, and a `git commit` there succeeds --- so the first signal can be a remote ruleset rejecting the push, arbitrarily later.

**Distinct from `flag-unchained-branch-switch.py`'s `&&` rule**, which is the closest thing in this corpus and covers the opposite mechanism.
There the shell runs a later command after an earlier one failed, so the granularity is the shell's own control flow and `&&` is the fix.
Here nothing in the call runs at all, so `&&` changes nothing --- the block precedes the shell.

Recovery, when a commit has already landed on the wrong branch and the push is refused:

```bash
git branch <name> <sha>          # save the commit
git reset --hard origin/main     # restore the branch you were actually on
git push -u origin <name>
```

- **Do:** after a hook blocks a compound command, re-verify any state its earlier segments were supposed to establish --- `git branch --show-current`, `pwd` --- before continuing.
- **Do:** re-run the whole corrected command rather than only the segment the hook named, so the setup steps run too.
- **Don't:** read "the blocked step didn't run" as the scope of the block; nothing in that call ran.
- **Don't:** reach for `&&` as the remedy --- that governs a *shell* sequencing hazard, and a hook denial never reaches the shell.

For the built-in **permission-rule matcher's** own segment-by-segment behavior (the mechanism the `&&` remedy above actually governs, and a different one from a hook's whole-string decision) see [`claude-code-permissions.md`](claude-code-permissions.md)'s "The matcher is shell-operator aware".

(2026-08-17, `Morrison-Lab/lab-manual`: one call carried `cd ... && git checkout -q -b fix/benchmarking-non-ascii && python3 - <<'EOF' ... EOF`.
The heredoc was a whole-file punctuation replace, correctly blocked.
Re-running the python part alone under `ALLOW_WHOLE_FILE_PUNCT=1` edited the file and committed --- onto `main`, because the branch had never been created.
Caught by `remote: error: GH013: Repository rule violations found for refs/heads/main`, not by anything local.
Tracked as ai-config#1609.)

## Hook matchers use JavaScript regular expressions, NOT shell globs

Hook matchers in `hooks/hooks.json` containing characters outside `[A-Za-z0-9_\- ,|]` are evaluated as JavaScript regexes (`RegExp.prototype.test()`).

- **Correct syntax:** Use `"mcp__github__.*"` (JavaScript regex syntax) to match all tools from the `mcp__github__` MCP server prefix.
- **Incorrect syntax:** Do not use `"mcp__github__*"` (shell glob syntax), which evaluates as regex matching `mcp__github` followed by 0 or more `_` characters.
- **Catalog validator:** `scripts/check-hook-catalog.py` parses compound matcher entries (e.g. `PreToolUse (Bash, mcp__github__.*)`) using `ROW` regex matcher class `[A-Za-z0-9_.*, -]` and aggregates multiple matcher groups for the same script and event.

## Complete hook lifecycle catalog (27 events)

Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236).
Harness behavior and event definitions evolve across releases;
re-verify against current runtime behavior rather than treating this snapshot as permanent.

The v2.1 hook schema supports 27 distinct lifecycle events:
- **Tool lifecycle:**
  `PreToolUse` (match query: `tool_name`),
  `PostToolUse` (`tool_name`),
  `PostToolUseFailure` (`tool_name`).
- **Prompt & turn lifecycle:**
  `UserPromptSubmit`,
  `Stop`,
  `StopFailure` (`error`).
- **Session & environment:**
  `SessionStart` (match query: `source`),
  `SessionEnd` (`reason`),
  `Setup` (`trigger`),
  `ConfigChange` (`source`),
  `InstructionsLoaded` (`load_reason`),
  `CwdChanged`,
  `FileChanged` (`basename(file_path)`),
  `WorktreeCreate`,
  `WorktreeRemove`.
- **Subagents & tasks:**
  `SubagentStart` (`agent_type`),
  `SubagentStop` (`agent_type`),
  `TeammateIdle`,
  `TaskCreated`,
  `TaskCompleted`.
- **Compaction:**
  `PreCompact` (`trigger`),
  `PostCompact` (`trigger`).
- **Permissions & MCP:**
  `PermissionRequest` (`tool_name`),
  `PermissionDenied` (`tool_name`),
  `Elicitation` (`mcp_server_name`),
  `ElicitationResult` (`mcp_server_name`),
  `Notification` (`notification_type`).

## Advanced hook capabilities in the native schema

Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236):

- **In-process pre-filtering (`if: "..."`)**:
  Hooks can declare `"if": "Bash(git *)"` or `"if": "Read(*.ts)"` to evaluate permission expressions in-process,
  bypassing process spawning overhead when conditions are not met.
- **Input mutation (`updatedInput`)**:
  `PreToolUse` and `PermissionRequest` hooks can return `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {...}}}` to rewrite tool arguments dynamically before execution.
- **MCP output rewrite (`updatedMCPToolOutput`)**:
  `PostToolUse` hooks can rewrite results returned from MCP tools.
- **Dynamic environment exports (`CLAUDE_ENV_FILE`)**:
  Bash hooks matching `SessionStart`, `Setup`, `CwdChanged`, and `FileChanged` receive a path in `$CLAUDE_ENV_FILE`.
  Environment variables exported to this file are sourced into subsequent Bash sessions.
- **Prompt elicitation protocol**:
  A command hook can output `{"prompt": "<id>", "message": "...", "options": [...]}` to prompt the user interactively,
  receiving `{"prompt_response": "<id>", "selected": "..."}` back on stdin.
- **`asyncRewake` execution**:
  Background hooks can run asynchronously and wake the model only if exit code 2 (blocking error) occurs.
