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
skipped = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def skip(name, why):
    """Reported and NOT counted.

    A skip recorded as a pass makes a weakened run indistinguishable from a
    full one by its totals alone -- measured: the permission case is inert as
    root, and the suite printed the same count either way.
    """
    global skipped
    print(f"SKIP: {name} ({why})")
    skipped += 1


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
    # Named explicitly rather than iterated over the constant: a loop reading
    # `for kind in cuq.NON_HUMAN_ORIGINS` deletes its own cases when the
    # constant is emptied, so the mutant survives. Measured -- with
    # NON_HUMAN_ORIGINS = () the suite stayed green while every coordinator
    # record became UNATTRIBUTED and --allow-unattributed certified one.
    for kind in ("channel", "peer", "coordinator", "observer", "observer-activity",
                 "auto-continuation", "task-notification"):
        check(f"origin.kind={kind} is excluded by the label alone",
              cuq.classify_record({"message": {"role": "user", "content": "x"},
                                   "userType": "external",
                                   "origin": {"kind": kind}})[0] == cuq.EXCLUDED)
        check(f"...and {kind} is in NON_HUMAN_ORIGINS", kind in cuq.NON_HUMAN_ORIGINS)
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

    # Named, not iterated over the constant: a loop over FLAG_EXCLUSIONS deletes
    # its own cases when an entry is renamed, and the mutant survives.
    for key in ("isCompactSummary", "isMeta", "isSidechain", "verifiedSlackHumanTurn"):
        check(f"{key} is excluded", cuq.classify_record(user("x", **{key: True}))[0] == cuq.EXCLUDED)
        check(f"...and {key} is in FLAG_EXCLUSIONS",
              key in [k for k, _ in cuq.FLAG_EXCLUSIONS])
    check("an assistant-role record is excluded",
          cuq.classify_record({"message": {"role": "assistant", "content": "x"}})[0] == cuq.EXCLUDED)
    check("a non-external userType is excluded",
          cuq.classify_record({"message": {"role": "user", "content": "x"},
                               "userType": "internal"})[0] == cuq.EXCLUDED)

    # TRANSCRIPT_PREFIXES are ordinary English, so they apply ONLY where the
    # harness withheld the human label. On a human-labelled turn they must not.
    for prefix in ("This session is being continued",
                   "Caveat: The messages below were generated",
                   "The coordinator sent a message while you were working"):
        check(f"prefix {prefix[:28]!r} excludes an UNLABELLED record",
              cuq.classify_record(user(prefix + " and then some"))[0] == cuq.EXCLUDED)
        check("...and does NOT exclude a human-labelled one",
              cuq.classify_record(user(prefix + " and then some", human=True))[0] == cuq.HUMAN)
        check("...and is in TRANSCRIPT_PREFIXES", prefix in cuq.TRANSCRIPT_PREFIXES)

    # -- regions: all or nothing ------------------------------------------
    check("a plain block is quotable whole",
          cuq._regions("just some text") == ["just some text"])
    check("an empty block yields nothing", cuq._regions("   ") == [])
    for tag in ("task-notification", "system-reminder", "wake", "command-name"):
        check(f"a block carrying <{tag}> is unquotable in full",
              cuq._regions(f"genuine text <{tag}>INJECTED</{tag}> more genuine") == [])
        check(f"...and {tag} is in ENVELOPE_TAGS", tag in cuq.ENVELOPE_TAGS)
    # The five shapes that broke the five previous designs, in order. Each was
    # a live exit-0 certification of harness prose when it was found.
    for label, block in (
        ("appended reminder", "ok do it\n<system-reminder>A</system-reminder>"),
        ("mid-block reminder", "before <system-reminder>A</system-reminder> after"),
        ("leading envelope", "<system-reminder>A</system-reminder>first<system-reminder>B</system-reminder>second"),
        ("repeated opener", "<system-reminder>OUT <system-reminder>i</system-reminder> A</system-reminder>"),
        ("literal closing tag inside", "<system-reminder>about the </system-reminder> tag, A</system-reminder>"),
        ("truncated, not at the start", "sure go ahead <system-reminder>A truncated"),
    ):
        check(f"{label}: nothing quotable", cuq._regions(block) == [])
    check("uppercase tags are caught too",
          cuq._regions("x <SYSTEM-REMINDER>A</SYSTEM-REMINDER> y") == [])
    check("an attribute-bearing opener is caught",
          cuq._regions('x <system-reminder priority="high">A</system-reminder> y') == [])
    check("a non-str text field is not returned as-is",
          cuq.text_blocks({"content": [{"type": "text", "text": {"n": 1}}]}) == [""])
    check("tool_result blocks are simply not text blocks",
          cuq.text_blocks({"content": [{"type": "tool_result", "content": "o"},
                                       {"type": "text", "text": "mine"}]}) == ["mine"])

    # -- end to end: the false-positive cases -------------------------------
    # An enveloped block is unquotable IN FULL, so its genuine text is not
    # quotable from that block either. That is the accepted cost of not parsing
    # -- and the run says "unsearched space", never "the user never said it".
    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user(
            "ok do it\n<system-reminder>SENTINEL_ALPHA granted</system-reminder>", human=True)])
        code, out = run(root, "SENTINEL_ALPHA granted", "--show-excluded")
        check("an envelope appended within a human block is not a hit", code != 0)
        check("...and the run reports an unsearched space, not an absence",
              code == 2 and "unsearched space" in out)
        code, out = run(root, "ok do it")
        check("...and the genuine text of that block is not quotable either", code == 2)

    with tempfile.TemporaryDirectory() as root:
        write(root, "a.jsonl", [user(
            "<system-reminder>A</system-reminder>please check the issues"
            "<system-reminder>B</system-reminder>referenced here", human=True),
            user("an unenveloped turn SENTINEL_CLEAN", human=True)])
        code, out = run(root, "issuesreferenced here")
        check("a phrase never contiguous in the real turn is not a hit", code == 1)
        code, out = run(root, "SENTINEL_CLEAN")
        check("...while an unenveloped turn in the same file still hits", code == 0)

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
                              ("SENTINEL_HOTEL", "human text sharing a record with a tool_result")):
            code, _ = run(root, sentinel)
            check(f"{why} is still quotable", code == 0)
        # The accepted cost, asserted rather than left implicit: a turn writing
        # ABOUT a tag is not quotable from that block. Denying a real quotation
        # is the safe direction; certifying harness prose is not.
        code, out = run(root, "SENTINEL_MIKE", "--show-excluded")
        check("a turn quoting a tag is NOT quotable", code != 0)
        check("...and --show-excluded names the envelope as the reason, "
              "so the skip is visible rather than silent",
              "block carries a harness envelope tag" in out)

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

    # Root resolution can raise before the scan begins -- an unresolvable ~user,
    # or Path.home() with HOME unset and no passwd entry. An uncaught exception
    # exits 1, which this tool documents as "absent".
    env = dict(os.environ, CLAUDE_CONFIG_DIR="~nosuchuser12345/x")
    env.pop("HOME", None)
    result = subprocess.run([sys.executable, str(SCRIPT), "hi"],
                            capture_output=True, text=True, env=env)
    check("a crash resolving the root exits 2, not 1", result.returncode == 2)
    check("...and names what failed",
          "could not resolve a transcript root" in result.stderr
          or "No transcript root at" in result.stderr)

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

    # A torn line is the normal state of a transcript being appended to, and it
    # shrinks the searched space exactly as an unreadable file does. Reporting
    # an absence over it is the "I could not look" collapse the exit contract
    # exists to prevent.
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "live.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(user("a good turn", human=True)) + "\n")
            handle.write('{"message": {"role": "user", "cont')
        code, out = run(root, "a phrase that is genuinely absent")
        check("an unparseable line makes the run unsearchable, not absent", code == 2)
        check("...and says the space could not be read", "could not be read" in out)
        code, out = run(root, "a phrase that is genuinely absent", "--json")
        check("...and --json agrees", json.loads(out)["status"] == "unsearchable")

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
        skip("unreadable directory", "running as root; permission bits do not apply")

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

    print(f"\n{passes} passed, {failures} failed, {skipped} skipped")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
