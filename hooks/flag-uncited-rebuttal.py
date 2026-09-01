#!/usr/bin/env python3
"""PreToolUse reminder: a PR/issue-comment rebuttal disputing a finding that
named a specific external source, with no fetch of that source anywhere in
the transcript.

THE INCIDENT
------------
On `Morrison-Lab/ai-config#2070` (2026-08-24), a reviewer's finding cited a
specific external URL as its evidence: "VS Code's own documentation
(`code.visualstudio.com/docs/agents/run/agent-harnesses` and
`agents-window`) names this setting `github.copilot.chat.claudeAgent.enabled`".
The session posted a rebuttal disputing that finding, using only two greps of
a local installed binary as evidence -- it never fetched the URL the
reviewer had named. The rebuttal was wrong. Two rounds later the reviewer
re-raised the same finding, still citing the same URL; only then did the
session run `WebFetch` on it, discover the reviewer was right all along, and
retract:

    "Retracting my earlier rebuttal. You were right to re-raise this ... I
    fetched code.visualstudio.com/docs/agents/run/agent-harnesses live just
    now and it does say what you quoted."

The wrong rebuttal read:

    "I'm not changing this claim -- the direct bundle read supports it as
    written."

`shared/workflow/address-every-comment.md`'s "read the cited source" rule
already exists in prose -- `shared/workflow/self-review-fallback.md` states
it as "a citation gets read against what the cited source actually says"
-- but nothing enforced it at the moment it mattered: before posting a
reply that disputes a finding which named a specific external source.

THE CHECK
---------
Fires only when ALL of these hold:

  1. The about-to-run Bash command posts a PR/issue comment or review reply
     with a body: `gh pr comment`, `gh issue comment`, or `gh api` against a
     `.../comments` or `.../replies` endpoint carrying a body argument
     (`--body`, `--body-file <file>`, or `-F body=@<file>`). The body text is
     read from disk when it is file-based, since this corpus's own
     convention (CLAUDE.md's "PowerShell CLI Command Safety") is to write
     the body to a file before the `gh` call, so the file already exists.
  2. That body text carries a dispute/rebuttal cue -- a lenient,
     case-insensitive phrase list built from this exact incident's wrong
     rebuttal ("I'm not changing this claim", "the direct bundle read
     supports it") and its later retraction ("Retracting my earlier
     rebuttal").
  3. Walking the transcript, the most recent fetch of that PR/issue's
     comments (a `gh api .../comments` GET, `gh pr view --json
     reviews,comments`, or an MCP `pull_request_read`/`issue_read` call)
     returned text containing at least one external URL -- one that is not
     a `github.com/<owner>/<repo>` link back to the same repo.
  4. No earlier `WebFetch` in the transcript targeted that URL (or its bare
     domain, so a fetch of a neighbouring page on the same doc site still
     discharges it), and no earlier `WebSearch` used it as a query term.

WHY WARN RATHER THAN BLOCK
---------------------------
The same asymmetry `warn-pr-create-without-dupe-check.py` names: a rebuttal
that turns out wrong is cheap to retract, one round later, in public, exactly
as the incident did -- while a blocked comment-post would refuse a large
class of legitimate replies this hook cannot actually verify are wrong. It
cannot know whether the cited URL was already read some other way (a prior
session, a cached copy, a colleague's report), only that nothing IN THIS
TRANSCRIPT fetched it. So it reminds, and names the specific unfetched URL,
rather than refusing the post.

WHY THE CUE LIST IS LENIENT
----------------------------
A missed true positive here is a wrong rebuttal shipped unexamined, which is
exactly the incident. A false positive costs one ignorable reminder. That
asymmetry is why the phrase list below is broad rather than narrow, and why
it is drawn from the incident's own two comments rather than invented from
first principles.

FAILS OPEN
----------
Any parse trouble, an unreadable transcript, a missing or unreadable body
file, or an unresolvable PR/issue number all return 0 silently. A reminder
that cannot establish its own precondition must not fire.
"""
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

# --------------------------------------------------------------------------
# Clause 1: is this command posting a PR/issue comment or reply with a body?
# --------------------------------------------------------------------------

# A heredoc body is prose, not commands -- same stripper as
# warn-pr-create-without-dupe-check.py, so a heredoc quoting `gh pr comment`
# as documentation does not itself look like a comment-post at a command
# position.
RX_HEREDOC = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?([^\n]*)\n"
    r".*?\n[ \t]*\1\b",
    re.DOTALL,
)


def strip_heredocs(command):
    return RX_HEREDOC.sub(lambda m: m.group(2), command)


