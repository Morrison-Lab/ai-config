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

So this matches the user's prompt for correction and repetition language and
injects the procedure: fix the instance, widen the correction to its general
rule, commit that rule in this turn to the repo that owns it (ai-config for a
cross-repo rule), and add a hook when the miss is decidable. Host memory is
allowed in addition, never instead.

Inject-only, like its siblings: the user's message is never blocked. Text the
user did not type as a correction is removed before matching: fenced code,
`>` quotes, and <system-reminder> / <pasted_content> blocks. The vocabulary
is deliberately narrow -- each phrase states a correction or a repeat
addressed to the agent -- because a reminder that fires on every "again" or
"still" teaches the reader to skip it. It fires on every matching prompt
rather than once per session: each correction is its own rule.
"""
import json
import re
import sys

PATTERNS = [
    r"\brepeat(?:ing|ed)? myself\b",
    r"\b(?:have|had|keep|kept) (?:to )?(?:tell|telling|remind|reminding) you\b",
    r"\bI(?:'ve| have)? (?:already|just) (?:told|explained (?:this )?to) you\b",
    r"\b(?:I(?:'ve| have)|already) told you\b",
    r"\b(?:as|like) I (?:said|told you|asked)(?: before| earlier| already)?\b",
    r"\bhow many times (?:do|have|must|will|should) I\b",
    r"\b(?:feels?|should be|seems?) (?:so )?obvious\b",
    r"\btoo (?:narrowly|literally)\b",
    r"\byou(?:'re| are)? still (?:not|interpreting|doing|missing|ignoring|forgetting|getting)\b",
    r"\byou keep (?:forgetting|ignoring|missing|getting|doing)\b",
    r"\bevery (?:single )?(?:time|session|project)\b.{0,40}\b(?:tell|remind)(?:ing)? you\b",
    r"\bshould(?:n't| not) have to (?:tell|ask|say|remind|repeat)\b",
    r"\byou(?:'ve| have)? (?:forgot(?:ten)?|ignored|missed|broke(?:n)?)\b.{0,60}\bagain\b",
]
MATCHER = re.compile("|".join(PATTERNS), re.IGNORECASE | re.DOTALL)

NOT_TYPED = [
    re.compile(r"^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$", re.MULTILINE | re.DOTALL),
    re.compile(r"<(system-reminder|pasted_content)\b[^>]*>.*?</\1>", re.DOTALL),
    re.compile(r"^ {0,3}>.*$", re.MULTILINE),
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
    text = prompt.replace("’", "'").replace("‘", "'")
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
