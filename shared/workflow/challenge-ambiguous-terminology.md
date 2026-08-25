When reviewing code or prose, challenge ambiguous phrasing and terminology
instead of silently accepting it. Flag a term or phrase when its meaning
depends on the reader guessing --- a name that could refer to more than one
thing, a claim that cites a value or construct without confirming it exists,
a word doing double duty for two different concepts in the same document. Ask
what the writer means, or check the referenced code/spec directly, rather than
inferring a plausible reading and moving on.

This catches more than typos: a reviewer who accepts ambiguous terminology at
face value can let a factually wrong claim through unchallenged --- for
example, documentation that cites a named constant or enum value that doesn't
exist in the code, because the term sounded plausible and nobody checked it
against the actual source.

Applies everywhere review already happens: PR/MR code review (`ard`/`ardi`),
prose and doc review (`use-preferred-style`, `find-ai-tells`), and issue/spec
review. When the ambiguity is resolvable by reading the code or spec yourself,
resolve it and note the correction; when it genuinely depends on the author's
intent, ask rather than assume.

**Cross-repo citations have a merge-order trap.**
Citing a specific file path or construct in another repo is itself unverifiable if the PR that adds it hasn't merged yet --- and a link checker will not save you, on any case measured here: a backticked path is not a link, so nothing crawls it.

Don't fix this by promising a future edit ("cite it generically for now, then
tighten the citation once it merges") --- that's still a citation that needs
someone to remember to come back and fix it, the same future-edit fragility
this guideline warns against, just moved one level up. Instead, phrase the
citation as a conditional that's already accurate regardless of which PR
merges first: "This is a global standing rule proposed in `<repo>#<PR>` ---
once merged, the fragment lives at `<path>` there." That sentence never needs
editing; it's true before the merge and still true after.

**This isn't only a review-time catch --- apply it while authoring the
citation, not just when checking one.** Before writing a sentence in one
repo's `CLAUDE.md` that names a specific path in another repo's still-open
PR, stop and check whether that companion PR has merged yet. Knowing the
evergreen-conditional phrasing exists doesn't help if the trap only comes to
mind during review, after the premature citation is already written --- by
then it takes a review round to catch what a ten-second merge-status check
would have prevented.

(Caught by this very guideline four times now, all while cross-linking a
still-open `ai-config` PR into `gha`'s `CLAUDE.md`: twice on gha#151 --- the
file it pointed at only existed on this fragment's own not-yet-merged PR ---
again on gha#208, and again on gha#217. On gha#208, the first fix cited the
file as already established; a review caught that. The reworded "not yet
merged as of this writing, tighten this citation once it lands" fix repeated
the exact future-edit trap this note originally warned against. A second
review (Copilot) caught that too, and the evergreen-conditional phrasing
above was adopted. On gha#217, the citation was written as an
already-established fact again --- even though the evergreen-conditional phrasing
had already landed on `main` in the same session --- because nothing
prompted a check of this guideline while writing a brand-new citation, only
once a review flagged it after the fact.)

**Fifth occurrence, 2026-08-24, and the first one SAME-repo.**
`CLAUDE.md` already says this section applies to a same-repo sibling PR unchanged, and this is that case: ai-config prose citing a construct in ai-config's own `hooks/`, where the four above are all `gha`'s `CLAUDE.md` citing `d-morrison/ai-config`.
Note what does **not** distinguish them, since the obvious contrast is wrong: none of the five had a link checker behind it.
The four cross-repo cases cite a backticked bare path and a repo-root link, and each escapes a checker for its own reason: a backticked path is not a link, so nothing crawls it, while the repo-root link resolves fine.
So the 404 warning never fired on any measured case, and it would not have fired on this one either.

**The new observation is why thorough review does not catch it.**
Every reviewer verifies the claim against the branch the claim is *about*, which is the correct artifact for its truth --- so it passes, and the more carefully that branch is checked, the more settled the sentence looks.
The question nobody asks is which artifact the *reader* will be standing on, because that is a question about the claim's audience rather than its truth.
So this is the one trap in this section where verification effort runs the wrong way.

