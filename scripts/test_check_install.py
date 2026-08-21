#!/usr/bin/env python3
"""Regression tests for check-install.py.

Builds a synthetic repo and consumer directory containing one entry of every
classification, so the tests never touch a real `~/.claude`.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SCRIPT = Path(__file__).parent / "check-install.py"

spec = importlib.util.spec_from_file_location("check_install", SCRIPT)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_fixture(tmpdir: Path) -> tuple[Path, Path]:
    """One entry per classification, mirroring bootstrap.sh's install model."""
    repo = (tmpdir / "repo").resolve()
    consumer = (tmpdir / "consumer").resolve()

    write(repo / "CLAUDE.md", "top-level instructions\n")
    write(repo / "GEMINI.md", "gemini instructions\n")
    write(repo / "README.md", "repo readme, never installed\n")

    write(repo / "skills" / "alpha" / "SKILL.md", "alpha v2\n")
    # beta's SKILL.md is identical in both trees; only a supporting file
    # differs. The hand-run sweep this script replaces diffed SKILL.md alone,
    # so it read beta as fresh.
    write(repo / "skills" / "beta" / "SKILL.md", "beta shared text\n")
    write(repo / "skills" / "beta" / "reference.md", "repo reference\n")
    write(repo / "skills" / "gamma" / "SKILL.md", "gamma v1\n")
    write(repo / "skills" / "delta" / "SKILL.md", "delta v1\n")

    write(repo / "shared" / "frag.md", "a shared fragment\n")
    write(repo / "commands" / "cmd.md", "a command\n")

    # Excluded from installation by bootstrap.sh, so never reportable.
    write(repo / "references" / "example.md", "example material\n")
    write(repo / "codex-skills" / "alpha" / "SKILL.md", "codex wrapper\n")

    consumer.mkdir(parents=True)
    # ok: symlinked top-level file
    (consumer / "CLAUDE.md").symlink_to(repo / "CLAUDE.md")
    # misdirected: symlink resolving outside the repo
    write(tmpdir / "elsewhere" / "GEMINI.md", "someone else's copy\n")
    (consumer / "GEMINI.md").symlink_to(tmpdir / "elsewhere" / "GEMINI.md")
    # ok: whole group symlinked
    (consumer / "shared").symlink_to(repo / "shared")
    # missing: commands/ never installed

    # A real skills/ directory, as remote containers pre-seed it.
    (consumer / "skills").mkdir()
    (consumer / "skills" / "alpha").symlink_to(repo / "skills" / "alpha")
    write(consumer / "skills" / "beta" / "SKILL.md", "beta shared text\n")
    write(consumer / "skills" / "beta" / "reference.md", "pre-seeded reference\n")
    write(consumer / "skills" / "gamma" / "SKILL.md", "gamma v1\n")
    write(consumer / "skills" / "zeta" / "SKILL.md", "a built-in we do not ship\n")
    write(consumer / "skills" / "index.json", json.dumps({"harness": "index"}))
    write(consumer / "skills" / "manifest.json", json.dumps({"skills": []}))
    (consumer / "skills" / "gone").symlink_to(repo / "skills" / "does-not-exist")

    return repo, consumer


def statuses(repo: Path, consumer: Path) -> dict[str, str]:
    return {e.label: e.status for e in ci.collect(repo, consumer)}


def run_cli(repo: Path, consumer: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo),
         "--consumer-dir", str(consumer), *extra],
        capture_output=True, text=True,
    )


