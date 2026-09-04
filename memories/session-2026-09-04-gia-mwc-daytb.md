# Session notebook: GIA sweep, continued on 2026-09-04

Continues [`session-2026-09-03-gia-mwc-daytb.md`](session-2026-09-03-gia-mwc-daytb.md) after the quota pause at 21:44 PDT;
same session, same mandate (`gia mwc daytb` on this repo), split here because the 09-03 file stood at 1310 lines at `d504cb98`, over the 1250-line gate, before the split.
Times are PDT on 2026-09-04 unless a heading says otherwise.

## 00:34 PDT (2026-09-04) --- resumed after the quota reset; r4 loops and both memory reviews launched

The user reported the reset and asked to continue.
The four r2 loops from the earlier limit turned out to have kept running under their own task ids after the pause's stop calls (which hit the r3 runs), and their completion notices arrived at 21:50 PDT:
0 of 6, 0 of 10, 1 of 12 (#3003 at `facfff6a`), and 0 of 10 verified, every other item cut by the session limit that reset at 00:10 PDT (each failure reads "You've hit your session limit" and names the reset as "7:10am (UTC)").
A later loop then committed on #3003 (`87b177f4`), so that verdict does not cover HEAD and #3003 rides in the wave-4 loop instead of being skipped.
The `wip:` commit on wt-2422 is dropped back into the tree;
wt-3038's `wip:` commit (`b9a75b79`) is under a later fix commit and stays for its loop to squash or reword.
Launched: round 7 on `ums/2026-09-03-fetch-by-sha` (`4af1f1ea`), round 1 on `ums/2026-09-03-recurrences` (`012c3d1c`), and r4 loops for waves 1 to 3 (`wf_c36c0514-ff3`, `wf_e9b0b619-162`, `wf_913fbdba-601`);
wave 4's r4 script (11 items) launches when a reviewer frees a slot.
Every branch on `origin` is a snapshot behind its worktree at most by the loops' new commits;
pushes fast-forward, never force.

## 00:44 PDT --- memory-pass branch round 7: four more mechanism defects; the section is cut to its point at `e91dda59`

Round 7 at `4af1f1ea` found the ranged `rev-list` claim false (a depth-1 clone returns 1 for the ranged form and 226 with only the PR ref deepened, since the exclusion side is grafted too), a "no request packet" claim that a flush packet refutes, an unscoped "always sends the want", and a nine-line sentence.
Rather than patch a fifth time, `e91dda59` removes the `ls-refs`/advertisement paths, the want-packet counts, and the protocol-default history, keeping the ref-name resolution, the two error strings with the one measured local-path variant, and the shallow-walk bound for both the plain and the ranged count.
Round 8 dispatched with a brief to re-measure each remaining claim in a fresh depth-1 clone.

Lesson for the memory pass: when a review loop keeps finding defects in sentences the entry's point does not need, the fix is deletion, and the tell was round 3, when the first mechanism sentence went in;
four rounds were spent defending detail no reader acts on.

## 00:48 PDT --- recurrences branch round 1: eleven findings, all about who said what and where

The review of `012c3d1c` confirmed every measurable claim (the workflow lines, both Jules verdicts, the two red heads and their causes, the grep behaviours, the issues) and found eleven attribution and dating errors: one run's wording quoted as both runs';
the second run's date item named the real file, so "a file the diff does not carry" was true of the first run only and the Do bullet mis-routed;
a UTC date beside two Pacific ones in the same diff;
the `(` claim placed in a commit body when it was in the prose line that commit added;
"each caught by an adversarial verdict" true of one case;
`memories/git.md` cited for a case it does not record (the sibling branch adds it, so the citation now names `709bc612`'s retraction instead);
the `mergeable_state` claim undated and underived;
a missing premise;
"afternoon" for 20:08 PDT;
no boundary with the inherited-claims bullet;
and two earlier prompt-injection blocks on the same PR omitted, one cleared by a single re-run.
`69523bd0` answers all eleven and `fc74e12a` replaces a head SHA I had guessed for the earlier block with the measured time.
Round 2 dispatched.
`memories/github-actions.md` is at 1243 of 1250 lines.

Lesson for the memory pass: a case record's attribution claims (which run, which artifact, who caught it) are the ones written from memory of the session rather than from the forge, and they were wrong at a higher rate than the measurements;
write them by re-reading the comment or commit named, not by recalling it.

## 00:54 PDT --- memory-pass branch round 8: the cut held; four residual sentences

Round 8 at `e91dda59` re-derived every numbered claim in a fresh depth-1 clone (plain and ranged counts 1, then 226 after deepening the PR ref, `--is-ancestor` exit 0 for all three) and found four residues:
the ranged-count sentence named the exclusion side as the cause when deepening `main` alone leaves the range at 1 (the walk back from the grafted tip binds);
the local-path refusal lacked its v2 contrast (measured here: v0 refuses, v2 fetches);
the opening's "says only whether its argument is a ref name" was unscoped against the full-SHA refusal;
and "was not a ref name" contradicted "resolved as a ref name".
`2969d8cb` fixes the four;
round 9 dispatched.

## 01:05 PDT --- recurrences branch round 2: the Jules entry re-derived owned content, and the #3154 merge exceeded the grant's letter

Round 2 at `fc74e12a` confirmed ten of eleven closures and found eleven more.
The load-bearing ones: the "single re-run cleared" claim was false (the approve four minutes later reviewed a new head, `c6ea044c`);
the disposal rule re-derived `fully-clean.cases.md`'s #818 record (Jules blocking for injection, repeating verbatim, claude-review clean, "the maintainer's call was to hold;
the PR merged with `jules/review` red") without citing it, and installed a session-side disposition where the precedent had the maintainer decide;
and the disposal rule never named that `check-pr-fully-clean.py` and the #2274 veto still read the head as not-clean, so the #3154 merge at 20:53 PDT exceeded the grant by its letter.
Filed as [#3192](https://github.com/Morrison-Lab/ai-config/issues/3192), which puts the disposition to the maintainer;
the entry now cites #818 and #3192 instead of settling it.
Smaller: a `/pulls/N/status` path that does not exist (it is `commits/<sha>/status`), #817 added the `extra_instructions` input and #2293 the env-var spelling, two inexact quotations, "two ASCII dashes before" reading as a commit distance, a pronoun on the wrong clause, a "third occurrence" over two cases, "per the section above" citing a section that repaired by amend, and a scope sentence excluding two of the four cases.
`684be2e9` answers all eleven;
round 3 dispatched.
`memories/github-actions.md` is at 1246 of 1250 lines.

Lesson for the memory pass, and the one this whole pass keeps teaching: the dupe check the #3154 fix widened was skipped for the entry recording #3154's own review, and the owned record (#818) was two directories away in `shared/workflow/`;
the corpus-wide grep the new step 3 prescribes would have found "injection-detector block" in one command.

## 01:07 PDT --- memory-pass branch round 9: every measurement confirmed; four residues in the remedy and provenance

Round 9 at `2969d8cb` re-derived every claim in a fresh depth-1 clone and a blob-less full clone and confirmed all of them, including the ranged count staying at 1 after deepening `main` to 500.
The four residues: the provenance line credited the catching review with "a full checkout" when its own comment says it fetched `refs/pull/3060/head` live and later rounds say its clone was shallow;
"Neither wording" after three wordings resolved to the wrong pair;
"walks forward" for a `rev-list` walk;
and the Do bullet prescribed a bounded deepen for a count query, which returns 226 against a true 2434 after the section's own `--depth=200` fetch, so a total count needs `--unshallow`.
`6a8f4a49` fixes the four;
round 10 dispatched.

## 01:15 PDT --- memory-pass branch round 10: one clause; pushed at `0242210f` for the forge reviewers

Round 10 at `6a8f4a49` re-measured everything (including `--depth=3000` on the PR ref returning the full 2434 while the clone stayed shallow) and left one finding: "any bounded depth still truncates it" was a false universal.
`0242210f` takes the reviewer's own shorter wording ("no depth picked in advance is known to reach the root") and no eleventh local round was run;
the PR body says so, and Copilot, Jules, and claude-review review the head on the forge.
Ten local rounds on a 65-line memory entry (its added lines at `0242210f`): rounds 1 and 2 on wording and causes, 3 to 7 on protocol mechanics the point never needed, 8 to 10 on the remedy's own claims.

## 01:15 PDT --- #3193 opened for the fetch-by-SHA entry; wave-4 loop launched

`ums/2026-09-03-fetch-by-sha` pushed fast-forward from the `4af1f1ea` snapshot to `0242210f` and opened as [#3193](https://github.com/Morrison-Lab/ai-config/pull/3193);
claim comment posted, Copilot requested, `@jules review` posted, subscription on.
The freed slot went to the wave-4 r4 loop (`wf_fa84b50c-e0b`, 11 items including #3003).
Five slots: four loops and the recurrences branch's round 3.

## 01:23 PDT --- recurrences branch round 3: the corpus already said "hold"

Round 3 at `684be2e9` found the file that owns this block shape, `review-verdict-pitfalls.md`'s seventh case ("re-triggering cannot clear it";
"do not count the re-raise against the rebuttal test ... reply once, then hold"), uncited and contradicted by the entry's "re-run once";
also "identical" in the heading when the two blocks differed in wording, a "nondeterministic" mechanism the corpus twice refuses to infer, the phantom file described as merely out of scope, two pronouns on the wrong clause, a heading covering half its section, and a missing boundary with "A block presented as program output".
`90fe6c86` cites the seventh case and #818, tells a session to rebut once, file, and hold, records the #3154 merge as the exception #3192 puts to the maintainer, and trims the file to 1249 of 1250 lines;
round 4 dispatched.

Lesson for the memory pass: the answer to "may a session merge over a repeating false-positive block" was already in the corpus (hold), two files away from where the session looked, and the merge of #3154 was made against it;
the dupe check has to run on the *rule* being recorded, not only on the incident.

## 01:25 PDT --- #3193: claude-review Ready with one nit, Copilot quota-skipped, Jules approved; `e63fd956` pushed

claude-review at `0242210f` reproduced every claim and returned Ready for merge with one non-blocking nit: `--is-ancestor` on the incident's shape dies with `fatal: Not a valid commit name <sha>` (exit 128) rather than returning a boolean.
Measured here: exit 128 with the ancestor's object absent, a quiet exit 1 once it is fetched;
`e63fd956` quotes both.
Copilot's round was a quota skip ("the user who requested the review has reached their quota limit"), so Copilot was re-requested on the new head and `@jules review` was posted in the same comment.
Jules approved `0242210f`.
The merge follows claude-review and Jules on `e63fd956` plus green checks;
a second Copilot quota skip is recorded as a skip, not as clean, and does not block on its own since Copilot has posted no finding on this PR.

## 01:31 PDT --- #3193 merged at `9578d66b`

At `e63fd956`: claude-review Ready for merge (it reproduced both `--is-ancestor` shapes), `require-clean-verdict` and every other check run green, `jules/review` success ("verdict: approve"), the adversarial verdict at `6a8f4a49` plus round 10's own wording at `0242210f`.
Copilot quota-skipped both heads ("the user who requested the review has reached their quota limit") and posted no finding;
the squash body records that.
Merged under the standing grant;
worktree and branch removed;
`main` fast-forwarded to `9578d66b`;
subscription dropped.

Merge-time memory pass, owed and queued behind the recurrences branch's round 4 (so as not to invalidate a running review):
(1) the deletion lesson from rounds 3 to 7, for `skills/ums/SKILL.md` or `shared/workflow/adversarial-self-review.md`: when successive rounds find defects in sentences the entry's point does not need, cut the sentences rather than patch them;
(2) check whether `memories/copilot-reviews.md` already records the quota-skip notice and its disposition (a skip is not clean and not a finding;
it does not block on its own when Copilot has posted nothing).

## 01:36 PDT --- recurrences branch round 4: the injection item had no rebuttal in the Do bullet

Round 4 at `90fe6c86` closed round 3's seven and found six more, two load-bearing:
the Do bullet's evidence (file list, clock) answered the date and file items and said nothing to the injection item, and the "sub-shape the seventh case does not name" offered a property that case already records (text in no diff);
the missing fact was in the entry's own first paragraph, that `INPUT_EXTRA_INSTRUCTIONS` is the reviewer's trusted configuration, so the rebuttal is provenance.
Also: `hooks/warn-status-read-after-pipe.py` already guards the `$?` form of the pipe defect and #3184 should extend it;
two verbatim clauses copied from the section above;
the `-zz` exit status stated as entailed when it depends on an accidental match;
and the `mergeable_state` discriminator restated 520 lines from the file's own bcs bullet.
`6fdb619b` answers all six and adds the deletion lesson from #3193 as a `ums` anti-pattern bullet;
round 5 dispatched.

## 01:51 PDT --- recurrences branch round 5: the Jules entry moves to `memories/jules-review.md`

Round 5 at `6fdb619b` closed round 4's six and found seven more, the load-bearing one structural:
`memories/github-actions.md` at 1249 of 1250 lines would fail the next one-line append, and the corpus precedent is a satellite at the gate.
`0b522fd3` moves the section to `memories/jules-review.md` (header in the `github-actions-outages.md` shape, its own `MEMORY.md` row) and `github-actions.md` returns to 1190 lines, unchanged against `main`.
Also: the errexit paragraph attributed a `$?` form to a section that has none (the hook's own case is #2149), and said #3184 extends the hook when the issue as filed proposed a second detector, so a comment on #3184 now proposes the extension and the paragraph says so;
the blank line that made the whole `ums` anti-patterns list loose is gone;
two pronouns, "the rebuttal is provenance" attributed to the seventh case, and "`-zz` is the valid `-z` flag twice".
Round 6 dispatched.

## 02:03 PDT --- recurrences branch round 6: an untracked file passed the local gate

Round 6 at `0b522fd3` found the `new-line-breaks` gate red on the new `memories/jules-review.md` while my local run had printed clean:
the file was untracked when the gate ran, and plain `git diff` never shows untracked content (the trap `memories/git-diffing.md` and gha's own README record);
the 82-character semicolon line is split and the chain now stages before gating.
Also from the move: "the bcs bullet above" pointing at nothing in the new file, two pronouns, a stray comma in the index row, no inbound link from `github-actions.md` (its header now names the satellite, 1191 lines), "the guard is filed" reading as the existing hook, "only `[` errors" false for `\{`, `\(`, `\)`, and round numbers the #3193 body does not assign (now the five commits `1fff7e63` to `4af1f1ea` and the cut at `e91dda59`).
`0c39d330` and a follow-up answer all eight;
round 7 dispatched.

Lesson for the memory pass: the untracked-file gap in the diff-scoped gates is documented and was hit anyway, on a file this very PR created;
a `git add` before the gate chain is the mechanical fix, and the chain template in the notebook now carries it.

## 02:19 PDT --- recurrences branch round 7: three findings in the ums case; pushed at `c8acdfc2`

Round 7 at `07dbebd0` confirmed every measurement and the move, and found the `ums` bullet's case wrong twice over:
`1fff7e63` wrote the Don't bullet's own one-command test (seven of its fifteen lines survive at #3193's merged head), so "protocol detail the Do/Don't never used" was false of it, and "the cut held" was false because `2969d8cb` re-added a protocol clause and three more rounds patched the paragraph;
plus "those four" with no antecedent.
`c8acdfc2` takes the reviewer's wordings (the five commits re-patched the same mechanism sentences, which the Do/Don't never used and `e91dda59` deleted;
the deleted paragraphs were not restored;
the four characters named) and no eighth local round was run;
pushed fast-forward from the `012c3d1c` snapshot and opened as a PR for Copilot, Jules, and claude-review.
Seven local rounds on a six-file memory pass (`git diff --name-only 9578d66b...c8acdfc2`): rounds 1 and 2 on attributions, 3 on the owned rule, 4 and 5 on the rebuttal's evidence and the file cap, 6 on the move's residue and an untracked file, 7 on the case cited for the deletion lesson.

## 02:20 PDT --- #3195 opened for the recurrences branch

`ums/2026-09-03-recurrences` at `c8acdfc2` opened as [#3195](https://github.com/Morrison-Lab/ai-config/pull/3195);
claim comment, Copilot requested (may quota-skip), `@jules review`, subscription on, squash body prepared.
The merge follows claude-review Ready, Jules approve, and green checks;
a Jules block on this PR is held per its own entry, not merged over.
Slots: four loops running, none for reviews.

## 02:27 PDT --- #3195 merged at `a72b0b39`

At `c8acdfc2`: claude-review Ready for merge (every citation traced), `require-clean-verdict` and every other check run green, `jules/review` success (approve), seven adversarial rounds;
Copilot quota-skipped with no finding.
Merged under the standing grant;
worktree and branch removed;
`main` fast-forwarded to `a72b0b39`;
subscription dropped.
Merged this session: #3154, #3166, #3171, #3193, #3195.

Merge-time memory pass: the two lessons this branch's rounds taught that the corpus does not yet carry as a rule are filed rather than written, since each wants its own PR and the loops hold the slots:
the untracked-file blind spot of the diff-scoped gates recurred with the rule loaded (an instrument is owed), and the `ums` dupe check ran on the incident's vocabulary rather than on the rule being recorded (step 3 wants a second query on the rule).
Filed as [#3196](https://github.com/Morrison-Lab/ai-config/issues/3196) (the diff-scoped gates' untracked-file blind spot wants an instrument) and [#3197](https://github.com/Morrison-Lab/ai-config/issues/3197) (`ums` step 3 dupe-checks the rule, not only the incident).

## 03:29 PDT --- notebook branch: adversarial rounds with no PR open yet, and the per-round entries are cut

As of `bdeeb6f5`, the head round 8 reviewed, eight adversarial rounds had run on this branch with no PR open, returning eleven, six, four, four, four, eleven, four, and three findings.
Round 1's were nine figures and mechanism claims written from recollection where the instrument was one command away (line counts, a character count, a PR's `updated_at` written as its open time, a grep search target, a `rev-list` direction, a bare UTC stamp, an index row) and two ambiguous references.
The 84 that should have been 82 was also in #3196's body, corrected there at 02:50 PDT.
Rounds 2 to 4 found defects in older entries (dangling "the HH:MM entry" pointers, a merge heading a minute late against its commit, an ancestry parenthetical left uncorrected in place) and, in growing share, in the entry the previous round's fix commit had appended to narrate its fixes: a wrong entry named, an unmeasured line distance, a miscount, a self-description the same entry contradicted, a claim about #3196's body that went stale within the minute, and a citation of the `ums` anti-pattern for a shape it does not record.
Those three narrating entries, appended by the commits answering rounds 1 to 3, were deleted rather than patched at `48380505`, the commit answering round 4, and this entry took their place.
Rounds 5 to 8 found figures in older entries no round had re-measured (a file count, two commit distances, two opened-PR heading minutes, an issue number given a branch, a PR linked through the issues path, a placeholder pointer, a UTC-relative "yesterday", a line count attributed to the wrong commit) and wording in this entry that its own contents, the transcripts, or the branch's history contradicted.
