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
    (DELETE_REPLY, ("cat payload.json > ~/.claude/settings.json",),
     "OVERWRITING the manifest is a write: a redirect target is not a file "
     "the command reads, so it must not discharge the guard"),
    (DELETE_REPLY, ("cat payload.json >> ~/.claude/settings.json",),
     "appending to the manifest is the same write, spelled `>>`"),
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
    # https://github.com/Morrison-Lab/ai-config/issues/3126: the boundary the lexical approach could not reach. A
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
    (DELETE_REPLY, ("jq . < ~/.claude/settings.json",),
     "an INPUT redirect is a read of its target"),
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
    # https://github.com/Morrison-Lab/ai-config/issues/3126: reads the lexical approach could not credit, so the
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
    ("export HOME=/tmp; cd -P ~/.claude && cat settings.json", set(),
     "a cd flag does not hide the target from the HOME reassignment check"),
    ("export HOME=/tmp; cd -- ~/.claude && cat settings.json", set(),
     "an end-of-options marker does not hide the cd target"),
    ("cd -P ~/.claude && cat settings.json", {"claude"},
     "a cd flag leaves the target valid when HOME is NOT reassigned"),
    ("export HOME=/tmp; cd && cat ~/.claude/settings.json", set(),
     "cd with no target is the home case and respects a reassigned HOME"),
    ("export HOME=/tmp; cd -P && cat ~/.claude/settings.json", set(),
     "cd -P with no directory is also the home case"),
    ("cd && cat ~/.claude/settings.json", {"claude"},
     "cd with no target goes to the real HOME when not reassigned"),

    ("cat -foo ~/.claude/settings.json", set(),
     "an unknown option is assumed to consume the next token, losing the file"),
    ("grep -Xn pattern ~/.claude/settings.json", set(),
     "a cluster with an unknown option consumes the next token"),
    ("cat -foo README.md ~/.claude/settings.json", {"claude"},
     "an unknown option eats only the token after it, leaving a later manifest to be credited"),
    ("grep -Xn pattern README.md ~/.claude/settings.json", {"claude"},
     "the same for grep: the unknown cluster eats pattern, README is the search pattern, the manifest is credited"),

    # Finding 2: attached short option (modified)
    ("grep -nm 1 ~/.claude/settings.json file.txt", set(), "a short cluster ending in a value-taking option consumes the next token, shifting the pattern to the manifest slot"),
    ("grep -nm 1 pattern ~/.claude/settings.json", {"claude"}, "the same cluster leaves the manifest as a file operand when a real pattern follows"),

    # Finding 3: cluster containing no-input letter
    ("jq -nc . ~/.claude/settings.json", set(), "a short cluster containing a no-input letter reads no inputs"),
    ("jq -cr . ~/.claude/settings.json", {"claude"}, "a short cluster without a no-input letter still reads its files"),

    # Finding 4: home reassignment with tilde
    ("export HOME=/tmp; cat ~/.claude/settings.json", set(), "HOME reassignment makes a tilde path indeterminate"),
    ("export HOME=/tmp; cat '" + os.path.join(_HOME, ".claude", "settings.json") + "'", {"claude"}, "HOME reassignment does not affect an already-expanded absolute path"),

    # Finding 5: home reassignment with cd target
    ("export HOME=/tmp; cd ~/.claude && cat settings.json", set(), "a cd target depending on HOME is indeterminate when HOME is reassigned"),
    ("export HOME=/tmp; cd '" + os.path.join(_HOME, ".claude") + "' && cat settings.json", {"claude"}, "an absolute cd target works even if HOME is reassigned"),
    ("jq . ~/.claude/settings.json", {"claude"}, "vacuous case: normal jq reads"),
    ("jq -n . ~/.claude/settings.json", set(), "jq -n does not read inputs"),
    ("rg src ~/.claude/settings.json", {"claude"}, "vacuous case: normal rg reads"),
    ("rg --files src ~/.claude/settings.json", set(), "rg --files reads no inputs"),
    ("cat --help ~/.claude/settings.json", set(), "cat --help reads no inputs"),

    # Finding 2: HOME reassignment
    ("cat \"$HOME/.claude/settings.json\"", {"claude"}, "vacuous case: normal $HOME expands to real HOME"),
    ("export HOME=/tmp; cat \"$HOME/.claude/settings.json\"", set(), "HOME reassignment makes $HOME indeterminate"),
    ("HOME=/tmp cat \"$HOME/.claude/settings.json\"", set(), "inline HOME reassignment makes $HOME indeterminate"),

    # Finding 3: builtin wrapper
    ("builtin cd ~/.claude && cat settings.json", {"claude"}, "vacuous case: builtin cd still changes dir for subsequent cat"),
    ("builtin cat ~/.claude/settings.json", set(), "wrapper builtin cannot read since cat is not a builtin"),

    # Finding 4: PAIR_OPTS second value
    ("jq --arg name value . ~/.claude/settings.json", {"claude"}, "vacuous case: jq --arg skips both and reads manifest"),
    ("jq --slurpfile refs ~/.claude/settings.json .", {"claude"}, "jq --slurpfile reads the file as second argument"),
    ("jq --rawfile refs ~/.claude/settings.json .", {"claude"}, "jq --rawfile reads the file as second argument"),

    # Finding 5: attached short option
    ("grep -e foo ~/.claude/settings.json", {"claude"}, "vacuous case: grep -e takes value in next token"),
    ("grep -efoo ~/.claude/settings.json", {"claude"}, "grep -efoo has attached value, consuming no extra tokens"),
    ("cat <<< '~/.claude/settings.json'", set(),
     "a here-string is the opener's literal text, not a file it opens"),
    ("cat <<<~/.claude/settings.json", set(),
     "the same with the text attached: the tokenizer splits it off either way"),
    ("cat <<-EOF ~/.claude/settings.json\nx\nEOF", {"claude"},
     "a dash heredoc opener followed by a real file operand still credits it"),
    ("cat <<EOF\ngrep -rn '~/.claude/settings.json' README.md\nEOF", set(),
     "a heredoc BODY is never executed, so a manifest it mentions is not "
     "read (review of https://github.com/Morrison-Lab/ai-config/issues/3469: a scratch script or commit message discharged "
     "the guard)"),
    ("cat > /tmp/x.py <<'PY'\nCASES = [(\"cat ~/.claude/settings.json\",)]\nPY",
     set(), "the same with a quoted delimiter and an output redirect"),
    ("cat <<EOF | wc -l\nsee cat ~/.claude/settings.json\nEOF", set(),
     "and with a pipe after the opener, which used to change the answer"),
    ("cat <<EOF > ~/.claude/settings.json\nx\nEOF", set(),
     "a heredoc written INTO a manifest is a write of it, not a read"),
    ("cat <<EOF; cat ~/.claude/settings.json\nbody\nEOF", {"claude"},
     "a real read chained after a heredoc opener is still credited"),
    ("grep -rn '~/.claude/settings.json' README.md && echo `date`", set(),
     "a backtick in a NEIGHBOURING segment does not hand the lexical fallback "
     "a segment the argv parse already decided (review round on https://github.com/Morrison-Lab/ai-config/issues/3469)"),
    ("cat ~/.codex/config.toml; jq . $(echo ~/.claude/settings.json)", {"codex"},
     "a manifest path a substitution PRODUCES is unknown here and not "
     "credited: the fallback scans the substitution's text, not its value"),
    ("echo $(grep -rn '~/.claude/settings.json' README.md)", set(),
     "a substitution's body is parsed, not regex-scanned, so a grep whose "
     "PATTERN spells a manifest credits nothing there either (CI review)"),
    ("RESULT=$(grep -rn '~/.claude/settings.json' README.md)", set(),
     "the same as a captured assignment"),
    ("echo $(cat ~/.claude/settings.json)", {"claude"},
     "a real read inside a substitution is still credited"),
    ("echo $(echo $(cat ~/.claude/settings.json))", {"claude"},
     "and one nested a level deeper"),
    ("echo $(echo $(echo $(echo $(cat ~/.claude/settings.json))))", {"claude"},
     "the scan resumes after each body rather than inside it, so nesting "
     "costs one pass per level and a deep read is still credited"),
    ("grep -rn '~/.claude/settings.json' $(git diff --name-only)", set(),
     "a substitution among a grep's arguments does not hand the fallback the "
     "grep whose pattern spells a manifest (CI review round on https://github.com/Morrison-Lab/ai-config/issues/3469)"),
    ("grep -rn '~/.claude/settings.json' README.md `date`", set(),
     "the same with a backtick"),
    ("diff <(cat ~/.claude/settings.json) <(cat $(echo x))", {"claude"},
     "a nested substitution inside a process substitution still scans"),
    ("echo $(foo \"(\" bar) ; grep -rn '~/.claude/settings.json' README.md", set(),
     "a quoted parenthesis inside a substitution is text, so the body ends at "
     "the real close and the later grep is never scanned (review round)"),
    ("echo 'example: $(cat ~/.claude/settings.json)'", set(),
     "an opener inside single quotes never expands, so it opens no body "
     "(CI review of 2f17a906)"),
    ("echo 'see `cat ~/.claude/settings.json`'", set(),
     "the same with a backtick"),
    ("echo \"$(cat ~/.claude/settings.json)\"", {"claude"},
     "inside double quotes the substitution does expand and is followed"),
    ("rm -rf ~/.claude ; echo \"it's fine\" '$(cat ~/.claude/settings.json)'", set(),
     "an apostrophe inside double quotes is not a single quote, so the "
     "separate single-quoted substitution stays inert (twelfth round)"),
    ("echo \"it's $(cat ~/.claude/settings.json)\"", {"claude"},
     "the same apostrophe with the substitution inside the double quotes, "
     "which does expand"),
    ("echo `it's $(cat ~/.claude/settings.json)`", {"claude"},
     "an unbalanced quote makes shlex reject the WHOLE command, so this "
     "takes the issue-mandated whole-command lexical fallback"),
    ("echo `echo '\\'` ; grep -rn '~/.claude/settings.json' README.md", set(),
     "a single-quoted backslash inside a backtick body escapes nothing, so the "
     "body closes at its backtick and the later grep is never scanned"),
    ("cat `cat 'x`y'; cat ~/.claude/settings.json`", {"claude"},
     "a quoted backtick inside a backtick body does not end the body early, "
     "so the real read after it is still credited"),
    ("cat $(echo \"a)b\"; cat ~/.claude/settings.json)", {"claude"},
     "a quoted close inside the body does not end it early"),
    ("cat $(echo \\( ; cat ~/.claude/settings.json)", {"claude"},
     "a backslash-escaped parenthesis is text too"),
    ("cat file 2<> ~/.claude/settings.json", {"claude"},
     "a read-write redirect opens its target for reading"),
    ("grep 5 < ~/.claude/settings.json", {"claude"},
     "a redirect target is credited even where the digit before it is read as "
     "a descriptor, since the target is no longer a positional the PATTERN "
     "drop can reach"),
    ("grep 2>&1 ~/.claude/settings.json", set(),
     "a descriptor digit is joined to its operator, not left as a positional "
     "that would shield the pattern slot of a pattern-first verb"),
    ("grep 2>/dev/null ~/.claude/settings.json", set(),
     "the same descriptor shape with a file target"),
    ("cat 2>&1 ~/.claude/settings.json", {"claude"},
     "a non-pattern verb still credits the operand after a joined redirect"),
    ("jq . 0< ~/.claude/settings.json", {"claude"},
     "a descriptor-prefixed input redirect is still a read"),
    ("cat <&0 ~/.claude/settings.json", {"claude"},
     "a descriptor duplication credits nothing and skips its number"),
    ("cat payload.json > ~/.claude/settings.json", set(),
     "an output redirect target is written, not read"),
    ("cat payload.json 2>~/.claude/settings.json", set(),
     "a descriptor-prefixed, attached redirect is still a write"),
    ("jq . < ~/.claude/settings.json", {"claude"},
     "an input redirect target is read"),
    ("cat ~/.claude/settings.json 2>/dev/null", {"claude"},
     "a stderr redirect elsewhere leaves the operand credited"),
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
    # Per-verb option grammar. A shared PATTERN_OPTS set read `jq -e`
    # (--exit-status, a boolean) as having supplied the filter, so the filter
    # positional survived and a quoted manifest path was credited as a file
    # operand -- a false DISCHARGE, the one direction a discharge test must
    # not fail in.
    ("jq -e '~/.claude/settings.json' README.md", set(),
     "`jq -e` is --exit-status, not a pattern option: the quoted path is "
     "still the FILTER positional and jq opens only README.md"),
    ("jq --arg foo bar --arg baz ~/.claude/settings.json '.a' README.md",
     set(),
     "`--arg NAME VALUE` consumes TWO tokens: skipping one leaves the value "
     "in file position, crediting a manifest the command never opens"),
    ("jq --args '.' ~/.claude/settings.json", set(),
     "`--args` rebinds the remaining positionals to $ARGS, so which are "
     "input files is not decidable from argv: credit none"),
    ("jq --jsonargs '.' ~/.claude/settings.json", set(),
     "the same for the JSON spelling"),
    ("jq -f filter.jq ~/.claude/settings.json", {"claude"},
     "jq's real pattern option, whose presence DOES make the first "
     "positional a file"),
    ("jq --indent 2 . ~/.claude/settings.json", {"claude"},
     "a genuinely single-valued jq option still skips exactly one token"),
    # The wrapper limit below is a false NEGATIVE (warns while the author
    # complied), so it is asserted as the CURRENT behaviour rather than the
    # desired one; https://github.com/Morrison-Lab/ai-config/issues/3321 tracks the fix in scripts/lib/shellcmd.py.
    ("sudo -u me cat ~/.claude/settings.json", set(),
     "strip_env peels a zero-argument wrapper only, so a wrapper carrying "
     "its own option hides the read verb (https://github.com/Morrison-Lab/ai-config/issues/3321)"),
    # Process substitution is the third construct whose argv is not the
    # shell's: the split leaves `diff` in argv[0] where `cat` ran, so the outer
    # parse SUCCEEDS and credits nothing. The fallback is not what saves this.
    # `argv_read_roots` returns an empty set rather than None, so `read_roots`
    # recurses into each substitution body instead, and the inner `cat` is what
    # credits the root.
    ("diff <(cat ~/.claude/settings.json) <(cat /tmp/other.json)", {"claude"},
     "a process substitution is credited by recursing into its body"),
    # A backtick or `<( )` body used to GLUE into the enclosing command's own
    # argv, because shlex opens a fresh scope for `$(` alone. So a read verb
    # wrapping a grep credited the grep's PATTERN as its own operand, which is
    # the exact false discharge this hook exists to close. Each of these is
    # credited only if the INNER command genuinely reads the manifest.
    ("cat <(grep -rn '~/.claude/settings.json' README.md)", set(),
     "a process substitution's grep PATTERN is not the outer command's operand"),
    ("cat `grep -rn '~/.claude/settings.json' README.md`", set(),
     "a backtick body's grep PATTERN is not the outer command's operand"),
    ("sed -n '1p' <(grep -rn '~/.claude/settings.json' README.md)", set(),
     "a read verb with its own option does not absorb a substitution's tokens"),
    ("cat <(cat ~/.claude/settings.json)", {"claude"},
     "a process substitution that really reads the manifest still credits it"),
    # Bash performs process substitution only OUTSIDE double quotes: the
    # quoted form is literal text the shell never runs, so scanning it
    # credited a read that never happened.
    ('echo "<(cat ~/.claude/settings.json)"', set(),
     "a quoted process substitution is literal text, not a read"),
    ('echo ">(cat ~/.claude/settings.json)"', set(),
     "a quoted output process substitution is literal text too"),
    ('echo "$(cat ~/.claude/settings.json)"', {"claude"},
     "a command substitution DOES expand inside double quotes"),
    # A redirect may appear anywhere in a simple command, so its target must
    # not sit where a pattern-first verb's PATTERN drop can remove it.
    ("grep < README.md '~/.claude/settings.json'", set(),
     "a redirect before the pattern does not shield the pattern from the drop"),
    ("grep '~/.claude/settings.json' < README.md", set(),
     "the same command with its redirect last reads the same way"),
    # shlex strips quotes before the argv parse sees a token, and the quoting
    # is what decides whether the shell expanded it. Measured against bash: a
    # tilde expands in neither quote, $HOME in double but not single.
    ("cat '~/.claude/settings.json'", set(),
     "a single-quoted tilde is a literal filename, not the home directory"),
    ('cat "~/.claude/settings.json"', set(),
     "a double-quoted tilde does not expand either"),
    ("cat '$HOME/.claude/settings.json'", set(),
     "a single-quoted $HOME is literal text"),
    ('cat "$HOME/.claude/settings.json"', {"claude"},
     "a double-quoted $HOME DOES expand"),
    (r"cat \~/.claude/settings.json", set(),
     "an escaped tilde is literal text"),
    (r"cat \$HOME/.claude/settings.json", set(),
     "an escaped $HOME is literal text"),
    ("cat ~/.claude/settings.json", {"claude"},
     "an unescaped tilde still discharges"),
    ("cat $HOME/.claude/settings.json", {"claude"},
     "an unescaped $HOME still discharges"),
    # Quoting the TRIGGER alone is enough, so matching the whole joined
    # operand missed it. Verified against bash: echo '<tilde>'/x prints the
    # tilde literally.
    ("cat '~'/.claude/settings.json", set(),
     "a split-quoted tilde expands no more than a fully quoted one"),
    ("cat '$HOME'/.claude/settings.json", set(),
     "a split-quoted $HOME is literal too"),
    # ...but a quoted trigger in ANOTHER argument must not refuse this one.
    ("grep -rn '~/.claude' ~/.codex/config.toml", {"codex"},
     "a quoted tilde in the pattern leaves the file operand expanding"),
    # A backslash-quote inside a double-quoted span is a literal quote, not the
    # span's close; missing that desynchronized the scan for the rest of the
    # command and made a later quoted operand read as unquoted.
    ('echo "a\\"" ; cat "~/.claude/settings.json"', set(),
     "an escaped quote does not desynchronize the quote scan"),
    # `)` ends a word, so a `#` after one starts a comment.
    ("(:)# $(cat ~/.claude/settings.json)", set(),
     "a comment after a closing paren is still a comment"),
    # Quoting is neutralized POSITIONALLY, so two operands with identical text
    # and different quoting are no longer conflated: the earlier content match
    # let a quoted mention suppress an unquoted read of the same path.
    ('echo "~/.claude/settings.json" ; cat ~/.claude/settings.json', {"claude"},
     "a quoted mention does not suppress an unquoted read of the same path"),
    # Braces are not shell metacharacters, so `${#x}` starts no comment. The
    # earlier boundary set included them and swallowed the rest of the line.
    ("echo ${#x} $(cat ~/.claude/settings.json)", {"claude"},
     "a parameter length is not a comment"),
    # An apostrophe in a comment or a heredoc body is not a quote. Reading one
    # flipped the neutralizing walk's quote state, so the real opening quote of
    # a later operand read as a close and its tilde survived un-neutralized --
    # a false discharge produced by the word "it's".
    ("echo ok # it's fine\ncat '~/.claude/settings.json'", set(),
     "an apostrophe in a comment does not desynchronize the quote walk"),
    ("cat <<EOF\nit's fine\nEOF\ncat '~/.claude/settings.json'", set(),
     "an apostrophe in a heredoc body does not either"),
    ("echo ok # it's fine\ncat ~/.claude/settings.json", {"claude"},
     "and a real unquoted read after such a comment still credits"),
    # The terminator is a WHOLE LINE, and `<<-` permits leading tabs. A plain
    # substring search missed a tab-indented terminator, so everything after
    # it read as body and a quoted operand there was never neutralized.
    ("cat <<-EOF\n\tEOF\ngrep -rn foo '~/.claude/settings.json'", set(),
     "a tab-indented terminator closes a dash heredoc"),
    # A first body line merely starting with the delimiter matched at the
    # body's own start, producing a region that mapped its start to itself and
    # hung the walk. This walk runs on every earlier command in a transcript.
    ("cat <<EOF\nEOFxyz\nreal\nEOF\ngrep foo bar", set(),
     "a body line that merely starts with the delimiter does not terminate it"),
    # One line may open several heredocs, and the shell reads their bodies
    # back to back in opener order. Computing each from the same line end let
    # the second overwrite the first with a shorter span, so real body text
    # was scanned as live code and its apostrophes desynchronized the walk.
    ("cat <<A > f1 && cat <<Z > f2\nit's fine\nZ\ndon't stop\nA\nsome data\nZ\ncat '~/.claude/settings.json'", set(),
     "two heredocs on one line consume their bodies in order"),
    ("cat <<A > f1 && cat <<Z > f2\none\nA\ntwo\nZ\ncat ~/.claude/settings.json", {"claude"},
     "and a real read after both still credits"),
    # A comment can trail a heredoc OPENER. Jumping the scan to that line's
    # end to collect the bodies skipped the comment, and an apostrophe in it
    # desynchronized the quote walk exactly as one in a body used to.
    ("cat <<EOF  # don't stop\nbody\nEOF\ncat '~/.claude/settings.json'", set(),
     "an apostrophe in a comment trailing a heredoc opener is not a quote"),
    ("cat > n.md <<'EOF'  # here's a note\nb\nEOF\ngrep -n foo '~/.claude/settings.json'", set(),
     "the same with a quoted delimiter and a later grep"),
    # One walk, not two. The region catalogue and the neutralizing walk each
    # tracked quotes, and the cataloguing one was not protected from the data
    # it catalogued: an apostrophe in a heredoc body flipped its state, the
    # following comment went unrecorded, and the other walk then read that
    # comment as live text and left a later quoted tilde expanding.
    ("cat <<EOF\nHere's the note\nEOF\n# fix: don't touch prod\ncat '~/.claude/settings.json'", set(),
     "an apostrophe in a body then one in a following comment"),
    ("cat <<A > f1 && cat <<B > f2\nit's one\nA\ntwo\nB\n# don't peek\ncat '~/.claude/settings.json'", set(),
     "the same across two heredocs opened on one line"),
    ("cat <<EOF\nHere's the note\nEOF\n# fix: don't touch prod\ncat ~/.claude/settings.json", {"claude"},
     "and the unquoted form of the first still credits"),
    ("cat <<A > f1 && cat <<B > f2\nit's one\nA\ntwo\nB\n# don't peek\ncat ~/.claude/settings.json", {"claude"},
     "and the unquoted form of the second still credits"),
    # An unquoted `#` starts a comment, and bash expands nothing after it.
    ("echo ok # $(cat ~/.claude/settings.json)", set(),
     "a substitution inside a comment is never run"),
    ('echo "# $(cat ~/.claude/settings.json)"', {"claude"},
     "a hash inside quotes starts no comment"),
    # A no-file option suppresses the POSITIONAL operands, not a redirect.
    ("python3 -c 'x' < ~/.claude/settings.json", {"claude"},
     "-c leaves no script path, and stdin still opens the manifest"),
    ("jq --args . < ~/.claude/settings.json", {"claude"},
     "jq --args suppresses its file operands, not its stdin"),
    # KNOWN LIMIT, tracked as https://github.com/Morrison-Lab/ai-config/issues/3564: the parser carries no operator
    # between simple commands, so a read the shell never reaches is credited.
    # Deciding it needs an exit status, which the text does not carry.
    ("false && cat ~/.claude/settings.json", {"claude"},
     "documented limit: a guarded command is credited although it never runs"),
    # An interpreter opens its SCRIPT. Every later token is sys.argv for that
    # script, which may open none of them, so crediting them all discharged
    # the guard over a script that might only delete.
    ("python3 tidy.py ~/.claude/settings.json", set(),
     "an interpreter's script arguments are not files the interpreter opens"),
    ("python3 -c 'print(1)' ~/.claude/settings.json", set(),
     "-c leaves no script path at all"),
    ("python3 -m json.tool ~/.claude/settings.json", set(),
     "-m leaves no script path either"),
    ("python3 ~/.claude/settings.json", {"claude"},
     "the script itself IS opened by the interpreter"),
    # A value option missing from a curated table is read as a bare flag, so
    # its value falls through as a positional and is credited as a file.
    ("rg somepattern --pre ~/.claude/settings.json bar.txt", set(),
     "rg --pre takes a preprocessor command, not a file it searches"),
    ("rg somepattern --replace ~/.claude/settings.json bar.txt", set(),
     "rg --replace takes replacement text, not a file"),
    ("rg somepattern ~/.claude/settings.json", {"claude"},
     "an rg search target is still credited"),
    # The option default is INVERTED: a spelling the table does not know is
    # assumed to consume the token after it. Five rounds each found another
    # missing value-option, so what matters is not the list's contents but
    # which way a gap fails. It now loses a discharge and warns.
    ("rg -e PATTERN --type-add '~/.claude/settings.json' real.txt", set(),
     "an rg value option missing from the table no longer credits its value"),
    ("rg -e PATTERN --some-future-option ~/.claude/settings.json f.txt", set(),
     "an option that does not exist yet fails toward warning"),
    ("grep --brand-new-flag ~/.claude/settings.json README.md", set(),
     "an unknown grep option consumes the token after it"),
    # A short cluster is bare only when every letter in it is, which is what
    # keeps the common shapes discharging.
    ("grep -rn pattern ~/.claude/settings.json", {"claude"},
     "a cluster of known bare flags does not swallow the pattern"),
    # A cluster can also CARRY the pattern option. `sed -ne` is the canonical
    # idiom, and testing the whole token left pattern_supplied false, so the
    # PATTERN drop took the one real file operand and lost the discharge.
    ("sed -ne '1,5p' ~/.claude/settings.json", {"claude"},
     "a clustered -e supplies the pattern, so the file is not dropped for it"),
    ("grep -ne pattern ~/.claude/settings.json", {"claude"},
     "the same cluster on grep reads the same way"),
    ("sed -n -e '1,5p' ~/.claude/settings.json", {"claude"},
     "the unclustered spelling of the same command agrees"),
    ("rg -i pattern ~/.claude/settings.json", {"claude"},
     "a known bare rg flag still leaves its search target credited"),
    ("jq -r .x ~/.claude/settings.json", {"claude"},
     "a known bare jq flag still leaves its file credited"),
    ("cat `cat ~/.claude/settings.json`", {"claude"},
     "a backtick body that really reads the manifest still credits it"),
    # The `=`-joined long-option form, which advances by exactly one token
    # whichever table the option belongs to.
    ("grep --regexp='~/.claude/settings.json' README.md", set(),
     "an `=`-joined pattern option supplies the pattern and consumes no "
     "further token, so README.md is still the only file operand"),
    ("grep --include=*.json hooks ~/.claude/settings.json", {"claude"},
     "an `=`-joined value option must NOT also eat the next token, or the "
     "pattern shifts and the manifest is dropped as the pattern positional"),
    ("echo $(cat ~/.claude/settings.json", set(),
     "an unterminated substitution paren is treated as unparseable and credits no reads"),
    ("echo `cat ~/.claude/settings.json", set(),
     "an unterminated backtick is treated as unparseable and credits no reads"),
    ("echo $(echo `cat ~/.claude/settings.json)", set(),
     "a nested unterminated opener inside a balanced outer one makes the whole command unparseable"),
    ("echo $(cat ~/.claude/settings.json)", {"claude"},
     "a balanced substitution still discharges as before"),
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

