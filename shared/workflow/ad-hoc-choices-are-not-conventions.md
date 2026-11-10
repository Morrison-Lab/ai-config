An ad-hoc choice made once, for local convenience, is not a convention.
Do not copy it, standardize it, or record it as a rule unless Ezra decided it or a sourced rule backs it.
This covers every repository and every kind of choice: a naming pattern, a file layout, a wording, a workflow step.

Ezra, 2026-11-10: "learn the broader rule about random decisions not turning into habits".

## The case

The `_py` and `_r` suffixes first appeared in lds commit a39e9c32 (2026-09-28) as a local choice: an R chunk holding results read from Python.
Later chunks copied the pattern, [lds#2175](https://github.com/Morrison-Lab/lds/issues/2175) found "no decision behind the differences" and asked for uniformity, [lds#2176](https://github.com/Morrison-Lab/lds/pull/2176) made the suffixes uniform, and a project-memory line then recorded them as a rule.
About 770 names across about 140 files carried the pattern when Ezra asked "why are you still putting `_py` and `_R` suffixes on objects in code".
No step was a decision.
Each step treated the previous one as one.

## The rule

Before you reuse, standardize or record a pattern, find where it came from.
A source is one of:

- an Ezra quote in the issue, thread or memory entry that names the pattern;
- a rule in an instruction file (a repository's `CLAUDE.md` or style guide, psc, psw, this repository);
- an issue or PR that records the decision.

Existing code is not a source.
Its existence shows what someone typed once, not what Ezra wants.

- **Do:** when a pattern has no source, ask Ezra once, with a recommendation, and record the answer with his quote.
- **Do:** when you must choose without asking, write the choice down as local to that file and do not repeat it elsewhere.
- **Do:** when a review or an issue (such as lds#2175) reports inconsistency, ask whether the pattern is wanted before making it uniform.
- **Don't:** copy a name, layout or wording from a neighbouring file because it is there.
- **Don't:** write a rule line into memory or an instruction file without his quote or a source link.

## Style is decided in psc and psw

Ezra, 2026-11-10: "imitating existing code style is not a good justification for style choices;
all style decisions must be made explicitly in psc or psw".
Code style comes from [psc](https://morrison-lab.github.io/psc/) and writing style from [psw](https://morrison-lab.github.io/psw/), or from a repository instruction that cites them.
It never comes from the code or prose around the edit.
A style choice that neither guide states is a question for Ezra, raised as an issue on psc (code) or psw (writing) with a recommendation.
It is not copied from a neighbouring file.

- **Do:** when psc or psw is silent on a style choice, file an issue there asking Ezra, and follow his answer once it is in the guide.
- **Don't:** justify a style choice by "the surrounding code or text does it this way".

## Writer and reviewer instructions

Writers follow the rule above.
Reviewers flag any naming, structure, wording or workflow pattern in a diff that no instruction supports, and ask where it came from.
Reviewers also flag code style that psc does not support and writing style that psw does not support, even when it matches the surrounding file.
A pattern repeated across a diff without a source is a finding, however consistent it is.

## Why prose, and what enforces it

Whether a choice was ad-hoc cannot be decided from text, so no hook or check can detect the general case.
The decidable cases get deny-form checks instead: `lms::base_subset_linter()` for base `[]` subsetting ([psc#112](https://github.com/Morrison-Lab/psc/pull/112)), and a diff-scoped check for language-suffixed names ([lds#2283](https://github.com/Morrison-Lab/lds/issues/2283)).
Add a check each time a recurring pattern turns out to be decidable.

Tracking issue: [ai-config#5278](https://github.com/Morrison-Lab/ai-config/issues/5278).
