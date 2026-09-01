In every session --- at session start, and again periodically during long sessions --- refresh the local state that goes stale as PRs merge elsewhere:

1. **The ai-config checkout.** Check that the local ai-config clone is on `main` --- not a leftover work branch from an earlier session --- and run `git pull --ff-only`.
   Only switch back to `main` when the working tree is clean; leave a dirty tree or another session's in-flight work alone and flag it instead.
   **If `pull --ff-only` fails with "diverged" rather than a dirty-tree error**, don't assume unpushed work is at risk --- a fresh container can seed local `main` from a stale/orphaned snapshot (e.g. a pre-history-rewrite state) whose commits never landed on `origin/main` at all.
   Confirm the working tree is clean (`git status --short`), then settle it by **content**, not by commit identity.
   `comm -23 <(git ls-tree -r --name-only main | sort) <(git ls-tree -r --name-only origin/main | sort)` returning nothing, plus a spot-check that a few of those files' contents match, means realigning loses nothing and is safe: `git checkout -B main origin/main`.
   **Don't decide this by matching the divergent commits' subjects against `git log origin/main`.**
   A squash merge writes one commit whose subject is the PR title, so a merged branch's own subjects are absent from `origin/main` by construction, and the check reports "orphaned" for ordinary merged work --- the alarming direction.
   See [`fail-fast`](../principles/fail-fast.md), "A proxy that answers a narrower question passes the same way".
   Still flag it rather than force if the tree is dirty, or if a path on local `main` is genuinely missing from `origin/main`.
   **If `main` isn't the currently checked-out branch** (the session is already working on a feature branch), skip the checkout dance entirely --- `git branch -f main origin/main` realigns the ref in place without touching the working tree or switching away from the branch you're actively on.
