# Copilot code review instructions for `Morrison-Lab/ai-config`

## What this repository is

This is an **agent-configuration corpus**, not an application.
The prose *is* the product: `CLAUDE.md`, `shared/**/*.md`, `skills/*/SKILL.md`, and `memories/*.md` are instructions loaded into AI coding agents, so a wrong sentence is a defect in the same way a wrong function is.
`scripts/` holds the small Python instruments that check the corpus.

Review prose with the rigor you would apply to code.

## Hard conventions, worth flagging on sight

**ASCII punctuation only.** Never em-dashes, en-dashes, curly quotes, or the multiplication sign, anywhere in a tracked file, including code comments and Markdown prose.
Write `--` where a dash is wanted.
This is enforced by convention rather than by CI, so review is the main line of defence.

**Semantic line breaks.**
Prose is written one clause per line, so a phrase routinely spans a newline.
Two consequences for you.
Do not flag a short line as needing to be joined.
And before reporting that some text or reference is missing, remember that a literal single-line search gives false negatives here; a claim of absence needs a whitespace-normalized search behind it.

**No hard line-length limit.** `MD013` is off deliberately.

## What to prioritize

Correctness first, in this order:

1. **Logic and factual errors.** A rule that contradicts another rule, a claim that is false, a cited file or section that does not exist, a command that would not work as written.
2. **Internal consistency.** This corpus cross-references itself heavily.
   A change to one rule frequently falsifies a restatement of it elsewhere, and the stale copy is usually in a *different* file from the one being edited.
3. **Instructions that cannot be followed.** Two sections giving opposite guidance for the same situation is the highest-value finding class here, and the hardest for the author to see.
4. **Documented style rules**, which in this repo are substantive rather than cosmetic.
   Ambiguous terminology, forward references to content the reader has not reached, unverified claims, and redundant restatement all have their own fragments under `shared/writing/` and `shared/workflow/`, and findings against them are welcome.
   What is *not* wanted is generic style preference with no rule behind it.

## Tests

Test files under `scripts/test_*.py` are plain Python scripts, not pytest.
Each defines its own `check(...)` helper and prints a pass/fail tally; the signature varies by file, so read the one in front of you rather than assuming a shape.

The single most valuable thing you can flag: **a test that would still pass if the fix it guards were reverted.** Common shapes seen in this repo:

- It calls a helper directly instead of exercising the real entry point, so it misses a wiring regression.
- Its fixture never reaches the branch under test, because an earlier guard handles the input first.
- Its fixture is handled incidentally by a *neighbouring* mechanism, so the code under test is never invoked.
- Its label describes different behaviour than its assertion checks.

## Evidence standards

Entries in this corpus are expected to be **falsifiable**: concrete case records with real PR/issue numbers, real measurements, and commands a reader can re-run.
Flag a new claim that asserts a mechanism with nothing checkable behind it.

Conversely, when you assert that something is wrong, prefer evidence over inference, and say which you have.
If a finding rests on a file you could not read or a command you could not run, say so rather than presenting it as established.

## Things that are deliberate, so please do not flag them

- **Restating a rule inline next to a citation.** `shared/` fragments are not auto-loaded by every consumer, so a bare pointer is invisible to some agents.
  The duplication is intentional.
- **Long files.** Several fragments are long by design; length alone is not a finding here.
- **An item already dispositioned as Deferred** with a linked tracking issue.
  Re-raising it each round costs a round and changes nothing.
- **`--` sequences in prose.** That is the required dash form, not a typo.
