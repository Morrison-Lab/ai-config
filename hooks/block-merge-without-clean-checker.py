#!/usr/bin/env python3
"""PreToolUse DENY: a PR merge with no `check-pr-fully-clean.py` pass for its head.

## The failure this exists for

On 2026-10-26 two thread sessions merged psw#354 (at 6ebf005) and gha#1239 (at
f450d6f) under a standing `mwc` without a `check-pr-fully-clean.py` run that
exited 0 on the head being merged. psw#354's only run had been made while
`build / build` was still pending. The rule was in project memory and
AGENTS.md, and both sessions knew it. It had happened before (ai-config#4399,
2026-10-08; ai-config#4538, 2026-10-15), and each time a hook "warned".

## Why the existing hooks did not stop it

* `no-unauthorized-merge.py` gates PERMISSION (the `mwc` grant), not
  cleanliness. A standing grant satisfied it.
* `enforce-mwc-review-gate.py` gates the live review state read from GitHub,
  not the instrument, and not the cloud case where it cannot run.
* `warn-merge-without-fully-clean.py` is the right idea and only WARNS (its
  docstring says it was "intended to be promoted to a deny once its
  false-positive rate is measured"). A warning arrives as context the session
  can read past. It also ties a run to the PR NUMBER, never to the HEAD SHA,
  so a run from before the last push, or one made while a check was pending,
  can pass; it credits only a Bash run in this transcript, which a cloud
  session can in fact produce (the checker builds a REST payload in a cloud
  container; before ai-config#4746 this was believed to need a Remote Control
  session, with the result relayed back as a message); and
  it lets a merge naming no PR number through.

## The condition (all must hold, or the merge is DENIED)

1. The merge names its PR (repo, number) and EXPECTED HEAD SHA (40 hex):
   `expectedHeadSha` on the MCP tool, `--match-head-commit` on `gh pr merge`,
   `-f sha=` on `gh api .../merge`, `"sha"` in a `curl` body. Pinning the sha
   is what lets GitHub itself refuse a merge if the head moved after the run.
2. The transcript holds the instrument's own line
   `<owner>/<repo>#<N> is FULLY CLEAN on HEAD <sha8>! [stale-base rule]` for that repo, that
   number, and a sha that is a prefix of the merge's sha. That line is printed
   only on exit 0, so it IS the exit status; it is tied to the head by
   construction, which makes "after the last push" a non-question: a push
   changes the head, and the old line no longer matches.
3. The line is in a RESULT, not in the model's own words. Accepted sources:
   * a Bash result whose command RAN the instrument (command word or an
     interpreter's first operand), with no `echo`/`printf`/`cat`/`tee` in the
     same command able to print it, and not a subagent's;
   * a RELAYED result: a user-role message (the coordinator or Ezra relays
     the Remote Control run's output), or the result of a message-reading
     tool (`ReadNotifications`, `mcp__hearthbot__read_*`,
     `mcp__claude-code-remote__get_event|list_events`). This is the cloud
     path: the session cannot run the checker, a Remote Control session does,
     and its output line comes back with the SHA in it.
   The assistant's own prose, and tool INPUTS, never count.
4. A "NOT fully clean" line in the same Bash result vetoes it.

No escape variable: a gate with a reflex escape stops being a gate
(`feedback-fix-wrong-gate-never-override`). A checker that looks wrong is
fixed or its input corrected, then re-run.

The one path past condition 2 is the USER'S OWN TYPED WORDS: an explicit
"merge it anyway" (or "override the merge check") in a user-role text block,
including a relayed `<cited author="user">` entry (Ezra, 2026-11-02, epi202#4).
A wake message that declares a trust other than `principal`, or a sender
other than `human`, is skipped; one that declares neither is read. A
decision-card tap is not typed words either, since the agent wrote the card.

A second path is a waiver he TAPS on a decision card (Ezra, 2026-11-19,
ai-config#5892: a repository with no workflows and no review bot can never
pass the checker, and his tapped waiver on quarto.test.book#7 and
test.quarto.website#3 was refused). The agent writes a card's text, so a tap
is held to more than typed words are: `tapped_waivers` lists the conditions,
and the waiver covers only the pull requests the card names.
The agent cannot supply it: the coordinator's `<note>`, a cited coordinator
entry, system reminders, tool results and the assistant's prose never count,
and a negated phrase does not. Condition 1 (PR, repo, 40-character sha pin)
still holds, and the merge is logged on stderr.

## The `mwr` grant (ai-config#3946)

Under the user's own typed `mwr` or `mwrs` (read by
`no-unauthorized-merge.py`'s `transcript_mwr_grant`, for this PR), the
checker's `--mwr` pass line
`<owner>/<repo>#<N> is MERGE-READY under mwr (review not evaluated) on HEAD <sha40>! [stale-base rule]`
stands in for the FULLY CLEAN line in condition 2. Conditions 1, 3 and 4
are unchanged: the same sha pin, repo, number, sources and veto. The line
is narrower still (round 5): it counts only as the last non-empty line of
a Bash run of `$CLAUDE_PLUGIN_ROOT/scripts/check-pr-fully-clean.py` alone,
never a checkout's copy, and only when it names the `-R` repository and
PR number of that same command. Without
the grant a MERGE-READY line satisfies nothing, and any error reading the
grant or the line counts as no grant (fails closed). An `echo` argument
holding "ready" is a possible forgery, as one holding "clean" is, and so
is any `echo` argument holding a backslash and any `echo -e`, on either
line, since escapes can spell either word.

A merge credited by the MERGE-READY line, not a FULLY CLEAN line, also
passes the live re-checks of `enforce-mwc-review-gate.py`
(`fetch_mwr_live`, `mwr_live_problem`; round 8), read in this hook call,
whatever the review gate decided: no DISMISSED, CHANGES_REQUESTED or
REJECTED review, nothing under `.github/` in the live base...head compare,
and a live head equal to the pinned sha. A problem or a failed read denies.

Under an mwr grant with no other user-given authority (`mwr_only_grant`,
round 9), a FULLY CLEAN line does not count at all: the merge needs the
MERGE-READY line and the live re-checks, whatever else the transcript holds.
The other authority (`other_merge_authority`, round 10) is what
`no-unauthorized-merge.py` reads: the user's typed `mwc`
(`transcript_merge_grant`, never the `.mwc` marker the agent can write), a
typed "merge ... PR N" naming the PR, the standing per-repository grant and
the standing infra-PR grant. `ALLOW_MERGE=1` never counts. An unreadable
grant counts as none, so the merge stays on the mwr path.

An mwr-only merge has one route (`mwr_route_problem`, round 12): the MCP
merge tool, with only the tool schema's keys, a digit `pullNumber` and an
`expectedHeadSha` of 40 lowercase hex characters. A gh, gh api or curl
merge is denied before any other check, since this hook reads such a
command differently from gh, curl and the server (ai-config#5959).
The same route is required of any merge the MERGE-READY line credits, under
a typed `mwc`, a named grant or any other authority as well (round 13). A
merge credited by a FULLY CLEAN line or the typed override keeps every
route. This check fails closed, so it is the backstop when
`no-unauthorized-merge.py` steps aside for `ALLOW_MERGE=1` or an
`allow_merge` input key.

## Recognised merge routes

`mcp__github__merge_pull_request`; `gh pr merge`; `gh api -X PUT
repos/o/r/pulls/N/merge`; `curl -X PUT .../repos/o/r/pulls/N/merge`; and a
`gh api graphql` call naming `mergePullRequest`, which cannot be tied to a
PR and is denied outright (use `gh pr merge`). Command position comes from
`scripts/lib/shellcmd.py`, so an echoed, grepped or heredoc-quoted merge is
inert.

LIMITS
------
* The typed path reads a wake's `<message>` elements as the harness wrote them.
  If a harness ever left a literal `</message>` unescaped inside a peer
  message's body, the text after it would read as a new element.
* A tap is told from typed words by its shape alone. A whole message the user
  types that opens with `Chose "`, holds `" on the decision card asking "`
  and ends with a quote mark is read as a tap and gives no override.
* The trust and sender checks read the whole `<message>` tag, so the user's
  own message is skipped if another attribute's value holds text such as
  `trust=peer`. Both limits refuse a merge and never allow one.
* A wake `<message>` with neither a `trust` nor a `from` attribute is read, as
  it was before those attributes were checked.
* A relayed line is trusted as relayed: a session that forges a message-reading
  result is outside what a transcript can show. The sha tie still means the
  line must name the exact head being merged.
* `mcp__github__enable_pr_auto_merge` merges later with no sha and is not
  covered here; `no-unauthorized-merge.py` still gates it.
* GitHub web UI merges and merges by another session or the `@claude` agent
  are not seen.
* Fails OPEN when the payload or transcript is unreadable (some harnesses
  supply no transcript); a broken `shellcmd` import writes one STDERR line.
"""
import html
import json
import os
import re
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from sibling import load_sibling
except ImportError as _exc:
    print(f"block-merge-without-clean-checker: cannot load scripts/lib/sibling.py "
          f"({_exc}); using the raw JSONL reader", file=sys.stderr)
    load_sibling = None


