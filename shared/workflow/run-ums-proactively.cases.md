# Proactive UMS Case Records

Case records and measured baselines for [`run-ums-proactively.md`](run-ums-proactively.md).

## Stale records checker baseline and shallow clones

### Measured baseline (2026-08-16)

Running `python3 scripts/check-stale-records.py` against this repository measured:
- 503 files examined
- 3 orphans: `commands/release-pr.md`, `memories/MEMORY.md`, `references/cloud-setup/README.md`
- 181 generated wrappers and 2 root entry points exempt

All three orphans were inspected and confirmed benign (an index, a directory README, and a named command).

### Shallow clone behavior

Under a shallow clone (such as default `actions/checkout` with depth 1), `git log` cannot inspect past the fetch depth, so every file appears no older than the oldest fetched commit. The checker reports `age_informative: false` in `--json`. A full unshallow fetch (`git fetch --unshallow`) is required for informative age measurements.
