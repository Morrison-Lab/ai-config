#!/usr/bin/env python3
"""PostToolUse guard: untracked files listed by a checkout that is behind upstream.

A `git status` run in a checkout that is BEHIND its upstream and that lists
untracked files tells the reader less than it seems to. The untracked paths
may already exist upstream: the checkout has not pulled them, so git sees a
file on disk that its own (stale) HEAD does not track.

Incident, 2026-10-07 (mlr): an agent ran `git status -sb` in the user's main
checkout. The output began `## main...origin/main [behind 23]` and listed
`?? books/mcs.pdf`, `?? books/mml-book.pdf` and others. The agent told the
user the files were new and needed adding. They were byte-identical to files
already on origin/main, uploaded through the GitHub web interface; the
checkout had simply not pulled.

The condition is decidable from the command output alone. When a `git status`
reports the checkout behind (`[behind N]` in `-sb` form, `Your branch is
behind` in long form) AND lists untracked files, this hook adds context naming
the count and the check that settles it: `git fetch`, then
`git ls-tree -r --name-only origin/<branch> -- <paths>` or
`git cat-file -e origin/<branch>:<path>`.

Also reads `--porcelain=v2 -b` (`# branch.ab +0 -N`, `? path`). Limit: the
behind count comes from the local remote-tracking ref, so a checkout that
has not fetched recently reports up to date and stays silent.

WARNS, never blocks: PostToolUse runs after the command, and the files may
well be new. It only ever adds `additionalContext`. Fails OPEN (exit 0, no
output) on any parse trouble, a non-Bash tool, a command that is not a
`git ... status`, or a response with no stdout.
"""
import json
import re
import shlex
import sys

MAX_PATHS = 10
SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "a": "\a", "b": "\b", "f": "\f",
                  "r": "\r", "v": "\v"}

# `git status`, tolerating global options before the subcommand (`git -C d status`).
# `status` must be the subcommand: only option tokens may sit between.
# Each token has exactly one parse, so matching cannot backtrack
# exponentially: `-C`/`-c` and `--git-dir`/`--work-tree`/`--namespace` take a
# separate value (quoted, or starting with a non-quote character, so the value
# branches are disjoint), other long options are `--name[=value]` (the lookahead
# keeps the three value-taking names out of that branch), other short flags
# take none. A value may be quoted (`git -C "my dir" status`).
_VAL = r"(?:\"[^\"]*\"|'[^']*'|[^\s\"']\S*)"
RX_GIT_STATUS = re.compile(
    r"(?<![\w-])git(?:\s+(?:-[Cc]\s+" + _VAL
    + r"|--(?:git-dir|work-tree|namespace)\s+" + _VAL
    + r"|--(?!(?:git-dir|work-tree|namespace)(?![\w=-]))[A-Za-z][\w-]*(?:=\S+)?"
    + r"|-[A-BD-Za-bd-z]))*\s+status\b"
)

# `-sb` / `--porcelain -b` header: `## main...origin/main [behind 23]`,
# `## main...origin/main [ahead 2, behind 23]`. Plain `ahead` has no "behind".
RX_SHORT_BEHIND = re.compile(
    r"^## (?P<local>\S+?)(?:\.\.\.(?P<up>\S+))?"
    r" \[(?:ahead \d+, )?behind (?P<n>\d+)\]",
    re.M,
)
# Long form: "Your branch is behind 'origin/main' by 23 commits, ..."
RX_LONG_BEHIND = re.compile(
    r"Your branch is behind '(?P<up>[^']+)' by (?P<n>\d+) commits?"
)
# Long form, diverged: "and have 2 and 23 different commits each, respectively."
RX_LONG_DIVERGED = re.compile(
    r"Your branch and '(?P<up>[^']+)' have diverged,\s+and have \d+ and "
    r"(?P<n>\d+) different commits? each"
)
# `--porcelain=v2 -b`: `# branch.ab +0 -23`, `# branch.upstream origin/main`.
RX_V2_AB = re.compile(r"^# branch\.ab \+\d+ -(?P<n>\d+)$", re.M)
RX_V2_UP = re.compile(r"^# branch\.upstream (?P<up>\S+)$", re.M)

