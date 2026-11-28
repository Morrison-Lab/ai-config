"""A typed approval for one exact lease-pinned branch-deleting push.

CC Safety Net's `git.push-delete` rule refuses every agent
`git push --delete`, and nothing said in chat lifted it (ai-config#6117).
`hooks/run-cc-safety-net.py` passes one such push only when all hold:

- The deny names `git.push-delete` as its only rule (`sole_push_delete_deny`).
- The command is `git push https://github.com/<o>/<r>
  --force-with-lease=refs/heads/<b>:<sha> ... --delete <b> ...` and nothing
  else: every deleted branch is leased to its 40-hex tip and every lease is
  deleted, so GitHub refuses a branch that moved (`leased_delete_push`).
- The user TYPED a line reading only `approve-push-delete <key>` within
  `WINDOW` seconds; `<key>` is the first `KEY_HEX` hex digits of the raw
  command's sha256 (`approval_key`), so one changed byte is another key.
  "Typed" is the merge hooks' `_typed_text`: reminders, coordinator notes,
  non-principal messages and card taps (whose label the agent wrote) are
  removed. A line typed in a project thread arrives inside a principal
  `<message>` element, which is opened first (ai-config#6177).

The approval is not consumed: a push that failed on the network can be
retried within the window, and one that ran fails at GitHub, its leased
branches gone.

LIMIT, shared with every typed-words gate in ai-config: an agent that can
write to its own transcript file could forge a user record. The window
and the exact-command key narrow what a forged record could do to one
lease-pinned push the agent itself composed.
"""
from __future__ import annotations

import hashlib
import re
import shlex
from datetime import datetime, timezone

WINDOW = 1800
PREFIX = "approve-push-delete"
KEY_HEX = 32
# The whole line, so a sentence that only mentions the approval is not one.
RX_APPROVAL = re.compile(rf"^[ \t]*approve-push-delete[ \t]+([0-9a-f]{{{KEY_HEX}}})[ \t]*$",
                         re.IGNORECASE | re.MULTILINE)
RX_LEASE = re.compile(r"\A--force-with-lease=refs/heads/([A-Za-z0-9._/-]+):([0-9a-fA-F]{40})\Z")
RX_BRANCH = re.compile(r"\A[A-Za-z0-9._/-]+\Z")
# The full URL, never a remote name: `origin` resolves through local git
# config, so the key would not bind which repository loses the branches.
RX_REMOTE = re.compile(
    r"\Ahttps://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+?(?:\.git)?\Z")
RX_UNSAFE = re.compile(r"[;&|`$<>(){}\\\n\r\v\f'\"*?!~#]")
# A project-thread wake wraps the user's message in one element on one line
# (`<message ... from="human" trust="principal" ...>approve-push-delete
# <key></message>`), so the line-anchored match needs the element's body on
# a line of its own (ai-config#6177). Only an element whose parsed attributes
# say exactly `from="human"` and `trust="principal"` is opened; any other
# stays wrapped and cannot match. The harness escapes `<` in a body, so
# neither a body holding one nor an element nested inside another message
# is opened: a tag there could not be the user's.
RX_MESSAGE = re.compile(r"<message(\s[^<>]*)?>([^<]*)</message>", re.IGNORECASE)
RX_ATTR = re.compile(r"\s+([\w-]+)=\"([^\"]*)\"")
RX_MESSAGE_OPEN = re.compile(r"<message\b", re.IGNORECASE)
RX_MESSAGE_CLOSE = re.compile(r"</message\s*>", re.IGNORECASE)


def _principal_attrs(attrs: str) -> bool:
    """Whether `attrs` parse wholly as attributes naming the human principal."""
    pairs = RX_ATTR.findall(attrs)
    if RX_ATTR.sub("", attrs).strip():
        return False
    names = [name.lower() for name, _ in pairs]
    if names.count("from") != 1 or names.count("trust") != 1:
        return False
    values = {name.lower(): value for name, value in pairs}
    return values["from"] == "human" and values["trust"] == "principal"


