#!/usr/bin/env python3
"""Tests for hooks/warn-bare-forge-reference.py (ai-config#4224).

Run: python3 hooks/test-warn-bare-forge-reference.py [hooks/warn-bare-forge-reference.py]
"""
import json
import os
import re
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "warn-bare-forge-reference.py")
REPLY = "mcp__hearthbot__reply"

# (name, tool, text, expected references named in the warning)
CASES = [
    ("bare issue", REPLY, "Fixed in #4224.", ["#4224"]),
    ("bare MR", REPLY, "Merged !125 today.", ["!125"]),
    ("repo-qualified", "mcp__hearthbot__post_message",
     "See Morrison-Lab/lds#342 for the batch.", ["Morrison-Lab/lds#342"]),
    ("update_message", "mcp__hearthbot__update_message", "PR #7 is green.", ["#7"]),
    ("two refs, one linked", REPLY,
     "[#1](https://github.com/o/r/pull/1) and #2 both landed.", ["#2"]),
    ("link text is not a bare ref", REPLY,
     "[lds#342](https://github.com/Morrison-Lab/lds/pull/342) is up.", None),
    ("bare URL", REPLY, "https://github.com/o/r/issues/9 is open.", None),
    ("inline code", REPLY, "The regex `#\\d+` matches.", None),
    ("fenced code", REPLY, "```\nfix #12\n```\nDone.", None),
    ("thread anchor", REPLY, "See [the thread](#cmsg_014Q) for details.", None),
    ("hex colour", REPLY, "The colour #123456 is used.", None),
    ("url fragment", REPLY, "Open page.html#12 now.", None),
    ("heading hash", REPLY, "## 2 items\n#hashtag", None),
    ("other tool", "Bash", "echo #12", None),
    ("no refs", REPLY, "Nothing to report.", None),
    ("ordinal is listed", REPLY, "#1 priority, Step #2.", ["#1", "#2"]),
    ("parenthesised", REPLY, "Done (#4224).", ["#4224"]),
    ("bold", REPLY, "**#4224** merged.", ["#4224"]),
    ("ref-style link", REPLY, "See [#12][1].\n\n[1]: https://x.test/12", None),
    ("ref definition label", REPLY, "[#12]: https://x.test/12", None),
    ("double-backtick span", REPLY, "Use ``fix #12`` here.", None),
    ("multi-line span", REPLY, "Use `fix\n#12` here.", None),
    ("unclosed fence", REPLY, "```\nfix #12\nmore", None),
    ("owner/repo shape", REPLY, "Edit a/b#12 now.", ["a/b#12"]),
    ("after period is not flagged", REPLY, "fixed.#12", None),
]


def run(tool, text):
    event = {"tool_name": tool, "tool_input": {"text": text}}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def main():
    failures = 0
    for name, tool, text, expected in CASES:
        code, out = run(tool, text)
        ok = code == 0
        if expected is None:
            ok = ok and out == ""
        else:
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
            named = re.findall(r"`([^`]+)`", ctx.split("by number", 1)[0])
            ok = ok and named == expected
        if not ok:
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r}")
    for bad in ("", "not json", "[]", json.dumps({"tool_name": REPLY, "tool_input": []})):
        proc = subprocess.run([sys.executable, HOOK], input=bad,
                              capture_output=True, text=True)
        if proc.returncode != 0 or proc.stdout:
            failures += 1
            print(f"FAIL malformed input {bad!r}")
    many = " ".join(f"#{n}" for n in range(1, 9))
    _, out = run(REPLY, many)
    if "3 more" not in out:
        failures += 1
        print("FAIL overflow count")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
