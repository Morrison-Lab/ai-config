#!/usr/bin/env python3
"""Stop-hook guard: catch opening a PR without requesting a reviewer.

Opening a PR auto-triggers the repo's *own* review workflow, so review
genuinely is in motion -- for that half. It does NOT summon Copilot, which
reviews only when explicitly requested. The auto-triggered half running is
exactly what disguises the missing half: the PR shows review-shaped activity
in its checks while no reviewer has read the diff.

That matters more here than in most repos, because `claude-review` on this
repo's own PRs has failed on every run that actually attempted a review this
session (ai-config#897). Whatever the cause -- #897 calls prompt overflow only
the leading hypothesis, states the literal error is unconfirmed, and reports
15 successful runs on six other branches -- the observed effect stands on its
own: when it fails, Copilot is the only working reviewer, so a PR opened
without an explicit request gets no review at all.

The condition is exactly decidable from the transcript, which is why this is
a hook rather than a rule to remember:

    a PR was created or marked ready this session
    AND no reviewer request came after it

A reviewer request is per-HEAD, not per-PR, so the same obligation re-arms on
every push that re-heads a tracked PR. Without that the guard is armed once and
PERMANENTLY discharged by the first request: round 2 pushes a new head, nothing
re-arms, and the PR carries a review of a commit that is no longer its head
(ai-config#1274, where round 1's Copilot request at 6a4101e5 was never renewed
at 76e619aa and nothing warned).

Attribution is the hard part, and it is answered by EXCLUSION rather than by
guessing. A push almost never names the PR it re-heads. Measured over this
machine's transcript corpus (204 transcripts, 20102 tool_use records): 718
`git push` commands, against 51 tool results anywhere carrying a PR's
`headRefName`. So branch-matching a push to a PR is unavailable for most
pushes, and a guard built on it would rarely fire.
So a push re-arms only when the session has exactly ONE live tracked PR, which
is the case where the push has only one PR it COULD re-head. With two or more
the push is genuinely unattributable and nothing is re-armed: arming all of
them would demand N requests for one push and wedge the session, which costs
more than the gap it closes.

Arming is the SAFE direction (an over-warn), so unlike every discharge path it
does not wait for a result and does not read `is_error`. Only releasing changes
need positive evidence of success -- see shared/principles/fail-fast.md, "A
guard's discharge fires on positive success".

Correlation is by tool_use identity, not by position or by a scalar
timestamp. Three facts make that necessary, each an independently-reproduced
bug in the position/timestamp model this replaces:

  * A `gh pr create` command cannot carry its own PR number -- the number
    only appears in the command's RESULT. So the open is keyed from its
    result (URL or `number` field), by tool_use id, not from the command.
  * A reviewer request is discharged only by ITS OWN successful result,
    matched by tool_use id -- not by the first result in a batch, which may
    belong to an unrelated tool.
  * A read of the `requested_reviewers` endpoint (a GET) is not a request;
    only a mutating POST (or a `--reviewer`/`--add-reviewer`/
    `request_copilot_review` form) discharges the obligation.

Obligations carry owner/repo when the transcript provides it, so the same PR
number in two repositories is two obligations, not one.

Two deferrals are legitimate, and both are recorded rather than assumed: a
DRAFT PR (which does not trigger the review bot at all), and a REDACTION PR,
whose diff carries the redacted literal on the removed side of every hunk so
that requesting a reviewer is itself the exposure. See the "Redaction
exemption" block below for that second one's two forms and why it is asserted
rather than inferred.

A THIRD deferral is legitimate, and unlike the other two it suspends the
whole guard rather than one PR's obligation: a standing user directive not to
request the reviewer at all. As of 2026-08-19 that is live -- Copilot review is
off across ALL repos until MORATORIUM_END below (memories/gh-cli.md, "Restated and
widened 2026-08-19"). A user instruction outranks a hook, and every discharge
this guard offers is the one action the directive forbids, so honoring it left
the demand repeating on every turn -- the per-message dedup below stops one
identical message re-firing, and does nothing about a demand that re-arms as
the transcript grows, which is a different thing from the wedge that dedup
prevents.

The script now reads that directive itself, from `MORATORIUM_END` below, and
`main` returns before scanning while it stands. Earlier revisions said to
unregister the hook from the Stop hooks for the duration; do NOT rely on that
now. It covers only a user-settings registration, and on a PLUGIN install the
registration is this repo's own `hooks/hooks.json`, so there is nothing in
`~/.claude/settings.json` to remove and unregistering silently does nothing
(ai-config#1709).

Fails OPEN on any parse trouble, and fires at most once per distinct message
per transcript, so it cannot wedge a session.
"""
import datetime
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile

# --- Copilot moratorium ----------------------------------------------------
# Every discharge this guard offers is a Copilot reviewer request, so a
# standing directive NOT to request Copilot leaves it with no satisfiable
# demand at all. That directive is live: `memories/gh-cli.md` ("Restated and
# widened 2026-08-19") forbids the request on ALL repos until MORATORIUM_END.
# A user instruction outranks a hook, so honoring it used to mean the demand
# simply repeated every turn, on a session that was already doing the right
# thing.
#
# The memory's prescribed remedy -- unregister the hook from
# `~/.claude/settings.json` -- covers ONE installation shape. Where ai-config
# is installed as a plugin the registration lives in this repo's own
# `hooks/hooks.json` under `${CLAUDE_PLUGIN_ROOT}`, so there is nothing in the
# user's settings to remove and the remedy silently does nothing
# (ai-config#1709). That shape is now the common one: `d-morrison/rme#1074`
# migrates off the submodule, and `Morrison-Lab/gha`'s
# `run-claude-review-attempt` installs the plugin for every review run.
#
# So the switch belongs in the script, where both installation shapes read it.
# It is a DATE rather than an env flag on purpose. An env flag has to be
# unset by whoever remembers the quota returned, and a guard nobody remembers
# to re-arm is a guard that is gone; a date re-arms itself on the day the
# override itself names, which is the property
# `shared/writing/timestamp-volatile-claims.md` asks of any claim whose truth
# expires. Extending the moratorium is then an edit to this constant and to
# the memory together, rather than a silent divergence between them.
#
# The guard is live ON the end date: the moratorium runs up to the date named,
# not through it.
#
# Extended 2026-09-02 on a fresh directive ("stop using copilot reviews"),
# given the day after the previous end date passed and the guard resumed
# demanding the request. That expiry is what produced the demand, so the
# recurrence is the mechanism working as designed rather than a defect --- the
# date re-armed itself and the user turned it off again.
#
# The new date is longer than the last, because the previous fortnight-scale
# window expired into an active session and cost a round of requests before
# anyone noticed. Three months puts the re-review far from the day-to-day and
# still refuses to become permanent by default.
MORATORIUM_END = datetime.date(2026, 12, 1)


def _today():
    """Today's date, as its own function so a test can drive a fixed clock.

    Deliberately NOT env-readable. A clock this guard reads from the
    environment would be a one-variable bypass of the guard itself, which is
    the same dangerous direction every discharge path here already refuses
    (see shared/principles/fail-fast.md). Tests import the module and override
    this name instead, which no session's environment can do.
    """
    return datetime.date.today()


def moratorium_active(today=None):
    """True while the Copilot request this guard demands is forbidden."""
    return (today if today is not None else _today()) < MORATORIUM_END


# Opening a PR, or taking a draft out of draft, via the CLI. The structured
# harness/MCP tools are matched by NAME below, not by this pattern -- a
# command string never contains `create_pull_request`, but a doc that quotes
# it would, which is the heredoc false positive README.md:265-271 warns about.
RX_OPEN = re.compile(r"gh\s+pr\s+(?:create|ready)\b", re.I)

# Marking a PR draft is a deliberate reason NOT to request review yet: a draft
# does not trigger the review bot, per shared/workflow/pr-on-claim.md. Only a
# *later* ready/create re-arms the guard.  `gh pr ready --undo` converts a
# ready PR BACK to draft, so it counts as a draft action even though it also
# matches RX_OPEN -- the draft branch is checked first below.
RX_DRAFT = re.compile(
    r"\"?draft\"?\s*[:=]\s*true|--draft\b|gh\s+pr\s+ready[^|;&]*--undo",
    re.I,
)

# A gh action must be an actual command word, not a string quoted inside a
# DIFFERENT command's argument. This repo's own docs and this hook's own
# recovery text are full of literal `gh pr create` / `requested_reviewers -X
# POST` examples, so a `gh pr comment --body "... gh pr create ..."` would
# otherwise forge an obligation, and a `--body "... requested_reviewers -X
# POST ..."` would silently DISCHARGE a real one -- the exact false negative
# this hook exists to catch (the README.md:265-271 heredoc trap, one layer in
# from the non-shell-tool case).
#
# Open/draft detection and request detection defend against that differently,
# because they key on structurally different things:
#
#   * RX_OPEN/RX_DRAFT key on `gh pr create`/`ready`, always a LEADING command
#     word, never legitimately inside quotes. So for them every quoted span is
#     blanked (`_scrub_all`) before matching -- that neutralises an example
#     create quoted in a `--body` AND a bare `echo "gh pr create"`, with no
#     risk to a real open, whose command word is never quoted.
#   * Request detection keys on `requested_reviewers`/`-X POST`, which are the
#     STRUCTURAL argv of the hook's OWN recovery command
#     (`gh api "repos/o/r/pulls/N/requested_reviewers" -X POST`) -- double-
#     quoting a `gh api` URL is standard shell, so blanking every quote there
#     erases a genuine request and the hook nags forever after the user does
#     exactly what it asked (round 4's regression). But those same tokens also
#     appear inside ordinary string arguments -- `echo "... -X POST"`, a
#     `gh pr comment` body, a heredoc/herestring -- where they are NOT a
#     request. Blanking only known payload flags (round 5) missed every other
#     embedding mechanism. So request detection instead PARSES the command into
#     simple commands and inspects each one's argv (`request_ident`), matching
#     the request tokens only when they are the argv of an actual `gh api`/
#     `gh pr edit`/`gh pr create` invocation -- never the value of a string
#     argument. That closes the class rather than the next instance of it.
#
# Over-blanking (open/draft) only ever DROPS a match -- a missed obligation,
# the fail-open direction -- never forges or discharges one. Request parsing
# fails toward NOT-a-request (a shlex error or unrecognised form leaves the
# obligation outstanding and the hook warns), so it never silently discharges.
RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)


def _scrub_all(cmd):
    """Blank heredoc bodies and EVERY quoted span (safe for RX_OPEN only)."""
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cmd)
    cmd = re.sub(r"'[^']*'", "''", cmd)
    return cmd


