# permission-check — diagnose why Claude Code is (or isn’t) prompting

A read-only diagnostic: given a tool/action pattern (e.g. `Bash(rm:*)`, `Edit`, `WebFetch(domain:example.com)`), walk every settings layer that can carry a `permissions` block, find every rule that matches the pattern, and report which one actually wins — and why.

This never edits a settings file. For *changing* permission config (adding an allow entry, moving a rule to a different layer), hand off to `update-config`.

## When this fires

- “permission check”, “why does this keep prompting me”, “why is this auto-allowed”, “check my permissions”, “diagnose this permission prompt”
- “what rule controls `<tool pattern>`”, “why did that just prompt when it didn’t last time”

## The resolution model

This is the part worth getting exactly right, because it’s counterintuitive: **rule type beats layer.** All layers’ matching rules are pooled into one set, then resolved by type — **deny, then ask, then allow** — the first match in that order wins, and neither pattern specificity nor which layer a rule came from changes that order. A `deny` in *any* layer blocks a matching `allow` in *any other* layer, including a higher-precedence one (a project-shared `deny` on `Bash(aws *)` still blocks a project-local `allow` on `Bash(aws s3 ls)`). The same holds one level down: a matching `ask` in any layer forces a prompt even when a more specific `allow` in a different layer also matches — a broad **user**-level `ask` can override a narrow **project-local** `allow` for the same call, which is easy to miss if you assume “more local wins.”

Layer precedence still matters, but for a narrower thing than resolving individual rule conflicts — it decides which layers’ rules are even in the pool at all:

