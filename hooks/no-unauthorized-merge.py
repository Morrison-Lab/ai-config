#!/usr/bin/env python3
"""PreToolUse guard: mechanistically prohibit PR/MR merge commands.

Prohibits commands attempting to merge PRs/MRs (e.g. `gh pr merge`, `glab mr merge`,
`gh api .../merge`, `glab api .../merge`, or GraphQL `mergePullRequest` / `enablePullRequestAutoMerge`)
unless explicit authorization is present via ALLOW_MERGE=1 or --allow-merge.
"""
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

# A command word begins only at a *command position*. Segments reaching
# MERGE_PATTERNS are already split on `;`, `&&`, `||`, `|` and newlines, so
# within a segment the command positions are: its start, after a background
# `&`, and after a subshell / command-substitution opener (`(`, `` ` ``, `$(`).
#
# Plain whitespace is deliberately NOT one. It used to be, and that is what made
# the guard fire on any prose, grep pattern, or string literal that merely NAMED
# the command -- including its own refusal text, so it blocked writing
# documentation, filing a bug report, or debugging itself (ai-config#1279,
# defect 2). shared/principles/fail-fast.md states the bar this restores:
# "test that mentions, greps, and quotes of the gated command pass".
CMD_POS = r"""(?:^|[;&`(\n]|\$\()\s*"""
# Keywords and wrappers whose OPERAND is itself a command word, so the word
# after one is still at a command position. Dropping bare whitespace from
# CMD_POS also dropped every one of these, because each is separated from its
# operand by a space rather than by punctuation: `! gh pr merge`, `time gh pr
# merge`, `nohup gh pr merge`, `{ gh pr merge; }` and `if true; then gh pr
# merge; fi` are all executable bash that ran the merge while the guard
# returned allow (ai-config#1287 review, reproduced end to end).
#
# This does NOT re-admit bare whitespace, because a keyword only counts when a
# CMD_POS precedes it: prose like `you can gh pr merge later` still has no
# command position before `gh` and stays allowed. Bounded for the same reason
# VAR_PREFIX is -- see its note below.
KEYWORD_PREFIX = r"""(?:(?:!|\{|time|nohup|sudo|then|else|do|if|elif|while|until)\s+){0,4}"""
# Expansions that may expand to nothing and so leave the NEXT word as the
# command: `$FOO gh pr merge` runs the merge when $FOO is empty. Matched only
# after a command position, so a mid-command `echo $FOO gh pr merge` does not.
#
# The repetition is BOUNDED rather than `*`. Unbounded, each of the N command
# positions in a long run of substitutions rescans the rest of the run before
# failing, which is quadratic: measured 610ms on 800 chained backtick pairs
# against 2.8ms for the pre-anchor matcher, on a hook that runs before every
# Bash call. Four consecutive empty-expansion prefixes is already well past
# anything a real command does, and capping makes the work per position
# constant.
VAR_PREFIX = r"""(?:(?:\$\{?[A-Za-z0-9_]+\}?|\$\([^)]*\)|`[^`]*`)\s*){0,4}"""
LEAD = CMD_POS + KEYWORD_PREFIX + VAR_PREFIX
ENV_WRAP = r"""(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*"""
# Programs that RUN text handed to them, rather than consuming it as data.
#
# One list, three consumers, because getting it wrong in any of them fails open
# in the same way and each door was found separately: a quoted operand
# (`bash -c "<merge>"`), pass 2's quote masking, and a heredoc body fed to a
# shell (`bash <<EOF`). Three rounds of review found one door each. Keeping the
# membership in one place is what makes the residual a single reviewable list
# rather than three lists that drift.
EXEC_PROGS = r"env|exec|command|bash|sh|zsh|ksh|dash|eval|trap|watch|su|ssh"

# Quoting is what makes these different from the KEYWORD_PREFIX family: pass 2
# blanks a quoted span as inert, which is right for prose and wrong here, so
# these must be recognised on the raw text in pass 1.
# The optional non-flag word is `ssh`'s hostname: `ssh host '<merge>'` puts a
# positional between the executor and its operand, which a flags-only wrapper
# never reached. This was round 2's stated residual, closed rather than left.
EXEC_WRAP = (
    r"""(?:[/\w.-]+/)?(?:""" + EXEC_PROGS + r""")"""
    r"""(?:\s+-[a-zA-Z0-9]+)*(?:\s+[A-Za-z0-9_.@-]+)?(?:\s+-[a-zA-Z0-9]+)*"""
    r"""(?:\s+["'])?\s*"""
)