# --- Structural reviewer-request detection --------------------------------
# `requested_reviewers`/`-X POST`/`--add-reviewer` are matched against the
# argv of parsed simple commands, never as substrings of the raw string, so an
# example request embedded in any string argument (echo, a comment body, a
# heredoc or herestring) is never mistaken for a real request. Verified
# against `gh --help`: `gh pr create --reviewer` and `gh pr edit
# --add-reviewer` exist; `gh pr review --request` does NOT (review has only
# --approve/--comment/--request-changes), so it is deliberately absent.

# Shell CONTROL operators that separate one simple command from the next:
# `;`, `&`/`&&`, `|`/`||`, `(`, `)` -- and a newline, handled below. Redirection
# operators (`<`, `>`, `>>`, `2>&1`) are deliberately EXCLUDED: a redirect
# attaches to the command it decorates rather than terminating it, so treating
# `>` as a separator split a genuinely-sole request with a trailing `> /dev/null`
# into two "commands", flipped its `last` flag to False, and left it permanently
# undischargeable (a severe over-warn). A `>`/`<` token now falls through into
# the current command's argv, where the request/draft detectors ignore it.
_SHELL_OPS = set("();|&")


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error.

    Line-continuations are joined and heredoc bodies blanked first, so shlex
    neither chokes on a heredoc body nor mis-splits a `\\`-continued request
    (like the hook's own recovery command) into two commands.

    An unescaped newline is a genuine command separator, but shlex treats it as
    whitespace and silently drops it -- which merged two commands on two lines
    into one, making a trailing command's exit status masquerade as the
    request's own `last` outcome and SILENTLY DISCHARGE a failed request (the
    dangerous direction). Multi-line Bash is the ordinary shape agents emit, so
    remaining newlines are converted to `;`. A newline INSIDE a quoted string
    becomes a `;` inside that quote -- a literal character in one token, not a
    separator -- so a multi-line `--body` is not split (and its contents are
    never argv the detectors read anyway).
    """
    cmd = re.sub(r"\\\r?\n", " ", cmd)   # join `\`-continued lines
    cmd = RX_HEREDOC.sub("<<", cmd)       # drop heredoc bodies
    cmd = cmd.replace("\n", ";")          # unquoted newline -> separator
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None                       # unbalanced quotes, etc.
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:    # a control-operator token (||, |, ;, &)
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _has_flag(argv, *flags):
    """True if argv contains any of `flags`, as a bare token or `flag=value`."""
    for a in argv:
        if a in flags or any(a.startswith(f + "=") for f in flags):
            return True
    return False


def _post_method(argv):
    """True if argv sets the HTTP method to POST (a mutating request)."""
    for i, a in enumerate(argv):
        au = a.upper()
        if au in ("-X", "--METHOD") and i + 1 < len(argv) \
                and argv[i + 1].upper() == "POST":
            return True
        if au == "-XPOST":
            return True
        if au.startswith("--METHOD=") and au.split("=", 1)[1] == "POST":
            return True
    return False


def _url_ident(url):
    """(num, repo) from a `repos/o/r/pulls/N/...` token; RX_CMD_API is below."""
    m = RX_CMD_API.search(url)
    if m:
        return m.group(3), f"{m.group(1)}/{m.group(2)}"
    return None, None


def _verb_ident(argv):
    """(num, repo) from a `gh pr edit <N> ... -R o/r` argv."""
    num = argv[3].lstrip("#") if len(argv) >= 4 \
        and argv[3].lstrip("#").isdigit() else None
    repo = None
    for i, a in enumerate(argv):
        if a in ("-R", "--repo") and i + 1 < len(argv):
            repo = argv[i + 1]
        elif a.startswith("--repo="):
            repo = a.split("=", 1)[1]
    return num, repo


def _argv_request(argv):
    """(is_request, num, repo) for one simple command's argv.

    Identity comes from the request command ITSELF -- the `gh api` URL, or the
    `gh pr edit` number/`-R` -- so a different PR path echoed earlier in the
    line cannot misdirect the discharge. `-r` (reviewer) differs from `-R`
    (repo) only by case, and argv tokens are matched case-sensitively, so the
    two never collide.
    """
    if not argv:
        return False, None, None
    a0 = argv[0]
    if a0 == "gh" and len(argv) >= 3 and argv[1] == "pr":
        sub, rest = argv[2], argv[3:]
        if sub == "create" and _has_flag(rest, "--reviewer", "-r"):
            return True, None, None       # a create's number is in its result
        if sub == "edit" and _has_flag(rest, "--add-reviewer"):
            num, repo = _verb_ident(argv)
            return True, num, repo
    # `gh api`/`curl`/`wget` hitting the requested_reviewers endpoint with a
    # POST. The same endpoint is read via GET (to CHECK who is requested), and
    # a GET must NOT discharge, which is why the method is required.
    api = (a0 == "gh" and len(argv) >= 2 and argv[1] == "api") \
        or a0 in ("curl", "wget")
    if api:
        url = next((t for t in argv if "requested_reviewers" in t), None)
        if url and _post_method(argv):
            num, repo = _url_ident(url)
            return True, num, repo
    return False, None, None


def request_ident(cmd):
    """(is_request, num, repo, last): does `cmd` genuinely request a reviewer?

    `last` is True when the matched request is the LAST simple command in the
    chain. That is exactly when the harness `is_error` exit status (which
    reflects the WHOLE call, i.e. its last command) is authoritative for the
    request's own outcome -- so the discharge can trust `err` only then. A
    request chained AHEAD of other commands has an is_error that belongs to a
    later command, so the discharge treats it as ambiguous and does not fire.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return False, None, None, False
    for i, argv in enumerate(cmds):
        ok, num, repo = _argv_request(argv)
        if ok:
            return True, num, repo, (i == len(cmds) - 1)
    return False, None, None, False


def _argv_draft(argv):
    """(is_draft, num, repo) for one simple command's argv: a draft transition.

    Structural and gh-SCOPED, exactly like _argv_request: a `--draft` token
    counts as a draft action ONLY as the flag of an actual `gh` invocation of
    the right shape -- never as a bare token in an UNRELATED command (a `--body`
    value, a different subcommand's argument). Without that scope, a failed
    `gh pr ready --undo` chained ahead of an unrelated command whose argv merely
    CONTAINS a `--draft`/`draft=true` token (`... ; gh pr comment N --body
    "draft=true"`, or a follow-up `gh pr create --draft`) is misread as the
    transition being last, silently discharging a still-ready PR -- the exact
    silent-discharge class every prior round blocked.

    Only the two shell forms that genuinely change draft state are matched:
    `gh pr ready [<N>] --undo` (ready -> draft) and `gh pr create --draft` (a
    new draft). A `gh api ... -f draft=true` is deliberately NOT matched: the
    REST `PATCH /pulls/{n}` endpoint does not accept `draft` (title/body/state/
    base/maintainer_can_modify only), so such a call does NOT convert a PR to
    draft -- treating it as one would discharge the obligation on a no-op
    success, silently clearing a still-ready PR. A real toggle is GraphQL
    (convert/markReady), which `gh pr ready` wraps and which this matches above.

    Identity comes from the draft command ITSELF, so a decoy PR verb elsewhere
    in the line (`gh pr comment 42 ... ; gh pr ready 1038 --undo`) cannot
    misdirect the clear onto the wrong PR.
    """
    if not argv or argv[0] != "gh":
        return False, None, None
    # `gh pr ready [<N>] --undo` converts a ready PR BACK to draft.
    if len(argv) >= 3 and argv[1] == "pr" and argv[2] == "ready" \
            and _has_flag(argv[3:], "--undo"):
        num, repo = _verb_ident(argv)
        return True, num, repo
    # `gh pr create --draft` opens a NEW draft PR (a draft action for ordering);
    # like any create, its number is in the result, not the command.
    if len(argv) >= 3 and argv[1] == "pr" and argv[2] == "create" \
            and _has_flag(argv[3:], "--draft"):
        return True, None, None
    return False, None, None