# Position-anchored, per this corpus's own dupe-check hooks: an unanchored
# match would fire on prose that merely mentions `gh pr comment`, which this
# repo's own fragments (and this docstring) quote constantly.
RX_COMMENT_POST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:"
    r"gh\s+pr\s+comment\b"
    r"|gh\s+issue\s+comment\b"
    r"|gh\s+api\s+\S*(?:issues|pulls)/\d+/comments\b"
    r"|gh\s+api\s+\S*/comments/\d+/replies\b"
    r")",
    re.I | re.M,
)

RX_PR_COMMENT_NUM = re.compile(r"gh\s+pr\s+comment\s+(\d+)", re.I)
RX_ISSUE_COMMENT_NUM = re.compile(r"gh\s+issue\s+comment\s+(\d+)", re.I)
RX_API_COMMENTS_NUM = re.compile(
    r"gh\s+api\s+\S*(?:issues|pulls)/(\d+)/comments\b", re.I)

RX_REPO_FLAG = re.compile(r"(?:^|\s)(?:-R|--repo)\s+([\w.-]+)/([\w.-]+)")
RX_API_REPO = re.compile(r"repos/([\w.-]+)/([\w.-]+)/")

# Body-argument shapes, in the order this corpus's own convention prefers
# them (a file on disk, then a literal). `--body-file`/`-F body=@file` are
# read from disk; `-f`/`--body` literals are read straight out of the
# command text.
RX_BODY_FILE = re.compile(
    r"--body-file[= ]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
RX_F_BODY_FILE = re.compile(
    r"(?:-F|--field)\s+body=@(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
RX_F_BODY_LITERAL = re.compile(
    r"(?:-f|--raw-field)\s+body=(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)'|(\S+))",
    re.S)
RX_BODY_LITERAL = re.compile(
    r"--body\s+(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)')", re.S)


def _first_group(m):
    return next(g for g in m.groups() if g is not None)


def extract_body_text(command, cwd):
    """The comment body this command would post, or None if undetermined.

    File-based forms are read from disk under `cwd`, per this corpus's own
    convention (CLAUDE.md's PowerShell/backtick-safety section) that the
    file is always written before the `gh` call -- so it already exists by
    the time this hook runs. Reading fails open (returns None) rather than
    raising, since a missing or unreadable file means the precondition this
    hook needs cannot be established.
    """
    for rx in (RX_BODY_FILE, RX_F_BODY_FILE):
        m = rx.search(command)
        if not m:
            continue
        rel = _first_group(m)
        if rel == "-":
            return None  # stdin body: nothing on disk to read
        path = rel if os.path.isabs(rel) else os.path.join(cwd, rel)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return None
    for rx in (RX_F_BODY_LITERAL, RX_BODY_LITERAL):
        m = rx.search(command)
        if m:
            return _first_group(m)
    return None


def extract_number(command):
    for rx in (RX_PR_COMMENT_NUM, RX_ISSUE_COMMENT_NUM, RX_API_COMMENTS_NUM):
        m = rx.search(command)
        if m:
            return int(m.group(1))
    return None


def extract_repo(command):
    m = RX_REPO_FLAG.search(command)
    if m:
        return m.group(1), m.group(2)
    m = RX_API_REPO.search(command)
    if m:
        return m.group(1), m.group(2)
    return None, None


RX_GIT_REMOTE = re.compile(r"[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$")


def resolve_repo_from_git(cwd):
    """(owner, repo) inferred from `origin`'s URL at `cwd` -- the same source
    `gh pr comment`/`gh issue comment` themselves use when no repo is named
    explicitly on the command line. This is what lets clause 3 tell a
    same-repo fetch from an unrelated one when the post command carries no
    `-R` flag, which is the common case: `gh pr comment N --body-file f`
    names no repo at all, inferring it from the working tree exactly as
    this function does.

    Fails open to (None, None) on any git or parse trouble -- this is a
    fallback signal that sharpens attribution, never a precondition for the
    hook to fire.
    """
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None, None
    if out.returncode != 0:
        return None, None
    m = RX_GIT_REMOTE.search(out.stdout.strip())
    return (m.group(1), m.group(2)) if m else (None, None)


def parse_comment_post(command, cwd):
    """(owner, repo, number, body_text) for a comment-post command, else None."""
    stripped = strip_heredocs(command)
    if not RX_COMMENT_POST.search(stripped):
        return None
    body_text = extract_body_text(stripped, cwd)
    if body_text is None:
        return None
    owner, repo = extract_repo(stripped)
    number = extract_number(stripped)
    return owner, repo, number, body_text


# --------------------------------------------------------------------------
# Clause 2: does the body dispute a finding?
# --------------------------------------------------------------------------

# Built from this incident's own two comments -- comment 5391223603 (the
# wrong rebuttal: "I'm not changing this claim", "the direct bundle read
# supports it as written", "Re-verified finding") and comment 5391266668
# (the retraction: "Retracting my earlier rebuttal"). Deliberately lenient:
# a missed true positive here is the incident recurring, a false positive
# costs one ignorable reminder.
DISPUTE_CUE = re.compile(
    r"""(
        retract(?:ing|ed|s)?
      | rebut(?:t(?:ing|ed)|s)?
      | not\s+changing\s+(?:this|that|my)
      | still\s+(?:think|believe|hold|stands?|correct)
      | \bdisagree\b
      | the\s+claim\s+stands
      | confirmed\s+(?:that|this)
      | verified\s+(?:that|this)
      | checked\s+(?:that|this)\s+(?:myself|directly)
      | my\s+(?:earlier|prior|original)\s+
          (?:claim|analysis|finding|check|reading|rebuttal)
      | (?:i\s*'?m|i\s+am)\s+not\s+changing
      | (?:direct|bundle|source|local)\s+(?:bundle\s+)?read\s+supports
      | re-?verified\s+finding
    )""",
    re.I | re.X,
)


# --------------------------------------------------------------------------
# Clauses 3-4: transcript scan
# --------------------------------------------------------------------------

RX_API_COMMENTS_GET = re.compile(
    r"gh\s+api\s+\S*repos/([\w.-]+)/([\w.-]+)/(?:issues|pulls)/(\d+)/comments\b",
    re.I,
)
RX_PR_VIEW = re.compile(
    r"gh\s+pr\s+view\s+(\d+)\b[^\n]*--json\s+\S*(?:comments|reviews)", re.I)
RX_ISSUE_VIEW = re.compile(
    r"gh\s+issue\s+view\s+(\d+)\b[^\n]*--json\s+\S*comments", re.I)
MCP_READ_NAME = re.compile(r"pull_request_read|issue_read", re.I)
MCP_NUMBER_KEY = re.compile(
    r'"(?:pullNumber|pull_number|issueNumber|issue_number)"\s*:\s*(\d+)')

RX_URL = re.compile(r"https?://[^\s<>\)\]\"'`]+")

# A reviewer's citation is routinely a BARE domain-plus-path, no scheme --
# exactly the incident this hook is named for: "VS Code's own documentation
# (`code.visualstudio.com/docs/agents/run/agent-harnesses`)" carries no
# `https://` at all. Requires a `/` after the domain (a real citation names a
# page, not a bare hostname), and a negative lookbehind so it does not
# re-match the domain portion of a URL RX_URL already found (excluded when
# preceded by `/`, `.`, `@`, or a word character -- which is exactly what
# precedes a domain inside `https://domain/path`).
RX_BARE_URL = re.compile(
    r"(?<![\w@/.])"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,24}"
    r"/[^\s<>\)\]\"'`]*"
)

RX_GITHUB_REPO_URL = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s]+)(?:/|$)", re.I)


