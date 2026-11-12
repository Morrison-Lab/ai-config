#!/usr/bin/env python3
"""PreToolUse deny (named `warn-` for its references): a merge with no cross-harness review since the last push.

## The failure this exists for

`shared/workflow/adversarial-self-review.md` ("Cross-model and cross-harness
reviews are required for merging") requires a merge verdict from a reviewer
whose model AND harness both differ from the authoring session's. An
`Agent`-dispatched subagent and the CI `claude-review` workflow are both
Claude, so neither qualifies.

Nothing enforced it. `no-unauthorized-merge.py` checks authorization and
`warn-merge-without-fully-clean.py` checks the fully-clean instrument; both
pass a merge whose every reviewer was Claude. ai-config#3099 records two such
merges on 2026-09-02 (PDT), and the same miss recurred on 2026-10-08, when nine
ai-config PRs were merged from a remote container with Claude reviewers only
before the gap was noticed.

## The condition

    the call merges a PR or arms auto-merge
        (`gh pr merge`, `gh api -X PUT .../pulls/N/merge`,
         `mcp__github__merge_pull_request`, `mcp__github__enable_pr_auto_merge`)
    AND NOT  this session's transcript holds, after the last push, a
             non-sidechain Bash call whose result is not an error and in
             which a simple command's command word is one of the CLIs in
             CROSS_HARNESS_CLIS, minus this session's own harness, run as a
             review (REVIEW_SUBCOMMANDS: `codex exec`, `opencode run`;
             REVIEW_FLAGS: `claude -p`, `agy --print`, ...), or a `curl` call
             with a data payload to `https://opencode.ai/zen/go/v1/chat/completions`
             (the cloud-session route when `opencode` qualifies per AGENTS.md policy),
             or a `curl` call with a data payload to `https://api.ollama.com/api/chat`
             (the Ollama Cloud route, ai-config#4849)
    AND NOT  the waiver's probe pass ran after the last push: each CLI in
             `clis` attempted with any result, or shown absent by a lone,
             unredirected `command -v` / `which` that exited 1; `opencode` attempted.

A skill (`dtc`, `dto`, `adv`) is not credited by being loaded: loading one
runs nothing. Its reviewer CLI call, which is a Bash call, is what counts.
On a cloud session where `opencode` CLI is unavailable, a `curl` invocation
targeting `https://opencode.ai/zen/go/v1/chat/completions` counts toward
`opencode` as an explicit policy grant.

Merge recognition reuses `_gh_merge` and push recognition reuses `_events`,
`_push_before_merge` and `MCP_PUSH_TOOLS` from
`warn-merge-without-fully-clean.py`, so the two merge warnings cannot disagree
about what a merge or a push is. The sibling's strict `check && merge` chain
discharge is deliberately NOT reused: passing the fully-clean instrument says
nothing about who reviewed.

## Why it denies

As a warning its note rode on the merge call and was read only with the
merge result (ai-config#4587, ai-config#5290). Both discharges are visible
tool calls, so a deny is decidable and costs at most the waiver's probe pass.

## What it cannot see

* The INVOCATION is decidable; the VERDICT is not. A run that returned
  "needs more work" discharges this hook. It answers "was the gate even
  attempted", which is the question both recorded misses failed;
  `check-pr-fully-clean.py` and `warn-merge-without-fully-clean.py` own
  the verdict.
* A multi-backend harness (`opencode`, `cursor-agent`) qualifies only when
  its configured model also differs. The model is a config file away, not on
  the command line, so the hook takes the harness as the signal.
* The session's own harness is read from `ANTIGRAVITY_AGENT`, the Antigravity
  transcript path (`brain/<id>/.system_generated/logs/transcript.jsonl`), or
  Antigravity record types (`PLANNER_RESPONSE`, `SYSTEM_MESSAGE`), defaulting
  to Claude Code otherwise. In an Antigravity session, both `agy` and `gemini`
  are excluded as same-harness/same-model family while `claude` qualifies.
* A review run in another session or by a human is invisible here.
* `nohup` and `timeout` are looked through, but a reviewer launched from a
  script (`dtc`'s background `nohup bash "$WORK/run.sh" &`) is not: the
  command word is `bash`, and the script's contents are not in the
  transcript. The foreground `codex exec ...` form is credited.
* Only the listed review forms count, so a review written another way is not
  credited: an option with a value before the subcommand (`codex -m o3 exec`)
  or a bare positional prompt (`gemini 'review'`). Each errs toward a false
  deny, which the listed form clears (`codex exec -m o3`, `gemini -p`).
* `gemini` and `cursor-agent` are credited although the gate fragment's
  ladder does not list them as active yet: a successful run of either in
  the transcript is itself the probe that ladder is waiting on.

A false deny from the script case is discharged by running the reviewer in the
foreground, or by the probe pass. There is no escape variable. The hook fails
open on any internal error.
"""
import json
import os
import re
import sys
import urllib.parse

