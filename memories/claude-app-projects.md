# Claude app and Claude Projects: device access and thread state

What a session on the user's own computer through the Claude app can reach, and how to tell what a Claude Project thread is actually doing.
Split out of `tools.md` when a 2026-10-02 append crossed its 1250-line gate.

## macOS privacy blocks the Claude app from network volumes; a Terminal tab can read them

On the user's Mac, a render that reads a file from a mounted network share (for example the S-drive at `/Volumes/biostatistics`) fails when run from the Claude app, because macOS privacy controls (TCC) deny the app access to network volumes.
The same command succeeds from a Terminal tab, which the user has already granted access (measured 2026-10-01 on the abridge manuscript render).

- **Do:** run the command in a Terminal tab, or ask the user to, when a Claude-app session gets a permission error on `/Volumes/...`.
- **Don't:** conclude the share is unmounted or the file is missing from that error alone.

When the work must run unattended (the user asleep, approval prompts piling up), a Terminal tab per run does not scale.
The one-time setup is a worker the user starts in Terminal, which already has the access, and which the Claude app feeds.
Starting it is the user's decision to delegate that access, not a way around the macOS gate, so propose it and let the user choose.
It has:

- a queue folder the session writes job requests into;
- an allowlist of job types, such as "render this project's manuscript", with no arbitrary shell commands;
- an expiry time, after which the worker exits on its own.

A job-type allowlist does not limit what code runs.
A render executes the document's own R code with Terminal's access, so the worker is only as safe as the code it renders.
Restrict it to files in the project repository at a commit the user has reviewed, never a file the session writes into the queue.
It is also not a data-egress control.
Write back only a status and exit code, and the project's normal rendered outputs (for example the manuscript of aggregate results), never logs or intermediate files that can echo restricted data.

The abridge render worker under `~/Library/Application Support/abridge-render-queue/` on the user's Mac follows this pattern (set up 2026-10-02, relayed from the coordinator session, not verified from this repo).
The user's prompt that led to it: "sure claude can't read the s-drive ,but can't it run code that can?"

- **Do:** propose the queue worker when a per-app gate blocks the Claude app from a resource the user already reaches from Terminal, and unattended work would otherwise stall.
- **Don't:** copy restricted data (row-level records, or anything the project treats as protected health information;
  the coordinator session described the S-drive as holding PHI on 2026-10-02) into a local cache the Claude app can read, to get around the block.

## Claude Projects: confirm a thread's own session state before saying it is running

In a Claude Project, a "remote control session active" notice inside a thread can belong to the coordinator session rather than to that thread's own session.
On 2026-10-02 one was read as "the thread resumed" when the thread was actually parked, and the user was told work was running when it was not.
The user chatting from their Mac also does not mean Remote Control is serving the folder the thread needs.

- **Do:** check `rc_session_status` for that thread (running, connected, served) before reporting that a device thread is working.
- **Do:** say plainly when a claude.ai setting or UI path is not visible, rather than guessing a menu path;
  on 2026-10-01 there was no visible way to remove a Library context folder, and a guessed path would have sent the user looking for a control that did not exist.
- **Don't:** infer a thread's state from a notice that names no session.
