#!/usr/bin/env python3
"""UserPromptSubmit: a user correction becomes a committed rule, not a memory.

ai-config#4208. On 2026-10-02 the user wrote, from a claude.ai project
(verbatim): "it's so frustrating when I have to tell you to do things that
feel obvious, and hwen I have to repeat msyelf between sessions or
projects". The rules for this already existed -- AGENTS.md "Treat user
profanity and frustration as urgent defect signals" and CLAUDE.md "Encoding
reusable feedback into ai-config" -- and neither had a trigger:

  - remind-ums-after-error.py, remind-learn-from-review.py and
    remind-ums-on-scrutiny.py key on the AGENT's own admission, an accepted
    review finding, or a read review. A user correcting the agent, or saying
    they have repeated themselves, matches none of them.
  - In a session whose repo is not ai-config, the natural landing place is
    whatever memory the host offers (a claude.ai project's memory, ~/.claude
    auto-memory). Each is invisible to every OTHER project, which is exactly
    how the user ends up repeating themselves.

So this matches the user's prompt for three families of phrase -- having to
say something again, the agent repeating a miss, and the agent reading an
instruction wrongly -- and injects the procedure: fix the instance, widen the
correction to its general rule, commit that rule in this turn to the repo
that owns it (ai-config for a cross-repo rule), and add a hook when the miss
is decidable. Host memory is allowed in addition, never instead.

It does not try to catch every plain correction ("no, use UTC"): those carry
no lexical marker that separates them from an ordinary instruction, and a
reminder that fires on every "no" or "again" teaches the reader to skip it.
Each pattern therefore needs wording that is rare outside a complaint to an
agent that missed something, and windows stay inside one sentence. Rare is
not never ("I repeat: great job" fires), so the reminder ends with an
explicit instruction to ignore it when the words were not a correction.

Inject-only, like its siblings: the user's message is never blocked. Text the
user did not type as a correction is removed before matching: fenced and
indented code, `>` quotes, inline code and double-quoted spans, and
<system-reminder> / <pasted_content> blocks. It fires on every matching
prompt rather than once per session: each correction is its own rule.
"""
import json
import re
import sys

PATTERNS = [
    # Having to say something again.
    r"\brepeat(?:ing|ed)? myself\b",
    r"\bmake me repeat\b",
    r"^\s*I repeat:",
    r"\b(?:have|had|keep|kept|need) (?:to )?(?:tell|telling|remind|reminding) you"
    r" (?:to|not|that you|again|this|that|every|each|over)\b",
    r"\b(?:keep|kept) having to (?:tell|remind|repeat|say|ask)\b",
    r"\bI(?:'ve| have) had to (?:tell|remind|repeat|say|ask)\b",
    r"\brepeated (?:this|that|it|myself) (?:many|multiple|several|\d|again|before)",
    r"\b(?:have to|need to) keep (?:saying|telling|asking|reminding)\b",
    r"\bI(?:'ve| have)? (?:already|just) (?:told|explained (?:this|that|it) to) you\b",
    r"\bI(?:'ve| have)? told you (?:before|already|this|that|so many|to|not|again"
    r"|yesterday|last|many|multiple|several|\d)",
    r"\bI(?:'ve| have) (?:said|asked you|explained) (?:this |that |it )?"
    r"(?:before|already|again|many|multiple|several|\d)",
    r"\bdidn't I (?:tell|say|ask)\b",
    r"\bhaven'?t I (?:told you|said|asked)(?: that)?\b",
    r"\bhity\b",
    r"\b(?:as|like) I (?:said|told you|asked)(?: you)? (?:before|earlier|already|last)\b",
    r"\bhow many times (?:do I have to|must I|have I (?:told|said|asked))\b",
    r"\bfor the (?:second|third|fourth|fifth|nth|\d+(?:st|nd|rd|th)) time\b",
    r"\bwe(?:'ve| have)? (?:went|gone|been) over this\b",
    r"\bevery (?:single )?(?:time|session|project)\b[^.?!\n]{0,40}"
    r"\b(?:have to|need to) (?:tell|remind) you\b",
    r"\bshould(?:n't| not) have to (?:tell|ask|say|remind|repeat)\b",
    # The agent repeating a miss.
    r"(?<!are )\byou(?:'re| are)? still (?:not|haven't|interpreting|ignoring|forgetting)\b",
    r"\byou(?:'re| are) doing (?:it|that|this) again\b",
    r"\byou (?:misread|misunderstood|misinterpreted) (?:me|my|what I)\b",
    r"\byou keep (?:forgetting|ignoring|missing|doing)\b",
    r"\byou never remember\b",
    r"\byou(?:'ve| have)? (?:forgot(?:ten)?|ignored|did (?:it|that|this))\b"
    r"[^.?!\n]{0,60}\bagain\b",
    r"\bsame mistake (?:again|as (?:last|before))\b",
    # The agent reading an instruction wrongly.
    r"\b(?:interpret\w*|read(?:ing)?|tak(?:e|ing) (?:it|this|that|me|my \w+))\b"
    r"[^.?!\n]{0,40}\btoo (?:narrowly|literally)\b",
    r"\b(?:things?|stuff) that (?:feel|feels|seem|seems|should be) obvious\b",
    r"\b(?:that'?s|this is|that is) not what I (?:asked|meant|said)\b",
    r"\byou ignored my\b",
]
MATCHER = re.compile("|".join(PATTERNS), re.IGNORECASE | re.MULTILINE)