# Reviewer CLIs, one per harness. The session's own harness is removed at run
# time, so `claude` counts only from a non-Claude session.
CROSS_HARNESS_CLIS = frozenset({
    "codex", "opencode", "agy", "gemini", "cursor-agent", "claude",
})
# What makes a reviewer CLI's call a review, listed rather than inferred, so
# housekeeping (`opencode stats`, `codex apply`, `cursor-agent ls`) never
# counts (ai-config#5383): the first word that is not an option, for a CLI
# with subcommands, or a print or prompt flag anywhere before `--`.
REVIEW_SUBCOMMANDS = {
    "codex": frozenset({"exec", "e", "review"}),
    "opencode": frozenset({"run"}),
}
REVIEW_FLAGS = {
    "agy": frozenset({"-p", "--print"}),
    "claude": frozenset({"-p", "--print"}),
    "cursor-agent": frozenset({"-p", "--print"}),
    "gemini": frozenset({"-p", "--prompt"}),
}
# `timeout` options that take a separate argument (`-s KILL`, `-k 5`).
TIMEOUT_ARG_OPTS = frozenset({"-s", "--signal", "-k", "--kill-after"})
# A help or version flag anywhere in the call (`codex exec --help`).
HELP_FLAGS = frozenset({"-h", "--help", "--version"})
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Both spellings of the MCP auto-merge tool are in use: this server exposes
# `enable_pr_auto_merge`, while enforce-mwc-review-gate.py expects
# `enable_pull_request_auto_merge`. Match both, as no-unauthorized-merge.py does.
RX_AUTO_MERGE_TOOL = re.compile(
    r"^mcp__github__enable_?(?:pull_?request_?|pr_)?auto_?merge$", re.I)
