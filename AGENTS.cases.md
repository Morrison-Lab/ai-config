# Case records: AGENTS.md

Worked-example case records and authentic incident directives for the rules in [`AGENTS.md`](AGENTS.md), moved here to keep them out of the auto-loaded context while preserving historical context and provenance.
Each heading names the section and the rule the record supports.

The wording is unchanged from `AGENTS.md`, word for word, conforming to ASCII punctuation (`---` for em-dashes) and semantic line breaks (one sentence per line).

## Commit, push, and PR any potentially-reusable work you produce --- Incidental math and code

(Directive from the user, 2026-09-08, in three parts.
Potentially-reusable code should be committed, pushed and PRed into at least one repo, creating one if none fits.
The rule covers code written incidentally, not only work that was requested.
And it applies to math and prose, not just code.
It came after two R scripts and a density derivation backing
[UCD-SERG/serocalculator#687](https://github.com/UCD-SERG/serocalculator/issues/687)
sat in a session scratchpad while that issue was already filed and being acted on by another session.
Both are now committed, so this entry is not a rule written in place of following it:
the script and its derivation in
[UCD-SERG/serocalculator#688](https://github.com/UCD-SERG/serocalculator/pull/688),
and the anchor-resolving instrument alongside this rule.)

## Interpret instructions broadly and maximize safe progress --- Do not narrow scope unnecessarily

(Directive from the user, 2026-09-28:
"cai: don't narrow scope unnecessarily".
The user had said exercises may move from evaluation material into the notes
and only accidental leaks matter;
a session then still checked a proposed lecture exercise against another class's public problem sets
as if a match would rule it out.
This is not the surface axis in [`challenge-the-assignment.cases.md`](shared/workflow/challenge-the-assignment.cases.md),
which is about carrying an instruction to a different context;
this is about shrinking an instruction inside the context it was given for.)

## Always give recommendations with questions --- Decision points in status lists

(User correction, 2026-09-28, on Morrison-Lab/mln#186:
"haven't I told you to always provide a recommendation when you ask me for input?")

## Search the tracker and AGENTS.md before building or denying a policy --- Open issues define scope

(Incident on #4085 duplicating already-open #4039:
implementing a fresh capability or grant request without searching open issues and PRs risks duplicating existing work.
An open issue or PR often contains requirements, allowlists, or prior user directives that define the necessary scope.)

## Proactively suggest better alternatives to proposed approaches --- Standing openness to suggestions

(User directive, Issue #4095:
"if there's another way to accomplish the same goal, I'm always open to suggestions".)

## Use real-world examples for general practice --- Concrete before-and-after examples

(User directive, Issue #4093:
"when we do or see something that would be a good example for general practice, use it".)

## Default to action without asking --- Non-destructive standing grant

(User directive, 2026-08-23:
"always yes".)

(User directive, 2026-10-06, ai-config#4337:
"you should have attached the macros repo without waiting for me to tell you to".
A session loading `Morrison-Lab/macros` in `Morrison-Lab/lds` had found an upstream defect, written that filing it "would need add_repo", and waited.
After attaching, it filed [macros#106](https://github.com/Morrison-Lab/macros/pull/106), [#107](https://github.com/Morrison-Lab/macros/issues/107) and [#108](https://github.com/Morrison-Lab/macros/issues/108) the same evening.)

(User directive, 2026-10-09, via `cai` in the `bcs` project:
"you can always attach other repos whenever it's helpful".
This widened the grant from repositories the work needs to any repository that would help.)

## Strict Merge Control Policy --- Infrastructure PRs standing MWC grant

(User directives, 2026-09-28:
"infra PRs are always mwc";
"'infra' includes recording instructions and notes for ai and human developers";
"fine with that definition of infra for now";
"let's say that everything in gha is infra",
"so is ai-config",
"that's why we have a standing mwc for ai-config".)
