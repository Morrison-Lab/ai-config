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
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HOOK = os.path.realpath(sys.argv[1])
ELSEWHERE = tempfile.mkdtemp()  # a cwd that is not the repo under test
_SCRATCH = [ELSEWHERE]  # every temp dir this run made, removed at exit
# atexit also runs on the sys.exit(FATAL) paths below, which would otherwise
# leave the scratch repos behind.
atexit.register(lambda: [shutil.rmtree(p, ignore_errors=True)
                         for p in _SCRATCH])
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
    _SCRATCH.append(path)
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


def symlink_to_dir_repo(path):
    """A tracked symlink to a directory, repointed at the (clean) submodule:
    status says ` M lnk`, but `lnk` is mode 120000, not a gitlink."""
    _base_with_submodule(path)
    _write(path, "docs", "f.txt")
    os.symlink("docs", os.path.join(path, "lnk"))
    _run(path, "add", "docs", "lnk")
    _run(path, "commit", "-qm", "link")
    os.remove(os.path.join(path, "lnk"))
    os.symlink("mod", os.path.join(path, "lnk"))


def many_files_repo(path):
    """A big sweep: thousands of modified tracked files, and a moved
    submodule that sorts after all of them."""
    _base_with_submodule(path)
    for i in range(5000):
        _write(path, "a", f"f{i}.txt")
    _run(path, "add", "a")
    _run(path, "commit", "-qm", "many")
    for i in range(5000):
        _write(path, "a", f"f{i}.txt", content="changed\n")
    _move_submodule_head(path)


def ignore_all_repo(path):
    """submodule.mod.ignore=all: git leaves the moved gitlink alone."""
    moved_pin_only_repo(path)
    _run(path, "config", "submodule.mod.ignore", "all")


def diff_ignore_all_repo(path):
    """diff.ignoreSubmodules=all: the same, set repository-wide."""
    moved_pin_only_repo(path)
    _run(path, "config", "diff.ignoreSubmodules", "all")


def latin1_path_repo(path):
    """A tracked file whose name is not valid UTF-8 (POSIX only), plus a
    moved submodule: `ls-files -z` and `status -z` emit that name raw."""
    _base_with_submodule(path)
    raw = os.path.join(os.fsencode(path), b"caf\xe9.txt")
    with open(raw, "w", encoding="utf-8") as handle:
        handle.write("x\n")
    _run(path, "add", "-A")
    _run(path, "commit", "-qm", "latin-1 name")
    _move_submodule_head(path)


def subdir_repo(path):
    """A moved pin plus a tracked `docs/` directory to run from."""
    moved_pin_only_repo(path)
    _write(path, "docs", "f.txt")
    _run(path, "add", "docs")
    _run(path, "commit", "-qm", "docs")


def rename_odd_repo(path):
    """A staged rename whose OLD name looks like a status record for `mod`
    (`xM mod`: two status letters, a space, a path), next to a submodule that
    has not moved. Reading the old name as a record would invent a modified
    `mod`."""
    _base_with_submodule(path)
    _write(path, "xM mod", content="rename me\n")
    _run(path, "add", "xM mod")
    _run(path, "commit", "-qm", "odd name")
    _run(path, "mv", "xM mod", "renamed.txt")


def fsmonitor_repo(path):
    """The repository's own config names a core.fsmonitor program: git runs
    it during `status`, so the hook's status must switch it off."""
    moved_pin_only_repo(path)
    marker = os.path.join(ELSEWHERE, "executed-marker")
    _run(path, "config", "core.fsmonitor", f'sh -c "touch {marker}"')


def filter_repo(path):
    """A stat-dirty file that .gitattributes routes to a clean filter named
    in the repository config: status would run that program."""
    moved_pin_only_repo(path)
    marker = os.path.join(ELSEWHERE, "executed-marker")
    _write(path, ".gitattributes", content="*.txt filter=evil\n")
    _write(path, "a.txt", content="one\n")
    _run(path, "add", ".gitattributes", "a.txt")
    _run(path, "commit", "-qm", "attrs")
    _run(path, "config", "filter.evil.clean", f"sh -c 'touch {marker}; cat'")
    _run(path, "config", "filter.evil.smudge", "cat")
    later = time.time() + 100
    os.utime(os.path.join(path, "a.txt"), (later, later))