# HTTP reviewer routes a `curl` POST can take: (host, path, CLI it stands for).
HTTP_ROUTES = (
    ("opencode.ai", "/zen/go/v1/chat/completions", "opencode"),
    ("api.ollama.com", "/api/chat", None),
)
# Presence probes, and the routes a presence probe alone cannot clear.
PROBE_WORDS = frozenset({"which", "command"})
NEEDS_ATTEMPT = frozenset({"opencode"})
# curl options whose next word is a value, never the request URL: every
# option `curl --help all` (curl 8.5.0) shows taking an argument, plus
# `--haproxy-clientip` (its help line omits the argument), `--ech` (curl 8.8)
# and the bundled `-sd`/`-sF`. `--url` is left out, since its value is the
# target (ai-config#5383).
CURL_VALUE_OPTS = frozenset({
    "--abstract-unix-socket", "--alt-svc", "--aws-sigv4", "--cacert",
    "--capath", "--cert", "--cert-type", "--ciphers", "--config",
    "--connect-timeout", "--connect-to", "--continue-at", "--cookie",
    "--cookie-jar", "--create-file-mode", "--crlfile", "--curves", "--data",
    "--data-ascii", "--data-binary", "--data-raw", "--data-urlencode",
    "--delegation", "--dns-interface", "--dns-ipv4-addr", "--dns-ipv6-addr",
    "--dns-servers", "--doh-url", "--dump-header", "--ech", "--egd-file",
    "--engine", "--haproxy-clientip",
    "--etag-compare", "--etag-save", "--expect100-timeout", "--form",
    "--form-string", "--ftp-account", "--ftp-alternative-to-user",
    "--ftp-method", "--ftp-port", "--ftp-ssl-ccc-mode",
    "--happy-eyeballs-timeout-ms", "--header", "--help", "--hostpubmd5",
    "--hostpubsha256", "--hsts", "--interface", "--ipfs-gateway", "--json",
    "--keepalive-time", "--key", "--key-type", "--krb", "--libcurl",
    "--limit-rate", "--local-port", "--login-options", "--mail-auth",
    "--mail-from", "--mail-rcpt", "--max-filesize", "--max-redirs",
    "--max-time", "--netrc-file", "--noproxy", "--oauth2-bearer",
    "--output", "--output-dir", "--parallel-max", "--pass",
    "--pinnedpubkey", "--preproxy", "--proto", "--proto-default",
    "--proto-redir", "--proxy", "--proxy1.0", "--proxy-cacert", "--proxy-capath",
    "--proxy-cert", "--proxy-cert-type", "--proxy-ciphers",
    "--proxy-crlfile", "--proxy-header", "--proxy-key", "--proxy-key-type",
    "--proxy-pass", "--proxy-pinnedpubkey", "--proxy-service-name",
    "--proxy-tls13-ciphers", "--proxy-tlsauthtype", "--proxy-tlspassword",
    "--proxy-tlsuser", "--proxy-user", "--pubkey", "--quote",
    "--random-file", "--range", "--rate", "--referer", "--request",
    "--request-target", "--resolve", "--retry", "--retry-delay",
    "--retry-max-time", "--sasl-authzid", "--service-name", "--socks4",
    "--socks4a", "--socks5", "--socks5-gssapi-service", "--socks5-hostname",
    "--speed-limit", "--speed-time", "--stderr", "--telnet-option",
    "--tftp-blksize", "--time-cond", "--tls-max", "--tls13-ciphers",
    "--tlsauthtype", "--tlspassword", "--tlsuser", "--trace",
    "--trace-ascii", "--trace-config", "--unix-socket", "--upload-file",
    "--url-query", "--user", "--user-agent", "--variable", "--write-out",
    "-A", "-C", "-D", "-E", "-F", "-H", "-K", "-P", "-Q", "-T", "-U", "-X",
    "-Y", "-b", "-c", "-d", "-e", "-h", "-m", "-o", "-r", "-sF", "-sd",
    "-t", "-u", "-w", "-x", "-y", "-z",
})
# Claude Code's "Exit code N" or Antigravity's header, never a refusal: an attempt at any exit, a probe at 1 only.
RX_RAN_FAILED = re.compile(r"^(?:\s|\\n)*(?:Exit code [1-9]|Command timed out)|^(?:\w+ At: .*\n)*(?:the )?command exited with code [1-9]", re.I)
RX_EXIT_1 = re.compile(r"^(?:\s|\\n)*Exit code 1\b|^(?:\w+ At: .*\n)*(?:the )?command exited with code 1\b", re.I)
RX_AGY_TRANSCRIPT_PATH = re.compile(
    r"(?:^|/)(?:\.gemini/antigravity/|brain/[^/]+/\.system_generated/logs/transcript)")
AGY_RECORD_TYPES = frozenset({
    "PLANNER_RESPONSE", "USER_INPUT", "SYSTEM_MESSAGE", "EPHEMERAL_MESSAGE",
    "TOOL_RESPONSE",
})
GATE = "shared/workflow/adversarial-self-review.md"

