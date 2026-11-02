#!/usr/bin/env bash
#
# Setup script for Claude Code (claude.ai/code) cloud sessions.
#
# Paste the CONTENTS of this file into the environment's "Setup script" field
# (claude.ai web UI -> the environment for this repo). Do NOT point the field at
# `bash scripts/cloud-setup.sh`: the Setup script runs at environment-build time,
# before/independently of the repo checkout, so a repo path is not on disk yet
# and fails with "No such file or directory" (exit 127). This file is the
# version-controlled source of truth -- keep the web-UI copy in sync with it (and
# with .github/workflows/copilot-setup-steps.yml). The script is self-contained:
# it touches no repo files, so it works whether or not the repo is present.
#
# The default Claude Code template adds the `deadsnakes` and
# `ondrej/php` PPAs, which this R/Quarto project does not need and which broke
# apt (launchpad 403 / "no longer signed", plus a broken `add-apt-repository`).
# This script installs only what the project actually uses, with NO third-party
# apt repositories.
#
# Scope: system libraries + R + Julia + Quarto/TinyTeX + the `renv` package. It
# does NOT run the full `renv::restore()` or the `inst/julia` Pkg.instantiate() --
# those are heavy and are launched in the background by the SessionStart hook
# (scripts/restore_renv.sh) once the session is up and the repo is on disk.
# Together the two cover the whole toolchain.
#
# Source of truth for these steps: .github/workflows/copilot-setup-steps.yml
# (the GitHub Actions setup, verified in CI). Keep the two in sync when
# dependencies change.
#
# These commands target the Ubuntu (noble) base image used by Claude Code cloud
# sessions. The apt package list is copied verbatim from the CI workflow above.
# R is installed from CRAN's apt repo and Quarto from its .deb -- the plain-shell
# equivalents of the `r-lib/actions` and `quarto-actions` steps, both using the
# system CA store so they work behind a TLS-intercepting proxy. If a future base
# image or upstream installer changes, re-check the URL flagged "VERIFY" below.
#
# ---------------------------------------------------------------------------
# Revisions in this reference copy (vs. the original reviewed script). Each is
# marked inline with `# [review]`. They are behavior-preserving robustness
# fixes -- no dependency or host changed:
#   1. Root/sudo aware: run privileged steps via $SUDO, which is empty when
#      already root (the cloud Setup script often is) and "sudo" otherwise.
#      Avoids exit-127 aborts on images where root has no `sudo` binary.
#   2. Quarto install is now truly best-effort: the `apt-get install` of the
#      .deb is folded into the success condition, so a failure there warns and
#      continues (as the comments always intended) instead of aborting under
#      `set -e`.
#   3. Idempotent renv install: skipped when renv is already present, so
#      resume/rebuild runs don't reinstall it.
#   4. Idempotent TinyTeX: an already-installed TinyTeX skips the slow,
#      rate-limit-prone reinstall but still re-pins the CTAN mirror.
#   5. JULIA_MINOR is resolved before it is echoed, so the banner reports the
#      version actually used.
#   6. The resolved Quarto version is sanity-checked against a `N.N` pattern
#      before building the download URL, so a changed redirect format fails
#      fast into the warning instead of fetching a garbage URL.
#
# Additions (2026-11-02), marked `# [lds]`: the repo-independent part of the
# lds notes site's render toolchain, so a session needs none of it installed by
# hand. lds's own SessionStart hook (.claude/hooks/render-toolchain.sh) installs
# the rest, but only in a session rooted in /home/user/lds; a project session
# rooted at /home/user never runs it. The added pieces:
#   a. librsvg2-bin (rsvg-convert, which PDF handouts with SVG figures need);
#   b. the `typos` spell checker, from the crate-ci/typos GitHub release;
#   c. the core R packages every lds page needs (knitr, rmarkdown, reticulate,
#      remotes, lintr, JuliaCall), as Posit Package Manager binaries.
# Each is best-effort: a failure warns and the build continues.
# ---------------------------------------------------------------------------
#
# Network allowlist (for restricted cloud networks that cannot use 'Full'):
# the build, the background renv::restore() (scripts/restore_renv.sh), and
# in-cloud PDF rendering need these hosts reachable. apt repos (ubuntu/docker)
# and cloud.r-project.org are usually already allowed; add the rest to a custom
# allowlist:
#   packagemanager.posit.co                              CRAN packages (renv.lock's repo)
#   github.com                                           Quarto .deb + GitHub-sourced R pkgs + typos release
#   release-assets.githubusercontent.com                 GitHub release downloads (Quarto, TinyTeX, typos)
#   objects.githubusercontent.com  codeload.github.com   GitHub release/tarball downloads
#   api.github.com                                       renv GitHub pkgs + TinyTeX lookup (rate-limited unauth; set GH_TOKEN)
#   ctan.math.illinois.edu                               one pinned CTAN mirror (see CTAN_REPO below)
#   cloud.r-project.org                                  renv bootstrap/fallback (usually already allowed)
#   bioconductor.org                                     the 'recipes' package is tagged Source=Bioconductor in renv.lock
#   julialang-s3.julialang.org                           Julia runtime binaries (the ONLY host for prebuilt Linux Julia; matches julia-actions/setup-julia in CI)
#   pkg.julialang.org                                    Julia package server -- inst/julia Pkg.instantiate()/precompile() at session start
# NOTE: quarto.org is NOT required -- Quarto is fetched from github.com releases.
# NOTE: the Julia binaries are NOT on github.com (the JuliaLang/julia releases
#       attach only source tarballs), so julialang-s3.julialang.org genuinely
#       must be allowlisted for the Julia step below to work.

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Some cloud environments route HTTPS through a TLS-intercepting proxy whose CA
# is trusted by the system store (so apt/curl/R-via-libcurl work) but NOT by
# tools that bundle their own roots (rig/rustls, Deno/Quarto), which then fail
# with "invalid peer certificate: UnknownIssuer". Point such tools at the system
# CA bundle so their downloads succeed through the proxy.
export SSL_CERT_FILE="${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}"
export CURL_CA_BUNDLE="${CURL_CA_BUNDLE:-/etc/ssl/certs/ca-certificates.crt}"
export DENO_TLS_CA_STORE=system

