#!/usr/bin/env python3
"""Tests for no-commit-chained-to-push.py.

The negatives carry most of the weight. This hook DENIES, and it fires on two
of the commonest strings in this corpus: a repo about git workflow writes
`git commit` and `git push` inside commit messages, issue bodies, PR bodies,
heredocs, fragments, and hook docstrings constantly. A matcher that fired on
prose about the rule would refuse every session that discusses it, which is
README's "a hook that misfires is worse than a missing one" in its worst form.

Each negative names the shape it protects, so a later reader can tell a
deliberate exclusion from an accident.

Run:  python3 hooks/test-no-commit-chained-to-push.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "no-commit-chained-to-push.py")

# Bytecode caching is disabled for this suite. The mutation section below
# rewrites, imports, and restores real source files, and a cached `.pyc` for
# `scripts/lib/shellcmd.py` silently survived one such restore during
# development -- so the suite reported a failure against source that was
# already correct. `sys.dont_write_bytecode` removes the confound rather than
# leaving anyone to diagnose it a second time.
sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def fires(command):
    return hook.evaluate(command) is not None


def run_hook(command, tool_name="Bash"):
    payload = json.dumps({"tool_name": tool_name,
                          "tool_input": {"command": command}})
    proc = subprocess.run([sys.executable, HOOK], input=payload,
                          capture_output=True, text=True, timeout=10)
    return proc.stdout.strip()


# --------------------------------------------------------------- must fire

# TEST CASE #1 -- the REPORTED shape (ai-config#2992, 2026-09-02): an `add`, a
# heredoc commit message, and the push, in one call. Reconstructed, not
# verbatim: #2992's author states they verified the mechanism from the hook
# registration and did NOT reproduce the lost commit, and the issue carries no
# command text. Saying "verbatim" over a second-hand report is the overclaim
# `shared/writing/fact-check-prose.md` exists to catch.
#
# The heredoc is the load-bearing part and is the reason this case is first.
# An earlier revision of this fixture also carried an interleaved
# `echo committed;`, and that `echo`'s semicolon was the ONLY reason it fired:
# `scripts/lib/shellcmd.py`'s heredoc blanking emitted `<<` flush against the
# newline-derived `;`, shlex merged them into one `<<;` token that the
# separator test did not recognize, and the push was absorbed into the
# commit's argv. The suite was green over a guard that was silent on the
# commonest way this corpus writes a commit. Keep this case echo-free.
INCIDENT = (
    "git add -A && git commit -F - <<'EOF'\n"
    "feat(hooks): add a guard\n"
    "\n"
    "Body text mentioning git push, because commit messages do.\n"
    "EOF\n"
    "git push -u origin hook-branch"
)
check("the reported incident shape", fires(INCIDENT), True)
check("a heredoc commit and a push separated only by the terminator newline",
      fires("git commit -F - <<'EOF'\nmsg\nEOF\ngit push"), True)
check("a heredoc commit and a push joined with &&",
      fires("git commit -F - <<'EOF'\nmsg\nEOF\n&& git push"), True)
check("a heredoc commit and a push joined with ;",
      fires("git commit -F - <<'EOF'\nmsg\nEOF\n; git push"), True)

check("&& chained", fires("git commit -m x && git push"), True)
check("semicolon separated", fires("git commit -m x; git push"), True)
check("newline separated", fires("git commit -m x\ngit push"), True)

# The rest of the OPENER's line is not body. A heredoc redirection is one word
# of a command that can carry more after it, and discarding everything from
# the opener to the body's first newline discarded a real chained push --- a
# BYPASS, measured as `allow` before the fix.
check("a push chained on the heredoc opener's own line still fires",
      fires("git commit -F - <<'EOF' && git push -u origin b\nmsg\nEOF\n"),
      True)
check("same, separated by a semicolon",
      fires("git commit -F - <<'EOF'; git push\nmsg\nEOF\n"), True)
# Nothing may follow the terminator. Verified against bash directly: a body
# line `EOF  ` does not close the heredoc, the body continues past it. Reading
# it as the terminator parsed the remaining body as live commands and refused
# a harmless call.
check("a body line with trailing whitespace does not close the heredoc",
      fires("cat <<'EOF' > f.md\nEOF  \ngit commit -m x && git push\nEOF\n"),
      False)

# Heredoc delimiters are ordinary shell words, not `\w+`, and the terminator
# is anchored. Both were false-DENY sources: an unrecognized opener left the
# body as live text, and a loosely-matched terminator closed the heredoc
# early so the rest of the body was parsed as commands. A false DENY on a
# harmless call is the direction README calls worse than a missing hook.
check("a hyphenated heredoc delimiter does not leave its body live",
      fires("cat <<'END-MSG' > f.md\ngit commit -m x && git push\nEND-MSG\n"),
      False)
check("a dotted heredoc delimiter does not leave its body live",
      fires("cat <<'EOF.1' > f.md\ngit commit -m x && git push\nEOF.1\n"),
      False)
check("an indented terminator inside a `<<` body does not close it early",
      fires("cat <<'EOF' > f.md\n  EOF\ngit commit -m x && git push\nEOF\n"),
      False)
check("`<<-` accepts a tab-indented terminator",
      fires("cat <<-'EOF' > f.md\ngit commit -m x && git push\n\tEOF\n"),
      False)
check("`<<-` does not accept a SPACE-indented terminator",
      fires("cat <<-'EOF' > f.md\n  EOF\ngit commit -m x && git push\nEOF\n"),
      False)
check("an unterminated heredoc runs to the end, as the shell reads it",
      fires("cat <<'EOF' > f.md\ngit commit -m x && git push\n"), False)
# The positives that keep the widened delimiter class from swallowing real
# commands: a chain AFTER a closed heredoc must still be refused, including
# after two of them, which the single-regex form could not span.
check("a real chain after a hyphenated heredoc still fires",
      fires("cat <<'END-MSG' > f.md\ntext\nEND-MSG\n"
            "git commit -m x && git push\n"), True)
check("a real chain after two heredocs still fires",
      fires("cat <<'A' > f\ntext\nA\ncat <<'B' > g\ntext\nB\n"
            "git commit -m x && git push\n"), True)

# An override authorizes THAT COMMAND, not the rest of the call. `evaluate`
# used to `return None` on the first overridden commit or push, abandoning the
# scan, so an override anywhere disarmed the guard for every later command --
# and the pair it then let through is unprotected, which is the whole thing
# this guard exists to refuse. Both shapes measured as `allow` before the fix.
check("an override on the first commit does not cover a second, unprotected one",
      fires("ALLOW_COMMIT_AND_PUSH=1 git commit -m a && git commit -m b "
            "&& git push"), True)
check("an override on one push does not cover a later bare push",
      fires("git commit -m a && ALLOW_COMMIT_AND_PUSH=1 git push "
            "&& git push origin x"), True)
# The negatives that keep the fix from breaking the override itself. Without
# these, changing `continue` back to `return None` -- or dropping the override
# read entirely -- would go unnoticed in one direction or the other.
check("a single overridden pair is still allowed",
      fires("ALLOW_COMMIT_AND_PUSH=1 git commit -m a && git push"), False)
check("an override on both halves is still allowed",
      fires("ALLOW_COMMIT_AND_PUSH=1 git commit -m a "
            "&& ALLOW_COMMIT_AND_PUSH=1 git push"), False)
check("an overridden commit with two pushes and no second commit is allowed",
      fires("ALLOW_COMMIT_AND_PUSH=1 git commit -m a && git push "
            "&& git push origin x"), False)

# A `#` comment used to disable the guard outright. `simple_commands` rewrites
# a newline to `;` so a script's second line is its own command, and `shlex`'s
# `commenters` then discarded everything from the `#` to the end of the WHOLE
# input rather than to the end of its line -- so the push after a commented
# commit was never seen. Measured on this branch before the fix: `allow`.
check("a comment on the commit line does not swallow the push",
      fires("git commit -m x # note\ngit push"), True)
check("a comment-only line between the two does not swallow the push",
      fires("git commit -m x\n# just a note\ngit push"), True)
# The negatives that keep the comment stripping from eating real arguments.
check("a `#` inside double quotes is data, not a comment",
      fires('git commit -m "fix #123 and more"'), False)
check("a `#` inside single quotes is data, not a comment",
      fires("git commit -m 'fix #123'"), False)
check("a word-internal `#` is not a comment",
      fires("git commit -m sha#1234"), False)
check("a quoted `#` does not hide a later real push",
      fires('git commit -m "fix #123" && git push'), True)

# Adversarial review of the first fix found three shapes it left open. Each
# was reproduced as an ALLOW before the rewrite, and each is a fail-open on a
# deny guard rather than a cosmetic miss.
#
# `shlex` starts a new token immediately after an operator, so a `#` glued to
# one begins a comment with no whitespace anywhere. A whitespace-only rule
# closed `x # note` and left `x &&#note` wide open.
check("a `#` glued to `&&` does not swallow the push",
      fires("git commit -m x &&#note\ngit push"), True)
check("a `#` glued to `|` does not swallow the push",
      fires("git commit -m x |#note\ngit push"), True)
# A double-quoted `-m` message spans physical lines, which this module's own
# docstring anticipates. Resetting quote state per line read a body line
# beginning `#` as an unquoted comment and deleted the closing quote and the
# push with it.
check("a `#` opening the second line of a quoted -m message is not a comment",
      fires('git commit -m "abc\n#def" && git push'), True)
# Backslash escapes the NEXT character outside single quotes. Skipping only
# the backslash let `\"` toggle quote state, and an odd number of them before
# a `#` corrupted the balance into the same deletion.
check("an escaped quote before a `#` does not corrupt quote state",
      fires('git commit -m "fix \\" # 123" && git push'), True)

# NOT a bypass, and asserted so the rewrite cannot "fix" it into one. A review
# round called this a hole; bash disagrees. Verified by running it:
#   $ bash -c 'echo COMMIT;#note; echo PUSH'
#   COMMIT
# The `#` begins a comment at a token start and runs to end of line, so the
# push is commented out and never executes. There is no chain to refuse, and
# denying here would refuse a command that does not do the thing.
check("a `;#` comment really does comment out the rest of the line",
      fires("git commit -m x;#note; git push"), False)

# `_SECRET_NAME`'s leading character class used to consume the keyword's own
# first letter, so the BARE names could never match while prefixed ones did.
# The suite's only case was `MY_DEPLOY_SECRET=`, which has a prefix and so
# passed straight over the defect -- a vacuous case, not a passing one.
for _bare in ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY", "APIKEY",
              "AUTH", "AUTHORIZATION", "BEARER", "COOKIE", "PAT", "KEY"):
    _out = hook.evaluate(
        _bare + "=abcdEFGH12345678opaque git commit -m a && git push") or ""
    check("the denial still fires with a bare " + _bare, bool(_out), True)
    check("the denial does not echo a bare " + _bare,
          "abcdEFGH12345678opaque" in _out, False)

# The denial renders the user's own argv back at them, into a transcript a
# session may paste onto a PR, and Actions-style secret masking does not reach
# it. An env-assignment prefix is where a credential rides along.
_LEAKY = (
    ("URL userinfo",
     "GIT_CONFIG_VALUE_0=https://user:ghp_SECRETTOKENVALUE@x.com "
     "git commit -m a && git push", "ghp_SECRETTOKENVALUE"),
    ("a classic PAT",
     "GH_TOKEN=ghp_AAAAAAAAAAAAAAAAAAAA git commit -m a && git push",
     "ghp_AAAAAAAAAAAAAAAAAAAA"),
    ("a modern PAT",
     "X=github_pat_11ABCDEFG0123456789 git commit -m a && git push",
     "github_pat_11ABCDEFG0123456789"),
    ("an sk- key",
     "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwx git commit -m a && git push",
     "sk-abcdefghijklmnopqrstuvwx"),
    ("a slack token",
     "S=xoxb-1234567890-abcdefghij git commit -m a && git push",
     "xoxb-1234567890-abcdefghij"),
    ("a secret-NAMED assignment whose value looks ordinary",
     "MY_DEPLOY_SECRET=hunter2hunter2 git commit -m a && git push",
     "hunter2hunter2"),
)
for _label, _cmd, _needle in _LEAKY:
    _out = hook.evaluate(_cmd) or ""
    check("the denial still fires with " + _label, bool(_out), True)
    check("the denial does not echo " + _label, _needle in _out, False)

# The over-redaction control: a benign command must come back readable, or the
# denial stops naming the command it refused.
_benign = hook.evaluate('git commit -m "fix the thing" && git push origin main') or ""
check("a benign commit subject survives redaction",
      "fix the thing" in _benign, True)
check("benign push arguments survive redaction",
      "origin main" in _benign, True)
check("|| separated", fires("git commit -m x || git push"), True)
check("add, commit, push", fires("git add -A && git commit -m x && git push -u origin b"), True)
check("commit -F file then push",
      fires("git commit -F /tmp/msg.txt && git push --force-with-lease"), True)
check("git -C on both halves",
      fires("git -C /repo commit -m x; git -C /repo push origin main"), True)
check("env assignment prefixes",
      fires("GIT_AUTHOR_NAME=x git commit -m y; GIT_TERMINAL_PROMPT=0 git push"),
      True)
check("subshell grouping", fires("(git commit -m x; git push)"), True)
check("brace grouping", fires("{ git commit -m x; } && git push"), True)
# The guard must fire wherever its siblings would. Each spelling below is
# denied by no-push-without-self-review.py and was SILENT here until
# scripts/lib/shellcmd.py adopted that guard's own wrapper classification.
check("timeout wrapper on the push",
      fires("git commit -m x && timeout 60 git push -u origin b"), True)
check("absolute path to git",
      fires("git commit -m x && /usr/bin/git push"), True)
check("an unexpanded $GIT program token",
      fires("git commit -m x && $GIT push"), True)
check("sudo with its own options before git",
      fires("git commit -m x && sudo -u me git push"), True)
check("env wrapper on the commit",
      fires("env git commit -m x && git push"), True)
check("a retry loop body opening with do",
      fires("git commit -m x; for i in 1 2; do git push; done"), True)
check("extra whitespace", fires("git   commit  -m x ;  git   push"), True)
check("an intervening unrelated command does not mask it",
      fires("git commit -m x; python3 scripts/check-links.py; git push"), True)
check("commit, push, and a later second push",
      fires("git commit -m x; git push origin a; git push origin b"), True)

# The reported reason names BOTH halves, so the message is actionable.
# `or ""` rather than a bare `in`: a mutation that makes `evaluate` return
# None here must produce a reported FAILURE, not a TypeError that aborts the
# suite before the remaining cases run. A crash is technically a red test and
# is a poor one -- it hides every assertion after it.
reason = hook.evaluate("git commit -m wip && git push -u origin feature") or ""
check("reason names the commit", "git commit -m wip" in reason, True)
check("reason names the push", "git push -u origin feature" in reason, True)

# ----------------------------------------------------------- must NOT fire

# 1. Order. Push-then-commit denies the same invocation, but nothing was
#    created to lose: the tree is exactly as it was and the author's belief
#    about it is correct. Only commit-then-push hides a missing commit.
check("push before commit", fires("git push; git commit -m x"), False)
check("push then commit then nothing",
      fires("git push origin main && git commit -m late"), False)

# 2. Either command alone -- overwhelmingly the common case.
check("commit alone", fires("git commit -m x"), False)
check("push alone", fires("git push -u origin b"), False)
check("add and commit, no push", fires("git add -A && git commit -m x"), False)
check("commit then a status read",
      fires("git commit -m x && git status --short"), False)
check("commit then gh pr create",
      fires("git commit -m x && gh pr create --fill"), False)

# 3. QUOTING. The whole reason the matcher runs over an argv split. A commit
#    MESSAGE mentioning a push is the single likeliest false positive in this
#    corpus, and it is a dequoted token inside the commit's own argv.
check("push named inside a double-quoted commit message",
      fires('git commit -m "split the commit from the git push"'), False)
check("push named inside a single-quoted commit message",
      fires("git commit -m 'do not chain git push onto this'"), False)
check("both commands quoted in an echo",
      fires("echo 'git commit -m x; git push'"), False)
check("both commands quoted in a gh issue comment body",
      fires('gh issue comment 2992 -b "The shape is git commit -m x; '
            'git push -u origin b -- split it."'), False)
check("a commit message quoting the push and a real commit after it",
      fires('git commit -m "mentions git push"; git status'), False)

# 4. HEREDOC BODIES are data. A body redirected into a file, or fed to a
#    commit as its message, routinely quotes both commands -- this repo's
#    issue and PR bodies do it constantly. `examples-are-scanned.md`.
check("push inside a commit message heredoc",
      fires("git commit -F - <<'EOF'\nfix: stop chaining\n\nUse git push separately.\nEOF"),
      False)
check("both commands inside a file-redirect heredoc",
      fires("cat > /tmp/body.md <<'EOF'\ngit commit -m x\ngit push\nEOF\n"
            "gh issue create --body-file /tmp/body.md"), False)
check("unquoted heredoc tag",
      fires("cat <<EOF > /tmp/b.md\ngit commit -m x\ngit push\nEOF"), False)
check("<<- with a tab-indented terminator",
      fires("cat <<-EOF > /tmp/b.md\ngit commit\ngit push\n\tEOF"), False)

# 5. PLUMBING SIBLINGS. `no-unshipped-commit.py` records both of these as
#    measured bugs of a `git\s+commit\b` scan, because a word boundary sits
#    between `commit` and `-`. Comparing the whole subcommand token cannot
#    make that mistake, and these pin it.
check("git commit-tree is not git commit",
      fires("git commit-tree $T -m x; git push"), False)
check("git commit-graph write is not git commit",
      fires("git commit-graph write && git push"), False)
check("git push-anything is not git push",
      fires("git commit -m x && git push-mirror"), False)
# Only `git commit` arms the guard, and only `git push` fires it. Every other
# subcommand that also writes a commit object is out of scope by design, and
# these pin that: a mutation widening the commit branch to `("commit",
# "stash")` otherwise survived the whole suite.
for other in ("stash", "merge --no-ff other", "cherry-pick abc123",
              "revert abc123", "am /tmp/p.patch", "rebase --continue"):
    check(f"git {other.split()[0]} does not arm the guard",
          fires(f"git {other} && git push"), False)
check("git fetch does not fire the guard",
      fires("git commit -m x && git fetch origin"), False)
check("git send-email is not git push",
      fires("git commit -m x && git send-email HEAD^"), False)

# 6. Other command words that merely contain the subcommand names.
check("a script named git-commit-and-push",
      fires("./git-commit-and-push.sh"), False)
check("a grep for both strings",
      fires("grep -rn 'git commit' hooks/ && grep -rn 'git push' hooks/"),
      False)

# 7. THE OVERRIDE, anchored to a real env assignment on one of the matched
#    commands rather than to a mention anywhere in the text.
check("override prefixing the commit clears the refusal",
      fires("ALLOW_COMMIT_AND_PUSH=1 git commit -m x && git push"), False)
check("override prefixing the push also clears it",
      fires("git commit -m x && ALLOW_COMMIT_AND_PUSH=1 git push"), False)
# `export` is accepted because no-unauthorized-merge.py's ALLOW_MERGE anchor
# accepts it. An escape valve that rejects the spelling its own precedent uses
# sends the author looking for a bypass instead.
check("export as its own leading command clears it",
      fires("export ALLOW_COMMIT_AND_PUSH=1 && git commit -m x && git push"),
      False)
check("a bare leading assignment clears it",
      fires("ALLOW_COMMIT_AND_PUSH=1\ngit commit -m x\ngit push"), False)
check("a bare leading assignment before a semicolon clears it",
      fires("ALLOW_COMMIT_AND_PUSH=1; git commit -m x && git push"), False)
check("export prefixing the commit clears it",
      fires("export ALLOW_COMMIT_AND_PUSH=1 git commit -m x && git push"),
      False)

# SCOPE. Each of the four below LOOKS like the override and authorizes
# nothing, so each must still deny. The first two were measured clearing an
# earlier revision of this guard while setting no variable at all.
check("a subshell assignment does not persist, so it does not clear",
      fires("(ALLOW_COMMIT_AND_PUSH=1); git commit -m x && git push"), True)
check("a short-circuited assignment never runs, so it does not clear",
      fires("false && ALLOW_COMMIT_AND_PUSH=1; git commit -m x && git push"),
      True)
check("an assignment scoped to a third command does not clear it",
      fires("ALLOW_COMMIT_AND_PUSH=1 git status --short && git commit -m x "
            "&& git push"), True)
# The same scope defect by a third route: an override prefixing an EARLIER,
# unrelated push. That assignment does not persist to the push being refused,
# so it authorizes nothing about it -- and because the earlier probe used
# `git status`, which `evaluate` skips, the mutation covering this clause did
# not see the hole either.
check("an override on an earlier unrelated push does not clear it",
      fires("ALLOW_COMMIT_AND_PUSH=1 git push origin y; git commit -m a "
            "&& git push origin x"), True)
check("an override on a later commit does not clear an already-matched chain",
      fires("git commit -m a && git push origin x; "
            "ALLOW_COMMIT_AND_PUSH=1 git commit -m b"), True)
# The same shape with the overridden commit BETWEEN the matched commit and the
# push, which is the position ai-config#3003 asked for and the one no case
# here covered. It is a BEHAVIOURAL pin rather than a mutation probe: it
# cannot separate a mutant that only drops `and commit_argv is None` (see the
# block below), but it does go silent under the compound regression of
# dropping that clause AND restoring the overridden commit's `return None`,
# which is a shape this hook has shipped before. Measured on this branch.
check("an override on a middle commit does not clear the first-matched chain",
      fires("git commit -m a && ALLOW_COMMIT_AND_PUSH=1 git commit -m b "
            "&& git push"), True)

# WHICH commit gets matched, which is what `commit_argv is None` decides: the
# FIRST one, and a later commit never displaces it. The case above the middle
# override puts the second commit AFTER the push, so `evaluate` returns at the
# push and the clause never sees that second commit; the gap needs the second
# commit BETWEEN the first commit and the push (ai-config#3003).
#
# No `fires` assertion can close it. That issue proposed
# `git commit -m a && ALLOW_COMMIT_AND_PUSH=1 git commit -m b && git push`
# and reported the mutant allowing it; measured on this branch, the mutant
# DENIES it too, because an overridden second commit takes the `continue` and
# leaves `commit_argv` holding the first commit either way. The clause changes
# only WHICH argv is stored, never whether one is, so the two modules give the
# SAME deny/allow answer on every input. The one observable difference is the
# commit the refusal NAMES -- the command the message identifies as the one
# about to be lost. M10 below is the matching mutation.
_TWO_COMMITS = hook.evaluate("git commit -m a && git commit -m b && git push") or ""
check("the refusal names the first commit of a two-commit chain",
      "git commit -m a" in _TWO_COMMITS, True)
check("a later commit does not displace the already-matched one",
      "git commit -m b" in _TWO_COMMITS, False)
check("a MENTION of the override does not clear it",
      fires("git commit -m 'set ALLOW_COMMIT_AND_PUSH=1 next time' && git push"),
      True)
# Strictness: only the exact value `1`. Both the leading-assignment path and
# the per-command path are covered, because relaxing `== "1"` to
# `is not None` at either site alone survives a suite that pins only the other.
check("a leading assignment to 0 does not clear it",
      fires("ALLOW_COMMIT_AND_PUSH=0; git commit -m x && git push"), True)
check("a leading assignment to the empty string does not clear it",
      fires("ALLOW_COMMIT_AND_PUSH=; git commit -m x && git push"), True)
check("a prefix assignment to 0 does not clear it",
      fires("ALLOW_COMMIT_AND_PUSH=0 git commit -m x && git push"), True)
check("a prefix assignment to true does not clear it",
      fires("ALLOW_COMMIT_AND_PUSH=true git commit -m x && git push"), True)

# 7b. NO EXEMPTION for a "dry-run" or "delete" command. An exemption for these
# was written on a reviewer's request and then removed, because a second review
# measured two ways it went silent on a real loss -- see the hook's own
# "NO EXEMPTION" comment. Each case below is a deliberately accepted FALSE
# POSITIVE; the two after them are why.
check("a dry-run push is still denied", fires("git commit -m x; git push --dry-run"), True)
check("a branch-deletion push is still denied",
      fires("git commit -m x && git push --delete origin b"), True)
check("a dry-run commit is still denied",
      fires("git commit --dry-run -m x && git push"), True)
# THE REGRESSION CASES. Both are denied by `no-clobbering-push.py` -- which
# exempts `delete` in its reading pass only, and honours `--no-` negation --
# so an exemption keyed on the literal flag hid a genuine discarded commit.
check("a force-delete push is denied, as no-clobbering-push.py denies it too",
      fires("git commit -m wip && git push --force --delete origin old"), True)
check("a negated dry-run carrying a force is denied",
      fires("git commit -m wip && git push --dry-run --no-dry-run --force "
            "origin main"), True)

# 7c. THE REMEDY LINES the deny message prints are copy-paste text, so they
# must be requoted rather than space-joined. A space join re-emits
# `git commit -m "fix: a b; rm -rf x"` as a command that commits `fix:` and
# then runs `rm -rf x`.
remedy = hook.evaluate('git commit -m "fix: a b; rm -rf x" && git push') or ""
check("the remedy requotes an argument containing a separator",
      "git commit -m 'fix: a b; rm -rf x'" in remedy, True)
check("the remedy does not emit the argument bare",
      "git commit -m fix: a b; rm -rf x" in remedy, False)
for hostile in ('git commit -m "a $HOME b" && git push',
                "git commit -m 'a `id` b' && git push",
                'git commit -m "a \\"q\\" b" && git push'):
    text = hook.evaluate(hostile) or ""
    check(f"the remedy quotes {hostile[16:28]!r} safely",
          "call 1:  git commit -m '" in text or 'call 1:  git commit -m "' in text,
          True)
# ... but it must NOT claim byte-fidelity, because the newline rewrite in
# `simple_commands` is quote-blind: a multi-line `-m` message comes back with
# its newline as `;`. The message says so rather than inviting a paste.
multiline = hook.evaluate("git commit -m 'line1\nline2' && git push") or ""
check("a multi-line message is visibly re-rendered",
      "line1;line2" in multiline, True)
check("the message warns the lines are not byte-for-byte",
      "rather than reproducing them byte for byte" in multiline, True)
check("the message does not promise nothing needs to change",
      "Nothing else about the commands needs to change" in multiline, False)

# 8. Degenerate inputs.
check("empty command", fires(""), False)
check("whitespace only", fires("   \n  "), False)
check("unrelated command", fires("git status --short"), False)
check("bare git", fires("git; git push"), False)

# --------------------------------------------------------------- end-to-end

out = run_hook("git add -A && git commit -m x && git push -u origin b")
check("end-to-end fires", bool(out), True)
if out:
    try:
        payload = json.loads(out)
        hso = payload["hookSpecificOutput"]
        check("event name is PreToolUse", hso["hookEventName"], "PreToolUse")
        check("decision is deny", hso["permissionDecision"], "deny")
        text = hso.get("permissionDecisionReason") or ""
        check("reason names the commit", "git commit -m x" in text, True)
        check("reason names the push", "git push -u origin b" in text, True)
        check("reason names the override", "ALLOW_COMMIT_AND_PUSH" in text, True)
        check("reason cites the tracking issue", "#2992" in text, True)
        check("systemMessage present", bool(payload.get("systemMessage")), True)
    except (ValueError, KeyError) as exc:
        failures.append(f"end-to-end output not well-formed: {exc}")

check("end-to-end silent on a commit alone", run_hook("git commit -m x"), "")
check("end-to-end silent on a push alone", run_hook("git push"), "")
check("end-to-end silent on a quoted mention",
      run_hook("git commit -m 'then git push'"), "")
check("non-Bash tool ignored",
      run_hook("git commit -m x && git push", tool_name="Read"), "")

# ---------------------------------------------------------------- fail open

proc = subprocess.run([sys.executable, HOOK], input="not json",
                      capture_output=True, text=True, timeout=10)
check("malformed input exits 0", proc.returncode, 0)
check("malformed input prints nothing to stdout", proc.stdout.strip(), "")

for literal in ("123", "null", "[1,2]", '"a string"'):
    proc = subprocess.run([sys.executable, HOOK], input=literal,
                          capture_output=True, text=True, timeout=10)
    check(f"non-dict payload {literal} exits 0", proc.returncode, 0)
    check(f"non-dict payload {literal} prints no traceback",
          "Traceback" in proc.stderr, False)
    check(f"non-dict payload {literal} prints nothing to stdout",
          proc.stdout.strip(), "")

for bad in ({"tool_name": "Bash", "tool_input": "oops"},
            {"tool_name": "Bash", "tool_input": {"command": 42}},
            {"tool_name": "Bash", "tool_input": {}},
            {}):
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(bad),
                          capture_output=True, text=True, timeout=10)
    check(f"degenerate payload {bad} exits 0", proc.returncode, 0)
    check(f"degenerate payload {bad} prints no traceback",
          "Traceback" in proc.stderr, False)
    check(f"degenerate payload {bad} prints nothing to stdout",
          proc.stdout.strip(), "")

# An unparseable command (an unbalanced quote) must fail open rather than
# refuse. `shlex` raises ValueError, `simple_commands` returns None.
check("unparseable command fails open", fires("git commit -m \"unclosed && git push"),
      False)

# ------------------------------------------------------------- the mutation
#
# `shared/principles/fail-fast.md`: a guard whose condition ANDs several
# clauses masks its own mutation test, because breaking one clause leaves the
# others still refusing the positive cases. So each mutation is checked against
# the specific case it should break rather than against the suite as a whole.
#
# TWO properties are asserted per mutation, and the second is what an earlier
# revision of this section lacked. A mutation that REPLACES `evaluate` with a
# locally written stand-in asserts a property of the stand-in: an adversarial
# review gutted `evaluate` to `return None` and two of the four mutations here
# still passed, because they never called the original at all. So every
# mutation now also asserts that the UNMUTATED module answers differently on
# the same input. A mutation whose two halves agree is testing nothing, and
# `_mutate` fails it explicitly rather than passing quietly.

def _mutate(label, patch, command, expect_mutant):
    """Assert the mutant answers `expect_mutant` AND the real module differs.

    The differential half is the guard against a vacuous mutation. If the
    unmutated module already gives the mutant's answer, the case distinguishes
    nothing, and that is reported as a failure of the TEST rather than of the
    hook.
    """
    baseline = hook.evaluate(command) is not None
    if baseline == expect_mutant:
        failures.append(
            f"MUTATION {label}: vacuous -- the unmutated module also answers "
            f"{baseline!r} on this input, so the case distinguishes nothing")
        return
    mspec = importlib.util.spec_from_file_location("mutant", HOOK)
    mutant = importlib.util.module_from_spec(mspec)
    mspec.loader.exec_module(mutant)
    patch(mutant)
    check(f"MUTATION {label}", mutant.evaluate(command) is not None,
          expect_mutant)


# M1 -- drop the ORDER constraint, by patching a COLLABORATOR rather than
#       `evaluate`. Reversing the command list makes a push-then-commit call
#       look like commit-then-push to the real `evaluate`, so the order clause
#       is the only thing that can decide it. An earlier revision reassigned
#       `m.evaluate` and supplied its own order-blind fallback, which passed
#       against an `evaluate` gutted to `return None` -- the mutation was
#       testing its own stand-in.
def _drop_order(m):
    real = m.simple_commands

    def split(command):
        cmds = real(command)
        return None if cmds is None else list(reversed(cmds))
    m.simple_commands = split


_mutate("dropping the order constraint fires on push-then-commit",
        _drop_order, "git push; git commit -m x", True)

# M2 -- replace the ARGV SPLIT with a raw substring scan, the naive
#       implementation this hook exists to avoid. Patched at the collaborator,
#       so the real `evaluate` runs over a deliberately quoting-blind split:
#       every whitespace-separated word becomes its own one-token command, so
#       `git push` inside a commit message reads as a command position.
def _quoting_blind_split(m):
    def split(command):
        out, cur = [], []
        for word in command.replace("&&", ";").replace("\n", ";").split():
            if word == ";":
                if cur:
                    out.append(cur)
                    cur = []
            elif word.endswith(";"):
                cur.append(word[:-1])
                out.append(cur)
                cur = []
            else:
                cur.append(word)
        if cur:
            out.append(cur)
        # a quoting-blind scanner sees each `git <sub>` as its own command
        flat = []
        for argv in out:
            i = 0
            while i < len(argv):
                if argv[i].strip("\"'") == "git" and i + 1 < len(argv):
                    flat.append(["git", argv[i + 1].strip("\"'")])
                    i += 2
                else:
                    i += 1
        return flat or out
    m.simple_commands = split


_mutate("a quoting-blind split fires on a quoted commit message",
        _quoting_blind_split,
        'git commit -m "split the commit from the git push"', True)

# M3 -- compare the subcommand with `startswith` instead of `==`, which is the
#       `git\s+commit\b` bug `no-unshipped-commit.py` measured twice.
def _prefix_match(m):
    real = m.git_subcommand

    def loose(argv):
        parsed = real(argv)
        if parsed is None:
            return None
        sub, rest, env = parsed
        for name in ("commit", "push"):
            if sub.startswith(name):
                return name, rest, env
        return parsed
    m.git_subcommand = loose


_mutate("prefix matching fires on git commit-tree",
        _prefix_match, "git commit-tree $T -m x; git push", True)

# M3b -- the SAME defect at the clause that actually discriminates. `evaluate`
#        filters on `sub not in ("commit", "push")` before it branches, so a
#        mutation of the later `sub == "commit"` alone is masked by that
#        filter and leaves the suite green -- `fail-fast.md`'s "a guard whose
#        condition ANDs several clauses masks its own mutation test", observed
#        here rather than reasoned about. This patches the filter instead.
def _prefix_filter(m):
    real = m.git_subcommand

    def loose(argv):
        parsed = real(argv)
        if parsed is None:
            return None
        sub, rest, env = parsed
        # A prefix-matching classifier, as a `git\s+commit\b` regex would be.
        if sub.startswith("commit"):
            return "commit", rest, env
        if sub.startswith("push"):
            return "push", rest, env
        return parsed
    m.git_subcommand = loose


_mutate("prefix matching at the discriminating clause fires on commit-graph",
        _prefix_filter, "git commit-graph write && git push", True)

# M7 -- widen the leading-override anchor from a SEPARATOR to any whitespace,
#       which is what an earlier revision did. `ALLOW_COMMIT_AND_PUSH=1 git
#       status && git commit && git push` then clears the guard, even though
#       that assignment is scoped to `git status` and never reaches the push.
def _loose_leading_anchor(m):
    import re as _re
    m.LEADING_OVERRIDE = _re.compile(
        r"\A\s*(?:export\s+)?" + m.OVERRIDE + r"=1(?:\s|;|&|\Z)")


_mutate("a whitespace-anchored override is cleared by a scoped prefix",
        _loose_leading_anchor,
        "ALLOW_COMMIT_AND_PUSH=1 git status --short && git commit -m x "
        "&& git push", False)


# M9 -- rejoin the remedy lines with a bare space instead of `shlex.join`, so
#       the message re-emits dequoted argv as copy-paste text.
def _space_join(m):
    real = m.evaluate

    def evaluate(command):
        out = real(command)
        return out if out is None else out.replace("'", "")
    m.evaluate = evaluate


mspec = importlib.util.spec_from_file_location("mutant_join", HOOK)
mutant_join = importlib.util.module_from_spec(mspec)
mspec.loader.exec_module(mutant_join)
_space_join(mutant_join)
check("MUTATION a space-joined remedy loses the quoting",
      "git commit -m 'fix: a b; rm -rf x'" in (mutant_join.evaluate(
          'git commit -m "fix: a b; rm -rf x" && git push') or ""),
      False)

# M4 -- widen the override to any mention. Must start CLEARING a deny it should
#       not, so the expectation is False against a real-module baseline of True.
def _loose_override(m):
    real = m.evaluate

    def evaluate(command):
        if m.OVERRIDE in command:
            return None
        return real(command)
    m.evaluate = evaluate


_mutate("an unanchored override is cleared by a mere mention",
        _loose_override,
        "git commit -m 'set ALLOW_COMMIT_AND_PUSH=1 next time' && git push",
        False)

# M5 -- read the override off ANY command rather than the commit or push,
#       which is what an earlier revision did. A stale prefix on an unrelated
#       `git status` then silently disarms the guard.
def _unscoped_override(m):
    # Its own handle on the library: the hook imports only what it calls,
    # and it does not call `strip_env`.
    import shellcmd as _shellcmd
    real = m.evaluate

    def evaluate(command):
        for argv in (m.simple_commands(command) or []):
            env, _rest = _shellcmd.strip_env(argv)
            if m.env_value(env, m.OVERRIDE) == "1":
                return None
        return real(command)
    m.evaluate = evaluate


_mutate("an unscoped override is cleared by a prefix on a third command",
        _unscoped_override,
        "ALLOW_COMMIT_AND_PUSH=1 git status --short && git commit -m x "
        "&& git push",
        False)

# M5b -- the same clause, probed with an unrelated PUSH rather than a
#        `git status`. `evaluate` skips a non-commit/push argv before it ever
#        reads the override, so M5's probe could not reach the clause that
#        actually decides this, and a revision reading the override off any
#        commit-or-push passed M5 while going silent on the shape below.
def _override_on_any_git(m):
    real = m.evaluate

    def evaluate(command):
        for argv in (m.simple_commands(command) or []):
            parsed = m.git_subcommand(argv)
            if parsed and parsed[0] in ("commit", "push"):
                if m.env_value(parsed[2], m.OVERRIDE) == "1":
                    return None
        return real(command)
    m.evaluate = evaluate


_mutate("reading the override off any commit or push clears an unrelated one",
        _override_on_any_git,
        "ALLOW_COMMIT_AND_PUSH=1 git push origin y; git commit -m a "
        "&& git push origin x",
        False)

# M6 -- restore the heredoc-blanking defect in the library: substitute a bare
#       `<<` so it fuses with the newline-derived `;` into one `<<;` token the
#       separator test does not recognize. Must go silent on the reported
#       incident shape, which is the regression this suite exists to hold.
def _fuse_heredoc(m):
    import re as _re
    real_split = m.simple_commands

    def split(command):
        import shellcmd as sc
        patched = _re.sub(r"\\\r?\n", " ", command)
        # `_heredoc_free` emits `" << "`; collapsing the spaces is exactly the
        # defect this mutation restores. Reconstructed through the real
        # function rather than a private regex, so the mutation keeps working
        # when the heredoc scanner changes shape.
        patched = sc._heredoc_free(patched).replace(" << ", "<<")
        patched = patched.replace("\n", ";")
        return real_split(patched)
    m.simple_commands = split


_mutate("fusing the heredoc marker with the separator goes silent",
        _fuse_heredoc, INCIDENT, False)

# M10 -- drop `and commit_argv is None`, so a later commit displaces the
#        first-matched one. Rewritten in SOURCE rather than patched at a
#        collaborator, because the clause is a local test inside `evaluate`
#        with nothing to stub; and asserted on the reason TEXT rather than
#        through `_mutate`, because the clause changes only WHICH argv is
#        stored, never whether one is -- so the two modules give the same
#        deny/allow answer on every input, a boolean case is vacuous, and
#        `_mutate` would report it as such.
#
#        A source anchor rots silently when the clause is reworded, which
#        would leave this mutation pinning nothing while still passing. So a
#        missing or duplicated anchor is a FAILURE of the test rather than a
#        skip, and the count is asserted rather than mere presence, matching
#        `test-no-handrolled-verdict-parse.py`'s own anchor check -- a bare
#        `in` test plus `replace(..., 1)` would silently patch a docstring
#        occurrence instead of the code, and this hook quotes its own source
#        in docstrings heavily.
_M10_CLAUSE = 'if sub == "commit" and commit_argv is None:'
with open(HOOK, encoding="utf-8") as _handle:
    _hook_source = _handle.read()
_M10_HITS = _hook_source.count(_M10_CLAUSE)
if _M10_HITS != 1:
    failures.append(
        "MUTATION a displaced commit_argv names the later commit: the source "
        "anchor " + repr(_M10_CLAUSE) + f" appears {_M10_HITS} times, expected "
        "exactly 1, so this mutation no longer pins the clause -- re-anchor "
        "it. (The two behaviour cases above still pin which commit is named.)")
else:
    mutant_first = types.ModuleType("mutant_first")
    mutant_first.__file__ = HOOK
    exec(compile(_hook_source.replace(_M10_CLAUSE, 'if sub == "commit":', 1),
                 HOOK, "exec"), mutant_first.__dict__)
    _M10_REASON = mutant_first.evaluate(
        "git commit -m a && git commit -m b && git push") or ""
    check("MUTATION a displaced commit_argv names the later commit",
          "git commit -m b" in _M10_REASON, True)
    check("MUTATION a displaced commit_argv drops the first commit",
          "git commit -m a" in _M10_REASON, False)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