LEFT_DQ, RIGHT_DQ = chr(0x201C), chr(0x201D)
NOT_TYPED = [
    re.compile(r"^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$", re.MULTILINE | re.DOTALL),
    re.compile(r"<(system-reminder|pasted_content)\b[^>]*>.*?</\1>", re.DOTALL),
    re.compile(r"^\s*>.*$", re.MULTILINE),
    re.compile(r"^(?: {4}|\t).*$", re.MULTILINE),
    re.compile(r'`[^`\n]*`|"[^"\n]*"|' + LEFT_DQ + "[^" + RIGHT_DQ + r"\n]*" + RIGHT_DQ),
]

REMINDER = """\
[hook: remind-encode-user-correction] The user's message reads as a \
correction, or says they have had to repeat themselves ("{quote}").
The user should never have to say this twice, in this session or any other \
project. Fix the instance they pointed at, then, in this same turn:
1. Name the general rule behind the correction, read broadly: an example \
stands for its category, and "etc." is open-ended.
2. Commit that rule to the repo that owns it and open the PR: \
Morrison-Lab/ai-config for anything that applies beyond one repo (AGENTS.md \
for a cross-agent rule; CLAUDE.md or a shared/ fragment for detail; a skill \
for a procedure), the current repo's own agent docs for a rule about that \
repo only. If ai-config is not in this session, attach or clone it first. \
Do this even when the rule is "obvious" -- that it had to be said is the \
evidence it was not encoded.
3. If the miss is mechanically detectable, add a hook for it in the same PR.
4. Project or host memory may get a copy too, but never instead: no other \
project reads it.
If the matched words are not a correction of you (quoted text, a remark \
about someone else), ignore this reminder. See AGENTS.md "Treat user \
profanity and frustration as urgent defect signals" and CLAUDE.md \
"Encoding reusable feedback into ai-config"."""


def typed_text(prompt: str) -> str:
    text = prompt.replace(chr(0x2019), "'").replace(chr(0x2018), "'")
    for pattern in NOT_TYPED:
        text = pattern.sub(" ", text)
    return text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str):
        return 0
    match = MATCHER.search(typed_text(prompt))
    if match is None:
        return 0
    quote = " ".join(match.group(0).split())[:80]
    print(REMINDER.format(quote=quote))
    return 0


if __name__ == "__main__":
    sys.exit(main())