# [review] Run privileged steps via $SUDO rather than a hard-coded `sudo`. The
# cloud "Setup script" frequently runs AS ROOT, where `sudo` is often not
# installed -- a literal `sudo` then fails with exit 127 and aborts the whole
# build under `set -e` before anything installs. Resolve once: empty when we are
# already root, "sudo" when we are not (and it exists), else fail with a clear
# message instead of a cryptic 127 later. (`$SUDO cmd` with an empty $SUDO word-
# splits to just `cmd`, which is what we want.)
if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  echo "ERROR: not running as root and 'sudo' is not installed; cannot install" >&2
  echo "       system packages. Run this where root or sudo is available." >&2
  exit 1
fi

echo "==> Removing broken third-party apt sources (deadsnakes, ondrej/php)"
# The cloud base image ships these launchpad PPAs preconfigured in
# /etc/apt/sources.list.d/. Their signing now returns 403 ("no longer signed"),
# so ANY `apt-get update` fails with exit 100 before installing anything -- the
# PPAs are not added by this script, they are already on the image. This
# R/Quarto project needs none of them, so drop any apt source that points at a
# launchpad PPA / those repos. (Files are root-readable; removal needs root.)
while IFS= read -r src; do
  echo "    removing $src"
  $SUDO rm -f "$src"
done < <(grep -rlE 'launchpadcontent\.net|deadsnakes|ondrej' \
          /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null || true)