NOTE = (
    "[warn-merge-without-cross-harness-review] Refused. {target}: this "
    "session's transcript shows no cross-harness reviewer run since the last "
    "push, and no probe of every route. "
    "The merge gate in " + GATE + " ('Cross-model and cross-harness reviews "
    "are required for merging') needs a verdict from a reviewer whose model "
    "AND harness both differ from this session's. An Agent subagent and the "
    "CI claude-review workflow are both Claude and do not qualify. Run one "
    "of {clis} (or in cloud sessions, curl to opencode.ai with candidate "
    "model fallback per delegate-to-opencode) on the shipping head first, "
    "in a review form: `codex exec`, `opencode run`, or `-p`/`--print` "
    "(`claude -p`); a subcommand comes before any option with a value. "
    "If no qualifying reviewer can run here (host blocked, backend down, "
    "CLI or credential absent), probe every route once: attempt each of "
    "{clis} as a reviewer, or show it absent with `command -v <cli>` or `which <cli>` alone, unredirected (exit 1); "
    "opencode needs an attempt (its CLI or the OpenCode Go curl). An Ollama Cloud chat curl is no attempt: it is itself a qualifying review. Then the "
    "gate is waived and this hook lets the merge through "
    "(Ezra, 2026-10-16; adversarial-self-review.md "
    "'Waiver when no cross-model reviewer can run'). The waiver grants no "
    "merge authority: the merge still needs mwc or an explicit instruction, "
    "a clean Claude review plus green CI, and a PR note that the review was "
    "waived. A reviewer that ran and was not clean is not unavailable."
)


_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from sibling import load_sibling
except ImportError as _exc:
    print(f"{os.path.basename(__file__)}: cannot load scripts/lib/sibling.py "
          f"({_exc}); its sibling hook will not load", file=sys.stderr)
    load_sibling = None


def _sibling():
    """Import `warn-merge-without-fully-clean.py` (scripts/lib/sibling.py); raises if it cannot load."""
    if load_sibling is None:
        raise ImportError("scripts/lib/sibling.py is not importable")
    return load_sibling(__file__, "warn-merge-without-fully-clean.py", "_sib_wmwfc", required=True)


def own_harness(path="", recs=None):
    """The CLI name of the harness running this hook (see the docstring)."""
    if os.environ.get("ANTIGRAVITY_AGENT"):
        return "agy"
    norm = (path or "").replace("\\", "/")
    if RX_AGY_TRANSCRIPT_PATH.search(norm):
        return "agy"
    if recs and any(isinstance(r, dict) and r.get("type") in AGY_RECORD_TYPES
                    for r in recs):
        return "agy"
    return "claude"


def own_harnesses(path="", recs=None):
    """CLI names that share the authoring session's harness/model family.

    Note: assumes an Antigravity session runs a Gemini-family model (the
    platform default) so `claude` counts as cross-harness and `agy`/`gemini`
    are excluded as same-family.
    """
    if own_harness(path, recs) == "agy":
        return frozenset({"agy", "gemini"})
    return frozenset({"claude"})


def _argvs(sib, command):
    for line in sib.shell_c_expansions(command):
        for argv in sib.simple_commands(line) or []:
            yield sib.strip_env(argv)[1]


def _peel_wrappers(rest):
    """Drop leading `nohup` and `timeout [opts] DURATION` from an argv."""
    while rest:
        word = os.path.basename(rest[0])
        if word == "nohup":
            rest = rest[1:]
        elif word == "timeout":
            rest = rest[1:]
            while rest and rest[0].startswith("-"):
                takes_arg = rest[0] in TIMEOUT_ARG_OPTS
                rest = rest[2:] if takes_arg else rest[1:]
            if rest and not rest[0].startswith("-") and (
                    os.path.basename(rest[0]) not in CROSS_HARNESS_CLIS
                    and os.path.basename(rest[0]) != "curl"):
                rest = rest[1:]  # the duration
        else:
            return rest
    return rest


def _takes_value(word):
    """True when curl reads the word after *word* as an option's value.

    A cluster of short options (`-sw`, `-4o`) is read as curl reads it:
    the first letter that takes a value takes the rest of the word when any
    is left (`-XPOST`, `-oout`), and the next word only when it is last.
    """
    if word in CURL_VALUE_OPTS:
        return True
    # curl 8.3+ takes `--expand-<option>` wherever `--<option>` takes a value.
    if word.startswith("--expand-"):
        return "--" + word[len("--expand-"):] in CURL_VALUE_OPTS
    if not word.startswith("-") or word.startswith("--"):
        return False
    for pos, letter in enumerate(word[1:], start=2):
        if "-" + letter in CURL_VALUE_OPTS:
            return pos == len(word)
    return False


