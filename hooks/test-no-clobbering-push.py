"""Test the no-clobbering-push guard, clause by clause.

Test case #1 is the incident shape verbatim, per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against the
incident that prompted it": a branch whose remote tip carries a commit the
local checkout does not have -- the `@claude` agent's `main`-sync push, or a
second session's fix -- and a `git push --force` about to overwrite it.

Like `test-flag-reset-hard-uncommitted-work.py`, this hook reads LIVE
repository state, so each case is a real scratch git repo. It additionally
needs a real REMOTE, because the whole point of the guard is that it takes a
fresh `git ls-remote` reading rather than trusting a remote-tracking ref -- so
every fixture builds a bare repo alongside and wires it up as `origin`.

The second half is the MUTATION harness described in
`shared/principles/fail-fast.md`'s "A guard whose condition ANDs several
clauses masks its own mutation test the same way".

Run:  python3 hooks/test-no-clobbering-push.py hooks/no-clobbering-push.py
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.abspath(sys.argv[1])
_TMPDIRS = []


def _run(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=check)


def _write(path, name, content="x\n"):
    with open(os.path.join(path, name), "w", encoding="utf-8") as handle:
        handle.write(content)


def _commit(path, name, content):
    _write(path, name, content)
    _run(path, "add", name)
    _run(path, "commit", "-qm", f"add {name}")


def bash(command, payload_cwd=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if payload_cwd is not None:
        payload["cwd"] = payload_cwd
    return payload


# `case_id -> directory`, filled in by the fixture that builds it. For each
# entry, every `git -C ...` line the warning emits must survive `shlex.split`
# and name that directory as one argument. A substring check cannot see this:
# `git -C /tmp/a b/wt fetch ...` contains `git -C ` and is still unrunnable.
ROUNDTRIP = {}


# ---------------------------------------------------------------- fixtures

def _new_repo():
    """A repo on `main` with one commit and a bare `origin` carrying it."""
    bare = tempfile.mkdtemp()
    _TMPDIRS.append(bare)
    _run(bare, "init", "-q", "--bare", "-b", "main")

    path = tempfile.mkdtemp()
    _TMPDIRS.append(path)
    _run(path, "init", "-q", "-b", "main")
    _run(path, "config", "user.email", "t@t.com")
    _run(path, "config", "user.name", "t")
    _commit(path, "base.txt", "base\n")
    _run(path, "remote", "add", "origin", bare)
    _run(path, "push", "-q", "-u", "origin", "main")
    return path, bare


def _remote_advances(path, bare, keep_object):
    """Put a commit on `origin/main` that local HEAD does not contain.

    `keep_object=True` leaves the object in the local store (the shape a prior
    fetch produces); `keep_object=False` builds it in a separate clone, so the
    local repo has never seen it -- the sharper of the two signals.
    """
    if keep_object:
        _commit(path, "theirs.txt", "theirs\n")
        _run(path, "push", "-q", "origin", "main")
        _run(path, "reset", "--hard", "-q", "HEAD~1")
        return
    other = tempfile.mkdtemp()
    _TMPDIRS.append(other)
    _run(other, "clone", "-q", bare, "wc")
    wc = os.path.join(other, "wc")
    _run(wc, "config", "user.email", "o@o.com")
    _run(wc, "config", "user.name", "other-agent")
    _commit(wc, "theirs.txt", "theirs\n")
    _run(wc, "push", "-q", "origin", "main")


def _local_advances(path):
    """A local commit the remote does not have -- an ordinary fast-forward."""
    _commit(path, "mine.txt", "mine\n")


def _named_remote(path, bare, name):
    """Add a second remote under a name that is NOT the config fallback."""
    _run(path, "remote", "add", name, bare)


def _second_worktree(path, branch, start="HEAD", leaf="wt"):
    """A second worktree of `path`, checked out on a new `branch`.

    `HEAD` is per-worktree; branch refs are not. That asymmetry is why every
    cross-worktree case below pushes `HEAD:<branch>` rather than a named
    source ref: a named branch resolves identically in both directories, so it
    could not tell the two readings apart.

    `leaf` names the directory inside the holder. Every other caller leaves it
    alone; the one that does not passes a name carrying a SPACE, which is the
    only way to tell a quoted remediation command from an unquoted one.
    """
    holder = tempfile.mkdtemp()
    _TMPDIRS.append(holder)
    target = os.path.join(holder, leaf)
    _run(path, "worktree", "add", "-q", "-b", branch, target, start)
    return target


def _diverged_peer_worktree(path, branch, leaf="wt", target=None):
    """A second worktree whose HEAD diverges from `origin/<branch>`, while the
    session's own HEAD equals that remote tip exactly.

    Both halves are load-bearing. The worktree half is the divergence the
    guard exists to report; the session half is what it read instead, and it
    reads as "already pushed" -- so resolving HEAD in the session's directory
    is a false NEGATIVE here, not merely a wrongly-worded warning.

    `target` places the worktree at an EXACT path rather than inside a fresh
    holder. Only the two `-C` cases pass it, and they need it: what they pin
    is a `-C` value the guard must DECLINE, and a decline is observable only
    where the literal path the guard would otherwise build is itself a real
    diverged worktree.
    """
    _commit(path, "shared.txt", "shared\n")
    _run(path, "push", "-q", "origin", "main")
    if target is None:
        wt = _second_worktree(path, branch, "HEAD~1", leaf)
    else:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        _run(path, "worktree", "add", "-q", "-b", branch, target, "HEAD~1")
        wt = target
    _commit(wt, "peer.txt", "peer\n")
    _run(wt, "push", "-q", "origin", branch)
    _run(path, "push", "-q", "-f", "origin", f"main:{branch}")
    return wt


def _wrong_repo_worktree(path, bare, branch):
    """A second worktree whose push is an ordinary fast-forward, while the
    session's own directory diverges from `origin/<branch>`.

    The mirror of `_diverged_peer_worktree`: there a reading taken in the
    session's directory is a false NEGATIVE, here it is a false POSITIVE. Any
    case built on this one is silent only if the guard read the right
    repository, or declined to read at all.
    """
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    wt = _second_worktree(path, branch)
    _commit(wt, "first.txt", "first\n")
    _run(wt, "push", "-q", "origin", branch)
    _commit(wt, "second.txt", "second\n")
    return wt


# --- should DENY ---------------------------------------------------------

def incident_case(path, bare):
    """TEST CASE #1: the remote gained another agent's commit, and a bare
    `--force` is about to overwrite it."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push --force origin HEAD"


def bare_force_case(path, bare):
    _local_advances(path)
    return "git push --force"


def short_f_case(path, bare):
    _local_advances(path)
    return "git push -f origin HEAD"


def short_cluster_case(path, bare):
    """`-fu` is real, accepted bash: `f` inside a short cluster means force."""
    _local_advances(path)
    return "git push -fu origin HEAD"


def warn_then_force_case(path, bare):
    """A compound command whose FIRST push warns and whose SECOND is a bare
    force push.

    A single-pass `evaluate()` returned on the first verdict, and a warn only
    attaches context -- it does not block -- so the force push ran. The
    reverse order was always safe, because a deny blocks the whole Bash call
    regardless of position. Nothing in the suite chained two pushes, so the
    path was untested as well as wrong.
    """
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push; git push --force origin HEAD"


