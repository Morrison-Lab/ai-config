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
    # A shell keyword's operand is still a command word. Narrowing CMD_POS to
    # punctuation-only dropped these, which fail OPEN: each is executable bash
    # that runs the merge (ai-config#1287 review).
    ("! gh pr merge 411", "`!` only inverts the exit status; the merge still runs"),
    ("time gh pr merge 411", "`time` wraps and runs its operand"),
    ("nohup gh pr merge 411", "`nohup` wraps and runs its operand"),
    ("sudo gh pr merge 411", "`sudo` wraps and runs its operand"),
    ("{ gh pr merge 411; }", "a brace group's body is at a command position"),
    ("if true; then gh pr merge 411; fi", "a `then` branch body is at a command position"),
    ("while true; do gh pr merge 411; done", "a `do` body is at a command position"),
    ("if gh pr merge 411; then echo ok; fi", "an `if` CONDITION runs too"),
    ("if false; then echo no; else gh pr merge 411; fi", "an `else` branch body"),
    ("if false; then echo no; elif gh pr merge 411; then echo ok; fi", "an `elif` condition"),
    ("while gh pr merge 411; do echo ok; done", "a `while` condition"),
    ("until gh pr merge 411; do echo ok; done", "an `until` condition"),
    ("! time gh pr merge 411", "stacked keywords"),
    ("time ${EMPTY} gh pr merge 411", "a keyword followed by an empty expansion"),
    # Pass 2. The first two below were the SECOND round of reported bypasses,
    # and the rest are the same class unreported -- which is the point: pass 2
    # stops enumerating what may precede a command word and blanks what cannot
    # run instead, so a construct nobody thought of blocks rather than slipping.
    ("case $x in merge) gh pr merge 411 ;; esac", "a one-line case arm"),
    ("f() { gh pr merge 411; }; f", "a function defined and then called"),
    ("case $x in\n  a) gh pr merge 411 ;;\nesac", "a multi-line case arm"),
    ("for i in 1 2; do gh pr merge 411; done", "a for-loop body"),
    ("f() {\n  gh pr merge 411\n}\nf", "a multi-line function body"),
    ("coproc gh pr merge 411", "coproc"),
    ("nice -n 5 gh pr merge 411", "a wrapper carrying a flag"),
    ("timeout 30 gh pr merge 411", "a wrapper carrying a positional argument"),
    ("setsid gh pr merge 411", "a wrapper in no keyword list"),
    ("xargs gh pr merge", "xargs"),
    ("[[ -f x ]] && gh pr merge 411", "after a conditional expression"),
    ("case $x in *) command gh pr merge 411 ;; esac", "a case arm plus an exec wrapper"),
    # Quoted, but bash evaluates it later -- so "a quoted span is inert" is
    # WRONG here. mask_inert_quotes now recognises an executor's own operand
    # and keeps it live, which is what carries these; they no longer depend on
    # the narrow pass.
    ("trap 'gh pr merge 411' EXIT", "a trap handler runs its single-quoted operand"),
    ("watch 'gh pr merge 411'", "watch runs its quoted operand"),
    # A heredoc body is inert only where its CONSUMER treats it as data. Fed to
    # a shell it is a script, and masking it hid the merge from both passes.
    # The quoted-delimiter form is no exception: `<<'EOF'` suppresses expansion,
    # and bash still runs what it reads.
    ("bash <<EOF\ngh pr merge 411\nEOF", "a heredoc fed to bash is a script"),
    ("sh <<EOF\ngh pr merge 411\nEOF", "a heredoc fed to sh"),
    ("bash -s <<EOF\ngh pr merge 411\nEOF", "bash -s reads the body as a script"),
    ("ssh myhost <<EOF\ngh pr merge 411\nEOF", "ssh sends the body to a remote shell"),
    ("ssh -T user@host <<EOF\ngh pr merge 411\nEOF", "ssh with a flag and a host"),
    ("bash <<'EOF'\ngh pr merge 411\nEOF", "a QUOTED delimiter still executes under bash"),
    ("cd /r && bash <<EOF\ngh pr merge 411\nEOF", "the executor in a later segment"),
    ("/usr/bin/bash <<EOF\ngh pr merge 411\nEOF", "an absolute-path executor"),
    ("ssh host 'gh pr merge 411'", "a positional hostname between executor and operand"),
    # The heredoc anchor gets the SAME keyword/wrapper prefixes the matching
    # passes do, because it is built from the same LEAD. Hand-rolling a second
    # anchor is what let these through.
    ("sudo bash <<EOF\ngh pr merge 411\nEOF", "a wrapper before the heredoc's executor"),
    ("time bash <<EOF\ngh pr merge 411\nEOF", "a keyword before the executor"),
    ("! bash <<EOF\ngh pr merge 411\nEOF", "a negation before the executor"),
    ("if true; then bash <<EOF\ngh pr merge 411\nEOF\nfi", "a then-body executor"),
    ("nohup ssh h <<EOF\ngh pr merge 411\nEOF", "a wrapper before ssh"),
    ("{ bash <<EOF\ngh pr merge 411\nEOF\n}", "a brace-group executor"),
    ("FOO=1 bash <<EOF\ngh pr merge 411\nEOF", "an env assignment before the executor"),
    # A wrapper carrying its OWN argument. The keyword list has no way to
    # express `sudo -u x` or `timeout 30`, so the masking anchor uses the
    # permissive lead: over-detecting an executor only declines to mask, which
    # scans more text rather than less.
    ("sudo -u x bash <<EOF\ngh pr merge 411\nEOF", "a wrapper with a flag and its value"),
    ("timeout 30 bash <<EOF\ngh pr merge 411\nEOF", "a wrapper with a positional argument"),
    ("nice bash <<EOF\ngh pr merge 411\nEOF", "a wrapper in no keyword list"),
    ("xargs bash <<EOF\ngh pr merge 411\nEOF", "xargs before the executor"),
    ("setsid sh <<EOF\ngh pr merge 411\nEOF", "setsid before the executor"),
    ("ssh -o X=y host <<EOF\ngh pr merge 411\nEOF", "ssh with an option and a host"),
    ("echo a | sudo -u x bash <<EOF\ngh pr merge 411\nEOF", "after a pipe"),
    # The SAME wrapper forms against a QUOTED operand rather than a heredoc.
    # Round 5 reported both halves and only the heredoc half was fixed: the
    # narrow pass could not see past `sudo -u x` to the executor, and the
    # permissive pass had already blanked the operand as prose, so ten
    # executable merges ran with the guard returning allow.
    ('sudo -u x bash -c "gh pr merge 411"', "a flag-carrying wrapper before a quoted operand"),
    ('sudo -E bash -c "gh pr merge 411"', "a bare flag before a quoted operand"),
    ('timeout 5 bash -c "gh pr merge 411"', "a wrapper with a positional before a quoted operand"),
    ('nice bash -c "gh pr merge 411"', "an unlisted wrapper before a quoted operand"),
    ('setsid eval "gh pr merge 411"', "an unlisted wrapper before eval"),
    ('xargs -0 bash -c "gh pr merge 411"', "xargs with a flag before a quoted operand"),
    ('command -p sudo bash -c "gh pr merge 411"', "a chain of wrappers before a quoted operand"),
    ('sudo -u x eval "gh pr merge 411"', "a flag-carrying wrapper before eval"),
    ('sudo -u x ssh host "gh pr merge 411"', "a wrapper, ssh and a hostname"),
    ('timeout 5 bash -c "glab mr merge 411"', "the same shape for glab"),
    ("timeout 5 bash -c 'gh pr merge 411'", "a SINGLE-quoted live operand"),
    ("sudo -u x sh -c 'glab mr merge 411'", "a single-quoted glab operand"),
    ('cd /r && timeout 5 bash -c "gh pr merge 411"', "a live operand in a later segment"),
    ('echo hi; nice bash -c "gh pr merge 411"', "a live operand after an inert one"),
    # A redirection may appear ANYWHERE in a simple command, so the executor
    # can follow the heredoc token. The masking anchor scanned forward from the
    # executor to the `<<`, which made every one of these read as data.
    ("<<EOF bash\ngh pr merge 411\nEOF", "the heredoc token before its executor"),
    ("<<EOF sh\ngh pr merge 411\nEOF", "the same for sh"),
    ("<<'EOF' sh\ngh pr merge 411\nEOF", "a quoted delimiter before its executor"),
    ("<<-EOF bash\ngh pr merge 411\nEOF", "a tab-stripping heredoc before its executor"),
    ("<<EOF ssh host\ngh pr merge 411\nEOF", "a hostname after the heredoc token"),
    ("<<EOF sudo -u x bash\ngh pr merge 411\nEOF", "a wrapper after the heredoc token"),
    ("cd /r && <<EOF bash\ngh pr merge 411\nEOF", "the reordered form in a later segment"),
    ("bash <<EOF 2>/dev/null\ngh pr merge 411\nEOF", "a redirection after the heredoc token"),
    # mask_payloads blanks the word after -m/-b/-d/-t/-s without checking the
    # flag belongs to a gh/glab invocation, so an unrelated program's flag
    # erased the EXECUTOR before the liveness check could see it. The executor
    # scan reads the pre-mask_payloads text now.
    ('nsenter -t 1 -m bash -c "gh pr merge 411"', "a payload flag erasing the executor"),
    ('foo -m bash -c "gh pr merge 411"', "-m immediately before the executor"),
    ('foo -b sh -c "gh pr merge 411"', "-b before sh"),
    ('foo -t eval "gh pr merge 411"', "-t before eval"),
    ('foo -d ssh host "gh pr merge 411"', "-d before ssh"),
    ('foo -s bash -c "glab mr merge 12"', "-s before the executor, glab payload"),
    # --- ai-config#1352: the standing per-repository grant must not widen ---
    # Every one of these is a merge the grant does NOT cover. They are the
    # whole content of the grant being target-scoped: if any of them allows,
    # the grant has stopped meaning "PRs targeting ai-config".
    ("gh pr merge 1352 --squash",
     "a bare merge names no repo, so no target is determined"),
    ("gh pr merge 1352 -R Morrison-Lab/gha --squash",
     "an explicit target outside the grant list"),
    ("gh api -X PUT repos/Morrison-Lab/gha/pulls/1/merge",
     "a REST PR merge against a repo outside the grant list"),
    ("gh api -X POST repos/Morrison-Lab/ai-config/merges -f base=main -f head=x",
     "a repository BRANCH merge is not a PR merge, granted repo or not"),
    ("gh pr merge 1352 -R Morrison-Lab/ai-config -R Morrison-Lab/gha",
     "two different targets in one segment is not a determination"),
    ("gh api -X PUT repos/Morrison-Lab/gha/pulls/1/merge -R morrison-lab/ai-config",
     "a granted -R must not authorize a merge whose path names another repo"),
    ('gh pr merge 1352 -R Morrison-Lab/gha --body "morrison-lab/ai-config"',
     "a granted repo named inside a masked payload supplies no target"),
    ("gh pr merge 1352 -R Morrison-Lab/gha # morrison-lab/ai-config",
     "a granted repo named inside a trailing comment supplies no target"),
    # The two above are caught by the AMBIGUITY clause -- each names a second,
    # ungranted repo -- so neither tests the payload masking at all. Nor does a
    # bare repo name in a payload, which supplies no target either way: only an
    # `-R`/`--repo` flag or a `repos/<owner>/<name>/` path is ever read as one.
    # These are the shapes where the masking is load-bearing -- a FORGED flag
    # or REST path inside a payload, with no real target elsewhere to make the
    # segment ambiguous.
    ('gh pr merge 1352 --body "run it with --repo morrison-lab/ai-config"',
     "a --repo flag forged inside a quoted payload"),
    ("gh pr merge 1352 --body 'see repos/morrison-lab/ai-config/pulls/1/merge'",
     "a REST repo path forged inside a single-quoted payload"),
    ("gh pr merge 1352 # --repo morrison-lab/ai-config",
     "a --repo flag forged inside a trailing shell comment"),
    # The flag anchor. `-R` is read only at a token boundary, so a longer word
    # merely ENDING in it supplies no target -- without the anchor this segment
    # names a granted repo and merges.
    ("gh pr merge 1352 --unrelated-R morrison-lab/ai-config",
     "a word ending in -R is not the -R flag"),
    ("glab mr merge 12 -R morrison-lab/ai-config",
     "the glab forms are GitLab and carry no grant"),
    ("gh api graphql -f query='mutation { mergePullRequest(input: {...}) }' -R morrison-lab/ai-config",
     "a GraphQL mutation names its target by node id, so -R proves nothing"),
    ("gh pr merge 1352 -R Morrison-Lab/ai-config-fork",
     "a repo whose name merely starts with the granted one"),
    ("gh pr merge 1352 -R Other-Owner/ai-config",
     "the same repo name under a different owner"),
    # --- ai-config#1353 review round 1: the merge-TYPE ambiguity bypass -----
    # `_merge_patterns` tries the `pulls/N/merge` forms before the
    # `repos/<o>/<n>/merges` ones, and both scan the segment unanchored. So a
    # real BRANCH merge carrying a forged `pulls/N/merge` substring anywhere
    # in the line is labelled `gh api PR merge` -- and because both the real
    # and the forged path name the SAME granted repo, the target test sees one
    # target and grants a direct push to the default branch. `-H`/`--header`
    # is the vehicle: it is a documented `gh api` flag and is NOT in
    # mask_payloads's list, so its value survives to the pattern scan.
    ('gh api -X POST repos/Morrison-Lab/ai-config/merges -f base=main -f head=x'
     ' -H "X-Note: repos/Morrison-Lab/ai-config/pulls/1/merge"',
     "a branch merge mislabelled a PR merge by a forged path in an -H header"),
    ("gh api -X POST repos/Morrison-Lab/ai-config/merges -f base=main -f head=x"
     " --header 'X-Note: repos/Morrison-Lab/ai-config/pulls/1/merge'",
     "the same bypass via the --header spelling and single quotes"),
    ("gh api -X POST repos/Morrison-Lab/ai-config/merges -f base=main -f head=x"
     " --jq 'repos/Morrison-Lab/ai-config/pulls/1/merge'",
     "the same bypass via another unmasked flag's value (--jq)"),
    # The mirror: a granted PR merge that ALSO reads as an excluded type is
    # ambiguous too, and denies. Over-blocking is the safe direction here.
    ("gh api -X PUT repos/Morrison-Lab/ai-config/pulls/1/merge"
     " -H 'X-Note: repos/Morrison-Lab/ai-config/merges'",
     "a PR merge that also matches the branch-merge pattern is ambiguous"),
    ("gh api graphql -X POST repos/Morrison-Lab/ai-config/pulls/1/merge"
     " -f query='mutation { mergePullRequest(input: {...}) }'",
     "a PR merge that also matches the GraphQL pattern is ambiguous"),
    # ai-config#1308: `<(...)` runs its body and hands the caller a /dev/fd path
    # whose contents are that body's OUTPUT. When the caller runs what it is
    # given, the output is a script.
    #
    # In MOST of these the merge text never reaches a command position at all,
    # which is why neither a wider command-position anchor nor the live-operand
    # rule reached them. Two are different and are marked: the merge sits at a
    # command position inside the body, so they already blocked before this
    # scanner existed. They are kept as regression guards for the masking, not
    # as evidence of what it fixed.
    ('bash <(echo "gh pr merge 411")', "a process substitution fed to bash"),
    ("sh <(printf %s 'gh pr merge 411')", "printf building the script body"),
    ('zsh <(echo "gh pr merge 411")', "a non-bash shell reading the substitution"),
    ('source <(echo "gh pr merge 411")', "source runs the contents it is handed"),
    ('. <(echo "gh pr merge 411")', "the dot form of source"),
    ('bash < <(echo "gh pr merge 411")', "a redirection from a process substitution"),
    ('timeout 30 bash <(echo "gh pr merge 411")', "a wrapper with an argument before the executor"),
    ('sudo -u x bash <(echo "gh pr merge 411")', "a wrapper carrying its own flag"),
    ('FOO=1 bash <(echo "gh pr merge 411")', "an env assignment before the executor"),
    ('bash <(echo a; echo "gh pr merge 411")', "a separator inside the body does not reset the command position"),
    ('bash <(cat <(echo "gh pr merge 411"))', "a nested substitution inside an executed body"),
    ("bash <(gh pr merge 411)", "REGRESSION GUARD (blocked before this scanner): the merge at a command position inside the body"),
    ('echo x > >(bash -c "gh pr merge 411")', "REGRESSION GUARD (blocked before this scanner): an output process substitution running an executor"),
    # Round 2 of ai-config#1308's adversarial review. Each of the four below
    # really executed the merge under bash against a `gh` stub, and each was
    # ALLOWED by round 1's own fix.
    #
    # A redirection may be written BEFORE the command name, so the test is
    # co-occurrence rather than order. This file already recorded that lesson
    # for heredocs and the first draft of the substitution scanner reproduced
    # it anyway -- a backwards-only scan never saw the trailing `bash`.
    ('< <(echo "gh pr merge 411") bash', "an executor written after the substitution"),
    ('0< <(echo "gh pr merge 411") bash', "the same with an explicit fd"),
    # `_paren_matches` is quote-STATEFUL, unlike every other scanner here, so
    # one apostrophe in a comment used to set `in_single` for the rest of the
    # string and silently suppress every later `<(`.
    ("echo hi # don't\nbash <(echo \"gh pr merge 411\")", "an apostrophe in a comment does not desync the paren scan"),
    ('echo hi # ok\nbash <(echo "gh pr merge 411")', "the same line with no apostrophe"),
    # `source`/`.` execute their input, so a heredoc fed to one is a script.
    # Round 1 taught that to the substitution scanner and not to the heredoc
    # masker, which is the enumerate-one-consumer-and-stop failure.
    ("source /dev/stdin <<'EOF'\ngh pr merge 411\nEOF", "a heredoc fed to source"),
    (". /dev/stdin <<EOF\ngh pr merge 411\nEOF", "a heredoc fed to the dot form"),
    # A bare `.` pathspec DOES read as the source builtin, because
    # PERMISSIVE_LEAD makes any whitespace a command position. Recorded as the
    # accepted over-block it is, rather than asserted away in an ALLOW case
    # whose stated reason the code contradicts.
    ('rsync -a . <(echo "gh pr merge 411")', "ACCEPTED OVER-BLOCK: a bare dot pathspec reads as the source builtin"),
    # Round 3 of ai-config#1308's review. The first two are fail-opens that
    # really executed a merge under bash; the last three cover clauses that
    # reverted to ZERO failing cases, which is this file's own definition of
    # an untested clause.
    #
    # A `case` pattern's `)` opened nothing, so pairing it with the nearest
    # open paren truncated the recorded body and left the merge outside every
    # live span. One character defeated the whole scanner.
    ('bash <(case x in x) echo "gh pr merge 411";; esac)', "a case pattern's `)` is not a paren closer"),
    ('< <(case x in x) echo "gh pr merge 411";; esac) bash', "the same with the executor written after"),
    # Round 6 of ai-config#1308's review, and the sharpest finding the guard
    # has had: round 6 was a REGRESSION against rounds 4 and 5. Exempting
    # `case` from `_APPROXIMATED` on the ground that "this scanner does model
    # it" was an assertion, not a proof, and the model failed in two shapes
    # that both execute real merges under bash. Each string below is valid
    # under `bash -n` and prints a merge against a `gh` stub.
    #
    # 1. `separated` was never cleared when a new `case` was pushed, so any
    #    `case` that was not the body's FIRST command failed to arm pattern
    #    mode, and the arm's `)` truncated the body.
    ('bash <(true; case b in b) echo "gh pr merge 411";; esac)',
     "a case after a separator inside a substitution body"),
    ('bash <(echo hi && case b in b) echo "gh pr merge 411";; esac)',
     "the same after `&&` rather than `;`"),
    ('source <(x=1; case b in b) echo "gh pr merge 411";; esac)',
     "the same under source with an assignment first"),
    ('< <(true; case b in b) echo "gh pr merge 411";; esac) bash',
     "the same with the executor written after"),
    # 2. The `esac` pop had no command-position or depth test, so an ordinary
    #    ARGUMENT word `esac` disarmed a live `case` mid-construct.
    ('bash <(case b in a) echo esac;; b) echo "gh pr merge 411";; esac)',
     "an argument word `esac` does not disarm a live case"),
    ('bash <(case b in a) grep esac f;; b) echo "gh pr merge 411";; esac)',
     "the same with grep rather than echo"),
    # Round 7. A newline between the case WORD and its `in` is legal bash:
    #
    #     case b
    #     in b) echo hi;; esac
    #
    # Counting it as a command separator left the `case` unarmed and truncated
    # the body at the first arm's `)` -- the THIRD executing fail-open in this
    # model. A grammar enumeration of 103,680 valid `case` shapes found 28,350
    # executing strings, every one carrying a newline in this window and none
    # carrying a plain space.
    ('bash <(case b\nin b) echo "gh pr merge 411";; esac)',
     "a newline between the case word and its `in`"),
    ('source <(case b \nin b) echo "gh pr merge 411";; esac)',
     "the same under source, with a space before the newline"),
    ('bash <(case b \nin b) echo "gh pr merge 411";;\nesac)',
     "the same with a newline before `esac` as well"),
    # The DEPTH half of the `esac` guard. An earlier version of this comment
    # claimed `esac` is valid only as a case TERMINATOR, so that no executable
    # input could distinguish the depth test. That was false and was asserted
    # rather than measured: `esac` is also valid as a PATTERN, and a leading
    # `(` on a pattern (POSIX-optional, bash-accepted) puts it at a command
    # position one stack level deeper than its own `case`:
    #
    #     $ bash -c 'case z in (esac) echo M;; z) echo RAN;; esac'
    #     RAN
    #
    # These three are valid bash and each reverts to allow with
    # `case_depths[-1] == len(stack)` dropped (round 7 finding 2).
    ('bash <(case b in (esac) echo hi;; b) echo "gh pr merge 411";; esac)',
     "a leading-paren `esac` PATTERN does not pop its own case"),
    ('source <(case b in (esac|b) echo hi;; b) echo "gh pr merge 411";; esac)',
     "the same as the first alternative of a pattern list"),
    ('bash <(case b in (b|esac) echo hi;; b) echo "gh pr merge 411";; esac)',
     "the same as the last alternative of a pattern list"),
    # The SIBLING guard, on `pending_case`, is the one for which the
    # syntax-error claim actually holds -- measured over the same shapes, not
    # assumed. A `case` still awaiting its `in` cannot have a command-position
    # `esac` at another depth in any string bash accepts. Kept as fail-closed
    # defense against scanner desync, and pinned so that dropping
    # `pending_case[-1] == len(stack)` stops being a silent no-op.
    ('bash <(case b (esac) in b) echo "gh pr merge 411";; esac)',
     "SYNTAX ERROR, span guard: a deeper `esac` does not pop a PENDING case"),
    # THE TRAILING-EXECUTOR FORM, one case per `_APPROXIMATED` member.
    #
    # This intersection had ZERO coverage, which is why 331/331 was green over
    # five executing fail-opens. The suite's six trailing-executor cases all
    # used bodies the whitelist already trusts, so they exercised exactly the
    # complement of where the bug lived.
    #
    # `bash <(...)` puts the executor BEFORE the region; `< <(...) bash` puts
    # it AFTER, where blanking an extended body erased the `bash` itself and
    # the span list came back EMPTY. Each of these is `bash -n` clean and ran
    # a real merge against a `gh` stub, on every revision from the whitelist
    # commit onward (ai-config#3649).
    ('< <(v=q; x=${v}; echo "gh pr merge 411") bash',
     "trailing executor, `${` in the body"),
    ('< <(x=$(printf q); echo "gh pr merge 411") bash',
     "trailing executor, `$(` in the body"),
    ('< <(x=`printf q`; echo "gh pr merge 411") bash',
     "trailing executor, a backtick in the body"),
    ('< <(cat <<EOF >/dev/null\nq\nEOF\necho "gh pr merge 411") bash',
     "trailing executor, a heredoc in the body"),
    ("< <(echo $'gh pr merge 411 --squash') bash",
     "trailing executor, `$'` in the body"),
    ('< <(echo hi # q\necho "gh pr merge 411") bash',
     "trailing executor, a comment in the body"),
    # The fourth `case`-model fail-open. Its body carries NO `_APPROXIMATED`
    # token, so the per-member cases above would not have caught it. Both
    # decoys are load-bearing: remove either and it blocks.
    ('< <(: case; case x in x) : in; echo "gh pr merge 411";; esac) bash',
     "a stale pending `case` is not popped by a later argument word `in`"),
    # The COST of `_APPROXIMATED`, asserted rather than left undocumented.
    # A body containing any listed token runs to end of TEXT (not end of line),
    # so a later merge-shaped mention anywhere in the command goes live. Round
    # 6 finding 9 found seven plausible commands newly blocked; two are pinned
    # here so that widening this cost stops being invisible.
    ('bash <(echo "${SCRIPT}"); echo "never gh pr merge here"',
     "ACCEPTED OVER-BLOCK: a `${` in the body extends it over a later mention"),
    ('bash <(echo "${X}")\nls -l\necho "policy: never gh pr merge"',
     "ACCEPTED OVER-BLOCK: the extended body reaches the whole text, not the line"),
    # One level past MAX_PROC_SUBST_DEPTH: the region at the cap was skipped
    # without being marked covered, so its child re-recorded a span INSIDE an
    # already-recorded one and the bisect then read the quote as dead.
    ('cat <(cat <(cat <(cat <(cat <(cat <(bash <(cat <(cat <(echo hi)) ; echo "gh pr merge 411")))))))',
     "a nest one level past the depth cap still fails closed"),
    # Covers `_depth_view`'s boundary spaces: the executor is at depth 1 and
    # the outer command is not one.
    ('cat <(bash <(echo "gh pr merge 411"))', "an executor nested inside a non-executor's substitution"),
    # Covers the `covered` array specifically: the merge is a sibling of an
    # inner substitution, inside an outer body that does run.
    ('bash <(cat <(bash <(echo hi)); echo "gh pr merge 411")', "a grandchild region does not escape its covered ancestor"),
    # Round 4. A candidate this scanner cannot balance now FAILS CLOSED rather
    # than being dropped. It was an ALLOW case, justified as "bash would reject
    # it anyway" -- true of a genuinely unbalanced command, and the condition
    # is a claim about the SCANNER, so dropping made every paren-model bug an
    # allow. Over-blocking a command bash rejects costs nothing.
    ("bash <(echo 'gh pr merge 411'", "an opener this scanner cannot balance fails closed"),
    # A word ENDS at a shell metacharacter. Matching `case` on letters alone
    # gave it no left boundary, so `use_case` pushed a spurious case depth, the
    # substitution's own `)` was skipped as a pattern terminator, and the merge
    # escaped. One appended token was the whole bypass.
    ('bash <(use_case=1; echo "gh pr merge 411")', "a word merely ENDING in case is not a case construct"),
    ('source <(test_case=1; echo "gh pr merge 411")', "the same through source"),
    ('< <(echo "gh pr merge 411"; lower-case=1) bash', "the same with the executor written after"),
    # An odd quote in an EXECUTING heredoc body reaches the paren scan
    # unmasked, because mask_heredocs deliberately leaves such a body live.
    ("bash <<EOF\ndon't\nEOF\nbash <(echo \"gh pr merge 411\")",
     "an apostrophe in an executing heredoc body does not suppress a later substitution"),
    ("ssh h <<EOF\ndon't\nEOF\nsource <(echo \"gh pr merge 411\")",
     "the same through ssh and source"),
    # Round 5. Six more `)`-misread fail-opens, each verified executing a real
    # merge under bash. Every one left the QUOTE state balanced, so the
    # quote-blind merge -- the whole fail-closed mechanism at the time -- never
    # fired. That is what moved the design from enumerating what BREAKS the
    # paren model to enumerating what it provably HANDLES.
    ('sh <(#)\necho "gh pr merge 411")', "a `)` inside a shell comment"),
    ('source <(v=$(case $k in a) echo 1;; esac); echo "gh pr merge 411")',
     "a case pattern inside $( ), whose terminator popped the substitution"),
    ('bash <(: $(case x in x) :;; esac); echo "gh pr merge 411")',
     "the same shape without an assignment"),
    ('bash <(: "$(: "a)")"; echo "gh pr merge 411")',
     "$( ) nested inside double quotes, where bash restarts quoting"),
    ('bash <(: "${x:-"a)"}"; echo "gh pr merge 411")', "${ } nested inside double quotes"),
    ('bash <(: "`: "a)"`"; echo "gh pr merge 411")', "a backtick nested inside double quotes"),
    ('bash <(bash <<EOF\n)\nEOF\necho "gh pr merge 411")',
     "a `)` inside an executing heredoc body, which mask_heredocs leaves live"),
    # TRAILING EXECUTOR x NO RECORDED CLOSER -- the crossing that had zero
    # coverage, which is why 339/339 was green over two executing bypasses
    # (ai-config#3635 pre-merge gate). Both run a real merge against a `gh`
    # stub and both are `bash -n` clean. Each is paired with its
    # leading-executor twin, which blocked throughout: the PAIR is the test,
    # since the defect was that the two forms disagreed on the same command.
    ('< <(: case\ncase x in x) : in\necho "gh pr merge 411";; esac) bash',
     "trailing executor, a case pattern eats the closer"),
    ('bash <(: case\ncase x in x) : in\necho "gh pr merge 411";; esac)',
     "leading executor, the same missing closer"),
    ('bash <<EOF\ndon\'t\nEOF\n< <(echo "gh pr merge 411") bash',
     "trailing executor, an apostrophe in an executing heredoc pops the closer"),
    ('bash <<EOF\ndon\'t\nEOF\nbash <(echo "gh pr merge 411")',
     "leading executor, the same popped closer"),
]

