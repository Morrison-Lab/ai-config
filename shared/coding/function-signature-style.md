When an R function signature doesn't fit on one line, format the argument
list with **single-indent** style: nothing after `function(`, each argument
on its own line indented one level (+2 spaces), and `) {` on its own line
closing the signature.

```r
# Preferred --- single-indent
build_surv_power_table <- function(
  frac_op,
  frac_nonop,
  projected_total,
  hrs = c(2.0, 1.5)
) {
  ...
}

# Avoid --- hanging/aligned indent
build_surv_power_table <- function(frac_op, frac_nonop, projected_total,
                                   hrs = c(2.0, 1.5)) {
  ...
}
```

A signature that fits within the line limit on one line stays on one line;
this rule is only about how to break long ones.

Why single-indent over hanging indent:

- A rename of the function doesn't reflow every continuation line, so diffs
  stay confined to the argument that actually changed.
- Adding or removing an argument is a one-line diff, like a trailing-comma
  list.
- It matches the tidyverse style guide's current recommendation.

lintr's `indentation_linter` doesn't settle this choice: as of lintr 3.4.0
it rejects a third style — the old *double-indent* form (arguments at +4
with `) {` attached; r-lib/lintr#2830) — but accepts both single-indent and
hanging-aligned indent. Choosing single-indent over hanging-aligned is
therefore a review-level preference, not a CI-enforced one: flag
hanging-indent signatures in review the same way as other formatting
findings, and convert them when touching a file for other reasons.

**Copy the rule, not the neighbouring file --- a repo full of the
double-indent form is not evidence that the form passes.**
A `lint-changed-files` job lints only the paths a PR touches, so pre-existing
violations everywhere else stay invisible and CI stays green over them.
A *new* file is therefore frequently the first thing in the repo ever held to
the rule, and the surrounding code is the worst available model precisely
because nothing has ever checked it.
Imitating a neighbour's 4-space signature then draws a lint failure that reads
as arbitrary, since every file around it does the same thing.

This is the general shape recorded in
[`ascii-punctuation-in-source`](ascii-punctuation-in-source.md)'s "writing
into a file that predates this rule" section: a diff-scoped check judges only
added lines, so the existing ones are grandfathered rather than permitted.
Match the linter and the written convention, not the file you are editing.

- **Do:** check the style guide and run the linter on a new file, rather than
  matching what the directory already does.
- **Don't:** read green CI over a repo's existing files as evidence their
  style passes --- a diff-scoped linter never looked at them.

(Encoded from review feedback on `ucdavis/rampp#137`, 2026-07-17; the
repo-wide conversion of pre-existing hanging signatures there is tracked in
`ucdavis/rampp#139`.
The diff-scoped-invisibility half is from `UCD-SERG/serocalculator` #633, 2026-08, where a 4-space signature copied from a neighbouring file drew a lint failure on the new file alone.
It recurred on serocalculator#668, 2026-09-01, in the other direction: the files were pre-existing, `lint-changed-files` held them to the rule for the first time, and the session read the repo-wide +4 form as "the package's own convention" and declined to reformat, filing serocalculator#672 for a `.lintr.R` change instead --- with this fragment loaded.
A census of `R/*.R` there, taken before the reformat, found 27 files whose multi-line signatures use the +4 form and 12 that already use +2, so the neighbours were the majority and still not the rule.
The user asked why the lint's own recommendation could not be applied, and the reformat took one commit.)

- **Do:** reformat a flagged +4 signature in a file you are already touching, even when every neighbouring file uses the same form.
- **Don't:** file a linter-config change to preserve a form the written convention already rejects, on the strength of how many files carry it.
