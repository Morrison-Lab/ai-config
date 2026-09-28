#!/usr/bin/env python3
"""Stop-hook guard: catch offering to file/record instead of just doing it.

`report-mistakes-proactively` and the user's standing `cai` both say to file
issues and record learnings *without* asking. The rule is read at load time;
the violation happens at composition time, in the closing paragraph of a long
message, where no rule is being consulted. So re-reading the rule does not
prevent it -- observed three times on 2026-07-29.

Two distinct shapes, both matched below:
  1. a pure offer   -- "worth saving as a memory?"
  2. a bundled one  -- "want me to file the issue and open that PR?", where a
     genuinely discretionary action (the PR) carries an ungated one (the issue)
  3. a statement   -- "I can also file an issue about X. Say if you want it."
     or "I haven't filed an issue about it. Say if you want one." -- the same
     offer with no question mark, which the question-form patterns missed

Fires once per distinct message (sentinel keyed by content hash) so a block
cannot loop. Fails OPEN: a guard that wedges the session costs more than the
lapse it prevents.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Offer-shaped, and specifically about filing/recording rather than about
# doing implementation work (which IS the user's call to gate).
PATTERNS = [
    r"want me to (file|open an issue|record|save|capture|note)",
    r"(should|shall) i (file|record|save|capture|memorize)",
    r"say the word and i('ll| will) (file|record|save|capture)",
    r"worth (an issue|filing|a memory|saving|capturing|recording)\b[^.]*\?",
    r"(let me know|tell me) if you('d| would) like me to (file|record|save)",
    r"i (could|can) file (an|a) (issue|follow-?up)[^.]*\?",
    # Statement-shaped offers: no question mark, same intent. Each needs a
    # filing/recording word in view so a report of work done cannot match.
    # The gap before the noun stops at a comma or semicolon, and the noun must
    # end there, so "file a ticket, but ... GitHub issues" and "file an
    # issue-tracking script" are not read as the filing idiom.
    r"i can (also )?file (an?|the) [^.!?,;\n]{0,60}?\b(issue|follow-?up|bug)(?![\w-])",
    r"\b(file|filing|issue|memory|memories|record|recording)\b[^\n]{0,240}?"
    r"\b(say|tell me|let me know) (if|whether) you('d| would)? (want|like) "
    r"((it|one|them)(?=\s*([.!?)\n]|$))|me to (file|record|save|capture|note|open an issue))",
    r"\b(file|filing|issue|memory|memories|record|recording)\b[^\n]{0,240}?"
    r"\b(just )?say the word\b",
]
RX = re.compile("|".join(PATTERNS), re.I)

# "I haven't filed an issue" is an offer in waiting unless the same sentence
# cites the existing tracker concretely: an issue/PR/MR URL, owner/repo#N, or
# #N. An excuse KEYWORD ("already", "tracked", ...) is not enough -- it can sit
# in an unrelated clause, and every narrower keyword window (forward-only,
# line, sentence) was evaded by the next-coarser clause join. A link is the
# thing a legitimate decline has and an unfiled observation does not. The
# window is the sentence: a paragraph has no internal newlines, so a line-wide
# scan would let a link three sentences away excuse the clause.
NOT_FILED_RX = re.compile(
    r"i (haven['\u2019]t|have not|didn['\u2019]t|did not) (yet )?file[d]? "
    r"(an?|the) [^.!?,;\n]{0,40}?\b(issue|follow-?up|bug)(?![\w-])",
    re.I,
)
TRACKER_REF_RX = re.compile(
    r"https?://[^\s/]+/[^\s]*?/(issues|pull|pulls|merge_requests)/\d+"
    r"|\b[\w.-]+/[\w.-]+#\d+\b"
    r"|(?<![\w/#&])#\d+\b",
    re.I,
)
# A sentence ends at a newline, or at terminal punctuation followed by
# whitespace or the end of text -- so the dots inside a URL
# ("github.com/.../issues/981") do not end one -- unless the punctuation
# closes a common abbreviation ("e.g.", "i.e.", "etc.", "vs.", "cf.").
SENTENCE_END_RX = re.compile(
    r"\n|(?<!\be\.g)(?<!\bi\.e)(?<!\betc)(?<!\bvs)(?<!\bcf)[.!?]+(?=\s|$)",
    re.I,
)


def sentence_around(text, start, end):
    """The sentence of `text` containing the span [start, end)."""
    s_start = 0
    for b in SENTENCE_END_RX.finditer(text, 0, start):
        s_start = b.end()
    after = SENTENCE_END_RX.search(text, end)
    return text[s_start:after.start() if after else len(text)]


def find_offer(prose):
    """The first offer-shaped match in `prose`, or None."""
    hit = RX.search(prose)
    if hit:
        return hit
    for m in NOT_FILED_RX.finditer(prose):
        if not TRACKER_REF_RX.search(sentence_around(prose, m.start(), m.end())):
            return m
    return None


# In a project-thread session every user-visible sentence is the `text` input
# of an `mcp__hearthbot__reply` tool call, never an assistant text block.
# Measured on ai-config#3798: a reader that only walks `type == "text"` blocks
# is blind to the whole reply.
REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)


def _reply_payload(block):
    """The user-visible text of a reply-tool call, or '' for any other block."""
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return ""
    if not REPLY_TOOL_RX.search(block.get("name") or ""):
        return ""
    inp = block.get("input")
    if not isinstance(inp, dict):
        return ""
    txt = inp.get("text")
    return txt if isinstance(txt, str) else ""


def last_assistant_text(path):
    last_text = ""
    last_reply = ""
    saw_reply_tool = False
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") == "assistant" or m.get("role") == "assistant":
                    blocks = (m.get("message") or {}).get("content") or m.get("content") or []
                    if isinstance(blocks, list):
                        txt = "".join(
                            b.get("text", "") for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if txt.strip():
                            last_text = txt
                        for b in blocks:
                            if isinstance(b, dict) and b.get(
                                "type"
                            ) == "tool_use" and REPLY_TOOL_RX.search(
                                b.get("name") or ""
                            ):
                                saw_reply_tool = True
                            payload = _reply_payload(b)
                            if payload.strip():
                                last_reply = payload
                    elif isinstance(blocks, str) and blocks.strip():
                        last_text = blocks
                elif m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
                    content = m.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text = content
                    elif isinstance(content, list):
                        txt = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                        if txt.strip():
                            last_text = txt
    except Exception:
        return ""
    chosen = last_reply if saw_reply_tool else last_text
    return chosen if chosen.strip() else ""


try:
    _lib = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
    )
    if _lib not in sys.path:
        sys.path.insert(0, _lib)
    from fences import strip_code
except Exception:
    _FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
    _CODE_SPAN_RE = re.compile(
        r"(?<!`)(`+)(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
    )

    def strip_code(text: str) -> str:
        """Strip fenced code blocks and inline backtick code spans."""
        return _CODE_SPAN_RE.sub(" ", _FENCE_RE.sub(" ", text))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = last_assistant_text(payload.get("transcript_path") or "")
    if not text:
        return 0

    prose = strip_code(text)
    hit = find_offer(prose)
    if not hit:
        return 0

    # fire at most once per distinct message
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-offer-guard-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Your message offers to file/record rather than doing it: "
            f"\"{hit.group(0).strip()}\".\n\n"
            "Standing rule (report-mistakes-proactively, plus the user's own "
            "`cai`): file issues and record learnings WITHOUT asking. A "
            "duplicate is cheap; a lost observation is not, and only the user "
            "can say a thing is not worth keeping -- which they can do after "
            "it exists.\n\n"
            "If this is the BUNDLED shape -- a discretionary action (opening a "
            "PR, making a code change) sharing a sentence with an ungated one "
            "(filing, recording) -- split them: do the ungated part now, then "
            "ask about the remainder only.\n\n"
            "Dupe-check first, then file or comment, then cite the identifier "
            "the API actually returned."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