ALLOW = [
    # Keeping an executor's operand live must not leak into the NEXT command.
    # A command separator ends the simple command, so a quote after one is
    # prose again however many executors preceded it -- without this bound,
    # every diagnostic written after a `bash -c` in the same session blocks.
    ('bash -c "true"; echo "you can gh pr merge later"', "prose after a separator, following an executor"),
    ('bash -c "true" && git commit -m "why gh pr merge is blocked"', "a commit message after an executor"),
    ('eval "true" | grep "gh pr merge"', "a grep pattern after an executor and a pipe"),
    # A word ENDING in an executor's name is not that executor.
    ('rebash -c "gh pr merge 411"', "an executor name as a word suffix is not a command position"),
    # The keyword prefix above must not become bare whitespace by another name:
    # a keyword only counts at a command position, so a keyword-shaped word
    # sitting mid-sentence or mid-command still leaves the mention allowed.
    ('echo "you can time gh pr merge later"', "a keyword inside quoted prose is not a command position"),
    ('grep -rn "then gh pr merge" docs/', "a keyword inside a grep pattern is not a command position"),
    ("gh issue comment 1 --body 'run time gh pr merge to time it'", "a keyword inside a comment body"),
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
    # --- ai-config#1352: the standing per-repository grant ------------------
    # A PR merge whose target resolves, unambiguously and from the command
    # text itself, to a repo in STANDING_MERGE_GRANT_REPOS. No marker file and
    # no per-session enabling step: that is what "standing" means.
    ("gh pr merge 1352 -R Morrison-Lab/ai-config --squash --delete-branch",
     "the canonical form: gh pr merge with -R naming the granted repo"),
    ("gh pr merge 1352 --repo morrison-lab/ai-config",
     "--repo spelling, and lowercase (GitHub routes case-insensitively)"),
    ("gh pr merge 1352 --repo=Morrison-Lab/ai-config",
     "--repo=value spelling"),
    ("gh pr merge 1352 -R=Morrison-Lab/ai-config",
     "-R=value spelling"),
    ("gh pr merge 1352 -RMorrison-Lab/ai-config",
     "-Rvalue with no separator, which gh's flag parser accepts"),
    ('gh pr merge 1352 -R "Morrison-Lab/ai-config" --squash',
     "a quoted repo argument, unquoted by unquote_words before the lookup"),
    ("gh api -X PUT repos/Morrison-Lab/ai-config/pulls/1352/merge",
     "the REST PR-merge form against the granted repo"),
    ("gh api --method PUT /repos/Morrison-Lab/ai-config/pulls/1352/merge",
     "the REST form with a leading slash and --method"),
    ('gh pr merge 1352 -R Morrison-Lab/ai-config --subject "merge other/repo work"',
     "a second repo named only inside a masked payload does not create ambiguity"),
    ("cd /repo && gh pr merge 1352 -R Morrison-Lab/ai-config --squash",
     "the granted target survives a cd && segment split"),
    # The other half of ai-config#1308. `cat` consumes its input as data, so a
    # process substitution handed to one merges nothing -- and a `<(` inside
    # quotes is literal to bash, so describing the construct in a comment body
    # is prose. Refusing either is the documentation-blocking failure defect 2
    # (ai-config#1279) fixed once already.
    ('cat <(echo "gh pr merge 411")', "a process substitution fed to a non-executor"),
    ('grep -q x <(echo "gh pr merge 411")', "grep reads the substitution as data"),
    ('echo "bash <(echo \'gh pr merge 411\')"', "the construct quoted as prose"),
    ('gh pr comment 1 --body "repro: bash <(echo \'gh pr merge 411\')"', "the construct inside a comment body"),
    ('ALLOW_MERGE=1 bash <(echo "gh pr merge 411")', "an explicit override on the substitution form"),
    ("bash <(echo hello)", "a process substitution with no merge in it"),
    # The executor is in the PREVIOUS segment, which a `bisect_left` on
    # separator ends reached into by returning the index OF the separator
    # ending at the `<(` rather than past it.
    ('bash -c y;<(echo "gh pr merge 411")', "an executor before the separator does not introduce this substitution"),
    ('cat f;<(echo "gh pr merge 411")', "the same with no executor anywhere"),
    # The `case` tracking must not turn a non-executor into one. Load-bearing
    # in the ALLOW direction: `cat` reads its input, and no paren-model change
    # may make it execute.
    ('cat <(case x in x) echo "gh pr merge 411";; esac)', "a case pattern inside a substitution cat merely reads"),
    # Restored. This was deleted in round 3 as vacuous-by-verdict, which was
    # the wrong test to apply: it is the only guard in the suite against the
    # PROSE direction of the `case` machinery, and EXEC_WRAP's own comment in
    # the guard makes the argument for keeping a measured-dead path -- removing
    # one on suite evidence alone fails OPEN if the suite is what is
    # incomplete. Deleting it applied the opposite rule to the same evidence in
    # the same commit (round 4 finding 8).
    ('echo "case x in x) gh pr merge 411;; esac"', "a whole case construct quoted as prose"),
    # Round 5. `case` now requires its `in` before a `)` is read as a pattern
    # terminator. Without that, a bare word `case` used as an ARGUMENT armed
    # pattern mode, the substitution's own closer was skipped, the fail-closed
    # default ran the body to end-of-text, and every later quoted merge mention
    # on the line became live -- the documentation-blocking failure this file
    # cites as its own bar (round 4 finding 7).
    ('bash <(grep -c case f) ; echo "you cannot gh pr merge 411 here"', "a bare word case is an argument, not a construct"),
    ('source <(grep -v case ~/.bashrc) ; echo "gh pr merge 411"', "the same through source"),
    # Round 5. `case` armed pattern mode from any later unquoted `in`, which
    # need not belong to it -- so a loop variable named `case`, or two
    # unrelated greps, ran the body to end of text and blocked a prose mention.
    ('bash <(for case in a b; do :; done); echo "never gh pr merge 411"',
     "a loop variable named case is not a case construct"),
    ('bash <(grep -c case f; grep -c in f); echo "never gh pr merge 411"',
     "an `in` in a later simple command does not belong to an earlier case"),
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
checks = 0


def check(ok):
    """Record one assertion outcome. `ok` is True when the verdict was correct."""
    global wrong, checks
    checks += 1
    wrong += not ok


print("should BLOCK:")
for cmd, desc in BLOCK:
    v = verdict(cmd)
    check(v == "BLOCK")
    print(f"  {v:<6} {desc}")

print("\nshould ALLOW:")
for cmd, desc in ALLOW:
    v = verdict(cmd)
    check(v == "allow")
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
    check(v_a == "allow")
    print(f"  {v_a:<6} active MWC grant for sanitized session A")

    # Session B (sanitized) does NOT have MWC enabled -> blocked (cross-session isolation)
    env_b = dict(os.environ, AI_SESSION_ID=session_b)
    v_b = verdict("gh pr merge 411 --squash", env=env_b)
    check(v_b == "BLOCK")
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
    check(v_pay == "allow")
    print(f"  {v_pay:<6} MWC grant honoured from the payload session_id (no env var)")

    v_pay_alt = verdict("gh pr merge 411 --squash", env=env_bare,
                        extra={"conversation_id": session_a})
    check(v_pay_alt == "allow")
    print(f"  {v_pay_alt:<6} MWC grant honoured from payload conversation_id")

    # Same, via the transcript filename stem, for a harness that omits the
    # field. Uses session C, whose id is filename-shaped like a real harness
    # UUID -- session A's id deliberately contains `/` and `:` to exercise
    # sanitize(), and no filename can carry those back.
    v_tr = verdict("gh pr merge 411 --squash", env=env_bare,
                   extra={"transcript_path": f"/tmp/projects/x/{session_c}.jsonl"})
    check(v_tr == "allow")
    print(f"  {v_tr:<6} MWC grant honoured from the transcript_path stem")

    # Cross-session isolation must survive the new resolution path: session B
    # holds no grant, so a payload naming B is still blocked.
    v_pay_b = verdict("gh pr merge 411 --squash", env=env_bare,
                      extra={"session_id": session_b})
    check(v_pay_b == "BLOCK")
    print(f"  {v_pay_b:<6} payload session_id for ungranted session B still blocks")

    # No identity at all -> no grant can be resolved -> block (fails closed).
    v_none = verdict("gh pr merge 411 --squash", env=env_bare)
    check(v_none == "BLOCK")
    print(f"  {v_none:<6} no session identity anywhere still blocks")

    # Disable MWC for Session A -> must block immediately
    ai_session("disable-mwc", "--id", session_a)
    v_a_revoked = verdict("gh pr merge 411 --squash", env=env_a)
    check(v_a_revoked == "BLOCK")
    print(f"  {v_a_revoked:<6} revoked MWC grant blocks for session A")
finally:
    ai_session("release", "--id", session_a)
    ai_session("release", "--id", session_b)
    ai_session("release", "--id", session_c)

# Both scanners below were quadratic once, and both fixes are worth a
# regression test. The command-position anchor makes every `;`, `&`, backtick
# and `$(` a place the matcher restarts; with an UNBOUNDED expansion prefix
# each of those N restarts rescanned the rest of a long substitution run before
# failing -- 610ms on 800 chained backtick pairs, against 2.8ms for the
# pre-anchor matcher, on a hook that runs before EVERY Bash call. Deciding
# whether a quoted span is a live operand likewise needs the start of its
# simple command, and rescanning for that from position zero per quote is
# quadratic; the separator offsets are computed once per pass instead, without
# which the same input takes ~10x as long.
#
# Two things this deliberately does NOT do, both of which it used to.
#
# It does not assert a WALL-CLOCK bound. `perf_counter` counts the time a scan
# spends descheduled, so its reading is a fact about the machine's load rather
# than about the scan. The same 2000-span input measured 342ms on one machine,
# 1122ms on a GitHub runner and 2115ms on a third, all on byte-identical work
# with an unchanged scanner -- a 6x spread. Any bound tight enough to catch a
# regression sits inside that spread, so it goes red on PRs that never touched
# this hook, which is how a gating check stops being read (#1314, #1396,
# #1785, #1796). `process_time` counts CPU actually consumed and does not
# advance while the process waits for a core, which is the property that makes
# the reading reproducible. Measured under 6 busy-loops on 4 cores, on
# unchanged code: the wall-clock ratio for these two scanners ranged
# 2.18-4.58x, while the CPU-time ratio over the same runs held at 3.96-4.31x.
# At the sizes set below the loaded and unloaded readings are
# indistinguishable, 4.0-4.3x either way.
#
# It does not assert a MILLISECOND figure at all. What these fixes protect is
# the SHAPE of the growth, so that is what is asserted: each scanner is timed
# at two input sizes in the same process, and the machine's own speed divides
# out of the ratio. Quadrupling the input grows a linear scan ~4x and a
# quadratic one ~16x, and the bound is the geometric mean of those, sitting
# equally far from both in log terms however slow the machine is.
import importlib.util  # noqa: E402
import time  # noqa: E402

_spec = importlib.util.spec_from_file_location("_guard", HOOK)
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)


