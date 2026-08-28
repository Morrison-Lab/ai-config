#!/usr/bin/env python3
"""Decide whether a phrase attributed to the user was ever typed by the user.

The instrument for `shared/writing/citations.md`'s
"The user's own words are on disk" section, which carries the argument for why
this is a classifier rather than a grep.  What follows is what the code does.

`message.role == "user"` is a transport role, so a user-role record is sorted
three ways rather than two:

  HUMAN         `origin.kind == "human"`, the harness's own label
  EXCLUDED      a flag, a non-external `userType`, a named non-human
                `origin.kind`, or a transcript marker on an unlabelled record
  UNATTRIBUTED  no `origin`, `origin.kind == "unclassified"`, or a kind this
                table has not seen

Sources for the harness behaviour below, read out of the shipped CLI 2.1.250
binary rather than inferred from a transcript, since a transcript can only show
which values happened to occur on one machine:

  demotion   `if (n.type === "user" && (s == null || s.kind == null ||
              s.kind === "human" || s.kind === "auto-continuation"))
              n.origin = {kind: "unclassified"}`
  human test `O0(o.origin) && o.verifiedSlackHumanTurn !== true`

The demotion is why UNATTRIBUTED cannot simply be excluded: a genuinely human
turn arrives as `unclassified` on the paths that rewrite it.  Excluding it
would answer "the user never said it" about a sentence the user typed.  The
harness's own human test is why `verifiedSlackHumanTurn` is excluded here: a
record so marked is stamped human and relayed, so it is somebody's typed turn
and not necessarily this user's.

Classification is per record; matching is per non-envelope REGION of a block.
A human-labelled record can carry injected text, and can carry it mid-block
rather than at the start -- so well-formed envelopes are cut out of a block
before the phrase is looked for, and a phrase found only inside one is not the
user's.

A closing tag is required, so a turn writing ABOUT a tag stays quotable.  The
one exception is a block that OPENS with an unclosed opener, which is read as a
truncated injection and yields nothing: that denies a quotation a user could
conceivably have typed, and the alternative is certifying harness prose, which
is the failure this tool exists to prevent.

Exit 0 found in a quotable human region; 1 absent; 2 no such region was
available to search -- a missing root, an unreadable file or directory, an
empty phrase, a crash, or a transcript carrying no labels; 3 found only in an
unattributed region, with `--allow-unattributed` passed.  Per
`shared/principles/fail-fast.md`, exit 2 is kept distinct from exit 1 so that a
degraded read can never be reported as an absence, and exit 3 from exit 0 so a
scripted caller cannot mistake the weaker reading for a certified one.

Known limit: a phrase spanning two blocks of one record is not found, because
the blocks are never concatenated. It reports absent, which is the safe
direction.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# Structural harness envelopes. Their CONTENT is never the user's, wherever in
# a block it appears -- an injected reminder appended to a genuine turn is the
# case a start-anchored test misses.
ENVELOPE_TAGS = ("task-notification", "system-reminder", "wake", "command-name")
# A CLOSING tag is required. An unclosed opener is far more likely to be a user
# writing about a tag than a harness injection, which is always well-formed, and
# swallowing to end-of-block there denies a genuine quotation. The truncated-
# injection case is covered separately: a block that STARTS with an unclosed
# opener is treated as an envelope in full.
_ENVELOPE_RX = re.compile(
    r"<(" + "|".join(ENVELOPE_TAGS) + r")\b.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE,
)
_OPENER_RX = re.compile(r"<(" + "|".join(ENVELOPE_TAGS) + r")\b", re.IGNORECASE)

# Prose markers that open a harness-written record. Applied ONLY to a record
# the harness did not label human: they are ordinary English, so a real turn
# can begin with one, and excluding it there would deny a true quotation.
TRANSCRIPT_PREFIXES = (
    "This session is being continued",
    "Caveat: The messages below were generated",
    "The coordinator sent a message while you were working",
)

FLAG_EXCLUSIONS = (
    ("isCompactSummary", "compaction summary"),
    ("isMeta", "harness injection"),
    ("isSidechain", "subagent transcript"),
    ("verifiedSlackHumanTurn", "relayed channel turn, possibly another person"),
)

# origin.kind values the harness uses for something other than a typed turn.
# "unclassified" is deliberately absent -- see the demotion source above.
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
    """Each prose block separately, as a str.

    A non-str `text` field becomes "", which no phrase can match and which
    `_regions` filters out. Returning it as-is would reach `.strip()` and abort
    the whole scan for every query against that root.
    """
    content = message.get("content")
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    out = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        text = block.get("text")
        out.append(text if isinstance(text, str) else "")
    return out


def _regions(block: str) -> List[str]:
    """Non-envelope regions of a block, in order.

    Segments are kept SEPARATE rather than joined, so a phrase can never match
    across the gap a removed envelope left behind -- two fragments of a real
    turn that merely abut once the injection is cut were never contiguous in
    what the user typed, and certifying such a span is the failure this whole
    tool exists to prevent.

    The one special case is a block opening with an UNCLOSED opener, read as a
    truncated injection and yielding nothing. It has to look only at the
    block's own opening, which is why it is tested before the split.
    """
    if _OPENER_RX.match(block.lstrip()) and not _ENVELOPE_RX.match(block.lstrip()):
        return []
    out, last = [], 0
    for match in _ENVELOPE_RX.finditer(block):
        out.append(block[last:match.start()])
        last = match.end()
    out.append(block[last:])
    return [r for r in out if r.strip()]


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

    origin = record.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    if kind == "human":
        return HUMAN, ""
    if kind in NON_HUMAN_ORIGINS:
        return EXCLUDED, f"origin.kind={kind}"

    # Unlabelled or demoted. Only here do the English prose markers apply.
    for block in text_blocks(message):
        stripped = block.lstrip()
        for prefix in TRANSCRIPT_PREFIXES:
            if stripped.startswith(prefix):
                return EXCLUDED, "harness transcript marker"
        break
    return UNATTRIBUTED, f"origin.kind={kind}" if kind else "no origin.kind label"


def quotable(message: dict) -> Iterable[str]:
    """Every region of every block that could carry the user's own words."""
    for block in text_blocks(message):
        for region in _regions(block):
            yield region


