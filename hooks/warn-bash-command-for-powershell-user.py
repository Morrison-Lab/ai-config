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

WHAT THE CORPUS ESTABLISHES, AND WHAT IT DOES NOT
-------------------------------------------------
Stated carefully, because the first version of this section published a figure
that did not reproduce and round-1 review caught it. The claim was that the
naive `&&` trigger "fires 13 times for one true positive". Re-derived: 13 was
the count for a much BROADER trigger (all six constructs, unmasked, ungated,
plus backtick substitution) measured over every assistant message on disk,
including the ~61% that live in `subagents/agent-*.jsonl` and that this hook,
bound to `Stop` in the main session, can never read.

The in-scope figures, re-derived 2026-09-15 over the 120 transcripts under
`~/.claude/projects` (1297 assistant text messages, of which **500** are not
sidechain and so readable here, 16 of those carrying a fenced block):

    all six constructs, no masking, no shape gate :  4 firings
    the shipped matcher                           :  3 firings, all the same
                                                       true positive, 0 false
    fenced block merely containing `&&`           :  4 firings (3 true, 1 a
                                                       `$ `-prompted quotation)

So the honest summary is that **the corpus is too small to validate this
design**. It contains one genuine incident, re-issued three times, and one
near-miss. What the numbers establish is narrow: the shipped matcher is silent
on everything else in it, including the corrected PowerShell form of that very
command. What they do NOT establish is the false-positive rate, and it would be
wrong to quote 3/0 as if they did.

The real evidence is the suite's CONSTRUCTED negatives. Round-1 review built
the false positives the corpus lacks -- a Dockerfile `RUN` line, a CI `run:`
step, a Make recipe, a git alias, a quoted session prompted `user@host:~$`, a
heredoc merely named in a comment -- and every one of them fired. Those are
fixed and pinned as cases. A command meant for a REMOTE host or container
shell is NOT among them: it has no signal, stays a declared KNOWN_LIMIT, and
is the largest false-positive class. A reader weighing this guard should weigh those, not the
corpus counts.

