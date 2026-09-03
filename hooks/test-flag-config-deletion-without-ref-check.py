#!/usr/bin/env python3
"""Cases for flag-config-deletion-without-ref-check.py.

Run:  python3 hooks/test-flag-config-deletion-without-ref-check.py \\
          hooks/flag-config-deletion-without-ref-check.py
"""
import json
import os
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit("Usage: python3 %s <path-to-hook>" % sys.argv[0])
HOOK = os.path.abspath(sys.argv[1])


def run(reply, prior_commands=()):
    """Return WARN or silent for a transcript ending in `reply`."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as stream:
            for command in prior_commands:
                stream.write(json.dumps({
                    "type": "assistant",
                    "message": {"content": [{
                        "type": "tool_use", "name": "Bash",
                        "input": {"command": command},
                    }]},
                }) + "\n")
            stream.write(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": reply}]},
            }) + "\n")
        # A fresh TMPDIR per case, so the once-per-message sentinel cannot
        # leak between cases. Two cases deliberately share a reply body --
        # they differ only in the PRIOR commands -- and without isolation the
        # second would read as silent because the first wrote the sentinel.
        env = dict(os.environ)
        sentinel_dir = tempfile.mkdtemp()
        env["TMPDIR"] = sentinel_dir
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, timeout=30, env=env,
        )
        if proc.returncode != 0:
            sys.exit("FATAL: hook exited %d\n%s" % (proc.returncode, proc.stderr))
        out = proc.stdout.strip()
        if not out:
            return "silent"
        payload = json.loads(out)
        assert "hookSpecificOutput" in payload, "missing hookSpecificOutput"
        assert "systemMessage" in payload, "missing systemMessage"
        return "WARN"
    finally:
        os.unlink(path)


DELETE_REPLY = (
    "Remove the stale copies so the plugin's hooks take effect:\n\n"
    "    find \"$HOME/.claude/hooks\" -maxdepth 1 -name '*.py' -delete\n"
)

WARN_CASES = [
    ("Nuke it: `git clean -fdx ~/.claude`; preview with -n if unsure.", (),
     "a destructive git clean whose PROSE mentions -n: the dry-run exemption "
     "must scan the option run, not 40 characters of arbitrary trailing text"),
    ("Wipe them with `rm -rf ~/.claude*`.", (),
     "a glob suffix is a common spelling of exactly what this catches; a "
     "bare path-or-space boundary exempted it"),
    ("Reset with `rm -rf ${HOME}/.config`.", (),
     "the braced ${HOME} form, which existed for .claude only"),
    ("Reset it with `git clean -fdx ~/.claude`.", (),
     "git clean as a STANDALONE verb over a config root: narrowing the rm "
     "branch to option-tokens-only silently dropped this form"),
    (DELETE_REPLY, ("grep -rn 'settings.json' README.md",),
     "grepping the CORPUS for the string opens no config file, so it must not "
     "discharge -- an earlier draft let it"),
    (DELETE_REPLY, (),
     "the measured incident: a find -delete over a config root, no ref check"),
    ("Clean it up with `rm -rf ~/.claude/hooks`.", (),
     "rm with the verb BEFORE the path, the other operand order"),
    ("Try `rm ~/.config/app/settings-old.json` to reset it.", (),
     "a second config root, so the rule is not ~/.claude-specific"),
    (DELETE_REPLY, ("ls -la ~/.claude/hooks", "wc -l ~/.claude/hooks/a.py"),
     "listing and counting the files is NOT a reference check -- staleness is "
     "a property of the file, safety-to-delete a property of the graph"),
]

SILENT_CASES = [
    ("Preview with `git clean -nd ~/.claude` first.", (),
     "the n may sit anywhere in the flag cluster, not only at its end"),
    ("Try `cd ~/.claude && git clean -n` to see what would go.", (),
     "the cd branch must exempt a dry run too -- the docstring claimed dry "
     "runs were excluded while only the standalone branch did it"),
    ("Delete the scratch notes: `rm -rf ~/.config-notes`.", (),
     "a root must end at a boundary -- `~/.config` must not match inside "
     "`~/.config-notes`, or an unrelated file would discharge the guard"),
    ("Preview it first with `git clean -n ~/.claude`.", (),
     "a dry run is non-destructive and IS the look-before-you-delete step "
     "this guard promotes: warning here fires while the author complies"),
    ("Check with `git clean --dry-run ~/.claude` before deciding.", (),
     "the long spelling of the same dry run"),
    ("Run `rm -rf /tmp/build` before you look at ~/.config/app.yml.", (),
     "an unrelated rm and a later config mention in one sentence: only OPTION "
     "tokens may sit between the verb and its operand"),
    (DELETE_REPLY,
     ("grep -o 'hooks/[a-z-]*.py' ~/.claude/settings.json | sort -u",),
     "an earlier grep of settings.json discharges it"),
    ("Remove the scratch dir with `rm -rf /tmp/scratch`.", (),
     "a destructive command outside any config root"),
    ("Run `rm build/output.o` to force a rebuild.", (),
     "an ordinary build artifact"),
    ("I read ~/.claude/settings.json to see what is registered.", (),
     "naming a config path without proposing deletion"),
    ("Use `git clean -fd` in the worktree.", (),
     "a destructive verb with no config-root operand"),
]

total = wrong = 0
print("--- expected WARN")
for reply, prior, desc in WARN_CASES:
    verdict = run(reply, prior)
    total += 1
    wrong += verdict != "WARN"
    print("%-7s %s" % (verdict, desc))

print("\n--- expected silent")
for reply, prior, desc in SILENT_CASES:
    verdict = run(reply, prior)
    total += 1
    wrong += verdict != "silent"
    print("%-7s %s" % (verdict, desc))

# The sentinel makes the warning fire once per distinct message, so a Stop
# guard cannot loop. Every case above gets a fresh TMPDIR, which deliberately
# hides this; here one TMPDIR is shared across two identical replies.
_shared = tempfile.mkdtemp()
_fd, _tpath = tempfile.mkstemp(suffix=".jsonl")
os.close(_fd)
with open(_tpath, "w", encoding="utf-8") as _stream:
    _stream.write(json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": DELETE_REPLY}]},
    }) + "\n")
_env = dict(os.environ)
_env["TMPDIR"] = _shared
_verdicts = []
for _ in range(2):
    _p = subprocess.run([sys.executable, HOOK],
                        input=json.dumps({"transcript_path": _tpath}),
                        capture_output=True, text=True, env=_env)
    _verdicts.append("WARN" if _p.stdout.strip() else "silent")
os.unlink(_tpath)
total += 1
_ok = _verdicts == ["WARN", "silent"]
wrong += not _ok
print("%-7s the same message warns once, then self-suppresses (got %s)"
      % ("ok" if _ok else "FAIL", "/".join(_verdicts)))

# The known OVER-approximation: the guard cannot tell a recommendation from a
# mention, so a reply warning AGAINST the command still fires. Pinned so the
# behaviour is a documented choice rather than an accident.
_verdict = run("Do NOT run `rm -rf ~/.claude/hooks` -- it unregisters the guards.")
total += 1
_ok = _verdict == "WARN"
wrong += not _ok
print("%-7s a reply arguing AGAINST the deletion still fires (documented "
      "over-approximation)" % _verdict)

# Linearity. An earlier draft paired two adjacent lazy stars and took 14.3s on
# a 40,000-character line, against this hook's declared 10s timeout, on the
# SILENT path -- a reply merely quoting config paths would have burned it.
import time as _time
_src = open(HOOK, encoding="utf-8").read()
_ns = {"__name__": "_probe"}
exec(compile(_src, HOOK, "exec"), _ns)
# Every branch is VERB-anchored, so a probe without a verb fails at the first
# literal and never enters a quantifier -- it would pass against an
# arbitrarily explosive pattern. Probe each branch through its own verb.
_worst = 0.0
for _prefix in ("find ~/.claude ", "rm -rf ~/.claude ", "cd ~/.claude ",
                "git clean -fdx ~/.claude "):
    _probe = _prefix + "a" * 40000
    _t0 = _time.time()
    _ns["RX_DESTRUCTIVE"].search(_probe)
    _worst = max(_worst, _time.time() - _t0)
total += 1
_ok = _worst < 0.5
wrong += not _ok
print("%-7s every branch stays linear on a 40,000-char line (worst %.4fs)"
      % ("ok" if _ok else "FAIL", _worst))

print("\n--- fail-open")
_proc = subprocess.run([sys.executable, HOOK], input="not json",
                       capture_output=True, text=True)
total += 1
_ok = _proc.returncode == 0 and not _proc.stdout.strip()
wrong += not _ok
print("%-7s unparseable stdin fails open" % ("silent" if _ok else "WARN"))

for _payload in ('"hello"', '[1,2]', 'null',
                 json.dumps({"transcript_path": ["a"]}),
                 json.dumps({"transcript_path": "/nonexistent"})):
    _proc = subprocess.run([sys.executable, HOOK], input=_payload,
                           capture_output=True, text=True)
    total += 1
    _ok = _proc.returncode == 0 and not _proc.stdout.strip()
    wrong += not _ok
    print("%-7s a non-object or non-string payload fails open (%s)"
          % ("silent" if _ok else "WARN", _payload[:24]))

_proc = subprocess.run([sys.executable, HOOK],
                       input=json.dumps({"transcript_path": "/nonexistent"}),
                       capture_output=True, text=True)
total += 1
_ok = _proc.returncode == 0 and not _proc.stdout.strip()
wrong += not _ok
print("%-7s a missing transcript fails open" % ("silent" if _ok else "WARN"))

print("\n%d/%d correct" % (total - wrong, total))
sys.exit(1 if wrong else 0)
