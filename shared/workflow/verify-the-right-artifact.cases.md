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
