#!/usr/bin/env python3
"""PreToolUse: refuse copying a file from one repository checkout into another.

Ezra, 2026-11-16: "don't copy; decompose" (#5709, shared/principles/dont-copy-decompose.md).
Denies a Write of a NEW file sharing at least MIN_LINES meaningful lines (stripped, over
3 chars), and at least MIN_SHARE of its own, with a same-named file in a sibling repository.
A repository is identified by its COMMON git dir, so a linked worktree is the
same repository as its main checkout, and siblings are listed beside the main
checkout. Not judged: Edit, MultiEdit and a Write over an existing file (they
change a file rather than create a copy); vendored paths (EXEMPT_PATH), which a
sync workflow should write; a thin caller of a `gha` reusable workflow, which
is the decomposed form; a copy within one repo, which is not compared (see the fragment).
A line comment `decompose: allow <reason>` passes (`<!--` only in Markdown, where `#` is a heading).
Bash: a `cp`, `rsync` or `install` (top level or inside `sh -c`) that copies a FILE
of MIN_LINES or more from one repository to a NEW path in another is denied, unless
the command carries `# decompose: allow <reason>` as a shell comment. Passes: a
remote operand (`host:path`), an existing destination, `install -d`, a directory
source, a path behind `$VAR` or a backtick, and a relative path inside `sh -c`
(its working directory after an outer `cd` is not tracked), which this scan cannot name.
Fails OPEN and SILENT on any parse trouble, and stops after TIME_BUDGET.
"""
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"))
try:
    from shellcmd import (COMMAND_WRAPPERS, WRAPPER_ARG_WINDOW, _comment_free, resolve_cd_target,
                          shell_c_expansions, simple_commands_with_scope, strip_env)
except Exception:  # broken install: the Bash branch checks nothing, the Write branch still runs
    shell_c_expansions = None

MIN_LINES = 15
MIN_SHARE = 0.7
MAX_SIBLINGS = 80
MAX_BYTES = 1_000_000
TIME_BUDGET = 6.0
ALLOW = re.compile(r"^\s*(?:#|<!--|//|/\*|--|%|;)\s*decompose:\s*allow\s+\S", re.I | re.M)
ALLOW_MD = re.compile(r"^\s*<!--\s*decompose:\s*allow\s+\S", re.I | re.M)
MARKDOWN = re.compile(r"\.(?:md|qmd|rmd|markdown)$", re.I)
WORKFLOW_PATH = re.compile(r"(?:^|/)\.github/workflows/[^/]+\.ya?ml$")
CALLER = re.compile(r"^\s*uses:\s*Morrison-Lab/gha/\.github/workflows/", re.M | re.I)
STEP = re.compile(r"^\s*(?:-\s*)?(?:run|steps):", re.M)
EXEMPT_PATH = re.compile(
    r"(?:^|/)(?:_extensions|vendor|node_modules)/|(?:^|/)shared/vendored/"
    r"|(?:^|/)(?:LICEN[CS]E|COPYING)(?:\.[A-Za-z]+)?$",
    re.I,
)
ALLOW_SH = re.compile(r"#\s*decompose:\s*allow\s+\S", re.I)
REMOTE = re.compile(r"^[^/]*:")
COPIERS = {  # program: (short options taking a value, long options taking a value)
    "cp": ("tS", {"--target-directory", "--suffix"}),
    "install": ("mogSt", {"--mode", "--owner", "--group", "--suffix", "--target-directory", "--strip-program"}),
    "rsync": ("efBTM@", {
        "--rsh", "--exclude", "--include", "--filter", "--exclude-from", "--include-from", "--files-from",
        "--chmod", "--chown", "--block-size", "--temp-dir", "--partial-dir", "--backup-dir", "--suffix",
        "--compare-dest", "--copy-dest", "--link-dest", "--log-file", "--log-file-format", "--password-file",
        "--max-size", "--min-size", "--bwlimit", "--timeout", "--contimeout", "--port", "--rsync-path",
        "--out-format", "--remote-option", "--usermap", "--groupmap", "--iconv", "--info", "--debug",
        "--modify-window", "--max-delete", "--sockopts", "--skip-compress", "--outbuf", "--address",
        "--write-batch", "--only-write-batch", "--read-batch", "--protocol", "--checksum-choice",
        "--compress-choice", "--compress-level", "--stop-after", "--stop-at", "--mkpath-mode"}),
}
REASON = (
    "[hook: no-cross-repo-copy] {what}\n\nEzra, 2026-11-16: \"don't copy; decompose\" "
    "(shared/principles/dont-copy-decompose.md). Factor the shared part into one component "
    "both repositories call, the original included (a `Morrison-Lab/gha` reusable workflow, "
    "a package function, or one canonical file), with what differs as inputs. A move (port) "
    "or a copy that truly cannot be shared passes with a line comment `decompose: allow <reason>` in the file's own syntax "
    "(for a shell copy, a `# decompose: allow <reason>` comment on the command)."
)


