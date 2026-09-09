#!/usr/bin/env python3
"""Cases for flag-config-deletion-without-ref-check.py.

Run:  python3 hooks/test-flag-config-deletion-without-ref-check.py \\
          hooks/flag-config-deletion-without-ref-check.py
"""
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit("Usage: python3 %s <path-to-hook>" % sys.argv[0])
HOOK = os.path.abspath(sys.argv[1])

# Every mkdtemp here is recorded and removed at exit, via atexit rather than a
# line at the end of the module: `run()` calls `sys.exit` on a FATAL hook exit
# and asserts on a bad payload shape, and both bypass module-level cleanup.
_TEMP_DIRS = []


def _ns_reason():
    """The hook's REASON text, read from the hook under test."""
    ns = {"__name__": "_reason_probe"}
    exec(compile(open(HOOK, encoding="utf-8").read(), HOOK, "exec"), ns)
    return ns["REASON"]


def _cleanup_temp_dirs():
    for _d in _TEMP_DIRS:
        shutil.rmtree(_d, ignore_errors=True)


atexit.register(_cleanup_temp_dirs)


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
        _TEMP_DIRS.append(sentinel_dir)
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
    (DELETE_REPLY, ("locate ~/.claude/settings.json",),
     "`locate` contains `cat`: the read verb is front-anchored like the "
     "manifest name, or a command that opens nothing discharges"),
    (DELETE_REPLY, ("grep -rn 'foo' README.md && rm -f ~/.claude/settings.json",),
     "the verb and the operand must be ONE command -- this DELETES the "
     "manifest, the mirror of the find-then-cat case above"),
    (DELETE_REPLY, ("grep -rn 'settings.json' ~/.claude/hooks/",),
     "a grep FOR the string over .py files opens no manifest: the read's "
     "OPERAND must be the manifest, not a root elsewhere on the line"),
    (DELETE_REPLY, ("cat ~/.claude/hooks/no-empty-promise.py && cat ./app/config.json",),
     "reading a hook file plus an unrelated config is not a manifest read"),
    (DELETE_REPLY, ("grep -rn '~/.claude' ~/.codex/config.toml",),
     "this DOES read a manifest, but codex's -- the claude here is the search "
     "PATTERN, so it must not discharge a ~/.claude deletion"),
    (DELETE_REPLY, ("cd ~/.claude && cat webpack.config.json",),
     "the manifest name is front-anchored: `webpack.config.json` is not "
     "`config.json`, and without the lookbehind it discharges"),
    (DELETE_REPLY, ("find ~/.claude -name '*.py' -delete && cat config.json",),
     "a root mention that is NOT a read must not pair with a later unrelated "
     "read -- this is the DELETION discharging the warning about itself"),
    (DELETE_REPLY, ("ls -la ~/.claude/hooks && cat ./app/config.json",),
     "listing plus one unrelated read is still not a reference check"),
    (DELETE_REPLY, ("du -sh ~/.claude; jq . tsconfig.json",),
     "`tsconfig.json` is not a manifest: the name must not match as a "
     "substring of an unrelated config file"),
    (DELETE_REPLY, ("jq . ~/.codex/config.toml",),
     "a read under a DIFFERENT root says nothing about what references "
     "`~/.claude/hooks`, so it must not discharge"),
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
    # ai-config#3126: the boundary the lexical approach could not reach. A
    # quoted pattern DEQUOTES into an argv element indistinguishable from a
    # path, so only its POSITION says it opens nothing.
    (DELETE_REPLY, ("grep -rn '~/.claude/settings.json' README.md",),
     "a quoted pattern spelling a whole manifest path opens no config file: "
     "the first positional of a grep is the PATTERN, not a file operand"),
    (DELETE_REPLY, ("rg '~/.claude/config.json' docs/",),
     "the same shape under rg, whose first positional is a pattern too"),
    (DELETE_REPLY, ("grep -e '~/.claude/settings.json' README.md",),
     "`-e` supplies the pattern, so the path here is that option's VALUE and "
     "the only file operand is README.md"),
    (DELETE_REPLY, ("(cd ~/.claude) && cat settings.json",),
     "a cd inside a subshell moves that subshell, not the parent, so the "
     "later relative read resolves nowhere near the root"),
    (DELETE_REPLY, ("awk -f ~/.claude/settings.json README.md",),
     "the manifest is the awk PROGRAM file, and README.md is what is read; "
     "crediting the root here would discharge on a command that opens the "
     "manifest as code rather than checking it for references"),
]