def index_hook_repo(path):
    """A stat-dirty file and a post-index-change hook: a status that writes
    the refreshed index would run the hook."""
    moved_pin_only_repo(path)
    marker = os.path.join(ELSEWHERE, "executed-marker")
    hook = os.path.join(path, ".git", "hooks", "post-index-change")
    _write(hook, content=f"#!/bin/sh\ntouch {marker}\n")
    os.chmod(hook, 0o755)
    later = time.time() + 100
    os.utime(os.path.join(path, "CLAUDE.md"), (later, later))


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
    ("W20", moved_pin_only_repo, "git add -u ':(glob)CLAUDE.md'",
     "magic the hook does not evaluate is not guessed at: warn, not silent"),
    ("W21", moved_pin_only_repo, "git add -u 'CLAUDE.*'",
     "glob include is not evaluated: warn, not silent"),
    ("W23", staged_then_moved_repo, f"git commit -am {MSG}",
     "MM: staged bump, then the submodule moved again"),
    ("W24", moved_pin_only_repo, "cd {link} && git add -u mod",
     "cwd reached through a symlink: paths compared through realpath"),
    ("W25", moved_pin_only_repo,
     f"git add -u CLAUDE.md && git commit -am {MSG}",
     "first match is filtered out by its pathspec; a later one still warns"),
    ("W26", moved_pin_only_repo,
     f"git -C /nonexistent-dir-xyz commit -am {MSG}; git commit -am {MSG}",
     "first match has a missing directory; a later one still warns"),
    ("W27", moved_pin_only_repo, "git add -A", "git add -A stages the gitlink"),
    ("W28", moved_pin_only_repo, "git add --all", "git add --all"),
    ("W29", moved_pin_only_repo, "git add .",
     "git add . stages the gitlink (checked with git 2.x)"),
    ("W30", moved_pin_only_repo, f"cd -P {{repo}} && git commit -am {MSG}",
     "`cd -P dir` is read as a cd to dir"),
    ("W31", moved_pin_only_repo, f"cd - ; git -C {{repo}} commit -am {MSG}",
     "an absolute -C is still read after a `cd -`"),
    ("W32", moved_pin_only_repo,
     f"ENVV=1 git --config-env a.b=ENVV --namespace ns commit -am {MSG}",
     "global --config-env and --namespace consume a separated value"),
    ("W33", moved_pin_only_repo, f"/usr/bin/git commit -am {MSG}",
     "the shared parser normalises /usr/bin/git, so it is read"),
    ("W34", moved_pin_only_repo,
     f"(cd mod && git log -1); git commit -am {MSG}",
     "a cd inside a subshell does not reach the command after it"),
    ("W35", moved_pin_only_repo, f"@payloadcwd git commit -am {MSG}",
     "the payload's `cwd` is the base directory, not the hook's own"),
    ("W36", moved_pin_only_repo, f"@inputcwd git commit -am {MSG}",
     "tool_input.Cwd beats the payload's `cwd`"),
    ("W37", moved_pin_only_repo, "git add --no-ignore-removal",
     "--no-ignore-removal is an alias of -A"),
    ("W40", subdir_repo, "cd docs && git add :/",
     "top-level magic covers the whole tree, even from a subdirectory"),
    ("W41", subdir_repo, "cd docs && git add ':(top)'",
     "the long spelling of the same top-level pathspec"),
    ("W44", moved_pin_only_repo, "git commit --message=x -a",
     "an attached long-option value does not eat the next token"),
    ("W45", moved_pin_only_repo,
     "git commit --author 'A U Thor <a@b.c>' -a -m fix",
     "a separated long-option value is skipped, and -a after it is read"),
    ("W46", moved_pin_only_repo, "git add --upd",
     "git accepts an unambiguous prefix: --upd is --update"),
    ("W47", moved_pin_only_repo, "git commit -a --s -m fix",
     "an ambiguous prefix (--s) is not guessed at, so -a still sweeps"),
    ("W48", moved_pin_only_repo, "git add -u --pathspec-from-file list.txt",
     "the value of --pathspec-from-file is not a pathspec"),
    ("W70", ignore_all_repo, f"git commit -am {MSG}",
     "submodule.mod.ignore=all hides the pin from status, not from -a"),
    ("W71", diff_ignore_all_repo, "git add -u",
     "diff.ignoreSubmodules=all hides the pin from status, not from add -u"),
    ("W66",moved_pin_only_repo, "git add 'mod*'",
     "a glob that matches the submodule stages it"),
    ("W67", moved_pin_only_repo, "git add '*'",
     "a glob that sweeps in the submodule from above"),
    ("W68", filter_repo, "git commit -am fix",
     "a clean filter named in the repository config must not run during status"),
    ("W69", index_hook_repo, "git commit -am fix",
     "status must not write the index, or post-index-change would run"),
    ("W62", fsmonitor_repo, "git commit -am fix",
     "a repository's core.fsmonitor program must not run during the hook's status"),
    ("W63", moved_pin_only_repo,
     "git -c submodule.mod.ignore=all commit -am fix",
     "a command-line submodule.<n>.ignore=all does not stop git staging it"),
    ("W64", moved_pin_only_repo, "git -c diff.ignoreSubmodules=all add -u",
     "a command-line diff.ignoreSubmodules=all does not stop add staging it"),
    ("W65", moved_pin_only_repo,
     "if true; then cd mod | cat; fi; git commit -am fix",
     "a pipeline cd after a shell keyword runs in a subshell"),
    ("W50", moved_pin_only_repo, "@home git -C ~ commit -am fix",
     "-C ~ is expanded like cd ~"),
    ("W51", moved_pin_only_repo, "@home git -C $HOME commit -am fix",
     "-C $HOME is expanded like cd $HOME"),
    ("W52", moved_pin_only_repo, "git add . ':!CLAUDE.md'",
     "an exclude that does not match the submodule leaves it covered"),
    ("W53", moved_pin_only_repo, "git add -u ':(exclude)CLAUDE.md'",
     "an exclude-only add -u still stages the submodule"),
    ("W54", moved_pin_only_repo, "git add ':!CLAUDE.md'",
     "a plain add of only an exclude takes `.` as the include"),
    ("W55", moved_pin_only_repo, "git add -u ':(icase)MOD'",
     "an icase include matches the submodule"),
    ("W56", moved_pin_only_repo, "cd mod | cat; git commit -am fix",
     "a cd in a pipeline stage runs in a subshell: the commit stays here"),
    ("W57", moved_pin_only_repo, "cd mod & git commit -am fix",
     "a backgrounded cd runs in a subshell: the commit stays here"),
    ("W58", moved_pin_only_repo, "bash -c 'git commit -am fix'",
     "a command inside bash -c is read"),
    ("W59", moved_pin_only_repo, "sh -c 'cd . && git commit -am fix'",
     "a nested shell starts in the session directory when nothing moved it"),
    ("W60", moved_pin_only_repo, "bash -c 'git -C {repo} commit -am fix'",
     "an absolute -C inside bash -c is read"),
    ("W61", moved_pin_only_repo,
     "cd /nonexistent-dir-xyz; bash -c 'git -C {repo} commit -am fix'",
     "after a cd the nested directory is unknown, but an absolute -C is read"),
    ("W43", moved_pin_only_repo, f"pushd {{repo}} && git commit -am {MSG}",
     "`pushd dir` moves the directory like `cd`"),
    ("W38", many_files_repo, f"git commit -am {MSG}",
     "5000 modified files and a moved submodule sorting last: the one index "
     "read keeps the warning inside the deadline"),
] + ([("W22", moved_pin_only_repo, "git add -u '.\\mod'",
       "Windows path separator is normalised")] if os.name == "nt" else []
     ) + ([("W39", latin1_path_repo, f"git commit -am {MSG}",
            "a tracked name that is not UTF-8 must not crash the hook")]
          if os.name != "nt" else [])
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
     "`cd ~` is expanded to the home directory, which is not the repo"),
    ("S18", moved_pin_only_repo, f"cd $SOME_DIR && git commit -am {MSG}",
     "`cd $VAR` is not expanded: documented silent case"),
    ("S19", moved_pin_only_repo, f"@budget0 git commit -am {MSG}",
     "git deadline already spent: fail open, not a late kill"),
    ("S21", symlink_to_dir_repo, f"git commit -am {MSG}",
     "a modified tracked symlink to a directory is mode 120000, not a gitlink"),
    ("S22", moved_pin_only_repo, f"git commit -a --dry-run -m {MSG}",
     "--dry-run commits nothing"),
    ("S23", moved_pin_only_repo, f"git commit -a --short -m {MSG}",
     "--short implies a dry run"),
    ("S24", moved_pin_only_repo, "git add -n -u", "add -n stages nothing"),
    ("S25", moved_pin_only_repo, "git add --dry-run .",
     "add --dry-run stages nothing"),
    ("S26", moved_pin_only_repo, f"cd - && git commit -am {MSG}",
     "`cd -` leaves the directory unknown: documented silent case"),
    ("S27", moved_pin_only_repo, f"cd && git commit -am {MSG}",
     "a bare `cd` goes home, which is not the repo"),
    ("S28", moved_pin_only_repo, "git add mod",
     "naming the submodule is how a pin bump is staged on purpose"),
    ("S29", moved_pin_only_repo, "git add ':(glob)CLAUDE.md'",
     "unevaluated magic on a plain add is not guessed at: documented silent case"),
    ("S30", moved_pin_only_repo, f"(cd mod && git commit -am {MSG})",
     "a cd inside a subshell applies to the commands inside it"),
    ("S31", moved_pin_only_repo, f"{{ cd mod; }}; git commit -am {MSG}",
     "a cd inside a { } group moves the caller"),
    ("S32", moved_pin_only_repo, f"@payloadelsewhere git commit -am {MSG}",
     "the payload's `cwd` beats the hook's own working directory"),
    ("S33", moved_pin_only_repo, "git add --refresh .",
     "--refresh stages nothing"),
    ("S39", subdir_repo, "cd docs && git add :/mod",
     "a top-level pathspec that names the submodule is a deliberate bump"),
    ("S43", moved_pin_only_repo, "git commit --message -a",
     "`-a` is the VALUE of --message"),
    ("S44", moved_pin_only_repo, "git commit -m fix -- -a",
     "after `--` every token is a path, `-a` included"),
    ("S45", moved_pin_only_repo, "git add -- -u",
     "after `--` `-u` is a path, not an option"),
    ("S46", moved_pin_only_repo, "git commit -a --dry -m fix",
     "--dry is an unambiguous prefix of --dry-run"),
    ("S47", moved_pin_only_repo, "git add --dr -u",
     "--dr is an unambiguous prefix of --dry-run"),
    ("S48", moved_pin_only_repo, "git commit --mess -a",
     "--mess is --message, and -a is its value"),
    ("S51", moved_pin_only_repo, "git add . ':!mod'",
     "an exclude of the submodule keeps it out"),
    ("S52", moved_pin_only_repo, "git add -u ':(exclude)mod'",
     "the long spelling of the same exclude"),
    ("S53", moved_pin_only_repo, "git add -A ':^mod'",
     "the `:^` spelling of the same exclude"),
    ("S54", moved_pin_only_repo, "git add -u mod ':!mod'",
     "an exclude beats an include of the same path"),
    ("S55", moved_pin_only_repo, "git add -u ':!mo*'",
     "a glob exclude is matched against the submodule path"),
    ("S56", moved_pin_only_repo, "git add . ':(exclude,icase)MOD'",
     "an icase exclude matches the submodule"),
    ("S57", subdir_repo, "cd docs && git add -u ':(exclude,top)mod'",
     "a top-level exclude is read from the repository root"),
    ("S58", moved_pin_only_repo, "cd mod 2>&1 && git commit -am fix",
     "a redirect `2>&1` is not a background job: the cd still moves"),
    ("S59", moved_pin_only_repo, "cd mod && bash -c 'git commit -am fix'",
     "after a cd a nested shell's directory is unknown: documented silent case"),
    ("S60", moved_pin_only_repo, "bash -c 'cd mod && git commit -am fix'",
     "a cd inside bash -c moves into the clean submodule"),
    ("S62", moved_pin_only_repo, "env -C mod git commit -am fix",
     "env -C runs git in another directory: documented silent case"),
    ("S63", moved_pin_only_repo, "env --chdir=mod git commit -am fix",
     "env --chdir runs git in another directory: documented silent case"),
    ("S65", moved_pin_only_repo, "git add -N .", "add -N stages no gitlink"),
    ("S66", moved_pin_only_repo, "git add --renormalize .",
     "add --renormalize stages no gitlink"),
    ("S67", moved_pin_only_repo, "git add -u ':!:mod'",
     "the optional `:` ending short magic: this excludes mod"),
    ("S68", moved_pin_only_repo,
     "bash -c \"cd mod && bash -c 'git commit -am fix'\"",
     "a cd in an intermediate bash -c makes the inner directory unknown"),
    ("S69", moved_pin_only_repo,
     "cd {repo} && bash -c 'git commit -am fix'",
     "after a cd a nested line is unknown: documented silent case"),
    ("S70", moved_pin_only_repo, "git add --intent-to-add .",
     "the long spelling of add -N"),
    ("S61", rename_odd_repo, "git add -u",
     "a staged rename's old name is not a status record of its own"),
    ("S40", moved_pin_only_repo, f"pushd mod && git commit -am {MSG}",
     "`pushd mod` moves into the clean submodule"),
    ("S41", moved_pin_only_repo, f"popd; git commit -am {MSG}",
     "`popd` leaves the directory unknown: documented silent case"),
    ("S42", moved_pin_only_repo,
     f"cd $X && cd {{reporel}} && git commit -am {MSG}",
     "after an unexpanded `$VAR` a relative cd is not guessed from the cwd"),
    ("S34", moved_pin_only_repo, f"GIT_DIR=.git git commit -am {MSG}",
     "a GIT_DIR prefix names another repository: documented silent case"),
    ("S35", moved_pin_only_repo, "GIT_WORK_TREE=. git add -u",
     "a GIT_WORK_TREE prefix names another repository"),
    ("S36", moved_pin_only_repo, f"env GIT_DIR=.git git commit -am {MSG}",
     "GIT_DIR after `env` redirects git too"),
] + ([] if os.name == "nt" else [
    ("S20", moved_pin_only_repo, "git add -u '.\\mod'",
     "on POSIX a backslash is a name character, not a separator"),
])