WHY THE PROSE AROUND THE BLOCK IS NOT THE DISCRIMINATOR
-------------------------------------------------------
This part does hold up, and it is the reason the guard is shaped the way it is.
Suppressing when the surrounding prose is retrospective ("failed", "the error
was", "I handed you") marks the true positive and the false ones identically:
the offending message also said "the agent stopped at the classifier denial"
and "genuinely doesn't exist", because a message can hand over a command AND
discuss a failure at the same time. Suppressing on it removes the true positive
and keeps nothing; firing on it is `remind-ums-after-error.py`'s ai-config#2997
pattern, a guard that fires on the explanation of the very mistake it polices.

So the separation is done on the SHAPE of the block. A command handed over is
short, carries no prompt, and shows no output; a quotation shows its prompt, or
the error beneath it, or runs long. `PROMPT` carries almost all of that load --
`MAX_LINES` is defence in depth rather than a measured ceiling, and the comment
beside it says so.

WHAT IT DOES NOT KEY ON
-----------------------
  * The block's LANGUAGE TAG, as an inclusion test. The harness instructs
    tagging runnable blocks ```bash to get a Run button, so the tag says
    nothing about which shell the command is FOR -- keying on it would invert
    the check. The tag is used only to EXCLUDE languages that are plainly not
    shell commands (`json`, `python`, `diff`, `console`, ...), which can only
    remove false positives. `powershell` is deliberately NOT excluded: a block
    tagged for PowerShell that contains `&&` is the bug, not an exception.
  * Backtick command substitution, which the spec proposed and which is left
    out. It produced 18 block-level hits across the corpus, every one ordinary
    markdown inline code rather than shell substitution, and contributed
    nothing to the true positive. In scope it adds nothing either way, so the
    exclusion rests on the out-of-scope evidence plus the shape of the risk
    rather than on an in-scope measurement. Recorded in the suite's
    KNOWN_LIMITS rather than silently dropped.
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
#
# Three OR MORE backticks: the harness emits a four-backtick fence whenever the
# block body itself contains a triple backtick, which is exactly when a reply is
# showing markdown that contains a command. A fixed-three pattern missed those
# outright (round-1 review of 8b504813, finding 3.5). The closing run is a
# backreference, so a four-backtick fence is not closed by a three-backtick line
# inside it.
FENCE = re.compile(r"^[ \t]*(`{3,})([^\n`]*)\n(.*?)^[ \t]*\1[ \t]*$",
                   re.S | re.M)

# Tags that mark the block as plainly not a shell command. EXCLUSION only --
# see the docstring on why an inclusion test on the tag would invert the check.
NON_SHELL_TAGS = frozenset({
    "json", "jsonc", "json5", "yaml", "yml", "toml", "xml", "html", "css",
    "python", "py", "r", "sql", "diff", "patch", "markdown", "md", "rst",
    "console", "text", "txt", "log", "output", "csv", "tsv", "ini",
    "javascript", "js", "typescript", "ts", "c", "cpp", "java", "go", "rust",
    # Formats whose bodies are bash BY DESIGN and are never pasted into the
    # user's terminal: a container build step, a CI step, a Make recipe, a git
    # alias. Round-1 review of 8b504813 (finding 2.1) found every one of these
    # firing. Tagging only helps the tagged spelling -- the untagged one is a
    # named limit in the suite rather than a silent gap.
    "dockerfile", "docker", "containerfile", "makefile", "make", "mk",
    "gitconfig", "conf", "config", "editorconfig", "properties", "env",
    "dotenv", "gitignore", "hcl", "tf", "terraform", "nginx", "apache",
    "systemd", "service", "cron", "crontab",
})

# A quoted session shows its prompt; a command handed over does not. This
# carries the whole load of the directive-versus-citation split, so it has to
# recognise the prompts people actually paste.
#
# The first spelling knew only a bare `$ ` at column 0, `PS ...>`, `>>>` and
# `C:\...>`. Round-1 review of 8b504813 (finding 2.5) found it missing
# `user@host:~$` -- the DEFAULT Git Bash and Linux prompt, and so the commonest
# way a failing session gets quoted -- along with `[user@host ~]$`, `bash-5.1$`
# and any `(venv) PS C:\...>`. Each is added below; a leading prefix is now
# allowed before `PS ...>` for the venv/conda case.
PROMPT = re.compile(
    r"""^[ \t]*(?:
        \$[ \t]                             # bare POSIX prompt
      | \S*@\S*[:~][^\n]*[$#][ \t]          # user@host:~$   root@box:/#
      | \[[^\]\n]*\][ \t]*[$#][ \t]         # [user@host ~]$
      | [A-Za-z][\w.-]*-[\d.]+[$#][ \t]     # bash-5.1$
      | [^\n>]{0,24}?PS[^>\n]*>             # PS C:\> and (venv) PS C:\>
      | >>>
      | [A-Za-z]:\\[^>\n]*>                 # C:\Users\Work>
    )""",
    re.M | re.X,
)

# Defence in depth against a script LISTING being read as a command to paste.
#
# Honest status, corrected after round-1 review (finding 1b): this is NOT
# currently load-bearing on the measured corpus. The docstring once claimed the
# first false positive appears at a bound of 12; that table was measured before
# quote/comment masking existed, and after masking the firing count is flat at
# three for every bound including unbounded. The bound is kept because a long
# listing is the shape it excludes and the corpus is small, not because a
# measurement currently separates it. It counts NON-BLANK lines, so a padded
# block of eight commands is admitted -- named in the suite's KNOWN_LIMITS.
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
    # `2>/dev/null` is listed BEFORE the path construct so the more specific
    # name is the one reported; the path pattern below also matches `/dev/`.
    ("`2>/dev/null`", re.compile(r"\d?>\s*/dev/null"),
     "`2>$null`", False),
    # `/mnt/c/` (the WSL spelling, which this corpus uses constantly), an
    # uppercase drive letter (`/D/GitHub`, which Git Bash accepts), and the
    # remaining FHS roots were all missing from the first spelling (round-1
    # review of 8b504813, finding 3.4).
    ("an MSYS/Unix absolute path", re.compile(
        r"(?<![\w.])/(?:mnt/[A-Za-z]/|[A-Za-z]/[A-Za-z0-9_.-]"
        r"|(?:tmp|usr|etc|var|home|opt|root|bin|sbin|proc|dev|srv|lib|Users)/)"),
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
    """Blank quoted spans, URLs and comments, preserving length and lines.

    QUOTED runs FIRST, and the order is load-bearing. `URL` is greedy to
    whitespace, so running it first ate the closing quote of
    `echo 'https://x/a' 'b && c'`, orphaned the opening one, and left the `&&`
    inside the second quoted span exposed -- the URL mask manufacturing the
    false positive it exists to prevent (round-1 review of 8b504813, finding
    2.2). With QUOTED first, a quoted URL is already blank and `URL` only has
    to cover the bare form.
    """
    out = body
    for rx in (QUOTED, URL, COMMENT):
        out = rx.sub(lambda m: " " * len(m.group(0)), out)
    return out


def ps_invalid(body):
    """[(name, replacement, offending_line)] for each construct found."""
    masked = _mask(body)
    found = []
    for name, rx, fix, use_raw in CONSTRUCTS:
        if use_raw:
            # Matched on the RAW body because the quote mask would blank a
            # heredoc's own quoted delimiter (`<<'EOF'`) and hide the opener.
            # The position is then checked against the mask, so an opener
            # MENTIONED inside a comment or a string is still excluded --
            # without that check a comment reading "use <<EOF for a heredoc"
            # fired, which is the exact class the COMMENT mask exists to stop
            # (round-1 review of 8b504813, finding 3.1).
            hit = next((m for m in rx.finditer(body)
                        if masked[m.start():m.end()].strip()), None)
        else:
            hit = rx.search(masked)
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
    for _ticks, tag, body in FENCE.findall(text):
        # `.lower()` so ```JSON is excluded like ```json, and `.split()[0]` so
        # an info string carrying attributes (```bash title="run me") is read
        # by its language alone.
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
    """All assistant text of the CURRENT turn -- everything since the last
    user record.

    Not just the last non-empty message. A turn that hands over a command and
    then makes one more tool call ends with a short "Done." record, and taking
    only the last one made the directive invisible (round-1 review of
    8b504813, finding 3.6). Accumulating the turn keeps the whole reply in
    view, which is what the user actually reads.

    `isSidechain` records are skipped: in a subagent transcript every
    assistant record carries it, and this hook is bound to `Stop` in the main
    session only.
    """
    turn = []
    for entry in _records(transcript_path):
        etype = entry.get("type") or entry.get("role")
        if etype == "user" and not entry.get("isSidechain"):
            turn = []
            continue
        if entry.get("isSidechain"):
            continue
        if etype != "assistant":
            continue
        message = entry.get("message")
        content = (message.get("content") if isinstance(message, dict)
                   else entry.get("content"))
        if isinstance(content, str):
            if content.strip():
                turn.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    piece = block.get("text") or ""
                    if piece.strip():
                        turn.append(piece)
    return "\n".join(turn)


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
