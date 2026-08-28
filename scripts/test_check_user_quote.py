#!/usr/bin/env python3
"""Tests for scripts/check-user-quote.py.

The classifier's two failure directions are not symmetric: a false positive
CERTIFIES a fabricated attribution, while a false negative only declines to
certify a real quotation.  So the false-positive cases are the ones with named
sentinels, and each is a case an earlier revision of the tool actually failed.

Fixture shapes were taken from the shipped CLI's own record handling (2.1.250)
and from 24 real transcripts surveyed 2026-08-28.  Values the survey did not
exhibit -- `unclassified`, `verifiedSlackHumanTurn`, and most of
NON_HUMAN_ORIGINS -- come from the binary, not from the survey; see the
module docstring for the two predicates quoted there.  Per
`shared/workflow/fixtures-are-not-evidence.md` a fixture is evidence about the
code that reads it and nothing more.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-user-quote.py"
spec = importlib.util.spec_from_file_location("cuq", SCRIPT)
cuq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cuq)

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


def user(text, human=False, **flags):
    record = {"message": {"role": "user", "content": text}, "userType": "external", **flags}
    if human:
        record["origin"] = {"kind": "human"}
    return record


def write(root, name, records):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return path


def run(root, phrase, *args):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), phrase, "--root", str(root), *args],
        capture_output=True, text=True,
    )
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    print("Testing check-user-quote.py...")

    # -- the origin label ---------------------------------------------------
    check("origin.kind=human is a human record",
          cuq.classify_record(user("merge it", human=True)) == (cuq.HUMAN, ""))
    for kind in cuq.NON_HUMAN_ORIGINS:
        check(f"origin.kind={kind} is excluded by the label alone",
              cuq.classify_record({"message": {"role": "user", "content": "x"},
                                   "userType": "external",
                                   "origin": {"kind": kind}})[0] == cuq.EXCLUDED)
    # The shipped CLI demotes a human turn to "unclassified" on the paths that
    # rewrite a record, so excluding it would deny a real quotation.
    check("origin.kind=unclassified is unattributed, not excluded",
          cuq.classify_record({"message": {"role": "user", "content": "x"},
                               "userType": "external",
                               "origin": {"kind": "unclassified"}})[0] == cuq.UNATTRIBUTED)
    check("an unseen origin.kind is unattributed, not excluded",
          cuq.classify_record({"message": {"role": "user", "content": "x"},
                               "userType": "external",
                               "origin": {"kind": "some-future-kind"}})[0] == cuq.UNATTRIBUTED)
    # An assistant-written dispatch brief: isSidechain false, no isMeta,
    # userType external. The fail-open the fourth review reproduced.
    check("an unlabelled record is unattributed, NOT a turn",
          cuq.classify_record(user("You are an adversarial reviewer"))[0] == cuq.UNATTRIBUTED)
    # Matches the harness's own predicate: O0(origin) && verifiedSlackHumanTurn !== true.
    check("a relayed channel turn is excluded even though it is labelled human",
          cuq.classify_record(user("hello", human=True,
                                   verifiedSlackHumanTurn=True))[0] == cuq.EXCLUDED)

    for key, _reason in cuq.FLAG_EXCLUSIONS:
        check(f"{key} is excluded", cuq.classify_record(user("x", **{key: True}))[0] == cuq.EXCLUDED)
    check("an assistant-role record is excluded",
          cuq.classify_record({"message": {"role": "assistant", "content": "x"}})[0] == cuq.EXCLUDED)
    check("a non-external userType is excluded",
          cuq.classify_record({"message": {"role": "user", "content": "x"},
                               "userType": "internal"})[0] == cuq.EXCLUDED)

    # TRANSCRIPT_PREFIXES are ordinary English, so they apply ONLY where the
    # harness withheld the human label. On a human-labelled turn they must not.
    for prefix in cuq.TRANSCRIPT_PREFIXES:
        check(f"prefix {prefix[:28]!r} excludes an UNLABELLED record",
              cuq.classify_record(user(prefix + " and then some"))[0] == cuq.EXCLUDED)
        check(f"...and does NOT exclude a human-labelled one",
              cuq.classify_record(user(prefix + " and then some", human=True))[0] == cuq.HUMAN)

    # -- regions ------------------------------------------------------------
    check("a plain block is one region",
          cuq._regions("just some text") == ["just some text"])
    check("a well-formed envelope is cut out of the middle",
          cuq._regions("before <system-reminder>INJECTED</system-reminder> after")
          == ["before ", " after"])
    check("...and INJECTED is in none of the regions",
          all("INJECTED" not in r for r in
              cuq._regions("before <system-reminder>INJECTED</system-reminder> after")))
    check("an UNCLOSED tag mid-block is not an envelope",
          "SENTINEL" in " ".join(cuq._regions("why do <system-reminder> tags SENTINEL appear?")))
    check("a block opening with an unclosed opener yields nothing",
          cuq._regions("<system-reminder>TRUNCATED grant") == [])
    check("a block that is entirely an envelope yields nothing",
          cuq._regions("<task-notification>x</task-notification>") == [])
    for tag in cuq.ENVELOPE_TAGS:
        check(f"envelope tag {tag!r} is cut",
              cuq._regions(f"a <{tag}>SECRET</{tag}> b") == ["a ", " b"])
    check("a non-str text field is dropped, not returned",
          cuq.text_blocks({"content": [{"type": "text", "text": {"n": 1}}]}) == [""])
    check("tool_result blocks are simply not text blocks",
          cuq.text_blocks({"content": [{"type": "tool_result", "content": "o"},
                                       {"type": "text", "text": "mine"}]}) == ["mine"])

    # -- end to end: the false-positive cases -------------------------------
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user(
            "ok do it\n<system-reminder>SENTINEL_ALPHA granted</system-reminder>", human=True)])
        code, out = run(root, "SENTINEL_ALPHA granted", "--show-excluded")
        check("an envelope appended within a human block is not a hit", code == 1)
        code, out = run(root, "ok do it")
        check("...while the genuine part of the same block still hits", code == 0)

    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user("<system-reminder>only this</system-reminder>", human=True)])
        code, out = run(root, "only this")
        check("a human record with no quotable region is unsearchable, not absent", code == 2)
        check("...and says so", "unsearched space" in out)

    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user("brief text", isSidechain=True),
                                user("a real turn", human=True)])
        code, out = run(root, "brief text", "--show-excluded")
        check("a subagent brief is not a hit", code == 1)
        code, out = run(root, "brief text", "--allow-unattributed")
        check("...and --allow-unattributed does not rescue an EXCLUDED record", code == 1)

    # -- end to end: the false-negative cases -------------------------------
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [
            user("This session is being continued only if you agree, so SENTINEL_KILO", human=True),
            user("why do <system-reminder> tags appear SENTINEL_MIKE here?", human=True),
            {"message": {"role": "user", "content": [
                {"type": "tool_result", "content": "out"},
                {"type": "text", "text": "and also SENTINEL_HOTEL please"}]},
             "userType": "external", "origin": {"kind": "human"}},
        ])
        for sentinel, why in (("SENTINEL_KILO", "a human turn opening with an English marker"),
                              ("SENTINEL_MIKE", "a human turn quoting an unclosed tag mid-block"),
                              ("SENTINEL_HOTEL", "human text sharing a record with a tool_result")):
            code, _ = run(root, sentinel)
            check(f"{why} is still quotable", code == 0)

    # -- the unattributed contract ------------------------------------------
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user("an unlabelled sentence"), user("a real turn", human=True)])
        code, out = run(root, "an unlabelled sentence")
        check("an unattributed match does not exit 0", code == 1)
        check("...and is labelled as not evidence",
              "UNATTRIBUTED MATCH" in out and "not evidence" in out)
        code, out = run(root, "an unlabelled sentence", "--allow-unattributed")
        check("--allow-unattributed exits 3, not 0", code == 3)
        check("...and still prints the caution", "not evidence" in out)
        code, out = run(root, "nothing matches this", "--json")
        payload = json.loads(out)
        check("--json reports counts on the absent branch",
              payload["status"] == "absent" and payload["human_regions"] == 1
              and "files" in payload and "records" in payload)

    # -- the negative control, from both directions -------------------------
    with tempfile.TemporaryDirectory() as root:
        write(root, "only-noise.jsonl", [user("injected", isMeta=True)])
        code, out = run(root, "anything")
        check("zero quotable human regions is unsearchable (exit 2)", code == 2)
        check("...and says so rather than reporting an absence", "unsearched space" in out)
        code, out = run(root, "anything", "--json")
        check("--json reports counts on the unsearchable branch",
              json.loads(out)["status"] == "unsearchable" and "files" in json.loads(out))

    code = subprocess.run([sys.executable, str(SCRIPT), "x", "--root", "/nonexistent-xyz"],
                          capture_output=True, text=True).returncode
    check("a --root that is not a directory is a usage error, not an absence", code == 2)

    empty = subprocess.run([sys.executable, str(SCRIPT), "  **  "],
                           capture_output=True, text=True)
    check("an empty phrase is a usage error, not an absence",
          empty.returncode == 2 and "empty after normalization" in empty.stderr)

    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, HOME=home, CLAUDE_CONFIG_DIR=str(Path(home) / "nothing"))
        result = subprocess.run([sys.executable, str(SCRIPT), "x", "--json"],
                                capture_output=True, text=True, env=env)
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        check("--json on the missing-root branch exits 2 with the full schema on stdout",
              result.returncode == 2 and payload.get("status") == "unsearchable"
              and "files" in payload and "human_regions" in payload and "reason" in payload)

    # -- degraded reads: none may become an absence -------------------------
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "torn.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(user("first turn", human=True)) + "\n")
            handle.write("{not json\n\n")
            handle.write(json.dumps(user("merge it", human=True)) + "\n")
        code, out = run(root, "merge it")
        check("a torn line does not end the scan", code == 0)
        check("unparseable lines are counted and reported", "1 unparseable line" in out)

    # A dangling symlink rather than a chmod, so the case holds when the suite
    # runs as root -- where permission bits are not enforced and a chmod-based
    # fixture would pass vacuously.
    with tempfile.TemporaryDirectory() as root:
        write(root, "ok.jsonl", [user("a real turn", human=True)])
        (Path(root) / "gone.jsonl").symlink_to(Path(root) / "nothing-here")
        code, out = run(root, "phrase that is absent")
        check("an unreadable file makes the run unsearchable, not absent", code == 2)
        check("...and names it", "UNREADABLE" in out)

    # os.walk with onerror, not rglob: rglob swallows a permission error from
    # scandir, so an unreadable project directory would shrink the space
    # silently and the run would report an absence.
    if os.geteuid() != 0:
        with tempfile.TemporaryDirectory() as root:
            write(root, "top.jsonl", [user("a real turn", human=True)])
            hidden = Path(root) / "hidden"
            write(root, "hidden/x.jsonl", [user("SENTINEL_INSIDE", human=True)])
            hidden.chmod(0o000)
            try:
                code, out = run(root, "SENTINEL_INSIDE")
                check("an unreadable DIRECTORY is not swallowed into an absence", code == 2)
            finally:
                hidden.chmod(0o755)
    else:
        check("(skipped: running as root, permission bits do not apply)", True)

    # A crash is a search that did not happen. Python's default status for an
    # uncaught exception is 1, which this tool documents as "absent".
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user("a real turn", human=True)])
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys, importlib.util as i;"
             "s=i.spec_from_file_location('m',%r);m=i.module_from_spec(s);s.loader.exec_module(m);"
             "m.text_blocks=lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'));"
             "sys.exit(m.main(['q','--root',%r]))" % (str(SCRIPT), root)],
            capture_output=True, text=True)
        check("an unexpected exception exits 2", result.returncode == 2)
        check("...and names what failed", "failed before it could answer" in result.stderr)

    # -- nested transcripts --------------------------------------------------
    with tempfile.TemporaryDirectory() as root:
        write(root, "proj/session/subagents/agent-1.jsonl", [user("brief", isSidechain=True)])
        write(root, "proj/top.jsonl", [user("a typed turn", human=True)])
        code, out = run(root, "brief", "--show-excluded")
        check("nested subagent transcripts are reached", "subagent transcript" in out)
        check("...and do not count as a hit", code == 1)

    # -- norm(): asserted against the literal, not against itself ------------
    check("norm collapses whitespace and inline markup", cuq.norm("A  `b`  **c**") == "a b c")
    check("norm is not degenerate", cuq.norm("hello") == "hello")

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
