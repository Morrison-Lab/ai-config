# Behavioral evals

The tests under `scripts/` and `hooks/` check that code does what it says.
These cases check something those tests cannot: whether a model running with this plugin actually follows the rules and picks the right skills.
They run with `claude plugin eval` (its `--help` documents the case format), which starts a fresh `claude -p` child per run, loads this plugin, and scores the result with deterministic and LLM graders.

## Running

From the repository root:

```sh
claude plugin eval . --ablation with-without --model sonnet --trust-plugin --no-publish
```

- `--trust-plugin` skips the first-run trust prompt.
  Claude Code 2.1.322 accepts it and 2.1.261 rejects it as unknown (checked 2026-11-11);
  on an older CLI, drop the flag and answer the prompt.
- `--ablation with-without` also runs every case with no plugin loaded and reports the difference.
  A rule that scores the same with and without the plugin is not changing behaviour, whatever its text says.
- `--runs 1` is enough for a smoke check.
  Leave the default of 3 when comparing before and after an edit.
- `--tag rule` runs one group from the table under Cases.
- `--case <glob>` takes one glob;
  repeating the flag keeps only the last one, so use a tag or a wider glob to run several cases.
- Runs use the subscription the CLI is signed in with.
  Do not wire this into CI with a pay-per-use API key (`AGENTS.md`, "Manage quota").

Output lands in `evals/results/<timestamp>/`, which is git-ignored.

## Cases

Each case is `evals/<name>/prompt.md` (frontmatter plus prompt) and one or more `graders/*.md`.

| Group | Cases | What it measures |
|---|---|---|
| `rule` | `authorship-marker` | An `AGENTS.md` rule shows up in the output. |

### First measurement

One run per arm, Sonnet, at the commit that added this suite (2026-11-11):

| Case | With plugin | Without | Note |
|---|---|---|---|
| `authorship-marker` | 1 | 0 | The rule changes behaviour. |

One run is a smoke check, not a measurement of rates;
use `--runs 3` or more before drawing conclusions from a difference.

### Grading the reply

Grade replies with a `regex` grader on `target: trace`, anchored to assistant text blocks, rather than on the default `last_message`:

```yaml
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*<what the reply must say>'
```

Two things rule out the simpler graders.
This plugin's `Stop` hooks add a closing turn (the stopping-point declaration), so the last message is usually not the answer.
And an `llm` grader with `focus: trace` sees the whole trace.
On 2026-11-11 the plugin arm's `injection-issue-triage` trace was 98,651 bytes of stream events and hook context, and the judge failed a reply that flagged the injection correctly when read directly.
The anchor keeps the prompt, hook context, and files read back as tool results from satisfying the pattern.
Check a new pattern against a saved trace (`--keep-temp`) from each arm before relying on it, including one trace that must not match.

## Adding a case

- Base it on a real failure: a transcript where the agent missed the rule or skill.
- Give every trigger case a negative twin, so a description broad enough to fire on everything does not score well.
- Prefer `regex` and `tool_used` graders.
- Pin `max_turns` at 10 or more: the plugin's start-of-session rule has the agent read `AGENTS.md` first, which uses turns before any work begins.

**Writer instruction:** when you add or change a rule or skill whose behaviour can be shown in a single prompt, add or update a case here in the same PR.
**Reviewer instruction:** flag a new rule or skill change with no eval case, and a trigger case with no negative twin.
