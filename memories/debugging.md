# Debugging notes

## Heredocs in chained terminal commands are unreliable

Multi-line heredoc-style commands in chained terminal commands get garbled or silently fail. Always write multi-line content to a temp file first, then reference it:

```sh
cat > /tmp/msg.txt << 'EOF'
line 1
line 2
EOF
git commit -F /tmp/msg.txt
```

Never inline heredocs in chained commands. Applies to git commit messages, MR descriptions, and any other multi-line content passed to CLI tools. (Learned during HACtions MR !37.)

## Markdown line-by-line processors: every inner loop needs its own fence tracker

When writing a script that reformats Markdown line by line, the outer loop usually
tracks `in_code_block` to pass fence bodies verbatim. But inner collection loops
(bullet continuation, blockquote accumulation) often collect lines first and process
later — they need their **own** fence-state tracker, or fenced code blocks inside
bullets/blockquotes get stripped, joined, and reflowed as prose.

Pattern: any loop that accumulates lines before processing should break (or track
`in_inner_code`) when it hits a ```` ``` ```` line.

**Test matrix before shipping a Markdown reformatter:**
- Top-level fenced code block (the baseline)
- Fenced code block inside a numbered step / bullet item
- Fenced code block inside a blockquote (`> ``` … > ``` `)
- Multi-line code block body (not just single-line) in each of the above

Hit on d-morrison/ai-config#265: the semantic-line-breaks script lacked fence
tracking in the bullet continuation loop and the blockquote collection loop.
Both took two rounds of review to fully fix (single-line fence caught in round 1,
multi-line body in blockquotes caught in round 2).
A separate edge case also surfaced in round 3: `_flush_bq_prose` silently dropped
lines when `split_sentences` returned `[]` (empty blockquote text) and multiple
lines had accumulated — unrelated to fence state, but found in the same cycle.

## Testing CSS/JS-dependent web features — use a REAL browser, not a DOM stub
- A hand-rolled DOM shim (or jsdom-style unit test) can PASS while the feature is
  visibly broken, because it doesn't apply the page's CSS or run the framework's
  own scripts. On rme#929 a DOM-stub test of a mobile TOC passed, but in a real
  browser the menu never opened: a framework CSS rule (`nav[role=doc-toc]{display:none}`)
  hid the cloned node, and native `<details>` closed-hiding didn't apply either.
  Neither failure is observable without real CSS.
- Drive a real headless browser. **In the remote/web-session runner** (paths
  below are that runner's — they differ on a local CLI setup; `which chromium` /
  `npm root -g` to find yours), Playwright is installed globally; the chromium
  binary is at `/opt/pw-browsers/chromium-*/chrome-linux/chrome` (the
  `/usr/bin/chromium-browser` is a snap stub that won't launch — pass the real
  path as `executablePath`, plus `args:['--no-sandbox']`). Import Playwright by
  its absolute global path (`/opt/node22/lib/node_modules/playwright/index.js`),
  which is a CommonJS default export: `import pkg from '…'; const {chromium}=pkg`.
- Serve the built site over HTTP (`python3 -m http.server` in `_site`) and load
  `http://localhost:<port>/…` — `file://` blocks the framework's `type=module`
  scripts (e.g. Quarto's `quarto-nav.js` / `quarto.js`) via CORS, so headroom/nav
  behavior won't run. Test viewport-specific behavior with `newPage({ viewport })`,
  and assert computed styles / `offsetHeight` (not just DOM presence).
- **Quarto dark mode** (the `theme: {light: cosmo, dark: darkly}` pair in
  `_quarto.yml` that adds a navbar toggle): to force/screenshot the dark theme,
  set `localStorage["quarto-color-scheme"] = "alternate"` via `addInitScript`
  BEFORE navigation, then load over HTTP (not `file://`). The toggle button calls
  `window.quartoToggleColorScheme()`, but it only works once `quarto.js` has
  loaded — which it can't under `file://` (CORS), so the toggle silently no-ops
  and the page stays light. Verify the switch took with
  `getComputedStyle(document.body).backgroundColor` (darkly → `rgb(34,34,34)`),
  not by the toggle icon alone. The stored value is the literal string
  `"alternate"` (dark) / `"default"` (light) — NOT `"dark"`/`"light"`.

## ARDI/iterate: must poll for new review after pushing
- After pushing fixes during an iterate loop, DON'T declare "clean" based on
  the previous review. A new push triggers a new auto-review.
- After a CI-fix push, don't return to chat on the first green jobs.
  Wait for a terminal, passing rollup (pending, queued, in-progress are still running; cancelled needs investigation/rerun).
  A question about that PR that isn't the word "status" still needs a
  fresh review fetch; answering from chat can leave a landed review
  unread (gha#511, 2026-08-18).
- **In repos whose review workflow carries a `pull_request` trigger.**
  `Morrison-Lab/ai-config` does again, as of #1707 on 2026-08-20, so a push
  there does schedule a review and polling terminates normally --- see
  [`claude-review-dispatch.md`](claude-review-dispatch.md)'s "`ai-config`
  auto-reviews on push as of 2026-08-20, and did not before" for the dated
  trigger table, and read its date rather than assuming either answer.
- Poll until a review note appears that references your latest commit SHA.
- Wait ~30-60s, then check. If nothing after ~2min, check pipeline status.
- The iterate skill now has explicit polling instructions for both GitHub and GitLab.

## Confirm a CI failure is pre-existing (not your diff) via workflow-run history on main
- Before waving off a red CI check as "unrelated, pre-existing" (e.g. to defer
  fixing it as out of scope for the current PR), verify it, don't assume —
  check that same workflow's run history filtered to `main`, not just that the
  failure looks unrelated to the files in your diff.
- `mcp__github__actions_list` (`list_workflow_runs`, `resource_id: "<file>.yml"`,
  `workflow_runs_filter: {"branch": "main"}`) returns that job's own run
  history; sort by `run_number` descending and read the most recent entries'
  `conclusion`. If it's already `failure` on `main`'s current HEAD commit (and
  several commits back), the failure predates your branch and is safe to defer
  — cite the specific `main` commit SHA(s) it fails on in the PR/issue as the
  evidence, not just "looks unrelated."
- The GitHub Checks API's check-run `name` (e.g. `jarl-check`) is often NOT the
  workflow **file** name `list_workflow_runs` needs as `resource_id` — grep
  `.github/workflows/*.y*ml` for the job's `name:` field to find which file
  defines it (a repo can have several workflow files; the job name doesn't
  say which one).
- `actions_list` responses for an active repo can exceed the tool's token cap
  and get written to a scratch file instead of returned inline — when that
  happens, `python3 -c "import json; ..."` on the saved file (filter by
  `path`/`head_branch`, sort by `run_number`) is far more reliable than
  grepping the raw JSON text, since a single workflow run's JSON blob is
  usually one unbroken line with no per-field markers to grep on the same
  line. (`d-morrison/altdoc#16`: confirmed `jarl-check`'s failures via
  `lint.yml`'s run history on `main` going back 4+ commits before reporting it
  as pre-existing and out of scope.)

## VS Code editor buffer vs disk desync
- `replace_string_in_file` / `read_file` operate on the VS Code editor buffer.
- If the file was externally modified (e.g., by `git pull`), the editor buffer
  may be stale or the edit may land in a buffer that doesn't match disk.
- `git diff` and terminal `cat`/`sed` see the DISK, not the editor buffer.
- Symptom: `read_file` shows your edit, but `git diff` shows nothing.
- Fix: write via terminal (`sed -i`, `cat >`, etc.) to guarantee disk write,
  OR save the VS Code buffer before committing.
- When `replace_string_in_file` fails with "could not find matching text",
  the disk file likely differs from what `read_file` showed (stale buffer).

## macOS sed vs GNU sed syntax differences
- `sed '1{/pattern/d}'` works on GNU sed (Linux CI) but FAILS on macOS BSD sed
- Portable form: `sed -e '1{' -e '/pattern/d' -e '}'` (separate -e expressions)
- Always test sed commands locally before committing if they use address+command blocks
- The CI runs on Linux (GNU sed) but local dev is macOS (BSD sed) — use portable form

## bash "syntax error: unexpected end of file" at last line
- Almost always an unclosed construct (`if`/`fi`, quote, `$(`).
- BUT a sneaky cause is **CRLF line endings**: `\r` makes bash read `then\r`/`fi\r`
  as non-keywords, so the `if` never closes -> EOF error.
- Diagnose: `sed -n 'A,Bp' file | od -c | head` and look for `\r \n`.
- Fix: `perl -i -pe 's/\r\n/\n/g' file`, then re-run `bash -n file`.
- Prevent: add `.gitattributes` with `*.sh text eol=lf`.

## Programmatic comment edits leave punctuation/grammar artifacts
Recurring across the sparta scrub PRs (Lacaedemon/sparta#150, Lacaedemon/sparta#152)
— removing inline content from comments (issue refs like `(#138)`, parentheticals,
clauses) via sed/scripted passes repeatedly broke the surrounding prose. The reviewer
(and Copilot) flagged ~6 of these. After any scripted comment edit, **re-audit the
touched lines** before pushing:
- **Mid-sentence parenthetical removed → orphaned comma/period on the wrapped continuation line.** When the ref opened a continuation line — `# ...launched from the map` / `# (#122), before...` — stripping `(#122)` leaves `# , before...`. Fix: move the comma/period up to the end of the prior line (`# ...launched from the map,` / `# before...`).
- **Line-leading `(#NN).` removed → comment marker + bare punctuation.** `## (#82/#84).` opening a continuation line → `##.`. Fix: end the previous line's sentence and drop the marker-orphan.
- **Trailing clause/ref removed → dangling text.** `# ... see issue #61.` → `# ... see issue.` (referent gone). Fix: drop the now-meaningless phrase.
- **Repeated word exposed.** `keyed off the uid (#50): keyed off get_instance_id()` → `...uid: keyed off...`. Fix: reword.
- Audit greps (ERE — `grep -E`): `grep -rnE "^[[:space:]]*#+[[:space:]]*[.,;:]"` (orphaned leading punctuation),
  and scan for `see issue\.`, `, #[0-9]+,`, double spaces, broken section-header dashes.
- The blanket strip patterns that work cleanly (with `sed -E` / `sed -r` — they need
  ERE for the `+` quantifier; in ERE, `\(` and `\)` match literal parens, not groups):
  `s/ \(#[0-9]+\)//g` (inline), `s/^# #[0-9]+: /# /` (prefix — `^`-anchored, so no `g`), `s/, #[0-9]+,/,/g` — but
  the line-leading and sentence-internal cases need hand edits, not sed.

## Merging main into a sibling PR can silently clobber an un-customized file
When PR-A merges and you sync sibling PR-B (which touches the same files), a file
that B never customized takes main's (A's) version **with no merge conflict** — so
it can end up with content describing A's change, not B's. Hit on Lacaedemon/sparta#152:
the `demos/demo.json` reason silently became Lacaedemon/sparta#143's diplomacy text.
After such a
merge, don't just resolve the marked conflicts — **diff the whole merge result vs
the PR's intent** and check files that merged "cleanly" but belong to this PR
(demo manifests, PR-specific metadata) still say the right thing. Also re-run the
PR's own invariant (here: the ref-scrub) over files main re-touched, since A may
have re-introduced exactly what B removed.

## `CONFLICT (add/add)` after a sibling PR merge: consolidate baseline + deltas

When two sibling PRs both add the same new file(s), syncing one branch after the
other merges can produce `CONFLICT (add/add)` across many paths. Fast, safe
pattern:

- Compare `git show ":2:<file>"` vs `git show ":3:<file>"` for **every conflicted file** (quote the whole revision argument — bash parses a bare `<` mid-word as input redirection, breaking the command).
  Representative files can establish a likely pattern, but they do not replace
  the per-file check (especially where late review fixes landed).
- Keep the side with the newer baseline (often incoming `main`), then re-apply
  newer deltas from the other side (e.g., review-driven pins/validation fixes).
- Re-run the PR's key verifier immediately after resolution (not just marker
  checks), because this class of conflict is easy to "resolve" while dropping a
  small but critical late-round fix.

## A parallel session can force-push your PR branch out from under you
On Lacaedemon/sparta#150 another driver (a second `@claude` task, or GitHub's
"Update with rebase") force-pushed the PR branch three times, each time replacing
my sync-merge commit with a rebase that dropped my conflict resolutions and
reverted fixes. Defenses:
- **Before pushing to a shared PR branch, `git fetch` and check that `origin/<branch>`
  hasn't moved since your last push** — don't assume your last push is still HEAD.
  `git log --oneline "HEAD..origin/<branch>"`: non-empty means a parallel session pushed
  past you. (This handles unpushed local commits, where a bare `rev-parse HEAD` vs
  `origin` would always differ by design.)