def force_plus_lease_case(path, bare):
    """`git push --help` on `-f, --force`: "when --force-with-lease option is
    used, the command refuses ... This flag disables these checks." So the two
    together are a plain force push, and reading the lease as clearing the
    refusal was a bypass."""
    _local_advances(path)
    return "git push --force --force-with-lease origin HEAD"


def negated_dry_run_case(path, bare):
    """Every `git push` option has a `--[no-]` form, so a positive-only scan is
    order-blind: this really does transfer."""
    _local_advances(path)
    return "git push --dry-run --no-dry-run --force origin HEAD"


def force_with_value_cluster_case(path, bare):
    """`-fo ci.skip` is accepted bash: `f` is force and `o` eats the next word.
    A matcher that does not know `o` misses the force AND mistakes `ci.skip`
    for the remote."""
    _local_advances(path)
    return "git push -fo ci.skip origin HEAD"


# --- should WARN ---------------------------------------------------------

def diverged_known_case(path, bare):
    """The remote tip is not an ancestor of HEAD, and its object IS local."""
    _remote_advances(path, bare, keep_object=True)
    return "git push origin HEAD"


def diverged_unknown_case(path, bare):
    """The remote tip is not an ancestor of HEAD, and its object is NOT local
    -- the remote moved after the last fetch."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push"


def diverged_lease_case(path, bare):
    """A leased force-push still gets the reading -- the lease is not the
    check, and this guard refuses only the bare form."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push --force-with-lease --force-if-includes"


def repo_option_case(path, bare):
    """`--repo <repository>` names the remote. Skipping it as a mere option
    value resolved the push against the configured remote instead."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    _named_remote(path, bare, "upstream")
    return "git push --repo upstream HEAD"


def named_branch_case(path, bare):
    """`git push origin feature-x` while `main` is checked out pushes local
    `feature-x`, not HEAD.

    The remote's `feature-x` is forced to a commit that IS an ancestor of local
    `main` while local `feature-x` genuinely diverges from it. Resolving the
    local side as HEAD read that as a fast-forward and stayed silent -- a false
    negative in the exact situation this guard exists for.
    """
    # main advances to a commit the remote feature-x will also carry.
    _commit(path, "shared.txt", "shared\n")
    _run(path, "push", "-q", "origin", "main")
    # feature-x branches off the ORIGINAL base and diverges independently.
    _run(path, "checkout", "-q", "-b", "feature-x", "HEAD~1")
    _commit(path, "mine-fx.txt", "mine\n")
    _run(path, "push", "-q", "origin", "feature-x")
    # The remote's feature-x is moved onto main's tip; local feature-x is not.
    _run(path, "push", "-q", "-f", "origin", "main:feature-x")
    _run(path, "checkout", "-q", "main")
    return "git push origin feature-x"


def named_branch_source_missing_case(path, bare):
    """The source ref exists on the REMOTE and diverges, but does not resolve
    locally -- so there is nothing to compare and the guard declines rather
    than silently substituting HEAD.

    The remote half matters: without it the `ls-remote` read comes back empty
    and the case would pass for the wrong reason.
    """
    _run(path, "checkout", "-q", "-b", "theirs-only")
    _commit(path, "theirs-only.txt", "theirs\n")
    _run(path, "push", "-q", "origin", "theirs-only")
    _run(path, "checkout", "-q", "main")
    _run(path, "branch", "-q", "-D", "theirs-only")
    _local_advances(path)
    return "git push origin theirs-only"


def explicit_current_branch_case(path, bare):
    """`git push origin main` while `main` IS checked out.

    `source` resolves to the literal `"main"` rather than the `"HEAD"`
    sentinel, so a `source == "HEAD"` test sent this down the not-on-that-branch
    path and emitted `git checkout main   # you are not on the branch being
    pushed`, which is false. Harmless to run and still wrong to say.
    """
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push origin main"


def cross_worktree_diverged_case(path, bare):
    """The push runs in a second worktree, via a leading `cd`, and diverges
    there while the session's own directory shows nothing to report."""
    wt = _diverged_peer_worktree(path, "peer")
    return f"cd {wt} && git push origin HEAD:peer"


def dash_c_worktree_case(path, bare):
    """`git -C <worktree> push` moves the push without a `cd`, so the `-C`
    values have to be read out rather than skipped as option noise."""
    wt = _diverged_peer_worktree(path, "peer-c")
    return f"git -C {wt} push origin HEAD:peer-c"


def subshell_push_case(path, bare):
    """`(cd <worktree> && git push)` -- the `cd` and the push are in the SAME
    subshell, so the `cd` does apply. The counterpart to S21, which is the
    same `cd` with the push outside the parentheses."""
    wt = _diverged_peer_worktree(path, "peer-inner")
    return f"(cd {wt} && git push origin HEAD:peer-inner)"


def brace_group_case(path, bare):
    """`{ cd <worktree>; } && git push` -- a brace group runs in the CURRENT
    shell rather than forking, so its `cd` outlives the closing brace.

    `_simple_commands` splits on operators only, so the opening brace arrives
    attached to the `cd` as a word; without stripping it the `cd` is invisible
    and the push is read in the session's own repository -- ai-config#2451's
    wrong-repository reading by a third route.
    """
    wt = _diverged_peer_worktree(path, "peer-brace")
    return f"{{ cd {wt}; }} && git push origin HEAD:peer-brace"


def spaced_worktree_case(path, bare):
    """The worktree the push runs in lives under a directory carrying a space.

    The verdict is the same warning W8 gets; what this case pins is that the
    emitted `git -C <dir>` survives a round trip through `shlex.split`.
    Unquoted, git reads the first word as the directory and the rest as stray
    arguments, so advice whose whole purpose is to be runnable is not -- and
    every other fixture here uses a `tempfile.mkdtemp()` path with no space,
    which is what kept the omission invisible.
    """
    wt = _diverged_peer_worktree(path, "peer-space", leaf="my worktree")
    ROUNDTRIP["W13"] = wt
    return f"cd {shlex.quote(wt)} && git push origin HEAD:peer-space"


def payload_cwd_case(path, bare):
    """The Bash call's own `cwd` names a different directory from the hook
    process's, with no `cd` and no `-C` to reveal it."""
    wt = _diverged_peer_worktree(path, "peer-payload")
    return "git push origin HEAD:peer-payload", wt


def value_cluster_remote_case(path, bare):
    """`-uo ci.skip upstream HEAD`: `o` eats `ci.skip`, so the remote is
    `upstream`. Without that, `ci.skip` is read as the remote and the reading
    never happens."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    _named_remote(path, bare, "upstream")
    return "git push -uo ci.skip upstream HEAD"


# --- should STAY SILENT --------------------------------------------------

def leased_fast_forward_case(path, bare):
    """`--force-with-lease` is the prescribed remedy: never refused."""
    _local_advances(path)
    return "git push --force-with-lease --force-if-includes origin HEAD"


def override_case(path, bare):
    """A real `ALLOW_FORCE_PUSH=1` assignment clears the refusal."""
    _local_advances(path)
    return "ALLOW_FORCE_PUSH=1 git push --force origin HEAD"


def dry_run_case(path, bare):
    """A dry run transfers nothing, so it can clobber nothing."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push --dry-run --force origin HEAD"


