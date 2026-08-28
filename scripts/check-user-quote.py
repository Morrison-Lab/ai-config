#!/usr/bin/env python3
"""Show every transcript record containing a phrase, with its provenance.

The instrument for `shared/writing/citations.md`'s
"The user's own words are on disk" section. That section carries the argument;
this notes what the code does and, more importantly, what it deliberately does
not do.

IT DOES NOT DECIDE WHO WROTE THE PHRASE. Ten earlier revisions tried, and each
certified harness- or assistant-authored text as the user's own words:

  exclusions alone; then the harness `origin.kind` label; then per record; then
  per block; then per non-envelope region; then a four-name tag list; then a
  structural opener test -- broken in turn by an appended reminder, a mid-block
  one, leftovers joined across a cut, a repeated opener, a literal closing tag
  inside injected content, a vocabulary of fifteen tag names against a list of
  four, a truncated opener, an entity-escaped tag, a namespaced one, and an
  envelope split across two blocks.

The last several were not slips. `message.role == "user"` is a transport role,
and the harness's text is not lexically identifiable: it arrives escaped
(`&lt;system-reminder&gt;` is what the harness itself writes when neutralizing
control tags), namespaced, split across blocks, or with no tag at all. A test
that returns "this is the user's" is a test that will eventually be wrong in
the one direction that matters.

So the verdict is the reader's. This prints the candidates and the facts about
each -- record shape, role, `origin.kind`, flags, session -- and stops.

It also reads FOUR record shapes, not one. A user's prompt is written to
`queue-operation` at enqueue and only becomes a `message` record at dequeue
(measured 380 ms apart), and `last-prompt` and `attachment` carry it too. An
earlier revision read `message` alone and so reported "Do not quote it" over
sentences the transcript held in another shape.

Exit 0 candidates found and printed; 1 none found anywhere; 2 the search was
degraded or impossible -- a missing or unresolvable root, an unreadable file or
directory, an unparseable line, an empty phrase, or a crash. Exit 1 and 2 are
kept apart so a search that did not happen is never reported as an absence.
Exit 0 asserts only that a record contains the phrase.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

# Facts worth printing beside a candidate. None is a verdict; each is something
# a reader can weigh. `origin.kind == "human"` is the harness's own label and is
# the strongest signal available -- and still only a signal, since the CLI
# rewrites it to "unclassified" on some paths and stamps a relayed channel
# message as human on others.
PROVENANCE_FLAGS = ("isMeta", "isCompactSummary", "isSidechain",
                    "verifiedSlackHumanTurn", "toolUseResult")


def norm(s: str) -> str:
    """Whitespace and inline markup collapsed, per this corpus's substring test."""
    return re.sub(r"[\s`*_]+", " ", s).strip().lower()


def default_root() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return base / "projects"


def texts(record: dict) -> Iterator[Tuple[str, str]]:
    """(shape, text) for every piece of prose a record can carry.

    Four shapes, because a prompt exists in more than one of them and can exist
    in only the others: `queue-operation` is written at enqueue, `message` at
    dequeue, and a session ending between the two leaves the sentence on disk
    in a form a message-only reader cannot see.
    """
    kind = record.get("type")
    message = record.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        role = message.get("role", "?")
        if isinstance(content, str):
            yield f"message/{role}", content
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str):
                    yield f"message/{role}", text
    if kind == "queue-operation" and isinstance(record.get("content"), str):
        yield "queue-operation", record["content"]
    if kind == "last-prompt" and isinstance(record.get("lastPrompt"), str):
        yield "last-prompt", record["lastPrompt"]
    attachment = record.get("attachment")
    if isinstance(attachment, dict):
        for key in ("prompt", "content", "text"):
            value = attachment.get(key)
            if isinstance(value, str):
                yield f"attachment/{attachment.get('type', '?')}", value


def provenance(record: dict) -> Dict[str, str]:
    """The facts a reader needs, none of them a verdict."""
    origin = record.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    flags = [f for f in PROVENANCE_FLAGS if record.get(f)]
    return {
        "origin.kind": kind or "(absent)",
        "flags": ",".join(flags) or "(none)",
        "userType": str(record.get("userType") or "(absent)"),
        "session": str(record.get("sessionId") or "(absent)"),
    }


# Presentation order, not judgment: a reader should meet the most informative
# record first. `last-prompt` is a rolling pointer rewritten every turn, so one
# prompt appears in scores of records; identical texts are collapsed with a
# count rather than printed again.
SHAPE_RANK = {"message/user": 0, "queue-operation": 1, "last-prompt": 2}


def _rank(candidate: dict) -> Tuple[int, int]:
    shape = candidate["shape"]
    base = SHAPE_RANK.get(shape, 4 if shape.startswith("attachment/") else 5)
    # The harness's own label is a fact worth surfacing early. It is still only
    # a label -- the CLI rewrites it on some paths and stamps relayed messages
    # with it on others -- so it orders the list and decides nothing.
    return (base, 0 if candidate["origin.kind"] == "human" else 1)


def collapse(candidates: List[dict]) -> List[dict]:
    """One entry per distinct (shape, text), carrying how many records held it."""
    seen: Dict[Tuple[str, str], dict] = {}
    for c in candidates:
        key = (c["shape"], norm(c["text"]))
        if key in seen:
            seen[key]["copies"] += 1
            # Track every file, so "(x2 records)" cannot be misread as two
            # copies in the one file named.
            if c["file"] not in seen[key]["files"]:
                seen[key]["files"].append(c["file"])
            continue
        seen[key] = dict(c, copies=1, files=[c["file"]])
    return sorted(seen.values(), key=_rank)