# A heredoc whose consumer is one of the above is a SCRIPT, not data: `bash
# <<EOF` and `ssh host <<EOF` execute the body line by line. The quoted-delimiter
# form is not an exception -- `<<'EOF'` only suppresses expansion, and bash still
# runs what it reads.
# Built from the SAME LEAD machinery the matching passes use, not a hand-rolled
# anchor. The first version rolled its own and accepted only an env assignment
# before the executor, so `sudo bash <<EOF`, `time bash <<EOF`, `! bash <<EOF`
# and `if true; then bash <<EOF` all walked through -- the keyword-prefix gap
# from round 1, reproduced in a fourth place by the very commit that
# consolidated EXEC_PROGS into one list. Consolidating one duplicated concept
# is no protection against forking a different one in the same edit.
HEREDOC_EXECUTOR = re.compile(
    LEAD + ENV_WRAP + r"(?:[/\w.-]+/)?(?:" + EXEC_PROGS + r")\b[^\n]*?<<",
)
OPT_VAL = r"""(?:="[^"]*"|='[^']*'|=[^\s;&|`()]+|\s+"[^"]*"|\s+'[^']*'|\s+[^\s;&|`()]+|\$\{IFS\}[^\s;&|`()]+)"""
OPT_FLAGS = rf"(?:\s+-[A-Za-z0-9_-]+(?:{OPT_VAL})?)*"
HTTP_METHOD = r"(?:[pP][uU][tT]|[pP][oO][sS][tT]|[pP][aA][tT][cC][hH])"
API_WRITE_FLAG = rf"(?:-X\s*=?\s*{HTTP_METHOD}|--method\s*=?\s*{HTTP_METHOD}|-f\b|-F\b|--field\b|--raw-field\b|--input\b)"

DELIM = r"(?:\s+|\$\{IFS\}|\$IFS\b|\$\([^)]*\)|\$[A-Za-z0-9_]+)+"
GH_PROG = r"(?:[/\w.-]+/)?(?:gh|\$GH|\$\{GH\})\b"
GLAB_PROG = r"(?:[/\w.-]+/)?(?:glab|\$GLAB|\$\{GLAB\})\b"

def _merge_patterns(lead: str) -> list:
    """Build the merge-command patterns against a given command-position LEAD.

    Parameterized so the same nine patterns can run twice: once with the narrow
    LEAD over raw text, and once with PERMISSIVE_LEAD over quote-masked text.
    See the two-pass note on `offending`.
    """
    return [
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + OPT_FLAGS + DELIM + r"pr\b" + OPT_FLAGS + DELIM + r"merge\b", "gh pr merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GLAB_PROG + OPT_FLAGS + DELIM + r"mr\b" + OPT_FLAGS + DELIM + r"merge\b", "glab mr merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*(?:^|[\s/])pulls/[^\n]+/merge\b", "gh api PR merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"[^\n]*\s+api\b[^\n]*(?:^|[\s/])pulls/[^\n]+/merge\b[^\n]*" + API_WRITE_FLAG, "gh api PR merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*(?:^|[\s/])repos/[^\n]+/merges\b", "gh api repository merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"[^\n]*\s+api\b[^\n]*(?:^|[\s/])repos/[^\n]+/merges\b[^\n]*" + API_WRITE_FLAG, "gh api repository merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"(?:\s+[^\n]+)?\s+api\b[^\n]*graphql\b[^\n]*(?:mergePullRequest|enablePullRequestAutoMerge|disablePullRequestAutoMerge)", "gh api GraphQL PR merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GLAB_PROG + r"[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*(?:^|[\s/])merge_requests/[^\n]+/merge\b", "glab api MR merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GLAB_PROG + r"[^\n]*\s+api\b[^\n]*(?:^|[\s/])merge_requests/[^\n]+/merge\b[^\n]*" + API_WRITE_FLAG, "glab api MR merge"),
    ]


MERGE_PATTERNS = _merge_patterns(LEAD)

