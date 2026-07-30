Reach for MCP servers proactively.
When a task would go better with typed tool access to some external system ---
an issue tracker, a browser, a database, a cloud console --- install and
register the server rather than waiting to be asked, and rather than working
around its absence by shelling out.

The failure this prevents is silent.
Nothing errors when a server is missing.
The work still gets done, with more calls and less structure, and whole
capabilities stay quietly unavailable --- so there is no moment at which
anything reports that a better tool existed.

## Prefer the typed tool over the shell, once one exists

[`tool-mappings.md`](../../tool-mappings.md) maps each canonical `gh`/`glab`
operation to its MCP equivalent.
Read its per-model table as a description of defaults, not of limits: it says
Claude Code uses the MCP tool in remote/web sessions and the CLI locally, and
the second half of that holds only until someone installs the server.
A local session can have it.

Prefer the MCP tool when one exists, because it returns structured data
instead of text to parse, and because a tool the harness knows about can be
permission-gated, logged, and retried.
Keep using the CLI where no equivalent exists --- the point is to stop
*defaulting* to the shell, not to avoid it.

## Before installing, read what is already registered

```sh
claude mcp list
```

Read the **transport and address**, not just the name.
A marketplace plugin can register a **remote** server under exactly the name
you meant to give a local one, so the listing shows a plausible entry that is
not your setup, and the local binary you installed sits unregistered.
An `(HTTP)` row pointing at a vendor URL is remote; a local server shows a
command path.

The official marketplace ships a concrete instance of this, worth knowing by
name rather than only by shape.
Its `github` plugin declares, in
`external_plugins/github/.mcp.json` under the marketplace checkout
(`~/.claude/plugins/marketplaces/claude-plugins-official/`):

```json
{"github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
            "headers": {"Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"}}}
```

That single file is both halves of this warning at once: it claims the name
`github`, and it carries the uninterpolated placeholder that produces the
400 the next section is about.
So don't install `github@claude-plugins-official` alongside a local server of
the same name, and check `enabledPlugins` in `~/.claude/settings.json` when a
`github` entry looks unfamiliar.
(Verified 2026-07-29; a plugin's config can change, so re-read the file rather
than trusting this snapshot.)

An installed binary is not a registered server.
Installing and registering are two separate acts, and skipping the second is
easy because the first felt like the work.

## Install the binary the platform's own way

The wrapper below hardcodes a path in its `exec` line, which quietly assumes
a binary is already sitting there.
Getting one is usually a single command, and the package manager's copy beats
a manual download because it updates with everything else:

```sh
brew install github-mcp-server        # macOS; /opt/homebrew/bin on Apple silicon
```

Two notes on the alternative.
GitHub's own `install-claude.md` leads with Docker recipes, and **`docker` on
`PATH` does not mean the daemon is running** --- so check `docker info` before
choosing that path.
Skipping the check defers the failure to *server start* rather than to
`claude mcp add`, where it presents as a broken MCP config instead of a
stopped daemon.

Take the binary path as an overridable variable rather than hardcoding it,
since the location differs per platform and package manager:

```sh
SERVER="${GITHUB_MCP_SERVER_BIN:-/opt/homebrew/bin/github-mcp-server}"
```

- **Do:** install via the platform's package manager, and confirm the daemon
  is up before committing to a container-based server.
- **Don't:** copy a wrapper's hardcoded binary path onto a machine whose
  package manager puts it somewhere else.

## 400 and 401 mean different things

A plugin config may hardcode a credential placeholder:

```json
{"headers": {"Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"}}
```

With that variable unset the header goes out as a bare `Bearer `, which is
**malformed**, not **unauthorized**:

- **401** --- the server read your token and rejected it.
  A credential problem: expired, wrong scopes, wrong account.
- **400** --- no token was ever substituted.
  A *configuration* problem, and no amount of re-issuing tokens will fix it.

Chasing a 400 as though it were a 401 sends you to the token-minting page for
a bug that lives in a config file.

## Supply credentials with a wrapper, not a stored token