def verdict(hook_path, repo, command, want_text=False):
    cwd = (ELSEWHERE if any(k in command for k in ("{repo}", "{link}", "{reporel}"))
           else repo)
    # The repo as seen from ELSEWHERE: what a cwd-relative guess would reach.
    command = command.replace("{reporel}", os.path.relpath(repo, ELSEWHERE))
    if "{link}" in command:  # a symlink to the repo, so the cwd is unresolved
        link = os.path.join(ELSEWHERE, "link-" + os.path.basename(repo))
        if not os.path.islink(link):
            os.symlink(repo, link)
        command = command.replace("{link}", link)
    command = command.replace("{repo}", repo)
    env = {**os.environ, "PYTHONPATH": SHELLCMD_LIB}
    payload = {"tool_name": "Bash"}
    tool_input = {}
    # `@name ` prefixes shape the payload rather than the command.
    while command.startswith("@"):
        name, _, command = command[1:].partition(" ")
        if name == "budget0":  # an already-spent git deadline
            env["FLAG_COMMIT_A_BUDGET_S"] = "0"
        elif name == "payloadcwd":  # payload `cwd` is the repo; process cwd is not
            payload["cwd"], cwd = repo, ELSEWHERE
        elif name == "inputcwd":  # tool_input.Cwd wins over payload `cwd`
            tool_input["Cwd"], payload["cwd"], cwd = repo, ELSEWHERE, ELSEWHERE
        elif name == "payloadelsewhere":  # payload `cwd` beats the process cwd
            payload["cwd"], cwd = ELSEWHERE, repo
        elif name == "home":  # HOME is the repo; the process cwd is not
            env["HOME"], cwd = repo, ELSEWHERE
        else:
            sys.exit(f"FATAL: unknown payload prefix @{name}")
    # The file a repository's core.fsmonitor program would create: if it
    # exists after the run, the hook let that config execute at hook time.
    marker = os.path.join(ELSEWHERE, "executed-marker")
    if os.path.exists(marker):
        os.remove(marker)
    tool_input["command"] = command
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps({**payload, "tool_input": tool_input}),
        capture_output=True, text=True, cwd=cwd,
        # Mutants are written to a temp dir, where the hook's own
        # `scripts/lib` lookup (relative to its file) finds nothing.
        env=env,
    )
    if os.path.exists(marker):
        os.remove(marker)
        return "EXECUTED"  # the hook ran the repository's fsmonitor program
    if proc.returncode != 0 and hook_path != HOOK:
        return "crash"  # a mutant that raises is a flip, not a harness error
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
    msg_checks = []  # (label, ok); counted apart from the verdict cases

    def check(label, needle, text, present=True):
        msg_checks.append((label, (needle in text) == present))

    for label, needle in (("submodule path", "mod:"), ("pinned sha", pinned[:7]),
                          ("checked-out sha", head[:7]),
                          ("suggestion", "git commit -- <paths>"),
                          ("push-first caution", "pushed or on a branch")):
        check(f"commit -a message names {label}", needle, text)
    check("commit -a message says this commit", "this commit would MOVE", text)
    check("commit -a message names no pathspec scope", " under ", text, False)
    # `add -u` only stages: the message must say the NEXT commit moves it,
    # and `add -u <pathspec>` must not claim to stage every modified path.
    res = verdict(HOOK, repo, "git add -u", want_text=True)
    text = json.dumps(res[1]) if isinstance(res, tuple) else ""
    check("add -u message says the next commit (additionalContext)",
          "the next commit", text)
    check("add -u message says the next commit (systemMessage)",
          "next commit would", text)
    res = verdict(HOOK, repo, "git add -u mod", want_text=True)
    text = json.dumps(res[1]) if isinstance(res, tuple) else ""
    check("add -u <pathspec> message scopes the staging to the pathspec",
          "every modified tracked path under mod", text)
    res = verdict(HOOK, repo, "git add -A", want_text=True)
    text = json.dumps(res[1]) if isinstance(res, tuple) else ""
    check("add -A message says it stages every change", "stages every change",
          text)
    for label, ok in msg_checks:
        print(f"  {'ok  ' if ok else 'WRONG'} {label}")
