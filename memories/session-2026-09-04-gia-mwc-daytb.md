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
