# Tool transport collapses doubled backslashes

Moved out of the auto-loaded `CLAUDE.md` (ai-config#3568), which keeps the rule and its pattern/anti-pattern pairs and links here for the mechanics, the reproducers, the platform measurements and the recurrence records.
The move changed three things and nothing else: two relative links were repointed for the new depth, every paragraph was reflowed by `scripts/semantic-line-breaks.py`, and the opening sentence's "above" was resolved to the section it used to sit below.

The sibling of the backtick hazard that `CLAUDE.md`'s "PowerShell CLI Command Safety" section covers, and the same class: content silently transformed between what you type and what the interpreter receives.

Inside a Bash-tool heredoc with a **quoted** delimiter (`<<'PY'`), which should be entirely literal, a doubled backslash `\\` arrives as a single `\`.
A single `\` survives intact.
So one level of unescaping is applied somewhere in transport.

**Scope it before relying on it: this is a property of the environment, not of heredocs.**
Measured 2026-08-22 on Windows 11 / MINGW64 through the Claude Code Bash tool.
A reviewer running the same cases in a GitHub Actions Linux runner could **not** reproduce any of it, and was right not to --- so a claim stated unconditionally here is false there, which is how a true observation becomes a wrong rule.
Test your own environment before trusting either answer.

The reproducer is one command and needs no interpreter, which is what rules out Python's own string parsing as the cause:

```
cat <<'EOF' > out.txt
a\\nb
c\nd
EOF
```

Both lines land in `out.txt` carrying **one** backslash: the doubled form collapsed, the single form survived.
Nothing but the transport touched it.

It fails silently and plausibly.
A patch script's `assert target in s` fails, which reads as a slightly-wrong anchor string --- so the natural response is to re-dump the region and retype the anchor, which fails identically.
The tell only appears on printing `repr()` of the constructed string.

The worse case is not a failed assert.
A heredoc that *writes* `\\d` into a regex emits `\d` --- a corrupted matcher with no syntax error and a green suite.
Anything writing regexes, escape sequences, or Windows paths through a heredoc is exposed, including a `jq` filter: `test("\\*\\*Claude finished")` reaches `jq` as `test("\*\*...")` and dies with `Invalid escape`.

Build the character rather than typing it:

```
B = chr(92)
def bs(t): return t.replace("@@", B)

# A NON-RAW literal is where this bites. Expressing one backslash inside one
# requires typing two, and that doubled form is exactly what collapses -- so
# the placeholder is doing real work here.
target = bs('print("done@@n")')
# -> the 15 characters  print("done\n")  ... with a real backslash,
#    which is what the file being patched actually contains.
```

The same collapse is already described twice.
[`algorithmatize-checks.rationale.md`](../workflow/algorithmatize-checks.rationale.md) records it for **this same transport** --- a shell heredoc feeding Python --- where `\\b` arrives as `\b` and becomes a **backspace**, worked through as a mutation that silently corrupts a guard's own regex.
[`address-every-comment.rationale.md`](../workflow/address-every-comment.rationale.md) records a genuinely different one, backslash quoting collapsing across nested shell layers.
What is new here is the trigger context --- a Bash-tool heredoc whose delimiter is quoted, so it should be literal --- and the placeholder remedy.
Cross-linked because a dupe-check keyed on this file's vocabulary would otherwise miss both.

A **raw** string needs none of this: `r"^\d+$"` is single backslashes throughout, and those survive.
The machinery is for the doubled form --- a non-raw literal, or any target that must itself contain a backslash escape.

- **Do:** route every literal backslash through `chr(92)` (or a placeholder token) when heredoc content must survive verbatim.
- **Do:** print `repr()` of a constructed string when a match inexplicably fails, rather than retyping the anchor.
- **Don't:** assume a quoted heredoc delimiter guarantees literal content --- on this platform, measured 2026-08-22, it does not.
- **Don't:** carry the claim to another platform without re-measuring;
  it did not reproduce in a Linux CI runner.
  It also did not reproduce in a Linux remote Claude Code container on 2026-09-01: the same reproducer left both backslashes of `a\\nb` intact under `repr()`.
- **Don't:** trust a green suite after writing a regex through a heredoc;
  read the emitted line back.

**Knowing this rule does not stop you tripping it, so add a check rather than trusting recall.**
Measured 2026-09-01: this file was loaded and had just been read when a heredoc'd Python edit wrote `'\\n\\n'` into a file, which arrived as the literal text `\n` and corrupted the script it was patching.
`ast.parse` caught it immediately, and the fix was the `chr(92)` placeholder this entry prescribes.
So the remedy works;
what fails is noticing that the moment has arrived, because nothing about typing an escape sequence announces itself as the trigger.
Run a parse or round-trip check after any heredoc'd edit that writes escape sequences.

- **Do:** parse-check (or read back) a file a heredoc just wrote with escapes in it.
- **Don't:** treat having read this file as the check --- it was, and the collapse happened anyway.

(Measured 2026-08-22; tracked as [ai-config#1923](https://github.com/Morrison-Lab/ai-config/issues/1923).
Cost three identical failed patch attempts before the cause was visible, then recurred immediately in a `jq` filter reading a PR review body.)

**2026-09-08 recurrence, twice in one session --- believed pattern and displacing fact, stated as their own pair.**
Believed pattern: typing `"\\n"` inside a heredoc body reaches the interpreter as the two-character escape sequence it was typed as.
Displacing fact: on this transport it reaches the interpreter as `"\n"`, a real newline landing inside what was meant to be a literal string.
First instance: a `printf "...\n"` line, composed inside a heredoc that assembled a markdown snippet, had its `\n` collapse to a literal newline in the emitted snippet.
Second instance: a Python-heredoc edit writing `"\\n"` escapes into a test fixture produced literal newlines instead, yielding a `SyntaxError` that was pushed to a PR before being caught.

- **Do:** build the character with `chr(92)` (or a placeholder token) before it enters a heredoc body, and print `repr()` of the constructed string before writing it.
- **Don't:** type a doubled backslash directly inside any heredoc body, quoted delimiter or not.

`hooks/warn-heredoc-doubled-backslash.py` is the mechanism this recurrence produced: a warn-only `PreToolUse` guard on the `Bash` tool matcher that scans a command's heredoc bodies for a doubled backslash and names the offending line, so the rule fires at composition time instead of relying on having read this file. (Tracked as [ai-config#3362](https://github.com/Morrison-Lab/ai-config/issues/3362).)

**The rule has an inverse, and knowing the rule is what produces it.**
Everything above argues one direction:
a doubled `\\` typed into a heredoc body can arrive as a single `\`.
Every **Don't** here is about under-escaping.
So the natural compensation, for a reader who has absorbed all of it, is to
double the escapes on purpose --- which is wrong on every transport that does
not collapse, and this file has already measured one of those.

Measured 2026-09-15, in a Linux remote Claude Code container, the exact
environment the 2026-09-01 bullet above records as **not** collapsing.
A Python converter's table pass was written through a heredoc with its escapes
pre-doubled: `r"\\\\"` reached the file where `r"\\"` was meant, and
`r"\\hline"` where `r"\hline"` was meant.
Nothing collapsed, so nothing corrected them.

**The doubled form is not a safer version of the prescribed remedy.**
Building the character with `chr(92)` is transport-agnostic and correct either
way; doubling is a different move, wrong on exactly the transports where the
documented hazard is absent.
That asymmetry is why the compensation instinct has to be named rather than
left to follow from the remedy.
Building the character does not imply doubling it,
and the argument above is what makes doubling feel implied.

**The failure mode is quieter than the collapse case, because the corrupted
literals were anchors rather than output.**
`str.count()` and `str.partition()` over a four-backslash literal simply match
nothing.
The function returned its input unchanged, the converter exited 0, and its own
summary line reported `0 table(s) unruled` --- which reads as "no tables needed
it", not as "the pass never fired".
A corrupted regex at least tends to throw or to mismatch visibly;
a corrupted anchor reports an honest zero.

**Reading `grep` output is not the check, and it is the one that feels like
one.**
The literals here were "verified" by grepping the written file and reading the
result.
Backslash counts in unhighlighted terminal output are close to unreadable, so
the grep ran, returned the wrong-but-plausible line, and was misread --- which
is indistinguishable from a grep that confirmed the literal.
`repr()` is already prescribed above for a failing match;
it is equally the check for a literal you believe is correct.

- **Do:** build every literal backslash with `chr(92)` or a placeholder,
  whatever the transport is known to do.
- **Do:** print `repr()` of the emitted literal, rather than grepping for it.
- **Do:** distrust a pass that reports zero work done, when you did not first
  confirm it fires on a known-positive input.
- **Don't:** double escapes as compensation --- that is not the remedy above,
  and it is wrong wherever the hazard is absent.
- **Don't:** read this file's argument as making the doubled form the safe
  default;
  it is the failing form in both directions, which is why the hook flags it
  regardless of transport.

`hooks/warn-heredoc-doubled-backslash.py` needs nothing for this direction: it
says the transport *can* collapse and prescribes building the character, both
direction-neutral.
It fires on the doubled form either way, which is the right behaviour here ---
the doubled form is what is wrong, not the collapse.

**A heredoc that writes SOURCE CODE has two parse layers, and there the doubled
form is not the failing form --- it is the arithmetic.**
Everything above is about content that must survive verbatim, where one layer
sits between what you type and what the interpreter sees.
A generator adds a second: the heredoc feeds Python, and the string Python
writes is itself Python source that will be parsed again.
`"\\n"` in the generator is then exactly right, because it puts `\n` in the
generated file, which that file parses as a newline.
Neither the collapse rule nor its inverse applies, and both of them read as
though they do.

The danger is diagnostic rather than mechanical, which is why it needs saying
after everything above rather than being derivable from it.
Measured 2026-09-17, in a Linux remote Claude Code container: a generator
heredoc carrying `"\\n"` produced a file containing `"\n"`, and that was read
as the transport having collapsed it --- a conclusion that would have contradicted
the 2026-09-01 and 2026-09-15 measurements recorded above, both of which are
correct.
The canonical interpreter-free reproducer, run in the same session, left
`a\\nb` intact.
So the wrong artifact was consulted: a two-layer edit cannot measure a
one-layer transport, and it is the artifact nearest to hand at exactly the
moment the question arises.

Counting the layers first settles it and costs nothing.
Ask how many times the text will be parsed between the keyboard and the
behaviour, and expect one doubling per layer beyond the first.
Then confirm the outcome rather than the theory, by exercising the generated
code --- here, the denial message printed with a real line break, which no
amount of reasoning about backslashes establishes.

- **Do:** count the parse layers before judging whether a doubled escape is
  wrong.
- **Do:** measure a transport with the interpreter-free reproducer above, never
  with a generator edit that happens to be in front of you.
- **Do:** confirm the generated code behaves, rather than confirming the
  literal looks right.
- **Don't:** read a correct two-layer escape as evidence about the transport
  --- that is how a true measurement gets overturned by a wrong one.
- **Don't:** read the hook's warning on a generator heredoc as a defect;
  it cannot count layers, and flagging the form regardless is the behaviour
  the section above asks for.


(Tracked as [ai-config#3710](https://github.com/Morrison-Lab/ai-config/issues/3710).)
