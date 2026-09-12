#!/usr/bin/env python3
"""Regression tests for check-chained-commit-push-in-fences.py.

The load-bearing case is the negative control.  Until the sweep has been seen
to produce a non-zero on a KNOWN chained block, a zero from it against the real
corpus is not evidence of anything --- which is the failure
[#3199](https://github.com/Morrison-Lab/ai-config/issues/3199) records against
the hand-run sweep it replaces, and the general argument in
`shared/workflow/batch-merge-and-resolve.md` about a sweep with no negative
control.

The second load-bearing case is fence indentation.  A block nested in a list
item is the shape the earlier sweep is believed to have missed, so an indented
fence carrying the chained form is asserted to be found and an extractor
anchored at column 0 would fail here.

Fixtures live in a tmpdir git repo, so nothing lands anywhere the corpus scan
would pick it up.
"""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

REPO = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "cccp", Path(__file__).parent / "check-chained-commit-push-in-fences.py"
)
cccp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cccp)

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


# ---------------------------------------------------------------------------
# Fence extraction
# ---------------------------------------------------------------------------

blocks = list(cccp.fenced_blocks(
    "text\n"
    "```bash\n"
    "git status\n"
    "```\n"
    "more text\n"
    "  ```bash\n"
    "  git log\n"
    "  ```\n"
))
check("both a column-0 and an indented fence are extracted", len(blocks) == 2)
check("the indented block's body has its indentation stripped",
      blocks[1][2] == "git log")
check("the reported line names the opening fence",
      blocks[0][0] == 2 and blocks[1][0] == 6)

tilde = list(cccp.fenced_blocks("~~~sh\ngit status\n~~~\n"))
check("a tilde fence is extracted too", len(tilde) == 1)

nested = list(cccp.fenced_blocks(
    "````markdown\n"
    "```bash\n"
    "git status\n"
    "```\n"
    "````\n"
))
check("a longer opener is not closed by a shorter inner fence",
      len(nested) == 1 and "git status" in nested[0][2])


# ---------------------------------------------------------------------------
# The predicate is the hook's own
# ---------------------------------------------------------------------------

evaluate = cccp.load_predicate(REPO)
check("the hook's evaluate() denies a chained commit-and-push",
      evaluate('git commit -m x\ngit push -u origin b') is not None)
check("the hook's evaluate() allows a commit with no push",
      evaluate('git commit -m x') is None)


# ---------------------------------------------------------------------------
# Info string parsing
# ---------------------------------------------------------------------------

check("verbatim {bash} maps to bash", cccp.language_of("{bash}") == "bash")
check("{bash, echo=FALSE} maps to bash", cccp.language_of("{bash, echo=FALSE}") == "bash")
check("{.bash} maps to bash", cccp.language_of("{.bash}") == "bash")

# ---------------------------------------------------------------------------
# End-to-end, against a synthetic repo
# ---------------------------------------------------------------------------

