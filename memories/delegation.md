# Delegation ladder

Moved out of `preferences.md` (2026-08-26)
when that file hit the 1200-line cap;
this section is self-contained.

## Delegate heavy work to another CLI first --- codex, agy, opencode, and openrouter

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
Three of those destinations are separately-billed plans with usage windows
(`codex`, `agy`, and OpenCode's `opencode-go/*` tier);
`opencode`'s free/local tiers cost nothing,
and `openrouter` draws a prepaid balance rather than a window.
Claude stays the orchestrator ---
writes prompts, assembles stages, integrates outputs ---
and is the fallback for any stage the delegate can't finish.
This is a standing default across all sessions,
including ultracode/Workflow fan-outs,
not occasional use.

**Three of these are metered plans, and the rule is to try all three before
Claude's: `codex`, `agy`, and OpenCode's `opencode-go/*` tier.
`opencode`'s free and local tiers sit outside that window logic entirely, and
`openrouter` is a prepaid balance rather than a window at all.**

| CLI / Provider | plan | skill |
|---|---|---|
| `codex` | ChatGPT | [`delegate-to-codex`](../skills/delegate-to-codex/SKILL.md) (alias `dtc`) |
| `agy` (Google Antigravity) | API retired, **CLI available** (2026-08-25) | none --- invoke `agy --print` directly |
| `opencode` | OpenCode Go (`opencode-go/*`, $10/mo windowed) + free hosted (`opencode/*`, opencode Zen) + local (`ollama/*`) | [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md) (alias `dto`) |
| `openrouter` | prepaid credit balance, reached through OpenCode's `openrouter` provider | [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)'s "A third destination" section |

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

**`opencode`'s free and local tiers have no window to exhaust,
which changes where they sit rather than just adding a row.**
Those two tiers cost nothing,
so for work a small model can actually do it goes *ahead* of codex and agy
rather than behind them: there is no budget to conserve by skipping it.
Capability is the binding constraint in its place,
and it is unmeasured here ---
the local ids carry parameter counts from 2B to 30B,
and the hosted ids are preview names
nobody has benchmarked against this corpus's work.
**The discriminator between the free and local tiers is the provider
prefix, not a `-free` id suffix.**
See [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)'s
"Hosted-free versus local: the routing rule" section
for the `opencode models` evidence and exact count.

**A third OpenCode tier, `opencode-go/*`, is a $10/mo windowed
subscription** rather than a free or local one, active and verified
2026-08-25.
It behaves like `codex`'s window --- exhaust it before falling back ---
not like the free/local tiers above.

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
work the free/local tiers cannot do --- see
[`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)'s "A
third destination" section for the activation mechanics, the stealth
roster query, and the data-sensitivity rule (a hosted destination's
payload leaves the machine regardless of billing tier, so a data
trigger forbids `openrouter/*` exactly as it forbids `opencode/*` and
`opencode-go/*`).
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

## "Local" means CLI-reachable, not on-device --- and the preference is a standing default

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
  free CLI-reachable budgets first ---
  `codex` (ChatGPT plan),
  `opencode` (its free hosted tier, Zen, and local Ollama),
  and the `agy --print` CLI ---
  then OpenRouter's prepaid credit balance,
  then a cheap Claude tier (haiku, then sonnet) ---
  reserving the conductor's own tier for judgment-heavy work.
  No new priority is implied within that free/CLI group beyond what
  the rest of this file already sets:
  `opencode`'s free and local tiers have no window to exhaust,
  so they go ahead of the metered `codex` and `agy` windows,
  per the "no window to exhaust" paragraph above.
- **Do (inferred):** read "local" as CLI-reachable everywhere in this
  ladder EXCEPT the data-sensitivity trigger,
  where on-device residency --- not CLI-reachability --- is still the
  deciding factor.
  A cloud-hosted model reached through a local CLI
  (`codex`, `agy`, OpenCode's hosted/Zen tiers, OpenRouter)
  still sends its payload off-machine,
  so only the `ollama/*` tier's loopback check (see above) satisfies a
  "must not leave this machine" requirement ---
  this section widens what counts as "local" for the cost-ordering
  preference, not for that separate residency check.
- **Don't (inferred):** default a dispatch to the inherited conductor
  tier because the cheaper route costs setup effort ---
  staging a brief file, checking a window's remaining budget, or
  probing an unmeasured destination is the ladder's ordinary cost of
  entry, not a reason to skip the cheaper route ---
  and don't skip a free CLI merely because its model happens to run
  off-device rather than on this machine.
- **Don't (inferred):** route work to a cheap tier where it
  predictably fails for a small model ---
  adversarial review, long-list triage, or any of the judgment-heavy
  work [`select-model`](../skills/select-model/SKILL.md)'s decision
  tree already carves out (architecture, a subtle-bug hunt, security
  review, synthesis) ---
  and count the resulting retry as cheap delegation.
  Escalate that work to a capable tier up front;
  a failed cheap attempt plus a retry costs more than starting at the
  right tier once.
