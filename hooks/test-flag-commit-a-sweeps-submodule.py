"""Test the flag-commit-a-sweeps-submodule guard, case by case, with a
mutation harness.

Test case W1 is the 2026-10-15 incident (Morrison-Lab/lds#1026) in its own
shape: a repo with a submodule pinned at one commit, the submodule's checkout
moved to another, and a tracked `CLAUDE.md` edited beside it, then
`git commit -am "..."`.

Like `test-flag-add-a-outside-pathspec.py`, the guard reads LIVE repository
state, so each case builds a real scratch repo (with a real submodule, added
over the file protocol) and runs the hook with that repo, or a directory
beside it, as cwd. The second half reverts one clause of the hook at a time
and checks that exactly the cases declared for it flip. A clause that no
case can observe declares an EMPTY set rather than faking coverage.

Run:  python3 hooks/test-flag-commit-a-sweeps-submodule.py \\
          hooks/flag-commit-a-sweeps-submodule.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1])
ELSEWHERE = tempfile.mkdtemp()  # a cwd that is not the repo under test
SHELLCMD_LIB = os.path.join(
    os.path.dirname(os.path.dirname(HOOK)), "scripts", "lib")


def _run(cwd, *args):
    return subprocess.run(
        ["git", "-c", "protocol.file.allow=always", *args], cwd=cwd,
        capture_output=True, text=True, check=True)


def _identity(path):
    _run(path, "config", "user.email", "t@t.com")
    _run(path, "config", "user.name", "t")


def _write(path, *parts, content="x\n"):
    full = os.path.join(path, *parts)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(content)


def _repo(build):
    path = tempfile.mkdtemp()
    _run(path, "init", "-q")
    _identity(path)
    build(path)
    return path


def _base_with_submodule(path):
    """CLAUDE.md plus a submodule `mod` pinned at its first commit."""
    src = os.path.join(path, ".subsrc")
    os.makedirs(src)
    _run(src, "init", "-q")
    _identity(src)
    _write(src, "lib.txt", content="v1\n")
    _run(src, "add", ".")
    _run(src, "commit", "-qm", "sub v1")
    _write(path, "CLAUDE.md", content="v1\n")
    _run(path, "submodule", "add", "-q", src, "mod")
    _run(path, "add", "CLAUDE.md")
    _run(path, "commit", "-qm", "init")
    _identity(os.path.join(path, "mod"))


def _move_submodule_head(path):
    mod = os.path.join(path, "mod")
    _write(mod, "lib.txt", content="v2\n")
    _run(mod, "commit", "-qam", "sub v2")


def moved_pin_repo(path):
    """The incident: pin moved, plus an intended CLAUDE.md edit."""
    _base_with_submodule(path)
    _move_submodule_head(path)
    _write(path, "CLAUDE.md", content="v2\n")


def moved_pin_only_repo(path):
    _base_with_submodule(path)
    _move_submodule_head(path)


def dirty_content_repo(path):
    """Submodule worktree edited, HEAD unchanged: gitlink is NOT modified."""
    _base_with_submodule(path)
    _write(path, "mod", "lib.txt", content="edited, uncommitted\n")
    _write(path, "CLAUDE.md", content="v2\n")


def clean_submodule_repo(path):
    _base_with_submodule(path)
    _write(path, "CLAUDE.md", content="v2\n")


def staged_then_moved_repo(path):
    """`MM`: a pin bump staged, then the submodule moved on again."""
    _base_with_submodule(path)
    _move_submodule_head(path)
    _run(path, "add", "mod")
    mod = os.path.join(path, "mod")
    _write(mod, "lib.txt", content="v3\n")
    _run(mod, "commit", "-qam", "sub v3")


def staged_bump_repo(path):
    """Pin move already staged on purpose: nothing left for -a to sweep."""
    _base_with_submodule(path)
    _move_submodule_head(path)
    _run(path, "add", "mod")


MSG = '"fix"'
# (id, builder, command, description). A command may use {repo}.
SHOULD_WARN = [
    ("W1", moved_pin_repo, f"git commit -am {MSG}",
     "TEST CASE 1: the incident, `git commit -am`, pin moved + CLAUDE.md edit"),
    ("W2", moved_pin_only_repo, f"git commit -a -m {MSG}", "separate -a -m"),
    ("W3", moved_pin_only_repo, f"git commit --all -m {MSG}", "long form --all"),
    ("W4", moved_pin_only_repo, "git add -u", "git add -u"),
    ("W5", moved_pin_only_repo, "git add --update", "git add --update"),
    ("W6", moved_pin_only_repo, "git -C {repo} commit -am 'fix'",
     "git -C <dir> form, cwd elsewhere"),
    ("W7", moved_pin_only_repo, "git add -u mod", "pathspec names the submodule"),
    ("W8", moved_pin_only_repo, f"git commit -sam {MSG}",
     "combined cluster -sam (a after another flag)"),
    ("W9", moved_pin_only_repo, "cd {repo} && git commit -am 'fix'",
     "an earlier `cd` in the same command sets the target"),
    ("W10", moved_pin_only_repo, f"git commit -m {MSG} -a", "-a after -m"),
    ("W11", moved_pin_only_repo, f"env FOO=1 git commit -am {MSG}",
     "env assignment and lead word skipped"),
    ("W12", moved_pin_only_repo, f"git -c user.name=x commit -am {MSG}",
     "global -c k=v option skipped"),
    ("W13", moved_pin_only_repo, "git add -u .", "pathspec `.` covers it"),
    ("W14", moved_pin_only_repo, f"git add -u && git commit -m {MSG}",
     "git add -u earlier in a chain"),
    ("W15", moved_pin_only_repo,
     "git commit -F - <<EOF\nmsg\nEOF\ngit add -u",
     "a real command AFTER a heredoc (reviewer repro on #4537)"),
    ("W16", moved_pin_only_repo,
     "cat <<'EOF' > note.txt\ngit add -u\nEOF\ngit commit -am 'fix'",
     "heredoc body mentions the command, then a real one follows"),
    ("W17", moved_pin_only_repo, f"git commit -S -a -m {MSG}",
     "-S takes an optional ATTACHED value; it must not eat the next token"),
    ("W18", moved_pin_only_repo, f"git commit -u -a -m {MSG}",
     "-u takes an optional attached value, like -S"),
    ("W20", moved_pin_only_repo, "git add -u :/",
     "magic pathspec is not evaluated: warn, not silent"),
    ("W21", moved_pin_only_repo, "git add -u 'mod*'",
     "glob pathspec is not evaluated: warn, not silent"),
    ("W22", moved_pin_only_repo, "git add -u '.\\mod'",
     "Windows path separator is normalised"),
    ("W23", staged_then_moved_repo, f"git commit -am {MSG}",
     "MM: staged bump, then the submodule moved again"),
]
SHOULD_STAY_SILENT = [
    ("S1", moved_pin_repo, f"git commit -m {MSG}", "no -a: nothing swept"),
    ("S2", moved_pin_repo, "git add CLAUDE.md", "explicit path add"),
    ("S3", dirty_content_repo, f"git commit -am {MSG}",
     "submodule has dirty CONTENT only; the gitlink is unchanged"),
    ("S4", clean_submodule_repo, f"git commit -am {MSG}",
     "submodule at its pinned commit"),
    ("S5", moved_pin_only_repo, "git commit -ma",
     "-ma is message `a`, not -a"),
    ("S6", moved_pin_repo, "git add -u CLAUDE.md",
     "pathspec excludes the submodule"),
    ("S7", moved_pin_only_repo, "echo 'git commit -am x' > note.txt",
     "mention inside a quoted string"),
    ("S8", moved_pin_only_repo, "cat <<'EOF' > note.txt\ngit add -u\nEOF\n",
     "heredoc that mentions the command"),
    ("S9", moved_pin_only_repo, "git -C /nonexistent-dir-xyz commit -am 'fix'",
     "target directory missing: fails open"),
    ("S10", moved_pin_only_repo, "git commit -m -a",
     "`-a` is the VALUE of -m here"),
    ("S11", staged_bump_repo, f"git commit -am {MSG}",
     "pin bump already staged on purpose"),
    ("S12", moved_pin_only_repo, "git status", "different subcommand"),
    ("S13", moved_pin_only_repo, f"git commit -m {MSG} -- CLAUDE.md",
     "commit with paths and no -a"),
    ("S14", moved_pin_only_repo, f"git commit -uall -m {MSG}",
     "-uall is -u with value `all`, not a -a flag"),
    ("S15", moved_pin_only_repo,
     f"git --git-dir=.git --work-tree=. commit -am {MSG}",
     "--git-dir/--work-tree name another repo: documented silent case"),
    ("S16", moved_pin_only_repo, f"git --git-dir .git commit -am {MSG}",
     "separated --git-dir: documented silent case"),
    ("S17", moved_pin_only_repo, f"cd ~ && git commit -am {MSG}",
     "`cd ~` is not expanded: documented silent case"),
    ("S18", moved_pin_only_repo, f"cd $SOME_DIR && git commit -am {MSG}",
     "`cd $VAR` is not expanded: documented silent case"),
    ("S19", moved_pin_only_repo, f"@budget0 git commit -am {MSG}",
     "git deadline already spent: fail open, not a late kill"),
]


def verdict(hook_path, repo, command, want_text=False):
    cwd = ELSEWHERE if "{repo}" in command else repo
    command = command.replace("{repo}", repo)
    env = {**os.environ, "PYTHONPATH": SHELLCMD_LIB}
    if command.startswith("@budget0 "):  # an already-spent git deadline
        command = command[len("@budget0 "):]
        env["FLAG_COMMIT_A_BUDGET_S"] = "0"
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True, text=True, cwd=cwd,
        # Mutants are written to a temp dir, where the hook's own
        # `scripts/lib` lookup (relative to its file) finds nothing.
        env=env,
    )
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {command!r}\n"
                 f"{proc.stderr.strip()}")
    if not proc.stdout.strip():
        return "silent"
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: non-JSON stdout ({exc}): {proc.stdout!r}")
    hso = out.get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        sys.exit("FATAL: hook emitted a permissionDecision; it must only add "
                 "context")
    if not (hso.get("additionalContext") and out.get("systemMessage")):
        return "silent"
    return ("WARN", out) if want_text else "WARN"


_REPOS = {}


def build_and_verdict(hook_path, builder, command):
    """The hook never mutates a repo, so each fixture is built once."""
    if builder not in _REPOS:
        _REPOS[builder] = _repo(builder)
    return verdict(hook_path, _REPOS[builder], command)


if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}; a missing file would read as "
             "'silent' on every case")
with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()

EXPECTED = {c[0]: "WARN" for c in SHOULD_WARN}
EXPECTED.update({c[0]: "silent" for c in SHOULD_STAY_SILENT})
CASES = {c[0]: (c[1], c[2]) for c in SHOULD_WARN + SHOULD_STAY_SILENT}

wrong = 0
print("should WARN:")
for case_id, builder, command, desc in SHOULD_WARN:
    got = build_and_verdict(HOOK, builder, command)
    wrong += got != "WARN"
    print(f"  {got:<6} {case_id}  {desc}")
print("\nshould STAY SILENT:")
for case_id, builder, command, desc in SHOULD_STAY_SILENT:
    got = build_and_verdict(HOOK, builder, command)
    wrong += got != "silent"
    print(f"  {got:<6} {case_id}  {desc}")

# The message must name the submodule path and both commits.
repo = _repo(moved_pin_repo)
try:
    pinned = _run(repo, "ls-files", "-s", "mod").stdout.split()[1]
    head = _run(os.path.join(repo, "mod"), "rev-parse", "HEAD").stdout.strip()
    res = verdict(HOOK, repo, f"git commit -am {MSG}", want_text=True)
    text = json.dumps(res[1]) if isinstance(res, tuple) else ""
    for label, needle in (("submodule path", "mod:"), ("pinned sha", pinned[:7]),
                          ("checked-out sha", head[:7]),
                          ("suggestion", "git commit -- <paths>")):
        ok = needle in text
        wrong += not ok
        print(f"  {'ok  ' if ok else 'WRONG'} message names {label}")
    # `add -u` only stages: the message must say the NEXT commit moves it.
    res = verdict(HOOK, repo, "git add -u", want_text=True)
    text = json.dumps(res[1]) if isinstance(res, tuple) else ""
    for label, needle in (("next commit (additionalContext)", "the next commit"),
                          ("next commit (systemMessage)", "next commit would")):
        ok = needle in text
        wrong += not ok
        print(f"  {'ok  ' if ok else 'WRONG'} add -u message says {label}")
finally:
    shutil.rmtree(repo, ignore_errors=True)

total = len(CASES)
print(f"\n{total - wrong}/{total} cases (+6 message checks) correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

# ------------------------------------------------------------ mutation harness

MUTATIONS = {
    "M_long_all": (
        "`--all` is read as -a",
        [('            if a == "--all":\n                return True',
          '            if False:\n                return True')],
        {"W3"},
    ),
    "M_cluster_a": (
        "an `a` inside a short-flag cluster is read as -a",
        [('                if ch == "a":\n                    return True',
          '                if False:\n                    return True')],
        {"W1", "W2", "W6", "W8", "W9", "W10", "W11", "W12", "W16", "W17", "W18", "W23"},
    ),
    "M_value_letter_stops_cluster": (
        "a value-taking letter (-m) ends the cluster, so -ma is not -a",
        [("                if ch in _COMMIT_VALUE_SHORT:\n"
          "                    if pos == len(a) - 1:",
          "                if False:\n                    if pos == len(a) - 1:")],
        {"S5", "S10"},  # S10's `-m -a`: `-m` alone then reads `-a` as flags
    ),
    "M_value_token_skipped": (
        "the token after a trailing -m is its value, not flags",
        [("                    if pos == len(a) - 1:\n"
          "                        i += 1  # value is the next token",
          "                    if pos == len(a) - 1:\n"
          "                        pass")],
        {"S10"},
    ),
    "M_optional_value_S_u_not_in_value_set": (
        "-S and -u do not consume the next token",
        [('_COMMIT_VALUE_SHORT = set("mFCct")',
          '_COMMIT_VALUE_SHORT = set("mFCctSu")')],
        {"W17", "W18"},
    ),
    "M_optional_attached_value_ends_cluster": (
        "the rest of a -S/-u cluster is its attached value (-uall)",
        [('                if ch in "Su":\n'
          "                    break  # optional attached value (-uall): rest of cluster",
          "                if False:\n                    break")],
        {"S14"},
    ),
    "M_magic_pathspec_warns": (
        "a magic pathspec (`:/`) warns instead of going silent",
        [('        if p.startswith(":") or any(ch in p for ch in "*?["):',
          '        if any(ch in p for ch in "*?["):')],
        {"W20"},
    ),
    "M_glob_pathspec_warns": (
        "a glob pathspec warns instead of going silent",
        [('        if p.startswith(":") or any(ch in p for ch in "*?["):',
          '        if p.startswith(":"):')],
        {"W21"},
    ),
    "M_windows_separator": (
        "backslash separators are normalised in pathspecs",
        [('        p = p.replace("\\\\", "/")  # Windows separators',
          "        pass")],
        {"W22"},
    ),
    "M_git_dir_work_tree_silent": (
        "--git-dir/--work-tree go silent instead of checking the wrong repo",
        [("            return None  # names another repository; go silent (docstring)",
          "            i += 1  # mutated: keep scanning")],
        {"S15"},
    ),
    "M_shared_deadline": (
        "git calls share one deadline, so a spent budget fails open",
        [("    if remaining <= 0:\n        return None",
          "    if False:\n        return None"),
         ("            timeout=min(_PER_CALL_S, remaining),",
          "            timeout=_PER_CALL_S,")],
        {"S19"},
    ),
    "M_ignore_submodules_dirty": (
        "status skips dirty-content scans of submodules",
        [('                  "--ignore-submodules=dirty")', "                  )")],
        # Declared EMPTY: it is a speed-up. Dirty content cannot change a
        # gitlink, so the verdict is identical with or without the flag.
        set(),
    ),
    "M_optional_locks_off": (
        "git runs with GIT_OPTIONAL_LOCKS=0",
        [('env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})',
          "env=os.environ)")],
        # Declared EMPTY: it only stops a read-only status from refreshing
        # the index under a concurrent git, which no verdict shows.
        set(),
    ),
    "M_add_update_long": (
        "`--update` is read as -u",
        [('        if f == "--update":\n            return True, paths',
          '        if False:\n            return True, paths')],
        {"W5"},
    ),
    "M_add_update_short": (
        "`-u` is read as update",
        [('        if not f.startswith("--") and "u" in f[1:]:\n'
          "            return True, paths",
          "        if False:\n            return True, paths")],
        {"W4", "W7", "W13", "W14", "W15", "W20", "W21", "W22"},
    ),
    "M_dash_c_dir": (
        "`git -C <dir>` retargets the repository",
        [("        for d in c_dirs:\n            target = os.path.join(target, d)",
          "        for d in c_dirs:\n            pass")],
        {"W6", "S9"},
    ),
    "M_cd_tracking": (
        "an earlier `cd <dir>` retargets the repository",
        [('            cd = os.path.join(cd, rest[1]) if rest[1] not in ("-",) else cd',
          "            pass")],
        # S17/S18 are silent only because the `cd` target is unresolvable.
        {"W9", "S17", "S18"},
    ),
    "M_lead_words": (
        "env assignments and lead words are skipped",
        [("    return _strip_env(argv)[1]", "    return argv")],
        {"W11"},
    ),
    "M_global_value_options": (
        "a global `-c k=v` consumes its value",
        [("        elif a in _GIT_VALUE_GLOBAL:\n            i += 2",
          "        elif a in _GIT_VALUE_GLOBAL:\n            i += 1")],
        {"W12"},
    ),
    "M_head_differs_from_pin": (
        "only a submodule whose HEAD differs from the pin counts",
        [("        if head != pinned:", "        if True:")],
        # Declared EMPTY since status runs with --ignore-submodules=dirty:
        # a worktree-`M` gitlink entry now always has HEAD != pin, so this
        # comparison is defence in depth that no case can reach (S3, the
        # dirty-content case, is dropped by status itself).
        set(),
    ),
    "M_pathspec_scoping": (
        "`git add -u <pathspec>` only counts a submodule under a pathspec",
        [("            return True\n    return False\n\n\nNOTE",
          "            return True\n    return True\n\n\nNOTE")],
        {"S6"},
    ),
    "M_mode_160000": (
        "only a gitlink (mode 160000) counts",
        [('        if len(fields) < 3 or fields[0] != "160000":',
          "        if len(fields) < 3:")],
        # Declared EMPTY: a modified regular file reaches the next guard
        # (rev-parse in a path that is not a directory fails and is skipped),
        # so removing the mode test changes no verdict here. It stays as the
        # explicit statement of the condition, not as separately tested code.
        set(),
    ),
    "M_worktree_column_modified": (
        "only a worktree-column `M` entry counts",
        [('        if xy[1] != "M":\n            continue',
          "        if False:\n            continue")],
        # Declared EMPTY: a pin bump staged on purpose has HEAD == index, so
        # M_head_differs_from_pin already silences it (S11).
        set(),
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
                         f"{mutated.count(find)}); the mutation harness is "
                         f"measuring nothing.\n---\n{find}\n---")
            mutated = mutated.replace(find, replace)
        path = os.path.join(tmp, f"mutant-{clause}.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(mutated)
        flipped = {cid for cid, (builder, command) in CASES.items()
                   if build_and_verdict(path, builder, command) != EXPECTED[cid]}
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
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<30} {statement}\n"
              f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under reversion")
shutil.rmtree(ELSEWHERE, ignore_errors=True)
sys.exit(1 if (wrong or mutation_wrong) else 0)
