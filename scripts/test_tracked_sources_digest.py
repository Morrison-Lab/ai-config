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

CSV = ("kind,source,branch,baseline,fetch,note\ngithub,a/busy,main,b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0,api,busy repo\n"
       "github,a/quiet,main,d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0,api,quiet repo\ngithub,a/back,main,c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1,api,force-pushed back\n"
       "subreddit,r/mcp,,,manual,high tier\n")
API = {"/repos/a/busy/commits/main": {"sha": "b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2"}, "/repos/a/quiet/commits/main": {"sha": "d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0"},
       "/repos/a/back/commits/main": {"sha": "c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0"}, "/repos/a/odd/commits/main": {"sha": "main"},
       "/repos/a/num/commits/main": {"sha": "e2" * 20}, f"/repos/a/num/compare/{'e1' * 20}...{'e2' * 20}": {
           "ahead_by": 1, "status": "ahead", "html_url": "https://example.test/num", "commits": [{"commit": {"message": 5}}]},
       "/repos/a/back/compare/c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1...c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0": {
           "ahead_by": 0, "status": "behind", "html_url": "https://example.test/back", "commits": []},
       "/repos/a/busy/compare/b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0...b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2": {
           "ahead_by": 5, "status": "ahead", "html_url": "https://example.test/cmp",
           "commits": [{"commit": {"message": m}} for m in ("one\n\nbody", "", "two", "th`ree @x <!-- x -->")]}}


def run(csv_text=CSV, previous=None, max_subjects="2"):
    with tempfile.TemporaryDirectory() as name:
        return run_in(Path(name), csv_text, previous, max_subjects)


