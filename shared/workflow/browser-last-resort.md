# Use the browser only when nothing else can do the task

Driving a browser, whether the built-in browser pane, Claude in Chrome, or computer use against a web page, is a last resort.
Before opening one for a task, look for a non-browser route:
a CLI (`gh`, `glab`, `gcloud`, a vendor CLI),
an MCP server that is installed or could be installed (see [`use-mcp-servers`](use-mcp-servers.md)),
or the service's REST API.
Use the browser only when that search finds no route that can do the task,
or when the task itself is visual (checking a rendered page, say).

The search has to happen *before* the browser opens, and its result goes in the reply.
"The Admin API exposes only a read method for this setting, so I used the browser" is a finding the user can check.
Opening the browser because it was the first tool to hand is the failure this rule exists to stop, and it looks just like a justified use until someone asks.

A missing route can also be a missing setup step: an API that needs an OAuth login, or a CLI that is not installed yet.
That is a reason to set the route up, or to ask the user for the one step only they can do (an OAuth consent screen, say), rather than a reason to fall back to the browser.

A task that still needs the browser gets logged per [`deterministic-tools`](../principles/deterministic-tools.md#browser-work-leaves-no-artifact-so-keep-a-log-of-it).

- **Do:** search for a CLI, MCP, or API route before opening a browser, and name what you found in the reply.
- **Do:** set up a missing route (install the CLI, register the MCP, ask for the one OAuth step) when the task will recur.
- **Don't:** open the browser first because it is already loaded and the task looks small.
- **Don't:** read a route that needs setup as a route that does not exist.

(Directive from Ezra Morrison, 2026-10-09:
"I'd prefer you don't use the browser unless you absolutely need to".
That day an agent changed Google Analytics account settings in the browser without first checking the Analytics Admin API.
A check afterwards, on 2026-10-09, found that the Analytics Admin API reference documents only a read method,
[`accounts.getDataSharingSettings`](https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1beta/accounts/getDataSharingSettings),
for account data-sharing settings,
while it documents create and update methods for the property, stream and retention settings set up two weeks earlier.
So the browser was needed for one of the two tasks, and neither was checked beforehand.
An older preference bullet in `memories/preferences.md` already said the browser is a last resort, but neither `AGENTS.md` nor `CLAUDE.md` loads that file at startup.)
