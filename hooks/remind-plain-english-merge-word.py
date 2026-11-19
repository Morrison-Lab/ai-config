#!/usr/bin/env python3
"""UserPromptSubmit: the user's plain-English merge word is an mwc grant.

ai-config#4698. Ezra, 2026-10-23: a typed "merge when ready" was not
recognized as a merge word, so he had to retype "mwc". `skills/mwc/SKILL.md`
listed `/mwc`, the bare word `mwc`, "merge when confident", "merge at will"
and "maw", and a model reading that list does not generalize it. This hook
makes the recognition mechanical: when the user's message is a merge
instruction in plain English, it injects the instruction to treat it as a bare
`mwc` (`mwc all`), with the same gates `mwc` has.

It only ADDS context; no-unauthorized-merge.py loads `merge_word()` and
`revokes()` from here and reads the grant from the transcript, so no Bash
step is needed (ai-config#5612). Text the user did not type and questions
are not grants.

Fails OPEN and SILENT on any parse trouble.
"""
import html
import json
import re
import sys

# A whole short message that is only a merge instruction.
WHOLE = re.compile(
    r"^\W*(?:/?mwc|/?maw|merge(?:\s+(?:it|them\s+all|all))?"
    r"|go\s+ahead\s+(?:and\s+)?merge(?:\s+(?:it|them|them\s+all))?"
    r"|(?:please\s+)?merge\s+(?:when|once|as\s+soon\s+as)\s+(?:ready|clean|green|confident|they(?:'re| are) ready)"
    r"|merge\s+when\s+ready|mwc\s+(?:them\s+)?all|mwc\s+them)\W*$",
    re.I,
)
# A merge instruction inside a longer message.
INLINE = re.compile(
    r"\b(?:merge\s+when\s+(?:ready|clean|green)|merge\s+them\s+all|mwc\s+(?:them\s+)?all)\b",
    re.I,
)
# A grant opens a clause: "ok, merge them all" grants, "I can merge when ready" does not.
CLAUSE_START = re.compile(
    r"(?:^|[.!;:\n,])(?:\W|\b(?:ok(?:ay)?|yes|yep|great|thanks|good|sure|then|and|so|please|now)\b)*$",
    re.I,
)
SLASH_COMMAND = re.compile(
    r"<command-name>\s*/?(?:ai-config:)?(mwc|maw|merge-when-confident|merge-at-will)\s*</command-name>"
    r"(?:.*?<command-args>(.*?)</command-args>)?",
    re.S | re.I,
)
# Withdrawing a grant: `/mwc revoke`, `disable-mwc`, "stop merging", "don't merge".
# A bare "stop", "wait" or "no" withdraws too, but only as a whole clause or
# before a merge word, so "stop asking for approvals" is not a revocation.
REVOKE = re.compile(
    r"(?:^|\W)(?:/?mw[cr]s?\s+revoke|revoke\s+(?:the\s+)?mw[cr]s?|disable-mw[cr]s?|stop\s+merging"
    r"|hold\s+off|not\s+yet"
    r"|(?:do\s+not|don't|dont|no\s+more|never)\s+merg(?:e|ing)\b)"
    r"|(?:^|[.!;])\s*(?:stop|wait|no)\b[^\w\n]*(?:$|merg)",
    re.I | re.M,
)
QUESTION = re.compile(r"\?\s*$")
QUESTION_SENTENCE = re.compile(r"[^.!?\n]*\?")

NOT_TYPED = [
    re.compile(r"^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$", re.MULTILINE | re.DOTALL),
    re.compile(r"<(system-reminder|pasted_content)\b[^>]*>.*?</\1>", re.DOTALL),
    re.compile(r"^\s*>.*$", re.MULTILINE),
    re.compile(r'`[^`\n]*`|"[^"\n]*"'),
]

# In a cloud thread, only the principal's wake message and a relay's
# `<cited author="user">` entries are the user's words.
HARNESS_WRAPPER = re.compile(r"<(?:wake|coordinator-relay)\b")
PRINCIPAL_MESSAGE = re.compile(
    r'<message\b(?=[^>]*\bfrom="human")(?=[^>]*\btrust="principal")'
    r'(?=[^>]*\btrigger="true")[^>]*>(.*?)</message>',
    re.S,
)
CITED_USER = re.compile(r'<cited\b(?=[^>]*\bauthor="user")[^>]*>(.*?)</cited>', re.S)
NOTE = re.compile(r"<note\b[^>]*>.*?</note>", re.S)
# A harness-written prompt (task notification, command output) opens with a tag.
REMINDER_BLOCK = re.compile(r"<system-reminder\b[^>]*>.*?</system-reminder>", re.S)
HARNESS_TAGGED = re.compile(r"^\s*<[A-Za-z][\w-]*\b")

