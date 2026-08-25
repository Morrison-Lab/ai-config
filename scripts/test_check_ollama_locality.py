#!/usr/bin/env python3
"""Unit tests for scripts/check-ollama-locality.py."""

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "check_ollama_locality", REPO_ROOT / "scripts" / "check-ollama-locality.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class TestCheckOllamaLocality(unittest.TestCase):
    def setUp(self):
        self.valid_config = json.dumps({
            "provider": {
                "ollama": {
                    "options": {
                        "baseURL": "http://localhost:11434/v1"
                    }
                }
            }
        })
        self.valid_tags_response = json.dumps({
            "models": [
                {
                    "name": "qwen2.5-coder:3b",
                    "digest": "sha256:1234567890abcdef",
                    "size": 1900000000,
                    "details": {"format": "gguf", "family": "qwen2"}
                },
                {
                    "name": "llama3.2:latest",
                    "digest": "sha256:abcdef1234567890",
                    "size": 2000000000,
                    "details": {"format": "gguf", "family": "llama"}
                }
            ]
        }).encode("utf-8")

    def test_scripts_synchronization(self):
        p1 = REPO_ROOT / "scripts" / "check-ollama-locality.py"
        p2 = REPO_ROOT / "skills" / "delegate-to-opencode" / "scripts" / "check-ollama-locality.py"
        self.assertTrue(p1.is_file(), "scripts/check-ollama-locality.py must exist")
        self.assertTrue(p2.is_file(), "skills/delegate-to-opencode/scripts/check-ollama-locality.py must exist")
        self.assertEqual(p1.read_text(encoding="utf-8"), p2.read_text(encoding="utf-8"), "Script copies must be identical")

    def test_missing_model_arg_refuses(self):
        ok, msg = checker.verify_locality("", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("required", msg)

    def test_malformed_config_refuses(self):
        ok, msg = checker.verify_locality("qwen2.5-coder:3b", "{invalid json")
        self.assertFalse(ok)
        self.assertIn("Cannot read", msg)

    def test_unsupported_url_scheme_refuses(self):
        cfg = json.dumps({
            "provider": {
                "ollama": {
                    "options": {
                        "baseURL": "ftp://localhost:11434/v1"
                    }
                }
            }
        })
        ok, msg = checker.verify_locality("qwen2.5-coder:3b", cfg)
        self.assertFalse(ok)
        self.assertIn("Unsupported scheme 'ftp'", msg)

    def test_non_literal_loopback_host_refuses(self):
        cfg = json.dumps({
            "provider": {
                "ollama": {
                    "options": {
                        "baseURL": "http://gpu-box.local:11434/v1"
                    }
                }
            }
        })
        ok, msg = checker.verify_locality("qwen2.5-coder:3b", cfg)
        self.assertFalse(ok)
        self.assertIn("not a literal loopback address", msg)

    @patch("socket.getaddrinfo")
    def test_non_loopback_resolved_host_refuses(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("192.168.1.100", 11434))]
        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("resolves off-machine", msg)

    @patch("urllib.request.OpenerDirector.open")
    @patch("socket.getaddrinfo")
    def test_daemon_status_unreachable_refuses_fail_closed(self, mock_getaddrinfo, mock_open):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        mock_open.side_effect = OSError("Connection refused")

        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("Cannot reach or verify live Ollama status", msg)

    @patch("urllib.request.OpenerDirector.open")
    @patch("socket.getaddrinfo")
    def test_daemon_with_cloud_disabled_false_refuses(self, mock_getaddrinfo, mock_open):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        status_resp = MagicMock()
        status_resp.read.return_value = json.dumps({"cloud": {"disabled": False, "source": "config"}}).encode("utf-8")
        status_resp.geturl.return_value = "http://localhost:11434/api/status"
        status_resp.__enter__.return_value = status_resp

        mock_open.return_value = status_resp

        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("cloud offloading is active", msg)

    @patch("urllib.request.OpenerDirector.open")
    @patch("socket.getaddrinfo")
    def test_daemon_with_boolean_cloud_false_refuses_strict_schema(self, mock_getaddrinfo, mock_open):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        status_resp = MagicMock()
        status_resp.read.return_value = json.dumps({"cloud": False}).encode("utf-8")
        status_resp.geturl.return_value = "http://localhost:11434/api/status"
        status_resp.__enter__.return_value = status_resp

        mock_open.return_value = status_resp

        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("cloud offloading is active or unverified", msg)

    @patch("urllib.request.OpenerDirector.open")
    @patch("socket.getaddrinfo")
    def test_daemon_with_unknown_cloud_schema_refuses(self, mock_getaddrinfo, mock_open):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        status_resp = MagicMock()
        status_resp.read.return_value = json.dumps({"cloud": "disabled"}).encode("utf-8")
        status_resp.geturl.return_value = "http://localhost:11434/api/status"
        status_resp.__enter__.return_value = status_resp

        mock_open.return_value = status_resp

        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("cloud offloading is active or unverified", msg)

    @patch("urllib.request.OpenerDirector.open")
    @patch("socket.getaddrinfo")
    def test_malformed_tags_elements_and_boolean_size_handled_defensively(self, mock_getaddrinfo, mock_open):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        status_resp = MagicMock()
        status_resp.read.return_value = json.dumps({"cloud": {"disabled": True}}).encode("utf-8")
        status_resp.geturl.return_value = "http://localhost:11434/api/status"
        status_resp.__enter__.return_value = status_resp

        malformed_tags = json.dumps({
            "models": [
                "string_entry_not_dict",
                {"name": "missing_size", "digest": "sha256:123"},
                {"name": "boolean_size", "digest": "sha256:456", "size": True},
            ]
        }).encode("utf-8")
        tags_resp = MagicMock()
        tags_resp.read.return_value = malformed_tags
        tags_resp.geturl.return_value = "http://localhost:11434/api/tags"
        tags_resp.__enter__.return_value = tags_resp

        mock_open.side_effect = [status_resp, tags_resp]

        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("not locally resident", msg)

    @patch("urllib.request.OpenerDirector.open")
    @patch("socket.getaddrinfo")
    def test_valid_local_model_with_status_succeeds(self, mock_getaddrinfo, mock_open):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        status_resp = MagicMock()
        status_resp.read.return_value = json.dumps({"cloud": {"disabled": True}}).encode("utf-8")
        status_resp.geturl.return_value = "http://localhost:11434/api/status"
        status_resp.__enter__.return_value = status_resp

        tags_resp = MagicMock()
        tags_resp.read.return_value = self.valid_tags_response
        tags_resp.geturl.return_value = "http://localhost:11434/api/tags"
        tags_resp.__enter__.return_value = tags_resp

        mock_open.side_effect = [status_resp, tags_resp]

        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config)
        self.assertTrue(ok)
        self.assertIn("OK: Verified loopback endpoint", msg)
        self.assertIn("http://localhost:11434/v1", msg)
        self.assertIn("cloud.disabled=true", msg)
        self.assertIn("qwen2.5-coder:3b", msg)


if __name__ == "__main__":
    unittest.main()
