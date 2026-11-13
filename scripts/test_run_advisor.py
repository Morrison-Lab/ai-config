"""Tests for scripts/run-advisor.py, with a fake engine and no network."""

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "run_advisor", Path(__file__).with_name("run-advisor.py")
)
adv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adv)


def sse(model, *pieces):
    events = [{"model": model, "choices": [{"delta": {"content": p}}]}
              for p in pieces]
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n"


class FakeRun:
    """Records each call and returns a canned CompletedProcess."""

    def __init__(self, stdout="", returncode=0):
        self.calls, self.stdout, self.returncode = [], stdout, returncode

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, "")


class RunAdvisorTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.briefing = Path(tmp.name) / "briefing.md"
        self.briefing.write_text("Does line 40 contradict line 12?\n", encoding="utf-8")

    def go(self, fake, engine="opencode", model="kimi-k3", effort="high", *extra):
        argv = ["--caller-model", "claude-opus-5-5", "--engine", engine,
                "--model", model, "--effort", effort,
                "--briefing", str(self.briefing), *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = adv.main(argv, run=fake)
        return code, out.getvalue().strip(), err.getvalue().strip()

    def test_opencode_answer_and_verified_seat(self):
        code, out, err = self.go(FakeRun(sse("kimi-k3", "No, ", "they agree.")))
        self.assertEqual((code, out), (0, "No, they agree."))
        self.assertIn("independent; answered by kimi-k3", err)

    def test_opencode_request_is_read_only_and_pinned(self):
        fake = FakeRun(sse("kimi-k3", "ok"))
        self.go(fake)
        argv, kwargs = fake.calls[0]
        body = json.loads(kwargs["input"])
        self.assertNotIn("tools", body)
        self.assertEqual((body["model"], body["reasoning_effort"]),
                         ("kimi-k3", "high"))
        self.assertIn("line 40", body["messages"][0]["content"])
        self.assertNotIn("line 40", " ".join(argv))

    def test_opencode_bad_replies(self):
        no_model = "data: " + json.dumps(
            {"choices": [{"delta": {"content": "hi"}}]}) + "\n"
        cases = [
            (FakeRun(sse("glm-5.3", "x")), 2, "not the requested"),
            (FakeRun(no_model), 1, "names no model"),
            (FakeRun(sse("kimi-k3", "")), 1, "no answer"),
            (FakeRun('{"error":"limit"}', returncode=22), 1, "curl exited 22"),
        ]
        for fake, want_code, want_err in cases:
            with self.subTest(want_err):
                code, out, err = self.go(fake)
                self.assertEqual((code, out), (want_code, ""))
                self.assertIn(want_err, err)

    def test_refusals_before_any_call(self):
        cases = [("claude-sonnet-5-5", "high", "caller's family"),
                 ("kimi-k3", "default", "names no level")]
        for model, effort, want_err in cases:
            with self.subTest(want_err):
                fake = FakeRun()
                code, _, err = self.go(fake, "opencode", model, effort)
                self.assertEqual((code, fake.calls), (2, []))
                self.assertIn(want_err, err)
        with self.assertRaises(SystemExit) as ctx:  # codex is not a choice
            self.go(FakeRun(), "codex", "gpt-5")
        self.assertEqual(ctx.exception.code, 2)
        self.briefing.write_text("  \n", encoding="utf-8")
        self.assertIn("briefing is empty", self.go(FakeRun())[2])
        self.briefing.unlink()
        self.assertEqual(self.go(FakeRun())[0], 2)

    def test_agy_plan_mode_and_unverified_label(self):
        fake = FakeRun("They agree.\n")
        code, out, err = self.go(fake, "agy", "gemini-4-argon-high")
        self.assertEqual((code, out), (0, "They agree."))
        self.assertIn("unverified", err)
        argv = fake.calls[0][0]
        self.assertEqual(argv[argv.index("--mode") + 1], "plan")
        self.assertTrue(argv[-1].startswith("--print=Does line 40"))
        self.assertEqual(self.go(FakeRun("\n"), "agy", "gemini-4-argon-high")[0], 1)

    def test_dry_run_calls_nothing_and_hides_briefing(self):
        for engine, model, start in (("opencode", "kimi-k3", "curl "),
                                     ("agy", "gemini-4-argon-high", "agy ")):
            with self.subTest(engine):
                fake = FakeRun()
                code, out, err = self.go(fake, engine, model, "high", "--dry-run")
                self.assertEqual((code, fake.calls), (0, []))
                self.assertTrue(out.startswith(start))
                self.assertNotIn("line 40", out)
                self.assertIn("seat: independent", err)


if __name__ == "__main__":
    unittest.main()
