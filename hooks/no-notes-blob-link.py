#!/usr/bin/env python3
"""PreToolUse: link notes content to the rendered site, not a github.com blob.

ai-config#5705. Ezra, 2026-11-16: "when you hyperlink to content in the notes,
can you prefer hyperlinking to the rendered github pages site (when the
relevant content is up to date there)?" The coordinator had linked
github.com/Morrison-Lab/lds/blob/main/chapters/_subfiles/classification-lab/_dat-smarket.qmd
where https://morrison-lab.github.io/lds/chapters/classification-lab.html#dat-smarket
was the better link.

Denies a user-visible post or a forge comment, issue or PR body that links
`github.com/Morrison-Lab/<notes repo>/blob/<main|master>/<path>.qmd`.
The reason suggests the rendered URL: a page maps to `<site>/<path>.html`,
and a subfile maps to the page that includes it (found in a local checkout of
the repo when one exists) plus the first `{#id}` in the subfile.

A deny, not a reminder, because the failing shape is lexical (ai-config#4741).
It passes:

- a link pinned to a branch or SHA, which is how content in an open PR, not
  yet deployed, is linked;
- a file the site does not render: not `.qmd`, or under `tools/`, `.github/`,
  `_extensions/`, `filters/`, `outtakes/`, `latex-macros/` or `macros/`;
- a link whose line says why the source is meant: the content is not deployed
  (published, live, on the site) yet, or the link points at source lines,
  source text or the source file.
  The hook cannot tell from the text whether the last deploy is current, so
  that judgment is the writer's, stated on the line where a reviewer sees it;
- `ALLOW_NOTES_BLOB_LINK=1`.

Fails open on any parse trouble.
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
TEXT_KEYS = {"text", "body", "question", "label", "consequence", "comment", "message"}
BLOB = re.compile(
    r"https?://github\.com/morrison-lab/([A-Za-z0-9_.-]+)/blob/([^/\s)>\]]+)/([^\s)>\]#?]+)",
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
    """Every string in the tool input under a key that carries prose."""
    if isinstance(value, str):
        if key in TEXT_KEYS:
            yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from strings(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v, key)


def bash_text(command: str) -> str:
    if not GH_POST.search(command):
        return ""
    try:
        return "\n".join(shlex.split(command))
    except ValueError:
        return command


def candidate_roots(repo: str) -> list:
    bases = [os.environ.get("CLAUDE_PROJECT_DIR") or "", os.getcwd(), "/home/user",
             os.path.expanduser("~/Documents/GitHub"), os.path.expanduser("~")]
    roots = []
    for base in bases:
        if not base:
            continue
        for root in (os.path.join(base, repo), os.path.join(os.path.dirname(base), repo)):
            if os.path.isdir(root) and root not in roots:
                roots.append(root)
        if os.path.basename(os.path.normpath(base)).lower() == repo.lower():
            roots.insert(0, base)
    return roots


def first_id(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            match = DIV_ID.search(f.read())
    except OSError:
        return None
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
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                continue
            if name not in text:
                continue
            for inc in INCLUDE.findall(text):
                if os.path.basename(inc) != name:
                    continue
                for base in (dirpath, root):
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
    for line in text.splitlines():
        if EXEMPT.search(line):
            continue
        for m in BLOB.finditer(line):
            repo, ref, rel = m.group(1), m.group(2), m.group(3).rstrip(".,;:!'\"")
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
    url = rendered_url(repo, rel)
    if url:
        suggest = f", such as {url}"
    else:
        suggest = (": the page that includes this subfile, plus the subfile's div anchor "
                   f"(https://morrison-lab.github.io/{repo.lower()}/<page>.html#<id>)")
    return REASON.format(link=link, suggest=suggest)


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
