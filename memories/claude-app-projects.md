# Claude app and Claude Projects: device access and thread state

What a session on the user's own computer through the Claude app can reach, how to run unattended work through a user-approved Terminal-side queue worker, and how to tell what a Claude Project thread is actually doing.
Split out of `tools.md` when a 2026-10-02 append crossed its 1250-line gate.

## macOS privacy blocks the Claude app from network volumes; a Terminal tab can read them

On the user's Mac, a render that reads a file from a mounted network share (for example the S-drive at `/Volumes/biostatistics`) fails when run from the Claude app, because macOS privacy controls (TCC) deny the app access to network volumes.
The same command succeeds from a Terminal tab, which the user has already granted access (measured 2026-10-01 on the abridge manuscript render).

- **Do:** run the command in a Terminal tab, or ask the user to, when a Claude-app session gets a permission error on `/Volumes/...`.
- **Don't:** conclude the share is unmounted or the file is missing from that error alone.
- **Don't:** suggest granting the Claude app Network Volumes or Full Disk Access to get around this block.

## Unattended work: a user-approved Terminal-side queue worker

When the work must run unattended (the user asleep, approval prompts piling up), a Terminal tab per run does not scale.
The alternative is a worker that the user approves and starts in Terminal.
Terminal already has the access, the Claude app feeds the worker jobs, and the worker stops at a set expiry time.
Starting the worker is the user's decision to delegate Terminal's access to the Claude app's session.
The delegation is one the macOS privacy controls did not grant, so the organization's policy must allow the delegation, and the delegation is the user's call, not the agent's.
The worker has:

- a queue folder the session writes job requests into;
- an allowlist of job types, such as "render this project's manuscript";
- a pinned commit SHA that the user sets, so the worker runs only that commit and never the working tree;
- an expiry time, after which the worker exits.

