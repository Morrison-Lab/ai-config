#!/usr/bin/env python3
"""Check that vendored files match their manifest hashes and sync workflows.

`shared/vendored/` holds pinned copies of fragments authored in another repo
(see README, "Shared content"). Each copy is recorded in a `MANIFEST.json` with
a content `sha256`. This check:
1. Recomputes each file's hash and asserts it matches the manifest.
2. Validates that `source_repo` and `source_url` in `MANIFEST.json` match the
   `source-repo` input configured in the `.github/workflows/` caller workflow
   that generates the manifest (#2618).

Exits 1 on any mismatch, missing file, or malformed manifest; prints a success
line otherwise. No network access.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_sync_workflows(repo_root: Path) -> dict[str, dict[str, str]]:
    """Scan .github/workflows for caller workflows using sync-shared-fragments.yml.

    Returns mapping of normalized manifest relative path -> {'source_repo': ..., 'workflow_path': ...}.
    """
    configs: dict[str, dict[str, str]] = {}
    workflow_dir = repo_root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return configs

    for wf_path in workflow_dir.glob("*.y*ml"):
        try:
            content = wf_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "sync-shared-fragments.yml" not in content and "manifest-path" not in content:
            continue

        manifest_path = None
        source_repo = None

        try:
            import yaml
            parsed = yaml.safe_load(content)
            if isinstance(parsed, dict):
                jobs = parsed.get("jobs") or {}
                for job_name, job_data in jobs.items():
                    if isinstance(job_data, dict):
                        with_args = job_data.get("with") or {}
                        if isinstance(with_args, dict):
                            if "manifest-path" in with_args and "source-repo" in with_args:
                                manifest_path = str(with_args["manifest-path"]).strip()
                                source_repo = str(with_args["source-repo"]).strip()
                                break
        except Exception:
            pass

        if not manifest_path or not source_repo:
            m_manifest = re.search(r"manifest-path:\s*([^\s#]+)", content)
            m_repo = re.search(r"source-repo:\s*([^\s#]+)", content)
            if m_manifest and m_repo:
                manifest_path = m_manifest.group(1).strip("'\"")
                source_repo = m_repo.group(1).strip("'\"")

        if manifest_path and source_repo:
            norm_manifest = Path(manifest_path).as_posix()
            rel_wf = wf_path.relative_to(repo_root).as_posix()
            configs[norm_manifest] = {
                "source_repo": source_repo,
                "workflow_path": rel_wf,
            }

    return configs


def check_manifest(
    manifest_path: Path,
    errors: list[str],
    sync_configs: dict[str, dict[str, str]] | None = None,
    repo_root: Path = REPO_ROOT,
) -> int:
    if sync_configs is None:
        sync_configs = find_sync_workflows(repo_root)

    rel = manifest_path.relative_to(repo_root).as_posix()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{rel}: cannot read manifest ({exc})")
        return 0

    sync_cfg = sync_configs.get(rel)
    manifest_source_repo = data.get("source_repo")

    if sync_cfg:
        expected_repo = sync_cfg["source_repo"]
        wf_path = sync_cfg["workflow_path"]
        if manifest_source_repo != expected_repo:
            errors.append(
                f"{rel}: source_repo mismatch: manifest has {manifest_source_repo!r}, "
                f"but {wf_path} specifies source-repo {expected_repo!r}"
            )
    elif not manifest_source_repo:
        errors.append(f"{rel}: 'source_repo' missing or empty")

    files = data.get("files")
    if not isinstance(files, list):
        errors.append(f"{rel}: 'files' missing or not a list")
        return 0

    verified = 0
    for entry in files:
        if not isinstance(entry, dict):
            errors.append(f"{rel}: 'files' entry is not an object: {entry!r}")
            continue
        path_str = entry.get("path")
        expected = entry.get("sha256")
        source_url = entry.get("source_url")
        if not path_str or not expected:
            errors.append(f"{rel}: entry missing 'path' or 'sha256': {entry!r}")
            continue

        if sync_cfg and source_url:
            expected_repo = sync_cfg["source_repo"]
            expected_prefix = f"https://github.com/{expected_repo}/"
            if not source_url.startswith(expected_prefix):
                errors.append(
                    f"{path_str}: source_url {source_url!r} does not match "
                    f"source-repo {expected_repo!r} from {sync_cfg['workflow_path']}"
                )

        vendored = repo_root / path_str
        if not vendored.resolve().is_relative_to(repo_root):
            errors.append(f"{path_str}: path escapes the repo root; refusing to read")
            continue
        if not vendored.is_file():
            errors.append(f"{path_str}: listed in {rel} but missing on disk")
            continue
        actual = sha256_of(vendored)
        if actual != expected:
            errors.append(
                f"{path_str}: sha256 mismatch (manifest {expected[:12]}..., "
                f"file {actual[:12]}...). Don't edit vendored copies; "
                f"edit upstream and let the sync workflow refresh them."
            )
            continue
        verified += 1
    return verified


def main(repo_root: Path = REPO_ROOT) -> int:
    manifests = sorted(repo_root.glob("shared/vendored/**/MANIFEST.json"))
    if not manifests:
        print("✓ no vendored manifests to check")
        return 0
    sync_configs = find_sync_workflows(repo_root)
    errors: list[str] = []
    checked = 0
    for manifest in manifests:
        checked += check_manifest(manifest, errors, sync_configs, repo_root=repo_root)
    if errors:
        print("Vendored drift check failed:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"✓ {checked} vendored file(s) match their manifest hashes and sync workflow definitions")
    return 0


if __name__ == "__main__":
    sys.exit(main())