SILENT_CASES = [
    ("Remove them with `rm -rf ~/.cursor/rules`.", ("cat ~/.cursor/mcp.json",),
     "cursor's real manifest is `mcp.json` with no leading dot: per-root "
     "coverage made this permanently un-dischargeable, warning an author who "
     "had read exactly the right file"),
    (DELETE_REPLY, ("cd ~/.claude/ && cat settings.json",),
     "a trailing slash is what tab-completion produces, so the cd form must "
     "accept it"),
    (DELETE_REPLY, ("cd ~/.claude && cat settings.json",),
     "root BEFORE the read verb: the natural spelling, which the docstring "
     "claimed was accepted and the regex rejected"),
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
     ("grep -o 'hooks/[a-z0-9-]*[.]py' ~/.claude/settings.json | sort -u",),
     "an earlier grep of settings.json discharges it"),
    ("Remove the scratch dir with `rm -rf /tmp/scratch`.", (),
     "a destructive command outside any config root"),
    ("Run `rm build/output.o` to force a rebuild.", (),
     "an ordinary build artifact"),
    ("I read ~/.claude/settings.json to see what is registered.", (),
     "naming a config path without proposing deletion"),
    ("Use `git clean -fd` in the worktree.", (),
     "a destructive verb with no config-root operand"),
    # ai-config#3126: reads the lexical approach could not credit, so the
    # guard warned while the author was complying.
    (DELETE_REPLY, ("cd ~/.claude/hooks && cat ../settings.json",),
     "a cd into a SUBdirectory then a relative `..` read: the path resolves "
     "under the root, which only a path join can see"),
    (DELETE_REPLY, ("sed -n '1,5p' ~/.claude/settings.json",),
     "`sed -n` is --quiet and takes no value: a shared value-option set would "
     "eat the script and drop the manifest as the pattern positional"),
    (DELETE_REPLY, ("grep -f patterns.txt ~/.claude/settings.json",),
     "`-f` supplies the pattern from a file, so the first positional IS the "
     "file operand and the manifest is genuinely read"),
    (DELETE_REPLY, ("grep -A 3 hooks ~/.claude/settings.json",),
     "a context option's value must be skipped, or it becomes the pattern "
     "positional and the real pattern shadows the manifest"),
    (DELETE_REPLY, ('cat "$HOME/.claude/settings.json"',),
     "shlex dequotes the operand, so the quoting a shell strips no longer "
     "has to be modelled by the pattern"),
    (DELETE_REPLY, ("sudo cat ~/.claude/settings.json",),
     "a command wrapper is peeled before argv[0] is read, so the verb is "
     "`cat` rather than `sudo`"),
    (DELETE_REPLY, ("grep -o 'hooks ~/.claude/settings.json",),
     "an unbalanced quote makes shlex raise: the fallback is the lexical "
     "path, not silence, so behaviour is unchanged rather than lost"),
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
_TEMP_DIRS.append(_shared)
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
for _rx, _prefix in (("RX_DESTRUCTIVE", "find ~/.claude "),
                     ("RX_DESTRUCTIVE", "rm -rf ~/.claude "),
                     ("RX_DESTRUCTIVE", "cd ~/.claude "),
                     ("RX_DESTRUCTIVE", "git clean -fdx ~/.claude "),
                     # RX_REF_CHECK carries two ordered alternatives of lazy pairs and
                     # is the regex this round changed, so it is timed too.
                     ("RX_REF_CHECK", "cat ~/.claude "),
                     ("RX_REF_CHECK", "cd ~/.claude && cat ")):
    _probe = _prefix + "a" * 40000
    _t0 = _time.time()
    _ns[_rx].search(_probe)
    _worst = max(_worst, _time.time() - _t0)
