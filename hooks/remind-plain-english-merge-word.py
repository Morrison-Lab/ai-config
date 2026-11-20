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
    r"(?:^|\W)(?:/?mwc\s+revoke|revoke\s+(?:the\s+)?mwc|disable-mwc|stop\s+merging"
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
# This search matches a wrapper anywhere in the text, so a harness record
# that opens with another tag and nests a principal wake still yields that
# wake's message. Only mwc and the revocation readers use it now; the mwr
# grant readers are anchored and strict (round 7). mwc's exposure is
# pre-existing and tracked in ai-config#5959.
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

    A revocation here clears every grant before it: `mwc`, a named
    "merge PR N", and `mwr`/`mwrs` alike. An mwr-only revocation is
    `revokes_mwr()`, and it leaves the mwc grants alone.
    """
    match = SLASH_COMMAND.search(prompt)
    if match and REVOKE.search("/mwc " + (match.group(2) or "")):
        return True
    return any(REVOKE.search(typed(body)) for body in user_bodies(prompt))


# The `mwr` merge grant (ai-config#3946; Ezra, 2026-11-19, "Skip review, keep
# green CI"): merge without a clean review (no non-Claude read, no Claude
# CLEAN verdict), every required check still green. `mwr` covers the PRs it
# names, `mwrs` the whole session. Only the typed tokens start it: the
# spelled-out "merge when ready" stays a plain-English `mwc` (merge_word()
# above; Ezra, 2026-10-23), and nothing here reads it.
#
# The grant is read only from a whole message that is nothing but the grant:
# the token, then optional PR references, then optional trailing "." or "!".
# A mention ("mwr would skip review here"), a hedge ("wait, mwr") or a
# question is no grant. No `/mwr` skill exists, so a `<command-name>` tag is
# never read: it can be quoted, or sit inside a system reminder or a task
# notification, where the user did not type it.
#
# An issue is not a PR: "issue 5", "issue#5" and "issues#5" are no reference,
# so a message holding one is no grant (round 3, finding 7).
_MWR_REF = (
    r"(?:https?://github\.com/[\w.-]+/[\w.-]+/pull/\d+"
    r"|(?:PRs?|pulls?)\s*#?\d+"
    r"|(?:[\w.-]+/)?(?!issues?#)[A-Za-z][\w.-]*#\d+"
    r"|#\d+)"
)
# A bare number is no reference: "mwrs 2026" is a year or a typo, not PR
# 2026, so it makes the message no grant. A number counts only after "#",
# "PR" or "pull". References are separated by spaces, commas, "and", or an
# Oxford ", and" ("mwr lds#1, mds#2, and pds#3").
MWR_WHOLE = re.compile(
    r"^\s*/?(?P<word>mwrs?)(?P<refs>(?:(?:\s*,\s*(?:and\s+)?|\s+(?:and\s+)?)" + _MWR_REF + r")*)"
    r"\s*[.!]*\s*$",
    re.I,
)
# One reference inside MWR_WHOLE's `refs` group.
MWR_REF = re.compile(
    r"https?://github\.com/(?P<owner3>[\w.-]+)/(?P<repo3>[\w.-]+)/pull/(?P<n3>\d+)"
    r"|(?:PRs?|pulls?)\s*#?(?P<n2>\d+)"
    r"|(?:(?P<owner1>[\w.-]+)/)?(?P<repo1>[A-Za-z][\w.-]*)#(?P<n1>\d+)"
    r"|#(?P<n4>\d+)",
    re.I,
)
# Words that name a kind of reference, never a repository: "mwr PR#5940".
MWR_NOT_A_REPO = frozenset({"pr", "prs", "pull", "pulls"})
# The PR references in a message, removed before MWR_REVOKE reads it, so a
# repository whose name holds a withdrawal word ("Morrison-Lab/not-a-bug#1")
# does not revoke its own grant. Only the reference goes: "mwr lds#5 not
# yet" still revokes on "not".
MWR_REF_TEXT = re.compile(
    r"https?://github\.com/[\w.-]+/[\w.-]+/pull/\d+"
    r"|(?<![\w.'/-])(?:[\w.-]+/)?[A-Za-z][\w.-]*#\d+"
    r"|\b(?:PRs?|pulls?)\s*#?\d+"
    r"|#\d+",
    re.I,
)
# An mwr-only revocation: it clears the mwr grants and leaves mwc alone.
# It fails toward revoking: ANY user message, with or without the mwr token,
# that holds a withdrawal word ("never mind", "cancel that", "undo that",
# "no, ...", "back to mwc only") or mentions review ("wait for review before
# merging") revokes, quoted words included (round 3, finding 1).
MWR_REVOKE = re.compile(
    r"\b(?:revoke[sd]?|revocation|stop(?:ped)?|no|not|nope|cancel(?:led|ed)?|off|undo|end(?:ed)?"
    r"|never\s*mind|nevermind|nvm|disable[sd]?|halt|withdraw|drop|pause|hold|wait"
    r"|don'?t|do\s+not|abort|rescind|scrap|forget|kill|retract|reverse|without"
    r"|back|instead|require[sd]?|mwc|review(?:s|ed|er|ers|ing)?)\b",
    re.I,
)
MWR_ALL = "all"


def _mwr_refs(refs: str) -> set:
    """{(repo or None, number)} for the references after the grant word.

    `repo` is "owner/name" or a bare "name", lowercased; None when the
    reference names no repository ("#5940", "PR 5940", "PR#5940").
    """
    out = set()
    for match in MWR_REF.finditer(refs):
        owner = match.group("owner1") or match.group("owner3")
        repo = match.group("repo1") or match.group("repo3")
        num = match.group("n1") or match.group("n2") or match.group("n3") or match.group("n4")
        if repo and repo.lower() in MWR_NOT_A_REPO:
            owner = repo = None
        spec = None
        if repo:
            spec = f"{owner}/{repo}".lower() if owner else repo.lower()
        out.add((spec, int(num)))
    return out


def _mwr_text(body: str) -> str:
    """`body` with the harness's system-reminder blocks removed, and nothing else.

    The user's own quotes, code spans, fences, blockquotes and pasted
    content stay, so they can only stop a whole-message grant, never make one.
    """
    return REMINDER_BLOCK.sub(" ", body.replace(chr(0x2019), "'")).strip()


def mwr_bodies(prompt: str) -> list:
    """The body an mwr grant may come from in a typed CLI prompt, else [].

    The grant-source allowlist (round 7): a record with no `promptSource`
    starts an mwr grant only as a plain typed prompt, so its text must not
    open with `<` once leading whitespace is stripped. A harness wrapper, a
    task notification, a webhook record and anything else that opens with a
    tag gives nothing here, wherever a principal wake sits inside it; only
    an SDK-sent record can carry a wake grant (`sdk_principal_bodies`). A
    relay's `<cited author="user">` entry can revoke an mwr grant
    (`revokes_mwr()` reads it) but never start one.
    """
    if not isinstance(prompt, str) or prompt.lstrip().startswith("<"):
        return []
    return [prompt]


# An SDK-sent prompt (`promptSource: "sdk"`) grants mwr only through the
# principal's own message in a cloud-thread wake (round 6). These are read
# strictly: the prompt opens with `<wake` (anchored, after leading
# whitespace only), every `<cited>` and `<note>` block is removed, and the
# `<message>` start tag must parse as whole attributes, none repeated, each
# double-quoted (round 7), with from="human", trust="principal" and
# trigger="true".
WAKE_OPEN = re.compile(r"\s*<wake\b")
ANY_CITED = re.compile(r"<cited\b[^>]*>.*?</cited>", re.S)
MESSAGE_TAG = re.compile(r"<message\b([^>]*)>(.*?)</message>", re.S)
TAG_ATTR = re.compile(r'\s+([A-Za-z_:][\w:.-]*)\s*=\s*"([^"]*)"')


def _principal_attrs(attr_text: str) -> bool:
    """Whether a `<message>` tag's attributes declare the human principal, strictly."""
    attrs = {}
    pos = 0
    for m in TAG_ATTR.finditer(attr_text):
        if m.start() != pos:
            return False
        name = m.group(1).lower()
        if name in attrs:
            return False
        attrs[name] = m.group(2)
        pos = m.end()
    if attr_text[pos:].strip():
        return False
    return (attrs.get("from") == "human" and attrs.get("trust") == "principal"
            and attrs.get("trigger") == "true")