echo "==> Installing system libraries (apt)"
# No third-party PPAs: this list is sufficient to build the project's R packages
# (mirrors copilot-setup-steps.yml). curl/ca-certificates are added so the R and
# Quarto download steps below work on a minimal base image.
# [lds] librsvg2-bin added: rsvg-convert, which lds's PDF handouts need.
$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  jags \
  libcurl4-openssl-dev \
  libssl-dev \
  libxml2-dev \
  libfontconfig1-dev \
  libharfbuzz-dev \
  libfribidi-dev \
  libfreetype6-dev \
  libpng-dev \
  libtiff5-dev \
  libjpeg-dev \
  chromium \
  cmake \
  libgit2-dev \
  libnode-dev \
  libx11-dev \
  pandoc \
  poppler-utils \
  tesseract-ocr \
  tesseract-ocr-eng \
  librsvg2-bin

echo "==> Installing R (latest release) from the CRAN apt repository"
# Install R from CRAN's apt repo rather than rig: apt uses the system CA store,
# which the proxy above is trusted by (the system-library install already proved
# apt works), whereas rig/rustls rejects the proxy cert ("UnknownIssuer"). This
# is the documented way to get the latest R on Ubuntu and matches setup-r's
# 'release'. Needs cloud.r-project.org reachable -- which R needs anyway to
# install packages.
if ! command -v R >/dev/null 2>&1; then
  . /etc/os-release
  $SUDO install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc \
    | $SUDO tee /etc/apt/keyrings/cran_r.asc >/dev/null
  echo "deb [signed-by=/etc/apt/keyrings/cran_r.asc] https://cloud.r-project.org/bin/linux/ubuntu ${VERSION_CODENAME:-noble}-cran40/" \
    | $SUDO tee /etc/apt/sources.list.d/cran-r.list >/dev/null
  $SUDO apt-get update
  $SUDO apt-get install -y --no-install-recommends r-base r-base-dev
fi

echo "==> Installing the renv package"
# The SessionStart hook (scripts/restore_renv.sh) calls renv::restore(), which
# requires renv itself to be present. renv is pure R (no compiled code), so a
# source install from CRAN is fast and distro-agnostic. The full library restore
# is intentionally left to that background hook -- it reads renv.lock and exceeds
# the setup script's cache-build budget.
# [review] Idempotent: skip the install when renv is already present so re-runs
# (resume/rebuild on the cached image) don't reinstall it. NOTE: $SUDO installs
# into the system R library, which is correct for this container build; an
# adapter doing a per-USER R install should drop $SUDO so renv lands in the
# user library instead.
$SUDO Rscript -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", repos = "https://cloud.r-project.org")'