def halfway_bound(step):
    """Growth halfway, in log terms, between linear and quadratic at `step`.

    A linear scan grows `step`x and a quadratic one `step ** 2`x, so their
    geometric mean is `step ** 1.5`. Deriving it rather than writing a number
    keeps the bound meaningful at whatever size step it is read against: a
    figure fixed for one step separates the two shapes at no other.
    """
    return step ** 1.5


def report_separation(label, bound, step):
    """Assert a growth bound sits strictly between the two shapes it separates.

    A timing control can only exercise the bound it is itself read against, so
    a second bound in this file has nothing checking it. This costs no clock
    at all and fails on any hand-edited flat figure that has stopped
    separating linear from quadratic -- which is exactly how widening a size
    step without recomputing the bound goes wrong.
    """
    ok = step < bound < step ** 2
    print(f"  {'allow' if ok else 'WRONG':<6} "
          f"{label}: bound {bound:g}x sits {'' if ok else 'NOT '}between "
          f"linear ~{step}x and quadratic ~{step ** 2}x")
    return ok


SCAN_SMALL = 300            # repetitions in the baseline input
SCAN_STEP = 4               # the large input is this multiple of the small one
SCAN_GROWTH_BOUND = halfway_bound(SCAN_STEP)   # 8.0 = sqrt(4 * 16)
SCAN_BASELINE_REPS = 3
SCAN_TARGET_REPS = 2