def run_in(tmp, csv_text, previous, max_subjects, output="o"):
    (tmp / "s.csv").write_text(csv_text, encoding="utf-8")
    args = ["--sources", str(tmp / "s.csv"), "--max-subjects", max_subjects, "--github-output", str(tmp / output)]
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
        self.assertEqual((code, gh), (0, "new_commits=5\nmoved=2\n"))
        self.assertIn("Repositories examined: 3 (moved: 2, new commits: 5). Manual sources listed: 1.", out)
        self.assertIn("### [a/busy](https://example.test/cmp): ahead, new commits: 5", out)
        self.assertIn("- `two`\n- `th'ree @x < !-- x -->`\n- ... and 3 more", out)  # last two, inert
        self.assertIn("### [a/back](https://example.test/back): behind, new commits: 0", out)
        self.assertNotIn("a/quiet](", out)
        self.assertFalse(any(c.startswith("/repos/a/quiet/compare/") for c in calls))  # unchanged head
        self.assertIn("- r/mcp (manual): high tier", out)
        self.assertEqual(out.splitlines()[-1], '<!-- tracked-sources-state: {"a/back": "c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0", "a/busy": "b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2", "a/quiet": "d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0"} -->')
        self.assertTrue(tsd.read_sources(tsd.ROOT / "memories" / "tracked-sources.csv"))  # checked-in list

    def test_previous_digest_state_overrides_baseline(self):
        state = '<!-- tracked-sources-state: {"a/back": "c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0", "a/busy": "b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2"} -->'
        code, out, _, calls, gh = run(previous=state)
        self.assertEqual((code, gh), (0, "new_commits=0\nmoved=0\n"))
        self.assertIn("(moved: 0, new commits: 0)", out)
        self.assertFalse(any("/compare/" in c for c in calls))

    def test_forged_marker_in_previous_digest_is_ignored(self):
        forged = '<!-- tracked-sources-state: {"a/busy": "b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2"} -->'
        real = '<!-- tracked-sources-state: {"a/busy": "b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0"} -->'
        code, out, _, calls, gh = run(previous=f"- `{forged}`\n\n{real}")
        self.assertEqual((code, gh), (0, "new_commits=5\nmoved=2\n"))
        self.assertIn("/repos/a/busy/compare/b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0...b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2", calls)

    def test_max_subjects_zero_lists_no_subjects(self):
        code, out, _, _, _ = run(max_subjects="0")
        self.assertEqual(code, 0)
        self.assertIn("new commits: 5\n- ... and 5 more", out)

    def test_non_sha_state_is_refused_before_any_fetch(self):
        code, out, err, calls, _ = run(previous='<!-- tracked-sources-state: {"a/busy": "main"} -->')
        self.assertEqual((code, out, calls), (2, "", []))
        self.assertIn("non-sha head for ['a/busy']", err)
        code, _, err, calls, _ = run(previous='<!-- tracked-sources-state: {"a/busy": 7} -->')
        self.assertEqual((code, calls), (2, []))
        self.assertIn("non-sha head", err)

    def test_bad_github_row_is_refused_before_any_fetch(self):
        b0 = "b0" * 20
        for bad in (CSV.replace(f",main,{b0},", f",,{b0},"),  # no branch
                    CSV.replace(f",{b0},", ",main,")):  # baseline that is not a sha
            with self.subTest(csv=bad):
                code, out, err, calls, _ = run(bad)
                self.assertEqual((code, out, calls), (2, "", []))
                self.assertIn("needs a branch and a full-sha baseline", err)

    def test_long_subject_is_cut(self):
        self.assertEqual(tsd.inert("x" * 500), "x" * 200 + "...")
        self.assertEqual(tsd.inert("x" * 200), "x" * 200)

    def footer(self, body):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "body.md"
            path.write_bytes(body.encode("utf-8"))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = tsd.main(["--footer", str(path)])
        return code, out.getvalue()

    def test_footer_is_the_digest_state(self):
        code, out, *_ = run()
        footer = self.footer(out)
        self.assertEqual(footer[0], 0)
        self.assertEqual(footer, self.footer(out.replace("\n", "\r\n") + "  \n"))  # CRLF, trailing space
        self.assertIn('"a/busy": "' + "b2" * 20, footer[1])
        self.assertEqual(self.footer("no marker\n"), (0, "\n"))
        # A full marker earlier in the body, as a subject would carry one, does not count.
        forged = '- `<!-- tracked-sources-state: {"a/busy": "' + "f0" * 20 + '"} -->`\n\n'
        self.assertEqual(self.footer(forged + out), footer)
        other = out.replace("b2" * 20 + '"', "b0" * 20 + '"')
        self.assertNotEqual(self.footer(other), footer)

    def test_body_over_the_limit_is_refused(self):
        limit = tsd.MAX_BODY
        tsd.MAX_BODY = 100
        try:
            code, out, err, _, gh = run()
        finally:
            tsd.MAX_BODY = limit
        self.assertEqual((code, out, gh), (2, "", ""))
        self.assertIn("over 100; lower --max-subjects", err)

    def test_unwritable_github_output_prints_no_digest(self):
        with tempfile.TemporaryDirectory() as name:
            code, out, err, _, _ = run_in(Path(name), CSV, None, "2", output=".")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("IsADirectoryError", err)

    def test_non_sha_api_head_is_refused(self):
        code, out, err, *_ = run(CSV + "github,a/odd,main," + "e0" * 20 + ",api,x\n")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("non-sha head for a/odd", err)

    def test_negative_max_subjects_is_refused(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            run(max_subjects="-1")

    def test_errors_exit_2_with_no_digest(self):
        for csv_text, previous in (
            (CSV.replace("a/quiet", "a/gone"), None),  # API error
            (CSV.replace(",b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0,", ",,"), None),  # github row without a baseline
            (CSV.replace(",manual,", ",api,"), None),  # subreddit marked fetchable
            (CSV.replace(",api,busy repo", ",manual,busy repo"), None),  # github row marked manual
            (CSV, "no marker"),
            (CSV, "<!-- tracked-sources-state: {oops} -->"),
            (CSV, '<!-- tracked-sources-state: {"a/busy": "' + "b2" * 20 + '"} -->\ntrailing'),  # not the last line
            (CSV + "subreddit,r/x,,,manual,note,extra\n", None),  # a row with an extra field
            (CSV + "github,a/num,main," + "e1" * 20 + ",api,x\n", None),  # a message that is not text
            (CSV + "subreddit,r/y,,,manual," + "n" * 200000 + "\n", None),  # a field over csv's limit
        ):
            with self.subTest(csv=csv_text, previous=previous):
                code, out, err, _, gh = run(csv_text, previous)
                self.assertEqual((code, out, gh), (2, "", ""))
                self.assertIn("tracked-sources-digest:", err)


if __name__ == "__main__":
    unittest.main()