def draft_ident(cmd):
    """(is_draft, num, repo, last): does `cmd` perform a draft transition, and
    is that transition the LAST simple command?

    Mirrors request_ident exactly: it locates the draft action STRUCTURALLY (the
    first simple command that is a gh draft invocation) and reports whether THAT
    command is last -- which is exactly when the harness is_error (the whole
    call's exit status) is authoritative for the transition's own outcome. A
    draft action chained AHEAD of another command has an is_error belonging to a
    later command, so the discharge treats it as AMBIGUOUS and keeps the PR
    tracked (the safe over-warn direction). Fails toward not-a-draft on a parse
    error, so it never fabricates a clear.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return False, None, None, False
    for i, argv in enumerate(cmds):
        ok, num, repo = _argv_draft(argv)
        if ok:
            return True, num, repo, (i == len(cmds) - 1)
    return False, None, None, False


# Options of `git push` that consume the following token, so a value is never
# mistaken for a refspec -- nor, in _push_re_heads() below, for the
# --dry-run/-n or --delete/-d exclusion (ai-config#1935). Shared with
# no-push-without-self-review.py, which binds these names from this module.
PUSH_OPTS_WITH_VALUE = {"--repo", "--receive-pack", "--exec", "-o", "--push-option",
                        "--recurse-submodules"}

# Short options that take a value, for the clustered form (`-qo ci.skip`).
SHORT_OPTS_WITH_VALUE = "o"

# git's parse-options accepts any UNAMBIGUOUS abbreviation of a long option, so
# every table here has to be matched through a resolver rather than by string
# equality. An earlier revision of no-push-without-self-review.py, which owned
# these tables before ai-config#1935 moved them here, hardened only `--repo`
# and left the rest exact, which was a fix to one site rather than to the
# class. Measured there on git 2.43.0, with no `remote.<name>.push` configured
# so only its indeterminate table could refuse them:
#
#   git push --all up   -> refused        git push --al up   -> ALLOWED
#   git push --mirror up-> refused        git push --mir up  -> ALLOWED
#   git push --tags up  -> refused        git push --ta up   -> ALLOWED
#
# and, defeating the value-aware parsing that guard's refspec walk depends on:
#
#   git push -o --repo=other   -> refused
#   git push --pu --repo=other -> ALLOWED   (`--pu` IS `--push-option`)
#
# `--al` ships every ref. So an unresolved abbreviation is not a cosmetic gap.
# Deliberately partial: it carries the options whose resolution CHANGES a
# verdict (in either hook), plus enough neighbours to make ambiguity match
# git's. `--ipv4` and `--ipv6` are absent, which is safe only because they
# take no value -- an unknown option is passed through, and a valueless one
# parses identically either way. A future value-taking option added in a
# namespace this set does not cover would diverge silently, so add it here
# when one appears.
PUSH_LONG_OPTS = frozenset({
    "--all", "--atomic", "--branches", "--delete", "--dry-run", "--exec",
    "--follow-tags", "--force", "--force-if-includes", "--force-with-lease",
    "--mirror", "--no-verify", "--porcelain", "--progress", "--prune",
    "--push-option", "--quiet", "--receive-pack", "--recurse-submodules",
    "--repo", "--set-upstream", "--signed", "--tags", "--thin", "--verbose",
    "--verify",
})

# Ambiguity is the reason this returns a sentinel rather than just resolving.
# `--re` matches --receive-pack and --recurse-submodules and git REFUSES it, so
# neither hook may silently pick one: no-push-without-self-review.py bails to
# indeterminate on it (the fail-closed direction for a refspec walk), and
# _push_re_heads below need not care, since the command never runs. Distinct
# from this file's `_AMBIGUOUS`, which marks a PR number seen in two repos.
AMBIGUOUS_OPTION = object()


def resolve_long_opt(head: str):
    """`head` resolved to the option git would read it as.

    Returns the full option name, AMBIGUOUS_OPTION when several match (git refuses
    those outright), or `head` unchanged when nothing matches -- an option this
    table does not know, left to be handled as it was before.

    `--no-<x>` is resolved against `<x>` and returned in its `--no-` form, since
    git accepts abbreviations there too (`--no-rep` is `--no-repo`).
    """
    if head in PUSH_LONG_OPTS:
        return head
    # No `--no-verify` special case is needed here: it is in PUSH_LONG_OPTS,
    # so the exact-match return above has already fired for it.
    negated = head.startswith("--no-")
    stem = "--" + head[len("--no-"):] if negated else head
    if stem in PUSH_LONG_OPTS:
        return head
    matches = {o for o in PUSH_LONG_OPTS if o.startswith(stem) and stem != "--"}
    if len(matches) > 1:
        return AMBIGUOUS_OPTION
    if not matches:
        return head
    full = matches.pop()
    return "--no-" + full[2:] if negated else full


def walk_push_options(rest):
    """Yield git's reading of each token after `push` as (kind, head, value).

    The one walk over git's push-option grammar that both this hook and
    no-push-without-self-review.py consume (ai-config#1935, #1920): this
    hook to decide whether the command re-heads anything, that one to find
    the refspecs it ships. Two hand-rolled walks disagreed about how git
    takes values, which is the class of bug both are meant to catch.

    kind "positional": `head` is the token; everything after a bare `--` is
    positional whatever it looks like (`refs/heads/-dash` is a valid ref).
    kind "option": `head` is the long option as git would read it, through
    `resolve_long_opt` (so an abbreviation resolves, and an ambiguous one
    is AMBIGUOUS_OPTION); `value` is the attached `=value`, or the next
    token when the option takes one, else None. kind "short": one letter of
    a cluster; a value-taking letter (`-o`) takes the rest of the cluster
    or, when it ends the cluster, the next token (`-on` is `-o` with `n`,
    `-qo ci.skip` is `-q` then `-o ci.skip`), and ends the cluster.
    """
    i = 0
    end_of_options = False
    while i < len(rest):
        tok = rest[i]
        i += 1
        if end_of_options or not tok.startswith("-") or tok == "-":
            yield ("positional", tok, None)
            continue
        if tok == "--":
            end_of_options = True
            continue
        if tok.startswith("--"):
            head, has_value, value = tok.partition("=")
            head = resolve_long_opt(head)
            if not has_value:
                value = None
                if head in PUSH_OPTS_WITH_VALUE:
                    value = rest[i] if i < len(rest) else None
                    i += 1
            yield ("option", head, value)
            continue
        letters = tok[1:]
        for position, letter in enumerate(letters):
            if letter in SHORT_OPTS_WITH_VALUE:
                value = letters[position + 1:]
                if not value:
                    value = rest[i] if i < len(rest) else None
                    i += 1
                yield ("short", letter, value)
                break
            yield ("short", letter, None)


def _push_re_heads(rest):
    """True unless the options after `push` say no ref is re-headed.

    `--dry-run`/`-n` performs no push at all, and `--delete`/`-d` removes a
    ref rather than advancing one, so neither leaves a new head to review.
    git reads these last-wins, so `--no-dry-run`/`--no-delete` after one of
    them restores the push (measured on git 2.43.0: `git push -n
    --no-dry-run origin main` moves the remote ref). The tokens come from
    `walk_push_options`, so `-n` as the value of `-o`, `-d` after
    `--receive-pack`, `-on`, and a positional after `--` are never read as
    the flag. After an ambiguous abbreviation (`--rec -n`) the answer is
    immaterial: git refuses the command, so no push happens either way.
    """
    re_heads = True
    for kind, head, _value in walk_push_options(rest):
        if kind == "option":
            if head in ("--dry-run", "--delete"):
                re_heads = False
            elif head in ("--no-dry-run", "--no-delete"):
                re_heads = True
        elif kind == "short" and head in "nd":
            re_heads = False
    return re_heads


def _argv_push(argv):
    """True if argv is a `git push` that genuinely re-heads a branch.

    Structural, exactly like _argv_request/_argv_draft: `git push` counts only
    as the argv of an actual `git` invocation, never as a quoted example inside
    another command's string argument (this hook's own docs and tests are full
    of literal `git push` text, which must not arm anything).

    Global options are skipped so `git -C <dir> push` and `git -c k=v push`
    are recognised. Two push forms are excluded because they do NOT re-head the
    branch, so no new head exists to review: `--dry-run`/`-n` performs no push
    at all, and `--delete`/`-d` removes a ref rather than advancing one --
    decided by _push_re_heads(), which walks option values rather than
    scanning for the bare tokens.
    """
    if not argv or argv[0] != "git":
        return False
    i = 1
    while i < len(argv):                 # skip git's own global options
        a = argv[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    if i >= len(argv) or argv[i] != "push":
        return False
    return _push_re_heads(argv[i + 1:])


def push_ident(cmd):
    """True if `cmd` contains a genuine `git push` simple command.

    Deliberately returns no `last` flag, unlike request_ident/draft_ident/
    close_ident/probe_ident. Those all decide a RELEASING change, which may fire
    only on positive evidence of its own success, so each needs to know whether
    the call's is_error belongs to it. Arming is the safe over-warn direction, so a
    push arms whether it succeeded or not -- a failed push that arms costs one
    warning, while waiting for proof would silently skip a real new head
    whenever the push shared a call with anything else (which, measured on this
    corpus, is nearly every push).

    Fails toward NOT-a-push on a parse error, so a malformed command never arms.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return False
    return any(_argv_push(a) for a in cmds)


def _argv_close(argv):
    """(is_close, num, repo) for one simple command's argv: a terminal action.

    Merging or closing a PR takes it past the point where requesting a reviewer
    means anything: GitHub ACCEPTS `POST /pulls/{n}/requested_reviewers` on a
    merged PR with HTTP 200 and adds nobody, so the obligation this guard
    reports becomes literally unsatisfiable and it re-fires forever
    (ai-config#1279, defect 3). A guard that cannot be satisfied trains everyone
    to narrate around it, which is how a guard stops being read at all.

    Structural and gh-SCOPED exactly like _argv_draft: the verb must be the argv
    of a real `gh pr` invocation, never a token inside some other command's
    string argument, so a `--body "gh pr merge"` cannot forge a discharge.
    Identity comes from the terminal command ITSELF, so a decoy PR number
    earlier in a chain cannot misdirect the clear onto a different PR.
    """
    if not argv or argv[0] != "gh" or len(argv) < 3 or argv[1] != "pr":
        return False, None, None
    if argv[2] in ("merge", "close"):
        num, repo = _verb_ident(argv)
        return True, num, repo
    return False, None, None