def delete_case(path, bare):
    """Branch deletion is `skills/clean-branches`' territory, not this
    guard's."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push --delete origin main"


def fast_forward_case(path, bare):
    """The overwhelmingly common push: remote tip is an ancestor of HEAD."""
    _local_advances(path)
    return "git push origin HEAD"


def up_to_date_case(path, bare):
    """Remote tip equals local HEAD."""
    return "git push origin HEAD"


def new_branch_case(path, bare):
    """No remote ref of that name yet -- nothing to collide with."""
    _run(path, "checkout", "-q", "-b", "feature/new")
    _local_advances(path)
    return "git push -u origin HEAD"


def cross_worktree_fast_forward_case(path, bare):
    """ai-config#2451 verbatim: the push is an ordinary fast-forward in the
    worktree it runs from, while the session's own directory sits on an
    unrelated branch.

    Resolving HEAD there reported a divergence that did not exist, named the
    pushing session's own commits as somebody else's, and prescribed a
    `git merge origin/<branch>` that would have merged a branch into itself.
    """
    wt = _wrong_repo_worktree(path, bare, "ums-lessons")
    return f"cd {wt} && git push origin HEAD:ums-lessons"


def git_dir_option_case(path, bare):
    """`--git-dir`/`--work-tree` move the repository a push reads without
    moving any directory, so resolving the directory alone reads the
    session's. Declining is the answer, as for `pushd`."""
    wt = _wrong_repo_worktree(path, bare, "gitdir-opt")
    return (f"git --git-dir {wt}/.git --work-tree {wt} "
            "push origin HEAD:gitdir-opt")


def git_dir_env_case(path, bare):
    """The same redirection spelled as an env prefix, which `_lead_prefix`
    skips along with every other assignment."""
    wt = _wrong_repo_worktree(path, bare, "gitdir-env")
    return (f"GIT_DIR={wt}/.git GIT_WORK_TREE={wt} "
            "git push origin HEAD:gitdir-env")


def subshell_cd_case(path, bare):
    """A `cd` inside a subshell dies at the `)`, so this push runs in the
    call's own directory.

    Reading it in the subshell's directory is a warning about a repository the
    push never touches -- the wrong-repository reading of ai-config#2451, and
    one this guard introduced for itself when it started tracking `cd` at all.
    """
    wt = _diverged_peer_worktree(path, "peer-subshell")
    return f"(cd {wt} && true) && git push origin HEAD:peer-subshell"


def sibling_subshell_cd_case(path, bare):
    """`(cd <worktree> && true) && (git push ...)` -- two SIBLING subshells.

    Both sit at the same nesting depth, so a directory kept per depth hands
    them one slot and the first one's `cd` leaks into the second. That is the
    wrong-repository reading of ai-config#2451 arriving through the very
    mechanism added to stop it, which is why the pair with S21 is the pin
    rather than S21 alone: S21's push sits OUTSIDE the parentheses, so it is
    silent under either keying.
    """
    wt = _diverged_peer_worktree(path, "peer-sibling")
    return (f"(cd {wt} && true) && "
            "(git push origin HEAD:peer-sibling)")


def conditional_cd_case(path, bare):
    """`if ...; then cd <worktree>; fi; git push` with a FALSE condition.

    A real shell never runs the `cd`, so the push is an already-pushed no-op
    in the call's own directory. `_simple_commands` splits on operators and
    models no short-circuiting, so the branch body arrives as an ordinary
    `cd` command and applying it warns about a repository the push never
    touches -- the wrong-repository reading of ai-config#2451.
    """
    wt = _diverged_peer_worktree(path, "peer-cond")
    return (f"if [ -d /nonexistent-ncp ]; then cd {wt}; fi; "
            "git push origin HEAD:peer-cond")


def alternative_cd_case(path, bare):
    """`cd <here> || cd <worktree>; git push` -- the first `cd` succeeds, so
    the alternative never runs.

    The counterpart to the branch body above, and the shape that shows why
    `&&` and `||` cannot be treated alike: a `cd` after `||` runs only when
    what preceded it FAILED.
    """
    wt = _diverged_peer_worktree(path, "peer-alt")
    return f"cd {path} || cd {wt}; git push origin HEAD:peer-alt"


def branch_body_cd_case(path, bare):
    """`if ...; then echo no; cd <worktree>; fi; git push` -- a branch body of
    MORE than one command.

    The keyword that opens a body attaches to that body's FIRST command, so
    the `cd` here carries none at all. Recognizing the keyword declined S23
    and applied this one, which is the same wrong-repository reading of
    ai-config#2451 arriving one command further along (measured 2026-09-04).
    """
    wt = _diverged_peer_worktree(path, "peer-body")
    return (f"if [ -d /nonexistent-ncp ]; then echo no; cd {wt}; fi; "
            "git push origin HEAD:peer-body")


def else_arm_cd_case(path, bare):
    """`if [ -d / ]; then true; else true && cd <worktree>; fi; git push` --
    the `then` branch is the one taken, so the `else` arm never runs.

    Its `cd` follows `&&`, the one separator this guard deliberately keeps, so
    no operator can decline it: only the region the `if` opened can.
    """
    wt = _diverged_peer_worktree(path, "peer-else")
    return (f"if [ -d / ]; then true; else true && cd {wt}; fi; "
            "git push origin HEAD:peer-else")


def background_cd_case(path, bare):
    """`cd <worktree> & git push` -- a backgrounded `cd` runs in a subshell,
    so the push runs where the Bash call started.

    The operator that reveals the fork FOLLOWS the `cd`. The one before it is
    the start of the command, which is what an ordinary `cd` carries too.
    """
    wt = _diverged_peer_worktree(path, "peer-bg")
    return f"cd {wt} & git push origin HEAD:peer-bg"


def pipeline_cd_case(path, bare):
    """`cd <worktree> | cat; git push` -- a pipeline element is forked as
    well, so this `cd` moves no directory the push can see."""
    wt = _diverged_peer_worktree(path, "peer-pipe")
    return f"cd {wt} | cat; git push origin HEAD:peer-pipe"


def condition_cd_if_case(path, bare):
    """`if cd <worktree>; then git push ...; fi` -- the `cd` is the CONDITION.

    It shares one argv with the keyword that opens the region, so the region
    never sees it and the operators recorded either side belong to the whole
    `if` rather than to the `cd`. Leaving it unseen read the push in the
    session's own repository, which diverges here: the
    wrong-repository warning of ai-config#2451, its misattributed commit list
    and its branch-into-itself merge included (measured 2026-09-04).

    A condition runs in the current shell, so declining is the answer rather
    than resolving: whether the shell is still there after `fi` depends on
    whether the condition succeeded.
    """
    wt = _wrong_repo_worktree(path, bare, "cond-if")
    return f"if cd {wt}; then git push origin HEAD:cond-if; fi"


def condition_cd_while_case(path, bare):
    """`while cd <worktree>; do git push ...; done` -- the same argv shape
    under a different keyword, so a fix keyed on `if` alone would miss it."""
    wt = _wrong_repo_worktree(path, bare, "cond-while")
    return f"while cd {wt}; do git push origin HEAD:cond-while; done"


def background_cd_newline_case(path, bare):
    """S29 with the `&` at the END OF A LINE, which is how a multi-line Bash
    call spells it.

    A newline is rewritten to `;` before parsing, so the fork arrives as the
    single punctuation run `&;`. Folding the run reported the `;` and
    discarded the `&`, which applied a `cd` a real shell forks -- the
    wrong-repository reading arriving through the very clause added to stop it
    (measured 2026-09-04).
    """
    wt = _diverged_peer_worktree(path, "peer-bg-nl")
    return f"cd {wt} &\ngit push origin HEAD:peer-bg-nl"


