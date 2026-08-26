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


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


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
}


def verdict(hook_path, repo, command, case_id=None):
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
        [sys.executable, hook_path], input=json.dumps(bash(command)),
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
    return "WARN"


# Fixture repos are built ONCE and reused across every hook variant.
#
# This is not a shortcut: the guard is read-only by construction (`ls-remote`,
# `rev-parse`, `merge-base`, `cat-file`, `log`), so no variant can leave a
# fixture in a state a later variant would see. Rebuilding per variant cost
# 32 x 17 = 544 repo-plus-bare-remote constructions and pushed the suite past
# two minutes; building once costs 32 and loses nothing.
_BUILT = {}


def build_all(cases):
    for case_id, builder in cases.items():
        path, bare = _new_repo()
        _BUILT[case_id] = (path, builder(path, bare))


def build_and_verdict(hook_path, case_id):
    path, command = _BUILT[case_id]
    return verdict(hook_path, path, command, case_id)


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
          "                     timeout=5)",
          '        local = _git(["rev-parse", "HEAD"], timeout=5)')],
        # Also covers the deletion and wildcard refspecs: this one read is
        # what declines them, so reverting it makes both warn about the
        # currently checked-out branch instead.
        {"W6", "S16", "S13", "S14"},
    ),
    "deny_scans_every_command": (
        "the refusal pass examines every simple command, not just the first",
        [("    for argv, flags, _pos, _repo, _ok, override in parsed:\n"
          '        if flags["force"] and not flags["dry_run"] '
          "and not override:",
          "    for argv, flags, _pos, _repo, _ok, override in parsed[:1]:\n"
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
          '            reconcile = (f"    git fetch origin {branch}\\n"',
          "        if True:\n"
          '            reconcile = (f"    git fetch origin {branch}\\n"')],
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
        # under-declared the first time.
        {"S1", "S2", "S5", "S11"},
    ),
    "subcommand": (
        "only `git push` matches, not another git subcommand",
        [('    if i >= len(argv) or argv[i] != "push":\n'
          "        return None, False",
          "    pass")],
        {"S10"},
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