def close_ident(cmd):
    """(is_close, num, repo, last): does `cmd` merge or close a PR, and is that
    the LAST simple command?

    Mirrors draft_ident, including its fail-safe: `last` is what makes the
    harness `is_error` (the WHOLE call's exit status) authoritative for this
    command's own outcome, so a terminal action chained AHEAD of something else
    is treated as ambiguous and does NOT discharge. Fails toward
    not-a-close on a parse error, so it never fabricates a clear.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return False, None, None, False
    for i, argv in enumerate(cmds):
        ok, num, repo = _argv_close(argv)
        if ok:
            return True, num, repo, (i == len(cmds) - 1)
    return False, None, None, False


def _argv_probe(argv):
    """(is_probe, num, repo) for a read-only single-PR status read.

    `gh pr view <N>` / `gh pr checks <N>`. These discharge nothing by
    themselves -- they are only the CHANNEL through which a PR merged OUTSIDE
    this session (by a human, or by the merge queue) becomes visible in the
    transcript. The discharge additionally requires the result body to report a
    terminal state, and the probe must name a PR number, so a repo-wide
    `gh pr list` -- whose body mentions many PRs and whose first match need not
    be the obligation's -- is deliberately NOT a probe.
    """
    if not argv or argv[0] != "gh" or len(argv) < 3 or argv[1] != "pr":
        return False, None, None
    if argv[2] in ("view", "checks"):
        num, repo = _verb_ident(argv)
        return (num is not None), num, repo
    return False, None, None


def probe_ident(cmd):
    """(is_probe, num, repo, last): mirrors close_ident, for a status read."""
    cmds = _simple_commands(cmd)
    if cmds is None:
        return False, None, None, False
    for i, argv in enumerate(cmds):
        ok, num, repo = _argv_probe(argv)
        if ok:
            return True, num, repo, (i == len(cmds) - 1)
    return False, None, None, False


# --- Redaction exemption ---------------------------------------------------
# A REDACTION PR carries the thing being redacted on the REMOVED side of every
# hunk -- deleting the literal is the whole change -- so the reviewer's input IS
# the secret. `ucdavis/bcs#610` records the concrete failure: the `@claude`
# reviewer quoted a network user id back into a PR comment while reviewing the
# PR that redacted it. `ucdavis/bcs#614` then merged a `redaction-gate` job that
# skips AUTOMATIC AI review on such a diff -- and an explicit
# `requested_reviewers` POST, which is exactly what this guard demands, routes
# straight around that gate.
#
# Without an exemption the guard has no terminating state on such a PR
# (ai-config#1392): refusing does not discharge it, recording the refusal on the
# PR does not, and the maintainer deciding "hold, no AI reviewer" does not.
# Its only discharges were a successful request -- the exposure -- and draft
# status, which misstates the reason and stalls the PR's own ARDI loop
# (shared/workflow/pr-on-claim.md). A guard no correct action can satisfy is one
# its reader learns to narrate around, so the fix is a discharge path that a
# correct action reaches.
#
# Detection is deliberately NOT inferred from the diff. This hook reads a
# transcript, not a repository, so it cannot see the hunks; and a discharge is
# the DANGEROUS direction (shared/principles/fail-fast.md), so the exemption is
# narrow and explicit rather than guessed. Two forms, preferred first:
#
#   * A `no-ai-review` LABEL on the PR. This is the stronger of the two because
#     it is a real repository artifact rather than a session's say-so, and it is
#     load-bearing rather than a token invented for this hook: `ucdavis/bcs`'s
#     own `ai-code-review.yml` already honours it, so applying it actually
#     prevents the review as well as recording that it was withheld. Like every
#     other releasing path here it discharges only on POSITIVE evidence the
#     label landed (last/atomic, non-failed), so a repo with no such label --
#     where `gh pr edit --add-label` errors -- gets no discharge from it.
#   * An `ALLOW_UNREVIEWED_REDACTION_PR=1` env-assignment prefix, the shape
#     `no-handrolled-verdict-parse.py` and `no-whole-file-punct-replace.py`
#     already use, for a repo that has no such label. This is the "something a
#     session can ASSERT" form, needed because on a redaction PR the correct
#     action set and the previous discharge set were disjoint.
EXEMPT_LABEL = "no-ai-review"
EXEMPT_ENV = "ALLOW_UNREVIEWED_REDACTION_PR=1"
RX_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# The REST labels endpoint is issue-scoped even for a PR, so it needs its own
# pattern -- RX_CMD_API matches only `pull`/`pulls` paths.
RX_CMD_LABELS = re.compile(
    r"repos/([\w.-]+)/([\w.-]+)/issues/(\d+)/labels", re.I)


def _mutating_api(argv):
    """True if a `gh api` argv performs a write.

    `-X POST` is the explicit form, and it is NOT the only one: `gh api --help`
    states that the method "is `GET` normally and `POST` if any parameters were
    added", so `gh api .../labels -f 'labels[]=no-ai-review'` is a POST with no
    `-X` anywhere. Requiring `-X POST` alone would miss the shape gh's own
    examples use (`gh api repos/{owner}/{repo}/issues/123/comments -f body=...`).
    An explicit `--method GET` sends the same parameters as a query string, so
    it is a read and is excluded.
    """
    if _post_method(argv):
        return True
    for i, a in enumerate(argv):
        au = a.upper()
        if au in ("-X", "--METHOD") and i + 1 < len(argv) \
                and argv[i + 1].upper() in ("GET", "HEAD"):
            return False
        if au.startswith("--METHOD=") and au.split("=", 1)[1] in ("GET", "HEAD"):
            return False
    return _has_flag(argv, "-f", "--raw-field", "-F", "--field")


def _names_label(argv):
    """True if some argv token carries EXEMPT_LABEL as a whole label name.

    Whole-name matching, not a substring: a label called `no-ai-review-later`
    is a different label, and `--add-label a,b` is one token carrying two
    names. The value may arrive as `--add-label=x`, `labels[]=x`, or a bare
    following token, so the token is split on both `=` and `,`.
    """
    for a in argv:
        if any(part == EXEMPT_LABEL
               for part in a.split("=")[-1].split(",")):
            return True
    return False


def _pr_ident(argv):
    """(num, repo) for any PR-naming argv: a `gh pr <verb> <N>` or an API path.

    Wider than _verb_ident alone so the env-assertion form can be attached to
    whatever read the session was going to run anyway (`gh pr view`,
    `gh pr comment`, `gh api repos/o/r/pulls/N`), rather than to one blessed
    verb. Identity still comes from THAT command's own argv, never from a
    whole-string scan, so a decoy number elsewhere in the line cannot
    misattribute the exemption.
    """
    num, repo = _verb_ident(argv)
    if num is not None:
        return num, repo
    for t in argv:
        n, r = _url_ident(t)
        if n is not None:
            return n, r or repo
    return None, repo


def _argv_exempt(argv):
    """(kind, num, repo) for one simple command's argv; kind is None/label/env.

    Both forms are gh-SCOPED and structural, exactly like _argv_request: the
    label token counts only as the argument of a real label-adding invocation,
    and the env token counts only as an actual leading VAR=VALUE assignment.
    So a `--body "... --add-label no-ai-review ..."` explaining the exemption,
    or a doc line quoting `ALLOW_UNREVIEWED_REDACTION_PR=1`, cannot forge one --
    which matters more here than for most detectors, since this file, its tests,
    and the message text below all contain both literals.
    """
    if not argv:
        return None, None, None
    # Env-assertion form: one or more leading `VAR=VALUE` tokens, one of them
    # ours. shlex keeps an assignment as a single token, so a mention inside a
    # quoted string arrives as part of some LARGER token and never matches the
    # exact-equality test here.
    i = 0
    env_ok = False
    while i < len(argv) and RX_ENV_ASSIGN.match(argv[i]):
        if argv[i] == EXEMPT_ENV:
            env_ok = True
        i += 1
    if env_ok:
        num, repo = _pr_ident(argv[i:])
        return "env", num, repo
    # Label form: `gh pr edit <N> --add-label no-ai-review` (the label may sit
    # in a comma-separated list), or a POST to the issue-labels endpoint.
    if argv[0] != "gh" or len(argv) < 3:
        return None, None, None
    if argv[1] == "pr" and argv[2] == "edit" \
            and _has_flag(argv[3:], "--add-label") and _names_label(argv[3:]):
        num, repo = _verb_ident(argv)
        return "label", num, repo
    if argv[1] == "api" and _mutating_api(argv) and _names_label(argv):
        for t in argv:
            m = RX_CMD_LABELS.search(t)
            if m:
                return "label", m.group(3), f"{m.group(1)}/{m.group(2)}"
    return None, None, None


def exempt_ident(cmd):
    """(kind, num, repo, last): does `cmd` exempt a redaction PR from review?

    `last` is reported for the same reason request_ident reports it -- the
    harness `is_error` belongs to the whole call, so it is authoritative for the
    label form only when the label command is last. The ENV form does not
    consult it: that assertion is lexical and depends on no API outcome, so
    requiring the command it prefixes to succeed would make the escape hatch
    fail for a reason unrelated to the assertion, which is how a guard with no
    reachable discharge is reproduced one layer in.

    Fails toward no-exemption on a parse error, so a malformed command never
    discharges.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return None, None, None, False
    for i, argv in enumerate(cmds):
        kind, num, repo = _argv_exempt(argv)
        if kind:
            return kind, num, repo, (i == len(cmds) - 1)
    return None, None, None, False


def _exempt(obligations, live, num, repo):
    """Retire EVERY outstanding obligation for an exempted PR, and stop arming.

    Exemption is a property of the PR's CONTENT, not of one head: the removed
    side of the diff still carries the redacted literal after the next push, so
    unlike a reviewer request -- which is per-head -- this survives later pushes.
    Hence the pop from `live`, and hence retiring every obligation for the PR
    rather than the single best-ranked one _clear() removes. An open's
    obligation and a push's re-armed one can both be outstanding at once, and
    leaving one behind would reproduce the unsatisfiable state this exists to
    end.
    """
    if num is None:
        return
    obligations[:] = [o for o in obligations
                      if not (o["num"] == num and _repo_ok(o["repo"], repo))]
    live.pop(num, None)


def _argv_open(argv):
    """(is_open, num, repo) for one simple command's argv: a create/ready open.

    Structural and gh-SCOPED, exactly like _argv_draft/_argv_request. Identity
    comes from the open command ITSELF, so a decoy PR verb earlier in a chained
    command (`gh pr view 42 && gh pr ready`) cannot misattribute the obligation's
    number. A `gh pr create`'s number is never in the command -- it comes from
    the result -- so num is None for create; a `gh pr ready [<N>]` carries a
    number only when one is given explicitly (a bare `gh pr ready` yields None,
    backfilled from the ready command's own `owner/repo#N` result).
    """
    if not argv or argv[0] != "gh" or len(argv) < 3 or argv[1] != "pr":
        return False, None, None
    if argv[2] == "create":
        _, repo = _verb_ident(argv)
        return True, None, repo          # a create's number is in its result
    if argv[2] == "ready":
        num, repo = _verb_ident(argv)
        return True, num, repo
    return False, None, None


def open_ident(cmd):
    """(num, repo) from the actual `gh pr create`/`gh pr ready` simple command.

    Mirrors draft_ident/request_ident: the OPEN identity is located
    structurally from the create/ready command, never from the whole raw string.
    A whole-string search (the old cmd_ident) matched a decoy PR number from an
    unrelated verb chained ahead (`gh pr checks 1029 && gh pr ready`), mislabeled
    the obligation, and let a later unrelated request for that decoy PR silently
    discharge the real one. Returns (None, None) when no open command carries a
    number -- the bare `gh pr ready` case -- so the number backfills from the
    open's own result instead. Fails toward no-identity on a parse error.
    """
    cmds = _simple_commands(cmd)
    if cmds is None:
        return None, None
    for argv in cmds:
        ok, num, repo = _argv_open(argv)
        if ok:
            return num, repo
    return None, None


# Tools whose input is a SHELL COMMAND. Matching CLI patterns against any
# other tool's serialized input is the documentation/heredoc false positive
# README.md:265-271 warns about -- self-demonstrating here, since these very
# hook files contain the strings `gh pr create` and `requested_reviewers`.
SHELL_TOOLS = {"Bash", "bash", "run_command", "execute_command", "terminal", "shell"}

# Structured PR tools, matched on the tool NAME with arguments read as fields.
OPEN_TOOLS = {"create_pull_request", "mcp__github__create_pull_request"}
EDIT_TOOLS = {"update_pull_request", "mcp__github__update_pull_request"}
REQ_TOOLS = {"request_copilot_review", "mcp__github__request_copilot_review"}
# Structured tools that commit to a branch, re-heading whatever PR it backs.
PUSH_TOOLS = {"push_files", "mcp__github__push_files",
              "create_or_update_file", "mcp__github__create_or_update_file"}
CLOSE_TOOLS = {"merge_pull_request", "mcp__github__merge_pull_request"}

# A result body reporting that a PR has reached a terminal state -- merged or
# closed. Tolerates the escaped quotes of a json.dumps'd tool_result, exactly as
# RX_RES_NUM does. Only ever consulted for a result whose own command named a
# single PR (see _argv_probe), so a body listing many PRs cannot discharge an
# obligation for one of them.
RX_TERMINAL_STATE = re.compile(
    r"\\?\"state\\?\"\s*:\s*\\?\"(?:MERGED|CLOSED)\\?\""
    r"|\\?\"merged\\?\"\s*:\s*true"
    r"|\\?\"mergedAt\\?\"\s*:\s*\\?\"\d",
    re.I,
)

