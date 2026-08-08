#!/usr/bin/env python3
"""Test the no-unauthorized-merge guard.

Must live in a file rather than a Bash heredoc so test runner (scripts/test_hooks.py)
can invoke it directly with sys.argv[1].
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else str(Path(__file__).parent / "no-unauthorized-merge.py")

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")

BLOCK = [
    ("gh pr merge 411 --squash", "bare gh pr merge"),
    ('bash -c "gh pr merge 411 --squash"', "subshell bash -c gh pr merge inside double quotes"),
    ("sh -c 'gh pr merge 411 --squash'", "subshell sh -c gh pr merge inside single quotes"),
    ("eval \"gh pr merge 411\"", "eval string execution gh pr merge"),
    ("gh pr \\\n merge 411 --squash", "backslash-newline line continuation gh pr merge"),
    ("gh pr me\\\nrge 411 --squash", "mid-word backslash-newline continuation gh pr merge"),
    ('(gh pr merge 411)', "parenthesized subshell gh pr merge"),
    ('gh pr comment 123 --body "hi"\ngh pr merge 999', "multiline script: comment on line 1, merge on line 2"),
    ('gh pr comment 123 --body "Line 1\nLine 2\nLine 3"\ngh pr merge 999', "multiline comment body with multiple newlines before merge command"),
    ('gh pr comment 123 --body "updating status && checking CI"; gh pr merge 411 --squash', "multiline body with && followed by merge command"),
    ('gh pr comment 123 --body "foo; bar"; gh pr merge 411', "body with semicolon followed by merge command"),
    ('gh pr comment 123 --body "hi";gh pr merge 999', "semicolon without trailing space before merge command"),
    ("gh -R owner/repo pr merge 411 --squash", "gh pr merge with -R flag before subcommands"),
    ('gh -R "owner name/repo" pr merge 411', "gh pr merge with quoted repo containing spaces"),
    ("gh pr -R owner/repo merge 411 --squash", "gh pr merge with -R flag between pr and merge"),
    ("gh --repo owner/repo pr merge 411", "gh pr merge with --repo flag before subcommands"),
    ("/usr/bin/gh pr merge 411", "full executable path"),
    ("env gh pr merge 411", "env wrapper prefix"),
    ("exec gh pr merge 411", "exec wrapper prefix"),
    ("command gh pr merge 411", "command wrapper prefix"),
    ("echo $(gh pr merge 411)", "subshell command substitution"),
    ("glab mr merge 12", "glab mr merge"),
    ("glab -R owner/repo mr merge 12", "glab mr merge with -R flag before subcommands"),
    ("glab mr --repo owner/repo merge 12", "glab mr merge with --repo flag between mr and merge"),
    ("gh api -X PUT /repos/owner/repo/pulls/123/merge", "gh api PR merge with integer ID and PUT method"),
    ("gh api -X PUT pulls/123/merge", "gh api PR merge with relative path without leading slash"),
    ("gh api -X put /repos/owner/repo/pulls/123/merge", "gh api PR merge with lowercase put method"),
    ("gh api --method post /repos/owner/repo/pulls/123/merge", "gh api PR merge with lowercase --method post"),
    ('gh api --method PUT "/repos/owner/repo/pulls/123/merge"', "gh api PR merge with double-quoted URL and method PUT"),
    ("gh api --method PUT '/repos/owner/repo/pulls/123/merge'", "gh api PR merge with single-quoted URL and method PUT"),
    ("gh api -X POST /repos/owner/repo/merges -f base=main -f head=feature", "gh api repository merges API endpoint"),
    ("gh api -X PUT /repos/owner/repo/pulls/$PR_NUM/merge", "gh api PR merge with shell variable ID"),
    ("gh api -X PUT /repos/owner/repo/pulls/${PR_NUM}/merge", "gh api PR merge with braced shell variable ID"),
    ("gh api -X PUT repos/owner/repo/pulls/$(echo 123)/merge", "gh api PR merge with subshell PR number"),
    ("gh api graphql -f query='mutation { mergePullRequest(input: {...}) }'", "gh api GraphQL PR merge mutation with -f flag"),
    ("gh api graphql -f query='mutation { enablePullRequestAutoMerge(input: {...}) }'", "gh api GraphQL auto-merge mutation"),
    ("glab api -X PUT projects/1/merge_requests/2/merge", "glab api MR merge endpoint"),
    ("glab api -X PUT merge_requests/2/merge", "glab api MR merge relative path endpoint"),
    ("echo foo && gh pr merge 123", "compound command with merge segment"),
    ('gh pr merge 123 --body "ALLOW_MERGE=1"', "ALLOW_MERGE inside --body string argument"),
    ('gh pr merge 123 -t " ALLOW_MERGE=1"', "ALLOW_MERGE inside -t string argument with leading space"),
    ('gh pr merge 123 --subject " ALLOW_MERGE=1"', "ALLOW_MERGE inside --subject string argument with leading space"),
    ("gh pr merge 123 # ALLOW_MERGE=1", "ALLOW_MERGE inside trailing shell comment"),
    ('gh pr comment 999 --body "Log: `gh pr merge 123 --squash`"', "backtick command substitution inside double-quoted payload"),
    ('gh pr comment 999 --body "Log: $(gh pr merge 123 --squash)"', "dollar-subshell command substitution inside double-quoted payload"),
    ('gh pr comment 999 --body $(gh pr merge 123 --squash)', "dollar-subshell command substitution inside unquoted payload"),
    ('gh pr comment 999 --body `gh pr merge 123 --squash`', "backtick command substitution inside unquoted payload"),
    ('echo "note #" ; gh pr merge 999', "double-quoted string with hash followed by semicolon and merge command"),
    ("echo 'note #' ; gh pr merge 999", "single-quoted string with hash followed by semicolon and merge command"),
    ('echo "closes #1156, needs review" ; gh pr merge 1157 --squash', "double-quoted issue reference with hash followed by semicolon and merge command"),
    ('echo "closes #1156, needs review" && gh pr merge 1157 --squash', "double-quoted issue reference with hash followed by double-ampersand and merge command"),
    ('gh pr merge 123 --reviewer "please --allow-merge this"', "unauthorized merge with --allow-merge forged inside unmasked flag value"),
    ('gh pr merge 123 "junk --allow-merge junk"', "unauthorized merge with --allow-merge forged inside positional argument"),
    ('gh pr comment 999 --body "Log: `gh pr merge 123 --squash`"', "backtick subshell inside double-quoted payload"),
    ('gh pr comment 999 --body "Log: $(gh pr merge 123 --squash)"', "dollar-subshell inside double-quoted payload"),
    ('"gh" pr merge 123', "quoted executable name gh"),
    ("'gh' pr merge 123", "single-quoted executable name gh"),
    ('gh "pr" merge 123', "quoted subcommand pr"),
    ('gh pr "merge" 123', "quoted subcommand merge"),
    ('g""h pr merge 123', "empty quote concatenation inside executable name"),
    ('"glab" mr merge 12', "quoted executable name glab"),
    ('glab "mr" "merge" 12', "quoted subcommands mr and merge"),
    ('"/usr/bin/gh" pr merge 123', "quoted full executable path"),
    ('gh${IFS}pr${IFS}merge 123', "IFS word-split gh pr merge"),
    ('gh$IFS pr$IFS merge 123', "short IFS word-split gh pr merge"),
    ('gh$(true) pr merge 123', "subshell expansion inside executable name gh"),
    ('GH=gh; $GH pr merge 123', "variable indirection for gh executable name"),
    # --- ai-config#1279 defect 2: anchoring must not UNDER-block ------------
    # Every command position within a segment still counts. Splitting happens on
    # `;`, `&&`, `||`, `|` and newlines, so what remains inside a segment is a
    # background `&`, a subshell/command-substitution opener, and the start.
    ("sleep 1 & gh pr merge 411", "background & is still a command position"),
    ("$EMPTY gh pr merge 411", "empty variable expansion before the command word"),
    ("${EMPTY} gh pr merge 411", "braced empty variable expansion before the command word"),
    ("cd /tmp && ALLOW_MERGE=0 gh pr merge 411", "ALLOW_MERGE=0 is not an override"),
    ("cd /tmp && echo ALLOW_MERGE=1 && gh pr merge 411", "override in a DIFFERENT segment does not authorize the merge segment"),
    ("cat <<EOF\n$(gh pr merge 411)\nEOF", "live subshell inside an UNQUOTED heredoc still executes"),
    ("cat <<EOF\n`gh pr merge 411`\nEOF", "live backtick inside an UNQUOTED heredoc still executes"),
    # Heredoc masking must not become a hiding place. A `<<WORD` that is only
    # TEXT introduces no heredoc, so it must not blank the lines beneath it --
    # that would fail OPEN, masking a real merge rather than merely over-warning.
    ('echo "see <<EOF for details"\ngh pr merge 411',
     "a quoted <<EOF is not a heredoc, so the next line is still scanned"),
    ("echo 'mentions <<BODY somewhere'\ngh pr merge 411",
     "a single-quoted <<BODY is not a heredoc either"),
    ('grep -n "<<HEREDOC" notes.txt\ngh pr merge 411',
     "a grep pattern containing << does not mask what follows"),
    ("grep foo <<<PAYLOAD\ngh pr merge 411",
     "a bare-word <<< herestring is not a heredoc introducer"),
]

ALLOW = [
    ("gh pr view 411", "read-only gh pr view"),
    ("gh api /repos/owner/repo/pulls/123/merge", "read-only REST GET PR merge status check"),
    ("gh pr checkout merge", "checking out branch named merge"),
    ("gh pr list --label merge", "listing PRs with label merge"),
    ("gh search prs -s \"gh pr merge\"", "searching PRs with search flag -s containing merge text"),
    ("grep \"gh pr merge\" README.md", "grep search for gh pr merge string in docs"),
    ("git log --grep \"gh pr merge\"", "git log search for gh pr merge"),
    ("gh pr comment 123 --body-file /tmp/gh-pr-merge-notes.txt", "unquoted body-file path containing hyphens and merge keyword"),
    ('gh pr comment 123 --body "He said \\"gh pr merge\\""', "comment with escaped quotes around trigger text"),
    ('gh pr comment 123 -f text="Discussing gh pr merge"', "comment with -f text field containing trigger text"),
    ('gh api /repos/owner/repo/issues/1/comments -f body="Discussing gh pr merge command"', "gh api -f body payload containing trigger text"),
    ('gh pr merge 123 --body "Merging PR" --allow-merge', "--allow-merge flag after quoted --body string"),
    ('gh pr merge 123 --body "Fix #1156" --allow-merge', "--allow-merge after body containing #"),
    ("gh pr comment 1157 --body \"This hook blocks unauthorized\ngh pr merge attempts.\"", "multiline body string containing trigger text across newlines"),
    ("gh pr comment 411 --body 'gh pr merge failed'", "quoted string containing trigger text"),
    ("gh pr comment 411 --body 'ALLOW_MERGE=1 in comment body'", "ALLOW_MERGE inside string argument"),
    ("gh pr comment 999 --body 'Log: `gh pr merge 123 --squash`'", "backtick inside single-quoted payload (inert)"),
    ("gh pr comment 999 --body 'Log: $(gh pr merge 123 --squash)'", "dollar-subshell inside single-quoted payload (inert)"),
    ("ALLOW_MERGE=1 gh pr merge 411 --squash", "explicit ALLOW_MERGE=1 env flag"),
    ('ALLOW_MERGE="1" gh pr merge 411 --squash', "explicit ALLOW_MERGE=\"1\" env flag with double quotes"),
    ("ALLOW_MERGE='1' gh pr merge 411 --squash", "explicit ALLOW_MERGE='1' env flag with single quotes"),
    ("echo ALLOW_MERGE=1 && gh pr view 411", "ALLOW_MERGE in benign command"),
    ('gh pr comment 999 --body "Ran $(pwd) today. Reminder: never run gh pr merge without asking."', "double-quoted payload mixing subshell with prose mentioning gh pr merge"),
    ("echo Even though pr merge conflicts arose it is fine", "prose sentence containing though followed by pr merge"),
    ("echo high pr merge priority task", "prose sentence containing high followed by pr merge"),
    # --- ai-config#1279 defect 4: the documented override must authorize ----
    # SPLIT leaves the separator's trailing space on the NEXT segment, so every
    # override after a `cd &&` used to fail the `^`-anchored ALLOW_MERGE regex.
    ("cd /tmp && ALLOW_MERGE=1 gh pr merge 411 --squash",
     "ALLOW_MERGE=1 after cd && (leading whitespace in segment)"),
    ("cd /repo && ALLOW_MERGE=1 gh pr merge 1226 -R o/r --squash --delete-branch 2>&1",
     "the exact reported override form: cd && override + 2>&1 redirect"),
    (" ALLOW_MERGE=1 gh pr merge 411", "ALLOW_MERGE=1 with plain leading whitespace"),
    ("\tALLOW_MERGE=1 gh pr merge 411", "ALLOW_MERGE=1 with a leading tab"),
    ("echo start; ALLOW_MERGE=1 gh pr merge 411", "ALLOW_MERGE=1 after a semicolon separator"),
    ('cd /tmp && ALLOW_MERGE="1" gh pr merge 411', "quoted ALLOW_MERGE after cd &&"),
    # --- ai-config#1279 defect 2: prose, quotes, greps and literals ---------
    # fail-fast.md: "test that mentions, greps, and quotes of the gated command
    # pass". Blocking these is what stopped the guard being documented, bug-
    # reported, or debugged from an agent session at all.
    ('echo "This hook blocks gh pr merge without an override"',
     "prose MENTION of the command inside a double-quoted string"),
    ("echo 'the gh pr merge guard fired again'",
     "prose mention inside a single-QUOTED string"),
    ('grep -rn "blocked: gh pr merge" hooks/',
     "GREP pattern with the command name not at the quote boundary"),
    ("""python3 -c "seg = 'ALLOW_MERGE=1 gh pr merge 1226 -R o/r'; print(seg)\"""",
     "Python STRING LITERAL holding the failing segment (the blocked diagnostic)"),
    ('printf "%s\\n" "MECHANISTIC PROHIBITION: gh pr merge is strictly blocked"',
     "the guard's own refusal text quoted back"),
    ("cat <<'EOF'\nMECHANISTIC PROHIBITION: `gh pr merge` is strictly blocked.\nEOF",
     "quoted heredoc carrying the guard's own refusal text (the blocked bug report)"),
    ("gh issue create --body-file - <<'BODY'\nRunning `gh pr merge` is blocked.\nBODY",
     "quoted heredoc body for gh issue create (the ai-config#1279 filing shape)"),
]


