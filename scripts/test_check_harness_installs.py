#!/usr/bin/env python3
"""Offline regression tests for the cross-harness install audit."""
import importlib.util
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("check-harness-installs.py")
spec = importlib.util.spec_from_file_location("harness_check", SCRIPT)
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)

passes = failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


with tempfile.TemporaryDirectory() as raw:
    root = Path(raw)
    repo = root / "repo"
    codex, gemini, cursor = root / "codex", root / "gemini", root / "cursor"
    write(repo / "codex-skills" / "alpha" / "SKILL.md")
    write(repo / "skills" / "alpha" / "SKILL.md")
    write(repo / "cursor-rules" / "base.mdc")
    (codex / "skills").mkdir(parents=True)
    (codex / "skills" / "alpha").symlink_to(repo / "codex-skills" / "alpha")
    (gemini / "skills").mkdir(parents=True)
    write(gemini / "skills" / "alpha" / "SKILL.md", "stale")
    (cursor / "rules").mkdir(parents=True)
    write(cursor / "rules" / "base.mdc")
    write(cursor / "rules" / "foreign.mdc")

    codex_entries = hc.collect_flat(repo, "codex-skills", codex / "skills", "codex")
    gemini_entries = hc.collect_flat(repo, "skills", gemini / "skills", "gemini")
    cursor_entries = hc.collect_flat(repo, "cursor-rules", cursor / "rules", "cursor")
    statuses = lambda entries: {entry.label: entry.status for entry in entries}
    check("Codex wrapper link is current", statuses(codex_entries) == {"codex/alpha": "ok"})
    check("Gemini stale skill is detected", statuses(gemini_entries) == {"gemini/alpha": "stale"})
    check("Cursor unlinked and foreign rules are detected", statuses(cursor_entries) == {"cursor/base.mdc": "unlinked", "cursor/foreign.mdc": "foreign"})
    check("absent consumer is explicit", hc.collect_flat(repo, "skills", root / "absent", "gemini") == [])
    write(codex / "config.toml", "[plugins.\"ai-config@example\"]\nenabled = true\n")
    check("enabled Codex plugin skips bare wrappers", hc.codex_plugin_enabled(codex / "config.toml"))
    (cursor / "skills").mkdir(parents=True)
    write(cursor / "skills" / "alpha" / "SKILL.md", "stale")
    claude = root / "claude"
    check(
        "Cursor stale skill is detected",
        statuses(hc.collect_flat(repo, "skills", cursor / "skills", "cursor"))
        == {"cursor/alpha": "stale"},
    )
    check(
        "empty Cursor dirs do not skip skill audit",
        not hc.cursor_skill_catalog_served(cursor, claude, repo),
    )
    (cursor / "plugins" / "local" / "ai-config").mkdir(parents=True)
    write(repo / "skills" / "beta" / "SKILL.md")
    check(
        "Cursor plugin is detected as serving the catalog",
        hc.cursor_skill_catalog_served(cursor, claude, repo),
    )
    check(
        "Cursor plugin still reports leftover stale skills",
        statuses(hc.catalog_leftovers(
            hc.collect_flat(repo, "skills", cursor / "skills", "cursor")
        ))
        == {"cursor/alpha": "stale"},
    )
    try:
        (cursor / "skills" / "beta").symlink_to(repo / "skills" / "beta")
        linked = True
    except OSError:
        linked = False
    if linked:
        leftover = statuses(hc.catalog_leftovers(
            hc.collect_flat(repo, "skills", cursor / "skills", "cursor")
        ))
        check("leftover current symlink is stacked, not ok",
              leftover.get("cursor/beta") == "stacked")
        check("leftover stale file stays stale beside a stacked link",
              leftover.get("cursor/alpha") == "stale")
    else:
        print("SKIP: leftover stacked symlink (platform cannot create it)")

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