def background_list_cd_case(path, bare):
    """`cd <worktree> && true & git push` -- the `&` backgrounds the whole
    AND-OR list, so the `cd` is forked even though `&&` follows it.

    The operator after the `cd` is the one separator this guard deliberately
    keeps, so only propagating the `&` backwards over the chain can decline
    it.
    """
    wt = _diverged_peer_worktree(path, "peer-bg-list")
    return f"cd {wt} && true & git push origin HEAD:peer-bg-list"


def alternative_cd_newline_case(path, bare):
    """S24 with the `||` at the END OF A LINE, so the run is `||;`."""
    wt = _diverged_peer_worktree(path, "peer-alt-nl")
    return f"true ||\ncd {wt}\ngit push origin HEAD:peer-alt-nl"


def pipeline_rhs_cd_newline_case(path, bare):
    """S31 with the `|` at the END OF A LINE, so the run is `|;`."""
    wt = _diverged_peer_worktree(path, "peer-pipe-rhs-nl")
    return f"echo x |\ncd {wt}\ngit push origin HEAD:peer-pipe-rhs-nl"


def pipeline_rhs_cd_case(path, bare):
    """`echo x | cd <worktree>; git push` -- the same fork read from the other
    side, where the `|` PRECEDES the `cd` rather than following it."""
    wt = _diverged_peer_worktree(path, "peer-pipe-rhs")
    return f"echo x | cd {wt}; git push origin HEAD:peer-pipe-rhs"


def dash_c_unexpanded_case(path, bare):
    """`git -C "$WT" push` -- the variable is unexpanded, so no directory is
    named.

    The worktree really is at `<path>/$WT`, which is the only way to tell a
    decline from the silence a nonexistent directory produces anyway: joining
    the token on as a literal path component lands exactly there and warns.
    """
    _diverged_peer_worktree(path, "peer-var",
                            target=os.path.join(path, "$WT"))
    return 'git -C "$WT" push origin HEAD:peer-var'


def dash_c_tilde_case(path, bare):
    """`git -C ~ncp-nosuchuser/wt push` -- a `~` git never sees, because the
    SHELL is what expands one.

    Joining it on as a literal path component is what the worktree at
    `<path>/~ncp-nosuchuser/wt` catches. Expanding it is the right answer and
    an unknown user has none, so the reading is declined.
    """
    _diverged_peer_worktree(
        path, "peer-tilde",
        target=os.path.join(path, "~ncp-nosuchuser", "wt"))
    return "git -C ~ncp-nosuchuser/wt push origin HEAD:peer-tilde"


def indeterminate_cd_case(path, bare):
    """`cd -` needs OLDPWD, which no static scan has.

    Declining is the point: the session's directory genuinely diverges here,
    so falling back to it would produce a confident warning about a repository
    the push may never touch.
    """
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "cd - && git push origin HEAD"


def quoted_mention_case(path, bare):
    """A mention inside a quoted string is not an invocation."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return 'echo "git push --force origin HEAD"'


def heredoc_mention_case(path, bare):
    """A heredoc that MENTIONS the command runs nothing."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "cat <<'EOF'\ngit push --force origin HEAD\nEOF"


def other_subcommand_case(path, bare):
    """A different git subcommand carrying a `--force`-shaped token."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git pull --force origin main"


def negated_force_case(path, bare):
    """`--force --no-force`: the last one wins, so this is not a force push."""
    _local_advances(path)
    return "git push --force --no-force origin"


def branches_alias_case(path, bare):
    """`git push -h`: `--branches` is "alias of --all", so it pushes a ref set
    that a single-branch reading would misdescribe."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push --branches origin"


def delete_refspec_case(path, bare):
    """`git push origin :main` is a deletion written as a refspec, not a push
    to a branch named `:main`."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push origin :main"


def wildcard_refspec_case(path, bare):
    """A wildcard refspec names no single branch; guessing one would send
    `ls-remote` at a ref the push never touches."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push origin refs/heads/*:refs/heads/*"


def unknown_cluster_case(path, bare):
    """An unrecognized short cluster might or might not consume the next word,
    so destination resolution declines rather than guessing."""
    _remote_advances(path, bare, keep_object=False)
    _local_advances(path)
    return "git push -Z origin HEAD"


def git_global_option_case(path, bare):
    """`git -C <dir> push` is still a push; the global option must be skipped
    before `push` is looked for."""
    _local_advances(path)
    return f"git -C {path} push --force origin HEAD"


# ---------------------------------------------------------------- cases

SHOULD_DENY = [
    ("D1", incident_case,
     "TEST CASE #1: bare `--force` over another agent's remote commit"),
    ("D2", bare_force_case, "bare `git push --force` with no refspec"),
    ("D3", short_f_case, "`-f` is the same flag spelled short"),
    ("D4", short_cluster_case, "`f` inside a `-fu` short cluster"),
    ("D5", force_plus_lease_case,
     "`--force --force-with-lease` -- `--force` disables the lease check"),
    ("D6", negated_dry_run_case,
     "`--dry-run --no-dry-run --force` really does transfer"),
    ("D7", force_with_value_cluster_case,
     "`-fo ci.skip` is force, and `o` eats the next word"),
    ("D8", git_global_option_case,
     "`git -C <dir> push --force` -- the global option is skipped first"),
    ("D9", warn_then_force_case,
     "a warn-worthy push chained BEFORE a bare force push must still deny"),
]

SHOULD_WARN = [
    ("W1", diverged_known_case,
     "remote tip not an ancestor of HEAD, its object present locally"),
    ("W2", diverged_unknown_case,
     "remote tip not an ancestor of HEAD, object absent locally"),
    ("W3", diverged_lease_case,
     "a leased force-push over a diverged remote still gets the reading"),
    ("W4", repo_option_case,
     "`--repo upstream` names the remote, not a value to skip"),
    ("W5", value_cluster_remote_case,
     "`-uo ci.skip upstream` -- `o` eats `ci.skip`, so `upstream` is the remote"),
    ("W7", explicit_current_branch_case,
     "`git push origin main` from `main` -- same branch, named explicitly"),
    ("W6", named_branch_case,
     "`git push origin feature-x` from `main` compares against local "
     "`feature-x`, not HEAD"),
    ("W8", cross_worktree_diverged_case,
     "`cd <worktree> && git push` reads HEAD where the push runs"),
    ("W9", dash_c_worktree_case,
     "`git -C <worktree> push` moves the push without a `cd`"),
    ("W10", payload_cwd_case,
     "the Bash call's own `cwd`, with no `cd` and no `-C` to reveal it"),
    ("W11", subshell_push_case,
     "`(cd <worktree> && git push)` -- the `cd` shares the subshell, so it "
     "does apply"),
    ("W12", brace_group_case,
     "`{ cd <worktree>; } && git push` -- a brace group does not fork, so "
     "the `cd` outlives it"),
    ("W13", spaced_worktree_case,
     "a worktree path carrying a space -- the emitted `git -C` must still "
     "parse as one argument"),
]

