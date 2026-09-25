#!/usr/bin/env python3
"""PreToolUse guard: deleting a Quarto/knitr render intermediate while a
render is live.

## The incident

2026-09-24, `health-analytics-core/abridge`, a report worktree. The agent
deleted a gitignored `inst/analysis/paper/paper-with-supplement.rmarkdown`,
reasoning it was a leftover from its own failed render. It was not: the user
was rendering that exact worktree from their own terminal at the time, and
Quarto CREATES that intermediate at the START of every render, not only at
the end. The render had already knitted all 251 chunks (~10 minutes,
including a forced analysis-cache rebuild) when it then failed with `cannot
open file 'paper-with-supplement.qmd'` -- the file the agent had just
deleted out from under it.

`AGENTS.md`'s "Subagent worktrees are assigned" section already states the
rule this violated: "Verify a dispatched agent's liveness before touching a
worktree you did not just create -- never infer it from a snapshot." That
prose rule existed before the incident and did not fire at composition
time, because a passive rule only fires if the agent happens to recall it at
the moment it types the command -- see `no-heavy-work-on-head-node.py`'s
docstring for the same argument made about a different rule. So the check
has to run at the command, independent of whether the moment felt like it
called for one.

## What this guards, and why the file being gitignored is not evidence

`*.rmarkdown`, `*.knit.md`, `*.knit.qmd`, `*_files` directories,
`*.quarto_ipynb`, and `.quarto/` are all render INTERMEDIATES: Quarto and
knitr generate every one of them fresh at the start of a render, and remove
or overwrite them again at the end. Because they are regenerated rather than
hand-maintained, they are almost always gitignored -- which is exactly what
makes one look like safe-to-delete clutter to an agent that finds it sitting
in a worktree with no obvious owner. `git status --short` cannot rule out
that a file belongs to a render in progress, because a render's own
intermediates never appear as untracked changes worth reporting -- they are
already ignored. The only way to know a directory is safely idle is to check
for a live process using it, not to check whether the file looks orphaned.

## Why this checks the whole MACHINE, not the worktree

A render process's cwd is not visible from the command being denied, and
grepping for the worktree's own path in `ps` output would miss the ordinary
case: an interactive `quarto preview` launched from a plain terminal, whose
argv is `quarto preview` with no path argument at all (see the incident --
the render was launched from "their own terminal," not from this session).
So `live_render_process()` asks whether ANY render is running anywhere on
the machine, and the deny message tells the agent to confirm the worktree
is unrelated rather than asserting that it is. That is a broader net than
the one worktree at risk, and deliberately so: a false positive here costs
one wait-or-confirm; a false negative reproduces the incident.

## Why this WARNS-as-DENY rather than only adding context

Unlike `no-clobbering-push.py`'s warn path, there is no cheap, ALWAYS-safe
remedy to a git push divergence read as a suggestion -- pushing anyway is a
click away. Here the dangerous action (`rm`) is irreversible the moment it
runs, and the render that reproduces the incident takes ~10 CPU-minutes to
fail. So this DENIES rather than warns, with a single, deliberately
cheap override (`ALLOW_RM_RENDER_INTERMEDIATE=1`) for the case the agent
has actually confirmed the directory is unrelated to the running render.

## Scope

Matches a `rm`, `trash`, `find ... -delete`, or `git clean` invocation (via
`scripts/lib/shellcmd.py`'s argv split, including any interpreter `-c`
piece `shell_c_expansions` can see, and past a leading command WRAPPER --
`sudo`, `timeout`, `nice`, `env`, `command`, ... -- via `_resolve_program`)
whose targets -- non-option arguments for `rm`/`trash`, every token after
`find`, and non-option pathspecs for `git clean` -- name one of the
intermediate families above, by filename suffix or directory-component
match. `git clean` additionally requires no `-n`/`--dry-run` flag, and is
skipped (not matched) with one, since a dry run deletes nothing.

The directory-component match is intentionally COARSE, the same
over-matching trade-off the module docstring's "Why this checks the whole
MACHINE" section already accepts for the process check: `rm -rf
collected_data_files/` (an ordinary directory that happens to end in
`_files`, unrelated to any render) and `find . -newer report.knit.md
-delete` (where `report.knit.md` is a `-newer` REFERENCE file, not what
gets deleted) both match, and both deny when a render happens to be live at
the same moment. Neither is the failure direction this guard exists to
close -- see "Why this WARNS-as-DENY" above for why a false positive here
is the cheap outcome.

Text that merely MENTIONS an intermediate -- inside an `echo`, a `grep`
pattern, a commit message -- never matches, because the match is over
individual argv TOKENS of a parsed `rm`/`trash`/`find`/`git clean`
invocation, not over the raw command string.

Denies only when a live render process is ALSO found; with none, the
deletion is allowed silently, on the same reasoning
`no-heavy-work-on-head-node.py` uses for "already on a compute node -- there
is nothing to fix here."

`live_render_process()` is a free function, replaced wholesale in tests
(`guard.live_render_process = lambda: "..."` / `lambda: None`), the same
seam `no-heavy-work-on-head-node.py`'s `compute_nodes()` uses.

Fails OPEN on any parse trouble, when `scripts/lib/shellcmd.py` cannot be
imported, and when the process check itself cannot run (no `pgrep` on this
machine, or a timeout) -- a guard that cannot look for a live render has no
basis for denying on one.

## Known limitation

`git clean` with no explicit pathspec (`git clean -fdx`) is not matched even
though it may delete intermediates incidentally: this guard's target
extraction, like `rm`'s, only sees pathspecs actually named on the command
line, and a bare invocation names none. Catching that would mean asking
whether the CURRENT directory contains a matching intermediate, which is a
different and heavier check (a filesystem walk from an unknown cwd) than
the text-only match every other branch here uses. Left as a gap rather than
folded in under review pressure, the same call `warn-blanket-worktree-
force-remove.py`'s docstring makes about its own known-limitation section.

`_resolve_program`'s post-wrapper lookahead is bounded by
`WRAPPER_ARG_WINDOW` (6 tokens, imported from `shellcmd.py`), the same bound
`strip_env`/`command_program` already accept for the identical class of
scan. A wrapper carrying 6 or more of its OWN argument tokens ahead of the
real program defeats detection -- measured,
`sudo -u me -H -E -i -n rm paper.rmarkdown` (5 wrapper-option tokens) is not
denied, while `sudo -u me -H rm paper.rmarkdown` (2) is. Unlike the
`git clean -fdx` gap above, there is no principled fix that stays a
text-only match: widening the window only moves the same boundary rather
than removing it, and `shellcmd.py`'s own comment for `WRAPPER_ARG_WINDOW`
gives the reason to leave it shared rather than growing it here alone --
"bounds the scan so an unrelated command running git much later on the
line is not mistaken for a wrapped one."
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (shell_c_expansions, simple_commands, git_subcommand,
                          COMMAND_WRAPPERS, SHELL_KEYWORDS, WRAPPER_ARG_WINDOW)
except Exception as _exc:  # broken install: degrade, do not fail open further
    print(f"no-rm-live-render-intermediate: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); not evaluating",
          file=sys.stderr)
    shell_c_expansions = simple_commands = git_subcommand = None
    COMMAND_WRAPPERS = SHELL_KEYWORDS = frozenset()
    WRAPPER_ARG_WINDOW = 6

import subprocess

OVERRIDE = "ALLOW_RM_RENDER_INTERMEDIATE"
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# The programs whose non-option arguments this guard treats as deletion
# TARGETS. `find` is handled separately below, since its "targets" include
# option VALUES (`-name '*.knit.md'`), not only bare operands.
DELETE_PROGRAMS = {"rm", "trash"}

# Filename SUFFIXES that mark a render intermediate. Checked with `endswith`
# against the final path component, so both a literal name
# (`report.knit.md`) and a simple glob (`*.knit.md`) match -- the asterisk
# is a prefix in the glob case, and `endswith` does not care what precedes
# the suffix.
INTERMEDIATE_SUFFIXES = (".rmarkdown", ".knit.md", ".knit.qmd",
                          ".quarto_ipynb")

# Directory-shaped intermediates, checked against every PATH COMPONENT
# rather than only the final one, since a target may name a file nested
# inside one of these (`paper_files/figure-html/plot-1.png`) rather than
# the directory itself.
INTERMEDIATE_DIR_SUFFIX = "_files"
INTERMEDIATE_DIR_NAME = ".quarto"


def _matches_intermediate(token: str) -> bool:
    """Whether TOKEN (a literal path, or a simple glob naming one) refers to
    a Quarto/knitr render intermediate.

    Deliberately does NOT reject a token starting with `-`: a `_rm_targets`/
    `_git_clean_targets` caller has already filtered those out UNLESS the
    token follows a `--` end-of-options marker, in which case a leading `-`
    is part of a real filename (`rm -- --report.knit.md`) and rejecting it
    here would silently undo that filtering. `_find_targets` passes every
    token after `find`, flags included, relying on this function's own
    suffix/component match to be false for `find`'s own predicate words
    (`-delete`, `-type`, `f`, ...) rather than on a leading-dash check.
    """
    token = token.strip()
    if not token:
        return False
    parts = [p for p in token.rstrip("/").split("/") if p]
    if not parts:
        return False
    last = parts[-1]
    if any(last.endswith(suf) for suf in INTERMEDIATE_SUFFIXES):
        return True
    return any(p.endswith(INTERMEDIATE_DIR_SUFFIX) or p == INTERMEDIATE_DIR_NAME
               for p in parts)


# The program names this guard dispatches on, used by `_resolve_program` to
# find one past a wrapper. `sh`/`bash` are deliberately absent: a nested
# shell is reached instead through `shell_c_expansions`, which analyses it
# as a SEPARATE piece rather than as this argv's own program.
KNOWN_PROGRAMS = {"rm", "trash", "find", "git"}


def _resolve_program(argv):
    """`(index of the program token, override present)` for ARGV.

    Peels leading `VAR=value` assignments (reporting
    `ALLOW_RM_RENDER_INTERMEDIATE=1` among them, since a mention of the
    string elsewhere -- a comment, an unrelated echo -- is not a real
    assignment and does not count) and command WRAPPERS
    (`sudo`, `timeout`, `nice`, `env`, `command`, ...), the same
    `COMMAND_WRAPPERS`/`SHELL_KEYWORDS`/`WRAPPER_ARG_WINDOW` classification
    `scripts/lib/shellcmd.py`'s `strip_env` already uses for `git`
    specifically, generalized here to the four programs this guard cares
    about. Without it, `sudo rm paper.rmarkdown` and
    `timeout 60 git clean -fd paper.knit.md` reached neither the `rm`/`trash`
    nor the `git` branch below, because `argv[0]` was `sudo`/`timeout`
    rather than the program actually invoked -- a silent false negative,
    the dangerous direction for a guard that exists to deny.

    Looking ahead for a token in `KNOWN_PROGRAMS` (rather than "the next
    token that is not an option," which a wrapper's own option VALUE can
    satisfy just as well -- `timeout 60 rm x` would otherwise read `60` as
    the program) mirrors `command_program`'s own lookahead for a shell,
    narrowed to the programs this guard recognizes instead of to a shell.
    `export FOO=1 rm x` is deliberately not specially handled the way
    `strip_env` handles it for `git`: `export` runs nothing, but the loop
    below simply fails to find a known program in its window and returns an
    index past the end of ARGV, which `main`'s `head = argv[lead:]` already
    reads as "nothing to dispatch on."
    """
    i, override, after_wrapper = 0, False, False
    while i < len(argv):
        tok = argv[i]
        if ASSIGNMENT.match(tok):
            if tok == f"{OVERRIDE}=1":
                override = True
            i += 1
            after_wrapper = False
            continue
        if tok in COMMAND_WRAPPERS:
            after_wrapper = True
            i += 1
            continue
        if tok in SHELL_KEYWORDS:
            after_wrapper = False
            i += 1
            continue
        if after_wrapper:
            window = argv[i:i + WRAPPER_ARG_WINDOW]
            hit = next((off for off, cand in enumerate(window)
                        if os.path.basename(cand) in KNOWN_PROGRAMS), None)
            i = i + hit if hit is not None else len(argv)
            break
        break
    return i, override


def _find_targets(argv):
    """Every token after `find` worth matching against an intermediate.

    `find`'s own predicates (`-delete`, `-type`, `f`, `-mtime`, `0`, ...)
    never coincidentally end in one of `INTERMEDIATE_SUFFIXES` or
    `_files`/`.quarto`, so scanning every token -- rather than modelling
    which ones are `-name`/`-path` VALUES versus bare search roots -- finds
    a real target wherever it appears (`find . -name '*.knit.md' -delete`,
    `find .quarto -delete`) without a second parser for `find`'s own
    expression grammar.
    """
    return argv[1:]


def _rm_targets(argv):
    """Non-option arguments of an `rm`/`trash` invocation."""
    targets, end_of_opts = [], False
    for tok in argv[1:]:
        if end_of_opts:
            targets.append(tok)
            continue
        if tok == "--":
            end_of_opts = True
            continue
        if tok.startswith("-") and tok != "-":
            continue
        targets.append(tok)
    return targets


# `git clean`'s only VALUE-TAKING short option. Once `-e`/`--exclude` appears
# in a bundled cluster, every character after it in that SAME token is its
# pattern argument, not a further boolean flag -- so a whole-cluster "does
# this contain the letter n" test is unsound: `-fen` is `-f -e n` (force,
# plus an ignore-pattern of literally "n"), confirmed against real git to
# actually DELETE its target, not skip it. An earlier version of this
# function used exactly that whole-cluster regex and read `-fen` as carrying
# `-n` (dry-run), which made the guard skip a real deletion entirely --
# caught by adversarial review before merge. `_short_cluster_is_dry_run`
# scans left to right and stops at `-e` instead, the same character-by-
# character approach `no-clobbering-push.py`'s `SHORT_BOOL`/`_parse_push`
# already uses to decode a bundled `git push` cluster: a value-taking option
# ends the scan for THAT cluster, it does not merely get skipped over.
_DRY_RUN_VALUE_OPT = "e"


def _short_cluster_is_dry_run(cluster: str) -> bool:
    """Whether short-option CLUSTER (the token with its leading `-` stripped)
    carries `git clean`'s `-n` (dry-run).

    Order matters and is read left to right, matching getopt-style bundling:
    a `n` BEFORE `-e` in the cluster is a real `-n` flag regardless of what
    follows (`-nef` == `-n -e f`, confirmed against real git to be a dry
    run); a `n` AFTER `-e` is part of `-e`'s pattern value, not a flag
    (`-fen` == `-f -e n`, confirmed to delete). Every other character
    (`d`, `f`, `i`, `q`, `x`, `X`, or anything else) is an ordinary boolean
    flag this scan does not need to individually recognize -- only `e`
    (stops the scan) and `n` (dry-run) change what the result is.
    """
    for ch in cluster:
        if ch == _DRY_RUN_VALUE_OPT:
            return False  # everything after this is -e's bundled value
        if ch == "n":
            return True
    return False


def _git_clean_targets(argv):
    """Non-option pathspecs of a `git clean` invocation, or `None` when the
    invocation is a dry run (`-n`/`--dry-run`, including `-n` BUNDLED into a
    short-option cluster like `-fdn`, correctly distinguished from `-e`'s
    bundled pattern value by `_short_cluster_is_dry_run`) and therefore
    deletes nothing.

    An earlier version checked only the exact tokens `"-n"`/`"--dry-run"`,
    which missed `git clean`'s standard bundled short-flag spelling: `git
    clean -fdn` is exactly `git clean -f -d -n`, confirmed against real git
    ("Would remove ..." and nothing actually removed), and denying that
    invocation as though it deletes its target contradicts this file's own
    stated design -- a dry run deletes nothing, so it should never need the
    override.
    """
    sub = git_subcommand(argv)
    if sub is None:
        return None
    subcommand, rest, _env = sub
    if subcommand != "clean":
        return None
    targets, end_of_opts, dry_run = [], False, False
    for tok in rest:
        if end_of_opts:
            targets.append(tok)
            continue
        if tok == "--":
            end_of_opts = True
            continue
        if tok in ("-n", "--dry-run"):
            dry_run = True
            continue
        if tok.startswith("--"):
            continue
        if tok.startswith("-") and tok != "-":
            if _short_cluster_is_dry_run(tok[1:]):
                dry_run = True
            continue
        targets.append(tok)
    if dry_run:
        return None
    return targets


def _matching_deletion(command):
    """`(display_segment, matched_target)` for the first deletion in COMMAND
    that targets a render intermediate, honouring an inline override on that
    same simple command -- or `None`.

    Every piece `shell_c_expansions` can see (the command itself, plus any
    interpreter `-c` argument reachable from it) is scanned, since a
    deletion wrapped in `sh -c "..."` is just as real as a bare one.
    """
    if shell_c_expansions is None or simple_commands is None:
        return None
    for piece in shell_c_expansions(command):
        argvs = simple_commands(piece)
        if argvs is None:
            continue
        for argv in argvs:
            lead, override = _resolve_program(argv)
            head = argv[lead:]
            if not head:
                continue
            program = os.path.basename(head[0])

            if program in DELETE_PROGRAMS:
                targets = _rm_targets(head)
            elif program == "find" and "-delete" in head[1:]:
                targets = _find_targets(head)
            elif program == "git":
                targets = _git_clean_targets(head)
                if targets is None:
                    continue
            else:
                continue

            if override:
                continue

            for target in targets:
                if _matches_intermediate(target):
                    return " ".join(argv), target
    return None


# The programs and argument shapes `live_render_process` looks for. `pgrep`
# does its own coarse text match first (so the subprocess call costs
# nothing extra to broaden), and `_is_render_line` then classifies each
# matching line precisely -- two passes rather than trusting `pgrep`'s own
# regex engine to encode the exact shape, which differs across platforms.
PGREP_FILTER = "quarto|rmarkdown|knitr|rmd_render|deno"

# `quarto render`/`quarto preview`, wherever `quarto` sits on PATH: a
# `pgrep -fl` line is always `"<pid> <full argv>"`, so the program token
# never sits at the START of the line, and never checking for that would be
# the bug this pattern must not repeat.
_QUARTO_RE = re.compile(r"quarto\s+(render|preview)\b", re.IGNORECASE)
_QUARTO_JS_RE = re.compile(r"quarto\.js", re.IGNORECASE)
_DENO_RENDER_RE = re.compile(r"\bdeno\b.*\brender\b", re.IGNORECASE)

# `R`/`Rscript` running knitr/rmarkdown, matched as two SEPARATE
# case-SENSITIVE word-boundary checks against the whole line rather than one
# combined, order-dependent, case-INSENSITIVE pattern. An earlier version
# anchored `R`/`Rscript` to start-of-line or right after a `/`
# (`r"(?:^|/)(?:R|Rscript)\b..."`), which never matches a bare,
# PATH-resolved `pgrep -fl` line at all -- the PID prefix means an ordinary
# `Rscript -e 'rmarkdown::render(...)'` from a terminal, exactly the
# incident this guard exists for, never sits at the line's start or right
# after a `/`. Measured against `"12345 Rscript -e knitr::knit('report.Rmd')"`:
# the anchored form does not match; a plain `\bRscript\b` does. Kept
# case-sensitive (rather than folded into the `re.IGNORECASE` the other
# three patterns use) because `R` in particular is a real, common word when
# lowercased, and this pattern's whole job is distinguishing the
# capital-letter INTERPRETER from prose that happens to mention rendering.
_R_INVOCATION_RE = re.compile(r"\b(?:R|Rscript)\b")
_R_RENDER_LIB_RE = re.compile(r"\b(?:knitr|rmarkdown|rmd_render)\b", re.IGNORECASE)


def _is_render_line(line: str) -> bool:
    """Whether LINE (one `pgrep -fl` result) names a live Quarto/knitr
    render process."""
    if _QUARTO_RE.search(line) or _QUARTO_JS_RE.search(line):
        return True
    if _DENO_RENDER_RE.search(line):
        return True
    return bool(_R_INVOCATION_RE.search(line) and _R_RENDER_LIB_RE.search(line))


def live_render_process(timeout=5):
    """A short `pid  command` description of a running Quarto/knitr render
    process, or `None` if none is found (or the check could not run at
    all -- fails open, like the rest of this guard).

    Replaced wholesale in tests, the same seam
    `no-heavy-work-on-head-node.py`'s `compute_nodes()` uses, because a
    guard whose only path to a verdict is "spawn `pgrep`" cannot be tested
    for both branches without either a real render running or a stub.
    """
    try:
        out = subprocess.run(
            ["pgrep", "-fl", PGREP_FILTER],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None  # no pgrep here; cannot prove a render is running
    # pgrep exits 1 when nothing matches its own filter -- a normal outcome,
    # not a failure. Anything else (2: usage error, 3: fatal error) means the
    # check did not run and this fails open the same way a missing binary
    # does.
    if out.returncode not in (0, 1):
        return None
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and _is_render_line(line):
            return line
    return None


DENY = (
    "This deletes `{target}`, which matches a Quarto/knitr render "
    "intermediate ({family}). A live render process is running:\n\n"
    "    {process}\n\n"
    "  command:  {segment}\n\n"
    "Quarto and knitr RECREATE this kind of file at the START of every "
    "render, not only at the end, so what looks like an orphaned leftover "
    "may belong to the render above -- deleting it out from under that "
    "render can make a long-running render (chunks already knitted, caches "
    "already rebuilt) fail partway through with a missing-file error, with "
    "no way to tell from the deletion alone that a render was using it.\n\n"
    "`git status --short` cannot rule this out: files in this family are "
    "almost always gitignored, so a render's own intermediates never show "
    "up as untracked changes worth reporting.\n\n"
    "Wait for the render above to finish, or confirm -- by checking the "
    "process's own working directory or arguments -- that it is not using "
    "this worktree or directory, before deleting.\n\n"
    "If you have already confirmed that, clear this with:\n\n"
    "    {override}=1 {segment}"
)


def _family(target: str) -> str:
    parts = [p for p in target.rstrip("/").split("/") if p]
    last = parts[-1] if parts else target
    for suf in INTERMEDIATE_SUFFIXES:
        if last.endswith(suf):
            return suf
    if any(p == INTERMEDIATE_DIR_NAME for p in parts):
        return INTERMEDIATE_DIR_NAME + "/"
    return "*" + INTERMEDIATE_DIR_SUFFIX


def _read_payload():
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin.

    Same shape as `no-heavy-work-on-head-node.py`'s `_read_payload` and
    `warn-blanket-worktree-force-remove.py`'s, kept local rather than
    shared because each of the three copies predates a payload-reading
    module and none is large enough on its own to justify extracting one
    here ahead of the eight-hook `_simple_commands` migration
    (ai-config#3178) this file's own splitter reuse already rides on.
    """
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
        print(f"no-rm-live-render-intermediate: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    # Multiple tool-name spellings and command-field names, the same set
    # `no-heavy-work-on-head-node.py` and `warn-blanket-worktree-force-
    # remove.py` accept, so an adapter mapping another harness's event onto
    # this shared script (`plugins/ai-config/claude-hook-adapter.py`,
    # per AGENTS.md) is not silently inert here.
    if payload.get("tool_name") not in ("Bash", "bash", "run_command",
                                        "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = (inp.get("command") or inp.get("CommandLine")
               or inp.get("cmd") or inp.get("script") or "")

    hit = _matching_deletion(command)
    if not hit:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    process = live_render_process()
    if not process:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    segment, target = hit
    reason = DENY.format(target=target, family=_family(target), process=process,
                         segment=segment, override=OVERRIDE)
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
