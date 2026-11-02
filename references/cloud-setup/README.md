# Reference: Claude Code cloud-session "Setup script"

A reviewed, revised reference copy of an **environment Setup script** for
[Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)
(claude.ai/code) cloud sessions. The original came from an R / Quarto / Julia
research project; this copy lives here as a worked example to crib from when
setting up a new repo's cloud environment.

> **The lab's environment Setup script is pasted from this file** (Ezra, 2026-11-02).
> It includes the `# [lds]` additions that give the notes repos' sessions their
> render toolchain at build time. Edit it here, then paste it into the environment.
>
> **Otherwise this is reference material, not active config.** It is **not** wired into
> ai-config's own build and is **not** symlinked into `~/.claude` by
> `bootstrap.sh` (the `references/` dir is on its skip list). Copy the relevant
> parts into the target project; don't expect ai-config to run it.

## What this script is for

The **Setup script** is pasted (contents, not a path) into the web UI's
environment config for a repo. It runs **at environment-build time, before the
repo is checked out**, and the resulting container image is cached. It is the
right place for slow, repo-independent toolchain installs (system libraries, R,
Julia, Quarto/TinyTeX).

It is distinct from a **`SessionStart` hook** (`.claude/hooks/session-start.sh`,
the subject of the `session-start-hook` skill), which runs **after** checkout
on every session and is where repo-dependent, per-session work belongs
(`renv::restore()`, `Pkg.instantiate()`, symlinking config). The two are
complementary: build-time setup primes the image; the hook finishes the job
once the repo is on disk. See `cloud-setup.sh`'s header for how this split is
applied to the R/Quarto/Julia toolchain.

## Files

- [`cloud-setup.sh`](./cloud-setup.sh) — the revised script, with every change
  marked inline as `# [review]` and summarized in a header block.
- [`allowlist.txt`](./allowlist.txt) — the paste-ready egress allowlist for the
  environment's custom network policy (the hostnames from `cloud-setup.sh`'s
  header plus the runtime hosts `renv::restore()` needs, one per line with
  rationale).

## Review summary

The original script is **genuinely good** and unusually well-documented — its
header captures hard-won, environment-specific knowledge that is easy to lose:

- **TLS-intercepting proxy handling.** Points tools that bundle their own CA
  roots (rig/rustls, Deno/Quarto) at the system CA bundle via `SSL_CERT_FILE` /
  `CURL_CA_BUNDLE` / `DENO_TLS_CA_STORE`, and deliberately prefers apt/curl over
  rig/juliaup precisely because the former trust the system store.
- **Restricted-network realism.** A precise egress allowlist with a one-line
  justification per host, and the non-obvious facts behind them (Quarto comes
  from github.com not quarto.org; prebuilt Julia binaries exist *only* on
  julialang-s3, never on github.com).
- **Removing the image's broken `deadsnakes`/`ondrej` PPAs** before any
  `apt-get update`, which otherwise fails the whole build with exit 100.
- **Best-effort, non-fatal** Julia/Quarto/TinyTeX steps so a blocked host
  degrades gracefully (R + renv stay usable) instead of failing the build.
- **GitHub API rate-limit mitigation** for TinyTeX (token if present, otherwise
  retry across shared egress IPs) and **pinning tlmgr to a single CTAN mirror**
  so render-time LaTeX installs hit one allowlistable host.

The revision keeps all of that and applies six **behavior-preserving robustness
fixes**. No dependency, host, or package was changed (the apt list is still
verbatim from the project's verified CI workflow).

| # | Finding | Fix in the revised copy |
|---|---------|-------------------------|
| 1 | Hard-coded `sudo` aborts with exit 127 on images where the Setup script runs **as root with no `sudo` binary** — a common cloud configuration. | Resolve a `$SUDO` prefix once: empty when already root, `sudo` otherwise, with a clear error if neither works. All privileged calls use `$SUDO`. |
| 2 | Quarto was only "best-effort" for the *download*; a failing `apt-get install "$tmp_deb"` ran **outside** the `if` condition and so **aborted the whole build** under `set -e`, contradicting the stated intent. | Fold the `apt-get install` into the success condition (matching the Julia step), so any failure warns and continues. |
| 3 | `renv` was reinstalled on **every** build/resume even when already present. | Guard with `requireNamespace("renv")` — install only if missing. |
| 4 | `quarto install tinytex` re-ran its slow, rate-limit-prone install on every build even when TinyTeX was already installed. | Detect an existing `tlmgr` (PATH or `~/.TinyTeX`) and skip the reinstall, while still re-pinning the CTAN mirror. |
| 5 | The Julia banner echoed `${JULIA_MINOR:-1.12}` one line **before** `JULIA_MINOR` was assigned. | Resolve `JULIA_MINOR` before the `echo`. |
| 6 | If GitHub's `releases/latest` redirect format ever changes, `${quarto_ver##*/tag/v}` leaves a full URL, which is then spliced into a download URL. | Sanity-check `quarto_ver` against a `N.N…` pattern before building the URL; otherwise fall straight through to the warning. |

### Noted, not changed

Left as-is to avoid diverging from the project's CI-verified source of truth,
but worth a glance when adapting the script to a new base image:

- **`libtiff5-dev`** is a transitional name on Ubuntu 24.04 (noble); newer
  images expose the headers as `libtiff-dev`. The list is copied verbatim from
  the verified CI workflow, so it's kept here — re-check it if an `apt-get
  install` ever fails on this package.
- **`chromium`** on noble can be a snap shim that doesn't run headless without
  snapd; fine if it matches what CI uses, but verify if Chromium-based rendering
  (chromote/webshot) misbehaves.

## Validation

`bash -n` passes, and the changed constructs were unit-tested in isolation:
empty-`$SUDO` expansion (including `echo … | $SUDO tee`), `find_tlmgr` returning
non-zero under `set -e` without aborting, and the `quarto_ver` version regex
(accepts `1.9.38`; rejects an empty string, an un-stripped URL, and a
`v`-prefixed value). The download/install steps themselves require the live
cloud network/proxy and so aren't exercised here.
