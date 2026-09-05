#!/usr/bin/env python3
"""Inject a changed detached-PR-monitor result on the next user prompt.

Two writers share the state directory: the per-PR watchers spawned by
`no-unmonitored-pr.py` (GitHub only), and `monitor-open-prs.py`, which
polls every open GitHub PR in the user's scope --- opened by them,
assigned to them, or opened by the `github-actions` app --- and every
GitLab merge request they authored.

A monitor that tracks a consecutive-error streak (today only
`monitor-open-prs.py` writes `error_streak`) is surfaced too once its last
N polls all errored with the same text: a watcher answering "no" forever
in the same words must stay distinguishable from a watcher finding
nothing.  A state file with no `error_streak` (the per-PR watchers, a
pre-fix daemon) surfaces only on change --- ai-config#2035 tracks
extending the streak to the per-PR watchers.

"Change" is a change in the data or in the error text.  `monitor-open-prs.py`
polls several sources and keeps the ones that answered beside the error
from the ones that did not, so `data` can be present (even empty) while
`error` is set; fingerprinting `data` alone there would read every later
error text as "no change" and never surface it again.
"""
import hashlib
import json
import os
import tempfile

STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-pr-monitors")
PERSISTENT_ERROR_POLLS = 3


def fingerprint(state):
    # The observation is the data AND the error, not one or the other: a
    # multi-source monitor (monitor-open-prs.py) keeps the sources that
    # answered beside the error from the ones that did not, so an
    # error-text change under unchanged (or empty) data is still a change
    # and must still surface.  A healthy state hashes its data alone, so an
    # already-reported healthy monitor keeps its fingerprint across this
    # change; an already-reported ERRORING per-PR watcher (error, no data)
    # does not, and re-surfaces once on the first prompt after upgrade (a
    # pre-fix daemon in the same shape with its persistent flag set can
    # re-surface twice: the change pops the flag, then the streak fires).
    if "error" not in state:
        observed = state.get("data")
    else:
        observed = {"data": state.get("data"), "error": state["error"]}
    return hashlib.sha256(json.dumps(observed, sort_keys=True).encode()).hexdigest()


def main():
    try:
        names = sorted(name for name in os.listdir(STATE_DIR) if name.endswith(".json"))
    except OSError:
        return
    updates = []
    for name in names:
        path = os.path.join(STATE_DIR, name)
        try:
            with open(path, encoding="utf-8") as stream:
                state = json.load(stream)
        except Exception:
            continue
        if "data" not in state and "error" not in state:
            continue
        has_error = "error" in state
        streak = int(state.get("error_streak") or 0)
        current = fingerprint(state)
        changed = current != state.get("reported")
        persistent = (has_error
                      and streak >= PERSISTENT_ERROR_POLLS
                      and not state.get("persistent_error_reported"))
        if not changed and not persistent:
            continue
        state["reported"] = current
        if persistent:
            state["persistent_error_reported"] = True
        elif changed:
            # Any changed observation re-arms the persistent report: a
            # recovery and a new error text each get their own shot at the
            # threshold (the monitor restarts the streak on a text change).
            state.pop("persistent_error_reported", None)
        temporary = f"{path}.{os.getpid()}.tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True)
        os.replace(temporary, path)
        updates.append({key: state.get(key)
                        for key in ("url", "data", "error", "checked_at", "error_streak")})
    if updates:
        print("Detached PR-monitor update (inspect and act if needed): " + json.dumps(updates, sort_keys=True))


if __name__ == "__main__":
    main()
