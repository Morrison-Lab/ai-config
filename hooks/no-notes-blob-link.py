#!/usr/bin/env python3
"""PreToolUse: link notes content to the rendered site, not a github.com blob.

ai-config#5705. Ezra, 2026-11-16: "when you hyperlink to content in the notes,
can you prefer hyperlinking to the rendered github pages site (when the
relevant content is up to date there)?"

Denies a user-visible post or a forge comment, issue or PR body that links
`github.com/Morrison-Lab/<notes repo>/blob/main/<path>.qmd`, and suggests the
rendered URL: a subfile maps to the page that includes it (read from a local
checkout) plus the subfile's first `{#id}`. A deny, not a reminder, because
the failing shape is lexical (ai-config#4741). It passes a branch- or
SHA-pinned link (an open PR's undeployed content), an unrendered path
(`tools/`, `.github/`, `outtakes/`, ...), a `#L<n>` or `?plain=1` source view,
a URL in a code span or fence, and a line saying the content is not deployed
yet or that it means the source lines, text or file (the writer states
whether the deploy is current; no text shows it). In Bash, only the --body/--title values of a gh issue/pr post are read (ai-config#5706).
Writer rule: shared/writing/hyperlink-liberally.md; reviewer: adversarial-reviewer.
`ALLOW_NOTES_BLOB_LINK=1` overrides. Fails open on any parse trouble.
"""
import json
import os
import re
import shlex
import sys

OVERRIDE = "ALLOW_NOTES_BLOB_LINK"
NOTES_REPOS = {"lds", "mds", "pds", "sds", "mcs", "psw", "psc", "rme", "win", "cie", "ids", "cds"}
TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|request_decision"
    r"|message_coordinator|message_thread)$"
    r"|^mcp__github__(?:add_issue_comment|update_issue_comment|add_reply_to_pull_request_comment"
    r"|add_comment_to_pending_review|pull_request_review_write|issue_write"
    r"|create_pull_request|update_pull_request)$")
GH_POST = re.compile(r"\bgh\s+(?:issue|pr)\s+(?:comment|create|edit|review)\b")
BODY_FLAGS = {"--body", "-b", "--title", "-t"}
TEXT_KEYS = {"text", "body", "title", "question", "label", "consequence", "comment", "message"}
FENCE = re.compile(r"^```.*?^```|^~~~.*?^~~~|`[^`\n]*`", re.S | re.M)
BLOB = re.compile(
    r"https?://github\.com/morrison-lab/([A-Za-z0-9_.-]+)/blob/([^/\s)>\]]+)/([^\s)>\]#?`]+)"
    r"(\?plain=1|#L\d)?",
    re.I)
MAIN_REFS = {"main", "master", "head"}
UNRENDERED = re.compile(
    r"(?:^|/)(?:tools|\.github|_extensions|filters|outtakes|latex-macros|macros|scripts)/")
EXEMPT = re.compile(
    r"\bnot\s+(?:yet\s+)?(?:been\s+)?(?:deployed|published|live|rendered|re-?rendered)"
    r"|\bnot\s+(?:yet\s+)?on\s+the\s+(?:rendered\s+|live\s+|published\s+)?site"
    r"|\b(?:undeployed|unpublished)\b|\bahead\s+of\s+the\s+(?:deploy|site)"
    r"|\bsource\s+(?:line|lines|text|code|file)\b|\bin\s+the\s+source\b",
    re.I)
INCLUDE = re.compile(r"\{\{<\s*include\s+([^\s>]+)\s*>\}\}")
DIV_ID = re.compile(r"\{#([A-Za-z][\w:.-]*)")

REASON = (
    "[hook: no-notes-blob-link] {link} links notes content as a github.com blob "
    "(ai-config#5705, Ezra 2026-11-16: \"prefer hyperlinking to the rendered github pages "
    "site (when the relevant content is up to date there)\"). Link the rendered page instead"
    "{suggest}. If the content is not deployed yet, or you mean the source itself, say so on "
    "the same line (\"not deployed yet\", \"source lines\") or pin the link to a branch or SHA."
)


def strings(value, key=None):
    if isinstance(value, str):
        if key in TEXT_KEYS:
            yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from strings(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v, key)


