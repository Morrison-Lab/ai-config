Make every parameter configurable.
A quantity a caller could reasonably want to vary --- a size, a count, a
layout, a timing, a threshold, a spawn geometry --- should enter through a
function parameter, a constructor/instance field, or a data file, with
today's value kept as the default. Never bury it as a bare literal inside
the implementation where only an edit to that function's own source can
change it.

## The exemption

**Universal physical constants** (the speed of light, Avogadro's number,
unit-conversion factors between fixed units) and **true mathematical
constants** (pi, e) are exempt from being caller-configurable --- no caller
has a legitimate reason to want a different one, ever. The test: would a
caller ever legitimately want a different value for a different call, run,
or configuration? If yes, it's a parameter. If the value is fixed by the
physical world or by mathematics itself and cannot vary by context, it
doesn't need to be a parameter --- but exempt from configurability isn't
license to hand-type an approximation: use the language or library's own
named constant (`Math.PI`, `np.pi`, `scipy.constants.c`), not a duplicated
literal that can drift from the canonical value or its precision.

**Not exempt: quantities that are measured or vary by context.** Local
gravitational acceleration varies by latitude and altitude (a caller
modeling a specific location may need a different `g`); a material
property varies by material and environment (a caller working with a
different material needs a different value). These look constant at a
single call site, but they still fail the variability test above --- a
different caller, a different location, or a different material
legitimately wants a different number. Treat them as parameters with the
commonly used value as the default, not as exemptions.

## Distinct from avoid-hardcoding-external-data

This is a different axis from
[`avoid-hardcoding-external-data`](avoid-hardcoding-external-data.md), which
is about duplicated **ownership** of a fact that already has an external
source of truth (a version number, a package list). This rule is about
**variability**: a value can have no external owner at all --- it's a
constant this project chose --- and still be a parameter, because some
future caller will legitimately want a different value for their own
call site. The two checks compose: a value can fail either, both, or
neither.

## Why

A compile-time or hard-coded constant shared across every caller forces
every future change in scope to become a global, code-editing change ---
and when call sites have accumulated downstream state that assumes the old
value (timing, layout, positioning baked into other artifacts), that
edit can cascade into a large, unplanned retiming/rework sweep instead of
a single call-site argument change.
(Lacaedemon/sparta#946 changed a shared compile-time battlefield-size
constant and had to audit all 19 default-spawn demo clips, retargeting or
retiming 8 of them that had baked in the old geometry;
Lacaedemon/sparta#964 later moved to per-battle map definitions so this
class of change no longer needs a repo-wide clip sweep.)

## Turning an extension point on by default: add a toggle, don't flip its default

A list-valued extension point --- a plugin list, a hook registry, a named
extra-arguments list --- usually ships empty, with callers passing whatever
they want added.
The trap below needs a **named** parameter carrying a default that a caller's
own value displaces.
A true varargs mechanism (R's `...`, Python's `*args`) is exempt, and is
worth recognizing as the shape that already behaves the way this section
argues for: it has no default to lose, so whatever a caller passes can only
add to what the callee supplies.

When some built-in entry should later be included *by default*, the tempting
move is to change that input's default from empty to the built-in value.
Don't.
A caller-supplied value **replaces** the default rather than adding to it ---
the ordinary semantics of function arguments, CLI flags, and CI/workflow
inputs alike --- so the first caller who uses the extension point for its
original purpose, adding an entry of their own, silently loses the built-in
one.
Nothing errors, and nothing in the caller's own config hints that a default
went missing.

Add a separate toggle instead (a boolean, defaulting on) and compose the two
where they are consumed: the toggle decides whether the built-in entry is
included, and the list input keeps meaning "further entries, on top of
whatever the toggle contributed".
A caller can then opt out, add extras, or both, independently.

Restate the composition in the list input's own description, not just the
toggle's.
Its meaning shifts from "the entries" to "further entries", and a reader who
finds only one of the two docs will otherwise assume they conflict.
Drop any example in that description that names the now-default entry --- the
default is the worst possible illustration of an *extra*.

(d-morrison/gha#321, 2026-07-27: `claude.yml` and `claude-code-review.yml`
gained opt-in `plugin-marketplaces` / `plugins` inputs, then needed one plugin
installed by default.
Flipping those defaults would have meant a consumer adding their own
marketplace silently dropped the default one, since `workflow_call` inputs
replace rather than append.
A `use-ai-config` boolean composed with both instead.)

## Default a useful feature on

A feature worth building is worth defaulting on.
Ship it opt-*out*, with a toggle that turns it off, rather than opt-in.

The reason is who the two defaults actually serve.
An opt-in feature reaches only the people who read a changelog looking for
new inputs to enable, and those are rarely the people it would help most --
so the work lands in the repo and never reaches a consumer.
An opt-out feature reaches everyone immediately, and the one consumer it does
not suit spends a single line turning it off.

This sits directly above the section before it, and the two are easy to read
as contradicting each other.
They compose instead, because they answer different questions:

- **That rule picks the mechanism.**
  Use a separate boolean toggle, never a flipped default on a list-valued
  input, since a caller's list *replaces* the default rather than adding to
  it.
- **This rule picks that toggle's value.**
  Default it to on.

The worked example there already follows both: gha#321 added a `use-ai-config`
boolean, defaulting on, beside the list inputs it composes with.

### What has to be true first

The default is a default, not a licence.
Three things gate it:

- **The feature has to be safe on.**
  Additive or advisory qualifies.
  Anything that can fail a build, spend money, or take a destructive action
  does not, and stays opt-in however useful it is.
- **"Useful" wants a measurement, not an assumption.**
  A check that fires constantly is worse on by default than off, because it
  trains every reader to ignore it (see
  [`algorithmatize-checks`](../workflow/algorithmatize-checks.md)).
- **Turning it on is a behavior change for existing consumers**, who get it
  without asking, so it belongs under a changelog's `changed` heading rather
  than `added`.

(d-morrison/gha#336, 2026-07-28: a new clause-break check for
`check-new-line-breaks` was proposed opt-in, on the strength of a real noise
measurement -- but the measurement that justified caution was for a *blanket
punctuation* rule flagging 50.5% of already-conforming lines, while the check
actually built flags 1.1%.
The maintainer's correction was "in general, useful features should be
opt-out", and the 1.1% is what made that safe.
The check is also warn-only unless a caller sets `fail`, which is the
safe-on condition above doing its work.)

## In review

Flag a new hard-coded tunable in a diff as a standard review finding, the
same weight as the other `shared/coding` rules: name the value, confirm it
isn't one of the two exemptions above, and ask for it to become a
parameter/field/data value with the current value as its default.
Flag the inverse too: a diff that turns an existing extension point on by
default by changing its own default value, where the section above calls for
a separate toggle.
Flag a new feature shipped **opt-in** as well, when it is additive or
advisory and nothing in the three gates above rules out defaulting it on --
an unused feature helps nobody, and the fix is one changed default plus a
`changed` changelog entry.