# A PR API path (`repos/o/r/pulls/1038`) inside a shell command, used by
# _url_ident to read identity from a request command's own `gh api` URL. Open,
# draft, and request identity are all resolved STRUCTURALLY from the specific
# simple command (open_ident/draft_ident/request_ident), never from a
# whole-string scan -- a decoy PR number chained ahead would otherwise mislabel
# the obligation (see open_ident).
RX_CMD_API = re.compile(r"repos/([\w.-]+)/([\w.-]+)/pulls?/(\d+)", re.I)

# A PR identity carried by a tool RESULT: the PR URL (owner/repo/number), gh's
# `Pull request owner/repo#N` success line, or a bare `"number"` field.
RX_RES_URL = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)", re.I)
RX_RES_API = re.compile(r"repos/([\w.-]+)/([\w.-]+)/pulls?/(\d+)", re.I)
# `gh pr ready`/`gh pr create` print `... Pull request owner/repo#N ...` (e.g.
# `Pull request o/r#42 is marked as "ready for review"`). A BARE `gh pr ready`
# (no number -- the ordinary way to ready the current branch's PR) carries no
# number in the command, so open_ident yields None and the obligation is
# appended with num=None. Without recognizing this result shape the number never
# backfills, and _clear() (which refuses to touch a num=None obligation) can
# never discharge it -- a bare `gh pr ready` would then block every message for
# the rest of the session, contradicting the "cannot wedge a session" invariant.
RX_RES_HASH = re.compile(r"[Pp]ull [Rr]equest\s+([\w.-]+)/([\w.-]+)#(\d+)")
RX_RES_NUM = re.compile(r"\\?\"number\\?\"\s*:\s*(\d+)")

# A tool result that reports failure. Kept specific: a bare 4xx substring
# matches PR numbers like 422 or a `/pull/430` URL, so failure is keyed on an
# HTTP-status shape or an explicit error word, plus the harness `is_error`
# flag when present.
RX_FAILED = re.compile(
    r"\\?\"status\\?\"\s*:\s*4\d\d|HTTP\s+4\d\d|\berror\b|\bfailed\b"
    r"|cannot be requested|not found",
    re.I,
)

# A request discharge must NOT be blocked by an UNRELATED command's failure
# text chained into the same Bash call (`some_check; gh api ... POST`, or
# `<request> || echo done`). RX_FAILED above matches generic `error`/`failed`/
# `not found` -- ordinary shell noise -- so a successful request sharing a
# result body with such text would nag forever. The discharge therefore keys
# on this NARROWER signal: an actual API-failure SHAPE (a 4xx status or GitHub's
# "cannot be requested"), plus the tool call's own is_error exit status. A
# genuinely failed `gh api`/`gh pr edit` request exits non-zero (is_error) or
# returns a 4xx, so this still catches every real failure without firing on a
# neighbouring command's stderr.
# The `\\?\"` before/after `status` tolerates the escaped-quote shape a string
# tool-result body takes once `json.dumps()` wraps it (`\"status\":422`), as
# well as an unescaped `"status":422`; without it this 4xx alternative was dead
# for the ordinary string-content case and only `HTTP 4\d\d`/`is_error` caught a
# failure. Mirrors RX_RES_NUM's `\\?\"` handling.
RX_REQ_FAILED = re.compile(
    r"\\?\"status\\?\"\s*:\s*4\d\d|HTTP\s+4\d\d|cannot be requested",
    re.I,
)


def input_ident(inp):
    """(num, repo) from a structured tool's input fields."""
    num = inp.get("pullNumber") or inp.get("pull_number")
    num = str(num) if num is not None else None
    owner, rp = inp.get("owner"), inp.get("repo")
    repo = f"{owner}/{rp}" if owner and rp else None
    return num, repo


def result_ident(body):
    """(num, repo) parsed from a tool_result body string."""
    m = RX_RES_URL.search(body) or RX_RES_API.search(body) \
        or RX_RES_HASH.search(body)
    if m:
        return m.group(3), f"{m.group(1)}/{m.group(2)}"
    m = RX_RES_NUM.search(body)
    if m:
        return m.group(1), None
    return None, None


def _new_obl(num, repo, tid, self_, slast, srnum, srrepo, push=False):
    """One outstanding-open record.

    `self_` marks an open whose SAME action also requested a reviewer, so the
    request's outcome is read from the open's own result. `slast`/`srnum`/`srrepo`
    carry that request's ordering and target so the `self` discharge can apply the
    same fail-safe guard as pending[tid] (discharge only on a last/atomic,
    same-PR, non-failed request). They are unread when `self_` is False.

    `push` marks an obligation re-armed by a push rather than by an open, so the
    warning can say the head moved instead of claiming the PR was never
    reviewed at all.
    """
    return {"num": num, "repo": repo, "tid": tid, "self": self_,
            "slast": slast, "srnum": srnum, "srrepo": srrepo, "push": push}


# A PR number seen in two DIFFERENT repositories. `live` is keyed by number
# alone -- deliberately, because a number's repo is often unknown at append time
# and backfills from the result, so keying by (num, repo) would file one PR
# under two keys and permanently suppress arming. The cost is that the same
# number in two repos collapses to one key, which would report ONE live PR when
# there are two and arm a push that is genuinely unattributable. Marking the
# number ambiguous keeps the exactly-one-live rule honest instead.
_AMBIGUOUS = object()


def _note_live(live, num, repo):
    """Record a PR this session opened or readied, once its number is known."""
    if num is None:
        return
    prev = live.get(num)
    if prev is _AMBIGUOUS:
        return
    if prev is not None and repo is not None and prev != repo:
        live[num] = _AMBIGUOUS      # same number, two repositories
        return
    live[num] = repo or prev


def _turn_transitions(blocks):
    """(PR number, tool_use_id) THIS turn drafts or retires; number None if
    unresolved.

    The arm and the transitions run on different clocks, and that difference is
    the whole defect. An arm fires synchronously while the tool_use is read; a
    draft or terminal transition is DEFERRED to its own tool_result, for the
    fail-safe reason that a releasing change may fire only on positive evidence
    it succeeded. So at the moment an arm fires, no transition from the same
    turn has been applied yet, and `live` still holds a PR the turn is about to
    retire.

    Scoping the check to the push's OWN command closed only the case where both
    sit in one chained Bash line. A turn can just as well carry them as separate
    tool_use blocks, and then neither order helps: read the push first and the
    sibling's transition is not registered yet, read it second and the
    transition is registered but still deferred. Asking about the TURN answers
    both, and subsumes the chained case, since the push's own block is one of
    the blocks examined here.

    A transition in an EARLIER turn is not a race: its tool_result arrives in
    the user message before the next assistant turn, so it has already been
    applied by the time any later arm fires.

    Returning a bare boolean was wrong, and wrong in the DANGEROUS direction. A
    turn-wide flag suppressed the arm for the live PR whenever any transition
    appeared anywhere in the turn, including one for a different, untracked PR
    -- the routine "merge an approved PR while still pushing fixes on the one I
    am driving" shape. That is a silent under-warn: the tracked PR gets a new
    head, nothing arms, and the guard never reports the very thing it exists
    for. So identity is resolved here exactly as every other function in this
    file resolves it, from the specific command rather than from anything else
    in the turn.

    `None` means a transition whose PR could not be resolved -- a bare
    `gh pr merge` or `gh pr ready --undo`, which act on the CURRENT branch's PR.
    Those suppress, on the same reasoning _note_drafted uses for the bare form:
    with one live PR the current branch's PR is that one.

    `gh pr create --draft` is deliberately NOT a target. It OPENS a new draft
    rather than transitioning a live PR, so treating it as one suppressed the
    arm for an unrelated PR that was never touched.

    Each transition carries its own tool_use_id, because knowing that a turn
    ATTEMPTED a transition is not knowing that the transition HAPPENED. The
    attempt is all this function can see -- it reads tool_use blocks, and a
    result exists for none of them yet -- so an arm suppressed on the attempt
    alone is suppressed on no evidence. A `gh pr ready --undo` that fails
    leaves the PR ready, unreviewed, and freshly re-headed by the push, which
    is the exact silent under-warn this hook exists to report. The id is what
    lets _rearm DEFER the decision to that transition's own result, the same
    way pending_clear and pending_close already defer their discharges.

    Fails toward "no transition" on anything unparseable, which only permits an
    arm -- the over-warn direction, per shared/principles/fail-fast.md.
    """
    out = []
    for b in blocks:
        if not isinstance(b, dict) or b.get("type") != "tool_use":
            continue
        name = b.get("name") or ""
        tid = b.get("id")
        inp = b.get("input")
        inp = inp if isinstance(inp, dict) else {}
        if name in CLOSE_TOOLS:
            out.append((input_ident(inp)[0], tid))
            continue
        if name in EDIT_TOOLS:
            if inp.get("draft") is True \
                    or str(inp.get("state") or "").lower() == "closed":
                out.append((input_ident(inp)[0], tid))
            continue
        if name in SHELL_TOOLS:
            cmds = _simple_commands(inp.get("command") or "")
            if cmds is None:
                continue
            for argv in cmds:
                ok, num, _repo = _argv_close(argv)
                if ok:
                    out.append((num, tid))
                    continue
                # `gh pr ready [<N>] --undo` only. The create form that
                # _argv_draft also matches opens a new PR instead.
                if len(argv) >= 3 and argv[0] == "gh" and argv[1] == "pr" \
                        and argv[2] == "ready" and _has_flag(argv[3:], "--undo"):
                    out.append((_verb_ident(argv)[0], tid))
    return out


def _note_drafted(live, num):
    """A PR went back to draft, so it leaves the live set and stops re-arming.

    The number is frequently absent: a bare `gh pr ready --undo` is the ordinary
    way to draft the CURRENT branch's PR, exactly as a bare `gh pr ready` is the
    ordinary way to ready it, so draft_ident yields num=None. Popping only on a
    known number would leave the entry in `live` and let a later push re-arm
    review for a PR that is legitimately drafted and needs none.

    With one live PR the bare form is unambiguous -- that PR is the one on the
    current branch -- so it is popped outright. With several, the transition
    cannot be attributed to any of them, and the honest answer is that `live` no
    longer supports the exactly-one-live rule _rearm depends on: every entry is
    marked ambiguous, which withholds arming rather than guessing which PR is
    still ready.
    """
    if num is not None:
        live.pop(num, None)
    elif len(live) == 1:
        live.clear()
    else:
        for key in live:
            live[key] = _AMBIGUOUS


