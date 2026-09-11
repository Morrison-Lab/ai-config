# Timestamp recaps in local time

Moved out of the auto-loaded `CLAUDE.md` (ai-config#3568), which keeps the rule and its pattern/anti-pattern pairs and links here for the platform mechanics, the surfaces the drift reaches, and the measured cases.
The move changed three things and nothing else: one relative link was repointed for the new depth, two em-dashes were converted to the corpus's spaced ` --- `, and every paragraph was reflowed by `scripts/semantic-line-breaks.py`.

When printing a status recap or summary, include a timestamp in the user's local time zone (Pacific Time, `America/Los_Angeles` --- get it from `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`;
the explicit `TZ` enforces PT on a machine set to any other zone).
This makes "as of when" unambiguous when the user reads the recap later.
Each reading expires immediately: run the command fresh for every recap rather than extrapolating elapsed time from a prior reading.
A single honest measurement earlier in the session is what most easily licenses an invented timestamp later, because the memory of having consulted the clock obscures that the measurement has expired.

**The same drift hits a dated claim written into a file, not only a chat recap.**
A "verified `<date>`" note added to a doc, a code comment, or a changelog entry during a long session is exactly as exposed to the UTC-versus-Pacific gap as a status recap is --- run the same clock check before typing the date into the file, not only before a chat update.
The risk peaks late in the day Pacific (roughly after 17:00), once UTC has already rolled over to the next calendar date.

**Check the `%Z` in the output.**
On Windows Git Bash the `TZ` override silently falls back to GMT (any IANA zone name does), so the command above prints GMT, not PT.
If the suffix isn't PDT/PST, fall back to plain `date` when the machine's system zone is already Pacific.
Otherwise use PowerShell: `[System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Pacific Standard Time')`.
Note the output format differs from the bash command --- it's a raw `DateTime` with no timezone-abbreviation field, so format it yourself if you need the `PDT`/`PST` suffix or a compact form.

**The same drift also hits a clock time typed into a forge comment --- an issue or PR comment, and a claim comment especially, since sessions habitually stamp their claims with a start time.**
A claim comment, a "working on this" status update, or a session-notebook heading is a dated claim exactly like the file edit above, so it needs the same fresh reading, not a reuse of whatever the last real reading said.
The near-miss is inferring the current time from how much work has happened since that last reading --- counting elapsed tool calls, or a rough sense of "it's been a while" --- rather than running the clock command again.
That inference feels safe because the earlier reading really was measured, but the clock keeps moving while a tool-call count does not track it, so the two drift apart the same way an unrefreshed chat timestamp does, and the drift compounds across several comments posted in sequence from the same stale reading. (Measured 2026-09-01: one real reading at 12:02 PDT was followed by claim comments on wai#81, wai#96, and wai#95 stamped "12:15 PT", "12:40 PT", and "12:58 PT" and by notebook headings "12:25", "12:55", "13:20", all extrapolated from elapsed tool calls.
The next real reading, taken when a PR head commit's timestamp was needed, came back 12:21 PDT --- up to an hour behind the invented stamps.
The brief that dispatched this entry itself asserted that `claim-pr` inserts the timestamp, which the skill's templates do not do.
The review caught it, and it is the same class of unmeasured claim.)

**Run the clock so its value lands in the transcript, not only in a file.**
A command of the shape `t=$(TZ=America/Los_Angeles date "+%H:%M %Z")` followed by a heredoc writing `$t` into a notebook does read the clock, and you still never see the reading --- so the next stamp you type comes from a sense of elapsed work exactly as if no command had run.
A reading you cannot quote is not a reading, however honestly it was measured.

- **Do:** run the clock command again immediately before typing a time into a forge comment, exactly as before a chat recap or a file edit.
- **Do:** print the reading --- run the clock command on its own, so the value comes back in a tool result you can read and quote.
- **Don't:** infer a clock time from the number of tool calls or actions taken since the last real reading.
- **Do:** derive a time written into a file from a `date` read in the *same* command that writes it, so a heredoc heading cannot be typed from memory.
- **Don't:** treat a reading captured into a shell variable whose only destination is that file as a measurement for a chat or comment claim --- the session never observes it, so print it as well (`echo "$now"`) when the same reading will be quoted.

See [`CLAUDE.cases.md`](../../CLAUDE.cases.md), "A notebook heading typed from the last reading, with the rule loaded".

Two hooks are this rule's mechanism, one per surface.
`hooks/no-unmeasured-clock-claim.py` reads the reply at `Stop`.
`hooks/flag-unmeasured-timestamp.py` reads a comment body at `PreToolUse`, on the `gh` comment and review commands and on the `mcp__github__` comment tools that `hooks/require-agent-disclosure.py` covers.
Each warns, never blocks, when the text states a Pacific clock time and no clock read appears in the transcript since the turn began, naming the stamp and the command to run before restating it (ai-config#2903, filed on the same day the rule above was written and broken again).

