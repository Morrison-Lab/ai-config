"""Tests for scripts/tracked-sources-digest.py on fixture API responses."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "tracked_sources_digest", Path(__file__).with_name("tracked-sources-digest.py"))
tsd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tsd)

CSV = ("kind,source,branch,baseline,fetch,note\ngithub,a/busy,main,b0,api,busy repo\n"
       "github,a/quiet,main,q0,api,quiet repo\ngithub,a/back,main,k1,api,force-pushed back\n"
       "subreddit,r/mcp,,,manual,high tier\n")
API = {"/repos/a/busy/commits/main": {"sha": "b2"}, "/repos/a/quiet/commits/main": {"sha": "q0"},
       "/repos/a/back/commits/main": {"sha": "k0"},
       "/repos/a/back/compare/k1...k0": {
           "ahead_by": 0, "status": "behind", "html_url": "https://example.test/back", "commits": []},
       "/repos/a/busy/compare/b0...b2": {
           "ahead_by": 5, "status": "ahead", "html_url": "https://example.test/cmp",
           "commits": [{"commit": {"message": m}} for m in ("one\n\nbody", "", "two", "th`ree @x <!-- x -->")]}}


def run(csv_text=CSV, previous=None, max_subjects="2"):
    tmp_dir = tempfile.TemporaryDirectory()
    tmp = Path(tmp_dir.name)
    (tmp / "s.csv").write_text(csv_text, encoding="utf-8")
    args = ["--sources", str(tmp / "s.csv"), "--max-subjects", max_subjects, "--github-output", str(tmp / "o")]
    if previous is not None:
        (tmp / "p.md").write_text(previous, encoding="utf-8")
        args += ["--previous", str(tmp / "p.md")]
    calls = []

    def fetch(path):
        calls.append(path)
        if path not in API:
            raise tsd.DigestError(f"GET {path} failed: HTTP Error 404")
        return API[path]
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = tsd.main(args, fetch=fetch)
    gh = (tmp / "o").read_text(encoding="utf-8") if (tmp / "o").exists() else ""
    tmp_dir.cleanup()
    return code, out.getvalue(), err.getvalue(), calls, gh


class DigestTest(unittest.TestCase):
    def test_digest_lists_new_commits_and_counts_sources(self):
        code, out, _, calls, gh = run()
        self.assertEqual((code, gh), (0, "new_commits=5\nmoved=2\npairs=[[\"a/busy\", \"b0\", \"b2\"], [\"a/back\", \"k1\", \"k0\"]]\n"))
        self.assertIn("Examined 3 repositories (2 moved, 5 new commits); listed 1 manual sources.", out)
        self.assertIn("### [a/busy](https://example.test/cmp): 5 new commits (ahead)", out)
        self.assertIn("- `two`\n- `th'ree @x < !-- x -->`\n- ... and 3 more", out)  # last two, inert
        self.assertIn("### [a/back](https://example.test/back): 0 new commits (behind)", out)
        self.assertNotIn("a/quiet](", out)
        self.assertFalse(any(c.startswith("/repos/a/quiet/compare/") for c in calls))  # unchanged head
        self.assertIn("- r/mcp (manual): high tier", out)
        self.assertIn('<!-- tracked-sources-state: {"a/back": "k0", "a/busy": "b2", "a/quiet": "q0"} -->', out)
        self.assertTrue(tsd.read_sources(tsd.ROOT / "memories" / "tracked-sources.csv"))  # checked-in list

    def test_previous_digest_state_overrides_baseline(self):
        state = '<!-- tracked-sources-state: {"a/back": "k0", "a/busy": "b2"} -->'
        code, out, _, calls, gh = run(previous=state)
        self.assertEqual((code, gh), (0, "new_commits=0\nmoved=0\npairs=[]\n"))
        self.assertIn("(0 moved, 0 new commits)", out)
        self.assertFalse(any("/compare/" in c for c in calls))

    def test_forged_marker_in_previous_digest_is_ignored(self):
        forged = '<!-- tracked-sources-state: {"a/busy": "b2"} -->'
        real = '<!-- tracked-sources-state: {"a/busy": "b0"} -->'
        code, out, _, calls, gh = run(previous=f"- `{forged}`\n\n{real}")
        self.assertEqual((code, gh), (0, "new_commits=5\nmoved=2\npairs=[[\"a/busy\", \"b0\", \"b2\"], [\"a/back\", \"k1\", \"k0\"]]\n"))
        self.assertIn("/repos/a/busy/compare/b0...b2", calls)

    def test_max_subjects_zero_lists_no_subjects(self):
        code, out, _, _, _ = run(max_subjects="0")
        self.assertEqual(code, 0)
        self.assertIn("(ahead)\n- ... and 5 more", out)

    def test_errors_exit_2_with_no_digest(self):
        for csv_text, previous in (
            (CSV.replace("a/quiet", "a/gone"), None),  # API error
            (CSV.replace(",b0,", ",,"), None),  # github row without a baseline
            (CSV.replace(",manual,", ",api,"), None),  # subreddit marked fetchable
            (CSV, "no marker"),
            (CSV, "<!-- tracked-sources-state: {oops} -->"),
        ):
            with self.subTest(csv=csv_text, previous=previous):
                code, out, err, _, gh = run(csv_text, previous)
                self.assertEqual((code, out, gh), (2, "", ""))
                self.assertIn("tracked-sources-digest:", err)


if __name__ == "__main__":
    unittest.main()
