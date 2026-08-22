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
verdict is admitted only from the `tool_result` of an `Agent` call whose
`subagent_type` IS the reviewer, and only when that result is not an error.

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
-- but it still needs a clean verdict to reach that comparison, unlike the two
forms below, which are never examined at all.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time

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

AGENT_TOOLS = {"agent", "task", "invoke_subagent"}

OVERRIDE_ENV = re.compile(r"\AALLOW_UNREVIEWED_PUSH=1\Z")

# Options of `git push` that consume the following token, so a value is never
# mistaken for a refspec.
PUSH_OPTS_WITH_VALUE = {"--repo", "--receive-pack", "--exec", "-o", "--push-option",
                        "--recurse-submodules"}

# Short options that take a value, for the clustered form (`-qo ci.skip`).
SHORT_OPTS_WITH_VALUE = "o"

# Options after which no single reviewed commit can describe the push.
# `--branches` is git's own documented alias of `--all` (`git push -h`), so it
# ships every branch while looking like an ordinary unknown option.
PUSH_OPTS_INDETERMINATE = {"--all", "--branches", "--mirror", "--tags",
                           "--follow-tags"}

# `--recurse-submodules` in these modes pushes commits in ANOTHER repository,
# which no fingerprint naming a commit in this one can describe.
SUBMODULE_PUSH_MODES = {"on-demand", "only"}


# --- push detection, borrowed rather than re-derived ------------------------
#
# `no-unreviewed-pr.py`'s detector is shell-parsed rather than regex-matched, so
# it already handles `git -C <dir> push` and `git -c k=v push`, already excludes
# the two push forms that re-head nothing, and is already tested there. A second
# hand-rolled detector would be a DRW finding and would diverge silently
# (ai-config#1920) -- an earlier revision of this file wrote one as a "fallback"
# and it did diverge, on all three of those points. So there is no fallback: if
# the sibling cannot be loaded this guard says so and denies, rather than
# quietly grading pushes with a worse parser.

