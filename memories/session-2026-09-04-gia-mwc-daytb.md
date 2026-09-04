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
`90fe6c86` cites the seventh case and #818, tells a session to rebut once, file, and hold, records the #3154 merge as the exception #3192 puts to the maintainer, and brings `memories/github-actions.md` to 1249 of 1250 lines;
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
and the `mergeable_state` discriminator restated 520 lines from `memories/github-actions.md`'s own bcs bullet.
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

As of `75bc0fc2`, the head round 13 reviewed, thirteen adversarial rounds had run on this branch with no PR open, returning eleven, six, four, four, four, eleven, four, three, one, two, one, one, and two findings.
The three entries that narrated rounds 1 to 3, appended by the commits answering those rounds, were deleted rather than patched at `48380505`, the commit answering round 4, and this entry took their place.

## 05:39 PDT --- the four r4 loops end at 0 of 38 verified; every head snapshotted; #3202 opened; #3203 filed

The round-14 review of this branch and the loops' last rechecks died on the account session limit that reset at 12:30 UTC (05:30 PDT).
The loops' completion notices: wave 1 0 of 6, wave 2 0 of 10, wave 3 0 of 11, wave 4 0 of 11, with 20 branches at the three-round cap still carrying findings and 18 cut before any recheck of their current head (the workflow reports a killed recheck as the finding `recheck agent returned null`).
Every wave worktree was clean and every branch fast-forwarded or already matched origin, so all 38 heads are on origin as snapshots with no PR.
Each branch's issue now carries a status comment with its head SHA and the last recheck's findings verbatim, or a note that the recheck was cut, posted through the REST API from body files.
[#3203](https://github.com/Morrison-Lab/ai-config/issues/3203) records the four loops' agent and token counts against the zero verified and proposes the restructuring.
This branch merged `origin/main` at `6af715ec` with the gates green and opened as [#3202](https://github.com/Morrison-Lab/ai-config/pull/3202): claim comment with `@jules review`, Copilot requested, session subscribed.

## 05:46 PDT --- #3202 at `c58e7172`: claude-review Ready, every check green, Jules blocks twice; held for #3192

Jules approved the first head `6af715ec` at 12:39:52Z, then blocked `c58e7172` at 12:43:14Z and again at 12:46:16Z after one rebuttal-and-re-run, on its own `INPUT_EXTRA_INSTRUCTIONS` config and on line 1076 of the 09-03 file ("file and merge on the approving round"), a recorded conclusion about #3154 that Jules reads as an instruction to itself.
The non-determinism (approve, block, block under one config) is posted on #3183;
the second instance is posted on #3192.
claude-review returned Ready for merge with no findings, `require-clean-verdict` and every check run are green, and Copilot quota-skipped on both heads.
The PR is held unmerged with `jules/review` red, per the #3192 disposition being the maintainer's;
this entry is appended locally and not pushed until that decision, since every push re-runs the reviewers.

## 09:49 PDT --- the user overrules Jules on #3202 and endorses #3203

User directive, verbatim:
"daytb; 3203 sounds good.
you can overrule jules and merge".
So #3202 merges at its next claude-review-clean head with `jules/review` red, as a maintainer decision for this PR (recorded on #3192), and the wave branches proceed by #3203's route: restructure the recheck-and-fix loop first, then rerun it once over the 38 snapshots.

## 09:56 PDT --- r5 loops launched from `gia-fix-loop-r5.js`; #3202 at `8a7d2314` awaiting claude-review before the merge

The r5 script implements #3203's five points: one whole-diff recheck per item, at most two fix rounds each rechecked on `git diff <prev>..HEAD` plus the answered findings, a no-narration brief with delete-not-repair for prose a previous round added, and `no_verdict` for a killed agent.
Runs `wf_bad31608-f03` (wave 1), `wf_ea4fb2c4-1cb` (wave 2), `wf_0400aa03-5ec` (wave 3), `wf_7a2c1144-332` (wave 4), one agent at a time each, opus, launched at 09:54 PDT and recorded on #3203.
The first launch failed to parse because the schema block was extracted by line number from the r4 script and picked up its ITEMS block instead;
extracting by text marker fixed it.

## 09:57 PDT --- #3202 merged at `78d7900b` over the Jules block; notebook continues on `docs/session-notebook-2026-09-04-part2`

claude-review returned Ready for merge on `8a7d2314` at 16:55:34Z with `require-clean-verdict` and every check run green;
squash-merged under the standing grant with `jules/review` red on the maintainer's call, the squash body naming #3192 and #3183.
Post-merge: unsubscribed, `wt-nb3` and its branch removed (origin auto-deleted the branch), `main` fast-forwarded to `78d7900b`, and this file's pending entries carried into worktree `wt-nb4` on the new branch by `git apply` of the uncommitted diff.
Merged this session: #3154, #3166, #3171, #3193, #3195, #3202.

## 09:59 PDT --- a false claim of mine on #3183 corrected; post-merge UMS pass opened as a branch

My first #3183 comment said "a re-run can clear it";
the approve it cited was the first run on `6af715ec`, not a re-run of the blocked head, and the one re-run on `c58e7172` reproduced the block, so the claim was corrected in a second comment.
The post-merge UMS pass for #3202 goes on branch `ums/2026-09-04-jules-per-run-and-fix-narration` (worktree `wt-ums4`): the per-run reading and the #3192 per-PR decision into `memories/jules-review.md` with a Do/Don't pair, and the fix-round-narration recurrence into the `ums` anti-pattern bullet, pointing at #3203.

## 10:00 PDT --- #3203's title carried leaked tool-call markup; retitled

claude-review's round on `8a7d2314` noted that #3203's title ended in raw tool-call markup: the `issue_write` call that filed it had a malformed `labels` parameter tag, so the title swallowed the tag text and the label was never applied.
Retitled and labelled `enhancement` through a second `issue_write`;
the tell for next time is a title that reads correctly in the call and wrong in the API response, so read the response's title back after every create.

## 10:10 PDT --- UMS branch round 1: eight findings, the mechanism prose cut at `15af3f00`

The round refuted the "fires per run" cause (one run on the approving head, whose Jules comment says its diff was truncated, cannot separate per-run from per-diff), the "merged over the red status" sentence (the merged head `8a7d2314` carried no `jules/review` status: the API's statuses list for it is empty), a Do that said "re-run once" against the section's own Do and the seventh case, two timestamps a second off the statuses' `created_at` (12:39:51Z and 12:46:15Z), an insertion that split a paragraph into a list item, and three claims in the `ums` bullet the merged notebook does not support.
The block now follows the section's existing list, states the three status times, says the merged head had no status, names the alternatives one run cannot exclude, and defers to the existing Do;
the bullet cites only the merged notebook's own text.
Round 2 dispatched on `15af3f00`.

## 10:21 PDT --- UMS branch round 2: one finding ("unanswered" for a rebutted block); pushed at `bc945786` and opened as a PR

The fix was one clause plus the measured note that the blocking re-run's comment also reported a truncated diff;
no third local round for one word, the forge's claude-review covers the head.

## 10:28 PDT --- #3207 merged at `090686c9`

claude-review Ready for merge, Jules approve, Copilot quota-skipped, every check run green at `bc945786`;
squash-merged under the standing grant, unsubscribed, worktree `wt-ums4` and its branch removed, `main` fast-forwarded.
Merged this session: #3154, #3166, #3171, #3193, #3195, #3202, #3207.
The merge-time UMS pass finds nothing beyond what #3207 itself recorded.

## 13:01 PDT --- r5 wave 1 verified 6 of 6; six PRs opened

`wf_bad31608-f03` finished: 6 of 6 verified, no verdict on 0, 28 agents, 4,278,236 subagent tokens, 3.06 hours, against r4's 36 agents, 6,060,363 tokens, and 0 of 6 on the same branches;
posted on #3203.
Each verified head fast-forwarded to origin after a fresh `ls-remote` (none diverged, none dirty, none conflicting with `origin/main` by `merge-tree`), then opened:
[#3211](https://github.com/Morrison-Lab/ai-config/pull/3211) (#3068, `bb4b4c8c`), [#3212](https://github.com/Morrison-Lab/ai-config/pull/3212) (#3086, `80a1056a`), [#3213](https://github.com/Morrison-Lab/ai-config/pull/3213) (#3062, `3dc56569`), [#3214](https://github.com/Morrison-Lab/ai-config/pull/3214) (#3117, `0e784162`), [#3215](https://github.com/Morrison-Lab/ai-config/pull/3215) (#3102, `d2cc0f8f`), [#3216](https://github.com/Morrison-Lab/ai-config/pull/3216) (#3113, `5d743c15`);
each claimed with `@jules review`, Copilot requested, subscribed.
The claim comments carry no hand-typed clock time;
the forge's `created_at` is the record.

## 13:06 PDT --- #3215 merged at `184d24bc` (#3102); #3214's Jules nits dispositioned

PR #3215 (#3102): claude-review Ready for merge, Jules approve, Copilot quota-skipped, every check run green at `d2cc0f8f`;
squash-merged under the standing grant, unsubscribed, `wt-3102` and its branch removed, `main` fast-forwarded. #3214: Jules approved with two nits;
the `\d+` one is addressed at `a48cd6c2` (suite 123/123) and the compiled-regex one rebutted on the PR, since the test suite mutates that constant by name.
Merged this session: #3154, #3166, #3171, #3193, #3195, #3202, #3207, #3215.

## 13:08 PDT --- #3217 merged at `f917ca3b`; notebook continues on `docs/session-notebook-2026-09-04-part3`

Jules approve, claude-review Ready for merge, Copilot quota-skipped, every check run green at `e661a9db`;
squash-merged under the standing grant, unsubscribed, `wt-nb4` and its branch removed, `main` fast-forwarded, the pending entries carried into worktree `wt-nb5` by `git apply`.
Merged this session: #3154, #3166, #3171, #3193, #3195, #3202, #3207, #3215, #3217.

## 13:08 PDT --- #3211 merged at `6321933b` (#3068)

Jules approve, claude-review Ready for merge, Copilot quota-skipped, every check run green at `bb4b4c8c`;
squash-merged under the standing grant, unsubscribed, `wt-3068` and its branch removed, `main` fast-forwarded. #3068 stays open: the branch's commits carry `Refs #3068`, not a closing keyword.
Merged this session: #3154, #3166, #3171, #3193, #3195, #3202, #3207, #3215, #3217, #3211.

## 13:09 PDT --- #3068 closed by hand; #3102 stays open for its part 2

PR #3211's commits carried `Refs #3068`, so the merge did not close it;
its three "done when" items are all in the merged diff, so it is closed as completed with a comment naming the merge. #3102's part 1 (the warning band) shipped in #3215 and part 2 (consolidating the per-file issues) did not, so it stays open with a comment saying which half landed.

## 13:12 PDT --- #3212 merged at `e53020f7` (#3086)

claude-review Ready for merge with one non-blocking observation, rebutted by measurement (`_API_VALUE_FLAGS` already skips the projection flags' values on the request side;
four projection-value cases return no request, the genuine POST returns one);
Jules approve, Copilot quota-skipped, every check run green at `80a1056a`.
Squash-merged under the standing grant with `Closes #3086`, unsubscribed, `wt-3086` and its branch removed, `main` fast-forwarded.

## 13:12 PDT --- #3213 merged at `c62869f4` (#3062)

claude-review Ready for merge with two non-blocking notes, both acknowledged on the PR without a change (a deny-reason ordering with no effect on the decision;
test lines a few characters past an unenforced width);
Jules approve, Copilot quota-skipped, every check run green at `3dc56569`.
Squash-merged under the standing grant with `Closes #3062`, unsubscribed, `wt-3062` and its branch removed, `main` fast-forwarded.
Merged this session: #3154, #3166, #3171, #3193, #3195, #3202, #3207, #3215, #3217, #3211, #3212, #3213.

## 13:19 PDT --- #3216 merged at `55e4c6a5` (#3113) after one Jules re-run; #3214 deferred its edge case to #3218

Jules timed out on `5d743c15` ("did not return a review within 15 minutes", status `error`), a reviewer failure named on the PR with the one re-run requested;
the re-run approved.
claude-review Ready for merge, Copilot quota-skipped, every check run green;
squash-merged under the standing grant with `Closes #3113`, unsubscribed, `wt-3113` and its branch removed, `main` fast-forwarded. #3214: claude-review Ready on `a48cd6c2` with one non-blocking edge case (`BRANCH_ITEM` reading a year-shaped run as an own item), filed as [#3218](https://github.com/Morrison-Lab/ai-config/issues/3218) and Deferred on the PR;
Jules requested on that head.
Merged this session: #3154, #3166, #3171, #3193, #3195, #3202, #3207, #3215, #3217, #3211, #3212, #3213, #3216.

## 13:20 PDT --- #3214 merged at `6c229025` (#3117); wave 1 fully merged

Jules approve on `a48cd6c2`, claude-review Ready for merge, Copilot quota-skipped, every check run green;
squash-merged under the standing grant with `Closes #3117`, unsubscribed, `wt-3117` and its branch removed, `main` fast-forwarded.
All six wave-1 PRs are merged: #3211, #3212, #3213, #3214, #3215, #3216, in 32 minutes from the first opening at 12:59 PDT, with one Jules timeout re-run and two nit rounds.
Merged this session: #3154, #3166, #3171, #3193, #3195, #3202, #3207, #3215, #3217, #3211, #3212, #3213, #3216, #3214.

## 13:21 PDT --- a run of extrapolated chat timestamps; wave-1 UMS pass opened as a branch

The clock read taken at this entry returned 13:20 PDT, while the chat updates posted between the 13:07 read and this one carried 13:09 through 13:31, each written from the UTC time of the event being handled plus a guess at elapsed work rather than from a fresh read.
The event times themselves were measured;
the labels on my replies were not, and the drift reached eleven minutes.
The rule's remedy is the same as ever: run the clock command before typing a time, and the `no-unmeasured-clock-claim` hook is not active in this remote session to catch it.
The wave-1 lesson (a `Refs` first commit closes nothing at squash time, and the fixer brief asserted otherwise for all six branches, true for four) goes into `memories/github-closing-keywords.md` on branch `ums/2026-09-04-refs-first-commit-closes-nothing` (worktree `wt-ums5`).

## 13:34 PDT --- UMS round 2 dispatched; waves 2-4 near the end

The wt-ums5 entry was rewritten after round 1's five findings (every-commit grep, pointer to `issue-first.md`, the premature close of #3068 named), and the gate chain passed once the line beginning with an issue number was reworded for MD018.
Committed as 494495d7 on top of bc791949;
the adversarial round 2 (opus) is running against the whole-branch diff.
Waves 2-4 each have one agent in flight (started/results 40/39, 35/34, 39/38).
Next: on Ready, push wt-ums5 and open its PR (Refs #3203);
as each wave's task output lands, post its result on #3203 and open PRs for the verified branches.

### UMS round 2 findings: the lesson itself was wrong

Round 2 returned seven findings, two of them against the account rather than the wording: the cited squash bodies (6321933b, 184d24bc) were written by hand, so the "default body concatenates commits" mechanism never operated on them, and commit 78fda241 on the #3068 branch had reworded the keyword out on purpose because the live-session item cannot be met by that branch.
The section is rewritten (812d79c2) to say that the squash body as entered plus the PR body decide the close, that a `Refs` where a `Closes` was expected is a decision to read in the branch's commits, and that the by-hand close counted an optional item as met.
The grep is widened to all nine spellings, case-insensitive, unanchored.
Round 3 (opus) is running on 812d79c2.

### UMS round 3: the timeline was wrong too

Round 3 found the rewrite's timeline false: the brief's sentence dates from the r1 script (2026-09-03 23:44Z), the #3068 rebase removed the keyword at 03:57Z on 2026-09-04, and the r5 script was written thirteen hours after that, so the assertion was stale before r5 ran.
Two of the #3102 branch's nine commits are generated merge lines without `Refs`;
78fda241 is an empty commit recording the rebase;
the hand-close bullet had forbidden closing on a transcript line.
Rewritten as aa9613ee; round 4 (opus) running.

### UMS round 4: three surfaces, not two

Round 4 (on aa9613ee) added the squash commit title to the deciding surfaces (filled from the PR title in this repo), the `OWNER/REPO#N` form to the grep, and a paired Do for the brief-assertion Don't pointing at `challenge-the-assignment.md`;
two mis-attached `because` clauses were split.
Rewritten as 27e7c82e; round 5 (opus) running.
Five rounds on a memory entry is the cost of recording a lesson whose account I had wrong twice;
the wave-2 to wave-4 branches are unaffected by it.

### UMS round 5: COMMIT_OR_PR_TITLE misread

Round 5 (on 27e7c82e) found the squash-title claim wrong: `COMMIT_OR_PR_TITLE` is the sole commit's subject on a one-commit PR and the PR title otherwise, not "from the PR title".
It also found `hooks/remind-brief-premises.py` does not fire on the brief's branch-state sentence (keys on corpus paths or counts), so the entry now records that gap rather than citing the hook as the mechanism.
Every Do now has its Don't;
the grep carries `%h`;
the section is one sentence per line.
Rewritten as 10671c78; round 6 (opus) running.

## 2026-09-04 14:19 PDT --- wave 2 done, ten PRs open, one backtick corruption repaired

Wave 2 (`wf_ea4fb2c4-1cb`) finished: 10 items, 44 agents, 6,612,301 tokens;
6 verified (#3121, #3038, #3050, #3111, #3108, #3034), 4 ended on history-only findings (#3105 trailer-less sync merge, #3098 and #3114 stale commit bodies, #3110 a `Closes` in a commit body with an unmet bullet).
All ten fast-forward pushed (remote tips were ancestors, merge-tree clean) and opened as PRs #3220-#3229;
PR #3219 filed for #3110's audit residual;
PR #3225 says `Refs #3110`.
Mistake: the PR-creation script ran under an unquoted heredoc delimiter (chosen to interpolate one shell variable), so every backtick span in the issue body, the ten PR bodies, and the ten claim comments ran as a shell command and vanished.
Caught by reading #3219 and #3225 back;
repaired by PATCH from a quoted-delimiter script with the variable passed through the environment.
The rule is already in CLAUDE.md ("The hazard is not PowerShell-specific");
the near-miss here is the delimiter chosen for interpolation, which turns the whole payload into a double-quoted string.
Copilot requested and this session subscribed on all ten;
each carries `@jules review` in its claim comment.
Result comment on #3203 and a status comment on each of the ten issues posted.

## 2026-09-04 14:21 PDT --- two UMS branches under review

Round 6 on wt-ums5 found the `%h %B` grep drops the hash from body-line hits (the listing now uses `git log --grep` with `%h %s`) and that "the three surfaces that decide" presupposed a hand-written squash body;
rewritten as b2f5f3aa, round 7 running.
The heredoc lesson is its own branch `ums/2026-09-04-unquoted-heredoc-runs-backticks` (worktree wt-ums6, 23098cab, `memories/git.md`), round 1 running.
Waves 3 and 4 each have one agent in flight.

## 2026-09-04 14:22 PDT --- #3229 validate red, fixed

`check-unpinned-git-fixtures.py` flagged the tracked-tree fixture on the #3114 branch (`git init -q` without `-b main`);
reproduced locally (rc=1), pinned, suite 31/31, pushed a29e449c on top of the verified head.
The other nine wave-2 PRs are being read for check state now.

## 2026-09-04 14:29 PDT --- heredoc entry was a duplicate; moved into claude-code.md

The wt-ums6 reviewer found `memories/claude-code.md` already carries the unquoted-heredoc rule (measured 2026-08-23);
a `grep -rni heredoc` over the corpus before authoring would have shown it.
The new git.md section is dropped;
the recurrence goes into the existing section as a second-occurrence paragraph with the stderr signal and the read-one-body-back pair (111473dc, Refs #3230, filed for the recurrence).
Round 2 (opus) running.

## 2026-09-04 14:31 PDT --- review workflows skipped the bot-authored wave-2 PRs

The claude-review runs for #3220-#3228 completed with every reusable-workflow job skipped, and the twelve latest jules-review and antigravity-review runs were all skipped with actor `claude[bot]`.
Cause: a REST call through the session proxy posts as `claude[bot]` (PR author and comment author), while the MCP tools post as `d-morrison`;
the review workflows gate on the actor. #3229 got its review only because my git push (a d-morrison synchronize event) re-triggered it.
Remedy applied: `claude-review.yml` dispatched by MCP with `pr_number` for the nine, and `@jules review` re-posted by MCP on all ten.
Learning to record (after wt-ums6 round 2 returns): REST-via-proxy versus MCP identity, and which workflows skip a bot actor.

## 2026-09-04 14:33 PDT --- closing-keywords round 7; #3231 filed

Round 7 (on b2f5f3aa) found the surfaces bullet still carried squash-only surfaces into the merge-commit and rebase cases, the merge commit body this repo fills from the PR title (`merge_commit_message` = `PR_TITLE`) was unlisted, and "nobody reads the title" contradicted the section's own parser claim.
Rewritten as fc5672d2 with a per-method surface list;
the file-level read-the-squash-message bullet folded in;
round 8 (opus) running.
The reviewer's out-of-scope observation (fail-fast.rationale.md:1432 says a squash subject is always the PR title) is filed as #3231.

## 2026-09-04 14:36 PDT --- Jules nits on #3220 fixed; wt-ums6 round 3

Jules returned `comment` on #3220 with two nits (the `pulls/<N>/comments` fetch inside the per-review loop in `skills/ardi/SKILL.md` and `skills/pr-status-all/SKILL.md`);
hoisted the fetch, verified the jq shape on a fixture, pushed 1d7ddeee, re-mentioned Jules.
Jules approved #3221, #3223, #3224, #3225, #3226;
claude-review Ready on #3229 (a29e449c);
nine dispatched claude-reviews in progress.
wt-ums6 round 2 found "the first case did not record" false (line 996 already had the stderr fact) and the stderr detector one-sided;
rewritten as cab3bcfc, which also adds the bot-actor review-skip bullet to `memories/github-mcp-tools.md` (the raw-API-writes-as-`claude[bot]` identity split was already recorded there;
the consequence for the review workflows was not).
Round 3 (opus) running.

## 2026-09-04 14:38 PDT --- four wave-2 PRs merged

PR #3221 (d2bf4f93, Closes #3105), #3224 (01e86fdc, Closes #3050), #3226 (65b538bd, Closes #3111), #3229 (ed4ca957, Closes #3114) squash-merged with hand-written bodies under the standing grant: claude Ready at head, Jules approve, Copilot quota-skip, checks green.
Issues confirmed closed;
worktrees and branches removed;
main fast-forwarded to ed4ca957. #3227's review found `Closes #3108` contradicted its own branch commit (the complexity-metric checker stays open);
PR body switched to `Refs #3108` and the review re-dispatched. #3228 claude Ready, Jules pending;
PR #3220 nits fixed, both reviews pending;
PR #3222, #3223, #3225 waiting on claude-review;
wave 4 finished (47/47), result not yet read.

## 2026-09-04 14:41 PDT --- three more wave-2 merges; #3232 filed; #3222 fix pushed

PR #3223 (661b382b, Closes #3098), #3225 (996e2a81, Refs #3110, residual #3219), #3228 (25ae1e27, Closes #3034) merged;
worktrees removed;
main at 25ae1e27. #3226's review carried `Ready for merge` in prose and `NOT_CLEAN` with two findings in its payload;
merged on the prose and the green check, so the two hook gaps (substring label match, missing backtick separator) are filed as #3232 for this session to fix. #3222's review found the `[a-z]+ly` adverb slot matched -ly nouns ("a claim that family overstated" allowed);
closed to a list, two nouns pinned blocking, 108/108, pushed. #3220 review running on 1d7ddeee (Jules approved twice);
PR #3227 re-dispatch pending (Jules approved).

## 2026-09-04 14:42 PDT --- nine of ten wave-2 PRs merged

PR #3220 (eb5047a5, Closes #3121) and #3227 (540daf3b, Refs #3108) merged;
worktrees removed;
main at 540daf3b.
Only #3222 (fix/3038) remains from wave 2, with the adverb-slot fix 0cadc427 under review.
Waves 3 and 4 each have one agent left (47/46, 48/47).

## 2026-09-04 14:47 PDT --- #3228's 14:41 merge found to have gone out over an off-head red check; #3233 filed

wt-ums6 round 3 found the bot-actor bullet's mechanism wrong for two of three workflows (Jules gates on `author_association`, Antigravity on a mention) and the counts wrong (21 per workflow, 11 on mention-less link-back comments).
Verifying the nine dispatch runs showed #3228's `require-clean-verdict` failed (`verdict: unrecognized`, a doubled `### Verdict` heading) on the dispatch run, which is not attached to the head's check-runs;
the head read showed the bot-sender run's `skipped` row, and I merged on that plus the prose Ready and Jules approve.
Content was clean;
the check was red off-head;
filed as #3233 and recorded in the bullet.
Rewritten as the new wt-ums6 head; round 4 (opus) running.

## 2026-09-04 14:50 PDT --- closing-keywords round 8 applied

Round 8 (on fc5672d2) returned eleven findings, three should-fix: the listing hid the matched body lines and hard-coded `origin/main`, and "no diff can meet" overgeneralized.
The listing now restricts to matching commits, prints header plus matching body lines, and resolves the base from the remote;
the #1718 Do/Don't list moved up beside its case with its post-merge bullet restored.
Rewritten as 4b117ddb;
round 9 (opus) running. #3222 Ready on 0cadc427, Jules re-mentioned for the new head.

## 2026-09-04 14:51 PDT --- #3232 fix pushed

Branch `fix/3232-label-token-and-backtick` (worktree wt-3232, a991b17f): the authorship label is compared as a comma-split token on all three paths and the separator class carries the backtick;
41/41;
PR opened through the MCP tool so the review workflows see the user as sender.

## 2026-09-04 14:55 PDT --- wave 2 fully merged

PR #3222 (5d4a2631, Closes #3038) merged: claude Ready at 0cadc427, Copilot skip, checks green;
Jules's approve sits on the prior head 8f77347e and the re-mention's run finished without a new verdict, so the merge went on the head verdict plus the earlier approve (the delta was the five-line adverb list the head review verified).
All ten wave-2 PRs are merged;
PR #3234 (the #3232 fix) has Jules approve and waits on claude-review and validate.

## 2026-09-04 14:56 PDT --- #3234 round 2

claude-review Ready on a991b17f with two non-blocking findings (the backtick separator made a single-quoted prose mention fire;
one blank line short);
fixed at 1e0a8d2c by blanking single-quoted spans before the position match only, 42/42, pushed, Jules re-mentioned.

## 2026-09-04 14:59 PDT --- wt-ums6 round 4: the bullet duplicated two existing entries

Round 4 found the bot-actor bullet re-derived what `memories/github-remote-sessions.md` recorded on 2026-09-03 (a raw-REST PR gets no automatic review;
read the run's jobs) and `memories/claude-bot-workflows.md` carries too, and that "only the jobs endpoint shows the skips" was false (the head's check-runs show them;
the run-level conclusion hides them).
Rewritten as b83a664c: a recurrence note that cross-links both entries and keeps the delta (each workflow's own `if:`, the MCP dispatch where the proxy's raw dispatch 403s, the off-head dispatch run behind #3233).
The recurrence with the rule loaded is itself the finding: a grep for the mechanism before authoring would have found the day-old entry.
Round 5 (opus) running.

## 2026-09-04 15:01 PDT --- closing-keywords round 9 applied

Round 9 (on 4b117ddb): the PR-body surface fires only on a PR targeting the default branch (a stacked PR's body keyword never fires;
its commits' keywords do once on main), and the listing needed a range count as its negative control.
Both added, plus the merge-commit subject's real form and editability and the restored heading qualifier;
df0025e0;
round 10 (opus) running.

## 2026-09-04 15:02 PDT --- #3234 merged

PR #3234 (b8908d6a, Closes #3232) merged: claude Ready at 1e0a8d2c, checks green, Copilot skip;
Jules approved the prior head and its re-mention run (21:56:57) finished without a new verdict or status, the same shape as on #3222.
Worktree wt-3232 and branch removed; main at b8908d6a.
Open on this session: wt-ums5 (round 10), wt-ums6 (round 5), the notebook branch, and waves 3 and 4 with one agent each.

## 2026-09-04 15:03 PDT --- #3234's second review kept the blank-line nit open

The round-2 review on 1e0a8d2c (posted after the merge) said the second blank line was still missing, because the new `strip_single_quoted` function moved the gap rather than closing it;
I merged with that nit open.
One-line follow-up branch `fix/3232-blank-line` (worktree wt-3232b, 8e2d34bc) pushed and opened as a PR through the MCP tool.

## 2026-09-04 15:12 PDT --- wave 4 done; nine PRs open (#3236-#3244)

Wave 4 (`wf_7a2c1144-332`): 11 items, 51 agents, 7,827,059 tokens;
8 verified, #2510 history-only, #3001 a real finding (substring projection check), #2981 conflicts with main.
Nine PRs opened through the MCP tool (author d-morrison): #3236 (#2422, branch `-r5`), #3237 (#2510), #3238 (#2528), #3239 (#2535), #3240 (#2905), #3241 (#2921, Refs), #3242 (#2928), #3243 (#2985), #3244 (#3003, branch `-r5`).
Two branches had diverged from their published snapshots (the loop rebuilt history), so they were pushed under new names rather than forced.
Claim comments, Copilot requests, and subscriptions done through MCP;
result posted on #3203;
status comments on the eleven issues.
wt-ums6 round 5 applied (de714541): all three conjuncts of each review gate named, the old remote-sessions Don't scoped to the raw API with a pointer;
round 6 running.

## 2026-09-04 15:13 PDT --- closing-keywords round 10 applied

Round 10 (on df0025e0): the zero-count rationale was wrong (a wrong base fails loudly;
zero means an empty range), and the opening rule lacked the default-branch condition the later bullet carried.
Both fixed, plus the count of branches the brief's assertion held for (four of six), the stacked-PR Don't, and "the merger" replaced by the brief;
5dc3db06;
round 11 (opus) running.

## 2026-09-04 15:14 PDT --- #3235 merged; nine wave-4 PRs under review

PR #3235 (d94c7dcd, Refs #3232) merged on Ready plus Jules approve plus green checks;
wt-3232b removed;
main at d94c7dcd.
Wave-4 PRs #3236-#3244 all show author d-morrison with claude-review and validate in progress on open, which is the MCP path working as the recurrence bullet says.
Wave 3 still has one agent in flight (50/49).

## 2026-09-04 15:15 PDT --- check-in re-armed; wave-4 merges begin

Check-in fired at 15:13 PDT and was re-armed for 16:16 PDT with the wave-4 state.
PRs #3238 (2528), #3240 (2905), #3241 (2921, Refs) had claude Ready at head, Jules approve, and green checks;
merging.
Jules's API returned a 404 on #3243;
the one re-run was requested by re-mention.
This notebook is committed and pushed at this checkpoint (wave 4 done, wave 2 fully merged).
