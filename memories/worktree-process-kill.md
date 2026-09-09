# `pkill -f <script>` on a path shared across worktrees kills every worktree's run, not just yours

Split out of [`git-worktrees.md`](git-worktrees.md) (ai-config#694 pattern) at the 1250-line gate.

Three worktrees of this repo can each run the identical validation script (`scripts/run-local-validation.py`) from the identical relative path, in parallel, in their own separate working directories.
`pkill -f` matches the full command line as a pattern.
It carries no notion of which working directory a matched process was started from, and cutting a worktree does not change the script's own path.
So a pattern chosen to mean "my stale run" --- the script's path, with nothing narrower available to distinguish worktrees by --- means "any worktree's run of this script" to `pkill`, a peer's live, progressing run included.

An agent clearing what it believed was its own stale background run of `scripts/run-local-validation.py` ran `pkill -f "scripts/run-local-validation.py"`.
It then reported, unprompted, that it believed the command had also killed a peer worktree's run --- the correct instinct to report, worth naming as such before naming what went wrong.

**State the impact honestly, because it was not fully established.**
When the peer worktree's process table was checked roughly ninety seconds later, a `run-local-validation.py` run there was alive, had been up for 1m26s, and its log had been written 4 seconds earlier.
So either the `pkill` missed that run on timing, or it killed an earlier run that had already been replaced by the time of the check.
The *mechanism* --- that the pattern cannot distinguish worktrees --- is confirmed regardless of which of those happened.
The *damage on this specific occasion* is not established, and asserting it occurred would be exactly the failure the second half of this section exists to name.

**Do: scope a process kill by identity or working directory, never by a script path shared across worktrees.**
Two safe forms exist.
Keep the PID from the launch (`nohup ... & pid=$!`, or an equivalent capture of `$!`) and `kill "$pid"` against that specific number.
Or, when the PID was not captured, resolve candidates with `pgrep -f <pattern>` and filter each one on its actual working directory before killing it --- `readlink /proc/<pid>/cwd` (or the platform equivalent) compared against your own worktree path, killing only a match.
The general shape: a kill with any peer-visible side effect needs a scoping predicate the pattern itself does not supply, because the pattern is necessarily identical across every worktree running the same script.

**Don't: run `pkill -f` (or `killall`) against a script's relative path in a repo where more than one worktree can run that script.**
The pattern cannot tell your worktree's process from a peer's, so it does not matter how confident you are that only your own run is stale.

**A report about another process's or another agent's state is a state claim, and it gets re-queried before anyone acts on it --- including a report you just wrote about your own action.**
The natural next step after "I may have killed your run" is to tell the peer so, and the natural remediation to suggest is "re-run validation there."
Acting on that suggestion without checking first is exactly backwards: if the peer's run had in fact survived --- as the measurement above shows it had, at least at the moment checked --- following that remediation would have prompted the peer to kill its own healthy, progressing run and start over, converting a near-miss into the very damage the report was only warning about.
The report is evidence that a kill was *attempted*, not evidence about its *effect*.
Only a fresh read of the peer's own process table settles the effect.

This is the same premise this file's "A quiet worktree is not evidence the session working it has stopped" section states for a different signal --- a snapshot answers a question about a moment, not about what is true now --- applied here to a report of an action rather than to an absence of activity.
That section's remedy is to ask the affected party or re-read live state before concluding a peer is *idle*.
This is the same remedy applied one step earlier, before concluding a peer's process is *dead*.

- **Do:** re-check the peer's actual process state (or ask the peer) before recommending, or acting on, a remediation that assumes a kill succeeded.
- **Do:** capture the PID at launch and kill that PID, or filter `pgrep -f` candidates by `/proc/<pid>/cwd` against your own worktree before killing any of them.
- **Don't:** run `pkill -f`/`killall` against a script path that more than one worktree can run.
- **Don't:** treat your own report of an attempted kill as confirmation of its effect, and don't pass a "you should re-run" recommendation to a peer without that check --- the recommendation itself can cause the damage the report only suspected.

(Measured 2026-09-09, `Morrison-Lab/ai-config`: three worktrees of this repo each ran `scripts/run-local-validation.py`.
An agent ran `pkill -f "scripts/run-local-validation.py"` to clear its own stale run and reported, unprompted, that it believed it had also killed a peer's run.
A check of the peer worktree's process table roughly ninety seconds later found a `run-local-validation.py` run alive, up 1m26s, with its log written 4 seconds earlier --- so the `pkill` either missed that run on timing or killed an earlier run already superseded.
Tracked as [ai-config#3427](https://github.com/Morrison-Lab/ai-config/issues/3427).)