# A broken install is the SECOND route to the lexical fallback, alongside a
# shlex raise. On it the guard reverts wholesale to the approximation this
# hook replaced, so these cases assert that BEHAVIOUR, not merely that the
# except block does not raise: the quoted grep PATTERN below is the case the
# argv parse exists to refuse, and the lexical scan credits it.
_BREAK_IMPORT = (
    "import sys; sys.modules['shellcmd'] = None; "
    "exec(open(sys.argv[1], encoding='utf-8').read())")


def run_broken(reply, prior_commands=()):
    """Run the hook with shellcmd unimportable. Returns (verdict, stderr)."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
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
    env = dict(os.environ)
    sentinel_dir = tempfile.mkdtemp()
    _TEMP_DIRS.append(sentinel_dir)
    env["TMPDIR"] = sentinel_dir
    proc = subprocess.run(
        [sys.executable, "-c", _BREAK_IMPORT, HOOK],
        input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True, timeout=30, env=env)
    if proc.returncode != 0:
        sys.exit("FATAL: broken-install hook exited %d\n%s"
                 % (proc.returncode, proc.stderr))
    return ("WARN" if proc.stdout.strip() else "silent"), proc.stderr


_verdict, _stderr = run_broken(DELETE_REPLY)
total += 1
_ok = _verdict == "WARN"
wrong += not _ok
print("%-7s broken install still WARNs on an undischarged deletion"
      % _verdict)
total += 1
_ok = "using the lexical fallback" in _stderr
wrong += not _ok
print("%-7s broken install says so on stderr" % ("ok" if _ok else "WARN"))

_verdict, _ = run_broken(
    DELETE_REPLY,
    ("grep -rn '~/.claude/settings.json' README.md",))
total += 1
_ok = _verdict == "silent"
wrong += not _ok
print("%-7s broken install falsely discharges a quoted grep PATTERN,"
      " as the lexical approximation always did" % _verdict)

# cluster_supplies_pattern asks whether ANY letter of a short cluster supplies
# the pattern, while takes_no_value asks whether EVERY letter is bare. The two
# can only agree while no verb lists one letter in both tables. That is true
# today and nothing enforced it, so a later table edit could reopen a false
# discharge with no test going red. PATTERN_OPTS' own comment records that a
# shared table caused exactly that once, with `jq -e`.
_BARE = _ns["BARE_OPTS"]
_PATTERN = _ns["PATTERN_OPTS"]
for _verb in sorted(set(_BARE) | set(_PATTERN)):
    _overlap = sorted(_BARE.get(_verb, frozenset())
                      & _PATTERN.get(_verb, frozenset()))
    total += 1
    _ok = not _overlap
    wrong += not _ok
    print("%-7s %s lists no option as both bare and pattern-supplying%s"
          % ("ok" if _ok else "WRONG", _verb,
             "" if _ok else (": " + ", ".join(_overlap))))

print("\n%d/%d correct" % (total - wrong, total))
sys.exit(1 if wrong else 0)
