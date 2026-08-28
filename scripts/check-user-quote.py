#!/usr/bin/env python3
"""Decide whether a phrase attributed to the user was ever typed by the user.

The instrument for `shared/writing/citations.md`'s
"The user's own words are on disk" section, which carries the argument for why
this is a classifier rather than a grep.  What follows is what the code does.

`message.role == "user"` is a transport role, so a user-role record is sorted
three ways rather than two:

  HUMAN         `origin.kind == "human"` -- the harness's own label,
                authoritative in both directions when present
  EXCLUDED      a flag (`isMeta`, `isCompactSummary`, `isSidechain`), a
                non-external `userType`, a tool-result carrier, an empty body,
                an anchored harness envelope, or any other `origin.kind`
  UNATTRIBUTED  survives every exclusion and carries no label

UNATTRIBUTED exists because the exclusion list is hand-maintained against one
snapshot of the transcript format.  An assistant-written dispatch brief was
measured passing all of it on 2026-08-28, so a match there is reported as a
candidate and never as a hit unless `--allow-unattributed` is passed.

Text blocks are searched separately rather than joined: an injected block
riding on a genuine turn would otherwise become searchable through that turn's
classification, and the envelope test is start-anchored so that a turn quoting
an envelope tag stays a turn.

Exit 0 found, 1 absent, 2 no human-labelled turn was available to search --
including a missing root, an unreadable file, and an empty phrase.  Per
`shared/principles/fail-fast.md` the last is kept distinct from the second so
a degraded read cannot be reported as an absence.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Harness envelopes delivered as user-role records. Matched against the START
# of the first text block only: a turn that merely quotes one of these tags
# (this file's own tests do) must stay a turn, for the same reason
# hooks/no-misattributed-quote.py exempts a message reporting a misquote.
ENVELOPE_PREFIXES = (
    "<task-notification>",
    "<system-reminder>",
    "<wake ",
    "<command-name>",
    "This session is being continued",
    "Caveat: The messages below were generated",
    "The coordinator sent a message while you were working",
)

FLAG_EXCLUSIONS = (
    ("isCompactSummary", "compaction summary"),
    ("isMeta", "harness injection"),
    ("isSidechain", "subagent transcript"),
)

HUMAN = "human"
UNATTRIBUTED = "unattributed"
EXCLUDED = "excluded"


def norm(s: str) -> str:
    """Whitespace and inline markup collapsed, per this corpus's substring test."""
    return re.sub(r"[\s`*_]+", " ", s).strip().lower()


def default_root() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return base / "projects"


def text_blocks(message: dict) -> List[str]:
    """Each prose block separately.

    Deliberately NOT joined: an injected block riding on a genuine turn would
    otherwise become searchable through that turn's own classification, and a
    start-anchored envelope test cannot see a second block at all.
    """
    content = message.get("content")
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"]


def classify(record: dict) -> Tuple[str, str]:
    """HUMAN, UNATTRIBUTED, or (EXCLUDED, why)."""
    message = record.get("message") or {}
    if message.get("role") != "user":
        return EXCLUDED, "not a user-role record"
    for key, reason in FLAG_EXCLUSIONS:
        if record.get(key):
            return EXCLUDED, reason
    user_type = record.get("userType")
    if user_type is not None and user_type != "external":
        return EXCLUDED, f"userType={user_type}"
    content = message.get("content")
    if isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    ):
        return EXCLUDED, "tool result"
    blocks = [b for b in text_blocks(message) if b.strip()]
    if not blocks:
        return EXCLUDED, "no prose"
    first = blocks[0].lstrip()
    for prefix in ENVELOPE_PREFIXES:
        if first.startswith(prefix):
            return EXCLUDED, "harness envelope"

    origin = record.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    if kind is not None:
        # Authoritative when present, in both directions.
        return (HUMAN, "") if kind == "human" else (EXCLUDED, f"origin.kind={kind}")
    return UNATTRIBUTED, "no origin.kind label"


class Scan:
    def __init__(self) -> None:
        self.files = 0
        self.records = 0
        self.user_records = 0
        self.human = 0
        self.unattributed = 0
        self.unparseable = 0
        self.unreadable: List[str] = []
        self.hits: List[Tuple[str, str]] = []
        self.uncertified: List[Tuple[str, str]] = []
        self.near_misses: List[Tuple[str, str, str]] = []


