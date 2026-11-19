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
       "github,a/quiet,main,q0,api,quiet repo\nsubreddit,r/mcp,,,manual,high tier\n")
API = {"/repos/a/busy/commits/main": {"sha": "b2"}, "/repos/a/quiet/commits/main": {"sha": "q0"},
       "/repos/a/busy/compare/b0...b2": {
           "ahead_by": 3, "status": "ahead", "html_url": "https://example.test/cmp",
           "commits": [{"commit": {"message": m}} for m in ("one\n\nbody", "two", "th`ree @x")]}}


def run(csv_text=CSV, previous=None):
    tmp = Path(tempfile.mkdtemp())
    (tmp / "s.csv").write_text(csv_text, encoding="utf-8")
    args = ["--sources", str(tmp / "s.csv"), "--max-subjects", "2", "--github-output", str(tmp / "o")]
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
    return code, out.getvalue(), err.getvalue(), calls, gh


class DigestTest(unittest.TestCase):
    def test_digest_lists_new_commits_and_counts_sources(self):
        code, out, _, calls, gh = run()
        self.assertEqual((code, gh), (0, "new_commits=3\n"))
        self.assertIn("Examined 2 repositories (3 new commits); listed 1 manual sources.", out)
        self.assertIn("### [a/busy](https://example.test/cmp): 3 new commits (ahead)", out)
        self.assertIn("- `two`\n- `th'ree @x`\n- ... and 1 more", out)  # newest, as code spans
        self.assertNotIn("a/quiet](", out)
        self.assertEqual(sum("/compare/" in c for c in calls), 1)  # none for an unchanged head
        self.assertIn("- r/mcp (manual): high tier", out)
        self.assertIn('<!-- tracked-sources-state: {"a/busy": "b2", "a/quiet": "q0"} -->', out)
        self.assertTrue(tsd.read_sources(tsd.ROOT / "memories" / "tracked-sources.csv"))  # checked-in list

    def test_previous_digest_state_overrides_baseline(self):
        code, out, _, calls, gh = run(previous='<!-- tracked-sources-state: {"a/busy": "b2"} -->')
        self.assertEqual((code, gh), (0, "new_commits=0\n"))
        self.assertIn("(0 new commits)", out)
        self.assertFalse(any("/compare/" in c for c in calls))

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
