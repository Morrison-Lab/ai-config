#!/usr/bin/env python3
"""Regression tests for the bugs fixed in semantic-line-breaks.py."""
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

# Import via the file name which has a hyphen
import importlib.util
spec = importlib.util.spec_from_file_location("slb", Path(__file__).parent / "semantic-line-breaks.py")
slb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slb)
process_file = slb.process_file


def run(name, content, expected):
    with tempfile.NamedTemporaryFile(suffix='.md', mode='w', delete=False, encoding='utf-8') as f:
        f.write(content)
        p = Path(f.name)
    process_file(p)
    result = p.read_text(encoding='utf-8')
    p.unlink()
    if result == expected:
        print(f"PASS: {name}")
        return True
    else:
        print(f"FAIL: {name}")
        print("  Expected:")
        for line in expected.splitlines():
            print(f"    {repr(line)}")
        print("  Got:")
        for line in result.splitlines():
            print(f"    {repr(line)}")
        return False


passes = 0
failures = 0


def check(name, content, expected):
    global passes, failures
    if run(name, content, expected):
        passes += 1
    else:
        failures += 1

    # Same scenario through the scoped path, with every line in scope.
    # Whole-file mode is `changed=None` and takes a different branch at each
    # emitter, so passing these six preservation rules there does not imply
    # passing them under scoping -- a scope-aware emitter that mishandled a
    # fence or an HTML comment would be invisible to the assertion above.
    all_lines = set(range(1, len(content.split('\n')) + 1))
    scoped = slb.reformat(content, all_lines)
    if scoped == expected:
        print(f"PASS: {name} [scoped]")
        passes += 1
    else:
        print(f"FAIL: {name} [scoped]")
        print(f"  Expected: {expected!r}")
        print(f"  Got:      {scoped!r}")
        failures += 1


# Bug 1: @include directive must NOT be merged with a preceding HTML comment.
check(
    "@include not merged with HTML comment",
    "<!-- Shared with the lab manual; edit there, not here. -->\n"
    "@shared/writing/ai-tells.md\n",
    "<!-- Shared with the lab manual; edit there, not here. -->\n"
    "@shared/writing/ai-tells.md\n",
)

# Bug 1b: @directive standalone stays on its own line.
check(
    "@directive standalone passes through",
    "@shared/workflow/claim-pr.md\n\nSome prose after.\n",
    "@shared/workflow/claim-pr.md\n\nSome prose after.\n",
)

# Bug 2: Lines inside a ````-fenced block that also contains a ```-fenced block
# must not be reflowed.
check(
    "nested fenced code blocks (4 vs 3 backticks)",
    "Here is an example:\n\n"
    "````\n"
    "```{r}\n"
    "#| label: stage-at-dx-fig\n"
    "#| code-fold: true\n"
    "\n"
    "plot_stage_at_dx(pt_data)\n"
    "```\n"
    "````\n",
    "Here is an example:\n\n"
    "````\n"
    "```{r}\n"
    "#| label: stage-at-dx-fig\n"
    "#| code-fold: true\n"
    "\n"
    "plot_stage_at_dx(pt_data)\n"
    "```\n"
    "````\n",
)

# Bug 3: Numbered list inside a blockquote must not be merged.
check(
    "blockquote numbered list preserved",
    "> 1. Step one\n"
    "> 2. Step two\n"
    "> 3. Step three\n",
    "> 1. Step one\n"
    "> 2. Step two\n"
    "> 3. Step three\n",
)

# Sanity check: blockquote prose still gets sentence-split.
check(
    "blockquote prose still sentence-split",
    "> This is sentence one. And this is sentence two.\n",
    "> This is sentence one.\n"
    "> And this is sentence two.\n",
)

# Bug 4: a mid-sentence prose line starting with "@" must not be treated
# as a directive — only a standalone "@path.md" line is a directive.
check(
    "prose line starting with @ is still sentence-split",
    "Comments come from the bot, by a human, or by a re-trigger,\n"
    "@claude bot, by a human, or by a re-trigger), and that newer review may\n"
    "contain findings the old one missed. Always check.\n",
    "Comments come from the bot, by a human, or by a re-trigger, @claude bot, "
    "by a human, or by a re-trigger), and that newer review may contain "
    "findings the old one missed.\n"
    "Always check.\n",
)

# Bug 5: multi-line HTML comments must be preserved verbatim, not reflowed.
check(
    "multi-line HTML comment preserved",
    "<!--\n"
    "Shared with the lab manual; edit shared/writing/ai-tells.md, not here.\n"
    "Second line of the comment.\n"
    "-->\n"
    "@shared/writing/ai-tells.md\n",
    "<!--\n"
    "Shared with the lab manual; edit shared/writing/ai-tells.md, not here.\n"
    "Second line of the comment.\n"
    "-->\n"
    "@shared/writing/ai-tells.md\n",
)

