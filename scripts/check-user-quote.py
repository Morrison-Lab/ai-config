#!/usr/bin/env python3
"""Decide whether a phrase attributed to the user was ever typed by the user.

The instrument for `shared/writing/citations.md`'s
"The user's own words are on disk" section, which carries the argument for why
this is a classifier rather than a grep.  What follows is what the code does.

`message.role == "user"` is a transport role, so a user-role record is sorted
three ways rather than two:

  HUMAN         `origin.kind == "human"`, the harness's own label
  EXCLUDED      a flag (`isMeta`, `isCompactSummary`, `isSidechain`,
                `verifiedSlackHumanTurn`), a non-external `userType`, a
                tool-result carrier, an empty block, an anchored harness
                envelope, or a named non-human `origin.kind`
  UNATTRIBUTED  no `origin` at all, or `origin.kind == "unclassified"`

UNATTRIBUTED covers two cases, and the second is why it cannot simply be
excluded.  A record may carry no `origin` at all -- the CLI itself only
*presumes* human there -- and a record the harness has demoted carries
`origin.kind == "unclassified"`, which a fork, relay, or resume path produces
from a genuinely human turn.  Excluding either would answer "the user never
said it" about a sentence the user typed.  So both are candidates, reported and
never certified, and `--allow-unattributed` accepts them at exit 3.

Classification is per BLOCK, not per record.  A human-labelled record can carry
an injected second block, and filing that block's match under the record's
verdict is what certifies harness prose as the user's words -- measured
2026-08-28, on this file's own test fixture.  The envelope test therefore runs
against whichever block matched, start-anchored so a turn quoting an envelope
tag stays a turn.

Exit 0 found in a human-labelled block; 1 absent; 2 no such block was
available to search -- a missing root, an unreadable file, an empty phrase, an
unexpected exception, or a transcript carrying no labels; 3 found only in an
unattributed block, with `--allow-unattributed` passed.  Per
`shared/principles/fail-fast.md`, exit 2 is kept distinct from exit 1 so that a
degraded read can never be reported as an absence, and exit 3 from exit 0 so a
scripted caller cannot mistake the weaker reading for a certified one.
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
    # Stamped origin.kind == "human" by the harness, but relayed from a shared
    # channel -- so it is somebody's typed turn and not necessarily this user's.
    ("verifiedSlackHumanTurn", "relayed channel turn, possibly another person"),
)

# origin.kind values the harness uses for something other than a typed turn.
# "unclassified" is deliberately absent: the CLI demotes a human turn to it on
# fork, relay and resume paths, so excluding it would deny a real quotation.
NON_HUMAN_ORIGINS = (
    "channel", "peer", "coordinator", "observer", "observer-activity",
    "auto-continuation", "task-notification",
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
    """Each prose block separately, so classify_block can judge the one that matched."""
    content = message.get("content")
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [b.get("text") or "" for b in content
            if isinstance(b, dict) and b.get("type") == "text"]


def classify_record(record: dict) -> Tuple[str, str]:
    """Record-level verdict, before any block is examined."""
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
    if not [b for b in text_blocks(message) if b.strip()]:
        return EXCLUDED, "no prose"

    origin = record.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    if kind == "human":
        return HUMAN, ""
    if kind in NON_HUMAN_ORIGINS:
        return EXCLUDED, f"origin.kind={kind}"
    # Absent, "unclassified", or a value this table has not seen.
    return UNATTRIBUTED, f"origin.kind={kind}" if kind else "no origin.kind label"


def classify_block(record_kind: str, block: str) -> Tuple[str, str]:
    """Per-block verdict.

    A human-labelled record can carry an injected block, so the record's verdict
    is a ceiling rather than an answer: the envelope test runs against the block
    that actually matched.
    """
    stripped = block.lstrip()
    for prefix in ENVELOPE_PREFIXES:
        if stripped.startswith(prefix):
            return EXCLUDED, "harness envelope"
    if not block.strip():
        return EXCLUDED, "empty block"
    return record_kind, ""


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
            # searched space, and rglob's ordering means the failure can precede
            # the file holding a genuine hit.
            result.unreadable.append(f"{path.name}: {exc.strerror or exc}")
            continue
        try:
            with handle:
                for line in handle:
                    _scan_line(line, path.name, target, show_excluded, result)
        except OSError as exc:
            result.unreadable.append(f"{path.name}: {exc.strerror or exc}")
    return result


def _scan_line(line: str, name: str, target: str, show_excluded: bool, result: Scan) -> None:
    line = line.strip()
    if not line:
        return
    result.records += 1
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        result.unparseable += 1
        return
    if not isinstance(record, dict):
        result.unparseable += 1
        return
    message = record.get("message")
    if not isinstance(message, dict) or message.get("role") != "user":
        return
    result.user_records += 1
    record_kind, record_reason = classify_record(record)
    if record_kind == HUMAN:
        result.human += 1
    elif record_kind == UNATTRIBUTED:
        result.unattributed += 1
    if not target:
        return
    for block in text_blocks(message):
        if not isinstance(block, str) or target not in norm(block):
            continue
        kind, block_reason = classify_block(record_kind, block)
        text = block.strip()
        if kind == HUMAN:
            result.hits.append((name, text))
        elif kind == UNATTRIBUTED:
            result.uncertified.append((name, text))
        elif show_excluded:
            result.near_misses.append((name, block_reason or record_reason, text[:160]))


def status(result: Scan, allow_unattributed: bool) -> str:
    if result.hits:
        return "found"
    if allow_unattributed and result.uncertified:
        # Deliberately not "found": a scripted caller branching on the exit code
        # must not read the weaker reading as a certified one.
        return "accepted-unattributed"
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
    if result.uncertified:
        print("\nAn unattributed match is one the harness never labelled a human turn. "
              "It is a candidate, not evidence. Do not quote it without a second source.")
    outcome = status(result, allow_unattributed)
    if outcome == "unsearchable":
        if result.unreadable:
            print("\nPart of the space could not be read, so an absence here is not established.")
        else:
            print("\nNo human-labelled turns were found at all -- this is an unsearched "
                  "space, not an absence. Pass --root, or --allow-unattributed to fall "
                  "back on the weaker heuristic.")
    elif outcome == "absent":
        print(f"\nNot present in any of {result.human} human-labelled turn(s). Do not quote it.")


def _payload(outcome: str, root: Path, result: Scan, reason: str = "") -> dict:
    """One schema for every branch, including the ones that could not search."""
    body = {
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
    }
    if reason:
        body["reason"] = reason
    return body


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phrase", help="the sentence you are about to attribute to the user")
    parser.add_argument("--root", help="transcript directory "
                        "(default: $CLAUDE_CONFIG_DIR/projects, else ~/.claude/projects)")
    parser.add_argument("--show-excluded", action="store_true",
                        help="also report matches inside excluded records, naming why each was excluded")
    parser.add_argument("--allow-unattributed", action="store_true",
                        help="accept a match in an unattributed block, exiting 3 rather "
                             "than 0. This readmits the failure the tool exists to "
                             "prevent -- an assistant-written dispatch brief is "
                             "unattributed -- so treat exit 3 as a lead, not a source.")
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
            if args.as_json:
                # Same keys as every other branch, on stdout: a caller piping to
                # jq must not hit a parse error on the one branch that means
                # "I could not look".
                print(json.dumps(_payload("unsearchable", root, Scan(), reason=message), indent=2))
            else:
                print(message, file=sys.stderr)
            return 2

    try:
        result = scan(root, args.phrase, args.show_excluded)
    except Exception as exc:  # noqa: BLE001 -- mapped to exit 2, never to 1
        # Python's default status for an uncaught exception is 1, which this
        # tool documents as "absent". A crash is a search that did not happen,
        # so it exits 2 and says what failed rather than answering the question.
        message = (f"check-user-quote failed before it could answer: "
                   f"{type(exc).__name__}: {exc}")
        if args.as_json:
            print(json.dumps(_payload("unsearchable", root, Scan(), reason=message), indent=2))
        else:
            print(message, file=sys.stderr)
        return 2
    outcome = status(result, args.allow_unattributed)

    if args.as_json:
        print(json.dumps(_payload(outcome, root, result), indent=2))
    else:
        report(result, root, args.allow_unattributed)

    return {"found": 0, "absent": 1, "unsearchable": 2, "accepted-unattributed": 3}[outcome]


if __name__ == "__main__":
    sys.exit(main())