# Pass 2's command position: ANY whitespace, plus a closing `)`.
#
# Enumerating what may precede a command word cannot be finished. Two rounds of
# review found five constructs and then two more (`case $x in p) <merge>`, and
# `f() { <merge>; }; f`), each a real bypass, each a member of a class with no
# closed definition -- and every miss fails OPEN, which is the direction that
# matters for a guard whose stated purpose is to be unbypassable.
#
# So pass 2 stops enumerating. It treats every position as a command position
# and instead removes the text that cannot execute. That inverts the failure:
# an unforeseen construct is now blocked rather than allowed, and the cost of
# being wrong is an over-block, which ALLOW_MERGE=1 clears.
#
# The measurement that chose this: making the narrow LEAD permissive changed
# exactly seven of 141 cases, and all seven were prose inside quotes. Nothing
# else in the suite depends on the narrowness -- so masking quotes buys back
# every one of them, and keeps defect 2 (ai-config#1279) fixed by construction
# rather than by enumeration.
PERMISSIVE_LEAD = r"""(?:^|[;&`()\n\s]|\$\()\s*""" + KEYWORD_PREFIX + VAR_PREFIX
PERMISSIVE_MERGE_PATTERNS = _merge_patterns(PERMISSIVE_LEAD)

# The leading-whitespace allowance is OUTSIDE the repeated env-assignment group,
# not inside it. Inside, it only ever applied to assignments AFTER the first, so
# a segment whose first token was the override itself failed the `^` anchor the
# moment it carried any leading whitespace -- which every segment after a `&&`,
# `;` or `|` does, because SPLIT leaves the separator's trailing space on the
# next segment. `ALLOW_MERGE=1 <merge>` was accepted while
# `cd /repo && ALLOW_MERGE=1 <merge>` was not (ai-config#1279, defect 4), and the
# refusal message printed the segment `.strip()`ed, removing the very character
# that caused the mismatch. Leading whitespace in a segment is inert in bash, so
# accepting it authorizes nothing a bare `ALLOW_MERGE=1 ...` did not already.
ALLOW_ENV_FLAG = re.compile(
    r"^\s*(?:(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)\s+)*ALLOW_MERGE=(?:\"1\"|'1'|1\b)"
)
SPLIT = re.compile(r"&&|\|\||;|\||\n")


def unquote_words(text: str) -> str:
    """Normalize bash quote-removal on individual command/subcommand word tokens.

    In Bash, quoting part or all of a word token without spaces or subshells
    (e.g. "gh", 'gh', "pr", "merge", g""h, 'glab', "mr", "/usr/bin/gh")
    is identical to the unquoted word. This function strips inert quotes from single-word tokens
    so MERGE_PATTERNS matches regardless of quote placement on command/subcommand names.
    """
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'''(["'])([A-Za-z0-9_./-]+)\1''', r'\2', text)
        text = re.sub(r'''(?<=[A-Za-z0-9_./-])(?:""|'')(?:(?=[A-Za-z0-9_./-])|$)''', '', text)
        text = re.sub(r'''(?:^|(?<=[\s;&|`()]))(?:""|'')(?:(?=[A-Za-z0-9_./-])|$)''', '', text)
    return text


def has_allow_override(segment: str) -> bool:
    """Check if command segment contains an explicit authorization override.

    Matches either:
    1. ALLOW_MERGE=1 env assignment anchored at segment start.
    2. Standalone --allow-merge flag token occurring OUTSIDE of string quotes.
       Tokenizing quote context ensures forged --allow-merge strings inside unmasked flag values
       or bare positional text (e.g. --reviewer "please --allow-merge this") do not bypass authorization.
    """
    if ALLOW_ENV_FLAG.search(segment):
        return True

    for m in re.finditer(r"(?:^|[\s;&|`\n])(--allow-merge)\b", segment):
        idx = m.start(1)
        in_single = False
        in_double = False
        escaped = False
        for i in range(idx):
            c = segment[i]
            if escaped:
                escaped = False
                continue
            if c == "\\" and not in_single:
                escaped = True
                continue
            if c == "'" and not in_double:
                in_single = not in_single
                continue
            if c == '"' and not in_single:
                in_double = not in_double
                continue
        if not in_single and not in_double:
            return True
    return False