# Bug 6: a tilde fence inside a backtick-fenced block must not close it.
check(
    "mismatched fence characters don't close the block",
    "```\n"
    "~~~\n"
    "code line\n"
    "~~~\n"
    "```\n",
    "```\n"
    "~~~\n"
    "code line\n"
    "~~~\n"
    "```\n",
)

# Bug 7: a sentence ending in bold (`**...**.`) must split from the next
# sentence. The closing `**` sits between the period and the whitespace, so a
# boundary regex keyed on `[.!?]\s+` misses it -- and this is the corpus's
# most common paragraph opener, so the tool was silently re-merging it.
check(
    "bold-close sentence boundary splits (**...**. Next)",
    "**Ending the head poll does not end the PR watch.** "
    "The two run at different frequencies.\n",
    "**Ending the head poll does not end the PR watch.**\n"
    "The two run at different frequencies.\n",
)

# Bug 7b: a single-asterisk (italic) close before the whitespace splits too.
check(
    "italic-close sentence boundary splits (.* Next)",
    "See the note.* Then continue with the next point.\n",
    "See the note.*\n"
    "Then continue with the next point.\n",
)

# Bug 7c: adding `*` to the closing-char class must NOT over-split. A
# bold-close period followed by a lowercase word is a continuing clause, not a
# sentence boundary -- the uppercase-or-markup lookahead keeps it on one line.
check(
    "bold-close then lowercase is left joined (no false split)",
    "It is **critical.** yet often skipped on the first pass.\n",
    "It is **critical.** yet often skipped on the first pass.\n",
)

# Bug 7d: the underscore emphasis forms (`__claim.__`, `_claim._`) split too.
# The corpus uses asterisk emphasis, not underscore, so this guards the class
# for both Markdown syntaxes rather than fixing a live corpus bug.
check(
    "underscore bold-close sentence boundary splits (__...__. Next)",
    "__Ending the head poll does not end the PR watch.__ "
    "The two run at different rates.\n",
    "__Ending the head poll does not end the PR watch.__\n"
    "The two run at different rates.\n",
)

# Bug 8: a GitHub alert marker (`> [!IMPORTANT]`, `[!NOTE]`, `[!WARNING]`,
# `[!TIP]`, `[!CAUTION]`) inside a blockquote must never be joined onto the
# following prose line — GitHub only renders the alert when the marker sits
# alone on the blockquote's first line (ai-config#1799, #1821).
check(
    "blockquote alert marker preserved, not joined to prose",
    "> [!IMPORTANT]\n"
    "> **A thing is out of service** (user directive,\n"
    "> 2026-08-20).\n"
    "> Route nothing to it.\n",
    "> [!IMPORTANT]\n"
    "> **A thing is out of service** (user directive, 2026-08-20).\n"
    "> Route nothing to it.\n",
)

# Bug 8b: the marker must also not swallow a preceding prose line in the
# same blockquote (a marker is not necessarily the block's first line).
check(
    "blockquote alert marker not merged with preceding prose",
    "> Some lead-in prose.\n"
    "> [!NOTE]\n"
    "> The actual note text goes here.\n",
    "> Some lead-in prose.\n"
    "> [!NOTE]\n"
    "> The actual note text goes here.\n",
)

# Bug 9: a Setext H1 heading (`Heading\n===\n`) must not be joined into a
# single line -- the underline never matches _is_new_block on its own, so it
# was falling into the following prose-paragraph accumulation and getting
# merged onto the heading text, destroying the heading (ai-config#1416).
check(
    "Setext H1 heading preserved, not joined",
    "Some heading\n"
    "=============\n",
    "Some heading\n"
    "=============\n",
)
check(
    "Setext H1 heading preserved ahead of following prose",
    "Some heading\n"
    "=============\n"
    "\n"
    "Body text here.\n",
    "Some heading\n"
    "=============\n"
    "\n"
    "Body text here.\n",
)

# ---------------------------------------------------------------------------
# Write-guard and diff-scoping tests.
#
# These pin the fix for the whole-file rewrite: naming a path must preview and
# write nothing, --write must touch only the lines the branch changed, and a
# scope that cannot be determined must fail loudly rather than widen silently.
# ---------------------------------------------------------------------------

import io
import os
import subprocess
import contextlib


def expect(name, condition, detail=""):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}" + (f"\n  {detail}" if detail else ""))
        failures += 1


# A two-paragraph document; each paragraph packs two sentences onto one line.
TWO_PARAS = (
    "First para one. First para two.\n"
    "\n"
    "Second para one. Second para two.\n"
)

# reformat() with no scope reflows everything.
expect(
    "reformat(changed=None) reflows the whole document",
    slb.reformat(TWO_PARAS) == (
        "First para one.\nFirst para two.\n\nSecond para one.\nSecond para two.\n"
    ),
    repr(slb.reformat(TWO_PARAS)),
)

# reformat() scoped to line 1 reflows only the first paragraph; the second is
# emitted byte-identically. This is the property that makes --write safe.
scoped = slb.reformat(TWO_PARAS, changed={1})
expect(
    "reformat scoped to line 1 leaves the untouched paragraph byte-identical",
    scoped == "First para one.\nFirst para two.\n\nSecond para one. Second para two.\n",
    repr(scoped),
)