def _mark_uncertain(live, uncertain, num):
    """Record that a transition may have retired a PR, without proof that it did.

    The number is frequently absent, for the reason _note_drafted gives: a bare
    `gh pr merge` or `gh pr ready --undo` is the ordinary way to act on the
    CURRENT branch's PR. The same tie-break applies here -- with one live PR the
    bare form is unambiguous, so that PR is the one marked.

    With several the transition cannot be attributed, and nothing is marked.
    That costs nothing: two or more live PRs already withhold the arm on their
    own, so there is no rival to de-count and no arm to rescue.
    """
    if num is None and len(live) == 1:
        num = next(iter(live))
    if num is not None:
        uncertain.add(num)


def _rearm(obligations, live, tid, turn_targets=(), pending_arm=None,
           uncertain=()):
    """Re-arm the reviewer obligation for the sole live PR, if a push earns it.

    Three gates, each of which alone withholds the arm:

      * EXACTLY ONE live PR, counting only the CERTAIN ones (see `uncertain`
        below). With none the push belongs to no tracked PR at all (the
        overwhelming majority of pushes -- a session that opened no PR must
        never be nagged). With two or more the push is unattributable, and
        arming every candidate would demand N requests for one push and wedge
        the session.
      * NO obligation already outstanding for that PR. Without this, N pushes
        between two requests stack N obligations that one request cannot clear,
        so the guard would nag forever after the user did exactly what it asked.
      * A number is known. An obligation with num=None can never be cleared by
        _clear(), so arming one would wedge the session.

    The synthetic `tid` can never equal a real tool_use_id, so a re-armed
    obligation is never mistaken for the open that a tool_result resolves.

    A same-turn transition targeting this PR DEFERS the arm rather than
    cancelling it. Suppressing outright treated the mere ATTEMPT as proof the
    PR was retired, and a transition that fails retires nothing: the PR stays
    ready, the push still re-headed it, and nothing would ever report it. That
    is the silent under-warn direction, and withholding an arm has the same
    effect as discharging one, so it owes the same positive evidence every
    other releasing path here owes (shared/principles/fail-fast.md). The
    candidate is parked under the transition's own tool_use_id and resolved by
    _resolve_arm when that result arrives.

    `uncertain` holds PRs a transition tried to retire without an attributable
    result. Membership in `live` answers two questions that pull in OPPOSITE
    safe directions once the answer is uncertain, which is why one flag cannot
    serve both:

      * "may a future push arm THIS PR?" -- keeping it is the over-warn
        direction, so an uncertain entry is still armable.
      * "does this entry make the push unattributable?" -- keeping it is the
        UNDER-warn direction, because a stale entry pushes the count past one
        and silently disables arming for every OTHER PR for the rest of the
        session.

    So an uncertain entry is skipped when counting rivals, and armed only when
    it is the sole live PR. A PR merged by a command chained ahead of a push no
    longer suppresses a later, unrelated PR's arm, while the sole-PR recovery
    that bounds the cost of ambiguity is kept.
    """
    certain = {n: r for n, r in live.items() if n not in uncertain}
    if len(certain) == 1:
        num, repo = next(iter(certain.items()))
    elif not certain and len(live) == 1:
        num, repo = next(iter(live.items()))
    else:
        return
    if num is None or repo is _AMBIGUOUS:
        return
    # This turn is drafting or retiring THIS PR, so the arm waits for that
    # transition's result. A transition for some OTHER PR is none of this
    # push's business and does not defer anything.
    hits = [t for (tnum, t) in turn_targets if tnum is None or tnum == num]
    if hits:
        if pending_arm is not None:
            for ttid in hits:
                pending_arm.setdefault(ttid, tid)
        return
    for ob in obligations:
        if ob["num"] == num and _repo_ok(ob["repo"], repo):
            return
    obligations.append(
        _new_obl(num, repo, "rearm:%s" % (tid,), False, False, None, None,
                 push=True))


def _resolve_arm(pending_arm, rid, failed, obligations, live, uncertain=()):
    """Settle an arm a same-turn transition deferred, now that its result is in.

    Fires only on POSITIVE evidence the transition FAILED. That asymmetry is
    deliberate, and it is narrower than "not confirmed to have succeeded":

      * FAILED -- the transition did not happen, so the PR is still ready and
        the push that re-headed it still owes a reviewer. Arm.
      * SUCCEEDED -- the PR is drafted or retired and owes nothing. Withhold.
      * AMBIGUOUS -- a transition chained ahead of another command shares one
        combined exit status, which belongs to the LAST command, so this call
        cannot attribute an outcome to the transition at all (the combined
        -result rule in shared/principles/fail-fast.md). Withhold, which is what
        the draft and terminal discharges in this same call already do on the
        same input: an ambiguous call changes nothing in either direction
        rather than acting on ambiguity in one of them.

    Withholding on ambiguity is bounded in a way a wrong discharge is not: the
    PR stays in `live` precisely because that same ambiguity withheld its own
    pop, so the NEXT push re-arms. The miss costs one push, not the session.

    _rearm re-runs its own gates here, so a sibling transition that succeeded
    earlier in this same result message has already removed the PR from `live`
    and no arm fires.
    """
    ptid = pending_arm.pop(rid, None)
    if ptid is not None and failed:
        _rearm(obligations, live, ptid, uncertain=uncertain)


def _repo_ok(a, b):
    return a is None or b is None or a == b


def _clear(obligations, num, repo):
    """Remove the best obligation a (num, repo) discharges, if any.

    Matches on PR number, preferring an exact owner/repo match over one where
    a side's repo is unknown. It deliberately does NOT clear an obligation
    whose own number is still unresolved: that would let a request for one PR
    silently discharge a different, unidentified one. A create's number is read
    from its result before any request could target it, so a resolved
    obligation is the normal state, and an unresolved one means a genuinely
    unparseable result -- which stays outstanding rather than being cleared by
    an unrelated request.
    """
    best, best_rank = None, 99
    for idx, ob in enumerate(obligations):
        if ob["num"] is not None and num is not None and ob["num"] == num \
                and _repo_ok(ob["repo"], repo):
            rank = 0 if (ob["repo"] and repo) else 1
            if rank < best_rank:
                best, best_rank = idx, rank
    if best is not None:
        obligations.pop(best)


