#!/usr/bin/env python3
"""Flag project threads whose last reply announced work and then went quiet.

ai-config#5054, layer 4 of the defense-in-depth rule (ai-config#5051).  The
session-side hooks (the announced-start Stop hook, the post_message deny) can
all be bypassed or absent; this check runs from outside the thread, on the
coordinator's schedule, so a thread that announced work and stopped is nudged
within minutes instead of when the person notices (2026-10-30: 80 minutes of
silence; 2026-11-07: the CI thread).

Input is a JSON list of thread snapshots on stdin or from --file:

  [{"id": "cmsg_...", "title": "...", "last_reply": "<text of the last reply>",
    "last_activity": "2026-11-07T10:00:00Z", "state": "working"}, ...]

`last_activity` is the newest of the last reply and the last tool activity.
A thread is flagged when all hold:

  - its state is `working` (a blocked, done or stopped thread is not quiet);
  - its last reply ends on an unconditional immediate-start sentence, judged
    by `offending_sentence` imported from the announced-start Stop hook so the
    two never drift;
  - `last_activity` is at least --quiet-minutes (default 10) before --now.

Output is one JSON object per flagged thread, naming the announcement, so the
coordinator can wake the thread with a nudge that quotes it.

Exit codes: 0 nothing flagged, 1 at least one flagged, 2 bad input or an empty
snapshot list (a check that examined nothing must not pass).
"""
import argparse
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "stop", HERE.parent / "hooks" / "no-announced-start-without-starting.py")
stop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stop)


def parse_time(text):
    """Parse an ISO time; raise ValueError unless it carries a UTC offset.

    A naive time cannot be subtracted from an aware one, so accepting it here
    would crash later with TypeError and Python's exit 1, the "flagged" code.
    """
    parsed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"time {text!r} has no UTC offset (end it with Z or +00:00)")
    return parsed


REQUIRED = ("id", "state", "last_reply", "last_activity")


def check_records(threads):
    """Raise ValueError unless every snapshot is an object with the required keys.

    Checked before any record is examined, so a malformed record exits 2 (bad
    input) and never crashes with Python's default exit 1, which means
    "flagged"; nothing is printed for a list that cannot be trusted.
    """
    if not isinstance(threads, list):
        raise ValueError("snapshots must be a JSON list")
    for i, t in enumerate(threads):
        if not isinstance(t, dict):
            raise ValueError(f"snapshot {i} is not an object")
        missing = [k for k in REQUIRED if k not in t]
        if missing:
            raise ValueError(f"snapshot {i} lacks {', '.join(missing)}")
        wrong = [k for k in (*REQUIRED, "title") if k in t and not isinstance(t[k], str)]
        if wrong:
            raise ValueError(f"snapshot {i}: {', '.join(wrong)} must be text")
        parse_time(t["last_activity"])


def quiet_announcers(threads, now, quiet_minutes=10):
    """Snapshots whose last reply announces work and whose activity is stale."""
    flagged = []
    for t in threads:
        if t.get("state") != "working":
            continue
        found = stop.offending_sentence(stop.strip_code(t.get("last_reply") or ""))
        if not found:
            continue
        idle = now - parse_time(t["last_activity"])
        if idle < timedelta(minutes=quiet_minutes):
            continue
        flagged.append({
            "id": t["id"],
            "title": t.get("title", ""),
            "announcement": found[0],
            "idle_minutes": int(idle.total_seconds() // 60),
        })
    return flagged


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--file", help="snapshot JSON (default: stdin)")
    ap.add_argument("--now", help="ISO time to measure idleness from (default: clock)")
    ap.add_argument("--quiet-minutes", type=int, default=10)
    args = ap.parse_args(argv)
    try:
        raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
        threads = json.loads(raw)
        now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not threads:
        print("error: no thread snapshots; the search space is empty", file=sys.stderr)
        return 2
    try:
        check_records(threads)
        flagged = quiet_announcers(threads, now, args.quiet_minutes)
    except Exception as e:  # noqa: BLE001 -- reported loudly, never swallowed
        # Python's default for an uncaught exception is exit 1, the code for
        # "flagged". Any failure to examine the input is bad input (exit 2),
        # whatever shape of defect the check_records list missed.
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    for f in flagged:
        print(json.dumps(f))
    print(f"examined {len(threads)} thread(s), flagged {len(flagged)}", file=sys.stderr)
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
