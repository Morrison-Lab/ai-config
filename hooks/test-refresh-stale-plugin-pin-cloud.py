#!/usr/bin/env python3
"""Tests for hooks/refresh-stale-plugin-pin-cloud.py.

A fake `claude` script stands in for the CLI: `plugin marketplace update` advances the
fake marketplace clone by one commit, `plugin update` rewrites the pin to the clone's HEAD.
  1. Remote, pin behind clone after update: refreshes, reports old and new, reloadSkills.
  2. Remote, pin already HEAD: silent, no `plugin update` call.
  3. Not remote: silent, claude never called.
  4. AI_CONFIG_NO_AUTO_REFRESH=1: silent, claude never called.
  5. claude fails: exit 0, nothing on stdout, stderr says so.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(sys.argv[1] if len(sys.argv) > 1 else
            os.path.join(os.path.dirname(__file__), "refresh-stale-plugin-pin-cloud.py"))
failures = []
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else " " + detail))
    if not cond:
        failures.append(name)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True, env=ENV).stdout.strip()


FAKE = """#!/bin/sh
echo "$@" >> "$AI_CONFIG_PLUGINS_DIR/calls.log"
[ -n "$FAKE_FAIL" ] && { echo boom >&2; exit 1; }
case "$3" in
  update) [ -n "$FAKE_ADVANCE" ] && git -C "$AI_CONFIG_PLUGINS_DIR/marketplaces/m" commit -q --allow-empty -m next ;;
esac
if [ "$2" = update ]; then
  sha=$(git -C "$AI_CONFIG_PLUGINS_DIR/marketplaces/m" rev-parse HEAD)
  sed -i "s/\\"gitCommitSha\\": \\"[0-9a-f]*\\"/\\"gitCommitSha\\": \\"$sha\\"/" "$AI_CONFIG_PLUGINS_DIR/installed_plugins.json"
fi
"""


def scenario(remote=True, advance=True, extra=None):
    d = Path(tempfile.mkdtemp())
    clone = d / "marketplaces" / "m"
    clone.mkdir(parents=True)
    git(clone, "init", "-q")
    git(clone, "commit", "-q", "--allow-empty", "-m", "one")
    old = git(clone, "rev-parse", "HEAD")
    pin = old
    (d / "installed_plugins.json").write_text(json.dumps({"plugins": {
        "ai-config@m": [{"scope": "user", "gitCommitSha": pin}]}}))
    fake = d / "claude"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    env = {**ENV, "AI_CONFIG_PLUGINS_DIR": str(d), "AI_CONFIG_CLAUDE_BIN": str(fake),
           **({"FAKE_ADVANCE": "1"} if advance else {}),
           **(extra or {})}
    env.pop("CLAUDE_CODE_REMOTE", None)
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "true"
    out = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True,
                         text=True, env=env)
    calls = (d / "calls.log").read_text() if (d / "calls.log").exists() else ""
    return out, calls, pin


out, calls, pin = scenario()
data = json.loads(out.stdout or "{}").get("hookSpecificOutput", {})
check("1 refreshes", "plugin update ai-config@m" in calls and data.get("reloadSkills") is True
      and pin[:12] in data.get("additionalContext", ""), out.stdout + out.stderr)
out, calls, _ = scenario(advance=False)
check("2 current pin: no plugin update", out.stdout == "" and "plugin update" not in calls, calls)
out, calls, _ = scenario(remote=False)
check("3 not remote", out.stdout == "" and calls == "", calls)
out, calls, _ = scenario(extra={"AI_CONFIG_NO_AUTO_REFRESH": "1"})
check("4 opt out", out.stdout == "" and calls == "", calls)
out, calls, _ = scenario(extra={"FAKE_FAIL": "1"})
check("5 claude fails", out.returncode == 0 and out.stdout == "" and "boom" in out.stderr, out.stderr)
sys.exit(1 if failures else 0)