# --- classification ---------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    repo, consumer = make_fixture(Path(tmp))
    found = statuses(repo, consumer)

    check("symlinked top-level file is ok", found.get("CLAUDE.md") == "ok")
    check("symlink outside the repo is misdirected",
          found.get("GEMINI.md") == "misdirected")
    check("whole-group symlink is ok", found.get("shared") == "ok")
    check("group the consumer lacks is missing", found.get("commands") == "missing")
    check("symlinked child of a merged dir is ok",
          found.get("skills/alpha") == "ok")
    check("divergent real copy is stale", found.get("skills/beta") == "stale")
    check("identical real copy is unlinked", found.get("skills/gamma") == "unlinked")
    check("repo child absent from a merged dir is missing",
          found.get("skills/delta") == "missing")
    check("consumer-only directory is foreign", found.get("skills/zeta") == "foreign")
    check("harness skill index is not a foreign skill",
          "skills/manifest.json" not in found)
    check("stray file in skills/ is ignored", "skills/index.json" not in found)
    check("dangling skill symlink is still foreign",
          found.get("skills/gone") == "foreign")

    # The headline improvement over the SKILL.md-only sweep: beta is stale
    # even though the file that sweep compared is byte-identical.
    same_skill_md = (
        (repo / "skills" / "beta" / "SKILL.md").read_bytes()
        == (consumer / "skills" / "beta" / "SKILL.md").read_bytes()
    )
    check("supporting-file drift is caught with SKILL.md identical",
          same_skill_md and found.get("skills/beta") == "stale")

    check("excluded dirs are never reported",
          not any(k.startswith(("references", "codex-skills", "cursor-rules")) for k in found))
    check("repo README is never reported", "README.md" not in found)

    write(repo / ".hidden.md", "local residue, not an instruction file\n")
    found_with_hidden = statuses(repo, consumer)
    check("hidden top-level markdown is not installable",
          ".hidden.md" not in found_with_hidden)

# --- reporting --------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    repo, consumer = make_fixture(Path(tmp))
    result = run_cli(repo, consumer)

    check("read-only run exits 0 by default", result.returncode == 0)
    # Derived rather than hardcoded, so adding a fixture entry cannot break
    # this on an otherwise unrelated change. The number itself still has to be
    # asserted: a bare "checked ... installed entries" substring also passes on
    # a run that examined nothing (an empty repo prints "checked 0 installed
    # entries"), and that vacuous case is exactly what this guards against.
    expected = len(ci.collect(repo, consumer))
    check("summary prints a real, non-vacuous count",
          expected > 0
          and f"checked {expected} installed entries" in result.stdout)
    check("summary names each defect count",
          "1 stale" in result.stdout and "2 missing" in result.stdout
          and "1 unlinked" in result.stdout and "2 foreign" in result.stdout)
    check("defects prompt the reader toward --fix", "--fix" in result.stdout)
    check("read-only run mutates nothing",
          not (consumer / "skills" / "beta").is_symlink())

    strict = run_cli(repo, consumer, "--strict")
    check("--strict exits 1 while defects remain", strict.returncode == 1)

# --- repair -----------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    repo, consumer = make_fixture(Path(tmp))
    fixed = run_cli(repo, consumer, "--fix")

    check("--fix exits 0", fixed.returncode == 0)
    check("stale entry becomes a symlink into the repo",
          (consumer / "skills" / "beta").is_symlink()
          and (consumer / "skills" / "beta").resolve() == repo / "skills" / "beta")
    check("unlinked entry becomes a symlink",
          (consumer / "skills" / "gamma").is_symlink())
    check("missing child is installed", (consumer / "skills" / "delta").is_symlink())
    check("missing group is installed", (consumer / "commands").is_symlink())

    check("foreign directory is left alone",
          (consumer / "skills" / "zeta" / "SKILL.md").read_text(encoding="utf-8")
          == "a built-in we do not ship\n")
    check("ignored harness file is left alone",
          (consumer / "skills" / "manifest.json").is_file())
    check("ignored stray file is left alone",
          (consumer / "skills" / "index.json").is_file())
    check("dangling skill symlink is left alone",
          (consumer / "skills" / "gone").is_symlink())
    check("misdirected symlink is left alone",
          (consumer / "GEMINI.md").resolve() == (Path(tmp) / "elsewhere" / "GEMINI.md").resolve())

    backups = list((consumer / ci.BACKUP_DIR_NAME).glob("*/skills/beta/reference.md"))
    check("displaced copy is backed up rather than deleted",
          len(backups) == 1
          and backups[0].read_text(encoding="utf-8") == "pre-seeded reference\n")

    after = statuses(repo, consumer)
    check("re-run reports no repairable defect",
          not any(v in ("stale", "unlinked", "missing") for v in after.values()))
    check("re-run still reports the untouched entries",
          after.get("GEMINI.md") == "misdirected"
          and after.get("skills/zeta") == "foreign"
          and after.get("skills/gone") == "foreign")
    check("--strict passes once only report-only entries remain",
          run_cli(repo, consumer, "--strict").returncode == 0)

