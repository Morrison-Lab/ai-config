# Case records: growth-mindset

Worked-example case records for the rules in
[`growth-mindset.md`](growth-mindset.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "First check the limitation is real" --- Quarto reported broken twice

(2026-07-30: checking whether Quarto's `execute: echo` can be set per output
format, `quarto` was reported broken twice, and was working both times.
The first invocation ran the conda environment's binary without activating
that environment, failing with
`bin/tools/x86_64/deno: No such file or directory`; `conda activate bcs`
fixed it.
The second ran from a scratchpad directory outside the project, so `renv`
never activated and the conda base R library genuinely lacked `rmarkdown`;
`export R_LIBS=<project renv library>` fixed it.
The user's correction was "if a tool you could use is broken, fix it, don't
accept it as broken".
The render then worked on the first try and settled the question, which the
manuscript would otherwise have asserted unchecked.)

## "A timeout bounds how long you wait" --- claude setup-token opened a browser

(2026-08-02, verifying a claim written into
[ai-config#1056](https://github.com/Morrison-Lab/ai-config/pull/1056) that
`claude setup-token` "needs a TTY, so an agent session cannot run it":
`perl -e 'alarm 8; exec "claude","setup-token"' < /dev/null` was run as a
supposedly non-destructive check, and returned exit 142 with no output.
It had already opened a real browser window on the user's machine, on the
wrong browser profile, which the session learned only because the user said
so.
The command's behaviour is recorded in
[`memories/claude-code.md`](../../memories/claude-code.md); reading its
`--help` would have answered the question the probe was asked to answer.)

## "A refusal can name its own remedy" --- a GraphQL 403 naming the REST route

(2026-07-30: a GraphQL call was refused with exactly the message
[`growth-mindset.md`](growth-mindset.md) quotes, read
as a flat denial, and answered by searching the MCP registry and plugin
catalog for a GitHub Discussions server to install.
Neither could have helped -- a local server sits behind the same proxy.
The REST route the refusal named worked on the first attempt.)

## "A limitation you never tested" --- branch-protection settings reported unreadable across several turns, never once queried

(`UCD-SERG/shigella#46`, 2026-08-31: across several turns a session told the
user that GitHub branch-protection and ruleset settings were "not readable
from this session" and that confirming a required-checks list needed a human
to open Settings.
The claim was inferred from the absence of a dedicated MCP tool for rulesets,
never tested, and then restated across several turns --- including in a merged
PR body and in a filed issue, where it became a "needs a human with
branch-protection access" note that outlived the conversation.

`GH_TOKEN` was set in the environment throughout, and plain `curl` against the
REST API answered every part of the question on the first attempt:
`/repos/{owner}/{repo}/rulesets` for the list,
`/repos/{owner}/{repo}/rulesets/{id}` for a ruleset's rules and
`bypass_actors`, `/repos/{owner}/{repo}/rules/branches/{branch}` for the rules
in effect including org-level ones, and
`/repos/{owner}/{repo}/branches/{branch}` for the classic protection summary.
The endpoints are recorded in
[`memories/gh-cli.md`](../../memories/gh-cli.md).

The false claim was load-bearing rather than incidental: it is what put the
"a human has to check this" note into two deliverables, so the cost was not a
mistaken sentence in chat but a premise shipped to later readers.)