def verdict(cmd: str, env: dict = None, extra: dict = None) -> str:
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    payload.update(extra or {})
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode} on {cmd!r}\n{p.stderr.strip()}")
    return "BLOCK" if '"permissionDecision": "deny"' in p.stdout else "allow"


wrong = 0
print("should BLOCK:")
for cmd, desc in BLOCK:
    v = verdict(cmd)
    wrong += (v != "BLOCK")
    print(f"  {v:<6} {desc}")

print("\nshould ALLOW:")
for cmd, desc in ALLOW:
    v = verdict(cmd)
    wrong += (v != "allow")
    print(f"  {v:<6} {desc}")

# Test active MWC grant integration and session isolation with sanitized session IDs.
# Invoked through `bash` rather than executed directly: on Windows a .sh file is
# not a valid executable image, so the direct form raised WinError 193 and every
# MWC case below -- including the cross-session isolation one -- never ran at all.
script_path = Path(__file__).parent.parent / "skills" / "session-lock" / "scripts" / "ai-session.sh"
session_a = f"session:mwc-a/{os.getpid()}"
session_b = f"session:mwc-b/{os.getpid()}"
# Filename-shaped, like a real harness session id, so a transcript path can
# round-trip it. Session A's id cannot -- that is the point of A's shape.
session_c = f"mwc-c-{os.getpid()}"


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
from findbash import find_bash  # noqa: E402

