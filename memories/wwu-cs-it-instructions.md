# WWU CS IT's instructions for the lab's cluster use

Ezra, 2026-11-04 02:42 UTC (lds project thread, cai): "you must always follow WWU CS IT's instructions exactly unless I say otherwise".
That rule has no exception for convenience, speed or an existing design.
Only Ezra's own words in the current conversation lift it, for the one case he names.
`hooks/require-wwu-it-instructions.py` blocks cluster-job edits and commands until a session has read this file.

## The instructions on record

Recorded from Ezra's report of his 2026-10-26 conversation with Zach McGrew of WWU CS IT, after which Ezra set the CI plan:

1. The self-hosted runners stay on the lab's own machines (`cf463-01`, `cf463-02`).
   They submit CI jobs to the WWU CS clusters, including the lab clusters, through HTCondor.
2. Do not run runners directly on lab machines of the cluster.
3. Submit batch jobs, not thousands of individual jobs.
4. Avoid heavy home-directory I/O in jobs.
   Use HTCondor file transfer, so a job works in its execute node's scratch directory.

These four lines are what is written down; IT's exact words are not.
When a design question touches IT's wishes and this list does not settle it, ask Ezra for IT's exact words.
Do not paraphrase a question into a looser rule, and do not fill the gap with a guess about what IT would accept.

## Route notes (how jobs reach the cluster; not IT instructions)

- Working route: `ssh -p 922 morri313@csci-lab-head` with key `~/.ssh/id_ed25519_condor` from `cf463-02`, `GSSAPIAuthentication=no`, `+CSCI_GrpDesktop = True`.
  Desktops have Apptainer and R, no Quarto; set `request_disk`.
- `condor-batch` in `Morrison-Lab/gha` (the `condor-batch` composite action) is the CI route: one HTCondor job per workflow job, on `cse-head.cluster.cs.wwu.edu`.

## Known deviation to fix

`condor-batch` copies the whole checkout to the NFS home and runs the job there (`should_transfer_files = NO`), with `.uvpy`, `.uvcache` and render outputs on the home.
That contradicts item 4 and filled the 5 GB home quota on 2026-11-03 and 2026-11-04.
The fix is to stage a small tarball with HTCondor file transfer and run in the execute node's scratch directory.