REMINDER = (
    "[hook: remind-plain-english-merge-word] The user's message (\"{quote}\") is a merge word "
    "in plain English. Treat it as a bare `mwc` (`mwc all`). The merge guard reads this "
    "message from the transcript, so run no `ai-session.sh` step and no other Bash for the "
    "grant; merge with the GitHub MCP merge tool where one is available, and merge every "
    "in-scope PR that is fully clean. Do not ask them to retype `mwc` or to name PR numbers. "
    "The gates still run on each PR (fully-clean, current head, stale base); a PR that fails "
    "them waits, and you say which. "
    "If the words were not a merge instruction (a question, quoted text), ignore this."
)


def typed(text: str) -> str:
    text = text.replace(chr(0x2019), "'")
    for pattern in NOT_TYPED:
        text = pattern.sub(" ", text)
    return text.strip()


def user_bodies(prompt: str) -> list:
    """The parts of a prompt the user wrote, harness wrappers removed."""
    if not HARNESS_WRAPPER.search(prompt):
        if HARNESS_TAGGED.match(REMINDER_BLOCK.sub("", prompt)):
            return []
        return [prompt]
    prompt = NOTE.sub(" ", prompt)
    bodies = PRINCIPAL_MESSAGE.findall(prompt) + CITED_USER.findall(prompt)
    return [html.unescape(body) for body in bodies]


def slash_grant(prompt: str):
    """The `/mwc` slash command recorded in `prompt`, unless it revokes, or None."""
    match = SLASH_COMMAND.search(prompt)
    if not match or REVOKE.search("/mwc " + (match.group(2) or "")):
        return None
    return "/" + match.group(1).lower()


def merge_word(prompt: str, strict: bool = False):
    """The merge word typed in `prompt`, or None; `strict` (the guard) needs it to open a clause."""
    slash = slash_grant(prompt)
    if slash:
        return slash
    for body in user_bodies(prompt):
        text = typed(body)
        if not text or QUESTION.search(text):
            continue
        match = WHOLE.match(text) or INLINE.search(text)
        if not match:
            continue
        if strict and match.start() > 0 and not CLAUSE_START.search(text[: match.start()]):
            continue
        # An inline match inside a sentence that ends in a question mark is not an instruction.
        if QUESTION_SENTENCE.match(text, match.end()):
            continue
        return " ".join(match.group(0).split())
    return None


# A merge instruction that names its PRs (ai-config#5703, #5723): "merge PR 113",
# "merge csci201 PRs 28, 24, 25, 26 and 27", "merge mcsg#113". It grants
# those PRs only, so it is read apart from merge_word(), which grants all.
_NUMS = r"#?\d+(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s*&\s*)#?\d+)*"
NAMED = re.compile(
    r"\bmerge\s+(?:(?:[\w.-]+/)?(?P<repo>[A-Za-z][\w.-]*)\s+)?(?:PRs?|pull\s+requests?)\s+"
    r"(?P<nums>" + _NUMS + r")\b"
    r"|\bmerge\s+(?:(?:[\w.-]+/)?(?P<repo2>[A-Za-z][\w.-]*))?#(?P<nums2>\d+"
    r"(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s*&\s*)#?\d+)*)\b",
    re.I,
)


def named_merge_grants(prompt: str) -> set:
    """{(repo or None, number)} for each PR the user's merge instruction names.

    Held to the strict test merge_word() applies for the guard: the
    instruction opens a clause and is not a question. `repo` is the bare
    repository name, lowercased, or None when the user named none.
    """
    grants = set()
    for body in user_bodies(prompt):
        text = typed(body)
        if not text or QUESTION.search(text):
            continue
        for match in NAMED.finditer(text):
            if match.start() > 0 and not CLAUSE_START.search(text[: match.start()]):
                continue
            if QUESTION_SENTENCE.match(text, match.end()):
                continue
            repo = match.group("repo") or match.group("repo2")
            nums = match.group("nums") or match.group("nums2")
            grants |= {((repo or "").lower() or None, int(n)) for n in re.findall(r"\d+", nums)}
    return grants


