#!/usr/bin/env python3
"""Regression tests for pr-scope.py.

The table below is the scope rule's own case list, taken from
`memories/reviewing-prs.md` rather than invented: the three Actions-app
login forms, the two-account alias mapping, an assignee, an explicit
request, the "do not touch #284" mention that is a veto rather than a
request, and the no-identity fail-closed case.

The classifier is pure over the PR payload shape, so these run offline with
no `gh` call.
"""
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "pr_scope", Path(__file__).parent / "pr-scope.py"
)
pr_scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr_scope)

passes = 0
failures = 0

ME = "d-morrison"
ALIAS = "dem-extra1"


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def gh_pr(number, author, assignees=(), base="main", head=None):
    """A `gh pr list --json` shaped entry."""
    return {
        "number": number,
        "title": f"PR {number}",
        "author": {"login": author},
        "assignees": [{"login": a} for a in assignees],
        "headRefName": head or f"branch-{number}",
        "baseRefName": base,
        "isDraft": False,
    }


def scope(prs, user=ME, aliases=(), requested=(), excluded=()):
    identities = ([user] if user else []) + list(aliases)
    return pr_scope.scope(
        prs,
        identities,
        set(requested),
        set(excluded),
        identity_resolved=bool(identities),
    )


def reason_for(result, number):
    for pr in result["prs"]:
        if pr["number"] == number:
            return pr["reason"]
    return None


# --- The scope table -------------------------------------------------------
#
# Each row: a PR, and the disposition the rule in memories/reviewing-prs.md
# gives it. Read as one table so a wrong arm shows up as a row rather than
# as a scattered assertion.

TABLE = [
    # (label, pr payload, requested, excluded, expected in_scope, reason)
    ("author is the user",
     gh_pr(1, ME), (), (), True, pr_scope.REASON_AUTHOR),
    ("author is the user's other account",
     gh_pr(2, ALIAS), (), (), True, pr_scope.REASON_AUTHOR),
    ("author differs only in case",
     gh_pr(3, "D-Morrison"), (), (), True, pr_scope.REASON_AUTHOR),
    ("assigned to the user",
     gh_pr(4, "someone-else", assignees=[ME]), (), (),
     True, pr_scope.REASON_ASSIGNEE),
    ("assigned to the user's other account",
     gh_pr(5, "someone-else", assignees=["third-party", ALIAS]), (), (),
     True, pr_scope.REASON_ASSIGNEE),
    ("explicitly requested by number",
     gh_pr(6, "someone-else"), (6,), (),
     True, pr_scope.REASON_REQUESTED),
    ("Actions app, gh pr list form",
     gh_pr(7, "app/github-actions"), (), (),
     True, pr_scope.REASON_ACTIONS_APP),
    ("Actions app, REST and MCP form",
     gh_pr(8, "github-actions[bot]"), (), (),
     True, pr_scope.REASON_ACTIONS_APP),
    ("Actions app, GraphQL bare form",
     gh_pr(9, "github-actions"), (), (),
     True, pr_scope.REASON_ACTIONS_APP),
    ("another member's PR",
     gh_pr(10, "someone-else"), (), (),
     False, pr_scope.REASON_NOT_MINE),
    ("another bot's PR",
     gh_pr(11, "dependabot[bot]"), (), (),
     False, pr_scope.REASON_NOT_MINE),
    ("a Copilot agent's PR",
     gh_pr(12, "copilot-swe-agent[bot]"), (), (),
     False, pr_scope.REASON_NOT_MINE),
    ("do not touch #284 vetoes a PR the user authored",
     gh_pr(284, ME), (), (284,), False, pr_scope.REASON_EXCLUDED),
    ("the veto beats the assignee arm",
     gh_pr(285, "someone-else", assignees=[ME]), (), (285,),
     False, pr_scope.REASON_EXCLUDED),
    ("the veto beats the Actions-app arm",
     gh_pr(286, "github-actions[bot]"), (), (286,),
     False, pr_scope.REASON_EXCLUDED),
    ("the veto beats an explicit request",
     gh_pr(287, "someone-else"), (287,), (287,),
     False, pr_scope.REASON_EXCLUDED),
]