# `?? path` (short/porcelain v1) and `? path` (porcelain v2).
RX_SHORT_UNTRACKED = re.compile(r"^\?\??  ?(?P<path>.+)$", re.M)
RX_LONG_UNTRACKED_HEAD = re.compile(r"^Untracked files:\s*$", re.M)


def behind_info(text):
    """Return (count, upstream-or-None) when `text` reports a behind checkout."""
    m = RX_SHORT_BEHIND.search(text)
    if m:
        return int(m.group("n")), m.group("up")
    for rx in (RX_LONG_BEHIND, RX_LONG_DIVERGED):
        m = rx.search(text)
        if m:
            return int(m.group("n")), m.group("up")
    m = RX_V2_AB.search(text)
    if m and int(m.group("n")) > 0:
        up = RX_V2_UP.search(text)
        return int(m.group("n")), up.group("up") if up else None
    return None


def untracked_paths(text):
    """Paths listed as untracked, in either output form."""
    paths = [m.group("path").strip() for m in RX_SHORT_UNTRACKED.finditer(text)]
    head = RX_LONG_UNTRACKED_HEAD.search(text)
    if head:
        for line in text[head.end():].splitlines():
            if not line.strip():
                if paths:
                    break
                continue
            if line.startswith("\t"):
                paths.append(line.strip())
            elif not line.lstrip().startswith("("):
                break
    return paths


def stdout_of(payload):
    resp = payload.get("tool_response")
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        out = resp.get("stdout")
        if isinstance(out, str):
            return out
    return ""


def unquote_path(path):
    """Undo git's C-style quoting (a name with a space or non-ASCII bytes)."""
    if not (len(path) > 1 and path[0] == path[-1] == '"'):
        return path
    body = path[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\" or i + 1 >= len(body):
            out += ch.encode("utf-8")
            i += 1
        elif body[i + 1] in "01234567":
            j = i + 1
            while j < min(i + 4, len(body)) and body[j] in "01234567":
                j += 1
            out.append(int(body[i + 1:j], 8) & 0xFF)
            i = j
        else:
            out += SIMPLE_ESCAPES.get(body[i + 1], body[i + 1]).encode("utf-8")
            i += 2
    return out.decode("utf-8", errors="replace")


def build_message(count, upstream, paths):
    ref = upstream or "origin/<branch>"
    shown = paths[:MAX_PATHS]
    listed = " ".join(shlex.quote(unquote_path(p)) for p in shown)
    more = f" (and {len(paths) - len(shown)} more)" if len(paths) > len(shown) else ""
    plural = "commit" if count == 1 else "commits"
    return (
        f"This checkout is {count} {plural} behind {ref}, so the untracked "
        f"path(s) it lists may already exist upstream: {listed}{more}. A "
        "stale checkout shows a file it has not pulled as untracked. Before "
        "calling them new or adding them, run `git fetch`, then "
        f"`git ls-tree -r --name-only {ref} -- {listed}` (or "
        f"`git cat-file -e {ref}:<path>` per path). Only a path absent from "
        "that listing is new. Paths are as `git status` printed them: "
        "relative to the current directory in `-s`/long form, to the "
        "repository root in `--porcelain`. `ls-tree` pathspecs are "
        "cwd-relative and `cat-file` paths are root-relative, so adjust. "
        "The behind count is only as fresh as the last fetch."
    )


def main():
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") != "Bash":
            return 0
        command = (payload.get("tool_input") or {}).get("command") or ""
        if not RX_GIT_STATUS.search(command):
            return 0
        text = stdout_of(payload)
        info = behind_info(text)
        if info is None:
            return 0
        paths = untracked_paths(text)
        if not paths:
            return 0
        count, upstream = info
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": build_message(count, upstream, paths),
            },
        }))
    except Exception:  # fail open: a warning hook must never break a tool call
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
