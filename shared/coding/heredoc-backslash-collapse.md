# Tool transport collapses doubled backslashes

Moved out of the auto-loaded `CLAUDE.md` (ai-config#3568), which keeps the rule and its pattern/anti-pattern pairs;
this file carries the mechanics, the reproducers, the platform measurements and the recurrence records.
Nothing here was rewritten in the move.


The sibling of the backtick hazard above, and the same class: content silently transformed between what I type and what the interpreter receives.

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
Cross-linked because a dupe-check keyed on this section's vocabulary would otherwise miss both.

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
Measured 2026-09-01: this section was loaded and had just been read when a heredoc'd Python edit wrote `'\\n\\n'` into a file, which arrived as the literal text `\n` and corrupted the script it was patching.
`ast.parse` caught it immediately, and the fix was the `chr(92)` placeholder this entry prescribes.
So the remedy works;
what fails is noticing that the moment has arrived, because nothing about typing an escape sequence announces itself as the trigger.
Run a parse or round-trip check after any heredoc'd edit that writes escape sequences.

- **Do:** parse-check (or read back) a file a heredoc just wrote with escapes in it.
- **Don't:** treat having read this section as the check --- it was, and the collapse happened anyway.

(Measured 2026-08-22; tracked as [ai-config#1923](https://github.com/Morrison-Lab/ai-config/issues/1923).
Cost three identical failed patch attempts before the cause was visible, then recurred immediately in a `jq` filter reading a PR review body.)

**2026-09-08 recurrence, twice in one session --- believed pattern and displacing fact, stated as their own pair.**
Believed pattern: typing `"\\n"` inside a heredoc body reaches the interpreter as the two-character escape sequence it was typed as.
Displacing fact: on this transport it reaches the interpreter as `"\n"`, a real newline landing inside what was meant to be a literal string.
First instance: a `printf "...\n"` line, composed inside a heredoc that assembled a markdown snippet, had its `\n` collapse to a literal newline in the emitted snippet.
Second instance: a Python-heredoc edit writing `"\\n"` escapes into a test fixture produced literal newlines instead, yielding a `SyntaxError` that was pushed to a PR before being caught.

- **Do:** build the character with `chr(92)` (or a placeholder token) before it enters a heredoc body, and print `repr()` of the constructed string before writing it.
- **Don't:** type a doubled backslash directly inside any heredoc body, quoted delimiter or not.

`hooks/warn-heredoc-doubled-backslash.py` is the mechanism this recurrence produced: a warn-only `PreToolUse` guard on the `Bash` tool matcher that scans a command's heredoc bodies for a doubled backslash and names the offending line, so the rule fires at composition time instead of relying on having read this section. (Tracked as [ai-config#3362](https://github.com/Morrison-Lab/ai-config/issues/3362).)

