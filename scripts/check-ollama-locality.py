#!/usr/bin/env python3
"""Verify data-locality guarantees for local Ollama delegation via OpenCode.

Verifies:
1. Endpoint loopback resolution (baseURL host resolves strictly to 127.0.0.1 or ::1).
2. Local-only configuration (OLLAMA_NO_CLOUD=1 environment variable or disable_ollama_cloud: true).
3. Target model local residency on-device (checked against Ollama /api/tags, refusing remote/cloud models).
"""

import argparse
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse
from typing import Optional, Tuple


def verify_locality(target_model: str, config_json: Optional[str] = None) -> Tuple[bool, str]:
    if not target_model or not target_model.strip():
        return False, "Target model identifier is required (e.g. 'qwen2.5-coder:3b')."

    clean_target = re.sub(r"^ollama/", "", target_model.strip())
    target_tag = clean_target if ":" in clean_target else f"{clean_target}:latest"

    # 1. Read opencode configuration
    try:
        if config_json is None:
            raw = subprocess.run(
                ["opencode", "debug", "config"],
                capture_output=True, text=True, check=True,
            ).stdout
        else:
            raw = config_json
        data = json.loads(raw)
        provider_cfg = data.get("provider", {}).get("ollama", {})
        url = provider_cfg.get("options", {}).get("baseURL")
        if not url:
            return False, "Cannot read the ollama baseURL from opencode's config."
    except Exception as exc:
        return False, f"Cannot read or parse opencode configuration: {exc}"

    # 2. Verify loopback host resolution
    host = urlparse(url).hostname
    if not host:
        return False, f"No host in ollama baseURL {url!r}"

    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError as exc:
        return False, f"Cannot resolve {host!r}: {exc}"

    remote = sorted(a for a in addrs if not ipaddress.ip_address(a).is_loopback)
    if remote:
        return False, f"Ollama baseURL {url} resolves off-machine: {', '.join(remote)}"

    # 3. Verify local-only mode (OLLAMA_NO_CLOUD=1 or disable_ollama_cloud: true)
    opts = provider_cfg.get("options", {})
    is_cloud_disabled = (os.environ.get("OLLAMA_NO_CLOUD") == "1") or (opts.get("disable_ollama_cloud") is True)
    if not is_cloud_disabled:
        return False, "Ollama local-only mode not verified (requires OLLAMA_NO_CLOUD=1 or 'disable_ollama_cloud: true' in config)."

    # 4. Verify local model residency via /api/tags
    try:
        base_api = url[:-3] if url.endswith("/v1") else url.rstrip("/")
        tags_url = base_api.rstrip("/") + "/api/tags"
        req = urllib.request.Request(tags_url, headers={"User-Agent": "opencode-locality-check"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            tags_data = json.loads(resp.read().decode("utf-8"))
            model_entries = tags_data.get("models", [])
    except Exception as exc:
        return False, f"Cannot verify local model residency from Ollama tags API ({exc})"

    if not model_entries:
        return False, "Local Ollama daemon reports 0 resident models in /api/tags."

    # Identify remote-backed or cloud models
    remote_models = {
        m.get("name", "") for m in model_entries
        if m.get("remote_model") or m.get("remote_host")
    }
    local_models = [
        m.get("name", "") for m in model_entries
        if m.get("name") and m.get("name") not in remote_models and m.get("digest") and m.get("size", 0) > 0
    ]

    matched = any(m == clean_target or m == target_tag for m in local_models)
    if not matched:
        if any(m == clean_target or m == target_tag for m in remote_models):
            return False, f"Target model {target_model!r} is backed by remote/cloud infrastructure."
        return False, f"Target model {target_model!r} (normalized {target_tag!r}) is not locally resident (local models: {', '.join(local_models)})."

    return True, f"OK: Verified loopback ({', '.join(sorted(addrs))}), local-only mode, and on-device residency for {target_tag} ({len(local_models)} local models)."


def main():
    parser = argparse.ArgumentParser(description="Verify Ollama locality and model residency.")
    parser.add_argument("model", help="Target model identifier (e.g. 'qwen2.5-coder:3b')")
    args = parser.parse_args()

    ok, msg = verify_locality(args.model)
    if not ok:
        print(f"REFUSE: {msg}", file=sys.stderr)
        sys.exit(1)
    print(msg)


if __name__ == "__main__":
    main()