def open_principal_messages(text: str) -> str:
    """`text` with each top-level principal message's body on its own line."""
    def opened(m):
        before = text[:m.start()]
        nested = len(RX_MESSAGE_OPEN.findall(before)) > len(RX_MESSAGE_CLOSE.findall(before))
        if nested or not _principal_attrs(m.group(1) or ""):
            return m.group(0)
        return f"\n{m.group(2)}\n"
    return RX_MESSAGE.sub(opened, text)


RX_RULE = re.compile(r"\bRule:\s*([A-Za-z0-9._-]+)")
RX_REASON = re.compile(r"\bReason:")
LIFTED_RULE = "git.push-delete"


def sole_push_delete_deny(said: str) -> bool:
    """Whether CC Safety Net's output names git.push-delete and no other rule.

    A decision can carry more than one reason. Lifting it because one of
    them is git.push-delete would drop the others too, so the lift needs
    exactly one `Rule:` line, naming git.push-delete, and at most one
    `Reason:` line.
    """
    return (RX_RULE.findall(said) == [LIFTED_RULE]
            and len(RX_REASON.findall(said)) <= 1)


def approval_key(command: str) -> str:
    """The KEY_HEX hex digits the user types to approve exactly `command`."""
    return hashlib.sha256(command.encode("utf-8")).hexdigest()[:KEY_HEX]


def leased_delete_push(command: str) -> bool:
    """Whether `command` is only a lease-pinned delete of remote branches."""
    text = command.strip()
    if not text or RX_UNSAFE.search(text):
        return False
    try:
        tokens = shlex.split(text)
    except ValueError:
        return False
    if tokens[:2] != ["git", "push"] or len(tokens) < 6:
        return False
    if not RX_REMOTE.match(tokens[2]):
        return False
    leases, i = {}, 3
    while i < len(tokens) and tokens[i].startswith("--force-with-lease="):
        m = RX_LEASE.match(tokens[i])
        if not m or m.group(1) in leases:
            return False
        leases[m.group(1)] = m.group(2)
        i += 1
    if not leases or i >= len(tokens) or tokens[i] != "--delete":
        return False
    deletes = tokens[i + 1:]
    if len(deletes) != len(set(deletes)):
        return False
    if not all(plain_branch(b) for b in deletes):
        return False
    return set(deletes) == set(leases)


def plain_branch(name: str) -> bool:
    """Whether `name` can only mean `refs/heads/<name>` on the remote.

    A delete of `refs/heads/main` under a lease on
    `refs/heads/refs/heads/main` would pass a plain set comparison while
    the lease pins a different ref, so a name that git could read as a full
    ref (`refs/...`, `HEAD`) is refused, as is one git refuses anyway.
    """
    if not RX_BRANCH.match(name) or name.startswith(("-", "/", "refs/")):
        return False
    if name == "HEAD" or name.endswith(("/", ".lock", ".")):
        return False
    return ".." not in name and "//" not in name


def _when(rec) -> float | None:
    stamp = rec.get("timestamp")
    if not isinstance(stamp, str):
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def typed_approval(records, blocks, typed_text, key: str, now: float) -> bool:
    """Whether a user record from the last WINDOW seconds types the approval.

    `records` is an iterable of transcript records, and `blocks` and
    `typed_text` are the merge hooks' readers, passed in so this module
    keeps one copy of the "typed" rule rather than its own.
    """
    for rec in records:
        if rec.get("isSidechain"):
            continue
        role = rec.get("type") or (rec.get("message") or {}).get("role")
        if role not in ("user", "USER_INPUT"):
            continue
        when = _when(rec)
        if when is None or not 0 <= now - when <= WINDOW:
            continue
        for block in blocks(rec):
            if block.get("type") != "text":
                continue
            text = typed_text(block.get("text") or "")
            text = open_principal_messages(text)
            if any(m.group(1).lower() == key for m in RX_APPROVAL.finditer(text)):
                return True
    return False