def common_dir(path):
    """(checkout root, realpath of its common git dir) for `path`, or (None, None)."""
    cur = os.path.abspath(path)
    while True:
        dotgit = os.path.join(cur, ".git")
        if os.path.isdir(dotgit):
            return cur, os.path.realpath(dotgit)
        if os.path.isfile(dotgit):
            with open(dotgit, encoding="utf-8") as fh:
                line = fh.readline().strip()
            gitdir = os.path.join(cur, line[len("gitdir:"):].strip()) if line.startswith("gitdir:") else ""
            common = os.path.join(gitdir, "commondir")
            if os.path.isfile(common):
                with open(common, encoding="utf-8") as fh:
                    gitdir = os.path.join(gitdir, fh.read().strip())
            return cur, os.path.realpath(gitdir) if gitdir else None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None, None
        cur = parent


def meaningful_lines(text):
    return [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 3]


def shared_lines(new_lines, old_text):
    """Lines of `new_lines` also in `old_text`, counted as a multiset."""
    return sum((Counter(new_lines) & Counter(meaningful_lines(old_text))).values())


def is_caller(path, text):
    """A workflow that only calls gha reusable workflows: no job has `steps:` or `run:`."""
    return bool(WORKFLOW_PATH.search(path) and CALLER.search(text)) and not STEP.search(text)


def allowed(path, text):
    return bool((ALLOW_MD if MARKDOWN.search(path) else ALLOW).search(text))


def sibling_roots(common):
    """Main checkouts beside this repository's main checkout (none for a submodule)."""
    if os.path.basename(common) != ".git":
        return []
    main = os.path.dirname(common)
    parent = os.path.dirname(main)
    try:
        cands = [os.path.join(parent, n) for n in sorted(os.listdir(parent))]
    except OSError:
        return []
    return [c for c in cands if c != main and os.path.isdir(os.path.join(c, ".git"))][:MAX_SIBLINGS]


def same_name_files(sib, basename, deadline):
    try:
        res = subprocess.run(
            ["git", "-C", sib, "ls-files", "-z", "--", basename, "*/" + basename],
            capture_output=True, timeout=max(0.5, deadline - time.monotonic()), check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [os.path.join(sib, p) for p in res.stdout.decode("utf-8", "replace").split("\0") if p]


def copied_source(path, content):
    """Path of a sibling-repo file that new file `content` mostly repeats, or None."""
    root, common = (None, None) if os.path.exists(path) else common_dir(os.path.dirname(path))
    if not common:
        return None
    rel = os.path.relpath(path, root).replace(os.sep, "/")  # so a checkout under vendor/ is not exempt
    new_lines = meaningful_lines(content)
    if (len(new_lines) < MIN_LINES or EXEMPT_PATH.search(rel) or allowed(rel, content)
            or is_caller(rel, content)):
        return None
    deadline = time.monotonic() + TIME_BUDGET
    for sib in sibling_roots(common):
        if time.monotonic() > deadline:
            return None
        for cand in same_name_files(sib, os.path.basename(path), deadline):
            if time.monotonic() > deadline:
                return None
            try:
                if os.path.getsize(cand) > MAX_BYTES:
                    continue
                with open(cand, encoding="utf-8", errors="replace") as fh:
                    hits = shared_lines(new_lines, fh.read())
            except OSError:
                continue
            if hits >= MIN_LINES and hits / len(new_lines) >= MIN_SHARE:
                return cand
    return None


def copy_operands(argv):
    """(operands, -t target or None, -T given, install -d given) for one copier argv."""
    prog = os.path.basename(argv[0])
    shorts, longs = COPIERS[prog]
    ops, target, no_tdir, dirmode, dashdash, i = [], None, False, False, False, 1
    while i < len(argv):
        arg = argv[i]
        i += 1
        if dashdash or arg == "-" or not arg.startswith("-"):
            ops.append(arg)
        elif arg == "--":
            dashdash = True
        elif arg.startswith("--"):
            name, eq, val = arg.partition("=")
            if name in longs and not eq:
                val, i = (argv[i] if i < len(argv) else ""), i + 1
            target = val if name == "--target-directory" else target
            no_tdir |= name == "--no-target-directory"
            dirmode |= prog == "install" and name == "--directory"
        else:
            for k, ch in enumerate(arg[1:], 1):
                if ch in shorts:
                    val = arg[k + 1:]
                    if not val:
                        val, i = (argv[i] if i < len(argv) else ""), i + 1
                    target = val if ch == "t" else target
                    break
                no_tdir |= ch == "T" and prog != "rsync"
                dirmode |= ch == "d" and prog == "install"
    return ops, target, no_tdir, dirmode


def resolve(path, cwd):
    """Absolute form of `path`, or None when it hides behind an expansion or no cwd is known."""
    path = os.path.expanduser(path)
    if "$" in path or "`" in path:
        return None
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(cwd, path)) if cwd else None