SHOULD_STAY_SILENT = [
    ("S1", leased_fast_forward_case,
     "`--force-with-lease --force-if-includes` is the remedy, never refused"),
    ("S2", override_case, "`ALLOW_FORCE_PUSH=1` clears the refusal"),
    ("S3", dry_run_case, "a `--dry-run` push transfers nothing"),
    ("S4", delete_case, "a `--delete` push is out of scope"),
    ("S5", fast_forward_case, "an ordinary fast-forward push"),
    ("S6", up_to_date_case, "remote tip already equals local HEAD"),
    ("S7", new_branch_case, "no remote ref of that name yet"),
    ("S8", quoted_mention_case, "a mention inside a quoted string"),
    ("S9", heredoc_mention_case, "a heredoc that mentions the command"),
    ("S10", other_subcommand_case, "a different git subcommand entirely"),
    ("S11", negated_force_case, "`--force --no-force` -- the last one wins"),
    ("S12", branches_alias_case, "`--branches` is an alias of `--all`"),
    ("S13", delete_refspec_case, "`origin :main` is a deletion refspec"),
    ("S14", wildcard_refspec_case, "a wildcard refspec names no one branch"),
    ("S15", unknown_cluster_case,
     "an unrecognized short cluster -- decline rather than guess a remote"),
    ("S16", named_branch_source_missing_case,
     "the pushed source ref does not resolve locally -- decline, don't fall "
     "back to HEAD"),
    ("S17", cross_worktree_fast_forward_case,
     "ai-config#2451: a fast-forward in the worktree the push runs from"),
    ("S18", indeterminate_cd_case,
     "`cd -` is indeterminate -- decline rather than read the session's own "
     "directory"),
    ("S19", git_dir_option_case,
     "`--git-dir`/`--work-tree` name a repository, not a directory -- "
     "decline"),
    ("S20", git_dir_env_case,
     "`GIT_DIR=`/`GIT_WORK_TREE=` redirect the same way as an env prefix"),
    ("S21", subshell_cd_case,
     "`(cd <worktree> && true) && git push` -- the `cd` dies at the `)`"),
    ("S22", sibling_subshell_cd_case,
     "`(cd <worktree> && true) && (git push)` -- a sibling subshell starts "
     "from the caller's directory, not its predecessor's"),
    ("S23", conditional_cd_case,
     "`if ...; then cd <worktree>; fi; git push` -- the branch is not taken, "
     "so the `cd` never runs"),
    ("S24", alternative_cd_case,
     "`cd <here> || cd <worktree>; git push` -- the alternative never runs"),
    ("S25", dash_c_unexpanded_case,
     "`git -C \"$WT\" push` -- an unexpanded variable names no directory"),
    ("S26", dash_c_tilde_case,
     "`git -C ~ncp-nosuchuser/wt push` -- a `~` is expanded, not joined on "
     "as a literal path component"),
    ("S27", branch_body_cd_case,
     "`if ...; then echo no; cd <worktree>; fi` -- a branch body of more than "
     "one command, whose `cd` carries no keyword"),
    ("S28", else_arm_cd_case,
     "`else true && cd <worktree>` -- an untaken arm whose `cd` follows the "
     "one separator the guard keeps"),
    ("S29", background_cd_case,
     "`cd <worktree> & git push` -- a backgrounded `cd` forks"),
    ("S30", pipeline_cd_case,
     "`cd <worktree> | cat; git push` -- a pipeline element forks too"),
    ("S31", pipeline_rhs_cd_case,
     "`echo x | cd <worktree>; git push` -- the same fork with the `|` before "
     "the `cd`"),
    ("S32", condition_cd_if_case,
     "`if cd <worktree>; then git push; fi` -- the `cd` is the condition, "
     "which shares an argv with the keyword"),
    ("S33", condition_cd_while_case,
     "`while cd <worktree>; do git push; done` -- the same shape under "
     "another keyword"),
    ("S34", background_cd_newline_case,
     "`cd <worktree> &` at the end of a line -- the newline joins the fork "
     "into one punctuation run"),
    ("S35", background_list_cd_case,
     "`cd <worktree> && true & git push` -- the `&` backgrounds the whole "
     "AND-OR list"),
    ("S36", alternative_cd_newline_case,
     "`true ||` at the end of a line -- the newline joins the alternative "
     "into one punctuation run"),
    ("S37", pipeline_rhs_cd_newline_case,
     "`echo x |` at the end of a line -- the same run with the fork operator "
     "before the `cd`"),
]


# The WARN text is behaviour, not decoration: it names the commit the guard
# compared against, and a reader reconciles against whatever it names. The
# suite used to assert only WARN-vs-DENY-vs-silent, which is how a message
# reading "your local HEAD" over `feature-x`'s tip shipped -- wrong in exactly
# the case the source-ref fix exists for.
#
# `(case_id) -> (must_appear, must_not_appear)`. A violation returns its own
# verdict string, so the mutation harness covers the label the same way it
# covers every other clause rather than needing a second pass.
# `(case_id) -> (must_all_appear, must_none_appear)`.
#
# The remediation COMMANDS are checked alongside the label, because they were
# the half that stayed wrong after the label was fixed: `WARN_TAIL` emitted
# `git merge origin/feature-x` unconditionally, which merges that branch into
# whatever is checked out. Advice is behaviour when a reader runs it.
LABEL_EXPECT = {
    "W6": (["your local `feature-x`",
            "git log --oneline feature-x..origin/feature-x",
            "git checkout feature-x"],
           ["your local HEAD", "HEAD..origin/"]),
    "W2": (["your local HEAD", "git log --oneline HEAD..origin/"],
           ["your local `", "git checkout "]),
    "W7": (["git log --oneline main..origin/main"],
           ["git checkout ", "you are not on the branch being pushed"]),
    # The commit SUBJECT is the directory-sensitive half here: `add shared.txt`
    # is what `local..tip` contains only when `local` was resolved in the
    # worktree the push runs from. Asserting the branch name alone would pass
    # on a reading taken in the session's own directory.
    #
    # W8, W9 and W11 additionally pin the DIRECTORY the reading was taken in.
    # The reader's shell is still where the Bash call started, so a bare
    # `git merge origin/peer` typed there merges into whatever is checked out
    # THERE -- the branch-into-itself merge of ai-config#2451 with the
    # directory axis substituted for the ref one. Asserting the bare form's
    # ABSENCE is the half that catches a regression: `read in` could be added
    # while the commands stayed unqualified.
    "W8": (["your local HEAD", "log --oneline HEAD..origin/peer",
            "add shared.txt", "read in `", "git -C "],
           ["git checkout ", "git log --oneline HEAD..origin/peer",
            "git fetch origin peer"]),
    "W9": (["your local HEAD", "log --oneline HEAD..origin/peer-c",
            "add shared.txt", "read in `", "git -C "],
           ["git checkout ", "git log --oneline HEAD..origin/peer-c",
            "git fetch origin peer-c"]),
    "W11": (["your local HEAD", "log --oneline HEAD..origin/peer-inner",
             "add shared.txt", "read in `", "git -C "],
            ["git checkout ", "git log --oneline HEAD..origin/peer-inner",
             "git fetch origin peer-inner"]),
    "W12": (["your local HEAD", "log --oneline HEAD..origin/peer-brace",
             "add shared.txt", "read in `", "git -C "],
            ["git checkout ", "git log --oneline HEAD..origin/peer-brace",
             "git fetch origin peer-brace"]),
    "W13": (["your local HEAD", "log --oneline HEAD..origin/peer-space",
             "add shared.txt", "read in `", "git -C "],
            ["git checkout ", "git log --oneline HEAD..origin/peer-space",
             "git fetch origin peer-space"]),
    # W10 is the opposite pin: the push runs in the call's OWN directory, so
    # naming it would be noise and `git -C` would be wrong.
    "W10": (["your local HEAD", "git log --oneline HEAD..origin/peer-payload",
             "add shared.txt"],
            ["git checkout ", "read in `", "git -C "]),
}


