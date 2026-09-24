#!/usr/bin/env python3
"""PreToolUse guard: a partial PUT to a REST resource root, which can null fields you never named.

`shared/principles/fail-fast.md` covers checks that silently pass. This is the
write-side twin: a request that silently *succeeds* while destroying state the
author never mentioned, and returns HTTP 200 either way.

THE MEASUREMENT (2026-09-24, WWU Canvas course 1906010)
--------------------------------------------------------
A session updating a Canvas course sent, through the browser:

    fetch('/api/v1/courses/1906010', {method:'PUT',
          body: JSON.stringify({course:{apply_assignment_group_weights:true}})})

It returned 200 and did what was asked. It ALSO cleared `start_at` and
`end_at`, which had been 2026-09-23 and 2026-12-11 and which the body never
mentioned. Nothing reported it. The loss surfaced only because a later,
unrelated sweep happened to print the course object again and the dates read
`null`.

Four restore attempts then returned 200 and changed nothing, so the damage was
not reversible by the same route that caused it.

The session DID read the resource back after each write --- but only compared
the fields it had just set, which is exactly the check that cannot see this.

WHAT IT CHECKS
--------------
    a `javascript_tool` call (or a Bash curl) issues a PUT
    AND the target is a RESOURCE ROOT --- `/api/v1/<collection>/<id>` with no
        further path segment
    AND the call does not capture a before/after snapshot of the whole
        resource (no `Object.keys` diff, no `JSON.stringify` of a prior GET
        held for comparison)

WHY A RESOURCE ROOT SPECIFICALLY
---------------------------------
A sub-resource PUT (`/courses/<id>/pages/<slug>`,
`/courses/<id>/assignments/<id>`) addresses a small object whose fields the
author is usually setting wholesale, so an omitted field is rarely a surprise.
A resource ROOT addresses the big aggregate --- a course, a user, an account
--- where the author is invariably setting one or two of dozens of fields, and
where the API's treatment of the rest is a per-vendor coin flip. That is the
shape worth interrupting, and restricting to it keeps the guard quiet: the
measured session made roughly twenty sub-resource PUTs and four resource-root
ones.

WHY THIS WARNS RATHER THAN BLOCKS
-----------------------------------
Whether omitted fields are preserved is a property of the remote API, not of
the request, and many APIs do the right thing. Blocking would refuse correct
code against a well-behaved endpoint. The cost of the warning is one line; the
cost of the miss is silent, and in the measured case unrecoverable.

THE REMEDY IT ASKS FOR
-----------------------
Snapshot the whole resource before, and diff the whole resource after ---
not just the fields being set:

    const before = await (await fetch(URL)).json();
    ... PUT ...
    const after  = await (await fetch(URL)).json();
    const lost = Object.keys(before).filter(k =>
        before[k] !== null && after[k] === null);
"""
from __future__ import annotations

import json
import re
import sys

# `/api/v1/<collection>/<id>` and nothing after it. The id may be numeric or a
# sis-style string. A trailing slash still counts as the root; any further
# segment does not.
RX_RESOURCE_ROOT = re.compile(
    r"""(?:["'`]|(?<=\s)|^)        # a quote, whitespace, or start of input
        (?:https?://[^"'`/\s]+)?    # optional scheme+host
        /api/v\d+/
        [a-z_]+ /                   # collection
        (?:\$\{[^}]+\}|[\w.:~-]+)   # id, literal or interpolated
        /?                          # optional trailing slash
        (?=["'`]|\s|$)              # nothing further in the path
    """,
    re.X | re.I | re.M,
)

RX_PUT = re.compile(r"""method\s*:\s*["'`]PUT["'`]|(?:^|\s)-X\s+PUT\b""", re.I)

# Evidence the author is comparing the WHOLE resource, not just what they set.
RX_WHOLE_DIFF = re.compile(
    r"""Object\.keys\s*\(\s*before|Object\.entries\s*\(\s*before
      | \bbefore\b[^\n]{0,80}\bafter\b[^\n]{0,80}(?:filter|diff|compare)
      | (?:diff|lost|cleared|nulled)\s*=
    """,
    re.X | re.I,
)


def _text(payload: dict) -> str:
    tool = payload.get("tool_name") or ""
    ti = payload.get("tool_input") or {}
    if tool == "mcp__claude-in-chrome__javascript_tool":
        return str(ti.get("text") or "")
    if tool == "Bash":
        return str(ti.get("command") or "")
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail open

    text = _text(payload)
    if not text or not RX_PUT.search(text):
        return 0

    m = RX_RESOURCE_ROOT.search(text)
    if not m:
        return 0  # sub-resource PUT: not this guard's shape

    if RX_WHOLE_DIFF.search(text):
        return 0  # the author is already diffing the whole resource

    target = m.group(0).strip("\"'`")
    print(json.dumps({"systemMessage": (
        f"This PUTs to a REST resource ROOT ({target}) with a partial body, and "
        "the call does not snapshot and diff the whole resource around it.\n\n"
        "An API may treat the fields you omit as 'leave alone' or as 'clear' --- "
        "that is the remote's choice, not the request's, and both return 200.\n\n"
        "Measured 2026-09-24 on a Canvas course: a PUT setting one boolean also "
        "nulled start_at and end_at, which the body never mentioned. The session "
        "did read the resource back, but compared only the field it had set, "
        "which cannot see this. Four restore attempts then returned 200 and "
        "changed nothing.\n\n"
        "Snapshot the whole object before, diff the whole object after:\n"
        "  const before = await (await fetch(URL)).json();\n"
        "  /* ... PUT ... */\n"
        "  const after  = await (await fetch(URL)).json();\n"
        "  const lost = Object.keys(before).filter(k => "
        "before[k] !== null && after[k] === null);\n\n"
        "If this endpoint is known to preserve omitted fields, carry on --- "
        "this is a reminder, not a refusal."
    )}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
