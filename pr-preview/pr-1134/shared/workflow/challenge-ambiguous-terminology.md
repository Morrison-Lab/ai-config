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

**Cross-repo citations have a merge-order trap.** Citing a specific file path
or construct in another repo is itself unverifiable --- and will 404 a link
checker --- if the PR that adds it hasn't merged yet.

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
above was adopted. On gha#217, the citation was written as an already-
established fact again --- even though the evergreen-conditional phrasing
had already landed on `main` in the same session --- because nothing
prompted a check of this guideline while writing a brand-new citation, only
once a review flagged it after the fact.)