# `records` normalizes Antigravity `PLANNER_RESPONSE` / `GENERIC` /
# `SYSTEM_MESSAGE` records into `_agy_blocks` (`tool_use` and `tool_result`);
# without the sibling the hook reads raw JSONL and still gates
# (scripts/lib/sibling.py).
_SIB_WMWFC = None
if load_sibling is not None:
    _SIB_WMWFC = load_sibling(__file__, "warn-merge-without-fully-clean.py", "_sib_wmwfc")


def _raw_records(path):
    """Yield each JSON object line of the transcript, skipping the rest."""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if isinstance(rec, dict):
                yield rec


_records = getattr(_SIB_WMWFC, "records", None) or _raw_records
try:
    from shellcmd import simple_commands, strip_env, shell_c_expansions
except Exception as _exc:  # broken install: degrade, never block
    print(f"block-merge-without-clean-checker: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); no gate will run", file=sys.stderr)
    simple_commands = strip_env = shell_c_expansions = None
try:
    import card_answer
except Exception as _exc:  # no tap parser: a tapped waiver is never read
    print(f"block-merge-without-clean-checker: cannot load "
          f"scripts/lib/card_answer.py ({_exc}); tapped waivers are refused",
          file=sys.stderr)
    card_answer = None

SHELL_TOOLS = frozenset({"Bash", "bash", "PowerShell", "run_command",
                         "execute_command", "terminal", "shell"})
MCP_MERGE_TOOL = "mcp__github__merge_pull_request"
RELAY_TOOLS = frozenset({
    "ReadNotifications", "mcp__claude-code-remote__get_event",
    "mcp__claude-code-remote__list_events",
})
RELAY_PREFIXES = ("mcp__hearthbot__read_",)
INSTRUMENT = "check-pr-fully-clean.py"
RUNNERS = frozenset({"python", "python3", "py", "python3.11", "python3.12",
                     "python3.13", "uv", "uvx", "poetry", "pdm", "hatch",
                     "pipenv", "rye", "pixi"})
NOT_A_FILE = frozenset({"-c", "--command", "-m", "--module", "-h", "--help",
                        "-V", "--version"})
PRINTERS = frozenset({"echo", "printf", "cat", "tee"})
RX_DURATION = re.compile(r"^\d+(\.\d+)?[smhd]?$")
WRAPPERS = frozenset({"timeout", "time", "nice", "nohup", "command", "stdbuf"})
RX_FORGE = re.compile(r"clean|ready|\$(?!\?)|`", re.IGNORECASE)
# The only Bash command whose output can supply the `--mwr` MERGE-READY line
# (ai-config#3946): the checker run alone, with plain arguments (no quotes,
# braces, expansions, globs, pipes or redirects but `2>&1`). A printer
# denylist cannot be completed (brace expansion, `python3 -c`, `awk`), so the
# MERGE-READY line uses this allowlist instead. No trailing `echo` is
# allowed, since only the run's last line is credited (round 5, finding 2).
# The FULLY CLEAN line keeps `_runs_instrument`.
RX_INSTRUMENT_ALONE = re.compile(
    r"\A[ \t]*(?:(?:python3?|py)[ \t]+)?(?P<script>(?:[\w./-]*/)?check-pr-fully-clean\.py)"
    r"(?P<args>(?:[ \t]+[\w./:=,@+-][\w./#:=,@+-]*)*)(?:[ \t]+2>&1)?[ \t]*\n?\Z")
# An echo option cluster that turns on escape reading: `-e`, `-ne`, `-en`.
RX_ECHO_E = re.compile(r"^-[a-zA-Z]*e[a-zA-Z]*$")
RX_EVIDENCE = re.compile(
    r"([\w.-]+/[\w.-]+)#(\d+) is FULLY CLEAN on HEAD ([0-9a-f]{7,40})!? \[stale-base rule\]")
# The checker's pass line under `--mwr` (ai-config#3946): review verdicts and
# quorum were not evaluated, every other axis was. It stands in for the
# FULLY CLEAN line only under the user's typed `mwr`/`mwrs` grant.
# The sha is the full 40 hex characters (round 6), and `mwr_clears` requires
# it to equal the merge's pinned sha. A checker older than round 6 printed an
# 8-hex prefix there; that line no longer matches, so until the plugin root's
# copy updates, an mwr merge is refused (fails closed).
RX_MWR_EVIDENCE = re.compile(
    r"([\w.-]+/[\w.-]+)#(\d+) is MERGE-READY under mwr \(review not evaluated\) "
    r"on HEAD ([0-9a-f]{40})! \[stale-base rule\]")
# The same line as the run's whole last line, opening with the checker's
# success marker (U+2705), as `check-pr-fully-clean.py --mwr` prints it last
# (round 5, finding 2).
RX_MWR_LAST_LINE = re.compile(chr(0x2705) + " " + RX_MWR_EVIDENCE.pattern)
RX_NOT_CLEAN = re.compile(r"NOT fully clean", re.IGNORECASE)
RX_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
RX_API_MERGE = re.compile(
    r"repos/([^/\s]+/[^/\s]+)/pulls/(\d+)/merge/?(?:\?.*)?$")
RX_BODY_SHA = re.compile(r"""["']?sha["']?\s*[:=]\s*["']?([0-9a-fA-F]{7,40})""")