- **Do:** settle it from the **PR's own state** (`gh pr view <N> --json state`), or from an empty `git diff <base> <branch> -- <path>`, per [`pr-on-claim`](pr-on-claim.md) --- not by grepping for the name, which succeeds once your own citing sentence lands on the target branch, and not by `git merge-base --is-ancestor`, which never discharges in a squash-merging repo because the squash commit excludes the branch's own commits.
- **Don't:** rely on a link checker to catch a premature citation, in either direction --- a backticked path and a bare construct name are both invisible to one.

(Measured on [ai-config#2207](https://github.com/Morrison-Lab/ai-config/pull/2207), whose prose described a constant in `hooks/require-agent-disclosure.py` in the present tense.
That constant exists only on [#2185](https://github.com/Morrison-Lab/ai-config/pull/2185), open at the time, and its introducing commit was an ancestor of neither `main` nor the citing branch.
Twelve pre-push adversarial rounds ran on that PR without raising it, and the round that did raise it had itself executed the regex, the commit ancestry, and the timestamps against `#2185` --- all correct, and all about the wrong branch.
Two separately-dispatched same-vendor passes then raised it nine minutes apart, once the diff was read as something about to become `main`: a session verification pass at `05:27:25Z` (comment `5405924657`) and the repo's own `claude-review` at `05:36:44Z`.
Naming both matters, because the *later* `claude-review` round at `05:46:39Z` reports zero findings and **Ready for merge** --- it confirmed the fix rather than raising anything, so a reader comparing only the two `claude-review` comments finds one raise, not two.)

**A cross-repo citation can also name the wrong repository, with nothing
pending and nothing to wait for.**
The trap above is about *when* a cited path exists, so its remedy is a
merge-status check and a phrasing that survives either merge order.
This one fires once everything has merged: the section is present, the title
is quoted correctly, and it lives in the other repository.

The setup is two repos' `CLAUDE.md` files auto-loaded at once, which is the
normal state of a session scoped to more than one repo.
A section title from the second one sits in context, reads as something
already verified, and gets cited from a memory file in the first --- where a
bare `` `CLAUDE.md` `` resolves to that repo's own.

Self-review does not catch it, because the check it prompts is whether the
section exists, and it does.
The title was read rather than invented, so re-reading the sentence confirms
the reading you already had.

A link checker cannot catch it either, and that is the part worth knowing.
`CLAUDE.md` exists in both repositories, so the *file* resolves and the
*section* does not.
A checker keyed on paths reports clean over a citation that sends a reader to
a document with no such heading in it.

The remedy is to qualify the path with its owner and repo whenever a citation
crosses one, rather than leaning on where the reader happens to be:
`` `Morrison-Lab/gha`'s `CLAUDE.md` ``.
Better still, cite the nearest home instead --- a fact already restated in the
file you are editing needs no cross-repo citation at all.

- **Do:** qualify a cited path with its owner and repo whenever more than one
  repo is loaded, however unambiguous the title reads in context.
- **Do:** settle which repository a section lives in by grepping for the
  heading, rather than by recalling where you read it.
- **Don't:** read "the section exists and I quoted it correctly" as having
  verified the citation --- that check passes on exactly this error.
- **Don't:** rely on a link check to catch it; a filename shared between two
  repos resolves in both.

(`Morrison-Lab/ai-config#1404`, 2026-08-12: a bullet in `memories/github.md`
cited `` `CLAUDE.md` ``'s "GitHub access in remote / web sessions" section as
the authority for `gh` being absent from remote sessions.
That section is real, and it lives in `Morrison-Lab/gha`'s `CLAUDE.md`, which
was auto-loaded alongside ai-config's in the same session.
ai-config's own `CLAUDE.md` has no such heading, so to a reader inside
ai-config the citation names a document that does not contain it.
Review caught it; the fix repointed the sentence at that memory file's own
"GitHub access from bash in remote/web sessions" section, which states the
same fact one file away rather than one repo away.
The same wrong citation had been copied into the PR body, which no diff-grep
reaches and which the reviewer re-verified the diff instead of, so it took a
second fix plus a correction note recorded inside the body.)
