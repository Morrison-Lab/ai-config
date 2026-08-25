#!/usr/bin/env python3
"""Tests for require-agent-disclosure.py.

The cases that matter are the near-misses, per
`shared/workflow/algorithmatize-checks.md`: a matcher that fires on every
`gh pr comment` is useless, and one that fires on none of them is invisible.
"""
import importlib.util
import json
import pathlib
import subprocess
import sys

_spec = importlib.util.spec_from_file_location(
    "guard", pathlib.Path(__file__).with_name("require-agent-disclosure.py"))
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

MARKER = "_Posted by Claude Code (AI agent) --- not written by a human._"


def GQL(body):
    """The corpus's verbatim addDiscussionComment command, with `body` in it."""
    return ("gh api graphql -f discussionId='<id>' -f body='" + body
            + "' -f query='\n"
            "  mutation($discussionId: ID!, $body: String!) {\n"
            "    addDiscussionComment(input: {discussionId: $discussionId, "
            "body: $body}) {\n      comment { id url }\n    }\n  }'")

# (label, command, expect_warning)
CASES = [
    # --- must warn -----------------------------------------------------------
    ("bare pr comment",
     'gh pr comment 12 --body "Working on this."', True),
    ("bare issue comment",
     'gh issue comment 12 --body "Working on this."', True),
    ("glab mr note",
     'glab mr note create 12 --message "Working on this."', True),
    ("glab issue note",
     'glab issue note 12 --message "Working on this."', True),
    ("gh pr review",
     'gh pr review 12 --comment --body "Looks fine."', True),
    ("prose self-id is not the marker",
     'gh pr comment 12 --body "Claude Code CLI (local session) is working on this."',
     True),

    # --- must NOT warn -------------------------------------------------------
    ("marker present",
     f'gh pr comment 12 --body "Working on this.\n\n{MARKER}"', False),
    ("marker with another agent name",
     'gh pr comment 12 --body "Done.\n\n_Posted by Codex (AI agent) -- not a human._"',
     False),
    ("dependabot rebase is exempt",
     'gh pr comment 12 --repo o/r --body "@dependabot rebase"', False),
    ("dependabot squash is exempt",
     'gh pr comment 12 --repo o/r --body "@dependabot squash and merge"', False),
    ("renovate is exempt",
     'gh pr comment 12 --body "@renovate rebase"', False),

    # --- not a comment-posting command at all --------------------------------
    ("reading comments is not posting",
     'gh pr view 12 --json comments', False),
    ("issue create is not a comment",
     'gh issue create --title x --body "y"', False),
    ("git commit is not a comment",
     'git commit -m "Working on this."', False),
    # --- the near-misses this corpus generates constantly ---------------------
    ("prose merely discussing the rule",
     'echo "always end a gh pr comment with the marker"', False),
    ("a doc-writing heredoc quoting the command",
     'cat > doc.md <<\'EOF\'\ngh pr comment <N> --body "Working on this."\nEOF',
     False),
    ("grep for the command is not the command",
     'grep -rn "gh pr comment" skills/', False),
    ("a chained real command still warns",
     'git push && gh pr comment 12 --body "Pushed."', True),
    ("a variable elsewhere does not hide a visible marker",
     f'gh pr comment "$N" --repo "$REPO" --body "Done.\n\n{MARKER}"', False),

    # --- forms the first version missed entirely (review findings 2, 12) ------
    ("gh api issues comments",
     'gh api repos/o/r/issues/12/comments -f body="Working on this."', True),
    ("gh api review-thread reply",
     'gh api repos/o/r/pulls/12/comments/9/replies -f body="Addressed."', True),
    ("gh api reply WITH marker",
     f'gh api repos/o/r/pulls/12/comments/9/replies -f body="Addressed.\n\n{MARKER}"',
     False),
    ("glab mr comment alias",
     'glab mr comment 12 --message "Working on this."', True),
    ("glab issue comment alias",
     'glab issue comment 12 --message "Working on this."', True),
    ("command after then",
     'if true; then gh pr comment 12 --body "bare"; fi', True),
    ("negated command",
     '! gh pr comment 12 --body "bare"', True),
    ("command inside a do-loop",
     'for n in 1 2; do gh pr comment $n --body "bare"; done', True),

    # --- one marker must not vouch for a sibling (review finding 4) -----------
    ("a disclosed comment does not vouch for an undisclosed sibling",
     f'gh pr comment 1 --body "a\n\n{MARKER}" && gh pr comment 2 --body "b"',
     True),
    ("both disclosed is silent",
     f'gh pr comment 1 --body "a\n\n{MARKER}" && gh pr comment 2 --body "b\n\n{MARKER}"',
     False),
    ("a grep for the marker does not vouch for a bare comment",
     'grep -rn "Posted by Claude Code (AI agent)" . ; gh pr comment 2 --body "bare"',
     True),

    # --- heredocs: body when piped, prose when written (review finding 3) -----
    ("heredoc IS the body, and discloses",
     'gh pr comment 12 --body-file - <<\'EOF\'\nDone.\n\n' + MARKER
     + '\nEOF', False),
    # `--body-file -` is genuinely unreadable-by-flag, and the heredoc makes the
    # body visible anyway -- so this must report MISSING, not "cannot read".
    ("heredoc IS the body, and does not disclose",
     'gh pr comment 12 --body-file - <<\'EOF\'\nDone, undisclosed.\nEOF', "missing"),
    ("a doc heredoc does not silence a real sibling command",
     'cat > d.md <<\'EOF\'\ngh pr comment <N> --body "x"\nEOF\ngh pr comment 2 --body "bare"',
     True),
    # The fixture above proves only that the sibling is SEEN. This one proves
    # the heredoc cannot vouch for it: the doc being written quotes the marker
    # verbatim, which is the normal shape when editing this very corpus.
    ("a heredoc quoting the marker does not vouch for a bare sibling",
     'cat > frag.md <<\'EOF\'\nEnd every body with:\n\n' + MARKER
     + '\nEOF\ngh pr comment 2 --body "bare claim"', True),

    # --- the exemption is whole-body, not first-token (review finding 8) ------
    ("a bot handle followed by prose for humans is NOT exempt",
     'gh pr comment 12 --body "@dependabot rebase please, and a note for the '
     'humans reading this thread: I will also rerun CI"', True),
    ("the review re-request is exempt",
     'gh pr comment 12 --body "@' + 'claude review"', False),

    # --- a READ is not a post; round-2 review finding 3 ----------------------
    ("gh api GET of comments is a read, not a post",
     'gh api repos/o/r/issues/12/comments --paginate | jq -s \'.\'', False),
    ("gh pr review --approve posts no prose",
     'gh pr review 12 --approve', False),
    ("gh pr review WITH a body is a post",
     'gh pr review 12 --request-changes --body-file /tmp/r.md', None),

    # --- forge-API comment routes; round-2 review finding 8 ------------------
    ("glab api discussion note",
     'glab api -X POST "projects/:id/merge_requests/5/discussions/9/notes" '
     '-f body="Addressed."', True),
    ("gh api graphql addDiscussionComment",
     "gh api graphql -f body='Moved.' -f query='mutation { "
     "addDiscussionComment(input:{}) { comment { url } } }'", True),
    ("gh api graphql addDiscussionComment WITH marker",
     "gh api graphql -f body='Moved.\n\n" + MARKER + "' -f query='mutation { "
     "addDiscussionComment(input:{}) { comment { url } } }'", False),

    # --- the exemption must survive a trailing token; round-2 finding 5 ------
    ("chores site verbatim, with its trailing comment",
     'gh pr comment "$N" --repo "$REPO" --body "@dependabot rebase"   '
     '# COMMENT_PR', False),
    ("bot body followed by another flag",
     'gh pr comment 12 --body "@dependabot rebase" --repo o/r', False),

    # --- VERBATIM corpus command lines; round-3 review findings 2 and 7 ------
    #
    # The earlier fixtures for these were single-line inventions, and both
    # passed while the detector matched nothing the corpus actually writes --
    # `fixtures-are-not-evidence` exactly. These are copied from the skills.
    ("ard's GitHub review-thread reply, with its line continuation",
     'gh api "repos/{owner}/{repo}/pulls/<N>/comments" \\\n'
     '  -F in_reply_to="<comment_id>" -F body="@/tmp/reply-<comment_id>.md"',
     None),
    ("ard's GitLab discussion note, with its line continuation",
     'glab api -X POST "projects/:id/merge_requests/<N>/discussions/<d>/notes" \\\n'
     '  -F body="@/tmp/reply-<d>.md"', None),
    ("discussions' multi-line addDiscussionComment, no marker",
     "gh api graphql -f discussionId='<id>' -f body='<reply text>' -f query='\n"
     "  mutation($discussionId: ID!, $body: String!) {\n"
     "    addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {\n"
     "      comment { id url }\n    }\n  }'", "missing"),
    ("discussions' multi-line addDiscussionComment, WITH marker",
     "gh api graphql -f discussionId='<id>' -f body='<reply text>\n\n" + MARKER
     + "' -f query='\n  mutation($discussionId: ID!, $body: String!) {\n"
     "    addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {\n"
     "      comment { id url }\n    }\n  }'", False),

    # --- precision on ordinary corpus reads; round-3 findings 3, 4, 11 -------
    ("the review-verdict read CLAUDE.md prescribes",
     "gh api repos/o/r/issues/12/comments --paginate | jq -s '.'", False),
    ("an incidental robot emoji is a missing marker, not a wrong one",
     'gh pr comment 5 --body "\U0001f916 CI regenerated the snapshots."',
     "missing"),
    ("-b with an expanded variable is unreadable, like --body",
     'gh pr comment 5 -b "$BODY"', None),
    # A MID-STRING `$VAR` is the case the whole-value fixture above cannot see:
    # HAS_INLINE_BODY_RE rejects only a value BEGINNING with `$`, so a round-6
    # edit deleted the short-flag clause as "dead" and this shape started
    # reporting a missing marker over a body the check never read.
    ("-b with a mid-string expansion is still unreadable",
     'gh pr comment 5 -b "Addressed in $SHA."', None),
    ("-f body= with a mid-string expansion is unreadable",
     'gh pr comment 5 -f body="Addressed in $SHA."', None),
    ("-F \"body=...\" with a mid-string expansion is unreadable",
     'gh pr comment 5 -F "body=Addressed in $SHA."', None),
    ("--body with a mid-string expansion is unreadable",
     'gh pr comment 5 --body "Addressed in $SHA."', None),
    # A single-quoted `$` does not expand in bash, so this body IS readable --
    # and it is reported unreadable anyway, deliberately. The `--body`/`--message`
    # clause has always behaved this way, so the short forms match it rather than
    # diverging, and the error is toward the weaker note rather than toward an
    # assertion about text never read. Pinned so the choice is visible as one.
    ("a single-quoted $ is reported unreadable, matching --body's behaviour",
     "gh pr comment 5 -b 'costs $9'", None),
    ("--raw-field body= is inline and readable",
     'gh api repos/o/r/issues/12/comments --raw-field body="hi"', "missing"),
    ("-F body=@file is a file reference, so unreadable",
     'gh api repos/o/r/issues/12/comments -F body="@/tmp/b.md"', None),

    # --- round-4: the body sits INSIDE what used to be the gap ---------------
    #
    # The round-3 GraphQL fixture used the 12-character placeholder
    # `<reply text>`, which has no `;`, no `&`, and fits any length bound -- so
    # it passed on the one input that concealed the bug. These vary exactly the
    # properties the old gap regex was sensitive to.
    ("GraphQL body containing a semicolon",
     GQL("Addressed; pushed."), "missing"),
    ("GraphQL body containing an ampersand",
     GQL("Fixed A & B."), "missing"),
    ("GraphQL body longer than the old 400-char bound",
     GQL("x" * 320), "missing"),
    ("GraphQL long body WITH marker",
     GQL("x" * 320 + "\n\n" + MARKER), False),

    # --- round-4: a typed -F field is not a body-file ------------------------
    ("a typed -F field does not hide a visible body",
     'gh api repos/o/r/pulls/1/comments -F in_reply_to=5 '
     '-F body="Addressed, undisclosed."', "missing"),

    # --- round-4: argument order must not decide it --------------------------
    ("gh api with the body flag before the path",
     'gh api -X POST -f body="Working on this." repos/o/r/issues/12/comments',
     "missing"),

    # --- round-5: properties a mutation could delete with the suite green ----
    #
    # Each of these was implemented and unpinned: removing the behaviour passed
    # 77/77. A property no test discriminates is one a later edit deletes for
    # free, which is the whole reason to pin it rather than to trust the code.
    ("an env-var prefix does not hide a command position",
     'GH_TOKEN=x gh pr comment 12 --body "bare"', True),
    ("ANSI-C $'...' keeps its escaped quote, so the body stays whole",
     "gh pr comment 12 --body $'Done, don\\'t worry.\n\n" + MARKER + "'",
     False),
    ("a bare /notes path is a comment target",
     'glab api -X POST "projects/:id/merge_requests/5/notes" -f body="bare"',
     True),
    # GitLab's create-a-new-thread route: `/discussions` with no `/notes` and
    # no `/comments`, so it is the only fixture that isolates that alternative.
    # The first attempt used `repos/o/r/discussions/5/comments`, which still
    # matched via `/comments` and masked the very thing it was pinning.
    ("a bare /discussions path is a comment target",
     'glab api -X POST "projects/:id/merge_requests/5/discussions" '
     '-f body="bare"', True),

    # --- round-5: `gh pr review`'s body flag may sit on a continuation line ---
    ("review with the body flag on a continuation line",
     'gh pr review 12 --request-changes \\\n  --body "Findings: one thing."',
     "missing"),
    ("review with body-file on a continuation line",
     'gh pr review 12 --comment \\\n  --body-file /tmp/r.md', None),

    # --- round-5: naming a mutation is not posting ---------------------------
    ("a command that merely NAMES the mutation posts nothing",
     'gh api graphql --input payload.json  # addDiscussionComment payload',
     False),

    # --- round-5: the `--body=` equals form is inline, not unreadable --------
    ("--body= equals form is a visible body",
     'gh pr comment 12 --body="Working on this."', "missing"),
    ("--message= equals form is a visible body",
     'glab mr note 12 --message="bare"', "missing"),
    ("--body= equals form WITH marker",
     'gh pr comment 12 --body="Done.\n\n' + MARKER + '"', False),
    ("--body= with an expanded variable is still unreadable",
     'gh pr comment 12 --body="$BODY"', None),

    # --- round-6: the QUOTED whole-argument field form ----------------------
    #
    # `tool-mappings`'s own canonical reply command writes `-F "body=@<file>"`,
    # quote first, and the field pattern required `body=` to follow whitespace
    # directly -- so the registry line this change annotates was invisible.
    ("gh api with a quoted body= argument",
     'gh api repos/o/r/issues/1/comments -f "body=Working on this."', "missing"),
    ("gh api with a quoted body= argument, WITH marker",
     'gh api repos/o/r/issues/1/comments -f "body=Done.\n\n' + MARKER + '"',
     False),
    ("the registry's own quoted body=@file reply command",
     'gh api -X POST "repos/o/r/pulls/1/comments/9/replies" -F "body=@/tmp/r.md"',
     None),
    ("a quoted typed field does not look like a body-file",
     'gh api repos/o/r/pulls/1/comments -F "in_reply_to=5" -f body="Addressed."',
     "missing"),
    ("an unquoted -F file is still a body-file",
     'gh pr comment 12 -F "/tmp/body.md"', None),

    # --- round-6: executing a GraphQL mutation vs naming one -----------------
    ("a GraphQL mutation whose body is not in a body= field",
     "gh api graphql --input p.json -f query='mutation { addDiscussionComment(x) }'",
     None),
    ("a comment mentioning the mutation posts nothing",
     'gh api graphql --input p.json  # addDiscussionComment payload', False),

    # --- round-6: properties that survived mutation with the suite green -----
    ("command substitution is a command position",
     'URL=$(gh pr comment 12 --body "bare")', True),
    ("a brace group is a command position",
     '{ gh pr comment 12 --body "bare"; }', True),
    ("the marker needs its attribution prefix, not just the parenthetical",
     'gh pr comment 12 --body "Our (AI agent) policy is documented."', "missing"),
    ("a heredoc piped into --body-file - keeps its opener tail",
     "cat <<'EOF' | gh pr comment 12 --body-file -\nDone, undisclosed.\nEOF",
     "missing"),
    # GitHub's reply route always contains `/comments`, so this is caught by
    # that alternative -- there is no separate `/replies` one to pin.
    ("the review-thread reply route is a comment target",
     'gh api "repos/o/r/pulls/1/comments/9/replies" -f body="bare"', True),

    # --- cross-vendor round: the marker must END THE BODY --------------------
    #
    # Eleven same-vendor rounds accepted a marker found ANYWHERE in the command.
    # A cross-vendor reviewer supplied all four of these on its first pass.
    ("a marker in a trailing shell comment is not in the body",
     'gh pr comment 1 --body "bare"  # ' + MARKER, "missing"),
    ("a marker followed by more human prose does not disclose",
     'gh pr comment 1 --body "Done.\n\n' + MARKER
     + '\n\nAlso, a human note."', "missing"),
    ("a partial marker does not disclose",
     'gh pr comment 1 --body "Done.\n\n_Posted by Claude Code_"', "missing"),

    # --- cross-vendor round: posting surfaces that are not named "comment" ----
    ("gh issue reopen --comment posts a comment",
     'gh issue reopen 5 -R o/r --comment "Reviving: still matters."', "missing"),
    ("gh issue close --comment posts a comment",
     'gh issue close 5 -R o/r --comment "Superseded."', "missing"),
    ("gh pr close --comment posts a comment",
     'gh pr close 5 -R o/r --comment "Superseded."', "missing"),
    ("gh issue reopen --comment WITH marker",
     'gh issue reopen 5 -R o/r --comment "Reviving.\n\n' + MARKER + '"', False),

    # --- cross-vendor round: --input and --form ------------------------------
    ("gh api --input supplies an unreadable body",
     'gh api repos/o/r/issues/1/comments --input payload.json', None),
    ("glab api --form body= is a post",
     'glab api projects/:id/merge_requests/1/notes --form body="bare"',
     "missing"),

    # --- cross-vendor round: the bot exemption is a command vocabulary -------
    ("prose after a real bot verb is not exempt",
     'gh pr comment 1 --body "@dependabot rebase please humans"', "missing"),
    ("an explicit GET is not a post",
     'gh api repos/o/r/issues/1/comments -X GET -f per_page=100', False),

    # --- push-gate round: the extractor must not warn on a COMPLIANT comment --
    #
    # A body that merely MENTIONS a field flag had that inner text taken as the
    # body, so a compliant comment about this very feature warned. A false
    # positive on a compliant comment is the worst outcome for a warn-only
    # guard.
    ("a compliant body that quotes -f body= is not a false positive",
     'gh pr comment 2130 --body "Addressed: inline_body now handles -f body= '
     'and --form body=.\n\n' + MARKER + '"', False),
    ("a compliant body that quotes -F body=@file",
     'gh pr comment 2130 --body "Rebutted: the canonical reply is -F '
     'body=@file, so the quote comes first.\n\n' + MARKER + '"', False),

    # --- push-gate round: the exemption across every accepted spelling -------
    ("bot command via --body=", 'gh pr comment 5 --body="@dependabot rebase"',
     False),
    ("bot command via -b", 'gh pr comment 5 -b "@dependabot rebase"', False),
    ("bot command via --comment",
     'gh issue close 5 -R o/r --comment "@dependabot close"', False),

    # --- push-gate round: a heredoc keeps its terminator line ----------------
    ("heredoc with a blank line before its terminator still discloses",
     "gh pr comment 5 --body-file - <<'EOF'\nHi.\n\n" + MARKER + "\n\nEOF",
     False),
    ("heredoc where prose follows the marker does not disclose",
     "gh pr comment 5 --body-file - <<'EOF'\nHi.\n\n" + MARKER
     + "\n\nAnd more human prose.\nEOF", "missing"),

    # --- push-gate round: gh pr merge has no --comment -----------------------
    ("gh pr merge --body is a merge-commit body, not a comment",
     'gh pr merge 5 -R o/r --body "merge commit body"', False),

    # --- #2185 review: the close/reopen gate must be QUOTE-AWARE -------------
    #
    # The first version used a lookahead over a raw `[^\n;&|]` tail, so a `;`
    # inside an EARLIER flag's quoted value ended the tail before `--comment`
    # and the command went undetected. `gh issue close` really does take a
    # free-text `--duplicate-of`, so this is a shape the corpus can produce.
    # Every other matcher in the guard routes through `split_segments` for this
    # reason; these now do too.
    ("a semicolon in an earlier flag does not hide --comment",
     'gh issue close 5 -R o/r --duplicate-of "see issue #3; also #4" '
     '--comment "Closing without disclosure."', "missing"),
    ("an ampersand in an earlier flag does not hide --comment",
     'gh issue close 5 -R o/r --duplicate-of "A & B" --comment "bare"',
     "missing"),
    ("a pipe in an earlier flag does not hide --comment",
     'gh pr close 5 -R o/r --title "a|b" --comment "bare"', "missing"),
    ("the same command WITH the marker stays silent",
     'gh issue close 5 -R o/r --duplicate-of "see #3; also #4" '
     '--comment "Closing.\n\n' + MARKER + '"', False),
    ("close with no --comment posts nothing",
     'gh issue close 5 -R o/r --duplicate-of "see #3"', False),
    ("reopen with no --comment posts nothing",
     'gh issue reopen 5 -R o/r', False),
    ("the -c short flag is a comment flag",
     'gh issue close 5 -R o/r -c "bare"', "missing"),

    # --- unreadable vs missing must not be confused (review finding 9) -------
    ("gh pr comment -F <file> is a body-file, reported unreadable",
     'gh pr comment 12 -F /tmp/body.md', None),
    ("--editor is unreadable",
     'gh pr comment 12 --editor', None),
]