2. **The `~/.claude` consumer install.**
   Claude Code and Cursor no longer read this repo's `skills/`/`commands/` as a symlinked copy under `~/.claude` at all --- they install this repo as a native plugin, which auto-updates at session start (see README's *Verify the install*), so the served copy needs no freshness check.
   That is a claim about what is **served**, and not about what is **left over**.
   `shared/`, `hooks/`, and `memories/` have no plugin-equivalent replacement yet ([#2352](https://github.com/Morrison-Lab/ai-config/issues/2352)), so anyone relying on `~/.claude/shared`, `~/.claude/hooks`, or `~/.claude/memories` today is on a symlink or copy placed by an install predating that change, or by a manual step --- `bootstrap.sh` no longer places any of them.
   **`skills/` belongs in that sweep too, and the plugin serving them is not a reason to skip it.**
   A leftover `~/.claude/skills` from a pre-plugin install loads alongside the plugin, listing every skill twice --- bare `ums` beside `ai-config:ums` --- which crowds the skill listing and can cost entries their descriptions, the text routing selects on.
   Measured 2026-08-27 ([#2405](https://github.com/Morrison-Lab/ai-config/issues/2405)), found by Claude Code's built-in `/doctor` rather than by this check.

   **Detecting it is harder than the other three, and this file does not yet have a reliable test.**
   Those three are paths no client creates, so finding one is the finding.
   `~/.claude/skills` is a standard client location, holding a user's own personal skills and an account-level `synced/` bucket the client populates --- on the machine measured 2026-08-28 that bucket carried 45 directories whose names match this repo's skills, none of them a leftover.
   So neither presence nor a name match settles it, and a wrong answer is expensive in one direction: deleting that directory takes the user's own skills with it, and this corpus references `~/.claude/skills/...` paths directly in 31 places (`grep -rn '~/\.claude/skills/' --include=*.md skills/ shared/ memories/`, 2026-08-28), which the plugin install does not provide ([#2530](https://github.com/Morrison-Lab/ai-config/issues/2530)).
   Treat a doubled listing as the symptom, investigate by hand, and see [#2528](https://github.com/Morrison-Lab/ai-config/issues/2528) for making this an instrument.

   - **Do:** include `skills/` when sweeping `~/.claude` for leftovers.
   - **Do:** read a doubled listing (a bare name beside an `ai-config:`-prefixed one) as the symptom, since the cost is otherwise invisible.
   - **Don't:** read "the plugin serves it" as "nothing is installed to check" --- a replacement does not remove what it replaced.
   - **Don't:** delete `~/.claude/skills` on presence or on a name match;
     neither distinguishes a leftover from the client's own skills.

   The dedicated verification instrument this section used to name (`check-install.py`, which compared installed copies against the checkout and repaired drift with `--fix`) was removed along with that symlink install and has no replacement yet either.
   Until one lands, use the manual branch-plus-diff check in this file's "The blast radius is the whole consumer surface" paragraph below, which does not depend on that instrument and still works whether the local copy is a symlink or a real copy.
   On Windows, Git Bash `ln -s` silently falls back to **real copies**, so a pull does NOT propagate to a real-copy install --- copy-sync every file whose repo version changed by hand.
   Before overwriting, check for edits made directly in `~/.claude` (a diff that adds prose the repo lacks) and upstream the genuine ones into the repo first;
   never clobber an un-upstreamed local edit.
   Don't rely on mtime to spot local edits --- git operations reset mtimes on checkout, so it false-positives right after a `pull`, the case this check most needs to handle correctly.
   **Don't rely on it in the other direction either --- to spot a copy that has gone stale.**
   A file copied once and never needing to change carries an old mtime and current contents, which is the reading a genuinely stale file also gives, so the proxy discriminates nothing.
   Run a direct content comparison instead.
   See [`verify-the-right-artifact`](verify-the-right-artifact.md), "A drift claim is relational, so one read cannot settle it".
   **Whether a hook's script is present and whether it is *registered* are two different questions, and `install-hooks.py` answers only the second.**
   `install-hooks.py` compares **bindings**: it asks whether `~/.claude/settings.json` actually invokes a script on an event, and its `stale` status names a registered script that is not on disk.
   A hook can be perfectly present and never run, so a report that finds it present is not evidence about registration.
   The failure is silent in the way this corpus is worst at noticing: an unregistered guard and a guard with nothing to block look identical, since neither ever produces output.
   It also degrades **one hook at a time** rather than all at once, which is why nothing announces it --- scripts reach `~/.claude/hooks` independently of registration (the retired symlink install placed them, and today only a manual copy does), so each hook added since the last registration run sits inert.
   That makes it a per-session freshness item rather than a one-time setup step.
   ```bash
   python3 <ai-config-checkout>/scripts/install-hooks.py          # report
   python3 <ai-config-checkout>/scripts/install-hooks.py --fix     # register the missing ones
   ```
   Four caveats before running `--fix`.
   Check `enabledPlugins` in `settings.json` first: if the ai-config **plugin** is enabled it already loads every hook in `hooks/hooks.json`, and `--fix` then registers each one a second time under a different command string, so every hook fires twice --- the two paths are mutually exclusive, per README.
   And hooks connect at **session start**, so a mid-session `--fix` arms nothing until a restart.
   Say so rather than reporting the guards as live.
   **On the plugin path nothing else is needed: the plugin loader serves and loads every hook in `hooks/hooks.json` straight from the plugin root.**
   **That plugin root is the version-cache SNAPSHOT, not the marketplace clone, so pulling the clone does not refresh a running session's hooks.**
   `${CLAUDE_PLUGIN_ROOT}` resolves to `~/.claude/plugins/cache/<marketplace>/<plugin>/<rev>/`;
   a `git pull` in `~/.claude/plugins/marketplaces/<marketplace>` updates the clone and changes nothing the harness executes,
   and overwriting the cache copy directly is denied by the auto-mode permission classifier (reasonably --- an agent rewriting its own active guard).
   A merged hook fix reaches a plugin-consumer session only when the plugin pin in `~/.claude/plugins/installed_plugins.json` advances to a snapshot that contains it ---
   a session restart alone does not advance it (measured 2026-09-01: a fresh session still ran `a3e0fdb` with a `79def2e` snapshot sitting unpinned beside it),
   so reporting "pulled the fix" or "restarted" reports a hook as updated that is still running stale.
   Advance the pin through the plugin CLI (`claude plugin marketplace update <marketplace>`, then `claude plugin install <plugin>@<marketplace>`, per [`use-plugins.md`](use-plugins.md)), then verify the pinned copy in `installed_plugins.json`.
   (Measured 2026-09-01: the cache hook at rev `a3e0fdb` predated ai-config#2820's fallback while the marketplace clone had pulled past it;
   tracked as [ai-config#2899](https://github.com/Morrison-Lab/ai-config/issues/2899);
   see [`mistake-patterns.md`](../../memories/mistake-patterns.md) Pattern 42 for the full deadlock.)
   `install-hooks.py --fix` covers the non-plugin path only, and its own docstring is explicit about what it does not do: it never places a file, and it does not check that the script it is registering exists.
   `bootstrap.sh` no longer places `hooks/` under `~/.claude` (see its header comment), so this path currently only helps on a machine whose `~/.claude/hooks` already holds the scripts some other way.
   Registering a hook whose file is absent is worse than leaving it unregistered: an unregistered guard is inert, while a registered-but-absent `PreToolUse` `Bash` hook makes `python3` exit 2 on **every** Bash call and takes the shell down.
   `--fix` prints a note naming this only when run *without* `--fix`, so the run that causes the damage is the one that stays silent about it.
   **Point 1 governs this instrument too, and its stale run is dangerous.**
   A stale `install-hooks.py` run reads an old `hooks/hooks.json`, finds every hook it knows about already bound, and prints `All hooks registered.` --- a positive all-clear over hooks it cannot see.
   Pull first, then measure, and treat the examined count as the thing to read: it is the manifest's size, so a number below the current hook count means the checkout is behind rather than the machine being clean.
   **A container with no `settings.json` at all is the degenerate case, and it arms nothing --- so every guard in this corpus is inert there, not just a drifted one.**
   The paragraphs above describe registration *drift*: a `settings.json` that exists and lacks some binding, which `install-hooks.py` reports and `--fix` repairs.
   A remote/web container can ship `~/.claude` with **no `settings.json` and no `settings.local.json` at all**, which is the same failure with the count at zero.
   Nothing about it announces itself, for the reason the file-versus-binding distinction above already gives: an unregistered guard and a guard with nothing to block look identical.
   What differs is the blast radius --- drift disarms the hooks added since someone last ran the binder, while an absent file disarms all of them, including the one built for the mistake you are about to make.
   One read settles it, and it is cheaper than either instrument:
   ```bash
   for p in ~/.claude/settings.json ~/.claude/settings.local.json; do
     [ -f "$p" ] && echo "$p exists" || echo "$p ABSENT"
   done
   ```
   Read this as a fact about the **session**, not about the corpus.
   The guards are merged and correct.
   They simply are not running, so anything they would have caught is back to being your own responsibility.
   That is [`deterministic-tools`](../principles/deterministic-tools.md)'s constraint failing open rather than its goal failing --- the instrument exists, and the environment is not consuming it.
   - **Do:** check whether either settings file exists before relying on any hook, and say plainly in a status report that the guards are inert when they are.
   - **Don't:** treat a merged guard as an active one.
     Merging places a file, and only a binding in `settings.json` makes it fire.

   **The plugin path can be off at the same time, and then the caveat above has no working alternative left.**
   The paragraphs above treat the plugin as the path that already loads every hook, so `--fix` would double-register.
   A remote/web container can have neither: no `~/.claude/settings.json`, and no plugin installed.
   `${CLAUDE_PLUGIN_ROOT}` is what every command string in `hooks/hooks.json` interpolates, so one read settles the plugin half as cheaply as the file test above settles the other:
   ```bash
   echo "CLAUDE_PLUGIN_ROOT=[${CLAUDE_PLUGIN_ROOT:-UNSET}]"
   ```
   Measured 2026-08-22: `UNSET`, `SKIP_PLUGIN_MARKETPLACE=true`, and `install-hooks.py` reporting `registered=0 missing=41 stale=0`.
   A repo-local `.claude/settings.json` registering two hooks of its own does not change that, and reads like partial coverage when it is none.

   **The second direction is worse than trusting an absent guard, and nothing above covers it: diagnosing why an absent guard let something through.**
   A guard that did not warn invites a search for the flaw in its logic, and that search can be careful, reproducible, and about a hook that never ran.
   Reading the hook's source and its passing test suite is [`verify-the-right-artifact`](verify-the-right-artifact.md)'s substitution --- both are real artifacts, and neither is the registration.
   So run `install-hooks.py` before diagnosing a miss, not only before relying on a guard.
   Measured the same day: a real weakness in a guard's discharge logic was reproduced and filed as the cause of a missed warning, while that guard was one of the forty-one.
   The weakness was genuine; the attribution was not.

   **Measured recurrence, 2026-08-20: `registered=15 missing=16 stale=0` against a 31-hook manifest, on a machine where every rule above was already written.**
   That is worth recording as evidence about the *rule* rather than about the machine.
   Each paragraph above is correct and none of them fired, because all of them describe a check somebody has to decide to run, and the drift is silent by construction.
   Among the sixteen inert guards was `flag-add-a-outside-pathspec.py`, and in the same session the exact mistake that hook was written to prevent reached a pushed commit.
   The gap that incident exposes is not a rule but a **moment**: README's activation gate forbids registering before the PR merges and names nothing that happens after, so the owed registration has no owner.
   [`post-merge`](../../skills/post-merge/SKILL.md)'s step 3.75 is now that owner, and carries the incident, the mechanics, and the argument for why a hook cannot be the instrument here.

   - **Do:** run `install-hooks.py` each session, and report its counts.
   - **Do:** compare `install-hooks.py`'s `examined N` against the current `hooks/hooks.json` before believing `All hooks registered.`
   - **Don't:** run `install-hooks.py --fix` as the whole of "arm these hooks" --- it binds, it never places.
   **An entry that genuinely IS a symlink resolves through the checkout's CURRENT BRANCH, so a freshness check can pass over a file from the wrong branch.**
   Everything above splits the world into symlinks, which a pull refreshes, and real copies, which it does not.
   That split is real and it is not exhaustive.
   A symlink points at a **path in the working tree**, never at a commit, so the file the harness loads is whatever branch that checkout happens to have out --- which on a machine driving several PRs is routinely a feature branch rather than `main`.
   A `git pull` on `main` then updates a ref the loaded file does not resolve through, and `git branch -f main origin/main` does not help either, for the same reason.
   Note this is the opening sentence of point 2 failing, not a further wrinkle in the Windows real-copy case: "the pull alone refreshes them" holds only while the checkout is on the branch you pulled.

   Nothing that merely inspects `settings.json` or a symlink's destination can see it, and the reason is structural rather than an oversight.
   A symlink resolving inside this repo says nothing about *which commit* the working tree currently has checked out.
   `install-hooks.py` reads `settings.json` and never opens the linked file at all.
   A clean report from it is therefore consistent with every loaded file being a branch behind, which makes this a third way the installed state can be wrong, alongside registration drift and the registered-but-never-placed script in [`claude-code-hooks.md`](../../memories/claude-code-hooks.md).

   The blast radius is the whole consumer surface rather than hooks alone, because `skills/`, `shared/`, `memories/`, and `CLAUDE.md` are linked the same way --- so the `@shared/...` fragments this file imports are exactly as exposed as a guard is.
   One read settles it, and it is the content comparison no instrument here performs:
   ```bash
   git -C <ai-config-checkout> rev-parse --abbrev-ref HEAD                  # is it even on main?
   git -C <ai-config-checkout> diff origin/main --stat -- shared hooks skills memories CLAUDE.md
   ```
   The repair is constrained in a way worth stating, since the obvious one is forbidden.
   Point 1 already says to leave another session's in-flight work alone, and a checkout parked on someone else's branch is precisely what produces this drift, so switching it to refresh your own hook trades a stale guard for a clobbered colleague.
   Report the drift instead and read from `origin/main` directly (`git show origin/main:<path>`).
   - **Do:** read the checkout's current branch before believing any freshness report, and diff the consumer surface against `origin/main` when a loaded rule or guard matters.
   - **Do:** say which branch a `~/.claude` file resolved through when reporting an install clean.
   - **Don't:** read a symlink or a registered path resolving inside this repo as meaning its content matches `main` --- it only means the path lands inside this repo, whatever branch that repo has checked out.
   - **Don't:** switch a checkout parked on another session's branch to refresh your own hook, or expect `git branch -f main origin/main` to move what a symlink resolves through.

3. **The working repo's main checkout.**
   Fast-forward the `main` checkout of whatever repo the session is working on (`git fetch origin`, then `git pull --ff-only` when `main` is checked out) --- it goes stale as the session's own PRs and other sessions' PRs merge.
   **The same "diverged" failure from point 1 above can hit any repo's `main`, not just ai-config's own** --- a fresh container's checkout isn't guaranteed fresh for every repo it holds.
   Apply the same recovery: confirm the working tree is clean, then check whether the local tip's commit is actually reachable from `origin/main` (`git merge-base --is-ancestor <local-tip> origin/main`) before force-realigning with `git checkout -B main origin/main`.
   Don't rely on a commit-message grep alone to decide safety --- the same message can appear under a *different hash* after a squash-merge or rebase (so the grep matches but the underlying commits differ, the milder case in point 1), and `git log origin/main` only reflects whatever your local remote-tracking ref last fetched (so a check run before fetching in this session can miss commits that already landed).
   Re-run `git fetch origin main` immediately beforehand and use the hash-based ancestry check as the authoritative signal.
   A clean working tree plus a non-ancestor local `main` tip is still safe to realign in the common case (the checkout is stale, not carrying real work), since realigning only moves a local branch ref --- the discarded commits stay recoverable via `git reflog` regardless.
4. **The `.ai-config` submodule pin, in any repo that vendors ai-config as a git submodule** (check `.gitmodules` for a `.ai-config` entry --- not every repo has one; most consume ai-config only via the Plugin Marketplace, which doesn't need this).
   **If the repository uses ai-config (or another tool) as both a native plugin and a submodule, remove the submodule rather than bumping it.**
   Native plugin integration supersedes the submodule;
   keeping both causes drift, double-loading, and maintenance friction.
   See [`remove-redundant-plugin-submodules.md`](remove-redundant-plugin-submodules.md).
   Where a repo legitimately relies on the submodule (e.g. an environment lacking plugin support):
   Compare the pinned commit against ai-config's current `origin/main`: `git rev-parse HEAD:.ai-config` for the pin's SHA, then `git -C <path-to-a-local-ai-config-clone> rev-list --count <pin>..origin/main` for how far behind it is.
   A pin more than a few weeks or dozens of commits stale is worth refreshing: file a tracking issue, bump it (`git submodule update --init --remote .ai-config` from the parent repo handles both init and fetch in one step; or, if already checked out, `git fetch origin` inside the submodule before `git checkout origin/main`), then `git add .ai-config` in the parent repo to record the new gitlink, verify the parent repo's own checks still pass, and open a PR.
   Before assuming this is risk-free, check whether the parent repo's CI actually reads the submodule's checked-out content (vs. treating it as inert until a dev runs `git submodule update --init` locally) --- a pin bump is a pure pointer change with no functional surface only when nothing reads it.
   **When the current checkout isn't `main` itself** (a feature branch or a worktree), `HEAD:.ai-config` only reflects that branch's own pin --- it can look badly stale purely because the branch was cut before a bump PR merged into `main`, not because the project's actual pin needs refreshing.
   Also check `origin/main:.ai-config` (the pin as recorded on the base branch) against ai-config's `origin/main`;
   if that one is already fresh, no bump PR is needed --- the branch's own pin resolves itself on its next merge/rebase.
   On Windows Git Bash, that comparison command hits an MSYS gotcha --- see `memories/git.md`.
   **When *adding a new citation* to an ai-config shared fragment inside a submodule-consuming repo's own `CLAUDE.md`, verify --- don't assume --- that the citation already resolves.**
   It only does once BOTH (a) the source PR has merged into ai-config's `main`, and (b) that repo's own `.ai-config` pin has been bumped to a commit containing the path --- the pin doesn't auto-follow `main`.
   Check with `git show <pin>:<path>` (or `ls` inside the checked-out submodule) before writing the citation in present tense;
   if either gate hasn't cleared, hedge to future/conditional tense instead of asserting settled fact --- mirroring the "proposed in ai-config#N --- once merged, the fragment lives at ..." convention `gha`'s own `CLAUDE.md` already uses for citing its still-open companion PRs.
   Once the citation does resolve, keep the local **restatement** of the rule's key points alongside the citation rather than trimming to a bare pointer --- unlike a skill distributed via the Plugin Marketplace (point 4's own preamble), `.ai-config`'s `shared/`/`memories/` fragments aren't auto-loaded into agent context --- they only enter it when a `CLAUDE.md` explicitly restates or `@`-references them --- so a bare citation is invisible to an agent that doesn't take the extra step of reading the fragment on demand.

## A scoped fetch refreshes only what it fetched, and prunes only that too

Point 3 above prescribes `git fetch origin main` before the ancestry check, and
that is right for the question it answers.
It is the wrong instrument for every *other* remote-tracking ref in the
checkout, and the way it fails is silent.

`--prune` deletes only refs the fetch's own refspec covers.
Naming a branch on the command line replaces the configured
`+refs/heads/*:refs/remotes/origin/*` for that invocation, so a branch deleted
upstream keeps a **stale, resolving** `refs/remotes/origin/<name>` afterwards.
Measured on git 2.43.0, deleting `feat` upstream and then fetching from a
second clone:

```
git fetch origin main --prune   ->  origin/feat still resolves (95f2077)
git fetch --prune               ->  origin/feat GONE
```

**The `fetch.prune=true` config does not rescue this**, which is the part worth
knowing, because setting it is what most people believe closes the question.
It is consulted per invocation and bounded by that invocation's refspec, so the
scoped fetch leaves the ref standing with the config on:

```
fetch.prune=true, git fetch origin main   ->  origin/feat still resolves
fetch.prune=true, git fetch               ->  origin/feat GONE
```

So a stale ref survives a session that both set the config and ran a prune,
which is a third state alongside the two
[`memories/git-branches.md`](../../memories/git-branches.md)'s "Cleaning up a
branch deleted on `origin`" section describes: not "no prune ran", but "a
prune ran and did not cover this".
Its `[gone]` sweep reports a false clean either way.

The consequence lands on the next push.
`git push --force-with-lease` fails with `stale info` against a branch that no
longer exists at all --- reproduced in the same scratch repo, followed by an
empty `git ls-remote` and a plain push reporting `* [new branch]`.
That failure's meaning and its remedy are already recorded, so read
[`memories/git-branches.md`](../../memories/git-branches.md)'s "`stale info`
after `checkout -B`" bullet rather than re-deriving them; what this section
adds is only that a
scoped `--prune` is one of the ways you arrive there.

- **Do:** run an unscoped `git fetch --prune` before relying on any
  remote-tracking ref other than the one you just named.
- **Do:** treat `git ls-remote --heads origin <branch>` as the authoritative
  answer to whether a branch exists, since it consults the remote rather than a
  local cache.
- **Don't:** read `fetch.prune=true` as making pruning automatic --- it is
  bounded by each invocation's refspec, so a scoped fetch prunes nothing.
- **Don't:** count a `--prune` you ran as having pruned the ref you care about;
  check which refspec it covered.

## Disabling a hook by unregistering it assumes ONE installation shape, and does nothing on the other

Point 2 above already records that the two installation paths are mutually
exclusive: with the ai-config **plugin** enabled, every hook in
`hooks/hooks.json` loads from the plugin root, and `install-hooks.py`'s
`settings.json` bindings are the *other* path rather than an additional one.
That is stated there as a hazard for **enabling** a hook --- run both and each
one fires twice.

The same fact has a quieter consequence in the opposite direction, and nothing
above reaches it.
The standard way to silence a hook is to delete its entry from
`~/.claude/settings.json`.
On a plugin install there is no such entry, so that edit removes nothing, the
hook keeps firing, and **the edit itself succeeds** --- which is the whole
problem.
A remedy that errors gets fixed; a remedy that quietly no-ops gets recorded as
applied, and the next reader inherits an instruction that has never once
worked.

The asymmetry with the enabling case is worth naming, because it is why the
enabling hazard was noticed and this one was not.
Double-firing is loud and immediate.
A failed disable looks exactly like a hook you decided to keep.

So when a hook has to stop firing for a reason that is not per-PR --- a
standing directive, a moratorium, a repo where its demand is meaningless ---
put the switch **in the script**, where both installation shapes read it, and
prefer a self-expiring form over a flag somebody has to remember to clear.
`hooks/no-unreviewed-pr.py`'s `MORATORIUM_END` is the worked example, and
[`memories/gh-cli.md`](../../memories/gh-cli.md)'s Copilot-moratorium section
carries that one incident's own record --- read this section for the general
rule about installation shapes, and that one for what the moratorium requires
of a session today.

- **Do:** put a non-per-PR suppression in the hook script itself, so it holds
  on a plugin install and a settings install alike.
- **Do:** prefer a dated constant to an env flag when the reason for
  suppression has a known expiry, so the guard re-arms without anyone
  remembering.
- **Don't:** prescribe "remove it from `~/.claude/settings.json`" without
  naming the installation shape that assumes; on a plugin install it is a
  no-op that reads as a fix.
- **Don't:** treat an env-readable switch as equivalent --- a clock or a kill
  flag the guard reads from the environment is a one-variable bypass of the
  guard in production, which is the direction
  [`fail-fast`](../principles/fail-fast.md) refuses for any discharge path.

(`Morrison-Lab/ai-config#1709` / `#1710`, 2026-08-19: `memories/github.md`
prescribed unregistering `no-unreviewed-pr.py` for the Copilot moratorium's
duration.
`grep -n no-unreviewed-pr ~/.claude/settings.json` returned nothing on the
machine where the hook was firing every turn, because `hooks/hooks.json:349`
supplied it under `${CLAUDE_PLUGIN_ROOT}`.)
