# grade-work

Grade a folder of submissions against a solution key and distill the results into a **ranked catalog of common error types** — the raw material for a review session, regrade, or answer-key improvement.

**Origin:** built from grading an exam where PDF submissions were compared against the course solution and the errors became a new review chapter in the course book.

## When to use

- A directory of student work (PDF scans, `.docx`, `.qmd`, images) plus a solution to grade against.
- The goal is *diagnostic* — what went wrong and how often — not just a score.

## Core principles

1.  **Confirm the exam/assignment version first.** Solution files drift. The solution on disk may be an *older variant* than the one students actually sat. Before trusting it, open one blank/clean submission (or the question sheet) and confirm the data, tables, covariate names, and number of subparts match the solution. A mismatch happens when the solution on disk is for one version of the dataset but students sat a different version, with different numbers or an extra subpart — grading against the wrong key would be wrong on every affected item.

2.  **Verify the key’s numbers yourself.** Recompute the solution’s numeric answers independently (a quick `python3`/`Rscript` block). Don’t assume the printed key is arithmetically correct; you need ground-truth values to grade against.

3.  **Anonymize in any shared output.** Describe error *patterns*, never individual students, in anything that leaves the grading context (review chapters, PRs, commits, issues). Per-student notes are fine for the instructor’s eyes only — keep them out of committed artifacts.

## Procedure

1.  **Locate inputs.**

    - List the submissions directory. Note any non-submissions (blank template, instructor test upload, `LATE`/partial files) and handle them separately.
    - Find the solution (search the course repo for the assignment’s `.md` / `.qmd` / `.pdf`). Read it fully.

2.  **Pin down the canonical answers.** Build a compact, per-subpart answer key: the correct value/derivation for each question, plus the *method* expected. Recompute every numeric answer to confirm it. Keep this key in your context — you’ll hand it to the grading agents so they all grade against the same ground truth.

3.  **Fan out the reading.** PDFs (especially handwritten/scanned) are context-heavy, so delegate. Spawn parallel `Agent` (general-purpose) calls, each handling ~3 submissions. Give every agent:

    - the full answer key and expected methods (inline in the prompt),
    - the exact file paths to read (they use `Read` on each PDF),
    - an instruction to report, **per submission and per subpart**, what was right and *specifically* what was wrong (concrete error types, not just “partially correct”), then a short per-submission theme summary. Send all the agent calls in one message so they run concurrently.

4.  **Aggregate into ranked error types.** Collect the agent reports and group errors into categories. Rank by **frequency × consequence** (an error that silently flips a conclusion outranks a cosmetic slip). For each category record: a clear name, how many submissions hit it, the correct approach, and a representative (anonymized) description of the wrong approach.

5.  **Deliver.** Produce:

    - a ranked common-errors table (category, count, the fix), and
    - optionally a per-student breakdown for the instructor (kept local / unshared). If the user wants teaching material from this, hand off to **plan-review-session**.

## Tips

- Round-trip the data scale: a common error class is scale-confusion (e.g. a raw vs log-transformed value, or a CI computed on one scale and reported on another). When you see a numeric answer, check *what scale* it’s on before calling it right or wrong.
- A “right answer, wrong method” still belongs in the catalog — it predicts failures on the next problem.
- Note submission-logistics problems (missing pages, wrong file, unrelated page) separately from content errors; they need a different follow-up.

## Orchestration

Grading is verification-bearing and decomposes cleanly — one independent target per submission, or per grading dimension on one large item — and it touches no shared CI runners, so it fans out safely. Consult `shared/workflow/when-to-orchestrate.md`. At ~4+ items or dimensions, run a Workflow: one grader agent per target, then a synthesis stage that reconciles the scores; use a panel (several independent graders per item) when the verdict carries weight. Launch directly when an opt-in signal is present; otherwise propose with a cost estimate first.

## Related

- **plan-review-session** — turns the ranked error catalog into a review chapter/handout and opens a PR.

Back to top