scoped3 = slb.reformat(TWO_PARAS, changed={3})
expect(
    "reformat scoped to line 3 leaves the FIRST paragraph byte-identical",
    scoped3 == "First para one. First para two.\n\nSecond para one.\nSecond para two.\n",
    repr(scoped3),
)

# Bullets are scoped too -- they are a separate emitter from prose paragraphs,
# and an unscoped bullet path would reflow the whole file under --write.
BULLETS = "- Bullet one a. Bullet one b.\n- Bullet two a. Bullet two b.\n"
bscoped = slb.reformat(BULLETS, changed={1})
expect(
    "bullet emitter honours scope (second bullet untouched)",
    bscoped == "- Bullet one a.\n  Bullet one b.\n- Bullet two a. Bullet two b.\n",
    repr(bscoped),
)

# Hunk-header parsing.
expect(
    "parse_changed_lines reads post-image line numbers",
    slb.parse_changed_lines("@@ -1,2 +5,3 @@\n@@ -9 +20 @@\n") == {5, 6, 7, 20},
    repr(slb.parse_changed_lines("@@ -1,2 +5,3 @@\n@@ -9 +20 @@\n")),
)
expect(
    "parse_changed_lines attributes a pure deletion to the abutting line",
    slb.parse_changed_lines("@@ -4,3 +3,0 @@\n") == {3},
    repr(slb.parse_changed_lines("@@ -4,3 +3,0 @@\n")),
)


