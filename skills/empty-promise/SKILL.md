---
name: empty-promise
description: "Investigate and correct empty promises."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# empty-promise — audit conversation context and discharge empty promises immediately

Audit recent conversation history and assistant turns for forward-looking
commitments, debt declarations, and unmonitored automation claims
made without an immediate enforcement mechanism shipped in the same turn.
Identify what mechanism is owed
and implement or file it immediately to clear the debt.

The operational counterpart to [`shared/workflow/no-empty-promises.md`](../../shared/workflow/no-empty-promises.md)
and the `AGENTS.md` "No empty promises" rule.

## When this fires

- "empty-promise", "ep", "/ep", "check for empty promises", "investigate empty
  promises", "discharge promise debts", "did we make an empty promise?", "audit
  promises", "correct empty promises".
- **When a Stop hook or guard (`hooks/no-empty-promise.py`) blocks or warns on an
  undischarged commitment or debt phrasing.**
- **At reflective checkpoints** — during `ums`, `wrap-up`, `post-merge`, or
  immediately after a mistake or correction was acknowledged.
- **Proactive self-check** — whenever reviewing recent turns where future behavior
  was discussed or committed to.

## Two kinds of promises, two kinds of mechanisms

A promise about future behavior is not work:
it is a claim that work will happen later,
made in a conversation that will not outlive it.
Every commitment must ship an **implemented accountability mechanism in the same turn** ---
or not be made at all.

### 1. Rule promises (standing policy / future behavior)

Commits to a class of future occasions — *"going forward I will X"*, *"from now
on I won't Y"*, *"I'll always Z"*, *"I won't do that again"*, *"in future sessions
I will..."*.

- **Owed mechanism**: A **durable, inspectable artifact** written in the same
  turn:
  - A memory or rule entry (`memories/`, `CLAUDE.md`, `AGENTS.md`, `shared/`
    fragment, or repo agent docs).
  - An enforcement hook (`hooks/` + `hooks/test-*.py` + `hooks/hooks.json` +
    README table row) when the condition is decidable.
  - A filed issue when the mechanism is real work someone has to schedule.
- **Crucial boundary**: A timer or wakeup does **NOT** clear a rule promise — a
  timer fires once and dies, so it cannot keep a standing rule.
