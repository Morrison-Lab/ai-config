#!/usr/bin/env python3
"""Fail when a Stop hook reads the final message but names no reply shape it skips.

ai-config#5055, layer 5 of the defense-in-depth rule (ai-config#5051).

WHY
---
`no-announced-start-without-starting.py` passed its own tests for months while
reading the wrong channel (ai-config#5050): Projects threads reply through
`mcp__hearthbot__post_message` tool calls, and the hook read only text blocks.
Its fixtures were text blocks too, so the suite could not see the gap.

WHAT IT CHECKS
--------------
A Stop hook (registered in hooks/hooks.json) *inspects the final message* when
its source mentions `transcript_path` and the string "assistant".  For each
transcript shape that hook can meet, it must either handle the shape or say it
does not:

- `post_message`: the source mentions `post_message` (or imports the shared
  `REPLY_TOOL_RX`), or declares `transcript-shapes-skip: post_message -- why`.
- `antigravity`: the source mentions `PLANNER_RESPONSE`, or declares
  `transcript-shapes-skip: antigravity -- why`.

A hook that does neither is a violation, unless it is on the baseline
(scripts/stop-hook-shapes-baseline.txt, one `hook shape` pair per line).  The
baseline is a ratchet: it lists the hooks that predate this check, an entry
whose hook now satisfies the check fails as stale (delete the line), and a new
hook can never be added to it.  Burn it down by handling or declaring a shape.

LIMITS
------
This is a static check on declarations.  It proves a hook names the shape, not
that its logic reads it correctly, so a hook that handles a shape needs its own
test with that fixture (see test-no-announced-start-without-starting.py).  A
hook that gets its transcript text from a shared module is judged on its own
source only; declare the shape or mention the token to satisfy it.

Usage:
  check-stop-hook-shapes.py            check the repository
Exit codes: 0 clean, 1 violations or stale baseline entries, 2 error.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASELINE = REPO / "scripts" / "stop-hook-shapes-baseline.txt"

SHAPES = {
    "post_message": re.compile(r"post_message|REPLY_TOOL_RX"),
    "antigravity": re.compile(r"PLANNER_RESPONSE"),
}
SKIP = re.compile(r"transcript-shapes-skip:\s*(post_message|antigravity)\s*--\s*\S")


def stop_hooks(repo):
    """Hook script names registered under Stop in hooks/hooks.json."""
    data = json.loads((repo / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    names = set()
    for group in data.get("hooks", {}).get("Stop", []):
        for entry in group.get("hooks", []):
            m = re.search(r"hooks/([\w.-]+\.py)", entry.get("command", ""))
            if m:
                names.add(m.group(1))
    return sorted(names)


def reads_final_message(source):
    return "transcript_path" in source and bool(re.search(r"[\"']assistant[\"']", source))


def missing_shapes(source):
    """Shapes the hook neither handles nor declares it skips."""
    skipped = set(SKIP.findall(source))
    # A declaration names the token, so strip those lines before looking for
    # handling; a malformed declaration then counts as nothing.
    body = "\n".join(l for l in source.splitlines() if "transcript-shapes-skip:" not in l)
    return [s for s, rx in SHAPES.items() if not rx.search(body) and s not in skipped]


def load_baseline(path):
    if not path.exists():
        return set()
    pairs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            hook, shape = line.split()
            pairs.add((hook, shape))
    return pairs


def evaluate(repo, baseline):
    """(violations, stale, examined) for the repository at *repo*."""
    violations, current, examined = [], set(), 0
    for name in stop_hooks(repo):
        path = repo / "hooks" / name
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if not reads_final_message(source):
            continue
        examined += 1
        for shape in missing_shapes(source):
            current.add((name, shape))
            if (name, shape) not in baseline:
                violations.append((name, shape))
    stale = sorted(baseline - current)
    return violations, stale, examined


def main():
    try:
        violations, stale, examined = evaluate(REPO, load_baseline(BASELINE))
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if examined == 0:
        print("error: no Stop hook reads the final message; the search space is empty",
              file=sys.stderr)
        return 2
    for name, shape in violations:
        print(f"hooks/{name}: reads the final message but neither handles the "
              f"`{shape}` transcript shape nor declares `transcript-shapes-skip: {shape} -- why`")
    for name, shape in stale:
        print(f"{BASELINE.name}: stale entry `{name} {shape}`: the hook now satisfies the check, delete the line")
    if violations or stale:
        return 1
    print(f"ok: {examined} Stop hook(s) read the final message, each names its transcript shapes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
