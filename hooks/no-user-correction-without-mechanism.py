#!/usr/bin/env python3
"""Stop: a turn that follows a user correction must build or cite a mechanism.

ai-config#4698. Ezra, 2026-10-23: "I'm tired of watching the agents make the
same mistakes over and over again". Two hooks already cover neighbouring
ground and leave this gap:

  * remind-encode-user-correction.py (UserPromptSubmit) recognizes a user
    correction, but only INJECTS a reminder, so a turn can read it and end
    having recorded a note.
  * no-mistake-without-a-hook.py (Stop) blocks, but keys on the AGENT's own
    admission of a mistake, so a correction the agent answers without
    admitting anything never reaches it.

This hook closes the loop. At Stop it finds the user's latest message; if it
reads as a correction (the sibling's MATCHER, imported so the two cannot
drift), it looks at everything after that message for a mechanism:

  * hook work: a tool call naming `hooks/<script>.py`, `hooks.json` or a hook
    event (no-mistake-without-a-hook's HOOK_WORK);
  * check work: a tool call naming a gha check (`check-*/action.yml` or a
    `check-*.yml` workflow);
  * a "Mechanism: <issue or PR URL>" line, for work done in another repo or
    by a subagent; or
  * a plain statement that the mistake is not mechanizable, with the reason
    (no-mistake-without-a-hook's NOT_HOOKABLE).

None of these in the turn means the turn may not end: the hook blocks once
per distinct user message and states what is owed. Blocking is right here
(unlike for an admission) because the correction has already been delivered
and answered; only the follow-up is owed.

Fails OPEN and SILENT on any parse trouble.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))


def _sibling(name):
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location("_sib_" + re.sub(r"\W", "_", name), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_corr = _sibling("remind-encode-user-correction.py")
_mist = _sibling("no-mistake-without-a-hook.py")

CHECK_WORK = re.compile(r"check-[\w-]+/action\.yml|\.github/workflows/check-[\w-]+\.yml", re.I)


def human_text(record):
    """Text of a human user record, or None for tool results and other records."""
    if (record.get("type") or record.get("role")) != "user":
        return None
    blocks = (record.get("message") or {}).get("content")
    if blocks is None:
        blocks = record.get("content")
    if isinstance(blocks, str):
        return blocks
    if not isinstance(blocks, list):
        return None
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
        return None
    parts = [b.get("text") or "" for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(parts) if parts else None


def owed(path):
    """Return (quote, key) when the latest correction has no mechanism after it."""
    records = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            if isinstance(m, dict) and not m.get("isSidechain"):
                records.append(m)

    # A correction stays owed until a later assistant record discharges it.
    # Any human-side record counts, including a GitHub review comment that
    # reached the session as an event (the sibling's typed_text decodes
    # those and skips bot authors), and a later non-correction record
    # (a CI notification, "thanks") does not clear it.
    pending = None
    for m in records:
        role = m.get("type") or m.get("role")
        if role == "user":
            text = human_text(m)
            if text is None or not text.strip():
                continue
            match = _corr.MATCHER.search(_corr.typed_text(text))
            if match is not None:
                quote = " ".join(match.group(0).split())[:80]
                key = hashlib.sha256(f"{path}:{text}".encode()).hexdigest()[:16]
                pending = (quote, key)
        elif role == "assistant" and pending is not None:
            blocks = (m.get("message") or {}).get("content") or m.get("content") or []
            if isinstance(blocks, str):
                blocks = [{"type": "text", "text": blocks}]
            for b in blocks if isinstance(blocks, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    blob = (b.get("name") or "") + " " + json.dumps(b.get("input") or {})
                    if _mist.HOOK_WORK.search(blob) or CHECK_WORK.search(blob):
                        pending = None
                elif b.get("type") == "text":
                    if _mist.discharges(_mist.visible_prose(b.get("text") or "")):
                        pending = None
    return pending


MESSAGE = (
    "[hook: no-user-correction-without-mechanism] The user's latest message "
    'reads as a correction or complaint ("{quote}"), and nothing after it '
    "built or cited a mechanism.\n\n"
    "A reminder and a note do not stop the next session making the same "
    "mistake. Before ending this turn, do one of:\n"
    "  * write the hook (hooks/<name>.py with a test that reproduces the "
    "mistake, registered in hooks/hooks.json) or the failing gha check;\n"
    "  * if the work is in another repo or a subagent, put a line of its own "
    "that starts \"Mechanism: <issue or PR URL>\";\n"
    "  * say plainly that the mistake is not mechanizable, and why (no "
    "condition decidable from the transcript).\n"
    "If the matched words were not a correction of you (quoted text, a remark "
    "about someone else), say so in one line and carry on."
)


def main() -> int:
    if _corr is None or _mist is None:
        return 0
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        found = owed(path) if path and os.path.isfile(path) else None
    except Exception:
        return 0
    if not found:
        return 0
    quote, key = found
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-no-user-correction-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("1")
    except Exception:
        pass
    print(json.dumps({"decision": "block", "reason": MESSAGE.format(quote=quote)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
