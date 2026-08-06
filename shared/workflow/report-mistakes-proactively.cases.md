# Case records: report-mistakes-proactively

Worked-example case records for the rules in
[`report-mistakes-proactively.md`](report-mistakes-proactively.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "Filing is not gated on approval" --- stale skills already tracked

(Corrected in an ai-config session, 2026-07-28: a sweep found 49 of 179
installed skills stale or orphaned, and the finding was reported as "worth a
tracking issue separately --- say the word and I'll file it".
The user's correction was "always file issues as soon as you notice them" /
"don't wait for my approval".
The dupe-check then showed it was already tracked by #755 and #769, so the
correct action was a comment with the new evidence rather than a new issue
--- which is step 2 doing its job, and is exactly the decision the offer had
deferred instead of making.)

## "A gated action bundled into a discretionary one is still an offer"

(Corrected 2026-07-29, a bcs branch-sweep session: an unlanded engineering fix
found on a closed branch was correctly identified as needing a tracking issue,
and the closing line asked "want me to file the issue and open that PR?".
The user's correction was that filing is not a thing to ask about.
The issue --- `ucdavis/bcs#466` --- was filed immediately afterward, which is
the evidence that nothing was blocking it in the first place.)

## "Offering to hand over work you have already finished"

(Corrected 2026-07-30: a drafted answer for a GitHub discussion sat complete
in a scratchpad file across two replies, each offering to print it on
request, while the surrounding messages explained at length why posting it
directly was blocked.
The user's correction was "why haven't you done it already then?".
It was printed in full in the next message, which is the evidence that
nothing was blocking it.)

## "Never name an issue number before the issue exists" --- filed as #821

(Corrected 2026-07-29, an ai-config session: a PR comment said a noticed
mistake was "filed as #821" before any issue had been created.
The dupe-check then found #815 already covering it, so the correct action was
a comment carrying the new evidence --- not a new issue at any number.
Both halves had to be repaired: a correction comment on the PR withdrawing
the citation, and the evidence re-posted onto #815.)
