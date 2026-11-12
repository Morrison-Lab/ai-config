#!/usr/bin/env python3
"""PreToolUse guard: no class announcement without the user's approval.

Ezra, 2026-10-27, said twice: never post a class announcement without his review and approval of its exact text
(ai-config#4780). Denies the CLI, `is_announcement`, a network write naming a topic and an MCP announcement write
unless the user's last message is only "post the announcement" ("yes, post it", ...); one write each. Known limits: #5453.
"""
import io
import json
import os
import re
import shlex
import sys
import tokenize

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"))
    from transcript_meta import is_real_user_turn, strip_injected_text
except Exception:  # detection still runs; a detected write is then denied
    is_real_user_turn = None

CLI = re.compile(r"\bcanvas\s+announcements?\s+(create|post|update|edit|publish)\b", re.I)
CODE = re.compile(r"\b(python3?|node|ruby|perl|Rscript)\b\s+(-c|-e|-\s)|<<")
QUOTED = re.compile(r"'[^']*'|\"(\\.|[^\"\\$`])*\"")  # a double-quoted span with $ or ` stays
TOPIC = re.compile(r"discussion(_|%5f)?topic|announcement", re.I)
ANNOUNCE = re.compile(r"is_announcement|get_announcements.*\.(edit|update)\(", re.I | re.S)
NET = re.compile(r"\b(curl|wget|requests(\.\w+|\s+import)|urllib\.request|httpx\.\w+|httr::\w+|http\.client|aiohttp|canvasapi|canvas\s+api|Invoke-\w+)\b|"
                 r"(https?://|/api/v1/).*(['\"](?i:put|post)['\"]|\.(put|post)\()", re.I | re.S)
WRITE = re.compile(r"(-\w*X|--request|-Method)[\s=]*[\"']?(?i:POST|PUT)|(^|\s)(-[a-zA-Z]*[dFT]|--data|--form|--json|--upload-file)")
SAFE_FIRST = {"git", "gh", "grep", "egrep", "rg"}
COMPOUND = re.compile(r"[;&|`\n<>]|\$\(")
MCP_READ = re.compile(r"^(get|list|search|read|find|fetch|show|count)", re.I)
APPROVAL = re.compile(r"\s*((yes|ok|okay|approved|looks good|lgtm)[,.!]*\s*)?(please\s+)?(go ahead and\s+)?"
                      r"((post|publish)\s+(it|the announcement|this announcement|that announcement)"
                      r"|send\s+(the|this|that)\s+announcement)( (now|as written|please))*[ .!]*", re.I)  # matched against single-spaced words
TAG = re.compile(r"<(/?)([a-z][\w-]*)([^>]*)>", re.I)
ENVELOPE = {"wake", "project", "thread", "message", "relay", "cited", "note"}  # and every hyphenated tag


SCRIPT = re.compile(r"\b(?:python[\d.]*|Rscript|node|deno|bash|z?sh|ruby|perl|pwsh|source|uv run)\s+(?:-[^\smc]\S*\s+)*"
                    r"([\w./~-]+\.(?:py|R|r|js|mjs|ts|sh|rb|pl|ps1))\b")
LEAD = re.compile(r"[{!]|if|then|do|else|elif|while|until|time|exec|command|nohup|xargs|sudo|env|nice|timeout|"
                  r"stdbuf|ionice|strace|watch|-\S*|\d\S*|\w+=\S*")  # words before the command a segment runs
INTERP = re.compile(r"(python[\d.]*|Rscript|node|deno|bash|z?sh|ruby|perl|pwsh|source|uv|\.)$")
EXT = re.compile(r"[\w./~-]+\.(py|R|r|js|mjs|ts|sh|rb|pl|ps1)$")
CODE_WRITE = re.compile(r"\b(post|put|edit|update|PUT|POST)\(|create_discussion_topic|['\"](POST|PUT|post|put)['\"]|"
                        r"-X\s*(POST|PUT)|\b(Request|urlopen)\([^)]*\bdata\s*=")
