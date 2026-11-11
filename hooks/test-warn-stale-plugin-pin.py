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

With a bare repository as the clone's `origin` (ai-config#5309 step 2):

  10. Origin ahead of the clone, pin at the clone's HEAD: warns that the
      clone has not been updated, naming origin's tip.
  11. Pin at origin's tip, clone behind it: silent.
  12. Pin behind the clone, clone behind origin: warns with the count and
      says the clone itself lags origin.
  13. Case 10 with AI_CONFIG_NO_REMOTE_CHECK=1: silent.
  14. Case 10 with CLAUDE_CODE_REMOTE=true: silent, since the cloud
      refresh hook updates the user-scope pin.
  14b. Case 14 with AI_CONFIG_NO_AUTO_REFRESH=1: warns, since nothing
      refreshes the pin.
  14c. Case 16's project pin with CLAUDE_CODE_REMOTE=true: warns, since the
      refresh hook leaves project pins alone.
  16. Project-scope pin at the clone's HEAD, clone behind origin: warns
      with --scope project.
  17. No recorded commit, clone behind origin: warns.
  18. Pin ahead of a clone that lags origin: says "ahead of", not
      "matching".
  19. Clone ahead of origin (origin's tip is its ancestor), pin at HEAD:
      silent.
  19b. Same clone, pin at origin's tip: warns that the pin is one commit
      behind the clone, although it contains origin's tip.
  20. Clone at origin's tip, pin behind: warns with the count and does not
      say the clone lags.
  22. Pin that descends from origin's tip, clone behind origin: silent.
  23. Case 10 with no time budget left (AI_CONFIG_REMOTE_BUDGET=0): origin
      is not read, stderr says so, and the clone alone is compared.
  15. Origin unreachable: falls back to the clone, says so on stderr, and
      passes git's own error through.
  21. Origin unreachable and no applicable entry: origin is not read, so
      stderr is empty.
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


def run(root, record, cwd, **extra):
    if record is not None:
        path = root / "installed_plugins.json"
        path.write_text(record if isinstance(record, str) else json.dumps(record), encoding="utf-8")
    env = {**os.environ, "AI_CONFIG_PLUGINS_DIR": str(root)}
    for name in ("CLAUDE_PROJECT_DIR", "CLAUDE_CODE_REMOTE",
                 "AI_CONFIG_NO_REMOTE_CHECK", "AI_CONFIG_NO_AUTO_REFRESH",
                 "AI_CONFIG_REMOTE_BUDGET"):
        env.pop(name, None)
    env.update(extra)
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

        mkt = root / "marketplaces" / "Morrison-Lab"
        origin = tmp / "origin.git"
        subprocess.run(["git", "clone", "-q", "--bare", "-b", "main", str(mkt), str(origin)],
                       check=True, capture_output=True)
        git(mkt, "remote", "add", "origin", str(origin))
        work = tmp / "work"
        subprocess.run(["git", "clone", "-q", "-b", "main", str(origin), str(work)],
                       check=True, capture_output=True)
        (work / "f").write_text("3", encoding="utf-8")
        git(work, "commit", "-q", "-am", "c3")
        git(work, "push", "-q", "origin", "HEAD:main")
        tip = git(work, "rev-parse", "HEAD")

        rc, ctx, err = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project)
        check("10 clone behind origin warns",
              rc == 0 and "has not been updated" in ctx and tip[:12] in ctx, ctx)
        check("10 a tip missing from the clone prints no git error", err == "", err)

        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": tip}), project)
        check("11 pin at origin's tip is silent", rc == 0 and ctx == "", ctx)

        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": shas[0]}), project)
        check("12 pin and clone both behind",
              "2 commit(s)" in ctx and "itself lags origin" in ctx, ctx)

        rc, ctx, err = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project,
                           AI_CONFIG_NO_REMOTE_CHECK="1")
        check("13 opt-out skips the remote read", rc == 0 and ctx == "" and err == "",
              ctx + err)

        rc, ctx, err = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project,
                           CLAUDE_CODE_REMOTE="true")
        check("14 cloud session skips the remote read", rc == 0 and ctx == "" and err == "",
              ctx + err)

        rc, ctx, err = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project,
                           AI_CONFIG_REMOTE_BUDGET="0")
        check("23 spent budget skips the remote read",
              rc == 0 and ctx == "" and "no time left to read origin" in err, err)

        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project,
                         CLAUDE_CODE_REMOTE="true", AI_CONFIG_NO_AUTO_REFRESH="1")
        check("14b cloud without refresh reads origin", "has not been updated" in ctx, ctx)

        rc, ctx, _ = run(root, record({"scope": "project", "projectPath": str(project),
                                       "gitCommitSha": shas[2]}), project / "sub",
                         CLAUDE_CODE_REMOTE="true")
        check("14c cloud still reads origin for a project pin",
              "--scope project" in ctx and "has not been updated" in ctx, ctx)

        rc, ctx, _ = run(root, record({"scope": "project", "projectPath": str(project),
                                       "gitCommitSha": shas[2]}), project / "sub")
        check("16 lagging clone warns a project pin",
              "--scope project" in ctx and "has not been updated" in ctx, ctx)

        rc, ctx, _ = run(root, record({"scope": "user"}), project)
        check("17 no recorded commit warns", "no recorded commit" in ctx, ctx)

        git(mkt, "reset", "-q", "--hard", shas[1])
        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project)
        check("18 pin ahead of a lagging clone says so",
              "ahead of the marketplace clone" in ctx and "matching" not in ctx, ctx)
        git(mkt, "reset", "-q", "--hard", shas[2])

        git(mkt, "fetch", "-q", "origin")
        git(mkt, "reset", "-q", "--hard", tip)
        (mkt / "f").write_text("4", encoding="utf-8")
        git(mkt, "commit", "-q", "-am", "c4")
        ahead = git(mkt, "rev-parse", "HEAD")
        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": ahead}), project)
        check("19 clone ahead of origin is silent", rc == 0 and ctx == "", ctx)

        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": tip}), project)
        check("19b pin at origin's tip, behind a clone ahead of origin, warns",
              "1 commit(s) behind the marketplace clone" in ctx, ctx)

        git(mkt, "reset", "-q", "--hard", tip)
        rc, ctx, err = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project)
        check("20 clone at origin's tip, pin behind",
              "1 commit(s)" in ctx and "lags origin" not in ctx and err == "", ctx + err)

        git(mkt, "reset", "-q", "--hard", shas[2])
        rc, ctx, _ = run(root, record({"scope": "user", "gitCommitSha": ahead}), project)
        check("22 pin descending from origin's tip is silent", rc == 0 and ctx == "", ctx)

        shutil.rmtree(origin)
        rc, ctx, err = run(root, record({"scope": "user", "gitCommitSha": shas[2]}), project)
        check("15 unreachable origin falls back to the clone",
              rc == 0 and ctx == "" and "compared with the local clone only" in err, err)
        check("15 passes git's error through", "git ls-remote origin HEAD" in err, err)

        rc, ctx, err = run(root, record({"scope": "project", "projectPath": str(other),
                                       "gitCommitSha": shas[0]}), project)
        check("21 no applicable entry reads no origin", rc == 0 and ctx == "" and err == "", err)

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