DENY_TEXT = (
    "BLOCKED: merging {target} needs {need}.\n\n"
    "{why}\n\n"
    "What to do:\n"
    "1. Get the head SHA: the PR's `head.sha` (40 hex).\n"
    "2. Run `python3 scripts/{inst} {num} -R {repo}` (local or Bash), and see "
    "exit 0 with the line `{repo}#{num} is FULLY CLEAN on HEAD <sha8>! [stale-base rule]`.\n"
    "   The same command works in a cloud session: with CLAUDE_CODE_REMOTE=true "
    "and a GITHUB_TOKEN or GH_TOKEN set, `-R` makes the checker build its own REST "
    "payload (older checkouts: run `scripts/build-pr-payload.py` first and "
    "pass `--from-json`). Run it in THIS session so its line is in this "
    "transcript; a Remote Control run is a fallback, and its output line "
    "must be relayed back into this session.\n"
    "   Pass arguments literally: a run whose command also holds `cat`, "
    "`printf`, `tee`, or an `echo` that could print the line (any argument "
    "holding \"clean\", \"ready\", a backslash or an expansion other than `$?`, or an "
    "`-e` flag), even inside `$(...)` "
    "such as `--annotations-read $(cat ids.txt)`, is not credited. A "
    "trailing `echo \"exit=$?\"` is fine.\n"
    "3. Retry the merge with the full head SHA pinned "
    "(`expectedHeadSha` / `--match-head-commit`). A run made while a check "
    "was pending, or before the last push, names the wrong state and does "
    "not match.\n"
    "Do not infer a pass from an earlier or near-final run, and do not merge "
    "over a checker that looks wrong: fix the checker or its input, then "
    "re-run (psw#354 and gha#1239, 2026-10-26)."
)


def _basename(tok):
    return os.path.basename(tok.strip("'\"").replace("\\", "/"))


def _flag_value(args, names):
    for i, tok in enumerate(args):
        for name in names:
            if tok == name and i + 1 < len(args):
                return args[i + 1]
            if tok.startswith(name + "="):
                return tok[len(name) + 1:]
    return None


def _known_repo(value):
    return None if not value or "{" in value else value


def _is_put(args):
    for i, tok in enumerate(args):
        if tok in ("-X", "--request", "--method") and i + 1 < len(args):
            if args[i + 1].upper() == "PUT":
                return True
        elif tok.startswith(("--method=", "--request=")):
            if tok.split("=", 1)[1].upper() == "PUT":
                return True
        elif tok.startswith("-X") and tok[2:].upper() == "PUT":
            return True
    return False


def _api_target(args):
    """(num, repo) of the `.../pulls/N/merge` URL in *args*, else None."""
    for tok in args:
        m = RX_API_MERGE.search(tok.strip("'\""))
        if m:
            return int(m.group(2)), _known_repo(m.group(1))
    return None


def _field_sha(args):
    """sha from `-f sha=X`, `-F sha=X`, `--field sha=X`, or a JSON body."""
    for i, tok in enumerate(args):
        cand = None
        if tok in ("-f", "-F", "--field", "--raw-field") and i + 1 < len(args):
            cand = args[i + 1]
        elif tok in ("-d", "--data", "--data-raw", "--json") and i + 1 < len(args):
            cand = args[i + 1]
        elif tok.startswith("sha="):
            cand = tok
        if cand:
            m = RX_BODY_SHA.search(cand)
            if m:
                return m.group(1)
    return None


def _gh_pr_number(args):
    skip = False
    for tok in args:
        if skip:
            skip = False
            continue
        if tok in ("-R", "--repo", "-t", "--subject", "-b", "--body", "-F",
                   "--body-file", "--match-head-commit", "-A", "--author-email"):
            skip = True
            continue
        if tok.startswith("-"):
            continue
        if tok.isdigit():
            return int(tok)
        m = re.search(r"/pull/(\d+)(?:[/?#].*)?$", tok)
        if m:
            return int(m.group(1))
    return None


def _argv_merge(rest):
    """(num|None, repo|None, sha|None) when argv *rest* merges a PR, else None.

    num None means the merge cannot be tied to a PR; "graphql" in the third
    slot of the returned tuple's num marks a GraphQL merge.

    Known gaps (ai-config#5959): this reads argv, not gh's own parsing, so a
    decoy `repos/O/R/pulls/N/merge` in a `-f` field can be read in place of
    the endpoint, a repeated `--repo` can name another repository than gh
    merges in, and a sha in a field the server ignores is read as a pin. An
    mwr-only merge no longer takes this route (round 12); ordinary and mwc
    merges still do.
    """
    if not rest:
        return None
    head = _basename(rest[0])
    if head == "gh":
        i = 1
        while i < len(rest) and rest[i].startswith("-"):
            i += 2 if rest[i] in ("-R", "--repo") else 1
        sub = rest[i:i + 2]
        if sub == ["pr", "merge"]:
            args = rest[i + 2:]
            repo = (_flag_value(args, ("-R", "--repo"))
                    or _flag_value(rest[1:i], ("-R", "--repo")))
            return (_gh_pr_number(args), _known_repo(repo),
                    _flag_value(args, ("--match-head-commit",)))
        if rest[i:i + 1] == ["api"]:
            args = rest[i + 1:]
            if "graphql" in args and any("mergePullRequest" in t for t in args):
                return (None, None, None)
            if _is_put(args):
                hit = _api_target(args)
                if hit:
                    return hit[0], hit[1], _field_sha(args)
    elif head == "curl":
        args = rest[1:]
        hit = _api_target(args)
        if hit and _is_put(args):
            return hit[0], hit[1], _field_sha(args)
    return None


def _shell_command(tool_input):
    if not isinstance(tool_input, dict):
        return None
    cmd = (tool_input.get("command") or tool_input.get("CommandLine")
           or tool_input.get("cmd") or tool_input.get("script"))
    return cmd if isinstance(cmd, str) and cmd.strip() else None


def merge_targets(tool, tool_input):
    """[(num|None, repo|None, sha|None)] for every merge this call performs."""
    if tool == MCP_MERGE_TOOL:
        # The server merges `pullNumber` and ignores unknown keys, so
        # conflicting PR-number keys leave num None and the hook denies
        # (no-unauthorized-merge.py's mcp_pull_number holds the same logic).
        present = [tool_input[k] for k in ("pullNumber", "pull_number", "number")
                   if k in tool_input and tool_input[k] is not None]
        if len({str(v).strip() for v in present}) > 1:
            num = None
        else:
            num = present[0] if present else None
        owner, name = tool_input.get("owner"), tool_input.get("repo")
        repo = f"{owner}/{name}" if owner and name else None
        sha = (tool_input.get("expectedHeadSha")
               or tool_input.get("expected_head_sha"))
        try:
            num = int(num)
        except (TypeError, ValueError):
            num = None
        return [(num, repo, sha)]
    command = _shell_command(tool_input)
    if command is None:
        return []
    out = []
    for line in shell_c_expansions(command):
        for argv in simple_commands(line) or []:
            hit = _argv_merge(strip_env(argv)[1])
            if hit:
                out.append(hit)
    return out


def _skip_wrapper_args(rest):
    """Drop the flags and duration `strip_env` leaves before a wrapped command:
    `timeout 300`, `30s`, `0.5`, `-k 10 300`, `--signal=KILL 300`."""
    while rest:
        tok = rest[0]
        if tok in ("-k", "-s", "--kill-after", "--signal") and len(rest) > 1:
            rest = rest[2:]
        elif tok.startswith("-") or RX_DURATION.match(tok):
            rest = rest[1:]
        else:
            break
    return rest


