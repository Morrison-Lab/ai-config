#!/usr/bin/env python3
"""PreToolUse guard: writing required status checks nobody derived.

## The gap this closes

A ruleset's `required_status_checks` holds *strings matched against a
check-run name exactly*. A string no workflow emits does not fail loudly: it
sits as `Expected` on every pull request forever, blocking every merge in the
repository, with nothing red to point at and no error raised anywhere.

`shared/workflow/verify-the-right-artifact.md` already names the substitution
that produces a wrong one, in its four bullet headings -- "A cached copy for
the origin", "A checkout for the run", "One half of a mechanism for the
whole", "A neighbour for the target". `shared/workflow/algorithmatize-checks.md`
already says a value the CI system computes should be read from the instrument
rather than retyped.

Both were loaded when this failure happened (ai-config#3039), and neither
fired, because the wrong artifact was a *real* one. Reading check names off an
open or recently-merged pull request feels like deriving the answer from
evidence rather than assuming: the names are right there, they are real check
runs, and they really were reported. They are evidence about **that pull
request's head**, which may predate a workflow rename -- while a required
context has to match what the **default branch** emits on every future pull
request.

A rule is consulted at read time and broken at composition time, so re-reading
either fragment does not reach the moment a `-X PUT` is composed. That is what
makes this a hook.

## Why it has no discharge condition

An earlier draft tried to stay quiet when the session had already derived the
names, by scanning the transcript for a job-name query. Adversarial review
killed that design, and the reasons are worth keeping so it is not
reintroduced:

- A transcript scan cannot tell a *default-branch* run from a pull request's
  own run. `actions/runs/<id>/jobs` names no branch, so accepting it re-admits
  the exact wrong-artifact substitution the guard exists to catch, one word
  away from the query that caused the incident.
- `gh run list --branch <x>` names a branch but not *which* branch, so a
  feature branch discharged it.
- Any scan over tool inputs is satisfiable by *text*. Writing the string in a
  file, grepping for it, or appending it as a shell comment on the write
  itself disarmed the guard with no query ever run.

So the guard always warns. That is affordable because the trigger is rare --
writing a ruleset is not something a session does incidentally -- and because
a warning costs a sentence to dismiss. A discharge that can be satisfied by
typing the right characters is worse than none: it converts a guard into a
formality while reporting itself as protection.

## Why it warns rather than refuses

It cannot see whether the *values* are right, only that a merge-gating write
is happening. Refusing would be wrong in a way whose remedy is not obvious,
and a guard that blocks legitimate settings changes gets switched off, taking
the real cases with it (`algorithmatize-checks`'s "Limits").

## Scope

`gh api` writes to repository rulesets, organization rulesets (whose blast
radius is every repo in the org), and classic branch protection. A `curl` to
`api.github.com` and a `gh api graphql` mutation are out of scope and stated
as such rather than silently missing.

Heredoc bodies are stripped and the command split into shell segments before
matching, reusing `require-gh-repo-flag.py`'s parser -- README names that
hook's first version, which fired on a heredoc merely documenting a command,
as this repo's cautionary example.

Fails OPEN on any parse trouble.
"""
import functools
import importlib.util
import json
import os
import re
import shlex
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


