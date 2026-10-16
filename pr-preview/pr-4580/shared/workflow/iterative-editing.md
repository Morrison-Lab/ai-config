Writing agents do not need to enforce all style guidelines on first draft.
They should work iteratively:
write a substantively-correct but stylistically loose first draft,
and then hand off to editor agents for revisions.

## Two-pass drafting and editing

Drafting and editing require different modes of thought.
Attempting to enforce every stylistic constraint during initial drafting
slows progress, distracts from substantive correctness,
and often leads to incomplete implementations.

Instead, separate authoring into two iterative stages:

1. **First draft (authoring):**
   Focus on substantive correctness, completeness, sound reasoning,
   and working code that passes tests.
   Style can be loose on the first pass as long as logic and facts are sound.
2. **Revisions (editing):**
   Hand off the drafted artifact to an editor agent to polish style
   and enforce style-guide compliance.

## Dedicated editor agents

Two dedicated editor agents handle revisions:

- **Prose editor agent ([`prose-editor`](../../.claude/agents/prose-editor.md)):**
  Improves prose style and enforces compliance with a style guide
  ([Principles of Scientific Writing (PSW)](https://github.com/Morrison-Lab/psw/) by default).
  Tightens sentence structure, limits subordinate clauses, removes filler and jargon,
  enforces active voice, and formats semantic line breaks while preserving substantive facts.
- **Code editor agent ([`code-editor`](../../.claude/agents/code-editor.md)):**
  Improves code style and enforces compliance with a style guide
  ([SERG Lab Manual](https://github.com/UCD-SERG/lab-manual) by default).
  Decomposes functions, flattens nesting, eliminates duplication,
  improves naming, and runs project formatters and linters while keeping tests green.
