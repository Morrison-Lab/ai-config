#!/usr/bin/env python3
"""Offline regression tests for the cross-harness install audit."""
import importlib.util
import os
import subprocess
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
    check(
        "Cursor plugin is detected as installed",
        hc.cursor_plugin_installed(cursor),
    )
    write(repo / "cursor-rules" / "live.mdc")
    try:
        (cursor / "rules" / "live.mdc").symlink_to(repo / "cursor-rules" / "live.mdc")
        rule_linked = True
    except OSError:
        rule_linked = False
    if rule_linked:
        leftover_rules = statuses(hc.catalog_leftovers(
            hc.collect_flat(repo, "cursor-rules", cursor / "rules", "cursor"),
            detail="Cursor plugin already serves this rule",
        ))
        check("leftover current rule symlink is stacked, not ok",
              leftover_rules.get("cursor/live.mdc") == "stacked")
        check("unlinked leftover rule stays unlinked beside a stacked rule",
              leftover_rules.get("cursor/base.mdc") == "unlinked")
    else:
        print("SKIP: leftover stacked rule symlink (platform cannot create it)")

# Drive main() so a wiring mistake (gating rule leftovers on the skill
# catalog skip, which is also true for a Claude-only install) cannot stay
# green. Helper-only checks above would not catch that.
with tempfile.TemporaryDirectory() as raw:
    root = Path(raw)
    repo = root / "repo"
    cursor = root / "cursor"
    claude = root / "claude"
    write(repo / "skills" / "alpha" / "SKILL.md")
    write(repo / "cursor-rules" / "live.mdc")
    claude_skills = claude / "skills"
    claude_skills.parent.mkdir(parents=True)
    try:
        claude_skills.symlink_to(repo / "skills")
        (cursor / "rules").mkdir(parents=True)
        (cursor / "rules" / "live.mdc").symlink_to(repo / "cursor-rules" / "live.mdc")
        wired = True
    except OSError:
        wired = False
    if wired:
        def run_audit() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--repo-root", str(repo),
                    "--cursor-dir", str(cursor),
                    "--claude-dir", str(claude),
                    "--codex-dir", str(root / "codex-absent"),
                    "--gemini-dir", str(root / "gemini-absent"),
                ],
                capture_output=True, text=True, check=False,
                env=os.environ,
            )

        result = run_audit()
        check(
            "Claude catalog without a plugin does not label Cursor rules as leftovers",
            "Cursor rules (plugin leftovers)" not in result.stdout,
        )
        check(
            "Claude catalog without a plugin does not stack an ok rule link",
            "STACKED" not in result.stdout,
        )
        (cursor / "plugins" / "local" / "ai-config").mkdir(parents=True)
        result = run_audit()
        check(
            "main() labels leftover rules as plugin leftovers when the plugin is live",
            "Cursor rules (plugin leftovers)" in result.stdout,
        )
        check(
            "main() reports a leftover ok rule link as stacked",
            "STACKED" in result.stdout and "cursor/live.mdc" in result.stdout,
        )
    else:
        print("SKIP: main() rule leftover wiring (platform cannot create symlink)")

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
