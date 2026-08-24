---
name: delegate-to-opencode
description: "Delegate sidecar work to opencode free or local models."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# delegate-to-opencode --- run sidecar work on a free or local model

The `opencode` CLI reaches two model tiers this corpus has no other route to: a hosted free tier (opencode Zen) and a fully local one (ollama).
Both cost no quota at all, so work small enough for them should not spend Claude's budget, codex's window, or agy's.
The local tier also does something none of the other destinations can: it keeps the payload on the machine.

Claude stays the orchestrator.
It writes the prompt, runs the delegate, validates what comes back, and does the synthesis.
This skill is the mechanism.
The budget preference it plugs into lives in `memories/preferences.md` ("Delegate heavy work to another CLI first").

## Why this is a shell-out and not a subagent

The `Agent` tool's `model` parameter is an enum of Claude aliases, and `.claude/agents/*.md` frontmatter takes the same aliases or `inherit`.
There is no per-agent hook for a third-party endpoint, so the only route to opencode is Bash --- the same shape [`delegate-to-codex`](../delegate-to-codex/SKILL.md) uses.

## When this fires

- "delegate to opencode", "use opencode", "run this on opencode", "run this on a local model", "use a free model", "keep this local", "dto"
- Proactively, before any **mechanical, bounded** read/extract/reformat pass --- a grep-and-summarize sweep, a bulk reformat, a first-pass triage of many files --- that would otherwise spend a metered budget.
- Whenever the work reads data that must not leave the machine, which routes to the local tier rather than the hosted one.

## When NOT to delegate

- **The task needs strong reasoning, judgment, or long-context synthesis.**
  This is the exception with no codex analogue, so check it first.
  A wrong answer from a small model costs more to detect than the quota it saved.
- **The critical-path edit the rest of the work waits on.**
  Do it inline, in this session, so progress does not block on a round-trip.
- **The result must conform to a schema and you have no cheap validator.**
  `opencode run` has no schema flag, so conformance is asked for in the prompt and checked on the way back rather than enforced at the boundary.
- **The hosted tier is rate-limited, or the ollama daemon is down.**
  Neither is a window running out, because neither tier has a window.
  This is availability, not budget, and what it licenses depends on whether a data trigger applies.

The first two transfer from `delegate-to-codex`, but for a reason that skill does not have.
There, work shape and model capability were independent.
Here they point the same way: authoring and judgment work is exactly what the free and local tiers are worst at.

## Hosted-free versus local: the routing rule

[`delegate-to-codex`](../delegate-to-codex/SKILL.md)'s "Data sensitivity is a second trigger" section says a repo can route work to codex because of **what the work reads**, that this trigger overrides the shape exceptions, and that when codex is busy the work waits rather than falling back.

That trigger does not transfer to opencode.
It **splits**, because opencode is two destinations rather than one, and the two differ in the only property the trigger cares about.

**The split.**
`opencode/*` is opencode Zen, a hosted gateway: the payload leaves the machine exactly as it does for any other hosted model.
Free is a **billing** fact and says nothing about where bytes go.
`ollama/*` is the only id on the whole ladder that *can* keep the payload on the machine --- not Claude, not codex, not agy, not opencode Zen.

**But locality is a property of the configured endpoint, not of the prefix.**
`ollama` is a user-authored provider entry in the opencode config, and its `options.baseURL` is an ordinary field in it.
Pointing that field at a LAN GPU box or a remote `OLLAMA_HOST` is ordinary usage rather than an edge case, and the id still reads `ollama/*` when it happens.
So the prefix narrows the candidates to one and licenses nothing by itself, and a model id recorded in a report names the provider label rather than the endpoint it resolved to.
What licenses the locality claim is the endpoint check in step 1, which resolves that `baseURL` and refuses anything that is not loopback.
Run it before sending data-triggered work, and record the endpoint it printed rather than the model id alone.
Measured 2026-08-19 on this machine: `http://localhost:11434/v1`, resolving to `127.0.0.1` and `::1`.

So a data trigger routes to `ollama/*` and forbids `opencode/*`, where under codex the same trigger simply said "delegate".
Read a repo's approval as naming a **destination**, not as naming delegation in general: a `CLAUDE.md` rule permitting codex for restricted data says nothing about a hosted free tier nobody has cleared.

**The discriminator is the provider prefix, not the `-free` suffix.**
`opencode models` on 2026-08-19 listed `opencode/big-pickle` alongside six ids ending in `-free`, all under the same hosted provider.
The suffix answers a pricing question.
The prefix answers which tier a job goes to, which is the routing question.
It does not answer where that tier's endpoint points, which is what step 1's endpoint check settles.

**The fallback inverts differently than it does for codex.**
There, the inversion was "wait for the window instead of falling back to Claude".
Local has no window, so there is nothing to wait for, and the move that must be blocked is a **tier** fallback rather than a vendor one: re-running a slow or failed `ollama/*` job on `opencode/*` because the hosted tier is faster.
That retry is one flag value away and reads as ordinary troubleshooting, which is why it needs naming rather than leaving to judgment.
When the local tier cannot do a data-triggered job, fall back only to whatever the repo's own rule already permits --- which may be doing the work by hand.

