#!/usr/bin/env python3
"""Regression tests for check-install.py.

Builds a synthetic repo and consumer directory containing one entry of every
classification, so the tests never touch a real `~/.claude`.
"""
import importlib.util
import json
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
    check("consumer-only file is foreign", found.get("skills/index.json") == "foreign")

    # The headline improvement over the SKILL.md-only sweep: beta is stale
    # even though the file that sweep compared is byte-identical.
    same_skill_md = (
        (repo / "skills" / "beta" / "SKILL.md").read_bytes()
        == (consumer / "skills" / "beta" / "SKILL.md").read_bytes()
    )
    check("supporting-file drift is caught with SKILL.md identical",
          same_skill_md and found.get("skills/beta") == "stale")

    check("excluded dirs are never reported",
          not any(k.startswith(("references", "codex-skills")) for k in found))
    check("repo README is never reported", "README.md" not in found)

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
    check("foreign file is left alone", (consumer / "skills" / "index.json").is_file())
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
          and after.get("skills/zeta") == "foreign")
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

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
