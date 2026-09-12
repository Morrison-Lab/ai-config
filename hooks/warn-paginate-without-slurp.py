#!/usr/bin/env python3
"""PreToolUse guard: warn when `gh api --paginate` feeds an aggregating `jq`
filter that has no `-s`/`--slurp`.

`gh api --paginate` emits ONE JSON ARRAY PER PAGE, concatenated, rather than
one combined array. A filter that aggregates -- `last`, `first`, `length`,
`max_by`, `min_by`, `add`, `sort_by`, `group_by`, `any`, `all`, `unique` --
therefore runs once per page and produces one answer per page.

That is the shape this guard exists for, because it is invisible on the data
you test with. A resource under one page long gives the right answer either
way; the wrong answer appears only once the resource grows past the page
size, and it appears as SEVERAL answers where the caller expected one, which
downstream code silently reduces to the first or the last it happens to read.

`mwc`'s own section states the rule ("The `-s` and the double flatten are both
load-bearing, and their absence is invisible on any PR small enough to test
on"), and stating it was not enough: measured 2026-09-10, a session that had
read that rule used `gh api ... --paginate --jq '[...] | last'` to check which
of twelve PRs had a review naming a real commit, got an empty answer for every
one, and reported a false conclusion from it. The rule is consulted when
reading and broken when composing, which is why it needs a guard rather than
another sentence.

The fix is `jq -s` plus a double flatten -- `.[][]` rather than `.[]` -- so the
per-page arrays become one stream:

    gh api repos/O/R/issues/N/comments --paginate \\
      | jq -s -r '[.[][] | select(...)] | last'

WARNS rather than denies. `--jq` with a non-aggregating filter is perfectly
correct and common (`--jq '.[].number'` streams fine across pages), and the
aggregation list cannot be exhaustive, so a deny would block correct commands.
Fails OPEN on any parsing trouble: a guard that wedges the session costs more
than the lapse it prevents.
"""

import json
import os
import re
import shlex
import sys

# Aggregating filters: those whose value depends on the WHOLE input, so one
# per page is wrong. Deliberately a closed list -- a filter not named here
# simply does not warn.
AGGREGATORS = (
    "last",
    "first",
    "length",
    "add",
    "max_by",
    "min_by",
    "sort_by",
    "group_by",
    "unique",
    "unique_by",
    "any",
    "all",
    "index",
    "to_entries",
)
AGG_RE = re.compile(
    r"(?:^|[|\s(\[])(?:" + "|".join(AGGREGATORS) + r")(?:$|[\s|)\].(])"
)


def segments(command):
    """Split a command line on the operators that start a new command."""
    return re.split(r"(?:&&|\|\||;|\n)", command)


def jq_filters(segment):
    """Yield (filter_text, has_slurp) for each jq invocation in the segment,
    plus any `gh --jq` filter, which never slurps."""
    out = []
    try:
        parts = shlex.split(segment)
    except ValueError:
        return out
    i = 0
    while i < len(parts):
        token = parts[i]
        if token == "jq" or token.endswith("/jq"):
            # Stop at the next pipe. Without this bound, a `-s` belonging to
            # a LATER stage -- a second `jq -s`, or an unrelated `column -s,`
            # -- reads as satisfying this jq's slurp requirement and silences
            # the warning in exactly the case the guard exists for
            # (ai-config#3557 review).
            rest = []
            for token_after in parts[i + 1:]:
                if token_after == "|":
                    break
                rest.append(token_after)
            has_slurp = any(
                p == "-s" or p == "--slurp" or (p.startswith("-") and not p.startswith("--") and "s" in p[1:])
                for p in rest
                if p.startswith("-")
            )
            # -f FILE means the filter lives in a file this guard cannot read;
            # treat it as opaque rather than guessing.
            if any(p in ("-f", "--from-file") for p in rest):
                out.append((None, has_slurp))
            else:
                positional = [p for p in rest if not p.startswith("-")]
                out.append((positional[0] if positional else "", has_slurp))
        elif token in ("--jq", "-q") and i + 1 < len(parts):
            out.append((parts[i + 1], False))
        i += 1
    return out


def offending(command):
    for segment in segments(command):
        if "gh api" not in segment or "--paginate" not in segment:
            continue
        for filter_text, has_slurp in jq_filters(segment):
            if has_slurp or filter_text is None:
                continue
            if filter_text and AGG_RE.search(filter_text):
                return segment.strip(), filter_text
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if (payload.get("tool_name") or "") != "Bash":
        return 0
    command = ((payload.get("tool_input") or {}).get("command")) or ""
    if not command:
        return 0
    try:
        hit = offending(command)
    except Exception:
        return 0
    if not hit:
        return 0
    segment, filter_text = hit
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "This command pipes `gh api --paginate` into an AGGREGATING jq "
                f"filter with no `-s`:\n\n    {filter_text.strip()[:160]}\n\n"
                "`--paginate` emits one array PER PAGE, so an aggregation runs "
                "once per page and returns one answer per page. Under a page of "
                "results that is indistinguishable from correct, which is why "
                "this survives testing and fails later --- and it fails as "
                "several answers where one was expected, not as an error.\n\n"
                "Slurp and double-flatten instead:\n\n"
                "    gh api <path> --paginate | jq -s -r '[.[][] | ...] | last'\n\n"
                "See mwc's \"Another session's PR\" section, which states the "
                "rule and the reason. If the filter is genuinely per-page, "
                "carry on --- this is a warning, not a refusal."
            ),
        }
    }
    # Antigravity's adapter prints `additionalContext` itself AND separately
    # prints every collected `systemMessage`, so a PreToolUse payload carrying
    # both warns twice there. README.md's warn-only hook section states the
    # convention and owns the census of hooks that follow it.
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            "gh api --paginate feeds an aggregating jq filter "
            f"({filter_text.strip()[:60]}) with no -s, so it answers once per page."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
