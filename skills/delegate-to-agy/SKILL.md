---
name: delegate-to-agy
description: "Delegate sidecar task to the Antigravity agy CLI."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# delegate-to-agy --- run sidecar work on the Antigravity subscription, not Claude

Standing rule: for bounded read-and-answer work, spend the Antigravity subscription through the **`agy` CLI** before Claude budget.
Claude stays the orchestrator: it writes the briefs, checks the outputs and integrates them, and it is the fallback for anything `agy` cannot finish.
This skill is the mechanism.
The flag traps, the permission findings and the install notes live in `memories/delegation.md`.

The subscription-only rule applies (Ezra, 2026-10-13): `agy` here means the CLI signed in with the Antigravity app's login.
Never route work through a Gemini, OpenAI or Anthropic API key.

For reviews and plain briefs, `scripts/agy-dispatch.py` runs steps 3 and 4 below with the checks built in;
the routing table is in [`route-to-agy`](../../shared/workflow/route-to-agy.md).

## Where it runs

`agy` authenticates with the login the Antigravity app stored on the machine, and it has no documented headless token (none found as of 2026-10-13).
So it works only on a machine where Antigravity is signed in.

| Session | Can use `agy`? |
|---|---|
| Local Claude Code on Ezra's Linux box | Expected to work, but unmeasured: the Linux measurement in `memories/delegation.md` ("agy on Linux") was a Remote Control session. |
| Remote Control session on that box | Yes, measured 2026-10-13. It is his default device. |
| Cloud session (claude.ai/code, GitHub Actions) | No. `AGENTS.md` records a cloud session as having no `agy`. |

From a cloud session, ask Ezra to start a Remote Control session on the Linux box and run the dispatch there, or fall back to OpenCode Go (`delegate-to-opencode`).
Do not look for a token, paste a credential, or switch to an API key to get around this.
This skill is scoped to the Linux and macOS behaviour recorded in the memory.
For Windows, read its "agy on Windows" section first, since the shell and command-line limits differ.

## When this fires

- "delegate to agy", "use agy", "use Antigravity", "offload to agy", "dta".
- Before a bounded audit, draft or second-opinion pass that would otherwise spend Claude tokens, when the session is on a machine with `agy`.

## When NOT to delegate