As in the codex skill, do not infer a data trigger from a repo merely holding sensitive data.
It applies where the consuming repo has written the rule down, and that repo owns the path list.

- **Do:** run step 1's endpoint check before data-triggered work, and record the endpoint it printed beside the model id so the destination is auditable afterwards.
- **Do:** send data-triggered work to an `ollama/*` id, and stop rather than re-route when the daemon is unavailable or the check refuses.
- **Don't:** retry a failed or slow local run on a hosted model.
- **Don't:** treat the `ollama/` prefix as the locality guarantee --- it names a provider entry whose endpoint is user-configurable.
- **Don't:** read a `-free` suffix, or its absence, as evidence about where the payload goes.

## Where opencode sits in the budget ladder

`memories/preferences.md`'s "Delegate heavy work to another CLI first" holds the order across `codex`, `agy`, and `opencode`.
Read it there rather than re-deriving it here.

Two things follow from opencode not being a metered plan at all, and they are what make its position unlike the other two:

- **It consumes no window, so there is no budget to conserve by skipping it.**
  For work a small model can do, it goes ahead of codex and agy rather than behind them.
- **Capability is the binding constraint instead, and it is unmeasured here.**
  The local ids carry their parameter counts, 2B to 30B as of 2026-08-19.
  The hosted ids are preview names this corpus has not benchmarked.
  So every figure one returns gets re-derived, per the same treatment `preferences.md` records for `agy` after it read a file correctly and miscounted its lines.

The practical shape is a filter rather than a queue: send what opencode can do to opencode, send what it cannot to codex or agy, and keep Claude for orchestration and the residue.

## Procedure

### 1. Confirm opencode is available and pick a tier

```bash
opencode --version
opencode models
```

`opencode models` prints ids as `provider/model`, which is the routing signal from the section above.
A malformed config fails here rather than mid-run --- see Troubleshooting.

An `ollama/*` id appearing in that list only says the config declares it, not that the daemon is up, so smoke-test the exact id you intend to use:

```bash
opencode run -m ollama/qwen2.5-coder:3b "Reply with exactly the word: PONG"
opencode run -m opencode/deepseek-v4-flash-free "Reply with exactly the word: PONG"
```

Measured 2026-08-19 on opencode 1.18.15: both returned `PONG`, in 13.3s local and 7.9s hosted.

**Before any data-triggered work, verify the endpoint.**
The routing rule above turns on where `ollama/*` actually points, and that is a config value rather than a fixed property, so it gets checked rather than assumed.
`opencode debug config` prints the resolved config as JSON on stdout (verified 2026-08-19), so the check reads the merged value rather than one file that something else may override:

```bash
python3 - <<'PY'
import ipaddress, json, socket, subprocess, sys
from urllib.parse import urlparse

try:
    raw = subprocess.run(
        ["opencode", "debug", "config"],
        capture_output=True, text=True, check=True,
    ).stdout
    url = json.loads(raw)["provider"]["ollama"]["options"]["baseURL"]
except Exception as exc:
    sys.exit(f"REFUSE: cannot read the ollama baseURL from opencode's config: {exc}")

host = urlparse(url).hostname
if not host:
    sys.exit(f"REFUSE: no host in ollama baseURL {url!r}")

try:
    addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
except OSError as exc:
    sys.exit(f"REFUSE: cannot resolve {host!r}: {exc}")

remote = sorted(a for a in addrs if not ipaddress.ip_address(a).is_loopback)
if remote:
    sys.exit(f"REFUSE: ollama baseURL {url} resolves off-machine: {', '.join(remote)}")

print(f"OK: ollama baseURL {url} resolves to loopback only ({', '.join(sorted(addrs))})")
PY
```

It exits 0 and prints the endpoint only when every address the host resolves to is loopback.
Every other outcome refuses: an unreadable or unparseable config, a missing `ollama` provider or `baseURL`, a host that will not resolve, or any resolved address that is not loopback.
Refusing on an unreadable config is deliberate rather than defensive, per [`fail-fast`](../../shared/principles/fail-fast.md): a config you could not read is not evidence that anything is local, so it must not reach the pass branch.
This check is what licenses the locality claim, so run it in the session that sends the data and quote its output, rather than carrying a verdict over from an earlier one.

### 2. Prepare the prompt

As of 2026-08-19, `opencode run` takes the message as positional arguments, and `-f/--file` attaches files.
Use `--dir` to point the run at a repo, and `--variant` for a provider-specific reasoning effort.
Fetch anything from the network yourself and embed it in the prompt.

**There is no schema flag.**
`opencode run --help` on 2026-08-19 offered `--format json`, which emits the raw event stream rather than a schema-constrained final message, and nothing equivalent to codex's `--output-schema`.
So ask for the structure in the prompt and validate it on return.
Expect that validation to fail sometimes, because emitting strict JSON is one of the things small models are worst at.

