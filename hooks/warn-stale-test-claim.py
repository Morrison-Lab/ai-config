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

# A small, explicit set of recognizable test-suite invocation shapes. See
# the docstring's "TEST-SUITE RECOGNITION" section for why this stays a list
# rather than a general heuristic.
#
# `test[-_][\w./-]*\.py` matches this repo's own `hooks/test-<name>.py`
# convention as well as a generic `test_*.py` module -- but ONLY inside a
# Bash COMMAND string, never against an Edit/Write file_path, so editing
# (rather than running) a test file never counts as a suite invocation.
TEST_SUITE_RE = re.compile(
    r"""
      \bpytest\b
    | \bpy\.test\b
    | \bpython[3]?\s+-m\s+(?:pytest|unittest)\b
    | \btest[-_][\w./-]*\.py\b
    | \bdevtools::test\(
    | \btestthat::test_
    | \bR\s+CMD\s+check\b
    | \bnpm\s+(?:run\s+)?test\b
    | \byarn\s+test\b
    | \bpnpm\s+test\b
    | \bcargo\s+test\b
    | \bgo\s+test\b
    | \bmake\s+test\b
    | \bmvn\s+test\b
    | \bgradle\s+test\b
    | \brspec\b
    | \bphpunit\b
    | \bdotnet\s+test\b
    """,
    re.I | re.X,
)

# A claim that tests/checks/cases pass. Matched against VISIBLE prose only
# (see visible_prose() below) so a reply quoting or discussing this rule in
# backticks or a fence does not self-trigger.
CLAIM_RE = re.compile(
    r"""
      \ball\s+[\w\s]{0,40}?(?:tests?|cases?|checks?|probes?)\s+pass\b
    | \b(?:tests?|checks?|suite)\s+(?:pass(?:es|ed)?|green|passing)\b
    | \bsuite\s+pass(?:es|ed)?\b
    | \b\d+\s*/\s*\d+\s+(?:tests?|cases?|checks?)\s+pass(?:ed)?\b
    | \b\d+\s+(?:tests?|cases?)\s+pass(?:ed)?\b
    | \b\d+\s+passed\b
    """,
    re.I | re.X,
)

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
    """Return (claim_text, last_edit_at, last_test_at)."""
    last_text = ""
    last_edit_at = -1
    last_test_at = -1

    for i, m in enumerate(records(path)):
        if m.get("isSidechain"):
            continue

        text_blocks, tool_calls = _extract(m)

        for txt in text_blocks:
            if txt.strip():
                last_text = txt

        for name, inp in tool_calls:
            if not isinstance(inp, dict):
                continue

            if name in EDIT_TOOLS:
                file_path = str(
                    inp.get("file_path") or inp.get("path")
                    or inp.get("TargetFile") or inp.get("target_file") or ""
                )
                if SOURCE_EXT_RE.search(file_path):
                    last_edit_at = i
                continue

            if name in BASH_TOOLS:
                command = str(
                    inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or ""
                )
                if not command:
                    continue
                if TEST_SUITE_RE.search(command):
                    last_test_at = i
                elif BASH_WRITE_RE.search(command):
                    last_edit_at = i

    return last_text, last_edit_at, last_test_at


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
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

    hit = CLAIM_RE.search(visible_prose(text))
    if not hit:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
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
