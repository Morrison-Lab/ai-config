# KISS: finding simplification opportunities

Keeping things simple is a standing obligation, not a one-off cleanup.
The hard part is not agreeing with the principle;
it is spotting the specific places where the tree has drifted away from it.

`scripts/kiss_scan.py` turns that into a measurable work list.
It reports duplication and complexity with exact `file:line` locations,
so a simplification pass starts from evidence rather than from a hunch.

## Running the scan