# [lds] The core R packages every lds page needs. Posit Package Manager serves
# Linux binaries, so this takes about a minute, not the compile time of a CRAN
# source install. The rest of lds's packages (about 100) are installed by lds's
# own SessionStart hook, which reads them from the render workflows so it never
# drifts from CI. Best-effort: a failure warns and the build continues.
echo "==> Installing the core R packages for the lds notes site"
if ! $SUDO Rscript -e '
  options(repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/noble/latest"))
  needed <- c("knitr", "rmarkdown", "reticulate", "remotes", "lintr", "JuliaCall")
  missing <- setdiff(needed, rownames(installed.packages()))
  if (length(missing) > 0) install.packages(missing)
  stopifnot(all(needed %in% rownames(installed.packages())))
'; then
  echo "WARNING: could not install the core R packages for lds (reticulate, knitr, ...)." >&2
  echo "         Check that packagemanager.posit.co is allowlisted (see header)." >&2
fi

# [review] Resolve JULIA_MINOR BEFORE it is referenced in the banner below, so
# the echo reports the version actually installed (the original echoed it one
# line before assigning the variable).
JULIA_MINOR="${JULIA_MINOR:-1.12}"
echo "==> Installing Julia (latest ${JULIA_MINOR}; matches julia-actions/setup-julia in CI)"
# The package's Julia out-of-core backend (inst/julia -- used by the streaming
# weighted-risk helpers) needs a Julia runtime. Mirror CI's
# `julia-actions/setup-julia@v3` (version '1.12'). Download the OFFICIAL binary
# tarball from julialang-s3.julialang.org over curl (system CA, so it works
# through the TLS-intercepting proxy -- same approach as the Quarto .deb below).
#
# We deliberately do NOT use juliaup: its rustls HTTP client rejects the proxy
# cert (the same rig/Deno "UnknownIssuer" failure noted at the top). We also
# cannot mirror from github.com (the way Quarto does): the JuliaLang/julia
# GitHub releases attach only SOURCE tarballs, never prebuilt Linux binaries --
# those live solely on julialang-s3. The `<minor>-latest` tarball always
# resolves to the newest patch of that minor, so there is nothing to pin.
#
# REQUIRES julialang-s3.julialang.org in the network allowlist (see header);
# without it the download returns 403 "Host not in allowlist". Best-effort: a
# failure warns but does not abort (R + renv stay usable). VERIFY the path
# scheme against https://julialang.org/downloads/ if a future base image breaks.
if ! command -v julia >/dev/null 2>&1; then
  case "$(dpkg --print-architecture)" in
    amd64) julia_arch=x64;     julia_libc=x86_64 ;;
    arm64) julia_arch=aarch64; julia_libc=aarch64 ;;
    *)     julia_arch="";      julia_libc="" ;;
  esac
  julia_tgz="$(mktemp --suffix=.tar.gz)"
  # Chain download+unpack with && inside the `if` so any failure (a 403, a bad
  # arch, a truncated tarball) falls through to the warning instead of aborting
  # the build under `set -e`, and the temp file is always cleaned up afterwards.
  if [ -n "$julia_arch" ] \
     && curl -fsSL \
          "https://julialang-s3.julialang.org/bin/linux/${julia_arch}/${JULIA_MINOR}/julia-${JULIA_MINOR}-latest-linux-${julia_libc}.tar.gz" \
          -o "$julia_tgz" \
     && $SUDO install -d -m 0755 /opt/julia \
     && $SUDO tar -xzf "$julia_tgz" -C /opt/julia --strip-components=1 \
     && $SUDO ln -sf /opt/julia/bin/julia /usr/local/bin/julia; then
    :
  else
    echo "WARNING: Could not install Julia from julialang-s3.julialang.org. The" >&2
    echo "         inst/julia out-of-core backend will be unavailable; R + renv" >&2
    echo "         remain usable. Add julialang-s3.julialang.org to the network" >&2
    echo "         egress allowlist (see header) -- the prebuilt Linux binaries" >&2
    echo "         are not mirrored on github.com -- then rebuild." >&2
  fi
  rm -f "$julia_tgz"
fi
# NOTE: the per-project Julia packages (inst/julia, e.g. CSV.jl) are NOT
# instantiated here -- this setup script runs before the repo is checked out, so
# inst/julia is not yet on disk. Instantiate them once per session from the
# SessionStart hook (the Julia analog of renv::restore), which DOES run after
# checkout, e.g.:
#   julia --startup-file=no --project=inst/julia \
#     -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
# That step downloads from pkg.julialang.org (allowlist it; see header) and
# honors SSL_CERT_FILE for the proxy CA -- export it in the hook as done above.