def _echo_could_forge(token):
    """Whether one `echo` argument could print a checker line.

    True for "clean", "ready", an expansion other than `$?` or a backtick
    (RX_FORGE), for any backslash, which an escape-reading echo turns into
    any character, and for an option cluster holding `e` (`-e`, `-ne`).
    """
    return bool(RX_FORGE.search(token) or "\\" in token or RX_ECHO_E.match(token))


def _runs_instrument(command):
    """True when *command* runs the instrument and cannot print its own line."""
    ran = False
    for line in shell_c_expansions(command):
        for argv in simple_commands(line) or []:
            rest = strip_env(argv)[1]
            if not rest:
                continue
            rest = _skip_wrapper_args(rest)
            while rest and _basename(rest[0]) in WRAPPERS:
                rest = _skip_wrapper_args(rest[1:])
            if not rest:
                continue
            head = _basename(rest[0])
            if head in PRINTERS:
                # `; echo "exit=$?"` is the usual way to read an exit status
                # and cannot print the evidence line: allow an `echo` whose
                # arguments hold no "clean" and no expansion but `$?`.
                # A backslash or an `-e` flag can spell the line in escapes
                # (`echo -e "MERGE-RE\x41DY"`, and dash's echo reads escapes
                # with no flag at all), so either one counts as a forgery.
                if head == "echo" and not any(_echo_could_forge(t)
                                              for t in rest[1:]):
                    continue
                return False
            if head == INSTRUMENT:
                ran = True
            elif head in RUNNERS:
                for tok in rest[1:]:
                    if tok in NOT_A_FILE or tok[:2] in ("-c", "-m"):
                        break
                    if tok.startswith("-") or tok in ("run", "exec"):
                        continue
                    if _basename(tok) == INSTRUMENT:
                        ran = True
                    break
    return ran


def _blocks(rec):
    if isinstance(rec.get("_agy_blocks"), list):
        return rec["_agy_blocks"]
    content = (rec.get("message") or {}).get("content") or rec.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


# The checker's flags that make it score a payload instead of fetching live
# state (scripts/check-pr-fully-clean.py, parse_args). argparse accepts any
# unambiguous prefix ("--from", "--f") and "--flag=VALUE", so every option
# token that is a prefix of one of these is refused (round 4, finding 2).
MWR_PAYLOAD_FLAGS = ("--from-json",)


def _plugin_root_checker():
    """The real path of `$CLAUDE_PLUGIN_ROOT/scripts/<checker>`, or None when unset."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return None
    return os.path.realpath(os.path.join(root, "scripts", INSTRUMENT))


def _payload_flag(cmd):
    """Whether `cmd` passes the checker a flag that makes it score a payload."""
    for token in cmd.split():
        name = token.split("=", 1)[0]
        if len(name) > 2 and name.startswith("--") and any(
                flag.startswith(name) for flag in MWR_PAYLOAD_FLAGS):
            return True
    return False


def _root_is_checkout(real):
    """Whether the root above checker `real` (`<root>/scripts/<checker>`) is a git checkout.

    Read from the file system (a `.git` entry at the root), so a git command
    that fails cannot pass a checkout off as a plain copy. A plugin cache
    nested in some other repository (a dotfiles home) is still a plain copy.
    """
    return os.path.lexists(os.path.join(os.path.dirname(os.path.dirname(real)), ".git"))


def trusted_mwr_checker(cmd, cwd):
    """Whether Bash command `cmd`, run in `cwd`, is the checker run alone from
    the plugin root's own copy, on live state (round 5, finding 1).

    The command must match RX_INSTRUMENT_ALONE and pass no payload flag
    (MWR_PAYLOAD_FLAGS), and its script must resolve to
    `$CLAUDE_PLUGIN_ROOT/scripts/check-pr-fully-clean.py`. The checker
    imports `scripts/lib/*.py` and loads `scripts/build-pr-payload.py` from
    its own directory, so hashing the checker file alone vouches for nothing
    a checkout holds: no checkout's copy is ever trusted, and a plugin root
    that is itself a git checkout is refused too. A relative script needs
    the record's `cwd`. Anything else, an unset CLAUDE_PLUGIN_ROOT, or any
    error is untrusted.

    Residual: an agent with shell access can still edit the plugin cache, or
    put a fake `gh` on PATH. That is tracked in ai-config#5959.
    """
    try:
        match = RX_INSTRUMENT_ALONE.match(cmd or "")
        if not match or _payload_flag(cmd):
            return False
        trusted = _plugin_root_checker()
        if trusted is None or not os.path.isfile(trusted) or _root_is_checkout(trusted):
            return False
        script = match.group("script")
        if not os.path.isabs(script):
            if not isinstance(cwd, str) or not os.path.isdir(cwd):
                return False
            script = os.path.join(cwd, script)
        return os.path.realpath(script) == trusted
    except Exception as exc:
        print(f"block-merge-without-clean-checker: checker trust check failed ({exc}); "
              "not credited", file=sys.stderr)
        return False


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def _is_relay_tool(name):
    return name in RELAY_TOOLS or (name or "").startswith(RELAY_PREFIXES)


def mwr_command_target(cmd):
    """(repo_lower, num) that checker command `cmd` names with `-R` and its PR number, or None.

    Fails toward None: the repository must come from exactly one `-R OWNER/NAME`
    pair, with no `--repo` spelling (argparse accepts `--r`, `--re`, `--rep`)
    and no `-RVALUE` form beside it. Every option but `--mwr` is read as
    taking a value, so a misread flag can only swallow the number, never
    supply one. Exactly one positional, all digits, is the number.
    """
    match = RX_INSTRUMENT_ALONE.match(cmd or "")
    if not match:
        return None
    tokens = match.group("args").split()
    repo, positional = None, []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        name = tok.split("=", 1)[0]
        if tok == "-R":
            if repo is not None or i + 1 >= len(tokens):
                return None
            repo = tokens[i + 1]
            i += 2
            continue
        if tok.startswith("-R") or (len(name) > 2 and "--repo".startswith(name)):
            return None
        if tok == "--mwr" or (tok.startswith("-") and "=" in tok):
            i += 1
            continue
        if tok.startswith("-"):
            i += 2
            continue
        positional.append(tok)
        i += 1
    if not repo or len(positional) != 1 or not positional[0].isdigit():
        return None
    return repo.lower(), int(positional[0])


def _mwr_last_line(text, cmd):
    """{(repo_lower, num, sha)} from the run's last non-empty line, or an empty set.

    The line must be the checker's whole MERGE-READY line, success marker
    first, and name the `-R` repository and PR number of `cmd` itself
    (round 5, finding 2). Earlier lines are never read, so text the agent
    controls that the checker echoes (a review thread's path in a NOTE)
    cannot carry a line for another PR.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    target = mwr_command_target(cmd)
    if not lines or target is None:
        return set()
    m = RX_MWR_LAST_LINE.fullmatch(lines[-1])
    if not m or (m.group(1).lower(), int(m.group(2))) != target:
        return set()
    return {(target[0], target[1], m.group(3).lower())}


def evidence(path, pattern=RX_EVIDENCE, alone=False):
    """{(repo_lower, num, sha)} of `pattern` lines (FULLY CLEAN by default) from accepted sources.

    With `alone` (the MERGE-READY line), only a Bash result counts, and only
    when its command is the checker run alone from the plugin root's copy
    (`trusted_mwr_checker`, read with the record's own `cwd`); only its last
    line is read (`_mwr_last_line`). A relay tool result and user-role text
    never supply that line (round 3, finding 3).
    """
    found = set()
    bash_ids, relay_ids = {}, set()

    def take(text, veto):
        if veto and RX_NOT_CLEAN.search(text):
            return
        # The FULLY CLEAN line is still read anywhere in the output, so a
        # forged line in a NOTE (a review thread's path) can name another
        # PR. That mwc-side gap is tracked in ai-config#5959.
        for repo, num, sha in pattern.findall(text):
            found.add((repo.lower(), int(num), sha.lower()))

    for rec in _records(path):
        if rec.get("isSidechain"):
            continue
        role = rec.get("type") or (rec.get("message") or {}).get("role")
        for b in _blocks(rec):
            kind = b.get("type")
            if kind == "tool_use":
                name = b.get("name")
                if name in SHELL_TOOLS:
                    cmd = _shell_command(b.get("input") or {})
                    try:
                        # The FULLY CLEAN line still trusts any script named
                        # check-pr-fully-clean.py; that mwc-side gap is
                        # ai-config#5959. The MERGE-READY line does not.
                        if cmd and _runs_instrument(cmd) and (
                                not alone or trusted_mwr_checker(cmd, rec.get("cwd"))):
                            bash_ids[b.get("id")] = cmd
                    except Exception:
                        pass
                elif _is_relay_tool(name) and not alone:
                    relay_ids.add(b.get("id"))
            elif kind == "tool_result":
                tid = b.get("tool_use_id")
                # `take()` only adds positive evidence to `found`; skipping
                # `is_error` tool results ensures a failed or nonzero-exit
                # command (e.g., Antigravity `status="ERROR"` or nonzero exit
                # header) is never credited even if its output quotes a clean
                # line.
                if tid in bash_ids and not b.get("is_error"):
                    text = _result_text(b)
                    if not alone:
                        take(text, veto=True)
                    elif not RX_NOT_CLEAN.search(text):
                        found |= _mwr_last_line(text, bash_ids[tid])
                elif tid in relay_ids:
                    take(_result_text(b), veto=False)
            elif kind == "text" and role in ("user", "USER_INPUT") and not alone:
                take(b.get("text") or "", veto=False)
    return found


RX_OVERRIDE = re.compile(
    r"\b(?:merge|ship)\s+(?:it|this|that|them)?\s*anyway\b"
    r"|\boverride\s+(?:the\s+)?(?:merge\s+)?(?:hook|gate|checker|check)\b",
    re.IGNORECASE)
# A negation anywhere earlier in the same clause voids the phrase ("I don't
# think we should merge it anyway"); fail closed on any such word.
RX_NEGATED = re.compile(
    r"\b(?:don'?t|do\s+not|never|not|won'?t|shouldn'?t|wouldn'?t|can'?t|"
    r"cannot|couldn'?t|isn'?t|aren'?t|without)\b",
    re.IGNORECASE)
RX_CLAUSE_START = re.compile(r"[.!?;\n]")
RX_STRIP = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<note>.*?</note>"
    r"|<cited\b[^>]*author=\"(?!user\")[^\"]*\"[^>]*>.*?</cited>"
    # A wake message that declares a trust other than the principal's (a peer
    # session's, a bot's), or a sender other than the human, is not the user's
    # words. One that declares neither is kept, as before this rule. The
    # attribute may be quoted either way or not at all, with spaces round its
    # `=`; `data-trust` is a different attribute and is not read.
    # ANY such declaration that is not exactly the allowed value drops the
    # message, so a second attribute or a look-alike inside another
    # attribute's value cannot rescue it.
    r"|<message\b(?=[^>]*(?<![\w-])trust\s*="
    r"(?!\s*[\"']?principal[\"']?(?=[\s/>])))[^>]*>.*?</message>"
    r"|<message\b(?=[^>]*(?<![\w-])from\s*="
    r"(?!\s*[\"']?human[\"']?(?=[\s/>])))[^>]*>.*?</message>",
    re.IGNORECASE | re.DOTALL)