def scan_fixture(files):
    """Run the sweep over a throwaway git repo containing `files`."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        (root / "hooks").mkdir()
        (root / "hooks" / "no-commit-chained-to-push.py").write_text(
            (REPO / "hooks" / "no-commit-chained-to-push.py")
            .read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "scripts").mkdir()
        (root / "scripts" / "lib").mkdir()
        (root / "scripts" / "lib" / "shellcmd.py").write_text(
            (REPO / "scripts" / "lib" / "shellcmd.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        for name, body in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        return cccp.scan(root)


CHAINED_INDENTED = (
    "Step one:\n"
    "\n"
    "  ```bash\n"
    "  git commit --allow-empty -m \"start\"   # COMMIT\n"
    "  git push -u origin my-branch          # PUSH\n"
    "  ```\n"
)

SPLIT = (
    "Step one:\n"
    "\n"
    "```bash\n"
    "git commit --allow-empty -m \"start\"   # COMMIT\n"
    "```\n"
    "\n"
    "Then push:\n"
    "\n"
    "```bash\n"
    "git push -u origin my-branch   # PUSH\n"
    "```\n"
)

result = scan_fixture({"skills/demo/SKILL.md": CHAINED_INDENTED})
check("NEGATIVE CONTROL: an indented chained block is reported",
      len(result["findings"]) == 1)
check("the finding names the file and the opening fence line",
      result["findings"] and result["findings"][0]["path"] == "skills/demo/SKILL.md"
      and result["findings"][0]["line"] == 3)
check("the denominator is reported alongside the finding",
      result["files_scanned"] == 1 and result["blocks_examined"] == 1)

# An empty shell fence reaches evaluate() never, so counting it would inflate
# the denominator and let one empty fence break the systemic-failure test,
# which asks whether EVERY examined block raised.
EMPTY_SHELL_FENCE = "# Demo\n\n```bash\n```\n\n```bash\ngit status\n```\n"

result = scan_fixture({"skills/demo/SKILL.md": EMPTY_SHELL_FENCE})
check("an empty shell fence is not counted as examined",
      result["blocks_examined"] == 1)
check("an empty shell fence still counts in the all-language total",
      result["blocks_all_languages"] == 2)

result = scan_fixture({"skills/demo/SKILL.md": SPLIT})
check("the split form the fix applies is NOT reported",
      result["findings"] == [] and result["blocks_examined"] == 2)

# The allowlist is keyed by (path, body fingerprint), so a fixture standing
# in for the real anti-example registers its own body. A per-path count
# could not tell a REPLACEMENT from the original; a fingerprint can.
FIXTURE_KEY = ("shared/workflow/check-before-pushing.md", 'c95b628e8b482c91')
_REAL_ALLOWED = dict(cccp.ALLOWED)
cccp.ALLOWED.clear()
cccp.ALLOWED[FIXTURE_KEY] = "the deliberate anti-example the fragment is about"

result = scan_fixture({
    "shared/workflow/check-before-pushing.md": CHAINED_INDENTED,
})
check("the deliberate anti-example is allowed, not a finding",
      result["findings"] == [] and len(result["allowed"]) == 1)
check("an allowed hit still states its reason, so no exemption is silent",
      result["allowed"] and "anti-example" in result["allowed"][0]["reason"])

result = scan_fixture({
    "shared/workflow/check-before-pushing.md":
        CHAINED_INDENTED + "\n" + CHAINED_INDENTED,
})
check("a second copy of the exempted block is allowed by fingerprint",
      len(result["allowed"]) == 2 and result["findings"] == [])

result = scan_fixture({
    "shared/workflow/check-before-pushing.md":
        CHAINED_INDENTED.replace("my-branch", "other-branch"),
})
check("a DIFFERENT chained block in an allowlisted file is a finding",
      len(result["findings"]) == 1 and result["allowed"] == [])

cccp.ALLOWED.clear()
cccp.ALLOWED.update(_REAL_ALLOWED)

result = scan_fixture({
    "skills/demo/SKILL.md":
        "```python\n"
        "git commit -m x\n"
        "git push origin b\n"
        "```\n"
})
check("a non-shell fence is not examined",
      result["blocks_examined"] == 0 and result["findings"] == [])

result = scan_fixture({
    "skills/demo/SKILL.md":
        "```\n"
        "git commit -m x\n"
        "git push origin b\n"
        "```\n"
})
check("a fence with no info string is examined, so a defect cannot hide "
      "by dropping one word",
      len(result["findings"]) == 1)


# ---------------------------------------------------------------------------
# The real corpus
# ---------------------------------------------------------------------------

original_evaluate = cccp.load_predicate

def patched_load_predicate(root):
    def raising_evaluate(body):
        raise ValueError("Systemic failure")
    return raising_evaluate

cccp.load_predicate = patched_load_predicate

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
    exit_code = cccp.main(["--root", str(REPO), "--json"])
payload = json.loads(buffer.getvalue())

check("blocks skipped is counted when evaluate raises",
      payload["blocks_skipped"] == payload["blocks_examined"] and payload["blocks_examined"] > 0)

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
    exit_code_text = cccp.main(["--root", str(REPO)])
check("main exits 1 when all examined blocks raise", exit_code_text == 1)

cccp.load_predicate = original_evaluate

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "hooks").mkdir()
    (root / "hooks" / "no-commit-chained-to-push.py").write_text(
        (REPO / "hooks" / "no-commit-chained-to-push.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "scripts").mkdir()
    (root / "scripts" / "lib").mkdir()
    (root / "scripts" / "lib" / "shellcmd.py").write_text(
        (REPO / "scripts" / "lib" / "shellcmd.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    path = root / "shared" / "workflow" / "check-before-pushing.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    # The other direction: the allowlisted passage no longer carries the
    # anti-example. A zero count trips no threshold, so without this the stale
    # entry is invisible and the sweep exits 0 over dead documentation.
    path.write_text("# Fragment\n\nNo fenced block here.\n", encoding="utf-8")
    # An unrelated, unchained shell fence keeps blocks_examined above zero.
    # Without it the scan trips main()'s empty-corpus branch, which returns 1
    # for its own reason, and the exit-code assertion below would pass even
    # with the stale-allowlist check removed.
    other = root / "skills" / "demo" / "SKILL.md"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("# Demo\n\n```bash\ngit status\n```\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)

    errors = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
        exit_code_stale = cccp.main(["--root", str(root)])
    check("main exits 1 when an allowlisted path has no hits left",
          exit_code_stale == 1)
    check("the stale-allowlist error says the exemption looks stale",
          "looks stale" in errors.getvalue())

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    exit_code = cccp.main(["--root", str(REPO), "--json"])
payload = json.loads(buffer.getvalue())

check("--json emits every bucket, so a caller can tell empty from unrun",
      set(payload) >= {"files_scanned", "blocks_examined", "findings", "allowed"})
check("the real corpus is actually scanned",
      payload["files_scanned"] > 0 and payload["blocks_examined"] > 0)
check("the corpus is clean, and the run exits 0 accordingly",
      payload["findings"] == [] and exit_code == 0)

# A Quarto attribute fence in a .qmd file, run end to end through the scanner.
QMD_CHAINED = "Some prose.\n\n```{bash}\ngit commit -m x && git push origin HEAD\n```\n"
result = scan_fixture({"notes/demo.qmd": QMD_CHAINED})
check("a {bash} fence in a .qmd is examined", result["blocks_examined"] == 1)
check("a {bash} fence in a .qmd is denied when chained", len(result["findings"]) == 1)

# A console transcript carries a prompt on every command, so the body parsed
# with `$` as argv[0] and the predicate saw no git command at all: the block
# scanned clean however it was written.
SESSION = (
    "Transcript:\n"
    "\n"
    "```console\n"
    "$ git commit -m x && git push -u origin b\n"
    "Everything up-to-date\n"
    "```\n"
)

result = scan_fixture({"skills/demo/SKILL.md": SESSION})
check("a chained command inside a console transcript is denied",
      len(result["findings"]) == 1)

# CommonMark: a backtick opener's info string may not contain a backtick.
# Treating one as an opener let it swallow the real block that followed.
BACKTICK_INFO = (
    "````not-an-info-string`\n"
    "```\n"
    "\n"
    "```bash\n"
    "git commit -m x && git push -u origin b\n"
    "```\n"
)

result = scan_fixture({"skills/demo/SKILL.md": BACKTICK_INFO})
check("a backticked info string does not swallow the next real block",
      len(result["findings"]) == 1)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
