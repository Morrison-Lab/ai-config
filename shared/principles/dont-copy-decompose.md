# Don't copy, decompose

When a second place needs something that already exists in another place, do not copy it.
Factor the shared part into one reusable component, and have every user call that component, the original included.

Asked on 2026-11-16 to move mcsg renders to the condor cluster "like lds and mlg do", a session proposed copying their setup.
Ezra corrected it and then asked for the general rule: "make that a general rule: don't copy, decompose" ([ai-config#5709](https://github.com/Morrison-Lab/ai-config/issues/5709)).

## Why

A copy is a fork with no merge path.
A fix or an upgrade made to one copy never reaches the other, so the copies drift, and nothing reports it.
Copying also hides that the two places share a design, so the third repository that wants the same setup copies whichever copy it finds first, drift included.
Decomposing pays the cost once, and every later fix lands everywhere.

## How

1. Name the shared part, and the parts that differ between the places.
2. Put the shared part in its home, and turn each difference into an input:
   - CI and workflows: a reusable workflow or composite action in [`Morrison-Lab/gha`](https://github.com/Morrison-Lab/gha) ([`upgrade-to-gha`](../workflow/upgrade-to-gha.md));
   - code: a function in a shared package;
   - agent rules: ai-config; prose guidance: [PSW](https://morrison-lab.github.io/psw/);
   - other files: one canonical file that the others include, link to, or receive through a sync workflow.
3. Switch the original to the component in the same piece of work, so it is a user and not a second copy.
   Where the original lives in a repository you cannot change now, file the switch as an issue there.

- **Do:** when asked to make repo B "do what repo A does", read A's setup, factor it into a component, and call it from both A and B.
- **Don't:** copy A's files into B, even as a first step to clean up later.
  The cleanup is the deferred fix [`dont-incur-technical-debt`](dont-incur-technical-debt.md) forbids.

## What this rule does not forbid

- **A move:** a port moves content to its new home, so the source is removed or stops being canonical, and one copy remains ([`port-by-script`](../workflow/port-by-script.md)).
- **A caller of a shared component:** a thin caller of a `gha` reusable workflow is the decomposed form, so copying a sibling's caller stub is how a repository uses the component ([`upgrade-to-gha`](../workflow/upgrade-to-gha.md)).
  A sibling workflow that runs its own steps instead of calling one is the setup to decompose first.
- **A synced copy:** a sync workflow, not an agent, writes the copy from one canonical source (`shared/vendored/`, Quarto `_extensions/`).

Beyond those, a copy is right only when the two places must differ in a way no input can express.
Say which case applies in the issue or PR, as [`centralize-or-distribute`](../workflow/centralize-or-distribute.md) asks.

## Mechanism

`hooks/no-cross-repo-copy.py` denies a `Write` of a new file whose content mostly repeats a same-named file in a sibling repository.
It also denies a `cp`, `rsync` or `install` command, including one inside `sh -c`, that copies a file of 15 or more lines from one repository to a new path in another.
A move, or a copy that must stay a copy, passes with a line comment `decompose: allow <reason>` in the file's own comment syntax (`<!--` in Markdown), so review sees the reason.
A shell copy passes with the same marker as a `#` comment on the command.

The hook does not judge a `Write` or a shell copy over an existing file, since that changes a file rather than creating a copy, or a shell copy to a remote `host:path`, which is a deploy.
It does not follow a directory copy (`cp -r`), a path behind `$VAR`, or a relative path inside `sh -c`.
It does not compare a new file with files of other names or with its own repository, since a scan of every tracked file is slow on each `Write` and refuses boilerplate that ordinary files repeat, such as a config stub.
It cannot see a copy of a design rather than of text, which shares no text.
This prose rule and review (`.claude/agents/adversarial-reviewer.md`) cover what the hook skips.

Related: [`dont-reinvent-wheel`](dont-reinvent-wheel.md) (look for the existing component first), [`prefer-systemic-solutions-over-one-off-fixes`](prefer-systemic-solutions-over-one-off-fixes.md), and the DRY entry in the [principles catalog](README.md#dry--dont-repeat-yourself).
