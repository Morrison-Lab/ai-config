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
help_text = parser.format_help()
expect(
    "parser help accurately mentions paragraph scoping",
    "paragraphs containing lines" in help_text or "paragraphs" in parser.epilog,
    f"got epilog: {parser.epilog!r}",
)


print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
