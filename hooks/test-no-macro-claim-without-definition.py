#!/usr/bin/env python3
"""Test the no-macro-claim-without-definition guard.

Verifies that a reply saying what a LaTeX macro prints, renders as or is defined
as is denied unless a Read, Grep or Bash result in the session shows that
macro's definition, that backticks do not exempt the claim, and that built-in
LaTeX commands, code fences, other tools and unreadable input pass.

The second half is a MUTATION harness: each clause is reverted on its own and
the cases that must flip are compared with what flipped, so a clause no case
exercises is reported rather than silently trusted.

Run: python3 hooks/test-no-macro-claim-without-definition.py hooks/no-macro-claim-without-definition.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-macro-claim-without-definition.py")
with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()

USER = {"type": "user", "message": {"content": [{"type": "text", "text": "check the notation"}]}}


def call(tool_id, name="Bash", **inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": name, "input": inp}]}}


def result(tool_id, text, is_error=False):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": text,
         "is_error": is_error}]}}


def read_of(text, name="Read", is_error=False, **inp):
    return [call("r1", name=name, **(inp or {"file_path": "macros.qmd"})),
            result("r1", text, is_error)]


MACROS = (
    "\\newcommand{\\vx}{\\utilde{x}}\n"
    "\\newcommand{\\covmat}{\\Sigma}\n"
    "\\def\\Var{\\operatorname{Var}}\n"
    "\\providecommand{\\norm}[1]{\\lVert #1 \\rVert}\n"
    "\\renewcommand{\\vbeta}{\\utilde{\\beta}}\n"
    "\\DeclareMathOperator{\\argmin}{arg\\,min}\n"
)

# The incident sentences, backticks included.
VX = "`\\vx` prints a bold x."
COV = "Swapping `\\Sigma` for `\\covmat` changes the notation, since `\\covmat` is defined as something new."

# (events before the reply, reply text, expected deny, label)
CASES = [
    # Denied: no definition read
    ([USER], VX, True, "the \\vx incident, in backticks, no read"),
    ([USER], "The macro \\vx prints a bold x.", True, "bare macro name, no backticks"),
    ([USER], COV, True, "the \\covmat is-defined-as incident"),
    ([USER], "`\\vx` renders as a boldface x.", True, "renders as"),
    ([USER], "`\\vx` displays an underset tilde.", True, "displays"),
    ([USER], "`\\vx` typesets as a tilde.", True, "typesets"),
    ([USER], "`\\vx` looks like a bold x.", True, "looks like"),
    ([USER], "`\\covmat` expands to \\Sigma.", True, "expands to"),
    ([USER], "`\\Var` is defined as the variance operator.", True, "is defined as, other macro"),
    ([USER], "`\\E` prints a bold E.", True, "single-letter library macro"),
    ([USER], "`\\vx` and `\\vbeta` both print bold letters.", True, "two macros, neither read"),
    # Denied: the reading does not count
    ([USER] + read_of("some chapter text, no macros", file_path="a.qmd"), VX, True,
     "a read that shows no definition"),
    ([USER] + read_of(MACROS, is_error=True), VX, True, "an errored read does not count"),
    ([USER] + read_of(MACROS, name="Edit", file_path="macros.qmd"), VX, True,
     "an Edit result is not a read"),
    ([USER] + read_of("\\newcommand{\\vxx}{y}", file_path="m.qmd"), VX, True,
     "a definition of \\vxx does not define \\vx"),
    ([USER] + read_of(MACROS, file_path="m.qmd"), "`\\vy` prints y.",
     True, "a read of other macros does not define \\vy"),
    ([USER] + read_of("\\newcommand{\\vx}{x}", file_path="m.qmd"),
     "`\\vx` and `\\vz` print letters.", True, "one of two macros read, the other not"),

    # Passes: the definition was read
    ([USER] + read_of(MACROS), VX, False, "Read result with \\newcommand{\\vx}"),
    ([USER] + read_of(MACROS), "`\\covmat` is defined as `\\Sigma`.", False,
     "Read result with \\newcommand{\\covmat}"),
    ([USER] + read_of(MACROS), "`\\Var` expands to the operator name.", False, "\\def\\Var form"),
    ([USER] + read_of(MACROS), "`\\norm` renders as double bars.", False, "\\providecommand form"),
    ([USER] + read_of(MACROS), "`\\vbeta` prints a tilde beta.", False, "\\renewcommand form"),
    ([USER] + read_of(MACROS), "`\\argmin` displays arg min.", False, "\\DeclareMathOperator form"),
    ([USER] + read_of(MACROS, name="Grep", pattern="vx"), VX, False, "Grep result counts"),
    ([USER] + read_of(MACROS, name="Bash", command="cat macros.qmd"), VX, False,
     "Bash result counts"),
    ([USER] + read_of(MACROS, name="mcp__github__get_file_contents", path="macros.qmd"), VX,
     False, "GitHub file read counts"),
    ([USER] + [call("r1", name="Read", file_path="macros.qmd"),
               {"type": "user", "message": {"content": [
                   {"type": "tool_result", "tool_use_id": "r1", "is_error": False,
                    "content": [{"type": "text", "text": MACROS}]}]}}], VX, False,
     "result content given as a list of text blocks"),
    ([USER] + read_of("\\\\newcommand{\\\\vx}{\\\\utilde{x}}"), VX, False,
     "a definition inside a JSON-escaped result"),
    ([USER] + read_of(MACROS) + [USER], VX, False,
     "a read from an earlier user turn still counts (session scope)"),

    # Passes: not a claim, or not a library macro
    ([USER], "`\\vx` is used in chapter 3.", False, "no rendering verb"),
    ([USER], "Chapter 3 prints a table.", False, "rendering verb, no macro"),
    ([USER], "`\\Sigma` prints a capital sigma.", False, "built-in \\Sigma"),
    ([USER], "`\\frac` renders as a fraction and `\\alpha` as an alpha.", False, "built-ins"),
    ([USER], "The script prints C:\\Users\\name on Windows.", False, "Windows path"),
    ([USER], "It prints a line ending in \\n.", False, "escape sequence"),
    ([USER], "`\\vx` is used here. The page prints a table.", False,
     "macro and verb in different sentences"),
    ([USER], "Use `\\vx`.\nThe chapter renders fine.", False, "macro and verb on different lines"),
    ([USER], "```tex\n% \\vx prints a bold x\n```\nDone.", False, "inside a code fence"),
    ([USER], "", False, "empty text"),
]


def write(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
    return path


def run(hook, payload, raw=None):
    return subprocess.run([sys.executable, hook],
                          input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True)


def denied(hook, events, text, tool="mcp__hearthbot__post_message"):
    path = write(events)
    try:
        out = run(hook, {"transcript_path": path, "tool_name": tool,
                         "tool_input": {"text": text}}).stdout
    finally:
        os.unlink(path)
    if not out.strip():
        return False
    spec = json.loads(out)["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert "ai-config#6109" in spec["permissionDecisionReason"]
    assert "macros.qmd" in spec["permissionDecisionReason"]
    return spec["permissionDecision"] == "deny"


# Each mutation reverts one clause; `flips` are indexes into CASES that must
# change verdict when it is reverted.
def idx(label):
    return next(i for i, c in enumerate(CASES) if c[3] == label)


MUTATIONS = [
    ("backtick exemption added",
     "    prose = FENCE_RX.sub(\" \", text)\n",
     "    prose = FENCE_RX.sub(\" \", text)\n    prose = re.sub(r\"`[^`]*`\", \" \", prose)\n",
     [idx("the \\vx incident, in backticks, no read")]),
    ("built-in exemption removed",
     "if name in BUILTINS or name in seen:", "if name in seen:",
     [idx("built-in \\Sigma"), idx("built-ins")]),
    ("fence skipping removed",
     "prose = FENCE_RX.sub(\" \", text)", "prose = text",
     [idx("inside a code fence")]),
    ("same-sentence requirement removed",
     "        if CLAIM_RX.search(sentence):\n",
     "        if CLAIM_RX.search(prose):\n",
     [idx("macro and verb in different sentences")]),
    ("errored results counted",
     "b.get(\"type\") == \"tool_result\" and not b.get(\"is_error\")",
     "b.get(\"type\") == \"tool_result\"",
     [idx("an errored read does not count")]),
    ("any tool result counted",
     "if READ_TOOL_RX.match(str(b.get(\"name\") or \"\")):",
     "if True:",
     [idx("an Edit result is not a read")]),
    ("all macros treated as defined by any definition",
     "missing = [(n, s) for n, s in claims if n not in known]",
     "missing = [(n, s) for n, s in claims if not known]",
     [idx("a read of other macros does not define \\vy"),
      idx("one of two macros read, the other not")]),
    ("Windows-path guard removed",
     "(?<![\\w\\\\:])", "(?<![\\w\\\\])",
     [idx("Windows path")]),
]


def main():
    passes = failures = 0

    def check(ok, label):
        nonlocal passes, failures
        print(("PASS: " if ok else "FAIL: ") + label)
        if ok:
            passes += 1
        else:
            failures += 1

    verdicts = []
    for events, text, expected, label in CASES:
        got = denied(HOOK, events, text)
        verdicts.append(got)
        check(got == expected, label)

    # Which macros the reason names.
    path = write([USER])
    out = run(HOOK, {"transcript_path": path, "tool_name": "mcp__hearthbot__post_message",
                     "tool_input": {"text": VX}}).stdout
    os.unlink(path)
    check("(\\vx:" in out or "(\\\\vx:" in out, "the reason names the macro")

    # Other reply tools are covered; other tools are not.
    for tool in ("mcp__hearthbot__reply", "mcp__hearthbot__update_message",
                 "mcp__hearthbot__edit_message"):
        check(denied(HOOK, [USER], VX, tool=tool), f"{tool} is covered")
    check(not denied(HOOK, [USER], VX, tool="Bash"), "a non-reply tool is ignored")
    check(not denied(HOOK, [USER], VX, tool="mcp__hearthbot__start_thread"),
          "start_thread is ignored")

    # Fail-open paths.
    bad = run(HOOK, None, raw="not json")
    check(bad.returncode == 0 and not bad.stdout.strip(), "unreadable payload fails open")
    check(not run(HOOK, None, raw="[1]").stdout.strip(), "non-object payload fails open")
    nopath = run(HOOK, {"tool_name": "mcp__hearthbot__post_message",
                        "tool_input": {"text": VX}})
    check('"deny"' in nopath.stdout, "a missing transcript path still judges the text")
    check(not run(HOOK, {"tool_name": "mcp__hearthbot__post_message",
                         "tool_input": {"text": 5}}).stdout.strip(),
          "a non-string text fails open")
    with tempfile.TemporaryDirectory() as tmp:
        lone = os.path.join(tmp, "no-macro-claim-without-definition.py")
        with open(HOOK, encoding="utf-8") as src, open(lone, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        orphan = run(lone, {"tool_name": "mcp__hearthbot__post_message",
                            "tool_input": {"text": VX}})
    check(orphan.returncode == 0 and not orphan.stdout.strip(),
          "missing sibling module fails open")

    print("\nrevert mutations (each listed case must flip when its clause is reverted):")
    for name, old, new, flips in MUTATIONS:
        if SOURCE.count(old) != 1:
            sys.exit(f"FATAL: the {name} anchor occurs {SOURCE.count(old)} times in the hook, "
                     "so that mutation is inert or ambiguous and pins nothing")
        fd, mutant = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(HOOK))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(SOURCE.replace(old, new, 1))
        try:
            for i in flips:
                events, text, expected, label = CASES[i]
                got = denied(mutant, events, text)
                check(got != expected, f"{name}: flips '{label}'")
        finally:
            os.unlink(mutant)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
