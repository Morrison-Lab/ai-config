# wait-for-results

Block on one or more long-running jobs until they finish, then run the follow-up step the work needs (combine, build, deploy, report). Because the wait may outlive the session, this skill **leads with a handoff** so state is never lost.

## When this fires

- “wait for results”, “wait for the jobs”, “poll until done then ”.
- Right after launching a long job (SLURM array, CI run, background task, remote agent) that you intend to act on at completion.

## Step 1 — Hand off first (always)

Invoke the `handoff` skill **immediately**, before waiting. This snapshots the branch/HEAD/unpushed commits/job IDs/pick-up steps into a project memory and posts a paused-state note on any active PR/MR. The point: if the session ends or context resets while you’re waiting, the next session resumes cleanly with zero lost state.

Refresh the handoff (re-run it) if the situation materially changes during the wait — a job fails, the plan changes, or new commits land.

## Step 2 — Identify what to wait on and the success condition

Pin down, concretely: - **What** the jobs are — SLURM array IDs, background task IDs + output files, CI run, etc. - The **done** condition — `squeue` empty, expected output-file count reached, `gh run watch` exits, a sentinel file appears. - The **follow-up step** to run on success (e.g. `combine-slurm-results.R`), and what counts as failure (missing chunks, non-zero exit, error in logs).

## Step 3 — Poll on a sensible cadence

Pick the waiting mechanism by whether the wait must survive the session ending or a context reset:

- **`ScheduleWakeup` (primary for cross-session survival).** Schedule a re-invocation with a cadence matched to the job and a long fallback heartbeat. This is the only mechanism that wakes the model back up *after* the current session has ended, so prefer it whenever the wait may outlive the session.
- **Background Bash loop (same-session short waits).** Run the poll as a background Bash command so the session stays responsive; the harness re-invokes you when the command exits — but only while *this* session is still alive. If the session has already ended, a finished loop wakes nobody, so don’t rely on it to survive a reset.

Either way, match the cadence to how fast the state actually changes; don’t burn cycles polling every few seconds for a multi-hour job.

``` bash
# Same-session example: wait for a SLURM array, then verify chunk count
for i in $(seq 1 240); do
  sleep 60
  if [ -z "$(squeue -u "$USER" --name=<job-name> 2>/dev/null | tail -n +2)" ]; then
    echo "JOBS DONE (check $i); outputs: $(ls <output-glob> 2>/dev/null | wc -l)"
    break
  fi
done
# Fallback: the loop has a silent 4-hour ceiling (240 × 60s). If it exhausted
# without breaking, the jobs are still running — make that observable.
if [ "$i" -eq 240 ] && [ -n "$(squeue -u "$USER" --name=<job-name> 2>/dev/null | tail -n +2)" ]; then
  echo "TIMEOUT: jobs still running after 240 checks — run a fresh handoff and check manually."
fi
```

## Step 4 — On completion, verify then run the follow-up

- **Verify** the success condition before acting — e.g. expected output count, no failures in `logs/`, clean exit. If the jobs failed or came up short, **stop and report** rather than running the follow-up on bad inputs.
- **Run the follow-up step**, capture its output, and sanity-check the result.
- **Update the handoff memory** to reflect the new state (jobs done, results produced, next action), and update or close the PR paused-note accordingly.
- Recap to the user with a local-time stamp: what finished, what the follow-up produced, and what’s next.

## Relationship to other skills

- `handoff` — run first (Step 1) and refreshed at the end; this skill *includes* it so the wait is crash-safe.
- `memories/preferences.md` (the “always leave handoff notes proactively” bullet) — the policy that makes Step 1 mandatory.
- `claim-pr` — the paused note posted via `handoff` lives inside an existing claim.

Back to top