class Scan:
    def __init__(self) -> None:
        self.files = 0
        self.records = 0
        self.texts = 0
        self.unparseable = 0
        self.unreadable: List[str] = []
        self.candidates: List[dict] = []


def _walk(root: Path, result: Scan) -> List[Path]:
    """Every *.jsonl under root, recording directories that could not be read.

    `Path.rglob` swallows a permission error from `scandir`, so an unreadable
    project directory would silently shrink the searched space.
    """
    found: List[Path] = []

    def onerror(exc: OSError) -> None:
        result.unreadable.append(f"{getattr(exc, 'filename', root)}: {exc.strerror or exc}")

    for dirpath, _dirnames, filenames in os.walk(root, onerror=onerror):
        found.extend(Path(dirpath) / n for n in filenames if n.endswith(".jsonl"))
    return sorted(found)


def scan(root: Path, needle: str) -> Scan:
    result = Scan()
    target = norm(needle)
    for path in _walk(root, result):
        result.files += 1
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError as exc:
            result.unreadable.append(f"{path.name}: {exc.strerror or exc}")
            continue
        try:
            with handle:
                for line in handle:
                    _scan_line(line, path.name, target, result)
        except OSError as exc:
            result.unreadable.append(f"{path.name}: {exc.strerror or exc}")
    return result


def _scan_line(line: str, name: str, target: str, result: Scan) -> None:
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
    facts = None
    for shape, text in texts(record):
        result.texts += 1
        if target not in norm(text):
            continue
        if facts is None:
            facts = provenance(record)
        result.candidates.append({"file": name, "shape": shape, "text": text.strip(), **facts})


def status(result: Scan) -> str:
    if result.unreadable or result.unparseable:
        return "degraded"
    return "found" if result.candidates else "absent"


def _payload(outcome: str, root: Path, result: Scan, reason: str = "") -> dict:
    body = {
        "status": outcome,
        "root": str(root),
        "files": result.files,
        "records": result.records,
        "texts_examined": result.texts,
        "unparseable_lines": result.unparseable,
        "unreadable": result.unreadable,
        "candidates": collapse(result.candidates),
        "candidate_records": len(result.candidates),
    }
    if reason:
        body["reason"] = reason
    return body


def report(result: Scan, root: Path, limit: int) -> None:
    # The search space prints first and unconditionally: a zero below it means
    # nothing until a reader can see what was examined to produce it.
    print(f"Searched {result.files} transcript file(s) under {root}")
    print(f"  {result.records} records, {result.texts} text field(s) across four record shapes, "
          f"{result.unparseable} unparseable line(s)")
    for problem in result.unreadable:
        print(f"  UNREADABLE {problem}")

    distinct = collapse(result.candidates)
    shown = distinct[:limit]
    if not shown:
        print("\nNo record contains the phrase.")
    else:
        print(f"\n{len(distinct)} distinct text(s) in {len(result.candidates)} record(s) "
              f"contain the phrase"
              f"{f'; showing {limit}' if len(distinct) > limit else ''}:\n")
    for i, c in enumerate(shown, 1):
        files = c.get("files", [c["file"]])
        where = files[0] if len(files) == 1 else f"{files[0]} +{len(files) - 1} more file(s)"
        copies = f"  (x{c['copies']} records)" if c["copies"] > 1 else ""
        print(f"  [{i}] {where}  shape={c['shape']}{copies}")
        print(f"      origin.kind={c['origin.kind']}  flags={c['flags']}  userType={c['userType']}")
        for chunk in c["text"].splitlines()[:6]:
            print(f"      > {chunk[:150]}")
        print()

    # Said on every run, including the empty one: the absence of a candidate is
    # not a finding about authorship either.
    print("This tool does not decide who wrote anything. `role: \"user\"` is a "
          "transport role, and no\nlexical test separates the harness's text from "
          "the user's -- ten revisions tried. Read the\nrecords above and judge. "
          "See shared/writing/citations.md.")
    if status(result) == "degraded":
        if result.candidates:
            print("\nPart of the space could not be read, so there may be further records "
                  "beyond those above.")
        else:
            print("\nPart of the space could not be read, so an absence here is not established.")


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass

    parser = argparse.ArgumentParser(
        description=(__doc__ or "show transcript records containing a phrase").splitlines()[0])
    parser.add_argument("phrase", help="the sentence you are about to attribute to the user")
    parser.add_argument("--root", help="transcript directory "
                        "(default: $CLAUDE_CONFIG_DIR/projects, else ~/.claude/projects)")
    parser.add_argument("--limit", type=int, default=10,
                        help="maximum candidates to print (default 10; --json prints all)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit the result as JSON, with the same counts")
    args = parser.parse_args(argv)

    if not norm(args.phrase):
        # A usage error, never an absence: an unset shell variable expanding to
        # "" must not answer "no record contains it".
        parser.error("phrase is empty after normalization; nothing to search for")

    root = Path(".")
    try:
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
                    print(json.dumps(_payload("degraded", root, Scan(), reason=message), indent=2))
                else:
                    print(message, file=sys.stderr)
                return 2

        result = scan(root, args.phrase)
        outcome = status(result)
        if args.as_json:
            print(json.dumps(_payload(outcome, root, result), indent=2))
        else:
            report(result, root, args.limit)
        return {"found": 0, "absent": 1, "degraded": 2}[outcome]
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 -- mapped to exit 2, never to 1
        # Python's default status for an uncaught exception is 1, which this
        # tool documents as "no record contains it". A crash is a search that
        # did not happen.
        message = (f"check-user-quote failed before it could answer: "
                   f"{type(exc).__name__}: {exc}")
        if args.as_json:
            print(json.dumps(_payload("degraded", root, Scan(), reason=message), indent=2))
        else:
            print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
