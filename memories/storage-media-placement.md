# Storage media placement: which drive a directory belongs on

Cross-machine rules for relocating data between drives on a multi-drive host.
The subject is not "how much space is free" but **what the destination is made of**, which is invisible in every size-ranked view of a filesystem.

## Rank relocation candidates by access pattern x destination media, never by size

- **Measured 2026-09-15, Windows 11 Pro 26200, this machine.**
  A "free space on `C:`" task ranked every directory by size and moved the largest movable ones to `D:`.
  `Get-PhysicalDisk` --- run only after the user asked "will it run slower on `D:`?" --- reported:

  | drive | device | media |
  |---|---|---|
  | `C:` | Samsung PM9A1 | NVMe SSD |
  | `D:` | TOSHIBA DT01ACA100 | 7200rpm SATA **spinning HDD** |

  By then `C:\Users\Work\.julia` (7.7 GB) had been moved to `D:\julia` with `JULIA_DEPOT_PATH` repointed and the `C:` source deleted, `C:\Users\Work\AppData\Local\R` (14 GB) had been copied to `D:\R`, and the WSL2 distro (19.5 GB, `ext4.vhdx`) was next.
  Every one of those is a random-small-file workload: an R `library()` call opens thousands of small files, Julia precompilation likewise, and a WSL2 ext4 image does constant small random I/O.
  Random 4K reads on a 7200rpm platter run roughly two orders of magnitude behind NVMe, so the size ranking had selected precisely the three worst candidates on the disk.

  The failure mode is what makes this worth an entry rather than a footnote.
  Nothing fails.
  The move succeeds, the toolchain still works, and the cost arrives weeks later as a diffuse "my machine got slow" with no event to attribute it to --- long after anyone would think to look at a completed cleanup task.

  - **Do:** classify each candidate by **access pattern** first, and only then by size.
    Cold, large, sequentially-read data (game installs, media libraries, archives, backups, ISOs, finished datasets) belongs on the HDD.
    Hot, random-small-file toolchain data stays on the SSD even when it is the biggest and most tempting target: language package libraries and depots (`.julia`, R's `win-library`, `site-packages`, `node_modules`, `.cargo`, `go/pkg/mod`, `.m2`, `.gradle`, `renv`), VM and container disk images (`.vhdx`, `.vmdk`, `.qcow2`, WSL's `ext4.vhdx`), and compiler/build caches --- anything a build, a REPL, or an `import` touches per invocation.
  - **Do:** say which side of that split each candidate is on, in the plan, before moving anything.
  - **Don't:** rank by `du`/`Get-ChildItem` size and take from the top.
    A size ranking is a ranking of *how much is reclaimed*, which is only half the objective;
    it carries no information at all about what the move costs.
  - **Don't:** treat "it still works after the move" as verification.
    The regression this entry is about is a latency regression, and a working `library()` call is consistent with a 100x slower one.

## The destination's media type is a precondition of the plan, not a detail to check later