echo "==> Installing Quarto"
# Plain-shell equivalent of quarto-dev/quarto-actions/setup@v2 (tinytex: true).
#
# Fetch the Quarto .deb from the quarto-cli GitHub release, NOT from quarto.org:
# on restricted cloud networks the whole quarto.org domain is blocked (HTTP 403),
# while github.com is reachable (verified in real cloud sessions, issue #284).
# Resolve the version from the /releases/latest redirect Location rather than the
# GitHub API (api.github.com is rate-limited/blocked). BEST-EFFORT: if it still
# fails, finish the build with a warning (R + renv are already usable) instead of
# aborting. VERIFY against https://github.com/quarto-dev/quarto-cli/releases.
quarto_ok=true
if ! command -v quarto >/dev/null 2>&1; then
  arch="$(dpkg --print-architecture)"
  tmp_deb="$(mktemp --suffix=.deb)"
  # Clean up the temp .deb even if a download or apt-get fails under `set -e`.
  trap 'rm -f "$tmp_deb"' EXIT
  # ".../releases/tag/v1.9.38" -> "1.9.38"; reads the redirect Location only, so
  # it stays on github.com and never touches api.github.com.
  quarto_ver="$(curl -fsS -o /dev/null -w '%{redirect_url}' \
    https://github.com/quarto-dev/quarto-cli/releases/latest 2>/dev/null || true)"
  quarto_ver="${quarto_ver##*/tag/v}"
  # [review] Two robustness fixes vs. the original:
  #   (a) sanity-check that $quarto_ver looks like a version (N.N...) before
  #       building the URL, so a changed redirect format fails fast into the
  #       warning rather than fetching a garbage URL;
  #   (b) fold the `apt-get install` of the .deb INTO the success condition, so
  #       a failure there is best-effort (warn + continue) like the comment
  #       says, instead of aborting the whole build under `set -e`.
  if [ -n "$quarto_ver" ] \
     && printf '%s' "$quarto_ver" | grep -qE '^[0-9]+(\.[0-9]+)+$' \
     && curl -fsSL \
          "https://github.com/quarto-dev/quarto-cli/releases/download/v${quarto_ver}/quarto-${quarto_ver}-linux-${arch}.deb" \
          -o "$tmp_deb" \
     && $SUDO apt-get install -y --no-install-recommends "$tmp_deb"; then
    :
  else
    quarto_ok=false
    echo "WARNING: Could not install Quarto from github.com. R + renv are" >&2
    echo "         installed and usable; PDF rendering needs Quarto. Ensure" >&2
    echo "         github.com + release-assets.githubusercontent.com are" >&2
    echo "         allowlisted (see the header), then rebuild." >&2
  fi
fi

