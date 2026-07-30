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
set -eu

now=$(TZ=America/Los_Angeles date '+%Y-%m-%d %H:%M:%S %Z' 2>/dev/null || date '+%Y-%m-%d %H:%M:%S %Z')
utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

printf 'Current time -- local: %s | UTC: %s\n' "$now" "$utc"
printf 'Use the local value verbatim in recaps. Do not derive a local time from a UTC timestamp read out of an API response.\n'
