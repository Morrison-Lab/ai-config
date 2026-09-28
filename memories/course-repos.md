# Course repositories: notes, evaluation material, and what moves between them

Morrison-Lab courses split into a student-facing **notes** repository
(`Morrison-Lab/mln`, `Morrison-Lab/rme`)
and a private **evaluation-material** repository holding assignments, quizzes, exams and their answers
(`Morrison-Lab/mlg`, `Morrison-Lab/epi204`).
Each repo's own `CLAUDE.md` has the details; these rules hold across all of them.
The names above were checked against the account's repository listing on 2026-09-28;
older entries in this corpus that say `ucdavis/epi204` or `d-morrison/rme` predate the moves.

## None of these repos is a record of past classes

Materials from earlier offerings are kept for reference while they are useful, not as an archive.
Revise them freely, port what is worth keeping into source files (`.qmd` question-bank fragments and assessment documents),
and delete a PDF or other container once everything in it lives in source.
A README saying a file is "as administered" describes where it came from;
it is not a reason to leave it untouched.

- **Do:** fix a question by editing or replacing it, and delete the old PDF once its content is ported.
- **Don't:** treat an old offering's files as a record to preserve, or build around them rather than port them.

(Ezra, 2026-09-28: "mlg is not a record of the past";
"none of these repos is purposely a record of past classes;
we only store past materials for reference, while useful";
"the pdfs can be deleted if all their content has been ported to qmd or other source files".)

## Exercises may migrate into the notes, but only on purpose

The notes must not answer a graded item: a worked solution in the notes that answers a question in the evaluation repo,
even with different numbers, is a leak.
That rule is about **accidental** exposure.
It does not freeze the evaluation repo's contents.

An exercise may move from any evaluation-material repo into the notes, with its solution,
when it serves students better as a lecture exercise than held back for assessment.
What makes a move legitimate is that it is **intentional**:

- someone decided it, and the PR that moves it says so;
- the item is removed from the evaluation repo's question bank and from every assessment that includes it,
  so it stops being graded and no graded question has its answer in the notes.

A notes change that happens to answer a graded question is still a leak, however useful the content,
until someone makes that decision and retires the graded item.

- **Do:** when an exercise is better in the notes, move it deliberately: say so in the PR, and remove it from the evaluation repo and its assessments in the same change or a linked one.
- **Do:** keep checking new notes content against the evaluation repo for accidental answers.
- **Don't:** leave a graded item in use once the notes carry its solution.
- **Don't:** read "exercises may migrate" as licence for notes content that answers graded work by accident.

(Ezra, 2026-09-28: "it's ok for exercises to migrate from mlg to the lecture-notes repos, if we think they would be better to include in the notes than reserve them for evaluation materials";
"and not just from mlg; from any evaluation-material repo (e.g. epi204)";
"we just need to be intentional about what we migrate, and not do it accidentally".)

## The leak check covers what we grade, not what another class assigned

What goes in the notes and what is held back for assessment is our decision.
The leak check protects the items we grade --- this course's current and planned homework, quizzes and exams --- from being answered by accident.
A third party's assessment material kept in an evaluation repo for reference,
such as the Stanford CS229 problem sets and keys in `mlg`,
is not a constraint on the notes: that another class assigned a problem does not stop us teaching it.
CS229's keys in particular have been public online for years,
so there is nothing about them left to protect.

On 2026-09-28 a session recommending a lecture exercise reported that it had checked the exercise against mlg's text and PDFs, CS229's problem sets included,
as if a match there would have ruled it out.
The user: "it's up to us to decide what content to put in the lecture notes versus saving for exams/hw/etc;
what another class did doesn't matter.
just don't leak solutions ACCIDENTALLY.";
"the stanford cs229 materials are particularly useless to protect, since they're available online".

- **Do:** check new notes content against the items this course grades, and decide what to hold back on the merits.
- **Don't:** treat another class's problem sets or keys as ruling content out of the notes, or present such a check as a gate.

## Where the book PDFs for a course's reading shelf come from

