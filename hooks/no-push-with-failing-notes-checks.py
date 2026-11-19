#!/usr/bin/env python3
"""PreToolUse guard: deny `git push` when the repo's own doc checks fail locally.

The incident: lds#1409, lds#1422 and lds#1424 each failed CI's `check-term-links`
or `check-new-line-breaks` within one hour (2026-10-26), though lds
`.claude/project-memory.md` tells every session to run both before pushing prose.
A prose rule that costs a CI round and a reset review on every miss is the case
for a mechanism (`shared/workflow/algorithmatize-checks.md`).

What it does, for each `git push` in the command:

  1. Reads the repo's own caller workflows (`.github/workflows/*.yml`) for jobs
     that `uses:` Morrison-Lab/gha's `check-term-links.yml`,
     `check-new-line-breaks.yml` or `check-title-references.yml` (added after
     lds#2793 failed CI on it, 2026-11-18), and takes their literal `with:` inputs (globs,
     paths-ignore, terms-file, allow-file, clause settings). The repo's CI
     configuration stays the single source; nothing is hard-coded per repo, so
     every repo that calls those workflows is covered (as of 2026-10-26: lds,
     sds, pds, mds and rme; psw and ids once they adopt the two checks).
     It also runs each diff-scoped `.gha/run-check/run-check.sh` line of a
     bundled-checks workflow such as lds's `cluster-checks.yml` (ai-config#4986).
  2. Runs gha's own scripts at the ref the workflow pins (`@v3`) from a cached
     shallow clone in `~/.cache/ai-config/gha/` (refetched whenever `git ls-remote`
     shows the tag or branch moved, since `v3` slides; the daily stamp is the
     offline fallback; override with `GHA_CHECKS_DIR` for a checkout), against
     `origin/main`.
  3. DENIES the push when any check exits non-zero, naming the findings. A
     check's `fail: false` is honored, except in a repo that also calls gha's
     annotation gate, which fails CI on the warnings a non-failing check emits.

`check-term-links` also learns terms from the prerequisite sites (mds, pds, sds, ...),
as CI does through its `terms-dirs` input. The hook picks the same sites per repository
(`TERMS_FROM_DEFAULTS`, mirroring gha's `check-term-links.yml`; a literal `terms-from`
in the caller workflow overrides it), shallow-clones them into
`~/.cache/ai-config/terms-from/`, and passes them as `TERM_LINKS_TERMS_DIRS`. Without
them the hook knew 823 terms to CI's 1909 and passed pushes CI then failed (ai-config#5022).

Bypass: prefix the command with `AI_CONFIG_SKIP_PUSH_CHECKS='<reason>'`. The
reason must be real text (not `1`/`true`); every bypass is appended to
`~/.cache/ai-config/push-check-bypass.log` as one JSON line.

Fails OPEN, with a visible systemMessage, when the checker cannot be fetched,
times out, or the base ref is missing: an unverifiable check must not wedge a
push, but it must not pass silently either.
"""
from __future__ import annotations

import json
import os
import re
import shlex
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
    "check-title-references": {
        "script": "check-title-references/check-title-references.py",
        "prefix": "CTR_",
        "inputs": {"globs": "GLOBS", "paths-ignore": "PATHS_IGNORE"},
        "base": "BASE_REF",
        "fail": "FAIL",
    },
}
CHECK_PREFIXES = tuple(spec["prefix"] for spec in CHECKS.values())

# gha's annotation gate fails a run on any warning or error annotation, so in a repo
# that calls it a check's `fail: false` still turns CI red (lds#2793, 2026-11-18:
# check-title-references is warn-only there, and the gate failed the PR on its warnings).
ANNOTATION_GATE = re.compile(
    r"^\s*uses:\s*Morrison-Lab/gha/\.github/workflows/annotation-gate[\w-]*\.yml@",
    re.IGNORECASE | re.MULTILINE,
)

