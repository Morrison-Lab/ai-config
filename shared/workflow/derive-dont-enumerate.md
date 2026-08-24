A brief that enumerates work items is a snapshot.
Before dispatching work scoped to a list --- PR numbers, issue numbers, files, hosts --- ask whether that set can grow or change while the work runs.
When it can, do not hand over the list.
Hand over the query that derives it, or run a sweep against the live set on a timer.

The failure this prevents is invisible by construction, which is why it needs a rule rather than more care.
Every agent does its job correctly on the list it was given, so no artifact reports a problem: the PRs that appear *between* the lists are covered by nobody, and coverage is a property of the **set** rather than of any member.
There is no file to grep, no check to go red, and no reviewer whose scope includes it.
Asking "did anyone drop something" cannot be answered by inspecting any of the things that were done.

Note the class this belongs to.
It is the same defect as a status reading that expires when a push lands, or a `mergeable` flag cached from before `main` moved: a fact about a moment, consumed later as though it were current.
[`fully-clean`](fully-clean.md) makes that point about one PR's verdict.
This makes it about the queue.

## The tell

A list is a snapshot whenever something other than you can add to it while you work.
Concretely, treat as derivable rather than enumerable:

- Open PRs and issues, in any repo where another session, a bot, or a human can open one.
- Failing checks, which a later push can add or clear.
- Files matching a pattern, where a merge can introduce another.
- Repos in scope, hosts in a fleet, or members of any set an API already enumerates.

A list is safe to hand over only when it is closed: a fixed set of inputs, frozen at a commit, that nothing can extend mid-flight.

## What to hand over instead

Give the recipient the derivation, not its result:

- **A query.** "Every open non-draft PR" beats "#937, #939, #943, #946", and stays correct when a seventh appears.
- **A predicate.** "Any PR idle past the threshold with an unaddressed finding" beats a list of the ones that were stalled when you looked.
- **A sweep on a timer.** When the work outlives a single pass, the set must be re-derived per pass, not carried forward from the first one.

When you genuinely must name specific items --- a stacked merge order, an exclusion --- say what the list is *for* and that it is a snapshot, so the recipient knows to re-derive rather than trust it.
The distinction is between a list used as an **index** of the work, which rots, and one used as a **constraint** on it, which does not.

## A derivation is still an enumeration of one pattern

Everything above treats the query as the safe end of the trade, and against the failure it targets it is: a query re-derives the set, so it survives whatever gets added while you work.
That is a claim about **time**, and it leaves the query's own **width** unexamined.

A `git grep` is an enumeration too --- of one pattern --- and it can come back short at the instant it runs, against a frozen corpus, with no concurrency anywhere.
The closedness test above answers **safe** for exactly that case: the inputs are fixed, the commit is frozen, nothing can extend the set mid-flight, and the derived list is still incomplete.
So the test clears a list it should not, which is the gap.

**The tell is that the search term names a command rather than an effect.**
An effect usually has more than one command that produces it, and a pattern built from one of them cannot match the others.
Before trusting a derived site list, ask how many distinct ways the corpus can express the thing being searched for, and search for the effect --- an endpoint, a field, a resulting state --- rather than for whichever spelling you reached for first.

Two things make this hard to catch afterwards.
The result is **non-empty**, so nothing about it invites suspicion; the too-narrow worry that a zero provokes never fires on a list of eight real hits.
And it survives both remedies the corpus already offers.
[`fail-fast`](../principles/fail-fast.md)'s "test the instrument against a known positive before trusting a negative" passes, because the pattern demonstrably matches --- every failure that section describes is a pattern that matched *nothing*, whereas this one matched most of the population.
Its "grep for the operation being guarded, not for the guard" passes too, one notch short: `add-reviewer` **is** the operation, and the grep still missed a site.

The general principle is [`metacognitive-monitoring`](metacognitive-monitoring.md)'s "an instrument's answer is only as wide as its input", and the conclusion already sits as a trailing caveat on [`address-every-comment`](address-every-comment.md)'s site-list rule --- "a differently-worded instance would not have matched".
Read those rather than re-deriving them.
What is added here is the tell, and the step from *the same idea worded differently* to *a different command with the same effect*.

- **Do:** ask how many commands produce the effect you are searching for, before treating a derived site list as the population.
- **Do:** search for the effect, alternating the spellings you know of when no single term covers them.
- **Do:** report the pattern beside the hit count, so the width of the derivation is checkable rather than implied.
- **Don't:** read the closedness test above as clearing a derived list --- it answers whether the set can grow, not whether your pattern found all of it.
- **Don't:** treat a non-empty result as evidence the pattern was wide enough; an incomplete match looks exactly like a complete one.

