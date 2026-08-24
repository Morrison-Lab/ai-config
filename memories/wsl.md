# WSL platform quirks

Satellite of `tools.md`, split at the 1200-line gate.
Covers platform-level quirks of running agent tooling from WSL on this machine.
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
