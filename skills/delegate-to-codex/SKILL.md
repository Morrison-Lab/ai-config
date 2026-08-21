---
name: delegate-to-codex
description: "Delegate sidecar task to Codex."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# delegate-to-codex — run heavy sidecar work on codex, not Claude

Standing rule: for heavy, parallelizable read / draft / verify work, spend the
separately-billed **`codex` CLI** (ChatGPT plan) first and keep Claude budget in
reserve. Claude stays the orchestrator — it writes the prompts, assembles the
stages, integrates the outputs — and is the **fallback** for anything codex
can't finish. Exhaust the *current 5-hour codex window*, then fall back to Claude
until the window resets. This skill is the mechanism; the preference lives in
`memories/preferences.md` ("Delegate heavy work to codex first").

## When this fires

- "delegate to codex", "use codex", "run this on codex", "do this with codex",
  "offload to codex", "codex-first", "dtc"
- Proactively, before any **heavy fan-out** read/analysis/verify pass (scoping a
  backlog, auditing many files, drafting N artifacts, adversarially verifying
  findings) that would otherwise spend Claude/Workflow tokens.

## When NOT to delegate

- A focused authoring/judgment task that needs Claude's own context and
  conventions (e.g. writing one skill, one PR body) — do it inline.
- The critical-path edit the rest of the work waits on — keep it local so
  progress doesn't block on a codex round-trip.
- codex is unavailable or the 5-hour window is already exhausted (see step 4).

The first two exceptions are stated in terms of **work shape**, so neither
applies when the trigger is what the work *reads*.
The third is not a shape exception at all --- it is about codex being
*available* --- and under a data trigger it inverts rather than applies: the
work waits for the window instead of falling back.
Both cases are covered in the next section.

## Data sensitivity is a second trigger, and it overrides the shape exceptions

Everything above weighs delegation against **quota**: heavy fan-out earns a
codex round-trip, a focused edit does not.
A repo can also route work to codex because of **what the work reads**, and
that trigger behaves differently in the one way that matters here.

The quota trigger is a heuristic that yields to workload shape.
A data-sensitivity trigger does not yield at all.
So read the exceptions above as scoped to the quota rationale: a focused,
single-file, critical-path analysis of restricted data matches both of the
first two exactly, and still goes to codex.

Two further consequences:

- **The exhausted-window fallback inverts.**
  Step 4 says to fall back to Claude until the window resets.
  Under a data trigger, the work waits for the reset instead.
  Falling back is what the rule exists to prevent, so it cannot be the
  remedy for codex being busy.
- **The path list belongs to the consuming repo, not here.**
  Which paths count as restricted is project-specific, so the repo's own
  `CLAUDE.md` defines them and this skill stays the mechanism.
  A good definition is mechanical rather than a judgment call --- `ucdavis/bcs`
  uses "under `inst/extdata/`, anything `git ls-files` does not list", checkable
  with `git check-ignore -q`, and names the boundary in its own API
  (schema-only inspection stays local, `collect()` goes to codex).

Do not infer a data trigger from a repo merely having sensitive data.
It applies where the consuming repo has written the rule down.

- **Do:** delegate to codex when a repo's own rules route that repo's data
  work there, even for a one-file, critical-path task.
- **Do:** wait for the window to reset when a data-triggered task cannot run.
- **Don't:** apply the shape-based exceptions above to a data-triggered task
  because it is small or blocking.
- **Don't:** invent a restricted-path list here; read the consuming repo's.

## Procedure

### 1. Confirm codex is available and in-window

```bash
codex --version            # binary at ~/.local/bin/codex
codex login status         # expect "Logged in using ChatGPT"
```

If your setup runs sessions under a cluster/HPC allocation, launch agent-scale
codex work on a compute node or allocation, not a shared login node. If login
fails or the account is out of quota, skip to step 4 (fall back to Claude).

### 2. Prepare prompts (and a schema for structured output)

Write each task's prompt to a file, and — when you need machine-readable results
back — a JSON Schema so codex is forced to emit conforming JSON:

```bash
WORK=<scratchpad>/codex-run           # a scratchpad dir, not the repo
mkdir -p "$WORK/out"
# ... write "$WORK/prompt_<id>.txt" per task, and "$WORK/schema.json" if structured
```

Fetch anything from the network yourself (e.g. `gh issue view`) and embed it in
the prompt — `-s read-only` keeps codex from mutating the repo, and you should
not rely on it having network/tooling for setup.

### 3. Run codex — background + poll for anything non-trivial

A single quick call runs in the foreground:

```bash
codex exec -C <repo> -s read-only --skip-git-repo-check \
  -o "$WORK/out/<id>.json" --output-schema "$WORK/schema.json" \
  - < "$WORK/prompt_<id>.txt"
```

- `-s read-only` for read/analyze/verify (codex can still run `rg`/`cat` to
  explore); drop to a writable sandbox only for a task that must edit.
- `-o <file>` captures the final message; `--output-schema <file>` forces JSON.
- stdin `-` feeds a long prompt.

Verify these flags against your installed `codex-cli` version (`codex exec
--help`) — flag names can shift between releases.

