#!/usr/bin/env python3
"""Tests for hooks/no-leftover-cleanup-ask.py (ai-config#5843).

Run: python3 hooks/test-no-leftover-cleanup-ask.py [hooks/no-leftover-cleanup-ask.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-leftover-cleanup-ask.py")
POST = "mcp__hearthbot__post_message"

# (name, tool, text, should_deny)
CASES = [
    ("the ONLYOFFICE handoff", POST,
     "ONLYOFFICE is installed. The 426 MB AppImage download is in ~/.local/opt/onlyoffice-dl; you can delete it.", True),
    ("safe to delete", POST, "The installer is safe to delete now.", True),
    ("can be removed", POST, "The extracted archive in /tmp/x can be removed.", True),
    ("feel free", POST, "Feel free to remove the .dmg from Downloads.", True),
    ("I left the tarball", POST, "I left the tarball in ~/scratch in case you want it.", True),
    ("you may want to clean up", POST, "You might want to clean up the temp directory.", True),
    ("Ezra can rm", POST, "Ezra can rm the downloaded .deb whenever.", True),
    ("already deleted", POST, "I deleted the 426 MB AppImage download and the extracted folder.", False),
    ("was removed", POST, "The installer was removed after the install finished.", False),
    ("done but still hands off", POST, "I removed the zip, but you can delete the extracted folder too.", True),
    ("no leftover noun", POST, "You can delete the old branch once the PR merges.", False),
    ("leftover without handoff", POST, "The download took four minutes.", False),
    ("secret exempt", POST, "You can delete the old token from the downloaded keychain file.", False),
    ("other tool ignored", "Bash", "you can delete the installer", False),
]


def run(tool, text, env=None):
    payload = json.dumps({"tool_name": tool, "tool_input": {"text": text}})
    proc = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True, text=True,
                          env={**os.environ, **(env or {})}, check=False)
    return '"deny"' in proc.stdout


def main():
    failures = 0
    for name, tool, text, want in CASES:
        got = run(tool, text)
        if got != want:
            failures += 1
            print(f"FAIL {name}: want deny={want}, got {got}")
    if run(POST, CASES[0][2], {"ALLOW_LEFTOVER_HANDOFF": "1"}):
        failures += 1
        print("FAIL override: ALLOW_LEFTOVER_HANDOFF=1 should allow")
    for bad in ("", "not json", "[]"):
        proc = subprocess.run([sys.executable, HOOK], input=bad, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or proc.stdout:
            failures += 1
            print(f"FAIL fail-open on {bad!r}")
    print(f"{len(CASES) + 4 - failures}/{len(CASES) + 4} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