finally:
    shutil.rmtree(repo, ignore_errors=True)

msg_wrong = sum(not ok for _, ok in msg_checks)
total = len(CASES)
print(f"\n{total - wrong}/{total} cases correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
print(f"{len(msg_checks) - msg_wrong}/{len(msg_checks)} message checks correct"
      + ("" if msg_wrong == 0 else f"  ({msg_wrong} WRONG)"))
wrong += msg_wrong

# ------------------------------------------------------------ ground truth
# The cases above say what the HOOK should do. This pass runs each real
# command in a throwaway copy of its fixture and asks git itself whether the
# pin of `mod` ended up different in the index or in HEAD. A case where the
# hook and git disagree must be listed here with the reason: a documented
# silent case (the hook cannot see the target), a documented over-warn, or a
# command that does not run as written.
GT_EXEMPT = {
    "W20": "unevaluated magic warns by design: git treats :(glob)CLAUDE.md as "
           "a path the submodule is not under",
    "W21": "an unmatched glob include warns by design (the hook does not "
           "expand it for -u)",
    "W47": "git rejects the ambiguous option --s, so nothing runs; the hook "
           "does not guess at it",
    "W48": "the pathspec file does not exist, so git stops; the hook does "
           "not read it",
    "S11": "a staged pin bump is committed by -a, but it was staged on "
           "purpose, so the hook stays silent",
    "S15": "documented silent case: --git-dir/--work-tree name another repo",
    "S16": "documented silent case: separated --git-dir",
    "S34": "documented silent case: GIT_DIR in the environment",
    "S35": "documented silent case: GIT_WORK_TREE in the environment",
    "S36": "documented silent case: GIT_DIR through env",
    "S28": "naming the submodule on a plain add is a deliberate bump",
    "S39": "a top-level pathspec naming the submodule is a deliberate bump",
    "S41": "documented silent case: the directory after popd is unknown",
    "S69": "documented silent case: a nested line after a cd has an unknown "
           "directory",
}
GT_SKIP_PREFIX = "@"  # payload-shaped cases (cwd, HOME) are not shell commands


def _pin_state(repo):
    return [subprocess.run(["git", *args], cwd=repo, capture_output=True,
                           text=True).stdout
            for args in (("ls-files", "-s", "mod"), ("ls-tree", "HEAD", "mod"))]


def _ground_truth(case_id, builder, command):
    """True if running `command` for real moves the pin of `mod`."""
    if builder not in _REPOS:
        _REPOS[builder] = _repo(builder)
    copy = tempfile.mkdtemp()
    _SCRATCH.append(copy)
    dst = os.path.join(copy, "r")
    shutil.copytree(_REPOS[builder], dst, symlinks=True)
    cwd = ELSEWHERE if any(k in command for k in ("{repo}", "{link}",
                                                 "{reporel}")) else dst
    command = (command.replace("{reporel}", os.path.relpath(dst, ELSEWHERE))
               .replace("{link}", dst).replace("{repo}", dst))
    # -S only signs; a runner with no GPG key would fail the commit for that
    # reason alone, so the real run drops it (the pin moves the same way).
    command = command.replace("commit -S ", "commit ")
    before = _pin_state(dst)
    subprocess.run(["bash", "-c", command], cwd=cwd, capture_output=True,
                   text=True, timeout=120,
                   env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    after = _pin_state(dst)
    shutil.rmtree(copy, ignore_errors=True)
    return before != after


gt_wrong = gt_checked = 0
print("\nground truth (does the real command move the pin?):")
for case_id, (builder, command) in CASES.items():
    if command.startswith(GT_SKIP_PREFIX):
        continue
    gt_checked += 1
    moved = _ground_truth(case_id, builder, command)
    agrees = moved == (EXPECTED[case_id] == "WARN")
    if case_id in GT_EXEMPT:
        if agrees:
            print(f"  WRONG {case_id}  exempt but git agrees with the hook; "
                  "drop the exemption")
            gt_wrong += 1
        continue
    if not agrees:
        print(f"  WRONG {case_id}  hook says {EXPECTED[case_id]}, git "
              f"{'moves' if moved else 'does not move'} the pin: {command}")
        gt_wrong += 1
print(f"{gt_checked - gt_wrong - len([c for c in GT_EXEMPT if c in CASES])}"
      f"/{gt_checked} cases agree with git "
      f"({len(GT_EXEMPT)} exempt, each documented)"
      + ("" if gt_wrong == 0 else f"  ({gt_wrong} WRONG)"))
wrong += gt_wrong

# ------------------------------------------------------------ mutation harness

POSIX = os.name != "nt"
MUTATIONS = {
    "M_long_all": (
        "`--all` is read as -a",
        [('            if name == "--all":\n                sweeps = True',
          '            if False:\n                sweeps = True')],
        {"W3"},
    ),
    "M_cluster_a": (
        "an `a` inside a short-flag cluster is read as -a",
        [('                if ch == "a":\n                    sweeps = True',
          '                if False:\n                    sweeps = True')],
        {"W1", "W2", "W6", "W8", "W9", "W10", "W11", "W12", "W16", "W17",
         "W18", "W23", "W25", "W26", "W30", "W31", "W32", "W33", "W34",
         "W35", "W36", "W38", "W43", "W44", "W45", "W47", "W50",
         "W51", "W56", "W57", "W58", "W59", "W60", "W61", "W62", "W63", "W65",
         "W68", "W69", "W70"}
        | ({"W39"} if os.name != "nt" else set()),
    ),
    "M_value_letter_stops_cluster": (
        "a value-taking letter (-m) ends the cluster, so -ma is not -a",
        [("                elif ch in _COMMIT_VALUE_SHORT:\n"
          "                    if pos == len(a) - 1:",
          "                elif False:\n                    if pos == len(a) - 1:")],
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
        [('                elif ch in "Su":\n'
          "                    break  # optional attached value (-uall): rest of cluster",
          "                elif False:\n                    break")],
        {"S14"},
    ),
    "M_commit_dry_run": (
        "`commit --dry-run/--short/--porcelain/--long` commit nothing",
        [("            elif name in _COMMIT_DRY_RUN:\n                dry = True",
          "            elif False:\n                dry = True")],
        {"S22", "S23", "S46"},
    ),
    "M_unevaluated_magic_warns": (
        "magic the hook does not evaluate warns instead of being read as a path",
        [('"literal" in words, long_form.group(2))\n    return None',
          '"literal" in words, long_form.group(2))\n'
          '    return False, False, False, False, p')],
        {"W20"},
    ),
    "M_top_magic_read": (
        "`:/` and `:(top)` are read as the repository root",
        [('    if top:\n        rel = os.path.normpath(body or ".")',
          '    if False:\n        rel = os.path.normpath(body or ".")')],
        {"W40", "W41", "S57"},
    ),
    "M_exclude_evaluated": (
        "an exclude pathspec that matches the submodule keeps it out",
        [("        if spec and spec[0] and _matches(",
          "        if False and _matches(")],
        {"S51", "S52", "S53", "S54", "S55", "S56", "S57", "S67"},
    ),
    "M_exclude_only_means_all": (
        "pathspecs that are all excludes mean everything else",
        [("        return True  # only excludes: git takes `.` as the include",
          "        return False")],
        {"W53", "W54"},
    ),
    "M_icase": (
        "`icase` magic compares case-insensitively",
        [("    return rel.lower() if icase else rel", "    return rel"),
         ("    sub = sub_path.lower() if spec[2] else sub_path",
          "    sub = sub_path")],
        {"W55", "S56"},
    ),
    "M_glob_include_unmatched_warns": (
        "with -u/-A a glob include warns even when it matches nothing",
        [("            if sweeping or _matches(spec, rel, sub_path):",
          "            if _matches(spec, rel, sub_path):")],
        {"W21"},
    ),
    "M_glob_include_matched_warns": (
        "a glob include that matches the submodule warns, even on a plain add",
        [("            if sweeping or _matches(spec, rel, sub_path):",
          "            if sweeping:")],
        {"W66", "W67"},
    ),
    "M_plain_add_unevaluated_silent": (
        "unevaluated magic on a plain `git add` is not guessed at: silent",
        [("        if spec is None:\n            if sweeping:\n                return True\n            continue",
          "        if spec is None:\n            return True")],
        {"S29"},
    ),
    "M_optional_locks_off": (
        "git runs with GIT_OPTIONAL_LOCKS=0, so status writes no index",
        [('env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})',
          "env=os.environ)")],
        {"W69"},
    ),
    "M_attr_source_empty": (
        "status reads attributes from the empty tree, so no filter runs",
        [('"--attr-source=" + empty.strip(), "status",',
          '"status",')],
        {"W68"},
    ),
    "M_long_exact_match_first": (
        "an exact long-option name wins over longer names it prefixes",
        [("    if name in known:\n        return name\n", "")],
        {"W3"},
    ),
    "M_glob_exclude_matched": (
        "a glob in an exclude is matched with fnmatch",
        [("    if _has_glob(spec, rel):\n        prefixes",
          "    if False:\n        prefixes")],
        # The same glob test reads a glob INCLUDE (W66, W67).
        {"S55", "W66", "W67"},
    ),
    "M_windows_separator": (
        "backslash separators are normalised in pathspecs (Windows only)",
        [('        if os.name == "nt":\n'
          '            body = body.replace("\\\\", "/")  # Windows separators only',
          '        if False:\n'
          '            body = body.replace("\\\\", "/")  # Windows separators only')],
        # Unobservable on POSIX, where the clause never runs.
        set() if POSIX else {"W22"},
    ),
    "M_backslash_is_separator_everywhere": (
        "backslash is normalised on POSIX too, where it is a name character",
        [('        if os.name == "nt":\n'
          '            body = body.replace("\\\\", "/")  # Windows separators only',
          '        if True:\n'
          '            body = body.replace("\\\\", "/")  # Windows separators only')],
        {"S20"} if POSIX else set(),
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
    "M_status_ignore_override": (
        "status overrides the configured submodule ignore settings",
        [('"-uno",\n                  "--ignore-submodules=dirty")',
          '"-uno")')],
        # Without the override, status hides a gitlink that -a and add -u
        # still stage when submodule.<name>.ignore or
        # diff.ignoreSubmodules is `all` (W70, W71).
        # S3 (dirty content only) is reported once the override is gone.
        {"W70", "W71", "S3"},
    ),
    "M_unknown_stays_unknown": (
        "an unknown directory plus a relative move stays unknown",
        [("    if target is None or (cur is None and not os.path.isabs(target)):",
          "    if target is None:")],
        {"S42"},
    ),
    "M_pushd_popd": (
        "`pushd` and `popd` move the directory like `cd`",
        [('        if rest and rest[0] in ("cd", "pushd", "popd"):',
          '        if rest and rest[0] in ("cd",):')],
        {"W43", "S40", "S41"},
    ),
    "M_add_update_long": (
        "`--update` is read as -u",
        [('    if "--update" in names or "u" in letters:',
          '    if "u" in letters:')],
        {"W5", "W46"},
    ),
    "M_add_update_short": (
        "`-u` is read as update",
        [('    if "--update" in names or "u" in letters:',
          '    if "--update" in names:')],
        {"W4", "W7", "W14", "W15", "W20", "W21", "W24", "W48", "W55", "W64",
         "W71"},
    ),
    "M_add_all": (
        "`-A`/`--all` is read as a sweeping add",
        [('    if "--all" in names or "--no-ignore-removal" in names or "A" in letters:',
          "    if False:")],
        {"W27", "W28", "W37"},
    ),
    "M_add_plain_pathspec": (
        "a plain `git add <dir>` covering a submodule is read",
        [('    return ("add", paths) if paths else None', "    return None")],
        {"W29", "W40", "W41", "W52", "W54", "W66", "W67"},
    ),
    "M_add_dry_run_long": (
        "`git add --dry-run` stages nothing",
        [('_STAGES_NOTHING = {"--dry-run", "--refresh",',
          '_STAGES_NOTHING = {"--refresh",')],
        {"S25", "S47"},
    ),
    "M_add_refresh": (
        "`git add --refresh` stages nothing",
        [('{"--dry-run", "--refresh", "--intent-to-add",',
          '{"--dry-run", "--intent-to-add",')],
        {"S33"},
    ),
    "M_add_intent_to_add_long": (
        "`git add --intent-to-add` stages no gitlink",
        [('"--refresh", "--intent-to-add",', '"--refresh",')],
        {"S70"},
    ),
    "M_add_renormalize": (
        "`git add --renormalize` stages no gitlink",
        [('"--intent-to-add",\n                   "--renormalize"}',
          '"--intent-to-add"}')],
        {"S66"},
    ),
    "M_add_dry_run_short": (
        "`git add -n` stages nothing",
        [('or "n" in letters or "N" in letters:', 'or "N" in letters:')],
        {"S24"},
    ),
    "M_add_intent_to_add_short": (
        "`git add -N` stages no gitlink",
        [('or "n" in letters or "N" in letters:', 'or "n" in letters:')],
        {"S65"},
    ),
    "M_fsmonitor_off": (
        "every git call runs with core.fsmonitor switched off",
        [('["git", "-c", "core.fsmonitor=false", *args], cwd=cwd,',
          '["git", *args], cwd=cwd,')],
        {"W62"},
    ),
    "M_env_chdir_silent": (
        "`env -C dir` / `env --chdir=dir` go silent",
        [("        if _env_chdir(argv):", "        if False:")],
        {"S62", "S63"},
    ),
    "M_cd_keyword": (
        "a pipeline cd after `then`/`do`/... is still a pipeline cd",
        [("    while words and words[0] in _LEAD_KEYWORDS:",
          "    while False:")],
        {"W65"},
    ),
    "M_short_magic_colon": (
        "the optional `:` ending short magic is dropped",
        [('r"^:([!^/]+):?(.*)$"', 'r"^:([!^/]+)(.*)$"')],
        {"S67"},
    ),
    "M_add_no_ignore_removal": (
        "`--no-ignore-removal` is an alias of -A",
        [(' or "--no-ignore-removal" in names', "")],
        {"W37"},
    ),
    "M_per_path_index_query": (
        "one index read serves every modified path (no query per path)",
        [("        pinned = gitlinks.get(path)  # only a gitlink (mode 160000) counts\n",
          "        one = _git(top, 'ls-files', '-s', '--', path) or ''\n"
          "        got = one.split(None, 3)\n"
          "        pinned = got[1] if len(got) > 2 and got[0] == '160000' else None\n")],
        # 5000 queries spend the 8 s deadline, so the hook fails open.
        {"W38"},
    ),
    "M_status_no_untracked": (
        "status skips the untracked scan (-uno)",
        [('"-z", "-uno",', '"-z",')],
        # Declared EMPTY: a speed-up; untracked files never change a verdict.
        set(),
    ),
    "M_dash_c_dir": (
        "`git -C <dir>` retargets the repository",
        [('            target = _move(["cd", "--", d], target)',
          "            pass")],
        # W26 is not here: with -C ignored the first command runs in the
        # cwd and warns too, so the verdict is the same.
        {"W6", "S9", "W31", "W50", "W51", "W60", "W61"},
    ),
    "M_cd_tracking": (
        "an earlier `cd <dir>` retargets the repository",
        [("            cds[scope] = _move(rest, cd)", "            pass")],
        # S17/S18 are silent only because the `cd` goes somewhere that is not
        # a repository or cannot be named; S26/S27/S41/S42 because the
        # directory is unknown; S30/S31/S40 because the move into the (clean)
        # submodule is what makes them silent.
        {"W9", "W24", "W30", "W43", "S17", "S18", "S26", "S27", "S30", "S31",
         "S40", "S41", "S58", "S60"},
    ),
    "M_cd_unknown_directory": (
        "a move the resolver cannot name makes the directory unknown, not "
        "unchanged",
        [("            cds[scope] = _move(rest, cd)",
          "            cds[scope] = _move(rest, cd) or cd")],
        # S27 is not here: a bare `cd` goes home, which the resolver names.
        {"S18", "S26", "S41", "S42"},
    ),
    "M_subshell_cd_scoped": (
        "a cd inside a subshell stays inside it",
        [("            cds[scope] = _move(rest, cd)",
          "            cds[(0,)] = _move(rest, cd)")],
        {"W34"},
    ),
    "M_payload_cwd": (
        "the payload's `cwd` is the base directory",
        [('(inp.get("Cwd"), payload.get("cwd"))', '(inp.get("Cwd"),)')],
        {"W35", "S32"},
    ),
    "M_input_cwd_first": (
        "tool_input.Cwd takes precedence over the payload's `cwd`",
        [('(inp.get("Cwd"), payload.get("cwd"))', '(payload.get("cwd"), inp.get("Cwd"))')],
        {"W36"},
    ),
    "M_lead_words": (
        "env assignments and lead words are skipped",
        [("        env, rest = _strip_env(argv)", "        env, rest = [], argv")],
        {"W11", "W32", "W33", "S31"},  # S31: `{ cd mod; }` needs `{` stripped
    ),
    "M_env_redirect_silent": (
        "a GIT_DIR/GIT_WORK_TREE prefix names another repository: silent",
        [("        if inv is None or _redirects_git(env):",
          "        if inv is None:")],
        {"S34", "S35", "S36"},
    ),
    "M_non_utf8_names": (
        "git output with a non-UTF-8 file name is decoded, not fatal",
        [('out.stdout.decode("utf-8", "surrogateescape")',
          'out.stdout.decode("utf-8", "strict")')],
        # Skipped (empty) on Windows, which has no such file names.
        {"W39"} if os.name != "nt" else set(),
    ),
    "M_global_value_options": (
        "a global `-c k=v`, `--namespace`, `--config-env` consume their value",
        [("        elif a in _GIT_VALUE_GLOBAL:\n            i += 2",
          "        elif a in _GIT_VALUE_GLOBAL:\n            i += 1")],
        {"W12", "W32", "W63", "W64"},
    ),
    "M_long_prefix": (
        "a long option may be abbreviated to an unambiguous prefix",
        [("    matches = [k for k in known if k.startswith(name)]\n"
          "    return matches[0] if len(matches) == 1 else None",
          "    return None")],
        {"W46", "S46", "S47", "S48"},
    ),
    "M_long_ambiguous_not_guessed": (
        "an ambiguous prefix names no option",
        [("    return matches[0] if len(matches) == 1 else None",
          "    return sorted(matches)[0] if matches else None")],
        {"W47"},
    ),
    "M_commit_long_value_skipped": (
        "the token after a separated long-option value is not read as flags",
        [('            elif name in _COMMIT_VALUE_LONG and "=" not in a:',
          "            elif False:")],
        {"S43", "S48"},
    ),
    "M_commit_long_value_attached": (
        "an attached `--opt=value` has no separate value token",
        [('            elif name in _COMMIT_VALUE_LONG and "=" not in a:',
          "            elif name in _COMMIT_VALUE_LONG:")],
        {"W44"},
    ),
    "M_commit_dashdash": (
        "`--` ends commit's options",
        [('        if a == "--":\n            break',
          '        if False:\n            break')],
        {"S44"},
    ),
    "M_add_dashdash": (
        "`--` ends add's options",
        [('        elif a == "--":\n            dashdash = True',
          '        elif False:\n            dashdash = True')],
        {"S45"},
    ),
    "M_add_long_value_skipped": (
        "the value of --chmod/--pathspec-from-file is not a pathspec",
        [('            if name in _ADD_VALUE_LONG and "=" not in a:',
          "            if False:")],
        {"W48"},
    ),
    "M_rename_second_record": (
        "a rename/copy record is followed by its old path, which is skipped",
        [('        if xy[0] in ("R", "C"):\n            i += 1',
          '        if False:\n            i += 1')],
        {"S61"},
    ),
    "M_pipeline_cd_unreachable": (
        "a cd in a pipeline stage or background job never moves the shell",
        [("    ignore_cd = _unreachable_cd(command)", "    ignore_cd = False")],
        {"W56", "W57", "W65"},
    ),
    "M_redirect_is_not_a_job": (
        "`2>&1` and `&>` are redirections, not background jobs",
        [('    text = re.sub(r"[0-9]*[<>]&[0-9-]*|&>>?", " ", text)  # 2>&1, &>f',
          "    pass")],
        {"S58"},
    ),
    "M_nested_shell_c": (
        "a command line inside `bash -c` is read",
        [("    pieces = _shell_c_expansions(command)", "    pieces = [command]")],
        # S60 stays silent: without the nested line nothing is read at all.
        {"W58", "W59", "W60", "W61"},
    ),
    "M_nested_start_unknown": (
        "when another line has a cd, a nested line's directory is unknown",
        [("        hits += _scan(piece, None)[0] if others_move else scans[i][0]",
          "        hits += scans[i][0]")],
        {"S59", "S68"},
    ),
    "M_pathspec_scoping": (
        "`git add -u <pathspec>` only counts a submodule under a pathspec",
        [("            return True\n    return False\n\n\n# What each kind stages",
          "            return True\n    return True\n\n\n# What each kind stages")],
        # S2, S28, S29 and S20 are plain `git add` cases: without the final
        # `return False` they too would warn.
        {"S2", "S6", "S28", "S29", "S39", "S45"} | ({"S20"} if POSIX else set()),
    ),
    "M_plain_add_names_submodule_silent": (
        "a plain `git add mod` naming the submodule is a deliberate bump",
        [("        if _matches(spec, rel, sub_path) and (sweeping or rel != sub_path):",
          "        if _matches(spec, rel, sub_path):")],
        {"S28", "S39"},
    ),
    "M_realpath": (
        "pathspecs and the repo root are compared through realpath",
        [("    real_cwd, real_top = os.path.realpath(cwd), os.path.realpath(top)",
          "    real_cwd, real_top = cwd, top")],
        {"W24"},
    ),
    "M_every_match_checked": (
        "every matching invocation is checked, not only the first",
        [("    for segment, kind, target, pathspecs in hits:",
          "    for segment, kind, target, pathspecs in hits[:1]:")],
        {"W25", "W26"},
    ),
    "M_mode_160000": (
        "only a gitlink (mode 160000) counts",
        [('        if len(fields) == 3 and fields[0] == "160000":',
          "        if len(fields) == 3:")],
        # A tracked symlink to a directory is ` M` with mode 120000; without
        # the test it is read as a submodule whose HEAD differs from a blob.
        {"S21"},
    ),
    "M_worktree_column_modified": (
        "only a worktree-column `M` entry counts",
        [('        if xy[1] != "M":\n            continue',
          "        if False:\n            continue")],
        # A pin bump already staged is `M ` (index column only): the commit
        # would carry it, but it is deliberate (S11).
        {"S11"},
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
        # A mutant that lets status write the index refreshes the stat data
        # of a shared fixture, which would hide its stat-dirty file from
        # every later clause: rebuild those two.
        for stat_dirty in (filter_repo, index_hook_repo):
            _REPOS.pop(stat_dirty, None)
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
