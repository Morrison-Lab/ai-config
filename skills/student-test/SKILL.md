---
name: student-test
description: "Test assessments with a simulated student."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Agent
---

# student-test --- can a student answer it from the wording alone?

Give each assessment to a "student" agent that has no access to the solutions, then have a separate grader compare its answers with the key.
Every wrong or hedged answer is either a student error, a wording problem (ambiguous, or missing information), or a key error.
The deliverable is a per-item report with a suggested rewording for each wording problem.

**Origin:** Ezra, 2026-10-12, for the DATA 571 repositories (`Morrison-Lab/mlg` assessments, `Morrison-Lab/lds` notes).
Ezra made it standing practice the same day: re-run it on every changed homework or exam.
It applies equally to the CSCI 481 assessments in `Morrison-Lab/dlg`, which copy `mlg`'s layout.

## When this fires

- A PR adds or changes a homework, exam, quiz or lab, or a question those include.
- A request to "test every hw and exam for clarity", or to see whether a student could get the key's answers.
- Not for grading real student work;
  that is [`grade-work`](../grade-work/SKILL.md), and student records stay out of this skill entirely.

## Procedure

1. **Render the student copy, and change nothing a student sees.**
   In `mlg` or `dlg`: `quarto render <item>.qmd --to markdown` with the default `assign` profile, then `--profile solution` for the key (grader only).
   Not `--to gfm`: GitHub-flavoured Markdown has no lettered lists, so it numbers parts a to e as 1 to 5,
   and a question that refers to "part c" then reads as broken to the student (dlg#2, 2026-10-23).
   - **Do:** render to `markdown`, and delete only the leading block of raw TeX macro definitions, which no student sees.
   - **Don't:** hand the student a `gfm` render of an item with lettered parts.

   Do not post-process the render beyond that.
   A link-stripping regex run on the pilot also deleted `[...]` inside inline math, which made the exam look defective and produced a false finding.
2. **Isolate the student.**
   Put the student text, any data file the item gives students, and for an exam its permitted note sheet, in a fresh scratch directory.
   The student's prompt holds only that and the rules.
   It gets no repository clone, no project files, no memory, and is told not to search for or read this course's solutions, other repositories or other files.
   Subagent tools cannot be technically blocked, so ask the student to report its tool use and check the transcript's tool-use count.
3. **Give the tools the item allows, no more.**

   | Item | Student may |
   | --- | --- |
   | Homework | run code, use the internet, read the course notes site |
   | Exam or quiz | only what its own instructions allow: a note sheet, a calculator, nothing |

   If the instructions allow nothing, the student gets the paper and no tools;
   do its arithmetic by hand and say so in the report.
   If they allow a calculator and the student has none, record that the test is harder than the real exam on arithmetic.
   Record the tools each item allowed in the report.
4. **The student flags every doubt.**
   Where a question is ambiguous or seems to lack information it states the reading it chose, carries on, and ends with a "Confusions" list.
   It asks nobody.
5. **A separate grader agent grades.**
   It reads the student copy, the student's answers and the key.
   It scores each part, re-runs any computation it relies on, and classifies every discrepancy and confusion as exactly one of: **STUDENT_ERROR** (the wording was clear), **AMBIGUOUS_WORDING**, **MISSING_INFORMATION**, **SOLUTION_ERROR**, **ACCEPTABLE_ALTERNATIVE**.
   Each non-student item carries a concrete suggested rewording or key fix.
   It also flags guessable questions, over-hinted ones, heavy arithmetic, time fit, and duplicated or mislabeled key text.
6. **Verify each finding before acting.**
   A grader can report an artifact of the test itself.
   Check the real student render against anything about formatting, and re-derive anything called a key error.
7. **Write the report** to the repository's report folder (`reports/student-test/<date>-<topic>/` in the assessment repository, `mlg` or `dlg`): a README table of item, score and tools allowed, plus the grader reports and the student answers.
   Open it as a PR.
   Fixing the assessment wording is a separate PR per item.
8. **Pilot first when new.**
   Run one homework and one exam, report the method, and then run the rest unless the pilot shows the method is broken.

## Model and cost

Run the students and graders on Sonnet-tier models;
one pair per item cost roughly 90k to 120k tokens each in the pilot.
Never use Fable (see [`no-fable-subagents`](../../shared/workflow/no-fable-subagents.md)).

## Relationship to other skills

- [`grade-work`](../grade-work/SKILL.md) grades real submissions against a key;
  this skill simulates the submission to test the question.
- [`plan-review-session`](../plan-review-session/SKILL.md) turns real student errors into lessons.
- [`fact-check-prose`](../fact-check-prose/SKILL.md) checks claims in prose;
  this checks whether the question can be answered as written.

## Anti-patterns

- **Don't** include solutions, student records, `Student_Work` folders or a course instructor's final exam anywhere in a student's context or in a report.
- **Don't** put reports or keys in a student-facing repository: reports quote answers, so `mlg` reports stay in `mlg` (never `lds`) and `dlg` reports stay in `dlg` (never `dds`).
- **Don't** trust a full score as proof of clarity: a lucky guess or a recited answer also scores full marks, so read the grader's guessable-question list.
- **Don't** post-process the student render beyond deleting its leading block of raw TeX macro definitions.
