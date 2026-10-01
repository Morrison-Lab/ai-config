#!/usr/bin/env python3
"""PreToolUse guard: warn when a GitHub MCP file write would shrink a file.

`mcp__github__create_or_update_file` and `mcp__github__push_files` have no
patch mode: every call replaces a file's WHOLE content. A write can therefore
be internally consistent (the `content` sent is what the caller meant to send)
and still be a stale or partial reconstruction far smaller than what is live on
the branch. That is what happened on ai-config#4134: a ~187KB memory file was
rebuilt from chat-context chunks and pushed smaller more than once across
several compaction cycles before anyone noticed. The size checks in
memories/github-mcp-tools.md compare against the intended source, which a
partial reconstruction passes.

For each file write this hook fetches the live size of the path on the target
branch (`gh api repos/O/R/contents/PATH?ref=BRANCH`) and compares it with the
byte length of the new `content` (plaintext for both tools).

Thresholds (module constants, env-overridable). A write is flagged when the
live file is at least MIN_LIVE_BYTES and either
  * the new content is more than SHRINK_RATIO smaller (default 0.5), or
  * the live file is over LARGE_BYTES (default 10240) and the new content is
    more than LARGE_SHRINK_RATIO smaller (default 0.2).
Rationale: a routine edit rarely deletes half a file, so 50% has almost no
false positives; a large file is the case where a partial rebuild is easy to
make and costly to miss, and 20% of 10KB is still 2KB of content gone, which
a one-line confirmation should cover. The MIN_LIVE_BYTES floor (default 512)
keeps a trivial rewrite of a tiny file from warning. Overrides:
WRITE_SHRINK_RATIO, WRITE_SHRINK_LARGE_RATIO, WRITE_SHRINK_LARGE_BYTES,
WRITE_SHRINK_MIN_BYTES.

WARNS rather than denies (ai-config#4169 asks for "at minimum flags loudly"):
a deliberate large deletion is legitimate and this hook cannot read intent.
Fails OPEN: a new file (404), a lookup error, a timeout, or a missing `gh`
never blocks; a failed lookup (not a 404) is reported as a visible note so the
silence is not mistaken for a pass.

NOT done: item 4 of the issue (re-fetch and report the size delta after the
write). It needs a PostToolUse hook that re-derives the target from the tool
response; left to a follow-up so this PR stays small.
"""

import json
import os
import subprocess
import sys
import time
import urllib.parse

TOOLS = ("mcp__github__create_or_update_file", "mcp__github__push_files")
MAX_LOOKUPS = 12
LOOKUP_TIMEOUT = 8
# One shared deadline for ALL lookups in a call, so the hook finishes and emits
# its fail-open note before the 60 s timeout hooks.json gives it. Without it
# MAX_LOOKUPS x LOOKUP_TIMEOUT could reach 96 s and the harness would kill the
# hook silently. Env-overridable (WRITE_SHRINK_BUDGET, WRITE_SHRINK_MAX_LOOKUPS).
TOTAL_BUDGET = 40.0


def _num(name, default, cast):
    try:
        return cast(os.environ.get(name, default))
    except (TypeError, ValueError):
        return cast(default)


def thresholds():
    return {
        "ratio": _num("WRITE_SHRINK_RATIO", 0.5, float),
        "large_ratio": _num("WRITE_SHRINK_LARGE_RATIO", 0.2, float),
        "large_bytes": _num("WRITE_SHRINK_LARGE_BYTES", 10240, int),
        "min_bytes": _num("WRITE_SHRINK_MIN_BYTES", 512, int),
    }


def writes(tool, inp):
    """Yield (path, content) for every whole-file write the call makes."""
    if tool == "mcp__github__create_or_update_file":
        path, content = inp.get("path"), inp.get("content")
        if isinstance(path, str) and isinstance(content, str):
            yield path, content
    elif tool == "mcp__github__push_files":
        for f in inp.get("files") or []:
            if (
                isinstance(f, dict)
                and isinstance(f.get("path"), str)
                and isinstance(f.get("content"), str)
            ):
                yield f["path"], f["content"]


def live_size(owner, repo, path, branch, timeout=LOOKUP_TIMEOUT):
    """Return (size, note). size None with note None means a new file."""
    api = f"repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}"
    if branch:
        api += "?ref=" + urllib.parse.quote(branch, safe="")
    cmd = ["gh", "api", api, "--jq", ".size"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{path}: lookup failed ({type(exc).__name__})"
    if proc.returncode != 0:
        if "404" in proc.stderr or "Not Found" in proc.stderr:
            return None, None
        return None, f"{path}: lookup failed (gh exit {proc.returncode})"
    try:
        return int(proc.stdout.strip()), None
    except ValueError:
        return None, f"{path}: lookup returned no size"


def shrunk(live, new, t):
    """True when the write shrinks the file past a threshold."""
    if live < t["min_bytes"] or new >= live:
        return False
    drop = (live - new) / live
    if drop > t["ratio"]:
        return True
    return live > t["large_bytes"] and drop > t["large_ratio"]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name") or ""
    if tool not in TOOLS:
        return 0
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    owner, repo = inp.get("owner"), inp.get("repo")
    if not (isinstance(owner, str) and isinstance(repo, str)):
        return 0
    branch = inp.get("branch") if isinstance(inp.get("branch"), str) else None
    t = thresholds()
    flagged, notes = [], []
    try:
        deadline = time.monotonic() + _num("WRITE_SHRINK_BUDGET", TOTAL_BUDGET, float)
        cap = _num("WRITE_SHRINK_MAX_LOOKUPS", MAX_LOOKUPS, int)
        items = list(writes(tool, inp))
        for i, (path, content) in enumerate(items):
            if i >= cap:
                notes.append(f"only the first {cap} files were checked")
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                notes.append(
                    f"time budget exhausted; {len(items) - i} file(s) not checked"
                )
                break
            live, note = live_size(
                owner, repo, path, branch, min(LOOKUP_TIMEOUT, remaining)
            )
            if note:
                notes.append(note)
            if live is None:
                continue
            new = len(content.encode("utf-8"))
            if shrunk(live, new, t):
                flagged.append((path, live, new))
    except Exception as exc:
        notes.append(f"shrink check aborted ({type(exc).__name__})")
    if not flagged and not notes:
        return 0
    lines = [
        f"- {path}: live {live} bytes, new content {new} bytes "
        f"({100 * (live - new) / live:.0f}% smaller)"
        for path, live, new in flagged
    ]
    parts = []
    if flagged:
        parts.append(
            "SHRINK WARNING: this write replaces the WHOLE file and is "
            "substantially smaller than what is live on the branch:\n"
            + "\n".join(lines)
            + "\n\nA partial or stale reconstruction looks identical to a "
            "deliberate cut (ai-config#4134, #4169). Confirm the deletion is "
            "intended, or rebuild from the live content, before proceeding."
        )
    if notes:
        parts.append(
            "Shrink check could not fully run (fail-open, write not blocked): "
            + "; ".join(notes)
        )
    text = "\n\n".join(parts)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": text,
        }
    }
    # Antigravity prints additionalContext AND systemMessage, so warn once there.
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = text.split("\n\n")[0][:600]
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
