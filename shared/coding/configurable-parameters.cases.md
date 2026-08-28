# Case records: configurable-parameters

Worked-example case records for the rules in
[`configurable-parameters.md`](configurable-parameters.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "Why" --- the shared battlefield-size constant

(Lacaedemon/sparta#946 changed a shared compile-time battlefield-size
constant and had to audit all 19 default-spawn demo clips, retargeting or
retiming 8 of them that had baked in the old geometry;
Lacaedemon/sparta#964 later moved to per-battle map definitions so this
class of change no longer needs a repo-wide clip sweep.)

## "Turning an extension point on by default: add a toggle"

(Morrison-Lab/gha#321, 2026-07-27: `claude.yml` and `claude-code-review.yml`
gained opt-in `plugin-marketplaces` / `plugins` inputs, then needed one plugin
installed by default.
Flipping those defaults would have meant a consumer adding their own
marketplace silently dropped the default one, since `workflow_call` inputs
replace rather than append.
A `use-ai-config` boolean composed with both instead.)

## "Default a useful feature on" --- the clause-break check

(Morrison-Lab/gha#336, 2026-07-28: a new clause-break check for
`check-new-line-breaks` was proposed opt-in, on the strength of a real noise
measurement -- but the measurement that justified caution was for a *blanket
punctuation* rule flagging 50.5% of already-conforming lines, while the check
actually built flags 1.1%.
The maintainer's correction was "in general, useful features should be
opt-out", and the 1.1% is what made that safe.
The check is also warn-only unless a caller sets `fail`, which is the
"feature has to be safe on" precondition doing its work.)
