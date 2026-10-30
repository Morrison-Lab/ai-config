#!/usr/bin/env python3
"""UserPromptSubmit reminder: a maintainer's PR comment is a class, not a line.

Ezra, 2026-10-17: "you should be learning from every comment I make on every
PR, as soon as I make it" (after sds#268 took 25 corrections, most of them the
same few classes repeated line by line).

The other reminders do not see this case.
`remind-learn-from-review.py` waits for the AGENT to say it accepts a finding,
and `remind-encode-user-correction.py` and `remind-record-standing-guidance.py`
read chat prose the user typed. A maintainer's comment on a PR arrives as a
GitHub event (`<event source="github" kind="...">` with the comment JSON), so
none of them fires until the agent has already fixed the one line.

This fires on the event itself: a GitHub comment or review event whose author
is the maintainer. It injects the procedure in `shared/workflow/learn-from-review-findings.md`
("Every maintainer comment"): sweep the whole class across the PR, record the
rule or check in its global home in the same turn, and name where.

Inject-only, like its siblings: fixing the comment is right, only the follow-up
is owed, so there is no code path that blocks or alters anything. Fires once per
distinct event (sentinel in the temp dir keyed on a content hash). Fails OPEN
and SILENT: any trouble parsing an event prints nothing (a bad config file
warns on stderr, see below). The maintainer logins come from
`_configured_maintainers` (MAINTAINER_LOGINS, else the local config file, else
`d-morrison`); see its docstring.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

EVENT = re.compile(r'<event\b[^>]*source="github"[^>]*>', re.I)
KIND = re.compile(r'kind="([^"]*)"', re.I)
# Only events that carry written feedback: review_requested and review_dismissed
# are state changes with no comment text, so a substring test on "review" misfires.
COMMENTISH = re.compile(
    r"^(?:issue_comment|pull_request_review_comment|review_comment"
    r"|pull_request_review|commit_comment)(?:\.|$)", re.I)


def _configured_maintainers():
    """Comma-separated maintainer logins: `MAINTAINER_LOGINS`, else the
    "maintainers" list in the JSON file `AI_CONFIG_LOCAL` names (default
    `~/.config/ai-config/local.json`, see `ai-config.local.example.json`),
    else `d-morrison`, the repo owner, so an unconfigured install keeps its
    behaviour. A missing file or an absent or empty list is "unconfigured";
    a file that exists but is unreadable, is not a JSON object, or holds
    anything but a list of non-empty strings warns on stderr and falls back
    too. Standalone: hooks are staged one file at a time and cannot import
    a sibling module."""
    raw = os.environ.get("MAINTAINER_LOGINS")
    if raw is not None:
        return raw
    path = os.path.expanduser(
        os.environ.get("AI_CONFIG_LOCAL") or "~/.config/ai-config/local.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                names = json.load(fh).get("maintainers", [])
            if not isinstance(names, list) or not all(
                    isinstance(n, str) and n.strip() for n in names):
                raise ValueError('"maintainers" must be a list of login strings')
            if names:
                return ",".join(names)
        except (OSError, ValueError, AttributeError) as err:
            print(f"ai-config: ignoring {path}: {err}", file=sys.stderr)
    return "d-morrison"


def logins():
    raw = _configured_maintainers()
    return [x.strip() for x in raw.split(",") if x.strip()]


def maintainer_event(prompt):
    """Return the matched login when the prompt holds a maintainer comment event."""
    for m in EVENT.finditer(prompt):
        kind = KIND.search(m.group(0))
        if not kind or not COMMENTISH.search(kind.group(1)):
            continue
        end = prompt.find("</event>", m.end())
        body = prompt[m.end(): end if end != -1 else len(prompt)]
        for login in logins():
            if re.search(r'"(?:login|author|user|sender)"\s*:\s*(?:\{[^{}]*"login"\s*:\s*)?"'
                         + re.escape(login) + r'"', body, re.I):
                return login
    return None


def first_time(prompt):
    key = hashlib.sha256(prompt.encode("utf-8", "ignore")).hexdigest()[:24]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-generalize-comment-{key}")
    if os.path.exists(sentinel):
        return False
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("1")
    except OSError:
        pass
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str):
        return 0
    try:
        login = maintainer_event(prompt)
        if not login or not first_time(prompt):
            return 0
    except Exception:
        return 0
    print(
        f"Maintainer-comment reminder: {login} commented on a PR.\n"
        "Before fixing the one line: name the class of the comment, sweep the "
        "whole PR for that class, and in this same turn record the rule or check "
        "in its global home (ai-config for agent rules, psw for prose rules, gha "
        "for checks; link an existing one instead of copying it). Say in your "
        "reply which rule or check you recorded, or that none applies and why. "
        "See shared/workflow/learn-from-review-findings.md, 'Every maintainer "
        "comment'.\n"
        "If the comment is only a question or thanks, disregard this."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
