#!/usr/bin/env python3
"""Inject a changed detached-PR-monitor result on the next user prompt.

A monitor whose last N polls all carried an error is surfaced too, even
when the error text is unchanged: a watcher answering "no" forever in the
same words must stay distinguishable from a watcher finding nothing.
"""
import hashlib
import json
import os
import tempfile

STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-pr-monitors")
PERSISTENT_ERROR_POLLS = 3


def fingerprint(state):
    observed = state.get("data") if "data" in state else {"error": state.get("error")}
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
        error = state.get("error")
        streak = int(state.get("error_streak") or 0)
        current = fingerprint(state)
        changed = current != state.get("reported")
        persistent = (bool(error)
                      and streak >= PERSISTENT_ERROR_POLLS
                      and not state.get("persistent_error_reported"))
        if not changed and not persistent:
            continue
        state["reported"] = current
        if persistent:
            state["persistent_error_reported"] = True
        elif not error:
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