def _bundle_verb(word, nxt):
    """The method a short-option bundle *word* sets, else None.

    `G` and `I` give a non-POST method, and `X` takes the rest of the bundle,
    or the next word *nxt* when it ends the bundle. A letter that takes a
    value ends the scan, since the letters after it are that value
    (ai-config#5363).
    """
    for pos, letter in enumerate(word[1:], start=2):
        if letter in "GI":
            return "GET" if letter == "G" else "HEAD"
        if letter == "X":
            return word[pos:] or nxt
        if "-" + letter in CURL_VALUE_OPTS:
            return None
    return None


def _curl_route(rest):
    """The HTTP_ROUTES entry a `curl` POST in *rest* reaches, else None."""
    if HELP_FLAGS.intersection(rest[1:]):
        return None
    # A review requires a POST payload with the prompt; a smoke test does not qualify
    has_data = any(
        arg.startswith(("-d", "-F", "-sd", "-sF", "--data", "--form", "--json"))
        or arg in ("-d", "-F", "-sd", "-sF", "--data", "--form", "--json")
        for arg in rest[1:]
    )
    if not has_data:
        return None
    args = rest[1:]
    for i, arg in enumerate(args):
        prev = args[i - 1] if i else ""
        # `-X GET`, `-XGET`, `--request=GET`, `-G` and `-I` are not a POST,
        # and neither is a bundle holding one of them (`-sSXGET`, `-sI`).
        verb = arg if prev == "--request" else None
        if arg.startswith("--request="):
            verb = arg.split("=", 1)[1]
        elif arg.startswith("-") and not arg.startswith("--"):
            verb = _bundle_verb(arg, args[i + 1] if i + 1 < len(args) else "")
        if (verb is not None and verb.upper() != "POST") or arg in (
                "--get", "--head"):
            return None
    # Only a bare URL word is the target, never an option value (`-d URL`, `--form-string URL`).
    # Walk from the left, so a value that looks like an option (`-d -e`) takes nothing.
    values, takes = set(), False
    for i, arg in enumerate(args):
        if takes:
            values.add(i)
            takes = False
        elif arg == "--":
            break
        else:
            takes = _takes_value(arg)
    for i, arg in enumerate(args):
        if not arg.lower().startswith(("http://", "https://")) or i in values:
            continue
        try:
            parts = urllib.parse.urlsplit(arg)
        except Exception:
            continue
        host = (parts.hostname or "").lower()
        for route in HTTP_ROUTES:
            if host == route[0] and parts.path.rstrip("/") == route[1]:
                return route
    return None


def _is_review_call(base, args):
    """True when *args* make reviewer CLI *base* run a review, not housekeeping."""
    words = args[:args.index("--")] if "--" in args else args
    if HELP_FLAGS.intersection(words):
        return False
    if base in REVIEW_SUBCOMMANDS:
        first = next((a for a in words if not a.startswith("-")), None)
        return first in REVIEW_SUBCOMMANDS[base]
    flags = REVIEW_FLAGS.get(base, frozenset())
    # A long flag may carry `=value`; a short one `=value` or an attached
    # value (`agy -p="..."`, memories/antigravity.md).
    return any(a.split("=", 1)[0] in flags if a.startswith("--")
               else any(a.startswith(f) for f in flags if len(f) == 2)
               for a in words)


def _review_route(rest, clis):
    """The route a reviewer call in *rest* takes: a CLI name, a host, or None."""
    rest = _peel_wrappers(rest)
    if not rest:
        return None
    base = os.path.basename(rest[0])
    if len(rest) > 1 and base in clis:
        return base if _is_review_call(base, rest[1:]) else None
    if base == "curl":
        route = _curl_route(rest)
        if route and (route[2] is None or route[2] in clis):
            return route[2] or route[0]
    return None