# The ratio is only as trustworthy as its denominator. A baseline this far
# below the ~60ms these inputs actually cost means the platform's CPU clock is
# too coarse to measure them (Windows resolves `process_time` to about 15ms),
# and dividing by it would report a growth figure that is really clock noise.
# Fail on that rather than blaming the scanner for it.
SCAN_FLOOR_SECONDS = 0.001

# A liveness ceiling, deliberately absurd rather than a runtime budget: the
# ratio is blind to a constant-factor blowup, and this hook runs before EVERY
# Bash call, so a scan burning half a minute of CPU is broken whatever its
# shape. Every timed case is read against it, `report_growth` and
# `report_control` alike. The slowest of them is the negative control's
# quadratic scan over 96000 characters, 1.45-1.54s of CPU over three runs on
# a 4-core Linux container at load average ~3.5, against 315ms for the
# slowest scanner case there, so the ceiling leaves about 20x of headroom.
# Load eats into that, so read a breach as a claim about the machine before
# one about the scanner.
SCAN_ABSURD_SECONDS = 30.0


def fastest_scan(scan, text, reps):
    """Least CPU time any of `reps` `scan(text)` calls consumed, in seconds.

    A garbage collection or a page fault can only ever ADD work to a run, so
    the minimum of a few runs is the sample least contaminated by one. Bails
    out early once a call has blown the liveness ceiling, so a genuinely
    broken scanner fails in one pass rather than in `reps` of them.
    """
    best = float("inf")
    for _ in range(reps):
        started = time.process_time()
        scan(text)
        best = min(best, time.process_time() - started)
        if best > SCAN_ABSURD_SECONDS:
            break
    return best


