# Local tools & CLIs

## Julia in Claude Code cloud / web sessions
- To install Julia, prefer downloading the official binary tarball from
  `julialang-s3.julialang.org` via `curl` (system CA store) over `juliaup`:
  juliaup's rustls HTTP client rejects TLS-intercepting proxies common in cloud
  environments, so it can fail even when the host is allowlisted. Prebuilt Linux
  Julia binaries live ONLY on `julialang-s3.julialang.org` — the
  `JuliaLang/julia` GitHub releases attach source tarballs only. `Pkg`
  operations need `pkg.julialang.org` allowlisted too.
- Reference implementation: `references/cloud-setup/cloud-setup.sh` in ai-config
  (curl+tarball, `$SUDO`-aware, best-effort/non-fatal).
- Layering: the build-time **Setup script** is the right place for slow,
  repo-independent toolchain installs (R, Julia, Quarto); the **SessionStart
  hook** is for repo-dependent per-session work (`renv::restore`,
  `Pkg.instantiate`). BUT the build-time Setup script can't be committed to a
  repo (it's pasted into the web UI), so a SessionStart hook is the only
  in-repo lever to auto-install a toolchain for *that repo's own* sessions.

## markdownlint / markdownlint-cli2
- **MD060/table-column-style is a real rule, present in `markdownlint-cli2@0.22.1`**
  (added in a recent markdownlint version; the `@claude` reviewer's rule list is
  outdated — it claims rules "top out at MD058", but `MD060/table-column-style` is a
  distinct real rule).
  Under default config it fires ~330 times on the ai-config corpus (2026-06 snapshot;
  count grows as files are added; every table with compact pipe style).
  Reproduction (move aside `.markdownlint-cli2.jsonc` first):
  `npx markdownlint-cli2@0.22.1 "**/*.md" "!codex-skills/**"`. The disable in
  `.markdownlint-cli2.jsonc` is load-bearing; do not remove it on the reviewer's say-so
  — rebut with the reproduction command. (Hit on ai-config#267.)
- **Introducing markdownlint to a legacy corpus — baseline strategy.** Run with all
  defaults first (no config): collect the full violation list. Disable every failing rule
  to achieve a green baseline with zero corpus churn. Re-enable rules incrementally after
  targeted fix passes. This prevents flooding CI with hundreds of pre-existing violations.
- **MD010/no-hard-tabs fires inside fenced code blocks too, so pasted command
  output fails lint.**
  Lots of CLI output is tab-separated --- `git ls-remote` puts a tab between
  the sha and the ref, as do `git ls-tree`, `git for-each-ref`, and `cut`/`awk`
  defaults.
  Pasting a real transcript into a ```` ``` ```` fence therefore carries those
  literal tabs into the file and fails `MD010`, which does not exempt code
  blocks under default config.
  Render the gap as spaces when quoting such output; the demonstration reads
  the same and the shas still line up.
  Worth running `npx markdownlint-cli2` locally before pushing any doc change
  that pastes command output --- the other content checks do not catch this,
  since a hard tab is neither a broken link nor a long line.
  (ai-config#725: a `git ls-remote` transcript added to `memories/git.md`
  failed `validate` on three `MD010` hits, after the link, memory-size, and
  line-break checks had all passed.)

## A literal backtick inside a Markdown code span needs a longer delimiter, not a backslash

To include a literal backtick in an inline code span, the span's delimiter
must be a **longer** run of backticks than any run inside it --- a
double-backtick delimiter holds single backticks verbatim, a triple holds
double backticks, and so on.
Backslash escaping does not work: per
[CommonMark's code-span rule](https://spec.commonmark.org/0.31.2/#code-spans),
backslash escapes are **not** processed inside code spans, and delimiter
matching is purely lexical --- the first backtick-run of equal length closes
the span.
So a single-backtick span wrapping text that itself contains a backtick closes
at that inner backtick and splits the line into garbled fragments, with the
stray backticks rendered as literal text.

No content check catches this.
It is well-formed Markdown, so `markdownlint`, the semantic-line-break check,
and `validate` all pass; only a human reviewer or a fetch of the rendered blob
sees the garble.
That puts it in the same class as the `MD010`-in-fences gotcha above: a
rendering defect the added-line checks are structurally blind to.

- **Do:** widen the delimiter to a double backtick when a code span must
  contain a single backtick, and drop any backslash escapes.
- **Do:** eyeball the rendered result (or fetch the blob) for any code span you
  write that quotes a backtick-bearing command or identifier.
- **Don't:** backslash-escape an inner backtick inside a single-backtick span
  --- CommonMark ignores the escape and the span closes early.
- **Don't:** trust green CI as evidence a code span renders correctly.

(Morrison-Lab/ai-config#1104 round 2, 2026-08-03: a new `memories/git.md`
section documenting bash command-substitution wrote
`` `git commit -m "fix the \`slast\` guard"` `` with backslash-escaped inner
backticks inside a single-backtick span.
It passed every check and garbled on GitHub; the reviewer traced the delimiter
matching and supplied a verified double-backtick fix, applied as `4b30781`.
The irony that the example *about* a backtick pitfall hit a different backtick
pitfall is the reason it is worth its own entry.)

## Office Open XML (.docx / .xlsx) — editing committed content
- `.docx`/`.xlsx` are zip archives. To strip or edit content (e.g. remove a sensitive
  link from a committed Word doc): `unzip` the file, edit `word/document.xml` for body
  text, and edit `word/_rels/document.xml.rels` for hyperlink **targets** — a clickable
  URL's address lives in the `.rels` `Target`, not just the visible `<w:t>` text, so
  delete both the `<w:hyperlink r:id="rIdN">...</w:hyperlink>` element and its matching
  `<Relationship Id="rIdN" ... Target="...">` to remove link and address.
- Re-zip from the extracted dir: `zip -r -X out.docx '[Content_Types].xml' _rels docProps word`
  (plus `customXml` if present). Verify with `unzip -t out.docx` and re-extract + grep to
  confirm the removed strings are gone before committing. (Done on ucdavis/bcs#237 to strip
  an internal SharePoint URL and a server reference from a to-do doc.)

## Evergreen-conditional citation phrasing can still regress in adjacent prose

`shared/workflow/challenge-ambiguous-terminology.md`'s "cross-repo citations
have a merge-order trap" note prescribes evergreen-conditional phrasing
("proposed in `<repo>#<PR>` --- once merged, the fragment lives at `<path>`
there") specifically so a citation never needs a follow-up edit. That
phrasing held up correctly once applied --- but while writing the *PR
description* for the companion PR, a draft sentence ("once this merges, that
citation should be tightened to the standard present-tense form") reintroduced
the same future-edit-fragility anti-pattern the citation fix had just avoided,
one level up. Caught before pushing by re-reading against the fragment's own
"never needs editing" design intent, not by a reviewer. When writing about an
evergreen-conditional citation elsewhere (a PR description, a commit message),
don't promise a future tightening --- the whole point of that phrasing is that
none is needed. (ai-config#455, 2026-07-03.)

## Personal machine setup (shiva cluster — not shared in project repos)

Personal, machine-specific tooling on the user's shiva login node (UCD PHS HPC),
deliberately NOT documented in shared project repos — collaborators don't have
these.

- **GitHub PAT stored encrypted, never as plaintext.** The user won't keep auth
  credentials as plaintext on this shared cluster (no keyring daemon available,
  no sudo to install one).
  - **At rest:** `~/.gh-token.gpg` (GPG symmetric, AES256, mode 600), created via
    `~/.local/bin/encrypt-gh-token.sh`.
  - **Unlock for a session:** `gh-unlock` (a zsh function) decrypts and exports
    `GH_TOKEN`; `gh-lock` clears it. `gh` then picks `GH_TOKEN` up from the env.
  - **Never run `gh auth login`** — it re-writes plaintext to
    `~/.config/gh/hosts.yml`. If asked to authenticate `gh` on this machine,
    remind the user to run `gh-unlock` instead.
  - **Git-over-HTTPS fallback** when `gh-unlock` can't run (an expired gpg-agent
    passphrase cache needs an interactive pinentry a non-interactive Bash tool
    can't supply): if `gh auth status` already shows a token from `hosts.yml`,
    route git through gh's credential helper inline —
    `git -c credential.helper='!gh auth git-credential' fetch/push ...` — putting
    the `-c` directly on the git command (don't pass it via a shell variable; zsh
    mangles the quoting).
  - SLURM jobs don't need the PAT; it's only for interactive `gh` / Claude Code.
- **`claude-alloc` / `codex-alloc` run agent sessions in a SLURM slice**, never
  compute on the login node directly (`claude-alloc` = Claude Code, `codex-alloc`
  = Codex CLI). Both wrap `~/bin/tui-alloc` (`~/bin` is on PATH via `~/.zshrc`).
  - **Session-in-a-slice vs. login-node + per-job compute --- pick by workload.**
    Running the whole session in a slice is safe-by-default, but it ties the session's life to the walltime: when the slice expires, the agent and every in-slice watcher die (the crash the session-notebook rule exists to survive).
    For an **orchestration-heavy session** (git/gh, PR babysitting, doc/memory work --- little actual compute), prefer launching Claude Code **on the login node** and dispatching each real compute step with `srun`/`sbatch`: the session then runs outside SLURM, so no walltime can crash it, it doesn't hold cores/memory idle for hours, and it sidesteps the nested-SLURM env-leak gotcha (the `sbatch`-from-inside-a-slice `SLURM_*` leak).
    Reserve `claude-alloc` for **compute-heavy** sessions (R tests, renders, simulations start to finish), where wrapping the session once beats `srun`-ing every step.
    The agent's Bash tool can't hold its own persistent interactive `salloc` across calls anyway (each call is a fresh shell), so "the agent manages its own slice" isn't an option --- it's either a user-launched slice (`claude-alloc`) or per-command `srun`/`sbatch`.
    A login-node session's own footprint (git/gh/grep/edits/orchestration) is light and fine on the head node; only real compute must be dispatched.
  - Defaults: 8 hwthreads (4 physical cores), `--mem=32G`, `--time=24:00:00`,
    `--exclude=c1` (the GPU node). Override per-launch with `ALLOC_CPUS`,
    `ALLOC_MEM`, `ALLOC_TIME`. The walltime default was 12h until 2026-07-24
    and was too short (it expired mid-session, killing the agent and every
    in-slice background watcher); raised to 24h. The limit is a courtesy
    choice, not a cluster constraint (`normal` reports `MaxTime=UNLIMITED`).
  - **A running slice cannot be extended:** `scontrol update jobid=<id>
    TimeLimit=...` is denied for a normal user (only operators may raise a
    limit), so a slice keeps its launch-time walltime for its whole life ---
    plan it up front. Anything inside the slice dies with it; a detached
    `sbatch` job does not, which is why heavy compute goes out as a batch job
    and a long watch loop should be re-armed after a restart.
  - **Always set `--mem`** (the launchers do): the `normal` partition uses
    `CR_CORE_MEMORY` with `DefMemPerNode=UNLIMITED`, so omitting `--mem` grabs the
    node's whole ~772G and locks everyone else out.
  - **Name the conda env for bcs work:** `ALLOC_CONDA_ENV=bcs claude-alloc`. A
    `chpwd` hook sets it automatically inside `~/Projects/bcs*` checkouts. The
    launchers are otherwise project-agnostic — they only read `ALLOC_CONDA_ENV`.
  - **Exit takes two steps** (salloc -> srun --pty zsh -> agent): quit the agent
    (`/exit`) to drop to the allocation shell (slice still held), then `exit` the
    shell to release the slice. Force-release with `scancel $SLURM_JOB_ID`; check
    for a forgotten slice with `squeue -u $USER` (job name `claude`/`codex`).
  - **When your own array jobs saturate the cluster:** `~/bin/yield-array
    <arrayjobid>` temporarily lowers that array's `ArrayTaskThrottle` to free
    a slot, launches the session (default `claude-alloc`), then restores the
    throttle on clean exit --- but NOT on a hard kill / walltime death, so undo
    manually with `scontrol update jobid=<id> ArrayTaskThrottle=<orig>`.
  - **zsh must live on the shared filesystem; there is no system zsh to fall
    back on.**
    `tui-alloc` runs `zsh -i` inside the srun step, and zsh is not provisioned
    on the compute nodes (confirmed missing on c2), so a slice landing there
    died with exit 127
    (`env: 'zsh': No such file or directory`).
    Fixed by installing a
    shared-`/home` zsh all nodes see via PATH (`conda install -n base -c
    conda-forge zsh` -> `~/miniconda3/bin/zsh`); `tui-alloc` also guards by
    dropping to `bash -i` if zsh isn't resolvable on the node.
    There is no `/usr/bin/zsh` on the login node either, as of 2026-07-31 ---
    `which zsh` resolves to the conda build from every node, so the shared
    install is the only zsh on the cluster rather than merely the portable
    one.
  - Full usage/exit doc: `~/.config/tui-alloc/README.md`.
  - **The launcher sources are tracked** in ai-config under
    `dotfiles/shiva/`, installed by `dotfiles/shiva/install.sh` (which
    `bootstrap.sh` runs).
    Edit them there, not in `~/bin` --- the installed copies are symlinks back
    into the checkout.
- **`cnode` is the agentless sibling**: a plain interactive zsh on a compute
  node, for when you want a shell rather than a coding agent.
  It differs from the `tui-alloc` family in four ways worth knowing.
  - **Bare `srun`, not `salloc` plus a step.** One layer, so one `exit`
    releases it, where the `tui-alloc` layering needs two.
  - **No `--exclude=c1`**, so it can land on the GPU node.
  - **`CNODE_CPUS` / `CNODE_MEM` / `CNODE_TIME` / `CNODE_ZSH`**, not the
    `ALLOC_*` names, and its walltime default is `1-00:00:00`.
  - **It hardcodes `~/miniconda3/bin/zsh`** rather than resolving `zsh` on
    PATH.
    That is belt-and-braces, not a workaround: the conda zsh IS on PATH on
    every node, which is what lets `tui-alloc` use `command -v zsh`.
- **Both refuse to nest.** `refuse_if_nested` (in
  `dotfiles/shiva/lib/slurm-guard.sh`, shared by `cnode` and `tui-alloc`)
  exits rather than grabbing a second allocation from inside an existing one,
  because a nested `srun`/`salloc` contends with its parent allocation's own
  step instead of getting new resources.
  Measured 2026-07-31: that deadlocked two jobs, one holding c1 while the
  other sat PENDING on Resources.
  It keys on `$SLURM_JOB_ID` first, falling back to checking `sinfo`'s node
  list for a shell that reached a compute node without one.

## Fact-check code comments' factual claims — a false one can survive many review rounds

A code comment asserting a checkable fact ("grepl() returns NA for NA
input") is prose the review bots tend to accept as given, especially when
it justifies adjacent defensive code: this one survived ~10 independent
review passes across two PRs before being caught — and only because a
WRONG Copilot finding on a third PR prompted an empirical check
(`grepl("a", NA)` is FALSE; it's `sub()`/`gsub()` that propagate NA — and
the guard it justified was load-bearing for a different reason:
`NA != ""` yields NA). Verified empirically in R 4.6.1
(`grepl("a", NA)` → FALSE; `sub("a", "b", NA)` → NA;
`gsub("a", "b", NA)` → NA; `NA != ""` → NA), and by `?grep` itself:
"Both 'grep' and 'grepl' take missing values in 'x' as not matching a
non-missing 'pattern'." When writing or reviewing a comment that states a
language/library behavior, run the one-liner that checks it instead of
trusting plausibility; when a reviewer finding is wrong, check whether the
code's own documentation made the same wrong claim — the finding often
mirrors prose it read in-context. This same claim was later re-disputed
by a reviewer citing a doc line that does not exist in `?grep` — a
reminder that the empirical one-liner outranks any quoted documentation,
including a reviewer's. (ucdavis/rampp #138/#111, 2026-07-17;
re-verified on ai-config#611, 2026-07-18.)

## Python regex features must fit the oldest runtime that will run the script

Do not choose a regex construct only because CI accepts it.
A repository can run validation under Python 3.12
while local sessions and users run the same script under Python 3.10,
so a syntax added in 3.11 fails before the code under review even starts.
Atomic groups, `(?>...)`, are the concrete trap:
they compile under Python 3.11+ and fail under Python 3.10.
Use a portable form,
such as a negative lookahead on a quantified run,
when the same backtracking guard is needed across those runtimes.

- **Do:** check the oldest Python runtime that will execute a script
  before using recently added `re` syntax.
- **Do:** prefer a portable negative-lookahead pattern
  when it expresses the same guard.
- **Don't:** treat `actions/setup-python`'s CI version
  as the only supported interpreter for a repo script.
- **Don't:** use an atomic group in ai-config scripts
  until local and CI Python floors both support it.

(Morrison-Lab/ai-config#1029/#1034:
the local session's `python3 --version` reported Python 3.10.18,
while `.github/workflows/validate.yml` pins `actions/setup-python` to Python 3.12.
The context-closure parser therefore could not use Python 3.11 atomic groups
to stop fence-regex backtracking;
the portable fix was a negative lookahead.)

## Windows Git Bash: `python`/`python3` may resolve to the Store stub; use `py`

On at least one Windows setup, `python` and `python3` both resolve on
`PATH` inside the Git Bash tool, but only to the Windows Store
install-shortcut stub. They print `Python was not found; run without
arguments to install from the Microsoft Store, or disable this shortcut
from Settings > Apps > Advanced app settings > App execution aliases`
instead of running the script, with a nonzero exit code. The `py` launcher
(the standard Windows Python launcher, installed alongside python.org
Python) works fine and should be the first thing tried when `python3 -c
"..."` fails with that specific message — don't waste a retry loop guessing
at other causes. When scripting a small one-off transform inline (e.g. a
Bash tool call doing a targeted string replacement Edit's exact-match
failed on), resolve which launcher actually works before using it, rather
than relying on the combined exit status of `A || B` (which tells you
*something* succeeded, not *which side*): probe each candidate
non-mutating and stop if neither works, rather than assuming the last one
must be fine. Use `if`/`elif`, not a `||`-chained subshell assignment
(`(cmd && VAR=x) || ...` looks like it works but the subshell's `VAR=x`
never reaches the parent shell — verified this by testing both forms
before publishing this note) —
```sh
if python3 -c "pass" >/dev/null 2>&1; then PY=python3
elif py -c "pass" >/dev/null 2>&1; then PY=py
else echo "no working python launcher found"; exit 1
fi
```
— then invoke `$PY` for the real transform. This both avoids risking a
second, possibly destructive run of a real script under a bare `||`
fallback, and fails loudly instead of proceeding with an unverified
command if neither launcher actually works. (ai-config#635,
2026-07-22/23: hit repeatedly running `scripts/validate-skills.py`, and
again scripting a one-off text replacement after an `Edit` tool call's
`old_string` failed to match despite `grep` showing byte-identical content
in the file.)

## `scripts/semantic-line-breaks.py` previews by default and scopes its writes

**Fixed in ai-config#951.**
This entry is kept because the old behaviour is what most of this corpus was
written against, and because the failure it describes is worth recognizing in
any formatter.

It used to be an unconditional in-place reformatter over every prose
paragraph in each file it was given --- no `--check`, no `--dry-run`, no diff
scoping, with `main()` taking bare paths and calling `path.write_text()`.
Running it on a mature file to tidy a few lines you had just appended
reflowed everything else too: on `memories/r-quarto.md` a 65-line addition
came back as `273 insertions(+), 923 deletions(-)`, burying the actual change
and rewriting `git blame` for content nobody touched.
Measured against a copy of `CLAUDE.md`, the unguarded version changed 342 of
1163 lines.

It now behaves the way the entry above used to tell you to behave by hand:

- naming a path **previews** a unified diff and writes nothing
- `--write` applies it, scoped to the lines changed against `--base`
  (default `origin/main`)
- `--all` widens to the whole file
- a scope it cannot determine is a **loud error**, never a silent widening

So the old advice --- format new prose by hand, and `git checkout -- <file>`
if you ran it by reflex --- is no longer needed for its own sake, though a
preview is still worth reading before passing `--write`.

The contrast that motivated the fix: its CI counterpart,
`check-new-line-breaks` in
[`d-morrison/gha`](https://github.com/d-morrison/gha), was diff-scoped by
design from the start, so a corpus's pre-existing drift is never reflagged.
The checker got that treatment years before the formatter did.

## macOS disk cleanup: where the space actually goes

Findings from a full sweep of the user's Mac, 2026-07-28, when the data
volume hit 97% full.
The order below is the order worth checking, since the biggest directories
are rarely the most reclaimable.

**A OneDrive account re-link orphans the entire old sync folder, and it
keeps every byte.**
Re-linking renames the previous folder with a timestamp suffix
(`OneDrive-<Org> (5-1-25 9:55 PM)`) and starts a fresh one alongside it.
The new folder syncs with files-on-demand, so it reports a few MB on disk
while holding the same content; the orphan holds real local bytes for all
of it and no longer syncs to anything.
The result is a directory that looks like live cloud storage and is neither
live nor reclaimable by any OneDrive setting.
33 GB in this case, against 2.1 MB for the live folder holding the same
tree.

Two checks settle whether an orphan is safe to delete, and both are cheap:

- **Name-diff it against the live folder** rather than trusting the
  timestamps.
  `find . -type f | sort` in each, then `comm -23`, lists exactly what
  exists only in the orphan.
  Here that was 103 files out of 11,428, all of them collaborator-marked
  manuscript drafts the live sync had never received.
  Copy those in and verify by size plus `md5` before deleting anything.
- **Check for FileProvider extended attributes on the two roots.**
  `ls -ld@` names them, and the live root carries
  `com.apple.file-provider-domain-id` while a detached one has no xattrs at
  all.
  Prefer that over reading the bare `@` marker in `ls -l` output, which only
  says *some* xattr is present.
  This is the direct evidence deletion is local-only, and it is worth having
  before removing a directory that sits under `CloudStorage/`.

Note that `ls -l` reports logical size for dataless placeholder files, so a
folder full of them can look enormous while occupying nothing.
Compare `du -h` against `ls -l` on a large file to tell real bytes from
placeholders: on a fully-downloaded file the two roughly agree, while a
placeholder reads `0B` under `du` and its full size under `ls -l`.
`ls -ldO` names the condition outright, flagging such a file `dataless`.

**`du` totals across `~/Library` double-count OneDrive and Google Drive.**
`CloudStorage/OneDrive-<Org>` and
`Group Containers/UBF8T346G9.OneDriveStandaloneSuite/OneDrive - <Org>.noindex`
are the same data seen twice.
Don't sum them when estimating what a cleanup will free.

**A Parallels VM is usually not the win its size suggests.**
Check before doing anything:
`prl_disk_tool compact --info --hdd "<vm>.pvm/harddisk.hdd"`.
It prints allocated versus used blocks, and the gap between them is the
entire reclaimable amount.
A 75 GB disk here showed 76,540 allocated against 76,437 used at 1 MB per
block, so compaction was worth about 100 MB.
There is no `info` subcommand despite the name, and no snapshots means no
hidden `.hds` growth to find either.
What is genuinely reclaimable is the suspend-state `.mem` file (a few GB, at
the cost of discarding the suspended session) and the guest pagefile via
`--exclude-pagefile`, whose help text reads `remove the page file from the
disk` -- it reclaims that space rather than skipping it, despite a name that
reads the other way.
`--force` is about the suspended state rather than either of those: its help
is `forcibly drop the suspended state before compacting the disk`, so it is
what lets `compact` run at all against a suspended VM.
A VM already shut down cleanly needs neither `--force` nor a `.mem` deletion.

**Everything else, in rough order of yield.**
`~/.ollama` holds multi-GB models that `ollama list` dates by last use, and
`ollama rm` reclaims immediately with a `pull` to undo it.
Chrome keeps a 4 GB on-device model under
`Application Support/Google/Chrome/OptGuideOnDeviceModel`, separate from
its profile and cache directories.
Outlook's local mail store under `Group Containers/UBF8T346G9.Office/Outlook`
shrinks only by narrowing the sync window in Outlook's own settings.
Regenerable dev caches worth sweeping together: `~/.cache/codex-runtimes`,
`~/.cache/puppeteer`, `~/.cache/uv`, `~/Library/Caches/{copilot,github-copilot-sdk,ollama}`,
plus `npm cache clean --force` and `brew cleanup --prune=all`.

## Two shell gotchas that make a path silently unreachable

Both surfaced in the disk sweep above, and both produce a confident wrong
answer rather than an obvious error.

**macOS writes U+202F (narrow no-break space) before AM/PM in generated
names.**
A path copied from `ls` output then quoted normally fails with
`No such file or directory`, because the quoted string carries a regular
space where the name has U+202F.
Nothing about the error hints at an encoding mismatch, and the two glyphs
are visually identical in terminal output.
Confirm it by piping the name through `xxd -p` and looking for `e280af`,
then avoid retyping the path at all: capture it with a glob into a
variable (`D=$(ls -d 'prefix'*)`) and use `"$D"` from there.

**`rsync` treats a path with a colon before the first slash as a remote
host.**
A directory named with a time in it (`... 9:55 PM`) is therefore parsed as
`host:path`, and the run dies with `hostname contains invalid characters`
followed by `unexpected end of file`.
Worse, the wrapper can still exit 0, so a script that checks only the exit
status concludes the copy succeeded -- the
[`fail-fast`](../shared/principles/fail-fast.md) trap, in a tool nobody
expects it from.
Prefix the source with `./` so a slash precedes the colon, or use a `cp`
loop when the file list is small enough not to need rsync.

## Markdown linting (markdownlint, lint-qmd)

- **Table rows must stay on one line (MD055/MD056).**
  Wrapping a cell across lines breaks the `|` alignment and trips both rules.
  Rewrite the cell concisely on a single line rather than word-wrapping it.
  Prefer a short, complete description over hitting a length target.
- **Don't tag a non-shell CLI block `bash`/`sh` (MD040).**
  MD040 wants a language on every fence, which invites tagging anything command-shaped as `bash`.
  Claude slash commands (`/ums`, `/plugin`, `/also`) and other application-level directives are not shell-executable, so `bash` implies a reader can run them and they fail when someone tries.
  Tag those `text` instead.

(Recovered 2026-07-30 from `a739c69`, an orphaned commit on `ums/ardi-review-link-handling`: it landed about 30 minutes after its own PR [#650](https://github.com/Morrison-Lab/ai-config/pull/650) merged, so it never reached `main` and sat unnoticed for a week.
Both rules were first learned on [#645](https://github.com/Morrison-Lab/ai-config/pull/645).)

## The Bash tool runs zsh here, and zsh does not word-split unquoted expansions

Kin to the two path gotchas above --- it produces a confident wrong answer
rather than an error --- but it is not about paths, so it gets its own entry.

`SHELL=/bin/zsh` on this machine, and zsh leaves `SH_WORD_SPLIT` **off** by
default.
So an unquoted parameter expansion stays one word, where bash would split it:

```zsh
r="804 MERGED 2026-07-29"
set -- $r      # zsh: $1="804 MERGED 2026-07-29", $2=""   <- bash: $1="804", $2="MERGED"
set -- ${=r}   # zsh: $1="804", $2="MERGED"               <- the = flag forces splitting
```

`for x in $list` has the same shape: one iteration over the whole string
rather than one per word.

**Nothing errors.** `$2` is simply empty, so a downstream `[ "$2" = "MERGED" ]`
is false and every row of a report comes back the same wrong way.
That uniformity is what sells it: a loop over 19 branches printing `no-PR` for
all 19 reads as a finding about the branches, not as a broken parser.

Prefer a form that needs no word splitting at all, since it is also portable
back to bash:

```zsh
num=${r%% *}; rest=${r#* }; state=${rest%% *}   # parameter expansion
read -r num state date <<< "$r"                 # or read into named vars
```

Reach for `${=r}` only when you specifically want zsh's splitting and know the
script will never run under bash.

- **Do:** parse with parameter expansion, `read`, or `awk`, rather than
  relying on the shell to split an unquoted expansion.
- **Do:** suspect the parser first when every row of a generated table reports
  the same value.
- **Don't:** carry a `set -- $var` idiom over from bash notes and assume it
  splits here.
- **Don't:** put `2>/dev/null` on the command whose output the table is built
  from --- that hides the other half of this failure class (see
  [`fail-fast`](../shared/principles/fail-fast.md)).

(2026-07-29/30, one ai-config session, twice.
The second time, a branch sweep reported all 19 local branches as having no
PR; the immediately preceding run of the same data had correctly shown 16 as
`MERGED`, which is the only reason the contradiction was noticed at all.)

## `grep` in a Claude Code session is a shell function, so a script gets a different program

Sibling of the entry above: another case where the harness's shell is not the
one you are reasoning about, and it also answers rather than erroring.

`grep` at the Bash tool's prompt is a **function** the harness installs,
routing to a `ugrep` bundled inside the `claude` binary rather than to any
`ugrep` on `PATH`.
A function does not reach a child shell unless it was exported, so a script
or a git hook gets the real binary instead.

**The mechanism, the `export -f` caveat, and the git-hook consequence live in
[`errexit-is-not-uniform`](../shared/coding/errexit-is-not-uniform.md)** ---
read it there rather than here.
That file is auto-loaded via `CLAUDE.md`, and its "A status consumed as a
predicate" section carries all three; it reached `main` with ai-config#1110
(merged 2026-08-04 as `fcb4ee10`).
This entry keeps only what a *tool* lookup needs, since that is what someone
grepping this file is after.

**Identification is the part that misleads**, because the obvious commands
disagree about what they are reporting:

| command | when a function is winning | what it actually reports |
|---|---|---|
| `command -v grep` | prints bare `grep` | that the winner is **not a binary on `PATH`** --- it does not say what kind |
| `type -aP grep` | prints only binaries (rc=1 if none) | `-P`aths only, so it hides the function entirely |
| `type -a grep` | prints the function first | the full resolution order |
| `type -t grep` | `function` / `file` / `builtin` | the kind --- run it *inside a script* to learn what a script gets |

**A bare name from `command -v` is not specific to functions.**
Measured on bash 5.1.16: `command -v` prints a bare name for builtins and
keywords too --- `cd`, `echo`, `test`, and `if` all print just themselves,
while `command -v /usr/bin/grep` prints the path.
So the bare name means "not a binary on `PATH`", and `type -t` is what
narrows it to a function.

- **Do:** use `type -a` for the resolution order and `type -t` from inside a
  throwaway script to learn what a script will actually get.
- **Don't:** read a bare name from `command -v` as confirming a binary was
  found, and don't read it as proving a *function* either --- builtins and
  keywords print the same thing.
- **Don't:** infer a `PATH`-shadowing binary from a command behaving oddly ---
  check for a function first, since no such binary need exist.

(Morrison-Lab/ai-config#1110, 2026-08-03: a `grep -q` exit-status divergence
between a prompt and a script was published as `ugrep 7.5.0` sitting on `PATH`
ahead of `/usr/bin/grep`.
Neither half held.
Corrected in `9c986521`.

Version numbers here are deliberately scoped rather than stated flat.
An earlier draft said the two `grep` binaries were "both GNU 3.7", which is
what this machine reports and is false elsewhere --- the reviewer that caught
it measured **3.11** on a GitHub Actions runner, and both readings are
correct.
On this machine `/usr/bin/grep --version` and `/bin/grep --version` both
report 3.7, and `readlink -f` shows they are the same file, so even "two
binaries" was generous.
An unscoped version claim is not merely imprecise; it is false on some
machine, which is why every number in this entry names where it was taken.)

## A hand-rolled verification check is worth nothing until it has caught something

Two ad-hoc pre-push checks failed in one session, in opposite directions,
while a maintained instrument for one of them sat in a checkout already on
disk.
Both reported clean.
Both were quoted as evidence in a PR body.

- A multi-sentence-line detector tested `line.count('. ') > 1`, which only
  fires at **three** sentences on a line, so every two-sentence line passed.
  It reported 0; the real count was 12.
- A banned-punctuation scan was written as an inline heredoc, and shell
  quoting collapsed its character class `'--""''x'` into one string
  containing ASCII `"`, so it flagged any line with a double quote.
  It reported a phantom hit on clean text.

The two failure directions are what make this worth a rule rather than a
shrug.
One under-reported and one over-reported, so neither "it found nothing" nor
"it found something" is self-validating.

**Prefer the maintained instrument, and know where it lives.**
For semantic line breaks that is
`<gha-checkout>/check-new-line-breaks/check-new-line-breaks.py`, run as
`NLB_BASE_REF=origin/main python3 <path>`.
Reaching for a hand-rolled substitute when a real one is one path away is the
error underneath whatever the regex got wrong, per
[`deterministic-tools`](../shared/principles/deterministic-tools.md).

**When a check must be ad hoc, write it to a file rather than an inline
heredoc.**
Quoting is where these break, and a file removes the shell from the problem
entirely.

**The maintained instrument's silence is not proof either**, for two reasons
of its own.
It has a blind spot: a sentence opening with a bare lowercase identifier is
not seen as a sentence boundary, so a line of exactly the shape this corpus
keeps writing goes unflagged
([gha#389](https://github.com/Morrison-Lab/gha/issues/389)).
And it is advisory, exiting 0 whatever it finds, so its green CI result never
meant the diff was clean.
Read its output, not its conclusion.

- **Do:** run the maintained checker against your own diff before pushing,
  and quote *its* output as the verification.
- **Do:** put an unavoidable ad-hoc check in a file, and sanity-test it on an
  input you know should fail.
- **Don't:** cite a hand-rolled check's clean result in a PR body as evidence.
- **Don't:** read an advisory check's green CI status as a verdict on content.

(2026-07-31, [ai-config#964](https://github.com/Morrison-Lab/ai-config/pull/964):
the review caught 8 of the 12 lines my own detector had missed, and then a
further one that the maintained tool had missed too.)

## `cmd | python3 - <<EOF` reads the heredoc, not the pipe, so `sys.stdin` scans nothing

Piping data into an interpreter invoked as `python3 -` (or `sh -`, `bash -`)
while *also* supplying the script through a `<<'EOF'` heredoc puts two things in
line for one stdin, and the heredoc wins.
The interpreter consumes the heredoc as its program, so the `-` that was meant
to read the piped data has nothing left to read.
A script that loops over `sys.stdin` iterates zero times, whatever was piped in:

```bash
some_command | python3 - <<'EOF'
import sys
for line in sys.stdin:   # reads the ALREADY-CONSUMED heredoc, i.e. nothing
    ...                  # loop body never runs
EOF
```

A scan built this way reports "0 found" on every input, which is a false
all-clear of exactly the shape [`fail-fast`](../shared/principles/fail-fast.md)
warns about in its "check you run by hand" section --- the pass path and the
failure path print the same thing.
It is also a "false claim about state" of the kind `CLAUDE.md`'s "Run UMS
proactively" section makes a trigger, since the scan asserts the corpus is
clean when it was never read.

The fix is to keep the pipe as the only stdin, or read a file instead of stdin:

- **Read a file.** Write the piped output to a temp file, then `python3 check.py
  <file>` reading `sys.argv[1]` --- the heredoc/`-` collision disappears because
  there is no `-`.
- **Put the script in its own file.** `some_command | python3 check.py` leaves
  the pipe as stdin, since no heredoc competes for it.
- **Use `-c` for a one-liner.** `some_command | python3 -c '...'` keeps stdin
  the pipe, because the program arrives as an argument rather than on stdin.

And give any such scan a **positive control** before trusting a zero: feed it
input you KNOW contains a violation and confirm it flags that, per
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)'s
positive-control discipline and [`fail-fast`](../shared/principles/fail-fast.md).
An instrument never once seen to flag anything is not yet an instrument.
This is the specific-mechanism companion to "A hand-rolled verification check is
worth nothing until it has caught something" above; that entry's heredoc failure
was shell *quoting*, this one is stdin *contention*.

- **Do:** read the data from a file argument (`sys.argv[1]`), or pipe into a
  script file or `python3 -c`, so the piped bytes are what gets scanned.
- **Do:** run a positive control that must flag, before believing a zero.
- **Don't:** pipe into `python3 -`/`sh -`/`bash -` and also feed the program
  through a `<<EOF` heredoc --- `sys.stdin` then reads the heredoc, not the pipe.
- **Don't:** trust a "0 candidates" result from a scan that has never been seen
  to report a nonzero.

(2026-08-03, an ai-config session: this idiom was used to verify ai-config#1078's
diff for semantic-line-breaks, and it read nothing --- a real multi-sentence-line
violation was reported as "0 found" and the vacuous all-clear was stated to the
user before the method was caught.)

## A process substitution feeding a pipeline fails under zsh, and reads as a clean zero

`diff <(a) <(b)` works at a zsh prompt and breaks the moment it feeds a pipe.
The piped form dies with `diff: /proc/self/fd/11: No such file or directory`,
because the path `<(...)` names no longer resolves when `diff` opens it.
Bash runs the identical line correctly, so a snippet copied from a bash script
or another machine silently changes meaning here.

Measured on zsh 5.9 and bash 5.1.16, against two files known to differ:

```bash
diff <(cat f1) <(cat f2)                             # zsh: works
o=$(diff <(cat f1) <(cat f2))                        # zsh: works
diff <(cat f1) <(cat f2) | grep -c '^>'              # zsh: /proc/self/fd error
bash -c 'diff <(cat f1) <(cat f2) | grep -c "^>"'    # bash: correct answer
```

The pipeline is the trigger.
Neither the surrounding `$(...)` nor a shell function inside the `<(...)` is
required, since plain `cat` in a bare pipeline fails the same way.

**The failure presents as an all-clear rather than as an error.**
`diff` writes its complaint to stderr and produces no stdout, so a downstream
`grep -c` counts zero, and a trailing `|| true` makes that zero unconditional.
The caller reads `0` as "the two inputs are identical".
This is the [`fail-fast`](../shared/principles/fail-fast.md) shape where the
pass path and the failure path print the same thing, reached by a route that
fragment does not cover: the comparison never ran at all, rather than its exit
status being swallowed.
The `|| true` could not have helped in any case, because a pipeline reports
only its last command's status --- see
[`errexit-is-not-uniform`](../shared/coding/errexit-is-not-uniform.md)'s
"A pipe discards the status of everything left of it".

Take the fd plumbing out of the comparison, and prove the detector works before
believing any zero it reports:

```bash
norm "$tracked" > /tmp/a; norm "$inst" > /tmp/b      # real files, no <(...)
printf 'a\nb\n' > /tmp/nc1; printf 'a\nZZZ\n' > /tmp/nc2
nc=$(diff /tmp/nc1 /tmp/nc2 | grep -c '^>')
[ "$nc" -ge 1 ] || { echo "DETECTOR BROKEN --- aborting"; exit 1; }
add=$(diff /tmp/a /tmp/b | grep -c '^>')
```

The negative control is the load-bearing half, per
[`batch-merge-and-resolve`](../shared/workflow/batch-merge-and-resolve.md)'s
"Any conflict sweep needs a negative control".
A zero from a detector never once seen to report a difference is not evidence
about the inputs.
This is the third sibling of the two entries above, whose plumbing failures
were shell *quoting* and stdin *contention*; this one is fd *lifetime*.

- **Do:** write both sides to real temp files and diff those, whenever a
  process substitution would otherwise feed a pipeline.
- **Do:** run a known-differing negative control first, and abort when the
  detector reports no difference.
- **Don't:** pipe the output of a command reading `<(...)` under zsh, on the
  strength of the same line working in bash or at a bare zsh prompt.
- **Don't:** read `0` from a `... | grep -c` as agreement when the producer
  could have died before writing anything.

(2026-08-03, auditing six installed dotfiles against their tracked copies on
shiva: `add=$(diff <(norm "$tracked") <(norm "$inst") | grep -c '^>' || true)`
reported `installed-only=0 repo-only=0` for all six files, which was read as
"identical apart from em-dash normalization".
Every one of those runs had emitted the `/proc/self/fd/11` error on stderr.
Re-run against temp files, four of the six differed --- `tui-alloc` by 6
installed-only and 15 repo-only lines.
Every `<(...)` use already in this corpus was checked and is safe, since none
feeds a pipeline: `skills/use-math-macros/SKILL.md`'s bare `comm -23`, plus the
`< <(...)` redirects in `skills/cascade/SKILL.md` and
`references/cloud-setup/cloud-setup.sh`.
Derive that set rather than counting it, since a count goes stale on the next
one added: `git grep -n '<(' -- ':!memories/'`.)

## Splitting a shell command into simple commands in Python: two `shlex` gotchas

When a Python guard splits a shell command string into its component simple
commands (to attribute an exit status, to find a trailing `echo`, to scope a
matcher), `shlex` gets two things wrong that both fail silently by merging
commands that should stay separate.

**`shlex` treats a newline as ordinary whitespace and drops it.**
An unquoted newline is not emitted as a token, so two commands written on two
lines merge into one:

```python
list(shlex.shlex("a\nb", punctuation_chars=True))   # ['a', 'b'] --- the \n is gone
```

There is no separator token to split on, so convert unquoted newlines to `;`
before tokenizing if a newline should end a command.

**`shlex.shlex(punctuation_chars=True)` conflates redirection with control
operators.**
Its default punctuation set is `();<>|&`, which lumps the *redirection*
operators `<` and `>` in with the command separators.
A redirect belongs to its command rather than terminating it, so `a > f; b`
must not split at `>`.
Pass only the genuine separators as the punctuation set:

```python
shlex.shlex(cmd, punctuation_chars=";&|()")   # not the default ();<>|&
```

Both produce a guard that reads a per-step outcome off the wrong boundary,
which for a discharge/attribution guard is exactly the "combined result cannot
attribute a per-step outcome" failure in
[`fail-fast`](../shared/principles/fail-fast.md).
(Morrison-Lab/ai-config#1042, 2026-08-03: both surfaced while building
`hooks/no-unreviewed-pr.py`'s shell-command parser during its review.)

## Two awk gotchas when an awk program is embedded in a single-quoted shell string

Many of our shell scripts pass an awk program as a **single-quoted** bash string
(`tr -d '\r' | awk -v ... '<program>'`).
Two failure modes recur when editing the program, and both are worth knowing
before touching one.

**An apostrophe or a bare backtick inside the awk body breaks the whole script.**
Inside the single-quoted program, any `'` closes the bash quote, and a `` ` ``
after it becomes command substitution.
The offending token is almost always in an awk **comment**, where it reads as
harmless prose: `awk's`, `#345's`, `iteration's` each broke the script.
The symptom is a bash error, not an awk one --- `line N: <word>: command not
found`, then `awk: syntax error ... missing }` --- because bash tears the string
apart before awk ever runs.
Reword the comment (`awk's` -> "the ... that awk uses"); the gha strip scripts
deliberately keep apostrophes out of awk comments.
It is algorithmatizable: a check that flags an apostrophe or backtick inside a
single-quoted awk body would catch it every time.

**awk regexes are POSIX ERE, which has no backreferences, so a `\1` pattern
silently never matches** --- it does not error, it just fails, which is the
dangerous direction (the check quietly passes instead of blowing up).
A thematic-break regex `/^([-*_])[ \t]*(\1[ \t]*){2,}$/`, meant to match `---` /
`***` / `___`, matched nothing.
Rewrite "the same character repeated" as an explicit character-count loop: read
the first character, require every later character to equal it or be a
space/tab, and require the count to be `>= 3`.

(Both surfaced on Morrison-Lab/gha#403, 2026-08-03, in the same
`strip-non-invoking-markup.sh`.
Sibling embedding trap: a bare `---` at column 0 inside a YAML `run: |` block is
a document separator that truncates the generated script.)

## validate-skills.py token validation

- **`validate-skills.py` checks backtick-wrapped `ALL_CAPS_WITH_UNDERSCORE` tokens against `tool-mappings.yml` operation IDs.**
  Any backtick-wrapped ALL_CAPS string (such as `GEMINI_API_KEY`, `GITHUB_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`) that represents an environment variable, secret, or API constant rather than an abstract operation ID must be added to `NON_OPERATION_TOKENS` in `scripts/validate-skills.py` to avoid validation errors.

## check-pr-fully-clean.py automated ARDI verification

- **[scripts/check-pr-fully-clean.py](../scripts/check-pr-fully-clean.py) `<pr-number>` programmatically enforces ARDI fully-clean criteria.**
  It checks that:
  (1) all CI check runs for the PR's exact HEAD commit SHA are `completed` with conclusion `success`, `neutral`, or `skipped`,
  (2) an automated review comment evaluating that HEAD SHA has been posted, and
  (3) the latest review comment for that HEAD SHA contains zero findings and no formal `CHANGES_REQUESTED` or `REJECTED` state.
  Returns exit code 0 only when fully clean.
  Run before declaring any ARDI loop complete or unclaiming a PR.

