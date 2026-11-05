#!/usr/bin/env python3
"""Fail-closed check of the model and effort the CURRENT session is running.

`select-model` and `assess-model-fit` recommend a tier; nothing verified the
tier actually running (ai-config#879). A session cannot self-report it by
introspection, so this reads the one source that records it: the session's own
transcript, `<projects-dir>/<project-slug>/<session-id>.jsonl`, whose assistant
records carry `message.model`, `requestedModel` and `effort`.

The posture is fail-closed, taken from `scdenney/open-science-skills`'
`check-lead-runtime.sh` (pattern only): the script prints `runtime OK` only
when every step below held, and exits non-zero otherwise.

  1. The session id comes from `--session-id` or `CLAUDE_CODE_SESSION_ID`.
     It is never guessed from "the newest file", which can be another session's.
  2. Exactly one transcript must match that id: zero or several is a stop (2).
  3. The LATEST assistant record decides the model and effort, so a mid-session
     `/model` switch is seen, and earlier turns are reported but not trusted.
  4. A record whose `requestedModel` differs from `message.model` is a reroute:
     the model that answered is not the model that was asked for (2).
  5. A missing model or effort is a stop (2), not a default.
  6. With `--expect-model` / `--expect-effort`, a mismatch is exit 1. Both take
     a comma-separated list of accepted values, and neither has a built-in
     default, so a caller states the tier it requires.

Exit codes: 0 ok, 1 expectation mismatch, 2 could not establish the runtime.
Sidechain (subagent) records are ignored: they run other models by design.

Usage:
    python3 scripts/check-session-runtime.py
    python3 scripts/check-session-runtime.py --expect-model claude-opus-5 \
        --expect-effort high,xhigh
"""
import argparse
import json
import os
import sys
from pathlib import Path


def find_transcript(projects_dir, session_id):
    """The single transcript for `session_id`, or an error string."""
    matches = sorted(Path(projects_dir).glob(f"*/{session_id}.jsonl"))
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, f"no transcript for session {session_id} under {projects_dir}"
    return None, f"{len(matches)} transcripts match session {session_id}: {[str(m) for m in matches]}"


def read_runtime(path):
    """Latest model, requested model and effort, plus every model seen."""
    models_seen = []
    latest = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict) or record.get("isSidechain"):
                continue
            message = record.get("message")
            model = message.get("model") if isinstance(message, dict) else None
            if not model or model == "<synthetic>":
                continue
            if not models_seen or models_seen[-1] != model:
                models_seen.append(model)
            latest = {
                "model": model,
                "requested": record.get("requestedModel"),
                "effort": record.get("effort"),
            }
    return latest, models_seen


def accepted(raw):
    return [v.strip() for v in raw.split(",") if v.strip()] if raw else []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--session-id", default=os.environ.get("CLAUDE_CODE_SESSION_ID"),
                        help="session id (default: $CLAUDE_CODE_SESSION_ID)")
    parser.add_argument("--projects-dir", default=os.path.expanduser("~/.claude/projects"),
                        help="Claude Code projects directory (default: ~/.claude/projects)")
    parser.add_argument("--expect-model", default="", help="accepted model id(s), comma-separated")
    parser.add_argument("--expect-effort", default="", help="accepted effort(s), comma-separated")
    args = parser.parse_args(argv)

    if not args.session_id:
        print("cannot establish runtime: no session id (set CLAUDE_CODE_SESSION_ID or pass --session-id)")
        return 2
    path, error = find_transcript(args.projects_dir, args.session_id)
    if error:
        print(f"cannot establish runtime: {error}")
        return 2
    latest, models_seen = read_runtime(path)
    if latest is None:
        print(f"cannot establish runtime: no assistant record with a model in {path}")
        return 2
    if not latest["effort"]:
        print(f"cannot establish runtime: latest record names model {latest['model']} but no effort")
        return 2
    if latest["requested"] and latest["requested"] != latest["model"]:
        print(f"cannot establish runtime: rerouted, asked for {latest['requested']} but {latest['model']} answered")
        return 2

    want_models, want_efforts = accepted(args.expect_model), accepted(args.expect_effort)
    if want_models and latest["model"] not in want_models:
        print(f"runtime MISMATCH: model {latest['model']}, expected one of {want_models}")
        return 1
    if want_efforts and latest["effort"] not in want_efforts:
        print(f"runtime MISMATCH: effort {latest['effort']}, expected one of {want_efforts}")
        return 1
    print(f"runtime OK: {latest['model']} at {latest['effort']}")
    if len(models_seen) > 1:
        print(f"note: models seen in order this session: {models_seen}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
