#!/usr/bin/env python3
"""PreToolUse reminder: issue-driven edits without a fresh issue and remote check.

[`check-history`](../skills/check-history/SKILL.md) already names an
issue-state check (VIEW_ISSUE: is the issue already resolved on `main`?) and
an open-PR check (LIST_PRS: does an existing PR already cover it?), but that
rule is consulted at read time and broken at the first `Write`/`Edit`. The
omission has no artifact, which is why a memory bullet does not catch it.
Neither of `check-history`'s own checks confirms the *local checkout* is
fresh against the remote default branch, which is the gap this hook adds a
check for.

WHAT HAPPENED
-------------
Recurred three times (tracked as Morrison-Lab/ai-config#2282):

  1. ucdavis/bcs#266: a PR merged between status reads.
  2. A Sparta gii-ffdb93 session on 2026-07-14: tool availability was
     asserted from stale documentation rather than live discovery.
  3. ucdavis/rampp#140 on 2026-08-26: implementation began from a 2026-07-19
     checkout; the issue and its implementing PR had already merged on
     2026-07-22. Three redundant local edits and an unpublished branch
     landed before a later status check caught the drift.

The written rule in `memories/preferences.md` and `skills/check-history/SKILL.md`
was loaded in each case. The third case is the one this hook can decide: the
session named a forge issue and edited source without a fresh VIEW_ISSUE or
a fresh remote/default-branch read after that request.

WHY WARN RATHER THAN BLOCK
--------------------------
README's "A hook that misfires is worse than a missing one". A blocked
`Write` is expensive --- it interrupts the edit that makes the work visible
--- and this hook cannot tell a live check that used an unmapped tool from
one that never ran. A reminder naming the two queries costs one line.
Closed-issue evidence also warns rather than denies: reopening is sometimes
the right next step, and Cursor JSONL often omits `tool_result`, so a block
built on result text would refuse a class of sessions it cannot actually
see.

THE CHECK
---------
Fires only when ALL of these hold:

  1. The about-to-run tool is a source/config write (`Write`, `Edit`,
     `NotebookEdit`, or the Cursor names the adapter maps onto those).
  2. Some earlier USER prose message in this transcript names a forge
     issue (a GitHub/GitLab issue URL, `owner/repo#N`, `issue #N`, or
     implement/fix/closes/resolves + `#N`). Pull URLs do not count.
     The first such message arms the guard. A later message retargets
     only with a URL or implement/fix/closes/resolves + `#N` that names
     a *different* issue; repeating the same number does not.
  3. After that message, the transcript lacks fresh evidence of BOTH:
       (a) a VIEW_ISSUE of that number, and
       (b) a remote/default-branch read.

VIEW_ISSUE and FETCH stems are read from `tool-mappings.yml` so a GitHub MCP
spelling counts, not only `gh issue view`. GitLab `glab issue view` (and its
documented `glab issue show` alias) and `git ls-remote` / `git pull` are
extra live-read forms the mapping file does not currently list; they
discharge the matching half, they do not replace it.

A check that appears ONLY BEFORE the naming message is stale for this
request --- leftover from an earlier task in the same session.

If a VIEW_ISSUE of that number after the request has a `tool_result` whose
state field is closed, the warning says so. Missing result text is not
treated as open and not treated as closed.

Command-position matching plus heredoc-body stripping follow
`warn-pr-create-without-dupe-check.py`: this corpus quotes `gh issue view`
constantly, and an unanchored matcher would fire on (or, worse, discharge
on) prose about the rule it enforces.

FAILS OPEN
----------
Unreadable stdin, a missing transcript, or any parse trouble prints nothing
and exits 0. A reminder that cannot establish its own precondition must not
fire.
"""
from __future__ import annotations

import functools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAPPINGS_PATH = os.path.join(ROOT, "tool-mappings.yml")

WRITE_TOOLS = frozenset({
    "Write", "Edit", "NotebookEdit",
    "StrReplace", "EditNotebook",  # Cursor names, if the adapter is skipped
    "write_to_file", "replace_file_content", "write", "edit", "multiedit",
    "notebookedit", "create", "update", "str_replace_editor", "apply_patch",
    "edit_file", "strreplace", "create_file",
})

