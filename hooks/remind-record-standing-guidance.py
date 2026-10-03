#!/usr/bin/env python3
"""UserPromptSubmit reminder: standing guidance belongs in its global home now.

When Ezra states a standing rule ("always ...", "never ...", "from now on",
"going forward", "it's up to you whether", "the rule is", "assume ... unless"),
the failure is to save it only in project memory, or to wait to be told it is
global. AGENTS.md ("Generalize instructions to every AI agent by default") and
the global-by-default rule say the rule goes to its global home in the same
turn: ai-config for agent rules, psw for prose rules, gha for checks. Project
memory is allowed in addition, but is not enough alone.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Same reason as remind-ums-after-error.py, whose conventions this copies: the
user's message is right to send and the agent's reply is right to send. Only
the follow-up is owed, so this only ADDS context on the next prompt. There is
no code path here that blocks or alters anything.

WHAT IT CHECKS
--------------
Two messages: the new prompt (payload["prompt"]) and the most recent earlier
human message in the transcript.

  * The new prompt fires immediately when it reads as standing guidance,
    because nothing can have been recorded after a message that just arrived.
  * The earlier message fires only when no LATER assistant tool call recorded
    it: a Write/Edit under ai-config, psw, shared/, memories/, AGENTS.md or
    CLAUDE.md; a Bash command that writes or runs git on such a path; or an
    Agent/Task dispatch whose prompt names ai-config or psw.

"Reads as standing guidance" is a conservative regex over visible prose
(code fences, blockquotes and inline code removed), skipping messages under
MIN_CHARS characters and matches that sit inside a question.

Fires once per distinct message, via a sentinel in the temp dir keyed on a
hash of the transcript path and the message text. Fails OPEN and SILENT: any
parse trouble prints nothing.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Shorter messages are acknowledgements ("ok thanks"), not rules.
MIN_CHARS = 25

# Apostrophe spelled as an escape, so this file stays pure ASCII.
_APOS = "['\u2019]"

# Conservative: each alternative is a phrase that states a rule about future
# behaviour. A bare "should" or "don't" is far too common in task requests.
GUIDANCE_RE = re.compile(
    r"""(
      \bfrom\s+now\s+on\b
    | \bgoing\s+forward\b
    | \bfrom\s+here\s+on\b
    | \bthe\s+rule\s+is\b
    | \bnew\s+(?:global\s+)?rule\b
    | \bstanding\s+(?:rule|instruction|guidance)\b
    | \bstart\s+enforcing\b
    | \bit""" + _APOS + r"""?s\s+up\s+to\s+you\s+(?:whether|if|when)\b
    | \bassume\b[^.!?\n]{3,80}\bunless\b
    | (?:^|[.!?;:\n]\s*|\byou\s+|\bshould\s+|\bmust\s+|\bplease\s+)
        (?:always|never)\b
    | (?:^|[.!?;:\n]\s*)(?:and\s+|but\s+|please\s+)?
        (?:do\s+not|don""" + _APOS + r"""t)\s+
        (?!worry\b|forget\b|bother\b|know\b|think\b|see\b|understand\b)\w+
    | \b(?:you|agents?|claude)\s+should\s+(?:not|stop|start)\b
    )""",
    re.I | re.X,
)

FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)
TICKED = re.compile(r"`[^`\n]*`")
REMINDER_BLOCK = re.compile(r"<system-reminder>.*?</system-reminder>", re.S | re.I)

# Where a recorded rule lands: ai-config, psw, or their file layout.
GLOBAL_PATH = re.compile(
    r"(ai-config|/psw/|^psw/|\bpsw/|(?:^|/)shared/|(?:^|/)memories?/|AGENTS\.md|CLAUDE\.md)",
    re.I,
)
# A Bash command only counts when it writes or uses git, not when it reads.
WRITE_CMD = re.compile(r"\bgit\b|\btee\b|\bsed\s+-i|>>?\s*\S|\bcp\b|\bmv\b")
AGENT_TARGET = re.compile(r"\bai-config\b|\bpsw\b", re.I)

# Compared case-insensitively: harnesses spell the same tool differently.
WRITE_TOOLS = {
    "write", "edit", "notebookedit", "multiedit", "write_to_file", "replace_file_content",
    "apply_diff", "strreplace", "editnotebook", "edit_file", "create_file", "apply_patch",
    "str_replace_editor",
}
BASH_TOOLS = {"bash", "run_command", "execute_command", "terminal", "shell"}
AGENT_TOOLS = {"task", "agent"}


def visible_prose(text):
    """Drop reminder blocks, code fences, blockquotes and inline code."""
    text = REMINDER_BLOCK.sub(" ", text)
    text = FENCE.sub(" ", text)
    text = QUOTED.sub(" ", text)
    return TICKED.sub(" ", text)


def standing_phrase(text):
    """Return the matched guidance phrase in `text`, or None."""
    prose = visible_prose(text).strip()
    if len(prose) < MIN_CHARS:
        return None
    for hit in GUIDANCE_RE.finditer(prose):
        start = prose.rfind("\n", 0, hit.start())
        for ch in ".!?":
            start = max(start, prose.rfind(ch, 0, hit.start()))
        ends = [e for e in (prose.find(c, hit.end()) for c in ".!?\n") if e != -1]
        end = min(ends) if ends else len(prose)
        terminator = prose[end] if end < len(prose) else ""
        if terminator == "?":
            continue  # the sentence is a question, not a rule
        phrase = " ".join(hit.group(0).split())
        return phrase.strip(" .!?;:,") or None
    return None


def _text_of(message):
    """Human text of a user record, or None for tool results and the like."""
    blocks = (message.get("message") or {}).get("content")
    if blocks is None:
        blocks = message.get("content")
    if isinstance(blocks, str):
        return blocks
    if not isinstance(blocks, list):
        return None
    parts = [
        b.get("text") or ""
        for b in blocks
        if isinstance(b, dict) and b.get("type") == "text"
    ]
    return "\n".join(parts) if parts else None


def scan(path):
    """Return (human_messages, recordings).

    human_messages is a list of (record_index, text); recordings is the list
    of record indexes holding a tool call that recorded guidance globally.
    """
    humans, recorded = [], []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            try:
                m = json.loads(line)
            except Exception:
                continue
            if not isinstance(m, dict) or m.get("isSidechain"):
                continue
            role = m.get("type") or m.get("role")
            if role == "user":
                text = _text_of(m)
                if text is not None and text.strip():
                    humans.append((i, text))
                continue
            if role != "assistant":
                continue
            blocks = (m.get("message") or {}).get("content") or m.get("content") or []
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name, inp = b.get("name") or "", b.get("input") or {}
                if not isinstance(inp, dict):
                    continue
                if name.lower() in WRITE_TOOLS:
                    target = str(
                        inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
                        or inp.get("TargetFile") or inp.get("target_file") or inp.get("filePath")
                        or inp.get("target_notebook") or ""
                    )
                    if GLOBAL_PATH.search(target):
                        recorded.append(i)
                elif name.lower() in BASH_TOOLS:
                    cmd = str(inp.get("command") or "")
                    if GLOBAL_PATH.search(cmd) and WRITE_CMD.search(cmd):
                        recorded.append(i)
                elif name.lower() in AGENT_TOOLS:
                    blob = str(inp.get("prompt") or "") + str(inp.get("description") or "")
                    if AGENT_TARGET.search(blob):
                        recorded.append(i)
    return humans, recorded


def _first_time(path, text):
    """True once per (transcript, message); records the sentinel."""
    key = hashlib.sha256(f"{path}:{text}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-record-guidance-{key}")
    if os.path.exists(sentinel):
        return False
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("1")
    except Exception:
        pass
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    prompt = payload.get("prompt")
    prompt = prompt if isinstance(prompt, str) else ""
    path = payload.get("transcript_path") or ""
    if not isinstance(path, str):
        return 0

    try:
        humans, recorded = ([], [])
        if path and os.path.isfile(path):
            humans, recorded = scan(path)

        found = []  # (phrase, which)
        phrase = standing_phrase(prompt) if prompt else None
        if phrase and _first_time(path, prompt):
            found.append((phrase, "your new message"))

        earlier = [(i, t) for i, t in humans if t.strip() != prompt.strip()]
        if earlier:
            idx, text = earlier[-1]
            ephrase = standing_phrase(text)
            if ephrase and not any(r > idx for r in recorded) and _first_time(path, text):
                found.append((ephrase, "the previous user message"))
    except Exception:
        return 0

    if not found:
        return 0

    for phrase, which in found:
        print(
            f'Standing-guidance reminder: {which} reads as a standing rule '
            f'("{phrase}").\n'
            "Record it in its global home in this same turn (ai-config for "
            "agent rules, psw for prose rules, gha for checks), and start "
            "following it now, without waiting to be told it is global. "
            "Project memory is allowed too, but is not enough alone.\n"
            "If it is only a one-off task instruction, disregard this."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