for label, pr, requested, excluded, want_scope, want_reason in TABLE:
    result = scope([pr], aliases=[ALIAS], requested=requested, excluded=excluded)
    entry = result["prs"][0]
    check(
        f"{label}: {'in scope' if want_scope else 'excluded'} ({want_reason})",
        entry["in_scope"] is want_scope and entry["reason"] == want_reason,
    )

# --- Fail closed on identity ----------------------------------------------

no_id = scope(
    [gh_pr(20, ME), gh_pr(21, "someone-else", assignees=[ME]),
     gh_pr(22, "github-actions[bot]"), gh_pr(23, "someone-else")],
    user=None,
    requested=(23,),
)
check("no identity: the author arm is unevaluated, not assumed true",
      reason_for(no_id, 20) == pr_scope.REASON_NO_IDENTITY)
check("no identity: the assignee arm is unevaluated, not assumed true",
      reason_for(no_id, 21) == pr_scope.REASON_NO_IDENTITY)
check("no identity: an Actions-app PR still passes",
      reason_for(no_id, 22) == pr_scope.REASON_ACTIONS_APP)
check("no identity: an explicitly requested PR still passes",
      reason_for(no_id, 23) == pr_scope.REASON_REQUESTED)
check("no identity: identity_resolved is false",
      no_id["identity_resolved"] is False)
check("no identity: a warning says the arms went unevaluated",
      any("unevaluated" in w for w in no_id["warnings"]))
check("resolved identity emits no warning",
      scope([gh_pr(24, ME)])["warnings"] == [])

# --- Field-name normalization ---------------------------------------------

rest_shape = {
    "number": 30,
    "user": {"login": ME},
    "assignees": [{"login": "third-party"}],
    "head": {"ref": "feature"},
}
check("REST shape: user.login is read as the author",
      scope([rest_shape])["prs"][0]["reason"] == pr_scope.REASON_AUTHOR)

mcp_shape = {"number": 31, "user": {"login": "someone-else"}, "assignees": [ME]}
check("MCP shape: bare login strings in assignees are read",
      scope([mcp_shape])["prs"][0]["reason"] == pr_scope.REASON_ASSIGNEE)

mcp_unassigned = {"number": 32, "user": {"login": "someone-else"}}
check("MCP shape: a missing assignees key means unassigned, not malformed",
      scope([mcp_unassigned])["prs"][0]["reason"] == pr_scope.REASON_NOT_MINE)

gitlab_shape = {
    "iid": 33,
    "author": {"username": ME},
    "assignees": [{"username": "third-party"}],
    "source_branch": "feature",
    "target_branch": "main",
}
gitlab = scope([gitlab_shape])["prs"][0]
check("GitLab shape: author.username and iid are read",
      gitlab["number"] == 33 and gitlab["reason"] == pr_scope.REASON_AUTHOR)
check("GitLab shape: source_branch and target_branch map to head and base",
      gitlab["head"] == "feature" and gitlab["base"] == "main")

# --- The full list survives, for stack mapping ----------------------------

stack = scope([
    gh_pr(40, "someone-else", head="base-branch"),
    gh_pr(41, ME, base="base-branch"),
])
check("the excluded base PR is still in the full listing",
      [p["number"] for p in stack["prs"]] == [40, 41])
check("the excluded base PR keeps its head ref for stack detection",
      stack["prs"][0]["head"] == "base-branch")
check("included and excluded numbers are both reported",
      stack["included"] == [41] and stack["excluded"] == [40])
check("examined counts every PR, not only the kept ones",
      stack["examined"] == 2)

# --- Login normalization --------------------------------------------------

check("app/ prefix is stripped",
      pr_scope.normalize_login("app/github-actions") == "github-actions")
check("[bot] suffix is stripped",
      pr_scope.normalize_login("github-actions[bot]") == "github-actions")