def sdk_principal_bodies(prompt: str) -> list:
    """The principal's message bodies in an SDK-sent cloud-thread wake, else [].

    Plain text, a relay's or anyone's `<cited>` entry, and a message from
    anyone but the human principal give nothing.
    """
    if not isinstance(prompt, str) or not WAKE_OPEN.match(prompt):
        return []
    prompt = NOTE.sub(" ", prompt)
    prompt = ANY_CITED.sub(" ", prompt)
    return [html.unescape(body) for attrs, body in MESSAGE_TAG.findall(prompt)
            if _principal_attrs(attrs)]


def _mwr_match(prompt: str, sdk: bool = False):
    """The MWR_WHOLE match for the first user body that is only an mwr grant, or None.

    Matched against the body with only the harness's wrappers removed
    (`_mwr_text`), not `typed()` text: `typed()` drops the user's own quotes,
    backticks and blockquotes, so `mwrs "only the docs PRs"` would read as a
    bare `mwrs`. Here any such qualifier makes the message no grant.

    Without `sdk`, only `mwr_bodies()` count: a plain prompt the user typed
    in this session, never anything that opens with a tag (round 7).
    With `sdk`, only `sdk_principal_bodies()` count: the principal's own
    message in a wake, never a relay's `<cited author="user">` entry
    (round 3, finding 5; round 6).
    """
    bodies = sdk_principal_bodies(prompt) if sdk else mwr_bodies(prompt)
    for body in bodies:
        text = _mwr_text(body)
        if not text:
            continue
        match = MWR_WHOLE.match(text)
        if match:
            return match
    return None