def scan(root: Path, needle: str, show_excluded: bool) -> Scan:
    result = Scan()
    target = norm(needle)
    for path in sorted(root.rglob("*.jsonl")):
        result.files += 1
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError as exc:
            # Never swallowed into an absence: an unreadable file shrinks the
            # searched space, and rglob's ordering means the crash can precede
            # the file holding a genuine hit.
            result.unreadable.append(f"{path.name}: {exc.strerror or exc}")
            continue
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                result.records += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    result.unparseable += 1
                    continue
                if not isinstance(record, dict):
                    result.unparseable += 1
                    continue
                message = record.get("message")
                if not isinstance(message, dict) or message.get("role") != "user":
                    continue
                result.user_records += 1
                kind, reason = classify(record)
                if kind == HUMAN:
                    result.human += 1
                elif kind == UNATTRIBUTED:
                    result.unattributed += 1
                if not target:
                    continue
                matched = next((b for b in text_blocks(message) if target in norm(b)), None)
                if matched is None:
                    continue
                if kind == HUMAN:
                    result.hits.append((path.name, matched.strip()))
                elif kind == UNATTRIBUTED:
                    result.uncertified.append((path.name, matched.strip()))
                elif show_excluded:
                    result.near_misses.append((path.name, reason, matched.strip()[:160]))
    return result


def status(result: Scan, allow_unattributed: bool) -> str:
    if result.hits or (allow_unattributed and result.uncertified):
        return "found"
    searchable = result.human or (allow_unattributed and result.unattributed)
    if not searchable or result.unreadable:
        return "unsearchable"
    return "absent"


def report(result: Scan, root: Path, allow_unattributed: bool) -> None:
    # The search space prints first and unconditionally: a zero below it means
    # nothing until a reader can see what was examined to produce it.
    print(f"Searched {result.files} transcript file(s) under {root}")
    print(f"  {result.records} records, {result.user_records} user-role, "
          f"{result.human} human-labelled, {result.unattributed} unattributed, "
          f"{result.unparseable} unparseable line(s)")
    for problem in result.unreadable:
        print(f"  UNREADABLE {problem}")
    for name, text in result.hits:
        print(f"\nHUMAN TURN in {name}:\n  {text}")
    for name, text in result.uncertified:
        label = "UNATTRIBUTED MATCH" if not allow_unattributed else "UNATTRIBUTED MATCH (accepted)"
        print(f"\n{label} in {name}:\n  {text}")
    for name, reason, text in result.near_misses:
        print(f"\nEXCLUDED ({reason}) in {name}:\n  {text}")
    if result.uncertified and not allow_unattributed:
        print("\nAn unattributed match carries no origin.kind label, so the harness never "
              "called it a human turn. It is a candidate, not evidence. Do not quote it.")
    if status(result, allow_unattributed) == "unsearchable":
        if result.unreadable:
            print("\nPart of the space could not be read, so an absence here is not established.")
        else:
            print("\nNo human-labelled turns were found at all -- this is an unsearched "
                  "space, not an absence. Pass --root, or --allow-unattributed to fall "
                  "back on the weaker heuristic.")
    elif status(result, allow_unattributed) == "absent":
        print(f"\nNot present in any of {result.human} human-labelled turn(s). Do not quote it.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phrase", help="the sentence you are about to attribute to the user")
    parser.add_argument("--root", help="transcript directory "
                        "(default: $CLAUDE_CONFIG_DIR/projects, else ~/.claude/projects)")
    parser.add_argument("--show-excluded", action="store_true",
                        help="also report matches inside excluded records, naming why each was excluded")
    parser.add_argument("--allow-unattributed", action="store_true",
                        help="accept a match in a record carrying no origin.kind label "
                             "(a weaker heuristic; the output says so)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit the result as JSON, with the same counts")
    args = parser.parse_args(argv)

    if not norm(args.phrase):
        # A usage error, never an absence: an unset shell variable expanding to
        # "" must not answer "the user never said it".
        parser.error("phrase is empty after normalization; nothing to search for")

    if args.root:
        root = Path(args.root).expanduser()
        if not root.is_dir():
            parser.error(f"--root {args.root} is not a directory")
    else:
        root = default_root()
        if not root.is_dir():
            message = (f"No transcript root at {root}. This check needs one; pass --root, "
                       "or set CLAUDE_CONFIG_DIR. On an agent that keeps no transcripts the "
                       "source genuinely is unavailable.")
            print(json.dumps({"status": "unsearchable", "reason": message})
                  if args.as_json else message, file=sys.stderr)
            return 2

    result = scan(root, args.phrase, args.show_excluded)
    outcome = status(result, args.allow_unattributed)

    if args.as_json:
        print(json.dumps({
            "status": outcome,
            "root": str(root),
            "files": result.files,
            "records": result.records,
            "user_records": result.user_records,
            "human_turns": result.human,
            "unattributed_records": result.unattributed,
            "unparseable_lines": result.unparseable,
            "unreadable_files": result.unreadable,
            "hits": [{"file": f, "text": t} for f, t in result.hits],
            "unattributed_matches": [{"file": f, "text": t} for f, t in result.uncertified],
            "near_misses": [{"file": f, "excluded_as": r, "text": t} for f, r, t in result.near_misses],
        }, indent=2))
    else:
        report(result, root, args.allow_unattributed)

    return {"found": 0, "absent": 1, "unsearchable": 2}[outcome]


if __name__ == "__main__":
    sys.exit(main())
