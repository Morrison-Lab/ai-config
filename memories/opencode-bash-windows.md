# opencode's Bash tool on Windows: the ChildProcess.kill bug and the `cmd /c` dodge

opencode running on this Windows box executes Bash-tool commands through
Windows PowerShell 5.1.
Two independent layers of friction showed up while landing the Windows PR
monitor (#2082), tracked as ai-config#2077.

## The tool bug

Calls fail with `Unknown: ChildProcess.kill (...)`,
naming the powershell.exe command line opencode tried to run.
Measured 2026-08-23/24:

- It fires **intermittently**, including on a *single* plain `python ...`
  invocation that had succeeded minutes earlier.
  It is not, as first hypothesized, caused only by chained commands.
- It correlates strongly with **long-running commands at kill time**.
  Every timeout-expiry kill produced either the bug itself or a burst of it
  on the immediately following calls.
- **The reliable dodge found so far is wrapping the payload in `cmd /c`**
  (`cmd /c "python scripts\test_hooks.py"`).
  The same command that failed twice bare ran to completion wrapped,
  repeatedly.
  A retry after a short wait also sometimes clears it.

## The PowerShell-5.1 layer

Each observed once:

- `&&` is rejected outright ("not a valid statement separator").
  Chain with `;`, or pass one quoted string to a single `cmd /c`.
- A trailing `>nul` after `cmd /c timeout ...` is applied by *PowerShell*
  (the outer interpreter), which tries to open the DOS device as a file and
  dies with a FileStream error.
  Use `Start-Sleep` instead of `timeout /t`.
- A `--jq` program whose text begins with `|` trips PS's parser
  ("An empty pipe element is not allowed") before cmd ever sees it.
  Route through `cmd /c` with the whole command quoted,
  and prefer jq programs that do not start with a pipe.
- Embedded double quotes inside `gh api --jq "..."` get eaten crossing
  cmd's quoting layer (`'###' is not recognized...`),
  so keep GitHub-body and jq payloads in temp files (`--body-file`) rather
  than inline strings.

## Do / Don't

- **Do:** reach for `cmd /c "<whole command>"` when a Windows opencode Bash
  call dies with ChildProcess.kill,
  and again whenever a command needs `&&` or redirects that PowerShell
  would steal.
- **Do:** keep multi-line or quote-heavy GitHub/jq payloads in temp files.
- **Don't:** assume the bug means the underlying command is wrong.
  The same command shape often succeeds on retry or under the wrapper.
- **Don't:** write PowerShell syntax (`&&`, `>nul`) into what you intend as
  a cmd or plain-executable command line.
  Name the interpreter you mean.

(Measured 2026-08-23/24 on shiva's Windows host; evidence thread in
ai-config#2077.)

Satellite of `tools.md`, split out at the 1200-line gate
(ai-config#694 pattern).