def growth_of(
    build_input, small=SCAN_SMALL, scan=_guard.offending, step=SCAN_STEP
):
    """Growth factor, large-input seconds, and the baseline it divided by."""
    base = fastest_scan(scan, build_input(small), SCAN_BASELINE_REPS)
    large = fastest_scan(scan, build_input(small * step), SCAN_TARGET_REPS)
    if base < SCAN_FLOOR_SECONDS:
        return float("nan"), large, base
    return large / base, large, base


def report_growth(label, build_input):
    """Assert the scan grows linearly, and report the measurement either way."""
    growth, large, base = growth_of(build_input)
    if base < SCAN_FLOOR_SECONDS:
        print(f"  WRONG  {label}: baseline of {base * 1000:.1f}ms is below the "
              f"{SCAN_FLOOR_SECONDS * 1000:.0f}ms floor, so this platform's CPU "
              f"clock cannot measure the growth")
        return False
    ok = growth <= SCAN_GROWTH_BOUND and large <= SCAN_ABSURD_SECONDS
    print(f"  {'allow' if ok else 'SLOW ':<6} "
          f"{label} {SCAN_SMALL} -> {SCAN_SMALL * SCAN_STEP} grew {growth:.1f}x "
          f"(linear ~{SCAN_STEP}x, bound {SCAN_GROWTH_BOUND:g}x, "
          f"{large * 1000:.0f}ms CPU)")
    return ok