SELF = (os.path.basename(__file__), "test-no-unapproved-announcement.py")  # this hook and its tests
COPY = ((r"^def is_announcement_write\(", r"^def main\("),  # lines every version of the hook, or of its tests, has
        (r"^SUBJECT\b[^=\n]*= sys\.argv\[1\]", r"^def run\(tool, inp"))
HEREDOC = re.compile(r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", re.S)  # its body is text
PY_OPT = re.compile(r"-[bBdEhiIOPqsSuvVx]*([cm])(.*)$")  # python's flags, then -c or -m and any attached value
UV_VALUE = ("--with", "--python", "-p", "--from", "--env-file", "--config")  # uv or deno options that take a value


def segments(cmd):
    """The command's simple commands as word lists: split on unquoted operators, with quoted text one word."""
    try:
        lex = shlex.shlex(HEREDOC.sub(r"\1", cmd).replace("\n", ";"), posix=True, punctuation_chars=";&|()")
        lex.whitespace_split, lex.commenters = True, ""
        tokens = list(lex)
    except ValueError:  # an unclosed quote: split on whitespace
        tokens = re.sub(r"([;&|()\n])", r" \1 ", cmd).split()
    words = []
    for t in tokens:
        if set(t) <= set(";&|()\n"):
            yield words
            words = []
        elif t.strip("`").lstrip("<!"):
            words.append(t.strip("`").lstrip("<!"))
    yield words


def inline_code(interp, x):
    """An option after which the interpreter runs code given inline, or a module, rather than a script file."""
    if interp.startswith("python"):
        return PY_OPT.match(x)
    return re.match(r"-[a-zA-Z]{0,3}[ceE]$|-p$|--(eval|print)\b|-Command$", x)  # perl -ne, Rscript -e


def script_names(cmd):
    """Script files the command runs: SCRIPT's matches, plus words the segment tokenizer finds."""
    yield from SCRIPT.findall(cmd)
    for words in segments(cmd):
        run = next((w for w in words if not LEAD.fullmatch(w)), "")
        if EXT.match(run):  # a script run by its path, after any keyword, wrapper or assignment
            yield run
        for i, w in enumerate(words):
            interp = w.rsplit("/", 1)[-1]
            if not INTERP.match(interp) or w in (".", "source") and i:  # `.` runs a file only first
                continue
            rest = words[i + 1:]
            if w.endswith(("uv", "deno")):  # `uv run x.py`: the word after `run` and its options, not a tool's argument
                rest = rest[1:] if rest[:1] == ["run"] else rest
                while rest and rest[0].startswith("-"):
                    rest = rest[2:] if rest[0] in UV_VALUE else rest[1:]
                rest = rest[:1]
            for j, x in enumerate(rest):  # the first script after the interpreter's options
                if re.match(r"(ba|z)?sh$", interp) and re.match(r"-[a-zA-Z]{0,3}c$", x):
                    yield from script_names(" ".join(rest[j + 1:j + 2]))  # `bash -c CODE`: the scripts CODE runs
                    break
                if inline_code(interp, x):
                    break
                if EXT.match(x):
                    yield x
                    break


def python_value(cmd, opt):
    """What `python` gets for `-c` or `-m` (opt "c" or "m"): after other options, in a cluster (-um), or attached (-mX)."""
    for words in segments(cmd):
        for i, w in enumerate(words):
            if not re.match(r"python[\d.]*$", w.rsplit("/", 1)[-1]):
                continue
            for j, x in enumerate(words[i + 1:], i + 1):
                hit = PY_OPT.match(x)
                if hit and hit[1] == opt and (hit[2] or j + 1 < len(words)):
                    yield hit[2] or words[j + 1]
                if hit or EXT.match(x):
                    break


def code_only(code):
    """Python code with its comments and string literals blanked.

    The hook and its tests hold write patterns only as literals; None when the code does not tokenize."""
    starts = [0]
    for line in io.StringIO(code).readlines():
        starts.append(starts[-1] + len(line))
    text = list(code)
    blank = {tokenize.COMMENT, tokenize.STRING} | {getattr(tokenize, f"{k}STRING_{p}", -1)
                                                   for k in "FT" for p in ("START", "MIDDLE", "END")}
    try:
        for t in tokenize.generate_tokens(io.StringIO(code).readline):
            if t.type in blank:
                a, b = starts[t.start[0] - 1] + t.start[1], starts[t.end[0] - 1] + t.end[1]
                text[a:b] = " " * (b - a)
    except (tokenize.TokenError, SyntaxError):
        return None
    return "".join(text)


def script_writes(cmd, cwd):
    """A script file the command runs makes a network topic write, or cannot be read (#5453)."""
    cds = [os.path.expanduser(d) for d in re.findall(r"\b(?:cd|pushd)\s+['\"]?([\w./~-]+)", cmd)]
    dirs = [cwd or "."] + [os.path.join(cwd or ".", d) for d in cds]
    code_args = " ".join(python_value(cmd, "c"))
    names = [n.split() for found in re.findall(r"\bimport\s+([\w., ]+)", code_args) for n in found.split(",")]
    modules = [n[0] for n in names if n] + re.findall(r"\bfrom\s+([\w.]+)", code_args)  # `import a, b as c`
    modules += [f"{a}.{b}" for a, b in re.findall(r"\bfrom\s+([\w.]+)\s+import\s+(\w+)", code_args)]
    modules += list(python_value(cmd, "m"))
    imported = {m.replace(".", "/") + ".py" for m in modules}  # a local module `-c` code loads or `-m` runs
    for name in [*script_names(cmd), *sorted(imported)]:
        paths = [p for p in (os.path.join(d, os.path.expanduser(name)) for d in dirs) if os.path.isfile(p)]
        try:
            with open(paths[-1], encoding="utf-8", errors="ignore") as fh:
                code = fh.read(1 << 20)
        except (IndexError, OSError):
            own = os.path.basename(name) in SELF  # this hook or its tests, run elsewhere
            if TOPIC.search(cmd) and name not in imported and not own:
                return True
            continue
        if any(all(re.search(p, code, re.M) for p in pair) for pair in COPY):  # a copy of this hook or its tests
            code = code_only(code) or code
        if (ANNOUNCE.search(code) or TOPIC.search(code)) and NET.search(code) and CODE_WRITE.search(code):
            return True
    return False


def is_announcement_write(tool, inp, cwd=""):
    if tool in ("Bash", "Monitor", "PowerShell"):
        cmd = inp.get("command") or ""
        first = (cmd.split() or [""])[0].rsplit("/", 1)[-1]
        bare = QUOTED.sub("", cmd)  # the command outside its quoted text
        plain = not COMPOUND.search(bare)
        if first in SAFE_FIRST and plain:  # one plain command
            return False
        if script_writes(cmd, cwd):
            return True
        net = NET.search(cmd) or first in ("http", "https", "xh")
        read = first == "curl" and not WRITE.search(cmd) and plain  # other reads deny: widening this failed open (#5453)
        cli = CLI.search(bare) or re.search(r"\b(ba|z)?sh\s+-c\b", cmd) and CLI.search(cmd)
        return bool(cli or ANNOUNCE.search(cmd) and (net or CODE.search(cmd))
                    or TOPIC.search(cmd) and net and not read)
    name = tool.lower()
    if not name.startswith("mcp__"):
        return False
    verb = name.split("__")[-1]
    if ("announc" in verb or "discussion_topic" in verb or "canvas" in name and (
            "discussion" in verb or "topic" in verb)) and not MCP_READ.search(verb):
        return True
    flat = json.dumps(inp).replace('\\"', '"')
    return bool(re.search(r"canvas|lms|instructure|http|\bapi_|\brequest\b", name.split("__")[1] + " " + verb)
                and TOPIC.search(flat) and re.search(r"is_announcement|\b(POST|PUT)\b|\"method\": \"(?i:post|put)\"", flat))


def user_words(text, top=True):
    """User text: untagged (if `top`), a principal wake message, or a relay's cited entry."""
    out, stack, pos = [], [], 0
    for m in TAG.finditer(text):
        if not re.search(r"[-_]", m.group(2)) and m.group(2).lower() not in ENVELOPE:
            continue  # the user's own markup, such as <b>, stays text
        path = [t for t, _ in stack]
        in_wake = (path[:1] == ["wake"] and path[-1:] == ["message"]
                   and set(path[1:-1]) <= {"project", "thread"})
        cited = path[-2:] == ["relay", "cited"] and path[:-2] in ([], ["coordinator-relay"])
        if (top and not stack) or stack and (in_wake or cited) and stack[-1][1]:
            out.append(text[pos:m.start()])
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if closing:
            while tag in [t for t, _ in stack] and stack.pop()[0] != tag:  # stray: ignored
                pass
        elif not attrs.rstrip().endswith("/"):
            ok = 'trust="principal"' in attrs if tag == "message" else 'author="user"' in attrs if tag == "cited" else True
            stack.append((tag, ok and (not stack or stack[-1][1])))
        pos = m.end()
    return [p for p in out + ([text[pos:]] if top and not stack else []) if p.strip()]


def _blocks(entry):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else entry.get("content")
    return content if isinstance(content, list) else [{"type": "text", "text": content or ""}]


def _user_text(entry):
    att = entry.get("attachment") or {}
    if att.get("type") == "queued_command" and att.get("commandMode") != "task-notification" \
            and (att.get("origin") or {}).get("kind") != "peer":
        return str(att.get("prompt") or ""), True
    if entry.get("type") != "user" or entry.get("promptSource") == "sdk":
        return None, False
    text = "\n".join(strip_injected_text(b.get("text") or "") for b in _blocks(entry) if b.get("type") == "text")
    real = bool(is_real_user_turn(entry)) or not entry.get("isMeta") and any(b.get("type") == "image" for b in _blocks(entry))
    return text if text.strip() or not real else "[a message with no text]", real


def verdict(path, tool, inp, cwd=""):
    if is_real_user_turn is None:
        return "scripts/lib/transcript_meta.py could not be loaded"
    try:
        with open(path, encoding="utf-8") as fh:
            entries = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError, TypeError):
        return "the transcript could not be read"
    answered = {b.get("tool_use_id") for e in entries for b in _blocks(e) if b.get("type") == "tool_result"}
    writes = []  # every write since the approval, failed ones included
    for entry in reversed(entries):
        text, top = _user_text(entry)
        words = "\n".join(user_words(text, top)) if text is not None else ""
        if words.strip():  # a harness note with no user words is skipped
            if not APPROVAL.fullmatch(" ".join(words.split())):
                return "the user's latest message is not only an approval of posting it"
            now = [w for w in writes if w[:2] == [tool, inp] and w[2] not in answered]
            if now:  # the call being judged, logged with no result yet
                writes.remove(now[0])
            return "an announcement was already posted after that approval" if writes else None
        if entry.get("type") == "assistant":
            writes += [[b.get("name"), b.get("input"), b.get("id")] for b in _blocks(entry) if b.get("type")
                       == "tool_use" and is_announcement_write(b.get("name") or "", b.get("input") or {}, cwd)]
    return "no message from the user approves posting it"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool, inp = payload.get("tool_name") or "", payload.get("tool_input")
    except Exception as exc:  # unreadable payload: nothing to judge
        print(f"no-unapproved-announcement: unchecked ({exc})", file=sys.stderr)
        return 0
    try:
        hit = isinstance(inp, dict) and is_announcement_write(tool, inp, payload.get("cwd") or "")
    except Exception:  # detection failed: fall back to a crude, closed check
        hit = bool(re.search(r"discussion_topic|announc", json.dumps(inp), re.I))
    if not hit:
        return 0
    try:
        why = ("it runs in a subagent or teammate, which the user's approval does not reach (#5453)" if payload.get("agent_id")
               else verdict(payload.get("transcript_path") or "", tool, inp, payload.get("cwd") or ""))
    except Exception as exc:  # a detected write: fail closed
        why = f"the check failed ({exc})"
    if why:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Refused: this posts or edits a class announcement, and {why} (Ezra, 2026-10-27, ai-config#4780: "
                "never post an announcement without his review and approval of its exact text).\n\nShow the exact "
                "text in chat and ask the user to reply with only \"post the announcement\"; then post that text once."),
        }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