# --- symlink-less environments (Windows Git Bash) ---------------------------

with tempfile.TemporaryDirectory() as tmp:
    repo, consumer = make_fixture(Path(tmp))
    stale = next(e for e in ci.collect(repo, consumer) if e.status == "stale")
    action = ci.backup_and_replace(stale, Path(tmp) / "backups", use_symlinks=False)

    check("copy fallback reports the action it took", action == "copied")
    check("copy fallback installs real repo content",
          not (consumer / "skills" / "beta").is_symlink()
          and (consumer / "skills" / "beta" / "reference.md").read_text(encoding="utf-8")
          == "repo reference\n")
    check("copy fallback still backs the displaced copy up",
          (Path(tmp) / "backups" / "skills" / "beta" / "reference.md").exists())

# --- absent install ---------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    repo, _ = make_fixture(Path(tmp))
    absent = run_cli(repo, Path(tmp) / "nonexistent", "--strict")

    check("absent consumer dir exits 0 even under --strict", absent.returncode == 0)
    check("absent consumer dir says so rather than exiting silently",
          "nothing installed to check" in absent.stdout)

# --- bootstrap skills.json alias-exclude derivation -------------------------

ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = ROOT / "bootstrap.sh"


def derive_ground_truth_aliases(skills_dir: Path) -> set[str]:
    aliases: set[str] = set()
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        first_lines = "\n".join(skill_md.read_text(encoding="utf-8").splitlines()[:8])
        if re.search(r"^description:\s*\"?(?:→|->|Alias for\b)", first_lines, re.IGNORECASE | re.MULTILINE):
            aliases.add(skill_dir.name)
    return aliases