def _probed_names(rest):
    """CLI names a `command -v` or `which` presence probe in *rest* asks about."""
    rest = _peel_wrappers(rest)
    if not rest or os.path.basename(rest[0]) not in PROBE_WORDS:
        return []
    args = rest[1:]  # any redirect: the tokens cannot tell stderr from stdout
    if any("<" in a or ">" in a for a in args):
        return []
    if os.path.basename(rest[0]) == "command":
        if not args or args[0] != "-v":  # `-V` prints "name is aliased to"
            return []
        args = args[1:]
    return [] if any(a.startswith("-") for a in args) else args  # `which -s` prints nothing


def _absent(name, text):
    """True when probe output *text* printed no path or name for *name*."""
    lines = [ln.strip() for ln in (text or "").splitlines()]
    return not any(ln == name or ln.endswith("/" + name)
                   or ln.startswith(("alias " + name + "=", name + ":", name + " (")) for ln in lines)  # zsh: `name: aliased`


def _shell_events(sib, command, clis):
    """Events in *command* as (kind, piece), kind 'push' or 'review'.

    `piece` numbers the expansion the event came from: 0 for the command
    itself, then each nested `bash -c` operand. Events within one piece are
    in text order; events in different pieces are not ordered at all, since
    the expansions are listed outer-first rather than in execution order.
    """
    events = []
    for piece, line in enumerate(sib.shell_c_expansions(command)):
        for argv in sib.simple_commands(line) or []:
            parsed = sib.git_subcommand(argv)
            if parsed and parsed[0] == "push":
                events.append(("push", piece))
            # strip_env peels `timeout` but not its options and duration, so
            # also test the raw argv with leading assignments dropped.
            raw = list(argv)
            while raw and ENV_ASSIGNMENT.match(raw[0]):
                raw = raw[1:]
            if (_review_route(sib.strip_env(argv)[1], clis)
                    or _review_route(raw, clis)):
                events.append(("review", piece))
    return events


def _fresh(events):
    """True when the command's last review runs after every push in it.

    Only order within one expansion piece is known, so a push in a different
    piece from the last review makes the review stale: crediting it could
    credit a review that ran before the push.
    """
    pushes = [(i, p) for i, (k, p) in enumerate(events) if k == "push"]
    if not pushes:
        return True
    last_i, last_piece = [(i, p) for i, (k, p) in enumerate(events)
                          if k == "review"][-1]
    return all(p == last_piece and i < last_i for i, p in pushes)


def _route_calls(sib, command, clis):
    """(routes attempted, names presence-probed) in *command*, any order."""
    attempts, probes = set(), []
    argvs = [a for ln in sib.shell_c_expansions(command) for a in sib.simple_commands(ln) or []]
    for argv in argvs:
        raw = list(argv)
        while raw and ENV_ASSIGNMENT.match(raw[0]):
            raw = raw[1:]
        for rest in (sib.strip_env(argv)[1], raw):
            route = _review_route(rest, clis)
            if route:
                attempts.add(route)
            probes.extend(_probed_names(rest))
    return attempts, probes if len(argvs) == 1 else []  # a probe counts only alone


def all_routes_probed(clis, cleared, last_push):
    """True when each route in *clis* was attempted, or found absent, after the last push."""
    return all(cleared.get(c, -1) > last_push or (c not in NEEDS_ATTEMPT and cleared.get(
        "absent:" + c, -1) > last_push) for c in clis)