# Latest user-prose issue reference, in this order.
RX_GH_ISSUE_URL = re.compile(
    r"(?:https?://)?github\.com/([^/\s]+)/([^/\s]+)/issues/(\d+)\b",
    re.I,
)
RX_GL_ISSUE_URL = re.compile(
    r"(?:https?://)[^\s]+/([^/\s]+)/([^/\s]+)/-/issues/(\d+)\b",
    re.I,
)
RX_SHORTHAND = re.compile(
    r"\b([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#(\d+)\b",
)
# implement/closes/fix(es)/resolves require '#': "implement 2-factor" is
# not issue #2. "issue N" also requires '#', because "the issue 2 weeks
# ago" is ordinary prose.
RX_TASK_HASH = re.compile(
    r"\b(?:implement(?:ing)?|closes|fix(?:es)?|resolves)\s+#(\d+)\b",
    re.I,
)
RX_ISSUE_WORD = re.compile(
    r"\bissues?\s+#(\d+)\b",
    re.I,
)
# A pull URL is not an issue, even though GitHub shares the number space.
RX_PULL_URL = re.compile(
    r"(?:https?://)?github\.com/[^/\s]+/[^/\s]+/pull/\d+\b",
    re.I,
)

RX_HEREDOC = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?([^\n]*)\n"
    r".*?\n[ \t]*\1\b",
    re.DOTALL,
)

# Command-position opener. Narrower than a full shell parser: omits `(` / `{`
# so a parenthetical aside inside prose cannot discharge the guard. Same
# trade-off as warn-pr-create-without-dupe-check.py's RX_DISCHARGE.
CMD_PREFIX = r"(?:^|[;&|\n])\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"

RX_FETCH_EXTRA = re.compile(
    CMD_PREFIX + r"git\s+(?:fetch|pull|ls-remote)\b",
    re.MULTILINE,
)

RX_HEADER_CLOSED = re.compile(r"^state:\s*closed\b", re.I | re.M)
# `glab issue view`'s TTY-rendered summary line leads with the state word
# followed by a bullet rather than a `state:` key ("closed • closed by
# ..."); a piped/non-TTY capture can still carry this shape depending on
# glab's renderer. Matched separately from RX_HEADER_CLOSED so the `gh`
# key-value format is not loosened.
RX_TTY_STATE_CLOSED = re.compile(r"^\s*closed\b\s*[•·]", re.I | re.M)

# Fallback stems if tool-mappings.yml cannot be read. Tests that care about
# the mapping file load it directly; these keep the hook failing open rather
# than silent-forever when the file is absent.
FALLBACK_VIEW_CLI = "gh issue view"
FALLBACK_VIEW_MCP = "mcp__github__issue_read"
FALLBACK_FETCH_CLI = "git fetch"

NOTE_MISSING = """\
Issue-driven edit without a fresh state check for {label}.

Confirm both of these AFTER the request that named the issue, before the
first source/config edit:

  1. issue state (VIEW_ISSUE): `gh issue view {number}` or the mapped
     GitHub MCP tool (`{view_mcp}`), or `glab issue view {number}`
  2. remote/default-branch (FETCH): `git fetch origin` or `git ls-remote`

{detail}
A session that implements from a stale checkout cannot see that the issue
already closed --- measured on ucdavis/rampp#140 (2026-08-26). If you have
already checked another way, carry on --- this is a reminder, not a refusal.
"""

NOTE_CLOSED = """\
Issue {label} appears CLOSED in the latest view in this session.

Stand it down rather than implementing from a stale checkout. If `main`
already satisfies it, report that and stop. If you are deliberately
reopening, say so and continue --- this is a reminder, not a refusal.

Measured on ucdavis/rampp#140 (2026-08-26): implementation began from a
July 19 checkout after the issue and its PR had merged on July 22.
"""

