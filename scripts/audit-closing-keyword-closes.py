#!/usr/bin/env python3
"""Find issues GitHub closed on an incidental closing-keyword match.

GitHub's parser closes `#N` whenever a closing keyword sits next to it in a
pull-request description or commit message, whatever the rest of the sentence
says. "A later PR will close #N" and "this does not resolve #N" both close the
issue on merge. `hooks/warn-deferred-closing-keyword.py` catches that shape in
text about to be posted; it cannot see a close that already happened, and
such a close reads as finished work until someone traces it by accident.

This is the retroactive half. For each closed issue with
`stateReason: COMPLETED` it reads the `ClosedEvent.closer` -- the pull request
or commit GitHub attributed the close to -- and scans that closer's text for
closing references to the issue:

- a reference that starts its line (`Closes #N`, optionally list-marked) or
  that sits in a sentence with no negation/deferral cue is DELIBERATE;
- a reference inside a sentence carrying a cue is RISKY.

An issue is flagged when the closer references it riskily at all -- as
"incidental" when that is its only reference, and as "contradicted" when the
same closer also closes it deliberately (a `(closes #N)` start commit squashed
into a merge whose description says the PR does not close #N). The
sentence heuristic is imported from the hook rather than copied, so the two
cannot drift.

Usage:
    python3 scripts/audit-closing-keyword-closes.py -R owner/repo [--limit N] [--json]
    python3 scripts/audit-closing-keyword-closes.py -R owner/repo --from-json nodes.json

Exit status: 0 when nothing is flagged, 1 when something is, 2 on error.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = ROOT / "hooks" / "warn-deferred-closing-keyword.py"

_spec = importlib.util.spec_from_file_location("warn_deferred_closing_keyword", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

PAGE_SIZE = 50

QUERY = """
query($owner: String!, $name: String!, $after: String, $size: Int!) {
  repository(owner: $owner, name: $name) {
    issues(states: CLOSED, first: $size, after: $after,
           orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        stateReason
        timelineItems(itemTypes: [CLOSED_EVENT], last: 1) {
          nodes {
            ... on ClosedEvent {
              closer {
                __typename
                ... on PullRequest {
                  number
                  body
                  mergeCommit { oid message }
                }
                ... on Commit { oid message }
              }
            }
          }
        }
      }
    }
  }
}
"""

# The issue named by a closing reference: `#12`, `owner/repo#12`, or a full
# issue URL. RX_CLOSING_REF already matched the whole reference, so these only
# pull the parts back out of `match.group(0)`.
RX_URL_REF = re.compile(r"https?://[^/\s]+/([\w.-]+)/([\w.-]+)/issues/(\d+)")
RX_SHORT_REF = re.compile(r"(?:([\w.-]+)/([\w.-]+))?#(\d+)$")


def referenced_issue(reference: str) -> tuple[str | None, int] | None:
    """(`owner/repo` or None for a bare `#N`, number) for one matched reference."""
    url = RX_URL_REF.search(reference)
    if url:
        return f"{url.group(1)}/{url.group(2)}".lower(), int(url.group(3))
    short = RX_SHORT_REF.search(reference)
    if short:
        repo = f"{short.group(1)}/{short.group(2)}".lower() if short.group(1) else None
        return repo, int(short.group(3))
    return None


# A list item begins a new sentence for this purpose. A squash-merge message
# is a stack of `* subject` bullets with no sentence-ending punctuation
# between them, so without this bound the hook's sentence window runs across
# every bullet and a cue word in one commit's subject ("after", "not", "once")
# taints another commit's deliberate close.
RX_LIST_ITEM = re.compile(r"\n[ \t]*(?:[-*+]|\d+[.)])[ \t]+")


def list_item_bounds(text: str, start: int) -> tuple[int, int]:
    """The [begin, end) span of the list item (or whole text) holding START."""
    begin, end = 0, len(text)
    for item in RX_LIST_ITEM.finditer(text):
        if item.start() < start:
            begin = item.start() + 1
        else:
            end = item.start()
            break
    return begin, end


def closing_references(text: str, repo: str, number: int) -> list[dict]:
    """Every closing reference in TEXT that names issue NUMBER of REPO."""
    found = []
    for match in hook.RX_CLOSING_REF.finditer(text or ""):
        target = referenced_issue(match.group(0))
        if target is None:
            continue
        target_repo, target_number = target
        if target_number != number or target_repo not in (None, repo.lower()):
            continue
        begin, end = list_item_bounds(text, match.start())
        item = text[begin:end]
        sentence = " ".join(hook.sentence_around(
            item, match.start() - begin, match.end() - begin).split())
        # `(closes #N)` is a close tag, not prose: the parenthesis opens on the
        # keyword itself, so no cue elsewhere in the sentence governs it.
        tagged = text[:match.start()].endswith("(")
        risky = (not tagged
                 and not hook.begins_line(text, match.start())
                 and bool(hook.RX_CUE.search(sentence)))
        found.append({"match": match.group(0), "sentence": sentence, "risky": risky})
    return found


def closer_texts(closer: dict | None) -> list[tuple[str, str]]:
    """(label, text) for every text GitHub's parser could have read on CLOSER."""
    if not closer:
        return []
    kind = closer.get("__typename")
    if kind == "PullRequest":
        texts = [(f"PR #{closer.get('number')} body", closer.get("body") or "")]
        merge = closer.get("mergeCommit") or {}
        if merge.get("message"):
            texts.append((f"merge commit {merge.get('oid', '')[:8]}", merge["message"]))
        return texts
    if kind == "Commit":
        return [(f"commit {closer.get('oid', '')[:8]}", closer.get("message") or "")]
    return []


