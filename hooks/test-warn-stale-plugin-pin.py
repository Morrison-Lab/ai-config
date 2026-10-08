#!/usr/bin/env python3
"""Tests for hooks/warn-stale-plugin-pin.py (ai-config#2439).

Builds a fake `~/.claude/plugins` (a three-commit marketplace clone plus an
`installed_plugins.json`) under a temp dir, points the hook at it through
`AI_CONFIG_PLUGINS_DIR`, and runs the hook as a subprocess:

  1. A user-scope pin two commits behind: warns, counts 2, and gives the
     user-scope update command with no --scope flag.
  2. A user-scope pin at the clone's HEAD: silent.
  3. A project-scope pin behind, session in a subdirectory of its
     projectPath: warns with --scope project.
  4. Negative control: a stale project pin for a DIFFERENT project: silent.
  5. Negative control: a stale pin for another plugin in the same
     marketplace: silent.
  6. A pin the clone does not contain: warns, says the count is unknown.
  6b. A non-object `plugins` value: exit 0, stderr says so.
  6c. A pin AHEAD of the clone (the clone is the stale one): silent.
  7. No installed_plugins.json: silent, exit 0.
  8. Malformed installed_plugins.json: exit 0, nothing on stdout, stderr
     names the file.
  9. No marketplace clone: exit 0, nothing on stdout, stderr says so.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(sys.argv[1] if len(sys.argv) > 1 else
            os.path.join(os.path.dirname(__file__), "warn-stale-plugin-pin.py"))

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        failures.append(name)
        print(f"FAIL {name} {detail}")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True,
        capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    ).stdout.strip()


def make_root(tmp):
    root = tmp / "plugins"
    mkt = root / "marketplaces" / "Morrison-Lab"
    mkt.mkdir(parents=True)
    git(mkt, "init", "-q", "-b", "main")
    shas = []
    for i in range(3):
        (mkt / "f").write_text(str(i), encoding="utf-8")
        git(mkt, "add", "f")
        git(mkt, "commit", "-q", "-m", f"c{i}")
        shas.append(git(mkt, "rev-parse", "HEAD"))
    return root, shas


def run(root, record, cwd):
    if record is not None:
        path = root / "installed_plugins.json"
        path.write_text(record if isinstance(record, str) else json.dumps(record), encoding="utf-8")
    env = {**os.environ, "AI_CONFIG_PLUGINS_DIR": str(root)}
    env.pop("CLAUDE_PROJECT_DIR", None)
    out = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps({"cwd": str(cwd)}),
        capture_output=True, text=True, env=env,
    )
    context = ""
    if out.stdout.strip():
        context = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    return out.returncode, context, out.stderr


def record(*entries, key="ai-config@Morrison-Lab"):
    return {"version": 2, "plugins": {key: list(entries)}}


def main():
    tmp = Path(tempfile.mkdtemp())
    try:
        root, shas = make_root(tmp)
        project = tmp / "proj"
        (project / "sub").mkdir(parents=True)
        other = tmp / "other"
        other.mkdir()

        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": shas[0]}), project)
        check("1 stale user pin warns", rc == 0 and "STALE PLUGIN PIN" in ctx, ctx)
        check("1 counts two commits", "2 commit(s)" in ctx, ctx)
        check("1 user command has no scope flag",
              "`claude plugin update ai-config@Morrison-Lab`" in ctx, ctx)

        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project)
        check("2 current user pin is silent", rc == 0 and ctx == "", ctx)

        rc, ctx, _ = run(root, record({"scope": "project", "projectPath": str(project),
                                       "gitCommitSha": shas[1]}), project / "sub")
        check("3 stale project pin warns with scope",
              "--scope project" in ctx and "1 commit(s)" in ctx, ctx)

        rc, ctx, _ = run(root, record({"scope": "project", "projectPath": str(other),
                                       "gitCommitSha": shas[0]}), project)
        check("4 other project's pin is silent", rc == 0 and ctx == "", ctx)

        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": shas[0]},
                                      key="other-plugin@Morrison-Lab"), project)
        check("5 other plugin is silent", rc == 0 and ctx == "", ctx)

        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": "f" * 40}), project)
        check("6 unknown pin warns with unknown count",
              "unknown number of commits" in ctx, ctx)

        rc, ctx, err = run(root, {"version": 2, "plugins": []}, project)
        check("6b non-object plugins reports on stderr",
              rc == 0 and ctx == "" and "not an object" in err, err)

        git(root / "marketplaces" / "Morrison-Lab", "reset", "-q", "--hard", shas[1])
        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project)
        check("6c pin ahead of the clone is silent", rc == 0 and ctx == "", ctx)
        git(root / "marketplaces" / "Morrison-Lab", "reset", "-q", "--hard", shas[2])

        (root / "installed_plugins.json").unlink()
        rc, ctx, err = run(root, None, project)
        check("7 no record is silent", rc == 0 and ctx == "" and err == "", err)

        rc, ctx, err = run(root, "{not json", project)
        check("8 malformed record reports on stderr",
              rc == 0 and ctx == "" and "installed_plugins.json" in err, err)

        shutil.rmtree(root / "marketplaces")
        rc, ctx, err = run(root, record({"scope": "user", "gitCommitSha": shas[0]}), project)
        check("9 missing clone reports on stderr",
              rc == 0 and ctx == "" and "cannot compare" in err, err)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        print(f"{len(failures)} failure(s): {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