# A decision-card tap arrives as a body that reads, in full, `Chose "<label>"
# on the decision card asking "<question>"`. The agent wrote the label and the
# question, so neither is the user's TYPED words: a body that is exactly a tap
# is dropped whole. A typed sentence that merely holds the word "chose" stays.
RX_TAP_BODY = re.compile(
    r'\A\s*Chose ".*?" on the decision card asking ".*"\s*\Z', re.DOTALL)
RX_ELEMENT = re.compile(
    r"(<(message|cited)\b[^>]*>)(.*?)(</\2>)", re.IGNORECASE | re.DOTALL)


def _is_tap(body):
    return bool(RX_TAP_BODY.match(html.unescape(body)))


def _typed_text(text):
    """*text* with everything the user did not type removed."""
    text = RX_STRIP.sub(" ", text)
    if _is_tap(text):
        return ""
    return RX_ELEMENT.sub(
        lambda m: " " if _is_tap(m.group(3)) else m.group(0), text)


# --- a waiver tapped on a decision card (Ezra, 2026-11-19, ai-config#5892) ---
# The tapped label is the waiver and nothing else: "Waive the check", with at
# most ", merge it" (or both, them, all) after it. A condition
# ("... only after CI is green"), a hold ("Hold; waive the check later") or a
# negation ("Do not waive the check") is not that label.
RX_WAIVE_LABEL = re.compile(
    r"\A\s*waive\s+the\s+check(?:\s*,\s*merge\s+(?:it|both|them|all))?[\s.]*\Z",
    re.IGNORECASE)
# Another option must decline. Its label is one of a fixed few and nothing
# else ("Hold it", "Hold", "Hold both", "No", "Not now"), and its consequence
# names no way of going ahead, so "Skip the checker, land it now" and a
# "Hold it" whose consequence merges are both refused.
RX_DECLINE_LABEL = re.compile(
    r"\A\s*(?:hold(?:\s+(?:it|both))?|no|not\s+now)[\s.]*\Z",
    re.IGNORECASE)
RX_PROCEEDS = re.compile(
    r"\b(?:merg|waiv|ship|overrid|land|push|squash|rebas|proceed|go\s+ahead)",
    re.IGNORECASE)
# The tapped option's consequence is "I merge <ref>", with further refs joined
# by a comma or "and", and nothing else. A ref is `owner/repo#N` or a
# github.com pull URL. A fixed form leaves no room for a condition ("... once
# CI is green") or for a pull request named only to be left alone.
_REF = (r"(?:(?:https?://)?github\.com/[\w.-]+/[\w.-]+/pull/\d+"
        r"|[\w.-]+/[\w.-]+#\d+)")
RX_WAIVE_CONSEQUENCE = re.compile(
    r"\A\s*I\s+merge\s+" + _REF
    + r"(?:(?:\s*,\s*and\s+|\s*,\s*|\s+and\s+)" + _REF + r")*\s*\.?\s*\Z",
    re.IGNORECASE)
RX_CARD_PR = re.compile(
    r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)\b"
    r"|(?<![\w/.-])([\w.-]+/[\w.-]+)#(\d+)\b",
    re.IGNORECASE)


def _declines(option):
    """True when a card *option* is a plain way to say no."""
    label = str(option.get("label") or "")
    consequence = str(option.get("consequence") or "")
    return bool(RX_DECLINE_LABEL.match(label)
                and not RX_PROCEEDS.search(consequence))