def chained_substitutions(n):
    return "`x` " * n + "echo hi"


def quoted_spans(n):
    return " ".join(f'echo "field {i}"' for i in range(n))


check(report_separation("scanner bound", SCAN_GROWTH_BOUND, SCAN_STEP))
check(report_growth("chained substitutions", chained_substitutions))
check(report_growth("quoted spans", quoted_spans))


# Negative control. A ratio test that never fires is indistinguishable from a
# scanner that is fine, so prove the bound still catches what it exists for:
# a deliberately quadratic scan, measured through the same helper against the
# halfway bound its own size step earns, has to land ABOVE it, and a linear
# scan measured the same way has to land BELOW it. Without this pair the two
# assertions above would keep passing if `fastest_scan` were ever broken.
#
# The pair is read against SCAN_CONTROL_BOUND, so it exercises that bound and
# no other -- in particular not SCAN_GROWTH_BOUND, which is the bound those
# two assertions are themselves read against. `report_separation` covers both,
# and covers them without a clock.
#
# The control needs a much longer input than the scanners above, for two
# reasons that push the same way. Python's own per-iteration overhead is
# linear, and below a few thousand characters it is large enough to mask the
# quadratic term and understate the growth. And the baseline has to clear
# SCAN_FLOOR_SECONDS with room to spare, or the control disqualifies itself.
# At this size the baseline costs ~6ms, six times the floor.
SCAN_CONTROL_SMALL = 6000