def copy_pairs(argv, cwd):
    """(source file, destination file) pairs that one copier argv writes."""
    ops, target, no_tdir, dirmode = copy_operands(argv)
    explicit = target is not None
    if dirmode or (not explicit and len(ops) < 2):
        return []
    if not explicit:
        target, ops = ops[-1], ops[:-1]
    if any(REMOTE.match(p) for p in [*ops, target]):
        return []
    paths = [resolve(p, cwd) for p in [*ops, target]]
    if None in paths:
        return []
    *srcs, dst = paths
    into = not no_tdir and (explicit or len(srcs) > 1 or target.endswith("/") or os.path.isdir(dst))
    return [(s, os.path.join(dst, os.path.basename(s)) if into else dst) for s in srcs if os.path.isfile(s)]


def copier_argv(argv):
    """`argv` from its copier program on, or None when it runs no cp, rsync or install."""
    _env, rest = strip_env(argv)
    window = rest[:WRAPPER_ARG_WINDOW] if rest and rest[0] in COMMAND_WRAPPERS | {"sudo"} else rest[:1]
    hit = next((k for k, tok in enumerate(window) if os.path.basename(tok) in COPIERS), None)
    return None if hit is None else rest[hit:]


def piece_copies(piece, cwd):
    """Every (source, destination) one command line copies, following its `cd`s per subshell."""
    dirs = {(0,): cwd}
    for scope, argv in simple_commands_with_scope(piece) or []:
        here = next((dirs[scope[:n]] for n in range(len(scope), 0, -1) if scope[:n] in dirs), None)
        rest = strip_env(argv)[1]
        if rest and rest[0] in ("cd", "pushd", "popd"):
            moved = resolve_cd_target(rest, here)
            dirs[scope] = moved if moved and (here or os.path.isabs(moved)) else None
            continue
        cmd = copier_argv(argv)
        yield from copy_pairs(cmd, here) if cmd else []


def shell_copy(command, cwd):
    """(source, destination) of a copy into a new file of another repository, or None."""
    if shell_c_expansions is None or (ALLOW_SH.search(command) and not ALLOW_SH.search(_comment_free(command))):
        return None
    deadline = time.monotonic() + TIME_BUDGET
    for depth, piece in enumerate(shell_c_expansions(command)):
        for src, dst in piece_copies(piece, cwd if depth == 0 else None):
            if time.monotonic() > deadline:
                return None
            if os.path.exists(dst) or os.path.getsize(src) > MAX_BYTES:
                continue
            with open(src, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            src_repo = common_dir(os.path.dirname(src))[1]
            dst_root, dst_repo = common_dir(os.path.dirname(dst))
            rel = os.path.relpath(dst, dst_root).replace(os.sep, "/") if dst_repo else ""
            if (src_repo and dst_repo and src_repo != dst_repo and len(meaningful_lines(text)) >= MIN_LINES
                    and not EXEMPT_PATH.search(rel) and not is_caller(rel, text)):
                return src, dst
    return None


def verdict(payload):
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    if payload.get("tool_name") == "Write" and isinstance(inp.get("content"), str):
        path = str(inp.get("file_path") or "")
        src = path and copied_source(path, inp["content"])
        return src and f"New file `{path}` repeats most of `{src}`, a file in another repository."
    if payload.get("tool_name") == "Bash" and isinstance(inp.get("command"), str):
        hit = shell_copy(inp["command"], str(payload.get("cwd") or "") or None)
        return hit and f"The command copies `{hit[0]}` to `{hit[1]}`, a new file in another repository."
    return None


def main() -> int:
    try:
        what = verdict(json.load(sys.stdin))
    except Exception:
        return 0
    if not what:
        return 0
    reason = REASON.format(what=what)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": reason,
        },
        "systemMessage": "Blocked: don't copy a file between repositories; decompose it into a shared component.",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
