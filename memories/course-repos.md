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
