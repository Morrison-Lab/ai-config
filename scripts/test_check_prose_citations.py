#!/usr/bin/env python3
"""Regression tests for check-prose-citations.py (ai-config#3660).

Each check gets a negative control: a fixture carrying a KNOWN bad citation,
asserted to produce a finding, beside the same shape done right, asserted not
to.  Until the checker has been seen to produce a non-zero, a zero from it on a
real diff is not evidence of anything (shared/principles/fail-fast.md).

Fixtures are throwaway git repositories in a tmpdir, so nothing lands where a
corpus scan would read it.
"""
import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "cpc", Path(__file__).parent / "check-prose-citations.py"
)
cpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpc)

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


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def run(prose: str, extra: dict[str, str] | None = None):
    """Commit a base, then add `prose` in doc.md on a branch; return results."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        git(root, "init", "-q", "-b", "main")
        git(root, "config", "user.email", "t@example.invalid")
        git(root, "config", "user.name", "t")
        (root / "hooks").mkdir()
        (root / "hooks" / "guard.py").write_text(
            "# The guard refuses every push while blocking.\n" + "x = 1\n" * 9
        )
        (root / "doc.md").write_text("# Doc\n\nOld line about `hooks/guard.py:99`.\n")
        for name, body in (extra or {}).items():
            (root / name).write_text(body)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "base")
        git(root, "checkout", "-q", "-b", "feat")
        with open(root / "doc.md", "a") as fh:
            fh.write(prose)
        git(root, "commit", "-q", "-am", "prose")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cpc.main(["--root", str(root), "--base", "main", "--json"])
        data = json.loads(out.getvalue())
        data["rc"] = rc
        return data


def kinds(data):
    return [f["kind"] for f in data["findings"]]


# path-line: past the end, missing file, and an in-range control.
d = run("A cite to `hooks/guard.py:40` here.\n")
check("path-line past the end is reported", kinds(d) == ["path-line"])
check("finding names the added line", d["findings"][0]["line"] == 4)
check("advisory: exit 0 on a finding", d["rc"] == 0)
d = run("See `hooks/missing.py:3` here.\n")
check("path-line to a missing file is reported", kinds(d) == ["path-line"])
d = run("See `hooks/guard.py:2-10` here.\n")
check("in-range path-line range is not reported", kinds(d) == [])
d = run("See `hooks/guard.py:2-11` here.\n")
check("range end past the file is reported", kinds(d) == ["path-line"])
d = run("Visit https://example.com:8080/x for more.\n")
check("a URL port is not a path-line citation", kinds(d) == [])
d = run("Connect to example.com:443 or host.local:8080 directly.\n")
check("a bare host:port is not a path-line citation", kinds(d) == [])

# Pre-existing lines are out of scope: doc.md's base line cites :99.
d = run("Nothing to see.\n")
check("unchanged lines are not examined", kinds(d) == [] and d["examined_lines"] == 1)

# quote-in-file: absent phrase reported, present phrase (rewrapped) not.
d = run('`hooks/guard.py` says "refuses every pull while blocking" plainly.\n')
check("misquote attributed to a file is reported", kinds(d) == ["quote-in-file"])
d = run('Its comment in `hooks/guard.py` says "refuses every  push while blocking".\n')
check("accurate quote (whitespace differs) is not reported", kinds(d) == [])
d = run('`hooks/guard.py` is short; "a phrase nobody attributed" stands alone.\n')
check("a quote with no quotation verb is not attributed", kinds(d) == [])

d = run("`hooks/guard.py` says \u201crefuses every pull while blocking\u201d.\n")
check("curly-quoted misquote is reported", kinds(d) == ["quote-in-file"])

# An added line beginning "++ " is content, not a file header, and the
# lines after it in the same hunk are still examined.
d = run("++ not a header\nSee `hooks/guard.py:40` here.\n")
check("'++ ' content line keeps the hunk", kinds(d) == ["path-line"]
      and d["findings"][0]["line"] == 5)

# corpus-state: reported unless the derivation is on the line.
d = run("This rule is already recorded above.\n")
check("corpus-state claim is reported", kinds(d) == ["corpus-state"])
d = run("This is already recorded above (`grep -n rule doc.md`).\n")
check("corpus-state claim with its query is not reported", kinds(d) == [])

d = run("The [style guide](https://example.invalid/g) already covered the case.\n")
check("corpus-state claim that links its evidence is not reported", kinds(d) == [])
d = run('Inline comments in `hooks/guard.py` compare "a login nobody quoted here".\n')
check("'comments' is not a quotation verb", kinds(d) == [])

# Fenced code is not prose.
d = run("```\nsee hooks/guard.py:400 and already recorded\n```\n")
check("fenced lines are skipped", kinds(d) == [] and d["examined_lines"] == 0)

# A bare name that resolves neither from the root nor beside doc.md.
d = run("Cite `guard.py:3`.\n")
check("unresolvable relative path is reported", kinds(d) == ["path-line"])

# quote-in-issue, with the network call replaced by a canned body.
cpc.issue_body = lambda num, repo, cache: (
    "The proposal keeps the hook advisory." if num == "42" else None)
_main = cpc.main
cpc.main = lambda argv: _main(argv + ["--issues"])
d = run('#42 proposes "keeps the hook advisory" as the scope.\n')
check("accurate issue quote is not reported", kinds(d) == [])
d = run('#42 proposes "makes the hook blocking" as the scope.\n')
check("issue misquote is reported", kinds(d) == ["quote-in-issue"])
d = run('#43 says "an unreadable issue body here" in full.\n')
check("unreadable issue is reported", kinds(d) == ["quote-in-issue"])
cpc.main = _main
d = run('#42 proposes "makes the hook blocking" as the scope.\n')
check("without --issues, issue quotes are not checked", kinds(d) == [])

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
