#!/usr/bin/env python3
"""Stop reminder: handing the user a bash command when their shell is
PowerShell 5.1.

WHAT HAPPENED
-------------
Measured 2026-09-15 on this machine. The session's environment brief states
"Shell: PowerShell (primary)", Windows PowerShell 5.1, and explicitly lists
`&&` as a parser error, says inline `VAR=value cmd` prefixes do not exist, and
says Unix paths do not resolve. The reply nonetheless handed the user this, in
a fenced block, for their PowerShell terminal:

    cd /d/GitHub/ai-config/.claude/worktrees/... && ALLOW_UNREVIEWED_PUSH=1 git push ...

Three incompatibilities in one line. The user pasted it and got
`The token '&&' is not a valid statement separator in this version.`
The correct form was
`Set-Location D:\\...; $env:ALLOW_UNREVIEWED_PUSH='1'; git push ...`.

The belief that produced it: "I am composing a shell command", where the shell
in mind was the one the Bash TOOL had been using all session. A command in a
fenced block in a reply is addressed to the USER'S shell, which is a different
program. Two shells coexist here and the target is decided by WHERE the command
goes, not by which one was last used.

WHY THIS ALMOST WAS NOT BUILT, AND WHAT DECIDED IT
--------------------------------------------------
The obvious trigger -- "a fenced block containing `&&` while the user runs
PowerShell" -- is unusable, and measurement rather than argument settled it.
Over the 118 transcripts under `~/.claude/projects` (1252 assistant text
messages, 42 carrying a fenced block), that trigger fires 13 times: ONE true
positive and twelve explanations, reviews, and corpus edits that merely quote
shell syntax.

The discriminator that suggests itself -- suppress when the surrounding prose
is retrospective ("failed", "the error was", "I handed you") -- is worse than
useless here, and this is the finding that matters. It marks all thirteen
messages identically, the true positive included: the offending message also
said "the agent stopped at the classifier denial" and "genuinely doesn't
exist", because a message can hand over a command AND discuss a failure at the
same time. Suppressing on it would remove the only true positive and keep
nothing. Firing on it is `remind-ums-after-error.py`'s ai-config#2997 pattern:
a guard that fires on the explanation of the very mistake it polices.

What separates the two classes is not the prose around the block but the SHAPE
of the block itself. A command handed over to be pasted is short, carries no
prompt, and shows no output. A quotation of a failure shows the prompt, or the
error beneath it, or sits inside a longer listing. Measured over the same
corpus:

    <=3 non-blank lines, no prompt marker, PS-invalid construct :  3 firings
    <=5                                                         :  3
    <=8                                                         :  3
    <=12                                                        :  4  <- first
    unbounded                                                   :  4     miss

All three firings at the <=8 bound are the same genuine directive, re-issued
across one session. Nothing else in 118 transcripts matches. `MAX_LINES = 8` is
therefore the measured ceiling, not a guess -- one line below where the first
false positive appears. The corrected PowerShell form of that very command,
which also appears in the corpus, is correctly silent.

WHAT IT DOES NOT KEY ON
-----------------------
  * The block's LANGUAGE TAG, as an inclusion test. The harness instructs
    tagging runnable blocks ```bash to get a Run button, so the tag says
    nothing about which shell the command is FOR -- keying on it would invert
    the check. The tag is used only to EXCLUDE languages that are plainly not
    shell commands (`json`, `python`, `diff`, `console`, ...), which can only
    remove false positives. `powershell` is deliberately NOT excluded: a block
    tagged for PowerShell that contains `&&` is the bug, not an exception.
  * Backtick command substitution, which the spec proposed and measurement
    rejected. It produced 17 block-level hits in the corpus, every one ordinary
    markdown inline code rather than shell substitution, and contributed
    nothing to the true positive. Including it is the likeliest single way to
    reintroduce the false positives this design exists to avoid. Recorded in
    the suite's KNOWN_LIMITS rather than silently dropped.
  * A block in a session whose shell is unknown. Absent positive evidence that
    the user's shell is PowerShell, this stays silent -- the safe direction.

It warns and never blocks. A `Stop` guard sits between the model and the user,
which README names as the worst place for a wrong one, so this only ever adds a
`systemMessage`; there is no path here that suppresses, delays, or alters the
reply.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# ---------------------------------------------------------------------------
# Gate 1: is the USER's shell PowerShell?
#
# The environment brief lives in an `attachment` record's `rendered[].content`
# (measured 2026-09-15: record index 3 of this session's transcript, carrying
# "- Shell: PowerShell (primary); Bash tool also available..."). It is not in
# the hook payload, so the transcript is the only place to read it.
SHELL_IS_PS = re.compile(r"Shell:\s*PowerShell", re.I)

# ---------------------------------------------------------------------------
# Gate 2/3: which fenced blocks are a command handed over to be pasted.
FENCE = re.compile(r"^[ \t]*```([^\n`]*)\n(.*?)^[ \t]*```[ \t]*$", re.S | re.M)

# Tags that mark the block as plainly not a shell command. EXCLUSION only --
# see the docstring on why an inclusion test on the tag would invert the check.
NON_SHELL_TAGS = frozenset({
    "json", "jsonc", "json5", "yaml", "yml", "toml", "xml", "html", "css",
    "python", "py", "r", "sql", "diff", "patch", "markdown", "md", "rst",
    "console", "text", "txt", "log", "output", "csv", "tsv", "ini",
    "javascript", "js", "typescript", "ts", "c", "cpp", "java", "go", "rust",
})

# A quoted session shows its prompt; a command handed over does not. `C:\...>`
# is the cmd/PowerShell prompt, `$ ` the POSIX one, `>>>` the Python REPL.
PROMPT = re.compile(
    r"^\s*(?:\$\s|PS[^>\n]*>|>>>|[A-Za-z]:\\[^>\n]*>)", re.M)

# The measured ceiling: one line below where the first false positive appears.
MAX_LINES = 8

# ---------------------------------------------------------------------------
# Gate 4: constructs Windows PowerShell 5.1 cannot run, each with the
# replacement the warning names. Every entry is a HARD error or a silent
# wrong-target in 5.1, not a style preference.
#
# The fourth field says whether the construct is matched against the RAW body
# rather than the masked one. A heredoc opener needs it: `<<'EOF'` carries a
# quoted delimiter, so the quote mask blanks the delimiter and the opener stops
# matching. Everything else is matched masked, because a `&&` or a path inside
# a string literal is data.
CONSTRUCTS = (
    ("`&&`", re.compile(r"(?<![&|])&&(?![&|])"),
     "`;` (or `; if ($?) { ... }` to keep the conditional)", False),
    ("`||`", re.compile(r"(?<![&|])\|\|(?![&|])"),
     "`; if (-not $?) { ... }`", False),
    ("an MSYS/Unix absolute path", re.compile(
        r"(?<![\w.])/(?:[a-z]/[A-Za-z0-9_.-]|(?:tmp|usr|etc|var|home|opt)/)"),
     "a Windows path (`D:\\GitHub\\...`)", False),
    # UPPERCASE only, and anchored to a command position. The first spelling
    # accepted any identifier and matched `ok=1 msg=...` in a test's output and
    # `start=18 end=...` in a Python repr -- three false positives out of six
    # firings when measured against the real transcripts. An environment
    # variable prefix is uppercase by universal convention, and narrowing to it
    # removed all three without costing the true positive.
    ("an inline `VAR=value command` prefix", re.compile(
        r"(?:^|[;&|\n])[ \t]*[A-Z_][A-Z0-9_]*=[^\s;&|]*[ \t]+[A-Za-z]"),
     "`$env:VAR='value'; command` (and `Remove-Item Env:\\VAR` after)", False),
    ("`2>/dev/null`", re.compile(r"\d?>\s*/dev/null"),
     "`2>$null`", False),
    ("a bash heredoc or here-string", re.compile(r"<<-?<?\s*['\"]?[A-Za-z_]"),
     "a single-quoted here-string, `@'` ... `'@` at column 0", True),
)

# `&&` inside a quoted string or a URL is data, not a separator. Blanked before
# the constructs are matched so a command that legitimately CONTAINS the text
# does not read as one that uses it.
QUOTED = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
URL = re.compile(r"https?://\S+")
# A `#` comment is prose inside a command block, and it is where a path gets
# QUOTED rather than run. Measured: a block whose comment read "under Git Bash
# `pwd -P` answers `/c/Users/...`" fired as an MSYS path being handed over.
# `#` opens a comment in both bash and PowerShell, so one rule covers both.
COMMENT = re.compile(r"(?m)(?:^|(?<=[ \t]))#[^\n]*$")


def _mask(body):
    """Blank quoted spans, URLs and comments, preserving length and lines."""
    out = body
    for rx in (URL, QUOTED, COMMENT):
        out = rx.sub(lambda m: " " * len(m.group(0)), out)
    return out


def ps_invalid(body):
    """[(name, replacement, offending_line)] for each construct found."""
    masked = _mask(body)
    found = []
    for name, rx, fix, use_raw in CONSTRUCTS:
        hit = rx.search(body if use_raw else masked)
        if not hit:
            continue
        line = body[:hit.end()].splitlines()[-1] if body[:hit.end()] else ""
        found.append((name, fix, line.strip()))
    return found


def runnable_blocks(text):
    """[(tag, body)] for blocks shaped like a command handed over to be run.

    The shape gate, not the prose around it, is what separates a directive
    from a quotation -- see the module docstring for the measurement.
    """
    out = []
    if not isinstance(text, str):
        return out
    for tag, body in FENCE.findall(text):
        tag = tag.strip().lower().split()[0] if tag.strip() else ""
        if tag in NON_SHELL_TAGS:
            continue
        lines = [ln for ln in body.splitlines() if ln.strip()]
        if not lines or len(lines) > MAX_LINES:
            continue
        if PROMPT.search(body):
            continue
        out.append((tag, body))
    return out


def find_wrong_shell_blocks(text):
    """[(name, replacement, offending_line)] over every runnable block."""
    found = []
    seen = set()
    for _, body in runnable_blocks(text):
        for name, fix, line in ps_invalid(body):
            key = (name, line)
            if key in seen:
                continue
            seen.add(key)
            found.append((name, fix, line))
    return found


def _records(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                yield entry


def _attachment_text(entry):
    """Yield the prose of an attachment record, however it is shaped."""
    for key in ("rendered", "attachment"):
        node = entry.get(key)
        if isinstance(node, str):
            yield node
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, str):
                    yield item
                elif isinstance(item, dict):
                    value = item.get("content")
                    if isinstance(value, str):
                        yield value
        elif isinstance(node, dict):
            value = node.get("content")
            if isinstance(value, str):
                yield value


def user_shell_is_powershell(transcript_path):
    """True only on positive evidence from the session's environment brief.

    Returns False when the transcript is missing, unreadable, or simply does
    not say -- an unknown shell must not produce a warning about the wrong one.
    """
    if not isinstance(transcript_path, str) or not transcript_path:
        return False
    if not os.path.isfile(transcript_path):
        return False
    try:
        for entry in _records(transcript_path):
            if entry.get("type") != "attachment":
                continue
            for text in _attachment_text(entry):
                if SHELL_IS_PS.search(text):
                    return True
    except OSError:
        return False
    return False


def last_assistant_text(transcript_path):
    """The text of the last assistant message in the transcript."""
    latest = ""
    for entry in _records(transcript_path):
        if entry.get("isSidechain"):
            continue
        is_asst = (entry.get("type") == "assistant"
                   or entry.get("role") == "assistant")
        if not is_asst:
            continue
        message = entry.get("message")
        content = (message.get("content") if isinstance(message, dict)
                   else entry.get("content"))
        parts = []
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text") or "")
        joined = "\n".join(p for p in parts if p)
        if joined.strip():
            latest = joined
    return latest


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    path = (payload.get("transcript_path")
            or payload.get("transcriptPath") or "")
    if not isinstance(path, str) or not path or not os.path.isfile(path):
        return 0

    try:
        if not user_shell_is_powershell(path):
            return 0
        text = last_assistant_text(path)
        if not text:
            return 0
        hits = find_wrong_shell_blocks(text)
    except Exception:  # fail open on any parse trouble
        return 0
    if not hits:
        return 0

    # Keyed on the transcript path as well as the reply, so two sessions that
    # emit the identical short command do not share one sentinel and silence
    # each other -- the bug `remind-ums-after-error.py` documents fixing.
    key = hashlib.sha256(f"{path}:{text}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(),
                            f".claude-bash-for-powershell-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    name, fix, line = hits[0]
    extra = ("" if len(hits) == 1
             else f" ({len(hits) - 1} more construct(s) in the same reply.)")
    print(json.dumps({"systemMessage": (
        f"Your reply hands the user a command containing {name}, and this "
        "session's environment brief says their shell is Windows PowerShell "
        f"5.1, where that is a parser error.\n  {line}\nUse {fix} instead.\n"
        "A command in a fenced block is addressed to the USER'S shell, which "
        "is a different program from the one your Bash tool runs -- the "
        "target is decided by where the command goes, not by which shell you "
        "last used." + extra
    )}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