- **Honest alternative**: If no mechanism is worth building, **drop the promise
  and state the plain fact** (*"I was wrong about X, and here is the corrected
  state Y"*).

### 2. Debt promises (owed actions)

Commits to one specific outstanding action — *"the UMS pass is owed by me"*,
*"I owe #1937 the ARDI loop"*, *"I still owe that follow-up"*, *"owed by me"*.

- **Owed mechanism**: An **active firing trigger or immediate execution**:
  - Perform the owed action immediately in the current turn (run UMS, run the
    ARDI loop, run verification).
  - Arm an active wake mechanism (`ScheduleWakeup`, timer, scheduled cron/task,
    or PR watcher / detached poller) carrying the concrete next step, and report
    the firing time in local Pacific Time.
  - File a tracking issue when the debt belongs to somebody else to schedule.
- **Crucial boundary**: A written memory entry alone is the wrong instinct
  when the debt is yours and has an actionable next step;
  documenting an ARDI loop is not running one.
  Arm or run it!

### 3. Future automation claims

Claims that external systems will complete work later — *"GitHub Actions will run
CI"*, *"the review bot will post a review"*, *"GitLab will run the pipeline"*.

- **Owed mechanism**: Inspect live status immediately, or arm an explicit
  monitor for the result and report its schedule.

## Procedure

### 1. Scan recent context and transcripts

Inspect recent assistant turns in the conversation context or review transcript
logs:

```bash
# Check recent Claude transcript entries if accessible
grep -E "going forward|from now on|I'll always|I will always|won't do that again|owed by me|I owe|still owe|an owed" \
  ~/.claude/projects/*/*.jsonl 2>/dev/null | tail -n 20 || true
```

Scan for signal phrases:
- **Rule modals**: `going forward`, `from now on`, `I will always`, `I'll always`,
  `I won't`, `won't do that again`, `in future sessions`, `next time I'll`.
- **Debt language**: `owed by me`, `I owe`, `I still owe`, `an owed pass`,
  `debt is owed`.
- **Unverified automation**: `CI will finish`, `bot will review`, `pipeline will run`.

### 2. Audit same-turn mechanism delivery

For every identified candidate commitment, check what tools executed in that same
turn:
- Did the turn write to a durable rule surface (`memories/`, `AGENTS.md`, `CLAUDE.md`,
  `shared/`, `skills/`, `hooks/`)?
- Did the turn arm an active timer, scheduled task, or detached poller?
- Did the turn file an issue on GitHub / GitLab?
- Did the turn execute the owed action directly?

If no matching mechanism was shipped, the commitment is an **undischarged empty
promise**.

### 3. Classify and select the corrective mechanism

For each undischarged empty promise, select the appropriate mechanism:

| Promise Type | Example Phrasing | Required Corrective Mechanism |
|---|---|---|
| **Standing Rule** | *"Going forward I'll check X before Y"* | Update `memories/<topic>.md`, `AGENTS.md`, or implement a hook in `hooks/`. Or retract the promise and state the fact. |
| **Owed Action** | *"The UMS pass is owed by me"* | Run the UMS pass immediately in the current turn. |
| **Owed Loop / Watch** | *"I owe PR #123 the ARDI loop"* | Arm a wakeup / timer / PR watcher carrying the next step; report clock time in Pacific Time. |
| **External Debt** | *"We still owe a refactor of module Z"* | File a tracked GitHub/GitLab issue immediately and link it. |
| **Automation Claim** | *"CI will run and verify the build"* | Query live check-runs immediately; arm a poller if pending. |

### 4. Implement and deliver the mechanism

Execute the selected remedy immediately:
- **Write memory/rule**: Edit the target memory file or shared fragment in an
  isolated worktree, ensuring grep deduplication and line-cap rules are respected.
- **Scaffold hook**: Implement `hooks/<name>.py`, test suite `hooks/test-<name>.py`,
  and manifest entry in `hooks/hooks.json`.
- **Execute owed action**: Run the skipped procedure (e.g. UMS pass, test suite,
  adversarial review).
- **Arm timer / watcher**: Schedule the wakeup or PR poller and record the exact
  local firing time.
- **File issue**: Create the tracking issue using `gh issue create` or `glab issue
  create`.

### 5. Report discharged debts

Present a structured summary table in the response:

| Identified Promise / Debt | Category | Delivered Mechanism | Status |
|---|---|---|---|
| *"Going forward I will check X"* | Rule Promise | Updated `memories/preferences.md` | Discharged |
| *"UMS pass is owed by me"* | Owed Action | Executed UMS pass in PR #... | Discharged |
| *"I owe #123 the ARDI loop"* | Owed Action | Armed wakeup for 12:45 PDT | Discharged |

Include a Pacific-time timestamp (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`)
and confirm that all empty promises in the audited context are cleared.

## Relationship to other skills

- **`ums`** — updates memories and skills when lessons are learned; `empty-promise`
  specifically audits conversation turns for unbacked promises and enforces
  immediate mechanism delivery.
- **`defer-issue`** — files tracking issues when intentionally deferring work;
  `empty-promise` clears behavioral debts and promises made in conversation.
- **`recover-followups`** — audits closed PRs/issues for dropped follow-ups;
  `empty-promise` audits live session context for undischarged agent promises.
- **`wrap-up` / `post-merge`** — session and PR closing checkpoints where an
  `empty-promise` audit ensures no unbacked commitments linger.
- **`workaround-watcher`** — monitors open PRs/issues; can serve as the active
  firing mechanism for debt promises on external review state.

## Anti-patterns

- ❌ Promising a future fix or hook ("*I'll add a hook for this*") instead of
  shipping it in the current turn.
- ❌ Treating an apology, an explanation, or a restatement of the rule as a
  mechanism.
- ❌ Writing a memory entry for an owed action instead of running or arming it
  (documenting an ARDI loop is not running one).
- ❌ Arming a one-off timer to keep a standing rule (timers fire once and die;
  they cannot enforce standing policy).
- ❌ Asserting automation will finish without checking live state or arming a
  monitor.
- ❌ Manufacturing promises when the audit is clean.
