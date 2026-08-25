#!/usr/bin/env python3
"""Regression tests for the stacked-install detector (ai-config#1409).

Covers `scripts/lib/plugin_overlap.py` (the shared matching and reporting)
and `scripts/check-plugin-overlap.py` (the CLI's symlink-liveness probe and
exit-code contract). Builds synthetic consumer/repo directories, so the tests
never touch a real `~/.claude`.

The known-positive cases run first, per `fail-fast.md`'s negative-control
rule: a detector whose every test input is clean proves only that it stays
quiet, and quiet is also what a broken detector produces.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

LIB = Path(__file__).parent / "lib" / "plugin_overlap.py"
CLI = Path(__file__).parent / "check-plugin-overlap.py"

spec = importlib.util.spec_from_file_location("plugin_overlap", LIB)
po = importlib.util.module_from_spec(spec)
spec.loader.exec_module(po)

cli_spec = importlib.util.spec_from_file_location("check_plugin_overlap", CLI)
cpo = importlib.util.module_from_spec(cli_spec)
cli_spec.loader.exec_module(cpo)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


# --- enabled_ai_config_plugins: known positives first ------------------------

both = {"enabledPlugins": {"ai-config@Morrison-Lab": True,
                           "ai-config@the repository owner": True}}
check("two marketplaces' entries are BOTH returned, in order",
      po.enabled_ai_config_plugins(both)
      == ["ai-config@Morrison-Lab", "ai-config@the repository owner"])

one = {"enabledPlugins": {"ai-config@the repository owner": True, "oss@other": True}}
check("a single enabled entry is returned, unrelated plugins ignored",
      po.enabled_ai_config_plugins(one) == ["ai-config@the repository owner"])

# --- enabled_ai_config_plugins: negatives ------------------------------------

check("a disabled (false) entry does not count",
      po.enabled_ai_config_plugins(
          {"enabledPlugins": {"ai-config@Morrison-Lab": False}}) == [])

# --- ai_config_entries: both polarities, unlike the truthy-only helper ------

check("ai_config_entries keeps an explicit false, which the name list drops",
      po.ai_config_entries(
          {"enabledPlugins": {"ai-config@Morrison-Lab": False,
                              "ai-config@the repository owner": True}})
      == {"ai-config@Morrison-Lab": False, "ai-config@the repository owner": True})
check("ai_config_entries still ignores non-ai-config names",
      po.ai_config_entries({"enabledPlugins": {"oss@x": True}}) == {})

# --- resolve_enabled: ASCENDING precedence, last writer wins -----------------
# The documented order is managed > cli > .claude/settings.local.json >
# .claude/settings.json > ~/.claude/settings.json, so the USER scope is the
# lowest. These are the cases that were wrong before ai-config#1417's
# self-review: a union would have kept the plugin enabled in the first two.

user_on = {"enabledPlugins": {"ai-config@Morrison-Lab": True}}
local_off = {"enabledPlugins": {"ai-config@Morrison-Lab": False}}

check("a later explicit false clears an earlier true (the documented opt-out)",
      po.resolve_enabled([user_on, local_off]) == [])
check("project-enabled then local-disabled resolves to disabled",
      po.resolve_enabled([{}, user_on, local_off]) == [])
check("a later true re-enables what an earlier false disabled",
      po.resolve_enabled([local_off, user_on]) == ["ai-config@Morrison-Lab"])
check("a scope with no entry does not clear a lower scope's true",
      po.resolve_enabled([user_on, {"enabledPlugins": {"oss@x": True}}])
      == ["ai-config@Morrison-Lab"])
check("resolve_enabled over one scope matches the single-scope helper",
      po.resolve_enabled([both]) == po.enabled_ai_config_plugins(both))
check("first-seen order is preserved across scopes",
      po.resolve_enabled([{"enabledPlugins": {"ai-config@Morrison-Lab": True}},
                          {"enabledPlugins": {"ai-config@the repository owner": True}}])
      == ["ai-config@Morrison-Lab", "ai-config@the repository owner"])
check("no scopes at all resolves to nothing enabled",
      po.resolve_enabled([]) == [])
check("a name merely CONTAINING ai-config does not count",
      po.enabled_ai_config_plugins(
          {"enabledPlugins": {"my-ai-config@x": True,
                              "ai-config-extras@x": True}}) == [])
check("no enabledPlugins key yields an empty list",
      po.enabled_ai_config_plugins({}) == [])
check("a non-dict enabledPlugins yields an empty list",
      po.enabled_ai_config_plugins({"enabledPlugins": ["ai-config@x"]}) == [])

# --- load_settings: absence is None, never an empty answer -------------------

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    check("a missing settings file loads as None",
          po.load_settings(tmp / "absent.json") is None)

    bad = tmp / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    check("malformed JSON loads as None rather than raising",
          po.load_settings(bad) is None)

    arr = tmp / "arr.json"
    arr.write_text("[1, 2]", encoding="utf-8")
    check("non-dict JSON loads as None", po.load_settings(arr) is None)

    good = tmp / "good.json"
    good.write_text(json.dumps(one), encoding="utf-8")
    check("valid JSON loads as its dict",
          po.load_settings(good) == one)

# --- describe_overlap --------------------------------------------------------


def settings_file(tmp: Path, name: str, payload: dict) -> Path:
    path = tmp / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)

    # Known positive: plugin + symlink both live -> stacked-install warning.
    p = settings_file(tmp, "one.json", one)
    lines = po.describe_overlap([p], symlink_install_live=True)
    check("plugin + live symlink reports the stacked install",
          len(lines) == 1 and "BOTH live" in lines[0]
          and "ai-config@the repository owner" in lines[0])

    # Known positive: two marketplaces -> namespace-collision warning.
    b = settings_file(tmp, "both.json", both)
    lines = po.describe_overlap([b], symlink_install_live=False)
    check("two marketplace entries report the namespace collision",
          len(lines) == 1 and "namespace" in lines[0]
          and "ai-config@Morrison-Lab" in lines[0]
          and "ai-config@the repository owner" in lines[0])

    # Both defects at once -> both warnings.
    lines = po.describe_overlap([b], symlink_install_live=True)
    check("both defects at once yield both warnings", len(lines) == 2)

    # The same entry enabled in two FILES (user + project) is one install,
    # not a collision -- deduplicated by name across files.
    p2 = settings_file(tmp, "two.json", one)
    lines = po.describe_overlap([p, p2], symlink_install_live=False)
    check("the same plugin name across two settings files is not a collision",
          lines == [])

    # Negatives.
    clean = settings_file(tmp, "clean.json", {"enabledPlugins": {"oss@x": True}})
    check("no ai-config plugin -> no findings, symlink live or not",
          po.describe_overlap([clean], symlink_install_live=True) == []
          and po.describe_overlap([clean], symlink_install_live=False) == [])
    check("plugin enabled but symlink NOT live -> no stacked-install warning",
          po.describe_overlap([p], symlink_install_live=False) == [])

    # The documented per-user opt-out must NOT be reported as an overlap:
    # project scope enables, higher-precedence local scope disables.
    proj = settings_file(tmp, "proj.json", user_on)
    loc = settings_file(tmp, "local.json", local_off)
    check("the documented local-scope opt-out reports no overlap",
          po.describe_overlap([proj, loc], symlink_install_live=True) == [])
    check("the same two files in the WRONG order would report one "
          "(so the order is load-bearing, not decorative)",
          len(po.describe_overlap([loc, proj], symlink_install_live=True)) == 1)

    # An unreadable higher scope must not silently clear a lower one's entry.
    check("a missing project file does not clear a user-scope true",
          len(po.describe_overlap([proj, tmp / "absent.json"],
                                  symlink_install_live=True)) == 1)

    # No readable file is reported as unexamined, never as clean.
    lines = po.describe_overlap([tmp / "absent.json"], symlink_install_live=True)
    check("no readable settings file says NOT checked rather than clean",
          len(lines) == 1 and "NOT checked" in lines[0])
    lines = po.describe_overlap([], symlink_install_live=True)
    check("an empty path list also says NOT checked",
          len(lines) == 1 and "NOT checked" in lines[0])

# --- symlink_install_live ----------------------------------------------------


def make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "skills" / "ardi").mkdir(parents=True)
    (repo / "skills" / "ardi" / "SKILL.md").write_text("x", encoding="utf-8")
    return repo


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    repo = make_repo(tmp)

    whole = tmp / "whole-consumer"
    whole.mkdir()
    (whole / "skills").symlink_to(repo / "skills")
    check("a whole-dir symlink into the repo is live",
          cpo.symlink_install_live(whole, repo))

    merged = tmp / "merged-consumer"
    (merged / "skills").mkdir(parents=True)
    (merged / "skills" / "ardi").symlink_to(repo / "skills" / "ardi")
    check("a merged install (child symlinks) is live",
          cpo.symlink_install_live(merged, repo))

    foreign = tmp / "foreign-consumer"
    (foreign / "skills" / "docx").mkdir(parents=True)
    check("a real skills dir with no repo symlinks (built-ins only) is NOT live",
          not cpo.symlink_install_live(foreign, repo))

    empty = tmp / "empty-consumer"
    empty.mkdir()
    check("a consumer dir with no skills/ at all is NOT live",
          not cpo.symlink_install_live(empty, repo))

    elsewhere = tmp / "elsewhere-consumer"
    other = tmp / "other-checkout"
    (other / "skills").mkdir(parents=True)
    elsewhere.mkdir()
    (elsewhere / "skills").symlink_to(other / "skills")
    check("a symlink into a DIFFERENT checkout is not live for this repo",
          not cpo.symlink_install_live(elsewhere, repo))

# --- CLI contract ------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    repo = make_repo(tmp)
    consumer = tmp / "consumer"
    consumer.mkdir()
    (consumer / "skills").symlink_to(repo / "skills")
    settings_file(consumer, "settings.json", both)
    project = tmp / "project"
    project.mkdir()

    result = subprocess.run(
        [sys.executable, str(CLI), "--consumer-dir", str(consumer),
         "--repo-root", str(repo), "--project-dir", str(project)],
        capture_output=True, text=True)
    check("CLI exits 0 even when it finds both defects (advisory)",
          result.returncode == 0)
    check("CLI prints both warnings on a doubly-defective install",
          result.stdout.count("WARNING:") == 2)

    clean_consumer = tmp / "clean-consumer"
    clean_consumer.mkdir()
    (clean_consumer / "skills").symlink_to(repo / "skills")
    settings_file(clean_consumer, "settings.json", {})
    result = subprocess.run(
        [sys.executable, str(CLI), "--consumer-dir", str(clean_consumer),
         "--repo-root", str(repo), "--project-dir", str(project)],
        capture_output=True, text=True)
    check("CLI reports what it examined on a clean install, not bare silence",
          result.returncode == 0 and "settings file(s) examined" in result.stdout)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
