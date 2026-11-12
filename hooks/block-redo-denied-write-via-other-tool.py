#!/usr/bin/env python3
"""PreToolUse deny: do not redo a classifier-denied GitHub write through another tool (ai-config#5121).

2026-11-08: a cloud thread's `gh api` POST and PATCH closing gha#1631 and
gha#1635 were denied by the auto-mode permission classifier. The same writes
then succeeded through `mcp__github__add_issue_comment` and
`mcp__github__issue_write`. `remind-retry-before-declaring-blocked.py` keys on
the identical command and only reminds, so a different tool reaching the same
target was invisible to it, and Ezra's standing rule (ai-config#4960: report a
classifier denial, do not push past it) was broken by the tool switch alone.

WHAT IT DOES
------------
Matched on `Bash` and `mcp__github__.*`. It reads the session transcript for
calls the classifier denied (the sibling's own `is_classifier_denial`),
normalizes each to (repo, issue-or-PR number, verb), and DENIES a later write
with the same number and verb, through any tool, while that denial is live.
The tool-independent key is the point: `gh api -X PATCH .../issues/1631 -f
state=closed`, `gh issue close 1631` and `issue_write(method=update,
state=closed)` are all (repo, 1631, close).

Verbs: comment, close, reopen, edit, merge, review. A comment and a close are
different actions, so a denied close does not block a comment.

A denial is live until one of two things:

  * the permission layer later let a call with the same target and verb
    through (the goal was reached, so a further write is a new action), or
  * a typed message from the user, after the denial, that names the number and
    carries a go-ahead word (retry, go ahead, proceed, do it, redo, try again,
    yes, approve, allow, ok to). The number must be named, so "yes" alone does
    not release every standing denial, and a negated clause ("don't retry
    1631") does not release it. Only a user-role text block counts: not a
    tool result, not the assistant's words, not a system reminder, and not a
    relayed message from another agent. A `<cited author="user">` entry in a
    relay counts, because the server copies the user's words into it.

WHY THIS DENIES WHERE THE SIBLING INJECTS
-----------------------------------------
The sibling is deliberately inject-only: reporting a denial is right, and only
the premature claim of permanence is wrong. A tool switch is different. It is
not a report and not a claim, it is the act the rule forbids, and the user
cannot see it happen before it lands. A deny is the only thing that stops it.
The reminder still runs for every denied command; this hook adds the
cross-tool block for GitHub writes.

WHAT IT DOES NOT DO
-------------------
Where the number cannot be parsed (a GraphQL mutation, a shell variable in the
URL, a `gh` call with no number) the call is not tied to any target, so
nothing is recorded and nothing is denied; the reminder is the fallback.
Where the repository is unknown on either side (`gh issue close 1631` with no
`-R`), the repository is treated as a wildcard, so the call still matches on
number and verb. That errs toward blocking, and a typed go-ahead releases it.

A user's own rejection, a permission-rule refusal and a hook refusal are not
classifier denials and record nothing, the sibling's reasoning exactly: they
are decisions to respect or deterministic answers, not samples.

Fails OPEN and SILENT on any parse trouble, a missing transcript or a missing
helper library. A deny that fired on a broken parse would be switched off.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))


_LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from sibling import load_sibling
except ImportError as _exc:
    print(f"{os.path.basename(__file__)}: cannot load scripts/lib/sibling.py "
          f"({_exc}); running without its sibling hooks", file=sys.stderr)
    load_sibling = None


def _load(name, filename):
    """Import a hyphenated sibling module, or None (scripts/lib/sibling.py)."""
    return load_sibling(__file__, filename, name) if load_sibling else None


_REMIND = _load("_sib_retry", "remind-retry-before-declaring-blocked.py")
_MERGE = _load("_sib_merge", "block-merge-without-clean-checker.py")
if _REMIND is None or _MERGE is None:
    print(f"{os.path.basename(__file__)}: a sibling hook is missing; not gating",
          file=sys.stderr)
try:
    from shellcmd import simple_commands, strip_env, shell_c_expansions
except Exception as _exc:
    print(f"block-redo-denied-write-via-other-tool: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); not gating", file=sys.stderr)
    simple_commands = strip_env = shell_c_expansions = None

SHELL_TOOLS = frozenset({"Bash", "bash", "PowerShell", "run_command"})

RX_ENDPOINT = re.compile(
    r"(?:^|/)repos/([^/\s]+/[^/\s]+)/(issues|pulls)/(\d+)"
    r"(/comments|/merge|/reviews)?/?(?:[?#].*)?$")
RX_URL_NUM = re.compile(r"/(?:pull|issues)/(\d+)(?:[/?#].*)?$")
RX_STATE = re.compile(r"""["']?state["']?\s*[:=]\s*["']?(closed|open)\b""")

GH_VERBS = {"close": "close", "comment": "comment", "reopen": "reopen",
            "edit": "edit", "merge": "merge", "review": "review"}

# tool -> (verb or None for "decide from input", number keys)
MCP_VERBS = {
    "mcp__github__add_issue_comment": "comment",
    "mcp__github__add_reply_to_pull_request_comment": "comment",
    "mcp__github__merge_pull_request": "merge",
    "mcp__github__enable_pr_auto_merge": "merge",
    "mcp__github__pull_request_review_write": "review",
    "mcp__github__issue_write": None,
    "mcp__github__update_pull_request": None,
}

RX_GO = re.compile(
    r"\b(?:retry|re-?run|go\s+ahead|proceed|do\s+it|redo|try\s+again|"
    r"approved?|allow(?:ed)?|ok(?:ay)?\s+to|yes)\b", re.IGNORECASE)
RX_NEGATED = re.compile(
    r"\b(?:don'?t|do\s+not|never|not|won'?t|shouldn'?t|wouldn'?t|can'?t|"
    r"cannot|couldn'?t|isn'?t|aren'?t|without|stop)\b", re.IGNORECASE)
RX_CLAUSE_START = re.compile(r"[.!?;\n]")
RX_STRIP = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<note>.*?</note>"
    r"|<cited\b[^>]*author=\"(?!user\")[^\"]*\"[^>]*>.*?</cited>"
    r"|<message\b[^>]*trust=\"relay\"[^>]*>.*?</message>",
    re.IGNORECASE | re.DOTALL)

DENY_TEXT = (
    "The auto-mode classifier already denied a `{verb}` of {target} in this "
    "session, through {was}. This call, through `{tool}`, redoes the same "
    "action by another route. Ezra's standing rule is to report a classifier "
    "denial and ask, not to push past it by switching tools (ai-config#5121, "
    "#4960). Tell the user what was denied and ask for a go-ahead. The deny "
    "lifts when the user types a message that names {num} with a go-ahead "
    "word, such as \"retry {num}\"; a relayed description from another agent "
    "does not count.")


def _num(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _repo_of(tool_input):
    owner, name = tool_input.get("owner"), tool_input.get("repo")
    return f"{owner}/{name}".lower() if owner and name else None


def _mcp_targets(tool, tool_input):
    if tool not in MCP_VERBS:
        return []
    num = _num(tool_input.get("issue_number") or tool_input.get("pullNumber")
               or tool_input.get("pull_number"))
    if num is None:
        return []
    verb = MCP_VERBS[tool]
    if verb is None:
        state = str(tool_input.get("state") or "").lower()
        if tool == "mcp__github__issue_write" and \
                tool_input.get("method") != "update":
            return []
        verb = {"closed": "close", "open": "reopen"}.get(state, "edit")
    return [(_repo_of(tool_input), num, verb)]


def _flag(args, names):
    return _MERGE._flag_value(args, names)


def _gh_api(args):
    method = None
    for i, tok in enumerate(args):
        if tok in ("-X", "--method", "--request") and i + 1 < len(args):
            method = args[i + 1].upper()
        elif tok.startswith(("--method=", "--request=")):
            method = tok.split("=", 1)[1].upper()
        elif tok.startswith("-X") and len(tok) > 2:
            method = tok[2:].upper()
    for tok in args:
        m = RX_ENDPOINT.search(tok.strip("'\""))
        if not m:
            continue
        repo, num, tail = m.group(1).lower(), int(m.group(3)), m.group(4)
        if repo.startswith("{") or "{" in repo:
            repo = None
        if method not in ("POST", "PATCH", "PUT", "DELETE"):
            fields = any(t in ("-f", "-F", "--field", "--raw-field", "--input")
                         for t in args)
            if not fields:
                return []
            method = "POST"
        if tail == "/merge":
            return [(repo, num, "merge")] if method == "PUT" else []
        if tail == "/reviews":
            return [(repo, num, "review")]
        if tail == "/comments":
            return [(repo, num, "comment")] if method == "POST" else []
        state = RX_STATE.search(" ".join(args))
        verb = ({"closed": "close", "open": "reopen"}[state.group(1)]
                if state else "edit")
        return [(repo, num, verb)] if method in ("PATCH", "POST") else []
    return []


def _shell_targets(tool_input):
    command = _MERGE._shell_command(tool_input)
    if command is None:
        return []
    out = []
    for line in shell_c_expansions(command):
        for argv in simple_commands(line) or []:
            rest = strip_env(argv)[1]
            if not rest or _MERGE._basename(rest[0]) != "gh":
                continue
            i = 1
            while i < len(rest) and rest[i].startswith("-"):
                i += 2 if rest[i] in ("-R", "--repo") else 1
            if rest[i:i + 1] == ["api"]:
                out.extend(_gh_api(rest[i + 1:]))
                continue
            if rest[i:i + 1] not in (["issue"], ["pr"]) or i + 2 > len(rest):
                continue
            verb = GH_VERBS.get(rest[i + 1])
            if not verb:
                continue
            args = rest[i + 2:]
            repo = _MERGE._known_repo(
                _flag(args, ("-R", "--repo")) or _flag(rest[1:i], ("-R", "--repo")))
            num = _MERGE._gh_pr_number(args)
            if num is None:
                for tok in args:
                    m = RX_URL_NUM.search(tok)
                    if m:
                        num = int(m.group(1))
            if num is None:
                continue
            repo = repo.lower() if repo else None
            out.append((repo, num, verb))
            if verb == "close" and any(
                    t in ("-c", "--comment") or t.startswith("--comment=")
                    for t in args):
                out.append((repo, num, "comment"))
    return out


def targets(tool, tool_input):
    """[(repo|None, number, verb)] for every write this call performs."""
    if not isinstance(tool_input, dict):
        return []
    if tool in SHELL_TOOLS:
        if simple_commands is None or _MERGE is None:
            return []
        return _shell_targets(tool_input)
    return _mcp_targets(tool, tool_input)


def _same(a, b):
    """Same number and verb; repo compared only when both are known."""
    if a[1] != b[1] or a[2] != b[2]:
        return False
    return a[0] is None or b[0] is None or a[0] == b[0]


def _text_of(block):
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(
            c.get("text") or "" for c in content if isinstance(c, dict))
    return content if isinstance(content, str) else ""


def scan(path):
    """Return (denials, allowed, goahead).

    denials   [(index, tool, target)] every classifier-denied write target
    allowed   [(index, target)] every write target the layer let through
    goahead   [(index, text)] every user-role text block, stripped
    """
    uses, denials, allowed, goahead = {}, [], [], []
    for i, rec in enumerate(_MERGE._records(path)):
        if not isinstance(rec, dict) or rec.get("isSidechain"):
            continue
        role = rec.get("type") or (rec.get("message") or {}).get("role")
        content = (rec.get("message") or {}).get("content", rec.get("content"))
        if role in ("user", "USER_INPUT") and isinstance(content, str):
            goahead.append((i, RX_STRIP.sub(" ", content)))
            continue
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            kind = b.get("type")
            if kind == "tool_use":
                name = b.get("name") or ""
                hits = targets(name, b.get("input") or {})
                if hits:
                    uses[b.get("id")] = (i, name, hits)
            elif kind == "tool_result":
                seen = uses.get(b.get("tool_use_id"))
                if not seen:
                    continue
                at, name, hits = seen
                if _REMIND.is_classifier_denial(rec, b):
                    denials.extend((at, name, t) for t in hits)
                elif _REMIND.permitted(rec, b):
                    allowed.extend((at, t) for t in hits)
            elif kind == "text" and role in ("user", "USER_INPUT"):
                goahead.append((i, RX_STRIP.sub(" ", b.get("text") or "")))
    return denials, allowed, goahead


def released(num, after, goahead):
    """True when a user text after index *after* names *num* with a go-ahead."""
    rx_num = re.compile(rf"(?<!\d){num}(?!\d)")
    for at, text in goahead:
        if at <= after or not rx_num.search(text):
            continue
        for m in RX_GO.finditer(text):
            before = text[:m.start()]
            starts = [s.end() for s in RX_CLAUSE_START.finditer(before)]
            clause = before[starts[-1]:] if starts else before
            if not RX_NEGATED.search(clause):
                return True
    return False


def live_denial(target, denials, allowed, goahead):
    """The (index, tool, target) denial that still blocks *target*, else None."""
    for at, tool, denied in sorted(denials, key=lambda d: d[0]):
        if not _same(target, denied):
            continue
        if any(i > at and _same(target, t) for i, t in allowed):
            continue
        if released(denied[1], at, goahead):
            continue
        return at, tool, denied
    return None


def deny(reason):
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}


def main() -> int:
    if _REMIND is None or _MERGE is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload.get("toolInput")
    try:
        mine = targets(tool, tool_input)
    except Exception:
        return 0
    if not mine:
        return 0
    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    try:
        denials, allowed, goahead = scan(path)
    except Exception:
        return 0
    for target in mine:
        hit = live_denial(target, denials, allowed, goahead)
        if hit:
            _at, was, denied = hit
            repo = denied[0] or target[0]
            name = f"{repo}#{denied[1]}" if repo else f"#{denied[1]}"
            print(json.dumps(deny(DENY_TEXT.format(
                verb=denied[2], target=name, was=f"`{was}`", tool=tool,
                num=f"#{denied[1]}"))))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