def scan(path):
    """Return (obligations, text).

    `obligations` is a list of {"num", "repo", "tid", "self"} records, one per
    non-draft PR opened whose reviewer request has not been discharged.
    Tracked as a list (not a scalar timestamp or a number-keyed dict) so that
    two PRs, or the same number in two repositories, are two obligations.
    """
    obligations = []
    pending = {}        # tool_use_id -> (num, repo) for reviewer requests
    pending_clear = {}  # tool_use_id -> (num, repo) for draft transitions
    pending_close = {}  # tool_use_id -> (num, repo) for merge/close actions
    pending_probe = {}  # tool_use_id -> (num, repo) for single-PR status reads
    # tool_use_id -> (num, repo) for a `no-ai-review` label add, whose discharge
    # waits on positive evidence the label actually landed.
    pending_exempt = {}
    # transition tool_use_id -> the push tool_use_id whose arm it deferred. An
    # arm may not be cancelled by a transition that merely tried and failed.
    pending_arm = {}
    # PR numbers a transition tried to retire without an attributable result.
    # They stay armable on their own, and stop counting as rivals that would
    # make some LATER PR's push unattributable. See _rearm.
    uncertain = set()
    # num -> repo for PRs this session opened or readied and still open. A
    # PR leaves on a draft transition and on any terminal state, so a later
    # push never re-arms review for a PR that can no longer take one.
    live = {}
    text = ""
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            blocks = (m.get("message") or {}).get("content") or m.get("content") or []
            if isinstance(blocks, str):
                blocks = [{"type": "text", "text": blocks}]
            elif not isinstance(blocks, list):
                blocks = []
            else:
                blocks = list(blocks)

            if "tool_calls" in m and isinstance(m["tool_calls"], list):
                for tc in m["tool_calls"]:
                    if isinstance(tc, dict):
                        tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                        targs = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                        if isinstance(targs, str):
                            try:
                                targs = json.loads(targs)
                            except Exception:
                                targs = {"command": targs}
                        tid = tc.get("id") or str(id(tc))
                        blocks.append({
                            "type": "tool_use",
                            "id": tid,
                            "name": tname,
                            "input": targs if isinstance(targs, dict) else {},
                        })
            # Which PRs THIS turn drafts or retires, computed over the whole
            # turn before any of its blocks are read -- a sibling call is
            # invisible to the push's own command, in either block order. Only
            # a transition targeting the live PR defers its arm, and only that
            # transition's own result decides whether the arm is cancelled.
            turn_targets = _turn_transitions(blocks)
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                kind = b.get("type")

                if kind == "tool_result":
                    rid = b.get("tool_use_id")
                    body = json.dumps(b.get("content") or "")
                    err = bool(b.get("is_error"))
                    failed = err or bool(RX_FAILED.search(body))
                    rnum, rrepo = result_ident(body)
                    # Resolve the open that produced this result.
                    keep = []
                    for ob in obligations:
                        if ob["tid"] != rid:
                            keep.append(ob)
                            continue
                        # `failed` is one flag over the WHOLE result body, but a
                        # single call can pair opening a PR with requesting a
                        # reviewer (`gh pr create --reviewer` whose reviewer step
                        # 422s, or `update_pull_request(draft=False,
                        # reviewers=[...])` whose reviewer-add fails). A failure
                        # there must not be read as the PR never existing:
                        #   * failed, NOT a self create+reviewers obligation, AND
                        #     the PR's identity is STILL unknown (never in the
                        #     input, not in this result) -> the open itself is what
                        #     failed, no PR exists to track, so drop it. This is a
                        #     plain `create_pull_request`/`gh pr create`, whose
                        #     number is only ever learned from the result -- a
                        #     create that failed without yielding a number yielded
                        #     no PR.
                        #   * failed BUT the PR's identity is known -- resolved
                        #     here (a URL/number in the result) OR already known
                        #     from the input (`update_pull_request`'s
                        #     `pull_number`, populated at append time) -> the PR
                        #     is real and its reviewer step is what failed, so
                        #     keep tracking it and let the `self` check below hold
                        #     it outstanding. Dropping a known-identity obligation
                        #     on a bare `{"status":422}` body (no number echoed --
                        #     the ordinary error shape) would silently clear a PR
                        #     that was genuinely marked ready with no reviewer.
                        #   * failed AND self (a create+reviewers: `gh pr create
                        #     --reviewer`, `create_pull_request(reviewers=[...])`)
                        #     -> its number is NEVER known at append time, so a
                        #     numberless failure body cannot distinguish "the
                        #     create failed, no PR" from "the PR was created and
                        #     only the reviewer step failed". Dropping would
                        #     silently discharge a genuinely-created, unreviewed
                        #     PR (the dangerous direction), so it is NOT dropped
                        #     here: it falls through to the `self` check below and
                        #     stays outstanding. The cost is a rare unclearable
                        #     (num-None) obligation when the create truly failed --
                        #     a safe over-warn, per shared/principles/fail-fast.md,
                        #     chosen over a silent discharge.
                        if failed and rnum is None and ob["num"] is None \
                                and not ob["self"]:
                            continue
                        if ob["num"] is None and rnum:
                            ob["num"] = rnum
                        if ob["repo"] is None and rrepo:
                            ob["repo"] = rrepo
                        # A create's number is knowable only here, so this is
                        # where most PRs enter the live set.
                        _note_live(live, ob["num"], ob["repo"])
                        # A `self` obligation (an open whose SAME action also
                        # requested a reviewer -- `gh pr create --reviewer`,
                        # `create_pull_request(reviewers=[...])`, or a create
                        # chained with a request in one Bash call) discharges only
                        # on POSITIVE evidence the reviewer request itself
                        # succeeded, the same fail-safe rule the pending[tid] path
                        # below uses. For the shell path `self` comes from
                        # request_ident scanning the WHOLE command, so the matched
                        # request may be a NON-LAST simple command (its own failure
                        # masked by a trailing success) or target a DIFFERENT PR
                        # than the one opened. So discharge only when that request
                        # was the LAST/atomic simple command (`slast`, so the
                        # coarse `failed` reflects IT rather than a trailing
                        # command) AND names THIS PR (`srnum` None -- the create's
                        # own reviewer or a current-branch edit -- or equal to the
                        # resolved number). Otherwise keep it tracked (the safe
                        # over-warn direction). A structured create/edit is atomic
                        # (slast=True) and targets its own PR, so it is unaffected.
                        if ob["self"]:
                            same_pr = (ob["srnum"] is None
                                       or ob["srnum"] == ob["num"])
                            if ob["slast"] and not failed and same_pr:
                                continue
                            keep.append(ob)
                            continue
                        keep.append(ob)
                    obligations[:] = keep
                    # Discharge the reviewer request that produced this result.
                    # A discharge is the DANGEROUS action -- it asserts the PR
                    # got its reviewer -- so it fires only on POSITIVE evidence
                    # the request itself succeeded, never merely on the absence
                    # of failure text.
                    #
                    # The one reliable success signal is the harness `is_error`
                    # exit status, but it is the exit status of the WHOLE Bash
                    # call -- its LAST simple command -- so it is authoritative
                    # for the request ONLY when the request is that last command
                    # (`last`), or when the call is a single structured tool
                    # (atomic, recorded with last=True). A request chained AHEAD
                    # of anything else has an is_error belonging to a later
                    # command, and no other signal recovers the request's own
                    # outcome from the one combined result blob -- RX_REQ_FAILED
                    # catches a 4xx body but not a network error, a timeout, a
                    # 5xx, or a GraphQL/auth failure. Such a call is therefore
                    # AMBIGUOUS, and the guard fails toward NOT discharging (it
                    # keeps blocking -- the safe over-warn direction) rather than
                    # risk silently clearing a genuinely-failed request.
                    #
                    # So discharge only a last/atomic request whose own result
                    # neither errored nor carries a 4xx failure body.
                    if rid in pending:
                        rnum2, rrepo2, last2 = pending.pop(rid)
                        req_failed = (not last2) or err \
                            or bool(RX_REQ_FAILED.search(body))
                        if not req_failed:
                            _clear(obligations, rnum2 or rnum, rrepo2 or rrepo)
                    # A deferred draft transition clears its PR only on POSITIVE
                    # evidence the transition itself succeeded -- a clear is the
                    # DANGEROUS action (it asserts the PR is now a draft and
                    # needs no reviewer), so it obeys the same fail-safe rule the
                    # reviewer-request discharge above does.
                    #
                    # `is_error`/`failed` is the WHOLE call's exit status, so it
                    # is authoritative for the transition ONLY when the draft
                    # action is the last simple command (`clast`) or an atomic
                    # structured tool. A `gh pr ready --undo` that genuinely
                    # fails but is chained AHEAD of a succeeding command (e.g.
                    # `... --undo; echo done`, or `... --undo || true`) has an
                    # is_error belonging to that later command -- so such a call
                    # is AMBIGUOUS and must NOT discharge (keep the PR tracked --
                    # the safe over-warn direction), never silently clear a
                    # still-ready, unreviewed PR.
                    #
                    # For the last/atomic case the BROAD `failed` (not the
                    # narrower RX_REQ_FAILED the request side uses) is
                    # deliberate: for a clear, over-warning is the SAFE direction,
                    # so a broader failure signal is strictly safer here -- per
                    # shared/principles/fail-fast.md, prefer keeping the over-warn
                    # rather than narrowing it to cut nags.
                    if rid in pending_clear:
                        cnum, crepo, clast = pending_clear.pop(rid)
                        clear_failed = (not clast) or failed
                        if not clear_failed:
                            _clear(obligations, cnum, crepo)
                            _note_drafted(live, cnum)
                            uncertain.discard(cnum)
                        elif failed:
                            # It certainly did NOT retire the PR.
                            uncertain.discard(cnum)
                        else:
                            # Non-last, non-failed: the outcome is unknowable,
                            # so the PR stays armable but stops blocking a
                            # later PR's arm.
                            _mark_uncertain(live, uncertain, cnum)
                        # This same result settles any arm the draft deferred:
                        # a draft that FAILED left the PR ready, so the push
                        # that re-headed it still owes a reviewer.
                        _resolve_arm(pending_arm, rid, failed, obligations,
                                     live, uncertain)
                    # A PR that MERGED or CLOSED is past the point where a
                    # reviewer request does anything: the POST this guard
                    # prescribes returns HTTP 200 on a merged PR and adds
                    # nobody, so the obligation cannot be discharged by
                    # complying with it (ai-config#1279, defect 3). Same
                    # fail-safe rule as the draft clear above -- the terminal
                    # action must be last/atomic and non-failed -- so a merge
                    # that failed, or one chained ahead of another command whose
                    # exit status is what `failed` really reflects, keeps the PR
                    # tracked. A bare `gh pr merge` names no number, so identity
                    # falls back to the result's own, exactly as the request
                    # discharge above does.
                    if rid in pending_close:
                        xnum, xrepo, xlast = pending_close.pop(rid)
                        # Same settlement as the draft clear above: a merge or
                        # close that FAILED retired nothing, so an arm it
                        # deferred is owed after all.
                        _resolve_arm(pending_arm, rid, failed, obligations,
                                     live, uncertain)
                        if xlast and not failed:
                            xnum, xrepo = xnum or rnum, xrepo or rrepo
                            _clear(obligations, xnum, xrepo)
                            # Terminal, so it can gain no further reviewable
                            # head: it leaves the live set, and no later push in
                            # this session re-arms review for it.
                            live.pop(xnum, None)
                            uncertain.discard(xnum)
                        elif failed:
                            uncertain.discard(xnum or rnum)
                        else:
                            # A terminal command chained ahead of something
                            # else. Whether it retired the PR is unknowable, so
                            # the entry stays for its own sake and stops
                            # counting against a later PR (see _rearm).
                            _mark_uncertain(live, uncertain, xnum or rnum)
                    # A PR merged OUTSIDE this session (by a human, or by the
                    # merge queue) leaves no action in the transcript -- only an
                    # observation. Discharged on POSITIVE evidence only: the
                    # probe named one PR, the read did not fail, and the body
                    # actually reports a terminal state.
                    if rid in pending_probe:
                        pnum, prepo, plast = pending_probe.pop(rid)
                        if plast and not failed and RX_TERMINAL_STATE.search(body):
                            _clear(obligations, pnum, prepo)
                            live.pop(pnum, None)
                    # A `no-ai-review` label exempts a redaction PR from the
                    # reviewer request, but only once the label has actually
                    # landed: a repo with no such label fails the add outright
                    # (`gh: label not found`), and a discharge on the ATTEMPT
                    # would clear the obligation while the PR carries no
                    # exemption at all. Same fail-safe shape as the draft and
                    # terminal discharges above, with the broad `failed` for the
                    # same reason -- over-warning is the safe direction here.
                    if rid in pending_exempt:
                        enum2, erepo2, elast2 = pending_exempt.pop(rid)
                        if elast2 and not failed:
                            _exempt(obligations, live, enum2 or rnum,
                                    erepo2 or rrepo)
                    continue

                if kind != "tool_use":
                    if kind == "text" and m.get("type") == "assistant":
                        if b.get("text", "").strip():
                            text = b["text"]
                    continue

                name = b.get("name") or ""
                tid = b.get("id")
                inp = b.get("input")
                if not isinstance(inp, dict):
                    inp = {}

                if name in OPEN_TOOLS:
                    if not inp.get("draft"):
                        num, repo = input_ident(inp)
                        # Structured tool: atomic (slast=True), and its reviewers
                        # field targets this PR's own number.
                        obligations.append(_new_obl(
                            num, repo, tid, bool(inp.get("reviewers")),
                            True, num, repo))
                        _note_live(live, num, repo)
                    continue
                if name in PUSH_TOOLS:
                    # These commit to a named branch, which re-heads whatever PR
                    # that branch backs. A write to the default branch is not a
                    # PR head, so it never arms.
                    if str(inp.get("branch") or "") not in ("", "main", "master"):
                        _rearm(obligations, live, tid, turn_targets,
                               pending_arm, uncertain)
                    continue
                if name in EDIT_TOOLS:
                    num, repo = input_ident(inp)
                    if str(inp.get("state") or "").lower() == "closed":
                        # Closing is terminal for review purposes, same as a
                        # merge. Atomic tool, so is_error reflects THIS change.
                        pending_close[tid] = (num, repo, True)
                        continue
                    if inp.get("draft") is False:
                        _note_live(live, num, repo)
                    if inp.get("draft") is True:
                        # Converting a ready PR back to draft defers review, but
                        # only if it SUCCEEDS. Clearing at tool_use time would
                        # forget a still-ready PR when the transition fails, so
                        # defer the clear to this call's own non-failed result.
                        # A structured tool is atomic -- one tool_use, one result
                        # -- so is_error reflects THIS transition: last=True.
                        pending_clear[tid] = (num, repo, True)
                    elif inp.get("draft") is False:
                        # Structured, atomic: slast=True, reviewers target num.
                        obligations.append(_new_obl(
                            num, repo, tid, bool(inp.get("reviewers")),
                            True, num, repo))
                    if inp.get("reviewers") and inp.get("draft") is not False:
                        # A structured tool call is atomic -- one tool_use, one
                        # result -- so is_error reflects THIS request, with no
                        # chained command to poison it: last=True -> trust err.
                        #
                        # But NOT when draft is False: that branch already
                        # appended a `self` obligation, whose discharge/keep is
                        # decided in the obligations loop by the BROAD `failed`
                        # (success -> discharge via the `self and not failed`
                        # drop; failure -> keep). Also registering `pending[tid]`
                        # here would add a SECOND discharge path for the same
                        # tid, keyed on the NARROWER RX_REQ_FAILED, that runs
                        # AFTER the obligations loop and `_clear()`s the very
                        # obligation the broad check just kept -- so a
                        # reviewer-add failing with plain-language text
                        # ("failed"/"error"/"not found") and no 4xx/HTTP shape,
                        # with is_error unset, would silently discharge a
                        # genuinely-unreviewed PR. The self-obligation path is
                        # sufficient and fail-safe on its own; the pending path
                        # is reserved for a reviewer-add with NO draft:false
                        # transition (a request against an already-ready PR).
                        pending[tid] = (num, repo, True)
                    continue
                if name in REQ_TOOLS:
                    rn, rr = input_ident(inp)
                    pending[tid] = (rn, rr, True)  # atomic; is_error is trusted
                    continue
                if name in CLOSE_TOOLS:
                    # Structured tool: atomic, so is_error reflects THIS merge.
                    cn, cr = input_ident(inp)
                    pending_close[tid] = (cn, cr, True)
                    continue
                if name not in SHELL_TOOLS:
                    continue  # never text-match a non-shell tool

                cmd_raw = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""
                # DETECTION (is this an open/draft?) blanks EVERY quote, since
                # `gh pr create`/`ready` is always a leading command word and a
                # quoted example must not forge an obligation. IDENTITY (which
                # PR) is resolved STRUCTURALLY from the specific simple command
                # by open_ident/draft_ident/request_ident -- never a whole-string
                # scan, which matched a decoy PR number chained ahead
                # (`gh pr view 42 && gh pr ready`) and mislabeled the obligation.
                cmd_open = _scrub_all(cmd_raw)
                draft = bool(RX_DRAFT.search(cmd_open))
                opened = bool(RX_OPEN.search(cmd_open)) and not draft
                onum, orepo = open_ident(cmd_raw)
                requested, rnum, rrepo, rlast = request_ident(cmd_raw)
                _dok, dnum, drepo, dlast = draft_ident(cmd_raw)
                pushed = push_ident(cmd_raw)
                # Draft is checked first: `gh pr ready --undo` matches RX_OPEN
                # too, and it is the draft action that decides. The clear is
                # deferred to the command's own non-failed result: a `gh pr
                # ready --undo` that fails leaves the PR ready, so clearing at
                # tool_use time would silently forget it.
                if draft:
                    # Identity and `last` come from the draft command ITSELF
                    # (draft_ident): a decoy PR verb earlier in the line cannot
                    # misdirect the clear onto the wrong PR, and a draft chained
                    # AHEAD of another command is seen as not-last (dlast=False),
                    # so the clear is withheld (is_error ambiguous). A draft form
                    # draft_ident does not resolve leaves dnum=None/dlast=False,
                    # which never clears -- the safe over-warn direction.
                    pending_clear[tid] = (dnum, drepo, dlast)
                elif opened:
                    # `self` carries the matched request's ordering (rlast) and
                    # target PR (rnum/rrepo) so the discharge can require the
                    # request to be last/atomic and same-PR -- a request from a
                    # non-last or different-PR command in a chained create combo
                    # must not silently discharge this open.
                    obligations.append(_new_obl(
                        onum, orepo, tid, requested, rlast, rnum, rrepo))
                    _note_live(live, onum, orepo)
                # A create --reviewer both opens and requests; its `self` flag
                # discharges it on the create's own result, so it is not also a
                # separate pending request here.
                if requested and not opened:
                    pending[tid] = (rnum, rrepo, rlast)
                # Terminal actions and status reads are registered regardless of
                # the branches above: `gh pr merge` is neither an open nor a
                # draft transition, and a `gh pr view` chained after a create
                # must still be able to report that PR merged later.
                cok, cnum, crepo, clast2 = close_ident(cmd_raw)
                if cok:
                    pending_close[tid] = (cnum, crepo, clast2)
                pok, pnum, prepo, plast = probe_ident(cmd_raw)
                if pok:
                    pending_probe[tid] = (pnum, prepo, plast)
                # A redaction PR must not reach an automated reviewer at all, so
                # its exemption is registered here, BEFORE the push arm below:
                # the env form takes effect immediately (it depends on no API
                # outcome), so a call that both asserts the exemption and pushes
                # finds an empty `live` and arms nothing.
                #
                # The label form waits for its own result, and that result can
                # only be attributed when the label add is the chain's LAST
                # simple command. So `<label add> && git push` does NOT
                # discharge: the push arms synchronously here, the label's
                # result is ambiguous (elast2 False), and the guard keeps
                # warning even though the label genuinely landed. That is the
                # safe direction, and it is deliberately NOT fixed by dropping
                # the `last` requirement -- doing so would read a later
                # command's exit status as the label add's own, which is the
                # silent-discharge class every other releasing path here
                # blocks. Run the label add on its own, exactly as
                # shared/workflow/pr-on-claim.md already requires of the
                # reviewer-request POST for the same reason; the reverse
                # ordering (`git push && <label add>`) also discharges, since
                # the label add is last.
                ekind, enum, erepo, elast = exempt_ident(cmd_raw)
                if ekind == "env":
                    _exempt(obligations, live, enum, erepo)
                elif ekind == "label":
                    pending_exempt[tid] = (enum, erepo, elast)
                # A push re-heads the PR, so the per-head reviewer request is
                # owed again. Checked last: a call that both pushes and requests
                # (`git push && gh api ... -X POST`) arms here and is discharged
                # by that same call's result, which is correct -- the request
                # came after the push. Arming needs no result, per push_ident.
                #
                # But NOT when the same call also drafts, merges, or closes a
                # PR. Those two transitions are DEFERRED to this call's result
                # while the arm fires here, synchronously, so a chained `gh pr
                # merge 1038 --squash && git push -u origin next-branch` would
                # arm 1038 off a `live` set the same call is about to empty.
                # That direction is not a harmless over-warn: a merged PR cannot
                # take a reviewer (ai-config#1279, defect 3), and when the
                # terminal command is not last its own discharge is withheld as
                # ambiguous, so the arm it raced would stand unsatisfiable. One
                # call cannot both retire a PR and owe review on it, so the arm
                # yields to the transition -- but only DEFERS to it, since a
                # transition that fails retires nothing (see _resolve_arm).
                if pushed:
                    _rearm(obligations, live, tid, turn_targets, pending_arm,
                           uncertain)
    return obligations, text