def _domain_of(url):
    """The host portion of `url`, scheme-optional."""
    if "://" in url:
        try:
            return urlparse(url).netloc.lower()
        except ValueError:
            return ""
    return url.split("/", 1)[0].lower()


MCP_OWNER_KEY = re.compile(r'"owner"\s*:\s*"([^"]+)"')
MCP_REPO_KEY = re.compile(r'"repo"\s*:\s*"([^"]+)"')

NO_MATCH = ("no-match", None, None)


def _is_bash_fetch(command):
    """(number_or_None, owner_or_None, repo_or_None) when `command` fetches
    PR/issue comments, else the NO_MATCH sentinel.

    `gh pr comment`/`gh issue comment` routinely carry no `-R` flag at all --
    they infer the repo from the working tree -- so the comment-post command
    itself is usually silent on owner/repo. The FETCH command that read the
    finding is the more reliable source: `gh api repos/OWNER/REPO/...` names
    it explicitly. Callers use this as a fallback when the post command's own
    owner/repo could not be determined.
    """
    stripped = strip_heredocs(command)
    # A `gh api .../comments` URL shape is shared by the GET this clause
    # wants and the POST clause 1 already claimed, and a POST's tool_result
    # is the newly created comment -- not the finding being disputed. Any
    # body-write flag means this is a write, not a fetch.
    if any(rx.search(stripped) for rx in
           (RX_BODY_FILE, RX_F_BODY_FILE, RX_F_BODY_LITERAL, RX_BODY_LITERAL)):
        return NO_MATCH
    m = RX_API_COMMENTS_GET.search(stripped)
    if m:
        return int(m.group(3)), m.group(1), m.group(2)
    m = RX_PR_VIEW.search(stripped) or RX_ISSUE_VIEW.search(stripped)
    if m:
        return int(m.group(1)), None, None
    return NO_MATCH