def scan(sib, path, clis, recs=None):
    """Return (last_push_seq, [seq of successful reviewer calls], cleared).

    A push and a review in one command count the push at seq - 0.5, a review
    that `_fresh` places after every push at seq, and any other at seq - 1.
    `cleared` maps each route to the seq of the last non-sidechain call that
    cleared it for the waiver: an attempt with any result (key: the route),
    or a presence probe that found a CLI absent (key: "absent:<cli>").
    """
    last_push = -1
    pending = {}
    reviews = []
    cleared = {}
    stream = recs if recs is not None else sib.records(path)
    for seq, rec in enumerate(stream):
        for b in sib._blocks(rec):
            kind = b.get("type")
            if kind == "tool_use":
                name = b.get("name")
                if name in sib.MCP_PUSH_TOOLS:
                    last_push = max(last_push, seq)
                    continue
                cmd = _shell_command(b.get("input") or {})
                if name not in sib.SHELL_TOOLS or not isinstance(cmd, str):
                    continue
                try:
                    events = _shell_events(sib, cmd, clis)
                    kinds = [k for k, _p in events]
                    if "push" in kinds:
                        last_push = max(last_push, seq - 0.5)
                    if rec.get("isSidechain"):
                        continue
                    attempts, probes = _route_calls(sib, cmd, clis)
                    review_seq = None
                    if "review" in kinds:
                        review_seq = seq if _fresh(events) else seq - 1
                    if review_seq is not None or attempts or probes:
                        # An attempt sharing a call with a push may precede it (a probe never shares one).
                        seq_call = seq - 1 if "push" in kinds else seq
                        pending[b.get("id")] = (seq_call, review_seq,
                                                attempts, probes)
                except Exception:
                    continue
            elif kind == "tool_result" and b.get("tool_use_id") in pending:
                seq_call, review_seq, attempts, probes = pending.pop(
                    b["tool_use_id"])
                text = sib._result_text(b)
                if rec.get("toolDenialKind") or b.get("is_error") and not RX_RAN_FAILED.match(text):
                    continue  # a refused call ran nothing: no attempt, no probe
                if review_seq is not None and not b.get("is_error"):
                    reviews.append(review_seq)
                for route in attempts:
                    cleared[route] = max(cleared.get(route, -1), seq_call)
                for probed in [p for p in probes if p in clis]:  # a later sighting voids an earlier absence
                    absent = RX_EXIT_1.match(text) and _absent(probed, text)
                    cleared["absent:" + probed] = max(cleared.get("absent:" + probed, -1), seq_call) if absent else -1
    return last_push, reviews, cleared


def _shell_command(tool_input):
    """The command text under whichever key the harness uses."""
    return (tool_input.get("command") or tool_input.get("CommandLine")
            or tool_input.get("cmd") or tool_input.get("script"))


def _targets(sib, tool, tool_input):
    """[(number|None, repo|None)] for every merge this call performs."""
    if tool == sib.MCP_MERGE_TOOL or RX_AUTO_MERGE_TOOL.match(tool):
        return sib._merge_targets(sib.MCP_MERGE_TOOL, tool_input)
    command = _shell_command(tool_input)
    if not isinstance(command, str):
        return []
    return [hit for hit in map(sib._gh_merge, _argvs(sib, command)) if hit]


def main() -> int:
    try:
        sib = _sibling()
        if sib.simple_commands is None:
            return 0
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    if (tool not in sib.SHELL_TOOLS and tool != sib.MCP_MERGE_TOOL
            and not RX_AUTO_MERGE_TOOL.match(tool)):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload.get("toolInput")
    if not isinstance(tool_input, dict):
        return 0
    path = payload.get("transcript_path") or ""
    try:
        targets = _targets(sib, tool, tool_input)
        if not targets or not path or not os.path.isfile(path):
            return 0
        recs = list(sib.records(path))
        clis = CROSS_HARNESS_CLIS - own_harnesses(path, recs)
        last_push, reviews, cleared = scan(sib, path, clis, recs=recs)
        if tool in sib.SHELL_TOOLS and sib._push_before_merge(
                _shell_command(tool_input) or ""):
            reviews, cleared = [], {}
        probed = all_routes_probed(clis, cleared, last_push)
    except Exception:
        return 0
    if probed or any(seq > last_push for seq in reviews):
        return 0

    nums = list(dict.fromkeys(
        f"#{num}" for num, _repo in targets if num is not None))
    target = "PR " + ", ".join(nums) if nums else "This merge"
    note = NOTE.format(target=target, clis=", ".join(sorted(clis)))
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "permissionDecision": "deny",
                                  "permissionDecisionReason": note}}
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Refused merging (or arming auto-merge for) {target} with no "
            f"cross-model, cross-harness review "
            f"since the last push ({GATE}).")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
