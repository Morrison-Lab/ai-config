"""Test the flag-tool-gap-handling guard.

Run: python3 hooks/test-flag-tool-gap-handling.py hooks/flag-tool-gap-handling.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def bash(cmd):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}


def user(text):
    return {"type": "user", "message": {"content": text}}


RESULT = {"type": "user", "message": {"content": [
    {"type": "tool_result", "content": "ok"}]}}

CASES = [
    ([say("I skipped the render because the cloud toolchain lacks R's "
          "reticulate.")], "tool is missing", "skip-because-missing warns"),
    ([say("The PDF could not be built: tinytex is not installed here.")],
     "tool is missing", "could-not plus not-installed warns"),
    ([say("Rendering was skipped; Julia isn't installed.")], "tool is missing",
     "skipped then missing, either order, warns"),
    ([say("Julia was missing, so I installed it and re-ran the render.")],
     None, "an excuse that was fixed in the same sentence stays silent"),
    ([say("I skipped the render because Julia wasn't installed. I then "
          "installed it and reran the render successfully.")], None,
     "the fix in the next sentence stays silent (review of #4884)"),
    ([say("I couldn't finish the migration because a config key was missing "
          "from the YAML file.")], None, "a missing config key is not a tool"),
    ([say("The render was skipped because the R package knitr was missing.")],
     "tool is missing", "a missing package named after 'package' warns"),
    ([say("Rendering was skipped because the reticulate package wasn't "
          "installed, so the render hook never ran.")], "tool is missing",
     "the founding incident with a later 'hook' still warns"),
    ([say("I couldn't deploy because the API key for the staging environment "
          "wasn't installed.")], None, "a modifier before 'installed' still reads as a key"),
    ([say("I couldn't run the pre-commit hook because black wasn't installed.")],
     "tool is missing", "a hook before the 'because' clause does not hide a tool"),
    ([say("I haven't rendered the page, and `typos` isn't installed in this "
          "session, so CI will be the first render and spell check.")],
     "tool is missing", "perfect-tense skip plus not-installed warns (psw#480)"),
    ([say("I haven\u2019t rendered the page, and `typos` isn\u2019t installed here.")],
     "tool is missing", "curly apostrophes warn like straight ones"),
    ([say("I haven't run into problems; the package is not installed by "
          "default but uv adds it.")], None,
     "a phrasal 'haven't run into' is not a skip"),
    ([say("We haven't checked in yet, and the CLI isn't available until "
          "tomorrow.")], None, "'haven't checked in' is not a skip"),
    ([say("I haven't been able to render: quarto isn't installed.")],
     "tool is missing", "'haven't been able to render' warns"),
    ([say("I haven't tested it, because pytest isn't installed.")],
     "tool is missing", "'haven't tested' warns"),
    ([say("I couldn't build the PDFs here because this container's LaTeX is too "
          "old for the exam template.")], "tool is missing",
     "a too-old toolchain warns (mlg thread, 2026-11-24)"),
    ([say("I couldn't render it, since the Quarto version here is outdated.")],
     "tool is missing", "an outdated version warns"),
    ([say("I couldn't update the page because its text is out of date.")], None,
     "out-of-date prose is not a tool"),
    ([say("One hook refuses any post that excuses skipped work because a tool "
          "is missing or too old.")], None,
     "describing the rule is not an excuse (2026-11-24 false positive)"),
    ([say("No excuse, I skipped the tests because pytest is not installed.")],
     "tool is missing", "the word excuse alone does not exempt a real skip"),
    ([say("The hook says no excuses; I skipped the tests because pytest is "
          "not installed.")],
     "tool is missing", "a rule clause does not exempt the next clause's skip"),
    ([say("This hook excuses when I skipped work because a tool is missing; "
          "I skipped tests because pytest is not installed.")],
     "tool is missing", "a real excuse after an exempt one still warns"),
    ([say("The hook refuses a post that excuses skipped work; I couldn't render "
          "it because pdflatex is not installed.")],
     "tool is missing", "a match spanning a rule clause and a real one still warns"),
    ([say("This hook refuses posts that excuse skipped work because a tool is "
          "missing; I couldn't render it: pdflatex is not installed.")],
     "tool is missing", "a real excuse split over two clauses after rule talk warns"),
    ([say("The hook says no excuses but I skipped the tests because pytest is "
          "not installed.")],
     "tool is missing", "rule talk joined by 'but' does not exempt the skip"),
    ([say("I couldn't render it because this container has an outdated version "
          "of LaTeX.")],
     "tool is missing", "an outdated version before the tool name warns"),
    ([say("A hook refuses posts that excuse skipped work because a tool is "
          "missing, and I skipped the tests because pytest is not installed.")],
     "tool is missing", "rule talk joined by ', and' does not exempt the skip"),
    ([say("I skipped the refit because the data is too old.")], None,
     "old data is not an old tool"),
    ([say("I couldn't render it even though LaTeX is not outdated.")], None,
     "a tool that is not outdated is no excuse"),
    ([say("I couldn't render it even though the Quarto version is not outdated.")],
     None, "a version that is not outdated is no excuse"),
    ([say("I haven't upgraded the compiler because it isn't outdated.")],
     None, "a contracted 'isn't outdated' is no excuse"),
    ([say("I skipped the migration because the schema is too old.")], None,
     "an old schema is not an old tool"),
    ([say("I couldn't render it even though LaTeX is not too old.")], None,
     "'not too old' is no excuse"),
    ([say("I couldn't render it because this is not an outdated version of "
          "LaTeX.")], None, "'not an outdated version' is no excuse"),
    ([say("I couldn't build the docs because Python 3.8 is too old for this "
          "package.")], "tool is missing", "a dotted version number does not end the span"),
    ([say("I couldn't render the slides because the template is too old; I "
          "couldn't compile them because texlive is not installed.")],
     "tool is missing", "a non-tool clause does not hide a real excuse beside it"),
    ([say("I installed pandoc. Then I wrote the summary. I couldn't render the "
          "PDF because LaTeX is too old.")],
     "tool is missing", "an unrelated earlier install does not excuse a later skip"),
    ([say("I haven't upgraded the compiler because it isn't an outdated version.")],
     None, "'isn't an outdated version' is no excuse"),
    ([say("I haven't upgraded LaTeX because the release is no longer outdated.")],
     None, "'no longer outdated' is no excuse"),
    ([say("I couldn't render it because this container has an out of date "
          "version of LaTeX.")],
     "tool is missing", "an unhyphenated out of date version warns"),
    ([say("Rendered both pages; no warnings.")], None, "plain report is silent"),
    ([user("go"), bash("Rscript -e 'install.packages(\"reticulate\")'"), RESULT,
      say("Rendered the chapter.")], "startup script",
     "an install with no startup-script mention warns"),
    ([user("go"), bash("uv pip install matplotlib"), RESULT,
      say("Rendered. Matplotlib is worth adding to the cloud startup script: "
          "`uv pip install matplotlib`.")], None,
     "an install reported with the startup script stays silent"),
    ([bash("pip install old"), RESULT, user("next task"),
      say("Done.")], None, "an install before the last user prompt is ignored"),
    ([user("go"), bash("git status"), RESULT, say("Clean.")], None,
     "no install, no excuse: silent"),
]

fails = 0
for lines, expect, name in CASES:
    with tempfile.TemporaryDirectory() as d:
        tp = os.path.join(d, "t.jsonl")
        with open(tp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(x) for x in lines) + "\n")
        env = dict(os.environ, TMPDIR=d)
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(
            {"transcript_path": tp, "session_id": "t" + name}), text=True,
            capture_output=True, env=env)
    out = p.stdout + p.stderr
    fired = bool(out.strip())
    ok = fired == (expect is not None) and (expect is None or expect in out)
    if fired and ok:
        # The block's `reason` is the only part the agent reads.
        try:
            payload = json.loads(p.stdout)
            ok = payload.get("decision") == "block" and bool(payload.get("reason"))
        except Exception:
            ok = False
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1
        print("   output:", out[:300])
sys.exit(1 if fails else 0)