# Mirrors the default of `terms-from` in gha's check-term-links.yml: the sites before
# the calling repository in the course sequence. Keep in sync with that workflow.
TERMS_FROM_DEFAULTS = {
    "morrison-lab/pds": ["Morrison-Lab/mds"],
    "morrison-lab/cds": ["Morrison-Lab/mds"],
    "morrison-lab/mcs": ["Morrison-Lab/mds"],
    "morrison-lab/sds": ["Morrison-Lab/mds", "Morrison-Lab/pds"],
    "morrison-lab/ids": ["Morrison-Lab/mds", "Morrison-Lab/pds"],
    "morrison-lab/lds": ["Morrison-Lab/mds", "Morrison-Lab/pds", "Morrison-Lab/sds"],
    "morrison-lab/rme": ["Morrison-Lab/mds", "Morrison-Lab/pds", "Morrison-Lab/sds"],
    "morrison-lab/mlg": ["Morrison-Lab/mds", "Morrison-Lab/pds", "Morrison-Lab/sds", "Morrison-Lab/lds"],
}
TERMS_CACHE = os.path.join(CACHE_ROOT, "terms-from")
REMOTE_SLUG = re.compile(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/?$")

USES = re.compile(
    r"^\s*uses:\s*Morrison-Lab/gha/\.github/workflows/(?P<name>[\w-]+)\.yml@(?P<ref>[\w.\-/]+)",
    re.IGNORECASE,
)
KEY_VALUE = re.compile(r"^(?P<indent>\s*)(?P<key>[\w-]+):\s*(?P<value>.*?)\s*$")
RUN_CHECK = re.compile(r"^\s*\.gha/run-check/run-check\.sh\s+(?P<rest>\S.*)$")
GHA_REPOSITORY = re.compile(r"^(?P<indent>\s*)repository:\s*['\"]?Morrison-Lab/gha['\"]?\s*(?:#.*)?$", re.IGNORECASE)
EXPR = re.compile(r"'\$\{\{.*?\}\}'")
BASE_PLACEHOLDER = "@@PUSH_CHECK_BASE@@"


_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from sibling import load_sibling
except ImportError as _exc:
    print(f"{os.path.basename(__file__)}: cannot load scripts/lib/sibling.py "
          f"({_exc}); running without its sibling hooks", file=sys.stderr)
    load_sibling = None


def _load_sibling():
    """`no-push-without-self-review.py`, whose `iter_pushes` decides what a
    push is, or None (scripts/lib/sibling.py)."""
    if load_sibling is None:
        return None
    return load_sibling(__file__, "no-push-without-self-review.py", "no_push_without_self_review")


_SIBLING = _load_sibling()
if _SIBLING is None:
    print(f"{os.path.basename(__file__)}: cannot load "
          "no-push-without-self-review.py; not gating", file=sys.stderr)


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
        # The job mapping is every contiguous line indented at least as far as `uses:`,
        # on either side of it, since YAML puts `with:` before or after `uses:`.
        start = i
        while start > 0 and (not lines[start - 1].strip()
                             or len(lines[start - 1]) - len(lines[start - 1].lstrip()) >= uses_indent):
            start -= 1
        in_with = False
        with_indent = -1
        for nxt in lines[start:]:
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                continue
            indent = len(nxt) - len(nxt.lstrip())
            if indent < uses_indent:
                break
            kv = KEY_VALUE.match(nxt)
            if not kv:
                continue
            if in_with and indent <= with_indent:
                in_with = False
            if not in_with:
                if indent == uses_indent and kv.group("key") == "with":
                    in_with, with_indent = True, indent
                continue
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
    bundled: list[dict] = []
    gated = False
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        try:
            with open(os.path.join(wf_dir, name), encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        calls.extend(parse_workflow(text))
        bundled.extend(parse_run_check_lines(text))
        gated = gated or bool(ANNOTATION_GATE.search(text))
    # A check that has its own caller workflow runs from that caller's inputs, once.
    named = {c["name"] for c in calls}
    for call in bundled:
        if call["name"] not in named:
            named.add(call["name"])
            calls.append(call)
    for call in calls:
        call["gated"] = gated
    return calls


def gha_checkout_ref(text: str) -> str | None:
    """The `ref:` of the step that checks Morrison-Lab/gha out at `path: .gha`, or None.

    Reads the sibling keys of each `repository: Morrison-Lab/gha` line (the `with:`
    mapping, in any order), so a checkout to another path is not taken for `.gha`.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = GHA_REPOSITORY.match(line)
        if not m:
            continue
        indent = len(m.group("indent"))
        siblings: dict[str, str] = {}
        for step in (-1, 1):
            j = i + step
            while 0 <= j < len(lines):
                cur = lines[j]
                if cur.strip() and not cur.lstrip().startswith("#"):
                    if len(cur) - len(cur.lstrip()) != indent:
                        break
                    kv = KEY_VALUE.match(cur)
                    if kv:
                        value = re.sub(r"(?:^|\s+)#.*$", "", kv.group("value")).strip()
                        siblings[kv.group("key")] = value.strip("'\"")
                j += step
        if siblings.get("path", "").rstrip("/") in (".gha", "./.gha") and siblings.get("ref"):
            return siblings["ref"]
    return None


def parse_run_check_lines(text: str) -> list[dict]:
    """Return [{name, ref, kind: "bundled", assigns, command, unhandled}] for each
    `.gha/run-check/run-check.sh <name> VAR=value ... -- <command>` line (lds#1839).
    Only diff-scoped lines (with a `*_BASE_REF=`) are kept: a whole-tree check can
    read files a local render left behind, which CI never sees."""
    ref = gha_checkout_ref(text)
    if not ref:
        return []
    calls = []
    for line in text.splitlines():
        m = RUN_CHECK.match(line)
        if not m:
            continue
        unhandled: list[str] = []

        def placeholder(expr: re.Match) -> str:
            body = expr.group(0)
            if "'pull_request'" in body:
                return BASE_PLACEHOLDER
            if "'workflow_dispatch'" in body:
                return "false"  # a local run stands in for a pull request, never a manual run
            unhandled.append(body)
            return "''"

        try:
            # comments=True drops a trailing YAML comment rather than passing it as arguments.
            argv = shlex.split(EXPR.sub(placeholder, m.group("rest")), comments=True)
        except ValueError:
            continue
        # An expression outside single quotes is not one EXPR can read; never run it as text.
        unhandled.extend(tok for tok in argv if "${{" in tok)
        if not argv or "--" not in argv:
            continue
        name, split = argv[0], argv.index("--")
        assigns = {}
        for token in argv[1:split]:
            key, sep, value = token.partition("=")
            if sep and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                assigns[key] = value
        if not any(k.endswith("_BASE_REF") for k in assigns):
            continue
        command = argv[split + 1:]
        # The pushed repo writes this line: run only .gha/<name>/<name>.py from a named
        # gha ref, with one prefix and only the fixed VALUE_SAFE_KEYS under it (run_bundled).
        if not SAFE_REF.fullmatch(ref or "") or re.fullmatch(r"[0-9a-f]{40}", ref or ""):
            unhandled.append(f"gha ref {ref} is not a named tag or branch")
        prefixes = check_prefixes(assigns)
        if len(prefixes) != 1:
            unhandled.append(f"{len(prefixes)} *_BASE_REF keys, not exactly one")
        unhandled.extend(f"{p}BASE_REF does not name a check's variables" for p in prefixes
                         if not re.fullmatch(r"[A-Z][A-Z0-9]*_(?:[A-Z0-9]+_)*", p)
                         or p.startswith(RESERVED_PREFIXES))
        unhandled.extend(f"{k} is not one of the check's own value-safe variables"
                         for k in assigns if not any(k == p + s for p in prefixes for s in VALUE_SAFE_KEYS))
        # Only a pull-request base belongs in a *_BASE_REF; a pull_request test anywhere
        # else (a FAIL switch, an argument) has no local meaning, so it is not guessed.
        unhandled.extend(f"{k}={v}" for k, v in assigns.items()
                         if BASE_PLACEHOLDER in v and not k.endswith("_BASE_REF"))
        unhandled.extend(tok for tok in command if BASE_PLACEHOLDER in tok)
        # Run only what the wrapper is for: python on this check's own script.
        if not gha_script_command(command, name):
            unhandled.append(f"command is not python on .gha/{name}/{name}.py: "
                             + (" ".join(command) or "(empty)"))
        calls.append({"name": name, "ref": ref, "kind": "bundled", "inputs": {},
                      "assigns": assigns, "command": command, "unhandled": unhandled})
    return calls


SAFE_PYTHON_FLAGS = ("-u", "-I", "-B")
# The pushed line chooses the check, so a key such as TYPOS_BIN_DIR would choose code to run:
# only these suffixes, which select files to read or how to report, may follow the prefix.
VALUE_SAFE_KEYS = ("BASE_REF", "WHOLE_TREE", "GLOBS", "PATHS_IGNORE", "FAIL", "CLAUSE_BREAKS",
                   "CLAUSE_MIN_LENGTH", "LIBRARY", "MACROS_FILE")
# A ref that names a cache directory inside CACHE_ROOT/gha: no "." or "..", no leading "-".
SAFE_REF = re.compile(r"(?!.*\.\.)[A-Za-z0-9][\w.\-/]*")
# Prefixes whose variables change how a loader, interpreter or git behaves.
# A check's own prefix is never one of these.
RESERVED_PREFIXES = ("LD_", "DYLD_", "GIT_", "GITHUB_", "RUNNER_", "ACTIONS_", "PYTHON", "BASH",
                     "XDG_", "SSH_", "GCONV_", "MALLOC_", "PERL", "RUBY", "NODE_", "JAVA_")


def check_prefixes(assigns: dict) -> tuple:
    """The prefixes of a line's *_BASE_REF keys: the check's own variable names."""
    return tuple(k[:-len("BASE_REF")] for k in assigns if k.endswith("_BASE_REF"))


def gha_script_command(command: list, name: str) -> bool:
    """True only for `python3 [-u|-I|-B ...] .gha/<name>/<name>.py [args]`, with
    `<name>` the line's own `check-<words>` name: no other gha script, `-c` or `-m`."""
    if not re.fullmatch(r"check-[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return False
    if not command or command[0] not in ("python3", "python"):
        return False
    rest = command[1:]
    while rest and rest[0] in SAFE_PYTHON_FLAGS:
        rest = rest[1:]
    return bool(rest) and rest[0] == f".gha/{name}/{name}.py"


def remote_moved(dest: str, ref: str) -> bool | None:
    """True when origin's `ref` is a different commit from the cached HEAD, False when
    it is the same, None when the remote cannot be read (the caller then falls back
    to the daily stamp). A peeled `^{}` line, present for an annotated tag, wins."""
    try:
        listed = subprocess.run(["git", "-C", dest, "ls-remote", "origin", f"refs/tags/{ref}", f"refs/heads/{ref}"],
                                capture_output=True, text=True, timeout=15)
        head = subprocess.run(["git", "-C", dest, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if listed.returncode != 0 or head.returncode != 0 or not listed.stdout.strip():
        return None
    shas = {}
    for line in listed.stdout.splitlines():
        sha, _, name = line.partition(chr(9))
        shas[name] = sha
    tag = f"refs/tags/{ref}"
    remote = shas.get(tag + "^{}") or shas.get(tag) or shas.get(f"refs/heads/{ref}")
    return remote is not None and remote != head.stdout.strip()


def ensure_gha(ref: str) -> str | None:
    """Return a gha checkout at `ref`, cloning or refreshing a cache; None on failure."""
    override = os.environ.get("GHA_CHECKS_DIR")
    if override:
        return override if os.path.isdir(override) else None
    if not SAFE_REF.fullmatch(ref):
        return None
    dest = os.path.join(CACHE_ROOT, "gha", re.sub(r"[^\w.\-]", "_", ref))
    stamp = os.path.join(dest, ".git", "refreshed")
    try:
        if os.path.isdir(os.path.join(dest, ".git")):
            last = os.path.getmtime(stamp) if os.path.exists(stamp) else 0
            # A commit pin is immutable, so only a tag or branch pin is ever refreshed.
            # A tag such as v3 moves when gha slides it, so the remote's sha is read on
            # every push; the daily stamp is only the fallback when the remote is unreachable.
            pinned = re.fullmatch(r"[0-9a-f]{40}", ref) is not None
            moved = None if pinned else remote_moved(dest, ref)
            if moved is None:
                moved = time.time() - last > REFRESH_SECONDS
            if not pinned and moved:
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
                     ["git", "-C", dest, "remote", "add", "origin", GHA_URL],
                     ["git", "-C", dest, "fetch", "-q", "--depth", "1", "origin", ref],
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


def repo_slug(git_root: str) -> str:
    """Lower-cased `owner/repo` of origin, or "" when it is not a GitHub remote."""
    url = _git(["remote", "get-url", "origin"], cwd=git_root) or ""
    m = REMOTE_SLUG.search(url)
    return m.group(1).lower() if m else ""


def terms_from(git_root: str, call: dict) -> list[str]:
    """The prerequisite sites CI would clone for this call: the caller's literal
    `terms-from` input, else the course-sequence default for the repository."""
    explicit = call["inputs"].get("terms-from", "").strip()
    if explicit:
        return [] if explicit == "none" else explicit.split()
    return TERMS_FROM_DEFAULTS.get(repo_slug(git_root), [])


def ensure_terms_repo(slug: str) -> str | None:
    """A shallow checkout of a prerequisite site, refreshed daily; None on failure."""
    override = os.environ.get("PUSH_CHECK_TERMS_ROOT")  # a directory holding one checkout per repo name
    if override:
        local = os.path.join(override, slug.split("/")[-1])
        return local if os.path.isdir(local) else None
    dest = os.path.join(TERMS_CACHE, slug.replace("/", "__"))
    stamp = os.path.join(dest, ".git", "refreshed")
    try:
        if os.path.isdir(os.path.join(dest, ".git")):
            last = os.path.getmtime(stamp) if os.path.exists(stamp) else 0
            if time.time() - last > REFRESH_SECONDS:
                # Stamp first, so an offline machine retries once a day, not on every push.
                with open(stamp, "w", encoding="utf-8") as fh:
                    fh.write(str(time.time()))
                fetched = subprocess.run(["git", "-C", dest, "fetch", "--depth", "1", "origin", "HEAD"],
                                         capture_output=True, timeout=30)
                if fetched.returncode == 0:
                    subprocess.run(["git", "-C", dest, "reset", "--hard", "FETCH_HEAD"],
                                   capture_output=True, timeout=30)
            return dest
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        cloned = subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{slug}.git", dest],
                                capture_output=True, timeout=CLONE_TIMEOUT,
                                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        if cloned.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            return None
        return dest
    except (OSError, subprocess.SubprocessError):
        if os.path.isdir(os.path.join(dest, ".git")):
            return dest
        shutil.rmtree(dest, ignore_errors=True)
        return None


def resolve_base(git_root: str) -> str | None:
    base = os.environ.get("PUSH_CHECK_BASE_REF", "").strip()
    if base:  # An explicit base that does not resolve is a missing base, not a cue to guess.
        found = _git(["rev-parse", "--verify", "--quiet", base + "^{commit}"], cwd=git_root)
        return base if found else None
    for cand in ("origin/main", "origin/master"):
        if _git(["rev-parse", "--verify", "--quiet", cand + "^{commit}"], cwd=git_root):
            return cand
    return None


def run_check(git_root: str, gha_dir: str, call: dict, base: str, terms_dirs: str = ""):
    """Run one check; return (name, status, output) with status ok|fail|error."""
    if call.get("kind") == "bundled":
        return run_bundled(git_root, gha_dir, call, base)
    spec = CHECKS[call["name"]]
    script = os.path.join(gha_dir, spec["script"])
    if not os.path.isfile(script):
        return call["name"], "error", f"{spec['script']} not found in gha checkout"
    # Start from a clean slate: a stray TERM_LINKS_*, NLB_* or CTR_* in the caller's shell is not CI.
    env = {k: v for k, v in os.environ.items() if not k.startswith(CHECK_PREFIXES)}
    for k, v in call["inputs"].items():
        suffix = spec["inputs"].get(k)
        if suffix:
            env[spec["prefix"] + suffix] = v
    env[spec["prefix"] + spec["base"]] = base
    # CI's default is blocking; a repo that sets `fail: false` is not predicted to fail, so honor
    # it, unless the repo runs the annotation gate, which fails CI on the check's warnings anyway.
    fail = "true" if call.get("gated") else call["inputs"].get("fail", "true")
    env[spec["prefix"] + spec["fail"]] = fail
    env.update(spec.get("extra", {}))
    if terms_dirs and call["name"] == "check-term-links":
        env["TERM_LINKS_TERMS_DIRS"] = terms_dirs
    try:
        proc = subprocess.run([sys.executable, script], capture_output=True, text=True,
                              cwd=git_root, env=env, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return call["name"], "error", f"timed out after {CHECK_TIMEOUT}s"
    except OSError as exc:
        return call["name"], "error", str(exc)
    out = (proc.stdout + proc.stderr).strip()
    return call["name"], ("ok" if proc.returncode == 0 else "fail"), out


def run_bundled(git_root: str, gha_dir: str, call: dict, base: str):
    """Run one `run-check.sh` line's command with its assignments, as the wrapper does,
    against the cached gha checkout in place of `.gha/`."""
    if call["unhandled"]:
        return call["name"], "error", "line not runnable locally: " + call["unhandled"][0]
    name, (prefix,) = call["name"], check_prefixes(call["assigns"])
    assigns = {k: v.replace(BASE_PLACEHOLDER, base) for k, v in call["assigns"].items()}
    if call.get("gated"):
        # The annotation gate fails CI on a warn-only check's warnings, including a check
        # whose line leaves its FAIL variable to the script's default.
        assigns[prefix + "FAIL"] = "true"
    script = os.path.join(gha_dir, name, name + ".py")
    if not os.path.isfile(script):
        return name, "error", f"{name}/{name}.py not found in gha checkout"
    # Inherited variables with the check's own prefix are dropped; nothing else is touched.
    env = {k: v for k, v in os.environ.items() if not k.startswith(prefix)}
    env.update(assigns)
    command = [sys.executable] + [os.path.join(gha_dir, a[len(".gha/"):]) if a.startswith(".gha/") else a
                                  for a in call["command"][1:]]
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              cwd=git_root, env=env, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return name, "error", f"timed out after {CHECK_TIMEOUT}s"
    except OSError as exc:
        return name, "error", str(exc)
    out = (proc.stdout + proc.stderr).strip()
    return name, ("ok" if proc.returncode == 0 else "fail"), out


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


def push_args(argv) -> list[str]:
    """Return the arguments after the `push` subcommand, skipping git's own options.

    `-C dir` and `-c k=v` take a value, so a directory literally named `push` is
    not mistaken for the subcommand.
    """
    args = list(argv or [])
    i = 1 if args[:1] == ["git"] else 0
    while i < len(args) and args[i] != "push":
        i += 2 if args[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    return args[i + 1:]


def refspecs(argv) -> list[str]:
    """Return the refspec words of a push: the arguments after the remote."""
    args = push_args(argv)
    words = []
    skip = False
    for a in args:
        if skip:
            skip = False
        elif a in ("--repo", "-o", "--push-option", "--receive-pack", "--exec"):
            skip = True
        elif not a.startswith("-"):
            words.append(a)
    return words[1:]  # words[0] is the remote


def deletes_only(argv) -> bool:
    """True when the push deletes refs and ships nothing: `--delete`, or only `:ref` specs."""
    args = push_args(argv)
    if any(a in ("--delete", "-d") for a in args):
        return True
    specs = refspecs(argv)
    if not specs and "--tags" in args:  # tags only: nothing from HEAD's history is pushed
        return True
    return bool(specs) and all(s.lstrip("+").startswith(":") for s in specs)


def pushed_other_than_head(argv, git_root: str, head: str | None) -> str | None:
    """Return the first pushed refspec source that resolves to a commit other than HEAD."""
    for spec in refspecs(argv):
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
        if deletes_only(argv):
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
        wanted = sorted({r for c, _ in runnable if c["name"] == "check-term-links"
                         for r in terms_from(git_root, c)})
        with ThreadPoolExecutor(max_workers=max(1, len(runnable), len(wanted))) as pool:
            fetched = dict(zip(wanted, pool.map(ensure_terms_repo, wanted)))
            for slug in wanted:
                if not fetched[slug]:
                    notes.append(f"check-term-links: could not fetch {slug} for its terms, "
                                 "so it knows fewer terms than CI.")
            results = list(pool.map(
                lambda cg: run_check(
                    git_root, cg[1], cg[0], base,
                    " ".join(fetched[r] for r in terms_from(git_root, cg[0]) if fetched.get(r))),
                runnable))
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
