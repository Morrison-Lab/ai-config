#!/usr/bin/env python3
"""Run one advisor consult read-only, between two seat checks.

Step 3 of skills/advisor/SKILL.md runs the call read-only with `model` and
`effort` pinned. For `opencode` this sends one streamed chat completion with
no `tools` key, so the advisor can only answer, through curl (the cloud proxy
refuses Python's urllib, skills/delegate-to-opencode/SKILL.md), with the
effort as `reasoning_effort`. For `agy` it runs `agy --mode plan --print=...`
(memories/antigravity.md). scripts/check-advisor-seat.py runs before the call
and, for `opencode`, again on the model the reply names. `agy --print` names
no model, so that seat is reported unverified rather than checked.

Answer on stdout, seat label on stderr. Exit 2: refused seat or bad argument;
exit 1: engine failure. `--dry-run` calls nothing. See ai-config#884.
"""

import argparse
import importlib.util
import json
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check_advisor_seat", Path(__file__).with_name("check-advisor-seat.py")
)
seat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seat)

OPENCODE_URL = "https://opencode.ai/zen/go/v1/chat/completions"


class EngineError(Exception):
    """The engine call failed or returned no answer."""


def opencode_payload(model, effort, briefing):
    """The request body: no `tools` key, so the reply can only be text."""
    return {"model": model, "stream": True, "reasoning_effort": effort,
            "messages": [{"role": "user", "content": briefing}]}


def opencode_argv(timeout, session_id):
    """curl reads the body from stdin, so the briefing never hits argv."""
    return ["curl", "-sS", "-N", "--fail-with-body", "--max-time",
            str(timeout), OPENCODE_URL, "-H", "Content-Type: application/json",
            "-H", f"x-opencode-session: {session_id}", "--data-binary", "@-"]


def agy_argv(model, effort, briefing, timeout):
    """`--print=` with `=`: a bare `--print` takes the next flag as prompt."""
    return ["agy", "--model", model, "--effort", effort, "--mode", "plan",
            "--print-timeout", f"{timeout}s", f"--print={briefing}"]


def parse_sse(text):
    """Return (answer, reported model) from a streamed chat completion."""
    parts, reported = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if chunk == "[DONE]":
            break
        try:
            event = json.loads(chunk)
        except json.JSONDecodeError as exc:
            raise EngineError(f"malformed stream event {chunk[:200]!r}") from exc
        reported = event.get("model") or reported
        for choice in event.get("choices") or []:
            parts.append((choice.get("delta") or {}).get("content") or "")
    answer = "".join(parts)
    if not answer.strip():
        raise EngineError(f"no answer in the reply: {text[:500]!r}")
    return answer, reported


def consult(args, briefing, run=subprocess.run):
    """Check the seat, call the engine, and check the seat again.

    `run` is subprocess.run's interface, injected so tests need no network.
    Returns the answer; raises seat.Refusal or EngineError.
    """
    check = dict(
        caller_model=args.caller_model, engine=args.engine, model=args.model,
        effort=args.effort, allow_same_family=args.allow_same_family,
        prefixes={**seat.FAMILY_PREFIXES, **dict(args.family)},
    )
    label = seat.check_seat(**check)
    if args.engine == "opencode":
        argv = opencode_argv(args.timeout, uuid.uuid4())
        body = json.dumps(opencode_payload(args.model, args.effort, briefing))
    else:
        argv = agy_argv(args.model, args.effort, briefing, args.timeout)
        body = None
    if args.dry_run:
        print(f"seat: {label}", file=sys.stderr)
        if body is None:
            return shlex.join([*argv[:-1], "--print=<briefing>"])
        return shlex.join(argv) + " < <request json>"
    proc = run(argv, input=body, capture_output=True, text=True,
               timeout=args.timeout + 60)
    if proc.returncode != 0:
        raise EngineError(
            f"{argv[0]} exited {proc.returncode}: "
            f"{(proc.stderr or proc.stdout)[:500]}"
        )
    if args.engine == "agy":
        answer = proc.stdout
        if not answer.strip():
            raise EngineError("agy printed no answer")
        print(f"seat: {label}; unverified: agy --print does not name the "
              "model that answered", file=sys.stderr)
        return answer
    answer, reported = parse_sse(proc.stdout)
    if not reported:
        raise EngineError("the reply names no model, so the seat is unverified")
    label = seat.check_seat(reported_model=reported, **check)
    print(f"seat: {label}; answered by {reported}", file=sys.stderr)
    return answer


def main(argv=None, run=subprocess.run):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for flag in ("--caller-model", "--model", "--effort"):
        ap.add_argument(flag, required=True)
    ap.add_argument("--engine", required=True, choices=("opencode", "agy"))
    ap.add_argument("--briefing", required=True, type=Path,
                    help="the self-contained briefing file (skill step 2)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds")
    ap.add_argument("--allow-same-family", action="store_true",
                    help="accept a same-family seat, labelled weaker")
    ap.add_argument("--family", type=seat._family_pair, action="append",
                    default=[], metavar="PREFIX=FAMILY",
                    help="add or override a model-name prefix (repeatable)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    briefing = args.briefing.read_text(encoding="utf-8")
    if not briefing.strip():
        print("refused: the briefing is empty", file=sys.stderr)
        return 2
    try:
        print(consult(args, briefing, run=run))
    except seat.Refusal as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except (EngineError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"engine failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
