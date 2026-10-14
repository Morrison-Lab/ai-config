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

Standing rule: for heavy, parallelizable read, draft and verify work, spend the Antigravity subscription through the **`agy` CLI** before Claude budget.
Claude stays the orchestrator: it writes the briefs, checks the outputs and integrates them, and it is the fallback for anything `agy` cannot finish.
This skill is the mechanism.
The preference, the flag traps and the Windows install notes live in `memories/delegation.md`.

The subscription-only rule applies (Ezra, 2026-10-13): `agy` here means the CLI signed in with the Antigravity app's login.
Never route work through a Gemini, OpenAI or Anthropic API key.

## Where it runs

`agy` authenticates with the login the Antigravity app stored on the machine, and it has no documented headless token.
So it works only on a machine where Antigravity is signed in:

| Session | Can use `agy`? |
|---|---|
| Local Claude Code on Ezra's Linux box (`cf463-02`) | Yes. `agy` 1.3.4 is on `PATH`, logged in (measured 2026-10-13). |
| Remote Control session on that box | Yes. It is his default device. |
| Cloud session (claude.ai/code, GitHub Actions) | No. It has no Antigravity login, and its proxy injects no credential for it. |

From a cloud session, ask Ezra to start a Remote Control session on the Linux box and run the dispatch there, or fall back to OpenCode Go (`delegate-to-opencode`).
Do not look for a token, paste a credential, or switch to an API key to get around this.

## When this fires

- "delegate to agy", "use agy", "use Antigravity", "offload to agy", "dta".
- Before a heavy read, audit or draft fan-out that would otherwise spend Claude tokens, when the session is on a machine with `agy`.
- A cross-vendor second opinion on a diff: point `agy` at Claude's output and ask whether it holds up.

## When NOT to delegate

- A focused authoring or judgment task that needs Claude's own context.
- The critical-path edit the rest of the work waits on.
- Restricted data (PHI, FERPA records): `agy` sends the prompt off the machine.
- Anything that must write files, unless you will read `git diff` afterwards (see step 4).

## Procedure

### 1. Confirm `agy` is available

```bash
command -v agy || ls ~/.local/bin/agy
agy --version
agy models
```

Run `agy models` rather than trusting a remembered roster.
At the 2026-10-13 measurement it listed 13 models, including Gemini, Claude Opus and Sonnet, and GPT-OSS 120B.
If the binary is off `PATH`, search for it before concluding it is absent (`memories/delegation.md`, "agy on Windows").

### 2. Write the brief to a file

Write the prompt to a scratchpad file with the Write tool, not a heredoc.
Embed anything from the network in the brief yourself.
Say which tools the run may use: headless runs cannot answer a permission prompt.

### 3. Dispatch headless

```bash
agy --model <id> --print-timeout 8m --print="$(cat "$WORK/prompt.txt")" > "$WORK/out.txt" 2> "$WORK/err.txt" < /dev/null
```

- Keep the prompt immediately after `--print`, or bind it with `=` as above.
  A flag between `--print` and the prompt becomes the prompt, and the exit status is still 0.
- Redirect stdin from `/dev/null`.
- Run anything longer than a minute in the background and poll a DONE marker, as `delegate-to-codex` does.
  A foreground call dies at the tool timeout.

### 4. Verify what came back

- **Exit 0 proves nothing.**
  A run can exit 0 with empty output, or with a summary of edits it never made.
  Read `$WORK/err.txt` and check the output is non-empty.
- **Headless auto-denies any command not in `permissions.allow`** in `~/.gemini/antigravity-cli/settings.json`.
  A denied tool shows up as a named permission error or a thin answer.
  Prefer read-only briefs.
  Widen the allow list only for the repos the dispatch should touch, and never with `--dangerously-skip-permissions`.
- **After any run that was meant to edit files, run `git diff`.**
  Trust the diff, not the summary.
- **Re-derive every number it reports.**
  `agy` has miscounted lines while reading correctly.

### 5. Fall back for failures only

If a run fails, times out or shows a quota error, redo only those items with a Claude subagent or OpenCode Go.
If the whole subscription window is exhausted, fall back to Claude in the current session, never to a metered API.

## Relationship to other skills

- [`delegate-to-codex`](../delegate-to-codex/SKILL.md): the same background-and-poll pattern, for the ChatGPT plan (UCDH projects only).
- [`delegate-to-opencode`](../delegate-to-opencode/SKILL.md): the cloud-session destination.
- [`agy-review-workflow`](../agy-review-workflow/SKILL.md): the retired API-dispatch workflow. Do not use it.
- [`adv`](../adv/SKILL.md): a cross-vendor adversarial review can run through `agy`.

## Anti-patterns

- ❌ Reading a clean exit as success: check the output and `git diff`.
- ❌ Looking for a token or API key to use `agy` from a cloud session.
- ❌ Granting `command(*)` or skipping permissions broadly to make a run succeed.
- ❌ Putting a flag between `--print` and the prompt.
- ❌ Sending restricted data to `agy`.
