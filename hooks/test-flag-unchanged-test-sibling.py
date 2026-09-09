#!/usr/bin/env python3
"""Tests for flag-unchanged-test-sibling.py.

Mutation-tested per `shared/workflow/algorithmatize-checks.md`. Two controls
carry most of the weight:

* a **negative control** on a real repository where the test sibling IS
  staged, so a guard that fired unconditionally would be caught;
* the **originating incident** replayed from ai-config#3415, with the exact
  separator mismatch (`check-tui-alloc-readme.py` against
  `test_check_tui_alloc_readme.py`) that defeated the original search. A
  guard that compared stems literally would pass every other test here and
  fail that one, which is the whole point of including it.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks/flag-unchanged-test-sibling.py"

failures = []
total = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global total
    total += 1
    print(f"{'ok' if cond else 'FAIL':4} {name}"
          + (f" -- {detail}" if not cond else ""))
    if not cond:
        failures.append(name)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


def make_repo(tmp: Path, files: dict[str, str], stage: list[str],
              untracked: dict[str, str] | None = None) -> Path:
    """A repo whose `files` are committed then re-dirtied, with `stage`
    staged. `untracked` files are written and never added, which is the
    brand-new-test case: `git ls-files` alone cannot see them."""
    repo = tmp / f"r{len(list(tmp.iterdir()))}"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    for path, body in files.items():
        f = repo / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    # Now dirty and stage only the named subset.
    for path in files:
        (repo / path).write_text(files[path] + "\n# edit\n", encoding="utf-8")
    git(repo, "reset", "-q")
    for path in stage:
        git(repo, "add", path)
    for path, body in (untracked or {}).items():
        f = repo / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    return repo


def run(repo: Path, command: str = "git commit -m x") -> dict:
    payload = {"tool_input": {"command": command}, "cwd": str(repo)}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True)
    if not r.stdout.strip():
        return {}
    return json.loads(r.stdout)


def fired(out: dict) -> bool:
    return bool(
        (out.get("hookSpecificOutput") or {}).get("additionalContext"))


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1. The originating incident: hyphenated subject, underscored test.
        # A literal stem comparison fails only this case.
        files = {
            "scripts/check-tui-alloc-readme.py": "print(1)",
            "scripts/test_check_tui_alloc_readme.py": "print(2)",
        }
        repo = make_repo(tmp, files, ["scripts/check-tui-alloc-readme.py"])
        out = run(repo)
        check("separator mismatch: subject staged, test not -- fires",
              fired(out), json.dumps(out))
        check("names the test file it wants read",
              "test_check_tui_alloc_readme.py"
              in json.dumps(out), json.dumps(out))

        # 2. NEGATIVE CONTROL: same repo, test staged too. A guard that
        # fired unconditionally would pass test 1 and fail here.
        repo = make_repo(tmp, files, list(files))
        out = run(repo)
        check("negative control: test staged too -- silent", not fired(out),
              json.dumps(out))

        # 3. No test sibling exists at all -- silent, not a false alarm.
        repo = make_repo(tmp, {"scripts/lonely.py": "print(1)"},
                         ["scripts/lonely.py"])
        check("no sibling in the repo -- silent", not fired(run(repo)))

        # 4. Staging only the test file must not fire on itself.
        repo = make_repo(tmp, files,
                         ["scripts/test_check_tui_alloc_readme.py"])
        check("staging only the test -- silent", not fired(run(repo)))

        # 4b. A staged TEST file must not be read as a subject in its own
        # right. Test 4 alone does not reach that line: with no
        # `test_test_*` in the repo there is nothing for it to pair with
        # either way, so the exclusion survives its removal. This is the
        # repo that tells them apart.
        nested = {"scripts/test_a.py": "1",
                  "scripts/test_test_a.py": "2"}
        repo = make_repo(tmp, nested, ["scripts/test_a.py"])
        check("staged test file is not itself treated as a subject",
              not fired(run(repo)), json.dumps(run(repo)))

        # 4c. The commonest real "forgot the test" shape: the test is
        # brand new and never `git add`-ed. `git ls-files` lists only
        # tracked paths, so a tracked-only listing is blind to exactly the
        # case this guard is most for (caught in review on #3421).
        repo = make_repo(tmp, {"scripts/subject.py": "1"},
                         ["scripts/subject.py"],
                         untracked={"scripts/test_subject.py": "2"})
        out = run(repo)
        check("untracked brand-new test sibling still warns", fired(out),
              json.dumps(out))

        # 4d. An IGNORED file is not a test someone forgot to stage.
        repo = make_repo(tmp, {"scripts/subject.py": "1",
                               ".gitignore": "scripts/test_subject.py\n"},
                         ["scripts/subject.py"],
                         untracked={"scripts/test_subject.py": "2"})
        check("ignored sibling does not warn", not fired(run(repo)))

        # 5. Trailing-form name, which this corpus also uses.
        trailing = {"scripts/thing.py": "print(1)",
                    "scripts/thing-test.py": "print(2)"}
        repo = make_repo(tmp, trailing, ["scripts/thing.py"])
        check("trailing <stem>-test form -- fires", fired(run(repo)))

        # 6. A sibling in a DIFFERENT directory is not this file's test.
        other = {"scripts/thing.py": "print(1)",
                 "other/test_thing.py": "print(2)"}
        repo = make_repo(tmp, other, ["scripts/thing.py"])
        check("test in another directory -- silent", not fired(run(repo)))

        # 7. Non-code subjects have no test sibling to name.
        docs = {"docs/thing.md": "x", "docs/test_thing.md": "y"}
        repo = make_repo(tmp, docs, ["docs/thing.md"])
        check("markdown subject -- silent", not fired(run(repo)))

        # 8. Command gating: only a git commit is inspected.
        repo = make_repo(tmp, files, ["scripts/check-tui-alloc-readme.py"])
        check("non-commit command -- silent",
              not fired(run(repo, "git status")))
        check("commit inside a compound -- fires",
              fired(run(repo, "git add -A && git commit -m x")))
        check("committish word that is not the subcommand -- silent",
              not fired(run(repo, "git log --grep=commit")))

        # 8b. A cwd that does not exist raises FileNotFoundError from
        # Popen rather than returning non-zero, so a returncode-only guard
        # would crash and take the commit down with it. Hooks fail open.
        payload = {"tool_input": {"command": "git commit -m x"},
                   "cwd": str(tmp / "definitely-absent")}
        r = subprocess.run([sys.executable, str(HOOK)],
                           input=json.dumps(payload),
                           capture_output=True, text=True)
        check("missing cwd fails open, exit 0", r.returncode == 0,
              f"rc={r.returncode} err={r.stderr[:200]!r}")

        # 9. Several unstaged siblings are all reported.
        many = {"scripts/a.py": "1", "scripts/test_a.py": "2",
                "scripts/b.py": "3", "scripts/test_b.py": "4"}
        repo = make_repo(tmp, many, ["scripts/a.py", "scripts/b.py"])
        out = run(repo)
        blob = json.dumps(out)
        check("both unstaged siblings named",
              "test_a.py" in blob and "test_b.py" in blob, blob)

    print(f"{total - len(failures)}/{total} checks passed")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