def _run_main(argv):
    """Run main(argv), returning (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = slb.main(argv)
    return code, out.getvalue(), err.getvalue()


# An unresolvable scope must be a loud error, never a silent whole-file widening.
with tempfile.TemporaryDirectory() as outside:
    stray = Path(outside) / "stray.md"
    stray.write_text(TWO_PARAS, encoding='utf-8')
    before = stray.read_text(encoding='utf-8')
    code, out, err = _run_main([str(stray), '--write'])
    expect(
        "unresolvable scope exits non-zero rather than widening",
        code == 1,
        f"exit={code}",
    )
    expect(
        "unresolvable scope leaves the file untouched",
        stray.read_text(encoding='utf-8') == before,
    )
    expect(
        "unresolvable scope says it is refusing to widen",
        'Refusing to widen' in err,
        err,
    )

# End-to-end against a real git repo, which is the only way to exercise the
# changed-line scope and the preview/--write split together.
with tempfile.TemporaryDirectory() as repo:
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@e',
               GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@e')

    def git(*a):
        return subprocess.run(['git', '-C', repo, *a], capture_output=True,
                              text=True, env=env)

    git('init', '-q', '-b', 'main')
    doc = Path(repo) / 'doc.md'
    # Baseline commit: both paragraphs already packed, and NOT this branch's work.
    doc.write_text(TWO_PARAS, encoding='utf-8')
    git('add', 'doc.md')
    git('commit', '-qm', 'base')
    git('branch', '-f', 'base-ref')
    # The branch changes only the second paragraph.
    doc.write_text(
        "First para one. First para two.\n\nEdited para one. Edited para two.\n",
        encoding='utf-8')
    git('commit', '-qam', 'edit second para')

    # Deliberately NOT chdir'ing into the repo: the scope must resolve from
    # the file's own location, not from the caller's working directory.
    pristine = doc.read_text(encoding='utf-8')

    # Preview by default: emits a diff, writes nothing.
    code, out, err = _run_main([str(doc), '--base', 'base-ref'])
    expect("preview exits 0", code == 0, f"exit={code} err={err}")
    expect(
        "preview writes nothing",
        doc.read_text(encoding='utf-8') == pristine,
    )
    expect(
        "preview says nothing was written",
        'Preview only' in out and 'nothing was written' in out,
        out,
    )
    expect("preview emits a unified diff", '@@' in out, out)

    # --write, scoped: reformats the edited paragraph only.
    code, out, err = _run_main([str(doc), '--base', 'base-ref', '--write'])
    after = doc.read_text(encoding='utf-8')
    expect("scoped --write exits 0", code == 0, f"exit={code} err={err}")
    expect(
        "scoped --write reflows only the changed paragraph",
        after == ("First para one. First para two.\n\n"
                  "Edited para one.\nEdited para two.\n"),
        repr(after),
    )

    # --all widens to the whole file, including the untouched paragraph.
    code, out, err = _run_main([str(doc), '--base', 'base-ref', '--all', '--write'])
    allout = doc.read_text(encoding='utf-8')
    expect(
        "--all reflows the untouched paragraph too",
        allout == ("First para one.\nFirst para two.\n\n"
                   "Edited para one.\nEdited para two.\n"),
        repr(allout),
    )

# A RELATIVE path must scope exactly as an absolute one does.
#
# The git calls run under `-C <file's parent>`, so passing the path as given
# would make git resolve `docs/doc.md` as `docs/docs/doc.md` -- matching
# nothing, which is indistinguishable from an unmodified file and falls
# through to whole-file scope. Silently. That is the rewrite this whole
# guard exists to prevent, so it gets its own test rather than riding on
# the absolute-path case above.
with tempfile.TemporaryDirectory() as repo:
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@e',
               GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@e')

    def git(*a):
        return subprocess.run(['git', '-C', repo, *a], capture_output=True,
                              text=True, env=env)

    git('init', '-q', '-b', 'main')
    os.makedirs(os.path.join(repo, 'docs'))
    nested = Path(repo) / 'docs' / 'doc.md'
    nested.write_text(TWO_PARAS, encoding='utf-8')
    git('add', '-A')
    git('commit', '-qm', 'base')
    git('branch', '-f', 'base-ref')
    nested.write_text(
        "First para one. First para two.\n\nEdited one. Edited two.\n",
        encoding='utf-8')
    git('commit', '-qam', 'edit second')

    total = len(nested.read_text(encoding='utf-8').split('\n'))
    cwd = os.getcwd()
    os.chdir(repo)
    try:
        rel_scope = slb.changed_lines_for(Path('docs/doc.md'), 'base-ref')
    finally:
        os.chdir(cwd)

    expect(
        "a relative path scopes to the changed line, not the whole file",
        rel_scope == {3},
        f"got {sorted(rel_scope)} of {total} lines "
        f"({'WHOLE FILE' if len(rel_scope) >= total else 'partial'})",
    )
    expect(
        "relative and absolute paths agree on scope",
        rel_scope == slb.changed_lines_for(nested, 'base-ref'),
    )

# Bug/clarity: parser epilog and help text accurately state paragraph scope (ai-config#1605)
parser = slb.build_parser()
norm_help = " ".join(parser.format_help().split())
expect(
    "parser help accurately mentions paragraph scoping",
    "scoped to paragraphs containing lines this branch changed against --base" in norm_help,
    f"got rendered help: {norm_help!r}",
)

# Bug/enhancement: untouched sentences in a changed paragraph preserve their exact wrapping (ai-config#1599)
UNTOUCHED_WRAPPED_PARA = (
    "Where no CI gate covers a file\n"
    "(commonly a Markdown doc...)\n"
    "Treat adding or extending\n"
    "the check.\n"
)
scoped_res = slb.reformat(UNTOUCHED_WRAPPED_PARA, {3, 4})
expected_scoped_res = (
    "Where no CI gate covers a file\n"
    "(commonly a Markdown doc...)\n"
    "Treat adding or extending the check.\n"
)
expect(
    "untouched wrapped sentences in a changed paragraph preserve line breaks",
    scoped_res == expected_scoped_res,
    f"expected:\n{expected_scoped_res!r}\ngot:\n{scoped_res!r}",
)

all_res = slb.reformat(UNTOUCHED_WRAPPED_PARA, None)
expected_all_res = (
    "Where no CI gate covers a file (commonly a Markdown doc...)\n"
    "Treat adding or extending the check.\n"
)
expect(
    "whole-file scope reflows all sentences",
    all_res == expected_all_res,
    f"expected:\n{expected_all_res!r}\ngot:\n{all_res!r}",
)

BQ_WRAPPED = (
    "> Where no CI gate covers a file\n"
    "> (commonly a Markdown doc...)\n"
    "> Treat adding or extending\n"
    "> the check.\n"
)
bq_scoped_res = slb.reformat(BQ_WRAPPED, {3, 4})
expected_bq_scoped_res = (
    "> Where no CI gate covers a file\n"
    "> (commonly a Markdown doc...)\n"
    "> Treat adding or extending the check.\n"
)
expect(
    "untouched wrapped sentences in blockquote preserve line breaks",
    bq_scoped_res == expected_bq_scoped_res,
    f"expected:\n{expected_bq_scoped_res!r}\ngot:\n{bq_scoped_res!r}",
)

BULLET_WRAPPED = (
    "- Where no CI gate covers a file\n"
    "  (commonly a Markdown doc...)\n"
    "  Treat adding or extending\n"
    "  the check.\n"
)
bullet_scoped_res = slb.reformat(BULLET_WRAPPED, {3, 4})
expected_bullet_scoped_res = (
    "- Where no CI gate covers a file\n"
    "  (commonly a Markdown doc...)\n"
    "  Treat adding or extending the check.\n"
)
expect(
    "untouched wrapped sentences in bullet continuation preserve line breaks",
    bullet_scoped_res == expected_bullet_scoped_res,
    f"expected:\n{expected_bullet_scoped_res!r}\ngot:\n{bullet_scoped_res!r}",
)

# Review Finding 1: internal double spaces / tabs must not break sentence matching or drop markers
DOUBLE_SPACE_BULLET = "- Ok  then.\n  Ok then.\n"
ds_res = slb.reformat(DOUBLE_SPACE_BULLET, {1})
expected_ds_res = "- Ok then.\n  Ok then.\n"
expect(
    "double-spaced line in touched bullet reformats cleanly with marker intact",
    ds_res == expected_ds_res,
    f"expected:\n{expected_ds_res!r}\ngot:\n{ds_res!r}",
)

# Review Finding 2: empty bullet-marker line must not vanish
EMPTY_MARKER_BULLET = "- \n  Hello world.\n"
em_res = slb.reformat(EMPTY_MARKER_BULLET, {1})
expected_em_res = "- Hello world.\n"
expect(
    "empty bullet marker line is reformatted with prefix when touched",
    em_res == expected_em_res,
    f"expected:\n{expected_em_res!r}\ngot:\n{em_res!r}",
)


# ---------------------------------------------------------------------------
# Gate agreement (ai-config#2085).
#
# The reformatter must consume CI's checker, not a second copy of its
# predicates. These tests pin the construction (the pin matches validate.yml,
# the loaded module is the vendored file) and the two predicates that used
# to disagree: the mid-line semicolon, and the lowercase-follower sentence.
# ---------------------------------------------------------------------------

nlb_gate = slb._nlb_gate
checker = nlb_gate.load_nlb_checker()

ci_sha = nlb_gate.parse_ci_nlb_sha()
pin_sha = nlb_gate.read_vendor_pin()
expect(
    "vendor pin matches the SHA validate.yml pins",
    ci_sha == pin_sha,
    f"ci={ci_sha} pin={pin_sha}",
)
expect(
    "assert_pin_matches_ci accepts the committed vendor copy",
    nlb_gate.assert_pin_matches_ci() == ci_sha,
)
expect(
    "parse_ci_nlb_sha returns a 40-char object id, not the short SHA in a comment",
    len(ci_sha) == 40 and ci_sha != "209bfb76",
    ci_sha,
)
expect(
    "loaded checker is the vendored file CI pins",
    Path(checker.__file__).resolve() == nlb_gate.VENDOR_PY.resolve(),
    f"loaded {checker.__file__}",
)

# A pin mismatch is a loud error, not a silent import of the wrong script.
with tempfile.TemporaryDirectory() as pin_dir:
    yml = Path(pin_dir) / "validate.yml"
    pin = Path(pin_dir) / "gha-check-new-line-breaks.pin"
    yml.write_text(
        "        uses: Morrison-Lab/gha/check-new-line-breaks@"
        + ("a" * 40)
        + " # v2\n",
        encoding="utf-8",
    )
    vendor = Path(pin_dir) / "checker.py"
    vendor.write_text("classify_line = None\n", encoding="utf-8")
    nlb_gate.write_vendor_pin("b" * 40, nlb_gate.file_sha256(vendor), pin)
    raised = False
    try:
        nlb_gate.assert_pin_matches_ci(yml, pin, vendor)
    except nlb_gate.NLBPinError as exc:
        raised = True
        expect(
            "pin mismatch names both SHAs",
            ("a" * 40) in str(exc) and ("b" * 40) in str(exc),
            str(exc),
        )
    expect("pin mismatch raises NLBPinError", raised)

    # Content-hash mismatch: git SHA matches, bytes were edited.
    nlb_gate.write_vendor_pin("a" * 40, "c" * 64, pin)
    raised_hash = False
    try:
        nlb_gate.assert_pin_matches_ci(yml, pin, vendor)
    except nlb_gate.NLBPinError as exc:
        raised_hash = True
        expect(
            "content-hash mismatch names sha256",
            "sha256" in str(exc),
            str(exc),
        )
    expect("content-hash mismatch raises NLBPinError", raised_hash)

# ---------------------------------------------------------------------------
# Config agreement (PR #2322 review finding): the gate module used to derive
# *which script* CI runs from validate.yml, but not *how it is configured*.
# `classify_line`/`split_sentences` were called at each call site's
# compiled-in default (clause_breaks=True, clause_min_length=80), so a
# future `with: clause-min-length: '10'` in validate.yml would change what
# CI flags without changing what this module accepts. These tests pin the
# fix: the resolved config matches today's defaults, and a synthetic
# validate.yml with a non-default `clause-min-length` changes both
# classify_line's verdict and emit_gate_clean's output for the same line.
# ---------------------------------------------------------------------------

resolved_config = nlb_gate.resolve_nlb_config()
expect(
    "resolved config from the live validate.yml equals today's defaults",
    resolved_config == (checker._DEFAULT_CLAUSE_BREAKS, checker._DEFAULT_CLAUSE_MIN_LENGTH),
    repr(resolved_config),
)
expect(
    "load_nlb_config caches the same resolution",
    nlb_gate.load_nlb_config() == resolved_config,
    repr(nlb_gate.load_nlb_config()),
)

# The reviewer's example: 30 visible characters and an interior semicolon,
# so it is a clause violation once the length gate drops to 10 but not at
# the default of 80.
# The config cache must engage on the ordinary path: a whole-file reformat
# calls emit_gate_clean once per sentence, and an uncached resolution
# re-parses validate.yml every time (measured ~170x slowdown on CLAUDE.md
# before the fix reviewed on #2322).
_resolve_calls = {"n": 0}
_orig_resolve = nlb_gate.resolve_nlb_config
def _counting_resolve(*a, **k):
    _resolve_calls["n"] += 1
    return _orig_resolve(*a, **k)
nlb_gate.resolve_nlb_config = _counting_resolve
nlb_gate._NLB_CONFIG = None
try:
    for _ in range(3):
        nlb_gate.emit_gate_clean("A plain short sentence.")
finally:
    nlb_gate.resolve_nlb_config = _orig_resolve
expect(
    "config resolution is cached across emit_gate_clean calls",
    _resolve_calls["n"] <= 1,
    f"resolve_nlb_config ran {_resolve_calls['n']} times for 3 calls",
)

CONFIG_DEMO_LINE = "Short clause here; second bit."
with tempfile.TemporaryDirectory() as config_dir:
    config_yml = Path(config_dir) / "validate.yml"
    config_yml.write_text(
        "jobs:\n"
        "  validate:\n"
        "    steps:\n"
        "      - name: Check new markdown lines for missing semantic breaks\n"
        "        uses: Morrison-Lab/gha/check-new-line-breaks@" + ("a" * 40) + "\n"
        "        with:\n"
        "          clause-min-length: '10'\n",
        encoding="utf-8",
    )
    config_10 = nlb_gate.resolve_nlb_config(config_yml, checker)
    expect(
        "synthetic `with: clause-min-length: '10'` resolves to 10",
        config_10 == (True, 10),
        repr(config_10),
    )
    expect(
        "at CI's live defaults the demo line is not a clause violation",
        checker.classify_line(CONFIG_DEMO_LINE, *resolved_config) is None,
        repr(checker.classify_line(CONFIG_DEMO_LINE, *resolved_config)),
    )
    expect(
        "at clause-min-length: '10' the same line becomes a clause violation",
        checker.classify_line(CONFIG_DEMO_LINE, *config_10) == "clause",
        repr(checker.classify_line(CONFIG_DEMO_LINE, *config_10)),
    )
    breaks_off_yml = Path(config_dir) / "validate-breaks-off.yml"
    breaks_off_yml.write_text(
        "jobs:\n"
        "  validate:\n"
        "    steps:\n"
        "      - name: Check new markdown lines for missing semantic breaks\n"
        "        uses: Morrison-Lab/gha/check-new-line-breaks@" + ("a" * 40) + "\n"
        "        with:\n"
        "          clause-breaks: 'false'\n",
        encoding="utf-8",
    )
    config_off = nlb_gate.resolve_nlb_config(breaks_off_yml, checker)
    expect(
        "synthetic `with: clause-breaks: 'false'` resolves clause_breaks off",
        config_off == (False, checker._DEFAULT_CLAUSE_MIN_LENGTH),
        repr(config_off),
    )
    LONG_SEMI_LINE = (
        "The first independent clause is padded with enough words to push "
        "the stripped length past eighty characters; then the second clause "
        "follows on from there."
    )
    expect(
        "with clause-breaks off, a long semicolon line is not a violation",
        checker.classify_line(LONG_SEMI_LINE, *config_off) is None,
        repr(checker.classify_line(LONG_SEMI_LINE, *config_off)),
    )
    expect(
        "at CI's live defaults the same long semicolon line IS a violation",
        checker.classify_line(LONG_SEMI_LINE, *resolved_config) == "clause",
        repr(checker.classify_line(LONG_SEMI_LINE, *resolved_config)),
    )
    emit_default = nlb_gate.emit_gate_clean(
        CONFIG_DEMO_LINE, checker,
        clause_breaks=resolved_config[0], clause_min_length=resolved_config[1],
    )
    emit_10 = nlb_gate.emit_gate_clean(
        CONFIG_DEMO_LINE, checker,
        clause_breaks=config_10[0], clause_min_length=config_10[1],
    )
    expect(
        "emit_gate_clean leaves the demo line whole at the live default",
        emit_default == [CONFIG_DEMO_LINE],
        repr(emit_default),
    )
    expect(
        "emit_gate_clean splits the demo line at min-length 10",
        emit_10 == ["Short clause here;", "second bit."],
        repr(emit_10),
    )

# Issue #2085: a line the old reformatter left whole, which CI rejected.
ISSUE_2085 = (
    "The **file-set** half of the pair-collision section does flag the shared "
    "path, which is the cue to run the arithmetic below on it; what no conflict "
    "scan above will report is the breach itself.\n"
)
expect(
    "the #2085 line is a clause violation to the gate before reflow",
    checker.classify_line(ISSUE_2085.strip()) == "clause",
    repr(checker.classify_line(ISSUE_2085.strip())),
)
got_2085 = slb.reformat(ISSUE_2085)
expect(
    "reformat splits the #2085 semicolon line",
    got_2085 == (
        "The **file-set** half of the pair-collision section does flag the "
        "shared path, which is the cue to run the arithmetic below on it;\n"
        "what no conflict scan above will report is the breach itself.\n"
    ),
    repr(got_2085),
)
flagged_2085 = [
    checker.classify_line(line)
    for line in got_2085.splitlines()
    if line.strip()
]
expect(
    "every line of the #2085 reflow is gate-clean",
    flagged_2085 == [None, None],
    repr(flagged_2085),
)

# Lowercase-follower sentence (gate _SENT_BREAK_LOWER_RE; the old local
# splitter left this whole and would rejoin a hand-break).
LOWER = "The rules, or agents. opencode instead reads the mailbox.\n"
expect(
    "lowercase-follower is a sentence violation to the gate before reflow",
    checker.classify_line(LOWER.strip()) == "sentence",
    repr(checker.classify_line(LOWER.strip())),
)
got_lower = slb.reformat(LOWER)
expect(
    "reformat splits a lowercase-follower sentence boundary",
    got_lower == (
        "The rules, or agents.\n"
        "opencode instead reads the mailbox.\n"
    ),
    repr(got_lower),
)
expect(
    "reformat does not rejoin a hand-broken lowercase-follower boundary",
    slb.reformat(
        "The rules, or agents.\nopencode instead reads the mailbox.\n"
    ) == got_lower,
    repr(slb.reformat(
        "The rules, or agents.\nopencode instead reads the mailbox.\n"
    )),
)

# A short semicolon line is below NLB_CLAUSE_MIN_LENGTH; the gate leaves it,
# so the reformatter must too.
SHORT_SEMI = "Keep this; it is short.\n"
expect(
    "a short semicolon line is not a gate clause violation",
    checker.classify_line(SHORT_SEMI.strip()) is None,
)
expect(
    "reformat leaves a short semicolon line joined",
    slb.reformat(SHORT_SEMI) == SHORT_SEMI,
    repr(slb.reformat(SHORT_SEMI)),
)

# A semicolon inside a code span is not a clause boundary (the gate strips
# markup first). This line is short enough that classify_line returns None.
CODE_SEMI = (
    "Run `python3 -m pytest; true` on the suite "
    "and wait for every worker to finish the remaining cases.\n"
)
expect(
    "a code-span semicolon is not a gate clause violation",
    checker.classify_line(CODE_SEMI.strip()) is None,
    f"len={len(checker.strip_inline_markup(CODE_SEMI.strip()))} "
    f"reason={checker.classify_line(CODE_SEMI.strip())!r}",
)
expect(
    "reformat does not split on a code-span semicolon",
    slb.reformat(CODE_SEMI) == CODE_SEMI,
    repr(slb.reformat(CODE_SEMI)),
)

# Same masking, but classify_line returns "clause" so emit_gate_clean
# actually calls split_clauses. A naive text.split(";") would emit three
# pieces; the mask must keep the code-span semicolon unsplit.
CLAUSE_AND_CODE_SEMI = (
    "The first independent clause is padded with enough words to push "
    "the stripped length past eighty characters; then run `pytest; true` "
    "and wait for every remaining worker to finish those cases.\n"
)
expect(
    "a long line with a prose semicolon is a clause violation",
    checker.classify_line(CLAUSE_AND_CODE_SEMI.strip()) == "clause",
    f"len={len(checker.strip_inline_markup(CLAUSE_AND_CODE_SEMI.strip()))} "
    f"reason={checker.classify_line(CLAUSE_AND_CODE_SEMI.strip())!r}",
)
got_clause_code = slb.reformat(CLAUSE_AND_CODE_SEMI)
expect(
    "reformat splits the prose semicolon and keeps the code-span one",
    got_clause_code == (
        "The first independent clause is padded with enough words to push "
        "the stripped length past eighty characters;\n"
        "then run `pytest; true` "
        "and wait for every remaining worker to finish those cases.\n"
    ),
    repr(got_clause_code),
)
naive_pieces = [
    p.strip()
    for p in CLAUSE_AND_CODE_SEMI.strip().split(";")
    if p.strip()
]
expect(
    "naive semicolon split of that fixture yields three pieces",
    len(naive_pieces) == 3,
    repr(naive_pieces),
)
expect(
    "split_clauses keeps the code-span semicolon (two pieces)",
    nlb_gate.split_clauses(CLAUSE_AND_CODE_SEMI.strip(), checker)
    == [
        "The first independent clause is padded with enough words to push "
        "the stripped length past eighty characters;",
        "then run `pytest; true` "
        "and wait for every remaining worker to finish those cases.",
    ],
)
expect(
    "every line of the clause-and-code-span reflow is gate-clean",
    [checker.classify_line(ln.strip()) for ln in got_clause_code.splitlines()]
    == [None, None],
)

# #2081 is the comma-clause join. The gate does not flag commas, so this
# change must not start splitting them --- that would be a different issue.
LONG_COMMA = (
    "They are explicit that it disables the check outright rather than "
    "allowlisting one host, so they advise pairing it with WebFetch permission "
    "rules to bound which domains stay reachable, and they present this as one "
    "of two remedies for a network that blocks the Anthropic API host.\n"
)
expect(
    "a long comma-clause sentence is not a gate violation",
    checker.classify_line(LONG_COMMA.strip()) is None,
)
expect(
    "#2081 comma joins are unchanged (still one line)",
    slb.reformat(LONG_COMMA) == LONG_COMMA,
    f"len={len(slb.reformat(LONG_COMMA).strip())} "
    f"lines={slb.reformat(LONG_COMMA).count(chr(10))}",
)

# Bullet continuation: first piece keeps the marker, later pieces indent.
BULLET_SEMI = (
    "- The **Don't:** count an explicit `raise` as louder than the incidental "
    "error it replaces; an adversarial self-review caught it before merge.\n"
)
got_bullet = slb.reformat(BULLET_SEMI)
expect(
    "bullet semicolon split keeps the marker on the first piece only",
    got_bullet.startswith("- ") and "\n  " in got_bullet,
    repr(got_bullet),
)
bullet_reasons = [
    checker.classify_line(checker.line_content(line))
    for line in got_bullet.splitlines()
    if line.strip()
]
expect(
    "split bullet lines are gate-clean",
    all(r is None for r in bullet_reasons) and len(bullet_reasons) >= 2,
    f"{got_bullet!r} reasons={bullet_reasons!r}",
)

# Ellipsis-before-capital is a sentence boundary to the shared regex
# (ai-config#2085: --write proposes the same split the gate flags).
ELLIPSIS = "[...] Everything else follows on.\n"
expect(
    "an ellipsis before a capital is a sentence violation to the gate",
    checker.classify_line(ELLIPSIS.strip()) == "sentence",
)
expect(
    "reformat splits an ellipsis before a capital",
    slb.reformat(ELLIPSIS) == "[...]\nEverything else follows on.\n",
    repr(slb.reformat(ELLIPSIS)),
)

# Scoped path: if split_sentences returns a piece that is not a substring
# of the paragraph, emit_gate_clean still has to run.
FIND_MISS_CLAUSE = (
    "The first independent clause is padded with enough words to push "
    "the stripped length past eighty characters; then the second clause "
    "follows on from there with more words."
)
orig_split = slb.split_sentences
try:
    slb.split_sentences = lambda text: [FIND_MISS_CLAUSE]
    got_miss = slb.reformat("Unrelated short prose.\n", {1})
finally:
    slb.split_sentences = orig_split
expect(
    "scoped find-miss still emits through the gate (splits the clause)",
    got_miss == (
        "The first independent clause is padded with enough words to push "
        "the stripped length past eighty characters;\n"
        "then the second clause follows on from there with more words.\n"
    ),
    repr(got_miss),
)


# PyYAML must stay optional for everything except CI-config resolution: the
# reformatter's --help (and any pre-parse path) must work on a machine with no
# PyYAML, and a run that genuinely needs the config must exit with the
# friendly install message, never a raw ModuleNotFoundError traceback
# (review finding on #2322: an unguarded module-scope import broke both).
import subprocess
import tempfile

SCRIPTS_DIR = Path(__file__).resolve().parent

with tempfile.TemporaryDirectory() as _shim_dir:
    (Path(_shim_dir) / "yaml.py").write_text(
        'raise ImportError("yaml blocked for test")\n', encoding="utf-8"
    )
    _env = dict(os.environ, PYTHONPATH=_shim_dir)
    _help = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "semantic-line-breaks.py"), "--help"],
        capture_output=True, text=True, env=_env,
    )
    expect(
        "--help works without PyYAML",
        _help.returncode == 0,
        _help.stderr[-200:],
    )
    # --all on a temp file outside the repo: deterministic (no base-ref git
    # scoping, which CI's checkout cannot resolve), and still reaches the
    # gate's config resolution, which is what needs PyYAML.
    _probe = Path(_shim_dir) / "probe.md"
    _probe.write_text("A short test sentence.\n", encoding="utf-8")
    _run = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "semantic-line-breaks.py"),
         "--all", str(_probe)],
        capture_output=True, text=True, env=_env,
    )
    expect(
        "yaml-needing run without PyYAML exits with the friendly message",
        _run.returncode != 0
        and "pip install pyyaml" in (_run.stderr + _run.stdout)
        and "Traceback" not in (_run.stderr + _run.stdout),
        (_run.stderr + _run.stdout)[-300:],
    )
    # Multi-path contract: the missing dependency is reported per path and
    # the run still reaches its summary line, instead of the first path
    # killing the whole batch (finding on #2322's delta review).
    _probe2 = Path(_shim_dir) / "probe2.md"
    _probe2.write_text("Another short sentence.\n", encoding="utf-8")
    _multi = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "semantic-line-breaks.py"),
         "--all", str(_probe), str(_probe2)],
        capture_output=True, text=True, env=_env,
    )
    _multi_out = _multi.stderr + _multi.stdout
    expect(
        "multi-path run without PyYAML reports each path and summarizes",
        _multi_out.count("pip install pyyaml") >= 2
        and "Done (" in _multi_out
        and "Traceback" not in _multi_out,
        _multi_out[-400:],
    )

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
