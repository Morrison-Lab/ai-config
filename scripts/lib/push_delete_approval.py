"""A typed approval for one exact lease-pinned branch-deleting push.

CC Safety Net's `git.push-delete` rule refuses every `git push --delete`
from an agent, and nothing the user can say in chat lifts it: the only
routes were the user running the push in their own terminal, or relaxing
the rule for every command (ai-config#6117, after the 12 merged `lds`
branches Ezra approved on 2026-11-20 stayed undeletable for four days).

This module lets `hooks/run-cc-safety-net.py` pass exactly one such push
when, and only when, all of these hold:

- CC Safety Net's deny names `git.push-delete` as its only rule
  (`sole_push_delete_deny`), so no other reason is dropped with it.
- The command is `git push <github-url> --force-with-lease=refs/heads/<b>:<sha>
  ... --delete <b> ...` and nothing else: every deleted branch carries a
  lease naming its 40-character tip, and every lease names a deleted
  branch. A branch that moved since it was checked is then refused by
  GitHub itself. No other option, no shell operator, no expansion
  (`leased_delete_push`).
- The user TYPED a line reading only `approve-push-delete <key>` in this
  session within the last `WINDOW` seconds, where `<key>` is the first 16
  hex digits of the command's sha256 (`approval_key`), hashed exactly as
  the command arrives. One changed byte, whitespace included, is a
  different key. A line that only mentions the approval ("do not
  approve-push-delete <key>") does not count.
  "Typed" is the merge hooks' rule (`_typed_text` in
  `block-merge-without-clean-checker.py`): a user-role text block, with
  system reminders, coordinator notes, non-principal messages and
  decision-card taps removed. A card tap is refused because the agent
  wrote its label.

The approval never covers another command, so it cannot be widened. It is
not consumed: within the window the same command is allowed again, so a
push that failed on the network can be retried. Repeating it after it ran
is harmless: its leases then name branches that no longer exist, and
GitHub refuses the push.

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
# The whole line, so a sentence that only mentions the approval is not one.
RX_APPROVAL = re.compile(r"^[ \t]*approve-push-delete[ \t]+([0-9a-f]{16})[ \t]*$",
                         re.IGNORECASE | re.MULTILINE)
RX_LEASE = re.compile(r"\A--force-with-lease=refs/heads/([A-Za-z0-9._/-]+):([0-9a-f]{40})\Z")
RX_BRANCH = re.compile(r"\A[A-Za-z0-9._/-]+\Z")
# The full URL, never a remote name: `origin` resolves through local git
# config, so the key would not bind which repository loses the branches.
RX_REMOTE = re.compile(
    r"\Ahttps://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+?(?:\.git)?\Z")
RX_UNSAFE = re.compile(r"[;&|`$<>(){}\\\n\r\v\f'\"*?!~#]")
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
    """The 16 hex digits the user types to approve exactly `command`."""
    return hashlib.sha256(command.encode("utf-8")).hexdigest()[:16]


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
            if any(m.group(1).lower() == key for m in RX_APPROVAL.finditer(text)):
                return True
    return False