def _load_sibling():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "no-unreviewed-pr.py")
    spec = importlib.util.spec_from_file_location("no_unreviewed_pr", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    _SIBLING = _load_sibling()
    _SIBLING_ERROR = None
except Exception as exc:  # covered by test-…'s orphan_cases(), which runs a copy
                          # of this file in a directory without the sibling
    _SIBLING = None
    _SIBLING_ERROR = str(exc)


ENV_ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")


# Wrappers that run the command that follows them, so `git` is not argv[0] even
# though a push is exactly what happens. `env` is the sharpest of these: the
# earlier revision handled `export`, which never runs a push at all, and not
# `env`, which does.
COMMAND_WRAPPERS = {"env", "command", "nohup", "time", "exec", "builtin"}


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
    while rest:
        tok = rest[0]
        if ENV_ASSIGNMENT.match(tok):
            env.append(tok)
            rest = rest[1:]
            continue
        if tok in COMMAND_WRAPPERS or tok == "export":
            rest = rest[1:]
            continue
        break
    if rest and rest[0] != "git" and os.path.basename(rest[0]) == "git":
        rest = ["git"] + rest[1:]
    return env, rest


def iter_pushes(command: str):
    """Yield (env, argv, directory) for each `git push` simple command.

    `directory` is the repo the push acts on: the push's own `-C`, else the
    directory of the last `cd`/`pushd` ahead of it in the same command line,
    else None (meaning the hook's own cwd). Both were previously read off the
    FIRST git command in the chain, so `git -C a status && git -C b push`
    graded the wrong repository.
    """
    if _SIBLING is None:
        return
    cmds = _SIBLING._simple_commands(command)
    if not cmds:
        return
    # A subshell confines a `cd`, and `_simple_commands` does not model nesting,
    # so a line containing one gets no hint at all rather than a wrong one:
    # `(cd elsewhere && git log) && git push` pushes in the ORIGINAL directory.
    nested = "(" in command or ")" in command
    cwd_hint = None
    for argv in cmds:
        if not argv:
            continue
        if argv[0] in ("cd", "pushd", "popd"):
            # `cd -`, `popd`, and a bare `cd` all move somewhere this cannot
            # resolve, so they clear the hint rather than leaving a stale one.
            arg = argv[1] if len(argv) > 1 else None
            cwd_hint = arg if (arg and not arg.startswith("-") and argv[0] != "popd") else None
            continue
        env, rest = _strip_env(argv)
        if not rest or not _SIBLING._argv_push(rest):
            continue
        directory = None
        for i, tok in enumerate(rest[1:-1], start=1):
            if tok == "-C":
                directory = rest[i + 1]
                break
        yield env, rest, (directory or (None if nested else cwd_hint))


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

    An empty list means "whatever the current branch is", i.e. HEAD.
    """
    try:
        idx = argv.index("push")
    except ValueError:
        return None
    positionals: list[str] = []
    i = idx + 1
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-") and tok != "-":
            head, _, value = tok.partition("=")
            if head in PUSH_OPTS_INDETERMINATE:
                return None
            if head == "--recurse-submodules" and value in SUBMODULE_PUSH_MODES:
                return None
            if head in PUSH_OPTS_WITH_VALUE and not _:
                if head == "--recurse-submodules" and i + 1 < len(argv) \
                        and argv[i + 1] in SUBMODULE_PUSH_MODES:
                    return None
                i += 2
                continue
            # A clustered short form (`-qo ci.skip`) takes its value from the
            # next token when the cluster ends in a value-taking letter.
            if not tok.startswith("--") and tok[-1] in SHORT_OPTS_WITH_VALUE:
                i += 2
                continue
            i += 1
            continue
        positionals.append(tok)
        i += 1
    return positionals[1:]  # drop the remote


# This hook is registered with a 10s timeout in `hooks/hooks.json`, and a
# PreToolUse hook killed on timeout does not deny -- the push simply proceeds.
# So the budget is enforced here rather than left to the harness: one call per
# refspec times a generous per-call timeout would exceed it on a slow repo, and
# the failure would be a silent allow on the one path this guard exists to hold.
BUDGET_SECONDS = 6.0
_DEADLINE = [0.0]


def _rev_parse(directory: str | None, rev: str) -> str | None:
    remaining = _DEADLINE[0] - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("ran out of time resolving what this push would ship")
    args = ["git"] + (["-C", directory] if directory else []) + ["rev-parse", rev]
    try:
        out = subprocess.run(args, capture_output=True, text=True,
                             timeout=min(3.0, remaining))
    except subprocess.TimeoutExpired:
        raise TimeoutError("ran out of time resolving what this push would ship")
    except Exception:
        return None
    if out.returncode != 0:
        return None
    sha = out.stdout.strip()
    return sha.lower() if re.fullmatch(r"[0-9a-f]{40}", sha) else None


def shipped_commits(directory: str | None, argv: list[str]) -> tuple[set[str] | None, str]:
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
        named = [t for t in argv if t.partition("=")[0] in PUSH_OPTS_INDETERMINATE
                 or t.partition("=")[0] == "--recurse-submodules"]
        which = f" ({', '.join('`' + t + '`' for t in named)})" if named else ""
        return None, ("this push does not name a single reviewable head" + which)
    if not refspecs:
        head = _rev_parse(directory, "HEAD")
        if head is None:
            return None, "HEAD could not be resolved for the repository being pushed"
        return {head}, ""

    commits: set[str] = set()
    for spec in refspecs:
        src = spec.split(":", 1)[0].lstrip("+")
        if not src:
            continue  # `:branch` deletes a ref and ships nothing
        sha = _rev_parse(directory, f"{src}^{{commit}}")
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


def _blank_fences(text: str) -> str:
    """Blank the contents of fenced code blocks, preserving offsets.

    Offsets are preserved because `parse_report` searches for the fingerprint
    forward from the verdict's own position in the ORIGINAL text.
    """
    out = list(text)
    fences = list(FENCE.finditer(text))
    for opener, closer in zip(fences[0::2], fences[1::2]):
        for i in range(opener.start(), closer.end()):
            if out[i] != "\n":
                out[i] = " "
    if len(fences) % 2:  # an unclosed fence swallows the rest
        last = fences[-1]
        for i in range(last.start(), len(out)):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def parse_report(text: str) -> tuple[str | None, str | None]:
    """(verdict, reviewed_commit) from one reviewer report.

    The verdict is the LAST verdict LINE, and the fingerprint is the first one
    after it. Both halves matter: taking the last verdict anywhere lets a
    closing sentence that quotes the other verdict decide the report, and
    taking the fingerprint from anywhere lets a fingerprint quoted in the
    findings stand in for the report's own.
    """
    matches = list(VERDICT_LINE.finditer(_blank_fences(text)))
    if not matches:
        return None, None
    last = matches[-1]
    verdict = "clean" if last.group(1).lower().startswith("ready") else "needs_work"
    sha = REVIEWED_COMMIT.search(text, last.end())
    return verdict, (sha.group(1).lower() if sha else None)


def read_latest_review(transcript_path: str) -> tuple[str | None, str | None, bool]:
    """(verdict, reviewed_commit, saw_reviewer_call) from the transcript.

    Only the reviewer's own call results are consulted, and an errored result is
    skipped -- a failed or interrupted reviewer states no verdict, and
    `fail-fast` forbids letting that look identical to a clean one.
    """
    reviewer_call_ids: set[str] = set()
    saw_reviewer_call = False
    verdict: str | None = None
    reviewed_commit: str | None = None

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

            for b in _iter_blocks(record):
                b_type = b.get("type")

                if b_type == "tool_use":
                    if (b.get("name") or "").lower() not in AGENT_TOOLS:
                        continue
                    inp = b.get("input") or {}
                    sub_type = str(
                        inp.get("subagent_type")
                        or inp.get("subagentType")
                        or inp.get("agent_type")
                        or ""
                    )
                    if ADVERSARIAL_AGENT_NAME.match(sub_type):
                        saw_reviewer_call = True
                        call_id = b.get("id")
                        if isinstance(call_id, str) and call_id:
                            reviewer_call_ids.add(call_id)

                elif b_type == "tool_result":
                    if b.get("tool_use_id") not in reviewer_call_ids:
                        continue
                    if b.get("is_error"):
                        continue
                    found, sha = parse_report(_result_text(b))
                    if found:
                        verdict, reviewed_commit = found, sha

    return verdict, reviewed_commit, saw_reviewer_call


def verify_review(transcript_path: str, directory: str | None,
                  argv: list[str]) -> tuple[bool, str]:
    """(is_clean, reason) -- is there a clean verdict for what this push ships?"""
    if not transcript_path or not os.path.exists(transcript_path):
        return False, "No transcript available to verify the adversarial self-review."

    try:
        verdict, reviewed_commit, saw_reviewer_call = read_latest_review(transcript_path)
    except Exception as e:
        return False, f"Failed reading transcript: {e}"

    if not saw_reviewer_call:
        return False, (
            "No `adversarial-reviewer` subagent was dispatched in this session.\n"
            "Dispatch it against your committed diff and address its findings before pushing."
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
            "The reviewer must end its report with `Reviewed-Commit: <sha>`, after the "
            "verdict; without it nothing ties the verdict to what this push would ship, "
            "and a report cut short before its fingerprint is not a verdict."
        )

    try:
        commits, why = shipped_commits(directory, argv)
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
    "committed diff, address or rebut every finding, and let its report state the "
    "commit it read.\n\n"
    "Only that subagent's own result counts -- this message does not, and neither "
    "does reading a file that quotes a verdict.\n\n"
    "Override by prefixing the push itself with `ALLOW_UNREVIEWED_PUSH=1` when no "
    "verdict can exist for the guard to check: an initial empty PR branch (per "
    "pr-on-claim), a review delivered by a separate CLI rather than a subagent, a "
    "session where the reviewer agent is unregistered or loaded from a stale "
    "definition, or an emergency. Say in your reply that you used it and why."
)


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"git push blocked by the pre-push self-review policy:\n{reason}{DENY_TAIL}"
            ),
        }
    }))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if (payload.get("tool_name") or "") != "Bash":
            return 0

        cmd = (payload.get("tool_input") or {}).get("command") or ""
        if not cmd:
            return 0

        if _SIBLING is None:
            # Only reached once a push-shaped command is plausible, so a broken
            # install does not deny every Bash call -- but it does deny rather
            # than grade pushes with a detector this file refuses to duplicate.
            # A degraded-mode heuristic rather than a second parser: it decides
            # only whether to SAY the guard is broken, never whether a command
            # is a push. Narrow enough that `git commit -m "push the button"`
            # and `grep push` do not trip it.
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
            is_clean, reason = verify_review(
                payload.get("transcript_path") or "", directory, argv
            )
            if not is_clean:
                deny(reason)
                return 0
        return 0
    except Exception:
        # Fail open, deliberately and in the same direction as the parse-failure
        # rule in the docstring: a guard that crashed closed would block every
        # push in the session, which is a worse failure than missing one review.
        return 0


if __name__ == "__main__":
    sys.exit(main())
