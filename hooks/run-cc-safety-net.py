#!/usr/bin/env python3
"""PreToolUse guard: run the pinned CC Safety Net release on every tool call.

CC Safety Net (https://github.com/kenryu42/cc-safety-net, MIT) parses a
command and refuses destructive ones: `rm -rf` of the root, the home
directory or the current tree, `git reset --hard`, `git push --force`,
`git clean -f`, `git stash clear`, `git branch -D`, `curl ... | bash`,
`dd` and `mkfs` on a device, and reads of SSH keys, `.env` files and cloud
credentials, including inside `bash -c` or `python -c`. Ezra chose to adopt
it as the base layer for every agent, with ai-config hooks only for the
gaps it leaves (ai-config#5317, #5474, 2026-11-12).

This hook runs the release `cc-safety-net.pin.json` names, never a newer
one. On the first call on a machine it fetches that release's npm tarball
with `npm pack --ignore-scripts`, checks the tarball's sha512 against the
pinned `integrity`, and unpacks it into
`${XDG_CACHE_HOME:-~/.cache}/ai-config/cc-safety-net/<version>/`. The
package has no runtime dependencies, so nothing else is installed and no
package script runs. Each call then hands the hook payload to
`node <package>/dist/bin/cc-safety-net.js hook --coding-cli` and passes
its answer through unchanged: a deny is a deny.

The catalog reaches Claude Code directly and Codex, Cursor and Antigravity
through their adapters, so this one entry covers every agent ai-config
configures.

FAILS OPEN, VISIBLY, when CC Safety Net cannot run: no `node` (it needs
Node.js 22 or later), no `npm` for the first fetch, a failed or mismatched
download, a crash, or a timeout. The tool call then proceeds and the agent
is told, once per session, that the base guard did not run and why. The
ai-config guards around it still run. Failing closed instead would stop
every tool call on a machine without Node.js.

A failed fetch is recorded in the cache, and no fetch is tried again for
`FETCH_BACKOFF` seconds, so a machine that cannot reach the npm registry
pays the fetch's wait once an hour rather than on every tool call.

A tarball whose sha512 differs from the pin is never unpacked or run.

The child runs with `CC_SAFETY_NET_PROJECT_TIGHTEN_ONLY=1`, so a
`.cc-safety-net/policy.json` committed to a repository the agent works in
can add blocks but cannot turn any off.

Set `AI_CONFIG_CC_SAFETY_NET=off` in the agent's environment to turn the
hook off. It must be set where the agent starts, since a variable set on a
command line never reaches the hook. `AI_CONFIG_CC_SAFETY_NET_CACHE`
overrides the cache directory (the self-test uses it).

The child runs with `CC_SAFETY_NET_NO_UPDATE_CHECK=1`. CC Safety Net keeps
its own audit log of each decision, with secrets redacted, in
`~/.cc-safety-net/logs/` (mode 0600).

To move the pin: pick a release, run `hooks/test-run-cc-safety-net.py`
with `CC_SAFETY_NET_LIVE=1` against it, compare its blocked-command list
with the gaps recorded on #5317, then set `version` and `integrity`
together.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN_FILE = HERE / "cc-safety-net.pin.json"
OFF_VAR = "AI_CONFIG_CC_SAFETY_NET"
CACHE_VAR = "AI_CONFIG_CC_SAFETY_NET_CACHE"
FETCH_TIMEOUT = 120
FETCH_BACKOFF = 3600
RUN_TIMEOUT = 30
CHILD_ENV = {
    "CC_SAFETY_NET_NO_UPDATE_CHECK": "1",
    "CC_SAFETY_NET_PROJECT_TIGHTEN_ONLY": "1",
}


class Unavailable(Exception):
    """CC Safety Net cannot run; the message says why."""


def cache_root() -> Path:
    override = os.environ.get(CACHE_VAR)
    if override:
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "ai-config" / "cc-safety-net"


def load_pin() -> dict:
    pin = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    for key in ("package", "version", "integrity"):
        if not isinstance(pin.get(key), str) or not pin[key]:
            raise Unavailable(f"{PIN_FILE.name} has no {key}")
    if not pin["integrity"].startswith("sha512-"):
        raise Unavailable(f"{PIN_FILE.name} integrity is not sha512")
    return pin


def sha512_integrity(path: Path) -> str:
    digest = hashlib.sha512(path.read_bytes()).digest()
    return "sha512-" + base64.b64encode(digest).decode("ascii")


def fetch_tarball(pin: dict, dest: Path) -> Path:
    npm = shutil.which("npm")
    if not npm:
        raise Unavailable("npm is not on PATH, so the pinned release cannot be fetched")
    spec = f"{pin['package']}@{pin['version']}"
    try:
        proc = subprocess.run(
            [npm, "pack", spec, "--ignore-scripts", "--loglevel=error",
             "--pack-destination", str(dest)],
            capture_output=True, text=True, timeout=FETCH_TIMEOUT, cwd=dest,
        )
    except subprocess.TimeoutExpired:
        raise Unavailable(f"npm pack {spec} timed out after {FETCH_TIMEOUT}s") from None
    if proc.returncode != 0:
        raise Unavailable(f"npm pack {spec} failed: {npm_reason(proc)}")
    tarballs = sorted(dest.glob("*.tgz"))
    if len(tarballs) != 1:
        raise Unavailable(f"npm pack {spec} left {len(tarballs)} tarballs, expected 1")
    return tarballs[0]


def npm_reason(proc: subprocess.CompletedProcess) -> str:
    """The line of npm's output that names the error, such as a FetchError."""
    lines = [line.strip() for line in (proc.stderr or proc.stdout or "").splitlines()]
    lines = [line for line in lines if line]
    named = [line for line in lines if "Error:" in line]
    return (named or lines or [f"exit {proc.returncode}, no output"])[0][:300]