- **Same incident.**
  `Get-PhysicalDisk` costs one command and under a second, and its answer determines whether the entire plan is correct or backwards.
  Discovering it late does not merely add a step: it invalidates work already done.
  Here the revert cost a 7.7 GB copy back, an environment variable to unset, and a deleted source directory that had to be reconstructed --- all of it work that the one-second query would have prevented.

  The general shape is that a fact which **selects between a plan and its opposite** is a precondition.
  It is not a refinement, an optimization, or something to confirm while the transfer runs.
  Preconditions are checked before the first irreversible step, and deleting a source directory is an irreversible step.

  - **Do:** run the check before the first byte moves, and record which drive is which in the plan.
    `Get-PhysicalDisk` alone prints **no drive letters**, so it cannot answer "is `D:` the slow one?" unaided.
    Joining it through the partition is necessary but not sufficient:

    ```powershell
    Get-Partition -DriveLetter C,D | Select-Object DriveLetter,
      @{n='Media';e={($_ | Get-Disk | Get-PhysicalDisk).MediaType}},
      @{n='Model';e={($_ | Get-Disk | Get-PhysicalDisk).FriendlyName}}
    ```

    The calculated properties are not decoration.
    Piping a partition straight through (`Get-Partition | Get-Disk | Get-PhysicalDisk | Format-Table`) projects the drive letter away, and returns rows in **disk** order rather than the order you asked for --- so on this machine it prints the TOSHIBA first and a reader taking it positionally concludes `C:` is the platter.
    That is the exact inverted claim this entry exists to prevent, reached by following the entry's own instruction.
    On Linux the equivalent is `lsblk -o NAME,ROTA,MOUNTPOINT`;
    `lsblk -d` suppresses partitions and so prints `ROTA` with nothing to attach it to. (Caught in adversarial review: the first draft of this entry, and of the hook's own note, gave the unjoined command --- the one command the entry exists to make people run.)
  - **Do:** ask, for any fact you are about to defer, whether learning it late would make already-done work wrong.
    If yes it is a precondition, whatever it costs to obtain.
  - **Don't:** begin with the largest item because it is the largest, intending to check the destination's suitability once something feels off.
  - **Don't:** delete a source until the destination has been confirmed to be the *right* destination, not merely a working one.

## A plan whose central assumption is never stated is a plan whose assumption is never checked

- **Same incident, and the reason it was caught at all.**
  "The two drives are interchangeable storage, differing only in free space" was load-bearing for every step, and it appeared nowhere: not in the plan, not in the reasoning, not in any message to the user.
  An unstated premise cannot be reviewed, by the user or by the agent that holds it, because there is no sentence to disagree with.
  What surfaced it was the user's question --- "did you move wsl?
  will it run slower on D?" --- which is an outside party guessing at the premise from the actions.
  That is not a review mechanism; it is luck, and it arrived three moves in.

  This is the same shape [`shared/workflow/incidents-dont-repeal-decisions.md`](../shared/workflow/incidents-dont-repeal-decisions.md) names for unexamined reasons --- "no one can rebut an argument that was never made" --- reached from the planning side rather than the decision side, and it is why [`shared/writing/fact-check-prose.md`](../shared/writing/fact-check-prose.md) asks for load-bearing unstated assumptions to be flagged.

  - **Do:** write the one sentence the whole plan rests on, explicitly, before executing it, and treat that sentence as the first thing to verify.
  - **Do:** read a user's clarifying question about a side effect ("will it be slower?", "is that safe?") as a possible hit on an unstated premise, and re-derive the premise rather than answering only the literal question.
  - **Don't:** let a premise stay implicit because it seems obvious --- obviousness is exactly the property that keeps it out of the plan and out of review.
  - **Don't:** answer the narrow question ("yes, WSL is still on C:") and resume the plan;
    the question is evidence the plan needs re-checking.

## Mechanism

[`hooks/warn-cross-drive-toolchain-move.py`](../hooks/warn-cross-drive-toolchain-move.py) is this entry's guard.
It warns, never blocks, on a `PreToolUse` `Bash`/`PowerShell` relocation command (`robocopy`, `xcopy`, `Move-Item`, `Copy-Item`, `cp -r`, `mv`, `rsync`, `wsl --import`/`--move`) whose **own command segment's** path arguments span two drive letters **and** name a toolchain path, when no media-type query appears earlier in the transcript.
Scoping the tokens to one segment is what keeps a size survey chained to an unrelated move from warning about the directory it merely measured.
It is deliberately narrow in four directions, and the first two are the ones the incident makes necessary: a cross-drive copy with no toolchain path (the ordinary backup, the media move) is silent, and so is one whose paths name a backup or archive location, because an HDD is the *correct* destination for both and a guard that cried wolf there would be worked around within a day.
Adversarial review added the other two: a rehearsal (`robocopy /L`, `-WhatIf`, `rsync -n`) moves nothing, and a path token in a neighbouring command segment belongs to a different command.
