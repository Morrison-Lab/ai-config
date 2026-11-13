"""Tests for scripts/check-advisor-seat.py: each rule refuses, and passes.

Model names are ones this lab's sessions use: the caller here runs
`claude-opus-5-5`, and OpenCode Go serves `kimi-k3` and `glm-5.3`
(skills/delegate-to-opencode/SKILL.md).
"""

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


def argv(caller="claude-opus-5-5", engine="opencode", model="kimi-k3",
         effort="high", *extra):
    return ["--caller-model", caller, "--engine", engine, "--model", model,
            "--effort", effort, *extra]


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = seat.main(args)
    return code, out.getvalue().strip(), err.getvalue().strip()


class FamilyTest(unittest.TestCase):
    def test_known_families(self):
        self.assertEqual(seat.family("claude-sonnet-5-5"), "anthropic")
        self.assertEqual(seat.family("gemini-4-argon-high"), "google")
        self.assertEqual(seat.family("opencode/glm-5.3"), "zhipu")
        self.assertEqual(seat.family("DeepSeek-V4-Pro"), "deepseek")

    def test_provider_qualified_ids(self):
        self.assertEqual(
            seat.family("bedrock/us.anthropic.claude-opus-5-5"), "anthropic"
        )
        self.assertEqual(seat.family("ollama:qwen3.8-max"), "alibaba")

    def test_prefix_needs_a_boundary(self):
        self.assertEqual(seat.family("o3-mini"), "openai")
        with self.assertRaises(seat.Refusal):
            seat.family("o3x")

    def test_two_families_in_one_name_refused(self):
        for name in ("kimi-k3.claude-haiku", "gpt-5.claude"):
            with self.assertRaises(seat.Refusal):
                seat.family(name)

    def test_unknown_family_fails_closed(self):
        with self.assertRaises(seat.Refusal):
            seat.family("mystery-model-1")


class SameModelTest(unittest.TestCase):
    def test_dated_snapshot_matches(self):
        self.assertTrue(seat.same_model("gpt-5", "gpt-5-2025-08-07"))
        self.assertTrue(seat.same_model("kimi-k3", "opencode/Kimi-K3"))
        self.assertTrue(seat.same_model("kimi-k3", "kimi-k3:free"))

    def test_sibling_model_does_not_match(self):
        self.assertFalse(seat.same_model("gpt-5", "gpt-5-mini"))
        self.assertFalse(seat.same_model("kimi-k3", "kimi-k2"))


class MainTest(unittest.TestCase):
    def test_cross_family_is_independent(self):
        self.assertEqual(run(argv()), (0, "independent", ""))

    def test_same_family_refused(self):
        code, out, err = run(argv(model="claude-sonnet-5-5"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("caller's family", err)

    def test_same_family_allowed_is_labelled_weaker(self):
        args = argv("claude-opus-5-5", "opencode", "claude-sonnet-5-5",
                    "high", "--allow-same-family")
        self.assertEqual(run(args), (0, "weaker: same family (anthropic)", ""))

    def test_allow_same_family_still_checks_reported_model(self):
        args = argv("claude-opus-5-5", "opencode", "claude-sonnet-5-5",
                    "high", "--allow-same-family",
                    "--reported-model", "claude-haiku-5-5")
        self.assertEqual(run(args)[0], 2)

    def test_codex_engines_refused(self):
        for engine in ("codex", "Codex", "codex-cli", "openai-codex"):
            code, _, err = run(argv(engine=engine))
            self.assertEqual(code, 2, engine)
            self.assertIn("never an advisor seat", err)
        for engine in ("opencode", "agy"):
            self.assertEqual(run(argv(engine=engine))[0], 0, engine)

    def test_reported_snapshot_passes_through_main(self):
        args = argv("claude-opus-5-5", "opencode", "gpt-5", "high",
                    "--reported-model", "gpt-5-2025-08-07")
        self.assertEqual(run(args), (0, "independent", ""))

    def test_family_option_overrides_a_builtin(self):
        args = argv("claude-opus-5-5", "opencode", "kimi-k3", "high",
                    "--family", "kimi=anthropic")
        self.assertEqual(run(args)[0], 2)

    def test_inherited_effort_refused(self):
        for effort in (" ", "default", "Inherit", "auto"):
            code, _, err = run(argv(effort=effort))
            self.assertEqual(code, 2, effort)
            self.assertIn("effort", err)

    def test_reported_model_mismatch_refused(self):
        code, _, err = run(argv("claude-opus-5-5", "opencode", "kimi-k3",
                                "high", "--reported-model", "kimi-k2"))
        self.assertEqual(code, 2)
        self.assertIn("fallback", err)

    def test_reported_model_match_passes(self):
        args = argv("claude-opus-5-5", "opencode", "kimi-k3", "high",
                    "--reported-model", "Kimi-K3")
        self.assertEqual(run(args)[0], 0)

    def test_unknown_models_refused(self):
        for args in (argv(model="mystery-1"), argv(caller="mystery-1")):
            code, _, err = run(args)
            self.assertEqual(code, 2)
            self.assertIn("unknown model family", err)

    def test_family_option_extends_the_table(self):
        args = argv("claude-opus-5-5", "opencode", "granite-4", "high",
                    "--family", "granite=ibm")
        self.assertEqual(run(args), (0, "independent", ""))

    def test_family_option_rejects_malformed_pair(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                seat.main(argv("claude-opus-5-5", "opencode", "kimi-k3",
                               "high", "--family", "granite"))


if __name__ == "__main__":
    unittest.main()
