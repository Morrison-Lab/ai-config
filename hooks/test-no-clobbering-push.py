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


# ---------------------------------------------------------------- cases

SHOULD_DENY = [
    ("D1", incident_case,
     "TEST CASE #1: bare `--force` over another agent's remote commit"),
    ("D2", bare_force_case, "bare `git push --force` with no refspec"),
    ("D3", short_f_case, "`-f` is the same flag spelled short"),
    ("D4", short_cluster_case, "`f` inside a `-fu` short cluster"),
]

SHOULD_WARN = [
    ("W1", diverged_known_case,
     "remote tip not an ancestor of HEAD, its object present locally"),
    ("W2", diverged_unknown_case,
     "remote tip not an ancestor of HEAD, object absent locally"),
    ("W3", diverged_lease_case,
     "a leased force-push over a diverged remote still gets the reading"),
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
]


def verdict(hook_path, repo, command):
    proc = subprocess.run(
        ["python3", hook_path], input=json.dumps(bash(command)),
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
    return "WARN" if hso.get("additionalContext") else "silent"


def build_and_verdict(hook_path, builder):
    path, bare = _new_repo()
    command = builder(path, bare)
    return verdict(hook_path, path, command)


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

wrong = 0
for label, group, want in (("should DENY", SHOULD_DENY, "DENY"),
                           ("should WARN", SHOULD_WARN, "WARN"),
                           ("should STAY SILENT", SHOULD_STAY_SILENT,
                            "silent")):
    print(f"{label}:")
    for case_id, builder, desc in group:
        got = build_and_verdict(HOOK, builder)
        wrong += got != want
        print(f"  {got:<6} {case_id:<4} {desc}")
    print()

total = len(CASES)
print(f"{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness

MUTATIONS = {
    "force_deny": (
        "a bare force push is refused",
        [('        if force and not lease and not override:\n'
          '            return "deny", DENY.format(segment=segment)',
          "        pass")],
        {"D1", "D2", "D3", "D4"},
    ),
    "force_token_exact": (
        "`--force` matches as an exact token, so `--force-with-lease` is not "
        "a force flag",
        [('        if tok == "--force" or tok == "-f":',
          '        if tok.startswith("--force") or tok == "-f":')],
        {"S1", "W3"},
    ),
    "override": (
        "a real `ALLOW_FORCE_PUSH=1` assignment clears the refusal",
        [("        if force and not lease and not override:",
          "        if force and not lease:")],
        {"S2"},
    ),
    "dry_delete_refset": (
        "dry-run, delete, and ref-set pushes are out of scope",
        [("        if dry or delete or refset:\n            continue",
          "        pass")],
        {"S3", "S4"},
    ),
    "ancestor_gate": (
        "a remote tip that IS an ancestor of HEAD is a fast-forward and "
        "warns about nothing",
        [("        if anc.returncode == 0:\n            continue  # plain "
          "fast-forward; nothing at risk",
          "        if False:\n            continue")],
        # S1 and S2 are fast-forward pushes too, so removing the gate makes
        # all three warn -- the harness caught this set being under-declared.
        {"S1", "S2", "S5"},
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

        flipped = {case_id for case_id, builder in CASES.items()
                   if build_and_verdict(path, builder) != EXPECTED[case_id]}

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