SYS_MISSING = (
    "Issue-driven edit of {label} with no fresh issue-state and/or "
    "remote default-branch check after the request that named it."
)
SYS_STALE = (
    "Issue-driven edit of {label}: the issue-state/remote checks in this "
    "session predate the request that named it."
)
SYS_CLOSED = (
    "Issue {label} appears CLOSED in the latest view; stand it down "
    "rather than implementing from a stale checkout."
)


@functools.lru_cache(maxsize=512)
def strip_heredocs(command):
    """Remove heredoc BODIES, keeping the rest of the opener line.

    Memoized because both `command_views_issue` and `command_fetches_remote`
    call it on the same command, so every Bash entry in the transcript was
    stripped twice. The hook runs on every Write/Edit/NotebookEdit
    (ai-config#2390), so halving the work is worth a cache.

    An early exit from `evaluate`'s loop once `view_after` and `fetch_after`
    are both set would be the larger win and is NOT safe: that same loop
    collects `view_results`, and `closed_after` reads the result of the LAST
    after-view, which arrives in a later entry than the tool_use that set the
    flag. Breaking would drop it and lose the closed-issue case.
    ai-config#2536 carries the remaining bound, on RX_HEREDOC itself.
    """
    return RX_HEREDOC.sub(lambda m: m.group(2), command)


def _mapping_block(text, op_id):
    matched = re.search(
        rf"(?ms)^  - id: {re.escape(op_id)}\n(.*?)(?=^  - id: |\Z)",
        text,
    )
    return matched.group(1) if matched else ""


def _mapping_field(block, key):
    matched = re.search(rf"(?m)^    {re.escape(key)}:\s*(.+)$", block)
    return matched.group(1).strip() if matched else ""


def _cli_prefix(cli):
    cleaned = re.sub(r"""['"]<[^>]+>['"]""", "", cli)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return " ".join(cleaned.split())


def _mcp_name(field):
    field = field.strip()
    if not field or field.startswith("("):
        return ""
    return re.split(r"[\s(]", field, 1)[0]


