When background tasks, asynchronous command executions, monitors, or subagents are dispatched to inspect, search, or diagnose an issue, actively terminate them as soon as their purpose is fulfilled, their findings are superseded, or the session moves on.
Never leave diagnostic processes or superseded background jobs running indefinitely.

## Asynchronous tasks are debt until terminated

An asynchronous background process (such as a recursive `grep`, `find`, test runner, or watchdog process) consumes system CPU, memory, and disk I/O.
When a broad search traverses large caches, database files, or nested repository trees, an unmonitored background command can write tens or hundreds of megabytes of log output to disk and silently degrade machine responsiveness.

More critically, leaving tasks running pollutes session state:
a later step or review cannot determine whether an active task is a critical in-flight pipeline monitor or an abandoned exploratory probe from half an hour earlier.
An unmanaged task leaves the session in an ambiguous state where "work is still running" even when the objective has been reached.

## Sweep and terminate when the finding arrives

The moment an answer is found --- whether from the task itself, from a different file, or from inspecting code directly --- the search has done its job.
If a command was sent to the background because it exceeded synchronous timeout limits, do not treat the background status as permission to forget it.
Cancel it immediately via the harness task management tool (such as `manage_task(Action='kill')`) or kill the background process.

Before declaring a task, milestone, or session complete (and specifically before asking or confirming whether a session is done), sweep active background tasks and subagents.
Confirm that only intentional standing daemons remain, and terminate every transient or superseded task.

- **Do:** kill diagnostic searches, greps, and test processes the moment their question has been answered or superseded.
- **Do:** run an active task and subagent sweep (`manage_task(Action='list')`, `manage_subagents(Action='list')`) before declaring a milestone or session complete.
- **Don't:** leave broad searches running in the background after moving on to fixing the code or writing documentation.
- **Don't:** answer "session done" or conclude a session while transient background tasks are still running.