# The control takes a WIDER size step than the scanners above, and the reason
# is load rather than taste. The ratio is large / small, so anything that
# inflates the SMALL reading more than the large one compresses it, and a
# quadratic scan then reads as sub-quadratic: the control reports that it
# cannot discriminate, which is a false negative about the instrument rather
# than a finding about any scanner. Measured at a step of 4: 14.5-15.3x over
# five runs on an idle container, against 7.3x on a loaded GitHub runner
# (#3098) -- a 2.1x compression, against a margin over the bound of only 1.9x.
#
# What a wider step buys is margin, because the quadratic term outruns the
# halfway bound: at step s the reading is s ** 2 and the bound is s ** 1.5, so
# the margin is sqrt(s). Measured here, 3.6-3.7x at step 16 against 1.9x at
# step 4, which clears the 2.1x compression the runner produced.
#
# The bound has to be recomputed at the control's own step for that to hold,
# and this is the trap in widening the gap alone: 8.0 is the halfway line for
# a 4x step and is EXACTLY the 8x a linear scan grows at an 8x step, so
# widening that far leaves it no margin against the shape it exists to reject.
# Measured at step 8, a linear scan grew 7.55-8.09x across twelve runs on one
# container and 7.83-8.11x on another, crossing 8.0 in 1 run of 12 and in 3 of
# 12. At the step of 16 this control actually runs at, a linear scan grew
# 15.7-16.0x and cleared 8.0 in all six runs, so a flat 8.0 read against this
# step would pass for either shape. The positive control below
# (`linear_scan`, checked through `report_control(..., expect_above=False)`)
# asserts the separation rather than arguing it.
#
# Subtracting a measured fixed cost was the other repair on offer. It was not
# chosen, and not because measurement ruled it out: what can be measured off
# the runner is the INTERPRETER's fixed cost -- 0.62ms of the 6.2ms baseline for
# the loop plus one zero-length `count` call, which is the shape #3098
# proposed subtracting -- while the LOAD-induced fixed cost the repair targets
# cannot be measured from here at all. So the distortion's shape stays a
# hypothesis, and the wider step is chosen for surviving either shape rather
# than for ruling one out.
SCAN_CONTROL_STEP = 16
SCAN_CONTROL_BOUND = halfway_bound(SCAN_CONTROL_STEP)   # 64.0 = sqrt(16 * 256)

# Passes chosen so the linear control's baseline costs ~8ms, well clear of
# SCAN_FLOOR_SECONDS: one pass over 6000 characters is far too fast to time.
#
# The positive control is exposed to the OPPOSITE distortion from the negative
# one, and its margin is worth stating because this file's timing assertions
# have now flaked six times. Load INFLATING a ratio is the direction
# shared/workflow/algorithmatize-checks.md already records, at 8.45x for an
# unchanged linear scanner against a bound of 8.0 -- a ~2.0x inflation, though
# of a wall-clock reading where this control uses `process_time`. Measured
# here the positive control reads 15.2-15.4x against the 64x bound, so it
# tolerates ~4.2x inflation, about twice the worst ever recorded.
SCAN_LINEAR_CONTROL_PASSES = 4000


def quadratic_scan(text):
    """Deliberately O(n^2): every suffix from position i is rescanned."""
    for i in range(len(text)):
        text.count("q", i)


def linear_scan(text):
    """Deliberately O(n): a fixed number of whole-text passes, no rescans."""
    for _ in range(SCAN_LINEAR_CONTROL_PASSES):
        text.count("q")


def report_control(label, scan, expect_above):
    """Assert a known-shape scan lands the right side of the control bound.

    Reports the ratio and its margin whichever way the comparison goes: a
    bound whose margin is only printed on failure fails suddenly, where one
    whose margin is printed on every run drifts visibly first (#3098).

    The liveness ceiling gates this case too. The negative control is the
    slowest scan the file runs, and `fastest_scan` bails out of a breach with
    a truncated minimum whose ratio still lands on the expected side, so an
    ungated control would print `allow` over a machine that had blown the
    ceiling -- a silent failure where the ceiling exists to be loud.
    """
    growth, large, base = growth_of(
        lambda n: "x" * n, small=SCAN_CONTROL_SMALL, scan=scan,
        step=SCAN_CONTROL_STEP)
    if base < SCAN_FLOOR_SECONDS:
        print(f"  WRONG  {label}: baseline of {base * 1000:.1f}ms is below "
              f"the {SCAN_FLOOR_SECONDS * 1000:.0f}ms floor, so this "
              f"platform's CPU clock cannot measure the growth")
        return False
    if expect_above:
        separated = growth > SCAN_CONTROL_BOUND
    else:
        separated = growth < SCAN_CONTROL_BOUND
    live = large <= SCAN_ABSURD_SECONDS
    ok = separated and live
    side = "above" if expect_above else "below"
    margin = (growth / SCAN_CONTROL_BOUND if expect_above
              else SCAN_CONTROL_BOUND / growth)
    ceiling = "" if live else f", OVER the {SCAN_ABSURD_SECONDS:g}s ceiling"
    print(f"  {'allow' if ok else 'WRONG':<6} "
          f"{label} {SCAN_CONTROL_SMALL} -> "
          f"{SCAN_CONTROL_SMALL * SCAN_CONTROL_STEP} grew {growth:.1f}x, "
          f"{'' if separated else 'NOT '}{side} the "
          f"{SCAN_CONTROL_BOUND:g}x bound "
          f"(linear ~{SCAN_CONTROL_STEP}x, "
          f"quadratic ~{SCAN_CONTROL_STEP ** 2}x, margin {margin:.1f}x, "
          f"{large * 1000:.0f}ms CPU{ceiling})")
    return ok


