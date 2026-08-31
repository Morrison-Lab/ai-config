# Prefer optionality over removing functionality

Never remove existing functionality entirely when you can add optionality instead.
When changing default behavior, addressing an edge-case bug, or refactoring a workflow,
do not delete an existing working capability or guard outright if it served a legitimate purpose.
Instead, make the improved behavior the default
and preserve the previous or alternative behavior behind an explicit, documented opt-in parameter,
environment variable, or configuration toggle.

## Why

Wholesale removal of a working code path or capability destroys backwards compatibility
and breaks workflows for downstream consumers who rely on it.
Often, an issue reports a bug caused by a default behavior in a specific scenario
(such as an auto-reviewer skipping merge commits by default).
The instinct to fix the issue by completely deleting the guard or code path
deprives users of a legitimate option they may need in different environments or configurations.

Adding optionality resolves both concerns:
1. The new, correct behavior becomes the default, solving the issue for the standard case.
2. The legacy or specialized capability remains available for users who explicitly opt in.

## The Pattern

When a behavior needs to change:

1. **Make the desired behavior the default.**
   New callers or unconfigured pipelines get the improved, correct behavior without needing manual configuration.
2. **Expose an explicit toggle for the alternative behavior.**
   Provide a named function parameter, CLI flag, or CI/CD environment variable (e.g. `HAC_SKIP_MERGE_COMMITS`, defaulting to `false`).
3. **Document the toggle and its default value.**
   State what the default is, why it was chosen, and how callers can opt into the alternative behavior.
4. **Test both branches.**
   Ensure regression tests cover both the default path and the opt-in configuration path.

## When wholesale removal is legitimate

This rule does not mean dead or dangerous code must be kept forever.
Wholesale deletion is legitimate when:

- **The code is provably dead or unreachable** and serves no legitimate caller or use case.
- **The code represents a security vulnerability** that cannot safely be offered even as an option.
- **The feature has completed a formal deprecation lifecycle** with advance notice and migration paths.

Outside those exceptions, prefer optionality over outright removal.

## Do / Don't

- **Do:** make the improved behavior the default while preserving the previous capability behind an opt-in toggle.
- **Do:** document the configuration toggle and its default value clearly in templates, manuals, or docstrings.
- **Do:** test both the default behavior and the opt-in behavior in automated test suites.
- **Don't:** delete a working feature, guard, or workflow step to fix a default behavior issue when it could be preserved as a configuration option.
- **Don't:** break backwards compatibility for existing consumers when an opt-in parameter achieves the fix safely.

## In review

Flag diffs that completely delete working logic, guards, or features to fix an issue:
- Ask whether the previous behavior has valid use cases that should be preserved under an opt-in configuration parameter.
- Require both default and opt-in paths to be tested and documented.