total += 1
_ok = _worst < 0.5
wrong += not _ok
print("%-7s every branch stays linear on a 40,000-char line (worst %.4fs)"
      % ("ok" if _ok else "FAIL", _worst))

# The discharge example and the command the hook RECOMMENDS are the same
# string, and nothing but this assertion couples them. They drifted once
# already --- the example missed digits and left the dot unescaped while the
# message said `[a-z0-9-]*[.]py` --- so the next drift should fail here rather
# than wait for a reviewer.
_example = next(
    (cmds[0] for _reply, cmds, _desc in SILENT_CASES
     if cmds and cmds[0].startswith("grep -o 'hooks/")),
    None,
)
_recommended = next(
    (ln.strip() for ln in _ns_reason().splitlines()
     if ln.strip().startswith("grep -o 'hooks/")),
    None,
)
total += 1
_ok = _example is not None and _example == _recommended
wrong += not _ok
print("%-7s the discharge example matches the command the hook recommends"
      % ("ok" if _ok else "FAIL"))
if not _ok:
    print("          example    : %r" % (_example,))
    print("          recommended: %r" % (_recommended,))

# Root ATTRIBUTION, read straight off `read_roots` rather than through a
# reply. The end-to-end cases above can only say warn or silent, so a command
# crediting the WRONG root and one crediting nothing look identical there --
# `grep -rn '~/.claude' ~/.codex/config.toml` warns either way. These pin the
# set itself. Run in-process because the question is about one function.
print("\n--- root attribution (read_roots)")
_HOME = os.path.expanduser("~")
_ATTRIBUTION_CASES = [
    ("grep -rn '~/.claude' ~/.codex/config.toml", {"codex"},
     "the pattern names claude and the OPERAND is codex's manifest"),
    ("grep -rn '~/.claude/settings.json' README.md", set(),
     "a whole path as the pattern credits nothing"),
    ("cd ~/.claude && cat settings.json", {"claude"},
     "the shell supplies the prefix, so the operand resolves under the root"),
    ("cd ~/.claude/hooks && cat ../settings.json", {"claude"},
     "a relative `..` still lands under the root"),
    ("jq . ~/.claude/settings.json ~/.codex/config.toml", {"claude", "codex"},
     "EVERY file operand is examined, so one command can discharge a "
     "two-root reply -- the lexical scan credited only the first"),
    ("cat '" + os.path.join(_HOME, ".claude", "settings.json") + "'",
     {"claude"},
     "an already-expanded absolute path resolves now, a limit the docstring "
     "used to list under DISCHARGE"),
    ("cat ~/.claudex/settings.json", set(),
     "`~/.claudex` is not `~/.claude`: the root must end at a path boundary"),
    ("cat ~/.config-notes/settings.json", set(),
     "the same boundary on the root most exposed to it"),
    ("cat $CONFIG_DIR/settings.json", set(),
     "an unexpanded variable is indeterminate, not a root"),
    ("locate ~/.claude/settings.json", set(),
     "argv[0] membership, so the `cat` inside `locate` cannot match"),
    ("sbatch ~/.claude/config.json", set(),
     "the `bat` inside `sbatch`, the other front-anchoring case"),
]
print("(argv parse active: %s)" % (_ns["simple_commands_with_scope"] is not None))
for _command, _expected, _desc in _ATTRIBUTION_CASES:
    _got = _ns["read_roots"](_command)
    total += 1
    _ok = _got == _expected
    wrong += not _ok
    print("%-7s %s" % ("ok" if _ok else "FAIL", _desc))
    if not _ok:
        print("          %r -> %s, expected %s"
              % (_command, sorted(_got), sorted(_expected)))

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
