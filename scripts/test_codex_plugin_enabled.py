#!/usr/bin/env python3
"""Regression tests for the Codex plugin-enable detector."""
import importlib.util
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("codex-plugin-enabled.py")
spec = importlib.util.spec_from_file_location("codex_plugin_enabled", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

passes = 0
failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += condition
    failures += not condition


def enabled(text: str) -> bool:
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "config.toml"
        path.write_text(text, encoding="utf-8")
        return module.ai_config_plugin_enabled(path)


check("enabled ai-config plugin is detected", enabled('[plugins."ai-config@the repository owner"]\nenabled = true\n'))
check("disabled ai-config plugin is ignored", not enabled('[plugins."ai-config@the repository owner"]\nenabled = false\n'))
check("another plugin's enabled flag is ignored", not enabled('[plugins."other@market"]\nenabled = true\n'))
check("a later ai-config table is still found", enabled('[plugins."other@market"]\nenabled = true\n\n[plugins."ai-config@the repository owner"]\nenabled = true\n'))
check("quoted false is not treated as enabled", not enabled("[plugins.'ai-config@the repository owner']\nenabled = false # keep installed but off\n"))

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