def main() -> int:
    # Checked before the transcript is read: while the moratorium stands there
    # is no request to demand, so there is nothing to scan for.
    if moratorium_active():
        return 0

    try:
        payload = json.load(sys.stdin)
        transcript = payload.get("transcript_path") or ""
        obligations, text = scan(transcript)
    except Exception:
        return 0  # fail open

    if not text or not obligations:
        return 0

    named = sorted({o["num"] for o in obligations if o["num"]}, key=int)
    which = ", ".join("#" + n for n in named) if named else "a PR"

    # An obligation re-armed by a push states a different fact from one armed by
    # an open -- the PR was reviewed, at a commit that is no longer its head --
    # so it gets its own lead paragraph. Both can be outstanding at once.
    pushed_only = all(o["push"] for o in obligations)
    lead = (
        "You pushed a new head to {w} in this session and no SUCCESSFUL "
        "reviewer request follows that push.\n\n"
        "A reviewer request is per-HEAD, not per-PR: an earlier round's "
        "request was answered at a commit that is no longer this PR's head, so "
        "nothing has read the code you just pushed. Nothing re-requests a "
        "reviewer on your behalf."
    ) if pushed_only else (
        "You opened or readied {w} in this session and no SUCCESSFUL "
        "reviewer request follows for it.\n\n"
        "Opening a PR auto-triggers the repo's own review workflow but does "
        "NOT summon Copilot, which reviews only when explicitly requested. The "
        "auto-triggered half is what disguises this: the PR shows "
        "review-shaped activity while nothing has read the diff."
    )

    # Sentinel scoped to this transcript AND this message, so a later session
    # ending with the same recap text does not silently skip the guard. The
    # mode is part of the key so a push re-arm is not suppressed by an earlier
    # open-block that happened to name the same PR from the same message.
    key = hashlib.sha256(
        (transcript + "\0" + text + "\0" + which + "\0" + str(pushed_only))
        .encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-unreviewed-pr-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            lead.format(w=which) + "\n\n"
            "Request it now, in this same message. Quote every placeholder -- "
            "an unquoted `<` is a shell redirect:\n\n"
            "    gh api \"repos/<owner>/<repo>/pulls/<N>/requested_reviewers\" "
            "\\\n      -X POST -f "
            "'reviewers[]=copilot-pull-request-reviewer[bot]'\n\n"
            "Then verify a review actually lands at the current head -- the "
            "request itself can 422, and a pending request can vanish from "
            "both `reviewRequests` and the GET endpoint (see "
            "memories/gh-cli.md):\n\n"
            "    gh pr view \"<N>\" --json reviews \\\n"
            "      --jq '[.reviews[] | select(.author.login | "
            "startswith(\"copilot\"))] | length'\n\n"
            "Two legitimate reasons to defer, and neither is silence:\n\n"
            "  * The PR is deliberately a DRAFT -- a draft does not trigger "
            "the review bot (see shared/workflow/pr-on-claim.md). Say so "
            "explicitly.\n"
            "  * The diff REDACTS a secret or a participant identifier. Then "
            "requesting a reviewer IS the exposure: the removed side of every "
            "hunk carries the thing being redacted, so the reviewer's input is "
            "the secret (ucdavis/bcs#610). Hold the AI review, say so on the "
            "PR, and record the exemption so this stops asking:\n\n"
            "        gh pr edit \"<N>\" -R \"<owner>/<repo>\" "
            "--add-label no-ai-review\n\n"
            "    where the repo honours that label, or, where it does not:\n\n"
            "        ALLOW_UNREVIEWED_REDACTION_PR=1 gh pr view \"<N>\" "
            "-R \"<owner>/<repo>\" --json number\n\n"
            "    Run the label add on its own: chained AHEAD of another "
            "command, it shares one exit status with that command, so its "
            "own outcome cannot be attributed and the exemption is "
            "withheld.\n\n"
            "Writing \"review owed\" into a recap does not discharge this."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
