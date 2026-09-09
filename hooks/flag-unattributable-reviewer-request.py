#!/usr/bin/env python3
"""PreToolUse guard: a reviewer request whose success nothing can attribute.

## The incident

Measured 2026-09-08, three times in one session on ai-config#3403. The reviewer
request was issued as:

    gh api "repos/O/R/pulls/3403/requested_reviewers" \
      -X POST -f 'reviewers[]=copilot-pull-request-reviewer[bot]' --jq '.number' 2>&1 | tail -3

It SUCCEEDED. A Copilot review landed. And `no-unreviewed-pr.py` still blocked
at `Stop` with "no SUCCESSFUL reviewer request follows for it", because the
pipe puts `tail` last: the harness credits a request by the WHOLE call's exit
status, so a request that is not the final simple command shares its status
with whatever trails it and cannot be credited. `request_ident`'s own docstring
in that hook states the rule.

The session read the block as "the request failed" and reissued it in the
identical shape twice more before running it bare, which discharged instantly.

## Why a hook rather than a rule

The rule already exists, in two places, and neither reached the moment it
breaks. `no-unreviewed-pr.py`'s block text says "Run the label add on its own:
chained AHEAD of another command, it shares one exit status with that command"
-- for the LABEL path, not the request path, so it reads as a footnote about a
different command. And `undischargeable_requests()` in that same hook already
computes exactly this set; it is used only to name the offenders inside the
Stop block, which is after the call has run.

So the information exists and arrives too late. The pipe is added for an
entirely unrelated reason -- trimming output -- and nothing at composition time
connects "I piped this to `tail`" with "the discharge will not fire". That gap
between a rule consulted at read time and a defect introduced at composition
time is what README names as the case for a hook.

The failure is also self-disguising in the expensive direction: the request
works, the review lands, and the block's wording ("no SUCCESSFUL request")
points at the request rather than at the plumbing -- so the natural response is
to retry the same broken shape, which is what happened.

## Why this warns rather than blocks

A non-last request is not always wrong. A caller may be requesting reviewers
for several PRs in one call and verifying afterwards, and only the last is
creditable by construction -- `undischargeable_requests` exists precisely
because that shape is legitimate and merely under-credited. Blocking would
refuse it. Per README's "A hook that misfires is worse than a missing one",
this only ever ADDS context.

## Why it reuses `undischargeable_requests` rather than matching itself

`no-unreviewed-pr.py`'s matcher carries hard-won exclusions -- a GET of the
same endpoint is not a request, a `--body` quoting the endpoint is not a
request, `$O`/`$R`/`$N` interpolations are genuine. A second copy would drift
from the hook whose discharge it is predicting, and a prediction that disagrees
with the thing predicted is worse than none.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
SIBLING = HOOK_DIR / "no-unreviewed-pr.py"

NOTE = """This reviewer request is NOT the last command in this Bash call, so its success \
cannot be attributed and `no-unreviewed-pr.py` will NOT treat it as discharging \
the obligation -- even when the request succeeds and a review lands.

  unattributable request(s): {names}

The harness credits a request by the WHOLE call's exit status. A pipe, or any \
command after the request, takes that status for itself. This is the shape:

    gh api "..." -X POST -f 'reviewers[]=...' --jq '.number' | tail -3   # NOT credited

Run the request ALONE, with nothing chained after it and no pipe:

    gh api "repos/<owner>/<repo>/pulls/<N>/requested_reviewers" \\
      -X POST -f 'reviewers[]=copilot-pull-request-reviewer[bot]'

Then verify separately that a review actually landed. If a later `Stop` block \
still says no successful request was made, the request did not fail -- it was \
not attributable. Re-running it in the same shape will not help."""


def _load_sibling():
    """Import `no-unreviewed-pr.py` by path; its name is not importable."""
    spec = importlib.util.spec_from_file_location("_no_unreviewed_pr", SIBLING)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SIBLING}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"flag-unattributable-reviewer-request: unreadable input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def unattributable(payload: dict) -> list:
    """Reviewer requests in this Bash command that no discharge can credit."""
    if payload.get("tool_name") != "Bash":
        return []
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return []
    mod = _load_sibling()
    found = mod.undischargeable_requests(command)
    return list(found or [])


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    try:
        found = unattributable(payload)
    except Exception as exc:  # fail open on any parse or import trouble
        print(f"flag-unattributable-reviewer-request: could not evaluate ({exc})",
              file=sys.stderr)
        return 0

    if not found:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    names = ", ".join(
        f"{repo or '<this repo>'}#{num}" for num, repo in found
    )
    # No `permissionDecision` key: an absent decision defers to the normal
    # permission flow. Naming "allow" would suppress a prompt the user would
    # otherwise have seen.
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(names=names),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            "Reviewer request for {names} is not the last command in this call, "
            "so its success cannot be attributed and will not discharge "
            "no-unreviewed-pr. Run it alone."
        ).format(names=names)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