def _is_mcp_fetch(name, inp_blob):
    if not MCP_READ_NAME.search(name or ""):
        return NO_MATCH
    num_m = MCP_NUMBER_KEY.search(inp_blob)
    owner_m = MCP_OWNER_KEY.search(inp_blob)
    repo_m = MCP_REPO_KEY.search(inp_blob)
    return (
        int(num_m.group(1)) if num_m else None,
        owner_m.group(1) if owner_m else None,
        repo_m.group(1) if repo_m else None,
    )


def _result_text(block):
    """Flatten a tool_result block's payload into one searchable string.

    Same shape as no-push-without-self-review.py's `_result_text`: a
    transport carries `content` as a plain string in some shapes and a list
    of content blocks in others.
    """
    parts = []
    content = block.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for sub in content:
            if isinstance(sub, str):
                parts.append(sub)
            elif isinstance(sub, dict):
                parts.append(str(sub.get("text") or sub.get("content") or ""))
    for key in ("output", "text"):
        val = block.get(key)
        if isinstance(val, str):
            parts.append(val)
    return "\n".join(p for p in parts if p)


def is_self_referential(url, owner, repo):
    m = RX_GITHUB_REPO_URL.match(url)
    if not m:
        return False  # not a github.com repo link at all -> external
    if owner and repo:
        return m.group(1).lower() == owner.lower() and m.group(2).lower() == repo.lower()
    return False  # can't confirm self-reference -> lean toward firing


_TRAILING_PUNCT = ").,;:!?]}\"'`"


def external_urls(text, owner, repo):
    found, seen = [], set()
    text = text or ""
    for rx in (RX_URL, RX_BARE_URL):
        for m in rx.finditer(text):
            url = m.group(0).rstrip(_TRAILING_PUNCT)
            if url in seen:
                continue
            seen.add(url)
            if is_self_referential(url, owner, repo):
                continue
            found.append(url)
    return found


def find_cited_urls(records, owner, repo, number):
    """URLs external_urls() found in the LAST matching comments-fetch.

    Walks the transcript forward and keeps overwriting the result, so
    finishing the walk leaves the MOST RECENT matching fetch's URLs -- the
    same answer "walk backward, take the first match" would give.
    """
    pending = {}  # tool_use_id -> matched number (or None if unresolved)
    result = []
    for idx, m in enumerate(records):
        blocks = (m.get("message") or {}).get("content") or m.get("content") or []
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        elif not isinstance(blocks, list):
            blocks = []
        else:
            blocks = list(blocks)

        if "tool_calls" in m and isinstance(m["tool_calls"], list):
            for tc in m["tool_calls"]:
                if isinstance(tc, dict):
                    tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                    targs = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                    if isinstance(targs, str):
                        try:
                            targs = json.loads(targs)
                        except Exception:
                            targs = {"command": targs}
                    tid = tc.get("id") or str(id(tc))
                    blocks.append({
                        "type": "tool_use",
                        "id": tid,
                        "name": tname,
                        "input": targs if isinstance(targs, dict) else {},
                    })

        for b in blocks:
            if not isinstance(b, dict):
                continue
            btype = b.get("type")
            if btype == "tool_use":
                name = b.get("name") or ""
                inp = b.get("input") or {}
                if not isinstance(inp, dict):
                    inp = {}
                command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd")
                if isinstance(command, str) and command.strip():
                    fetch = _is_bash_fetch(command)
                else:
                    fetch = _is_mcp_fetch(name, json.dumps(inp))
                if fetch[0] == "no-match":
                    continue
                use_id = b.get("id") or f"idx_{idx}"
                pending[use_id] = fetch
            elif btype == "tool_result":
                use_id = b.get("tool_use_id")
                if not use_id or use_id not in pending:
                    continue
                fetch_num, fetch_owner, fetch_repo = pending.pop(use_id)
                if number is not None and fetch_num is not None and fetch_num != number:
                    continue
                # A fetch naming a DIFFERENT repo than the one this comment
                # is being posted to is never a match, even when the PR/issue
                # number is unresolved -- `owner`/`repo` here is already the
                # post command's own repo, git-remote-resolved as a fallback
                # by the caller when the command carried no `-R`. Without
                # this, an unnumbered `gh pr comment` with an unrelated
                # earlier fetch anywhere in the transcript (a different repo
                # entirely) could be misattributed as this PR's citation.
                if (owner and repo and fetch_owner and fetch_repo
                        and (fetch_owner.lower() != owner.lower()
                             or fetch_repo.lower() != repo.lower())):
                    continue
                effective_owner = owner or fetch_owner
                effective_repo = repo or fetch_repo
                urls = external_urls(_result_text(b), effective_owner, effective_repo)
                if urls:
                    result = urls
    return result