def unpack(tarball: Path, dest: Path) -> None:
    with tarfile.open(tarball, "r:gz") as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
            return
        root = dest.resolve()
        for member in tar.getmembers():
            target = (dest / member.name).resolve()
            if root not in target.parents or not (member.isfile() or member.isdir()):
                raise Unavailable(f"tarball member {member.name!r} is unsafe")
        tar.extractall(dest)


def install(pin: dict, version_dir: Path) -> None:
    version_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=version_dir.parent))
    try:
        tarball = fetch_tarball(pin, staging)
        got = sha512_integrity(tarball)
        if got != pin["integrity"]:
            raise Unavailable(
                f"the downloaded {pin['package']}@{pin['version']} tarball has "
                f"integrity {got}, not the pinned {pin['integrity']}; it was not run")
        unpacked = staging / "unpacked"
        unpacked.mkdir()
        unpack(tarball, unpacked)
        (unpacked / "INTEGRITY").write_text(pin["integrity"] + "\n", encoding="utf-8")
        try:
            os.rename(unpacked, version_dir)
        except OSError:
            if not ready(version_dir, pin):
                raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def ready(version_dir: Path, pin: dict) -> bool:
    marker = version_dir / "INTEGRITY"
    entry = version_dir / "package" / "dist" / "bin" / "cc-safety-net.js"
    return (marker.is_file() and entry.is_file()
            and marker.read_text(encoding="utf-8").strip() == pin["integrity"])


def entry_point(pin: dict) -> Path:
    version_dir = cache_root() / pin["version"]
    if not ready(version_dir, pin):
        if version_dir.exists():
            raise Unavailable(
                f"{version_dir} exists but does not hold the pinned release; "
                "remove it so the hook can fetch the release again")
        failed = version_dir.with_name(version_dir.name + ".fetch-failed")
        recent_failure(failed)
        try:
            install(pin, version_dir)
        except Unavailable as exc:
            record_failure(failed, str(exc))
            raise
        failed.unlink(missing_ok=True)
    return version_dir / "package" / "dist" / "bin" / "cc-safety-net.js"


def recent_failure(failed: Path) -> None:
    """Raise the recorded reason if a fetch failed under FETCH_BACKOFF ago."""
    try:
        record = json.loads(failed.read_text(encoding="utf-8"))
        age = time.time() - float(record["time"])
        reason = str(record["reason"])
    except (OSError, ValueError, KeyError, TypeError):
        return
    if 0 <= age < FETCH_BACKOFF:
        wait = int(FETCH_BACKOFF - age) // 60 + 1
        raise Unavailable(f"{reason} (fetch not retried for another {wait} min; "
                          f"delete {failed} to retry now)")


def record_failure(failed: Path, reason: str) -> None:
    try:
        failed.write_text(json.dumps({"time": time.time(), "reason": reason}),
                          encoding="utf-8")
    except OSError:
        pass


def run(entry: Path, payload: bytes) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    if not node:
        raise Unavailable("node is not on PATH (CC Safety Net needs Node.js 22 or later)")
    env = dict(os.environ, **CHILD_ENV)
    try:
        proc = subprocess.run(
            [node, str(entry), "hook", "--coding-cli"],
            input=payload, capture_output=True, timeout=RUN_TIMEOUT, env=env,
        )
    except subprocess.TimeoutExpired:
        raise Unavailable(f"CC Safety Net timed out after {RUN_TIMEOUT}s") from None
    if proc.returncode not in (0, 2):
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["no output"]
        raise Unavailable(f"CC Safety Net exited {proc.returncode}: {tail[0]}")
    return proc


def warn_once(session_id: str, why: str) -> None:
    """Tell the agent the base guard did not run, once per session."""
    key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    marker = cache_root() / "warned" / key
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        with open(marker, "x", encoding="utf-8"):
            pass
    except FileExistsError:
        return
    except OSError:
        pass
    message = (
        "hooks/run-cc-safety-net.py: the CC Safety Net base guard did not run "
        f"on this tool call, so its checks were skipped: {why}. The other "
        "ai-config guards still ran. Fix the cause before relying on it "
        "(ai-config#5474); this note appears once per session.")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": message}}))


def main() -> int:
    payload = sys.stdin.buffer.read()
    if os.environ.get(OFF_VAR, "").lower() == "off":
        return 0
    try:
        session_id = str(json.loads(payload or b"{}").get("session_id") or "unknown")
    except (ValueError, AttributeError):
        session_id = "unknown"
    try:
        proc = run(entry_point(load_pin()), payload)
    except (Unavailable, OSError, ValueError, tarfile.TarError) as exc:
        warn_once(session_id, str(exc))
        return 0
    sys.stdout.buffer.write(proc.stdout)
    sys.stderr.buffer.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
