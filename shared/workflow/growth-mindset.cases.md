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

## "A limitation you never tested" --- an R toolchain declared absent from a probe of five packages

Measured 2026-09-08 on [`UCD-SERG/serocalculator#685`](https://github.com/UCD-SERG/serocalculator/pull/685).

`requireNamespace()` returned `FALSE` for a handful of R packages.
That is a true measurement about those packages.
What got written down was a claim about the environment: "R 4.6.1 with about 30
base packages --- no `devtools`, no `testthat`, no `spelling`, no `lintr`, no
`roxygen2`", so `devtools::check()`, `devtools::test()`,
`spelling::spell_check_package()` and `lintr::lint_package()` "could not be
run".
It went into commit messages, a PR body, and PR comments, and held for several
hours.

`options(repos = c(P3M = "https://packagemanager.posit.co/cran/__linux__/noble/latest")); available.packages()`
returned a full CRAN index on the first attempt.
About ninety packages installed from binaries in a few minutes, and the package
compiled and loaded.

What the untested claim cost, all of it downstream of the same premise:

- **Three failed spellcheck CI rounds**, each "fixed" by guessing which word a
  dictionary would reject, because `spelling::spell_check_package()` was
  believed unavailable.
  It ran clean on the first real invocation.
- **A testthat snapshot reconstructed by hand**, column widths and pillar
  padding worked out on paper because `tibble` was believed unavailable.
  It turned out byte-exact, which is the unlucky outcome:
  it made the method look sound.
- **Two `expect_snapshot_value(style = "serialize")` payloads missed
  entirely.**
  A hand edit cannot regenerate base64, so they were left stale and shipped to
  CI red.
  No local test could run to fail on them, which is the mechanism this section
  names --- an untested limitation removes the very instrument that would
  contradict it.
- **A PR body of "could not be verified" claims** that had to be publicly
  retracted once the same checks ran green.

The generalization is what made it durable.
A guess invites a check; a claim with a real `requireNamespace()` result behind
it feels already checked, so re-testing reads as redundant rather than as the
one thing never done.