def revokes(prompt: str) -> bool:
    """Whether the user's own words in `prompt` withdraw a merge grant.

    A revocation clears every grant before it: `mwc`, a named "merge PR N",
    and `mwr`/`mwrs` alike.
    """
    match = SLASH_COMMAND.search(prompt)
    if match and REVOKE.search("/mwc " + (match.group(2) or "")):
        return True
    match = MWR_SLASH_COMMAND.search(prompt)
    if match and REVOKE.search("/mwr " + (match.group(2) or "")):
        return True
    return any(REVOKE.search(typed(body)) for body in user_bodies(prompt))


# The `mwr` merge grant (ai-config#3946; Ezra, 2026-11-19, "Skip review, keep
# green CI"): merge without a clean review (no non-Claude read, no Claude
# CLEAN verdict), every required check still green. `mwr` covers one PR,
# `mwrs` the whole session. Only the typed tokens start it: the spelled-out
# "merge when ready" stays a plain-English `mwc` (merge_word() above; Ezra,
# 2026-10-23), and nothing here reads it.
MWR_WORD = re.compile(r"(?<![\w/.#-])/?(mwrs?)(?![\w-])", re.I)
MWR_SLASH_COMMAND = re.compile(
    r"<command-name>\s*/?(?:ai-config:)?(mwrs?)\s*</command-name>"
    r"(?:.*?<command-args>(.*?)</command-args>)?",
    re.S | re.I,
)
# A PR the same message names: "#5940", "ai-config#5940", "PR 5940",
# ".../pull/5940", or a number right after the word ("mwr 5940").
MWR_PR_REF = re.compile(
    r"(?:(?<![\w.-])(?:[\w.-]+/)?(?P<repo>[A-Za-z][\w.-]*))?#(?P<n1>\d+)\b"
    r"|\bPRs?\s+#?(?P<n2>\d+)\b"
    r"|/(?:[\w.-]+/)?(?P<repo3>[A-Za-z][\w.-]*)/pull/(?P<n3>\d+)\b",
    re.I,
)
MWR_TRAILING_NUMBER = re.compile(r"\s+(\d+)\b")
MWR_ALL = "all"


def _mwr_scope(word: str, text: str, end: int):
    """MWR_ALL, or {(repo or None, number)} for the PRs a bare `mwr` names.

    `mwr` grants one PR, the single most relevant one. When the same user
    message names a PR, that PR is the grant, as a named "merge PR N" is.
    When it names none, the most relevant PR is not something a hook can
    decide, so the grant covers the session's merges, the way a bare `/mwc`
    means `/mwc all` (skills/mwc/SKILL.md); the agent picks the one PR. Every
    merge still has to pass the checker's MERGE-READY line for its own head.
    `mwrs` is the session grant, so it is always MWR_ALL.
    """
    if word.lower() == "mwrs":
        return MWR_ALL
    refs = set()
    for match in MWR_PR_REF.finditer(text):
        repo = match.group("repo") or match.group("repo3")
        num = match.group("n1") or match.group("n2") or match.group("n3")
        refs.add(((repo or "").lower() or None, int(num)))
    trailing = MWR_TRAILING_NUMBER.match(text, end)
    if trailing:
        refs.add((None, int(trailing.group(1))))
    return refs or MWR_ALL


def mwr_grant(prompt: str):
    """The `mwr`/`mwrs` grant the user typed in `prompt`: MWR_ALL, a set of
    (repo or None, number), or None.

    Held to merge_word()'s strict test: the word is the user's own text (not
    quoted, fenced or a system reminder), opens a clause, and is not part of
    a question, so "what does mwr mean?" is no grant.
    """
    match = MWR_SLASH_COMMAND.search(prompt)
    if match:
        args = match.group(2) or ""
        if REVOKE.search("/mwr " + args):
            return None
        return _mwr_scope(match.group(1), args, 0)
    for body in user_bodies(prompt):
        text = typed(body)
        if not text or QUESTION.search(text) or REVOKE.search(text):
            continue
        for match in MWR_WORD.finditer(text):
            if match.start() > 0 and not CLAUSE_START.search(text[: match.start()]):
                continue
            if QUESTION_SENTENCE.match(text, match.end()):
                continue
            return _mwr_scope(match.group(1), text, match.end())
    return None


def main() -> int:
    # Quoted prompt text can hold curly quotes, which a cp1252 console can
    # neither read from a UTF-8 payload nor write for a UTF-8 reader
    # (ai-config#5462). Read stdin and write stdout as UTF-8 whatever the
    # console says.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str):
        return 0
    word = merge_word(prompt)
    if word is None:
        return 0
    print(REMINDER.format(quote=word[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