def _reconcile_runs(context, want_dir):
    """True when every `git -C ...` line in `context` names `want_dir`.

    Vacuously true when the case declared no directory, so this costs the
    other cases nothing. `comments=True` drops the trailing `# or rebase, ...`
    the reconcile block appends, which is a shell comment rather than an
    argument.
    """
    if want_dir is None:
        return True
    for line in context.splitlines():
        line = line.strip()
        if not line.startswith("git -C "):
            continue
        try:
            argv = shlex.split(line, comments=True)
        except ValueError:
            return False
        if len(argv) < 3 or argv[2] != want_dir:
            return False
    return True


def verdict(hook_path, repo, command, case_id=None, payload_cwd=None):
    # sys.executable, not a bare "python3": that guarantees the same
    # interpreter running this test, rather than whatever (if anything)
    # "python3" resolves to on the machine's PATH. ai-config#2098 flagged a
    # bare "python3" as a suspect for a Windows hang -- the Windows App
    # Execution Alias stub for python3.exe -- but that issue itself calls
    # the mechanism unverified, and the redirector's documented behavior
    # when invoked with an argument is to print an error and exit, not
    # block. Keep sys.executable for the guaranteed-correct-interpreter
    # reason; don't restate the blocking hypothesis as settled.
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(bash(command, payload_cwd)),
        capture_output=True, text=True, cwd=repo,
    )
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {command!r}\n"
                 f"{proc.stderr.strip()}")
    if not proc.stdout.strip():
        return "silent"
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: hook emitted non-JSON on stdout ({exc}): "
                 f"{proc.stdout!r}")
    hso = out.get("hookSpecificOutput") or {}
    decision = hso.get("permissionDecision")
    if decision == "allow":
        sys.exit("FATAL: hook emitted permissionDecision=allow, which would "
                 "BYPASS the normal permission prompt for every push")
    if decision == "deny":
        return "DENY"
    context = hso.get("additionalContext")
    if not context:
        return "silent"
    want, unwanted = LABEL_EXPECT.get(case_id, ([], []))
    if any(w not in context for w in want) or any(u in context for u in unwanted):
        return "WARN-WRONGLABEL"
    if not _reconcile_runs(context, ROUNDTRIP.get(case_id)):
        return "WARN-UNRUNNABLE"
    return "WARN"


# Fixture repos are built ONCE and reused across every hook variant.
#
# This is not a shortcut: the guard is read-only by construction (`ls-remote`,
# `rev-parse`, `merge-base`, `cat-file`, `log`), so no variant can leave a
# fixture in a state a later variant would see. Rebuilding per variant cost one
# repo-plus-bare-remote PAIR per case and per mutation clause; building once
# costs one pair per case and loses nothing.
_BUILT = {}


def build_all(cases):
    """Build every fixture. A builder returns its command, or that command
    paired with the `cwd` the Bash payload should carry -- which is how the
    tool call's own directory is exercised separately from the hook process's.
    """
    for case_id, builder in cases.items():
        path, bare = _new_repo()
        built = builder(path, bare)
        command, payload_cwd = built if isinstance(built, tuple) else (built,
                                                                       None)
        _BUILT[case_id] = (path, command, payload_cwd)


def build_and_verdict(hook_path, case_id):
    path, command, payload_cwd = _BUILT[case_id]
    return verdict(hook_path, path, command, case_id, payload_cwd)


if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would "
             "otherwise read as 'silent' on every case and print a perfect "
             "pass")

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()

EXPECTED = {case_id: "DENY" for case_id, *_ in SHOULD_DENY}
EXPECTED.update({case_id: "WARN" for case_id, *_ in SHOULD_WARN})
EXPECTED.update({case_id: "silent" for case_id, *_ in SHOULD_STAY_SILENT})
CASES = {case_id: builder for case_id, builder, _ in
         SHOULD_DENY + SHOULD_WARN + SHOULD_STAY_SILENT}

build_all(CASES)

wrong = 0
for label, group, want in (("should DENY", SHOULD_DENY, "DENY"),
                           ("should WARN", SHOULD_WARN, "WARN"),
                           ("should STAY SILENT", SHOULD_STAY_SILENT,
                            "silent")):
    print(f"{label}:")
    for case_id, builder, desc in group:
        got = build_and_verdict(HOOK, case_id)
        wrong += got != want
        print(f"  {got:<6} {case_id:<4} {desc}")
    print()

