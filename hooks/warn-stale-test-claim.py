#!/usr/bin/env python3
"""Stop-hook guard: warn when a reply claims tests pass over stale code.

Measured in a session on 2026-09-06/07, working on
`hooks/no-push-without-self-review.py`. The session edited a source file, ran
an ad-hoc inline probe of one function (a heredoc'd python script exercising
the predicate directly), saw the probe pass, and reported to the user that
the change was verified -- "All 25 probe cases pass, including every one of
the five forgeries". The project's own test suite had NOT been run since
that edit. When it was run, 2 of 297 cases failed.

The defect is not the probe. A quick probe is good practice. The defect is
treating the probe as the verification and saying so, while the real suite
sat un-run over the current state of the file.

Do: run the real test suite (or say plainly that only a probe ran) before
claiming tests pass over an edited file.
Don't: report "tests pass" / "all cases pass" on the strength of an ad-hoc
probe when the project's own suite has not been run since the edit -- or has
never been run at all.

See `shared/workflow/verify-the-right-artifact.md`, of which this is one
instance: a probe is an adjacent artifact to the suite, not the suite itself.

THE DECIDABLE CONDITION
------------------------
1. The reply asserts that tests/checks/cases pass ("all N cases pass", "N
   passed", "the suite passes", "tests green", ...).
2. A source-file edit (Edit/Write/MultiEdit/NotebookEdit, or a Bash command
   that redirects output into a source file) occurred AFTER the most recent
   recognizable test-suite invocation anywhere earlier in the transcript --
   including when no such invocation ever occurred at all.

That pair means the passing claim describes a state of the code that no
longer exists, or was never checked by anything but a probe.

NOT keyed on truncation (`| tail`, `| head`). That was a red herring in the
incident, and truncating test output is ordinary, legitimate practice; a hook
keyed on it would misfire constantly and get switched off, taking the real
cases with it.

WHY THIS WARNS RATHER THAN BLOCKS
----------------------------------
Same shape as `remind-ums-after-error.py`'s reasoning, restated for a `Stop`
hook rather than a `UserPromptSubmit` one: a false positive here (a genuine
probe correctly disclosed as a probe, or a claim about a file this hook's
test-suite matcher does not recognize) must cost a line of context and
nothing more. `hooks/no-placeholder-reply.py` is a block because a
placeholder reply is NEVER right to send; this is a warn because a passing
claim can be entirely honest and the hook cannot verify the code itself --
it only orders two events in the transcript.

ANCHORING AGAINST SELF-REFERENCE
----------------------------------
ai-config's own corpus -- this docstring, the PR that adds it, review
threads about it -- will describe the exact phrases this hook matches
("all N cases pass", "tests pass"). A substring matcher would then fire on
every reply that quotes or discusses this rule. Following the same fix
`no-placeholder-reply.py` uses for its own self-reference problem (matching
the WHOLE message rather than a substring) is wrong here, because the claim
is normally one clause inside a longer reply, not the entire message. So
this instead strips fenced code, blockquotes, and inline code before
matching -- `remind-ums-after-error.py`'s `visible_prose()` -- on the
assumption that a reply discussing this rule quotes its example phrases in
backticks or a fence, as this docstring and its PR body do. A bare-prose
discussion that never quotes the phrases can still misfire; that residual
gap is why this warns rather than blocks.

TEST-SUITE RECOGNITION IS DELIBERATELY A SMALL, EXPLICIT LIST
----------------------------------------------------------------
Recognizing "the project's test suite" from an arbitrary Bash command is not
solvable in general, so this matches a short list of recognizable shapes
(pytest, `test-*.py`/`test_*.py`, `devtools::test`, `testthat::`, `npm test`,
`cargo test`, `go test`, and similar) rather than a clever heuristic. Missing
a suite invocation this list does not know about produces a false positive
(a warning over a suite that actually ran); that is the safe direction for a
warn-only guard, and strictly better than firing on every Bash command that
happens to contain the word "test".

Fails OPEN: any parse trouble prints nothing at all.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
BASH_TOOLS = {"Bash", "bash", "run_command", "execute_command", "terminal", "shell"}

# Extensions treated as "a source file" for the purpose of this guard. Kept
# to common code file types -- editing a .md or a .json does not carry the
# same "did the code under test change" question this guard exists to ask.
SOURCE_EXT_RE = re.compile(
    r"\.(py|r|jl|js|jsx|ts|tsx|go|rs|java|kt|kts|scala|c|cc|cpp|cxx|h|hpp"
    r"|rb|php|swift|sh|pl|cs|qmd|rmd)$",
    re.I,
)

# A Bash command that writes stdout/a heredoc into a source file: `cat <<EOF
# > foo.py`, `echo ... > foo.py`, `... | tee foo.py`. Conservative on purpose
# -- this is a secondary path behind the Edit/Write/MultiEdit tool calls,
# which cover the overwhelmingly common case.
BASH_WRITE_RE = re.compile(
    r"(?:>{1,2}|\btee\b(?:\s+-a)?)\s*['\"]?([\w./-]+\.(?:py|r|js|jsx|ts|tsx"
    r"|go|rs|java|kt|scala|c|cc|cpp|h|hpp|rb|php|swift|sh|pl|cs))\b",
    re.I,
)

# `sed -i`/`perl -i` in-place edits are a THIRD, common way a source file
# changes via Bash with no Edit/Write/MultiEdit tool call and no
# redirection for `BASH_WRITE_RE` to see (sixth-round adversarial review
# finding). Argument order for `-i` varies by platform (GNU `sed -i
# 's/a/b/' file.py` vs. BSD/macOS `sed -i '' 's/a/b/' file.py`), so rather
# than parsing that precisely this checks two independent, bounded facts:
# the command names `sed`/`perl` with an in-place flag ANYWHERE, and
# SEPARATELY that some whitespace-delimited token in the command looks
# like a source file path (reusing `SOURCE_EXT_RE`). Neither check alone
# is reliable; both together catch the common shapes without attempting
# real argument parsing.
#
# `sed` requires a standalone `-i` token. `perl` instead requires a
# BUNDLED short-option token drawn only from perl's common one-liner
# flags (`p`, `n`, `l`, `a`, `e`, `0`, `i`) -- `-pi`, `-pie`, `-ni`, bare
# `-i`, and similar -- rather than any token merely containing the letter
# `i`. Without that restriction, case-insensitive matching would treat
# `perl -Ilib ...` (an unrelated `-I` include-path flag) as an in-place
# edit purely because "lib" contains a lowercase `i`; the curated
# character class excludes it.
_INPLACE_TOOL_RE = re.compile(
    r"(?i:\bsed\b)[^\n]*\s-i\b"
    r"|(?i:\bperl\b)[^\n]*\s-[pnlae0]*i[pnlae0]*\b"
)


def _inplace_edit_target(command):
    """True if `command` looks like an in-place sed/perl edit of a source file."""
    if not _INPLACE_TOOL_RE.search(command):
        return False
    for token in re.split(r"\s+", command):
        if SOURCE_EXT_RE.search(token.strip("'\"")):
            return True
    return False


# A command-position anchor: start of the command string, or immediately
# after a shell separator (`;`, `&&`, `||`, a single `&` or `|`). A bare
# newline is DELIBERATELY EXCLUDED, unlike an earlier version of this
# anchor -- a heredoc BODY line sits right after a newline with no real
# command boundary there, so including `\n` let a documentation line like
# "python3 hooks/test-foo.py" inside a `cat <<EOF > NOTES.md` heredoc read
# as a run (third-round adversarial review finding). Dropping it means a
# genuine multi-line script with one statement per line and no `;`/`&&`
# joining them is no longer recognized either -- that is the SAFE
# direction for a warn-only guard (an unrecognized real run costs one
# extra warning; a recognized mention costs a missed one), not a
# regression.
#
# `_WRAPPER` lets a small, explicit set of process wrappers sit between the
# anchor and the actual invocation (`timeout 60 pytest -q`, `sudo npm
# test`, `env FOO=1 cargo test`) without reopening the mention-vs-run gap
# to arbitrary preceding text.
_WRAPPER = r"(?:(?:timeout\s+\S+|nohup|sudo|env(?:\s+\w+=\S+)*)\s+)*"
_CMD_START = r"(?:^|;|&&|\|\||[&|])\s*" + _WRAPPER

# A small, explicit set of recognizable test-suite invocation shapes. See
# the docstring's "TEST-SUITE RECOGNITION" section for why this stays a list
# rather than a general heuristic.
#
# EVERY alternative is anchored to `_CMD_START` -- not just the
# python-file one. Two earlier rounds anchored only that alternative,
# reasoning that `\bpytest\b` etc. needed to stay bare so `timeout 60
# pytest -q` would still match; a THIRD round of adversarial review showed
# that same bare-word matching let `echo "remember to run pytest before
# merging"` and `git commit -m "will run cargo test later"` register as
# real runs -- the identical mention-vs-run bug the first two rounds
# fixed only for the python-file shape. `_WRAPPER` above is what makes the
# uniform anchor safe: it is what lets `timeout 60 pytest` still match
# without leaving the other fifteen alternatives unanchored.
#
# `(?:[\w./-]*/)?test[-_]` (rather than `[\w./-]*test[-_]`) requires
# `test[-_]` to start the FILENAME itself, not merely appear as a
# substring anywhere in it -- otherwise `python3 scripts/latest_run.py`,
# `contest_data.py`, and `attest_config.py` all "matched" a suite run
# that was really an unrelated script (third-round finding).
#
# `(?![-:])` after each `X\s+test\b` alternative rejects a PARTIAL or
# adjacent target that merely starts with "test": `npm run test:unit`,
# `npm run test:watch`, `mvn test-compile`, `make test-unit`, and `yarn
# test:watch` are all ordinary, common script/build-target NAMES, not a
# run of the whole suite -- bare `\b` is satisfied by the following `:`
# or `-` since both are non-word characters, so without this guard a
# lint-only or watch-mode target read as a genuine full run (fifth-round
# adversarial review finding, reproduced with no adversarial shell
# construction at all).
TEST_SUITE_RE = re.compile(
    _CMD_START + r"""(?:
      pytest\b(?!=)
    | py\.test\b(?!=)
    | python[3]?\s+-m\s+(?:pytest|unittest)\b
    | python[3]?\s+(?:-\S+\s+)*(?:[\w./-]*/)?test[-_][\w./-]*\.py\b
    | devtools::test\(
    | testthat::test_
    | R\s+CMD\s+check\b
    | npm\s+(?:run\s+)?test\b(?![-:])
    | yarn\s+test\b(?![-:])
    | pnpm\s+test\b(?![-:])
    | cargo\s+test\b(?![-:])
    | go\s+test\b(?![-:])
    | make\s+test\b(?![-:])
    | mvn\s+test\b(?![-:])
    | gradle\s+test\b(?![-:])
    | rspec\b(?!=)
    | phpunit\b(?!=)
    | dotnet\s+test\b
    )""",
    re.I | re.X,
)

# Strip shell string literals and heredoc bodies before matching
# TEST_SUITE_RE. Fourth-round adversarial review found that `_CMD_START`'s
# separator characters (`;`, `&`, `&&`, `||`) are not aware of quoting: an
# ORDINARY, non-adversarial phrase like `echo "Build & pytest"` or
# `git commit -m "run lint; pytest; deploy"` contains those characters
# inside a string literal, where the shell never treats them as
# separators -- so they were still misread as real command boundaries,
# reopening the mention-vs-run gap a fourth time. This is not full shell
# parsing (which is out of scope, per this hook's own design constraint of
# staying conservative rather than clever): it recognizes exactly two
# bounded shapes -- a `'...'` or `"..."` string literal, and a `<<TAG` /
# `<<'TAG'` heredoc body up to its closing `TAG` line -- and blanks them,
# so a keyword sitting inside either can no longer supply a match.
_DQUOTE_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
_SQUOTE_RE = re.compile(r"'[^']*'")
_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(?:.*?\n)?\1\b", re.S)


def _strip_shell_literals(command):
    """Blank out quoted strings and heredoc bodies before test-run matching.

    Order matters: heredocs first, since a heredoc body can itself contain
    quote characters that would otherwise confuse the quote stripper.
    """
    command = _HEREDOC_RE.sub(lambda m: m.group(0).split("\n", 1)[0] + "\n", command)
    command = _DQUOTE_RE.sub('""', command)
    command = _SQUOTE_RE.sub("''", command)
    return command

# A claim that tests/checks/cases pass. Matched against VISIBLE prose only
# (see visible_prose() below) so a reply quoting or discussing this rule in
# backticks or a fence does not self-trigger.
# Both the "all N X pass" alternative and the bare "X pass(ed)" alternative
# allow the SAME subject-noun set (tests/cases/checks/probes). A seventh
# round of adversarial review found these had drifted apart: the first
# alternative required the literal word "pass" (rejecting "passed"), and
# the second allowed "passed" but only for tests/checks/suite, not
# cases/probes -- so "the 25 probe cases passed" (ordinary past tense of
# the exact incident phrasing this hook was built to catch) went
# unmatched while "the 25 probe cases pass" matched. Both alternatives
# now share one subject-noun group and one tense group.
# The bare "X pass(ed)/green/passing" alternative above catches "tests
# passing" but not the equally ordinary copula form "tests ARE passing" /
# "the suite IS green" -- an eighth round of adversarial review found this
# is a distinct gap from the present/past-tense fix just above (that one
# was about the verb's own suffix; this is about an intervening "is"/"are"
# before a participle or adjective), and at least as common a way to
# report results conversationally.
_SUBJECT = r"(?:tests?|cases?|checks?|probes?|suite)"
CLAIM_RE = re.compile(
    r"""
      \ball\s+[\w\s]{0,40}?""" + _SUBJECT + r"""\s+pass(?:es|ed)?\b
    | \b""" + _SUBJECT + r"""\s+(?:pass(?:es|ed)?|green|passing)\b
    | \b""" + _SUBJECT + r"""\s+(?:is|are)\s+(?:passing|green)\b
    | \b\d+\s*/\s*\d+\s+(?:tests?|cases?|checks?)\s+pass(?:ed)?\b
    | \b\d+\s+(?:tests?|cases?)\s+pass(?:ed)?\b
    | \b\d+\s+passed\b
    """,
    re.I | re.X,
)

# A window checked around a CLAIM_RE hit for a disclosed failure COUNT ("12
# passed, 3 failed", "2 errors"). Without this, a reply that already
# disclosed partial results still reads as a full passing claim -- worse
# than a missed warning, since the reply is honest and this would tell the
# author their honest disclosure was a stale-claim violation. Requires a
# NUMBER next to the fail/error word (either order), not the bare word
# alone: a first version matched bare "error"/"errors" anywhere in the
# window, which suppressed a genuine warning next to unrelated prose like
# "error handling" or "no errors expected" (second-round adversarial
# review finding) -- the wrong direction for a warn-only guard, whose whole
# value is not missing the case it exists to catch.
FAIL_NEARBY_RE = re.compile(
    r"\b\d+\s+(?:fail(?:ed|ures?)?|errors?)\b"
    r"|\b(?:fail(?:ed|ures?)?|errors?)\s*:?\s*\d+\b",
    re.I,
)
NEARBY_WINDOW = 80

FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)
TICKED = re.compile(r"`[^`\n]*`")


def visible_prose(text):
    """Drop code fences, blockquotes, and inline code before matching.

    Same rationale as `remind-ums-after-error.py`'s helper of the same name:
    quoting or discussing this rule is the main false-positive source, and it
    is nearly always inside one of these three.
    """
    text = FENCE.sub(" ", text)
    text = QUOTED.sub(" ", text)
    return TICKED.sub(" ", text)


def records(path):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def _extract(m):
    """Return (text_blocks, tool_calls) for one transcript record.

    Mirrors the multi-harness extraction `remind-ums-after-error.py` and
    `no-placeholder-reply.py` already use, so this hook reads the same
    Claude Code / Antigravity record shapes they do.
    """
    text_blocks = []
    tool_calls = []

    is_assistant = m.get("type") == "assistant" or m.get("role") == "assistant"
    blocks = (m.get("message") or {}).get("content") or m.get("content") or []
    if isinstance(blocks, list):
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                tool_calls.append((b.get("name") or "", b.get("input") or {}))
            elif b.get("type") == "text" and is_assistant:
                text_blocks.append(b.get("text") or "")
    elif isinstance(blocks, str) and is_assistant:
        text_blocks.append(blocks)

    if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
        content = m.get("content")
        if isinstance(content, str):
            text_blocks.append(content)
        elif isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    text_blocks.append(b.get("text") or "")
                elif isinstance(b, str):
                    text_blocks.append(b)
        for tc in m.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
            targs = (
                tc.get("args") or tc.get("input")
                or (tc.get("function") or {}).get("arguments") or {}
            )
            if isinstance(targs, str):
                try:
                    targs = json.loads(targs)
                except Exception:
                    targs = {"command": targs}
            tool_calls.append((tname, targs if isinstance(targs, dict) else {}))

    return text_blocks, tool_calls


def scan(path):
    """Return (claim_text, last_edit_at, last_test_at).

    Ordering is tracked with a counter incremented once per TOOL CALL
    (`tool_idx`), not per JSONL record. A single assistant turn can carry
    both an Edit and a Bash test invocation in one content array, and
    indexing by record collapses both to the same position -- losing the
    real intra-turn order between them. Text (the claim itself) does not
    need this fine-grained ordering: only the LAST non-empty text block in
    the whole transcript is kept, which is always the reply about to be
    sent.
    """
    last_text = ""
    last_edit_at = -1
    last_test_at = -1
    tool_idx = 0

    for m in records(path):
        if m.get("isSidechain"):
            continue

        text_blocks, tool_calls = _extract(m)

        for txt in text_blocks:
            if txt.strip():
                last_text = txt

        for name, inp in tool_calls:
            tool_idx += 1
            if not isinstance(inp, dict):
                continue

            if name in EDIT_TOOLS:
                file_path = str(
                    inp.get("file_path") or inp.get("path")
                    or inp.get("TargetFile") or inp.get("target_file") or ""
                )
                if SOURCE_EXT_RE.search(file_path):
                    last_edit_at = tool_idx
                continue

            if name in BASH_TOOLS:
                command = str(
                    inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or ""
                )
                if not command:
                    continue
                # TEST_SUITE_RE is matched against the LITERAL-STRIPPED
                # command (see _strip_shell_literals), so a keyword sitting
                # inside a quoted string or a heredoc body cannot supply a
                # match. BASH_WRITE_RE is matched against the RAW command,
                # since it exists precisely to find a redirect target that
                # is often itself inside a quoted path.
                if TEST_SUITE_RE.search(_strip_shell_literals(command)):
                    last_test_at = tool_idx
                elif BASH_WRITE_RE.search(command) or _inplace_edit_target(command):
                    last_edit_at = tool_idx

    return last_text, last_edit_at, last_test_at


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # `json.load` succeeds on any valid JSON document, not just an object --
    # a bare list, string, number, bool, or null on stdin parses fine and
    # then crashes the very next line with an uncaught AttributeError
    # (ninth-round adversarial review finding). A malformed *hook payload*
    # is exactly the kind of input this guard must fail open on, same as a
    # parse error above.
    if not isinstance(payload, dict):
        return 0

    path = payload.get("transcript_path") or payload.get("transcriptPath") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        text, last_edit_at, last_test_at = scan(path)
    except Exception:
        return 0

    if not text:
        return 0
    if last_edit_at <= last_test_at:
        # No source edit since the last recognized suite run (or no edit at
        # all). Nothing is stale.
        return 0

    prose = visible_prose(text)
    hit = CLAIM_RE.search(prose)
    if not hit:
        return 0

    window_lo = max(0, hit.start() - NEARBY_WINDOW)
    window_hi = min(len(prose), hit.end() + NEARBY_WINDOW)
    if FAIL_NEARBY_RE.search(prose[window_lo:window_hi]):
        # A disclosed failure nearby ("12 passed, 3 failed") means this is
        # not a claim of full, verified success -- the honest disclosure
        # must not be told it violated this rule.
        return 0

    # Keyed on the transcript path too, so the sentinel is per session.
    # Without it, two sessions producing the identical short final reply
    # (e.g. "All tests pass.") share one sentinel in /tmp, and the second
    # session's genuine warning is silently swallowed -- the same class of
    # bug `remind-ums-after-error.py` documents fixing for its own sentinel.
    key = hashlib.sha256(f"{path}:{text}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-stale-test-claim-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    claim = hit.group(0).strip()
    suite_ran = "never" if last_test_at < 0 else "before the most recent edit"
    print(json.dumps({"systemMessage": (
        f'Your reply claims tests pass ("{claim}"), but a source-file edit '
        f"happened after the last recognized test-suite invocation "
        f"(the project's own suite ran {suite_ran} in this transcript). "
        "Run the real suite over the current state of the file before "
        "reporting it verified, or say plainly that only a probe ran."
    )}))

    sys.stderr.write(
        f'[hook: warn-stale-test-claim] Your reply claims tests pass '
        f'("{claim}"), but a source-file edit happened after the last '
        f"recognized test-suite run ({suite_ran}).\n\n"
        "A quick ad-hoc probe of one function is good practice, but it is "
        "not the project's test suite -- verifying the probe and saying "
        "'tests pass' verifies an adjacent artifact, not the one the claim "
        "is about (shared/workflow/verify-the-right-artifact.md).\n\n"
        "Run the real suite (pytest, devtools::test(), npm test, cargo "
        "test, or whatever this project uses) over the CURRENT file before "
        "reporting it verified. If only a probe ran, say so explicitly "
        "instead of claiming the suite passed.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
