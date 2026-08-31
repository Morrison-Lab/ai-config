Think outside the box.
Do not make unnecessary assumptions about structural limitations;
consider which limitations are real and which are artificial.

When designing, implementing, or debugging a system, it is easy to accept
assumed constraints that do not actually exist.
An artificial limitation leads to convoluted workarounds, premature
surrenders, or fragile adaptations designed to survive inside an unnecessary
box.
Thinking outside the box is the discipline of inspecting every perceived
constraint to determine whether it is an immutable property of the problem
or merely an inherited convention, an unexamined default, or an artifact
of how things happen to be structured today.

## Hard constraints vs artificial boundaries

Distinguish between two fundamentally different classes of limitation:

- **Hard constraints**:
  Inviolable bounds imposed by mathematics, physical laws, operating system
  boundaries, verified external API protocols, cryptographic guarantees,
  or explicit security and permission policies.
  A hard constraint cannot be engineered away from within the current scope;
  it must be accommodated and respected.
- **Artificial boundaries**:
  Assumptions, defaults, conventions, and habits inherited from earlier
  iterations, adjacent tools, or initial mental models.
  These include assuming an upstream interface cannot be updated,
  assuming a multi-step serial workflow is mandatory when a direct
  invocation works, assuming a default configuration parameter is fixed,
  or assuming a problem must be solved exclusively on one side of a boundary
  when changing the other side eliminates the problem entirely.

## Why artificial limitations go unexamined

Artificial constraints persist because they rarely present themselves as
decisions.
They arrive disguised as the environment itself:

1. **Inherited architecture mistaken for permanent reality.**
   Codebases grow by accretion.
   A temporary structure created for an earlier milestone or a narrower use
   case becomes the invisible boundary within which all subsequent features are
   forced to fit.
2. **Conflating the objective with a previous solution's framing.**
   When assigned a task, the prompt or ticket often frames the problem in
   terms of a specific mechanism (for example, "how do we parse output X from
   tool Y?").
   Focusing solely on the mechanism accepts the premise that tool Y must
   produce output X in that format, ignoring whether tool Y can be configured
   or replaced to emit structured data directly.
3. **Unverified folklore and speculative impossibilities.**
   An assumption that "platform A cannot do B" or "tool C does not support D"
   is often repeated without verification.
   Toolchains and platforms evolve rapidly; what was impossible in an older
   version may now be a standard option.
4. **Self-imposed local scoping.**
   Treating the current file, module, or repository layer as a sealed box
   often leads to complex defensive wrappers when a one-line adjustment in
   the caller or parent schema would solve the root issue cleanly.

## Diagnostic questions to test perceived constraints

Before accepting a constraint that makes a design awkward or complex,
ask:

1. **What enforces this constraint?**
   Is it enforced by the runtime, a compiler, an external service contract,
   or an explicit policy?
   Or is it enforced only by how existing helper functions happen to be written?
2. **Has the limitation been empirically verified?**
   Did you test the boundary directly with a minimal reproduction or
   read the underlying source, or are you relying on intuition, stale docs,
   or third-party speculation?
3. **Is the constraint part of the problem or part of the proposed solution?**
   Strip away the proposed implementation and restate the user's root goal.
   Does the constraint belong to the goal itself, or only to one way of
   achieving it?
4. **What breaks if the boundary is moved or removed?**
   If you alter the upstream contract, modify the schema, or invoke the
   lower-level primitive directly, what concrete failure occurs?
   If the answer is "nothing, except we have not done it that way before,"
   the constraint is artificial.
5. **Can the problem be dissolved rather than solved?**
   Instead of writing complex logic to handle edge cases created by an
   awkward data shape, can you change the producer to never emit that
   awkward shape in the first place?

## Reframing patterns: moving beyond artificial boxes

- **Change the producer instead of compensating in the consumer.**
  When consumer logic becomes bogged down with sanitization, parsing hacks,
  or heuristic guessing, move outside the consumer box and adjust the
  producer to supply clean, typed, or structured inputs.
- **Probe the actual API and runtime surface.**
  Do not assume an API endpoint, CLI tool, or library cannot perform an
  operation.
  Check the latest documentation, inspect available flags and parameters,
  and run exploratory probes to verify actual capabilities.
- **Question artificial serial workflows.**
  When tasks are performed in sequence out of habit, evaluate whether they
  can be executed in parallel, batched, or collapsed into a single
  deterministic operation.
- **Eliminate intermediate representations.**
  If an architecture transforms data through multiple lossy or redundant
  intermediate formats, question why those intermediate layers exist.
  Direct transformation often eliminates an entire class of synchronization
  and serialization bugs.
- **Restructure the workflow for structural efficiency.**
  Address high token costs, excessive round-trips, or sprawling manual
  steps by changing the workflow's shape rather than merely trimming
  individual steps
  (see [`restructure-for-efficiency`](../workflow/restructure-for-efficiency.md)).

## The boundary: what is not an artificial constraint

Thinking outside the box is an instrument for discovering simpler,
more direct paths by discarding unneeded assumptions.
It is never a license to bypass real, deliberate boundaries:

- **Security, permission, and authorization boundaries are real.**
  Membership checks, access controls, repository boundaries, and permission
  gates exist to protect systems and users.
  Never treat a security policy or authorization gate as an "artificial
  limitation" to be circumvented.
- **Verification and correctness requirements are real.**
  Verification checks, test suites, deterministic linters, and adversarial
  reviews are non-negotiable standards of quality.
  Thinking outside the box means finding better ways to satisfy and automate
  them, not skipping them to move faster.
- **KISS and YAGNI still govern.**
  Discarding artificial constraints should lead to simpler, leaner
  architectures, not speculative frameworks or gratuitous abstractions.
  If an outside-the-box idea introduces more moving parts than the
  straightforward path, KISS rejects it.

## In development and review

- **In development:**
  When a task feels disproportionately difficult, stop and identify which
  assumed constraints are creating the difficulty.
  Test whether altering an upstream parameter, updating a shared utility,
  or reframing the interface dissolves the complexity before writing
  elaborate workaround code.
- **In review:**
  Look for code that works around a problem rather than solving it at the
  source.
  Flag intricate parsing of internally-controlled strings, complex state
  machines built to handle avoidable race conditions, or convoluted adapter
  layers that exist only because nobody wanted to update the underlying
  interface.
