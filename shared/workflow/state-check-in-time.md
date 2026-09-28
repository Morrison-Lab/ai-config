# State the actual time when reporting a scheduled check-in

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#state-the-actual-time-when-reporting-a-scheduled-check-in) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When telling the user I've scheduled a wakeup or check-in (`ScheduleWakeup`, or an equivalent poll-later mechanism), state the clock time it fires at, not just the relative delay or a bare "I scheduled a check-in."
The tool result already returns a clock time (e.g. "Next wakeup scheduled for 08:22:00") --- surface that time in the chat reply instead of dropping it, converting to Pacific local time per [`CLAUDE.md`'s "Timestamp recaps in local time"](../../CLAUDE.md#timestamp-recaps-in-local-time) if the returned time is in a different zone.
"Scheduled a check-in to continue monitoring both" leaves the user unable to tell whether that's one minute away or twenty; "I'll check back at 08:22 PT (~4 min)" does not.
