#!/usr/bin/env python3
"""PreToolUse block: a project-chat post names another session without linking it.

The user's standing rule (2026-10-16, reaffirmed 2026-10-22): every mention of a
session is a link. On 2026-10-22 a reply named "your Mac session" and "the
coordinator" with no link, and the user asked "aren't you supposed to
strengthen the rule?". `no-unlinked-thread-pointer.py` covers "in its thread";
this covers a named session.

Scope: the user-visible reply tools (`mcp__hearthbot__reply`, `post_message`,
`update_message`, `edit_message`). An edit is a post the user reads, so it is
held to the same rule: on 2026-11-03 an edit named "the thread that owns that
runner" with no link and passed, and the user said "always hyperlink when you
mention other threads". Blocks, because the fix is one resend.

What counts:
  - A mention is "Remote Control session", "RC session", "Mac session",
    "Linux session", "cloud session", "local session", "device session",
    "coordinator session", "your ... session", or the word "coordinator".
    The same prefixes before "chat" count too ("the ab12-03 chat", "your Mac
    chat"), as do "that chat" and "other chat" (ai-config#4878).
    "This session", "a session", "this chat" and "the project chat" are not
    mentions of another session.
  - A link is `https://claude.ai/code/session_...`, `(#cmsg_...)` or a URL
    carrying `thread=cmsg_...`.
  - A bare "session" or "thread" counts when the word before it points at
    another session: "the", "that", "those", "other", "another", "my",
    "our", "their", "its", "previous", "earlier", "prior", "parent",
    "child", "sibling", or a host id such as "ab12-03" ("the session",
    "that thread", "the ab12-03 session"). Any other word before it, as in
    "the R session", "a training session" or "the support thread", names
    nothing to link, so it is not a mention.
  - The unit is one paragraph or one list item. A mention in a unit with no
    link of its own blocks.
  - Fenced code and inline code spans are removed first.
Fails open on any parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(
    r"(^|__)(reply|post_message|update_message|edit_message)$")
FENCE = re.compile(
    r"^ {0,3}(```+|~~~+).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.M | re.S)
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
MENTION = re.compile(
    r"\b(?:(?:Remote Control|RC|Mac|Linux|cloud|local|device|coordinator|your)"
    r"(?: \w+){0,2} sessions?|coordinator"
    # ai-config#4878: a Remote Control session called a "chat".
    r"|(?:Remote Control|RC|Mac|Linux|cloud|local|device|your|[a-z]+\d+-\d+)"
    r"(?: \w+){0,2} chats?|(?:that|those|other) chats?)\b", re.I)
# ai-config (Ezra, 2026-11-02, "always link to the session"): any other
# session or thread, however it is named ("the ab12-03 session", "the runner
# thread", "that session"). The word before it decides: a determiner that
# names this session or an unspecific one is not a mention.
GENERIC = re.compile(r"(?<![\w-])([\w-]+) (sessions?|threads?)\b", re.I)
POINTING = {"the", "that", "those", "other", "another", "my", "our", "their",
            "its", "previous", "earlier", "prior", "parent", "child",
            "sibling"}
HOST_ID = re.compile(r"[a-z]+\d+-\d+", re.I)
# ai-config#5058 (Ezra, 2026-11-07, "always hyperlink; don't make me ask"):
# a descriptive name between a pointing word and "thread" ("the runner
# thread", "the CI thread") names a project thread. These words name a
# technical or forge thread instead and stay exempt.
NAMED_THREAD = re.compile(
    r"(?<![\w-])(?:the|that|those|other|another|my|our|their|its|your)"
    r" ([\w-]+) threads?\b", re.I)
TECHNICAL_THREAD = {
    "main", "worker", "review", "support", "comment", "email", "forum",
    "discussion", "reply", "background", "conversation", "os", "kernel", "gui",
    "ui", "io", "gpu", "cpu", "python", "r", "julia", "java", "jvm", "event",
    "render", "download", "upload", "polling", "daemon"}
LINK = re.compile(
    r"claude\.ai/code/session_\w+|\(#cmsg_\w+\)|[?&]thread=cmsg_\w+")
# ai-config#5060 (Ezra, 2026-11-07, "always hyperlink; don't make me ask"): a
# PR, issue or run named outside a markdown link or URL. Detected: `repo#N`,
# `owner/repo#N`, a bare `#N` of two or more digits, "PR 12", "issue 12" and
# "run 123456". File paths are the separate FILE_REF check below.
# A run id is six or more digits, so "the suite runs 12 times" is not one.
# The repo prefix is two or more characters, so "C#12" is not a reference.
FORGE_REF = re.compile(
    r"(?<![\w/&.-])(?:[\w.-]+/)?[\w.-]{2,}#\d{2,}\b"
    r"|(?<![\w/&.-])#\d{2,}\b"
    r"|\b(?:PRs?|pull requests?|issues?) #?\d{2,}\b"
    r"|\bruns? #?\d{6,}\b", re.I)
# A reference counts as linked only inside a markdown link or a bare URL, so
# one link elsewhere in the paragraph does not cover the rest.
LINKED = re.compile(r"\[[^\]]*\]\(https?://[^)]*\)|https?://\S+")
# The target of any other markdown link is not prose: "[here](./a.md#5060)"
# names no PR. Its text still counts, so "[#5059](#cmsg_1)" is flagged.
LINK_TARGET = re.compile(r"(?<=\])\([^)]*\)")
# ai-config#5072 (the file half of #5060): a file named outside a link. Detected:
# a name ending in a known document, code or data extension, with or without
# directories, a leading slash, or a ":line" anchor ("hooks/a.py", "AGENTS.md",
# "/mnt/project-files/x/plan.md", "a.py:12"). Not detected: a file with another
# extension, an extensionless name ("Makefile") and a directory ("hooks/"). A
# pattern for any slash or dot also matches "and/or", version numbers and
# hosts, and a list of every repo file goes stale, so the extension list is the
# bound; a deny that cannot decide stays silent (ai-config#4741).
# A word then "." then letters, as in "e.g.", is not a name: the extension must
# be one of the listed ones and end the token.
FILE_EXT = (r"py|md|qmd|ya?ml|json|jsonl|sh|toml|bib|csv|txt|html|lua|scss|css"
            r"|R|Rmd|ipynb|pdf|docx|pptx|xlsx|cff|lock")
FILE_REF = re.compile(
    r"(?<![\w/@.:=#-])/?(?:[\w.-]+/)*[\w-][\w.-]*\.(?:" + FILE_EXT + r")"
    r"(?::\d+)?(?![\w/@-])(?!\.\w)")
# A file is linked inside a markdown link to an https URL or to a published
# project file, or inside a bare URL; the project-file target is the form the
# thread tools document ("[plan.md](/mnt/project-files/notes/plan.md)").
FILE_LINKED = re.compile(
    r"\[[^\]]*\]\((?:https?://|/mnt/project-files/)[^)]*\)|https?://\S+")
UNIT_BREAK = re.compile(r"\n[ \t]*\n|\n(?=(?:[-*+]|\d+[.)])[ \t])")

REASON = """\
[hook: no-unlinked-session-mention] This post names a session ("{phrase}") \
without a link. The user's standing rule (2026-10-16, reaffirmed 2026-10-22): \
"anytime you mention a session, you must provide a link".
Resend with a link in the same paragraph or list item: \
[session](https://claude.ai/code/session_<id>) for a Claude Code session \
(the id from the status wake or cross-session message, `cse_` becomes \
`session_`), or [thread title](#cmsg_...) for a project thread (find its \
title and id with `list_threads`). Do not type an id from memory.
If the phrase is not a Claude Code session or project thread (an R, database \
or debugger session, an OS thread), put it in backticks and resend."""


def unlinked_mention(text: str):
    """The first session mention in a unit with no link, or None."""
    text = FENCE.sub(" ", text.replace("\r\n", "\n"))
    for unit in UNIT_BREAK.split(text):
        unit = INLINE_CODE.sub(" ", unit)
        if LINK.search(unit):
            continue
        m = MENTION.search(unit)
        if m:
            return m.group(0)
        for g in GENERIC.finditer(unit):
            before = g.group(1)
            if before.lower() in POINTING or HOST_ID.fullmatch(before):
                return g.group(0)
        for n in NAMED_THREAD.finditer(unit):
            if n.group(1).lower() not in TECHNICAL_THREAD:
                return n.group(0)
    return None


FORGE_REASON = """\
[hook: no-unlinked-session-mention] This post names a forge artifact \
("{phrase}") that is not itself a link. The user's \
standing rule (2026-11-07): "always hyperlink; don't make me ask".
Resend with that text as a markdown link to its https URL (a URL elsewhere \
in the paragraph does not cover it), for example \
[owner/repo#12](https://github.com/owner/repo/pull/12) or \
[run 123](https://github.com/owner/repo/actions/runs/123).
If the text is not a PR, issue or run (a footnote number, a heading), put it \
in backticks and resend."""


def unlinked_forge_ref(text: str):
    """The first PR, issue or run reference outside a link, or None."""
    text = FENCE.sub(" ", text.replace("\r\n", "\n"))
    for unit in UNIT_BREAK.split(text):
        unit = INLINE_CODE.sub(" ", unit)
        unit = LINK_TARGET.sub("", LINKED.sub(" ", unit))
        m = FORGE_REF.search(unit)
        if m:
            return m.group(0)
    return None


FILE_REASON = """\
[hook: no-unlinked-session-mention] This post names a file ("{phrase}") that \
is not itself a link. The user's standing rule (2026-11-07): "always \
hyperlink; don't make me ask", and ai-config#5072 extends it to files.
Resend with that name as a markdown link: its https URL on the forge, for \
example [hooks/a.py](https://github.com/owner/repo/blob/main/hooks/a.py), or \
[name](/mnt/project-files/<path>) for a file you wrote to the project folder.
If the text is not a file (a domain, a version string), put it in backticks \
and resend."""


def unlinked_file_ref(text: str):
    """The first file name outside a link, or None."""
    text = FENCE.sub(" ", text.replace("\r\n", "\n"))
    for unit in UNIT_BREAK.split(text):
        unit = INLINE_CODE.sub(" ", unit)
        unit = LINK_TARGET.sub("", FILE_LINKED.sub(" ", unit))
        m = FILE_REF.search(unit)
        if m:
            return m.group(0)
    return None


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
    phrase = unlinked_mention(text)
    reason = REASON
    if not phrase:
        phrase = unlinked_forge_ref(text)
        reason = FORGE_REASON
    if not phrase:
        phrase = unlinked_file_ref(text)
        reason = FILE_REASON
    if not phrase:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason.format(phrase=phrase),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
