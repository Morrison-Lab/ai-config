#!/usr/bin/env python3
"""Regression tests for `scripts/lib/plugin_overlap.py`.

The library's one live consumer is `scripts/install-hooks.py`, whose
double-registration warning depends on `enabled_ai_config_plugins`
answering exactly. These tests cover the retained library surface only:
the stacked-install CLI (`check-plugin-overlap.py`) and its
`describe_overlap`/`resolve_enabled` helpers were removed along with the
symlink install they compared against (ai-config#2229).

The known-positive cases run first, per `fail-fast.md`'s negative-control
rule: a detector whose every test input is clean proves only that it stays
quiet, and quiet is also what a broken detector produces.
"""
import importlib.util
import sys
from pathlib import Path

LIB = Path(__file__).parent / "lib" / "plugin_overlap.py"

spec = importlib.util.spec_from_file_location("plugin_overlap", LIB)
po = importlib.util.module_from_spec(spec)
spec.loader.exec_module(po)

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
                           "ai-config@other-marketplace": True}}
check("two marketplaces' entries are BOTH returned, in order",
      po.enabled_ai_config_plugins(both)
      == ["ai-config@Morrison-Lab", "ai-config@other-marketplace"])

one = {"enabledPlugins": {"ai-config@Morrison-Lab": True, "oss@other": True}}
check("a single enabled entry is returned, unrelated plugins ignored",
      po.enabled_ai_config_plugins(one) == ["ai-config@Morrison-Lab"])

# --- enabled_ai_config_plugins: negatives ------------------------------------

check("a disabled (false) entry does not count",
      po.enabled_ai_config_plugins(
          {"enabledPlugins": {"ai-config@Morrison-Lab": False}}) == [])
check("a name merely CONTAINING ai-config does not count",
      po.enabled_ai_config_plugins(
          {"enabledPlugins": {"my-ai-config@x": True,
                              "ai-config-extras@x": True}}) == [])
check("no enabledPlugins key yields an empty list",
      po.enabled_ai_config_plugins({}) == [])
check("a non-dict enabledPlugins yields an empty list",
      po.enabled_ai_config_plugins({"enabledPlugins": ["ai-config@x"]}) == [])

# --- ai_config_entries: both polarities, unlike the truthy-only helper ------

check("ai_config_entries keeps an explicit false, which the name list drops",
      po.ai_config_entries(
          {"enabledPlugins": {"ai-config@Morrison-Lab": False,
                              "ai-config@other-marketplace": True}})
      == {"ai-config@Morrison-Lab": False,
          "ai-config@other-marketplace": True})
check("ai_config_entries still ignores non-ai-config names",
      po.ai_config_entries({"enabledPlugins": {"oss@x": True}}) == {})
check("ai_config_entries coerces truthy values to bool",
      po.ai_config_entries({"enabledPlugins": {"ai-config@x": 1}})
      == {"ai-config@x": True})

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
