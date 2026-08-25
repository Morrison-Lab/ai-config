Avoid ambiguity in writing.
A referring expression --- a pronoun, a demonstrative, a relative `which` ---
must have exactly one reading, and the reading a reader reaches first has to be
the one you meant.

## The tell

A pronoun or demonstrative whose **nearest grammatical antecedent is not its
intended referent**.
The words to watch are the short ones carrying no meaning of their own:
`it`, `this`, `that`, `which`, `they`, `these`, `those`.

The dangerous case is not a pronoun with **no** clear referent.
A reader meets that one, notices the gap, and re-reads until the sentence
resolves, so the cost is a pause.
The dangerous case is a pronoun whose **wrong** referent sits closer and reads
perfectly well.
Nothing prompts the reader to stop, so they take away the wrong fact without
ever having been unsure.
A sentence that slows a reader down costs a moment;
one that reads smoothly into the wrong meaning costs the fact.

That inverts the usual defence.
Re-reading your own draft does not reliably catch it, because the reading you
meet is the reading you meant: you already know the referent, so the fluent
wrong reading is invisible from the inside.
The check has to be **grammatical rather than semantic**.
Find the nearest noun phrase before the pronoun and ask whether that noun
phrase is the intended one, rather than asking whether the sentence makes
sense, since it will.

## The remedy: replace the pronoun with the noun

Naming the referent costs a few words and removes the ambiguity completely.
Rewording around the sentence while keeping the pronoun does not, because the
pronoun is the ambiguous element:
any fix leaving it in place leaves the reader the same choice to make.

Where the intended referent has no ready short name, supply one rather than
gesturing at it more elaborately.
"That identity", "that Hessian", and "the integral" each name a thing.
"The above", "the former", and "the aforementioned result" each ask the reader
to do the resolving you were supposed to do.

## The limit

Not every pronoun needs replacing.
Prose naming every referent explicitly becomes leaden, and a pronoun whose
antecedent is unmistakable is doing its job.

The test is not "is there a pronoun" but **"is the nearest grammatical
antecedent the intended one"**.
Where it is, leave the pronoun alone.

A clause-referring `which` is the common legitimate case, and this corpus uses
it constantly:

```bash
python3 -c "
import re, pathlib
norm = lambda s: re.sub(r'[\`*_\s]+', ' ', s)
naive = norm_n = files = 0
for p in pathlib.Path('.').rglob('*.md'):
    if '.git' in str(p): continue
    t = p.read_text(errors='ignore')
    naive += len(re.findall(r'which is what', t))
    c = len(re.findall(r'which is what', norm(t)))
    if c: norm_n += c; files += 1
print('naive:', naive, 'normalized:', norm_n, 'files:', files)
"
```

That reported `naive: 53 normalized: 57 files: 33` at `7d843650`.
Read the gap between the two totals as its own small lesson:
four of those occurrences straddle a newline, so a line-oriented grep misses
them in a corpus written to
[`semantic-line-breaks`](semantic-line-breaks.md).
The counts are offered as evidence that the construction is normal here, not
as a claim that all 57 are unambiguous --- they were counted, not audited.

The construction is fine wherever the `which` attaches to the whole preceding
clause and no competing noun phrase intervenes.
It stops being fine the moment a noun sits between that clause and the `which`,
because the noun is then the nearer antecedent and wins the reader's first
reading.

## One instance predicts others

The defect is a habit rather than a slip, so a document with one ambiguous
referent usually carries several.
When a review flags one, sweep the whole document rather than fixing only the
line that was named.
[`address-every-comment`](../workflow/address-every-comment.md) states the
general form: a reviewer's enumeration is the extent of that reviewer's read
and never the extent of the pattern, so derive your own site list rather than
inheriting theirs.

Nothing decides this mechanically.
"Is the nearest antecedent the intended one" has no decidable condition, so it
stays in the judgment residue
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) reserves.
What narrows the search is positional:
risk concentrates where a pronoun opens a subordinate clause
(`because it`, `so it`, `and this`, `, which`)
in a sentence already naming two or more nouns.
Read those, and leave the rest.

## The most expensive place for one is a Do/Don't bullet

Everything above prices an ambiguous referent as a **wrong fact** a reader
carries away.
In a Do/Don't bullet it costs more, because the bullet *is* the instruction.
A pronoun landing on the wrong antecedent there does not merely mislead ---
it prescribes the opposite action, and a bullet is the one place with no
surrounding prose for a reader to recover the intent from.

The remedy the sections above give does not fire here, which is the gap.
"Find the nearest noun phrase and confirm it is the intended referent" is a
check on one sentence, and a bullet pair fails as a **pair**: each half reads
correctly alone, and only reading them against each other shows that one tells
you to edit a thing the other tells you to leave alone.