The user keeps a collection of textbook PDFs in `G:\My Drive\Texts 2` on their Windows machine (the XPS).
A cloud session cannot read that folder, but the user can open a Remote Control session there on request.
Copying a book from it into a course's reading-shelf repository (`Morrison-Lab/mlr` for the machine learning course) is pre-authorized, as needed.
The user, 2026-09-28: "G:\My Drive\Texts 2 has a collection of book pdfs;
you can copy them to mlr as needed".
Only the reading-shelf repo, never the notes or graded-material repos, since the books are copyrighted.

- **Do:** ask the user for the Remote Control session when a task needs a book's text, and copy just the books the task needs into the reading-shelf repo.
- **Don't:** copy a book into the notes repo or the graded-material repo.

## List a cloud-sync mount's top level before searching it

`G:\My Drive\Texts 2` is a Google Drive for desktop streaming mount holding 1700+ book folders, not a local disk.
A recursive `find` or `grep -r` over it has to fault in and stream every folder it touches, and running one twice with 300-400 second timeouts made the user's machine lag badly enough that their Remote Control client showed "Can't reach your computer."

The fix is not a shorter search.
It is a narrower one: list the top-level index directory first (this library keeps a `Texts_by_Title` folder for exactly this purpose) and descend only into the specific folders a task actually needs.

- **Do:** on a network, cloud-sync, or streaming mount (Google Drive, OneDrive, SMB), or any large tree, list the top level first --- a single index directory such as a by-title folder --- and descend only into the folders you have chosen.
- **Don't:** run a recursive `find`/`grep -r`/glob `**` over such a mount.
  A long timeout does not make that acceptable;
  it only makes the damage last longer.

(The Do side is the user's, 2026-09-28, after two timed-out recursive searches;
the Don't side is inferred.
The user's words: "let's not crawl all of my drive;
just get the folder names from texts_by_title and look through them."
A follow-up issue for a possible guard --- warning on a recursive `find`/`grep -r` whose path is under `G:\`, `/g/My Drive`, or `OneDrive` --- is tracked in [ai-config#4072](https://github.com/Morrison-Lab/ai-config/issues/4072);
see [`grep-is-not-coverage.md`](../shared/workflow/grep-is-not-coverage.md)'s "A `timeout`-killed search's output is partial, not complete" section for the companion mistake this same incident produced, where the truncated output of the first (pre-fix) recursive search was read as a complete absence.)

## File an access-request issue for a text genuinely not in the library

When a task needs a book, paper, or other reference that is not in `G:\My Drive\Texts 2` (confirmed by a real, non-truncated search --- see the section above and [`grep-is-not-coverage.md`](../shared/workflow/grep-is-not-coverage.md)'s timeout section before concluding absence), file an access-request issue in the reading-shelf repo (`Morrison-Lab/mlr`) rather than only mentioning the gap in chat.

- **Do:** file one issue per reference, carrying the full citation, its DOI when it has one, where it was searched and when, and the likely access route (a library subscription, a publisher purchase, an author copy) --- labelled `ai-authored` and `model:<id>` per [`label-agent-filed-issues`](../shared/workflow/label-agent-filed-issues.md).
- **Don't:** mention the missing reference only in chat, or silently drop it from the task instead of filing it.

(The Do side is the user's, 2026-09-28, verbatim: "whenever there are texts we should get access to, file issues (or other refs)";
the Don't side is inferred.
Filed as [Morrison-Lab/mlr#10](https://github.com/Morrison-Lab/mlr/issues/10), [#11](https://github.com/Morrison-Lab/mlr/issues/11), and [#12](https://github.com/Morrison-Lab/mlr/issues/12), 2026-09-28, for Robert & Casella's *Monte Carlo Statistical Methods*, Gelman & Rubin (1992), and Brooks & Gelman (1998) respectively.
Issue #10 was later found to rest on a truncated search --- the book is present under a search that was not cut short --- and was corrected rather than left standing;
see the timeout section linked above.)