def load_mapping_stems(path=None):
    """Return {view_cli, view_mcp, fetch_cli} from tool-mappings.yml.

    Fails open to fallbacks when the file is missing or unparseable, so a
    hook that cannot see the registry still recognises the documented CLI
    spellings rather than going silent on every session.
    """
    stems = {
        "view_cli": FALLBACK_VIEW_CLI,
        "view_mcp": FALLBACK_VIEW_MCP,
        "fetch_cli": FALLBACK_FETCH_CLI,
    }
    target = path if path is not None else MAPPINGS_PATH
    try:
        with open(target, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return stems
    view_block = _mapping_block(text, "VIEW_ISSUE")
    fetch_block = _mapping_block(text, "FETCH")
    view_cli = _cli_prefix(_mapping_field(view_block, "cli"))
    view_mcp = _mcp_name(_mapping_field(view_block, "github_mcp"))
    fetch_cli = _cli_prefix(_mapping_field(fetch_block, "cli"))
    if view_cli:
        stems["view_cli"] = view_cli
    if view_mcp:
        stems["view_mcp"] = view_mcp
    if fetch_cli:
        # `git fetch origin` is the mapping; `git fetch` still counts.
        toks = fetch_cli.split()
        stems["fetch_cli"] = " ".join(toks[:2]) if len(toks) >= 2 else fetch_cli
    return stems


# A later user message retargets only with these forms. Incidental
# `owner/repo#N` citations (how recurrences are named) must not steal
# the issue the session is already implementing.
RETARGET_FORGES = frozenset({"github", "gitlab", "task"})


def find_issue_ref(text):
    """Return the primary forge-issue ref in user prose, or None.

    Pull URLs are ignored. The first GitHub/GitLab issue URL wins, then
    implement/closes/fix(es)/resolves + `#N`, then `issue #N`, then
    `owner/repo#N`.
    """
    if not text or not isinstance(text, str):
        return None
    # Drop pull URLs so a PR-only request cannot arm this guard via a
    # coincidental later owner/repo#N in the same blob.
    stripped = RX_PULL_URL.sub("", text)
    matched = RX_GH_ISSUE_URL.search(stripped)
    if matched:
        return {
            "owner": matched.group(1),
            "repo": matched.group(2),
            "number": matched.group(3),
            "forge": "github",
        }
    matched = RX_GL_ISSUE_URL.search(stripped)
    if matched:
        return {
            "owner": matched.group(1),
            "repo": matched.group(2),
            "number": matched.group(3),
            "forge": "gitlab",
        }
    matched = RX_TASK_HASH.search(stripped)
    if matched:
        return {
            "owner": "",
            "repo": "",
            "number": matched.group(1),
            "forge": "task",
        }
    matched = RX_ISSUE_WORD.search(stripped)
    if matched:
        number = matched.group(1)
        return {
            "owner": "",
            "repo": "",
            "number": number,
            "forge": "issue-word",
        }
    matched = RX_SHORTHAND.search(stripped)
    if matched:
        return {
            "owner": matched.group(1),
            "repo": matched.group(2),
            "number": matched.group(3),
            "forge": "shorthand",
        }
    return None


def same_issue(left, right):
    """True when two refs are the same issue number, and owners agree if both named."""
    if left["number"] != right["number"]:
        return False
    if left.get("owner") and right.get("owner") and left.get("repo") and right.get("repo"):
        return (
            left["owner"].lower() == right["owner"].lower()
            and left["repo"].lower() == right["repo"].lower()
        )
    return True


def issue_label(issue):
    if issue.get("owner") and issue.get("repo"):
        return f"{issue['owner']}/{issue['repo']}#{issue['number']}"
    return f"#{issue['number']}"


def _content_blocks(entry):
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else entry.get("content")
    blocks = []
    if isinstance(content, str):
        blocks.append({"type": "text", "text": content})
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                blocks.append(block)
            elif isinstance(block, str):
                blocks.append({"type": "text", "text": block})
    if "tool_calls" in entry and isinstance(entry["tool_calls"], list):
        for tc in entry["tool_calls"]:
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
    return blocks


def is_user_prose(entry):
    kind = entry.get("type") or entry.get("role") or entry.get("source")
    if kind not in ("user", "USER_EXPLICIT", "USER_INPUT"):
        return False
    blocks = _content_blocks(entry)
    if not blocks:
        return False
    if any(block.get("type") == "tool_result" for block in blocks):
        return False
    return any(
        block.get("type") == "text" and isinstance(block.get("text"), str)
        for block in blocks
    )


def user_text(entry):
    parts = []
    for block in _content_blocks(entry):
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts)


def _stem_regex(stem):
    return r"\s+".join(re.escape(tok) for tok in stem.split())


def command_views_issue(command, issue, view_cli):
    """True when `command` views `issue` at a command position.

    The number checked is the CLI's own positional argument --- the first
    token after the stem --- not any number occurring later on the line.
    Both `gh issue view` and `glab issue view`/`show` take the issue number
    (or a URL naming it) as their first positional argument with no flags
    in between, so requiring the target number to appear in that first
    token (rather than `[^\\n]*` anywhere on the line) still discharges
    every documented invocation while refusing a line whose target number
    only appears in a flag, a trailing comment, or a downstream pipe stage
    (e.g. `gh issue view 99  # ... 2282`, `... | grep 2282`,
    `gh issue view 99 -R owner/repo-2282`).
    """
    if not isinstance(command, str) or not command.strip():
        return False
    text = strip_heredocs(command)
    number = re.escape(issue["number"])
    # "show" is a documented alias for "view" in gitlab-org/cli, so a live
    # `glab issue show N` must discharge exactly like `glab issue view N`.
    stems = [view_cli, "glab issue view", "glab issue show"]
    for stem in stems:
        if not stem:
            continue
        pattern = re.compile(
            CMD_PREFIX + _stem_regex(stem) + r"\s+(\S+)",
            re.MULTILINE,
        )
        for match in pattern.finditer(text):
            arg = match.group(1).strip("'\"")
            if re.search(rf"\b{number}\b", arg):
                return True
    rest_issue = re.compile(
        CMD_PREFIX
        + rf"gh\s+api\b[^\n]*/issues/{number}(?!\d)(?!/)",
        re.MULTILINE,
    )
    return bool(rest_issue.search(text))