def mask_trailing_comments(text: str) -> str:
    """Mask trailing shell comments (# ...) with spaces while respecting quote context.

    In Bash, '#' inside quotes ('...' or "...") is a literal character, not a comment boundary.
    This function tokenizes quote state line-by-line to ensure '#' inside quoted strings is NOT
    mistaken for a shell comment, preventing quote-enclosed '#...' strings from swallowing
    subsequent statement separators or merge commands.
    """
    lines = text.split("\n")
    masked_lines = []
    for line in lines:
        in_single = False
        in_double = False
        escaped = False
        comment_start = -1
        for i, c in enumerate(line):
            if escaped:
                escaped = False
                continue
            if c == "\\" and not in_single:
                escaped = True
                continue
            if c == "'" and not in_double:
                in_single = not in_single
                continue
            if c == '"' and not in_single:
                in_double = not in_double
                continue
            if c == "#" and not in_single and not in_double:
                if i == 0 or line[i - 1] in " \t;&|`()":
                    comment_start = i
                    break
        if comment_start != -1:
            line = line[:comment_start] + " " * (len(line) - comment_start)
        masked_lines.append(line)
    return "\n".join(masked_lines)


def mask_subexpressions(val: str) -> str:
    """Mask literal prose inside payload flags with spaces, while preserving live command substitutions (`...` or $(...)) unmasked."""
    sub_pattern = r"(`[^`]*`|\$\([^)]*\))"
    tokens = re.split(sub_pattern, val)
    result = []
    for i, tok in enumerate(tokens):
        if i % 2 == 1:
            result.append(tok)
        else:
            result.append("".join("\n" if c == "\n" else " " for c in tok))
    return "".join(result)


def mask_inert_quotes(text: str) -> str:
    """Blank quoted spans that bash cannot execute, preserving length.

    Length-preserving because `offending` derives segment offsets from one
    string and slices another with them; a shorter result would misalign the
    segment reported in the refusal message.

    A single-quoted span is wholly inert. A double-quoted span is inert EXCEPT
    for `$(...)` and backtick substitutions, which bash still expands inside
    double quotes -- those are preserved verbatim, so hiding a merge in one
    still blocks.

    This is only ever applied for the PERMISSIVE pass. An executor's own quoted
    operand (`bash -c "<merge>"`, `eval "<merge>"`) IS live, and blanking it
    here would lose it -- pass 1 catches those on unmasked text via EXEC_WRAP,
    which is why the narrow pass is kept rather than replaced.
    """
    def blank(s: str) -> str:
        return "".join("\n" if c == "\n" else " " for c in s)

    def repl_double(m: "re.Match") -> str:
        inner = m.group(0)[1:-1]
        return " " + mask_subexpressions(inner) + " "

    text = re.sub(r"\"(?:\\.|[^\"\\])*\"", repl_double, text, flags=re.DOTALL)
    text = re.sub(r"'[^']*'", lambda m: blank(m.group(0)), text, flags=re.DOTALL)
    return text


HEREDOC_START = re.compile(
    r"""<<-?[ \t]*(?:(['"])([A-Za-z_][A-Za-z0-9_]*)\1|([A-Za-z_][A-Za-z0-9_]*))"""
)


def _heredoc_intro(line: str):
    """The first `<<DELIM` on `line` that is a REAL heredoc introducer, or None.

    Quote context decides it, and getting this wrong fails OPEN rather than
    noisily: `echo "see <<EOF for details"` introduces no heredoc, but treating
    it as one masks every following line until a lone `EOF` that never comes --
    hiding any real merge command underneath it. Same for a `grep "<<PATTERN"`.

    `<<<` is a herestring, not a heredoc, and is skipped whole: scanning it
    character by character would otherwise match `<<` at its second `<` and read
    the rest as a delimiter.
    """
    in_single = in_double = escaped = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if escaped:
            escaped = False
        elif c == "\\" and not in_single:
            escaped = True
        elif c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "<" and not in_single and not in_double:
            if line.startswith("<<<", i):
                i += 3
                continue
            m = HEREDOC_START.match(line, i)
            if m:
                return m
        i += 1
    return None