So the decisive check is free and sits in the same block: **read each bullet
against the worked example the block cites.**
A block that earns a Do/Don't pair almost always carries a case record, and
that record says what somebody actually did --- so it settles what the bullet
is supposed to prescribe, with no judgment about pronouns involved at all.

The near-miss is drafting the bullets from the block's **diagnosis**
paragraph rather than from its example.
The diagnosis is the half freshest in mind and the half carrying the
argument, and it describes the defect rather than the remedy --- so a bullet
written out of its vocabulary names the defective artifact, and a pronoun
then binds to that.
Nothing about this feels like guessing, since the diagnosis is the block's own
prose, correctly understood.

- **Do:** read a new Do/Don't pair against the block's worked example, and
  against each other, before pushing.
- **Do:** name the noun in a bullet even where the prose above it has just
  established the referent, since a bullet is read alone.
- **Don't:** draft a bullet out of the diagnosis paragraph's vocabulary ---
  that paragraph names the broken artifact, and the bullet is about the
  remedy.
- **Don't:** treat the nearest-antecedent check as sufficient for a bullet
  pair; each half can pass it while the two contradict.

(`Morrison-Lab/ai-config#1429`, 2026-08-12, review finding 1, blocking.
`shared/workflow/ardi.md`'s "A `Corrections to this body` entry is itself a
figure in the body" block closed with a **Do** bullet reading "re-derive every
figure a corrections entry vouches for at each push, and move the entry's own
SHA along with them".
The nearest antecedent for "the entry" is the corrections entry already in the
body, so the bullet read as an in-place SHA edit --- which the very next
bullet forbids, asking for a further numbered entry "rather than editing the
previous one".
The block's own worked example settles it in the same direction:
`Morrison-Lab/ai-config#1395` appended a fourth entry recording its second
refresh, leaving the third entry's figures where they were.
Fixed to "record the SHA the new figures were derived at alongside them".)

## Relationship to neighbouring rules

- [`challenge-ambiguous-terminology`](../workflow/challenge-ambiguous-terminology.md)
  governs an ambiguous **term** --- a word whose meaning is unresolved, or a
  name that could denote more than one thing --- and fires at review time.
  This governs an ambiguous **reference**, where the word's meaning is settled
  and its antecedent is not.
  The remedies differ with them: there you ask the author or read the source,
  here you replace the pronoun with the noun.
- [`forward-references`](forward-references.md) also concerns a referent the
  reader cannot resolve, and there the defect is **position** rather than
  identity --- the referent is named unambiguously and has simply not been
  reached yet.
  Its remedy is to rearrange; this one's is to name.