def tapped_waivers(path):
    """{(repo, number)} the user waived the checker for by tapping a card.

    A tap counts only when ALL of these hold; anything else yields nothing:

    * `scripts/lib/card_answer.py` reads it as a verified tap (the top-level
      `decision-chosen` wake with the platform's note that the tap came from
      the member's own client). A relayed tap carries no card and is refused.
    * This transcript holds the `request_decision` call that posted the card,
      and the tapped label is that card's option at the tapped index.
    * The tapped label is the waiver and nothing else (`RX_WAIVE_LABEL`).
    * Another option on the card declines: its label is exactly "Hold it"
      (or "Hold", "Hold both", "No", "Not now"; `RX_DECLINE_LABEL`) and its
      consequence names no way of going ahead (`RX_PROCEEDS`), so the user
      had a way to say no. The agent writes every label, and a card whose
      options all merge proves nothing.
    * The tapped option's consequence is "I merge <ref>", with further refs
      joined by a comma or "and", and nothing else (`RX_WAIVE_CONSEQUENCE`).
      The waiver covers the pull requests named there and no other; the
      card's question, where one may be named only as background, is not read.

    LIMIT: the hook cannot judge prose. It checks that the card had this
    fixed shape; the user reading the card is what makes the tap a decision.
    """
    if card_answer is None:
        return set()
    pending, cards, waived = {}, {}, set()
    for rec in _records(path):
        if rec.get("isSidechain"):
            continue
        card_answer.track_cards(rec, pending, cards)
        role = rec.get("type") or (rec.get("message") or {}).get("role")
        if role not in ("user", "USER_INPUT"):
            continue
        msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
        prompt = card_answer.prompt_text(msg.get("content"))
        for option, _question, did, idx in card_answer.answers_in_prompt(prompt):
            card = cards.get(did) if did else None
            opts = card.get("options") if isinstance(card, dict) else None
            if not isinstance(opts, list) or idx is None or idx >= len(opts):
                continue
            if not all(isinstance(o, dict) for o in opts):
                continue
            chosen = opts[idx]
            if str(chosen.get("label") or "").strip() != option:
                continue
            if not RX_WAIVE_LABEL.match(option):
                continue
            others = [o for i, o in enumerate(opts) if i != idx]
            if not any(_declines(o) for o in others):
                continue
            named = str(chosen.get("consequence") or "")
            if not RX_WAIVE_CONSEQUENCE.match(named):
                continue
            for m in RX_CARD_PR.finditer(named):
                waived.add(((m.group(1) or m.group(3)).lower(),
                            int(m.group(2) or m.group(4))))
    return waived


def typed_override(path):
    """True when the user typed an explicit "merge it anyway" override.

    Only a user-role TEXT block counts: not a tool result, not the assistant's
    words, not a hook or system reminder, and not the coordinator's `<note>` or
    a `<cited author="coordinator">` entry. A relayed `<cited author="user">`
    entry counts, because the server copies the user's words into it. A negated
    phrase ("don't merge it anyway") does not. The override replaces only the
    checker-evidence condition; the PR, repo and 40-character sha pin are still
    required, so GitHub itself refuses a merge if the head moved.
    """
    for rec in _records(path):
        if rec.get("isSidechain"):
            continue
        role = rec.get("type") or (rec.get("message") or {}).get("role")
        if role not in ("user", "USER_INPUT"):
            continue
        for b in _blocks(rec):
            if b.get("type") != "text":
                continue
            text = _typed_text(b.get("text") or "")
            for m in RX_OVERRIDE.finditer(text):
                before = text[:m.start()]
                starts = [s.end() for s in RX_CLAUSE_START.finditer(before)]
                clause = before[starts[-1]:] if starts else before
                if not RX_NEGATED.search(clause):
                    return True
    return False


def mwr_granted(payload, repo, num):
    """Whether the user's typed `mwr`/`mwrs` covers `repo`#`num` (ai-config#3946).

    Reads `transcript_mwr_grant` from no-unauthorized-merge.py, the one copy
    of the rule. Fails closed: a sibling that cannot load, or any error, is
    no grant, so a MERGE-READY line then satisfies nothing.
    """
    try:
        if load_sibling is None:
            return False
        module = load_sibling(__file__, "no-unauthorized-merge.py", "_sib_nua_mwr")
        if module is None or not hasattr(module, "transcript_mwr_grant"):
            return False
        return bool(module.transcript_mwr_grant(payload, repo, num))
    except Exception as exc:
        print(f"block-merge-without-clean-checker: mwr grant read failed ({exc}); "
              "no mwr grant", file=sys.stderr)
        return False


def _nua_sibling():
    """no-unauthorized-merge.py, the one copy of every merge-grant rule, or
    None when it cannot load."""
    if load_sibling is None:
        return None
    return load_sibling(__file__, "no-unauthorized-merge.py", "_sib_nua_mwr")


def mwc_granted(payload):
    """Whether the user TYPED an `mwc` grant this session, read by
    `transcript_merge_grant` in no-unauthorized-merge.py (round 10).

    Never the `.mwc` marker that `check_mwc_active` also accepts: the agent
    can write that marker itself (`ai-session.sh enable-mwc`), so it must not
    lift an mwr-only merge onto the FULLY CLEAN path (the marker itself is
    ai-config#5959). Fails toward False: an unreadable grant leaves an
    mwr-granted merge on the mwr path.
    """
    try:
        module = _nua_sibling()
        if module is None or not hasattr(module, "transcript_merge_grant"):
            return False
        return bool(module.transcript_merge_grant(payload))
    except Exception as exc:
        print(f"block-merge-without-clean-checker: mwc grant read failed ({exc}); "
              "an mwr merge stays on the mwr path", file=sys.stderr)
        return False


def other_merge_authority(payload, repo, num, sha=None):
    """Whether user-given authority other than `mwr` covers `repo`#`num`
    (round 10), so the merge keeps the ordinary FULLY CLEAN path.

    The rules no-unauthorized-merge.py allows a merge on, each read from
    there: the typed `mwc` (`mwc_granted`), a typed "merge ... PR N" naming
    this PR (`transcript_named_grant`), the standing per-repository grant
    (`STANDING_MERGE_GRANT_REPOS`, the test `standing_grant_target` ends
    with) and the standing infra-PR grant (`infra_grant_applies`, the core of
    `standing_infra_grant`, which reads the PR's files from GitHub and needs
    the pinned `sha`). As there, neither the named nor the infra grant covers
    an auto-merge. `ALLOW_MERGE=1` never counts, since the agent can type it,
    and neither does the `.mwc` marker. Fails toward False, so a failed read,
    the infra grant's network read included, leaves the merge mwr-only.
    """
    try:
        if mwc_granted(payload):
            return True
        module = _nua_sibling()
        if module is None or not repo or num is None:
            return False
        target = repo.strip().lower()
        if target in getattr(module, "STANDING_MERGE_GRANT_REPOS", ()):
            return True
        if mwr_auto_merge(payload):
            return False
        if (hasattr(module, "transcript_named_grant")
                and module.transcript_named_grant(payload, target, num)):
            return True
        return bool(sha and hasattr(module, "infra_grant_applies")
                    and module.infra_grant_applies(target, num, sha))
    except Exception as exc:
        print(f"block-merge-without-clean-checker: merge-grant read failed ({exc}); "
              "an mwr merge stays on the mwr path", file=sys.stderr)
        return False


