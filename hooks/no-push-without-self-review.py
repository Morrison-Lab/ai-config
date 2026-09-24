#!/usr/bin/env python3
"""PreToolUse guard: require an adversarial self-review before `git push`.

Every self-review this corpus calls for is dispatched to a separate
`adversarial-reviewer` subagent rather than performed inline by the session
that wrote the diff (`shared/workflow/adversarial-self-review.md`). This guard
enforces the pre-push case.

THREE QUESTIONS, NOT ONE
------------------------
**WHO said it.** A transcript-wide search for the verdict phrase cannot work,
for the reason `no-handrolled-verdict-parse.py` documents (ai-config#1297):
this corpus quotes verdict vocabulary constantly. Here it was self-defeating
rather than merely unsound -- a `PreToolUse` deny reason is surfaced back into
the transcript as the blocked call's result, so one blocked push authorized
every retry after it, and `Read`ing any of this repo's prose did the same. So a
verdict is admitted from the `tool_result` of a subagent-dispatch call whose
named persona IS the reviewer, and only when that result is not an error.
Which tool names count as a dispatch is `AGENT_TOOLS` MINUS `TASK_OUTPUT_TOOLS`,
spanning harnesses -- Claude's `Agent`/`Task` and Codex's `spawn_agent` among
them. The subtracted names retrieve a dispatch's output instead of making one.
On the native path they reach a task-id gate rather than a persona check; on the
flat OMO records there is no such gate to reach, since nothing on that path
records task ids, so they reach nothing. See `TASK_OUTPUT_TOOLS`. A review that
never happened must block a push; a harness whose dispatch records this guard
cannot read must be taught to it, not left to present as the first. The two are
indistinguishable from inside this function, which is why the remedy is the
tool-name set rather than any softening here (ai-config#3707).
A second provenance is admitted alongside it: a `Bash` call matching this
file's own external-reviewer pattern, which today recognizes `agy --print`
and none of the other delegation CLIs.
Both are narrow for the same reason.
Neither admits a verdict read out of a file, or out of this guard's own denial.

**WHAT it said.** Restricting provenance does not make a phrase search sound
INSIDE the admitted body, which is the same #1297 failure one layer in: a
review whose closing note quotes the clean verdict it is withholding would be
read as clean. So the verdict is taken from the last line that IS a verdict
line -- anchored at line start, optionally as a heading -- and a quotation
mid-sentence is not one.

**WHAT it was about.** Provenance and content together still let one clean
verdict authorize unlimited later pushes of unrelated work. So the reviewer
states the commit it read as a `Reviewed-Commit: <sha>` line AFTER its verdict,
and this guard resolves what the push would actually ship and compares. That
comparison is the tie between the permission and the code: a later commit, a
`main` merge, a rebase, or a commit made by a subagent in a transcript this
guard cannot see all change what would be shipped and fail it. It also closes
the truncation hole, since a report cut short carries no fingerprint.

Resolving the shipped commits means reading the refspec, not just `HEAD`.
`git push origin other-branch` ships something the reviewer never saw, and an
earlier revision of this guard waved it through while its own docstring claimed
otherwise.

CONSEQUENCES FOR HOW THE REVIEWER IS DISPATCHED
------------------------------------------------
Dispatch it in the FOREGROUND (`run_in_background: false`): a background
dispatch returns an agent id rather than a report, so no verdict ever becomes
that call's result. This is also the Agent tool's own criterion -- the push is
waiting on the answer.

Re-dispatch FRESH for each re-review round, rather than resuming the finished
reviewer with `SendMessage` to its agent id. A resumed reviewer's verdict
arrives later as a task notification, not as that `SendMessage` call's result,
so this guard still sees only the earlier verdict it already cached from the
original foreground call and blocks the push -- even though the session that
sent the message may believe the re-review already happened and came back
clean. See `shared/workflow/adversarial-self-review.md`'s "Freshly dispatched,
not resumed" section for why a resumed reviewer also converges on its own
prior verdict, independent of this guard's visibility gap.

Review AFTER committing, which is where `shared/workflow/ardi.md` already puts
the pause point. A review of uncommitted work names a commit that does not
exist yet.

WHERE IT DELIBERATELY DOES NOT FIRE
------------------------------------
- `git push --dry-run` and `git push --delete` re-head nothing, so there is no
  diff to review. (This is `no-unreviewed-pr.py`'s `_argv_push` rule, reused
  rather than re-derived.)
- A command running `git` through another interpreter (`bash -c "git push"`,
  `ssh host git push`) is one simple command whose argv is not a push. Nothing
  here parses a nested shell.
- A command this guard cannot parse is treated as not-a-push -- the same
  fail-open direction as `main()`'s bare `except`, stated rather than silent: a
  guard that crashed closed would block every push in the session.
- The MCP write tools (`mcp__github__push_files`, `create_or_update_file`,
  `push_files`) commit straight to a remote branch with no local commit to
  fingerprint, so nothing here can check them. They are an open gap, tracked as
  ai-config#1929, not a decision that they are safe.
- A push whose every resolved push URL ends in an `EXEMPT_REPOS` entry
  (Morrison-Lab's mln, mlg and mlr) passes with no verdict and no override.
  Only a github.com URL (https or ssh) on a configured remote counts, and only
  for a plain push in a plain command (`[cd DIR &&] git ... [| tail N]`): no
  `-c`, no environment setting of any kind, and no ssh command, proxy, exec
  path or receive-pack program that could deliver the pack elsewhere. A
  push URL on any other host, a local path, a literal URL in the remote
  position, or anything else is still gated.

Authorized override: `ALLOW_UNREVIEWED_PUSH=1`, as an environment assignment on
the pushing command itself.

Scoping it to that command is the whole of the fix. An earlier revision searched
the WHOLE command line -- splitting on `&&`/`;` and testing each segment -- so a
quoted mention of the override anywhere disarmed the guard, and this repo
documents that override in four files. Measured across revisions: with the
second `--allow-unreviewed-push` spelling neutered and only the env spelling
live, three of the four known bypasses still worked. So the second spelling was
not the cause; it is deleted because it was undocumented everywhere and
duplicated a variable that now has one meaning and one placement.

A `:branch` deletion refspec ships nothing, and so passes the commit comparison
-- but it still needs a clean verdict to reach that comparison, unlike
`--dry-run` and `--delete` in the block above, which are never examined at all.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

NO_WINDOW = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)} if sys.platform == "win32" else {}

# Save an independent duplicate of stdout (fd 1) as early as possible, so that
# any subsequent closure, poisoning, or redirection of fd 1 (e.g. from open(1))
# does not silence a denial decision into a silent allow (ai-config#3756).
try:
    _ORIGINAL_STDOUT_FD: int | None = os.dup(1)
except Exception:
    _ORIGINAL_STDOUT_FD = None

_DENIAL_ISSUED: list[bool] = [False]

# --- what counts as a verdict ----------------------------------------------

# Anchored at line start, optionally as a Markdown heading. Anchoring is what
# separates a verdict from a sentence quoting one, which a bare `Verdict:`
# search cannot do -- see this module's docstring.
VERDICT_LINE = re.compile(
    r"^[ \t]{0,3}(?:#{1,6}[ \t]*)?Verdict[ \t]*:[ \t]*(?:\*\*)?"
    r"(Ready for merge|Needs (?:more )?work)\b",
    re.I | re.M,
)

# A fenced block is quoted material, so a verdict inside one is an example
# rather than a verdict. Blanking fences before matching is what makes the
# anchoring above mean anything: `> ` is already excluded by the prefix class,
# and four-space indentation by the `{0,3}` bound, but a fence can hold a line
# that is anchored and indented exactly like the real thing.
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,}).*$", re.M)

# An inline code span is also quoted material. Blanking code spans ensures
# that literal comment openers (like `<!--`) or spoofed verdict lines inside
# inline code are not mistaken for live HTML comments or verdicts.
# Matches backtick runs of equal length that do not span blank lines,
# per CommonMark (ai-config#3961).
CODE_SPAN = re.compile(
    r"(?<!`)(`+)(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
)

# The reviewer's statement of what it read, required to appear AFTER the
# verdict it belongs to: that ordering is what makes a truncated report fail,
# and it is why this is searched forward from the verdict rather than globally.
REVIEWED_COMMIT = re.compile(
    r"\*{0,2}Reviewed-Commit\*{0,2}[ \t]*:[ \t]*\*{0,2}[ \t]*`?([0-9a-fA-F]{7,40})`?",
    re.I,
)

# Matched against an Agent/Task call's `subagent_type` ONLY. An earlier revision
# also matched the call's free-text `prompt`, which any prompt containing the
# word "adversarial" satisfied. A plugin-namespaced name
# (`ai-config:adversarial-reviewer`) is accepted -- the same persona is the same
# reviewer whichever surface registered it.
ADVERSARIAL_AGENT_NAME = re.compile(
    r"\A\s*(?:[\w.-]+[:/])?adversarial[-_ ]?reviewer\s*\Z", re.I
)

# When no dedicated `adversarial-reviewer` persona is registered in the
# environment (e.g. built-in subagents or automated sessions), allow
# fallback subagents whose prompt requests adversarial review.
FALLBACK_AGENT_NAME = re.compile(
    r"\A\s*(?:[\w.-]+[:/])?(?:general[-_ ]?purpose|general|reviewer|code[-_ ]?reviewer|research|self)\s*\Z", re.I
)

REVIEW_PROMPT_RE = re.compile(
    r"\b(?:adversarial[-_ ]?(?:self[-_ ]?)?review|pre[-_ ]?push[-_ ]?review|self[-_ ]?review)\b", re.I
)

# Tool names that dispatch a subagent, lowercased. Membership here does not
# authorize anything on its own: the dispatch's persona must still match
# ADVERSARIAL_AGENT_NAME (or FALLBACK_AGENT_NAME plus a review prompt), the
# verdict must still come back as that call's own non-errored result, and the
# `Reviewed-Commit` fingerprint must still resolve and cover what the push
# ships. So this set decides which harnesses the guard can SEE, not which
# reviews it trusts.
#
# `spawn_agent` is Codex's native subagent interface. Its absence was the whole
# of ai-config#3707: a Codex session dispatched the reviewer, got a clean report
# naming the exact commit, and was denied for never having dispatched a reviewer
# at all.
#
# The two spellings have DIFFERENT standing, and conflating them is what an
# earlier revision of this comment did. `spawn_agent` is attested in this
# repository, by `TOOL_ALIASES` in `plugins/ai-config/codex-hook-adapter.py`.
# `collaboration.spawn_agent` is the name ai-config#3707's reporter used for the
# interface in prose; nothing here has measured it as the name a Codex
# TRANSCRIPT carries, and the adapter cannot match it, since `matcher_hits` does
# an exact dict lookup. It is listed anyway because a name that Codex never
# emits costs nothing -- membership admits no verdict on its own -- while its
# absence would reproduce #3707. Replace it with a measurement when one exists;
# ai-config#3741 tracks that, and the adapter gap it implies.
#
# That earlier revision also claimed this was the only missing half of the
# alias. It is not: sibling hooks gate on their own hard-coded subagent
# tool-name sets that omit `spawn_agent` entirely, so they are silently inert
# in a Codex session -- the Fable prohibition among them. Tracked as
# ai-config#3740 rather than fixed here.
#
# The adapter's copy and this one are deliberately not shared: the adapter maps
# a live payload's tool name onto a matcher, this reads names out of a
# transcript, and a Codex rename would want re-attesting on both paths rather
# than propagating silently through one constant.
AGENT_TOOLS = {
    "agent", "task", "invoke_subagent", "taskoutput", "task_output",
    "manage_task",
    "spawn_agent", "collaboration.spawn_agent",
}

# The subset of AGENT_TOOLS that RETRIEVES a dispatch's output rather than
# making one. The distinction decides provenance, so it cannot be left implicit.
#
# For a dispatching tool the persona names who will run. For one of these the
# persona field is decorative -- `task_id` names whose output is coming back --
# so admitting one on its label alone severs the WHO-said-it chain this module
# is built on. Measured: a background `Agent` dispatch of `doc-writer` returning
# `{"task_id": "T7"}`, followed by `taskoutput({"task_id": "T7", "persona":
# "adversarial-reviewer"})` whose result is a well-formed clean report, yielded
# a clean verdict with no reviewer having run.
#
# That hole PRE-DATES the persona-key widening -- `name` was already read, and
# reproduces it on origin/main -- so this is not a regression introduced here;
# ai-config#3742 tracks the pre-existing variant. It is closed here because the
# widening turned one spelling into three, and because a diff asserting that
# nothing downstream is relaxed owes the check.
#
# `manage_task` is here on INFERENCE, not measurement, and it is the one entry
# whose standing differs from its neighbours -- said plainly because the
# `collaboration.spawn_agent` note above discloses its own gap, and a disclosed
# neighbour makes an undisclosed one read as checked. The repository's only
# evidence is `memories/antigravity.md:151`, `plugins/ai-config/rules/ai-config.md:28`
# and `memories/preferences.md:118`. The first two show `Action='status'`; the
# third names the tool with no `Action` at all ("lists harness-managed background
# tasks"). So all three describe retrieval and none covers creation, which is the
# conclusion -- but "all of which show `Action='status'`" was how this comment put
# it, and that was false for one of the three (ai-config#3737 round 6). A comment
# whose whole purpose is to state its evidence has to state it exactly, or it
# reads as checked while resting on a file that says something else.
#
# The name and that `Action` parameter both suggest the tool also creates,
# which is the risk this listing forecloses. Listing it here therefore
# CHANGES behaviour for a `manage_task` reviewer dispatch, from admitted to
# denied. That direction is the safe one for an authorization guard, and it is
# not free: the denial such a session gets is #3707's own misleading one. It is
# listed anyway because discriminating on the payload would readmit the bypass
# (a retrieval call can carry a decorative `prompt` as easily as a decorative
# persona). ai-config#3746 tracks measuring it and giving that case its own
# denial; `codex_cases` pins the current behaviour either way.
TASK_OUTPUT_TOOLS = {"taskoutput", "task_output", "manage_task"}

# Spellings a harness may use for a background task's id, read by BOTH ends of
# the dispatch chain: the result that announces a task (the producer, which puts
# the id into `reviewer_task_ids`) and the retrieval call that names one (the
# consumer, which tests membership). They share one tuple because they are two
# ends of a single chain -- a spelling present at one end and missing at the
# other denies a review that genuinely ran, with #3707's own misleading message,
# and that is exactly how `taskId` was missed: the consumer read it, the
# producer did not. An earlier comment here asserted the two already agreed;
# they did not, and stating an invariant is not enforcing one (ai-config#3737
# round 6). Widening the producer cannot admit anything, since the set is built
# only from reviewer dispatch results.
#
# `agentId` is in the tuple because it is the ONE spelling this repository
# has actually observed in a live session: `shared/workflow/adversarial-self-review.md`
# records a Claude Code CLI result reading `agentId: a29a955ac15b38f72`, four
# genuine reviews refused on the strength of it, and a one-line widening
# proposed on ai-config#3045. The first revision of this constant rewrote both
# ends of that exact chain and still omitted the spelling the measurement named
# -- the tuple was assembled from what the code already read rather than from
# what the corpus had already recorded (ai-config#3737 round 7).
# The generic `id` is split out, because it is the one spelling that is not
# self-evidently a task id. Under the earlier first-wins producer it was a LAST
# RESORT, reached only when no specific spelling was present. Registering every
# spelling instead made it a peer, and a low-entropy value safe as a fallback is
# not safe as a peer: a dispatch result carrying `{"task_id": "REAL", "id": "7"}`
# then trusted `7`, so an unrelated task-output call numbered 7 authorized the
# push. Measured against `d25ea1e`: base DENY, widened ALLOW, with three
# controls denying on both sides (ai-config#3737 round 9).
#
# The same argument is already written thirty lines below, as the reason
# `TASK_ID_KEYS_ORIGIN` omits the key. It was not applied to this constant.
TASK_ID_KEYS_SPECIFIC = ("task_id", "taskId", "TaskId", "conversationId", "agentId")
TASK_ID_KEYS_GENERIC = ("id",)
TASK_ID_KEYS = TASK_ID_KEYS_SPECIFIC + TASK_ID_KEYS_GENERIC

# The task-notification `origin` envelope gets a NARROWER list, deliberately.
# `origin` identifies a notification, so its `id` is the notification's own id
# rather than the task's -- a different identifier space, and admitting it would
# test membership for a value that was never a task id. The other four mean the
# same thing here as above. This is the one site where the sets legitimately
# differ, and the reason is the payload's meaning rather than an oversight.
TASK_ID_KEYS_ORIGIN = ("task_id", "taskId", "TaskId", "conversationId")


def _task_ids(source, keys=TASK_ID_KEYS):
    """Every task-id spelling present in `source`, as `str`, in `keys` order.

    Returning only the FIRST spelling is the gap the shared tuple above could
    not close on its own, and the comment there used to imply it had. A real
    harness result carries several id keys at once, so a producer registering
    one of them and a retrieval naming another miss each other -- the same
    denial the shared tuple exists to prevent, reached by a different route,
    and one the suite could not see because its fixture built single-key dicts
    on both ends (ai-config#3737 round 7).

    Neither guard below is decorative. A malformed `tool_input` yields a list
    or a string here, and `.get` on it would raise `AttributeError` out into a
    generic handler reporting "Failed reading transcript" rather than
    evaluating the session. The `str()` coercion is equally load-bearing: a
    harness reporting an id as a JSON number on one end and quoting it as text
    on the other must still match.
    """
    if not isinstance(source, dict):
        return []
    out = []
    for k in keys:
        v = source.get(k)
        if v:
            out.append(str(v))
    return out


def _registrable_task_ids(source):
    """The ids a reviewer dispatch result may be TRUSTED for, most specific first.

    Asymmetric with `_task_ids` on purpose. The consumer reads every spelling
    of its OWN input, which is not a trust decision -- it asks "is any id I
    name already trusted?". The producer decides what BECOMES trusted, so the
    generic `id` stays a last resort here: taken only when no specific spelling
    is present, exactly as the first-wins producer took it.

    Relaxing a lookup from first-match to any-match makes every previously
    shadowed key independently trusted, which is a change to the set's SAFETY
    rather than only its completeness. Dropping `id` altogether would close the
    collision and reopen the false denial this chain exists to prevent, since a
    result whose only id key is `id` would then register nothing.
    """
    specific = _task_ids(source, TASK_ID_KEYS_SPECIFIC)
    return specific if specific else _task_ids(source, TASK_ID_KEYS_GENERIC)


def _first_task_id(source, keys=TASK_ID_KEYS) -> str:
    """The first task-id spelling present in `source`, as a `str`, else ""."""
    ids = _task_ids(source, keys)
    return ids[0] if ids else ""

# A cross-family reviewer invoked as a CLI, whose print-mode output IS its
# review. Each value lists the flags putting that program in non-interactive
# print mode, so an interactive session -- whose transcript carries no
# response -- cannot be mistaken for a review.
#
# Accepting these lets `when-to-orchestrate`'s cross-family verify
# recommendation reach the one check that most wants it, and gives a session at
# its own quota ceiling a reviewed-push path at all.
#
# Only flags this repository has attested against the real CLI belong here.
# `--print` and `-p` are both recorded in `memories/antigravity.md`; a plausible
# third spelling was dropped rather than shipped on inference, since a flag that
# does NOT mean print mode would let an interactive run count as a review.
EXTERNAL_REVIEWER_PRINT_FLAGS = {
    "agy": ("--print", "-p"),
}

# The ONE accepted shape, matched against the raw command text:
#
#     agy --print 'a prompt naming the review'
#
# The prompt must be SINGLE-quoted, which is what makes this sound. Bash
# performs no expansion or substitution inside single quotes and no character
# escapes them, so every metacharacter in there is literal and the quoted run
# ends at the next `'`. Anchoring to the whole string then leaves nowhere for a
# second command to live.
#
# Matching raw text rather than `shlex.split` output is the sixth adversarial
# finding against this check, and the reason is worth keeping: `shlex.split`
# splits on WHITESPACE only and knows nothing of `;`, `&&`, `|` or `&`. So
#
#     agy --print adversarial-self-review;evilbin
#
# is three words to `shlex` and two commands to bash, and the second one's
# stdout joins the first's in the tool result the verdict is read from.
#
# The separators are `[ \t]`, NOT `\s`. Python's `\s` matches `\n`, and a
# newline is one of bash's own statement separators, so `\s` between the
# program and its flag accepted
#
#     agy
#     --print 'a prompt naming the review'
#
# as one command while bash ran two --- invoking the real reviewer with no
# argument at all, and putting a second statement's output in the same tool
# result. Found by the seventh adversarial round. Space and tab are bash's own
# default IFS, and are the only separators that keep one command one command.
EXTERNAL_REVIEWER_COMMAND_RE = re.compile(
    r"\A[ \t]*(?P<program>[A-Za-z0-9_.-]+)"
    r"[ \t]+(?P<flag>--print|-p)"
    r"[ \t]+'(?P<prompt>[^']*)'[ \t]*\Z")

def external_reviewer_command(command: str) -> bool:
    """Is this Bash command a cross-family reviewer run whose output is its review?

    The guard is sound because the harness produces the tool result and a
    session cannot fabricate one. That property survives the move to a CLI
    reviewer only if the COMMAND is verified rather than the text of its
    result: scanning the transcript for a `Reviewed-Commit:` line would be
    satisfied by typing `echo`, which is the discharge
    `shared/workflow/algorithmatize-checks.md` says to refuse to ship rather
    than to weaken.

    So the command must be ONE CANONICAL SHAPE, compared rather than parsed:

        agy --print 'a prompt naming the review'
        agy -p 'a prompt naming the review'

    A recognized reviewer, a print-mode flag attested against the real CLI, and
    a SINGLE-QUOTED prompt naming the review, matched against the whole raw
    command. Anything else is refused.

    The single quotes carry the weight. Bash expands nothing inside them and no
    character escapes them, so the quoted run ends at the next `'` and every
    metacharacter within it is literal; anchoring the match to the whole string
    then leaves nowhere for a second command to live.

    That severity is the point, and it was expensive to learn. Five successive
    adversarial review rounds each produced a working end-to-end bypass of a
    laxer rule, and every round after the first was defeated by the fix for the
    round before it:

        1. the keyword in a trailing `#` comment, against a match on the raw
           command text
        2. the keyword in a decoy trailing argument, against a match on any
           positional
        3. the keyword in the first of two `--print` flags, where a last-wins
           parser delivers the second
        4. the keyword behind a mid-word `#`, where a second comment rule
           deleted the second `--print` and made an ambiguous command read as
           an unambiguous one
        5. a comment truncated to end of string rather than end of line, hiding
           `echo` lines whose forged verdict the report parser read as the last

    All five were one defect: the matched text was not the delivered prompt.
    Each fix modelled another program's argument grammar from outside that
    program, closing one instance while feeling like it closed the class.

    A shape comparison ends that. It has no model of how `agy` parses anything,
    so there is no model to be wrong.

    A sixth round then showed why the shape must be compared against the RAW
    command rather than against `shlex.split` output. `shlex` splits on
    whitespace alone and knows nothing of bash's operators, so

        agy --print adversarial-self-review;evilbin

    is three words to it and two commands to bash, and the second program's
    stdout joins the first's in the very tool result the verdict is read from.
    An unquoted word cannot be certified by counting words.

    The cost is real and deliberate. Refused: a double-quoted prompt, since
    bash expands `$(...)` inside one; `$'...'`, whose leading `$` is outside
    the quotes; a leading `cd /x &&`; any extra flag, `--model` included; and a
    prompt supplied on stdin. A prompt containing an apostrophe is refused too,
    which is the sharpest edge here. Run the `cd` as its own earlier command,
    pass the prompt as one single-quoted argument, and reword an apostrophe.

    Refusing `--model` means this path cannot select a model, so an invocation
    needing a specific one falls back to the in-family dispatch. That is worth
    revisiting only with an attested flag and a shape that keeps this
    property, never by loosening the quoting.

    Two residues this accepts rather than closes, stated because a guard that
    hides its own limits is worse than one that names them.

    The session composes the prompt, so it can steer toward the verdict it
    wants. The in-family path shares that: it takes its brief from the same
    session and applies `REVIEW_PROMPT_RE` to it. The difference favours the
    in-family path, whose `prompt` field is exactly what the subagent receives,
    while this is a pre-expansion shell word -- a variable or substitution can
    still make the delivered prompt differ from the word that matched.

    The program name is resolved from `PATH`, so a script named `agy` earlier
    on `PATH` satisfies this. That one IS new, since the in-family path names a
    `subagent_type` the harness resolves. Accepted deliberately (user decision,
    2026-09-06, on #3209): forging it costs writing an executable that prints a
    verdict, which is a decision to defeat the guard rather than a shape a
    session falls into by accident.
    """
    match = EXTERNAL_REVIEWER_COMMAND_RE.match(command)
    if match is None:
        return False
    if match.group("flag") not in EXTERNAL_REVIEWER_PRINT_FLAGS.get(
            match.group("program"), ()):
        return False
    return bool(REVIEW_PROMPT_RE.search(match.group("prompt")))

OVERRIDE_ENV = re.compile(r"\AALLOW_UNREVIEWED_PUSH=1\Z")

# Degraded mode only, where the shell parser is unavailable and the strict
# argv-scoped check cannot run. Deliberately loose: with no parser this guard
# can only report that it is broken, so a false ALLOW here costs nothing a
# working guard would have caught, while a false DENY has no escape at all --
# a PreToolUse deny is not user-overridable.
DEGRADED_OVERRIDE = re.compile(r"(?:^|[;&|`(\s])ALLOW_UNREVIEWED_PUSH=1\s")

# Repositories whose pushes this guard does not gate at all, as lowercase
# `owner/repo`. A push is exempt only when EVERY URL it would push to names one
# of these (see `push_is_exempt`), so the list narrows the guard by
# destination and never by what the command says about itself.
#
# Morrison-Lab's DATA 571 course repositories, at the owner's request
# (2026-09-23): their agent sessions push feature branches under a standing
# grant, and the harness there backgrounds every reviewer dispatch, so the
# guard could never see a verdict (ai-config#3045) and every push ended in the
# override. A constant rather than an environment variable or a file in the
# pushed repository, because both of those are writable by the session the
# guard is checking; widening this list is a reviewed change to this file.
EXEMPT_REPOS = frozenset({
    "morrison-lab/mln",
    "morrison-lab/mlg",
    "morrison-lab/mlr",
})

# `owner/repo` of a push URL, accepted only on github.com: `https://` (with
# or without credentials), scp-style `git@github.com:owner/repo`, or
# `ssh://git@github.com/owner/repo`. Each form takes exactly the separator git
# itself reads it with -- `git@github.com/owner/repo` is a local path to git,
# and `ssh://git@github.com:owner/repo` drops the owner from the path it
# requests -- so neither is matched. Matching the trailing path alone let one
# inline `-c remote.origin.pushurl=https://any.host/x/Morrison-Lab/mln` read
# as exempt while shipping somewhere else, so the host is part of the match.
# The host is case-insensitive, as DNS is; any other host or a local path is
# never exempt.
_URL_OWNER_REPO = re.compile(
    r"(?:(?i:https://(?:[^@/\s]+@)?github\.com/)"
    r"|(?i:git@github\.com:)"
    r"|(?i:ssh://git@github\.com/))"
    r"([^/:\s]+)/([^/:\s]+?)(?:\.git)?/*")

# Options after which no single reviewed commit can describe the push.
# `--branches` is git's own documented alias of `--all` (`git push -h`), so it
# ships every branch while looking like an ordinary unknown option.
PUSH_OPTS_INDETERMINATE = {"--all", "--branches", "--mirror", "--tags",
                           "--follow-tags"}

# `--recurse-submodules` in these modes pushes commits in ANOTHER repository,
# which no fingerprint naming a commit in this one can describe.
SUBMODULE_PUSH_MODES = {"on-demand", "only"}

# The config forms of PUSH_OPTS_INDETERMINATE. Each entry is (key, the flag it
# mirrors, a predicate on the configured value). `{remote}` is filled from the
# resolved remote and the entry is skipped when no remote resolves.
def _is_true(v: str) -> bool:
    return v.strip().lower() in {"true", "yes", "on", "1"}


# (key, the flag it mirrors, a predicate on the value, read-as-boolean).
# The last field matters: a valueless key is true to git and prints empty
# under a plain `--get`, so a boolean entry has to be read with `--bool`.
CONFIG_LIKE_INDETERMINATE_FLAGS = (
    ("remote.{remote}.mirror", "--mirror", _is_true, True),
    ("push.followTags", "--follow-tags", _is_true, True),
    ("push.recurseSubmodules", "--recurse-submodules",
     lambda v: v.strip().lower() in SUBMODULE_PUSH_MODES, False),
)


# --- push detection, borrowed rather than re-derived ------------------------
#
# `no-unreviewed-pr.py`'s detector is shell-parsed rather than regex-matched, so
# it already handles `git -C <dir> push` and `git -c k=v push`, already excludes
# the two push forms that re-head nothing, and is already tested there. A second
# hand-rolled detector would be a DRW finding and would diverge silently
# (ai-config#1920) -- an earlier revision of this file wrote one as a "fallback"
# and it did diverge, on all three of those points. So there is no fallback
# parser: if the sibling cannot be loaded this guard never grades pushes with
# a worse one. It applies only the narrow degraded-mode heuristic in main()
# to decide whether to report the broken installation and deny a command
# whose text looks like a push (ai-config#2981).

def _load_sibling():
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-unreviewed-pr.py")
    spec = importlib.util.spec_from_file_location("no_unreviewed_pr", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    _SIBLING = _load_sibling()
    _SIBLING_ERROR = None
except Exception as exc:  # covered by orphan_cases() in
                          # test-no-push-without-self-review.py, which runs a
                          # copy of this file in a directory without the sibling
    _SIBLING = None
    _SIBLING_ERROR = str(exc)

# The walk over git's push-option grammar, its tables, and the abbreviation
# resolver live in the sibling and are bound here rather than declared twice
# (ai-config#1935, #1920): the sibling decides whether a command is a push at
# all, and that decision reads values and abbreviations exactly as this
# file's refspec walk must, so one walk keeps the two halves of the decision
# from disagreeing about how git's CLI works. With no sibling the names stay
# unbound: every path that consults them sits behind the deny that a missing
# sibling triggers.
if _SIBLING is not None:
    walk_push_options = _SIBLING.walk_push_options
    resolve_long_opt = _SIBLING.resolve_long_opt
    AMBIGUOUS_OPTION = _SIBLING.AMBIGUOUS_OPTION


def _load_review_payload():
    try:
        from scripts.lib.review_payload import (
            extract_review_payload,
            payload_is_blocking,
        )
        return extract_review_payload, payload_is_blocking
    except ImportError:
        pass
    repo_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    lib_dir = os.path.join(repo_root, "scripts", "lib")
    path = os.path.join(lib_dir, "review_payload.py")
    if os.path.isfile(path):
        try:
            if lib_dir not in sys.path:
                sys.path.insert(0, lib_dir)
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            spec = importlib.util.spec_from_file_location("scripts.lib.review_payload", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                extract_fn = getattr(module, "extract_review_payload", None) or getattr(module, "extract_structured_review", None)
                blocking_fn = getattr(module, "payload_is_blocking", None)
                if extract_fn and blocking_fn:
                    return extract_fn, blocking_fn
        except Exception:
            pass
    return None, None


try:
    _extract_review_payload, _payload_is_blocking = _load_review_payload()
except Exception:
    _extract_review_payload, _payload_is_blocking = None, None


def _load_native_path():
    """`scripts/lib/shellcmd.py`'s `native_path`, or the identity.

    The Bash tool on Windows is Git Bash, so a `-C` or `cd` target arrives as
    `/c/Users/...`, which native `git.exe` cannot open ("cannot change to
    '/c/Users/...'"). Every git call here would then fail, and a cross-repo
    push with a clean verdict was refused as unresolvable. The identity
    fallback reproduces that refusal rather than an allow, so a broken install
    fails in the safe direction.
    """
    lib_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                           "scripts", "lib")
    try:
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        from shellcmd import native_path
        return native_path
    except Exception:
        return lambda path, is_windows=None: path


_native_path = _load_native_path()


ENV_ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")


# Wrappers that run the command that follows them, so `git` is not argv[0] even
# though a push is exactly what happens.
COMMAND_WRAPPERS = {"env", "command", "nohup", "time", "exec", "builtin",
                    "sudo", "timeout", "stdbuf", "nice", "ionice", "doas"}

# Shell keywords that can open a simple command. The regex detector this file
# replaced carried these, and dropping them was a REGRESSION rather than a
# simplification: `_simple_commands` splits on `;` and `&&`, so the keyword
# becomes argv[0] of the segment holding the push. `skills/push/SKILL.md`
# prescribes a retry loop, so `do git push ...` is a shape this corpus asks for
# by name.
SHELL_KEYWORDS = {"!", "{", "}", "(", ")", "if", "then", "elif", "else", "fi",
                  "while", "until", "do", "done", "for", "case", "esac"}

# An unexpanded `$GIT`/`${GIT}` program token. shlex leaves it literal, so
# without this the command is not a push as far as argv is concerned.
GIT_VARIABLE = re.compile(r"\A\$\{?GIT\}?\Z")

# A duration argument, so `timeout 5 git push` does not stop the scan at `5`.
# How far past a wrapper to look for the git token. Six covers
# `sudo -u name -H git`, and bounds the scan so an unrelated command
# running git much later on the line is not mistaken for a wrapped push.
WRAPPER_ARG_WINDOW = 6


def _strip_env(argv: list[str]) -> tuple[list[str], list[str]]:
    """Split a simple command's leading env assignments and wrappers off its argv.

    shlex reports `FOO=1 git push` as three tokens, so the sibling's
    `_argv_push` (which requires `argv[0] == "git"`) never sees such a command
    as a push. The same is true of `env git push`, `command git push`, and an
    absolute `/usr/bin/git push`; the last is an ordinary invocation rather than
    an evasion. Splitting here is also what scopes the override to the pushing
    command rather than to any segment of the line.

    Returns (env assignments, argv with `git` first) -- the program token is
    normalized to its basename so the sibling's own check still applies.
    """
    rest = list(argv)
    env: list[str] = []
    after_wrapper = False
    while rest:
        tok = rest[0]
        if ENV_ASSIGNMENT.match(tok):
            env.append(tok)
            rest = rest[1:]
            after_wrapper = False
            continue
        if tok in COMMAND_WRAPPERS:
            after_wrapper = True
            rest = rest[1:]
            continue
        if tok in SHELL_KEYWORDS:
            after_wrapper = False
            rest = rest[1:]
            continue
        # A wrapper's own arguments, so `env -i`, `env -u FOO`, `timeout 5` and
        # `sudo -u someone` do not stop the scan before `git`. Enumerating each
        # wrapper's option grammar would be its own parser, so instead: look
        # ahead a bounded distance for the git token and drop what precedes it.
        # Nothing is consumed unless git is actually found, so a wrapper running
        # something else is left alone.
        if after_wrapper:
            window = rest[1:1 + WRAPPER_ARG_WINDOW]
            hit = next((i for i, t in enumerate(window, start=1)
                        if GIT_VARIABLE.match(t) or os.path.basename(t) == "git"), None)
            if hit is not None:
                rest = rest[hit:]
                continue
        break
    if rest:
        if GIT_VARIABLE.match(rest[0]) or os.path.basename(rest[0]) == "git":
            rest = ["git"] + rest[1:]
    return env, rest


def _depth_segments(command: str):
    """[(depth, segment_text)] -- split on operators, tracking PAREN depth.

    `_simple_commands` deliberately models no nesting, so an earlier revision
    approximated with `nested = "(" in command`, which is wrong twice over: a
    parenthesis inside a quoted string (a commit message reading "fix (typo)")
    discarded a legitimate hint, and `(cd elsewhere && git push)` -- where the
    `cd` DOES apply to the push -- was graded against the wrong repository.
    Depth is the fact that separates those, and it is not derivable from the
    sibling's output, so it is computed here rather than duplicating its parser.
    """
    segs: list[tuple[int, str]] = []
    depth = 0
    cur: list[str] = []
    in_single = in_double = escaped = False
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if escaped:
            escaped = False
            cur.append(c)
        elif c == "\\" and not in_single:
            escaped = True
            cur.append(c)
        elif c == "'" and not in_double:
            in_single = not in_single
            cur.append(c)
        elif c == '"' and not in_single:
            in_double = not in_double
            cur.append(c)
        elif in_single or in_double:
            cur.append(c)
        elif c in "()":
            segs.append((depth, "".join(cur)))
            cur = []
            depth += 1 if c == "(" else -1
            depth = max(depth, 0)
        elif c in ";&|\n" or command.startswith("&&", i) or command.startswith("||", i):
            segs.append((depth, "".join(cur)))
            cur = []
            if command.startswith(("&&", "||"), i):
                i += 1
        else:
            cur.append(c)
        i += 1
    segs.append((depth, "".join(cur)))
    return [(d, t.strip()) for d, t in segs if t.strip()]


def _blank_shell_redirections(command: str) -> str:
    """Blank unquoted shell redirections while preserving quoted arguments."""
    chars = list(command)
    i, n = 0, len(command)
    in_single = in_double = escaped = False
    while i < n:
        c = command[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if c == "\\" and not in_single:
            escaped = True
            i += 1
            continue
        if c == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if in_single or in_double:
            i += 1
            continue

        start = i
        if c.isdigit() and (i == 0 or command[i - 1].isspace()
                            or command[i - 1] in ";|&()"):
            while i < n and command[i].isdigit():
                i += 1
            if i >= n or command[i] not in "<>":
                i = start + 1
                continue
        elif c not in "<>" and not (c == "&" and i + 1 < n
                                      and command[i + 1] == ">"):
            i += 1
            continue

        # A herestring's operator and target are both shell syntax; blank
        # them like any redirection (checked before "<<", its prefix).
        if command[i:i + 3] == "<<<":
            i += 3
        # Leave heredocs to the sibling's existing body-aware
        # preprocessing.
        elif command[i:i + 2] == "<<":
            i += 2
            continue

        # Redirections are shell syntax, not git argv (ai-config#2477).
        # Three-character forms first: a fixed two-character window left
        # the third character to be absorbed as a bogus one-character
        # target, letting the real target leak into git argv (#2494
        # review round: &>>, <>, <<<).
        elif command[i:i + 3] == "&>>":
            i += 3
        elif command[i:i + 2] in (">>", ">&", "<&", "&>", "<>", ">|"):
            i += 2
        else:
            i += 1
        while i < n and command[i].isspace():
            i += 1
        quoted = None
        while i < n:
            if quoted:
                if command[i] == quoted:
                    quoted = None
                elif command[i] == "\\" and quoted == '"' and i + 1 < n:
                    i += 1
            elif command[i] in "'\"":
                quoted = command[i]
            elif command[i].isspace() or command[i] in ";|&()":
                break
            elif command[i] == "\\" and i + 1 < n:
                i += 1
            i += 1
        chars[start:i] = " " * (i - start)
    return "".join(chars)


def _resolve_cd_target(rest: list[str], cur_dir: str | None) -> str | None:
    """Resolve the directory after a `cd`, `pushd`, or `popd` command relative to `cur_dir`.

    Returns the new effective directory, or None if cleared / indeterminate.
    """
    cmd_name = rest[0]
    if cmd_name == "popd":
        # `popd -n` suppresses the directory change, leaving cur_dir untouched.
        if any(tok.startswith("-") and "n" in tok and tok != "-" for tok in rest[1:]):
            return cur_dir
        # Without a full dirstack simulation across commands, popd without -n clears the hint.
        return None

    # For `cd` and `pushd`: parse flags and positional directory target.
    i = 1
    target = None
    suppress_chdir = False
    while i < len(rest):
        tok = rest[i]
        if tok == "--":
            # End of options; next token (if present) is the target directory.
            if i + 1 < len(rest):
                target = rest[i + 1]
            break
        if tok == "-":
            # `cd -` switches to OLDPWD, which is indeterminate without shell state.
            return None
        if tok.startswith("+") or (tok.startswith("-") and tok[1:].isdigit()):
            # `pushd +N` or `pushd -N` rotates the directory stack.
            return None
        if tok.startswith("-"):
            # Flags like -P, -L, -e, -@ for cd, or -n for pushd
            if cmd_name == "pushd" and "n" in tok:
                suppress_chdir = True
            i += 1
            continue
        target = tok
        break

    if cmd_name == "pushd" and suppress_chdir:
        # `pushd -n <dir>` rotates/modifies stack without changing current working directory.
        return cur_dir

    if target is None:
        # Bare `cd` or `cd -P` with no directory defaults to $HOME (~).
        # For pushd with no args, it swaps top 2 stack entries (indeterminate -> None).
        if cmd_name == "pushd":
            return None
        target = "~"

    # Expand ~ and ~/path
    if target == "~" or target.startswith("~/"):
        target = os.path.expanduser(target)
    elif target.startswith("$HOME/") or target == "$HOME" or target.startswith("${HOME}/") or target == "${HOME}":
        home = os.path.expanduser("~")
        if target in ("$HOME", "${HOME}"):
            target = home
        elif target.startswith("$HOME/"):
            target = os.path.join(home, target[len("$HOME/"):])
        elif target.startswith("${HOME}/"):
            target = os.path.join(home, target[len("${HOME}/"):])
    elif "$" in target or "`" in target:
        # Unexpanded shell variables/substitutions cannot be resolved statically.
        return None

    # Before `isabs`: on Windows under Python 3.13, `isabs("/c/Users/x")` is
    # False, so a Git Bash drive path was joined onto `cur_dir` and then
    # normalized into a drive-less path nothing downstream could repair.
    target = _native_path(target)
    was_windows_drive_forward = bool(re.match(r"^[A-Za-z]:/", target))
    resolved = os.path.normpath(os.path.join(cur_dir, target) if cur_dir is not None else target)
    if was_windows_drive_forward:
        resolved = resolved.replace("\\", "/")
    return resolved


def _hints_by_position(command: str) -> list[str | None]:
    """One directory hint per push, in order, or [] when structure is unclear.

    A hint is the directory of the last `cd`/`pushd` at or above the push's own
    paren depth. Entering a subshell inherits the enclosing hint; leaving it
    discards whatever was set inside.
    """
    hints: list[str | None] = []
    stack: list[str | None] = [None]
    for depth, text in _depth_segments(command):
        while len(stack) <= depth:
            stack.append(stack[-1])
        del stack[depth + 1:]
        try:
            argv = shlex.split(text)
        except ValueError:
            return []
        if not argv:
            continue
        # Strip FIRST. Push detection three lines below already does, so a
        # `cd` behind a shell keyword (`while true; do cd other; git push`)
        # was invisible here while the push after it was still detected --
        # and that is the retry-loop shape `skills/push/SKILL.md` prescribes,
        # so it is reachable by ordinary use rather than only adversarially.
        _, rest = _strip_env(argv)
        if rest and rest[0] in ("cd", "pushd", "popd"):
            stack[depth] = _resolve_cd_target(rest, stack[depth])
            continue
        if rest and _SIBLING and _SIBLING._argv_push(rest):
            hints.append(stack[depth])
    return hints


# Ways a command points git at a repository other than the one a `-C` scan
# would find. Resolving them means reproducing git's git-dir/work-tree
# precedence, so the guard refuses instead -- see `iter_pushes`.
REPO_REDIRECT_OPTS = {"--git-dir", "--work-tree", "--namespace"}
REDIRECTS_REPO = re.compile(r"\A(?:GIT_DIR|GIT_WORK_TREE|GIT_NAMESPACE)=")

# Distinct from None, which means "the hook's own cwd" and is a real answer.
REDIRECTED = object()


# POSIX shlex treats an unquoted backslash as an escape, so
# `git -C C:\Users\foo\AppData\Local\Temp\npwsr-abc push origin main` parses as
# `-C C:UsersfooAppDataLocalTempnpwsr-abc`. The guard then rev-parses `main` in
# a directory that does not exist and reports that `main` could not be resolved
# to a commit --- every allow-case in this hook's suite on Windows 11 /
# Python 3.13 / Git Bash, measured against main at 47e49fd1 (ai-config#2037).
# Recovering the original backslashes after shlex has eaten them is not
# possible. Git accepts forward slashes on Windows, so rewriting the drive
# path before the parse is the recovery. A POSIX path has no drive-letter
# backslash run and is unchanged.
#
# The excluded-character class stops the match at any character a genuine
# path segment cannot plausibly contain: whitespace, the other shell
# separators already excluded, and --- added after ai-config#2325's review
# round --- `#`, `(`, `)`, the two quote characters, a backtick, and `$`.
# Without those five, the match ran through them: an escaped `\#` became an
# unescaped `/#`, which turned the rest of the line into a shlex comment and
# hid a real `git push --all` entirely; an escaped `\)` became a bare `)`,
# which is one of `_simple_commands`'s punctuation_chars and split a chained
# push in two, hiding the second; and with neither a quote character nor
# whitespace excluded, a match starting inside a quoted path ran straight
# through the closing quote into the next argument, turning an unrelated
# `--\all` into `--/all` and degrading a refused indeterminate push into an
# approved bare one. Verified against real bash (not just this module's own
# shlex-based simulation) for all three: `bash -c 'git(){ ...; }; git -C
# C:\a\)b push origin main'` executes a genuine, un-mangled push, and `git -C
# 'C:\repo' push --\all origin` resolves to the argv `--all` on its own,
# unquoted-backslash escaping already turning it into exactly that string
# before this module ever sees the command.
_WIN_PATH_CHARS = r"[^\s\\/;&|<>()#'\"`$]+"
_WIN_DRIVE_PATH = re.compile(r"[A-Za-z]:(?:\\" + _WIN_PATH_CHARS + r")+")

# A quoted span, single or double, matched so it can be skipped rather than
# rewritten. Real bash (confirmed by execution, not just read) already keeps
# a single-quoted backslash literal and a double-quoted one is only special
# before `$` `` ` `` `"` `\` or a newline --- so a quoted Windows path never
# had the backslash-eating bug this function exists to fix, and rewriting it
# anyway makes the guard verify a directory bash never asked for: on POSIX,
# `C:\repo` and `C:/repo` are two unrelated paths, not two spellings of one.
_QUOTED_SPAN = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")


def _posixize_windows_paths(command: str) -> str:
    """Rewrite an UNQUOTED `C:\\Users\\...` to `C:/Users/...`.

    Confined to text outside quotes; see `_QUOTED_SPAN` and `_WIN_DRIVE_PATH`
    above for why both restrictions are load-bearing rather than tidiness.
    """
    def rewrite(segment: str) -> str:
        return _WIN_DRIVE_PATH.sub(lambda m: m.group(0).replace("\\", "/"), segment)

    out = []
    pos = 0
    for m in _QUOTED_SPAN.finditer(command):
        out.append(rewrite(command[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(rewrite(command[pos:]))
    return "".join(out)


def iter_pushes(command: str):
    """Yield (env, argv, directory) for each `git push` simple command.

    `directory` is the push's own absolute `-C`, else the push's relative `-C`
    resolved within the directory a `cd`/`pushd` put it in (subshell scoping
    respected), else the `cd`/`pushd` directory, else None -- meaning the hook's
    own cwd. Both were previously read off the FIRST git command in the chain, so
    `git -C a status && git -C b push` graded the wrong repository.

    The sibling stays authoritative on WHETHER a command is a push. The
    positional hint list is used only when it agrees with the sibling on how
    many pushes there are; disagreement means this module's structural read and
    the sibling's parse have diverged, and a wrong directory is worse than none.

    `directory` is the sentinel REDIRECTED when the command points git at a
    repository this scan will not resolve. `--git-dir`/`--work-tree`, and their
    `GIT_DIR`/`GIT_WORK_TREE` environment forms, all send the push to another
    repository while leaving nothing for a `-C` scan to find, so the guard
    resolved HEAD in its OWN cwd and graded the wrong repo. Measured against
    two throwaway repos, the hook's cwd being repoA and the verdict naming
    repoA's HEAD:

        git --git-dir=repoB/.git --work-tree=repoB push origin main  -> allowed
        GIT_DIR=repoB/.git git push origin main                      -> allowed

    while the `-C` spelling of the same push was correctly denied. Resolving
    them properly means reproducing git's own git-dir/work-tree precedence, so
    this refuses instead, which is the direction the rest of the module takes
    when it cannot describe what a push ships.

    `-C` is also CHAINED by git -- each is applied relative to the last -- so
    the first one is not the answer when several appear (ai-config#1977).

    Windows drive paths are rewritten to forward slashes before either parser
    runs, so `_simple_commands` and `_hints_by_position` see the same command.
    """
    if _SIBLING is None:
        return
    # Join line-continuations BEFORE posixize. Otherwise a Windows CRLF
    # continuation (`\` + `\r\n`) is swallowed into the drive path (`/` + CR),
    # the leftover newline becomes `;`, and a real `git push` is no longer
    # detected --- fail-open. Measured on this change: `git -C C:\Users\...\`
    # plus CRLF plus `push origin main` yielded zero pushes after posixize
    # and one push (mangled directory, fail-closed) without it. `\r` is also
    # excluded from the path class so a stray CR cannot extend the match even
    # if this join were skipped. The sibling's `_simple_commands` runs the
    # identical `re.sub` again on its own copy of the command; that second
    # pass is a no-op once this one has already run, not a second parser to
    # keep in sync, so there is nothing left here for a future change to miss.
    command = re.sub(r"\\\r?\n", " ", command)
    command = _posixize_windows_paths(command)
    command = _blank_shell_redirections(command)
    cmds = _SIBLING._simple_commands(command)
    if not cmds:
        return
    pushes = []
    for argv in cmds:
        if not argv:
            continue
        env, rest = _strip_env(argv)
        if not rest or not _SIBLING._argv_push(rest):
            continue
        directory = None
        if any(REDIRECTS_REPO.match(tok) for tok in env):
            directory = REDIRECTED
        else:
            i = 1
            while i < len(rest) - 1:
                tok = rest[i]
                if tok == "-C" and i + 1 < len(rest):
                    # Chained: each -C is relative to the accumulated path.
                    # Converted here, not only in `_run_git`: the join above
                    # and the `isabs` test in the hint merge below both
                    # misread a Git Bash drive path.
                    value = _native_path(rest[i + 1])
                    directory = os.path.join(directory or "", value) \
                        if directory not in (None, REDIRECTED) else value
                    i += 2
                    continue
                head = tok.partition("=")[0]
                if head in REPO_REDIRECT_OPTS:
                    directory = REDIRECTED
                    break
                i += 1
        pushes.append((env, rest, directory))

    hints = _hints_by_position(command)
    if len(hints) != len(pushes):
        hints = [None] * len(pushes)
    for (env, rest, directory), hint in zip(pushes, hints):
        effective_dir = directory
        if effective_dir is REDIRECTED:
            yield env, rest, REDIRECTED
            continue
        if effective_dir is None:
            effective_dir = hint
        elif hint is not None and not os.path.isabs(effective_dir):
            # When -C is relative and an in-command cd/pushd established a working
            # directory, git applies -C relative to that directory.
            effective_dir = os.path.normpath(os.path.join(hint, effective_dir))
        yield env, rest, effective_dir


def has_allow_override(env: list[str]) -> bool:
    """True if the PUSHING command carries the override as an env assignment.

    Scoped to that command's own environment prefix, deliberately. A previous
    revision searched the whole command line, so `git push && echo
    'ALLOW_UNREVIEWED_PUSH=1'` -- or a commit message quoting this repo's own
    documentation of the override -- disarmed the guard.
    """
    return any(OVERRIDE_ENV.match(tok) for tok in env)


def push_refspecs(argv: list[str]) -> list[str] | None:
    """The refspecs a `git push` argv would ship; None if indeterminate.

    An empty list means the push names no refspec. What THAT ships is a
    `push.default` question rather than a fact about the command, which
    `shipped_commits` asks git rather than assuming.
    """
    # `positionals[0]` is dropped as the remote even when `--repo` supplied
    # one. `--repo` does NOT turn the positionals into refspecs -- an explicit
    # positional repository OVERRIDES it, which is git's documented "if both
    # are specified, the command-line argument takes precedence". Measured on
    # git 2.43.0, since a review of this line read it the other way and called
    # it a bypass:
    #
    #   git push --dry-run --repo=origin evil main
    #     -> fatal: 'evil' does not appear to be a git repository
    #   git push --dry-run --repo=origin main
    #     -> fatal: 'main' does not appear to be a git repository
    #   git push --dry-run --repo=/nonexistent origin main
    #     -> succeeds, pushing via `origin`; /nonexistent is never contacted
    #
    # So `--repo=origin main` is a BARE push to the repository named `main`,
    # and resolving it through push.default rather than through `main` is
    # correct. Regression rows: grep CASES and config_cases() for --repo.
    positionals = _push_positionals(argv)
    return None if positionals is None else positionals[1:]  # drop the remote


def _push_positionals(argv: list[str]) -> list[str] | None:
    """The positional arguments after `push` -- remote first; None if indeterminate."""
    return None if (parsed := _parse_push(argv)) is None else parsed[0]


def _parse_push(argv: list[str]) -> tuple[list[str], str | None] | None:
    """(positionals after `push`, the --repo value); None if indeterminate.

    `--repo` is read HERE rather than by a separate scan of argv, because the
    guards that make this walk correct are exactly the ones such a scan lacks.
    An earlier revision scanned raw argv for `--repo` and was permissive twice
    over, measured on git 2.43.0 against a repo whose `remote.pushDefault` was
    `alpha` and whose `remote.alpha.push` shipped every branch:

        git push --repo=zzz --no-repo   -> git pushes to alpha; the scan said zzz
        git push -o --repo=zzz          -> `--repo=zzz` is -o's VALUE, not an
                                           option; git pushes to alpha

    Both turned a correctly-refused push into an allowed one. This walk already
    classifies option values, so resolving `--repo` inside it cannot disagree
    with that classification -- but only for the spellings its tables know,
    which is why every long option is put through `resolve_long_opt` first. An
    earlier revision skipped that and `--pu --repo=X` walked straight back into
    the same hole, `--pu` being `--push-option`. `--no-repo` clears the value,
    as it does for git, and the last occurrence wins. The tokens come from the
    sibling's `walk_push_options`, the one walk both hooks read git's push
    grammar through (ai-config#1935).
    """
    try:
        idx = argv.index("push")
    except ValueError:
        return None
    positionals: list[str] = []
    repo: str | None = None
    for kind, head, value in walk_push_options(argv[idx + 1:]):
        if kind == "positional":
            positionals.append(head)
            continue
        if kind == "short":
            continue
        if head is AMBIGUOUS_OPTION:
            return None
        if head in PUSH_OPTS_INDETERMINATE:
            return None
        if head == "--recurse-submodules" and value in SUBMODULE_PUSH_MODES:
            return None
        if head == "--no-repo":
            repo = None
        elif head == "--repo":
            repo = value
    return positionals, repo


# This hook is registered with a 10s timeout in `hooks/hooks.json`, and a
# PreToolUse hook killed on timeout does not deny -- the push simply proceeds.
# So the budget is enforced here rather than left to the harness: one call per
# refspec times a generous per-call timeout would exceed it on a slow repo, and
# the failure would be a silent allow on the one path this guard exists to hold.
# Overridable so the timeout path is testable: it is the one branch whose
# failure direction (allow vs deny) cannot be observed any other way, and a
# mutation turning its refusal into an allow survived an untested suite.
BUDGET_SECONDS = float(os.environ.get("NPWSR_BUDGET_SECONDS", "6.0"))
PER_CALL_SECONDS = 3.0
_DEADLINE = [0.0]
_OMO_SEQ = [0]


def _run_git(directory: str | None, env: list[str], *args: str) -> str | None:
    """Run one git command inside the shared budget; None if it failed.

    EVERY git call goes through here, deliberately. An earlier revision budgeted
    only `_rev_parse` and let `_git_config`/`_rev_parse_ref` carry their own
    hardcoded timeouts, so the bare-push resolution path could spend six
    unbudgeted subprocess calls -- eighteen seconds against a ten-second
    PreToolUse timeout -- before reaching the one call that enforced the budget.
    A hook killed on timeout does not deny, so that reopened the silent allow
    this budget exists to prevent, on the newest path rather than the oldest.

    Sharing one helper is what makes that unrepeatable: a future call site
    cannot forget to check the deadline, because there is nowhere else to run
    git from.

    `env` is the PUSHING command's environment prefix, and it is required for
    the same reason. git takes config from the environment as well as from
    `-c` and from files: `GIT_CONFIG_COUNT` with `GIT_CONFIG_KEY_<n>` and
    `GIT_CONFIG_VALUE_<n>` is a documented override equivalent to `-c`. This
    process does not carry those, so a subprocess run under the hook's own
    environment reads different config than the push will. Measured on git
    2.43.0, with nothing on disk:

        GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.mirror \
        GIT_CONFIG_VALUE_0=true git push origin

    ships every branch, including an unreviewed one, while the guard allowed
    it. Enumerating that one variable would have been the fourth patch to the
    same class, so the overlay is applied wholesale instead: every git call
    runs under the environment the push will run under, which covers env-based
    overrides this file does not know about. `GIT_DIR` and friends are refused
    upstream rather than forwarded, since those redirect the repository.
    """
    remaining = _DEADLINE[0] - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("ran out of time resolving what this push would ship")
    overlay = dict(os.environ)
    for assignment in env:
        key, sep, value = assignment.partition("=")
        if sep:
            overlay[key] = value
    git_bin = "git"
    custom_path = overlay.get("PATH")
    if custom_path and custom_path != os.environ.get("PATH"):
        git_bin = shutil.which("git", path=custom_path) or "git"
    cmd = [git_bin] + (["-C", _native_path(directory)] if directory else []) + list(args)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, env=overlay,
                             timeout=min(PER_CALL_SECONDS, remaining),
                             **NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise TimeoutError("ran out of time resolving what this push would ship")
    except Exception:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _rev_parse(directory: str | None, env: list[str], rev: str) -> str | None:
    sha = _run_git(directory, env, "rev-parse", rev)
    return sha.lower() if sha and re.fullmatch(r"[0-9a-f]{40}", sha) else None


def _config_overrides(argv: list[str]) -> list[str]:
    """The pushing command's own `-c key=value` tokens, to forward to `git config`.

    `git -c remote.origin.mirror=true push` is process-local, so a separate
    `git config --get` subprocess cannot see it. Measured on git 2.43.0 with
    NO on-disk config: that command ships every branch, including an unreviewed
    one, while the guard's config read returned nothing.

    `--config-env=KEY=VAR` names an environment variable rather than a value,
    and this process may not carry it, so it is not forwardable. `main` refuses
    a push carrying one instead.
    """
    out: list[str] = []
    i = 1
    while i < len(argv) and argv[i] != "push":
        tok = argv[i]
        if tok == "-c" and i + 1 < len(argv):
            out += ["-c", argv[i + 1]]
            i += 2
            continue
        if tok.startswith("-c") and len(tok) > 2:
            out += ["-c", tok[2:]]
        i += 1
    return out


def _has_config_env(argv: list[str]) -> bool:
    """True if the command carries `--config-env`, which cannot be forwarded."""
    for tok in argv:
        if tok == "push":
            return False
        if tok == "--config-env" or tok.startswith("--config-env="):
            return True
    return False


def _git_config(directory: str | None, flag: str, key: str,
                argv: list[str], env: list[str],
                as_bool: bool = False) -> str | None:
    """A config value as the PUSHING git would see it.

    Two ways a plain `git config --get` reads something git does not.

    A valueless key is TRUE to git's boolean parser and prints EMPTY here, so
    `[remote "origin"]` + a bare `mirror` line read as unset. `--bool --get`
    normalizes it. Measured on git 2.43.0:

        git config --file t --get      remote.origin.mirror  -> '' (exit 0)
        git config --file t --bool --get remote.origin.mirror -> 'true'

    And an inline `git -c key=value push` is process-local to that invocation,
    so a separate `git config` subprocess never sees it. `--config-env` is not
    forwardable -- it names an environment variable this process may not carry
    -- and is refused upstream instead.

    `argv` is REQUIRED, and the overrides are derived here rather than passed
    in, because an optional `overrides=` parameter is exactly what a call site
    forgets. One did: `_push_remote`'s fallback chain read
    `remote.pushDefault` without them, so `git -c remote.pushDefault=alpha -c
    remote.alpha.push=... push` sent the real push to `alpha` while the guard
    resolved the literal `origin` and checked the wrong remote's keys. Every
    read now goes through this one function and cannot omit them.
    """
    args = _config_overrides(argv) + ["config"]
    if as_bool:
        args.append("--bool")
    return _run_git(directory, env, *args, flag, key) or None


def _push_remote(directory: str | None, argv: list[str],
                 env: list[str]) -> str | None:
    """The remote this push acts on, named or not.

    Returning None for a bare `git push` skipped the `remote.<name>.push` check
    in exactly the case it exists for: the command that names nothing is the one
    whose destination is decided entirely by config. So when the command does
    not spell the remote out, resolve the one git would use, in git's own
    precedence order.

    `--repo=<remote>` supplies the remote for a push that names no positional
    one, so it has to be consulted BEFORE that config chain -- reading it as a
    bare push resolved the wrong remote and skipped the `remote.<name>.push`
    check on a command that does ship other refs. Measured on git 2.43.0, in a
    repo whose `remote.other.push` is `refs/heads/*:refs/heads/*`:

        git push --dry-run --repo=other
          -> * [new branch]  feature -> feature      (an unreviewed ref)
             * [new branch]  main -> main

    while `git push other` was already refused. The positional still wins over
    `--repo` when both appear, which is git's documented precedence and is why
    it is checked first.
    """
    parsed = _parse_push(argv)
    if parsed is None:
        return None
    positionals, repo = parsed
    if positionals:
        return positionals[0]
    if repo:
        return repo
    branch = _rev_parse_ref(directory, env, "--abbrev-ref", "HEAD")
    for key in ((f"branch.{branch}.pushRemote",) if branch else ()) + (
            "remote.pushDefault",) + ((f"branch.{branch}.remote",) if branch else ()):
        value = _git_config(directory, "--get", key, argv, env)
        if value:
            return value
    return "origin"


def _owner_repo(url: str) -> str | None:
    """Lowercase `owner/repo` of a github.com push URL, or None."""
    m = _URL_OWNER_REPO.fullmatch(url.strip())
    return f"{m.group(1)}/{m.group(2)}".lower() if m else None


# What can send a push somewhere its URL does not name. `git remote get-url`
# reports the URL after `insteadOf`/`pushurl` rewriting, but a command git runs
# to reach it (an ssh wrapper, a proxy, a replaced remote helper, a
# `--receive-pack` program) can deliver the pack anywhere while git still
# prints the github.com URL. So a push that carries or inherits any of these is
# never exempt. Disabling TLS verification belongs here too: with it off, any
# HTTP proxy in the path can answer for github.com.
#
# An HTTP proxy and a custom CA bundle are deliberately NOT refused, because
# the cloud sessions this exemption exists for need both (HTTPS_PROXY and
# GIT_SSL_CAINFO are set in every one). The exemption therefore trusts the
# session's configured proxy and CA store. It is not a sandbox against a
# session that sets up a hostile transport in an earlier command: `main`
# already fails open on errors, MCP pushes are ungated (#1929), and the
# override exists, so that threat was never in this hook's scope.
TRANSPORT_ENV = frozenset({
    "GIT_SSH", "GIT_SSH_COMMAND", "GIT_SSH_VARIANT", "GIT_PROXY_COMMAND",
    "GIT_EXEC_PATH", "GIT_SSL_NO_VERIFY",
})
TRANSPORT_CONFIG = (r"^(core\.sshcommand|core\.gitproxy"
                    r"|remote\..*\.(receivepack|vcs)"
                    r"|http\.(.*\.)?sslverify)$")


def _is_plain_command(command: str) -> bool:
    """True when the whole Bash command is `[cd DIR &&]... git ... [2>&1] [| tail|head N]`.

    `iter_pushes` reports only the environment PREFIX of a push, so anything
    that sets the push's environment another way -- `export X=... &&`, an
    `env -i X=... git push` wrapper whose assignments `_strip_env` skips, a
    sourced file, a function, a substitution -- is invisible to
    `_is_plain_push`. Rather than enumerate those, the exemption accepts only
    this one shape and sends every other command to the ordinary review check.

    `#` is refused anywhere. shlex treats it as a comment wherever it appears,
    while bash starts a comment only at the beginning of a word, so
    `git push origin main#z && touch x` lexes here as one bare push while bash
    runs both commands. A `#` is legal in a ref name, so this is reachable.
    """
    if re.search(r"[$`;()<#\n\\]", command):
        return False
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return False
    i = 0
    while toks[i:i + 1] == ["cd"]:
        if len(toks) < i + 3 or toks[i + 2] != "&&" or not _is_word(toks[i + 1]):
            return False
        i += 3
    if toks[i:i + 1] != ["git"]:
        return False
    j = i + 1
    while (j < len(toks) and _is_word(toks[j])
           and toks[j:j + 3] != ["2", ">&", "1"]):
        j += 1
    rest = toks[j:]
    if rest[:3] == ["2", ">&", "1"]:
        rest = rest[3:]
    if not rest:
        return True
    return (rest[0] == "|" and rest[1:2] in (["tail"], ["head"])
            and all(re.fullmatch(r"-n|-?\d+", t) for t in rest[2:]))


def _is_word(tok: str) -> bool:
    """A shlex token that is not shell punctuation."""
    return not re.fullmatch(r"[|&;<>()]+", tok)


def _is_plain_push(directory: str | None, argv: list[str],
                   env: list[str]) -> bool:
    """True when nothing in or around this push can redirect its transport.

    Plain means: no environment prefix at all, no git global option but `-C`,
    no `--receive-pack`/`--exec`, none of TRANSPORT_ENV in the inherited
    environment, and none of TRANSPORT_CONFIG in the repository's resolved
    config. Stricter than it needs to be on purpose: an exempt push that is
    not plain just goes through the ordinary review check.
    """
    if env or any(os.environ.get(k) for k in TRANSPORT_ENV):
        return False
    i = 1
    while i < len(argv) and argv[i] != "push":
        if argv[i] != "-C" or i + 1 >= len(argv):
            return False
        i += 2
    for tok in argv[i + 1:]:
        # git accepts any unambiguous prefix of a long option, so match the
        # prefixes that can only mean these two (`--rec`, `--ex`).
        if tok.startswith(("--rec", "--ex")):
            return False
    return not _run_git(directory, env, "config", "--get-regexp",
                        TRANSPORT_CONFIG)


def push_is_exempt(directory: str | None, argv: list[str],
                   env: list[str], command: str) -> bool:
    """True when every URL this push would write to is in EXEMPT_REPOS.

    Only a plain command (`_is_plain_command`) running a plain push
    (`_is_plain_push`) qualifies, so no `-c`, environment setting or transport
    command is in play. The remote is resolved the way
    `_push_remote` resolves it, and its URLs are read with
    `git remote get-url --push --all`, so `pushurl` and `insteadOf` rewrites
    in the repository's config are seen as git will apply them.
    A remote with several push URLs is exempt only if all of them are. A
    command naming a URL or path instead of a configured remote is never
    exempt: `git remote get-url` cannot resolve it, and git still applies
    `insteadOf`/`pushInsteadOf` to it, so its literal text says nothing
    reliable about where the push goes.

    Anything unresolvable is NOT exempt, which leaves the push to the ordinary
    review check: the exemption can only ever narrow the guard by destination.
    That includes running out of the shared time budget, and any parse error:
    `_run_git` raises `TimeoutError` then, and letting any exception escape
    here would reach `main`'s fail-open `except` -- a silent allow for the
    whole command, which is what `push_refspecs` guards against the same way.
    """
    try:
        if not (_is_plain_command(command)
                and _is_plain_push(directory, argv, env)):
            return False
        remote = _push_remote(directory, argv, env)
        if not remote:
            return False
        listed = _run_git(directory, env,
                          "remote", "get-url", "--push", "--all", remote)
    except Exception:  # TimeoutError included; see above.
        return False
    urls = [u.strip() for u in (listed or "").splitlines() if u.strip()]
    return bool(urls) and all(_owner_repo(u) in EXEMPT_REPOS for u in urls)


def _rev_parse_ref(directory: str | None, env: list[str], *args: str) -> str | None:
    name = _run_git(directory, env, "rev-parse", *args)
    return name if name and name != "HEAD" else None


def shipped_commits(directory: str | None, argv: list[str],
                    env: list[str]) -> tuple[set[str] | None, str]:
    """(commits this push would ship, reason-if-unknown).

    None means the guard cannot tell -- `--all`, `--mirror`, an unresolvable
    ref -- which is a refusal rather than a pass, since an unknown payload is
    exactly what a review cannot have covered.
    """
    try:
        refspecs = push_refspecs(argv)
    except Exception:
        return None, "its arguments could not be parsed"
    if refspecs is None:
        named = [t for t in argv if resolve_long_opt(t.partition("=")[0]) in PUSH_OPTS_INDETERMINATE
                 or t.partition("=")[0] == "--recurse-submodules"]
        which = f" ({', '.join('`' + t + '`' for t in named)})" if named else ""
        return None, ("this push does not name a single reviewable head" + which)
    # These apply whether or not the push names a refspec, so the loop cannot
    # live in the bare-push branch alone -- the equivalent command-line flag is
    # refused on both paths. Measured: with `push.recurseSubmodules=on-demand`,
    # `git push origin main` was ALLOWED while
    # `git push --recurse-submodules=on-demand origin main` was refused, and
    # real git reports `Pushing submodule` for the former.
    remote_for_config = _push_remote(directory, argv, env)
    for key, mirrors, verdict, as_bool in CONFIG_LIKE_INDETERMINATE_FLAGS:
        if "{remote}" in key:
            # `--mirror` cannot be combined with refspecs (git refuses it), so
            # its config form only decides anything on the bare-push path.
            if refspecs or not remote_for_config:
                continue
            key = key.format(remote=remote_for_config)
        value = _git_config(directory, "--get", key, argv, env, as_bool)
        if value and verdict(value):
            return None, (f"`{key}` is set, which does what `{mirrors}` does "
                          "without naming it on the command line")
    if not refspecs:
        # A bare `git push` ships the current branch only under the modern
        # `push.default`. Under `matching` (git's default before 2.0, and still
        # present in long-lived global configs) it ships every branch whose name
        # exists on the remote, and a configured `remote.<name>.push` overrides
        # the question entirely. Measured on git 2.43.0:
        # `git -c push.default=matching push --dry-run origin` reports a branch
        # that is not HEAD. So this is checked rather than assumed.
        default = _git_config(directory, "--get", "push.default", argv, env)
        if default and default.lower() == "matching":
            return None, "`push.default` is `matching`, so a bare push ships more than HEAD"
        remote = remote_for_config
        if remote and _git_config(directory, "--get-all",
                                  f"remote.{remote}.push", argv, env):
            return None, (f"`remote.{remote}.push` is configured, so what a bare push "
                          "ships is not simply the current branch")
        head = _rev_parse(directory, env, "HEAD")
        if head is None:
            return None, "HEAD could not be resolved for the repository being pushed"
        return {head}, ""

    commits: set[str] = set()
    for spec in refspecs:
        src = spec.split(":", 1)[0].lstrip("+")
        if not src:
            continue  # `:branch` deletes a ref and ships nothing
        sha = _rev_parse(directory, env, f"{src}^{{commit}}")
        if sha is None:
            hint = ("; a shell variable cannot be expanded here, so push `HEAD` "
                    "(`git push -u origin HEAD`) when you mean the current branch"
                    if "$" in src or "`" in src else "")
            return None, f"`{src}` could not be resolved to a commit{hint}"
        commits.add(sha)
    return commits, ""


# --- transcript reading -----------------------------------------------------

def _result_text(block: dict) -> str:
    """Flatten a tool_result block's payload into one searchable string.

    A subagent's report arrives as `content`, which is a plain string in some
    transports and a list of content blocks in others. Reading only one shape
    returns "" for the other, and an empty string is indistinguishable from a
    report that stated no verdict.
    """
    parts: list[str] = []
    content = block.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for sub in content:
            if isinstance(sub, str):
                parts.append(sub)
            elif isinstance(sub, dict):
                parts.append(str(sub.get("text") or sub.get("content") or ""))
    for key in ("output", "text"):
        val = block.get(key)
        if isinstance(val, str):
            parts.append(val)
    return "\n".join(p for p in parts if p)


def _iter_blocks(record: dict):
    message = record.get("message")
    blocks = message.get("content") if isinstance(message, dict) else record.get("content")
    if isinstance(blocks, str):
        blocks = [{"type": "text", "text": blocks}]
    elif not isinstance(blocks, list):
        blocks = []
    for b in blocks:
        if isinstance(b, dict):
            yield b
    if "tool_calls" in record and isinstance(record["tool_calls"], list):
        for tc in record["tool_calls"]:
            if isinstance(tc, dict):
                args = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                yield {
                    "type": "tool_use",
                    "id": tc.get("id") or str(id(tc)),
                    "name": tc.get("name") or (tc.get("function") or {}).get("name") or "",
                    "input": args if isinstance(args, dict) else {},
                }


def _blank_quoted_regions(text: str) -> tuple[str, bool]:
    """Blank fenced code, HTML comments, and code spans in one render-faithful pass.

    Linear passes cannot be correct across interleaved constructs: CommonMark
    resolves ambiguity by ORDER: whichever construct opens first swallows the
    other's markers until its own closer. This scanner walks the text once and
    enters whichever region begins next:
    - a fence per FENCE's dialect (closing only on a same-character,
      at-least-as-long BARE marker; blocks take precedence over inlines),
    - an inline code span per CODE_SPAN (closing on an identical backtick run),
    - or an HTML comment at ``<!--`` (closing at ``-->``).

    The blanked region is then what a renderer hides, ensuring literal
    comment openers in inline code (e.g. `<!--`) do not blank subsequent
    verdicts (ai-config#3961).

    An unclosed fence or comment at end of text reports True, and parse_report
    fails closed. Offsets are preserved throughout.
    """
    out = list(text)
    n = len(text)

    def blank(a: int, b: int) -> None:
        for i in range(a, b):
            if out[i] != "\n":
                out[i] = " "

    pos = 0
    while pos < n:
        fence = FENCE.search(text, pos)
        span = CODE_SPAN.search(text, pos)
        comment_at = text.find("<!--", pos)

        # A block fence takes precedence over any inline code span that
        # starts at or spans across the fence opener.
        span_start = None
        if span is not None and (fence is None or fence.start() >= span.end()):
            span_start = span.start()

        fence_start = fence.start() if fence is not None else None
        comment_start = comment_at if comment_at != -1 else None

        candidates: list[tuple[int, str]] = []
        if fence_start is not None:
            candidates.append((fence_start, "fence"))
        if span_start is not None:
            candidates.append((span_start, "span"))
        if comment_start is not None:
            candidates.append((comment_start, "comment"))

        if not candidates:
            break

        candidates.sort(key=lambda c: c[0])
        chosen = candidates[0][1]

        if chosen == "fence":
            assert fence is not None
            open_char = fence.group(1)[0]
            open_len = len(fence.group(1))
            close = None
            for m in FENCE.finditer(text, fence.end()):
                marker = m.group(1)
                # A CLOSING fence is bare: CommonMark allows an info string
                # after an OPENER only, so a candidate with non-whitespace
                # trailing text is fenced content, not a closer -- reading
                # it as one exposed everything after it as live text
                # (#2479 review rounds).
                if (marker[0] == open_char and len(marker) >= open_len
                        and not text[m.end(1):m.end(0)].strip()):
                    close = m
                    break
            if close is None:
                blank(fence.start(), n)
                return "".join(out), True
            blank(fence.start(), close.end())
            pos = close.end()
        elif chosen == "span":
            assert span is not None
            blank(span.start(), span.end())
            pos = span.end()
        else:
            close_at = text.find("-->", comment_at + 4)
            if close_at == -1:
                blank(comment_at, n)
                return "".join(out), True
            blank(comment_at, close_at + 3)
            pos = close_at + 3
    return "".join(out), False


def parse_report(text: str) -> tuple[str | None, str | None]:
    """(verdict, reviewed_commit) from one reviewer report.

    The verdict is the LAST verdict LINE, and the fingerprint is the first one
    after it. Both halves matter: taking the last verdict anywhere lets a
    closing sentence that quotes the other verdict decide the report, and
    taking the fingerprint from anywhere lets a fingerprint quoted in the
    findings stand in for the report's own.
    """
    # BOTH searches run against the blanked text. Blanking only the verdict
    # search left the asymmetry that mattered: a fenced example whose
    # illustrative fingerprint happened to name the current HEAD was found
    # first and stood in for the report's real one, which named the older
    # commit actually reviewed -- so the push of an unreviewed commit was
    # allowed by the very comparison this guard is built around.
    # Fences and HTML comments are blanked in ONE interleaving-aware pass:
    # a commented-out "Verdict:" line must not decide the report
    # (ai-config#2413), and neither may a spoofed verdict exposed by a
    # fence/comment straddle in either direction (#2479 review rounds) --
    # see _blank_quoted_regions for why two sequential passes cannot be
    # correct.
    blanked, unresolved = _blank_quoted_regions(text)
    if unresolved:
        return None, None
    matches = list(VERDICT_LINE.finditer(blanked))
    if not matches:
        return None, None
    last = matches[-1]
    verdict = "clean" if last.group(1).lower().startswith("ready") else "needs_work"
    sha = REVIEWED_COMMIT.search(blanked, last.end())
    if verdict == "clean" and _extract_review_payload is not None and _payload_is_blocking is not None:
        try:
            payload = _extract_review_payload(text)
            if _payload_is_blocking(payload):
                verdict = "needs_work"
        except Exception:
            pass
    return verdict, (sha.group(1).lower() if sha else None)




def _agent_subtypes(inp: dict) -> list[str]:
    """Subagent names an Agent/Task dispatch names, from any observed key."""
    sub_types: list[str] = []
    # `agent`, `persona` and `role` are here because `_is_reviewer_record` below
    # already treats them as persona-naming keys, and two predicates in one file
    # disagreeing about what names a persona is how a dispatch gets seen by one
    # and not the other. Widening the TOOL set without widening this one left
    # exactly that hole: a `spawn_agent` record keyed on `agent` reproduced
    # ai-config#3707's denial verbatim after the tool name was recognized.
    #
    # Parity is with the persona KEYS, not with that function's key list, and
    # the difference is deliberate. `_is_reviewer_record` also reads
    # `attributionAgent`, which this must not: that one names who AUTHORED a
    # transcript record, while this reads a tool's INPUT. Copying it across
    # would be structural fit standing in for a transferred purpose
    # (`check-purpose-before-reusing`). `role` does transfer -- `Role` is
    # already read here and the two are one key in different casings -- and it
    # is safe on its own terms besides: a message's `role` value can only be
    # `user`, `assistant` and the like, which is why `_is_reviewer_record`
    # filters them and this does not have to. Neither name regex matches any of
    # them.
    #
    # Nothing downstream is relaxed -- every name found here is still matched
    # against ADVERSARIAL_AGENT_NAME, or FALLBACK_AGENT_NAME plus a review
    # prompt.
    for k in ("subagent_type", "subagentType", "agent_type", "TypeName",
              "name", "Role", "role", "agent", "persona"):
        if inp.get(k):
            sub_types.append(str(inp.get(k)))
    if isinstance(inp.get("Subagents"), list):
        for sa in inp["Subagents"]:
            if isinstance(sa, dict):
                for k in ("TypeName", "Role", "name"):
                    if sa.get(k):
                        sub_types.append(str(sa.get(k)))
    return sub_types


def _is_reviewer_dispatch(inp: dict) -> bool:
    """True when this Agent/Task dispatch dispatches the reviewer persona.

    The adversarial persona by name, or a fallback persona whose prompt reads
    as an adversarial review prompt. OMO's flat `tool_use` records and the
    Claude-native `tool_use` blocks must agree on what counts (ai-config#2875),
    so both paths call this instead of carrying two copies of the predicate.
    """
    sub_types = _agent_subtypes(inp)
    if any(ADVERSARIAL_AGENT_NAME.match(st) for st in sub_types):
        return True
    prompt = str(inp.get("prompt") or inp.get("Prompt") or inp.get("instruction")
                 or inp.get("description") or "")
    return bool(
        sub_types
        and any(FALLBACK_AGENT_NAME.match(st) for st in sub_types)
        and REVIEW_PROMPT_RE.search(prompt)
    )


def _is_reviewer_record(record: dict) -> bool:
    """True if this transcript record is attributed to the adversarial reviewer."""
    candidates: list[str] = []
    for k in ("attributionAgent", "agent_type", "subagent_type", "subagentType",
              "TypeName", "Role", "agent", "name", "persona"):
        val = record.get(k)
        if isinstance(val, str) and val:
            candidates.append(val)
        elif isinstance(val, dict):
            for sub_k in ("name", "TypeName", "Role", "type"):
                sub_val = val.get(sub_k)
                if isinstance(sub_val, str) and sub_val:
                    candidates.append(sub_val)
    msg = record.get("message")
    if isinstance(msg, dict):
        for k in ("attributionAgent", "agent_type", "subagent_type", "subagentType",
                  "TypeName", "Role", "agent", "name", "persona", "role"):
            val = msg.get(k)
            if isinstance(val, str) and val and val.lower() not in (
                "user", "assistant", "system", "tool", "model", "planner"
            ):
                candidates.append(val)
    return any(ADVERSARIAL_AGENT_NAME.match(c) for c in candidates)


def read_latest_review(transcript_path: str) -> tuple[str | None, str | None, bool]:
    """(verdict, reviewed_commit, saw_reviewer_call) from the transcript.

    Only the reviewer's own call results and attributed subagent reports are
    consulted, and an errored result on the dispatch itself is skipped -- a failed
    or interrupted reviewer states no verdict, and `fail-fast` forbids letting that
    look identical to a clean one. Transient tool call errors during a subagent's
    exploration (e.g. bash command syntax retry) do not invalidate an otherwise
    clean final review verdict.

    Two transcript shapes are read. Claude-native JSONL carries tool calls as
    `message.content` blocks paired by `tool_use_id`. oh-my-openagent's OpenCode
    bridge appends flat records with no message nesting and no call IDs
    (measured 4.19.4, ai-config#2875): `{"type":"tool_use","tool_name":...,
    "tool_input":...}` and `{"type":"tool_result","tool_name":...,
    "tool_output":...}`. Those are paired positionally per tool name -- opencode
    runs tools sequentially per session, so the nearest outstanding use of that
    name is the result's partner -- and fed through the same dispatch predicate
    and report parser as the native path.
    """
    reviewer_call_ids: set[str] = set()
    reviewer_task_ids: set[str] = set()
    saw_reviewer_call = False
    verdict: str | None = None
    reviewed_commit: str | None = None
    pending_omo_uses: dict[str, list[str]] = {}
    ambiguous_omo_names: set[str] = set()

    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue

            r_type = record.get("type")
            omo_tool_name = record.get("tool_name")
            if r_type in ("tool_use", "tool_result") and isinstance(omo_tool_name, str):
                # OMO's flat record shapes (see docstring). Record-level
                # tool_use/tool_result with a `tool_name` key is never a
                # Claude-native shape -- there the block sits inside
                # `message.content` -- so this branch is unambiguous.
                name = omo_tool_name.lower()
                if r_type == "tool_use":
                    _OMO_SEQ[0] += 1
                    call_id = f"omo-{_OMO_SEQ[0]}"
                    pending_omo_uses.setdefault(name, []).append(call_id)
                    inp = record.get("tool_input")
                    if (name in AGENT_TOOLS and name not in TASK_OUTPUT_TOOLS
                            and isinstance(inp, dict)):
                        if _is_reviewer_dispatch(inp):
                            saw_reviewer_call = True
                            reviewer_call_ids.add(call_id)
                else:
                    queue = pending_omo_uses.get(name) or []
                    # An authorization decision must FAIL CLOSED under
                    # ambiguity. OMO's records carry no call ids, so the only
                    # thing linking a result to a use is order -- and order is
                    # a guess the moment two dispatches of the SAME tool name
                    # are outstanding at once, since nothing requires results
                    # to arrive in dispatch order.
                    #
                    # Popping FIFO there is exploitable rather than merely
                    # imprecise. Measured against this hook: dispatch the real
                    # reviewer, dispatch any other `task`, and let only the
                    # SECOND return, carrying verdict-shaped text naming the
                    # pushed commit. FIFO pops the reviewer's id, so
                    # `parse_report` reads the unrelated output and the push is
                    # authorized with no review having completed. Any dispatch
                    # whose output embeds a rendered example of this guard's own
                    # report format reaches that state with nobody intending an
                    # attack -- this file and its test carry such strings, and
                    # so does anything documenting the report contract.
                    #
                    # So a name whose queue is ever ambiguous is poisoned for
                    # the REST of the transcript: its pending uses are dropped
                    # and no later result of that name authorizes anything. The
                    # cost is a false refusal in a genuinely interleaved
                    # session, whose remedy is one more review round. The cost
                    # of the other direction is an unreviewed push.
                    #
                    # The Claude-native path is unaffected: `tool_use_id` is a
                    # real per-call identifier, not an order-derived guess.
                    if len(queue) > 1 or name in ambiguous_omo_names:
                        ambiguous_omo_names.add(name)
                        pending_omo_uses[name] = []
                        continue
                    call_id = queue.pop(0) if queue else None
                    if call_id is not None and call_id in reviewer_call_ids:
                        # `is_error` is INERT here, and deliberately kept.
                        # OMO's records carry no error flag at all --
                        # `docs/opencode-hook-mapping.md` lists `is_error`
                        # among what its shape omits -- so this condition is
                        # always true on this path today. It is retained so
                        # the two paths read alike and so the guard tightens
                        # on its own if OMO ever adds the field, NOT because
                        # it currently excludes anything.
                        #
                        # What actually carries the weight on this path is the
                        # fingerprint: `parse_report` must find a verdict line
                        # AND a `Reviewed-Commit:` naming a commit this push
                        # ships. A dispatch that errored partway rarely has
                        # both, and one that does emitted a complete report
                        # before failing, which is a report.
                        #
                        # That is weaker than the native path's tested
                        # exclusion, and saying so is the point: an errored
                        # OMO dispatch whose output happens to carry a
                        # complete, correctly-fingerprinted report WILL
                        # authorize. No signal available here distinguishes it.
                        if not record.get("is_error"):
                            found, sha = parse_report(
                                _result_text({"content": record.get("tool_output")})
                            )
                            if found:
                                verdict, reviewed_commit = found, sha
                continue

            is_assistant = (
                record.get("source") == "MODEL"
                or record.get("type") == "assistant"
                or (isinstance(record.get("message"), dict) and record["message"].get("role") == "assistant")
            )

            record_is_reviewer = _is_reviewer_record(record)
            if record_is_reviewer:
                saw_reviewer_call = True
                content_text = _result_text(
                    record.get("message") if isinstance(record.get("message"), dict) else record
                )
                if content_text:
                    found, sha = parse_report(content_text)
                    if found:
                        verdict, reviewed_commit = found, sha

            for b in _iter_blocks(record):
                b_type = b.get("type")

                if b_type == "tool_use":
                    tool_name = (b.get("name") or "").lower()
                    call_id = b.get("id")
                    inp = b.get("input") or {}

                    # Task-output tools are tested FIRST so a persona label on
                    # one can never short-circuit the task-id gate below, which
                    # is their only sound provenance (see TASK_OUTPUT_TOOLS).
                    if tool_name in TASK_OUTPUT_TOOLS:
                        # Since the reorder above, this gate is the ONLY
                        # provenance a retrieval tool has -- the persona path it
                        # used to fall back on is exactly the bypass that was
                        # closed -- so a spelling missing from either end of the
                        # chain is no longer a near-miss that something else
                        # catches. It denies a review that genuinely ran, with
                        # #3707's own misleading message.
                        #
                        # Both ends now read `TASK_ID_KEYS`, which is why this
                        # site no longer carries a key list of its own. An
                        # earlier revision of this comment INSTRUCTED the two to
                        # agree, and they did not agree at the moment it said so:
                        # the consumer read `TaskId` and the producer did not,
                        # the producer read `conversationId` and the consumer did
                        # not. A comment cannot hold an invariant that a shared
                        # constant can (ai-config#3737 round 6).
                        if any(t in reviewer_task_ids
                               for t in _task_ids(inp)):
                            if isinstance(call_id, str) and call_id:
                                reviewer_call_ids.add(call_id)
                    elif tool_name in AGENT_TOOLS:
                        if _is_reviewer_dispatch(inp):
                            saw_reviewer_call = True
                            if isinstance(call_id, str) and call_id:
                                reviewer_call_ids.add(call_id)
                    elif tool_name == "bash" and external_reviewer_command(
                            str(inp.get("command") or "")):
                        saw_reviewer_call = True
                        if isinstance(call_id, str) and call_id:
                            reviewer_call_ids.add(call_id)
                    elif tool_name == "send_message" and record_is_reviewer:
                        msg_text = str(inp.get("Message") or inp.get("message") or "")
                        if msg_text:
                            found, sha = parse_report(msg_text)
                            if found:
                                verdict, reviewed_commit = found, sha

                elif b_type == "tool_result":
                    call_id = b.get("tool_use_id")
                    if call_id in reviewer_call_ids:
                        # Check if this result launched a background task with an ID
                        res_text = _result_text(b)
                        try:
                            res_data = json.loads(res_text)
                            if isinstance(res_data, dict):
                                for tid in _registrable_task_ids(res_data):
                                    reviewer_task_ids.add(tid)
                        except Exception:
                            tid_match = re.search(r"\b(?:task[-_ ]?id|conversationId|agentId)[:=]\s*[`\"']?([\w-]+)", res_text, re.I)
                            if tid_match:
                                reviewer_task_ids.add(tid_match.group(1))

                        if not b.get("is_error"):
                            found, sha = parse_report(res_text)
                            if found:
                                saw_reviewer_call = True
                                verdict, reviewed_commit = found, sha

                # Genuine task notifications from tracked background reviewer dispatches
                origin = record.get("origin")
                is_task_notification = (
                    isinstance(origin, dict)
                    and origin.get("kind") in ("task-notification", "task_notification")
                )
                if is_task_notification and not is_assistant and not b.get("is_error"):
                    origin_ids = _task_ids(origin, TASK_ID_KEYS_ORIGIN)
                    sender_id = str(record.get("sender") or "")
                    if (
                        any(t in reviewer_task_ids for t in origin_ids)
                        or (sender_id and sender_id in reviewer_task_ids)
                    ):
                        text = str(b.get("text") or b.get("content") or "")
                        found, sha = parse_report(text)
                        if found:
                            saw_reviewer_call = True
                            verdict, reviewed_commit = found, sha

    return verdict, reviewed_commit, saw_reviewer_call


def _opencode_transcript_fallback(session_id) -> str:
    """oh-my-openagent's per-session transcript for this session_id.

    OMO's OpenCode bridge runs the catalog from ~/.claude/settings.json but
    never sets transcriptPath in its PreToolUse hook context (measured 4.19.4,
    ai-config#2875), so an OpenCode session's push guard reads nothing. OMO
    maintains its own JSONL per session under the Claude config dir, keyed by
    the payload's session_id. Claude Code payloads always carry an existing
    transcript_path, so the fallback fires only where the primary path is
    absent or missing; a session_id that is not a bare filename component
    resolves to no file rather than to a traversal.
    """
    if not session_id:
        return ""
    raw = str(session_id)
    if "/" in raw or "\\" in raw or raw in (".", "..") or raw != os.path.basename(raw):
        return ""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude"
    )
    return os.path.join(base, "transcripts", f"{raw}.jsonl")


def verify_review(transcript_path: str, directory: str | None,
                  argv: list[str], env: list[str]) -> tuple[bool, str]:
    """(is_clean, reason) -- is there a clean verdict for what this push ships?"""
    saw_reviewer_call = False
    verdict: str | None = None
    reviewed_commit: str | None = None

    # `transcript_path and` stays here, unlike the two conjuncts removed below,
    # and the difference is not cosmetic. Those two restated a fact a preceding
    # `return` had already proven, so removing them changed nothing. This one
    # guards a non-`str` argument: the annotation is not enforced, and
    # `os.path.exists(None)` raises. With the conjunct a `None` falls through to
    # the denial below instead. Measured both ways, and pinned by a case that
    # calls this function directly.
    #
    # It is defence in depth for a hypothetical second caller, NOT the thing
    # standing between this repository and a fail-open. An earlier version of
    # this comment claimed the latter, and that was wrong in a way worth keeping
    # on the record: the sole caller's `or ""` already foreclosed the `None` this
    # conjunct catches, while the live bypass sat one line EARLIER in that
    # caller, on the `list`/`dict`/`True` values `or ""` does not rescue. The
    # comment named a real mechanism, attached it to the wrong site, and so read
    # as a fail-open having been closed while it was open (ai-config#3752). The
    # caller now coerces, which is where the fix belongs; this stays because a
    # future caller need not.
    if transcript_path and os.path.exists(transcript_path):
        try:
            verdict, reviewed_commit, saw_reviewer_call = read_latest_review(transcript_path)
        except Exception as e:
            return False, f"Failed reading transcript: {e}"

    # Neither this condition nor the one below carries `and not
    # saw_reviewer_call`. That conjunct cannot be False on either path:
    # `saw_reviewer_call` is assigned only inside the `os.path.exists` branch
    # above, which both of these conditions exclude, so it is still False here.
    # Dropped from both rather than one, so the two read alike
    # (`dead-code-is-tech-debt`).
    if not transcript_path:
        return False, "No transcript available to verify the adversarial self-review."

    if not os.path.exists(transcript_path):
        # Distinguished from the denial below because the two have different
        # remedies and only one of them is the pusher's to apply. Reporting a
        # harness integration gap as "you did not dispatch a reviewer" sends
        # someone to re-run a review they already ran, and it is what made
        # ai-config#3707 read as a reviewer problem rather than a discovery
        # one. `fail-fast` wants the real condition named, not a plausible
        # nearby one.
        return False, (
            f"This session reported a transcript at `{transcript_path}`, but no file "
            "exists there, so no review could be read either way.\n"
            "That is a harness gap rather than a verdict: nothing here says whether a "
            "reviewer ran. Check that your harness writes the transcript it names in "
            "the hook payload, and file the gap. Use the override and say so if you "
            "need to push before it is fixed."
        )

    if not saw_reviewer_call:
        return False, (
            "No `adversarial-reviewer` subagent or recognized external reviewer (`agy --print`) "
            "was dispatched in this session.\n"
            "Dispatch the subagent or run an `agy --print '<prompt>'` review against your "
            "committed diff and address its findings before pushing."
        )

    if verdict is None:
        return False, (
            "An `adversarial-reviewer` subagent was dispatched, but no verdict came back "
            "as that call's own result.\n"
            "Dispatch it in the foreground (`run_in_background: false`) so its report "
            "returns as the tool result -- a background dispatch returns an agent id, "
            "which carries no verdict, and an errored result carries none either."
        )

    if verdict == "needs_work":
        return False, (
            "The latest adversarial self-review returned a blocking verdict.\n"
            "Address, rebut, or defer every finding, commit, and re-dispatch the reviewer."
        )

    if not reviewed_commit:
        return False, (
            "The clean verdict does not say which commit it read.\n"
            "The reviewer must state `Reviewed-Commit: <full sha>` on its own line "
            "immediately after the verdict; the JSON payload may follow it, and "
            "nothing else should. Without the line nothing ties the verdict to what "
            "this push would ship, and a report cut short before its fingerprint is "
            "not a verdict."
        )

    try:
        resolved_commit = _rev_parse(directory, env, f"{reviewed_commit}^{{commit}}")
    except TimeoutError as e:
        return False, (
            f"This guard {e}.\n"
            "It refuses rather than letting the push through unchecked; re-run once the "
            "repository is responsive, or use the override and say so."
        )
    if resolved_commit is None:
        return False, (
            f"The clean verdict's fingerprint `{reviewed_commit}` does not resolve to any "
            "commit in this repository.\n"
            "That is a fabricated or corrupted fingerprint, not a stale verdict for a "
            "different commit -- a reviewer that recalls or reconstructs a SHA instead of "
            "reading it can get a prefix right and invent the rest. Re-dispatch the "
            "reviewer and tell it to obtain the SHA by running `git rev-parse HEAD` and "
            "copy the 40-character output verbatim, not reconstruct or abbreviate it."
        )
    reviewed_commit = resolved_commit

    try:
        commits, why = shipped_commits(directory, argv, env)
    except TimeoutError as e:
        return False, (
            f"This guard {e}.\n"
            "It refuses rather than letting the push through unchecked; re-run once the "
            "repository is responsive, or use the override and say so."
        )
    if commits is None:
        return False, (
            f"Cannot determine which commits this push would ship: {why}.\n"
            "A clean verdict covers the commit it names, so a push whose payload cannot "
            "be resolved is not covered by it."
        )
    if not commits:
        return True, "This push ships no commits (a ref deletion)."

    unreviewed = sorted(c for c in commits if not c.startswith(reviewed_commit))
    if unreviewed:
        return False, (
            f"The clean verdict is for commit {reviewed_commit}, but this push would ship "
            f"{', '.join(c[:12] for c in unreviewed)}.\n"
            "A push ships commits, so whatever differs -- a later commit, a `main` merge, "
            "a rebase, or a branch other than the reviewed one -- is unreviewed. "
            "Re-dispatch the reviewer against what you are actually pushing."
        )

    return True, f"Clean adversarial self-review verified at {reviewed_commit}."


DENY_TAIL = (
    "\n\nStanding rule: every self-review is an adversarial review by a separate "
    "subagent. Dispatch `adversarial-reviewer` in the foreground against your "
    "committed diff (or dispatch a fallback reviewer subagent such as `general-purpose` "
    "or `self` with an adversarial review prompt when the persona is unregistered), "
    "address or rebut every finding, and let its report state the commit it read.\n\n"
    "Only that reviewer's own result or report counts -- this message does not, "
    "and neither does reading a file that quotes a verdict.\n\n"
    "Override by prefixing the push itself with `ALLOW_UNREVIEWED_PUSH=1` when no "
    "verdict can exist for the guard to check: an initial empty PR branch (per "
    "pr-on-claim), an auto-mode session where no subagent tool exists, "
    "or an emergency. In auto mode, if the permission classifier denies the env "
    "prefix, request a Bash permission rule. "
    "Say in your reply that you used the override and why."
)


def deny(reason: str) -> None:
    _DENIAL_ISSUED[0] = True
    payload = json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"git push blocked by the pre-push self-review policy:\n{reason}{DENY_TAIL}"
            ),
        }
    }) + "\n"

    # Attempt 1: If fd 1 was closed or redirected, restore it using our saved duplicate
    if _ORIGINAL_STDOUT_FD is not None:
        try:
            os.dup2(_ORIGINAL_STDOUT_FD, 1)
        except Exception:
            pass

    # Attempt 2: Write via standard sys.stdout
    written = False
    try:
        sys.stdout.write(payload)
        sys.stdout.flush()
        written = True
    except Exception:
        pass

    # Attempt 3: If standard sys.stdout write failed, write directly to the saved descriptor
    if not written and _ORIGINAL_STDOUT_FD is not None:
        try:
            os.write(_ORIGINAL_STDOUT_FD, payload.encode("utf-8"))
            written = True
        except Exception:
            pass

    # Attempt 4: If emission to stdout could not succeed, we have already decided
    # to deny the push. Failing open into return 0 would silently permit an unauthorized
    # push. Emit an emergency failure log to stderr and fail closed (exit 2).
    if not written:
        try:
            sys.stdout = open(os.devnull, "w")
        except Exception:
            pass
        try:
            sys.stderr.write(
                "no-push-without-self-review: FATAL: denial could not be written to stdout;\n"
                f"blocking push. Denial reason:\n{reason}\n"
            )
            sys.stderr.flush()
        except Exception:
            pass
        sys.exit(2)


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"no-push-without-self-review: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    try:
        if (payload.get("tool_name") or "") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        inp = payload.get("tool_input")
        inp = inp if isinstance(inp, dict) else {}
        cmd = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""
        if not cmd:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        if _SIBLING is None:
            # Only reached once a push-shaped command is plausible, so a broken
            # install does not deny every Bash call -- but it does deny rather
            # than grade pushes with a detector this file refuses to duplicate.
            # A degraded-mode heuristic rather than a second parser: it decides
            # only whether to SAY the guard is broken, never whether a command
            # is a push. Narrow enough that `git commit -m "push the button"`
            # and `grep push` do not trip it.
            #
            # The override is honoured here too: denying a push that carries it,
            # under a message saying the override works, is a session-wide
            # lockout with no escape.
            if DEGRADED_OVERRIDE.search(cmd):
                return 0
            if re.search(
                r"(?:^|[;&|`(\s])(?:[\w./-]*/)?git"
                r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--(?:git-dir|work-tree|namespace)[= ]\S+|-\S+))*"
                r"\s+push\b", cmd):
                deny(
                    "This guard could not load its push detector from "
                    f"`no-unreviewed-pr.py` ({_SIBLING_ERROR}), so it cannot tell whether "
                    "this command pushes."
                )
            return 0

        _DEADLINE[0] = time.monotonic() + BUDGET_SECONDS
        for env, argv, directory in iter_pushes(cmd):
            if has_allow_override(env):
                continue
            if _has_config_env(argv):
                deny("this push carries `--config-env`, whose value comes from "
                     "an environment variable this guard cannot read, so what "
                     "the push ships cannot be determined")
                return 0
            if directory is REDIRECTED:
                deny("this push points git at another repository "
                     "(`--git-dir`/`--work-tree`/`GIT_DIR`/`GIT_WORK_TREE`), "
                     "so a verdict naming a commit in this one cannot cover it")
                return 0
            if push_is_exempt(directory, argv, env, cmd):
                continue
            # Coerce before `os.path.exists` rather than after. `or ""` rescues
            # only the FALSY non-`str` values: a truthy `list` or `dict` reaches
            # `os.path.exists`, which raises `TypeError` (it catches `OSError`
            # and `ValueError` and not that), and the raise lands in this
            # function's deliberate `except Exception: return 0` -- a silent
            # ALLOW, no denial emitted, indistinguishable in the transcript from
            # an authorized push. Measured on this branch AND on `main`, so the
            # bypass predates the branch; filed as ai-config#3752.
            #
            # `True` allows by a SECOND and worse route, and the first account of
            # it here was wrong in a way worth keeping: it said the bool was
            # "carried into `verify_review`". Measured, it never gets there.
            # `os.path.exists(True)` is indeed `True` (fd 1 exists), so the
            # value survives the check above -- but `read_latest_review` then
            # calls `open(True)`, which opens FILE DESCRIPTOR 1, raises
            # `OSError: [Errno 9]` on read, and CLOSES STDOUT leaving the
            # `with`. The guard does reach a denial; it cannot EMIT one,
            # because every `print` after that raises into the deliberate
            # `except Exception: return 0`. Measured on `main`: of the five
            # non-`str` values case 22 pins, exactly three produce zero bytes on
            # stdout AND on stderr, by TWO different routes.
            #
            #   None        falsy, so `or ""` rescues it     denial emitted
            #   123         truthy; exists(123) is False     denial emitted
            #   True        truthy; exists(True) is True      SILENT
            #   ["/tmp/x"]  TypeError inside exists()         SILENT
            #   {"p": 1}    TypeError inside exists()         SILENT
            #
            # The list and the dict raise at `os.path.exists` itself. `True`
            # does not: fd 1 is open, so it passes, and the failure arrives
            # later -- `open(True)` succeeds, raises on read, and closes stdout
            # on the way out of the `with`, so the guard reaches a denial it can
            # no longer emit. Naming "all three" without naming WHICH three read
            # as a count of the pinned matrix, which has five (round 9).
            #
            # `isinstance` closes this instance. For the wider class of failures
            # (stdout closure, bad file descriptors, broken pipes, or serialization
            # errors), `deny()` duplicates fd 1 at startup to restore stdout or
            # write directly, tracks `_DENIAL_ISSUED`, and fails closed (exit 2)
            # if stdout cannot be written or if an exception occurs after a denial
            # decision, closing the silent-allow bypass (ai-config#3756).
            _tp = payload.get("transcript_path")
            transcript_path = _tp if isinstance(_tp, str) else ""
            if not os.path.exists(transcript_path):
                # Adopt the fallback only when it resolves to a real file.
                # Overwriting unconditionally erased a reported-but-missing
                # path, so `verify_review` saw "" and reported no transcript
                # available -- or, when the fallback was itself constructed but
                # absent, reported that no reviewer had been dispatched. Both
                # describe the session rather than the gap, and neither is
                # something the pusher can act on. Keeping the reported path
                # lets the denial name it (ai-config#3707).
                fallback = _opencode_transcript_fallback(
                    payload.get("session_id")
                )
                if fallback and os.path.exists(fallback):
                    transcript_path = fallback
            is_clean, reason = verify_review(
                transcript_path, directory, argv, env
            )
            if not is_clean:
                deny(reason)
                return 0
        return 0
    except Exception as exc:
        if _DENIAL_ISSUED[0]:
            try:
                sys.stdout = open(os.devnull, "w")
            except Exception:
                pass
            try:
                sys.stderr.write(
                    f"no-push-without-self-review: exception raised after denial decision: {exc}\n"
                )
                sys.stderr.flush()
            except Exception:
                pass
            return 2
        # Fail open, deliberately and in the same direction as the parse-failure
        # rule in the docstring: a guard that crashed closed would block every
        # push in the session, which is a worse failure than missing one review.
        return 0


if __name__ == "__main__":
    sys.exit(main())
