# Cursor hook mapping

Claude Code loads enforcement guards from [`hooks/hooks.json`](../hooks/hooks.json).
Cursor Cloud does not.
It loads [`.cursor/hooks.json`](../.cursor/hooks.json), which must use Cursor's native schema (`version: 1`).

Pointing the Cursor plugin `hooks` field at the Claude file would feed a foreign schema.
That is [ai-config#1934](https://github.com/Morrison-Lab/ai-config/issues/1934), out of #1927 by design.

[`.cursor/hooks/adapt-claude-hooks.py`](../.cursor/hooks/adapt-claude-hooks.py) is the Cursor-schema command.
It translates Cursor stdin into the payload the existing `hooks/` scripts already consume, then translates their stdout back.

It does not call `install-hooks.py --fix`, so it cannot double-bind the Claude plugin path.

## Event mapping

| Claude Code event | Cursor event | Cloud agent | Notes |
|---|---|---|---|
| `PreToolUse` | `preToolUse` | yes | Covers Shell (Claude `Bash`), Task/Agent, and MCP tools. Matcher translation lives in the adapter. |
| `Stop` | `stop` | yes | Claude `decision: block` becomes Cursor `followup_message`. The message has already gone out; Cursor cannot suppress it the way Claude Stop can. `loop_limit` is `5` (Cursor's default) so a block can retry a few times without an unbounded follow-up loop. The adapter is one Cursor `stop` command, so several catalog scripts that fire in the same event share one `followup_message` and one loop-count increment. Warn-only Stop hooks (`systemMessage` without `decision`) also map to `followup_message`: Cursor's `stop` schema has no warn-only field, so a warning continues the turn up to `loop_limit` rather than going silent on stderr. The adapter rewrites a Cursor JSONL (`role` + `Shell`) into the Claude shape (`type` + `Bash`) before the catalog reads it. Cursor transcripts omit tool *results* (Cursor staff, 2026-04-13; re-verify on a harness bump), so scripts that fail closed without a `tool_result` (`no-push-without-self-review.py`, `no-unreviewed-pr.py`, `no-unmonitored-pr.py`) are skipped rather than locking out every push or looping Stop (tracked as [#2241](https://github.com/Morrison-Lab/ai-config/issues/2241): stash `postToolUse.tool_output` and unskip). `no-empty-promise.py` still runs: it discharges on a mechanism `tool_use` even without a result. |
| `UserPromptSubmit` | `sessionStart` | no | Cursor `sessionStart` can inject `additional_context`. Cloud agents do not load `sessionStart`. |
| `UserPromptSubmit` | `postToolUse` | yes | First `postToolUse` of a generation emits the same stdout / `additionalContext` the Claude UPS path would have added before the turn, as Cursor `additional_context`. Whether that field reaches the model is version-dependent: desktop through 3.7.x accepted and discarded it ([forum 155689](https://forum.cursor.com/t/155689), still broken on 3.7.36 as of 2026-06-15); Cursor claimed a desktop fix for 3.9.8+ on 2026-06-29 ([forum 158168](https://forum.cursor.com/t/158168)); Cloud consumption is unmeasured as of 2026-08-25. A cloud turn that never calls a tool never fires `postToolUse`, so UPS context is dropped, not delayed. On desktop, `sessionStart` already injects at session open; the first `postToolUse` of that conversation does not emit again, later generations still do. `inject-local-time.sh` therefore *emits* after the first tool when there is one, and not at all on a tool-less cloud turn. |
| `UserPromptSubmit` | `beforeSubmitPrompt` | yes, but unused | Cursor `beforeSubmitPrompt` can only `continue` / block. It cannot inject context. No UPS hook here currently blocks, so this event is unbound. |
| `PreToolUse` matcher `SendMessage` | (none) | n/a | `remind-brief-premises.py` also binds `Agent` and `Task`, which Cursor maps. The SendMessage-only slice has no analog. |
| `PreToolUse` MCP | `preToolUse` (`MCP:` prefix) | yes | Cursor Cloud does not load `beforeMCPExecution` / `afterMCPExecution`. `preToolUse` is the cloud path. |
| `SessionStart` / `SessionEnd` / `PreCompact` | unused | mixed | This catalog does not register those Claude events. |

A per-payload tick sentinel collapses two adapter processes of the same
Cursor event. The waiter uses the wrapper timeout minus slack so it can
emit JSON before Cursor SIGKILLs the command. An overlapping first
process that crashes still yields empty JSON, and Cursor fail-opens
`preToolUse` in that latent case (no second Cursor-schema source is
bound today).

The adapter parses leading `KEY=VALUE` tokens from each catalog `command`
(the Stop registration of `no-mistake-without-a-hook.py` needs
`AI_CONFIG_STOP=1`) and runs each script with a remaining-time budget so
Cursor does not SIGKILL the wrapper mid-catalog.
A catalog script that times out or cannot exec fails closed on
`preToolUse` / `stop` (exit 2).
UserPromptSubmit / `postToolUse` injection ignores that status: a missing
or hung UPS script is a silent drop, not a deny.
The wrapper itself still fail-opens: `.cursor/hooks.json` does not set
`failClosed`, because an adapter crash would otherwise deny every tool.
`main()` dispatches through `HANDLERS`, and every `EVENT_MAPPING` value must be a `HANDLERS` key.
`scripts/test_cursor_hook_adapter.py` asserts every Claude event in `hooks/hooks.json` appears there.

## Tool-name mapping

| Cursor `tool_name` | Claude `tool_name` values the adapter tries |
|---|---|
| `Shell` | `Bash` |
| `Task` | `Task`, and `Agent` unless `subagent_type` is `explore` / `plan` / `shell` (top-level or in `tool_input`) |
| `StrReplace` | `Edit` (transcript translation so Stop guards see a write) |
| `EditNotebook` | `NotebookEdit` |
| `MCP:github-<id>` | `mcp__github__<id>` plus the raw suffix |
| other `MCP:<id>` | `mcp__<id>` with hyphens folded to underscores |

Warn-only `PreToolUse` output (`additionalContext` / `systemMessage` without a deny) is stashed and replayed as `postToolUse.additional_context` for that `tool_use_id`.
Cursor `preToolUse` has no injection field on an allow.

## What this file is not

It is not a second catalog.
New guards still land in `hooks/` with a `hooks/hooks.json` row, a README row, and a `test-<name>.py`.
The adapter reads that catalog.
Do not add a parallel list of script names here.

## Activation

Project hooks in [`.cursor/hooks.json`](../.cursor/hooks.json) load for this repo, including Cursor Cloud agents once the file is on the branch they boot from.
User-level `~/.cursor/hooks.json` is not available in cloud agents.

Do not also run `install-hooks.py --fix` to "activate" these for Cursor.
That path writes `~/.claude/settings.json` for Claude Code.
Cursor Cloud can still have `~/.claude/settings.json`
(measured 2026-08-26 PDT on this VM,
whose primary checkout is ai-config).
That measurement does not say how this VM's copy got there,
or whether Claude Code's native hook runner also fires on Cloud
(unmeasured as of 2026-08-26 PDT).
Those settings do not make the Cursor adapter run Claude's hook runner.
Desktop Cursor with third-party Claude hooks enabled loads that file natively
and runs every source ([third-party hooks](https://cursor.com/docs/reference/third-party-hooks.md), fetched 2026-08-25);
the adapter's tick sentinel does not collapse adapter-plus-native.
On a desktop session, leave one path enabled:
this project file, or Claude settings, not both.
On Cursor Cloud, that file can already exist
(see the measurement above),
and whether the native runner also fires is unmeasured
as of 2026-08-26 PDT.
Until both are measured, do not treat
both-present as a Cloud defect to clear by deleting settings.
A native deny of the unprefixed push is still the
observable that the native runner fired.
