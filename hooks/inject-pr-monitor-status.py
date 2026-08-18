#!/usr/bin/env python3
"""Inject a changed detached-PR-monitor result on the next user prompt."""
import hashlib
import json
import os
import tempfile

STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-pr-monitors")


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
        current = fingerprint(state)
        if current == state.get("reported"):
            continue
        state["reported"] = current
        temporary = f"{path}.{os.getpid()}.tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True)
        os.replace(temporary, path)
        updates.append({key: state.get(key) for key in ("url", "data", "error", "checked_at")})
    if updates:
        print("Detached PR-monitor update (inspect and act if needed): " + json.dumps(updates, sort_keys=True))


if __name__ == "__main__":
    main()
