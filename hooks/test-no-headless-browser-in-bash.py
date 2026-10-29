#!/usr/bin/env python3
"""Tests for no-headless-browser-in-bash.py.

Both directions are exercised: the blocks (including the exact 2026-10-28
incident, a script file that imports Playwright) and the passes (a command
that only mentions a browser, or runs an ordinary script).
"""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else str(Path(__file__).with_name("no-headless-browser-in-bash.py"))
)
spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def run(command, tool="Bash"):
    buf = io.StringIO()
    stdin, sys.stdin = sys.stdin, io.StringIO(json.dumps(
        {"tool_name": tool, "tool_input": {"command": command}}
    ))
    try:
        with redirect_stdout(buf):
            guard.main()
    finally:
        sys.stdin = stdin
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


class TestBlocks(unittest.TestCase):
    def assert_blocked(self, command):
        result = run(command)
        self.assertIsNotNone(result, f"expected a block for: {command}")
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_incident_script_file_importing_playwright(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "redir.js"
            script.write_text("const { chromium } = require('playwright');\n", encoding="utf-8")
            self.assert_blocked(f"cd {tmp} && node {script}")

    def test_python_script_file_importing_playwright(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "check.py"
            script.write_text("from playwright.sync_api import sync_playwright\n", encoding="utf-8")
            self.assert_blocked(f"python3 {script}")

    def test_inline_node(self):
        self.assert_blocked("node -e \"require('playwright').chromium.launch()\"")

    def test_inline_python(self):
        self.assert_blocked("python3 -c 'import selenium'")

    def test_browser_binary(self):
        self.assert_blocked("chromium --headless --dump-dom https://example.com")
        self.assert_blocked("cd /tmp && google-chrome-stable --headless=new --screenshot")

    def test_wrapped_browser_binary(self):
        self.assert_blocked("xvfb-run -a firefox https://example.com")
        self.assert_blocked("HOME=/tmp timeout 30 chromium --headless")

    def test_automation_cli(self):
        self.assert_blocked("npx playwright screenshot https://example.com out.png")
        self.assert_blocked("npx -y puppeteer browsers install chrome")
        self.assert_blocked("lighthouse https://example.com --chrome-flags=--headless")


class TestReviewedBlocks(unittest.TestCase):
    def blocked(self, command):
        result = run(command)
        self.assertIsNotNone(result, f"expected a block for: {command}")

    def test_stdin_scripts(self):
        self.blocked("python3 - <<EOF\nfrom playwright.sync_api import sync_playwright\nEOF")
        self.blocked("node << 'EOF'\nconst p = require('puppeteer')\nEOF")

    def test_module_and_library_flags(self):
        self.blocked("python3 -m playwright install")
        self.blocked("node -r playwright x.js")
        self.blocked("uv run --with playwright python x.py")

    def test_shell_wrappers(self):
        self.blocked('bash -c "chromium --headless"')
        self.blocked("sh -c 'chromium --headless'")

    def test_quoted_path_and_flagged_wrappers(self):
        self.blocked('"/usr/bin/chromium" --headless')
        self.blocked("nohup chromium --headless &")
        self.blocked("timeout -s KILL 5 chromium")
        self.blocked("sudo -u x chromium")
        self.blocked("nice -n 5 chromium")
        self.blocked("xvfb-run -a -s '-screen 0 1280x1024x24' chromium")

    def test_env_assignments_and_background_operator(self):
        self.blocked("env DISPLAY=:99 chromium --headless")
        self.blocked("env CHROME_BIN=/usr/bin/chromium chromium-browser --headless")
        self.blocked("echo hi & chromium --headless")

    def test_shell_keywords(self):
        self.blocked("if true; then chromium; fi")
        self.blocked("! chromium")

    def test_scoped_package_and_r(self):
        self.blocked("npx @playwright/test test")
        self.blocked("Rscript -e 'library(chromote)'")

    def test_relative_script_uses_payload_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pw.py").write_text("from playwright.sync_api import sync_playwright\n", encoding="utf-8")
            buf = io.StringIO()
            stdin, sys.stdin = sys.stdin, io.StringIO(json.dumps(
                {"tool_name": "Bash", "cwd": tmp, "tool_input": {"command": "python3 pw.py"}}))
            try:
                with redirect_stdout(buf):
                    guard.main()
            finally:
                sys.stdin = stdin
            self.assertIn("deny", buf.getvalue())


class TestReviewedPasses(unittest.TestCase):
    def passes(self, command):
        self.assertIsNone(run(command), f"expected a pass for: {command}")

    def test_prose_mentions(self):
        self.passes("gh pr create --body 'x\nchromium launch is blocked\n'")
        self.passes('git commit -m "x; chromium"')
        self.passes("gh pr create --body \"$(cat <<'EOF'\nchromium here\nEOF\n)\"")

    def test_browser_prefixed_tools_and_versions(self):
        self.passes("chrome-devtools --help")
        self.passes("lighthouse-ci --help")
        self.passes("chromium --version")
        self.passes("firefox -v")

    def test_library_word_outside_the_interpreter_segment(self):
        self.passes("python3 -c 'print(1)' ; cat playwright.txt")
        self.passes("python3 -c 'import json' # playwright")
        self.passes("python3 -c 'print(\"webdriver\")'")

    def test_comment_only_mention_in_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "notes.py"
            script.write_text("# we should never use selenium here\nprint(1)\n", encoding="utf-8")
            self.passes(f"python3 {script}")

    def test_non_string_command_fails_open(self):
        stdin, sys.stdin = sys.stdin, io.StringIO(
            json.dumps({"tool_name": "Bash", "tool_input": {"command": 123}}))
        try:
            self.assertEqual(guard.main(), 0)
        finally:
            sys.stdin = stdin

    def test_escape_valve_only_as_prefix(self):
        self.passes("ALLOW_HEADLESS_BROWSER=1 chromium --headless")
        self.assertIsNotNone(run("echo ALLOW_HEADLESS_BROWSER=1; chromium"))
        self.assertIsNotNone(run("ALLOW_HEADLESS_BROWSER=10 chromium"))


class TestPasses(unittest.TestCase):
    def assert_passes(self, command):
        self.assertIsNone(run(command), f"expected a pass for: {command}")

    def test_mention_is_not_launch(self):
        self.assert_passes("grep -rn playwright /home/user/ai-config")
        self.assert_passes("echo 'do not run chromium here'")
        self.assert_passes("pip install playwright")
        self.assert_passes("git commit -m 'block chromium and playwright from Bash'")

    def test_ordinary_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "ok.js"
            script.write_text("console.log('hello');\n", encoding="utf-8")
            self.assert_passes(f"node {script}")

    def test_missing_script_fails_open(self):
        self.assert_passes("node /nonexistent/redir.js")

    def test_curl(self):
        self.assert_passes("curl -sS https://morrison-lab.github.io/lds/ -o page.html")

    def test_non_bash_tool(self):
        self.assertIsNone(run("chromium", tool="Read"))

    def test_escape_valve(self):
        self.assert_passes("ALLOW_HEADLESS_BROWSER=1 chromium --headless --dump-dom x")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
