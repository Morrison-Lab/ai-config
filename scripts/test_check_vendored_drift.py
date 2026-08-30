#!/usr/bin/env python3
"""Regression tests for scripts/check-vendored-drift.py."""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "cvd", Path(__file__).parent / "check-vendored-drift.py"
)
cvd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cvd)

passes = 0
failures = 0


def check(name: str, condition: bool):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# 1. Real repository run
check("real repository passes check-vendored-drift", cvd.main() == 0)

# 2. Synthetic fixture tests in temp dirs
with tempfile.TemporaryDirectory() as tmp_dir:
    root = Path(tmp_dir)
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    vendored_dir = root / "shared" / "vendored"
    vendored_dir.mkdir(parents=True)

    wf_content = """
name: Sync
jobs:
  sync:
    uses: Morrison-Lab/gha/.github/workflows/sync-shared-fragments.yml@v1
    with:
      source-repo: Morrison-Lab/wai
      manifest-path: shared/vendored/MANIFEST.json
"""
    (wf_dir / "sync.yml").write_bytes(wf_content.encode("utf-8"))

    frag1 = "Content of frag 1\n"
    frag2 = "Content of frag 2\n"
    (vendored_dir / "frag1.md").write_bytes(frag1.encode("utf-8"))
    (vendored_dir / "frag2.md").write_bytes(frag2.encode("utf-8"))

    manifest_data = {
        "source_repo": "Morrison-Lab/wai",
        "source_ref": "main",
        "files": [
            {
                "path": "shared/vendored/frag1.md",
                "source_path": "shared/frag1.md",
                "sha256": sha256_text(frag1),
                "source_url": "https://github.com/Morrison-Lab/wai/blob/main/shared/frag1.md",
            },
            {
                "path": "shared/vendored/frag2.md",
                "source_path": "shared/frag2.md",
                "sha256": sha256_text(frag2),
                "source_url": "https://github.com/Morrison-Lab/wai/blob/main/shared/frag2.md",
            },
        ],
    }
    manifest_path = vendored_dir / "MANIFEST.json"
    manifest_path.write_bytes(json.dumps(manifest_data, indent=2).encode("utf-8"))

    sync_cfg = cvd.find_sync_workflows(root)
    check("find_sync_workflows detects manifest-path and source-repo", "shared/vendored/MANIFEST.json" in sync_cfg)
    check("detected source-repo is Morrison-Lab/wai", sync_cfg.get("shared/vendored/MANIFEST.json", {}).get("source_repo") == "Morrison-Lab/wai")

    errors = []
    verified = cvd.check_manifest(manifest_path, errors, sync_cfg, repo_root=root)
    check("valid fixture passes with 2 files verified and 0 errors", verified == 2 and not errors)

    # Test mismatch in source_repo (#2618)
    manifest_data_mismatch = dict(manifest_data, source_repo="d-morrison/wai")
    manifest_path.write_bytes(json.dumps(manifest_data_mismatch, indent=2).encode("utf-8"))
    errors = []
    cvd.check_manifest(manifest_path, errors, sync_cfg, repo_root=root)
    check(
        "source_repo mismatch is flagged",
        any("source_repo mismatch" in e and "d-morrison/wai" in e and "Morrison-Lab/wai" in e for e in errors),
    )

    # Test mismatch in source_url (#2618)
    manifest_data_bad_url = {
        "source_repo": "Morrison-Lab/wai",
        "source_ref": "main",
        "files": [
            {
                "path": "shared/vendored/frag1.md",
                "source_path": "shared/frag1.md",
                "sha256": sha256_text(frag1),
                "source_url": "https://github.com/d-morrison/wai/blob/main/shared/frag1.md",
            }
        ],
    }
    manifest_path.write_bytes(json.dumps(manifest_data_bad_url, indent=2).encode("utf-8"))
    errors = []
    cvd.check_manifest(manifest_path, errors, sync_cfg, repo_root=root)
    check(
        "source_url mismatch with source_repo is flagged",
        any("source_url" in e and "does not match source-repo" in e for e in errors),
    )

    # Test file hash mismatch
    (vendored_dir / "frag1.md").write_bytes(b"Tampered content\n")
    manifest_path.write_bytes(json.dumps(manifest_data, indent=2).encode("utf-8"))
    errors = []
    cvd.check_manifest(manifest_path, errors, sync_cfg, repo_root=root)
    check("file content hash mismatch is flagged", any("sha256 mismatch" in e for e in errors))

    # Test missing file on disk
    (vendored_dir / "frag1.md").unlink()
    errors = []
    cvd.check_manifest(manifest_path, errors, sync_cfg, repo_root=root)
    check("missing file on disk is flagged", any("missing on disk" in e for e in errors))

    # Test malformed manifest JSON
    manifest_path.write_bytes(b"invalid json {")
    errors = []
    cvd.check_manifest(manifest_path, errors, sync_cfg, repo_root=root)
    check("malformed manifest JSON is flagged", any("cannot read manifest" in e for e in errors))

# Test empty repository / no manifests
with tempfile.TemporaryDirectory() as empty_dir:
    check("empty directory reports 0 exit code", cvd.main(repo_root=Path(empty_dir)) == 0)

print(f"\n{passes} passed, {failures} failed")
if failures:
    sys.exit(1)
