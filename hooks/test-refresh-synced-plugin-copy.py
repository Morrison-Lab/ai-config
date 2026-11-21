#!/usr/bin/env python3
"""Tests for hooks/refresh-synced-plugin-copy.py.

  1. Remote, stale synced copy: its changed file is overwritten, a synced-only file kept,
     a new file added, .git skipped, and the report names the copy.
  2. Not remote: synced copy untouched, nothing on stdout.
  3. AI_CONFIG_NO_SYNCED_REFRESH=1: untouched.
  4. Hook running from the synced copy itself: untouched.
  5. A synced plugin with another name: untouched.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(sys.argv[1] if len(sys.argv) > 1 else
            os.path.join(os.path.dirname(__file__), "refresh-synced-plugin-copy.py"))
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else " " + detail))
    if not cond:
        failures.append(name)


def make_plugin(root, name, files):
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}))
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def scenario(remote=True, opt_out=False, from_synced=False, synced_name="ai-config"):
    d = Path(tempfile.mkdtemp())
    plugins = d / "plugins"
    fresh = plugins / "cache" / "Morrison-Lab" / "ai-config" / "abc"
    make_plugin(fresh, "ai-config", {"hooks/guard.py": "new", "hooks/added.py": "added",
                                     ".git/HEAD": "ref"})
    synced = plugins / "synced" / "bucket" / "ai-config"
    make_plugin(synced, synced_name, {"hooks/guard.py": "old", "hooks/only-synced.py": "keep"})
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_CODE_REMOTE", "AI_CONFIG_NO_SYNCED_REFRESH")}
    env["AI_CONFIG_PLUGINS_DIR"] = str(plugins)
    env["CLAUDE_PLUGIN_ROOT"] = str(synced if from_synced else fresh)
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "true"
    if opt_out:
        env["AI_CONFIG_NO_SYNCED_REFRESH"] = "1"
    out = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True,
                         text=True, env=env)
    return out, synced


out, synced = scenario()
check("1 exit 0", out.returncode == 0, out.stderr)
check("1 changed file overwritten", (synced / "hooks/guard.py").read_text() == "new")
check("1 synced-only file kept", (synced / "hooks/only-synced.py").read_text() == "keep")
check("1 new file added", (synced / "hooks/added.py").read_text() == "added")
check("1 .git skipped", not (synced / ".git").exists())
try:
    ctx = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
except (ValueError, KeyError):
    ctx = ""
check("1 report names the copy", str(synced) in ctx, out.stdout)

for label, kwargs in [("2 not remote", {"remote": False}),
                      ("3 opt-out", {"opt_out": True}),
                      ("4 running from synced", {"from_synced": True}),
                      ("5 other plugin name", {"synced_name": "other"})]:
    out, synced = scenario(**kwargs)
    check(f"{label}: exit 0", out.returncode == 0, out.stderr)
    check(f"{label}: untouched", (synced / "hooks/guard.py").read_text() == "old")
    check(f"{label}: silent", out.stdout.strip() == "", out.stdout)

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