check(report_separation("control bound", SCAN_CONTROL_BOUND,
                        SCAN_CONTROL_STEP))
check(report_control("negative control: a quadratic scan",
                     quadratic_scan, expect_above=True))
check(report_control("positive control: a linear scan",
                     linear_scan, expect_above=False))

# The executor scan reads a DIFFERENT string from the one being masked, and the
# two are interchangeable only because both are length-preserving. A caller that
# passes a mismatched subject would silently index the wrong offsets, so the
# guard falls back to the masked text rather than trusting the argument.
_txt = 'bash -c "gh pr merge 411"'
# A mismatched subject must fall back to `text`, so the operand still reads as
# LIVE and survives unmasked. Asserting only that the length is preserved would
# pass either way -- masking is length-preserving by construction.
_short = _guard.mask_inert_quotes(_txt, "too short")
_ok = ("pr merge" in _short) and len(_short) == len(_txt)
check(_ok)
print(f"  {'allow' if _ok else 'WRONG':<6} "
      f"a mismatched-length executor subject falls back instead of indexing")

def verdict_mcp(tool_name: str, tool_input: dict, env: dict = None, extra: dict = None) -> str:
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    payload.update(extra or {})
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode} on MCP {tool_name!r}\n{p.stderr.strip()}")
    return "BLOCK" if '"permissionDecision": "deny"' in p.stdout else "allow"

MCP_BLOCK = [
    ("mcp__github__merge_pull_request", {"owner": "Other-Owner", "repo": "ai-config", "pull_number": 123}, "MCP merge_pull_request for ungranted repo"),
    ("mcp__github__merge_pull_request", {}, "MCP merge_pull_request without owner/repo"),
    ("mcp__github__enable_pr_auto_merge", {"owner": "Other-Owner", "repo": "ai-config", "pull_number": 123}, "MCP enable_pr_auto_merge for ungranted repo"),
    ("mcp__github__enable_pull_request_auto_merge", {"owner": "Other-Owner", "repo": "ai-config", "pull_number": 123}, "MCP enable_pull_request_auto_merge for ungranted repo"),
    ("mcp__github__disable_pr_auto_merge", {"owner": "Other-Owner", "repo": "ai-config", "pull_number": 123}, "MCP disable_pr_auto_merge for ungranted repo"),
    ("mcp__github__disable_pull_request_auto_merge", {"owner": "Other-Owner", "repo": "ai-config", "pull_number": 123}, "MCP disable_pull_request_auto_merge for ungranted repo"),
]

MCP_ALLOW = [
    ("mcp__github__merge_pull_request", {"owner": "Morrison-Lab", "repo": "ai-config", "pull_number": 123}, "MCP merge_pull_request for standing grant repo"),
    ("mcp__github__merge_pull_request", {"owner": "morrison-lab", "repo": "ai-config", "pull_number": 123}, "MCP merge_pull_request for standing grant repo (lowercase)"),
    ("mcp__github__merge_pull_request", {"owner": "Other-Owner", "repo": "ai-config", "pull_number": 123, "allow_merge": "1"}, "MCP merge_pull_request with allow_merge override"),
    ("mcp__github__enable_pr_auto_merge", {"owner": "Morrison-Lab", "repo": "ai-config", "pull_number": 123}, "MCP enable_pr_auto_merge for standing grant repo"),
    ("mcp__github__get_file_contents", {"owner": "Other-Owner", "repo": "ai-config", "path": "README.md"}, "non-merge MCP tool get_file_contents"),
    ("mcp__github__update_pull_request", {"owner": "Other-Owner", "repo": "ai-config", "pull_number": 123, "state": "closed"}, "non-merge MCP tool update_pull_request"),
]

print("\nMCP should BLOCK:")
for tool_name, tool_input, desc in MCP_BLOCK:
    v = verdict_mcp(tool_name, tool_input)
    check(v == "BLOCK")
    print(f"  {v:<6} {desc}")

print("\nMCP should ALLOW:")
for tool_name, tool_input, desc in MCP_ALLOW:
    v = verdict_mcp(tool_name, tool_input)
    check(v == "allow")
    print(f"  {v:<6} {desc}")

# ------------------------------------------------ scanner-level assertions
#
# These assert the SPAN rather than a verdict, because a span is what the
# clause changes and a verdict can be reached by a different route.
#
# An earlier version of this comment said the clauses were "NOT reachable
# through a verdict", and then a later one gave per-clause counts that were
# wrong for the code shipped beside them (round 5 finding 7). Both errors have
# the same cause: a mutation count measured against one revision and copied
# forward into the next.
#
# So no counts are quoted here. Re-measure them -- revert the clause, run this
# file, read the number -- rather than trusting a figure written down when the
# surrounding code was different. The span checks below are a sharper
# instrument than a verdict case for these clauses, which is the reason to have
# both, and is true independently of any count.
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("_guard", HOOK)
_guard = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_guard)

print("\nscanner-level:")


def _span_check(label, command, want):
    global checks, wrong
    checks += 1
    got = _guard.live_proc_subst_spans(command)
    ok = got == want
    if not ok:
        wrong += 1
    print(f"  {'ok' if ok else 'WRONG':<6} {label}")
    if not ok:
        print(f"         got {got}, want {want}")


# `use_case` must not be read as a `case`, so the `)` closes the `<(` and the
# body is the real one. With the letters-only word match the region vanished.
# `_FILL` must not be whitespace, asserted structurally rather than by timing.
#
# Reverting it to a space failed 0 suite cases -- including the ratio-based
# performance cases, which bound GROWTH and not this shape -- while costing a
# measured 57x on a 400-deep nest (23ms at HEAD, 1311ms reverted). The
# documented invariant had no test at all, so a future edit restoring a space
# would have gone green (ai-config#1308 review, round 8 finding 7).
#
# A timing assertion is the obvious test and the wrong one: CI timings are
# noisy, and the property that matters is not "fast" but "not whitespace",
# because EXEC_AT_CMD_POS is quadratic on whitespace runs.
_fill_ok = len(_guard._FILL) == 1 and not _guard._FILL.isspace()
checks += 1
if not _fill_ok:
    wrong += 1
    print(f"  WRONG  the blank fill character must not be whitespace, "
          f"got {_guard._FILL!r}")
else:
    print("  ok     the blank fill character is not whitespace")

_span_check("a word ending in case leaves the closer intact",
            'bash <(use_case=1; echo hi)', [(7, 26)])
# The `case` pattern's `)` is skipped, so the body runs to the real closer.
_span_check("a case pattern's `)` is not the closer",
            'bash <(case x in x) echo hi;; esac)',
            [(7, 34)])
# The depth cap was described in a commit message as "a performance bound with
# no reachable behavioural test". That was wrong: past the cap the analysis
# stops and the body is assumed executed, so a nest one level past it blocks
# WITH the cap and is allowed without it (round 4 finding 6). A `cat`-only nest
# isolates the cap, since no executor appears anywhere in it.
_DEEP = "cat " + "<(cat " * 7 + '<(echo "gh pr merge 411")' + ")" * 7
checks += 1
if not _guard.offending(_DEEP):
    wrong += 1
print(("  ok    " if _guard.offending(_DEEP) else "  WRONG ")
      + " a nest past the depth cap fails closed")

# An odd quote makes the quote-aware read unreliable by its own account, so a
# quote-blind pass is merged in. The body then runs to the end of the text
# rather than to the `)`, because the two passes do not agree on a closer.
_span_check("an unbalanced quote merges a quote-blind scan, failing closed",
            "don't\nbash <(echo hi)", [(13, 21)])

total = checks
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