- A focused authoring or judgment task that needs Claude's own context.
- The critical-path edit the rest of the work waits on.
- Implementation on a machine whose `~/.gemini/antigravity-cli/settings.json` has no allow-rule for the tools the job needs.
  The standing directive (2026-09-09, "use agy only for subagents;
  no claude subagents except reviewers") sends implementation to `agy`, but it worked on Windows only because the user added a `command(*)` allow-rule there.
  Without a rule, headless `agy` writes nothing and exits 0.
  Check `settings.json` first, and ask Ezra before editing it;
  on a machine with no rule, ask Ezra to add the rule, or send the job to OpenCode Go, and cite the 2026-09-09 directive as the reason.
- Restricted data (PHI, FERPA records): `agy` sends the prompt off the machine.

## Procedure

### 1. Confirm `agy` is available

```bash
command -v agy || ls ~/.local/bin/agy
agy --version
agy models
```

Read the roster from `agy models` itself, never from a remembered list.
If the binary is off `PATH`, search for it before concluding it is absent (`memories/delegation.md`, "agy on Windows").

### 2. Write a self-contained brief

Headless `agy` cannot read repo files or run `git diff` on its own.
Embed the full text of every file the task needs, and for a review embed the diff too, regenerated before every re-dispatch round.
Set `WORK=<scratchpad>/agy-run` and write the brief to `$WORK/prompt.txt` with the Write tool, not a heredoc.
Embed anything from the network yourself.
Keep the brief under about 100 KB.
The prompt travels as one command-line argument, and Linux caps a single argument at 128 KiB (not measured with `agy`).
Split a larger job into several briefs.

### 3. Dispatch headless, in the background

```bash
WORK=<scratchpad>/agy-run
mkdir -p "$WORK"
rm -f "$WORK/DONE"
nohup bash -c 'agy --model <id> --print-timeout 8m --print="$(cat "$0/prompt.txt")" > "$0/out.txt" 2> "$0/err.txt" < /dev/null; touch "$0/DONE"' "$WORK" > /dev/null 2>&1 &
```

Poll for `$WORK/DONE` in a background Bash task, as `delegate-to-codex` does.
A `nohup` launcher returning is not the run finishing.

- Keep the prompt immediately after `--print`, or bind it with `=` as above.
  A flag between `--print` and the prompt becomes the prompt, and the exit status is still 0.
- Redirect stdin from `/dev/null`.

### 4. Verify what came back

- **Exit 0 proves nothing.**
  A denied tool exits 0 with `jetski: no output produced --- a tool required the "<tool>" permission that headless mode cannot prompt for, so it was auto-denied`.
  Read `$WORK/err.txt` and `$WORK/out.txt` for that line, and treat empty output or an `Argument list too long` error as a failure.
  `DONE` appears whether the run succeeded or not.
- A run can also print a "Completed Work Summary" naming files it never wrote.
  Run `git diff` after any dispatch that might have touched the repo.
- Re-derive every number it reports.
  `agy` has miscounted lines while reading correctly.
- Do not edit the allow list or skip permissions on your own to make a run succeed.
  On Linux 1.3.4 a command outside `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` was auto-denied, so the list does gate headless runs.
  Upstream issue #548 reports that some versions ignore that file's `command()` grants, so smoke-test a rule before relying on it.
  The allow list is Ezra's call.
  The memory allows `--dangerously-skip-permissions` only for a fully trusted brief, and this skill never uses it.
  For read-only work, embed the material in the brief instead.

### 5. Posting a cross-harness review to a PR

When posting an `agy` review to a PR under a user or Remote Control session,
always wrap the output in a standardized header and verdict structure:

```markdown
## Cross-harness review (Antigravity agy CLI) of <HEAD_SHA>

Reviewed-Commit: <HEAD_SHA>

<verbatim agy output>

### Verdict

Verdict: <Clean or Needs more work>

_Posted by Antigravity (AI agent) --- not written by a human._
```

This ensures `check-pr-fully-clean.py` admits the review by construction
and allows a clean verdict to supersede any earlier standing not-clean verdicts (#4425).

### Default cross-harness reviewer: Argon

Ezra approved Argon, meaning Gemini through the `agy` CLI, as the default non-Claude reviewer (2026-10-14).
Use it whenever a Claude-authored PR needs a reviewer that differs in model and harness, on a machine where `agy` is signed in.
Dispatch it read-only: pass `--mode plan`, embed the PR diff in the brief, and tell it to use no tools.
Run it from a scratch checkout of the PR head, never one that can push.
Afterward run `git status` and `git diff` in that checkout, since its summaries can claim edits that never happened.
Post the review as a PR comment whose body says an agent (Argon via `agy`) wrote it, and end it with the standard disclosure footer naming the agent that posted it (the footer line above, or "Claude Code" when Claude posts on Argon's behalf).
Ask Argon to list what it checked even when it finds nothing, so a clean verdict is not a single line.
See [`memories/delegation.md`](../../memories/delegation.md) ("Argon is the default cross-harness reviewer") for the first eight-PR run.

### 6. Fall back for failures only

If a run fails, times out or returns nothing, redo only those items on OpenCode Go.
Use a Claude subagent only for a reviewer, per the 2026-09-09 directive.
No memory entry records what `agy` prints when the subscription window is exhausted, so treat an unexplained failure on every item as possible exhaustion, and say so in the report.
If the whole window is exhausted, fall back to Claude in the current session, never to a metered API.

## Relationship to other skills

- [`delegate-to-codex`](../delegate-to-codex/SKILL.md): the same background-and-poll pattern, for the ChatGPT plan (UCDH projects only).
- [`delegate-to-opencode`](../delegate-to-opencode/SKILL.md): the cloud-session destination.
- [`adv`](../adv/SKILL.md): a cross-vendor adversarial review can run through `agy`.
  The pre-push hook accepts a review only as the sole Bash command in the shape `agy --print '<prompt>'` (`memories/delegation.md`, 2026-09-09 section), so this skill's background launcher does not discharge it.
- [`agy-review-workflow`](../agy-review-workflow/SKILL.md): the retired API-dispatch workflow, separate from the CLI route.
  Do not dispatch it.

## Anti-patterns

- ❌ Reading a clean exit as success: check the output for the `jetski` line and for empty output.
- ❌ Pointing headless `agy` at repo paths instead of embedding the text.
- ❌ Looking for a token or API key to use `agy` from a cloud session.
- ❌ Skipping permissions, or granting `command(*)` without Ezra's say-so, to make a run succeed.
- ❌ Putting a flag between `--print` and the prompt.
- ❌ Sending restricted data to `agy`.