- **When it was force-pushed, reset to origin and re-verify the content** (refs,
  the specific fixes, demo/metadata) rather than force-pushing your divergent copy
  back. The rebase may already carry the same correct content — diff it.
- **If origin's content is already correct, stand down — don't push.** Pushing a
  divergent merge just restarts the tug-of-war. Reset local to origin and let the
  review run.
- **Escalate to the user to settle who drives the PR** once you see repeated
  force-pushes — that's the claim-pr/parallel-session collision, and one driver
  should own it.

## PR `mergeable_state: blocked` can just mean required checks are still running
Don't treat `blocked` as a branch-protection or review-request mystery by
default — GitHub reports it whenever any required check hasn't yet completed
successfully, including one that's simply still `in_progress` after a fresh
push. Check `get_check_runs` before hypothesizing about missing approvals or
protection rules: if `build`/`claude-review`/etc. are `in_progress`, that alone
explains `blocked`, and it clears on its own once they finish. Only dig into
branch-protection settings if `blocked` persists after every check is
`completed`.

## A CI job that STALLS looks identical to one that's merely slow -- diff the log twice, don't judge from one sample

- Signature: a required check sits `in_progress` far past its normal
  runtime, so the PR stays `mergeable_state: blocked` (the entry above)
  with nothing red to point at. Reading the job's log tail once shows
  plausible in-flight work (package resolution, a build step) and recent
  timestamps, which reads as "slow, still going."
- Mechanism: a single log sample cannot distinguish progress from a hang.
  The timestamps on the last lines are when those lines were WRITTEN, not
  when you read them -- a job frozen 20 minutes ago still shows the
  timestamp of its last successful write, which looked "recent" at the
  moment it stalled.
