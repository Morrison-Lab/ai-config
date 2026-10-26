#!/usr/bin/env python3
"""PreToolUse guard: deny `git push` when the repo's own doc checks fail locally.

The incident: lds#1409, lds#1422 and lds#1424 each failed CI's `check-term-links`
or `check-new-line-breaks` within one hour (2026-10-26), though lds
`.claude/project-memory.md` tells every session to run both before pushing prose.
A prose rule that costs a CI round and a reset review on every miss is the case
for a mechanism (`shared/workflow/algorithmatize-checks.md`).

What it does, for each `git push` in the command:

  1. Reads the repo's own caller workflows (`.github/workflows/*.yml`) for jobs
     that `uses:` Morrison-Lab/gha's `check-term-links.yml` or
     `check-new-line-breaks.yml`, and takes their literal `with:` inputs (globs,
     paths-ignore, terms-file, allow-file, clause settings). The repo's CI
     configuration stays the single source; nothing is hard-coded per repo, so
     every notes repo that calls those workflows (lds, sds, pds, mds, rme, psw,
     ids, ...) is covered.
  2. Runs gha's own scripts at the ref the workflow pins (`@v3`) from a cached
     shallow clone in `~/.cache/ai-config/gha/` (refreshed daily; override with
     `GHA_CHECKS_DIR` for a checkout), against `origin/main`.
  3. DENIES the push when either check exits non-zero, naming the findings.

Bypass: prefix the command with `AI_CONFIG_SKIP_PUSH_CHECKS='<reason>'`. The
reason must be real text (not `1`/`true`); every bypass is appended to
`~/.cache/ai-config/push-check-bypass.log` as one JSON line.

Fails OPEN, with a visible systemMessage, when the checker cannot be fetched,
times out, or the base ref is missing: an unverifiable check must not wedge a
push, but it must not pass silently either.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

GHA_URL = "https://github.com/Morrison-Lab/gha.git"
CACHE_ROOT = os.path.join(os.path.expanduser("~"), ".cache", "ai-config")
BYPASS_VAR = "AI_CONFIG_SKIP_PUSH_CHECKS"
BYPASS_LOG = os.path.join(CACHE_ROOT, "push-check-bypass.log")
REFRESH_SECONDS = 24 * 3600
CHECK_TIMEOUT = 60
CLONE_TIMEOUT = 40
SHELL_TOOLS = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# workflow file name -> (script path within gha, env prefix, input -> env suffix)
CHECKS = {
    "check-term-links": {
        "script": "check-term-links/check-term-links.py",
        "prefix": "TERM_LINKS_",
        "inputs": {"globs": "GLOBS", "paths-ignore": "PATHS_IGNORE",
                   "terms-file": "TERMS_FILE", "allow-file": "ALLOW_FILE"},
        "base": "BASE_REF",
        "fail": "FAIL",
    },
    "check-new-line-breaks": {
        "script": "check-new-line-breaks/check-new-line-breaks.py",
        "prefix": "NLB_",
        "inputs": {"globs": "GLOBS", "paths-ignore": "PATHS_IGNORE",
                   "clause-breaks": "CLAUSE_BREAKS",
                   "clause-min-length": "CLAUSE_MIN_LENGTH"},
        "base": "BASE_REF",
        "fail": "FAIL",
        "extra": {"NLB_SCOPE": "committed"},
    },
}

USES = re.compile(
    r"^\s*uses:\s*Morrison-Lab/gha/\.github/workflows/(?P<name>[\w-]+)\.yml@(?P<ref>[\w.\-/]+)",
    re.IGNORECASE,
)
KEY_VALUE = re.compile(r"^(?P<indent>\s*)(?P<key>[\w-]+):\s*(?P<value>.*?)\s*$")


def _load_sibling():
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-push-without-self-review.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("no_push_without_self_review", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


_SIBLING = _load_sibling()


def _git(args, cwd=None, timeout=10):
    try:
        res = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def parse_workflow(text: str) -> list[dict]:
    """Return [{name, ref, inputs}] for each gha check call in a workflow file.

    A minimal line parser, not YAML: it reads `uses:` and the literal scalar
    `with:` entries beneath it, and skips any value containing an expression
    (`${{ ... }}`), whose value only CI can know.
    """
    calls = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = USES.match(line)
        if not m or m.group("name") not in CHECKS:
            continue
        uses_indent = len(line) - len(line.lstrip())
        inputs: dict[str, str] = {}
        in_with = False
        with_indent = -1
        for nxt in lines[i + 1:]:
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                continue
            indent = len(nxt) - len(nxt.lstrip())
            if indent < uses_indent:
                break
            kv = KEY_VALUE.match(nxt)
            if not kv:
                continue
            if not in_with:
                if indent == uses_indent and kv.group("key") == "with":
                    in_with, with_indent = True, indent
                continue
            if indent <= with_indent:
                break
            value = kv.group("value")
            if "${{" in value or not value or value[0] in "|>":
                continue
            quoted = re.match(r"""^(['"])(.*?)\1(?:\s+#.*)?$""", value)
            if quoted:
                value = quoted.group(2)
            else:
                value = re.sub(r"(?:^|\s+)#.*$", "", value).strip()
            if not value:
                continue
            inputs[kv.group("key")] = value
        calls.append({"name": m.group("name"), "ref": m.group("ref"), "inputs": inputs})
    return calls


def find_calls(git_root: str) -> list[dict]:
    wf_dir = os.path.join(git_root, ".github", "workflows")
    if not os.path.isdir(wf_dir):
        return []
    calls: list[dict] = []
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        try:
            with open(os.path.join(wf_dir, name), encoding="utf-8") as fh:
                calls.extend(parse_workflow(fh.read()))
        except OSError:
            continue
    return calls


def ensure_gha(ref: str) -> str | None:
    """Return a gha checkout at `ref`, cloning or refreshing a cache; None on failure."""
    override = os.environ.get("GHA_CHECKS_DIR")
    if override:
        return override if os.path.isdir(override) else None
    dest = os.path.join(CACHE_ROOT, "gha", re.sub(r"[^\w.\-]", "_", ref))
    stamp = os.path.join(dest, ".git", "refreshed")
    try:
        if os.path.isdir(os.path.join(dest, ".git")):
            last = os.path.getmtime(stamp) if os.path.exists(stamp) else 0
            if time.time() - last > REFRESH_SECONDS:
                # Stamp first, so an offline machine retries once a day, not on every push.
                with open(stamp, "w", encoding="utf-8") as fh:
                    fh.write(str(time.time()))
                fetched = subprocess.run(["git", "-C", dest, "fetch", "--depth", "1", "origin", ref],
                                         capture_output=True, timeout=30)
                if fetched.returncode == 0:
                    subprocess.run(["git", "-C", dest, "reset", "--hard", "FETCH_HEAD"],
                                   capture_output=True, timeout=30)
            return dest
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if re.fullmatch(r"[0-9a-f]{40}", ref):
            # A commit pin cannot be a `--branch`: fetch that one commit instead.
            steps = [["git", "init", "-q", dest],
                     ["git", "-C", dest, "fetch", "-q", "--depth", "1", GHA_URL, ref],
                     ["git", "-C", dest, "checkout", "-q", "FETCH_HEAD"]]
        else:
            steps = [["git", "clone", "-q", "--depth", "1", "--branch", ref, GHA_URL, dest]]
        try:
            for step in steps:
                if subprocess.run(step, capture_output=True, timeout=CLONE_TIMEOUT).returncode != 0:
                    raise OSError(f"{step[:3]} failed")
        except (OSError, subprocess.SubprocessError):
            # Never leave a half-built checkout behind: the next run would treat it as a cache.
            shutil.rmtree(dest, ignore_errors=True)
            return None
        return dest
    except (OSError, subprocess.SubprocessError):
        # A failed refresh keeps the stale cache usable.
        return dest if os.path.isdir(os.path.join(dest, ".git")) else None


def resolve_base(git_root: str) -> str | None:
    base = os.environ.get("PUSH_CHECK_BASE_REF", "").strip()
    for cand in ([base] if base else []) + ["origin/main", "origin/master"]:
        if _git(["rev-parse", "--verify", "--quiet", cand + "^{commit}"], cwd=git_root):
            return cand
    return None


def run_check(git_root: str, gha_dir: str, call: dict, base: str):
    """Run one check; return (name, status, output) with status ok|fail|error."""
    spec = CHECKS[call["name"]]
    script = os.path.join(gha_dir, spec["script"])
    if not os.path.isfile(script):
        return call["name"], "error", f"{spec['script']} not found in gha checkout"
    env = dict(os.environ)
    for k, v in call["inputs"].items():
        suffix = spec["inputs"].get(k)
        if suffix:
            env[spec["prefix"] + suffix] = v
    env[spec["prefix"] + spec["base"]] = base
    env[spec["prefix"] + spec["fail"]] = "true"
    env.update(spec.get("extra", {}))
    try:
        proc = subprocess.run([sys.executable, script], capture_output=True, text=True,
                              cwd=git_root, env=env, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return call["name"], "error", f"timed out after {CHECK_TIMEOUT}s"
    except OSError as exc:
        return call["name"], "error", str(exc)
    out = (proc.stdout + proc.stderr).strip()
    return call["name"], ("ok" if proc.returncode == 0 else "fail"), out


def findings(output: str, limit: int = 25) -> str:
    lines = [ln for ln in output.splitlines() if ln.startswith("::error") or ln.startswith("::warning")]
    lines = lines or output.splitlines()[-limit:]
    shown = [f"  {ln}" for ln in lines[:limit]]
    if len(lines) > limit:
        shown.append(f"  ... and {len(lines) - limit} more")
    return "\n".join(shown)


def bypass_reason(env_assignments, command: str) -> str | None:
    value = None
    for assignment in env_assignments or []:
        key, sep, val = assignment.partition("=")
        if sep and key == BYPASS_VAR:
            value = val
    if value is None:
        value = os.environ.get(BYPASS_VAR)
    if value is None:
        return None
    value = value.strip("'\" \t")
    return value if value and value.lower() not in {"1", "0", "true", "false", "yes", "no", "y", "n", "on", "off"} else ""


def log_bypass(git_root: str, reason: str) -> None:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": git_root,
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=git_root),
        "head": _git(["rev-parse", "HEAD"], cwd=git_root),
        "reason": reason,
    }
    try:
        os.makedirs(os.path.dirname(BYPASS_LOG), exist_ok=True)
        with open(BYPASS_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def pushed_other_than_head(argv, git_root: str, head: str | None) -> str | None:
    """Return the first pushed refspec source that resolves to a commit other than HEAD."""
    args = list(argv or [])
    # Everything before the `push` token is git's own options (`-C dir`, `-c k=v`).
    args = args[args.index("push") + 1:] if "push" in args else args
    words = []
    skip = False
    for a in args:
        if skip:
            skip = False
        elif a in ("--repo", "-o", "--push-option", "--receive-pack", "--exec"):
            skip = True
        elif not a.startswith("-"):
            words.append(a)
    for spec in words[1:]:  # words[0] is the remote
        src = spec.lstrip("+").split(":", 1)[0]
        if src in ("", "HEAD"):
            continue
        sha = _git(["rev-parse", "--verify", "--quiet", src + "^{commit}"], cwd=git_root)
        if sha and sha != head:
            return src
    return None


def evaluate(command: str):
    """Return ("deny", reason) | ("note", message) | None."""
    if _SIBLING is None:
        return None
    try:
        pushes = list(_SIBLING.iter_pushes(command))
    except Exception:
        return None
    redirected = getattr(_SIBLING, "REDIRECTED", object())
    notes: list[str] = []
    for env_assign, argv, directory in pushes:
        if directory is redirected:
            continue
        if any(a in ("--delete", "-d") or a.startswith(":") for a in (argv or [])):
            continue
        git_root = _git(["rev-parse", "--show-toplevel"], cwd=directory or os.getcwd())
        if not git_root:
            continue
        calls = find_calls(git_root)
        if not calls:
            continue
        reason = bypass_reason(env_assign, command)
        if reason is not None:
            if not reason:
                return "deny", (
                    f"{BYPASS_VAR} needs a reason, not a flag: "
                    f"{BYPASS_VAR}='why the doc checks cannot run here' git push ..."
                )
            log_bypass(git_root, reason)
            notes.append(f"Doc checks bypassed for this push ({reason}); logged to {BYPASS_LOG}.")
            continue
        base = resolve_base(git_root)
        if not base:
            notes.append("Doc checks skipped: no origin/main to diff against (fetch it, then push).")
            continue
        head = _git(["rev-parse", "HEAD"], cwd=git_root)
        other = pushed_other_than_head(argv, git_root, head)
        if other:
            notes.append(f"Doc checks skipped: this push ships `{other}`, not HEAD, and the checks read HEAD.")
            continue
        if head and head == _git(["rev-parse", base + "^{commit}"], cwd=git_root):
            continue
        by_ref: dict[str, str | None] = {}
        runnable = []
        for call in calls:
            if call["ref"] not in by_ref:
                by_ref[call["ref"]] = ensure_gha(call["ref"])
            if by_ref[call["ref"]]:
                runnable.append((call, by_ref[call["ref"]]))
            else:
                notes.append(f"{call['name']} skipped: could not fetch gha@{call['ref']}.")
        with ThreadPoolExecutor(max_workers=max(1, len(runnable))) as pool:
            results = list(pool.map(lambda cg: run_check(git_root, cg[1], cg[0], base), runnable))
        failed = [(n, out) for n, status, out in results if status == "fail"]
        for n, status, out in results:
            if status == "error":
                notes.append(f"{n} could not run locally ({out}); CI will still run it.")
        if failed:
            body = "\n\n".join(f"{n} failed against {base}:\n{findings(out)}" for n, out in failed)
            return "deny", (
                f"This push would fail CI. The repo's own doc checks fail locally:\n\n{body}\n\n"
                "Fix every finding, commit, and push once. To run them again by hand, use the "
                "inputs in the repo's `.github/workflows/check-*.yml` with gha's scripts "
                f"(cached under {os.path.join(CACHE_ROOT, 'gha')}). If a check cannot run here, "
                f"prefix the push with {BYPASS_VAR}='<reason>' (logged)."
            )
    return ("note", " ".join(notes)) if notes else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"no-push-with-failing-notes-checks: unreadable hook input ({exc})", file=sys.stderr)
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") not in SHELL_TOOLS:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command") or tool_input.get("CommandLine") or tool_input.get("cmd")
    if not isinstance(command, str) or "push" not in command:
        return 0
    try:
        verdict = evaluate(command)
    except Exception as exc:
        print(f"no-push-with-failing-notes-checks: evaluation failed ({exc})", file=sys.stderr)
        return 0
    if verdict is None:
        return 0
    kind, text = verdict
    hso = {"hookEventName": "PreToolUse"}
    if kind == "deny":
        hso["permissionDecision"] = "deny"
        hso["permissionDecisionReason"] = text
        print(json.dumps({"hookSpecificOutput": hso}))
    else:
        hso["additionalContext"] = text
        print(json.dumps({"hookSpecificOutput": hso, "systemMessage": text}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
