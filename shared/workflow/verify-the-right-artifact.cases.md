Case records for
[`verify-the-right-artifact.md`](verify-the-right-artifact.md).

## Five claims from one session, four sharing a root cause

Recorded from a session on `d-morrison/rme`
covering rme#1068, #1073, #1074, #1076 and #1086,
and filed for transfer as
[rme#1089](https://github.com/d-morrison/rme/issues/1089).
Each claim was asserted confidently and each was wrong.
In every case a real artifact was inspected,
real evidence was found in it,
and the reasoning from that evidence was sound.
The artifact was adjacent to the claim
rather than being the thing the claim was about.

| # | The claim | The artifact read | The artifact the claim was about | Shape |
|---|---|---|---|---|
| 1 | A stale pull request preview means the Quarto freeze is stale | the `github.io` CDN copy | the `gh-pages` branch content, via `raw.githubusercontent.com` | cached copy for the origin |
| 2 | The plugin activates 18 hooks | a stale submodule checkout at `b323a4f` in the working directory | the installed plugin, built from live `main` | cached copy for the origin |
| 3 | Fragments live under `~/.claude/plugins/marketplaces/` | the marketplace checkout, which held them only because this marketplace *is* the plugin repository | the install directory, `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` | neighbour for the target |
| 4 | Bare skill names must come from the plugin, since the branch carries no submodule | the pull request branch's tree | the CI checkout --- an `issue_comment` trigger checks out the default branch | checkout for the run |
| 5 | A `renv.lock` change invalidates the freezer and forces an uncached re-render on `main` | the `actions/cache/save` step's key | whether any `restore` step exists at all | one half of a mechanism for the whole |

### Case 5 is the cleanest instance, and the cheapest to have refuted

The reasoning ran: the save step's key interpolates
`hashFiles('renv.lock')`,
so a lockfile change yields a different key,
so the cache misses and the render runs uncached.
Every step of that is correct given a restore step,
and none of it was ever checked for one.

One command settles it, over the whole workflow directory rather than
the one file already open:

```console
$ grep -rn "actions/cache" .github/workflows/
.github/workflows/publish.yml:83:        uses: actions/cache/save@v6
```

A single line, and it is the save.
Nothing in that repository ever reads the cache,
so the key's contents cannot matter and the premise is empty.

Re-measured 2026-08-20 on `d-morrison/rme` at `main`:
still exactly one match, still the save.
The line number had moved from 86 to 83 in the interval,
which is its own small argument for citing the derived command
rather than a line number.

Cost before a reviewer caught it in rme#1084:
the claim reached rme#1073's body,
rme#1075,
and rme#1086's commit message and description,
and rme#1086 was opened on the false premise and closed unmerged.

### Case 2 is the one an ordinary re-read would have confirmed

Measured 2026-08-20 by counting entries in `hooks/hooks.json`:

| Tree | `UserPromptSubmit` | `PreToolUse` | `Stop` | Total |
|---|---|---|---|---|
| `b323a4f` (the checkout that was read) | 6 | 8 | 4 | 18 |
| `main` (what the install was built from) | 8 | 11 | 12 | 31 |

Both counts are exactly what each artifact says.
The claim was not a miscount and re-reading the file more carefully
would have reproduced the same wrong answer,
because the file was not the disputed object.
The check that separates them is
`claude plugin list` or the install manifest,
never a closer reading of the checkout in the working directory.

## A stale branch read that produced two issues and a config edit

Measured 2026-08-20, `Morrison-Lab/wai` and `Morrison-Lab/ai-config`.

A session was asked whether a set of Databricks model-serving endpoints was configured correctly.
The user pointed at `wai` as the repo holding the notes, and the session ran `cat chapters/ai-tools/byok-vscode-databricks.qmd` in `~/Documents/GitHub/wai`.

That checkout was on `docs/opencode-ollama-setup`, which predates [wai#75](https://github.com/Morrison-Lab/wai/pull/75).
The branch's version of the chapter carries a per-model table giving `context_length` values of 1,000,000 for the Claude 5 family.
`main`'s version replaced it with a quota-aware table prescribing **64,000** context, 16,000 output, and a 15,000 ms delay for the Claude, GPT-5, and Gemini tiers, so that one client stays inside a 200,000 ITPM / 20,000 OTPM workspace quota.

Nothing about the read announced the discrepancy.
The file existed, parsed, and described the right subject in the right vocabulary.

Downstream, before the branch was checked:

- 29 of 41 entries in the live VS Code `settings.json` were rewritten from 64,000 to provider maximums --- reversing a deliberate quota policy.
- [ai-config#1747](https://github.com/Morrison-Lab/ai-config/issues/1747) was filed asserting the live config had "drifted".
- [wai#79](https://github.com/Morrison-Lab/wai/issues/79) was filed asserting the chapter's table was missing endpoints, when `main`'s table is organized by quota tier and covers them by group.
- A branch, a draft PR ([wai#80](https://github.com/Morrison-Lab/wai/pull/80)), and a claim comment were created on that premise.

The session had *also* flagged, in the same reply as the edit, that `delay: 15000` beside `retry.interval_ms: 15000` "reads like a deliberate rate-limit throttle" --- and then overrode its own flag.
The evidence that would have settled it was in the repo it had already opened.

What exposed it was reading `main` for an unrelated reason: the table looked nothing like the one quoted an hour earlier.

`git reflog` then showed a concurrent session had run `checkout: moving from docs/opencode-ollama-setup to main` **after** the original read.
That timing matters, and it cuts *for* the fragment's remedy rather than against it: a `rev-parse --abbrev-ref HEAD` run beside the original read would have returned `docs/opencode-ollama-setup` and caught the whole thing.
The check was not performed at all, so nothing about this incident tests whether checking once per session would have sufficed.
What the reflog does establish is the separate hazard the fragment's second property names --- the branch moved mid-session, so a check performed at the *first* read would not have described the checkout by the time of a later one.

The live config was then reverted to the backup taken before the edit, byte-identical, restoring all 29 entries to 64,000.
Re-derived against `main`'s table afterwards, all 41 live entries matched it exactly, with zero mismatches.
The configuration had been correct the whole time, and the session's own edit was the only thing that had ever made it diverge.

The generalizable point is not that the branch was wrong.
It is that **a plausible answer is the expected output of this failure**: `docs/opencode-ollama-setup` forked from a `main` the corpus had already described, so the stale table matched prior expectation better than the current one did.
Confirmation felt like recognition.

## A stale install diagnosed from an mtime and an absence

Measured on `Morrison-Lab/ai-config`, 2026-08-21 (UTC).

[#1812](https://github.com/Morrison-Lab/ai-config/issues/1812) was filed
claiming `~/.claude/hooks/` had gone stale,
so merged hook fixes were not reaching the running guards.
Two observations were reasoned from:
the installed `no-unshipped-commit.py` was dated 2026-08-18,
and it contained zero occurrences of `strip_quoted`,
a function the issue asserted `main` "has carried".

Both readings were accurate.
Neither supported the staleness-at-that-moment conclusion.

The narrower wording is deliberate, because #1812 asserted two things and only
one of them is refuted here.
Its claim that the copy was *already* stale when filed is false, as the
comparison below shows.
Its claim that a copy cannot track future merges is **true**, and the table
confirms it three minutes later: nothing had drifted at 01:17, and two of 61
files had by 01:20, once #1807 merged.
A blanket refutation would dismiss the half the record's own data supports.

The deciding comparison, against `main` as it stood when the issue was filed
(`fbe10c53^`):

```
total=61 identical=61 drifted=0
```

`strip_quoted` was absent because `main` had never carried it.
It existed only on
[#1807](https://github.com/Morrison-Lab/ai-config/pull/1807),
still unmerged at that moment.

The issue was filed at 01:17:14Z and closed at 01:18:54Z, once the direct `cmp` comparison ran.

### The mtime read identically on both sides of the transition

PR [#1807](https://github.com/Morrison-Lab/ai-config/pull/1807)
merged at 01:20:48Z, two minutes after the issue closed,
and `main`'s copy of that hook changed.
The installed copy did not.

| Time (UTC) | Event | Installed mtime | Drifted |
|---|---|---|---|
| 01:17:14 | #1812 filed | 2026-08-18 18:44:59 | 0 of 61 |
| 01:20:48 | #1807 merged | 2026-08-18 18:44:59 | 2 of 61 |

The same file with the same mtime was current before 01:20 and stale after it,
which is the whole argument against the proxy in one measurement:
an instrument reading the same value in both states
has not measured either.

## A summary read as its source, in the session that fixed the summary

Morrison-Lab/ai-config#2622 / #2623, 2026-08-29.

A push refused with `stale info`.
The auto-loaded `CLAUDE.md@05ec10e^:851` read (the line has since been rewritten by that very commit, so the quote is not findable at that path on `main`):

> A `stale info` refusal is not a reason to force either: `memories/git-branches.md` records that it means the remote branch is gone.

Acting on that, I plain-pushed, and the push was rejected: the branch existed.
I then reported to the user that **`memories/git-branches.md` was inaccurate**.

It was not.
Opening the file:

> **`stale info` after `checkout -B` usually means the remote branch was DELETED, not moved** [...]
> ```sh
> git ls-remote --heads origin <branch>   # empty output = deleted
> ```

It hedges ("usually" --- the source's own word, unemphasised), names the competing cause, and prescribes the disambiguating read.
Every one of those was dropped by the one-line restatement, and the restatement was the copy in context.

Three things this case pins that the shape's prose states more briefly.

**The summary named the file, which is what made it feel like a citation.**
Had `CLAUDE.md` asserted the claim without attribution, "which file says that?" is the obvious next question.
Naming the source answers that question in advance, so nothing prompts the read.

**The error was reported before it was checked.**
The claim went into a user-facing message, not into a file, so no review, hook, or CI step could see it.
The correction came from re-reading the source while drafting the fix --- that is, from the work, not from any instrument.

**The near-miss is that the eventual fix was still right.**
`CLAUDE.md` was genuinely defective and #2623 genuinely fixed it.
A wrong claim about *which artifact* was defective sat inside an otherwise correct diagnosis, which is the configuration in which such a claim is least likely to be revisited.

An adversarial review of that same PR then caught a second instance of the same substitution one level up.
The fix had been swept across `CLAUDE.md` and `shared/workflow/check-before-pushing.md` but not `AGENTS.md`, which `CLAUDE.md:3-5` names as the authoritative cross-agent contract and which carried a near-verbatim twin of the edited paragraph.
The sweep had been keyed on the file that prompted the work rather than on the population carrying the claim.

## A stale local base that nearly quadrupled a review diff's file count

Measured 2026-09-02 while reviewing [ucdavis/matt.contracts#98](https://github.com/ucdavis/matt.contracts/pull/98).

The PR head was fetched as a local branch `pr-98`, and an `adversarial-reviewer` subagent was dispatched with the instruction to review `git diff main...pr-98`.
That `main` was the worktree's local branch, 128 commits behind the remote (`git rev-list --count 43d59cc..7ec49fe`), or 28 by first-parent (`--first-parent`), and 0 ahead (`git rev-list --count 7ec49fe..43d59cc`):

| ref | commit |
| --- | --- |
| local `main` | `43d59cc` |
| `github/main` | `7ec49fe` |

The merge-base moved accordingly, and so did the diff:

| base | files | insertions |
| --- | --- | --- |
| stale local `main` | 53 | 2999 |
| true merge-base `6345e92` | 14 | 1584 |

The 39 extra files were already-merged work from other pull requests.
The contamination was not confined to whole extra files, which is the more insidious half.
`DESCRIPTION` and `.Rbuildignore` are both among the 14 the pull request really changes, and the wide diff mixed already-merged hunks into them --- a `foodwebr`-to-`covr` swap in `Suggests`, and a template-name cleanup --- so the spurious content sat inside files the reviewer had every reason to be reading.

The base was *behind*, so the diff grew.
A base carrying local commits the remote lacks --- ahead of it, or diverged from it --- fails the other way, narrowing the diff and hiding part of the change behind a clean verdict;
that direction was not what happened here.

**The detection was accidental, which is the part worth recording.**
No finding looked wrong, because none were: every one quoted a real line and applied a real rule.
What surfaced it was running `git diff` on `DESCRIPTION` out of curiosity and recognizing changes that belonged to other pull requests.
A scope correction sent mid-run had the subagent discard the out-of-scope findings.

Note which check would have caught it and which would not.
A session-start freshness pass per [`keep-checkouts-fresh`](keep-checkouts-fresh.md) had no bearing, since the staleness accrued afterwards.
The forge cross-check would have: `gh pr view 98 --json changedFiles,additions,deletions` reported 14 and 1584 against head `9446e72`, and the derived 53 and 2999 disagree loudly.
Re-run later it returns different figures, because the pull request's head moves;
compare against the head you actually diffed.

Tracked as [ai-config#3013](https://github.com/Morrison-Lab/ai-config/issues/3013).

## A merged pull request's check names written into a live ruleset

The user asked whether `ucdavis/rampp`'s `main` ruleset still listing bare
`Spellcheck` and `Check Changelog Action` as required contexts meant those
settings needed updating to `check / spellcheck` and
`Check-Changelog / Check Changelog Action`.

The answer given was that the premise failed twice over: that the ruleset
listed neither context, and that the repository's `gha` v2 workflows emit bare
names rather than slash-prefixed pairs.
The second claim was derived from the check-run names on
[`ucdavis/rampp#157`](https://github.com/ucdavis/rampp/pull/157), whose head
`e9e8d418` publishes exactly `Spellcheck` and `Check Changelog Action`.
That reading was correct, and correct about `main` at the moment it was
produced, which is what makes it the harder case rather than a careless one.
The migration to called reusable workflows reached `main` at `9bdeb4de`, the
merge commit of
[`ucdavis/rampp#153`](https://github.com/ucdavis/rampp/pull/153), at
`2026-09-02T22:07:16Z` --- three hours and fourteen minutes **after** `#157`
merged at `18:53:12Z`.
`main`'s `check-spelling.yaml` at `14f7b448`, the merge commit of `#157`
itself, is still the inline form.
So nothing about `#157` lagged the branch;
the branch moved afterwards, and the observation was dated retroactively by a
merge that had nothing to do with it.

`main`'s own definitions, read 2026-09-03, settle it in the direction the user
had already stated:

```
$ gh api "repos/ucdavis/rampp/contents/.github/workflows/check-spelling.yaml?ref=main" \
    --jq .content | base64 -d
name: Spellcheck
...
jobs:
  check:
    uses: Morrison-Lab/gha/.github/workflows/spellcheck.yml@v2

$ gh api repos/ucdavis/rampp/actions/runs/33688762211/jobs --jq '.jobs[].name'
check / spellcheck
```

`news.yaml` has the same shape with job key `Check-Changelog` calling
`check-news.yml@v2`, and its published context was measured rather than
derived:

```
$ gh api repos/ucdavis/rampp/actions/runs/33727364476/jobs --jq '.jobs[].name'
Check-Changelog / Check Changelog Action
```

Again as stated.
That run also settles the composition rule's second branch: `check-news.yml@v2`
keys its inner job `Check-Changelog` and gives it `name: Check Changelog
Action`, and the `name:` is what appears --- while `check / spellcheck`
exercises only the branch where neither job sets one.

The false claim was not merely said.
It was written into
[`ucdavis/rampp#159`](https://github.com/ucdavis/rampp/issues/159) as fact and
applied to the live ruleset with
`gh api -X PUT repos/ucdavis/rampp/rulesets/3889405`, which now carries
`Spellcheck` and `Check Changelog Action` among its required contexts.
Neither is emitted by any workflow on `main`, and nothing turns red to say so.
The reach looks narrower than it is, because open pull requests keep the check
runs they already have.
`ucdavis/rampp#154` reports both contexts `SUCCESS`, which reads as current and
is not: those two check runs started at `2026-08-27T23:42:10Z` and
`23:42:12Z`, six days before the migration landed, and the pull request has
published nothing since.
Its next run will resolve the workflow file through the current `main` and
publish `check / spellcheck` instead, after which the bare requirement can
never be met.
Reading that rollup as evidence about present behaviour is this case record's
own subject, committed while writing it up.
The correcting write was then refused by the permission classifier, leaving the
repository in that state pending the user.

Two things are worth separating.
The wrong artifact was **real**, so gathering it felt like deriving from
evidence rather than assuming --- which is this fragment's whole subject, and
the reason it was loaded and did not fire.
And the user had supplied the correct answer in the question itself, so the
evidence had a strong prior to overturn and did not;
see [`challenge-the-assignment`](challenge-the-assignment.md)'s "The limit".

Tracked as
[ai-config#3125](https://github.com/Morrison-Lab/ai-config/issues/3125);
a guard is *proposed* under
[ai-config#3039](https://github.com/Morrison-Lab/ai-config/issues/3039), open
and unimplemented as of 2026-09-03.