def mwr_grant(prompt: str, sdk: bool = False):
    """The `mwr`/`mwrs` grant the user typed in `prompt`: MWR_ALL, a set of
    (repo or None, number), or None.

    `mwrs` alone is the session grant, MWR_ALL. `mwr` (or `mwrs`) followed by
    PR references grants those PRs only. A bare `mwr` names no PR, so it
    grants nothing: the hook cannot tell which PR is meant, and fails closed.

    With `sdk` (an SDK-sent record), only the principal's message in a
    cloud-thread wake is read (`sdk_principal_bodies`, round 6).
    """
    match = _mwr_match(prompt, sdk=sdk)
    if not match:
        return None
    refs = _mwr_refs(match.group("refs") or "")
    if refs:
        return refs
    if match.group("word").lower() == "mwrs":
        return MWR_ALL
    return None


def mwr_bare(prompt: str) -> bool:
    """Whether the user typed an mwr grant that names no repository for a PR.

    A bare `mwr` names no PR, and a repo-less "#N" or "PR N" names no
    repository (round 4; Ezra, 2026-11-20: a bare mwr merges nothing and
    asks which PR). The guard grants neither, so the reminder asks the user
    to name the repository. This is a reminder, not a grant, so the
    principal's message in a wake is read too.
    """
    match = _mwr_match(prompt) or _mwr_match(prompt, sdk=True)
    if not match:
        return False
    refs = _mwr_refs(match.group("refs") or "")
    if not refs:
        return match.group("word").lower() == "mwr"
    return any(repo is None for repo, _ in refs)


def revokes_mwr(prompt: str) -> bool:
    """Whether the user's own words withdraw the `mwr` grants.

    Every revocation `revokes()` reads, plus any user body, a relay's cited
    user entry included, that holds a withdrawal word or mentions review
    (MWR_REVOKE) anywhere, its own quotes included, whether or not it names
    the mwr token: "never mind", "cancel that", "stop mwr", "wait for review
    before merging". It fails toward revoking. Text in a system reminder,
    and a harness-written prompt, are not the user's and are not read.
    PR references are removed first (MWR_REF_TEXT), so a repository name
    such as "not-a-bug" is not read as a withdrawal.
    """
    if revokes(prompt):
        return True
    return any(MWR_REVOKE.search(MWR_REF_TEXT.sub(" ", _mwr_text(body)))
               for body in user_bodies(prompt))


MWR_BARE_REMINDER = (
    "[hook: remind-plain-english-merge-word] The user typed an `mwr` that names no PR, or "
    "a PR number with no repository (\"mwr #N\"), so it grants no merge: the merge guard "
    "denies until the user names the repository and PR (\"mwr owner/repo#N\", or "
    "\"mwr repo#N\" for Morrison-Lab/repo), or types `mwrs` for the session. Merge nothing; "
    "ask the user to name the repository and PR they mean."
)


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
    if mwr_bare(prompt):
        print(MWR_BARE_REMINDER)
        return 0
    word = merge_word(prompt)
    if word is None:
        return 0
    print(REMINDER.format(quote=word[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