def run_bootstrap_for_skills_json(tmp: Path) -> tuple[Path, Path, str]:
    gemini_home = tmp / "gemini"
    gemini_config = tmp / "gemini-config"
    codex = tmp / "codex"
    bin_dir = tmp / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    scontrol = bin_dir / "scontrol"
    scontrol.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
    scontrol.chmod(0o755)

    env = os.environ | {
        "HOME": str(tmp / "home"),
        "CLAUDE_HOME": str(tmp / "claude"),
        "CODEX_HOME": str(codex),
        "GEMINI_HOME": str(gemini_home),
        "GEMINI_CONFIG_HOME": str(gemini_config),
        "CURSOR_HOME": str(tmp / "cursor"),
        "COPILOT_MEMORY_DIR": str(tmp / "copilot-memory"),
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
    }
    result = subprocess.run(
        ["bash", str(BOOTSTRAP)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return gemini_home, gemini_config, result.stdout


with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    gemini_home, gemini_config, output = run_bootstrap_for_skills_json(tmp / "initial")
    skills_json_file = gemini_config / "skills.json"

    check("skills.json is generated", skills_json_file.is_file())

    try:
        data = json.loads(skills_json_file.read_text(encoding="utf-8"))
        is_valid_json = True
    except Exception:
        data = {}
        is_valid_json = False
    check("skills.json is valid JSON", is_valid_json)

    entries = data.get("entries", [])
    check("skills.json has entries array", isinstance(entries, list) and len(entries) > 0)

    first_entry = entries[0] if entries else {}
    expected_skills_path = str(gemini_home / "skills")
    check("entries[0].path matches GEMINI_DIR/skills", first_entry.get("path") == expected_skills_path)

    exclude_patterns = first_entry.get("exclude", [])
    check("entries[0].exclude is a non-empty list", isinstance(exclude_patterns, list) and len(exclude_patterns) > 0)

    excluded_names = {re.sub(r"^\^|\$$", "", p) for p in exclude_patterns}
    ground_truth_aliases = derive_ground_truth_aliases(ROOT / "skills")

    check("derived exclude set is non-empty (negative control)", len(excluded_names) > 0)
    check(
        f"derived exclude set matches ground-truth alias skills exactly ({len(excluded_names)} == {len(ground_truth_aliases)})",
        excluded_names == ground_truth_aliases,
    )

    # Canonical skills must NOT be excluded
    check("canonical skill 'skill-builder' is not excluded", "skill-builder" not in excluded_names)
    check("canonical skill 'rescue-closed' is not excluded", "rescue-closed" not in excluded_names)
    check("canonical skill 'clean-branches' is not excluded", "clean-branches" not in excluded_names)
    check("canonical skill 'slide-tag' is not excluded", "slide-tag" not in excluded_names)

    # Aliases MUST be excluded
    check("alias 'revive-closed' is excluded", "revive-closed" in excluded_names)
    check("alias 'antigravity-review-workflow' is excluded", "antigravity-review-workflow" in excluded_names)
    check("alias 'do-as-you-think-best' is excluded", "do-as-you-think-best" in excluded_names)
    check("alias 'rct' is excluded", "rct" in excluded_names)
    check("alias 'ts' is excluded", "ts" in excluded_names)
    check("alias 'cb' is excluded", "cb" in excluded_names)

    # Idempotency check: re-running when skills.json exists and registers path
    _, _, output_second = run_bootstrap_for_skills_json(tmp / "initial")
    check("re-running bootstrap reports skills.json already registered", "already registered" in output_second)


# --- worktree resolution (ai-config#1729) -----------------------------------
#
# A linked worktree carries its own `scripts/`, so `REPO_ROOT` resolves to the
# worktree rather than to the checkout `bootstrap.sh` installed from, and every
# `~/.claude` symlink then reads `misdirected` with nothing misinstalled. The
# fixture below is a REAL git repository with a REAL linked worktree, because
# the resolution shells out to `git worktree list` -- a stubbed one would test
# the test rather than the script.


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", *args],
        cwd=repo, capture_output=True, text=True,
    )


def make_worktree_fixture(tmpdir: Path) -> tuple[Path, Path, Path]:
    """A git repo holding this script under scripts/, plus a linked worktree.

    Returns (main_checkout, linked_worktree, consumer_dir). The consumer dir is
    installed the way bootstrap.sh installs it: symlinks into the MAIN
    checkout, which is what makes the worktree run interesting.
    """
    main = tmpdir / "repo"
    (main / "scripts").mkdir(parents=True)
    (main / "scripts" / "check-install.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8",
    )
    write(main / "CLAUDE.md", "root instructions\n")
    write(main / "shared" / "note.md", "shared note\n")

    # No explicit branch is created: `git init`'s default branch name varies by
    # git version and by user config, and `checkout -b main` fails outright when
    # it already matches. Nothing here depends on the name.
    git(main, "init", "-q")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "fixture")

    linked = tmpdir / "linked"
    git(main, "worktree", "add", "-q", str(linked), "-b", "wt")

    # Untracked, so it exists in the main checkout and in NO worktree. This
    # reproduces the second half of ai-config#1729: the worktree run enumerated
    # one entry fewer than the main run (15 versus 16), because a top-level
    # entry is enumerated from the repo side only. It is what makes the
    # entry-count assertion below load-bearing rather than vacuous.
    write(main / "local-only" / "note.md", "untracked local build output\n")

    consumer = tmpdir / "consumer"
    consumer.mkdir()
    os.symlink(main / "CLAUDE.md", consumer / "CLAUDE.md")
    os.symlink(main / "shared", consumer / "shared")
    os.symlink(main / "local-only", consumer / "local-only")
    return main, linked, consumer


def run_from(checkout: Path, consumer: Path, *extra: str) -> subprocess.CompletedProcess:
    """Invoke the copy of the script living inside `checkout`, no --repo-root."""
    return subprocess.run(
        [sys.executable, str(checkout / "scripts" / "check-install.py"),
         "--consumer-dir", str(consumer), *extra],
        capture_output=True, text=True,
    )