The job request carries no shell commands, but the code at the pinned commit can still run anything, for example through R's `system()`.
The worker rejects any job that names a path or a git ref, because the session can write the repository and a reviewed commit is only enforceable when the worker, not the job, picks the code.
A job-type allowlist limits job types, not code.
A render executes the document's own R code with Terminal's full access, so the user must review the code at the pinned commit before approving.
That SHA pins only the repository: R packages, input data, `.Rprofile`, and `renv` fetches sit outside it.
The worker's code, its configuration, and the pinned SHA must live where the Claude app cannot write, or the session could change what runs.
The worker is also not a data-egress control.
Limits on what the worker writes back (a status and exit code, and the project's normal rendered outputs, never logs or intermediate files that can echo restricted data) rest on the user's review of the code at the pinned commit, not on enforcement.
Even aggregate outputs, such as a manuscript of aggregate results, can contain small cells that identify individuals.

The abridge render worker under `~/Library/Application Support/abridge-render-queue/` on the user's Mac reportedly follows this pattern.
The Claude Project's coordinator session (the session that routes work to threads) reported it on 2026-10-02, and this repo has not verified it: its existence, the queue folder, and the properties above are reported, not observed.
In particular, the separation of the worker's code and configuration from the queue folder is not verified.
That coordinator session also described the S-drive as holding PHI on 2026-10-02.

- **Do:** before proposing the worker, confirm (or ask the user to confirm) that the organization's data and IT policy permits it;
  the user's approval does not waive that policy.
- **Do:** propose the queue worker when a per-app gate blocks the Claude app from a resource the user already reaches from Terminal, and unattended work would otherwise stall.
- **Do:** let the user review the code at the pinned commit before the worker starts.
- **Don't:** copy row-level records, or anything the project treats as protected health information, into a local cache the Claude app can read.
- **Don't:** write rendered outputs with unsuppressed small cells to a location the Claude app can read.
- **Don't:** offer Network Volumes or Full Disk Access as the alternative (see the first section's Don't).

## Claude Projects: confirm a thread's own session state before saying it is running

In a Claude Project, a "remote control session active" notice inside a thread can belong to the coordinator session rather than to that thread's own session.
On 2026-10-02 one was read as "the thread resumed" when the thread was actually parked, and the user was told work was running when it was not.
The user chatting from their Mac also does not mean Remote Control is serving the folder the thread needs.

- **Do:** check `rc_session_status` for that thread (running, connected, served) before reporting that a device thread is working.
- **Do:** say plainly when a claude.ai setting or UI path is not visible, rather than guessing a menu path;
  on 2026-10-01 there was no visible way to remove a Library context folder, and a guessed path would have sent the user looking for a control that did not exist.
- **Don't:** infer a thread's state from a notice that names no session.

## Claude Projects: an idle Remote Control session is parked after an hour, not lost

The Claude desktop app stops a Remote Control session that has had no activity for about an hour, and resumes it within seconds when the next message arrives.
This is the app's `idleSweep`, not a network, suspend or out-of-memory failure.
The one-hour limit comes from a server-side config, so no local setting changes it.
Measured 2026-11-14 on cf463-02 ([ai-config#5672](https://github.com/Morrison-Lab/ai-config/issues/5672)): the long-lived runner was parked 12 times between 2026-11-07 and 2026-11-14, each logged as `idle sweep: ... idle for` about 3,600,000 ms followed by `stopping session (idle)`, and each time the session came back with an `attached` line 2 to 8 s after it was re-admitted (usually after `redispatch requested`;
once, after the 2026-11-14 11:20 park, through `admitted (resume, activity poll)` with no `redispatch requested` line).
A desktop app restart stops sessions too, logged as `stopping session (quit)`.
The log is `~/.config/Claude/logs/remote-control.log` on the device.

- **Do:** send the message and expect a short cold start;
  report the session as parked, not as a dropped connection.
- **Do:** check that log for `stopping session (idle)` or `(quit)` before reporting a device session as lost.
- **Don't:** restart the runner or add a keep-alive ping to keep it warm;
  a ping every 50 minutes would add about 29 turns a day (decided 2026-11-14, ai-config#5672).

## Claude Projects: practices the coordinator and threads follow

Recorded from the Machine Learning course project (2026-10-12 to 2026-10-16, with later dated additions), where the user asked for each.

- **Link both the PR and its thread** whenever a message names a PR: the full PR URL, and the thread as `[title](#cmsg_...)`.
- **Broadcast to every open thread, not a remembered subset.**
  When asked to tell "all relevant threads" something, list every non-resolved thread, read each one's latest status (including threads bucketed "completed", which can be stalled on a blocked merge), and then choose recipients.
- **Apply a bulk action to every thread, resolved ones included.**
  This is wider than the broadcast rule above.
  For an action such as moving every thread to another model, enumerate with `list_threads` (every page, every state, resolved threads included, since the action applies to all of them, not only open ones), act on each, and re-list to confirm none was missed.
  When the user says "all", do all of them, and never ask "do you want me to switch all of them?"
  (2nd occurrence of the broadcast rule's remembered-subset miss, 2026-11-12: the coordinator messaged threads one at a time from memory, missed some, then asked;
  Ezra: "obviously yes; this shouldn't have been a question".)
- **Read a thread's model with `get_session`; never report it from memory.**
  Call it on every thread before saying which model one runs, and check for a capability before saying it is missing
  ([`check-thread-models`](../shared/workflow/check-thread-models.md), 2026-11-12).
- **Know ai-config's skills and commands by name.**
  A coordinator or thread may not have the plugin's skill list in context, so read the `skills/*/SKILL.md` and `commands/*.md` frontmatter in ai-config (or the project's memory index of them) before saying what a named skill or command does.
  Run a skill the user names, such as `ums`, without asking what it is
  (Ezra, 2026-11-12: "UMS is a skill in ai-config;
  you should know the names of all the skills and commands in ai-config").
- **A thread starts its own Remote Control sessions.**
  Where the user has granted a device, call `start_rc_session` yourself and never ask the user to start a session or run a terminal command.
  The call takes only a message the user typed in the same thread
  (seen 2026-11-11 on Morrison-Lab/rme#1460).
  It refuses a decision-card tap, a message the coordinator relayed, and a project-chat message.
  When a thread will need the device after the user approves, ask for a typed reply in the thread instead of a decision card,
  so the approval also serves as the message the session starts from.
  Before sending a device work that needs WWU CS hosts (cf463-01, cf463-02, the HTCondor heads), check which devices are serving with `list_devices`.
  On 2026-11-12 only the XPS was serving.
  It sat on a home network with no VPN and resolved no internal WWU CS name,
  so a rebuild of `lds-ci.sif` (Morrison-Lab/gha#1645) could not run from it.
  If no device on the WWU network is serving, say so and offer the routes, rather than brief a device that cannot reach the host.
- **Transfer GitHub issues from a device session.**
  GitHub has no REST endpoint for an issue transfer: it needs the GraphQL `transferIssue` mutation,
  and cloud sessions are refused GraphQL.
  Run `gh issue transfer` on the user's device instead.
  On the user's device, the auto-mode check blocked it as an "External System Write" until the user typed approval in the thread.
  A transferred issue keeps its sub-issue link to a parent in the original repository (rme#1460, 69 issues, 2026-11-11).
- **Check a PR preview yourself.**
  Open the deployed preview in Playwright Chromium and confirm the change, rather than handing the check to the user.
  A local `file://` render can differ from the `https` preview.
- **Never merge over a gate that looks wrong.**
  When `check-pr-fully-clean.py` fails on what looks like a false positive, get the input corrected or fix the checker, rerun, and merge only on a pass.
  Run the checker before the merge call, since the merge hook only warns.
- **The coordinator redirects a tangential task away from an in-progress thread** (Ezra, 2026-10-19, ai-config#4629).
  When the user gives a thread that is mid-task an irrelevant or tangential ask, the coordinator intervenes:
  it sends the ask to a more appropriate existing thread, or starts a new one, and tells the user where it went.
  The busy thread does not take the ask on.
  The coordinator holds itself to the same rule:
  before it routes a task to an active thread, it checks that the task falls within that thread's PR scope, and otherwise uses a separate or new thread (Ezra, 2026-10-19).
- **A thread flags a tangential ask to the coordinator instead of starting it.**
  If the coordinator has not already redirected it, the thread sends the ask to the coordinator and keeps working on its own task.
  A thread questions an instruction that seems too tangential or irrelevant to its current work, whether it comes from the user or the coordinator:
  it asks whether the instruction belongs in this thread and suggests a separate one, and does not quietly do the instruction (Ezra, 2026-10-19).
  Questioning is not refusing: the user decides where the task goes.
  An explicit "switch to this" from the user is the exception, as in [`dont-get-sidetracked`](../shared/workflow/dont-get-sidetracked.md).

## Project threads run the account-synced ai-config copy; fix delivery in a hook, not in the environment

Measured 2026-11-21 ([#6004](https://github.com/Morrison-Lab/ai-config/issues/6004), [#6060](https://github.com/Morrison-Lab/ai-config/pull/6060)): a project thread's hooks came only from the claude.ai account-synced copy under `~/.claude/plugins/synced/`, which is as fresh as Ezra's last press of **Sync** on the plugin card in claude.ai's plugin settings (then 2026-11-12).
The project's cloud environment had a Setup script older than the plugin-install step, so `ai-config@Morrison-Lab` was not installed.
The stale `guard-slide-major-tag.py` denied two gha `v3` slides that `main`'s guard allows, and both waited on Ezra.

The `update_environment` approval card cannot be approved from the Claude phone app ("This request can't be approved here.
Review it on your computer."), and the service rejected the call twice that night.
`hooks/refresh-synced-plugin-copy.py` now installs the marketplace plugin when it is missing and overwrites the synced copy at each cloud `SessionStart`.

- **Do:** when a hook in a cloud thread denies something `main` would allow, re-run `main`'s copy of the hook on the same state before treating the deny as real.
- **Do:** fix a delivery problem in a hook or PR;
  when a one-time human step is unavoidable, name it exactly, such as "press Sync on the ai-config plugin card".
- **Don't:** make an environment change the fix, or retry a rejected `update_environment` call.

## Claude Projects: the merge guard cannot see a merge grant given in a thread

Measured 2026-11-23 on [mds#865](https://github.com/Morrison-Lab/mds/pull/865).
Ezra tapped "Merge it" on a decision card in the thread and then typed "mwr mds#865" there.
`hooks/no-unauthorized-merge.py` refused the merge three times.
It reads a grant only from a typed user record, or from a record with `promptSource=sdk` and `origin.kind=human`, and a project-thread wake is neither.
The auto-mode classifier also denied `enable-mwc`.
The gap is tracked in [ai-config#6096](https://github.com/Morrison-Lab/ai-config/issues/6096), filed 2026-11-24 once a retry was accepted.
`hooks/no-unnamed-repo-pr.py` has the same gap: it denied this entry's PR after Ezra said "daytb" to opening it, because his words reached the thread only as a coordinator relay citing them.
Ezra merged the PR himself with GitHub's Merge button.
A decision-card tap does satisfy `hooks/no-unnamed-repo-pr.py`.
On 2026-11-24 a thread configured only for lds ran UMS for its quota-retry lesson,
and the hook denied the resulting ai-config PR twice.
The PR, [ai-config#6111](https://github.com/Morrison-Lab/ai-config/pull/6111) (the `self-review-fallback.md` quota-retry rule), opened once Ezra tapped a card naming ai-config.
The hook denied the PR even though the coordinator's note said ai-config was configured and other threads were opening PRs there.

- **Do:** when a thread's configured repo is not ai-config, post a decision card naming ai-config before opening a UMS PR there.
- **Don't:** take "other threads open PRs there" as evidence that this thread can.
  Read the hook's denial instead.

A link-only `.qmd` PR, [mds#882](https://github.com/Morrison-Lab/mds/pull/882), merged from the same thread under the standing "hyperlink changes count as infra" grant.
The steps were:

1. Run `check-pr-fully-clean.py` on a `build-pr-payload.py` payload.
2. Post a PR comment that starts `Annotation dispositions for head <sha7>:`, and rerun the checker with `--annotations-read` set to the ids that `batch-read-annotations.py` printed.
3. Run five `command -v` probes, each as its own command.
4. Make one opencode curl attempt (the classifier denied it, which counts as the attempt), and post a waiver note on the PR.
5. Merge through MCP with `allow_merge` and `expectedHeadSha`.

- **Do:** when a content PR's merge grant arrives as a card tap or a typed "mwr" in a project thread, tell Ezra in one line that the guard cannot read thread grants, and ask him to press Merge on the PR.
- **Do:** merge a link-only or id-only PR from a thread through the steps above, after reading the diff to confirm that it changes only links or ids.
- **Don't:** retry the guarded merge, or route around it with `enable-mwc`, once the guard has refused a thread grant.
