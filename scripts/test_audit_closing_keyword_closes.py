#!/usr/bin/env python3
"""Regression tests for audit-closing-keyword-closes.py.

The fixtures for #32, #603, #1154, and #1522 paraphrase real closer text
from the 2026-09-22 audit of Lacaedemon/sparta (issue numbers kept for
traceability; #1154 has since been re-closed as not planned, so a live run
now skips it). The rest are constructed edge cases, and use issue numbers
only as labels. The classifier is pure over the GraphQL node shape, so these
run offline with no `gh` call.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "audit", Path(__file__).parent / "audit-closing-keyword-closes.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

REPO = "Lacaedemon/sparta"
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


def pr_node(number, body, merge_message="", state_reason="COMPLETED"):
    closer = {"__typename": "PullRequest", "number": 9000, "body": body,
              "mergeCommit": {"oid": "c5beccd9aaaa", "message": merge_message}}
    return {"number": number, "title": f"issue {number}", "stateReason": state_reason,
            "timelineItems": {"nodes": [{"closer": closer}]}}


def verdict(node):
    return audit.classify(node, REPO)


# sparta#32: a negated close with nothing deliberate beside it.
v = verdict(pr_node(32, "## Summary\n\nThis **does not close #32** -- it's the first of three stages."))
check("negated close alone is flagged incidental",
      v["verdict"] == "flagged" and v["contradicted"] is False)

# sparta#603: the description negates the close while the squashed start
# commit closes it deliberately -- the closer disagrees with itself.
v = verdict(pr_node(
    603,
    "Phase 1 only. It does not close #603; the rest is tracked in #1503.",
    "Campaign phase 1 (#1496)\n\n* start: Campaign phase 1: map and time foundation (closes #603)\n"))
check("negation beside a deliberate start-commit close is flagged contradicted",
      v["verdict"] == "flagged" and v["contradicted"] is True)

# sparta#1154: `fix: #N` -- GitHub allows the colon -- inside "rather than".
v = verdict(pr_node(1154, "Tracked as its own issue rather than blocking this fix: #1154."))
check("keyword-colon-number inside a 'rather than' sentence is flagged",
      v["verdict"] == "flagged")

# sparta#1522 shape: a squash message of start/fix bullets whose SUBJECTS carry
# cue words ("after", "not"). Before list items bounded the sentence window,
# these bled into each other and flagged 31 deliberate closes.
v = verdict(pr_node(
    1522, "Closes #1522",
    "Title (#1536)\n\n"
    "* start: partial-rank reform after a turn must not countermarch (closes #1522)\n"
    "* fix: reform keeps its files after the turn\n\nCloses #1522\n"))
check("cue words in a bullet's subject do not taint a (closes #N) tag",
      v["verdict"] == "deliberate")

v = verdict(pr_node(
    1300, "",
    "* start: add demo options (slow motion, before/after comparisons) (closes #1300)"))
check("a parenthetical close tag is deliberate even with a cue in its sentence",
      v["verdict"] == "deliberate")

# No parenthesis here, so only the list-item bound keeps the neighbouring
# bullet's "not" out of this close's sentence.
v = verdict(pr_node(
    1400, "", "* feat: this closes #1400 cleanly\n* revert: do not keep the old fallback"))
check("a cue in the next bullet does not taint a mid-line close",
      v["verdict"] == "deliberate")

text = "a\n* one after\n* two (closes #5)\n* three"
begin, end = audit.list_item_bounds(text, text.index("two"))
check("list-item bounds isolate the bullet holding the match",
      text[begin:end] == "* two (closes #5)")

# A line-leading close is deliberate whatever surrounds it.
v = verdict(pr_node(1565, "Closes #1565\n\nFollow-ups will land later."))
check("line-leading Closes is deliberate", v["verdict"] == "deliberate")

# References to other issues, or to the same number in another repo, are not
# this issue's close.
v = verdict(pr_node(700, "This does not close #701."))
check("a reference to another issue number is ignored", v["verdict"] == "unattributed")

v = verdict(pr_node(700, "This closes other/repo#700 and will not touch anything else."))
check("the same number in another repo is ignored", v["verdict"] == "unattributed")

v = verdict(pr_node(700, "This closes lacaedemon/SPARTA#700 and will not touch anything else."))
check("this repo named explicitly, in any case, is recognised", v["verdict"] == "flagged")

v = verdict(pr_node(100, "", "* start: tidy (closes #100, not yet verified)"))
check("a cue inside the close tag's own parenthesis still makes it risky",
      v["verdict"] == "flagged")

v = verdict(pr_node(5, "", "* start: x (closes #5 (originally reported in #3) but not verified)"))
check("a nested parenthesis does not end the tag's cue scan early",
      v["verdict"] == "flagged")

v = verdict(pr_node(
    435, "This must not auto-close https://github.com/Lacaedemon/sparta/issues/435 yet."))
check("a full issue URL for this repo is recognised", v["verdict"] == "flagged")

check("NOT_PLANNED closes are skipped",
      verdict(pr_node(1, "does not close #1", state_reason="NOT_PLANNED"))["verdict"] == "skipped")

no_closer = {"number": 2, "title": "t", "stateReason": "COMPLETED",
             "timelineItems": {"nodes": [{"closer": None}]}}
check("a close with no recorded closer is unattributed",
      verdict(no_closer)["verdict"] == "unattributed")

commit_node = {"number": 3, "title": "t", "stateReason": "COMPLETED",
               "timelineItems": {"nodes": [{"closer": {
                   "__typename": "Commit", "oid": "abc", "message": "fix: x\n\nFixes #3\n"}}]}}
check("a commit closer is scanned", verdict(commit_node)["verdict"] == "deliberate")

# parse_page: the two failures that would otherwise surface far from their cause.
def raises_oserror(stdout):
    try:
        audit.parse_page(stdout)
    except OSError:
        return True
    return False


check("parse_page refuses a None stdout", raises_oserror(None))
check("parse_page surfaces GraphQL errors",
      raises_oserror(json.dumps({"data": None, "errors": [{"message": "rate limited"}]})))
check("parse_page refuses a missing repository",
      raises_oserror(json.dumps({"data": {"repository": None}})))
page = {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}
check("parse_page returns the issues connection",
      audit.parse_page(json.dumps({"data": {"repository": {"issues": page}}})) == page)

# End to end through main(): exit 1 when flagged, 0 when clean, 2 on error.
with tempfile.TemporaryDirectory() as directory:
    flagged = Path(directory) / "flagged.json"
    flagged.write_text(json.dumps([pr_node(32, "This does not close #32.")]), encoding="utf-8")
    clean = Path(directory) / "clean.json"
    clean.write_text(json.dumps([pr_node(5, "Closes #5")]), encoding="utf-8")
    broken = Path(directory) / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    malformed = Path(directory) / "malformed.json"
    malformed.write_text(json.dumps([{"number": 4, "stateReason": "COMPLETED",
                                      "timelineItems": {"nodes": ["not an object"]}}]),
                         encoding="utf-8")
    check("main exits 2, not 1, on a malformed node",
          audit.main(["-R", REPO, "--from-json", str(malformed)]) == 2)
    check("main exits 1 when an issue is flagged",
          audit.main(["-R", REPO, "--from-json", str(flagged)]) == 1)
    check("main exits 0 when nothing is flagged",
          audit.main(["-R", REPO, "--from-json", str(clean)]) == 0)
    check("main exits 2 on an unreadable payload",
          audit.main(["-R", REPO, "--from-json", str(broken)]) == 2)
    check("main exits 2 on a malformed repo", audit.main(["-R", "sparta"]) == 2)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