BASH = find_bash(script_path)
if BASH is None:
    sys.exit("FATAL: no bash able to run ai-session.sh; set AI_SESSION_BASH. "
             "The MWC authorization cases cannot be verified without it.")


def ai_session(*args):
    return subprocess.run([BASH, str(script_path), *args],
                          check=True, capture_output=True)


ai_session("register", "--id", session_a)
ai_session("register", "--id", session_b)
ai_session("register", "--id", session_c)
ai_session("enable-mwc", "--id", session_a)
ai_session("enable-mwc", "--id", session_c)

try:
    # Session A (sanitized) has MWC enabled -> allowed
    env_a = dict(os.environ, AI_SESSION_ID=session_a)
    v_a = verdict("gh pr merge 411 --squash", env=env_a)
    wrong += (v_a != "allow")
    print(f"  {v_a:<6} active MWC grant for sanitized session A")

    # Session B (sanitized) does NOT have MWC enabled -> blocked (cross-session isolation)
    env_b = dict(os.environ, AI_SESSION_ID=session_b)
    v_b = verdict("gh pr merge 411 --squash", env=env_b)
    wrong += (v_b != "BLOCK")
    print(f"  {v_b:<6} cross-session isolation for sanitized session B")

    # ai-config#1279 defect 1: the hook process inherits NEITHER AI_SESSION_ID
    # nor CLAUDE_SESSION_ID, so an env-only lookup could never see a grant made
    # the sanctioned way (`/mwc` -> `ai-session.sh enable-mwc --id <harness id>`).
    # The harness's own `session_id` payload field is that same id, so the grant
    # must be honoured from the payload with no session env var set at all.
    env_bare = {k: v for k, v in os.environ.items()
                if k not in ("AI_SESSION_ID", "CLAUDE_SESSION_ID")}
    v_pay = verdict("gh pr merge 411 --squash", env=env_bare,
                    extra={"session_id": session_a})
    wrong += (v_pay != "allow")
    print(f"  {v_pay:<6} MWC grant honoured from the payload session_id (no env var)")

    # Same, via the transcript filename stem, for a harness that omits the
    # field. Uses session C, whose id is filename-shaped like a real harness
    # UUID -- session A's id deliberately contains `/` and `:` to exercise
    # sanitize(), and no filename can carry those back.
    v_tr = verdict("gh pr merge 411 --squash", env=env_bare,
                   extra={"transcript_path": f"/tmp/projects/x/{session_c}.jsonl"})
    wrong += (v_tr != "allow")
    print(f"  {v_tr:<6} MWC grant honoured from the transcript_path stem")

    # Cross-session isolation must survive the new resolution path: session B
    # holds no grant, so a payload naming B is still blocked.
    v_pay_b = verdict("gh pr merge 411 --squash", env=env_bare,
                      extra={"session_id": session_b})
    wrong += (v_pay_b != "BLOCK")
    print(f"  {v_pay_b:<6} payload session_id for ungranted session B still blocks")

    # No identity at all -> no grant can be resolved -> block (fails closed).
    v_none = verdict("gh pr merge 411 --squash", env=env_bare)
    wrong += (v_none != "BLOCK")
    print(f"  {v_none:<6} no session identity anywhere still blocks")

    # Disable MWC for Session A -> must block immediately
    ai_session("disable-mwc", "--id", session_a)
    v_a_revoked = verdict("gh pr merge 411 --squash", env=env_a)
    wrong += (v_a_revoked != "BLOCK")
    print(f"  {v_a_revoked:<6} revoked MWC grant blocks for session A")