def mask_heredocs(text: str) -> str:
    """Mask heredoc bodies, preserving length and line structure.

    A QUOTED delimiter (`<<'EOF'`, `<<"EOF"`) tells bash to perform no expansion
    at all in the body, so nothing in it can execute: it is inert text and is
    masked in full. An UNQUOTED delimiter (`<<EOF`) does expand, so only the
    literal prose is masked and `$(...)` / backtick substitutions are left live,
    exactly as mask_subexpressions does for payload flags.

    Without this a heredoc carrying prose ABOUT a merge command was matched as
    one -- which is how filing ai-config#1279 was itself blocked, by the guard
    matching its own refusal text quoted inside a `gh issue create` heredoc.

    But "inert text" is a claim about the CONSUMER, not about the heredoc. A
    body fed to a shell (`bash <<EOF`, `ssh host <<EOF`) is a script, and
    masking it hid a real merge from both later passes -- the quoted-delimiter
    form included, since `<<'EOF'` suppresses expansion and bash still runs
    what it reads. Those are left untouched; see HEREDOC_EXECUTOR.
    """
    lines = text.split("\n")
    out = list(lines)
    i = 0
    while i < len(lines):
        m = _heredoc_intro(lines[i])
        if not m:
            i += 1
            continue
        quoted = bool(m.group(2))
        delim = m.group(2) or m.group(3)
        executes = bool(HEREDOC_EXECUTOR.search(lines[i]))
        j = i + 1
        while j < len(lines) and lines[j].strip() != delim:
            if not executes:
                out[j] = " " * len(lines[j]) if quoted else mask_subexpressions(lines[j])
            j += 1
        i = j + 1
    return "\n".join(out)


