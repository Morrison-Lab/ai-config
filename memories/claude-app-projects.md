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