total = len(CASES)
print(f"{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness

MUTATIONS = {
    "force_deny": (
        "a force push is refused",
        [('        if flags["force"] and not flags["dry_run"] and not override:\n'
          '            return "deny", DENY.format(segment=" ".join(argv))',
          "        pass")],
        {"D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"},
    ),
    "force_ignores_lease": (
        "the refusal does NOT consult the lease -- `--force` disables it",
        [('        if flags["force"] and not flags["dry_run"] and not override:',
          '        if flags["force"] and not flags["lease"] '
          'and not flags["dry_run"] and not override:')],
        {"D5"},
    ),
    "force_token_exact": (
        "`--force` matches as an exact long option, so `--force-with-lease` "
        "is not one",
        [('            if base == "--force-with-lease" '
          'or name.startswith("--force-with-lease"):\n'
          '                flags["lease"] = not negated\n'
          "                continue",
          '            if base == "--force-with-lease" '
          'or name.startswith("--force-with-lease"):\n'
          '                flags["lease"] = not negated\n'
          '                flags["force"] = not negated\n'
          "                continue")],
        {"S1", "W3"},
    ),
    "negation_aware": (
        "`--no-*` forms are honoured in order, so a later one wins",
        [("                flags[LONG_FLAG[base]] = not negated",
          "                flags[LONG_FLAG[base]] = True")],
        {"D6", "S11"},
    ),
    "short_value_letter": (
        "a value-taking letter in a short cluster (`-o`) eats the next word",
        [("                if pos == len(letters) - 1:\n"
          "                    i += 1  # its value is the next word, "
          "not the remote\n"
          "                break",
          "                break")],
        {"W5"},
    ),
    "repo_option": (
        "`--repo <repository>` supplies the remote",
        [('                if base == "--repo" and not negated:\n'
          "                    repo_opt = value",
          "                pass")],
        {"W4"},
    ),
    "override": (
        "a real `ALLOW_FORCE_PUSH=1` assignment clears the refusal",
        [('        if flags["force"] and not flags["dry_run"] '
          "and not override:",
          '        if flags["force"] and not flags["dry_run"]:')],
        {"S2"},
    ),
    "out_of_scope_gate": (
        "dry-run, delete, ref-set, and unparsed pushes get no reading",
        [('        if flags["dry_run"] or flags["delete"] or flags["refset"] '
          "or not ok:\n            continue",
          "        pass")],
        # S3 flips too: the deny path already excludes `--dry-run` on its own,
        # so without this gate a dry run over a diverged remote takes the
        # reading and warns. The harness caught the set being under-declared.
        {"S3", "S4", "S12", "S15"},
    ),
    "branches_is_all": (
        "`--branches` is an alias of `--all`",
        [('    "--branches": "refset",   # `git push -h`: "alias of --all"', "")],
        {"S12"},
    ),
    "local_is_the_source_ref": (
        "the local side of the comparison is the ref being PUSHED, not HEAD",
        [('        local = _git(["rev-parse", "--verify", "--quiet", '
          'source + "^{commit}"],\n'
          "                     timeout=5, cwd=cwd)",
          '        local = _git(["rev-parse", "HEAD"], timeout=5, cwd=cwd)')],
        # Also covers the deletion and wildcard refspecs: this one read is
        # what declines them, so reverting it makes both warn about the
        # currently checked-out branch instead.
        {"W6", "S16", "S13", "S14"},
    ),
    "deny_scans_every_command": (
        "the refusal pass examines every simple command, not just the first",
        [("    for argv, flags, _pos, _repo, _ok, override, _cwd in parsed:\n"
          '        if flags["force"] and not flags["dry_run"] '
          "and not override:",
          "    for argv, flags, _pos, _repo, _ok, override, _cwd in "
          "parsed[:1]:\n"
          '        if flags["force"] and not flags["dry_run"] '
          "and not override:")],
        {"D9"},
    ),
    "on_source_is_not_the_HEAD_sentinel": (
        "whether you are on the pushed branch is decided by comparing refs, "
        "not by testing the `HEAD` sentinel",
        [("        if on_source:", '        if source == "HEAD":')],
        {"W7"},
    ),
    "reconcile_uses_the_pushed_ref": (
        "the remediation commands operate on the ref being pushed",
        [("        if on_source:\n"
          '            reconcile = (f"    {gitc}fetch origin {branch}\\n"',
          "        if True:\n"
          '            reconcile = (f"    {gitc}fetch origin {branch}\\n"')],
        {"W6"},
    ),
    "warning_names_the_pushed_ref": (
        "the WARN text names the ref actually compared, not always HEAD",
        [('        srclabel = ("your local HEAD" if source == "HEAD"\n'
          '                    else f"your local `{source}`")',
          '        srclabel = "your local HEAD"')],
        {"W6"},
    ),
    "ancestor_gate": (
        "a remote tip that IS an ancestor of HEAD is a fast-forward and "
        "warns about nothing",
        [("        if anc.returncode == 0:\n            continue  # plain "
          "fast-forward; nothing at risk",
          "        if False:\n            continue")],
        # S1, S2 and S11 are fast-forward pushes too, so removing the gate
        # makes all of them warn -- the harness caught this set being
        # under-declared the first time. S17 joins them: its silence is a
        # fast-forward READ IN THE RIGHT DIRECTORY, so it flips here as well
        # as under the `cd` clause below.
        {"S1", "S2", "S5", "S11", "S17"},
    ),
    "subcommand": (
        "only `git push` matches, not another git subcommand",
        [('    if i >= len(argv) or argv[i] != "push":\n'
          "        return None, False, ()",
          "    pass")],
        {"S10"},
    ),
    "cd_moves_the_push": (
        "a `cd` earlier in the compound command moves the directory the push "
        "runs in",
        [("        if head and head[0] in CD_WORDS:\n"
          "            if region or sep in BRANCH_SEPS or after in "
          "FORK_SEPS:\n"
          "                dirs[scope] = None\n"
          "            else:\n"
          "                dirs[scope] = _resolve_cd(head, dirs[scope])\n"
          "            continue",
          "        if head and head[0] in CD_WORDS:\n"
          "            continue")],
        # S23, S24 and S27-S31 do NOT flip: their `cd` is declined rather than
        # applied, and a `cd` that is not applied at all leaves the same
        # directory.
        {"S17", "S18", "W8", "W11", "W12", "W13"},
    ),
    "branch_region_declines": (
        "a compound statement opens a REGION, so every `cd` in its body is "
        "declined rather than only the one carrying the keyword",
        # Anchored on the region's USE rather than on `BLOCK_OPEN`: the
        # condition test below sits inside the same `head[0] in BLOCK_OPEN`
        # arm, so emptying that set would revert two clauses at once and
        # report a flip set neither of them owns.
        [("            if region or sep in BRANCH_SEPS or after in "
          "FORK_SEPS:",
          "            if sep in BRANCH_SEPS or after in FORK_SEPS:")],
        # S27 and S28 are the shapes a keyword-only test missed: their `cd` is
        # not the body's first command, so no keyword reaches it. S32 and S33
        # do NOT flip: their `cd` is the condition rather than the body, and
        # a separate clause declines it.
        {"S23", "S27", "S28"},
    ),
    "alternative_cd_declines": (
        "a `cd` the shell may never reach -- an `||` alternative, or a "
        "pipeline element -- makes the directory indeterminate rather than "
        "moving it",
        [('BRANCH_SEPS = {"||", "|"}', "BRANCH_SEPS = set()")],
        {"S24", "S31", "S36", "S37"},
    ),
    "forked_cd_declines": (
        "a `cd` the shell forks into a subshell of its own -- backgrounded, "
        "or piped -- moves no directory the push can see",
        [('FORK_SEPS = {"&", "|"}', "FORK_SEPS = set()")],
        # S34 and S35 are the same decline reached by two shapes whose `&`
        # this clause could not see until it was recovered: one written at the
        # end of a line, and one backgrounding the whole AND-OR list.
        {"S29", "S30", "S34", "S35"},
    ),
    "separator_is_tracked": (
        "each simple command carries the operator before it, which is what "
        "tells an `||` alternative from an `&&` chain",
        [("                        sep = _next_sep(sep, ch)",
          "                        pass")],
        # S23, S27 and S28 cannot see this: their decline comes from the
        # region an `if` opened, which no separator reports.
        {"S24", "S31", "S36", "S37"},
    ),
    "separator_reads_the_first_operator": (
        "the leading punctuation run reports the operator it STARTS with, so "
        "the `;` a newline leaves behind cannot overwrite the `||` or `|` "
        "before it",
        [("                    if sep and ch != sep[-1]:\n"
          "                        frozen = True\n"
          "                    else:\n"
          "                        sep = _next_sep(sep, ch)",
          "                    sep = _next_sep(sep, ch)")],
        # Only the end-of-line spelling can see this: S24 and S31 write the
        # operator and the `cd` on one line, so each run is one operator --
        # `||` and `|` -- which folding leaves unchanged.
        {"S36", "S37"},
    ),
    "trailing_separator_is_tracked": (
        "each simple command also carries the operator after it, which is the "
        "only side a fork is visible from",
        # Anchored on the assignment alone rather than on the loop around it:
        # the loop now also carries the first-operator break, and blanking the
        # pair would revert two clauses at once.
        [("                trailing = _next_sep(trailing, ch)",
          "                pass")],
        {"S29", "S30", "S34", "S35"},
    ),
    "trailing_separator_reads_the_first_operator": (
        "a punctuation run reports the operator it STARTS with, so the `;` a "
        "newline leaves behind cannot overwrite the `&` before it",
        [("                if trailing and ch != trailing[-1]:\n"
          "                    break\n", "")],
        # Only the end-of-line spelling can see this: S29 writes the `&` and
        # the next command on one line, so its run is a single character.
        {"S34"},
    ),
    "background_forks_the_whole_list": (
        "a `&` backgrounds the AND-OR list before it, so the trailing "
        "operator propagates backwards across `&&` and `||`",
        [("        prev, here = cmds[i - 1], cmds[i]\n"
          '        if here[3] == "&" and prev[3] in ("&&", "||") '
          "and prev[0] == here[0]:\n"
          '            cmds[i - 1] = (prev[0], prev[1], prev[2], "&")',
          "        pass")],
        {"S35"},
    ),
    "condition_cd_declines": (
        "a `cd` in a compound statement's own condition is declined, though "
        "it shares an argv with the keyword and the region never sees it",
        [("            if skip < len(cond) and cond[skip] in CD_WORDS:\n"
          "                dirs[scope] = None",
          "            if False:\n"
          "                dirs[scope] = None")],
        {"S32", "S33"},
    ),
    "unexpanded_value_declines": (
        "a `$name` or a command substitution names no directory, so it is "
        "declined rather than joined on as a literal path component",
        [('    if "$" in target or "`" in target:\n'
          "        return None  # unexpanded; resolving it means simulating "
          "the shell",
          "    pass")],
        {"S25"},
    ),
    "tilde_is_expanded": (
        "a leading `~` is expanded the way the shell would have expanded it, "
        "and an unknown user declines",
        [('    if target.startswith("~"):\n'
          "        target = os.path.expanduser(target)\n"
          '        if target.startswith("~"):\n'
          "            return None  # an unknown user",
          "    pass")],
        {"S26"},
    ),
    "indeterminate_cd_declines": (
        "a `cd` that cannot be resolved declines the reading rather than "
        "falling back to the hook's own directory",
        [("        if cwd is None:\n            continue",
          "        if cwd is None:\n            cwd = os.getcwd()")],
        # S19 and S20 reach the same gate by a different route: their
        # directory is indeterminate because the REPOSITORY was redirected,
        # not because a `cd` was. S32 and S33 reach it because a `cd` in a
        # condition is declined without being resolved.
        {"S18", "S19", "S20", "S32", "S33"},
    ),
    "dash_c_moves_the_push": (
        "the push's own `-C` values are read out, not skipped as option noise",
        [('            if argv[i] == "-C" and i + 1 < len(argv):\n'
          "                cdirs.append(argv[i + 1])\n"
          "            i += 2",
          "            i += 2")],
        {"W9"},
    ),
    "base_is_the_payload_cwd": (
        "the directory a push starts in is the Bash call's own `cwd`, not the "
        "hook process's",
        [('        verdict = evaluate(command, payload.get("cwd"))',
          "        verdict = evaluate(command)")],
        {"W10"},
    ),
    "subshell_scopes_cd": (
        "a subshell's parentheses are tracked, so a `cd` inside one does not "
        "leak onto a push outside it",
        # Anchored on the parenthesis clause alone, NOT on the `for ch in t`
        # loop around it: that loop also derives the separator each simple
        # command carries, and blanking it would revert two clauses at once
        # and report a flip set neither of them owns.
        [('                if ch == "(":\n'
          "                    opened += 1\n"
          "                    scopes.append(scopes[-1] + (opened,))\n"
          '                elif ch == ")" and len(scopes) > 1:\n'
          "                    scopes.pop()",
          "                pass")],
        # W11's `cd` shares the subshell with its push, so it still applies
        # when every command reads as root -- which is what makes the pair a
        # two-sided pin rather than one case asserting silence.
        {"S21", "S22"},
    ),
    "subshells_have_identities": (
        "a subshell is identified, not merely counted, so a `cd` in one does "
        "not leak into its next SIBLING",
        [("                    opened += 1\n"
          "                    scopes.append(scopes[-1] + (opened,))",
          "                    scopes.append(scopes[-1] + (len(scopes),))")],
        # S21's push sits outside the parentheses, so a depth-shaped label
        # leaves it correct; only the sibling shape can see the difference.
        {"S22"},
    ),
    "brace_group_is_transparent": (
        "a brace group's punctuation is stripped as a lead word, so the `cd` "
        "inside one is visible and outlives the closing brace",
        [('              "{", "}"}', "              }")],
        {"W12"},
    ),
    "remediation_quotes_the_directory": (
        "the directory is shell-quoted, so a `git -C` line naming a path with "
        "a space is still runnable",
        [("        gitc = f\"git -C {shlex.quote(cwd)} \" if moved else "
          '"git "',
          '        gitc = f"git -C {cwd} " if moved else "git "')],
        {"W13"},
    ),
    "git_dir_option_declines": (
        "`--git-dir`/`--work-tree` name a repository, so the reading is "
        "declined rather than taken in the session's",
        [('GIT_REPO_OPTS = {"--git-dir", "--work-tree"}',
          "GIT_REPO_OPTS = set()")],
        {"S19"},
    ),
    "git_dir_env_declines": (
        "the `GIT_DIR=`/`GIT_WORK_TREE=` env spellings decline the same way",
        [('GIT_ENV_REDIRECT = ("GIT_DIR=", "GIT_WORK_TREE=")',
          "GIT_ENV_REDIRECT = ()")],
        {"S20"},
    ),
    "warning_names_the_directory": (
        "a reading taken somewhere other than the call's own directory says "
        "where, and qualifies every remediation command with `git -C`",
        [("        moved = os.path.realpath(cwd) != os.path.realpath(base)",
          "        moved = False")],
        {"W8", "W9", "W11", "W12", "W13"},
    ),
    "heredoc_blanking": (
        "a heredoc body is blanked before parsing, so a mention inside one "
        "is not an invocation",
        [('    cmd = RX_HEREDOC.sub("<<", cmd)', "    pass")],
        {"S9"},
    ),
}

print("\nmutation tests (revert one clause, see which cases flip):")
mutation_wrong = 0
with tempfile.TemporaryDirectory() as tmp:
    for clause, (statement, edits, expected_flips) in MUTATIONS.items():
        mutated = SOURCE
        for find, replace in edits:
            if mutated.count(find) != 1:
                sys.exit(f"FATAL: clause {clause}'s anchor is not present "
                         f"exactly once in {HOOK} (found "
                         f"{mutated.count(find)}). The mutation harness is "
                         "measuring nothing; re-derive the anchor.\n---\n"
                         f"{find}\n---")
            mutated = mutated.replace(find, replace)

        path = os.path.join(tmp, f"mutant-{clause}.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(mutated)

        # Re-run a case ONCE before calling it flipped.
        #
        # The guard fails open on any subprocess timeout, so a slow
        # `ls-remote` under load yields "silent" and reads as a mutation
        # flip. Observed once here: `negation_aware` reported flipping W3,
        # whose flags are provably identical under that mutant, and a clean
        # re-run showed 14/14. A genuine flip is deterministic and survives
        # the retry, so this removes the flake without masking a regression.
        flipped = {cid for cid in CASES
                   if build_and_verdict(path, cid) != EXPECTED[cid]
                   and build_and_verdict(path, cid) != EXPECTED[cid]}

        ok = flipped == expected_flips
        mutation_wrong += not ok
        if not flipped and expected_flips:
            note = "NOTHING FLIPPED -- this clause is untested"
        elif ok:
            note = ("flipped " + ", ".join(sorted(flipped))
                    if flipped else "flipped nothing, as declared")
        else:
            note = (f"flipped {sorted(flipped)}, expected "
                    f"{sorted(expected_flips)}")
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<22} {statement}\n"
              f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under reversion")

for d in _TMPDIRS:
    shutil.rmtree(d, ignore_errors=True)

sys.exit(1 if (wrong or mutation_wrong) else 0)