**Omit `-m`.**
A ChatGPT-account login does not reach every model the CLI will accept on the command line, and the refusal comes from the API rather than from argument parsing, so the flag is accepted and the run dies afterwards.
Measured 2026-08-21: `codex exec -m gpt-5.1-codex-max` returned `400 invalid_request_error: The 'gpt-5.1-codex-max' model is not supported when using Codex with a ChatGPT account.`
The same command with no `-m` ran normally.
Reach for `-m` only against an API-key login, and treat a `400` naming the account type as settled rather than retryable.

**Don't wrap the call in `timeout`.**
It is a GNU coreutils binary and is absent on macOS, so the wrapper fails before codex starts --- and it fails in a way that reads like codex failing.
The background-orchestrator pattern below is the portable answer to a long run, and it is the one this skill already prescribes.

**codex takes ~2–4 min per task, which exceeds the foreground tool timeout** —
so for multi-item or long work, run a **background orchestrator** and poll a
DONE marker (a `nohup … &` launcher returns immediately, so its completion
signal is NOT the run finishing — poll the marker instead):

```bash
cat > "$WORK/run.sh" <<'RUN'
#!/usr/bin/env bash
WORK="<scratchpad>/codex-run"; REPO="<repo>"; MAXPAR=3
export PATH="$HOME/.local/bin:$PATH"
rm -f "$WORK/DONE" "$WORK/status.log"
run_one() {
  local id="$1" start=$SECONDS rc sz flag=""
  codex exec -C "$REPO" -s read-only --skip-git-repo-check \
    -o "$WORK/out/$id.json" --output-schema "$WORK/schema.json" \
    - < "$WORK/prompt_$id.txt" > "$WORK/out/$id.codexlog" 2>&1
  rc=$?; sz=$(wc -c < "$WORK/out/$id.json" 2>/dev/null || echo 0)
  # Gate on failure: unconditional grep false-positives on incidental log mentions (warnings, prompt text).
  if [ "$rc" -ne 0 ] || [ "$sz" -eq 0 ]; then
    grep -qiE "rate limit|quota|usage limit|429|too many requests" "$WORK/out/$id.codexlog" && flag="RATELIMIT"
  fi
  echo "$id rc=$rc bytes=$sz $flag" >> "$WORK/status.log"
}
for id in <ids…>; do
  run_one "$id" &
  while [ "$(jobs -rp | wc -l)" -ge "$MAXPAR" ]; do sleep 2; done
done
wait; touch "$WORK/DONE"
RUN
chmod +x "$WORK/run.sh"
nohup bash "$WORK/run.sh" > "$WORK/runner.log" 2>&1 &
```

Then poll for `$WORK/DONE` in a **background Bash task** (so the wait itself
doesn't hit the foreground timeout), reading `$WORK/status.log` for per-item
exit code / byte count / `RATELIMIT` flags.

### 4. Detect exhaustion and fall back to Claude

Treat an item as codex-failed when its `status.log` line shows a non-zero `rc`,
`bytes=0` (empty `-o`), or a `RATELIMIT` flag. For **only those** items, redo
the stage with a Claude `Agent` / `Workflow` — don't re-route the ones codex
already finished. If the whole window is rate-limited, fall back to Claude for
the remainder and note it; resume on codex after the window resets.

### 5. Collect and synthesize

Read the `$WORK/out/*.json` results, validate them, and integrate. Claude owns
this synthesis step — codex produced the parts, Claude assembles the whole.

## Relationship to other skills

- **`select-model`** — picks *which Claude model* for a task; this skill picks
  *whether to run it on codex at all* first. Complementary: decide codex-vs-Claude
  here, then model tier there.
- **`agent-builder`**'s worker-role archetypes — this skill's "verify" work
  (via a verify-only prompt, same steps 2–5) is the concrete mechanism for
  that taxonomy's "paranoid reviewer, cross-model-family" case: point codex at
  Claude's own prior output ("does this design/diff hold up?") instead of only
  ever handing codex fresh investigation. Same procedure, different prompt.
- **Workflow orchestration** (the `Workflow` tool) — runs fan-out on **Claude**
  subagents. Prefer this skill's codex path first for the read/verify stages to
  conserve Claude budget; reserve `Workflow` for stages codex can't do or once
  its window is exhausted.
- **`ums` / `record-learnings`** — capture any new codex mechanics learned into
  the backing memory so this skill stays current.

## Anti-patterns

- ❌ Running codex in the foreground for a multi-minute task — the tool timeout
  kills it mid-run; background + poll a DONE marker instead.
- ❌ Trusting a `nohup … &` launcher's immediate "completion" as the run
  finishing — poll the marker, not the launcher.
- ❌ Re-routing codex-finished items back through Claude on a partial failure —
  fall back only for the items that actually failed.
- ❌ Spending Claude/Workflow tokens on heavy fan-out read/verify while the codex
  5-hour window still has budget.
- ❌ Delegating a focused authoring/judgment task that needs Claude's own context
  (write those inline --- unless a data-sensitivity trigger applies, which
  overrides this shape exception; see "Data sensitivity is a second trigger").