def classify(node: dict, repo: str) -> dict:
    """One closed issue's verdict: flagged, deliberate, unattributed, or skipped."""
    number = node["number"]
    result = {"number": number, "title": node.get("title", "")}
    if node.get("stateReason") != "COMPLETED":
        return {**result, "verdict": "skipped", "reason": node.get("stateReason")}
    events = ((node.get("timelineItems") or {}).get("nodes")) or []
    closer = events[-1].get("closer") if events else None
    texts = closer_texts(closer)
    if not texts:
        return {**result, "verdict": "unattributed", "reason": "no closer recorded"}
    references = []
    for label, text in texts:
        for reference in closing_references(text, repo, number):
            references.append({**reference, "source": label})
    if not references:
        return {**result, "verdict": "unattributed",
                "reason": "closer carries no closing reference to this issue"}
    risky = [reference for reference in references if reference["risky"]]
    if not risky:
        return {**result, "verdict": "deliberate"}
    # A deliberate reference beside a risky one is still flagged: the closer's
    # own text disagrees about whether the issue should close, which is the
    # case a reader of the closed issue can least afford to take on trust.
    contradicted = len(risky) < len(references)
    return {**result, "verdict": "flagged", "contradicted": contradicted,
            "references": references}


def fetch_nodes(repo: str, limit: int | None) -> list[dict]:
    owner, name = repo.split("/", 1)
    nodes, after = [], None
    while True:
        command = ["gh", "api", "graphql", "-f", f"query={QUERY}",
                   "-F", f"owner={owner}", "-F", f"name={name}",
                   "-F", f"size={PAGE_SIZE}"]
        if after:
            command += ["-F", f"after={after}"]
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", check=True)
        issues = json.loads(result.stdout)["data"]["repository"]["issues"]
        nodes.extend(issues["nodes"])
        if limit is not None and len(nodes) >= limit:
            return nodes[:limit]
        if not issues["pageInfo"]["hasNextPage"]:
            return nodes
        after = issues["pageInfo"]["endCursor"]


def report(verdicts: list[dict], repo: str) -> str:
    counts = {}
    for verdict in verdicts:
        counts[verdict["verdict"]] = counts.get(verdict["verdict"], 0) + 1
    lines = [
        f"{repo}: examined {len(verdicts)} closed issues -- "
        + ", ".join(f"{key} {counts.get(key, 0)}"
                    for key in ("flagged", "deliberate", "unattributed", "skipped"))
    ]
    for verdict in verdicts:
        if verdict["verdict"] != "flagged":
            continue
        shape = ("contradicted: the closer also closes it deliberately"
                 if verdict["contradicted"] else "incidental: no deliberate reference")
        lines.append(f"\n#{verdict['number']} {verdict['title']}  ({shape})")
        for reference in verdict["references"]:
            tag = "RISKY" if reference["risky"] else "deliberate"
            quote = reference["sentence"]
            if len(quote) > 300:
                quote = quote[:297] + "..."
            lines.append(f"  {tag} [{reference['source']}] `{reference['match']}` in: {quote}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("-R", "--repo", required=True, help="owner/repo")
    parser.add_argument("--limit", type=int, default=None,
                        help="examine at most N closed issues (most recently updated first)")
    parser.add_argument("--from-json", type=Path,
                        help="read issue nodes from a file instead of querying GitHub")
    parser.add_argument("--json", action="store_true", help="emit verdicts as JSON")
    args = parser.parse_args(argv)
    # Issue and PR bodies carry arbitrary Unicode; a cp1252 console would
    # otherwise die mid-report on the first character it cannot encode.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "/" not in args.repo:
        print("ERROR: --repo must be owner/repo", file=sys.stderr)
        return 2
    try:
        if args.from_json:
            nodes = json.loads(args.from_json.read_text(encoding="utf-8"))
        else:
            nodes = fetch_nodes(args.repo, args.limit)
        verdicts = [classify(node, args.repo) for node in nodes]
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or ""
        print(f"ERROR: {error} {detail}".rstrip(), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(verdicts, indent=2))
    else:
        print(report(verdicts, args.repo))
    return 1 if any(verdict["verdict"] == "flagged" for verdict in verdicts) else 0


if __name__ == "__main__":
    sys.exit(main())
