#!/usr/bin/env python3
"""PreToolUse guard: pushing an edit to a generated file's SOURCE without
running its generator.

## The incident

Morrison-Lab/ai-config, 2026-09-10 (#3524): `hooks/hooks.json` was hand-edited
and pushed. That file has a generated companion,
`skills/ai-config-hooks/hooks/hooks.json`, produced by
`scripts/gen-hooks-plugin.py`. Both `validate` runs went red on the mismatch,
and the review round was spent on a defect the repo's own generator would have
prevented in one command.

## Why a guard rather than a rule

The repo already owns the instrument -- `gen-hooks-plugin.py --check` exits
non-zero on exactly this mismatch, and `validate.yml` runs it. The gap is
purely one of *timing*: the verdict arrives from CI minutes after the push,
having spent a review round, when the same verdict was available locally
before it. So this hook consumes the existing instrument's exit status rather
than re-deriving anything, per shared/workflow/algorithmatize-checks.md.

Nothing semantic is being judged: the condition is a path appearing in the
push's own diff, and a generator's exit code. That is why it is mechanizable
where the deferral-phrase guard attempted in #3520 was not.

## Warn, never block

A stale generated file is cheap to fix and cheap to detect again in CI, and a
push can be legitimate mid-stack. Blocking would buy little and cost a refused
turn, so this only ever adds context.
"""
import json
import os.path
import re
import subprocess
import sys

# (source path, generator argv) -- the generator must support a --check mode
# that exits non-zero when its output is stale.
GENERATED = [
    ("hooks/hooks.json", ["python3", "scripts/gen-hooks-plugin.py", "--check"]),
]

_ENV = r"""(?:[A-Za-z_][A-Za-z0-9_]*=(?:'[^']*'|"[^"]*"|\S*)\s+)*"""
PUSH = re.compile(r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+push(?![\w-])", re.M)


def repo_root():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def pushed_paths(root):
    """Files this branch changes relative to its upstream, or the default branch."""
    for rev in ("@{upstream}", "origin/HEAD", "origin/main"):
        try:
            out = subprocess.run(
                ["git", "-C", root, "diff", "--name-only", f"{rev}...HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0:
                return set(out.stdout.split())
        except Exception:
            continue
    return set()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if not PUSH.search(cmd):
        return 0

    root = repo_root()
    if not root:
        return 0

    changed = pushed_paths(root)
    if not changed:
        return 0

    stale = []
    for source, argv in GENERATED:
        if source not in changed:
            continue
        # This plugin's hooks fire in EVERY repo the session touches, and
        # GENERATED names ai-config's own generator. Without this check a
        # repo that merely happens to have a file at the same path -- or
        # ai-config itself with a broken generator -- gets told to run a
        # script that is not there. A missing generator is 'cannot tell',
        # never 'stale': a nonzero exit only means staleness once the thing
        # that would report it actually exists.
        script = next((a for a in argv if a.endswith('.py')), None)
        if not script or not os.path.isfile(os.path.join(root, script)):
            continue
        try:
            rc = subprocess.run(
                argv, cwd=root, capture_output=True, text=True, timeout=20,
            ).returncode
        except Exception:
            continue
        if rc != 0:
            stale.append((source, argv))

    if not stale:
        return 0

    lines = [
        "[hook: warn-generated-file-stale] This push changes a generated "
        "file's SOURCE, and the generator reports its output is stale.",
        "",
    ]
    for source, argv in stale:
        lines.append(f"  {source} -> run: {' '.join(argv[:-1])}")
    lines += [
        "",
        "CI runs the same check and will fail on the mismatch, so this costs a "
        "red round rather than one command. Run the generator, commit its "
        "output, and push again.",
        "Warning only -- the push is not blocked.",
    ]
    print(json.dumps({"systemMessage": "\n".join(lines)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