Registering with the token inline writes a live credential into harness
config in plain text and pins you to one token that will expire.
A launch wrapper reads it at start time from a tool that already holds one:

```sh
#!/bin/sh
set -eu
SERVER="${GITHUB_MCP_SERVER_BIN:-/opt/homebrew/bin/github-mcp-server}"
TOKEN="$(gh auth token)"
if [ -z "$TOKEN" ]; then
  echo "empty token; run 'gh auth login'" >&2   # fail loudly
  exit 1
fi
export GITHUB_PERSONAL_ACCESS_TOKEN="$TOKEN"
exec "$SERVER" stdio "$@"
```

Note the explicit failure on an empty token.
A wrapper that silently exports an empty string reproduces the bare-`Bearer `
bug above, which is the shape [`fail-fast`](../principles/fail-fast.md) warns
about: a check whose failure path and pass path look the same.

## Toolsets are opt-in, and the default may omit what you need

A server does not necessarily expose everything it can do.
Two consequences, both observed on GitHub's:

- **The default omits things you will want.**
  It carries no CI access at all --- no workflow runs, no job logs, no re-run
  trigger --- and no notification/subscription tools.
- **A selection replaces the default rather than extending it.**
  Asking for `actions` alone trades the whole default set for a handful of
  tools: a net loss that presents as a successful configuration change.
  Name the default explicitly (`default,actions,notifications`).
  (Measured on `github-mcp-server` 1.7.0: 44 tools in `default`, 4 in
  `actions` alone.
  Read those as a dated snapshot rather than as current fact --- the ratio
  is the point, and it is why the paragraph below says to measure rather
  than to trust a number written here.)

Measure the tool list before and after rather than assuming, and confirm the
count went up rather than sideways.
This is [`algorithmatize-checks`](algorithmatize-checks.md) applied to your
own configuration: two counts decide it exactly.

## Verify by a real call, and expect to restart

**Verify by calling, not by reading a list.**
A tool appearing in the registry proves that a config file parsed.
It does not prove the server started, authenticated, or can reach the API.
One identity call plus one read (for GitHub: `get_me`, then listing pull
requests on a repo you know) proves the whole path.

**Expect the tools to be missing until you restart.**
Servers connect at session start, so one registered mid-session is inert for
the rest of it.
This is a common false alarm: the registration worked, and the tools
genuinely are not there yet.

Note which new tools can **write**.
A re-run or dispatch tool can trigger CI, and permissive permission modes will
not prompt first, so treat those the way you would treat a merge.

## When a rule names a mechanism this session does not have

This is the most generalizable item here, and the easiest to miss, because
nothing fails.

A standing rule can name a specific tool that exists only in some sessions.
`CLAUDE.md`'s "subscribe to PR updates automatically" names
`subscribe_pr_activity`, which is a remote/web harness tool.
A local CLI session does not have it --- so the rule silently degrades into
per-PR polling, and no error, check, or reviewer reports the gap.

The instinct at that moment is to note the tool is unavailable and fall back.
Don't stop there.
**Ask whether a local equivalent exists**, because the fallback is usually
worse in ways that compound: polling costs N calls per round per PR, sees
only the PRs you remembered to watch, and structurally cannot notice a PR
another session opened.

Often the equivalent is already installed and merely disabled.
So when a named mechanism is missing, enumerate what the servers you *do*
have can actually do before accepting the degraded path.

(2026-07-29: an entire session ran `gh pr checks` polling loops because
`subscribe_pr_activity` was absent.
The GitHub MCP server's `notifications` toolset --- carrying
`manage_notification_subscription` and a `list_notifications` call that covers
every subscribed thread across every repo in one request --- was present the
whole time, switched off.
Those are the **server's own** tool names, as returned by a `tools/list` call
against `github-mcp-server` 1.7.0.
A harness that namespaces MCP tools surfaces them prefixed, which is why this
repo's other references spell them `mcp__github__list_notifications`; ask the
server rather than grepping our docs when you need to know what a toolset
actually contains.
The same session had already hit the shadowed-plugin and 400-vs-401 traps
above, which is why they are written down here.)