# --- the emoji branch --------------------------------------------------------
ROBOT_CASE = (
    'gh pr comment 12 --body "Done.\n\n\U0001f916 Posted by Claude Code."')

# --- the unreadable-body branch ---------------------------------------------
INDIRECT_CASES = [
    ("body-file", 'gh pr comment 12 --body-file /tmp/b.md'),
    ("api body file", 'gh pr comment 12 -F body=@/tmp/b.md'),
    ("variable body", 'gh pr comment 12 --body "$BODY"'),
]


def run():
    failed = 0
    for label, command, expect in CASES:
        reason = guard.verdict(command)
        if expect == "missing":
            ok = reason is not None and "no agent-disclosure marker" in reason
            print(f"{'PASS' if ok else 'FAIL'}: {label} "
                  f"(reported missing={ok})")
        elif expect is None:
            # Must warn, and specifically about a body it could not read --
            # accusing a command of omitting a marker never seen is the
            # misdiagnosis review finding 9 named.
            ok = reason is not None and "cannot read" in reason
            print(f"{'PASS' if ok else 'FAIL'}: {label} "
                  f"(reported unreadable={ok})")
        else:
            got = reason is not None
            ok = got == expect
            print(f"{'PASS' if ok else 'FAIL'}: {label} "
                  f"(warned={got}, expected={expect})")
        failed += not ok

    reason = guard.verdict(ROBOT_CASE)
    ok = reason is not None and "robot emoji" in reason
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'}: a robot-emoji disclosure is named as "
          f"the wrong marker")

    # Review finding 14: a body merely MENTIONING the emoji discloses nothing,
    # so the emoji advice would be inapplicable and would displace the real one.
    mention = 'gh pr comment 12 --body "The \U0001f916 badge broke; rerunning."'
    reason = guard.verdict(mention)
    ok = reason is not None and "robot emoji" not in reason
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'}: merely mentioning the emoji is not "
          f"treated as disclosing with it")

    for label, command in INDIRECT_CASES:
        reason = guard.verdict(command)
        ok = reason is not None and "cannot read" in reason
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {label} reports an unreadable body "
              f"rather than a missing marker")

    # The hook must never block. Its only output shape is additionalContext.
    src = pathlib.Path(__file__).with_name(
        "require-agent-disclosure.py").read_text(encoding="utf-8")
    body = src.split('"""', 2)[-1]
    ok = "permissionDecision" not in body
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'}: the hook warns and never denies")

    # End-to-end through stdin, because `verdict()` returning a string proves
    # only that the text was COMPUTED. Whether the harness ever surfaces it is a
    # fact about the emitted JSON, and a test asserting bool(verdict) cannot
    # tell a surfaced warning from discarded output.
    for label, payload, expect_warning in (
        ("a bare comment emits additionalContext",
         {"tool_name": "Bash",
          "tool_input": {"command": 'gh pr comment 12 --body "Working on this."'}},
         True),
        ("a disclosed comment emits nothing",
         {"tool_name": "Bash",
          "tool_input": {"command": f'gh pr comment 12 --body "Done.\n\n{MARKER}"'}},
         False),
        ("a non-Bash tool emits nothing",
         {"tool_name": "Edit", "tool_input": {"command": "gh pr comment 1 --body x"}},
         False),
        ("malformed stdin fails open", "not json at all", False),
    ):
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        proc = subprocess.run(
            [sys.executable,
             str(pathlib.Path(__file__).with_name("require-agent-disclosure.py"))],
            input=stdin, capture_output=True, text=True)
        out = proc.stdout.strip()
        if expect_warning:
            try:
                emitted = json.loads(out)["hookSpecificOutput"]
            except Exception:
                emitted = {}
            try:
                whole = json.loads(out)
            except Exception:
                whole = {}
            ok = (proc.returncode == 0
                  and emitted.get("hookEventName") == "PreToolUse"
                  and "additionalContext" in emitted
                  and "permissionDecision" not in emitted
                  and "disclosure marker" in emitted.get("additionalContext", "")
                  # The user-facing half. Warning only the model leaves the
                  # account holder unaware a comment posted under their login
                  # was flagged, and check-hook-output-shape.py's systemMessage
                  # rule fires on Stop hooks only, so nothing else pins this.
                  and isinstance(whole.get("systemMessage"), str)
                  and "agent" in whole.get("systemMessage", ""))
        else:
            ok = proc.returncode == 0 and out == ""
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {label}")

    # Review finding 10: a remote/web session has no `gh`, so MCP is its only
    # path -- a Bash-only guard is silent exactly where the CLI is absent.
    for label, tool, body, expect in (
        ("MCP add_issue_comment bare", "mcp__github__add_issue_comment",
         "Working on this.", True),
        ("MCP add_issue_comment disclosed", "mcp__github__add_issue_comment",
         "Working on this.\n\n" + MARKER, False),
        ("MCP review reply bare",
         "mcp__github__add_reply_to_pull_request_comment", "Addressed.", True),
        ("MCP bot-command body is exempt", "mcp__github__add_issue_comment",
         "@dependabot rebase", False),
        # Round-4: verdict_mcp used to synthesize `--body "<body>"` to reuse the
        # shell-shaped pattern, so a quote INSIDE the body closed that synthetic
        # argument early and faked the exemption.
        ("MCP body with an embedded quote does not fake the exemption",
         "mcp__github__add_issue_comment",
         '@dependabot rebase" and a long note for the humans reading this',
         True),
        ("a non-comment MCP tool is out of scope",
         "mcp__github__create_pull_request", "Closes #1", False),
        # Round-5: three of the five MCP tools were unpinned -- removing any of
        # them from MCP_POST_TOOLS passed the whole suite.
        ("MCP pending-review comment", "mcp__github__add_comment_to_pending_review",
         "Bare finding.", True),
        ("MCP review write", "mcp__github__pull_request_review_write",
         "Bare review body.", True),
        ("MCP discussion comment", "mcp__github__discussion_comment_write",
         "Bare discussion reply.", True),
        # The end-anchoring fix landed on the Bash path only, and no MCP
        # fixture covered it -- 121 green cases did not catch a marker followed
        # by human prose on the route a remote session must use.
        ("MCP marker followed by human prose does not disclose",
         "mcp__github__add_issue_comment",
         "Working on this.\n\n" + MARKER + "\n\nAlso: please look at CI.",
         True),
        ("MCP marker first, prose after, does not disclose",
         "mcp__github__add_issue_comment",
         MARKER + "\n\nWorking on this, and a long human paragraph.", True),
        ("MCP discussion comment WITH marker",
         "mcp__github__discussion_comment_write",
         "Reply.\n\n" + MARKER, False),
        # Round-6: the isinstance guard exists for review methods that submit no
        # body at all (resolve_thread, delete_pending); nothing pinned it.
        ("an MCP call with no body is not judged",
         "mcp__github__pull_request_review_write", None, False),
    ):
        payload = {} if body is None else {"body": body}
        got = guard.verdict_mcp(tool, payload) is not None
        ok = got == expect
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {label} "
              f"(warned={got}, expected={expect})")

    total = len(CASES) + 2 + len(INDIRECT_CASES) + 1 + 4 + 13
    print(f"\n{total - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