echo "==> Installing TinyTeX"
# TinyTeX is the LaTeX engine for PDF rendering. `quarto install tinytex`
# resolves the release via the GitHub API (api.github.com), which rate-limits
# UNauthenticated requests from shared cloud egress IPs (60/hr) and returns 403
# (verified in real cloud sessions, issue #284; CI sidesteps it with GITHUB_PAT).
# Authenticate with a token if one is present, otherwise retry -- successive
# attempts hit different egress IPs. Best-effort either way.
#
# [review] locate an existing tlmgr (system PATH or ~/.TinyTeX) once, reused
# both to skip a redundant reinstall and to pin the CTAN mirror afterwards.
find_tlmgr() {
  if command -v tlmgr >/dev/null 2>&1; then
    printf 'tlmgr\n'; return 0
  fi
  # Glob ~/.TinyTeX with `nullglob` set inside a subshell (so the option stays
  # local to this lookup) -- a no-match then expands to nothing instead of the
  # literal pattern, which sidesteps the SC2144/SC2045 glob footgun and needs no
  # per-iteration existence guard.
  local cand
  cand="$(shopt -s nullglob
          for c in "$HOME"/.TinyTeX/bin/*/tlmgr; do
            if [ -x "$c" ]; then printf '%s\n' "$c"; break; fi
          done)"
  if [ -n "$cand" ]; then printf '%s\n' "$cand"; return 0; fi
  return 1
}

if [ "$quarto_ok" = true ] && command -v quarto >/dev/null 2>&1; then
  GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-${GITHUB_PAT:-}}}"
  export GH_TOKEN
  if [ -n "$GH_TOKEN" ]; then
    echo "    (authenticating Quarto's GitHub API requests with a token)"
  fi
  tinytex_ok=false
  tlmgr_bin="$(find_tlmgr || true)"
  if [ -n "$tlmgr_bin" ]; then
    # [review] Idempotent: TinyTeX is already installed (e.g. a rebuild on the
    # cached image), so skip the slow, rate-limit-prone reinstall but still
    # re-pin the CTAN mirror below.
    tinytex_ok=true
    echo "    (TinyTeX already installed; skipping reinstall)"
  else
    for attempt in 1 2 3 4 5; do
      if quarto install tinytex; then
        tinytex_ok=true
        break
      fi
      echo "    TinyTeX attempt ${attempt} failed (likely a shared-IP GitHub API rate limit); retrying..." >&2
      if [ "$attempt" -lt 5 ]; then sleep $(( attempt * 3 )); fi
    done
    [ "$tinytex_ok" = true ] && tlmgr_bin="$(find_tlmgr || true)"
  fi
  if [ "$tinytex_ok" = true ]; then
    # Pin tlmgr to ONE CTAN mirror so render-time LaTeX-package installs hit a
    # single allowlistable host -- the default mirror.ctan.org rotates across
    # mirrors, which is awkward for a custom allowlist. Override CTAN_REPO if
    # your network requires a different mirror; verified single-host tlnet
    # mirrors include ctan.math.illinois.edu, mirrors.rit.edu/CTAN, and
    # mirror.math.princeton.edu/pub/CTAN.
    CTAN_REPO="${CTAN_REPO:-https://ctan.math.illinois.edu/systems/texlive/tlnet}"
    if [ -n "$tlmgr_bin" ]; then
      "$tlmgr_bin" option repository "$CTAN_REPO" \
        || echo "WARNING: could not pin tlmgr to ${CTAN_REPO}; render-time LaTeX installs will use the default mirror." >&2
      # [lds] lds's PDF handouts need these two LaTeX packages.
      "$tlmgr_bin" install luacolor lua-ul \
        || echo "WARNING: could not install luacolor and lua-ul; lds PDF handouts will fail to build." >&2
    else
      echo "WARNING: tlmgr not found after TinyTeX install; cannot pin the CTAN mirror." >&2
    fi
  else
    echo "WARNING: 'quarto install tinytex' failed after 5 attempts (GitHub API rate" >&2
    echo "         limit?). PDF rendering needs TinyTeX -- set GH_TOKEN/GITHUB_TOKEN in" >&2
    echo "         the environment, or rerun 'quarto install tinytex' later." >&2
  fi
fi

# [lds] The `typos` spell checker, which lds's pre-commit checklist runs.
# Same approach as Quarto: read the version from the /releases/latest redirect
# (not the rate-limited API), then fetch the musl release tarball. Best-effort.
echo "==> Installing typos"
if ! command -v typos >/dev/null 2>&1; then
  typos_arch="$(uname -m)"
  typos_ver="$(curl -fsS -o /dev/null -w '%{redirect_url}' \
    https://github.com/crate-ci/typos/releases/latest 2>/dev/null || true)"
  typos_ver="${typos_ver##*/tag/}"
  typos_tgz="$(mktemp --suffix=.tar.gz)"
  if printf '%s' "$typos_ver" | grep -qE '^v[0-9]+(\.[0-9]+)+$' \
     && curl -fsSL \
          "https://github.com/crate-ci/typos/releases/download/${typos_ver}/typos-${typos_ver}-${typos_arch}-unknown-linux-musl.tar.gz" \
          -o "$typos_tgz" \
     && typos_dir="$(mktemp -d)" \
     && tar -xzf "$typos_tgz" -C "$typos_dir" \
     && $SUDO install -m 0755 "$(find "$typos_dir" -type f -name typos | head -1)" /usr/local/bin/typos; then
    :
  else
    echo "WARNING: Could not install typos from github.com. lds's spell check" >&2
    echo "         (typos path/to/changed/files) will be unavailable." >&2
  fi
  rm -f "$typos_tgz"
fi

echo "==> Setup complete:"
R --version | head -1
if command -v julia >/dev/null 2>&1; then
  julia --version
else
  echo "julia: NOT installed (see WARNING above) -- allowlist julialang-s3.julialang.org and rebuild for the inst/julia backend."
fi
if command -v quarto >/dev/null 2>&1; then
  quarto --version
else
  echo "quarto: NOT installed (see WARNING above) -- R + renv are ready; fix network for rendering."
fi
# [lds] Report the pieces added for the lds notes site.
command -v rsvg-convert >/dev/null 2>&1 && rsvg-convert --version | head -1 || echo "rsvg-convert: NOT installed"
command -v typos >/dev/null 2>&1 && typos --version || echo "typos: NOT installed (see WARNING above)"
