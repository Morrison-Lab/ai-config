#!/bin/sh
# Inject the current local time into context on every prompt.
#
# Rationale: CLAUDE.md requires status recaps to carry a Pacific-time
# timestamp. Getting one means running `date`, and a model that "knows"
# roughly what time it is will confidently write a wrong one instead --
# which is exactly what happened on 2026-07-29, when UTC values read off
# API responses were labelled PDT across several recaps.
#
# A rule cannot fix that, because a fabricated timestamp feels identical
# to a remembered one. Supplying the real value removes the opportunity.
#
# %Z is included deliberately: on some platforms the TZ override silently
# falls back to GMT, and printing the zone makes that visible rather than
# producing a plausible wrong label.
#
# ai-config#1918: printing it was not enough, because nothing CONSUMED it.
# On Windows Git Bash `TZ=America/Los_Angeles date` does not fail -- it
# succeeds and answers in GMT -- so the `||` fallback never engaged and the
# injected "local" value was GMT while claiming to be the value a Pacific
# recap should quote verbatim. That left the three requirements mutually
# unsatisfiable: quote it verbatim and the recap is not Pacific; convert it
# and the timestamp is derived. So the zone is now checked rather than merely
# printed, and this walks the exact ladder CLAUDE.md's "Timestamp recaps in
# local time" prescribes:
#
#   1. TZ=America/Los_Angeles date  -- correct where the TZ database is present
#   2. plain `date`                 -- correct where the SYSTEM zone is Pacific,
#                                      which is the Git Bash case above
#   3. PowerShell                   -- the documented last resort; it reports no
#                                      zone abbreviation of its own, so the
#                                      PDT/PST label is derived from the
#                                      Pacific zone's own DST rule rather than
#                                      guessed.
set -eu

FMT='+%Y-%m-%d %H:%M:%S %Z'

# Accept a reading only if it actually carries a Pacific zone abbreviation.
pacific() {
    case "$1" in
        *\ PDT|*\ PST) return 0 ;;
        *) return 1 ;;
    esac
}

now=$(TZ=America/Los_Angeles date "$FMT" 2>/dev/null || true)

if ! pacific "$now"; then
    now=$(date "$FMT" 2>/dev/null || true)
fi

if ! pacific "$now"; then
    now=$(powershell -NoProfile -Command "
        \$tz = [System.TimeZoneInfo]::FindSystemTimeZoneById('Pacific Standard Time')
        \$t  = [System.TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, \$tz)
        \$z  = if (\$tz.IsDaylightSavingTime(\$t)) { 'PDT' } else { 'PST' }
        '{0:yyyy-MM-dd HH:mm:ss} {1}' -f \$t, \$z
    " 2>/dev/null | tr -d '\r' || true)
fi

utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

if pacific "$now"; then
    printf 'Current time -- local: %s | UTC: %s\n' "$now" "$utc"
    printf 'Use the local value verbatim in recaps. Do not derive a local time from a UTC timestamp read out of an API response.\n'
else
    # Fail loudly rather than injecting a zone that is not Pacific. A wrong
    # label is worse than none: it reads as measured and licenses a recap
    # timestamp nobody can check. Naming the failure is what keeps the
    # no-unmeasured-clock-claim guard meaningful instead of discharging it
    # with a value that was never Pacific.
    printf 'Current time -- UTC: %s (no Pacific reading available: TZ database, system zone, and PowerShell all failed)\n' "$utc"
    printf 'Do NOT state a PDT/PST time in this turn without measuring it first.\n'
fi
