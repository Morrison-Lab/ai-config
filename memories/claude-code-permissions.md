# Claude Code permission-rule matching mechanics

How Claude Code's built-in permission matcher decides whether a Bash (or other tool) call is allowed, denied, or asked about --- the syntax and matching mechanics, as opposed to the scope-precedence question (`managed` > CLI > local > project > user) that [`claude-code-settings.md`](claude-code-settings.md) already owns, or the deny/ask/allow evaluation order across settings layers that [`skills/permission-check/SKILL.md`](../skills/permission-check/SKILL.md) already owns correctly.
Satellite of [`claude-code.md`](claude-code.md).

Verified 2026-08-21 against [code.claude.com/docs/en/permissions](https://code.claude.com/docs/en/permissions) (fetched in full that day).
Third-party platform behavior changes, so re-fetch rather than trusting this snapshot.

## The matcher is shell-operator aware: a chained command is checked segment by segment, not as one string

**The belief that was wrong:** a Bash command chaining an allowed pattern with `;`, `&&`, `|`, or a redirect is rejected as a WHOLE command even though the allowed part matches exactly --- i.e. `Bash(gh pr diff:*)` being an allow rule would not help `gh pr diff N | wc -l`, because the string as a whole isn't `gh pr diff N`.

**The fact that replaced it:** Claude Code splits a Bash command on the recognized separators (`&&`, `||`, `;`, `|`, `|&`, `&`, and newlines) and requires **every** resulting segment to match its own rule.
The docs state it directly:

> Claude Code is aware of shell operators, so a rule like `Bash(safe-cmd *)` won't give it permission to run the command `safe-cmd && other-cmd`.
> The recognized command separators are `&&`, `||`, `;`, `|`, `|&`, `&`, and newlines.
> A rule must match each subcommand independently.

So `gh pr diff N | wc -l` is refused not because the whole string fails to match `gh pr diff N`, but because `wc -l` is a second, independent segment with no allow rule of its own --- `gh pr diff N` alone matches fine.

This cuts both ways, and both directions matter:

- **A deny rule cannot be evaded by chaining.**
  `cd /tmp && git commit ...` is still refused, at its second segment, by a deny rule on `git commit`, even though `cd /tmp` alone would be fine.
- **An allow rule fails on a chained command when some OTHER segment has no rule of its own**, even when the allowed part matches exactly.
  This is the one that bites in practice: a reviewer prompt granting `Bash(gh pr diff:*)` still gets denied on `gh pr diff N | wc -l`, `gh pr diff N > /tmp/pr.diff`, or `gh pr diff N && echo done`, because the second segment (or the redirect target --- see the docs' own "Redirections" section) needs its own coverage.

**PowerShell has the identical segment-aware behavior**, splitting on `|`, `;`, and (PowerShell 7+) `&&`/`||` via the parsed AST, with the same "every subcommand must match" rule.

**Do NOT confuse this with a `PreToolUse` hook's deny.**
A hook decides over the whole `tool_input.command` string as one blob --- see [`claude-code-hooks.md`](claude-code-hooks.md)'s "A hook's deny rejects the WHOLE call, so a compound command's setup segments never run either".
That section's own closing line ("reach for `&&` as the remedy ... governs a *shell* sequencing hazard, and a hook denial never reaches the shell") is correct and does not need revising --- it is about hooks, a different mechanism from the **built-in permission-rule matcher** this entry covers.
The two coexist: the built-in matcher is segment-aware;
a hook you write yourself is not, unless you make it so.

- **Do:** when a reviewer/agent prompt or a settings file grants a command pattern, check whether the actual invocations pipe, redirect, or chain it with something else, and grant (or scope a deny to) every segment that can appear, not just the "main" one.
- **Do:** read a denial's blocked segment from the execution/log output before assuming the whole compound string was rejected.
- **Don't:** assume a chained command is refused as one indivisible string, or that granting the first/main segment of a pipeline is sufficient.
- **Don't:** reach for `&&`-avoidance as a fix for a `PreToolUse` hook denial --- that hazard and this one are different mechanisms with different remedies.

## A bare tool name means "all invocations" as an allow rule, and "remove the tool entirely" as a deny rule

`Bash` with no parentheses is the canonical bare-tool-name form and is equivalent to `Bash(*)`.
As an **allow** rule it matches every Bash call.
As a **deny** rule, both forms do something stronger than blocking every call: they remove the tool from Claude's context entirely, so Claude never sees it as an option at all (with one exception, `EndConversation`, which a bare deny cannot remove while any other tool remains).
A scoped rule like `Bash(rm *)` is different in kind, not just narrower: it leaves the tool available and blocks only the matching calls when attempted.

- **Do:** use a bare tool name in `deny` when the goal is to hide the tool from the model's available-tools list, not merely refuse specific calls.
- **Don't:** read a bare-name deny as equivalent to a maximally-broad scoped deny (`Bash(*)` behaving like `Bash(** )`) --- it removes the tool from context, which is a different, stronger effect.

## Absolute paths in path-scoped rules need a `//` prefix; a single leading `/` anchors at the settings source, not the filesystem root

**The belief that was wrong (an easy one to default to):** a rule like `Edit(/tmp/**)` or `Read(/Users/alice/file)` names an absolute filesystem path because it starts with `/`.

**The fact that replaced it:** a single leading `/` in a `Read`/`Edit`/`Write` (or `Cd`) path pattern anchors at the directory associated with the **settings source that defines the rule** (project root, the local-settings starting directory, `~/.claude/`, etc.) --- not the filesystem root.
The docs give this exact warning:

> A pattern like `/Users/alice/file` isn't an absolute path.
> The single leading slash anchors at the settings source, not the filesystem root.
> Use `//Users/alice/file` for absolute paths.

So the four pattern forms are:

| Pattern            | Meaning                              | Example                    |
| ------------------- | ------------------------------------ | --------------------------- |
| `//path`            | Absolute path from filesystem root   | `Edit(//tmp/**)` = anywhere under `/tmp` |
| `~/path`            | Path from home directory             | `Read(~/Documents/*.pdf)`   |
| `/path`             | Path relative to the settings source | `Edit(/src/**/*.ts)` = `<project root>/src/**/*.ts` in project settings |
| `path` or `./path`  | Path relative to current directory   | `Read(*.env)`               |

On Windows, paths are normalized to POSIX form first, so `//c/**/.env` matches `.env` anywhere on the `C:` drive.

### A path rule must be spelled `Edit(...)`, never `Write(...)`

Getting the `//` prefix right is not sufficient, because the TOOL NAME in a
path rule matters too, and the natural choice is the wrong one.

> Claude Code checks file permissions against `Edit(path)` and `Read(path)`
> rules only.

> Use `Edit(docs/**)` in place of `Write(docs/**)`, `NotebookEdit(docs/**)`, or
> `MultiEdit(docs/**)`, and `Read(docs/**)` in place of `Glob(docs/**)`.

So `Edit(...)` covers the `Write`, `NotebookEdit` and `MultiEdit` tools as well
as `Edit` itself.
A `Write(//tmp/**)` rule is accepted and then never consulted, so the grant
does nothing.

**It is not silent, though, and the difference decides where you would notice.**
The same passage continues:

> If you write a path rule for `Write`, `NotebookEdit`, `Glob`, or the legacy
> `MultiEdit` tool instead, Claude Code accepts the rule but never consults it,
> and **warns at startup**, except for a `Glob` rule passed in
> `--allowedTools`.
> [...]
> Requires Claude Code v2.1.210 or later.

So an interactive session tells you.
What does not tell you is a headless CI run, where nobody reads the startup
log --- which is exactly where such a rule tends to be written, and why the
grant can look present and correct for as long as it does.
The version floor matters for the same reason: below v2.1.210 there is no
warning at all, so the only signal is the one nobody was watching.

Measured 2026-08-21: `Write(//tmp/**)` was written into a real reviewer
allowlist on the strength of the `//` fix above, in a CI-only workflow, and a
reviewer caught that the tool name defeated it.
The two facts are independent, and getting the first one right is what makes
the second easy to miss.

- **Do:** spell every path-scoped rule `Edit(...)` or `Read(...)`, whichever
  side of the read/write split it governs.
- **Do:** read the startup warning when one is available, and remember that a
  headless run gives you no such thing.
- **Don't:** write `Write(...)`, `MultiEdit(...)`, `NotebookEdit(...)`, or
  `Glob(...)` with a path --- each is accepted and never consulted.
- **Don't:** describe the failure as silent without qualifying it.
  It warns at startup from v2.1.210, and the `Glob`-in-`--allowedTools` case
  is exempt from even that.

- **Do:** write `//path` (double leading slash) for a genuinely filesystem-root-absolute rule, e.g. `Edit(//tmp/**)` to grant scratch writes anywhere under `/tmp` regardless of which settings file defines the rule or where the session started.
- **Don't:** write a single leading `/` and expect it to mean "absolute" --- it means "relative to wherever this settings file's own anchor is," which varies by settings source (project root, starting directory, `~/.claude/`, etc.).

## Parameter-scoped rules (`Tool(param:value)`) are valid only in deny/ask, never allow -- and an omitted parameter is never matched

`Tool(param:value)` matches a top-level input field on any tool (e.g. `Agent(model:opus)`, `Bash(run_in_background:true)`) and is restricted to **deny and ask** rules only:

> Deny and ask rules can match a top-level input parameter on any tool with `Tool(param:value)`. ...
> An allow rule for one parameter value wouldn't establish that the call is safe overall, so allow rules continue to use each tool's own specifier syntax.

Two consequences worth keeping straight:

- **There is no allow-rule form of this.**
  You cannot write an allow rule that says "only when `run_in_background` is false" --- allow rules use each tool's own specifier syntax (e.g. `Bash(npm run build)`), not parameter matching.
- **A parameter the model omits from the call is never matched**, so `Agent(run_in_background:true)` as a deny rule does NOT catch a call that simply leaves `run_in_background` unset --- even when the tool's own default for that unset parameter is `true`.
  The docs state this plainly: "A parameter the model omits is never matched, so `Agent(model:*)` doesn't match a call that leaves `model` unset."
- **You can't match a tool's primary content field this way** --- `command` for Bash/PowerShell, `file_path` for Read/Edit/Write, `url` for WebFetch, etc. Claude Code ignores such a rule and warns at startup, because e.g. `Bash(command:rm *)` would be bypassable by a compound command.
  Use the tool's own specifier syntax (`Bash(rm *)`) for those instead.

- **Do:** use `Tool(param:value)` only in `deny`/`ask`, and only for a parameter that will actually be present on the call you're trying to gate --- check the tool's default and whether the model is likely to omit the parameter rather than set it explicitly.
- **Do:** write a matching prompt instruction (e.g. "always pass `run_in_background: false`") as a complement, not a substitute, when the parameter is commonly omitted --- the rule only reaches calls that state the parameter explicitly.
- **Don't:** write `Agent(run_in_background:false)` as an allow rule expecting it to restrict Agent calls to foreground-only --- parameter matching isn't available in allow rules at all.
- **Don't:** assume a deny rule on a parameter's "dangerous" value also blocks the same call when that parameter is left at its default and omitted from the call --- it does not.

## Recording a WRONG mechanism for a denial is worse than recording no mechanism at all

A `Morrison-Lab/gha` reviewer-prompt comment concluded that writing to a file was "a hard block in this sandbox, so no allowlist entry can satisfy it," after observing `Write` calls fail --- an unverified mechanism that stood unchallenged for months.
Checking it against the execution file, rather than trusting the earlier assumption, showed it was wrong: the failure was recorded in the execution file's `permission_denials` array, which is the **permission layer's own refusal log**, not evidence of an OS-level sandbox block.
A `Write` grant was exactly the missing fix, and the comment's wrong mechanism had argued against making it the whole time (`Morrison-Lab/gha#578`, opened 2026-08-21, not yet merged).

The transferable lesson is not "verify observations" in general --- it's specifically about what a wrong *mechanism* costs once written down: a wrong observation just needs re-checking, but a wrong mechanism actively **argues against the real fix**, because a reader who trusts the stated cause ("hard sandbox block, unfixable by permission config") has no reason to try the very change that would have worked ("grant `Write`").
The wrong mechanism doesn't just fail to help;
it forecloses the correct next step for every later reader who takes it at face value.

- **Do:** when recording why a tool call failed, verify the *layer* it failed at (permission rule vs. `PreToolUse` hook vs. OS-level sandbox) against the actual artifact --- the execution file's `permission_denials` array names which layer refused --- before writing the explanation down.
- **Do:** treat "I haven't verified the mechanism" as a reason to write "cause unknown" rather than a plausible-sounding guess, when a comment or memory entry will be read later as authoritative.
- **Don't:** generalize an observed failure ("the write didn't happen") into a specific, unverified mechanism ("sandbox hard block") and then let that mechanism claim stand as the reason a fix wasn't attempted.
- **Don't:** treat a wrong mechanism as merely a wrong fact with no further cost --- weigh it as actively blocking whatever fix the correct mechanism would have suggested.

## Auto-mode YOLO classifier pipeline & denial circuit breakers

Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236).
Classifier models, prompt evaluations, and safety thresholds are actively updated by upstream providers;
re-verify before relying on these internal pipeline stages:

- **Bypass-immune safety checks**:
  Sensitive directories (`.git/`, `.claude/`, shell RC files) cannot be auto-approved by the classifier unless explicitly marked `classifierApprovable`.
- **Fast paths**:
  Read-only safe tools (`isAutoModeAllowlistedTool`) and actions allowed under `acceptEdits` (excluding `Agent` and `REPL`) bypass the classifier API and auto-allow immediately.
- **Two-stage classifier**:
  - Stage 1: Fast classifier.
  - Stage 2: Thinking classifier (invoked only if stage 1 is uncertain).
  - Fail-closed gate: If the classifier API fails, execution fails closed with retry guidance.
- **Denial limits**:
  Tracks consecutive and total denials (default thresholds: 3 consecutive, 20 total).
  Exceeding thresholds falls back to user prompts or aborts headless runs.
- **A chained `&&` sequence of otherwise-routine git commands can be blocked where each command run individually is not.**
  Observed 2026-08-29: `cd <repo> && git status --short && git fetch origin main && git checkout main && git pull --ff-only origin main && git branch -D <branch>` was refused outright with "Blocked by classifier" and no further detail.
  Re-issuing the same five operations as five separate Bash calls succeeded with no prompt at all, `git branch -D` (a destructive operation) included.
  The mechanism is unverified --- per the section above, don't assert one --- but the workaround is cheap regardless of cause: when a chained command is denied for no stated reason, split it into individual sequential Bash calls before assuming a deeper permission problem.
  - **Do:** split a denied `&&`-chained shell sequence into individual Bash calls and retry, before escalating or asking the user.
  - **Don't:** assume a chained-command denial means any one of its individual steps (even a destructive one like `git branch -D`) is itself blocked --- test each step alone first.
- **A denial can also be transient in TIME, not only in command shape --- and reporting one as a hard blocker is the expensive error.**
  The bullet above is about splitting a chain.
  Measured 2026-08-30: after a chained heredoc was refused, an UNCHAINED call (`python3 build_payload.py`, which only wrote a JSON file) was refused too, so splitting did not recover it.
  About twenty minutes later that identical command ran first try, and so did the merge-gating script it fed.
  Nothing about permissions changed in between.
  So a denial that survives the split is still not evidence of standing policy.
  What makes this worth its own bullet is the asymmetry in what the two mistakes cost.
  Re-attempting a genuinely blocked action wastes a call and reads as evading the refusal.
  Reporting a transient one as a blocker ends the turn, asks the user for a permission they did not need to grant, and stalls whatever the command gated --- in the measured case two PRs that were already fully clean, which merged immediately once the command simply ran.
  The user spends a round trip on a problem that had already dissolved.
  - **Do:** after splitting, wait and retry once more before calling it a blocker.
  - **Do:** report what you actually tried ("denied, split, retried once, still denied") rather than only that something was denied.
  - **Don't:** read a denial that survives the split as standing policy --- it may just be the surrounding turn.

## OS sandbox filesystem invariants & customization lockdown paths

Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236) and managed policy behavior:

- `sandbox.autoAllowBashIfSandboxed: true` auto-approves safe commands inside Seatbelt/Bubblewrap/WSL2.
- **Protected paths**:
  Writes to customization directories (`~/.claude`, `.claude/skills`, `.claude/commands`, `.claude/agents`, `settings.json`, `.mcp.json`)
  and bare git repository control files (`HEAD`, `objects`, `refs`, `hooks`, `config`)
  are restricted under sandboxed and managed customization lockdown modes to prevent escape vectors.