finally:
    ai_session("release", "--id", session_a)
    ai_session("release", "--id", session_b)
    ai_session("release", "--id", session_c)

# The command-position anchor makes every `;`, `&`, backtick and `$(` a place
# the matcher restarts. With an UNBOUNDED expansion prefix each of those N
# restarts rescanned the rest of a long substitution run before failing, which
# is quadratic: 610ms on 800 chained backtick pairs, against 2.8ms for the
# pre-anchor matcher, on a hook that runs before EVERY Bash call. Bounding the
# repetition restores linear behaviour (~19ms at 1600).
#
# The threshold is deliberately loose -- this asserts the SHAPE of the growth,
# not a runtime budget, so it survives a slow or loaded runner. A reintroduced
# quadratic lands near 2.4s here, over an order of magnitude past the bound.
import importlib.util  # noqa: E402
import time  # noqa: E402

_spec = importlib.util.spec_from_file_location("_guard", HOOK)
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)
_adversarial = "`x` " * 1600 + "echo hi"
_t0 = time.perf_counter()
_guard.offending(_adversarial)
_elapsed = time.perf_counter() - _t0
wrong += (_elapsed > 1.0)
print(f"  {'allow' if _elapsed <= 1.0 else 'SLOW ':<6} "
      f"1600 chained substitutions scanned in {_elapsed * 1000:.0f}ms (bound 1000ms)")

total = len(BLOCK) + len(ALLOW) + 8
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