def mwr_only_grant(payload, repo, num, sha=None):
    """Whether `repo`#`num` is merged under an `mwr` grant and no other
    user-given authority (round 9; `other_merge_authority`, round 10). Then a
    FULLY CLEAN line does not count: the merge rests on the MERGE-READY line
    (`mwr_clears`) and the live re-checks (`mwr_live_check`). Without `sha`
    the infra-PR grant cannot be read, so it does not count.
    """
    return (mwr_granted(payload, repo, num)
            and not other_merge_authority(payload, repo, num, sha))


def mwr_route_problem(tool, tool_input):
    """"" when an mwr-only merge uses the one route mwr allows, else why not
    (round 12).

    The route is the MCP merge tool with a strict input, judged by
    `mwr_mcp_input_problem` in no-unauthorized-merge.py, the one copy of the
    rule; its text `MWR_MCP_ONLY_TEXT` says how to merge instead. Any shell
    route (gh, gh api, curl) is refused. Fails closed: a sibling that cannot
    load is a problem.
    """
    try:
        module = _nua_sibling()
        if module is None or not hasattr(module, "mwr_mcp_input_problem"):
            return "the strict-input rule in no-unauthorized-merge.py could not load."
        text = getattr(module, "MWR_MCP_ONLY_TEXT", "")
        if tool != MCP_MERGE_TOOL:
            return f"a shell merge is refused. {text}"
        problem = module.mwr_mcp_input_problem(tool_input)
        return f"{problem} {text}" if problem else ""
    except Exception as exc:
        return f"the strict-input rule could not run ({exc})."


# An auto-merge: `gh pr merge --auto`, the MCP auto-merge tools, a GraphQL
# `enablePullRequestAutoMerge`, or a REST `auto_merge` / `ccr/auto_merge`
# route. It merges whatever the PR holds when checks pass, so the mwr grant
# never skips review for it (round 3, finding 8).
RX_AUTO_MERGE = re.compile(r"(?:^|[\s=])--auto\b|auto[_-]?merge", re.IGNORECASE)
# Free text the merge tool takes, never a switch: a commit title such as
# "fix auto-merge bug" must not read as an auto-merge.
MCP_FREE_TEXT_KEYS = ("commit_title", "commit_message")
# `gh pr merge` flags whose value is free text (title, body, body file).
GH_MERGE_FREE_TEXT_FLAGS = ("-t", "--subject", "-b", "--body", "-F", "--body-file")
# Shells whose quoting `shellcmd` models. PowerShell's differs, so its
# command is read raw.
POSIX_SHELL_TOOLS = frozenset({"Bash", "bash"})
# Text the argv split cannot see into, so a command holding any of it is
# read raw: a heredoc body (blanked by the split), command and process
# substitution.
RX_OPAQUE_SHELL = re.compile(r"<<|\$\(|`|<\(|>\(")
# A free-text value is set aside only when it holds nothing the shell could
# expand or re-split differently from the parse: no expansion, escape,
# brace or glob character, no newline, and no leading dash (a value that
# looks like a flag is ambiguous).
RX_UNSAFE_VALUE = re.compile(r"[$`\\{}*?\[\]\n]|^-")


def _gh_merge_kept_tokens(argv):
    """The tokens of `argv` left once a `gh pr merge`'s free-text values go.

    Any other command keeps every token. A value is dropped only when it is
    safe (`RX_UNSAFE_VALUE`), so an ambiguous one stays and is tested.
    """
    rest = strip_env(argv)[1]
    if not rest or _basename(rest[0]) != "gh":
        return list(argv)
    i = 1
    while i < len(rest) and rest[i].startswith("-"):
        i += 2 if rest[i] in ("-R", "--repo") else 1
    if rest[i:i + 2] != ["pr", "merge"]:
        return list(argv)
    kept = list(argv[:len(argv) - len(rest)]) + rest[:i + 2]
    args = rest[i + 2:]
    j = 0
    while j < len(args):
        tok = args[j]
        name, eq, value = tok.partition("=")
        if eq and name in GH_MERGE_FREE_TEXT_FLAGS and name.startswith("--"):
            if RX_UNSAFE_VALUE.search(value):
                kept.append(tok)
            j += 1
            continue
        if tok in GH_MERGE_FREE_TEXT_FLAGS and j + 1 < len(args):
            kept.append(tok)
            if RX_UNSAFE_VALUE.search(args[j + 1]):
                kept.append(args[j + 1])
            j += 2
            continue
        kept.append(tok)
        j += 1
    return kept


def _shell_auto_merge(command):
    """Whether a POSIX shell `command` could arm an auto-merge, judged from
    its parsed argv with `gh pr merge` free-text values set aside. Anything
    the split cannot see into, or cannot parse, is read raw."""
    if not RX_AUTO_MERGE.search(command):
        return False
    if RX_OPAQUE_SHELL.search(command):
        return True
    argvs = simple_commands(command)
    if not argvs:
        return True
    return any(RX_AUTO_MERGE.search(tok)
               for argv in argvs for tok in _gh_merge_kept_tokens(argv))


def mwr_auto_merge(payload):
    """Whether this tool call is, or could be, an auto-merge. Fails toward True.

    The tool name decides first (the MCP auto-merge tools). Then the input:
    for the MCP route, every key but the free-text `commit_title` and
    `commit_message`; for a POSIX shell, the command's parsed argv with the
    free-text values of `gh pr merge` set aside (`_shell_auto_merge`), and
    every other input key but the harness's `description`. Any other tool's
    input is read whole.
    """
    try:
        tool = str((payload or {}).get("tool_name") or "")
        if RX_AUTO_MERGE.search(tool):
            return True
        tool_input = (payload or {}).get("tool_input")
        if not isinstance(tool_input, dict):
            return False
        if tool.startswith("mcp__"):
            rest = {k: v for k, v in tool_input.items() if k not in MCP_FREE_TEXT_KEYS}
            return bool(RX_AUTO_MERGE.search(json.dumps(rest)))
        if tool in POSIX_SHELL_TOOLS:
            command = tool_input.get("command")
            if not isinstance(command, str):
                return bool(RX_AUTO_MERGE.search(json.dumps(tool_input)))
            rest = {k: v for k, v in tool_input.items() if k not in ("command", "description")}
            return bool(RX_AUTO_MERGE.search(json.dumps(rest)) or _shell_auto_merge(command))
        return bool(RX_AUTO_MERGE.search(json.dumps(tool_input)))
    except Exception:
        return True


def mwr_clears(payload, repo, num, sha):
    """True only when an `mwr` grant covers `repo`#`num` AND an accepted
    MERGE-READY line names that repo, number and exactly `sha` (40 hex).

    The line's sources, the NOT-fully-clean veto and the sha tie are the
    FULLY CLEAN line's (`evidence`). Fails closed on any error.
    """
    try:
        path = (payload or {}).get("transcript_path") or ""
        if not repo or num is None or not sha or not path or not os.path.isfile(path):
            return False
        if mwr_auto_merge(payload):
            return False
        if not mwr_granted(payload, repo, num):
            return False
        sha = sha.lower()
        # Equality with the pinned sha, never a prefix match (round 6).
        return any(r == repo.lower() and n == num and sha == s
                   for r, n, s in evidence(path, RX_MWR_EVIDENCE, alone=True))
    except Exception as exc:
        print(f"block-merge-without-clean-checker: MERGE-READY read failed ({exc}); "
              "not credited", file=sys.stderr)
        return False


