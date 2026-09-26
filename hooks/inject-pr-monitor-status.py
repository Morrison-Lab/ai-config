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

What is *emitted* is a digest, not the raw state (ai-config#3999).  Raw
states carry every check run's timestamps and URLs and, for the multi-source
monitor, every open PR in scope with its `updatedAt`; injected verbatim they
reached ~100 KB per prompt while telling the session nothing it could act on.
A per-PR state is reduced to a summary (state, mergeability, review
decision, check counts, failing and pending check names) and is emitted only
when that summary changes.  A list-shaped state is reduced to the entries
that appeared or disappeared since the last report, so `updatedAt` churn on
an unchanged set is silent (GitHub `updatedAt` and GitLab `updated_at`
alike), and a source left out of a poll because it errored keeps its last
reported set.  An error is emitted whenever the state carries one, exactly as
before, and its clearing is emitted as `recovered_from`.
"""
import hashlib
import json
import os
import tempfile

STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-pr-monitors")
PERSISTENT_ERROR_POLLS = 3
MAX_LISTED = 20
VOLATILE_KEYS = {"updatedAt", "createdAt", "updated_at", "created_at",
                 "checked_at"}
FAILING = {"FAILURE", "TIMED_OUT", "CANCELLED", "ERROR", "ACTION_REQUIRED",
           "STARTUP_FAILURE"}
PENDING = {"IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED",
           "EXPECTED"}


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


def is_pr_view(data):
    return isinstance(data, dict) and (
        "state" in data or "statusCheckRollup" in data
    )


def summarize_pr(data):
    """One PR's `gh pr view --json` payload, reduced to what a session acts on."""
    counts = {}
    failing = []
    pending = []
    for check in data.get("statusCheckRollup") or []:
        status = str(check.get("status") or check.get("state") or "").upper()
        conclusion = str(check.get("conclusion") or "").upper()
        name = check.get("name") or check.get("context") or "?"
        if conclusion and status in ("", "COMPLETED"):
            key = conclusion
        else:
            key = status or "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
        if key in FAILING:
            failing.append(name)
        elif key in PENDING:
            pending.append(name)
    summary = {
        key: data[key]
        for key in ("state", "mergeStateStatus", "mergeable", "reviewDecision")
        if data.get(key) not in (None, "")
    }
    summary["checks"] = dict(sorted(counts.items()))
    if failing:
        summary["failing"] = sorted(failing)[:5]
    if pending:
        summary["pending"] = sorted(pending)[:5]
    if isinstance(data.get("reviews"), list):
        verdicts = {}
        for review in data["reviews"]:
            verdict = str(review.get("state") or "UNKNOWN").upper()
            verdicts[verdict] = verdicts.get(verdict, 0) + 1
        summary["reviews"] = dict(sorted(verdicts.items()))
    return summary


def item_identity(item):
    if isinstance(item, dict):
        url = item.get("url") or item.get("web_url")
        if url:
            return url
        return {key: value for key, value in item.items()
                if key not in VOLATILE_KEYS}
    return item


def list_sources(data):
    if isinstance(data, list):
        return {"items": data}
    if isinstance(data, dict):
        return {key: value for key, value in data.items()
                if isinstance(value, list)}
    return {}


def cap(values):
    if len(values) <= MAX_LISTED:
        return values
    return values[:MAX_LISTED] + [f"... and {len(values) - MAX_LISTED} more"]


def data_digest(state):
    """What changed in a state's data since its last report, or None.

    Updates the state's `reported_summary` / `reported_items` bookkeeping in
    place, so the next call compares against what was just reported.
    """
    data = state.get("data")
    if is_pr_view(data):
        summary = summarize_pr(data)
        if summary == state.get("reported_summary"):
            return None
        state["reported_summary"] = summary
        return {"summary": summary}
    if data is None:
        return None
    previous = state.get("reported_items") or {}
    current = {}
    changes = {}
    for source, items in list_sources(data).items():
        keyed = {}
        for item in items:
            identity = item_identity(item)
            keyed[json.dumps(identity, sort_keys=True)] = identity
        current[source] = sorted(keyed)
        before = set(previous.get(source, []))
        added = [keyed[key] for key in sorted(set(keyed) - before)]
        removed = [json.loads(key) for key in sorted(before - set(keyed))]
        if added or removed:
            changes[source] = {"open": len(keyed)}
            if added:
                changes[source]["added"] = cap(added)
            if removed:
                changes[source]["removed"] = cap(removed)
    # A source absent from the data was not checked this poll (its CLI
    # failed or is missing; monitor-open-prs.py records that as an error and
    # leaves the key out), which is not the same as "checked, none open".
    # Carry its last reported set forward instead of reporting every entry
    # removed and then re-added on recovery.
    for source in set(previous) - set(current):
        current[source] = previous[source]
    state["reported_items"] = current
    return {"changes": changes} if changes else None


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
        entry = data_digest(state) or {}
        if has_error:
            entry["error"] = state["error"]
        elif state.get("reported_error") is not None:
            # A reported error clearing is itself news, even when the data
            # it hid turns out unchanged.
            entry["recovered_from"] = state["reported_error"]
        state["reported_error"] = state.get("error")
        temporary = f"{path}.{os.getpid()}.tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True)
        os.replace(temporary, path)
        if not entry:
            continue
        entry["url"] = state.get("url") or name
        if state.get("error_streak"):
            entry["error_streak"] = state["error_streak"]
        updates.append(entry)
    if updates:
        print("Detached PR-monitor update (inspect and act if needed): "
              + json.dumps(updates, sort_keys=True))


if __name__ == "__main__":
    main()
