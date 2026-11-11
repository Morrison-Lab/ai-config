#!/usr/bin/env python3
"""UserPromptSubmit reminder: a whether-or-how question gets a start-or-file ask.

Ezra (2026-11-10, ai-config#5287): "when I ask you whether we should do
something or how we should do something, etc, come up with a recommendation,
but before implementing, ask me if you should start now or file it for later
(with your recommendation). only start immediately if I give you a
declarative instruction."  The rule is shared/workflow/start-or-file.md.

Injects, never blocks. A deny form is not workable: whether a prompt is a
question or an instruction ("can you push that?") is a reading of intent, and a
PreToolUse deny on Edit or Write after a question would also block the research
and memory writes the rule allows. Fails OPEN and SILENT on any parse trouble.
"""
import json
import re
import sys

QUESTION_RE = re.compile(
    r"""(
      \b(should|shall)\s+(we|i)\b
    | \bhow\s+(should|would|could|can|do|might)\s+(we|i)\b
    | \b(can|could)\s+we\b
    | \bis\s+it\s+worth\b
    | \bwould\s+it\s+(make\s+sense|help|be\s+(better|worth))\b
    | \bwhat(\s+do|\s+would)?\s+you\s+(think|recommend|suggest)\b
    | \bwhat'?s\s+the\s+best\s+way\b
    | \bwhat\s+if\s+we\b
    | \bany\s+(ideas|suggestions|thoughts)\b
    | \bwhy\s+don'?t\s+we\b
    | \bdo\s+you\s+think\b
    | \bwhether\s+(we|i|to)\b
    | ^\s*should\b
    | \bhow\s+about\b
    | \bgood\s+idea\b
    | \bdo\s+you\s+recommend\b
    | \bwhy\s+not\b
    )""",
    re.I | re.X | re.M,
)
FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)
TICKED = re.compile(r"`[^`\n]*`")
REMINDER_BLOCK = re.compile(r"<system-reminder>.*?</system-reminder>", re.S | re.I)


def question(text):
    prose = TICKED.sub(" ", QUOTED.sub(" ", FENCE.sub(" ", REMINDER_BLOCK.sub(" ", text))))
    m = QUESTION_RE.search(prose)
    return " ".join(m.group(0).split()) if m else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        prompt = payload.get("prompt") if isinstance(payload, dict) else None
        found = question(prompt) if isinstance(prompt, str) else None
    except Exception:
        return 0
    if found:
        print(
            f'Start-or-file reminder: the prompt asks "{found}".\n'
            "If that is a whether-or-how question rather than a declarative "
            "instruction, research as needed, give a recommendation, and ask "
            "whether to start now or file it for later, recommending one. "
            "Do not edit, commit, push, open a PR or file an issue for the "
            "question's work until the user answers. Any declarative "
            "instruction in the same message (a `cai:` rule, \"fix X\") still "
            "starts at once (shared/workflow/start-or-file.md)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
