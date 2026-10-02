#!/usr/bin/env python3
"""UserPromptSubmit: a user correction becomes an ai-config rule, not a memory.

ai-config#4208. On 2026-10-02 the user wrote, from a claude.ai project:
"it's so frustrating when I have to tell you to do things that feel obvious,
and when I have to repeat myself between sessions or projects". The rules
for this already existed -- AGENTS.md "Treat user profanity and frustration
as urgent defect signals" and CLAUDE.md "Encoding reusable feedback into
ai-config" -- and neither had a trigger:

  - remind-ums-after-error.py, remind-learn-from-review.py and
    remind-ums-on-scrutiny.py key on the AGENT's own admission, an accepted
    review finding, or a read review. A user correcting the agent, or saying
    they have repeated themselves, matches none of them.
  - In a session whose repo is not ai-config, the natural landing place is
    whatever memory the host offers (a claude.ai project's memory, a repo's
    CLAUDE.md, ~/.claude auto-memory). Each is invisible to every OTHER
    project, which is exactly how the user ends up repeating themselves.

So this matches the user's prompt for correction and repetition language and
injects the procedure: widen the correction to its general rule, commit that
rule to Morrison-Lab/ai-config in this turn (attaching or cloning it when
the session is elsewhere), and add a hook when the miss is decidable. Host
memory is allowed in addition, never instead.

Inject-only, like its siblings: the user's message is never blocked, and no
code path suppresses or alters anything. The vocabulary is deliberately
narrow -- phrases that state a correction or a repeat -- because a reminder
that fires on every "always" or "again" teaches the reader to skip it.
"""
import json
import re
import sys

PATTERNS = [
    r"\brepeat(?:ing)? myself\b",
    r"\b(?:have|had|need|needed|keep|kept) (?:to )?(?:tell|telling|remind|reminding|ask|asking) you\b",
    r"\b(?:already|just) (?:told|said|asked|explained)\b",
    r"\btold you (?:before|already|that)\b",
    r"\bhow many times\b",
    r"\bfeels? obvious\b|\bshould be obvious\b|\bobvious things?\b",
    r"\b(?:too|so) (?:narrowly|literally)\b",
    r"\bstill (?:not|interpreting|doing|missing|ignoring|forgetting)\b",
    r"\bbetween (?:sessions|projects|threads|chats)\b",
    r"\bevery (?:single )?(?:time|session|project)\b.{0,40}\b(?:tell|remind|ask|say)\b",
    r"\bshould(?:n't| not) have to (?:tell|ask|say|remind|repeat)\b",
    r"\byou (?:did|made|forgot|ignored|missed|broke)\b.{0,60}\bagain\b",
]
MATCHER = re.compile("|".join(PATTERNS), re.IGNORECASE | re.DOTALL)

REMINDER = """\
[hook: remind-encode-user-correction] The user's message reads as a \
correction, or says they have had to repeat themselves ("{quote}").
The user should never have to say this twice, in this session or any other \
project. Before replying:
1. Name the general rule behind the correction, read broadly: an example \
stands for its category, and "etc." is open-ended.
2. Commit that rule to Morrison-Lab/ai-config in THIS turn and open the PR \
(AGENTS.md for a cross-agent rule; CLAUDE.md or a shared/ fragment for \
detail; a skill for a procedure). If this session's repo is not ai-config, \
attach or clone it first. Do this even when the rule is "obvious" -- that \
it had to be said is the evidence it was not encoded.
3. If the miss is mechanically detectable, add a hook for it in the same PR.
4. Project or host memory may get a copy too, but it is never a substitute: \
it is invisible to every other project.
Then fix the instance the user pointed at. See AGENTS.md "Treat user \
profanity and frustration as urgent defect signals" and CLAUDE.md \
"Encoding reusable feedback into ai-config"."""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str):
        return 0
    match = MATCHER.search(prompt)
    if match is None:
        return 0
    quote = " ".join(match.group(0).split())[:80]
    print(REMINDER.format(quote=quote))
    return 0


if __name__ == "__main__":
    sys.exit(main())