def gh_flag_values(tokens: list) -> list:
    """The --body/--title values in one gh command's tokens, in any of its spellings."""
    values = [t for prev, t in zip([""] + tokens, tokens) if prev in BODY_FLAGS]
    for t in tokens:
        if t.startswith("--") and t.split("=", 1)[0] in BODY_FLAGS and "=" in t:
            values.append(t.split("=", 1)[1])
        elif t[:2] in BODY_FLAGS and len(t) > 2 and not t.startswith("--"):
            values.append(t[2:])
    return values


def bash_text(command: str) -> str:
    """The --body and --title values of each gh issue/pr post; a --body-file is not read."""
    if not GH_POST.search(command):
        return ""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return ""
    values, segment = [], []
    for token in tokens + [";"]:
        if token and set(token) <= set(";&|\n"):
            if segment[:1] == ["gh"] and GH_POST.search(" ".join(segment[:3])):
                values += gh_flag_values(segment)
            segment = []
        else:
            segment.append(token)
    return "\n".join(values)


def candidate_roots(repo: str) -> list:
    bases = [os.environ.get("CLAUDE_PROJECT_DIR") or "", os.getcwd(), "/home/user",
             os.path.expanduser("~/Documents/GitHub"), os.path.expanduser("~")]
    roots = [b for b in bases if b and os.path.basename(os.path.normpath(b)).lower() == repo.lower()]
    for base in filter(None, bases):
        roots += [os.path.join(base, repo), os.path.join(os.path.dirname(base), repo)]
    return [r for i, r in enumerate(roots) if os.path.isdir(r) and r not in roots[:i]]


def first_id(path: str):
    with open(path, encoding="utf-8") as f:
        match = DIV_ID.search(f.read())
    return match.group(1) if match else None


def including_file(root: str, target: str):
    """The .qmd under root whose include resolves to target, or None."""
    name = os.path.basename(target)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")
                       and d not in {"_site", "_freeze", "_extensions", "node_modules"}
                       and not os.path.islink(os.path.join(dirpath, d))]
        for fname in filenames:
            if not fname.endswith(".qmd"):
                continue
            path = os.path.join(dirpath, fname)
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            for inc in INCLUDE.findall(text) if name in text else []:
                for base in (dirpath, root) if os.path.basename(inc) == name else ():
                    if os.path.realpath(os.path.join(base, inc)) == os.path.realpath(target):
                        return path
    return None


def rendered_url(repo: str, rel: str) -> str:
    site = f"https://morrison-lab.github.io/{repo.lower()}/"
    anchor = None
    for root in candidate_roots(repo):
        target = os.path.join(root, rel)
        if not os.path.isfile(target):
            continue
        current = target
        for _ in range(6):
            if not os.path.basename(current).startswith("_"):
                break
            anchor = anchor or first_id(current)
            parent = including_file(root, current)
            if parent is None:
                return ""
            current = parent
        page = os.path.relpath(current, root)
        url = site + re.sub(r"\.qmd$", ".html", page)
        return url + (f"#{anchor}" if anchor else "")
    if os.path.basename(rel).startswith("_"):
        return ""
    return site + re.sub(r"\.qmd$", ".html", rel)


def flagged(text: str) -> list:
    hits = []
    for line in FENCE.sub(" ", text).splitlines():
        if EXEMPT.search(line):
            continue
        for m in BLOB.finditer(line):
            repo, ref, rel = m.group(1), m.group(2), m.group(3).rstrip(".,;:!'\"")
            if m.group(4):
                continue
            if repo.lower() not in NOTES_REPOS or ref.lower() not in MAIN_REFS:
                continue
            if not rel.endswith(".qmd") or UNRENDERED.search(rel):
                continue
            hits.append((m.group(0), repo, rel))
    return hits


def denial(payload: dict):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    if tool == "Bash":
        text = bash_text(str(tool_input.get("command") or ""))
    elif TOOL.search(tool):
        text = "\n".join(strings(tool_input))
    else:
        return None
    hits = flagged(text)
    if not hits:
        return None
    link, repo, rel = hits[0]
    url = rendered_url(repo, rel) or f"https://morrison-lab.github.io/{repo.lower()}/<page>.html#<id>"
    return REASON.format(link=link, suggest=f", such as {url}")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        reason = denial(payload)
    except Exception:
        return 0
    if reason:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
