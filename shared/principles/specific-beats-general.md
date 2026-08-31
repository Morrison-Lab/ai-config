Specific beats general.
When two instructions, policies, configurations,
or design rules apply to the same decision,
the narrower, more specific rule takes precedence over the broader, more general one.
General policies define default baselines for the standard case;
specific instructions express intentional decisions for the concrete case at hand.

This is both an operational principle
(for interpreting user instructions and configuration layers)
and an architectural principle
(for designing code, error handlers, and type contracts).

## The precedence hierarchy

Rules and instructions resolve along a four-tier precedence hierarchy,
from highest priority (most specific) to lowest priority (most general):

1. **Explicit human user instructions for the current session or task**:
   Direct instructions from the human user in an active session
   override repository-wide policies, default workflows, and general agent guidelines.
   When the user specifies a particular workflow, tool, format, or architectural choice,
   follow the specific directive rather than resisting it by citing a general policy.
2. **Narrow, subsystem, or file-level configurations**:
   Rules scoped to a specific directory, subfolder `AGENTS.md`,
   file-level frontmatter, or component-specific configuration
   override repository-wide defaults for files within that scope.
3. **Repository-specific policies**:
   A repository's local `AGENTS.md`, `CONTRIBUTING.md`,
   and root configurations take precedence over universal,
   cross-repository agent baselines.
4. **Universal baselines and global defaults**:
   Global instructions, vendor defaults, and organization-wide baseline templates
   provide the fallback foundation when no narrower rule or specific instruction applies.

| Level | Scope | Example | Precedence |
|---|---|---|---|
| **Tier 1** | Session / User directive | "Use a standard for-loop here instead of purrr" | Highest |
| **Tier 2** | Subsystem / File config | Directory-level `.markdownlint.json` or subfolder `AGENTS.md` | High |
| **Tier 3** | Repository policy | Root `AGENTS.md`, repo `.editorconfig` | Medium |
| **Tier 4** | Universal baseline | Global agent instructions, cross-repo templates | Baseline |

## User directives override general defaults

General repository instructions establish conventions for autonomous operation
when no specific direction has been given.
They are defaults,
not immutable constraints that tie the hands of the user.

When a user gives an explicit command that departs from a general preference:

- **Do not push back with a general policy quote**:
  Quoting a general guideline (such as "we prefer purrr over for-loops" or "our default branch naming is X")
  in response to an explicit user request for an alternative
  mistakes a default guideline for a mandatory prohibition.
- **Do not require the user to re-justify a clear choice**:
  Once the user specifies a concrete requirement or preference for a task,
  treat the preference as settled for that task.
- **Distinguish genuine hazards from policy preferences**:
  Challenge an instruction only when it would cause data loss,
  violate an external safety boundary,
  or break a known invariant,
  not because it differs from a routine habit or stylistic preference.

## Boundaries and safety constraints

The specific-beats-general principle is a resolution rule for conflicting preferences and defaults,
not a license to bypass hard safety boundaries:

- **Hard safety gates remain binding**:
  Non-negotiable security boundaries
  (such as verifying membership before external forge communication,
  preventing credential leaks,
  or guarding against destructive system operations)
  require explicit user authorization that names the specific boundary and action.
  A vague or incidental instruction does not implicitly override a safety gate.
- **Overrides are strictly scoped**:
  A user directive to bypass a convention in one session or file
  applies solely to that session or file.
  It does not license rewriting global defaults
  or ignoring policies in other unrelated worktrees.
- **Document intentional deviations**:
  When a specific implementation deviates from a repository standard by instruction,
  note the rationale in the commit message or PR description
  so future maintainers understand why the general standard was not used.

## Specific beats general in code architecture

The same principle applies to software design,
type systems,
and error handling:

- **Specific types over generic containers**:
  Prefer explicit, typed structs or schemas over unbounded maps, lists, or stringly-typed data.
- **Targeted exception handlers over catch-alls**:
  Catch specific error classes and conditions rather than swallowing all exceptions
  in a bare catch block (see [`fail-fast`](fail-fast.md)).
- **Explicit interface contracts over implicit fallbacks**:
  Define exact argument shapes and return types
  rather than accepting arbitrary variadic inputs with hidden default behavior.
- **Narrower scope over broader scope**:
  Limit variables, helper functions, and state mutations
  to the smallest enclosing lexical scope that needs them.

## Relationship to sibling principles

- [`fail-fast`](fail-fast.md) relies on specificity in error handling:
  specific error classes isolate failures without masking unrelated bugs.
- [`challenge-the-assignment`](../workflow/challenge-the-assignment.md) governs premise checks
  and upstream requirement ambiguities:
  it guides when to clarify underspecified requirements,
  while specific-beats-general ensures that explicit, clarified directions govern execution.
- [`least-flexible-tool`](../coding/least-flexible-tool.md) is the coding counterpart:
  choose the construct with the most specific, constrained capability for the job.
- [`deterministic-tools`](deterministic-tools.md) prioritizes specific, deterministic tools
  over general, non-deterministic model judgment.

## Do / Don't

- **Do:** treat explicit human user instructions as the highest-priority directive in a session.
- **Do:** apply scoped directory or file configurations over repository-wide defaults.
- **Do:** handle specific error classes and edge cases explicitly in code.
- **Do:** limit the effect of a specific user override to the exact scope and task requested.
- **Don't:** cite a general repository convention to refuse or debate an explicit user instruction.
- **Don't:** treat a one-off user override as a mandate to change repository-wide defaults for all sessions.
- **Don't:** allow a general instruction to override a hard safety gate without explicit, verified authorization.
- **Don't:** use generic catch-all handlers or stringly-typed structures where specific types and conditions exist.

## In review

Flag these during code and process review:

- Review responses that push back against an intentional user-specified design choice
  by citing general repository defaults.
- Generic error handlers (`except Exception:`, `tryCatch(..., error = function(e) ...)`)
  that catch all failures instead of targeting specific condition classes.
- Top-level repository configs that inadvertently clobber or disable
  necessary subsystem-level configuration files.
- Ambiguous or overly broad interface contracts
  where specific types and validations should be enforced.
