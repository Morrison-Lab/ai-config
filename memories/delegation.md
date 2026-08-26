# Delegation ladder

Moved out of `preferences.md` (2026-08-26)
when that file hit the 1200-line cap;
this section is self-contained.

## Delegate heavy work to another CLI first --- codex, agy, and now opencode

> [!IMPORTANT]
> **`agy` (Google Antigravity)'s API-dispatch route is permanently out of
> service** (user directive, 2026-08-20; scope corrected 2026-08-23),
> confirmed via a dispatched run's `429: prepayment credits depleted`.
> Route no API-dispatched subagent work to it.
> **The API and the CLI are two separate paths: the API is out of commission,
> but the agy CLI is available** (user clarification, 2026-08-25),
> so headless `agy --print` invocations
> --- including adversarial review dispatch ---
> remain usable.
> The interactive subscription/extension is unaffected and not at quota ---
> don't extrapolate this into "uninstall the extension".
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
Two of those CLIs are separately-billed plans with usage windows;
the third is free.
Claude stays the orchestrator ---
writes prompts, assembles stages, integrates outputs ---
and is the fallback for any stage the delegate can't finish.
This is a standing default across all sessions,
including ultracode/Workflow fan-outs,
not occasional use.

**Two of these are metered plans, and the rule is to try both before Claude's.
A third, `opencode`, is free and sits outside that window logic entirely.**

| CLI | plan | skill |
|---|---|---|
| `codex` | ChatGPT | [`delegate-to-codex`](../skills/delegate-to-codex/SKILL.md) (alias `dtc`) |
| `agy` (Google Antigravity) | API retired, **CLI available** (2026-08-25) | none --- invoke `agy --print` directly |
| `opencode` | free hosted (opencode Zen) or local (ollama) | [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md) (alias `dto`) |

Headless dispatch: `agy --print="<prompt>" [--effort low]`,
or `agy --print "<prompt>" [--effort low]`.
The `--print` flag consumes the next token as its prompt argument,
so keep the prompt immediately after `--print` (via space or `=`)
and keep other flags outside it.

Dispatching large prompts (a full diff plus context files) hits the Windows
command-line length limit around 32k characters ---
`--print=$big` fails with "filename or extension is too long",
and passing multiline content as a PowerShell argument mangles quoting.
Pipe the brief through stdin instead:
`cmd /c "type brief.txt | agy.exe"`.
Stage the brief file itself as UTF-8 ---
PowerShell's `Out-File` defaults to UTF-16LE,
which Python then cannot read as UTF-8.

A headless reviewer has no tool permissions:
it cannot run `git diff`, so embed the diff **and** the full text of every
file the diff touches directly in the brief.
Missing context produces phantom-reference findings
(the reviewer cannot verify that a cited section exists)
and missed ones (it cannot check claims against their referent).
Regenerate the embedded diff before **every** re-dispatch round ---
a stale brief once produced an entire review round
against content the fix had already changed.

`cursor` was named for the machine inventory by the user
(2026-08-25, CLI installed)
but has no measured headless dispatch mechanics here yet ---
probe before relying on it.

Exhaust the *current usage window* of each metered CLI in turn ---
`codex` first (roughly 5 hours), then `agy` CLI as its own availability allows ---
then fall back to Claude until a window resets.
"Delegate first" means the current window,
not abandoning Claude permanently.

**`opencode` has no window to exhaust,
which changes where it sits rather than just adding a row.**
Its two tiers cost nothing,
so for work a small model can actually do it goes *ahead* of codex and agy
rather than behind them: there is no budget to conserve by skipping it.
Capability is the binding constraint in its place,
and it is unmeasured here ---
the local ids carry parameter counts from 2B to 30B,
and the hosted ids are preview names
nobody has benchmarked against this corpus's work.
The local (`ollama/*`) tier is also the only destination anywhere in this
ladder that *can* keep the payload on the machine,
so it is the one route for work whose data must not leave.
That is a property of the endpoint its provider entry is configured with,
not of the `ollama/` prefix,
which reads the same when the `baseURL` points at a LAN box or a remote
`OLLAMA_HOST`.
So the claim is licensed by the loopback check in that skill's step 1
rather than by the model id,
and the check refuses rather than passing when the config cannot be read.
[`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md) carries the
mechanics and the hosted-versus-local routing rule.
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

Stated 2026-07-02 ("exhaust its tokens before using our own"),
reaffirmed 2026-07-06 ("always use codex first
(until we hit the 5-hour limits) before using up claude quota"),
and widened 2026-08-15 ("in addition to codex, we have agy quota to use;
try using both of those as subagents before exhausting claude quota").
