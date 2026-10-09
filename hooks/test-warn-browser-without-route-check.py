#!/usr/bin/env python3
"""Tests for warn-browser-without-route-check.py."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "warn-browser-without-route-check.py")

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def transcript(entries):
    """entries: ('user', text) | ('tool_result',) | (tool_name, input_dict)."""
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8")
    last_id = None
    for n, e in enumerate(entries):
        if e[0] == "user":
            rec = {"type": "user", "message": {"role": "user", "content": e[1]}}
            if len(e) > 2:
                rec.update(e[2])
        elif e[0] == "tool_result":
            rec = {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": last_id,
                 "content": "ok"}]}}
        else:
            last_id = f"toolu_{n}"
            rec = {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": last_id, "name": e[0],
                 "input": e[1]}]}}
        fh.write(json.dumps(rec) + "\n")
    fh.close()
    return fh.name


def run(tool_name, tool_input, entries=None, path=None):
    if path is None:
        path = transcript(entries or [("user", "do the task")])
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input,
                          "transcript_path": path})
    proc = subprocess.run([sys.executable, HOOK], input=payload,
                          capture_output=True, text=True, timeout=10)
    out = proc.stdout.strip()
    check(f"exit code for {tool_name} {tool_input}", proc.returncode, 0)
    return json.loads(out) if out else None


def warns(label, *a, **kw):
    out = run(*a, **kw)
    ok = bool(out) and "browser-last-resort.md" in out.get("systemMessage", "") \
        and set(out) == {"systemMessage"}
    check(label, ok, True)


def silent(label, *a, **kw):
    check(label, run(*a, **kw), None)


GA = {"url": "https://analytics.google.com/analytics/web/#/admin"}
USER = ("user", "change the GA settings")

# ---- positives: each trigger tool, no route search
warns("chrome navigate", "mcp__claude-in-chrome__navigate", GA)
warns("builtin navigate", "mcp__Claude_Browser__navigate", GA)
warns("preview_start with url", "mcp__Claude_Browser__preview_start", GA)
warns("request_access Chrome", "mcp__computer-use__request_access",
      {"apps": ["Google Chrome"]})
warns("request_access Safari dict", "mcp__computer-use__request_access",
      {"apps": [{"displayName": "Safari"}]})
warns("unrelated tool calls do not count as a search",
      "mcp__claude-in-chrome__navigate", GA,
      [USER, ("Bash", {"command": "ls -la"}), ("Read", {"file_path": "/x"})])
warns("search before the last user message does not count",
      "mcp__claude-in-chrome__navigate", GA,
      [("WebSearch", {"query": "ga admin api"}), USER])

# ---- negatives: not a browser call
silent("preview_start by name has no url", "mcp__Claude_Browser__preview_start",
       {"name": "dev"})
silent("request_access non-browser", "mcp__computer-use__request_access",
       {"apps": ["Notes", "Finder"]})
silent("other tool", "Bash", {"command": "echo hi"})

# ---- discharges: a route search since the last user message
for label, entry in [
    ("WebSearch", ("WebSearch", {"query": "x"})),
    ("WebFetch", ("WebFetch", {"url": "https://developers.google.com"})),
    ("ToolSearch", ("ToolSearch", {"query": "analytics"})),
    ("claude mcp list", ("Bash", {"command": "claude mcp list"})),
    ("command -v", ("Bash", {"command": "command -v gcloud"})),
    ("which", ("Bash", {"command": "which gcloud"})),
    ("--help", ("Bash", {"command": "gcloud analytics --help"})),
    ("gh api", ("Bash", {"command": "gh api repos/o/r"})),
]:
    silent(f"discharged by {label}", "mcp__claude-in-chrome__navigate", GA,
           [USER, entry, ("tool_result",)])

silent("search then tool_result does not reset the turn",
       "mcp__claude-in-chrome__navigate", GA,
       [USER, ("WebSearch", {"query": "x"}), ("tool_result",),
        ("Read", {"file_path": "/y"}), ("tool_result",)])

# ---- first call only
silent("second browser call after a warned first",
       "mcp__claude-in-chrome__navigate", GA,
       [USER, ("mcp__claude-in-chrome__navigate", GA), ("tool_result",)])
warns("new user message re-arms the warning",
      "mcp__claude-in-chrome__navigate", GA,
      [USER, ("mcp__claude-in-chrome__navigate", GA), ("tool_result",),
       ("user", "now another thing")])
warns("prior exempt render navigation does not suppress the warning",
      "mcp__claude-in-chrome__navigate", GA,
      [USER, ("mcp__claude-in-chrome__navigate",
              {"url": "http://localhost:4321/"}), ("tool_result",)])

# ---- exemptions: render checks
for url in ["http://localhost:8080/index.html", "localhost:3000",
            "http://127.0.0.1:4000/", "https://docs.localhost/x",
            "file:///Users/e/_site/index.html", "/Users/e/repo/_site/a.html",
            "_site/index.html"]:
    silent(f"exempt {url}", "mcp__Claude_Browser__navigate", {"url": url})
silent("exempt preview_start localhost", "mcp__Claude_Browser__preview_start",
       {"url": "http://localhost:5173"})
warns("localhost-lookalike host is not exempt",
      "mcp__claude-in-chrome__navigate", {"url": "https://localhost.evil.com/"})

# ---- the call under evaluation is already the last transcript record
warns("evaluated call itself in the transcript, unanswered",
      "mcp__claude-in-chrome__navigate", GA,
      [USER, ("mcp__claude-in-chrome__navigate", GA)])
silent("answered earlier browser call suppresses",
       "mcp__claude-in-chrome__navigate", GA,
       [USER, ("mcp__claude-in-chrome__navigate", GA), ("tool_result",),
        ("mcp__claude-in-chrome__navigate", GA)])

# ---- harness-injected user records do not reset the turn
SEARCHED = [USER, ("WebSearch", {"query": "x"}), ("tool_result",)]
silent("skill-load meta record keeps the search",
       "mcp__claude-in-chrome__navigate", GA,
       SEARCHED + [("user", "skill body",
                    {"isMeta": True, "sourceToolUseID": "toolu_1"})])
silent("sidechain user record keeps the search",
       "mcp__claude-in-chrome__navigate", GA,
       SEARCHED + [("user", "sub-agent prompt", {"isSidechain": True})])
silent("hook feedback record keeps the search",
       "mcp__claude-in-chrome__navigate", GA,
       SEARCHED + [("user", "[SYSTEM NOTIFICATION - NOT USER INPUT] tick")])

# ---- remote URLs containing _site/ are not render checks
warns("remote _site path is not exempt", "mcp__claude-in-chrome__navigate",
      {"url": "https://admin.example.com/_site/x"})
warns("_site in a query string is not exempt",
      "mcp__claude-in-chrome__navigate",
      {"url": "https://evil.example/?next=/_site/x"})

warns("?.localhost suffix on a remote host is not exempt",
      "mcp__claude-in-chrome__navigate", {"url": "https://evil.com?.localhost"})
warns("#.localhost suffix on a remote host is not exempt",
      "mcp__claude-in-chrome__navigate", {"url": "https://evil.com#x.localhost"})
warns("userinfo with ?.localhost is not exempt",
      "mcp__claude-in-chrome__navigate",
      {"url": "https://x@evil.com?.localhost"})
warns("scheme-less remote host with _site is not exempt",
      "mcp__claude-in-chrome__navigate", {"url": "admin.example.com/_site/x"})
warns("scheme-less host with _site in query is not exempt",
      "mcp__claude-in-chrome__navigate", {"url": "example.com/?next=/_site/x"})
for inj in ["<system-reminder>x</system-reminder>",
            "<task-notification>t</task-notification>",
            "[Request interrupted by user for tool use]"]:
    silent(f"injected user record keeps the search: {inj[:18]}",
           "mcp__claude-in-chrome__navigate", GA, SEARCHED + [("user", inj)])

# ---- back/forward and missing url are not visits
silent("navigate back", "mcp__claude-in-chrome__navigate", {"url": "back"})
silent("navigate forward", "mcp__Claude_Browser__navigate", {"url": "forward"})
silent("navigate with no url", "mcp__claude-in-chrome__navigate", {})

# ---- fail open
silent("missing transcript", "mcp__claude-in-chrome__navigate", GA,
       path="/nonexistent/transcript.jsonl")
silent("empty transcript path", "mcp__claude-in-chrome__navigate", GA, path="")
proc = subprocess.run([sys.executable, HOOK], input="not json",
                      capture_output=True, text=True, timeout=10)
check("malformed payload exits 0 silently",
      (proc.returncode, proc.stdout.strip()), (0, ""))

if failures:
    print("FAIL")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("ok")