(Morrison-Lab/ai-config#1178, 2026-08-06: encoding a repo-scoped reviewer exception, `git grep -n 'add-reviewer d-morrison' -- skills/` returned eight hits across six files, including sites a reviewer's own enumeration had missed --- which is this fragment's rule working, and is why the list was trusted.
It also missed `skills/claude-agent-workflow/SKILL.md:118`, which requests the same reviewer as `gh api -X POST repos/.../pulls/$PR_NUMBER/requested_reviewers -f "reviewers[]=d-morrison"`.
A parallel session caught that site in `c9e70fc3` --- a PR-branch commit, squashed into `7a5b2ce0` --- and widened the sweep prescribed in `skills/request-pr-review/SKILL.md` to `add-reviewer d-morrison|requested_reviewers.*d-morrison`, so until then the incomplete pattern had been the corpus's own documented derivation.
The alternatives were already enumerated twice in the same repository: `hooks/no-unreviewed-pr.py` matches five command forms for this one effect --- `gh pr create --reviewer/-r`, `gh pr edit --add-reviewer`, a `-X POST` to the `requested_reviewers` endpoint, and two `request_copilot_review` tool names --- and `tool-mappings.yml` is an effect-to-command registry whose `REQUEST_COPILOT_REVIEW` row carries the REST form outright.
So the corpus's code already knew the effect had several spellings while the grep searched for one.)

### An identity has textual forms the same way an effect has commands

The tell above is stated for commands, and an **identity** decays the same
way: one owner, repo, plugin, or person is written in several textual forms,
and a sweep deriving its sites from one form cannot reach the others.
`owner/repo` is also `owner.github.io/repo` (the separator is a dot, so no
slash-anchored pattern can match it), also `plugin@owner` (the identity is a
suffix), also a bare `"owner"` key in a config block (the repo half is
absent entirely).
A rename sweep that derives from the slash form alone reports itself
complete over a corpus that still carries the identity three other ways.

The same session that produced this section's parent case also produced two
accepted review findings of this shape, in one afternoon:

- A quoting sweep derived its sites from `cli: gh api`, a **field** spelling,
  and missed the same command in a sibling `github_mcp:` field and embedded
  mid-value after `git log` (Morrison-Lab/ai-config#1476, round 1: 6 sites
  claimed, 8 real).
- An owner-rename sweep derived from the literal `d-morrison/ai-config` and
  missed the dead `d-morrison.github.io/ai-config` domain in `_quarto.yml`'s
  `site-url` --- a genuinely broken reference, not mere staleness, invisible
  to the slash form (Morrison-Lab/ai-config#1482, round 1).
  The broken plugin refs (`ai-config@d-morrison`) and marketplace key
  (`"d-morrison"`) had needed their own second pattern in the same sweep for
  the same reason.

So before publishing an identity sweep's site list, enumerate the identity's
**forms** --- path, domain, ref-suffix, bare key, and whatever the ecosystem
adds --- and run one derivation per form, reporting each pattern beside its
count.

- **Do:** list an identity's textual forms first, and derive per form.
- **Don't:** report an identity sweep complete from the form you swept;
  the other forms return the same confident non-empty result for whoever
  checks them next.

## The instrument

`scripts/pr-sweep.py` is this rule's deterministic half for the open-PR case.
It derives the live set for one or more repos and reports which PRs are stalled, with a configurable threshold:

```bash
python3 scripts/pr-sweep.py -R Morrison-Lab/ai-config -R ucdavis/bcs
python3 scripts/pr-sweep.py -R owner/name --stale-minutes 15 --json
```

It always reports what it examined, not only what it found, so a sweep that examined nothing is distinguishable from a clean one.
Per [`algorithmatize-checks`](algorithmatize-checks.md), "which PRs are stalled" has a numeric definition over data the API already returns, so it should not cost model reasoning.
The script is also an instance of [`deterministic-tools`](../principles/deterministic-tools.md): judging coverage by eye is exactly the recurring judgment task that fragment says should become a tool.

It is **read-only reporting, not authorization**.
[`ardi`](ardi.md) limits its monitoring mandate to PRs a session owns or has explicitly claimed, and a PR appearing in this sweep does not transfer ownership.
Surface an unowned stalled PR to the human, or claim it per [`claim-pr`](claim-pr.md) before driving it.

[`pr-status-all`](../../skills/pr-status-all/SKILL.md) remains the richer per-PR dashboard.
This is the cheap standing sweep that says where to point it.

`scripts/pr-overlap.py` is its sibling, deriving the same live set and answering the other set-level question --- which pairs of open PRs share a file:

```bash
python3 scripts/pr-overlap.py -R Morrison-Lab/ai-config
```

The split is worth keeping straight, because "stalled" is a property of each PR and "collides" is a property of the **pair**, so no per-PR sweep can reach it however carefully it is run.
[`batch-merge-and-resolve`](batch-merge-and-resolve.md) owns the collision rule and the boundary: an intersection sees collisions and never dependencies.

## Asserting the set is EMPTY is the enumeration that skips its own check

Everything above governs a set with members: hand over the query rather than the members, and watch that the query itself is wide enough.
A claim that the set has **no** members is the same defect, and it evades both of those remedies, because there is nothing left to derive over.

`CLAUDE.md`'s merge-order section already prescribes the derivation --- "'disjoint' is a claim about their file *sets*, so derive both sets and check the intersection before asserting it".
An intersection against an empty population is vacuously empty, so that rule reports itself discharged while never having run.
The population claim therefore sits **upstream** of every check the corpus offers here, and it is the one claim nothing prompts you to make with a command.

Two things keep it from being noticed.

**The conclusion is usually correct.**
Collisions are rare, so "nothing to collide with" is right most of the time, and being right is exactly what stops anyone examining the reason.
That makes this the shape [`fail-fast`](../principles/fail-fast.md)'s "A proxy that answers a narrower question passes the same way" describes: a test that is usually right, for a reason it never checked.

**A reviewer will not supply the missing half.**
The premise is about the *tracker* rather than about the diff, so it sits outside what a diff review reads at all --- which is [`fully-clean`](fully-clean.md)'s ratification case one step further out.
There a reviewer inherits the author's population and verifies its members;
here there are no members to verify, so a clean verdict says nothing whatever about the claim.

The tell is a first-person scope word: "no other PR **of mine**", "nothing else in flight", "the only open one".
Each names a population nobody counted, and "mine" is doing silent work --- it can mean opened by this session or held by this account, and those differ by however many sessions are running.

Derive the population first, then the intersection over it, and publish both counts.
`scripts/pr-sweep.py` above already derives the live open-PR set, and it reports what it examined rather than only what it found, which is the property this case needs.

- **Do:** derive the population before the intersection, and report both counts --- "10 open PRs examined, 0 touching this file" is checkable, and "no others are open" is not.
- **Do:** say which population a scope word covers --- this session's PRs, the account's, or the repo's --- since the three differ.
- **Don't:** assert a set is empty from recollection;
  emptiness is the one claim that makes the derivation rule vacuous rather than merely unsupported.
- **Don't:** read a correct conclusion as evidence the premise held --- a collision-free result is the usual case whether or not anyone counted.

(Morrison-Lab/ai-config#1435, 2026-08-12.
Its PR body closed with "No other PR of mine is open, so there is no merge-order constraint and nothing to collide with", and the review confirmed the PR clean without touching that sentence.
Ten PRs were open at merge time, eight of them under the same account.
The post-merge sweep derived each one's file set against its own merge base and found 0 of 10 touching `shared/writing/ambiguous-reference.md` --- so the conclusion held and its stated reason did not.)

## A qualifier clause is a second figure, measured somewhere else

The section above governs a population nobody counted.
This governs one that *was* counted, correctly, for the figure it was counted for --- alongside a second figure in the same sentence that was measured somewhere else.

A total usually arrives with a qualifier attached: "ten open, eight of them under the same account", "forty files changed, six of them generated".
The qualifier reads as a decomposition of the total, because that is what the grammar says, and nothing in the sentence tells a reader that the subset came from a different query than the total did.

**Deriving one number in a sentence discharges the feeling of having derived the sentence.**
That is the whole mechanism.
The total is the figure the claim was about, so it gets the query, the timestamp, and the care.
The qualifier is a detail added while writing, so it gets whichever number is nearest to hand --- and that number is frequently a real one, correctly derived, against a population that has since moved.

Both figures are then individually defensible, which is why re-reading finds nothing.
Only asking **which population each was measured in** separates them.

[`ardi`](ardi.md)'s pre-push checklist already carries the nearest rule, requiring every number in a PR body to be re-derived by command and stating that "a base figure owes its own derivation rather than riding on the delta's".
Read that rather than re-deriving it here.
Two things differ.
That rule is scoped to the **PR body**, the artifact nothing re-measures, whereas a subset figure in a shared fragment ships as prose and is read long after the tracker state it described.
And base-versus-delta is one instance of a general shape: any two figures in one sentence can name different populations, whatever their arithmetic relationship looks like.

- **Do:** run a separate query for a subset figure, and name the moment both figures were measured at.
- **Do:** treat a qualifier clause as a second claim owing its own derivation, rather than as a decomposition of the figure it follows.
- **Don't:** carry a subset count measured at one moment into a sentence whose total names another --- the two populations differ by whatever moved in between.
- **Don't:** read "I derived the number in this sentence" as covering the sentence.
  The figure you derived is the one you were thinking about.

(Morrison-Lab/ai-config#1437, 2026-08-12, review finding 1.
The case record directly above shipped reading "Ten PRs were open at merge time, seven of them under the same account", and now reads "eight of them".
The total was derived against #1435's merge instant, `21:50:27Z`, and was right.
The subset was not: at that instant `d-morrison` held eight of the ten (#1393, #1411, #1413, #1417, #1420, #1421, #1422, #1436), with `claude[bot]` holding #1427 and #1434.
Seven is the same-account count of a **different** population --- the nine PRs left after #1436 merged at `21:54:09Z`, four minutes later --- so it was a real figure, correctly derived, about a moment the sentence was not describing.
Re-derived here from `list_pull_requests` over `created_at`/`closed_at` rather than from the reviewer's own number, per [`metacognitive-monitoring`](metacognitive-monitoring.md)'s rule that a finding's conclusion is the sound half and its particulars are not.)

## A count and its label can disagree about whether the subject is a member

The two sections above both fail somewhere in the derivation.
One never derives the population at all.
The other derives two figures and measures them in different places.
This one derives correctly, once, and attaches the result to a claim about a different set.

A query returns a **population**.
A claim frequently quantifies over that population **minus the subject** --- the other PRs, the remaining files, everything else in flight.
Nothing in the query knows you meant to exclude yourself, so its answer is right about the set it counted and wrong about the set the sentence names.

**The tell is a scope word attached to a figure that came from a whole-population query.**
"Other", "remaining", "else", "besides", "the rest".
Each one silently subtracts the subject from the set being described, while the number beside it still includes the subject.

That is also the empty-set section's tell, and the two point at opposite defects.
There a scope word marks a population **nobody counted**, so deriving it is the whole fix.
Here the population **was** counted, so the scope word marks a correct count of the wrong set, and the fix is a subtraction rather than a query.

**Re-deriving the same total cannot catch this, which is what lets it survive a careful pass.**
The total is not the part that is wrong.
Running the query again returns the same number, so the check that would ordinarily settle a suspect figure confirms it instead.
[`ardi`](ardi.md)'s pre-push requirement to re-derive every number in a PR body is satisfied in full by a re-run that changes nothing.
So subtract the subject explicitly, or filter it out in the query, and state which population the figure counts.

**The cheapest check needs no query at all.**
A scope-word figure usually sits beside an enumeration of the same set --- a table, a list of numbers --- which is a second and independent statement of that count.
When a body carries both, they have to agree, and a figure that disagrees with the list under it is decidable by looking.

- **Do:** subtract the subject from a whole-population count before attaching a scope word to it, and name the population the figure counts.
- **Do:** compare a scope-word figure against any enumeration of the same set beside it, since the two state one count twice.
- **Don't:** read a re-derivation that returns the same total as confirming a figure labelled "other" --- the total is the half that was already right.
- **Don't:** reach for the empty-set section's remedy here;
  that one is discharged by deriving the population, and this one by subtracting from a population already derived.

(Morrison-Lab/ai-config#1455, 2026-08-13, review round 1, non-blocking.
Its "Merge order" section read "No constraint against the **5** other open PRs" and then listed four: #1452, #1422, #1420, #1393.
The finding, verbatim: "A live count shows 5 open PRs *total* including #1455 itself, so there are 4 *other* open PRs, not 5 --- an off-by-one in the population count."
Re-derived here from `list_pull_requests` over `created_at`/`closed_at` rather than from the reviewer's own number, per [`metacognitive-monitoring`](metacognitive-monitoring.md)'s rule that a finding's conclusion is the sound half and its particulars are not: at #1455's creation, `20:22:48Z`, the open set was #1393, #1420, #1422, #1452, and #1455 itself --- 5 total and 4 others, unchanged at the review's own `20:30:47Z`.

The coincidence that hid it is worth naming, because it is what makes the re-derivation useless here.
The figure was carried from PR #1454's body, which had read "all 5 open PRs examined" over a five-row table whose first row was `**#1454** (this)` --- correct there, as a total *including* the subject.
That PR merged at `18:14:51Z` and #1455 opened at `20:22:48Z`, so one subject replaced another and the total stayed 5.
Re-deriving the total at #1455's own moment therefore returns the very figure that was wrong.)

## A closed population inside one file still needs deriving, not guessing

Everything above governs external sets --- PRs, issues, files matching a pattern --- that can grow while the work runs.
A population confined to one file, frozen at the commit being edited, cannot grow out from under you the same way.
That makes it tempting to search for the specific members a sweep expects to be affected, rather than deriving the whole set --- and the temptation runs backwards, because a **closed** population, per the closedness test above, is exactly the one a derivation can enumerate completely.

A back-reference sweep that bumps one section's ordinal (fifth to sixth, say) has to update every downstream reference to the old count.
The natural query names the strings the sweep expects to be stale --- the old ordinal word, the old count phrase --- and that query is unsound by construction: it can only match text that still says the *old* value, so a section whose own back-reference was never in the search terms passes the sweep untouched and collides with the section just bumped.

The remedy is this fragment's own rule, applied to a smaller population: derive every ordinal and count-word the file contains with one query covering the whole class, and read the resulting sequence for internal consistency, rather than searching for the handful of strings predicted to need a fix.

- **Do:** enumerate every ordinal or count-word in a file with one query covering the whole class, before touching any of them.
- **Do:** read the resulting sequence for collisions and stale back-references across the whole file, not only near the edit.
- **Don't:** grep for the specific old strings a sweep expects to be stale --- that query cannot match a value it was never told to expect.
- **Don't:** treat a within-file population as exempt from this fragment's rule merely because it cannot grow while you work;
  it still needs deriving rather than guessing.

(Morrison-Lab/ai-config#1864, 2026-08-21, review comment [3834448521](https://github.com/Morrison-Lab/ai-config/pull/1864#discussion_r3834448521): a PR bumped `shared/workflow/verify-the-right-artifact.md`'s "interpreter's own defaults" section from "fifth" to "sixth adjacent artifact", correctly, but its own back-reference sweep grepped for `four recognizable shapes` and `a fifth adjacent` --- strings that, by construction, cannot match `sixth` or `The five above`.
The downstream section "A sixth: the fact that a check ran..." kept its stale ordinal and collided with the newly bumped one.
The author's own fix commit named the mechanism directly ([comment 3834476467](https://github.com/Morrison-Lab/ai-config/pull/1864#discussion_r3834476467)): "I grepped for the strings I *expected* to be stale...
Derive the population of ordinals; do not search for the ones you predict.")

## In review

Flag a brief, a plan, or a skill step that hands an agent a hard-coded list of PR or issue numbers to work through, where the tracker could gain another before the work finishes.
Ask for the query instead.
This is [`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md) applied to work items rather than to documentation: that fragment's "prose enumerations rot unnoticed" section is the same argument about a different artifact, and its remedy is the same one --- replace the list with a pointer, rather than refreshing the list and resetting the clock.

- **Do:** hand over the query that derives the set, and re-derive it once per pass.
- **Do:** state the examined count alongside any finding count, so a sweep that examined nothing is distinguishable from a clean one.
- **Don't:** hand an agent a list of item numbers when something else can add to that set while the work runs.
- **Don't:** treat "every item on my list was handled" as evidence that everything was handled --- that is the claim the list cannot support.

(Morrison-Lab/ai-config#960, 2026-07-30/31: agents were dispatched with enumerated PR numbers, and one brief said "#937, #939, #943, #946 are already CLEAN --- leave them alone", which was true when written.
Both #943 and #946 gained an open review thread within minutes, and nothing was watching them for 73 minutes.
Then #953 and #954 were opened by other sessions afterward, so no brief contained them, and #954 sat with two failing checks for 26 minutes.
Later still came #957.
Running the sweep built for this issue at 07:35Z reported #943 and #946 stalled at 83.5 and 81.7 idle minutes with unresolved threads, and #954 stalled with a genuinely failing `validate` --- the three PRs no list contained.)
