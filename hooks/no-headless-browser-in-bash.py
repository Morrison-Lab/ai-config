#!/usr/bin/env python3
"""PreToolUse guard: refuse a Bash command that launches a browser.

Ezra's standing rule is no Chrome, no browser and no computer use, ever
(AGENTS.md "Use the browser only when nothing else can"; project memory
"NO CHROME/browser/computer-use ever"). The rule was written for the browser
*tools* (`mcp__claude-in-chrome__*`, `mcp__Claude_Browser__*`,
`mcp__computer-use__*`), and `hooks/warn-browser-without-route-check.py` only
watches those. On 2026-10-28 an agent checked a hash redirect on the live lds
site by running a headless Chromium through the cloud container's preinstalled
Playwright (`node redir.js` with `require('playwright')`). No tool name said
"browser", the container's system prompt advertised Playwright, and the
coordinator caught it afterwards. The rule held for the named tools and said
nothing about the same browser started from Bash.

What replaces it is almost always `curl` plus HTML parsing, and for a page's
client-side JavaScript, `node` against stub `location` and `document` objects.

THE CHECK
---------
Fires on a Bash command that *invokes*:

  1. a browser binary: chromium, chrome, google-chrome, firefox, msedge,
     chrome-headless-shell, headless_shell;
  2. a browser-automation CLI: `playwright`, `puppeteer`, `lighthouse`,
     `chromedriver`, `geckodriver`, `selenium-side-runner`
     (including through `npx`, `pnpm dlx`, `bunx`, `uvx`);
  3. an interpreter (node, python, python3, bun, deno, Rscript, uv run) whose
     inline code (`-e`, `-c`) or script file imports a browser-automation
     library: playwright, puppeteer, selenium, pyppeteer, chromote, webshot2,
     RSelenium. The script file is read, because the incident's command line
     was just `node redir.js`.

Matching is on invocation, not mention: `grep -rn playwright .` and
`pip install playwright` start no browser and pass.

Escape valve: `ALLOW_HEADLESS_BROWSER=1` in the command. Using it means saying
in the reply why no curl/node route works.

Fails OPEN on an unreadable payload or an unreadable script file.
"""
import json
import os
import re
import sys

# Start of a command: line start or just after a shell operator, allowing
# VAR=value assignments and common wrappers.
START = (
    r"(?:^|&&|\|\||;|\||\n|\()\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:(?:sudo|env|nice|time|timeout\s+\S+|xvfb-run(?:\s+-\S+)*|exec|command)\s+)*"
    r"(?:[\w./~-]*/)?"
)

BROWSER_BINARY = re.compile(
    START
    + r"(?:chromium(?:-browser)?|chrome|google-chrome(?:-stable)?|firefox|msedge|"
    r"microsoft-edge|chrome-headless-shell|headless_shell|chromedriver|geckodriver)\b"
)

# CLI names, optionally behind a package runner.
AUTOMATION_CLI = re.compile(
    START
    + r"(?:(?:npx|bunx|uvx|pipx\s+run|pnpm\s+(?:dlx|exec)|yarn\s+dlx|npm\s+exec)\s+(?:-\S+\s+)*)?"
    r"(?:playwright|puppeteer|lighthouse|selenium-side-runner)\b"
)

INTERPRETER = re.compile(
    START
    + r"(?P<prog>node|nodejs|bun|deno|python3?(?:\.\d+)?|Rscript|uv\s+run)\b(?P<rest>[^\n;&|]*)"
)

LIBRARY = re.compile(
    r"\b(?:playwright|puppeteer|pyppeteer|selenium|webdriver|chromote|webshot2|RSelenium)\b"
    r"|chromium\.launch|firefox\.launch|webkit\.launch",
    re.IGNORECASE,
)

SCRIPT_FILE = re.compile(r"""(?:^|\s)["']?([\w./~-]+\.(?:js|mjs|cjs|ts|py|R|r))["']?(?=\s|$)""")
MAX_SCRIPT_BYTES = 400_000


def script_imports_browser(path: str) -> bool:
    try:
        with open(os.path.expanduser(path), encoding="utf-8", errors="replace") as handle:
            return bool(LIBRARY.search(handle.read(MAX_SCRIPT_BYTES)))
    except OSError:
        return False        # unreadable or not there yet: fail open


def offending(command: str):
    """Return (label, matched text) for the first browser launch, else None."""
    if match := BROWSER_BINARY.search(command):
        return "a browser binary", match.group(0).strip(" ;&|(\n")
    if match := AUTOMATION_CLI.search(command):
        return "a browser-automation CLI", match.group(0).strip(" ;&|(\n")
    for match in INTERPRETER.finditer(command):
        rest = match.group("rest")
        inline = re.search(r"\s(?:-e|-c|--eval|--print|-p)\s", " " + rest + " ")
        if inline and LIBRARY.search(command[match.start("rest"):]):
            return "inline code that imports a browser-automation library", match.group(0).strip(" ;&|(\n")
        script = SCRIPT_FILE.search(rest)
        if script and script_imports_browser(script.group(1)):
            return f"{script.group(1)}, which imports a browser-automation library", match.group(0).strip(" ;&|(\n")
    return None


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"no-headless-browser-in-bash: unreadable hook input ({exc})", file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""

    hit = None if re.search(r"\bALLOW_HEADLESS_BROWSER=1\b", command) else offending(command)
    if not hit:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    label, segment = hit
    reason = (
        f"Blocked: this command starts a browser ({label}).\n\n"
        f"    {segment}\n\n"
        "Ezra's standing rule is no Chrome, no browser and no computer use, ever, "
        "and it covers a headless Chromium started from Bash as much as the "
        "browser tools. On 2026-10-28 a headless Playwright run to check a hash "
        "redirect broke it.\n\n"
        "Instead:\n"
        "  - fetch the page with `curl -sS <url> -o page.html` and parse the HTML;\n"
        "  - for a page's client-side JavaScript, copy the script out of the "
        "served HTML and run it under `node` with stub `location` and `document` "
        "objects;\n"
        "  - for a rendered preview, read the built HTML from the gh-pages branch.\n\n"
        "If none of these can answer the question, put ALLOW_HEADLESS_BROWSER=1 "
        "in the command and say in your reply why no curl or node route works."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
