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

UNATTRIBUTED cannot simply be excluded: 2,270 of 2,339 user-role records in
one transcript root carried no `origin` key at all on 2026-08-28, and one of
the CLI's own human predicates reads (de-minified) `O0(o.origin) &&
o.verifiedSlackHumanTurn !== true`, so a labelled record can be somebody else's
message relayed from a channel. `shared/writing/citations.md` carries the
argument; this notes only what the code depends on.

The check here is a SUBSET of that predicate in one respect and stricter in
another: it does not implement `O0` itself, and it excludes any record carrying
`toolUseResult` outright rather than reasoning about whether such a record can
hold text.

Related instrument: `hooks/no-misattributed-quote.py` does the structurally
similar job for a phrase attributed to a corpus FILE. A Stop-hook form of this
check -- firing on a quote attributed to the user with no prior run of this
script -- is the obvious next step and is not in this change.

Classification is per record; matching is per text block. A block containing
any tag-shaped opener is unquotable in full, and blocks are never concatenated.

Exit codes. `shared/writing/citations.md` is the statement of record; this is
what the code does.

  0  found in a quotable human region
  1  absent from every one -- relative to the region count the run prints,
     which is itself a signal: an absence over two regions is a much weaker
     result than one over two thousand, and the count is always reported
  2  no such region was available to search: a missing root, a root that could
     not be resolved, an unreadable file or directory, an unparseable line, an
     empty phrase, or a crash anywhere after the arguments parse
  3  found only in an unattributed region, with `--allow-unattributed`

Exit 2 is kept distinct from 1 so a degraded read can never be reported as an
absence, and 3 from 0 so a scripted caller cannot mistake the weaker reading
for a certified one.

Known limits, stated rather than left to be discovered:
  - A phrase spanning two blocks of one record is not found; blocks are never
    concatenated.
  - A block carrying any tag-shaped opener is unquotable in full, so a turn
    written ABOUT a tag cannot be quoted from that block. The run exits 2 and
    says the phrase is present but unsearchable; `--show-excluded` shows which
    block.
  - `unparseable` is a root-wide latch: one torn line anywhere makes every
    absence report as could-not-search until it is repaired. Safe, and blunt.
  - The opener test is lexical, so it denies a block that merely LOOKS like it
    carries a tag -- prose containing `if x <y then` is unquotable. It is
    reported as a denial rather than an absence, which is the whole point of
    keeping those two exit codes apart.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# A block containing ANY tag-shaped opener is unquotable in full.
#
# The previous revision enumerated four names and claimed "nothing is parsed".
# That was false: the parse had moved from grammar to VOCABULARY, and the
# vocabulary was not mine. The shipped CLI defines at least fifteen tag names
# it emits into or strips from user content -- command-name, command-message,
# bash-stdout, bash-stderr, local-command-stdout, local-command-stderr,
# local-command-caveat, tick, task-notification, task-id, task-type,
# output-file, status, summary, teammate-message -- and the four-name list
# intersected that set in exactly one. `teammate-message` is another agent's
# words in a user-role record; `ide_selection` is editor content appended to
# the user's own typed prompt. Both certified at exit 0.
#
# So the test is structural rather than enumerated. Measured on this machine's
# transcript root, it denies zero human-labelled blocks and one unattributed
# block (an assistant-written dispatch brief), so the recall it costs on real
# data is nil while the name list it removes was already incomplete.
# NO closing ">" is required. Requiring one was a regression introduced when
# this test replaced a four-name list: the enumerated form matched on a word
# boundary and so caught a truncated opener for free, while requiring closure
# let `<system-reminder never closes...` through as quotable. A real injection
# can be cut mid-write; the reader of a transcript is not owed well-formed XML.
_OPENER_RX = re.compile(r"<[A-Za-z][A-Za-z0-9_-]*(?:[\s/>]|$)")

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
    """The block, or nothing at all if it carries a harness envelope opener.

    Deliberately all-or-nothing. Returning the block whole means a phrase is
    matched against exactly what the transcript holds, with no reconstruction
    that could join text the user never wrote consecutively.
    """
    if _OPENER_RX.search(block):
        return []
    return [block] if block.strip() else []





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

    if record.get("toolUseResult") is not None:
        # The CLI's own human predicate carries `toolUseResult === undefined`.
        # The previous revision omitted it and argued the omission was safe
        # because such a record has no text block -- true of the observed
        # corpus, and an assumption of exactly the shape this file's history is
        # made of. Enforced rather than assumed.
        return EXCLUDED, "tool-result carrier"

    origin = record.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    if kind == "human":
        return HUMAN, ""
    if kind in NON_HUMAN_ORIGINS:
        return EXCLUDED, f"origin.kind={kind}"

    # Unlabelled or demoted. Only here do the English prose markers apply.
    # Every block, not the first: a leading empty block -- which text_blocks
    # produces for a non-str `text` field -- would otherwise hide a marker.
    for block in text_blocks(message):
        stripped = block.lstrip()
        if any(stripped.startswith(prefix) for prefix in TRANSCRIPT_PREFIXES):
            return EXCLUDED, "harness transcript marker"
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
        self.denied = 0   # the phrase is present, but only outside a quotable region


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
        # Derived unconditionally, not only under --show-excluded: whether the
        # phrase is present-but-unsearchable decides the EXIT CODE, and a
        # denial reported as a bare exit 1 says "the user never said it" about
        # a sentence sitting in the transcript.
        blocks = text_blocks(message)
        whole_block = next((b for b in blocks if target in norm(b)), None)
        if whole_block is not None:
            result.denied += 1
            if show_excluded:
                why = reason if kind == EXCLUDED else "block carries a tag-shaped opener"
                result.near_misses.append((name, why, whole_block.strip()[:160]))
        elif show_excluded and target in norm(" ".join(blocks)):
            result.near_misses.append(
                (name, "spans two blocks; never contiguous in one", " ".join(blocks).strip()[:160]))
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
    if result.denied:
        # Present in the transcript, in a block nothing could search. That is a
        # could-not-search, not an absence.
        return "unsearchable"
    searchable = result.human or (allow_unattributed and result.unattributed)
    # An unparseable line is the commonest degraded read there is -- a live
    # session appends while this reads, so a torn final line is normal -- and it
    # shrinks the searched space exactly as an unreadable file does.
    if not searchable or result.unreadable or result.unparseable:
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
        "denied_blocks": result.denied,
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
        if result.denied:
            print(f"\nThe phrase is present in {result.denied} block(s) that could not be "
                  "searched -- each carries a tag-shaped opener, or its record is excluded. "
                  "That is not an absence. Re-run with --show-excluded to see them.")
        elif result.unreadable or result.unparseable:
            print("\nPart of the space could not be read, so an absence here is not established.")
        else:
            print("\nNo quotable human regions were found at all -- this is an unsearched "
                  "space, not an absence. Pass --root, or --allow-unattributed to fall "
                  "back on the weaker reading.")
    elif outcome == "absent":
        print(f"\nNot present in any of {result.human} quotable human region(s). Do not quote it.")


def _harden_stdout() -> None:
    """A transcript carries whatever the user typed; the console may not encode it.

    Without this, `LC_ALL=C` plus an em-dash in a matched turn kills the process
    while PRINTING the hit, and Python's default status for that is 1 -- the
    code this tool documents as "absent".
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: Optional[List[str]] = None) -> int:
    _harden_stdout()
    parser = argparse.ArgumentParser(
        description=(__doc__ or "check whether a phrase was typed by the user").splitlines()[0])
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

    # Inside the try: resolving the root can itself raise -- an unresolvable
    # `~user` in CLAUDE_CONFIG_DIR, or Path.home() with HOME unset and no passwd
    # entry -- and an uncaught exception exits 1, the code that means "absent".
    root = Path(".")
    try:
        if args.root:
            root = Path(args.root).expanduser()
            if not root.is_dir():
                parser.error(f"--root {args.root} is not a directory")
        else:
            root = default_root()
            resolved = root.is_dir()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 -- mapped to exit 2, never to 1
        message = (f"check-user-quote could not resolve a transcript root: "
                   f"{type(exc).__name__}: {exc}")
        if args.as_json:
            print(json.dumps(_payload("unsearchable", root, Scan(), reason=message), indent=2))
        else:
            print(message, file=sys.stderr)
        return 2

    if not args.root:
        if not resolved:
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
        outcome = status(result, args.allow_unattributed)
        if args.as_json:
            print(json.dumps(_payload(outcome, root, result), indent=2))
        else:
            report(result, root, args.allow_unattributed)
        return {"found": 0, "absent": 1, "unsearchable": 2, "accepted-unattributed": 3}[outcome]
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


if __name__ == "__main__":
    sys.exit(main())