- Fix/check: two mechanical comparisons, not a judgment call.
  1. **Baseline the duration.** `actions_list` `list_workflow_runs` on
     that workflow gives the recent runs' start/update times; compute
     durations and compare. A 40-minute run against a 2-6 minute norm is
     a signal on its own.
  2. **Sample the log twice, minutes apart, and compare BOTH the last
     timestamp and the byte length** (`get_job_logs`'s `original_length`).
     Identical on both = no output at all in the interval = stalled.
     A slow-but-live job advances at least one of them.
  Also check whether the same branch's PREVIOUS run of that workflow
  passed -- if it did, the job is at fault, not the diff.
- Caveat: GitHub's live-log API can buffer for in-progress jobs, so a
  static log is strong evidence, not proof. Weigh it with the duration
  baseline rather than alone.
- Remedy may be out of reach: in a Claude Code remote/web session the
  GitHub token is typically denied Actions write --- both
  `cancel_workflow_run` and `rerun_workflow_run` return
  `403 Resource not accessible by integration`. Don't burn rounds
  retrying; report the stalled run and ask the human to hit Re-run, and
  offer the empty-commit retrigger as the alternative (noting its cost:
  it re-runs the whole matrix, and it only displaces the stuck run if
  that workflow actually sets `cancel-in-progress`).
  (UCD-SERG/serocalculator#598, 2026-07-25: `lint-changed-lines` stalled
  ~40 min against a 2-6 min norm; the same branch's prior run of it had
  passed in 4:33. Reported as slow-not-hung at first on a single log
  read, corrected only after a second read showed a byte-identical log.)

## Test implicit path coverage when a change affects more branches than described
When a code block is placed in a shared path (e.g. the non-append `else:` branch
of an order dispatcher), it implicitly covers every non-append command type —
plain moves, reform moves, form-up drags, etc. — even if the PR's focus was one
specific case. Reviewers flag missing coverage for implicit paths.

Pattern: after placing a change in a shared branch, enumerate the full set of
command types that reach it, and add at least one test per type beyond the primary
case. Name each test to make the path explicit (e.g. `test_form_up_pre_faces_march_direction`).

Hit on Lacaedemon/sparta#352: the pre-facing block ran for form-up drags too,
but no test covered that path until the reviewer flagged it.

## Appending to skill/memory files: grep for duplicate sections first
Before adding a new `##` section to an existing skill or memory file, grep the
file for the section heading. It's easy to append a section that already exists —
the scout-peers duplicate `## Relationship to other skills` bug (ai-config#132)
happened because an existing section was missed and a duplicate was appended at
the end. Run `grep -n "^## " -- "<file>"` before appending.

## An empty grep for one spelling is not evidence the concept is absent
Grepping for the value you *expect* only tests that spelling. When the question
is "does this document mention X at all," a miss has two very different causes:
X genuinely isn't there, or X is there under a **different, wrong string** --
and the second is precisely the case worth catching, since a stale value is a
live defect while a missing one is only a gap.

The tell is a grep whose pattern encodes an assumption about the *correct*
answer (a current URL path, a renamed flag, the new function name). Before
concluding "not present," read the surrounding section, or re-grep for the
stable part of the concept rather than the volatile part -- the domain
(`serocalculator.github.io`) rather than the path (`/dev/`), the function
family rather than the exact name.

Getting this backwards inverts the fix: "missing" leads you to *add* a second
copy alongside the broken one, which is worse than the defect you started with
(now two pointers, one wrong, and a DRY violation to boot).

(`UCD-SERG/serocalculator#605`, 2026-07-25: grepped a README for `dev/` to
check whether it linked the development docs, got nothing, and reported the
link as missing. It existed -- pointing at a `/main/` path that had been dead
since the docs deploy moved. Caught only when a full read of the file surfaced
the real sentence, at which point the fix changed from "add a paragraph" to
"correct the URL," and the originally-planned addition would have been a
duplicate.)

**A second mechanism produces the same false absence, and this one is
structural rather than a wrong guess: the phrase spans a line break.**
The case above is grepping the wrong *string*.
This is grepping a right string that a line-scoped tool cannot see, because
`grep` matches within a line and the text does not stay on one.
Any corpus following
[`semantic-line-breaks`](../shared/writing/semantic-line-breaks.md) breaks
prose at clause boundaries by construction, so a quoted phrase longer than a
few words straddles a newline as a matter of course rather than by bad luck.

It is the more dangerous of the two, because the pattern is quoted **from the
target** and is therefore known to be correct.
That removes the doubt a guessed spelling would leave, so a zero-hit result
reads as proof of absence rather than as a reason to look again -- and the
conclusion it invites is that someone else's citation is dangling.

Use a tool that is not line-scoped, or match a fragment short enough to sit on
one line.
All four measured against the same file, where the sentence breaks after
"test the class it":

```
grep -rn  "test the class it distinguishes"          -> 0 hits    (the trap)
grep -rlzP "test the class it\s+distinguishes"       -> 1 file
rg -U      "test the class it\s+distinguishes"       -> 1 match
grep -rn  "test the class it"                        -> 1 hit
```

Those ran on GNU grep 3.11.
`-P` and `-z` are GNU extensions rather than POSIX, so on a BSD/macOS `grep`
reach for `rg -U` or the one-line fragment, which need neither.

`git show <sha> -- <path>` and reading the hunk is the other reliable form,
and it is the one to reach for when verifying that a citation resolves.
(ai-config#771, 2026-07-28: a cross-referenced bullet in
`shared/workflow/ardi.md` was checked before citing it; the repo-wide grep
returned nothing and the citation was one step from being reported back to
its author as dangling.
The sentence was present verbatim the whole time.)

**Third occurrence, 2026-08-20** (after ai-config#771), twice, and with two different phrases rather than one phrase in two files.
`never auto-reviews a PR on push` gave `grep` 0 and a `\s+` regex 1 here;
`at the end of this file` gave `grep` 0 in `claude-review-dispatch.md`,
split across lines 32-33, and was found while checking the first.
The remedy above was already written and not reached for, so what recurs is
recall rather than knowledge, and this machine's BSD `grep` also rejects `-P`.

## Writing robust bash scripts (recurring review findings)
Lessons the reviewer flagged across the `session-lock` PR (d-morrison/ai-config#38) —
pre-empt these when authoring shell, especially under `set -euo pipefail`:
- **`mktemp` + rename: add a cleanup trap.** A process killed between `mktemp`
  and the `mv` orphans temp files forever. Pattern: `tmp=$(mktemp -- "<dir>"/.tmp.XXXXXX);
  trap 'rm -f "${tmp:-}"' EXIT; … > "$tmp"; mv -f "$tmp" "$dest"; trap - EXIT`.
  Quoting alone isn't enough here: a `<dir>` value starting with `-` (e.g.
  `-cache`) makes the whole substituted template start with `-`, and
  `mktemp` parses that as an option regardless of quoting (verified:
  `mktemp "-cache"/.tmp.XXXXXX` fails with "unknown option -- c"; `mktemp --
  "-cache"/.tmp.XXXXXX` correctly treats it as a path instead). Belt-and-
  suspenders for `SIGKILL` (trap can't fire): a prune path that sweeps
  `find "<dir>" -maxdepth 1 -name '.tmp.*' -type f -mmin +60 -delete` --
  without `-maxdepth 1 -type f` it recurses into subdirectories and can
  delete unrelated `.tmp.*` files nested below `<dir>`, not just this
  script's own orphans (see the reference implementation, the `find`
  prune inside `prune_stale()` in
  `skills/session-lock/scripts/ai-session.sh`, which includes both
  flags). Those two flags bound depth and type, not ownership:
  `.tmp.*` is a generic pattern, so in a directory shared with other
  processes (bare `/tmp`, most of all) the prune can delete another
  process's live temp files that happen to match.
  The reference implementation is safe because its `$REG_DIR`
  (`"$COMMON_DIR/ai-sessions"`) is reserved for that script alone.
  Point `<dir>` at a script-reserved directory like that, or --- when the
  directory must be shared --- put a script-specific prefix in the
  `mktemp` template and the glob alike
  (`.myapp.tmp.XXXXXX` → `'.myapp.tmp.*'`), so the sweep can only ever
  match this script's own files.
  Separately, **`--` does not fix
  this for `find`** the way it does for `mktemp`: GNU `find`'s own
  path-vs-expression parser still reads a dash-prefixed argument as an
  expression even after `--` (verified: `find -- "-weird"` fails with
  "unknown predicate `-weird'"). Make sure `<dir>` itself never starts with
  `-` -- prefix a relative one with `./`, or use an absolute path, before
  it reaches `find`. Separately, the `-name` glob must match
  the `mktemp` prefix you chose, or it silently misses every orphan
  (`.tmp.XXXXXX` → `'.tmp.*'`; mktemp's bare `tmp.XXXXXX` default → `'tmp.*'`).
- **Bounds-check value-taking flags before `shift 2`.** In a `set -e` arg
  parser, `--flag` as the last arg makes `${2:-}` expand to "" but the following
  `shift 2` fail (count out of range) → script aborts with a cryptic error.
  Guard with the `set -u`-safe presence test:
  `--flag) [ "${2+set}" = set ] || die "--flag requires a value"; V="$2"; shift 2 ;;`
  (`${2+set}` → `set` when `$2` is present even if empty, `""` when absent.)
- **Never interpolate shell vars into a `python3 -c` / `awk` program string.**
  Pass them as arguments: `python3 -c '…sys.argv[1]…' "$val"` (not `"…'$val'…"`)
  — keeps code and data separate and avoids quoting/injection breakage.
- **Declare loop-local vars once** in the function's top `local` line; bash
  `local` is function-scoped, so re-declaring inside loop bodies is redundant.
- **bash 3.2 (macOS default) compatibility:** indexed arrays, C-style
  `for ((…))`, and `${2+set}` all work; **associative arrays do NOT** (4.0+).
  Parse key=value records with `while IFS='=' read -r k v; do case "$k" in …`.

## `grep -P '\x{NNNN}'` fails on an unset locale -- and a `||` fallback turns that into a reported pass

A non-ASCII glyph scan written as `grep -P '\x{2014}'` (the natural way to
look for an em-dash per
[`ascii-punctuation-in-source`](../shared/coding/ascii-punctuation-in-source.md))
exits 2 with `grep: character code point value in \x{} or \o{} is too large`
whenever the locale is unset or `C`.
The cause is the locale, not the syntax: PCRE runs in non-UTF-8 mode there,
so `\x{}` caps at `0xFF`.
Verified on GNU grep 3.11 with `LANG` and `LC_ALL` both empty, which is the
default in at least some Claude Code containers -- so this fires by default,
not as an exotic edge case.

**The fix is to fix the locale**: prefix the command with `LC_ALL=C.UTF-8`,
or do the scan in Python.
Either spelling of that locale works where it exists at all -- glibc
normalizes the name, so `LC_ALL=C.utf8` behaves identically even though
`locale -a` may list only the lowercase `C.utf8` form (both verified here).

**Do not reach for a literal-glyph bracket as a locale-independent
workaround.**
It is not one, and it fails in the worst way -- silently, with plausible
output.
Under a byte-wise locale `grep -P` reads a bracket holding multi-byte
characters as a set of individual *bytes*, so a pattern meant to match an
em-dash or en-dash also matches any other character sharing one of those
bytes.
Verified against a file holding an em-dash, an en-dash, a euro sign, and an
e-acute: a two-glyph bracket with the locale unset matched **three** lines,
including the euro sign (`e2 82 ac`, sharing the leading `e2` with both
dashes), while the identical pattern under `LC_ALL=C.UTF-8` matched the
correct two.
Injecting the bytes programmatically instead of typing them (`grep -P
"$(printf '[\xe2\x80\x94\xe2\x80\x93]')"`) does not help, for the same
reason -- what breaks is how the locale interprets the bracket, not how the
bytes reached it.
So a glyph scan has exactly two correct forms: set the locale, or leave
`grep` behind.

**Two traps beyond the error itself.**
First, a single-byte pattern like `\x{80}` does **not** error and *does*
match a line containing an em-dash -- it matches a continuation byte of that
character's UTF-8 encoding (`e2 80 94`) rather than the character, so a
byte-level pattern can produce right-looking output for the wrong reason and
will also match unrelated characters sharing that byte.
Second, and worse: the idiomatic `<check> || echo "clean"` wrapper converts
grep's exit-2 *tool error* into a printed pass, because `||` fires on any
non-zero status and cannot distinguish "searched, found nothing" (exit 1)
from "never ran" (exit 2).
That is the shell-fallback case
[`fail-fast`](../shared/principles/fail-fast.md) warns about, in the one
place it hurts most -- a verification step whose failure mode is a green
result.
When a check's own success message is the thing you would act on, branch on
the exit status explicitly (`rc=$?; case $rc in 0) ...;; 1) ...;; *) echo
"CHECK FAILED TO RUN"; exit 1;; esac`) rather than `||`-chaining it.
(ai-config#712, 2026-07-24: a pre-push glyph scan reported "clean: no banned
glyphs" without having scanned anything; caught only by re-reading the
command's own stderr, which was sitting in the same output.)

## An error quotes the failing call, so its ARGUMENTS are not your data

An error prints the call that raised it, arguments included.
Those arguments belong to the *library*, not to your input --- but they share a
line with the failure, so a distinctive-looking literal among them reads as the
thing that was flagged.

The shape: a call with a hard-coded search/pattern/sentinel argument fails on
*separate* input, and the message shows both.

```
Error in chartr("<U+2019>", "'", as.character(add_words)) :
  invalid input multibyte string 5
```

`<U+2019>` is `chartr()`'s **search** argument --- `hunspell:::dictionary_load()`
normalizing curly apostrophes, hard-coded in the package --- rendered as an
escape only because a non-UTF-8 locale cannot print it.
The real bad input is element `5` of `add_words`, an accented author name in
`inst/WORDLIST`.
Reading the escape as flagged data sends you hunting a smart quote the file
does not contain, and searching for the literal apostrophe glyph itself
returning zero hits then reads as a puzzle rather than as the answer.

The tell is a literal in the error that you cannot find in your own input.
Before concluding your data contains it, check whether it is a *parameter of
the call*: deparse the function
(`grep("chartr", deparse(pkg:::fn), value = TRUE)`) or read its source, and see
whether the literal is written there.
That also reveals which package really owns the frame --- worth knowing before
naming one in a doc or a bug report, since the failing frame is often a
dependency of the package you invoked rather than that package itself.

- **Do:** locate a suspicious literal in the callee's source before assuming it
  came from your input.
- **Do:** trust the index in the message (`... string 5`) over the eye-catching
  literal --- the index points at real data.
- **Don't:** treat an escape sequence in an error as evidence your input holds
  that character; a C locale escapes anything non-ASCII, the library's own
  constants included.
- **Don't:** name the package you called as the owner of the failing frame
  without checking --- `spelling` surfaced this one, `hunspell` owns it.

(`ucdavis/bcs#532`, 2026-07-31: a `CLAUDE.md` note blamed a curly apostrophe in
`inst/WORDLIST`; the file has none, and `grep -nP '[^\x00-\x7F]'` returns five
accented names.
The wrong cause shipped and was caught in review; the corrected note then
attributed `dictionary_load()` to `spelling` rather than `hunspell` --- the same
misreading one level down, caught by the next round.)

## Verifying R-package tests: install + testthat, never `source()` the R files
Hit on ucdavis/ettbc#14. The env had no `devtools`/`renv`, so I "verified" the new
tests by `sys.source()`-ing every `R/*.R` file and re-running the assertions by
hand. They passed — but CI's `R CMD check` failed with
`could not find function "run_augment_one"`. Two lessons:
- **testthat runs each test file top-to-bottom, and `test_that()` executes
  immediately.** Helper functions (and file-scope fixtures) must be defined
  **above** the `test_that()` blocks that call them. A helper defined at the
  bottom of the file is undefined when the earlier tests run. Manual sourcing
  hides this because you naturally define helpers before use in the REPL.
- **Don't emulate the test run by sourcing `R/`.** It reproduces neither
  testthat's execution model nor the package namespace (internal, unexported
  functions resolve under `source()` but the suite's `test_check` exposes them
  differently). Install the toolchain from the Posit package manager and run it
  the way CI does:
  `install.packages(c("testthat","cli", <Suggests used>), repos="https://packagemanager.posit.co/cran/__linux__/noble/latest")`,
  then `R CMD INSTALL .`, then `testthat::test_dir("tests/testthat", load_package="installed")`.
  roxygen2, lintr, and spelling install the same way — so `roxygenise()` (diff
  check), `lint_package()`, and `spell_check_package()` are all runnable locally
  even when `renv::restore()` can't reach the full dependency set.
  **Caution: a full `test_dir()` / `devtools::test()` pass can PRUNE `_snaps/`
  files whose snapshot test was skipped or went unrun this pass** (e.g. snapr
  tests skipped because `NOT_CRAN` is unset) — see the snapr section below before
  running it with `git add -A` in scope.

## R snapshot tests (snapr / testthat) — regenerating without collateral damage
Hit across ucdavis/bcs#264 (the snapr-based `expect_snapshot_data` suite):
- **When a snapshot's test is skipped or doesn't run in a given pass, a full
  `testthat::test_dir()` / `devtools::test()` run PRUNES its now-orphaned
  `_snaps/` file** (not every routine run — the trigger is the snapshot going
  unproduced this pass). On #264 the snapr tests were skipped (`NOT_CRAN` unset,
  see below), so a `test_dir()` pass treated their snapshots as orphaned and
  deleted 23 of them; `git add -A` then silently staged every deletion. (Stock
  testthat 3.x gates orphan *deletion* on snapshot-update mode — a normal run
  only warns — so the #264 prune was likely either an implicit update pass or
  snapr's own `expect_snapshot_data` pruning path; I didn't pin down which. The
  defense below holds either way.) Regenerate **per file** with
  `testthat::test_file("tests/testthat/test-<fn>.R")`, stage only the snapshots
  you meant to touch (`git add "tests/testthat/_snaps/<fn>.md"`), and if the suite
  did prune others, restore them: `git checkout origin/main -- tests/testthat/_snaps`.
- **snapr snapshot tests are skipped unless `NOT_CRAN=true`** (they're guarded
  like `skip_on_cran()`); locally you must set the env var or every snapshot
  silently no-ops and "passes" without comparing.
- **`furrr`/`future` parallel workers cannot load a `pkgload::load_all()`'d
  package** — a worker starts a fresh R process that only sees installed
  packages, so any snapshot that runs the analysis under `future_map` errors or
  produces nothing. Regenerate those snapshots in a **sequential** plan
  (`future::plan("sequential")` / set workers to 1), then copy the result into
  the parallel snapshot path — verify seq==par output on `main` first so the
  copy is sound.
- **A failed CI snapshot run may still upload the authoritative `.new` files.**
  When a reusable snapshot updater cannot commit because unrelated tests fail,
  download its or the coverage job's failure artifact and copy only the
  generated `*_*.new.*` files over their matching committed snapshots; do not
  regenerate a partial suite locally and assume skipped parallel tests are
  covered. Confirm the artifact head SHA matches the PR head before accepting
  it.
- **`require-review` failure caused by dispatch winning the concurrency race.**
  `cancel-in-progress: true` on a concurrency group means a newly-dispatched
  review cancels the still-running push-triggered review. The push-triggered
  run's `require-review` gate then shows as failed (cancelled parent = failed
  dependent), while the dispatched run's `require-review` is green. The PR
  shows `mergeable_state: unstable` from the cancelled run but is still
  mergeable — GitHub uses the most recent check run per name and commit SHA, so
  the dispatched run's passing `require-review` replaces the cancelled push
  run's check in branch protection. Confirm the dispatched run posted a clean
  verdict and proceed to merge; don't re-trigger. (gha#133.)
- **`tests/testthat.R` runs with `stop_on_warning = TRUE`**, so any warning
  during a test FAILS CI even with 0 test failures (shows as `WARN N`). When you
  hit it, don't guess the source — **capture the actual messages**
  (`withCallingHandlers(..., warning = \(w) {message(conditionMessage(w)); ...})`).
  On #264 the GLM "fitted probabilities 0 or 1" / "did not converge" warnings
  were a red herring; the real one was a `cli::cli_warn("risk ratio is undefined")`
  from a zero-risk group at small n. Muffle expected small-sample warnings in
  BOTH the package source (a `suppress_*_warnings()` helper wrapping the fit
  chain) AND the test helper, matching every pattern the fits actually emit.

## A push-to-main-only workflow can't fail a PR — add a static PR guard when you fix one
A workflow that triggers only on `push:` to `main` (deploy/publish/release jobs)
never runs on pull requests, so a bug it would catch stays invisible until after
merge — and then it fails on `main`, where no one is watching a specific PR.
Hit on d-morrison/rme#966/#967: the Quarto **publish** workflow (push-to-main
only) went red the moment the concept-map appendix merged and stayed red for two
days across several later merges, because no PR ever ran the full multi-format
website render that collides.

When you fix such a post-merge-only failure, don't stop at the fix — add a
**cheap static check that runs on `pull_request`** so the bug class can't regress
unnoticed. It needn't reproduce the whole heavy job; a few seconds of parsing
that asserts the invariant is enough. d-morrison/rme#970 added `check-render-headers`, a
~120-line Python + PyYAML script that asserts "no two of a render-list page's
formats resolve to the same output file," runs in ~8s, and would have caught the
original bug at PR time. Prevention (fix the scaffolder/template that emits the
bad input) and enforcement (the PR guard) are complementary — ship both.

## An Actions job that fails in ~1s with NO logs = a concurrency-group self-collision
When a GitHub Actions job reports `failure` almost instantly and has no logs at
all, don't hunt for a step that failed -- no step ran.
The signature is distinctive: the run's `created_at` and `updated_at` are 1 second apart, the
job's `completed_at` is stamped *before* its `started_at`, `get_job_logs`
404s on the log download, and the check run's `output.title`/`summary`/`text`
are all empty (so there's no annotation to read either).

The cause is a **job-level `concurrency:` group that resolves to the same
string as the workflow-level one**.
Per the Actions docs
([`jobs.<job_id>.concurrency`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idconcurrency)),
"there can be at most one running job or workflow in a concurrency group at
any time" -- the workflow run already holds the group, so its own job can
never acquire it and is failed immediately.
That sentence is verbatim from `data/reusables/actions/actions-group-concurrency.md`
in `github/docs`, the fragment both concurrency pages include.
It sits in that fragment's `{% ifversion actions-nga %}` branch; the `{% else %}`
branch reads "at most one running and one pending job" instead, which supports
the same deadlock, since only the at-most-one-*running* half is load-bearing here.
Nothing in the docs calls this deadlock out explicitly,
so it has to be recognized from the signature.

**Why it hides until after merge.** The two groups usually collide on only
*some* events.
A workflow-level `docs-${{ github.event.pull_request.number
|| github.ref }}` and a job-level `docs-${{ github.event_name ==
'pull_request' && github.run_id || github.ref }}` differ on `pull_request`
(PR number vs run id) but both fall through to `docs-<github.ref>` on push,
`release`, and `workflow_dispatch`.
So every PR check passes and the job dies the moment it merges --
a specific instance of the push-to-main-only blind spot in the section above.

**Confirming it cheaply,** since the logs are unavailable: read both
`concurrency.group` expressions and hand-evaluate them for the failing
event, then diff the workflow file against the last *successful* run of the
same trigger to prove the block is new
(`list_workflow_runs` with `workflow_runs_filter: {"event": "push",
"branch": "main"}`, then `git show <that-sha>:.github/workflows/<file>`).
Same-workflow, same-event, one variable changed is much stronger evidence
than reasoning about the expressions alone.

**The fix is usually to delete the job-level block, not to rename its
group.** A workflow-level `cancel-in-progress: true` cancels the whole run
including its jobs, so a per-`run_id` job group can't deliver the
"don't cancel this job" behavior such a block is typically written to
provide -- it was already dead code on every event where it differed, and a
deadlock on every event where it didn't. (`UCD-SERG/serocalculator#590`/`#591`,
2026-07-24: the altdoc-migration PR added such a block, so the merge to
`main` published no `/dev/` docs at all -- and no tag/release/dispatch deploy
could have run either -- while every PR docs build stayed green.)

## stop-hook-git-check's "N" flag can be a false positive for SSH-signed commits
The `~/.claude/stop-hook-git-check.sh` Stop hook flags a commit "N" (Unverified)
whenever local `git log --show-signature` can't verify it — but locally that
check needs `gpg.ssh.allowedSignersFile` configured, which this environment
usually doesn't set up. A commit made with `commit.gpgsign=true` /
`gpg.format=ssh` and the right `user.signingkey` is still genuinely signed even
when the local verify fails; `git cat-file -p "<sha>"` shows a real
`-----BEGIN SSH SIGNATURE-----` block with the correct author/committer email.
GitHub verifies independently (it publishes the corresponding public signing
key), so the commit still shows Verified there.

Before treating the hook's feedback as an actionable problem: check
`git cat-file -p "<sha>" | head -8` for the `gpgsig` block and confirm
`author`/`committer` say `noreply@anthropic.com`. If both hold, the "N" is a
local-verification artifact, not a real signing gap — no amend/re-sign needed.
Only act on the hook's suggested fix (config + `--amend --reset-author`) for a
commit that's missing the `gpgsig` block entirely, or whose author/committer
email is genuinely wrong. (ai-config#314 was the opposite: two SSH-signed
`noreply@anthropic.com` commits flagged "N" back-to-back, but both were already
correct — a false positive, not a real signing gap.)

## stop-hook-git-check also false-positives on GitHub's own merge commits
A second false positive from the same hook, distinct from the SSH-signing one
above: it flags the **merge commit GitHub creates when a PR is merged**.
That commit's committer is `GitHub <noreply@github.com>` by construction, which
trips the `%ce != noreply@anthropic.com` test.

The trigger is a specific, common state.
After a PR merges, restarting the designated branch from the updated `main`
(`git checkout -B <branch> origin/main`) leaves the local branch at `main`'s
merge commit while `origin/<branch>` still points at the pre-merge tip.
The hook's range is `origin/<branch>..HEAD`, so it holds exactly one commit --
GitHub's -- and the hook asks you to `--amend --reset-author` it.

**Do not.**
That commit is already merged and byte-identical to `origin/main`; amending it
mints a new SHA, diverges the branch from `main`, and publishing it means
force-pushing over shared history.
Two tells separate this from a real signing gap: the flagged commit has two
parents (`git log -1 --format=%p`), and `git rev-list origin/main..HEAD --count`
is `0`.

The fix is `--no-merges` on **both** of the hook's checks, since a merge commit
is never Claude-authored, and one pulled in by resetting onto `main` is not
unpushed local work:

```bash
unverifiable=$(git log --no-merges --format='%h %G? %ce' "$upstream..HEAD" ...)
unpushed=$(git rev-list --no-merges "$upstream..HEAD" --count ...)
```

Patching only the first converts the warning into a bogus "1 unpushed commit"
for the very same commit, so both lines are load-bearing.
The hook is provisioned by the CCR sandbox rather than by this repo, so the
patch has to be applied wherever that image is built; a session cannot fix it
for the next session, and editing `~/.claude/` is blocked by the permission
classifier anyway.
(UCD-SERG/serocalculator#618, 2026-07-27: fired on every turn for the rest of
the session once the PR merged.)

## Reproduce heavy-tool project bugs minimally
The Quarto
`safeMoveSync`/`renderProject` `rename '<stem>.html' -> No such file` collision
reproduced in an R-free, LaTeX-free two-file website project (`format: {html,
revealjs}`, one page missing the revealjs `output-file` rename so revealjs and
html both write `<stem>.html`) in seconds. When a full render/build is too heavy
to run in the sandbox, strip the failing behavior down to the smallest project
that still triggers it — it confirms both the diagnosis and the fix far faster
than the real pipeline, and becomes the negative test for the guard.

## R: `glm()`'s default `na.action = na.omit` silently MISALIGNS `fitted()`

`stats::glm()` defaults to `na.action = na.omit`, which **drops** rows with any
missing predictor. `stats::fitted()` then returns a vector **shorter than the
data frame**, so writing it back onto the full frame is wrong. How it fails
depends on how you write it back — and only one of the two is loud:

```r
data <- dplyr::mutate(data, p = stats::fitted(fit))  # ERRORS (size N vs size k)
data$p <- stats::fitted(fit)                         # SILENT when k divides N:
                                                     # base R recycles -> wrong rows
```

Verified on R 4.5 / dplyr 1.2 with `nrow = 100` and 50 complete cases:
`dplyr::mutate()` aborts with a size mismatch, while base `$<-` **silently
recycles** the 50 fitted values twice, assigning each prediction to two
different subjects. (Base `$<-` errors instead when `k` does *not* divide `N` —
so the same code is loud or silent depending on the data, which is worse than
either.) The same silent misalignment reaches you through any downstream
join/index pattern where the short vector escapes undetected.

Fix: `na.action = stats::na.exclude`, which pads `fitted()`/`residuals()` back
out to the full row count with `NA` at the dropped positions, preserving
alignment.

```r
fit <- stats::glm(f, data = data, family = binomial(), na.action = stats::na.exclude)
data <- dplyr::mutate(data, p = stats::fitted(fit))   # aligned; dropped rows are NA
```

**This is a latent landmine, not a hypothetical.** Code that has always been fed
fully-imputed (NA-free) data works perfectly and hides the bug — it only fires
the day a covariate with real missingness is added. If you see
`fitted(fit)`/`residuals(fit)` written back onto a data frame anywhere, check
the `na.action`, even if the code currently "works". (Found on ucdavis/bcs#349,
where adding a covariate that SAS deliberately leaves unimputed would have
activated it.)

## R: `mice` silently DROPS collinear columns instead of imputing them

`mice::mice()` runs a collinearity check and quietly removes offending
predictors — the evidence is only in `mi_result$loggedEvents`
(`meth = "collinear"`), not in a warning you'd notice. The completed dataset
then still has `NA` in the "imputed" column, and an
`expect_false(anyNA(x))` test fails with no obvious cause.

The usual trigger in a **test fixture**: covariates derived deterministically
from the row index (`race = k %% 2`, `bmi = 22 + k %% 11`, ...). That makes
every covariate an exact function of every other, so `mice` flags most of them
collinear and imputes nothing. The fixture *looks* rich and is actually rank-1.

Fixes:
- Build the fixture by **sampling under a fixed seed** (`withr::with_seed()`),
  not by deriving from the index — reproducible *and* genuinely varied.
- When `mice` doesn't impute something, `print(mi_result$loggedEvents)` first.
  It names the variable and the reason and saves a long hunt.

Note the same index-derived-fixture degeneracy also makes GLM coefficients
alias (NA coefficients) — which can be harmless if the test only asserts on
*fitted values* — so it can lurk in a fixture for a long time before `mice`
finally trips over it. (ucdavis/bcs#349.)

## Prove-the-test-fails reverts: commit the fix first, never revert uncommitted work

The standard "prove the new fixture catches the regression" step (temporarily
revert the fix, confirm the test fails, restore) is only safe once the fix is
**committed**. Sequence:

1. Commit the fix.
2. Revert to the parent commit's state: `git restore --source=HEAD~1 --staged
   --worktree -- "<file>"`.
3. Run the test, confirm it fails.
4. Restore the fix: `git checkout HEAD -- "<file>"`.

**Why `--staged --worktree`, and why not other forms:**

- **Index vs. HEAD.** Both flags matter -- the default `git restore
  --source=HEAD~1 -- "<file>"` only touches the working tree, leaving the
  fix still staged in the index (verified: default form left `git status`
  showing ` M`; `--staged --worktree` correctly showed `M `). That fixes a
  test that reads staged/working file *content* (`git show :"<file>"`, a
  checked-out worktree). It does **not** fix a test built on `git diff
  --cached`: HEAD is still the fix commit, so the cached diff is a non-empty
  reverse patch of the fix, not the empty diff a "clean at the parent"
  check would expect (verified directly). A test like that needs a
  detached worktree at `HEAD~1` instead, not an index/working-tree restore.
- **Uncommitted fix.** Reverting before committing is destructive, not just
  imprecise: `git checkout -- "<file>"` restores from the index, not HEAD.
  If the fix is unstaged (the index still matches HEAD), this silently
  discards the working-tree-only fix with nothing to restore back to. If
  the fix is staged, checkout hands it right back instead, silently
  no-opping the "revert" -- both defeat the point of the step, differently
  (verified both cases directly).
- **Branch/option parsing.** `git checkout "<file>"` (no `--`) can switch
  branches instead of restoring, if a branch shares the file's name
  (verified). A dash-prefixed filename is parsed as an option by *both*
  `checkout` and `restore` even when shell-quoted -- usually a loud error,
  but a name matching a real flag (e.g. `-p`) silently triggers that flag's
  behavior instead (verified: `git restore "-p"` opened interactive patch
  mode with no error at all). Always use `--` before the path.
- **Newly added file.** `git checkout HEAD~1 -- "<file>"` errors out if the
  fix itself added `<file>` (no match in the parent tree) -- `git restore
  --source=HEAD~1 --staged --worktree -- "<file>"` handles this correctly
  by removing the file entirely (verified both cases).
- **Stashing instead.** Once the fix is committed the working tree is
  clean, so `git stash push -- "<file>"` prints "No local changes to save"
  and exits 0 without creating a stash -- not silent, but easy to miss, and
  it leaves the fix in place during the "prove it fails" run (verified).

A scripted counter-edit (sed/perl) works the same way: edit, prove the
failure, restore via `git checkout HEAD -- "<file>"` -- safe here because
the fix is already committed and the index matches HEAD.

(Self-hit on Lacaedemon/sparta PR #870,
2026-07-15: proved the overlap test failed against the density-blind layout
via a perl counter-edit, then `git checkout -- scripts/SelectionManager.gd` to
"restore" — which discarded four uncommitted fix edits; all were re-applied
from conversation context, but only because they were small and recent.)

## A delegated fix must be verified against the issue body before merging

A triage summary (yours or a scout agent's) describes what the issue
*probably* means; the implementing agent then fixes the surface the SUMMARY
names, which can be adjacent to — not the same as — the surface the issue's
own words describe. Before merging a delegated fix, re-read the actual issue
body and check the diff touches the thing IT names. (Lacaedemon/sparta #863,
2026-07-15: issue said "the click and drag line doesn't match the current
unit width" — the delegated fix corrected the flank-grip RESIZE preview,
while the form-up click-and-drag one function over had the identical
density-blind bug plus a real deployment-overlap consequence; caught only
when the user asked which surface the PR targeted. The same bug pattern
recurring in the same file also means the pattern rule applied: fix every
occurrence, not the flagged one.)

## GitHub Pages serves stale content / new paths 404: check gh-pages size vs the 1 GB limit

- Signature: the site's existing pages load fine but a **newly added path
  404s**, even though the file verifiably exists at the `gh-pages` tip.
  Pages serves the last **successful build**, not the branch — when builds
  start failing, the domain silently freezes on an old deployment, so old
  content works, new content (including a just-merged fix deployed to the
  site root) never goes live, and nothing in the repo's checks goes red
  (deploy actions only push the branch; `wait-for-pages-deployment` is
  often disabled on private repos).
- First check: total site size against Pages' hard **1 GB** limit.
  The Pages build API (`/repos/<o>/<r>/pages*`) is blocked by the CCR agent
  proxy even for in-scope repos, so measure from git instead:
  `git fetch origin gh-pages --depth 1`, then
  `git ls-tree -r -l origin/gh-pages | awk '{s+=$4} END {printf "%.2f GB\n", s/1e9}'`
  (and the same `awk` keyed on path prefix for a per-directory breakdown).
- Usual cause in our repos: accumulated `pr-preview/<pr-N>/` directories —
  a rendered docs-site preview runs ~40+ MB, so a couple dozen closed PRs'
  previews reach 1 GB on their own.
- Fix: dispatch the repo's `cleanup-pr-previews` workflow (the
  `d-morrison/gha` reusable: deletes previews for non-open PRs, then
  orphan-squashes `gh-pages` under `compact-history`) rather than waiting
  for its weekly Sunday cron — the limit can be crossed mid-week. Re-measure
  after, and expect the next successful Pages build to pick up everything
  that accumulated on the branch while builds were failing.
- (ucdavis/bcs, 2026-07-18: 24 preview dirs put `gh-pages` at 1.05 GB; PR
  #375's preview and the post-merge production deploy both sat unserved on
  the branch while the URL 404'd; one dispatch dropped the tree to 0.09 GB.)

## Quarto `_metadata.yml` gets NO knitr pass -- inline R there renders as "Invalid Date"

- Signature: a Quarto document's title block shows a literal
  `Invalid Date` where a date should be. Affects every format the file
  renders to (HTML title block, revealjs title slide, docx), so it is not
  a format-specific quirk.
- Mechanism: knitr evaluates inline R (`` `r expr` ``) in the document
  body and in the document's **own** YAML front matter. A directory-level
  `_metadata.yml` is a plain YAML file that Quarto merges into the
  document metadata directly, with no knitr pass -- so
  ``date: '`r Sys.Date()`'`` reaches Quarto's date handling as a literal
  backtick string, fails to parse, and renders as `Invalid Date`.
- Fix: use Quarto's own resolved keywords, which need no R evaluation --
  `date: today` (or `now` / `last-modified`). `today` resolves to the same
  current date `Sys.Date()` was meant to produce; how it is *displayed* is
  a separate question, controlled by `date-format`. Leave a comment
  next to it, or the inline-R form gets reintroduced by the next person who
  "fixes" the hardcoded-looking value.
- The per-format display defaults differ, which is easy to mistake for a
  bug when comparing two outputs of the same document. With no
  `date-format` set, the same `date: today` renders as a locale long date
  in HTML (`July 25, 2026`) but as ISO in revealjs (`2026-07-25`) --
  observed on one render of the reprex below under Quarto 1.10.18
  (2026-07-25), not looked up as a documented guarantee.
  Set `date-format: iso`
  explicitly if you need them to agree. Note that the `dcterms.date` meta
  tag is always ISO in both, so grepping the raw HTML for `\d{4}-\d\d-\d\d`
  finds a match even when the visible date is not ISO -- read the title
  block's own text, not just any date-shaped string in the file.
- Reprex (fast, no package deps): put the date in a `vignettes/_metadata.yml`,
  add a trivial `.qmd` beside it, `quarto render`, then
  `grep -c 'Invalid Date'` the outputs. The same throwaway-`.qmd`-beside-the-
  real-`_metadata.yml` trick verifies a fix against the REAL metadata file
  without needing the package's own render dependencies.
  (UCD-SERG/serocalculator#597/#598, 2026-07-25.)

## Verify a rendered docs site via the `gh-pages` blob, not the Pages URL (which 403s WebFetch)

- Signature: you want to confirm a docs/render fix actually landed on a
  deployed site (a PR preview, `/dev/`), but `WebFetch` on the
  `*.github.io` URL returns `403 Forbidden`, and `curl` to it can fail
  outright at the transport layer.
- Mechanism: GitHub Pages rejects these fetches (apparently anti-scraping).
  The deployed bytes are still a plain file in the repo -- Pages serves the
  `gh-pages` branch -- so they are reachable through the raw-blob host,
  which does not 403 for public repos.
- Fix/check: map the site URL to its branch path and raw-fetch it:
  `https://raw.githubusercontent.com/<owner>/<repo>/gh-pages/<path-after-the-site-root>`
  -- e.g. a preview at `<site>/pr-preview/pr-598/vignettes/x.html` is
  `.../gh-pages/pr-preview/pr-598/vignettes/x.html`. Then grep the HTML for
  the thing you're verifying.
- This is strictly better than the "403 on the docs page, so raw-fetch its
  `.qmd` source instead" fallback in `d-morrison/gha`'s `CLAUDE.md`: the
  source only tells you what SHOULD render, while the `gh-pages` blob is the
  actual rendered artifact the reader sees, so it verifies the whole
  toolchain end to end.
  (UCD-SERG/serocalculator#598, 2026-07-25: confirmed the fixed title slide
  read `2026-07-25` with zero `Invalid Date` on the real PR preview, after
  both `WebFetch` and `curl` to the Pages URL failed.)

## Dead rdrr.io self-links on an altdoc docs site = downlit couldn't discover the site

- Signature: an altdoc/Quarto docs site (`code-link: true`) links the
  documented package's **own** functions to
  `https://rdrr.io/pkg/<pkg>/man/<topic>.html`, all 404 — rdrr.io only
  indexes CRAN packages.
- Mechanism: downlit resolves a package's site by fetching
  `<DESCRIPTION URL>/pkgdown.yml` at render time
  (`remote_metadata_slow()`); on a **private** GitHub Pages repo that URL
  404s publicly (the real site sits behind auth on an obfuscated
  `*.pages.github.io` domain), so downlit falls back to rdrr.io for every
  self-reference. Deliberate downlit behavior (r-lib/downlit#106, #195) —
  not worth forking downlit over, since even its local-package hooks emit
  pkgdown's `reference/` layout, not altdoc's `man/`.
- Fixed generally in the `d-morrison/altdoc` fork (altdoc#25/#26): the
  post-render rewrite pass converts the documented package's rdrr-form
  self-links to page-relative `man/` links, alongside the recorded-site-URL
  form it already handled. A consumer repo just needs its renv altdoc pin at
  or past that merge (`fb551ef`, 2026-07-18) and a re-render.
  (ucdavis/bcs#374/#375: ~140 dead links on one article page.)

## A test suite that only covers the exact-multiple/round-number case can miss an asymmetry bug entirely

- Signature: a function distributes `n` items across `k` groups (soldiers
  across formation files, rows across pages, work across shards) and has a
  "leftover redistribution" rule for when `n` isn't an exact multiple of
  `k` — e.g. centre the remainder, round-robin it, pad the last group.
  A hand-written implementation of that rule can be silently biased (always
  piling the remainder onto the same edge/first group) while every test
  only ever exercises `n` values that ARE exact multiples of `k`, so the
  remainder-handling code path never actually runs under test at all.
- Mechanism: it's natural to write the "happy path" test first (round
  numbers, no remainder) and consider the function covered once that
  passes, especially when the remainder case feels like a minor edge case
  rather than the interesting part of the function. But the remainder case
  is exactly where an asymmetry bug lives — the exact-multiple case can't
  distinguish a correctly-centred remainder from a raw
  first-N/last-N assignment, because there IS no remainder to place.
- Fix/check: for any "distribute `n` across `k` with a leftover rule"
  function, deliberately test at least one `n` where `n % k != 0`, and
  assert on WHERE the leftover lands (centred, not banked onto one edge),
  not just that every item got assigned somewhere. If reviewing someone
  else's tests for such a function, check the specific `n`/`k` values used
  and confirm at least one is a genuine non-exact-multiple case before
  trusting the coverage. (Sparta#995/#997, 2026-07-19: a formation-grid
  reflow function's tests all happened to use soldier counts that were
  exact multiples of the file count, so a real bug — a raw `i % files`
  assignment piling every reshuffled unit's leftover rank onto the same
  edge column instead of centring it, making a fresh, zero-casualty spawn
  visibly lopsided for almost every real unit in the game — passed the
  full test suite undetected until an independent review deliberately
  picked a non-exact-multiple count to check.)

## R `gsub()` correction: `fixed = TRUE` keeps replacement literal

Correction to an earlier note: with `gsub(..., fixed = TRUE)`, both matching and
replacement are treated literally (no backreferences), so this mode does *not*
interpret replacement escapes like `\\1`.

If you do need regex matching (`fixed = FALSE`), replacement escapes can still
apply, so validate any claim about replacement behavior against a runnable
example before recording a generalized rule.
(Correction logged from review on d-morrison/ai-config#641, 2026-07-22.)

## When a diagnosis asserts an ordering, measure the ordering

A bug report that explains itself in terms of *sequence* -- "X skips it
because Y already put it there", "the cleanup runs before the writer" -- has
smuggled in a claim that is usually cheap to test and rarely tested.
The explanation sounds mechanical, it accounts for the symptom, and every
detail in it is individually true, so the sequence goes unchecked and the
proposed fix targets a step that was never at fault.

Two sources usually settle it outright.
A tool's own log is a timestamped record of what it saw: counts of what it
did and did not act on discriminate between orderings, so read what it
*reported* rather than reasoning about what it would have done.
And `stat -c '%y'` on the artifacts gives an independent clock.
Prefer a count that could not hold under the proposed story: "zero skips" is
decisive in a way that "it looks linked" is not.

Beware inherited mtimes when using the second source alone.
A file materialized from a bundle can carry the bundle's timestamp, so an
artifact can look older than the event that created it, and the log-based
check is what disambiguates.

(ai-config#765, 2026-07-28: an issue attributed stale skills to `bootstrap.sh`
skipping pre-seeded copies.
Its log showed 527 `already linked` and zero relevant skips, so every entry was
still a symlink when it ran -- 53 pre-seeded directories would have produced 53
skip lines.
The clobber came a second later, from a different pass.
Implementing the suggested fix would have changed a code path that was never
reached, and the repair would have been wired to a hook that runs before the
damage.
The affected directories' mtimes read *earlier* than the bootstrap run because
they were copied from a bundle, which is why the log, not the mtimes, was the
deciding evidence.)

## An except-branch that substitutes a fallback value hides a misclassification

A `try/except` whose handler assigns a default instead of re-raising turns a
failed computation into a *quiet answer*, and the answer is usually wrong in a
way nothing downstream can see.
It is the swallowed-error shape from
[`fail-fast`](../shared/principles/fail-fast.md), one level in: the exception
is caught deliberately and for a real reason, so it does not read as swallowing
at all.

Path comparison is where this bites most often, because the two sides can
disagree without either being wrong:

```python
try:
    rel = candidate.resolve().relative_to(ROOT).as_posix()
except ValueError:
    rel = raw_source          # <- silently a different string
```

`resolve()` follows symlinks and `ROOT` may not have been resolved, so
`relative_to` raises `ValueError` and the fallback returns something that
never matches the registry it is about to be looked up in.
Every branch keyed on that lookup then takes the wrong arm, with no error
anywhere.
macOS makes this reproducible for free: `tempfile` hands out `/var/folders/...`
while `resolve()` returns `/private/var/folders/...`, so a test exercises the
fallback that production never reaches, or the reverse.

Two habits:

- **Resolve both sides of any path comparison**, not just the one you compute.
- **Prefer a test over an inspection for this class of bug.**
  A fallback branch is invisible in review precisely because the code that
  produces it looks defensive and correct.

(Morrison-Lab/ai-config#804, 2026-07-29: a new `check_plugin_sources()` in
`scripts/validate-skills.py` classified an uninitialized git submodule as a
warning and anything else missing as an error.
Its own regression test failed on the warning case only, because the temp-dir
root was unresolved -- so every registered submodule would have been demoted to
the error branch on any checkout reached through a symlink.
The function passed against the real repo throughout, since `ROOT` there is
already `resolve()`d.)

## Read the failure's own output --- the PR thread is one of its surfaces

`Morrison-Lab/gha`'s `CLAUDE.md` states the rule under "Never just theorize
-- investigate empirically": read the failure's own output before theorizing
about its cause.
Agreeing with it is not the hard part.
The hard part is that "the failure's own output" names a place, and which
places get searched is decided by habit rather than by where the string is.

Check runs, job step lists, artifacts, and job logs are the habitual four,
and they share one assumption: that a failure registers as a failure
somewhere.
An agent run can break that assumption outright.
Its post-step reports the error by **posting a plain comment on the PR**, and
the job itself finishes green, so every step conclusion reads `success` or
`skipped` and there is no failure surface left to inspect.

That is what makes the wrong conclusion the end of a *thorough* search rather
than a careless one.
Nothing was hidden, nothing needed credentials, and the string sat in plain
text on the thread throughout --- in the one place a CI investigation does not
look, because a PR comment does not read as CI output.

So list the PR's own comments early, before concluding an error string cannot
be recovered.
It costs one call and needs no credentials.
Then generalize past PR comments to the shape: any surface the failing system
*writes to* can carry its error, including an issue thread, a commit status
description, and a check run's summary text.

- **Do:** read the PR's comment list before reporting a failure's output as
  unavailable.
- **Do:** read the job's own conclusion first, since an all-green job means
  the error is on no failure surface and the search has to move elsewhere.
- **Don't:** treat check runs, step lists, artifacts, and logs as exhausting
  where a failure reports itself.
- **Don't:** read a thorough search of those four as evidence that the string
  does not exist.

(`Morrison-Lab/ai-config#986`, 2026-07-31: a session read check runs, job step
lists, and artifact listings across several failed review runs, concluded the
underlying error string was unrecoverable, and published that conclusion
twice.
The string was a PR comment posted at 20:47:04Z reading `Prompt is too long`,
the API's context-length error verbatim, under a footer naming the posting
step and linking workflow run 30664135897.
That run is the agent, `claude-bot.yml` calling `claude.yml@v1`, and its one
job `claude / claude` concluded **success** with every step `success` or
`skipped`: step 19 `Run Claude Code` ran 36 seconds, and step 23
`Post Claude's response if no code was committed` completed one second after
the comment's own timestamp.
The maintainer found it by reading the thread.)

## An artifact you cannot retrieve may never have been produced

This narrows the section above rather than standing beside it.
It explains why one route came back empty, and it is not why the answer was
missed, since the answer was on the thread the whole time.

Before diagnosing why a fetch failed, confirm the thing was produced.
A retrieval failure and a nonexistent artifact present identically: every
route returns nothing, and the routes are where the error messages come from,
so all the available evidence describes access.

That makes the wrong diagnosis the cheap one to reach and the expensive one to
hold.
"I cannot download it" sends you to credentials, scopes, and proxy policy.
Worse, it is a claim about someone else's configuration, so it gets reported
to a user or written onto an issue as a blocker they are expected to clear.
Nothing in the repository contradicts it, because the artifact that would have
is the one that was never written.

Adding routes does not settle it either.
Three failing routes read as stronger evidence of an access problem than one,
when they are the same non-observation three times.

Ask instead what step would have produced it, and check that step ran.
For a GitHub Actions artifact that is one call: `actions_get`
`get_workflow_job` on the job id returns the job's `steps` array, and a
producing step is either named there or is not.
The same shape works elsewhere: a log nobody configured, a report whose
generator was skipped, a cache never populated.

- **Do:** name the step that produces the artifact and confirm it ran, before
  spending a call on fetching it.
- **Do:** report "nothing produced it" as a different finding from "I cannot
  reach it", since only the second is anyone else's to fix.
- **Don't:** read several failing access routes as evidence about access ---
  they are one non-observation repeated.
- **Don't:** publish a retrieval blocker to a user or an issue without the
  production check behind it.

(2026-07-31, `Morrison-Lab/ai-config`: repeated attempts to download the
`claude-code-action` execution-output artifact for failed `claude-review` runs
were reported to the user, and on a tracking issue, as an access problem.
MCP tools list artifacts but cannot download them, and direct fetches returned
403 under both owner spellings, with and without a token.
Those runs were pinned at `Morrison-Lab/gha`'s `claude-code-review.yml@v1`,
which has no `Resolve and upload execution file path` step at all, so no
artifact ever existed for any of them --- confirmed by
`git show v1:.github/workflows/claude-code-review.yml`, which defines 12 named
steps and no upload.
See [`claude-bot-workflows.md`](claude-bot-workflows.md), whose
artifact-download advice presupposes `@v2`.)