def fully_clean_on(found, repo, num, sha):
    """Whether `found` (from `evidence`) holds a FULLY CLEAN line for
    `repo`#`num` whose sha is a prefix of the pinned `sha`."""
    sha = (sha or "").lower()
    return bool(repo and sha) and any(
        r == repo.lower() and n == num and sha.startswith(s) for r, n, s in found)


def mwr_live_check(payload, repo, num, sha):
    """"" when the merge-time mwr re-checks pass on live data, else the reason.

    Runs `fetch_mwr_live` and `mwr_live_problem` from the sibling
    `enforce-mwc-review-gate.py`, the one copy of both (round 8). Fails
    closed: a sibling that cannot load or any error is a reason.
    """
    try:
        if load_sibling is None:
            return "scripts/lib/sibling.py could not be loaded."
        gate = load_sibling(__file__, "enforce-mwc-review-gate.py",
                            "_sib_enforce_mwr_live", required=True)
        pr_data = {"url": f"https://github.com/{repo}/pull/{num}", "headRefOid": sha}
        pr_data["mwrLive"] = gate.fetch_mwr_live(
            pr_data, (payload or {}).get("cwd") or os.getcwd())
        return gate.mwr_live_problem(pr_data)
    except Exception as exc:
        return f"the live re-checks could not run ({exc})."


def deny(reason):
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }


def _refuse(target, need, why, num, repo):
    return deny(DENY_TEXT.format(
        target=target, need=need, why=why, inst=INSTRUMENT,
        num=num if num is not None else "<N>", repo=repo or "<owner>/<repo>"))


def main() -> int:
    if simple_commands is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    if tool not in SHELL_TOOLS and tool != MCP_MERGE_TOOL:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload.get("toolInput")
    if not isinstance(tool_input, dict):
        return 0
    try:
        targets = merge_targets(tool, tool_input)
    except Exception:
        return 0
    if not targets:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        print("block-merge-without-clean-checker: no transcript; not gating",
              file=sys.stderr)
        return 0
    try:
        found = evidence(path)
        overridden = typed_override(path)
        waived = tapped_waivers(path)
    except Exception:
        return 0

    for num, repo, sha in targets:
        target = (f"{repo}#{num}" if repo and num is not None
                  else f"PR #{num}" if num is not None
                  else "a PR that cannot be identified")
        if num is None or not repo:
            print(json.dumps(_refuse(
                target, "an explicit PR number and repository",
                "A merge that names no PR or no repository cannot be tied to "
                "a checker run. A GraphQL `mergePullRequest` call cannot be "
                "tied at all: use `gh pr merge N -R o/r --match-head-commit "
                "<sha>` or the MCP merge tool.", num, repo)))
            return 0
        # Under an mwr grant with no other authority, only the MCP merge
        # tool with a strict input may merge (round 12), checked before
        # anything else. A Bash route is read here differently from how gh,
        # curl or the server read it, so it is refused outright.
        pin = sha.lower() if isinstance(sha, str) and RX_SHA40.match(sha) else None
        mwr_only = mwr_only_grant(payload, repo, num, pin)
        if mwr_only:
            route_problem = mwr_route_problem(tool, tool_input)
            if route_problem:
                print(json.dumps(deny(f"BLOCKED: merging {target} under `mwr`: {route_problem}")))
                return 0
        if not sha or not RX_SHA40.match(sha):
            print(json.dumps(_refuse(
                target, "the full 40-character head SHA pinned",
                "Without `expectedHeadSha` (MCP) or `--match-head-commit` "
                "(`gh pr merge`) the merge cannot be tied to the head the "
                "checker measured, and GitHub cannot refuse it if the head "
                "moved after the run.", num, repo)))
            return 0
        sha = sha.lower()
        # Under an mwr grant with no mwc grant, a FULLY CLEAN line does not
        # count: only the MERGE-READY line and the live re-checks (round 9).
        # `mwr_only` was read above, with this same sha.
        ok = not mwr_only and fully_clean_on(found, repo, num, sha)
        mwr_problem = ""
        route_problem = ""
        if not ok and mwr_clears(payload, repo, num, sha):
            # Credited by the MERGE-READY line alone: the merge takes the
            # strict MCP route whatever other grant covers it (round 13), and
            # the live re-checks run here whatever the review gate decided
            # (round 8). An mwr-only merge was route-checked above.
            route_problem = "" if mwr_only else mwr_route_problem(tool, tool_input)
            if not route_problem:
                mwr_problem = mwr_live_check(payload, repo, num, sha)
            if not route_problem and not mwr_problem:
                print(f"block-merge-without-clean-checker: {target} merged under the "
                      "user's typed mwr grant on a MERGE-READY line; review not "
                      "evaluated", file=sys.stderr)
                ok = True
        if not ok and overridden:
            print(f"block-merge-without-clean-checker: {target} merged on the "
                  "user's typed override; no checker pass was required",
                  file=sys.stderr)
            ok = True
        if not ok and (repo.lower(), int(num)) in waived:
            print(f"block-merge-without-clean-checker: {target} merged on the "
                  "user's tapped waiver; no checker pass was required",
                  file=sys.stderr)
            ok = True
        if not ok and route_problem:
            print(json.dumps(deny(
                f"BLOCKED: merging {target} under `mwr`: {route_problem} "
                "A merge credited by the MERGE-READY line takes this route "
                "whatever other grant covers it; a merge credited by a FULLY "
                "CLEAN line keeps every route.")))
            return 0
        if not ok and mwr_problem:
            print(json.dumps(deny(
                f"{target}: the mwr merge-time check failed: {mwr_problem} "
                "Under mwr, the live PR state is read again at merge time.")))
            return 0
        if not ok and mwr_only:
            print(json.dumps(_refuse(
                target, f"a `{INSTRUMENT} --mwr` MERGE-READY line on head {sha}",
                "This merge is granted by the user's typed `mwr` or `mwrs`, and by no "
                "typed `mwc` and no named, standing or infra-PR grant, so a FULLY CLEAN "
                "line does not count. The merge needs the "
                f"`{repo}#{num} is MERGE-READY under mwr (review not evaluated) "
                f"on HEAD {sha}! [stale-base rule]` line, as the last line of a run of "
                f"`python3 {_plugin_root_checker() or '$CLAUDE_PLUGIN_ROOT/scripts/' + INSTRUMENT} "
                f"{num} -R {repo} --mwr`, alone in its command, and the live re-checks. "
                "If the PR needs the FULLY CLEAN path, ask the user to type `mwc`; "
                "do not create an mwc grant yourself.",
                num, repo)))
            return 0
        if not ok:
            print(json.dumps(_refuse(
                target, f"a `{INSTRUMENT}` pass on head {sha[:8]}",
                f"No `{repo}#{num} is FULLY CLEAN on HEAD {sha[:8]}! [stale-base rule]` line is "
                "in this session's checker results or relayed messages. "
                "Under the user's typed `mwr` or `mwrs` grant, a `--mwr` run's "
                f"`{repo}#{num} is MERGE-READY under mwr (review not evaluated) "
                f"on HEAD {sha}! [stale-base rule]` line (the full head sha) serves instead, "
                "as the last line of a run of the plugin root's own copy, "
                f"`python3 {_plugin_root_checker() or '$CLAUDE_PLUGIN_ROOT/scripts/' + INSTRUMENT} "
                f"{num} -R {repo} --mwr`, alone in its command; a checkout's "
                "copy is never credited.",
                num, repo)))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