class Scan:
    def __init__(self) -> None:
        self.files = 0
        self.records = 0
        self.user_records = 0
        self.human = 0            # quotable human REGIONS, not records
        self.unattributed = 0
        self.unparseable = 0
        self.unreadable: List[str] = []
        self.hits: List[Tuple[str, str]] = []
        self.uncertified: List[Tuple[str, str]] = []
        self.near_misses: List[Tuple[str, str, str]] = []


def _walk(root: Path, result: Scan) -> List[Path]:
    """Every *.jsonl under root, recording directories that could not be read.

    `Path.rglob` swallows a permission error from `scandir`, so an unreadable
    project directory would silently shrink the searched space and be reported
    as an absence.
    """
    found: List[Path] = []

    def onerror(exc: OSError) -> None:
        result.unreadable.append(f"{getattr(exc, 'filename', root)}: {exc.strerror or exc}")

    for dirpath, _dirnames, filenames in os.walk(root, onerror=onerror):
        for name in filenames:
            if name.endswith(".jsonl"):
                found.append(Path(dirpath) / name)
    return sorted(found)


def scan(root: Path, needle: str, show_excluded: bool) -> Scan:
    result = Scan()
    target = norm(needle)
    for path in _walk(root, result):
        result.files += 1
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError as exc:
            # Never swallowed into an absence: an unreadable file shrinks the
            # searched space, and a hit may have been in it.
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
    kind, reason = classify_record(record)
    regions = list(quotable(message))
    # Counted per region, so a human-labelled record whose every block is an
    # envelope contributes nothing searchable -- otherwise "could not search"
    # is reported as "the user never said it".
    if kind == HUMAN:
        result.human += len(regions)
    elif kind == UNATTRIBUTED:
        result.unattributed += len(regions)
    if not target:
        return
    matched = next((r for r in regions if target in norm(r)), None)
    if matched is None:
        if show_excluded and kind != EXCLUDED:
            # It matched nothing quotable; say so only if it matched at all.
            whole = " ".join(text_blocks(message))
            if target in norm(whole):
                result.near_misses.append((name, "inside a harness envelope", whole.strip()[:160]))
        elif show_excluded:
            whole = " ".join(text_blocks(message))
            if target in norm(whole):
                result.near_misses.append((name, reason, whole.strip()[:160]))
        return
    if kind == HUMAN:
        result.hits.append((name, matched.strip()))
    elif kind == UNATTRIBUTED:
        result.uncertified.append((name, matched.strip()))
    elif show_excluded:
        result.near_misses.append((name, reason, matched.strip()[:160]))


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


