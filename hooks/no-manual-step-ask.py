#!/usr/bin/env python3
"""PreToolUse: do not ask the user for hand work the agent can do itself.

ai-config#4698; shared/workflow/lab-operating-rules.md. Ezra, 2026-10-23:
"don't make me intervene manually to prompt threads to \"go\" if there's any
other way", and no merge buttons or manual steps. Blocks (deny) a user-visible
reply tool call (mcp__hearthbot__reply, post_message, update_message,
edit_message) whose text asks the user to

  * type "go" (or similar) into a Remote Control / RC session;
  * click or press a Merge button, or merge a PR themselves;
  * paste, append, or hand-add text into a file or settings (Ezra, 2026-10-26:
    "never ask me to paste anything into a file; always give me a script-based
    command to run that does it for me");
  * type or run a shell command in their own terminal (Ezra, 2026-10-29,
    ai-config#4842: "don't make me do anything myself unless there's absolutely
    no other way; instead, ask me for permission to do it for me"). This
    replaces the earlier fallback of handing one script command. A message that
    names a secret, token, password or credential is exempt, because those
    steps cannot be done for him.

The denial points at the substitute: start a fresh session on an already
approved environment with the brief as its opening task, retry a denied step
once, for merges ask for the plain `mwc` word, and for a file edit write an
idempotent script and give one command that runs it. Fails open on parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")

FILE_ASK = "a paste or hand-edit of a file"
COMMAND_ASK = "a shell command for the user to type or run"

# A secret has to be entered by the user, so a message about one may hand over
# a command (ai-config#4842).
SECRET = re.compile(r"\b(?:secrets?|tokens?|passwords?|passphrases?|credentials?|api keys?)\b", re.I)

# Imperative lead-in: a sentence start, or a polite or modal lead-in.
LEAD = r"(?:(?:^|[.!?\n:]\s*)|\b(?:please|you can|you could|can you|could you|just|then|but|and|or|so)\s+)"
SHELL_WORD = r"(?:ssh|bash|sh|zsh|python3?|Rscript|git|gh|sudo|brew|curl|cd)"

# A sentence that hands over one command running a script is the substitute the
# rule asks for. It exempts a paste-like clause only in the same sentence; a script
# named in another sentence does not. A reply that pairs an ask with a script in
# separate sentences is denied and rewritten as the script alone, which is the point.
SCRIPT_COMMAND = re.compile(
    r"\b(?:run(?:s|ning)?|use|execute)\b[^.,;\n]{0,40}"
    r"\b(?:python3?|bash|sh|Rscript)\s+[~/.\w-]+\.(?:py|sh|R)\b",
    re.I)
# A sentence ends at ., ! or ? plus whitespace, but not after e.g., i.e., vs. or etc.
SENTENCE_BREAK = re.compile(
    r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<!\betc\.)(?<=[.!?])\s+|\n+",
    re.I)

# A file cue unambiguous enough that add, put and copy, which are ordinary code
# verbs, can rely on it, and that "config dict" or "settings object" do not trip.
FILE_CUE = (
    r"(?:\bfile\b|\.json\b|\.ya?ml\b|\.toml\b|~/"
    r"|\b(?:the|your) (?:settings|config)\s*(?:[.!?]|\n|$))"
)

# Filler inside one ask: stays within a sentence, so it never crosses ? or !, and
# passes a period only inside a name (settings.json) or after e.g., i.e., vs., etc.
ABBREV = r"\b(?:e\.g|i\.e|vs|etc)\."
FILL = r"(?:[^.,\n!?]|\.(?=\S)|" + ABBREV + r")"
PASTE_FILL = r"(?:[^.\n!?]|\.(?=\S)|" + ABBREV + r")"

ASKS = (
    ("a manual 'go' in a Remote Control session", re.compile(
        r"\b(?:type|say|send|reply|enter|answer)\s+(?:with\s+)?[`'\"*]*go\b[`'\"*]*[^.\n]{0,60}"
        r"\b(?:remote control|RC|session|device)\b"
        r"|\b(?:remote control|RC)\b[^.\n]{0,80}\b(?:type|say|send|reply|enter)\b[^.\n]{0,40}[`'\"*]\bgo\b",
        re.I)),
    ("a merge button or manual merge", re.compile(
        r"\b(?:click|press|hit|tap)\b[^.\n]{0,30}\bmerge\b[^.\n]{0,20}\bbutton\b"
        r"|\bmerge (?:it|them|the PRs?) (?:yourself|manually|by hand)\b",
        re.I)),
    (COMMAND_ASK, re.compile(
        LEAD + r"(?:type|run|paste|enter|execute)\b[^.\n]{0,60}"
        r"\b(?:in|into|on|at)\s+(?:your|the)\s+(?:\w+\s+)?(?:terminal|shell|command line|prompt)\b",
        re.I)),
    (COMMAND_ASK, re.compile(
        LEAD + r"(?:type|run|paste|enter|execute)\b[^.\n]{0,40}?[`'\"]*\b"
        + SHELL_WORD + r"\s+[~/.\w'\"-]",
        re.I)),
    # paste, append and insert are rarely anything but a hand-edit, so a bare
    # settings or config is cue enough after them.
    (FILE_ASK, re.compile(
        r"(?:(?:^|[.!?\n:]\s*)|\b(?:please|you can|you could|can you|could you|just)\s+)(?:paste|append|insert)"
        r"\b" + PASTE_FILL + r"{0,80}\b(?:into|to|in|onto)\b"
        + PASTE_FILL + r"{0,60}(?:" + FILE_CUE + r"|\b(?:settings|config)\s*(?:[.!?]|\n|$))",
        re.I)),
    # add, put and copy are ordinary code verbs, so after a polite lead-in they
    # need the strong file cue.
    (FILE_ASK, re.compile(
        r"\b(?:please|you can|you could|can you|could you|just)\s+(?:add|put|copy)"
        r"\b" + FILL + r"{0,60}?\b(?:into|to|in|onto)\b"
        + FILL + r"{0,40}?" + FILE_CUE,
        re.I)),
    # A bare "Add ... to settings.json" is the plainest hand-add ask. add, put and
    # copy are also ordinary code verbs, so this form needs a strong file cue.
    (FILE_ASK, re.compile(
        r"(?:^|[.!?\n:]\s*)(?:add|put|copy)\b" + FILL + r"{0,60}?\b(?:into|to|in|onto)\b"
        + FILL + r"{0,40}?" + FILE_CUE,
        re.I)),
)

REASON = (
    "[hook: no-manual-step-ask] This message asks the user for hand work: {what}. "
    "Do it another way: ask the user for permission to do the step yourself (a decision card, an approval prompt, "
    "or a permission rule you ask to add), then run it; only a secret may be handed back to the user (ai-config#4842). For a Remote Control session, start a fresh one on an "
    "already approved environment with the brief as its opening task (no 'go' to type). "
    "For a merge, ask for plain `mwc`. For a file edit, write an idempotent script, test it, and give one command that runs it (no pasting). For a denied step, retry once unchanged. "
    "shared/workflow/lab-operating-rules.md; ai-config#4698."
)


def scripted(text: str, match: re.Match) -> bool:
    """True when the sentence holding the ask's last visible character tells the user to run a script command."""
    ask_end = len(text[:match.end()].rstrip()) - 1
    position = 0
    for piece in SENTENCE_BREAK.split(text):
        start = text.find(piece, position)
        position = start + len(piece)
        if start <= ask_end < position:
            return bool(SCRIPT_COMMAND.search(piece))
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPLY_TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    text = tool_input.get("text") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return 0
    for what, pattern in ASKS:
        if what == COMMAND_ASK and SECRET.search(text):
            continue
        for match in pattern.finditer(text):
            if what == FILE_ASK and scripted(text, match):
                continue
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON.format(what=what),
                }
            }))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