1.  **Managed policy settings** — always in the pool, and can enforce two absolute overrides nothing below can undo: its own `deny` rules, and (if set) `allowManagedPermissionRulesOnly: true`, which excludes every other layer’s `allow`/`ask`/`deny` rules from the pool entirely (not just overridden — genuinely not considered). File locations: `/Library/Application Support/ClaudeCode/managed-settings.json` (+ `managed-settings.d/`) on macOS, `/etc/claude-code/managed-settings.json` (+ `managed-settings.d/`) on Linux/WSL, `C:\Program Files\ClaudeCode\managed-settings.json` (+ `managed-settings.d\`) on Windows.
2.  **CLI arguments** for this invocation (`--allowedTools`, `--disallowedTools`, `--permission-mode`) — temporary session overrides.
3.  **Project-local settings** — `.claude/settings.local.json` (gitignored, personal).
4.  **Project-shared settings** — `.claude/settings.json` (checked in).
5.  **User settings** — `~/.claude/settings.json`.

Beyond the managed-settings special cases above, once a layer’s rules are in the pool, its rank in this list does **not** break ties among rules of the *same* type — two matching `allow` rules from different layers both just mean “allowed;” there’s no conflict to resolve. The list matters for step 2 below (only a layer that’s actually present contributes rules) and for knowing when managed settings might be excluding a layer altogether.

**Hooks** (`PreToolUse`) run *before* the permission prompt but don’t bypass this chain: a matching `deny`/`ask` rule still applies regardless of what a hook itself returns. A hook that exits with code 2 is a separate, stronger mechanism — it blocks the call *before* permission rules are even evaluated, so it can stop a call an `allow` rule would otherwise have let through.

Source: [Claude Code permissions docs](https://code.claude.com/docs/en/permissions.md) (rule evaluation order, hook interaction) and [settings docs](https://code.claude.com/docs/en/settings.md) (layer list and paths). If either page has since changed its ordering or paths, that page wins over this skill’s restatement — re-fetch it rather than trust this file blindly on a stale point.

## Procedure

### 1. Get the exact pattern to diagnose

Ask for (or infer from context) the specific tool-call pattern — the same shape a rule would use: `Bash(git push:*)`, `Edit`, `WebFetch(domain:x.com)`. A vague description (“git stuff”) isn’t enough to match rule syntax precisely; ask the user to narrow it if it’s ambiguous.

### 2. Read every layer, in precedence order

``` bash
# 1. Managed policy (host-global — see privacy gate below before reading)
# macOS:   /Library/Application Support/ClaudeCode/managed-settings.json
# Linux:   /etc/claude-code/managed-settings.json
# Windows: C:\Program Files\ClaudeCode\managed-settings.json
# (each may also have a managed-settings.d/ directory of fragments)

# 2. CLI args for this session — not a file; note if the invocation used
#    --allowedTools / --disallowedTools / --permission-mode

# 3. Project-local (gitignored, personal)
cat .claude/settings.local.json 2>/dev/null

# 4. Project-shared (checked in)
cat .claude/settings.json 2>/dev/null

# 5. User
cat ~/.claude/settings.json 2>/dev/null
```

**Privacy gate on layer 1.** The managed-policy file is host-global, outside this project and outside the user’s own home-relative config — reading it can surface content unrelated to this session (org-wide policy meant for a different audience). Only read it after telling the user you’re about to, and skip it if they’d rather not. The user-settings file (`~/.claude/settings.json`) is personal but not host-global; read it without asking, same as the project layers.

### 3. Extract every matching rule

**Preflight: check for `allowManagedPermissionRulesOnly` first.** If the managed-policy file (layer 1) sets `"allowManagedPermissionRulesOnly": true`, every other layer’s `allow`/`ask`/`deny` rules are excluded from the pool entirely — not overridden, genuinely not considered. When this is set, skip layers 2–5 for this step and apply step 4 only to managed-policy rules; note in the report that the flag is active and why non-managed rules were excluded.

Otherwise, for each layer that exists, pull its `permissions.allow` / `permissions.ask` / `permissions.deny` arrays and check each entry against the target pattern — an exact match, a wildcard match (`Bash(git *)` matches `Bash(git push:*)`), or a bare tool name (`Edit` matches any `Edit` call). Record every hit with its layer and rule type; don’t stop at the first one found; the analysis needs the *full* set to apply the resolution model.

### 4. Apply the resolution model and report

1.  Any `deny` hit, from any layer → **blocked**. Report that layer + rule as the reason, and note that no `allow`/`ask` anywhere can override it.
2.  Else any `ask` hit, from any layer → **prompts** (with the layer + rule), even if a more specific `allow` also matched in a different layer.
3.  Else any `allow` hit, from any layer → **auto-allowed** (with the layer + rule).
4.  Else no hit anywhere → **prompts**, by Claude Code’s own default (no rule means ask).

If a step finds more than one matching rule of the *winning* type (e.g. two `allow` rules across different layers both match), name any one of them as the reason — they agree on the outcome, so there’s nothing to break a tie on — and list the others as also-matching.

Report format — note the counterintuitive result: a broader user-level `ask` overrides a narrower project-local `allow`, because type beats layer:

    Pattern: Bash(git push:*)

    | Layer            | Rule type | Rule                | Matches? |
    |------------------|-----------|----------------------|----------|
    | Managed policy    | —         | (not present)        | —        |
    | CLI args          | —         | (none passed)         | —        |
    | Project-local     | allow     | Bash(git push:*)      | yes      |
    | Project-shared    | —         | (no match)            | —        |
    | User              | ask       | Bash(git *)           | yes      |

    Verdict: prompts — the user-level `ask` on `Bash(git *)` wins over
    project-local's more specific `Bash(git push:*)` allow rule, because ask
    beats allow regardless of layer or specificity. If the intent was to make
    this auto-allowed, the fix is to narrow or remove the user-level `ask` rule
    (via `update-config`), not to add a more specific project-local allow rule —
    that's already there and it isn't enough.

### 5. If nothing explains the observed behavior

If the reported verdict doesn’t match what the user actually saw happen (e.g. it should auto-allow per the rules but still prompted), say so plainly rather than forcing a fit — flag the mismatch and suggest checking for a hook (`PreToolUse`) that may be intercepting the call before rule evaluation, or a session using `--permission-mode plan`/`bypassPermissions` that changes the baseline. Don’t guess at a hook’s behavior; read `hooks` config in the same settings files if one is suspected.

## Relationship to other skills

- **`update-config`** — the mutating counterpart. Once this skill identifies *which* layer and rule should change, hand off there to actually edit it; this skill never writes.
- **`fewer-permission-prompts`** — scans transcripts for *repeated* prompts and proposes an allowlist; this skill diagnoses a single pattern’s current resolution on demand. Run `fewer-permission-prompts` when the question is “what should I allowlist”, and `permission-check` when it’s “why did/didn’t this one thing prompt.”

## Anti-patterns

- ❌ Editing a settings file to “fix” the prompt — that’s `update-config`’s job; this skill only diagnoses.
- ❌ Reading the managed-policy file without telling the user first — it’s host-global, not project- or user-scoped.
- ❌ Stopping at the first matching rule found instead of collecting all matches across every layer before applying the deny/ask/allow resolution order.
- ❌ Asserting a stale precedence rule from memory instead of checking the cited docs when the diagnosis doesn’t match observed behavior.

Back to top
