#!/usr/bin/env python3
"""Verify data-locality guarantees for local Ollama delegation via OpenCode.

Verifies:
1. Direct loopback endpoint (literal loopback host, http/https scheme, proxies disabled, redirects disabled).
2. Live daemon local-only state (checked directly against running Ollama daemon /api/status, requiring cloud.disabled == true).
3. Target model local residency on-device (checked against Ollama /api/tags, refusing remote/cloud models).
"""

import argparse
import json
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse
from typing import Optional, Tuple


LITERAL_LOOPBACK_ADDRESSES = frozenset({"127.0.0.1", "::1"})


def _is_literal_loopback_address(address: str) -> bool:
    """True only for the two addresses the docs and refuse text name.

    ``ipaddress.ip_address(x).is_loopback`` is true for the whole
    127.0.0.0/8 range, not just 127.0.0.1, so relying on it lets an
    endpoint like 127.0.0.2 or 127.255.255.255 pass a check whose refuse
    message claims to require the literal address.
    """
    return address in LITERAL_LOOPBACK_ADDRESSES


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            newurl, code, f"HTTP redirects disallowed for locality-verified endpoints ({newurl})", headers, fp
        )


def _safe_fetch_json(url: str, timeout: int = 5) -> Tuple[dict, str]:
    # Disable all system/environment proxies and redirects for locality safety
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirectHandler)
    req = urllib.request.Request(url, headers={"User-Agent": "opencode-locality-check"})
    with opener.open(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        final_host = urlparse(final_url).hostname
        if not final_host:
            raise ValueError(f"No host in response URL {final_url!r}")
        addrs = {info[4][0] for info in socket.getaddrinfo(final_host, None)}
        remote = sorted(a for a in addrs if not _is_literal_loopback_address(a))
        if remote:
            raise ValueError(f"Final response URL {final_url} resolves off-machine: {', '.join(remote)}")
        data = json.loads(resp.read().decode("utf-8"))
        return data, final_url


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
            proc = subprocess.run(
                ["opencode", "debug", "config"],
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or proc.stdout.strip()
                return False, f"opencode debug config failed (exit {proc.returncode}): {err}"
            raw = proc.stdout
        else:
            raw = config_json
        data = json.loads(raw)
        provider_cfg = data.get("provider", {}).get("ollama", {})
        url = provider_cfg.get("options", {}).get("baseURL")
        if not url:
            return False, "Cannot read the ollama baseURL from opencode's config."
    except Exception as exc:
        return False, f"Cannot read or parse opencode configuration: {exc}"

    # 2. Verify literal loopback endpoint
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        return False, f"Unsupported scheme {parsed_url.scheme!r} in baseURL {url!r}; only 'http' and 'https' are supported."

    host = parsed_url.hostname
    if not host:
        return False, f"No host in ollama baseURL {url!r}"

    # Require literal loopback identifier: exactly 'localhost', '127.0.0.1',
    # or '::1' -- not the whole 127.0.0.0/8 range ipaddress.is_loopback
    # would otherwise license (see _is_literal_loopback_address above).
    is_literal_loopback = (host == "localhost") or _is_literal_loopback_address(host)

    if not is_literal_loopback:
        return False, f"Ollama baseURL host {host!r} is not a literal loopback address ('localhost', '127.0.0.1', or '::1')."

    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError as exc:
        return False, f"Cannot resolve {host!r}: {exc}"

    remote = sorted(a for a in addrs if not _is_literal_loopback_address(a))
    if remote:
        return False, f"Ollama baseURL {url} resolves off-machine: {', '.join(remote)}"

    base_path = re.sub(r"/v1/?$", "", parsed_url.path).rstrip("/")
    base_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}{base_path}"

    # 3. Verify running daemon live local-only status via /api/status
    try:
        status_url = f"{base_endpoint}/api/status"
        status_data, _ = _safe_fetch_json(status_url, timeout=5)
    except Exception as exc:
        return False, f"Cannot reach or verify live Ollama status at {base_endpoint}/api/status ({exc}). Refusing: running daemon must confirm cloud is disabled."

    if not isinstance(status_data, dict):
        return False, f"Unexpected response schema from {base_endpoint}/api/status: expected JSON object."

    cloud_obj = status_data.get("cloud")
    if not isinstance(cloud_obj, dict) or cloud_obj.get("disabled") is not True:
        return False, f"Running Ollama daemon at {url} reports cloud offloading is active or unverified (status: {json.dumps(status_data)}). Refusing."

    # 4. Verify local model residency via /api/tags
    try:
        tags_url = f"{base_endpoint}/api/tags"
        tags_data, _ = _safe_fetch_json(tags_url, timeout=5)
    except Exception as exc:
        return False, f"Cannot verify local model residency from Ollama tags API ({exc})"

    if not isinstance(tags_data, dict):
        return False, f"Unexpected response schema from {tags_url}: expected JSON object."

    model_entries = tags_data.get("models")
    if not isinstance(model_entries, list) or not model_entries:
        return False, "Local Ollama daemon reports 0 resident models in /api/tags."

    # Validate model entries defensively
    remote_models = set()
    local_models = []
    for m in model_entries:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name", ""))
        if not name:
            continue
        if m.get("remote_model") or m.get("remote_host"):
            remote_models.add(name)
        else:
            sz = m.get("size")
            if m.get("digest") and type(sz) in (int, float) and sz > 0:
                local_models.append(name)

    matched = any(m == clean_target or m == target_tag for m in local_models)
    if not matched:
        if any(m == clean_target or m == target_tag for m in remote_models):
            return False, f"Target model {target_model!r} is backed by remote/cloud infrastructure."
        return False, f"Target model {target_model!r} (normalized {target_tag!r}) is not locally resident (local models: {', '.join(local_models)})."

    return True, f"OK: Verified loopback endpoint ({url}, {', '.join(sorted(addrs))}), direct connection (proxies disabled), daemon local-only mode (cloud.disabled=true), and on-device residency for {target_tag} ({len(local_models)} local models)."


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