def mask_payloads(text: str) -> str:
    """Mask string payload flags (--body, -m, etc.) so benign occurrences of gh pr merge inside commit/PR messages do not trigger false positives.

    Leaves command substitutions (`...` or $(...)) inside payload flags unmasked so malicious execution cannot be hidden inside payload flags.
    """
    flag_pattern = (
        r"(?:--body-file\b|--body\b|--title\b|--subject\b|--comment\b|--message\b|"
        r"--commit-title\b|--commit-message\b|--reason\b|--notes\b|--description\b|"
        r"--summary\b|-m\b|-b\b|-d\b|-t\b|-s\b|"
        r"(?:-f|-F|--field|--raw-field|--input)\s+"
        r"(?:body|title|subject|comment|message|commit_title|commit_message|reason|notes|description|text|summary)\b)"
    )
    hspace = r"[ \t]*"

    def repl_double(m):
        return m.group(1) + mask_subexpressions(m.group(2))

    def repl_single(m):
        val = m.group(2)
        return m.group(1) + "".join("\n" if c == "\n" else " " for c in val)

    def repl_unquoted(m):
        return m.group(1) + mask_subexpressions(m.group(2))

    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(\"(?:\\.|[^\"])*\")", repl_double, text, flags=re.DOTALL)
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(\'(?:\\.|[^\'])*\')", repl_single, text, flags=re.DOTALL)
    text = mask_trailing_comments(text)
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(`[^`]*`|\$\([^)]*\)|[^-;\s&|\n][^;\s&|\n]*)", repl_unquoted, text)
    return text


def sanitize(name: str) -> str:
    """Sanitize session ID matching ai-session.sh: tr -c 'A-Za-z0-9._-' '_'"""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def is_session_alive(sess_file: Path) -> bool:
    try:
        content = sess_file.read_text(encoding="utf-8")
        sess_data = dict(line.split("=", 1) for line in content.splitlines() if "=" in line)
        pid = sess_data.get("pid")
        host = sess_data.get("host")
        local_host = platform.node()
        if pid and pid.isdigit() and int(pid) > 0:
            if not host or host.split(".")[0].lower() == local_host.split(".")[0].lower():
                try:
                    os.kill(int(pid), 0)
                    return True
                except OSError:
                    return False  # PID is dead on local host
        hb = int(sess_data.get("heartbeat") or sess_data.get("started") or 0)
        return (time.time() - hb) < 1800
    except Exception:
        pass
    return False


def get_git_common_dirs() -> list[Path]:
    dirs = []
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        ).strip()
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = (Path.cwd() / common_path).resolve()
        dirs.append(common_path)
    except Exception:
        pass

    repo_dir = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parents[1])
    try:
        common_dir = subprocess.check_output(
            ["git", "-C", repo_dir, "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = (Path(repo_dir) / common_path).resolve()
        if common_path not in dirs:
            dirs.append(common_path)
    except Exception:
        pass

    pwd_git = Path.cwd() / ".git"
    if pwd_git.is_dir() and pwd_git.resolve() not in dirs:
        dirs.append(pwd_git.resolve())

    return dirs


def resolve_session_id(payload: dict | None = None) -> str | None:
    """The id of the session this hook is running under, or None.

    The harness supplies its own session id in the hook payload, alongside
    `transcript_path`; that is the SAME id `/mwc` passes to
    `ai-session.sh enable-mwc --id`, so it is the authoritative one. Reading it
    is what makes a granted MWC visible to the guard at all: the hook process
    inherits neither AI_SESSION_ID nor CLAUDE_SESSION_ID (both measured unset on
    a machine where the grant was live), so the env-only lookup this replaces
    returned None unconditionally and no legitimate grant ever reached the guard
    (ai-config#1279, defect 1).

    Order: the payload's own id, then the transcript filename stem (the same id,
    for a harness that omits the field), then the environment forms. Each is a
    way to learn WHICH session is running -- none of them grants anything, since
    the caller still requires a marker for exactly that id plus a live session.
    """
    if payload:
        sid = payload.get("session_id")
        if isinstance(sid, str) and sid.strip():
            return sid.strip()
        tpath = payload.get("transcript_path")
        if isinstance(tpath, str) and tpath.strip():
            stem = Path(tpath.strip()).stem
            if stem:
                return stem
    return os.environ.get("AI_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")


def check_mwc_active(payload: dict | None = None) -> bool:
    try:
        current_session = resolve_session_id(payload)
        if not current_session:
            return False

        sanitized_session = sanitize(current_session)
        for common_dir in get_git_common_dirs():
            reg_dir = common_dir / "ai-sessions"
            if not reg_dir.exists():
                continue
            mwc_file = reg_dir / f"{sanitized_session}.mwc"
            if mwc_file.exists():
                sess_file = reg_dir / f"{sanitized_session}.session"
                if sess_file.exists() and is_session_alive(sess_file):
                    return True
    except Exception:
        pass
    return False


def offending(command: str, payload: dict | None = None):
    # 1. Normalize bash backslash-newline line continuations (matching bash semantics: remove backslash and newline without inserting a space)
    norm_command = re.sub(r"\\\n", "", command)
    # 2. Mask heredoc bodies BEFORE unquote_words, which would otherwise strip
    #    the quotes off a `<<'EOF'` delimiter and make an inert body look live.
    #    Length-preserving, so later slice offsets stay aligned.
    heredoc_masked = mask_heredocs(norm_command)
    # 3. Normalize single-word token quote removal (e.g. "gh" -> gh, "pr" -> pr, "merge" -> merge, g""h -> gh)
    unquoted_command = unquote_words(heredoc_masked)
    # 4. Mask prose payloads across the entire command BEFORE splitting on separators/newlines
    masked_command = mask_payloads(unquoted_command)

    # 5. Use finditer on masked_command to derive exact character slice offsets for unquoted_command
    matches = list(SPLIT.finditer(masked_command))
    starts = [0] + [m.end() for m in matches]
    ends = [m.start() for m in matches] + [len(masked_command)]

    # 6. Two passes, both length-preserving so the same offsets slice both.
    #    Pass 1 (narrow LEAD, raw text) keeps every behaviour the suite pins,
    #    including an executor's live quoted operand (`bash -c "<merge>"`).
    #    Pass 2 (permissive LEAD, quote-masked text) is strictly ADDITIVE: it
    #    stops asking which constructs may precede a command word -- an
    #    enumeration two review rounds showed cannot be finished -- and instead
    #    removes the text that cannot execute. See PERMISSIVE_LEAD.
    inert_command = mask_inert_quotes(masked_command)

    for start, end in zip(starts, ends):
        orig_seg = unquoted_command[start:end]
        if has_allow_override(orig_seg):
            continue
        hit = None
        for seg, patterns in (
            (masked_command[start:end], MERGE_PATTERNS),
            (inert_command[start:end], PERMISSIVE_MERGE_PATTERNS),
        ):
            for pattern, label in patterns:
                if re.search(pattern, seg):
                    hit = label
                    break
            if hit is not None:
                break
        if hit is None:
            continue
        if check_mwc_active(payload):
            continue  # Allowed via active MWC session grant
        return hit, orig_seg.strip()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"no-unauthorized-merge: unreadable hook input ({exc})", file=sys.stderr)
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    hit = offending(command, payload)
    if not hit:
        return 0

    label, segment = hit
    reason = (
        f"MECHANISTIC PROHIBITION: `{label}` is strictly blocked without explicit permission.\n\n"
        f"    Offending command segment: {segment}\n\n"
        "AI agents are mechanistically forbidden from merging PRs/MRs unless explicitly instructed "
        "by the user or executing under an explicit override (e.g. ALLOW_MERGE=1 or active /mwc)."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
