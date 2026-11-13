"""Tests for scripts/check-advisor-seat.py: each rule refuses, and passes."""

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check_advisor_seat", Path(__file__).with_name("check-advisor-seat.py")
)
seat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seat)

BASE = ["--caller-model", "claude-opus-5-5", "--engine", "opencode",
        "--model", "kimi-k3", "--effort", "high"]


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = seat.main(argv)
    return code, out.getvalue().strip(), err.getvalue().strip()


class FamilyTest(unittest.TestCase):
    def test_known_families(self):
        self.assertEqual(seat.family("claude-sonnet-5-5"), "anthropic")
        self.assertEqual(seat.family("gemini-4-argon-high"), "google")
        self.assertEqual(seat.family("opencode/glm-5.3"), "zhipu")
        self.assertEqual(seat.family("DeepSeek-V4-Pro"), "deepseek")

    def test_no_prefix_shadows_another(self):
        # family() returns the first match, so an overlap would make the
        # answer depend on dict order.
        prefixes = list(seat.FAMILY_PREFIXES)
        for a in prefixes:
            for b in prefixes:
                if a != b:
                    self.assertFalse(b.startswith(a), (a, b))

    def test_unknown_family_fails_closed(self):
        with self.assertRaises(seat.Refusal):
            seat.family("mystery-model-1")


class MainTest(unittest.TestCase):
    def test_cross_family_is_independent(self):
        self.assertEqual(run(BASE), (0, "independent", ""))

    def test_same_family_refused(self):
        argv = BASE[:5] + ["claude-sonnet-5-5", "--effort", "high"]
        code, out, err = run(argv)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("caller's family", err)

    def test_same_family_allowed_is_labelled_weaker(self):
        argv = BASE[:5] + ["claude-sonnet-5-5", "--effort", "high",
                           "--allow-same-family"]
        self.assertEqual(run(argv), (0, "weaker: same family (anthropic)", ""))

    def test_codex_engine_refused(self):
        argv = BASE.copy()
        argv[3] = "Codex"
        code, _, err = run(argv)
        self.assertEqual(code, 2)
        self.assertIn("never an advisor seat", err)

    def test_blank_effort_refused(self):
        code, _, err = run(BASE[:-1] + [" "])
        self.assertEqual(code, 2)
        self.assertIn("effort", err)

    def test_reported_model_mismatch_refused(self):
        code, _, err = run(BASE + ["--reported-model", "kimi-k2"])
        self.assertEqual(code, 2)
        self.assertIn("fallback", err)

    def test_reported_model_match_passes(self):
        self.assertEqual(run(BASE + ["--reported-model", "Kimi-K3"])[0], 0)

    def test_unknown_advisor_model_refused(self):
        code, _, err = run(BASE[:5] + ["mystery-1", "--effort", "high"])
        self.assertEqual(code, 2)
        self.assertIn("unknown model family", err)


if __name__ == "__main__":
    unittest.main()
