#!/usr/bin/env python3
"""Tests for hooks/refresh-synced-plugin-copy.py.

  1. Remote, run from the marketplace plugin: the synced copy's changed file is
     overwritten, a synced-only file kept, a new file added, .git skipped, and the
     report names the copy.
  2. Not remote: untouched.
  3. AI_CONFIG_NO_SYNCED_REFRESH=1: untouched.
  4. A synced plugin with another name: untouched.
  5. Run from the synced copy, marketplace plugin recorded in installed_plugins.json:
     overwritten from the recorded install, claude never called.
  6. Run from the synced copy, nothing installed: a fake `claude` installs it, the
     copy is overwritten, and the report says it installed the plugin.
  7. As 6 with AI_CONFIG_NO_SYNCED_INSTALL=1: untouched, claude never called.
  8. As 6 with `claude` failing: untouched, exit 0.
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

# A stand-in for the claude CLI: `plugin install` copies $FAKE_SOURCE into the
# cache and records it as the user-scope install; FAKE_FAIL makes every call fail.
FAKE = """#!/bin/sh
echo "$@" >> "$AI_CONFIG_PLUGINS_DIR/calls.log"
[ -n "$FAKE_FAIL" ] && { echo boom >&2; exit 1; }
if [ "$2" = install ]; then
  dest="$AI_CONFIG_PLUGINS_DIR/cache/Morrison-Lab/ai-config/new"
  mkdir -p "$dest" && cp -R "$FAKE_SOURCE"/. "$dest"/
  printf '{"plugins": {"ai-config@Morrison-Lab": [{"scope": "user", "installPath": "%s"}]}}' \\
    "$dest" > "$AI_CONFIG_PLUGINS_DIR/installed_plugins.json"
fi
exit 0
"""


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else " " + detail))
    if not cond:
        failures.append(name)


def make_plugin(root, name, files):
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def scenario(remote=True, opt_out=False, root="fresh", synced_name="ai-config",
             recorded=False, no_install=False, fail=False):
    d = Path(tempfile.mkdtemp())
    plugins = d / "plugins"
    fresh = plugins / "cache" / "Morrison-Lab" / "ai-config" / "abc"
    make_plugin(fresh, "ai-config", {"hooks/guard.py": "new", "hooks/added.py": "added",
                                     ".git/HEAD": "ref"})
    synced = plugins / "synced" / "bucket" / "ai-config"
    make_plugin(synced, synced_name, {"hooks/guard.py": "old", "hooks/only-synced.py": "keep"})
    if recorded:
        (plugins / "installed_plugins.json").write_text(json.dumps({"plugins": {
            "ai-config@Morrison-Lab": [{"scope": "user", "installPath": str(fresh)}]}}), encoding="utf-8")
    fake = d / "claude"
    fake.write_text(FAKE, encoding="utf-8")
    fake.chmod(0o755)
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_CODE_REMOTE", "AI_CONFIG_NO_SYNCED_REFRESH",
                        "AI_CONFIG_NO_SYNCED_INSTALL", "CLAUDE_PLUGIN_ROOT")}
    env.update({"AI_CONFIG_PLUGINS_DIR": str(plugins), "AI_CONFIG_CLAUDE_BIN": str(fake),
                "FAKE_SOURCE": str(fresh),
                "CLAUDE_PLUGIN_ROOT": str(fresh if root == "fresh" else synced)})
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "true"
    if opt_out:
        env["AI_CONFIG_NO_SYNCED_REFRESH"] = "1"
    if no_install:
        env["AI_CONFIG_NO_SYNCED_INSTALL"] = "1"
    if fail:
        env["FAKE_FAIL"] = "1"
    out = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True,
                         text=True, env=env)
    calls = (plugins / "calls.log").read_text(encoding="utf-8") if (plugins / "calls.log").exists() else ""
    return out, synced, calls


def context(out):
    try:
        return json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError):
        return ""


def refreshed(label, out, synced):
    check(f"{label}: exit 0", out.returncode == 0, out.stderr)
    check(f"{label}: changed file overwritten", (synced / "hooks/guard.py").read_text(encoding="utf-8") == "new")
    check(f"{label}: synced-only file kept", (synced / "hooks/only-synced.py").read_text(encoding="utf-8") == "keep")
    check(f"{label}: new file added", (synced / "hooks/added.py").read_text(encoding="utf-8") == "added")
    check(f"{label}: .git skipped", not (synced / ".git").exists())
    check(f"{label}: report names the copy", str(synced) in context(out), out.stdout)


def untouched(label, out, synced):
    check(f"{label}: exit 0", out.returncode == 0, out.stderr)
    check(f"{label}: untouched", (synced / "hooks/guard.py").read_text(encoding="utf-8") == "old")
    check(f"{label}: silent", out.stdout.strip() == "", out.stdout)


out, synced, calls = scenario()
refreshed("1 from marketplace", out, synced)
check("1: claude never called", calls == "", calls)

for label, kwargs in [("2 not remote", {"remote": False}),
                      ("3 opt-out", {"opt_out": True}),
                      ("4 other plugin name", {"synced_name": "other"})]:
    out, synced, _ = scenario(**kwargs)
    untouched(label, out, synced)

out, synced, calls = scenario(root="synced", recorded=True)
refreshed("5 from synced, recorded install", out, synced)
check("5: claude never called", calls == "", calls)

out, synced, calls = scenario(root="synced")
refreshed("6 from synced, installs", out, synced)
check("6: plugin install called", "plugin install ai-config@Morrison-Lab" in calls, calls)
check("6: report says installed", "first installed" in context(out), out.stdout)

out, synced, calls = scenario(root="synced", no_install=True)
untouched("7 no-install opt-out", out, synced)
check("7: claude never called", calls == "", calls)

out, synced, calls = scenario(root="synced", fail=True)
untouched("8 claude fails", out, synced)

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