def _payload(outcome: str, root: Path, result: Scan, reason: str = "") -> dict:
    """One schema for every branch, including the ones that could not search."""
    body = {
        "status": outcome,
        "root": str(root),
        "files": result.files,
        "records": result.records,
        "user_records": result.user_records,
        "human_regions": result.human,
        "unattributed_regions": result.unattributed,
        "unparseable_lines": result.unparseable,
        "unreadable": result.unreadable,
        "hits": [{"file": f, "text": t} for f, t in result.hits],
        "unattributed_matches": [{"file": f, "text": t} for f, t in result.uncertified],
        "near_misses": [{"file": f, "excluded_as": r, "text": t} for f, r, t in result.near_misses],
    }
    if reason:
        body["reason"] = reason
    return body


def report(result: Scan, root: Path, allow_unattributed: bool) -> None:
    # The search space prints first and unconditionally: a zero below it means
    # nothing until a reader can see what was examined to produce it.
    print(f"Searched {result.files} transcript file(s) under {root}")
    print(f"  {result.records} records, {result.user_records} user-role, "
          f"{result.human} quotable human region(s), {result.unattributed} unattributed, "
          f"{result.unparseable} unparseable line(s)")
    for problem in result.unreadable:
        print(f"  UNREADABLE {problem}")
    for name, text in result.hits:
        print(f"\nHUMAN TURN in {name}:\n  {text}")
    for name, text in result.uncertified:
        label = "UNATTRIBUTED MATCH (accepted)" if allow_unattributed else "UNATTRIBUTED MATCH"
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
            print("\nNo quotable human regions were found at all -- this is an unsearched "
                  "space, not an absence. Pass --root, or --allow-unattributed to fall "
                  "back on the weaker reading.")
    elif outcome == "absent":
        print(f"\nNot present in any of {result.human} quotable human region(s). Do not quote it.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phrase", help="the sentence you are about to attribute to the user")
    parser.add_argument("--root", help="transcript directory "
                        "(default: $CLAUDE_CONFIG_DIR/projects, else ~/.claude/projects)")
    parser.add_argument("--show-excluded", action="store_true",
                        help="also report matches outside quotable regions, naming why each was excluded")
    parser.add_argument("--allow-unattributed", action="store_true",
                        help="accept a match in an unattributed region, exiting 3 rather "
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
                print(json.dumps(_payload("unsearchable", root, Scan(), reason=message), indent=2))
            else:
                print(message, file=sys.stderr)
            return 2

    try:
        result = scan(root, args.phrase, args.show_excluded)
    except Exception as exc:  # noqa: BLE001 -- mapped to exit 2, never to 1
        # Python's default status for an uncaught exception is 1, which this
        # tool documents as "absent". A crash is a search that did not happen.
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