- The [`use-preferred-style`](../../skills/use-preferred-style/SKILL.md)
  skill's rule 8, "Name a demonstrative's referent", already covers standalone
  `this`/`that`/`these`/`those`, following PSW's
  [Grammar](https://morrison-lab.github.io/psw/chapters/grammar.html) chapter.
  This widens that rule on two axes:
  to every referring expression rather than the demonstratives alone, and to
  the **wrong**-antecedent case rather than the missing-antecedent case that
  rule describes.
- [`plain-prose`](plain-prose.md) is the general style umbrella this sits
  under.

- **Do:** find the nearest noun phrase before a pronoun and confirm it is the
  intended referent, rather than checking whether the sentence reads sensibly.
- **Do:** replace the pronoun with the noun, supplying a short name for the
  referent when it has none.
- **Do:** sweep the whole document once one ambiguous referent is found.
- **Don't:** treat a pronoun as safe because the sentence is fluent --- fluency
  is exactly what the wrong-antecedent case produces.
- **Don't:** reword around a pronoun to clarify it while leaving it in place;
  the pronoun is the ambiguous element.
- **Don't:** name every referent explicitly --- a pronoun whose antecedent is
  unmistakable needs no fix.

## In review

Flag an ambiguous referent in a prose diff with the same weight as the other
prose-review findings, wherever `ard`/`ardi` already reviews prose.
Quote the pronoun, name the two candidate antecedents, and propose the noun.
A finding saying only "this is ambiguous" leaves the author to guess which
reading you reached, and that guess is the same defect one level up.

(Directive from the user, 2026-08-09:
"cai: avoid ambiguity in writing; for example, in
`https://ucd-serg.github.io/serocalculator/pr-preview/pr-654/vignettes/methodology.html#estimating-incidence-from-cross-sectional-serosurveys:~:text=it%20turns%20products%20into%20sums`,
the referent of 'it' is ambiguous; log-likelihood, or the log function?"
The URL is kept as a code span rather than a link because a PR-preview page is
torn down when its PR closes.

The sentence, in `UCD-SERG/serocalculator#654`'s `vignettes/methodology.qmd`,
read:

> The **log-likelihood** $\llik(\lambda) \eqdef \logf{\Lik(\lambda)}$ is
> maximized at the same $\lambda$, and is easier to work with because **it**
> turns products into sums.

"It" could be the log-likelihood --- grammatically nearest, and the subject of
the sentence --- or the logarithm, which is the semantically correct reading:
a log-likelihood does not turn products into sums, the log function does.
The grammatically natural reading is the wrong one, and that mismatch is what
makes the sentence a defect rather than an imprecision.
Fixed to "is easier to work with because **the logarithm** turns products into
sums".

A sweep of the same file found three more:

1. "Written out, **it** is" --- the intended referent was "that integral", two
   sentences back, while the nearest antecedents were an atom, a distribution,
   and $T$.
   Fixed to "Written out over both parts, **the integral** is".
2. "returns a numerical Hessian at the maximum, **which** is what the theorem
   turns into a standard error" --- the nearest noun was "the maximum".
   Fixed to "and the theorem turns **that Hessian** into a standard error".
3. "the incidence rate of the definition, **which** is what makes $T$ worth
   recovering" --- the `which` could attach to the incidence rate or to the
   identity just asserted.
   Fixed to "and **that identity** is what makes $T$ worth recovering".

All four landed in that PR's commit `c57547567`, "Remove ambiguous pronoun
referents; cite rme for the log-product result".
One reported instance yielding three more on a sweep is the evidence for the
habit-rather-than-slip claim above.)

## A bare `#N` takes its repo from context, so it is a referent too

The rule above governs pronouns.
A bare issue or PR reference --- `#1677`, with no owner or repo --- has the same structure and is easier to miss, because it looks like a precise citation rather than like a word waiting for an antecedent.
A human reader resolves it against whatever repo the surrounding sentence named,
and when that is not the repo it belongs to, the sentence asserts something neither half of it says.

**Inside a file there is no second resolver to catch it.**
GitHub's autolinking does not run in repository files ---
its own documentation says autolinked references are not created in wikis or in files in a repository ---
so a bare `#1677` in a memory or fragment is inert text rather than a link.
That strengthens the rule rather than weakening it:
on a conversational surface a wrong bare `#N` at least renders as a link a reader can follow and find wrong,
whereas in a file the reader's own assumption is the only resolver there is.

The failure needs two ordinary, individually-true facts sitting next to each other.
A memory entry recorded `wai session 2026-08-19: told user PR #1677 was on the branch`.
The session's working directory really was `wai`, and the PR really was `Morrison-Lab/ai-config#1677` --- a session working one repo from another's checkout, which is routine.
Composed, the line claims a `wai` PR that has never existed.

**A reviewer checking it will confirm the error and misdiagnose the cause.**
Searching `wai` for `#1677` correctly returns nothing, which reads as a mislabeled repo, so the natural fix is to relabel the session.
That is wrong: the session label was accurate, and relabelling it would trade a false claim about the PR for a false claim about the session.
The actual defect is an *unqualified* number, so the fix is to qualify it and keep both facts: write the session as ``2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`)``, with the reference itself written `Morrison-Lab/ai-config#1677`.

The asymmetry worth remembering: a bare `#N` is safe exactly while the document, the repo, and the work are the same repo.
Every cross-repo note breaks that, and cross-repo notes are what a memory corpus is mostly made of.

[`memories/preferences.md`](../../memories/preferences.md) already carries the operational half of this for *posted* prose ---
a PR comment, an issue, a commit message --- where GitHub really does resolve a bare `#N` to the current repo and produce a wrong link.
This section is the file-side complement: same remedy, different mechanism, and no link to be wrong.

- **Do:** write `owner/repo#N` in any note whose surrounding text names a different repo than the one the reference belongs to.
- **Do:** separate the session's location from the work's location when they differ, rather than picking one.
- **Don't:** read "that number does not exist in the repo I searched" as proof the repo label is wrong --- check whether the *number* is unqualified first.
- **Don't:** leave a bare `#N` in a memory or fragment merely because it resolves correctly where it currently lives;
  these files get quoted, migrated, and read from other repos.

(Morrison-Lab/ai-config#1677, 2026-08-20: caught in review, with exactly the misdiagnosis described above --- the reviewer verified `#1677` exists in neither `the repository owner/wai` nor `Morrison-Lab/wai` and concluded the repo label was wrong.
Three Example lines carried the same construction.)