def command_fetches_remote(command, fetch_cli):
    """True when `command` reads the remote at a command position."""
    if not isinstance(command, str) or not command.strip():
        return False
    text = strip_heredocs(command)
    if RX_FETCH_EXTRA.search(text):
        return True
    if fetch_cli and fetch_cli not in ("git fetch", "git pull", "git ls-remote"):
        pattern = re.compile(
            CMD_PREFIX + _stem_regex(fetch_cli) + r"\b",
            re.MULTILINE,
        )
        return bool(pattern.search(text))
    return False


def mcp_views_issue(name, tool_input, issue, view_mcp):
    """True when `name`/`tool_input` is a VIEW_ISSUE call for `issue`.

    A `method` field of `get_comments`, `get_labels`, `get_sub_issues`, or
    `get_parent` reads the issue but is not VIEW_ISSUE (tool-mappings.yml
    maps `get_comments` to the separate READ_ISSUE_COMMENTS op), and its
    result carries no top-level `state`, so a closed issue would not be
    classified as closed. Only `method: get` (or a tool with no `method`
    field at all) counts.
    """
    if not isinstance(name, str) or not name:
        return False
    mcp = view_mcp or FALLBACK_VIEW_MCP
    if name != mcp and not name.endswith("issue_read"):
        return False
    if isinstance(tool_input, dict):
        method = tool_input.get("method")
        if isinstance(method, str) and method != "get":
            return False
    blob = ""
    if isinstance(tool_input, dict):
        try:
            blob = json.dumps(tool_input)
        except (TypeError, ValueError):
            blob = str(tool_input)
    elif isinstance(tool_input, str):
        blob = tool_input
    number = re.escape(issue["number"])
    if re.search(rf"/issues/{number}\b", blob):
        return True
    # No whole-blob fallback beyond these two shapes: an issue_read of a
    # DIFFERENT issue whose tool_input happens to mention the target
    # number in an unrelated field (a title, a body excerpt, a comment)
    # must not discharge. An /issues/N URL path and an
    # issue_number/issueNumber/number key are the only documented
    # VIEW_ISSUE argument shapes; this warn-only hook's stated bias is
    # toward warning, never toward silent discharge (see module
    # docstring, WHY WARN RATHER THAN BLOCK).
    return bool(re.search(
        rf'"(?:issue_number|issueNumber|number)"\s*:\s*{number}\b',
        blob,
    ))


def _tool_result_text(entry):
    for block in _content_blocks(entry):
        if block.get("type") != "tool_result":
            continue
        content = block.get("content")
        parts = []
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
        yield block.get("tool_use_id"), "\n".join(parts)


def _tool_uses(entry):
    for block in _content_blocks(entry):
        if block.get("type") != "tool_use":
            continue
        yield block


def load_entries(transcript_path):
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    entries = []
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return None
    return entries


def result_is_closed(text):
    """True when this tool_result is the issue's own state, and it is closed.

    Parses JSON when the whole result is an object, accepts a bare
    `CLOSED` from `gh issue view --jq .state`, and otherwise reads only
    the metadata header (before a `--` or blank-line body). A substring
    `"state": "closed"` inside an OPEN issue's body must not count.
    """
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip()
    bare = stripped.strip("\"'")
    if bare.lower() == "closed":
        return True
    try:
        data = json.loads(stripped)
    except (ValueError, TypeError):
        data = None
    if isinstance(data, dict):
        return str(data.get("state") or "").lower() == "closed"
    if isinstance(data, str):
        return data.lower() == "closed"
    header = stripped
    for sep in ("\n--\n", "\n\n"):
        if sep in stripped:
            header = stripped.split(sep, 1)[0]
            break
    return bool(
        RX_HEADER_CLOSED.search(header) or RX_TTY_STATE_CLOSED.search(header)
    )