@functools.lru_cache(maxsize=None)
def _load_shell_parser():
    """Borrow `require-gh-repo-flag.py`'s heredoc stripper and segment splitter.

    Reimplementing either would be a second copy of a parser this repo already
    maintains and has hardened (`shared/principles/dont-reinvent-wheel.md`).
    The module name carries hyphens, so it cannot be a plain import. Memoised
    (`shared/coding/use-memoisation.md`): it is pure, it costs an `exec` of the
    whole parser file, and a mutation harness calls it hundreds of times per
    run.
    """
    path = os.path.join(_HERE, "require-gh-repo-flag.py")
    spec = importlib.util.spec_from_file_location("_gh_repo_flag_parser", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.strip_heredocs, module.split_command


# A `gh api` call that WRITES. `-X PUT`, `--method PUT` and the concatenated
# pflag shorthand `-XPUT` are all accepted by gh, so all three count; an
# earlier draft required a separator and missed `-XPUT`.
# PUT and PATCH only. An explicit POST is not listed because gh switches to
# POST precisely WHEN parameters are supplied, so every POST that carries a
# body is already caught by RX_IMPLICIT_POST below -- listing it here would be
# an alternation no input can reach, which is dead code by another name.
RX_WRITE_METHOD = re.compile(r"(?:-X|--method)[=\s]*(?:PUT|PATCH)\b")

# ... but an explicit method is not required at all. `gh api --help`: "The
# default HTTP request method is GET normally and POST if any parameters were
# added", and gh's own documented example for this very endpoint is
# `gh api repos/{owner}/{repo}/rulesets --input file.json` with no -X. So
# supplying parameters IS a write, and an earlier draft missed the single most
# idiomatic way to create a ruleset.
# `-f`/`-F` need no separator either, for the same pflag reason `-XPUT` does
# not: an earlier draft required one and was silent on
# `gh api ... -frequired_status_checks[][context]=lint`. The leading
# `(?:^|\s)` keeps `-[fF]` from matching inside `--field` or `--force`, whose
# second character is a dash.
RX_IMPLICIT_POST = re.compile(r"(?:^|\s)(?:--input\b|-[fF]|--(?:raw-)?field\b)")

# An explicit read method beats both: `-X GET` with parameters is a query.
RX_READ_METHOD = re.compile(r"(?:-X|--method)[=\s]*(?:GET|HEAD)\b")

# Endpoints whose payload can carry required status checks. Organization
# rulesets are included: one bad context there blocks merges across every
# repository in the org.
RX_PROTECTION_ENDPOINT = re.compile(
    r"(?:^|[\s\"'/])(?:repos|orgs)/[^\s\"']+?"
    # No `(?:/\d+)?` after `rulesets`: under re.search an optional trailing
    # group cannot change whether a match exists, so it would be inert.
    r"/(?:rulesets|branches/[^\s\"']+/protection)",
)

# Payload markers: the field named inline, or a whole document supplied by
# file, whose contents cannot be seen from here.
#
# CASE-SENSITIVE, deliberately. `gh` distinguishes `-f` (raw field) from `-F`
# (typed field) by case alone, so an `re.I` pattern mentioning either matches
# both. An earlier draft included `-F\s` under `re.I` and fired on
# `gh api -X PUT .../rulesets/1 -f enforcement=disabled`, a ruleset write with
# no status checks in it. Neither flag is listed now: a field-supplied status
# check still names `required_status_checks`, which the first alternative
# catches on its own.
RX_STATUS_PAYLOAD = re.compile(r"required_status_checks|\bcontexts\b|--input\b")

WARNING = """\
no-underived-required-check: this writes repository merge-gating settings.

A required status-check context is matched against a check-run name EXACTLY. \
A string no workflow emits never fails loudly -- it sits as `Expected` on \
every pull request forever and blocks every merge, with nothing red to point \
at.

Derive each context from the workflow definitions on the DEFAULT BRANCH -- \
they are what future pull requests run. `gh pr view --json statusCheckRollup` \
reads a PR's own head, which can predate a workflow rename, so its check names \
may be names the default branch no longer emits; that substitution is the \
failure this guard exists to catch \
(shared/workflow/verify-the-right-artifact.md).

A run listing is NOT a sound substitute, for the same reason. A \
`pull_request`-only workflow has no default-branch run at all, so \
`gh run list --branch <default>` returns `[]`; and on a mixed-trigger \
workflow the newest default-branch run may be a `workflow_dispatch` whose job \
set differs from the `pull_request` one under an event-gated `if:`.

Read the definitions, then confirm against a run of a PR built on current \
`<default>`:

    git fetch origin && git show origin/<default>:.github/workflows/<file>
    gh api repos/<owner>/<repo>/actions/runs/<id>/jobs --jq '.jobs[].name'

Three rules turn a definition into a context, and the last two are where a \
retyped string goes wrong:

  * A job's context is its `name:` when set, and its job key otherwise.
  * A MATRIX job appends its values in parentheses -- `test (ubuntu-latest, \
    3.11)`, not `test`. Requiring the bare name requires a string no run \
    emits.
  * A reusable-workflow call (`uses:`) reports as `<caller job> / <called \
    job>`, each half named by the first rule. That pair is the string most \
    often retyped as just one of its halves.

This is a warning, not a refusal -- if the contexts are already derived, \
proceed."""

SYSTEM_MESSAGE = (
    "Merge-gating write: required status-check contexts must be derived from a "
    "default-branch run's job names, not from a PR's statusCheckRollup."
)


# Leading `VAR=value` assignments precede the command word in a shell segment.
RX_ENV_PREFIX = re.compile(r"^(?:\s*[A-Za-z_][A-Za-z0-9_]*=(?:\S*)\s+)*")

# Words that can precede the real command word within one segment. Two kinds,
# deliberately in one set because the stripping is identical:
#
#   * Shell keywords. `split_command` emits these as part of the segment, so
#     `for r in a b; do gh api -X PUT ...; done` arrives as `do gh api ...`.
#     This half is `require-gh-repo-flag.py`'s KEYWORD_PREFIX verbatim.
#   * Wrappers that take a command as their argument -- `xargs`, `timeout`,
#     `nice` and friends. These are NOT in that constant; they are added here
#     because `gh repo list | xargs -I{} gh api -X PUT repos/o/{}/rulesets/1
#     --input rs.json` is the same one-write-across-many-repositories shape the
#     loop form is, and an earlier draft was silent on it.
#
# Stripping a wrapper is approximate: its own flags are dropped along with it,
# so `xargs -I{} gh api ...` anchors because `-I{}` precedes `gh`. `timeout`
# additionally takes a POSITIONAL duration, which no flag rule reaches, so it
# gets one narrow extra skip -- otherwise `timeout 60 gh api -X PUT ...` is
# silent, and a wrapper the guard half-knows is worse than one it does not.
SHELL_KEYWORDS = ("!", "{", "time", "nohup", "sudo", "then", "else", "do",
                  "if", "elif", "while", "until")
COMMAND_WRAPPERS = ("env", "command", "xargs", "timeout", "nice", "stdbuf",
                    "parallel")
SHELL_WRAPPERS = frozenset(SHELL_KEYWORDS + COMMAND_WRAPPERS)
# A `timeout`/`parallel` duration: a bare number with an optional unit suffix.
RX_DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
RX_SHELL_WRAPPER_PREFIX = re.compile(
    r"^\s*(?:(?:" + "|".join(re.escape(w) for w in SHELL_WRAPPERS)
    # a flag, optionally followed by its separated value (never `gh` itself)
    + r")\s+(?:-\S+\s+(?!gh\s)(?:[^-\s]\S*\s+)?)*"
    + r"(?:\d+(?:\.\d+)?[smhd]?\s+)?)*"
)


def segment_invokes_gh_api(segment):
    """True when `gh api` is the segment's COMMAND, not text inside an argument.

    Splitting on shell operators is not enough on its own. `git commit -m "gh
    api -X PUT .../rulesets/1 --input rs.json"` is a single segment whose text
    contains the whole trigger, and so is a `gh pr comment --body '...'` or a
    `grep` for the pattern. Matching those is the exact failure README names as
    this repo's cautionary example, so the command word is checked rather than
    the segment's text.

    `shlex` resolves the quoting properly. When it cannot -- an unbalanced
    quote, most often from a fragment of a larger construct -- the fallback
    requires the segment to BEGIN with `gh`, which is conservative in the
    direction of silence. A warn-only guard that cries wolf gets switched off,
    so a missed write costs less here than a false positive.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        stripped = RX_SHELL_WRAPPER_PREFIX.sub("", segment)
        stripped = RX_ENV_PREFIX.sub("", stripped).lstrip()
        return bool(re.match(r"gh\s+api\b", stripped))
    while tokens:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens.pop(0)
        elif tokens[0] in SHELL_WRAPPERS:
            tokens.pop(0)
            # A command wrapper's own flags sit between it and the command,
            # and `timeout` puts a positional duration there too. A flag's
            # VALUE may be a separate token (`xargs -I {}`, `sudo -u ci`,
            # `timeout -k 10`), so it is consumed with the flag -- unless it is
            # `gh` itself, which is the command rather than a value.
            while tokens and tokens[0].startswith("-"):
                flag = tokens.pop(0)
                if ("=" not in flag and tokens
                        and not tokens[0].startswith("-")
                        and tokens[0] != "gh"):
                    tokens.pop(0)
            if tokens and RX_DURATION.match(tokens[0]):
                tokens.pop(0)
        else:
            break
    return len(tokens) >= 2 and tokens[0] == "gh" and tokens[1] == "api"


def segment_is_write(segment):
    """True when this `gh api` segment mutates rather than queries.

    An explicit `-X GET`/`--method GET` wins outright: parameters on a GET are
    query parameters, not a write.
    """
    if RX_READ_METHOD.search(segment):
        return False
    if RX_WRITE_METHOD.search(segment):
        return True
    return bool(RX_IMPLICIT_POST.search(segment))


def command_is_protection_write(command, strip_heredocs, split_command):
    """True when `command` writes required status checks to a protection API.

    Heredoc bodies are dropped and the remainder split into shell segments, so
    a command that merely quotes or documents such a write does not match.
    """
    for segment in split_command(strip_heredocs(command)):
        if not segment_invokes_gh_api(segment):
            continue
        if not segment_is_write(segment):
            continue
        if not RX_PROTECTION_ENDPOINT.search(segment):
            continue
        if RX_STATUS_PAYLOAD.search(segment):
            return True
    return False


def evaluate(command, strip_heredocs=None, split_command=None):
    """Return the warning text, or None when the guard does not apply."""
    if strip_heredocs is None or split_command is None:
        strip_heredocs, split_command = _load_shell_parser()
    if not command_is_protection_write(command, strip_heredocs, split_command):
        return None
    return WARNING


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"no-underived-required-check: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0

    if payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
    ):
        return 0

    tool_input = payload.get("tool_input") or {}
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or tool_input.get("cmd")
        or tool_input.get("script")
    )
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        text = evaluate(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"no-underived-required-check: could not evaluate ({exc})",
              file=sys.stderr)
        return 0

    if text is None:
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": text,
        },
        "systemMessage": SYSTEM_MESSAGE,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