### 3. Run it

There is no sandbox flag either.
`opencode run --help` on 2026-08-19 listed none, and permissions come from the `permission` block in the opencode config.
`--auto` auto-approves everything not explicitly denied, and its own help calls it dangerous, so scope the config rather than reaching for that flag.
The root `opencode.json` in this repo is intentionally unscoped
(`permission: allow` for all tools, `opencode.json:23-37`)
to avoid interactive prompts for routine `gh`/`sh` pipelines.
This is the config-scoped equivalent of `--auto`
and is documented as deliberate here.
Prefer this repo-level allow over per-invocation `--auto`.

For a long or multi-item run, borrow the background-runner-plus-DONE-marker *shape* from [`delegate-to-codex`](../delegate-to-codex/SKILL.md) step 3 rather than making a foreground call that the tool timeout will kill.
Borrow the shape and not the body.
**Four things in that skill's `run_one()` do not transfer**, and the fourth fails silently rather than erroring:

- **`-o <file>`**, which opencode has no equivalent of, so there is no per-item JSON file to write.
- **`--output-schema`**, which it has no equivalent of either.
- **stdin `-`**, which is not how a prompt is passed here.
  `opencode run` took the message as positional arguments as of 2026-08-19, so a literal `-` becomes the prompt text.
- **The `bytes=0` success gate**, which reads the `-o` file that was never written.
  It therefore reports `bytes=0` for every item, misclassifying a run that fully succeeded as one that entirely failed.

Capture stdout and gate on the exit status instead, per step 4.

**`MAXPAR` is the fifth, and it half-transfers: it applies to the hosted tier and not to the local one.**
Local runs share one machine's GPU and memory, so raising parallelism against a single ollama daemon contends for the same hardware instead of fanning out.
The crossover point is unmeasured here, so treat local work as serial until somebody measures it.

### 4. Detect failure

With no `-o` capture file, key on the exit status and on empty stdout.
Then check something codex's step 4 does not have to: a small model's usual failure is a **fluent wrong answer** rather than an error, so output validation matters more here than exhaustion detection does.
Re-run only the items that actually failed.

### 5. Collect, validate, synthesize

Read the results, re-derive every count and citation, and integrate.
Claude owns this step.

## Troubleshooting

**Every invocation fails with a config error when a model declares `limit.context` without `limit.output`.**
Reported 2026-08-19 in [ai-config#1693](https://github.com/Morrison-Lab/ai-config/issues/1693): `~/.config/opencode/opencode.jsonc` had `gemma4:12b` and `granite4:7b-a1b-h` each carrying `limit.context` alone, and every `opencode` call failed until both were given an `output` value.
The schema wants the pair.

Two things make it a plausible first-run trap.
The failure is total rather than scoped to the offending model, so it looks like a broken install rather than a config typo.
And it fires on `opencode models` too, so the command you would reach for to diagnose it fails the same way.

The fix is to give every model that declares `limit.context` a `limit.output`, or to drop the `limit` block entirely --- as of 2026-08-19 the models in that file carrying no `limit` at all were unaffected.

## Relationship to other skills

- **[`delegate-to-codex`](../delegate-to-codex/SKILL.md)** --- the same shell-out shape aimed at a metered frontier CLI.
  Read its steps 2 to 5 for the background runner and DONE-marker poll rather than duplicating them here.
  What does not carry over is its data-sensitivity trigger, which splits into the routing rule above.
- **[`select-model`](../select-model/SKILL.md)** --- picks *which Claude model* runs a task.
  This skill decides whether the task runs on Claude at all.
- **[`agent-builder`](../agent-builder/SKILL.md)** --- an opencode model is a different model family from both Claude and codex, so it is a cheap cross-family second reader for that skill's "paranoid reviewer" role.
  How much its agreement is worth is governed by [`self-review-fallback`](../../shared/workflow/self-review-fallback.md)'s cross-vendor section.
- **[`ums`](../ums/SKILL.md)** --- record new opencode mechanics here as they are measured, since the model list and the version above will go stale.

## Anti-patterns

- ❌ Sending data-triggered work to an `opencode/*` model because it is free --- free is a billing property, and the payload still leaves the machine.
- ❌ Retrying a failed or slow `ollama/*` run on the hosted tier.
- ❌ Passing `--auto` to widen a delegate's permissions instead of scoping the config (repo root `opencode.json` uses a blanket-allow config intentionally as the scoped equivalent — see above — prefer that over `--auto` per-run).
- ❌ Pointing a codex-style `MAXPAR` fan-out at one ollama daemon and expecting hosted-style throughput.
- ❌ Quoting a count, a line number, or a citation a free model returned without re-deriving it.
- ❌ Skipping opencode for small mechanical work because codex is stronger --- codex has a window to conserve and opencode does not.
- ❌ Handing a free or local model the authoring or judgment task that needed Claude's own context.
