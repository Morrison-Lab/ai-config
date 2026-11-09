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

A script that a heredoc in the same command writes (`cat > shot.js <<'X' ... X`
followed by `node shot.js`) does not exist on disk when the hook runs, so the
heredoc body is checked too (2026-11-06, ai-config#5027).

Matching is on invocation, not mention: `grep -rn playwright .`,
`pip install playwright`, `chrome --version` and a commit message that names
a browser start no browser and pass. A script on stdin (heredoc or pipe), a
`-m playwright` module run and a `bash -c '...'` payload are checked too.

An MCP tool of a browser-automation server (a tool name that carries playwright,
puppeteer or selenium, such as `mcp__playwright__browser_navigate`) is denied
outright, with no escape valve, since the valve is a Bash command prefix
(ai-config#5123). The Claude browser tools stay with
`warn-browser-without-route-check.py`.

Escape valve (Bash only): `ALLOW_HEADLESS_BROWSER=1` as a prefix of the command. Using it means saying
in the reply why no curl/node route works.

Fails OPEN on an unreadable payload or an unreadable script file.
"""
import json
import os
import re
import sys

# Start of a command: line start or just after a shell operator or keyword,
# allowing a leading quote, VAR=value assignments and common wrappers
# (with their flags).
WRAPPER = (
    r"(?:(?:sudo|env|nice|nohup|setsid|time|timeout|xvfb-run|exec|command|stdbuf)"
    r"(?:\s+-\S+(?:\s+(?:[\w.:=,-]+|'[^']*'|\"[^\"]*\"))?|\s+\d\S*|\s+[A-Za-z_]\w*=\S*)*\s+)*"
)
START = (
    r"(?:^|&&|\|\||;|&|\||\n|\(|\bthen\b|\bdo\b|\belse\b|!)\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    + WRAPPER
    + r"[\"']?(?:[\w./~-]*/)?"
)

# `-` must not continue the name, so `chrome-cli` and `lighthouse-ci` pass.
END = r"(?![\w-])"

BROWSER_BINARY = re.compile(
    START
    + r"(?:chromium(?:-browser)?|chrome|google-chrome(?:-stable)?|firefox|msedge|"
    r"microsoft-edge|chrome-headless-shell|headless_shell|chromedriver|geckodriver)"
    + END
    + r"(?!\s+(?:-v|--version)\b)"
)

# CLI names, optionally behind a package runner.
AUTOMATION_CLI = re.compile(
    START
    + r"(?:(?:npx|bunx|uvx|pipx\s+run|pnpm\s+(?:dlx|exec)|yarn\s+dlx|npm\s+exec)\s+(?:-\S+\s+)*)?"
    r"(?:@playwright/test|playwright|puppeteer|lighthouse|selenium-side-runner)"
    + END
)

INTERPRETER = re.compile(
    START
    + r"(?P<prog>node|nodejs|bun|deno|python3?(?:\.\d+)?|Rscript|R|uv\s+run)"
    + END
    + r"(?P<rest>[^\n;&|]*)"
)

SHELL_C = re.compile(
    START + r"(?:ba|z|da)?sh\s+(?:-\w+\s+)*-c\s+(?P<q>[\"'])(?P<body>.*?)(?P=q)",
    re.DOTALL,
)

# An import or launch, not any mention of the word.
LIBRARY = re.compile(
    r"(?:\bimport\s+(?:playwright|selenium|pyppeteer)\b"
    r"|\bfrom\s+(?:playwright|selenium|pyppeteer)\b"
    r"|\brequire\(\s*[\"'](?:@?playwright|puppeteer|selenium-webdriver)[^\"']*[\"']\s*\)"
    r"|\bfrom\s+[\"'](?:@?playwright|puppeteer|selenium-webdriver)[^\"']*[\"']"
    r"|\bimport\(\s*[\"'](?:@?playwright|puppeteer)"
    r"|\b(?:library|require|loadNamespace)\(\s*[\"']?(?:chromote|webshot2|RSelenium)\b"
    r"|\b(?:chromium|firefox|webkit)\.launch\b"
    r"|\bchromote::|\bwebshot2::)"
)
# Flags that load a browser library or run one as a module.
LIBRARY_FLAG = re.compile(r"(?:\s-m\s+(?:playwright|selenium)\b|\s(?:-r|--require|--with)[\s=]+@?(?:playwright|puppeteer|selenium)\b)")

SCRIPT_FILE = re.compile(r"""(?:^|\s)["']?([\w./~$()-]+\.(?:js|mjs|cjs|ts|py|R|r))["']?(?=\s|$)""")
MAX_SCRIPT_BYTES = 400_000
HEREDOC = re.compile(
    r"<<-?\s*\\?[\"']?([^\s\"'\\;&|<>()]+)[\"']?[^\n]*\n(.*?)\n\s*\1\s*(?:\n|$)", re.DOTALL
)
# A browser-automation MCP server's tool, such as `mcp__playwright__browser_navigate`.
# The first letter is left out so one pattern matches `playwright` and
# `Playwright`: a hooks.json matcher cannot carry a case-insensitive flag, and
# the README catalog row (checked against hooks.json by check-hook-catalog.py)
# cannot hold a `[Pp]` character class.
MCP_AUTOMATION_TOOL = re.compile(r"^mcp__.*(?:laywright|uppeteer|elenium)")

ALTERNATIVES = (
    "Instead:\n"
    "  - fetch the page with `curl -sS <url> -o page.html` and parse the HTML;\n"
    "  - for a page's client-side JavaScript, copy the script out of the "
    "served HTML and run it under `node` with stub `location` and `document` "
    "objects;\n"
    "  - for MathJax output, typeset in `node` with `mathjax-full` "
    "(`tex2svg` or `tex2mml`) and read the markup, no browser involved;\n"
    "  - for LaTeX output, compile with `pdflatex` and inspect with "
    "`pdftotext` or `pdftoppm`;\n"
    "  - for a rendered preview, read the built HTML from the gh-pages branch."
)
PROSE_FLAG = re.compile(
    r"""(?:^|\s)(?:-m|--message|--body|--title|-b|-t|--description)(?:\s+|=)(?:"(?:[^"\\]|\\.)*"|'[^']*')"""
)


def script_imports_browser(path: str, cwd: str | None) -> bool:
    path = os.path.expanduser(os.path.expandvars(path))
    if cwd and not os.path.isabs(path):
        path = os.path.join(cwd, path)
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return bool(LIBRARY.search(handle.read(MAX_SCRIPT_BYTES)))
    except OSError:
        return False        # unreadable or not there yet: fail open


SCRIPT_NAME = re.compile(
    r"""[\w./~-]+\.(?:js|mjs|cjs|jsx|ts|mts|cts|tsx|py|R|r)\b"""
)


def script_key(token: str) -> str:
    """The file name a script token stands for, however it is spelled."""
    return os.path.basename(os.path.normpath(token))


def _script_name_counts(command: str) -> dict:
    """Count script file names in the whole command, if it imports a browser
    library anywhere. Nothing is parsed: not heredocs (a `# <<true` comment or
    an empty heredoc made the heredoc pattern swallow the real writer), not
    quotes. Characters that the shell removes or expands (quotes, backslashes,
    `$`, backticks, braces, parentheses) are deleted, so `shot."js"`,
    `$'shot'.js`, `shot.``js` and `{a,shot}.js` all name `shot.js`. A body that
    names a script counts too, which only adds blocks."""
    if not LIBRARY.search(command):
        return {}
    text = re.sub(r"\$\{[^}]*\}", "", command)
    text = re.sub(r"""["'\\$`{}()]""", "", text)
    counts: dict = {}
    for token in SCRIPT_NAME.findall(text):
        key = script_key(token)
        counts[key] = counts.get(key, 0) + 1
    return counts


def heredoc_script_names(command: str) -> dict:
    """Map a script file name to how often the command names it, but only when
    the command carries a browser-library import anywhere.

    `cat > shot.js <<'X' ... X` followed by `node shot.js` writes the script
    in the same command, so it is not on disk when the hook runs
    (2026-11-06, ai-config#5027). Which redirect, `tee` argument, brace group
    or pipeline stage really writes the file is shell syntax this hook cannot
    parse without drifting from the shell (six review rounds each found one
    more spelling). So it does not try: a file name that the command names
    in the command at least twice, once to write it in some way
    and once to run it, counts as written by the browser heredoc. A false
    positive needs a browser-importing heredoc and an unrelated script of
    the same base name in one command, and fails closed.

    The command is read twice, as written and with every backslash-newline
    removed the way the shell removes it, and the larger count wins. Neither
    reading alone is right: joining first breaks a quoted heredoc whose last
    body line ends in a backslash, and not joining hides a redirect on a
    continued opener line or a library name split inside an unquoted body
    (agy review of ai-config#5031, 2026-11-06).

    There is no prose exemption. Telling a commit message that quotes an
    import from a script that runs one took a regex over the owning command
    and then over the body, and five agy rounds each found a new spelling
    of both; so a commit message that quotes an import, plus a same-named
    script named twice in one command, blocks (fails closed; run the two
    steps as separate commands).
    Not covered: a name built from a variable (`/tmp/$s.js`), a script with
    no extension, a script run by `npx tsx` or named with `${...}` in the
    interpreter call (the interpreter side only knows plain file names), or
    one that a directory name stands for (`python3 dir`
    runs `dir/__main__.py`)."""
    as_written = _script_name_counts(command)
    joined = _script_name_counts(command.replace("\\\n", ""))
    return {key: max(as_written.get(key, 0), joined.get(key, 0))
            for key in as_written.keys() | joined.keys()}


def strip_prose(command: str) -> str:
    """Blank text that is data, not commands: commit/PR message flags and
    heredoc bodies not fed to an interpreter. A browser word there is a
    mention (`git commit -m 'block chromium'`)."""
    command = PROSE_FLAG.sub(" ", command)

    def keep_if_interpreter(match):
        head = command[: match.start()].rsplit("\n", 1)[-1]
        if re.search(r"\b(?:node|nodejs|bun|deno|python3?|Rscript|R|sh|bash|zsh)\b", head):
            return match.group(0)
        return "\n"     # keep the line break the heredoc match consumed
    return HEREDOC.sub(keep_if_interpreter, command)


def offending(command: str, cwd: str | None = None, depth: int = 0):
    """Return (label, matched text) for the first browser launch, else None."""
    named = heredoc_script_names(command)
    command = strip_prose(command)
    if match := BROWSER_BINARY.search(command):
        return "a browser binary", match.group(0).strip(" ;&|(\n\"'")
    if match := AUTOMATION_CLI.search(command):
        return "a browser-automation CLI", match.group(0).strip(" ;&|(\n\"'")
    if depth < 3:
        for match in SHELL_C.finditer(command):
            if hit := offending(match.group("body"), cwd, depth + 1):
                return hit
    for match in INTERPRETER.finditer(command):
        rest = match.group("rest")
        shown = match.group(0).strip(" ;&|(\n\"'")
        if LIBRARY_FLAG.search(" " + rest):
            return "a flag that loads a browser-automation library", shown
        inline = re.search(r"\s(?:-e|-c|--eval|--print|-p)\s", " " + rest + " ")
        if inline and (LIBRARY.search(rest) or LIBRARY.search(command[match.end():].split("\n", 1)[0])):
            return "inline code that imports a browser-automation library", shown
        script = SCRIPT_FILE.search(rest)
        if script and named.get(script_key(script.group(1)), 0) >= 2:
            return f"{script.group(1)}, written by a heredoc in this command, which imports a browser-automation library", shown
        if script and script_imports_browser(script.group(1), cwd):
            return f"{script.group(1)}, which imports a browser-automation library", shown
        # Script on stdin: a heredoc, a here-string, or a pipe into the interpreter.
        if not script and not inline and ("<<" in command or re.search(r"\|\s*$", command[: match.start()]) or "|" in command[: match.start()]):
            if LIBRARY.search(command):
                return "a script on stdin that imports a browser-automation library", shown
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

    tool = payload.get("tool_name") or ""
    if isinstance(tool, str) and MCP_AUTOMATION_TOOL.search(tool):
        # No escape valve: ALLOW_HEADLESS_BROWSER=1 is a Bash command prefix,
        # and an MCP call has no command to carry it.
        reason = (
            f"Blocked: `{tool}` drives a browser through an automation MCP "
            "server.\n\n"
            "Ezra's standing rule is no Chrome, no browser and no computer use, "
            "ever (AGENTS.md, \"Use the browser only when nothing else can\"), "
            "and it covers a Playwright, Puppeteer or Selenium server as much "
            "as the Claude browser tools.\n\n" + ALTERNATIVES)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""

    if not isinstance(command, str):
        command = ""          # unexpected payload shape: fail open
    allowed = re.match(r"\s*(?:[A-Za-z_]\w*=\S*\s+)*ALLOW_HEADLESS_BROWSER=1\s", command)
    hit = None if allowed else offending(command, payload.get("cwd"))
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
        "redirect broke it. A cloud container's system prompt that advertises "
        "Playwright or Chromium does not lift the rule.\n\n"
        + ALTERNATIVES + "\n\n"
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