with tempfile.TemporaryDirectory() as tmp:
    main_co, linked_co, wt_consumer = make_worktree_fixture(Path(tmp))

    worktree_created = linked_co.is_dir() and (linked_co / "scripts").is_dir()
    check("negative control: the linked worktree fixture was actually created",
          worktree_created)

    # Negative control for the assertion itself. Comparing against the linked
    # worktree explicitly MUST still report misdirected -- that is the bug's
    # signature, and a test that cannot produce it cannot detect its absence.
    forced = run_cli(linked_co, wt_consumer)
    check("negative control: an explicit worktree root still reports misdirected",
          "misdirected" in forced.stdout and "0 misdirected" not in forced.stdout)

    from_main = run_from(main_co, wt_consumer)
    check("main checkout reports no misdirected entries",
          "0 misdirected" in from_main.stdout)

    from_worktree = run_from(linked_co, wt_consumer)
    check("run from a linked worktree reports no misdirected entries",
          "0 misdirected" in from_worktree.stdout)
    def entry_count(stdout: str) -> str:
        return stdout.split("checked ")[-1].split(" installed")[0]

    check("negative control: the main run enumerates the untracked entry",
          entry_count(from_main.stdout) == "4")
    check("run from a linked worktree enumerates the same entries as main",
          entry_count(from_worktree.stdout) == entry_count(from_main.stdout))
    check("run from a linked worktree names the main worktree as its base",
          str(main_co.resolve()) in from_worktree.stdout)
    check("run from a linked worktree says which worktree it is running in",
          "linked worktree" in from_worktree.stdout)
    check("run from the main checkout stays silent about worktrees",
          "linked worktree" not in from_main.stdout)

    # An explicit --repo-root is a deliberate retarget and must be taken
    # literally, or the flag's only purpose is silently defeated.
    explicit = run_from(linked_co, wt_consumer, "--repo-root", str(linked_co))
    check("--repo-root is honoured literally, not resolved to the main worktree",
          "misdirected" in explicit.stdout and "0 misdirected" not in explicit.stdout)

    check("main_worktree() finds the main checkout from a linked worktree",
          ci.main_worktree(linked_co) == main_co.resolve())
    check("main_worktree() is identity from the main checkout",
          ci.main_worktree(main_co) == main_co.resolve())


with tempfile.TemporaryDirectory() as tmp:
    # Outside any repository the answer is not established, so the helper
    # declines rather than guessing, and the caller keeps its own root.
    outside = Path(tmp) / "not-a-repo"
    outside.mkdir()
    check("main_worktree() returns None outside a git repository",
          ci.main_worktree(outside) is None)


with tempfile.TemporaryDirectory() as tmp:
    # `git clone --bare` plus worktrees is a common layout, and the bare
    # repository is itself a listed record -- emitted FIRST. Taking the first
    # record would hand back a `.git` directory as the checkout to compare
    # against, so every entry would read misdirected or foreign: the same
    # symptom this PR fixes, in a different layout.
    root = Path(tmp)
    bare = root / "src.git"
    git(root, "init", "-q", "--bare", str(bare))
    seed = root / "seed"
    seed.mkdir()
    write(seed / "CLAUDE.md", "root instructions\n")
    git(seed, "init", "-q")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "seed")
    git(seed, "remote", "add", "origin", str(bare))
    git(seed, "push", "-q", "origin", "HEAD:refs/heads/seeded")

    bare_wt = root / "from-bare"
    git(bare, "worktree", "add", "-q", str(bare_wt), "seeded")

    # Resolved, because git reports the real path and macOS puts the temp dir
    # behind the /var -> /private/var symlink.
    listing = git(bare_wt, "worktree", "list", "--porcelain").stdout
    listing_is_bare_first = bare_wt.is_dir() and listing.startswith(
        f"worktree {bare.resolve()}\nbare"
    )
    check("negative control: the bare repo really is the first listed record",
          listing_is_bare_first)
    check("main_worktree() skips a bare record rather than returning the .git dir",
          ci.main_worktree(bare_wt) == bare_wt.resolve())


print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