check("a bare login is unchanged",
      pr_scope.normalize_login("github-actions") == "github-actions")
check("dependabot does not normalize onto the Actions app",
      pr_scope.normalize_login("dependabot[bot]") != pr_scope.ACTIONS_APP_SLUG)
check("None normalizes to the empty string rather than raising",
      pr_scope.normalize_login(None) == "")

# --- Argument parsing -----------------------------------------------------

check("comma-separated numbers parse",
      pr_scope.split_numbers(["1,2, 3"]) == {1, 2, 3})
check("repeated numbers parse",
      pr_scope.split_numbers(["1", "2"]) == {1, 2})
check("a leading hash is tolerated",
      pr_scope.split_numbers(["#284"]) == {284})
check("an empty list parses to no numbers",
      pr_scope.split_numbers([]) == set())
try:
    pr_scope.split_numbers(["not-a-number"])
    check("a non-numeric PR id raises rather than being dropped", False)
except pr_scope.InputError:
    check("a non-numeric PR id raises rather than being dropped", True)
check("comma-separated aliases parse",
      pr_scope.split_logins(["a, b"]) == ["a", "b"])

# --- Payload loading ------------------------------------------------------

check("a bare list loads",
      len(pr_scope.load_payload(json.dumps([gh_pr(50, ME)]))) == 1)
check("a wrapper object loads",
      len(pr_scope.load_payload(json.dumps({"prs": [gh_pr(51, ME)]}))) == 1)
check("a single PR object loads as a one-element list",
      len(pr_scope.load_payload(json.dumps(gh_pr(52, ME)))) == 1)
for bad, label in (("{}", "an unrecognized object"), ('"x"', "a bare string")):
    try:
        pr_scope.load_payload(bad)
        check(f"{label} raises rather than scoping nothing silently", False)
    except pr_scope.InputError:
        check(f"{label} raises rather than scoping nothing silently", True)

try:
    pr_scope.normalize_pr({"author": {"login": ME}})
    check("a PR with no number raises rather than being skipped", False)
except pr_scope.InputError:
    check("a PR with no number raises rather than being skipped", True)

# --- Negative control -----------------------------------------------------
#
# A table that cannot fail is indistinguishable from one that never ran, so
# assert that a deliberately broken predicate is caught by it.

ids = {pr_scope.normalize_login(ME), pr_scope.normalize_login(ALIAS)}
leaked = []
for label, pr, requested, excluded, want_scope, want_reason in TABLE:
    if want_scope or not excluded:
        continue
    # The same row, classified with the veto list emptied.
    in_scope, _ = pr_scope.classify(
        pr_scope.normalize_pr(pr), ids, set(requested), set(), True
    )
    if in_scope:
        leaked.append(label)
check("negative control: dropping the exclusion veto lets vetoed PRs through",
      len(leaked) == 4)

# --- End-to-end through main() --------------------------------------------

payload = json.dumps([gh_pr(60, ME), gh_pr(61, "someone-else")])
buf = io.StringIO()
sys.stdin = io.StringIO(payload)
with redirect_stdout(buf):
    code = pr_scope.main(["--user", ME])
sys.stdin = sys.__stdin__
emitted = json.loads(buf.getvalue())
check("main reads stdin and emits JSON with exit 0",
      code == 0 and emitted["included"] == [60]
      and emitted["excluded"] == [61])

buf = io.StringIO()
sys.stdin = io.StringIO(payload)
with redirect_stdout(buf):
    code = pr_scope.main(["--user", ME, "--text"])
sys.stdin = sys.__stdin__
text = buf.getvalue()
check("--text reports what was examined before what it found",
      code == 0 and text.startswith("examined 2 PR(s)"))

buf = io.StringIO()
sys.stdin = io.StringIO("not json")
with redirect_stdout(buf):
    code = pr_scope.main(["--user", ME])
sys.stdin = sys.__stdin__
check("malformed input exits 2 rather than reporting an empty scope",
      code == 2)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
