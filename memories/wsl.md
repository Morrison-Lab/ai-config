# WSL platform quirks

Satellite of `tools.md`, split at the 1200-line gate.
Covers platform-level quirks of the WSL layer on this machine, in both directions: running agent tooling from WSL, and a Windows session reaching WSL by accident.
Per-tool entries stay in `tools.md` unless they are about the WSL layer itself.

## On WSL, `npx` resolves to the Windows node and cannot see the checkout

- **Running `npx --yes markdownlint-cli2@0.22.1` from a WSL session prints a CMD.EXE "UNC paths are not supported" banner plus usage help and exits 2.**
  PATH carries `/mnt/c/Program Files/nodejs/`, so `npx` is Windows node.
  It starts in `C:\Windows`, never sees `.markdownlint-cli2.jsonc`, and lints nothing.
  No Linux node is installed (`which node` finds nothing).
  Fetch a standalone Linux build into /tmp and prepend it to PATH:

  ```sh
  curl -fsSL https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz -o /tmp/opencode/node.tar.xz
  tar -xJf /tmp/opencode/node.tar.xz -C /tmp/opencode
  export PATH=/tmp/opencode/node-v22.14.0-linux-x64/bin:$PATH
  ```

  (Measured 2026-08-23 on this machine: after the swap the same command linted 514 files with 0 errors.)
  - **Do:** read exit 2 plus usage text as "wrong node", not as a lint failure.
  - **Don't:** conclude markdown passes because npx printed nothing useful.

## Under the Windows PATH, a bare `bash` resolves to WSL's bash, not Git Bash

The section above is WSL bleeding *out*; this is WSL bleeding *in*.
A process running under the **Windows** `PATH` --- the PowerShell tool, a `.bat`, a Windows-launched Python --- resolves a bare `bash` to `C:\Windows\System32\bash.exe`, the WSL launcher.
`C:\Windows\System32` precedes `C:\Program Files\Git\cmd` on that PATH, and the Git `cmd` directory carries no `bash.exe` at all.
The condition is the PATH, not the session: measured in one Claude Code session on 2026-09-10, `shutil.which("bash")` returned the System32 launcher from the PowerShell tool and `C:\Program Files\Git\usr\bin\bash.EXE` from the Bash tool.
So a helper invoked one way finds Git Bash and the same helper invoked the other way finds WSL, with nothing in either invocation saying which.

The failure is silent and reads as the opposite of what it is.
Windows PATH interop is on, so WSL's `PATH` does carry the `/mnt/c` entries and a Windows `jq.exe` is reachable there --- but the *Linux* `jq` the script invokes under its bare name is not installed, so every case exits 127.
Do not read the 127 as PATH interop being off;
measured 2026-09-10, WSL's `PATH` carried dozens of `/mnt/c` entries and resolved `jq.exe` while resolving no `jq`.
The entry count varies with the launching environment, so check for the bare name rather than counting entries.
A mutation sweep whose harness invokes `bash` by its bare name then produces byte-identical output before and after every mutation, because no case ever reached the code under test.
Whichever way the harness reads that sameness --- as the mutation surviving, or as the behaviour being pinned --- it is reading a suite that never ran, and nothing in the output says so.
That is the vacuous-green shape [`fixtures-are-not-evidence.md`](../shared/workflow/fixtures-are-not-evidence.md) names, arriving through the interpreter rather than through the fixture.
[`r-quarto.md`](r-quarto.md) already carries the general remedy --- assert harness liveness on every path, with an invocation counter or a mutation known to be caught --- and this entry only adds the interpreter as one more way for that liveness to be absent.

Let a Git Bash shell resolve the interpreter and have Python consume it.
It has to be Git Bash: `cygpath` is not on the Windows PATH at all, and a `command -v bash` run under the Windows PATH returns WSL's own bash --- the interpreter this entry exists to avoid.

```sh
export BASH_BIN="$(cygpath -w "$(command -v bash)")"
```

```python
BASH = os.environ["BASH_BIN"]
```

The Bash tool does not persist shell state between calls and the PowerShell tool has its own environment, so the `export` and the `python3` invocation must happen in the **same** call, or the value must be written into a config the helper reads.

Two neighbouring Windows traps sit in the same helper and are not about WSL, so they live elsewhere: `write_text` writing CRLF ([`python.md`](python.md)) and process substitution failing for a native-Windows consumer ([`shell.md`](shell.md)).

- **Do:** pass an explicitly resolved interpreter path to `subprocess`, never the bare name `bash`.
- **Do:** read a mutation sweep in which *every* mutation survives as a question about the harness before it is a question about the tests.
- **Don't:** trust identical before/after output as evidence a suite ran --- assert on a case you know should be red.
- **Don't:** read a 127 from a WSL-launched script as PATH interop being off --- check for the Linux build of the tool under its bare name.

(Measured 2026-09-09 on Windows 11 / Git Bash, driving `Morrison-Lab/gha`'s `run-fixture-tests.sh` from a Python mutation harness.
Cost one full sweep reported as twelve pinned mutations that had not run at all.)