def evaluate(entries, stems=None):
    """Return a verdict dict or None (silent).

    None means fail-open or nothing to say. A dict has `kind` in
    missing / stale / closed.
    """
    if not entries:
        return None
    stems = stems or load_mapping_stems()
    naming_idx = None
    issue = None
    for idx, entry in enumerate(entries):
        if not is_user_prose(entry):
            continue
        found = find_issue_ref(user_text(entry))
        if not found:
            continue
        if issue is None or (
            found.get("forge") in RETARGET_FORGES
            and not same_issue(found, issue)
        ):
            naming_idx = idx
            issue = found
    if issue is None:
        return None

    view_before = False
    fetch_before = False
    view_after = False
    fetch_after = False
    views_after_ids = []
    view_results = {}

    def note_view(where_after, tool_id=None):
        nonlocal view_before, view_after
        if where_after:
            view_after = True
            if tool_id:
                views_after_ids.append(tool_id)
        else:
            view_before = True

    def note_fetch(where_after):
        nonlocal fetch_before, fetch_after
        if where_after:
            fetch_after = True
        else:
            fetch_before = True

    for idx, entry in enumerate(entries):
        after = naming_idx is not None and idx > naming_idx
        for block in _tool_uses(entry):
            name = block.get("name") or ""
            inp = block.get("input") if isinstance(block.get("input"), dict) else {}
            command = (
                inp.get("command")
                or inp.get("cmd")
                or inp.get("CommandLine")
                or ""
            )
            if isinstance(command, str) and command_views_issue(
                command, issue, stems["view_cli"]
            ):
                note_view(after, block.get("id"))
            elif mcp_views_issue(name, inp, issue, stems["view_mcp"]):
                note_view(after, block.get("id"))
            if isinstance(command, str) and command_fetches_remote(
                command, stems["fetch_cli"]
            ):
                note_fetch(after)
        for tool_use_id, text in _tool_result_text(entry):
            if tool_use_id:
                view_results[tool_use_id] = text

    closed_after = False
    if views_after_ids:
        last_id = views_after_ids[-1]
        if last_id in view_results:
            closed_after = result_is_closed(view_results[last_id])

    if closed_after:
        kind = "closed"
    elif view_after and fetch_after:
        return None
    elif not view_after and not fetch_after and (view_before or fetch_before):
        kind = "stale"
    else:
        kind = "missing"
    return {
        "kind": kind,
        "issue": issue,
        "view_after": view_after,
        "fetch_after": fetch_after,
        "view_before": view_before,
        "fetch_before": fetch_before,
        "stems": stems,
    }


def _detail(verdict):
    bits = []
    if not verdict["view_after"]:
        where = "stale (predates the request)" if verdict["view_before"] else "missing"
        bits.append(f"  - issue-state check: {where}")
    if not verdict["fetch_after"]:
        where = "stale (predates the request)" if verdict["fetch_before"] else "missing"
        bits.append(f"  - remote/default-branch check: {where}")
    return "\n".join(bits) + ("\n" if bits else "")


def warning_payload(verdict):
    issue = verdict["issue"]
    label = issue_label(issue)
    stems = verdict["stems"]
    kind = verdict["kind"]
    if kind == "closed":
        additional = NOTE_CLOSED.format(label=label)
        system = SYS_CLOSED.format(label=label)
    elif kind == "stale":
        additional = NOTE_MISSING.format(
            label=label,
            number=issue["number"],
            view_mcp=stems["view_mcp"],
            detail=_detail(verdict),
        )
        system = SYS_STALE.format(label=label)
    else:
        additional = NOTE_MISSING.format(
            label=label,
            number=issue["number"],
            view_mcp=stems["view_mcp"],
            detail=_detail(verdict),
        )
    res = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": additional,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        res["systemMessage"] = system
    return res


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        tool_name = payload.get("tool_name") or ""
        if tool_name not in WRITE_TOOLS:
            return 0
        entries = load_entries(payload.get("transcript_path") or "")
        if entries is None:
            return 0
        verdict = evaluate(entries)
        if not verdict:
            return 0
        print(json.dumps(warning_payload(verdict)))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
