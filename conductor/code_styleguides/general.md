# General Code Style Principles

This document outlines general coding principles that apply across all languages
and frameworks used in this project.

## Readability

-   Code should be easy to read and understand by humans.
-   Avoid overly clever or obscure constructs.

## Consistency

-   Follow existing patterns in the codebase.
-   Maintain consistent formatting, naming, and structure.

## Simplicity

-   Prefer simple solutions over complex ones.
-   Break down complex problems into smaller, manageable parts.

## Maintainability

-   Write code that is easy to modify and extend.
-   Minimize dependencies and coupling.

## Documentation

-   Document *why* something is done, not just *what*.
-   Keep documentation up-to-date with code changes.

## Lab Manual & Multi-Harness Integration (UCD-SERG)

- **Source Reference**: [UCD-SERG Lab Manual](https://github.com/UCD-SERG/lab-manual)
- **Semantic Line Breaks (SemBr)**: Break markdown lines at semantic sentence boundaries and clause breaks for clear, mergeable git diffs.
- **ASCII Compatibility**: Shared documentation fragments under `shared/` must remain pure ASCII (e.g., `---` for em-dashes, straight quotes) to pass lab manual submodule validation.
- **Agent Attribution**: Forge comments must include explicit agent disclosure markers.
- **No Empty Promises**: All behavioral guidelines must be paired with mechanical tests, linters, or hooks.