def urls_were_fetched(records, urls):
    """True when an earlier WebFetch targeted one of `urls` (or its domain),
    or an earlier WebSearch used one as a query term."""
    if not urls:
        return True
    targets = set()
    for u in urls:
        targets.add(u)
        domain = _domain_of(u)
        if domain:
            targets.add(domain)

    for m in records:
        blocks = (m.get("message") or {}).get("content") or m.get("content") or []
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        elif not isinstance(blocks, list):
            blocks = []
        else:
            blocks = list(blocks)

        if "tool_calls" in m and isinstance(m["tool_calls"], list):
            for tc in m["tool_calls"]:
                if isinstance(tc, dict):
                    tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                    targs = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                    if isinstance(targs, str):
                        try:
                            targs = json.loads(targs)
                        except Exception:
                            targs = {"command": targs}
                    tid = tc.get("id") or str(id(tc))
                    blocks.append({
                        "type": "tool_use",
                        "id": tid,
                        "name": tname,
                        "input": targs if isinstance(targs, dict) else {},
                    })

        for b in blocks:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            name = b.get("name") or ""
            inp = b.get("input") or {}
            if not isinstance(inp, dict):
                continue
            if name in ("WebFetch", "read_url_content", "fetch_web_page"):
                fetched = str(inp.get("url") or inp.get("Url") or "")
                if any(t and (t in fetched or fetched in t) for t in targets):
                    return True
            elif name in ("WebSearch", "search_web", "google_search"):
                query = str(inp.get("query") or inp.get("Query") or "")
                if any(t and t in query for t in targets):
                    return True
    return False


def read_records(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


NOTE = """\
This rebuttal disputes a finding, and the source the finding cited was never \
fetched in this transcript:

{urls}

On Morrison-Lab/ai-config#2070, a rebuttal disputing a finding that cited an \
external URL was posted using only local grep evidence -- never fetching the \
URL the reviewer named. The rebuttal was wrong; the reviewer re-raised it, \
and only then did a WebFetch of the URL show the reviewer had been right \
all along.

If the source has genuinely already been checked some other way, this is a \
false positive -- disregard it. Otherwise, fetch the URL before posting.\
"""


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        if is_dry_run:
            print(f"flag-uncited-rebuttal: unreadable hook input ({exc})",
                  file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if not isinstance(payload, dict) or payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0
    command = tool_input.get("command") or tool_input.get("CommandLine") or tool_input.get("cmd") or tool_input.get("script")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    cwd = payload.get("cwd") or os.getcwd()

    try:
        parsed = parse_comment_post(command, cwd)
        if parsed is None:
            return 0
        owner, repo, number, body_text = parsed
        if not DISPUTE_CUE.search(body_text):
            return 0
        if not owner or not repo:
            # `gh pr comment`/`gh issue comment` routinely carry no `-R`,
            # inferring the repo from the working tree exactly as this
            # fallback does. Resolving it here is what lets find_cited_urls
            # reject a same-shaped fetch belonging to an unrelated repo.
            git_owner, git_repo = resolve_repo_from_git(cwd)
            owner = owner or git_owner
            repo = repo or git_repo

        transcript_path = payload.get("transcript_path") or ""
        if not transcript_path or not os.path.isfile(transcript_path):
            return 0
        records = list(read_records(transcript_path))

        urls = find_cited_urls(records, owner, repo, number)
        if not urls:
            return 0
        if urls_were_fetched(records, urls):
            return 0
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-uncited-rebuttal: could not evaluate ({exc})",
              file=sys.stderr)
        return 0

    url_list = "\n".join(f"  - {u}" for u in urls)
    note = NOTE.format(urls=url_list)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"This rebuttal disputes a finding whose cited source "
            f"({urls[0]}) was never fetched in this transcript."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
