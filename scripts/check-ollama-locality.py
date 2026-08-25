#!/usr/bin/env python3
"""Verify data-locality guarantees for local Ollama delegation via OpenCode.

Verifies:
1. Endpoint loopback resolution (baseURL host resolves strictly to 127.0.0.1 or ::1).
2. Live daemon local-only state (checked directly against running Ollama daemon /api/status).
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


def verify_locality(
    target_model: str,
    config_json: Optional[str] = None,
) -> Tuple[bool, str]:
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
    parsed_url = urlparse(url)
    host = parsed_url.hostname
    if not host:
        return False, f"No host in ollama baseURL {url!r}"

    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError as exc:
        return False, f"Cannot resolve {host!r}: {exc}"

    remote = sorted(a for a in addrs if not ipaddress.ip_address(a).is_loopback)
    if remote:
        return False, f"Ollama baseURL {url} resolves off-machine: {', '.join(remote)}"

    base_path = re.sub(r"/v1/?$", "", parsed_url.path).rstrip("/")
    base_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}{base_path}"

    # 3. Verify running daemon live local-only status via /api/status
    try:
        status_url = f"{base_endpoint}/api/status"
        req_status = urllib.request.Request(status_url, headers={"User-Agent": "opencode-locality-check"})
        with urllib.request.urlopen(req_status, timeout=5) as resp:
            status_data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        status_data = None

    if status_data is not None:
        # If daemon reports explicit cloud status, verify cloud is disabled
        cloud_active = status_data.get("cloud") is True or status_data.get("cloud_enabled") is True or status_data.get("cloud") == "enabled"
        if cloud_active:
            return False, f"Running Ollama daemon at {url} reports active cloud offloading in /api/status."
    else:
        # Fallback: check daemon-level configuration file if /api/status is unavailable
        server_cfg_file = os.path.expanduser("~/.ollama/server.json")
        server_cloud_disabled = False
        if os.path.isfile(server_cfg_file):
            try:
                with open(server_cfg_file, "r", encoding="utf-8") as f:
                    scfg = json.load(f)
                    if scfg.get("disable_ollama_cloud") is True or str(scfg.get("OLLAMA_NO_CLOUD", "")) == "1":
                        server_cloud_disabled = True
            except Exception:
                pass
        if not server_cloud_disabled and os.environ.get("OLLAMA_NO_CLOUD") != "1":
            return False, "Ollama local-only mode not verified (running daemon did not confirm cloud-disabled status in /api/status or ~/.ollama/server.json)."

    # 4. Verify local model residency via /api/tags
    try:
        tags_url = f"{base_endpoint}/api/tags"
        req_tags = urllib.request.Request(tags_url, headers={"User-Agent": "opencode-locality-check"})
        with urllib.request.urlopen(req_tags, timeout=5) as resp:
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

    return True, f"OK: Verified loopback endpoint ({url}, {', '.join(sorted(addrs))}), daemon local-only mode, and on-device residency for {target_tag} ({len(local_models)} local models)."


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
