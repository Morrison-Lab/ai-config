#!/usr/bin/env python3
"""Decide whether a phrase attributed to the user was ever typed by the user.

The instrument for `shared/writing/citations.md`'s
"The user's own words are on disk" section.  Every quote-fidelity check in
that file needs a fetchable source, and a sentence attributed to the user in
conversation looks like it has none -- so the check gets skipped, and a
reconstruction goes out inside quotation marks.

It has a source.  Claude Code writes every turn to a JSONL transcript, and 29
hooks in this repository already parse one.  What makes the lookup non-trivial
is that `message.role == "user"` is a TRANSPORT role rather than an authorship
claim.  The same role carries harness continuations, stop-hook output, skill
bodies, task notifications, tool results, compaction summaries, and -- inside a
subagent's own transcript -- the brief the ASSISTANT wrote to dispatch it.
Matching any of those and reporting a hit is the artifact substitution the
section exists to reject, dressed up as a verification.

So the classifier, not the search, is what carries this check.  A record is a
typed turn only when every exclusion below fails.

Two failures are deliberately kept distinct, per
`shared/principles/fail-fast.md`:

  exit 1  searched successfully, no typed turn contains the phrase
  exit 2  could not establish a search space at all -- no transcript root, no
          files, or no typed turns anywhere in them

Collapsing them is what turns "I could not look" into "the user never said
it", which is the stronger claim and the wrong one.  A run therefore always
reports what it examined (files, records, typed turns, unparseable lines)
alongside what it found, so a zero is never mistaken for a detector that never
engaged.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# Harness envelopes delivered as user-role records.  Anchored at the start of
# the stripped body: a message merely QUOTING one of these tags (this file's
# own docs do) is still a typed turn.
ENVELOPE_PREFIXES = (
    "<task-notification>",
    "<system-reminder>",
    "<wake ",
    "<command-name>",
    "This session is being continued",
    "Caveat: The messages below were generated",
)

# Excluded because the body is the assistant's own prose, not the user's.
FLAG_EXCLUSIONS = (
    ("isCompactSummary", "compaction summary"),
    ("isMeta", "harness injection"),
    ("isSidechain", "subagent transcript"),
)


def norm(s: str) -> str:
    """Whitespace and inline markup collapsed, per this corpus's substring test."""
    return re.sub(r"[\s`*_]+", " ", s).strip().lower()


def transcript_root(explicit: Optional[str]) -> Optional[Path]:
    """Where Claude Code keeps transcripts, or None on an agent that has none."""
    if explicit:
        root = Path(explicit).expanduser()
        return root if root.is_dir() else None
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    root = base / "projects"
    return root if root.is_dir() else None


def record_text(message: dict) -> str:
    """The record's prose, or "" when it carries no prose at all."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return " ".join(parts)


def classify(record: dict) -> Tuple[str, str]:
    """('typed', '') for a turn the user actually typed, else ('excluded', why)."""
    message = record.get("message") or {}
    if message.get("role") != "user":
        return "excluded", "not a user-role record"
    for key, reason in FLAG_EXCLUSIONS:
        if record.get(key):
            return "excluded", reason
    user_type = record.get("userType")
    if user_type is not None and user_type != "external":
        return "excluded", f"userType={user_type}"
    content = message.get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return "excluded", "tool result"
    body = record_text(message).strip()
    if not body:
        return "excluded", "no prose"
    for prefix in ENVELOPE_PREFIXES:
        if body.startswith(prefix):
            return "excluded", "harness envelope"
    return "typed", ""


class Scan:
    def __init__(self) -> None:
        self.files = 0
        self.records = 0
        self.user_records = 0
        self.typed = 0
        self.unparseable = 0
        self.hits: List[Tuple[str, str]] = []
        self.near_misses: List[Tuple[str, str, str]] = []


def scan(root: Path, needle: str, show_excluded: bool) -> Scan:
    result = Scan()
    target = norm(needle)
    for path in sorted(root.rglob("*.jsonl")):
        result.files += 1
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                result.records += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    # Counted and reported rather than swallowed: a live session
                    # appends while this reads, so a torn final line is expected.
                    # Aborting here would end the scan and read as "not found".
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
                body = record_text(message)
                if kind == "typed":
                    result.typed += 1
                    if target and target in norm(body):
                        result.hits.append((path.name, body.strip()))
                elif show_excluded and target and target in norm(body):
                    result.near_misses.append((path.name, reason, body.strip()[:120]))
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phrase", help="the sentence you are about to attribute to the user")
    parser.add_argument("--root", help="transcript directory (default: $CLAUDE_CONFIG_DIR/projects or ~/.claude/projects)")
    parser.add_argument("--show-excluded", action="store_true",
                        help="also report matches inside excluded records, with the reason each was excluded")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    root = transcript_root(args.root)
    if root is None:
        message = (
            "No Claude Code transcript root found. This check needs one; on another "
            "agent, or with transcripts elsewhere, pass --root."
        )
        print(json.dumps({"status": "unsearchable", "reason": message}) if args.as_json else message,
              file=sys.stderr)
        return 2

    result = scan(root, args.phrase, args.show_excluded)

    if args.as_json:
        print(json.dumps({
            "status": "found" if result.hits else ("unsearchable" if result.typed == 0 else "absent"),
            "root": str(root),
            "files": result.files,
            "records": result.records,
            "user_records": result.user_records,
            "typed_turns": result.typed,
            "unparseable_lines": result.unparseable,
            "hits": [{"file": f, "text": t} for f, t in result.hits],
            "near_misses": [{"file": f, "excluded_as": r, "text": t} for f, r, t in result.near_misses],
        }, indent=2))
    else:
        # The search space prints first and unconditionally: a zero below it is
        # only meaningful once a reader can see what was examined to produce it.
        print(f"Searched {result.files} transcript file(s) under {root}")
        print(f"  {result.records} records, {result.user_records} user-role, "
              f"{result.typed} typed turns, {result.unparseable} unparseable line(s)")
        for name, text in result.hits:
            print(f"\nTYPED TURN in {name}:\n  {text}")
        for name, reason, text in result.near_misses:
            print(f"\nEXCLUDED ({reason}) in {name}:\n  {text}")
        if not result.hits:
            if result.typed == 0:
                print("\nNo typed turns found at all -- this is an unsearched space, not an absence.")
            else:
                print(f"\nNot present in any of {result.typed} typed turn(s). Do not quote it.")
        if result.near_misses and not result.hits:
            print("A match inside an excluded record is the assistant's own text, not the user's.")

    if result.typed == 0:
        return 2
    return 0 if result.hits else 1


if __name__ == "__main__":
    sys.exit(main())
