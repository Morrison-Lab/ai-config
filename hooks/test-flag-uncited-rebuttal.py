"""Tests for flag-uncited-rebuttal.py.

Reproduces the incident it was named for
(`Morrison-Lab/ai-config#2070`, 2026-08-24): a reviewer's finding cited
`code.visualstudio.com/docs/agents/run/agent-harnesses` as its evidence, a
rebuttal disputing that finding was posted with no fetch of the URL, and the
rebuttal was wrong. The finding is quoted with the URL BARE (no `https://`),
exactly as the real comment carried it -- `gh pr comment` and `gh issue
comment` routinely omit `-R` too, so the true-positive fixture below also
pins the owner/repo fallback: the comment-post command names no repo at all,
and the earlier `gh api repos/OWNER/REPO/.../comments` fetch is the only
source of it.

The negative cases carry most of the weight, per this repo's own convention
for a warn-only detector: one guard clause isolated per case, so a failure
names which clause broke rather than "the hook is wrong somehow".

Run:  python3 hooks/test-flag-uncited-rebuttal.py hooks/flag-uncited-rebuttal.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

SUBJECT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "flag-uncited-rebuttal.py")


def load(path):
    spec = importlib.util.spec_from_file_location("subject_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


failures = 0


def check(label, got, want):
    global failures
    if got != want:
        print(f"FAIL: {label}: got {got!r}, want {want!r}")
        failures += 1
    else:
        print(f"PASS: {label}")


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

FETCH_CMD = "gh api repos/Morrison-Lab/ai-config/issues/2070/comments"

# The real finding, quoted verbatim: the URL is BARE, no scheme. This is the
# case the hook exists for -- a reviewer citation almost never carries
# `https://` in prose.
FINDING_TEXT = (
    "Finding: VS Code's own documentation "
    "(code.visualstudio.com/docs/agents/run/agent-harnesses and "
    "agents-window) names this setting github.copilot.chat.claudeAgent.enabled"
)

SELF_REF_TEXT = (
    "See https://github.com/Morrison-Lab/ai-config/pull/2065 for the prior "
    "discussion of this."
)

NO_URL_TEXT = "Finding: the docstring above is out of date."

# The two real comments from the incident (paraphrased for the true-positive
# fixture's body text -- the wrong rebuttal and, separately, its retraction).
WRONG_REBUTTAL = (
    "Re-verified finding 1 directly against the installed build. "
    "I'm not changing this claim -- the direct bundle read supports it as "
    "written."
)
RETRACTION = (
    "Retracting my earlier rebuttal. You were right to re-raise this -- I "
    "fetched the URL live just now and it does say what you quoted."
)
NO_CUE_TEXT = "Thanks for flagging this, fixed in commit abc123."


def write_transcript(records):
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8")
    for r in records:
        fh.write(json.dumps(r) + "\n")
    fh.close()
    return fh.name


def body_file_with(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


def fetch_records(result_text, extra_blocks=None):
    """A `gh api .../2070/comments` fetch and its result, optionally
    followed by an extra tool_use block (e.g. a WebFetch)."""
    fetch_use = {"message": {"content": [
        {"type": "tool_use", "id": "call1", "name": "Bash",
         "input": {"command": FETCH_CMD}}]}}
    fetch_result = {"message": {"content": [
        {"type": "tool_result", "tool_use_id": "call1",
         "content": result_text}]}}
    records = [fetch_use, fetch_result]
    if extra_blocks:
        records.append({"message": {"content": extra_blocks}})
    return records


def run_hook(body_text, records):
    """Run the hook end-to-end over a `gh pr comment` posting `body_text`;
    return raw stdout. Deliberately carries NO `-R`/owner-repo flag, matching
    how this corpus actually writes the command -- see the module docstring."""
    transcript_path = write_transcript(records)
    body_path = body_file_with(body_text)
    cmd = "gh pr comment 2070 --body-file " + body_path
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd},
               "transcript_path": transcript_path, "cwd": os.getcwd()}
    proc = subprocess.run([sys.executable, SUBJECT], input=json.dumps(payload),
                          capture_output=True, text=True)
    return proc.stdout.strip()


# --------------------------------------------------------------------------
# Unit-level checks on the pure functions
# --------------------------------------------------------------------------

def unit_checks(mod):
    # extract_body_text: a real file on disk, referenced via --body-file.
    path = body_file_with("hello world")
    check("extract_body_text reads a --body-file path",
          mod.extract_body_text(f"gh pr comment 5 --body-file {path}", "."),
          "hello world")

    # extract_body_text: -F body=@file (gh api convention).
    check("extract_body_text reads -F body=@file",
          mod.extract_body_text(
              f"gh api repos/o/r/issues/5/comments -F body=@{path}", "."),
          "hello world")

    # extract_body_text: a literal --body string.
    check("extract_body_text reads a literal --body string",
          mod.extract_body_text('gh pr comment 5 --body "hi there"', "."),
          "hi there")

    # extract_body_text: undetermined form returns None.
    check("extract_body_text returns None with no body arg at all",
          mod.extract_body_text("gh pr comment 5", "."),
          None)

    # extract_number: each of the three number-bearing shapes.
    check("extract_number from gh pr comment",
          mod.extract_number("gh pr comment 2070 --body x"), 2070)
    check("extract_number from gh issue comment",
          mod.extract_number("gh issue comment 42 --body x"), 42)
    check("extract_number from gh api issues/N/comments",
          mod.extract_number(
              "gh api repos/o/r/issues/99/comments -f body=x"), 99)

    # Dispute cue: both real phrasings from the incident fire, ordinary
    # acknowledgement does not.
    check("dispute cue fires on the wrong rebuttal's phrasing",
          bool(mod.DISPUTE_CUE.search(WRONG_REBUTTAL)), True)
    check("dispute cue fires on the retraction's phrasing",
          bool(mod.DISPUTE_CUE.search(RETRACTION)), True)
    check("dispute cue silent on plain acknowledgement",
          bool(mod.DISPUTE_CUE.search(NO_CUE_TEXT)), False)

    # external_urls: bare-domain citation (the real incident's shape) is
    # found; a same-repo github.com link is excluded; no match yields [].
    check("external_urls finds a bare-domain citation",
          mod.external_urls(FINDING_TEXT, "Morrison-Lab", "ai-config"),
          ["code.visualstudio.com/docs/agents/run/agent-harnesses"])
    check("external_urls excludes a same-repo github.com link",
          mod.external_urls(SELF_REF_TEXT, "Morrison-Lab", "ai-config"),
          [])
    check("external_urls finds nothing when nothing is cited",
          mod.external_urls(NO_URL_TEXT, "Morrison-Lab", "ai-config"),
          [])

    # is_self_referential: a DIFFERENT repo's github.com link is still
    # external, even though it shares the host.
    check("a different repo's github.com link is external",
          mod.is_self_referential(
              "https://github.com/Morrison-Lab/gha/pull/1", "Morrison-Lab",
              "ai-config"),
          False)


# --------------------------------------------------------------------------
# End-to-end cases
# --------------------------------------------------------------------------

def end_to_end_checks():
    # True positive: the incident, reproduced. The comment-post command
    # carries NO owner/repo (as `gh pr comment` never does in practice), so
    # this also pins the fetch-command owner/repo fallback.
    out = run_hook(WRONG_REBUTTAL, fetch_records(FINDING_TEXT))
    check("true positive: hook fires on the reproduced incident",
          bool(out), True)
    if out:
        payload = json.loads(out)
        ctx = (payload.get("hookSpecificOutput") or {}).get("additionalContext")
        check("true positive: additionalContext names the unfetched URL",
              bool(ctx and "code.visualstudio.com" in ctx), True)
        check("true positive: systemMessage is present",
              "systemMessage" in payload, True)
        check("true positive: no permissionDecision key",
              "permissionDecision" in json.dumps(payload), False)

    # Guard 1: no dispute cue -> silent, even with an uncited URL sitting
    # right there in the fetched finding.
    out = run_hook(NO_CUE_TEXT, fetch_records(FINDING_TEXT))
    check("guard: no dispute cue -> silent", bool(out), False)

    # Guard 2: the cited URL WAS fetched -> silent.
    webfetch_block = [{"type": "tool_use", "name": "WebFetch", "input": {
        "url": "https://code.visualstudio.com/docs/agents/run/agent-harnesses"}}]
    out = run_hook(WRONG_REBUTTAL,
                   fetch_records(FINDING_TEXT, webfetch_block))
    check("guard: cited URL already WebFetched -> silent", bool(out), False)

    # Guard 3: only a self-referential github.com link is present -> silent.
    out = run_hook(WRONG_REBUTTAL, fetch_records(SELF_REF_TEXT))
    check("guard: only self-referential URLs -> silent", bool(out), False)

    # Guard 4: no URL cited at all -> silent.
    out = run_hook(WRONG_REBUTTAL, fetch_records(NO_URL_TEXT))
    check("guard: no URL cited at all -> silent", bool(out), False)

    # Negative control: an ordinary, non-comment-posting Bash command over
    # the SAME transcript never fires.
    transcript_path = write_transcript(fetch_records(FINDING_TEXT))
    payload = {"tool_name": "Bash",
               "tool_input": {"command": "git status --porcelain"},
               "transcript_path": transcript_path, "cwd": os.getcwd()}
    proc = subprocess.run([sys.executable, SUBJECT], input=json.dumps(payload),
                          capture_output=True, text=True)
    check("negative control: a non-comment Bash command is silent",
          bool(proc.stdout.strip()), False)


# --------------------------------------------------------------------------
# Mutation check: systemMessage -> reason must be caught
# --------------------------------------------------------------------------

def mutation_check():
    """Per README's 'Writing a warn-only hook': revert systemMessage to
    reason and require the suite to fail -- i.e. the payload this hook
    emits must stop carrying `systemMessage` once that literal is reverted,
    which is exactly the defect check-hook-output-shape.py's test-side rule
    exists to catch."""
    src = open(SUBJECT, encoding="utf-8").read()
    anchor = '"systemMessage"'
    if src.count(anchor) != 1:
        print(f"FAIL: mutation anchor {anchor!r} matched "
              f"{src.count(anchor)} times, expected 1")
        return 1
    mutated_src = src.replace(anchor, '"reason"')

    tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                      encoding="utf-8")
    tmp.write(mutated_src)
    tmp.close()
    try:
        transcript_path = write_transcript(fetch_records(FINDING_TEXT))
        body_path = body_file_with(WRONG_REBUTTAL)
        payload = {"tool_name": "Bash",
                   "tool_input": {"command":
                                  "gh pr comment 2070 --body-file " + body_path},
                   "transcript_path": transcript_path, "cwd": os.getcwd()}
        proc = subprocess.run([sys.executable, tmp.name],
                              input=json.dumps(payload),
                              capture_output=True, text=True)
        out = proc.stdout.strip()
        mutated_payload = json.loads(out) if out else {}
    finally:
        os.unlink(tmp.name)

    # The mutated hook still fires (same trigger logic), but its payload no
    # longer carries `systemMessage` -- exactly the shape defect
    # scripts/check-hook-output-shape.py's test-side rule is built to catch.
    # A test suite that only asserted `bool(out)` would still pass here,
    # which is precisely what that rule rules out.
    if "systemMessage" in mutated_payload:
        print("FAIL: mutation systemMessage->reason should have removed "
              "'systemMessage' from the payload, but it is still present")
        return 1
    print("PASS: mutation systemMessage->reason drops 'systemMessage' from "
          "the payload, which a shape-inspecting test correctly flags")
    return 0


def main():
    global failures
    mod = load(SUBJECT)
    unit_checks(mod)
    end_to_end_checks()
    failures += mutation_check()

    if failures:
        print(f"\n{failures} failure(s)")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
