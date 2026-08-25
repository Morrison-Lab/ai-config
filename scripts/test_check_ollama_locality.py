#!/usr/bin/env python3
"""Unit tests for scripts/check-ollama-locality.py."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    "check_ollama_locality", Path(__file__).parent / "check-ollama-locality.py"
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

    def test_missing_model_arg_refuses(self):
        ok, msg = checker.verify_locality("", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("required", msg)

    def test_malformed_config_refuses(self):
        ok, msg = checker.verify_locality("qwen2.5-coder:3b", "{invalid json")
        self.assertFalse(ok)
        self.assertIn("Cannot read", msg)

    @patch("socket.getaddrinfo")
    def test_non_loopback_host_refuses(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("192.168.1.100", 11434))]
        cfg = json.dumps({
            "provider": {
                "ollama": {
                    "options": {
                        "baseURL": "http://lan-gpu:11434/v1"
                    }
                }
            }
        })
        ok, msg = checker.verify_locality("qwen2.5-coder:3b", cfg)
        self.assertFalse(ok)
        self.assertIn("resolves off-machine", msg)

    @patch("socket.getaddrinfo")
    def test_cloud_enabled_daemon_refuses(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        with patch.dict(os.environ, {}, clear=True):
            ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config, server_json_path="/nonexistent/server.json")
            self.assertFalse(ok)
            self.assertIn("local-only mode not verified", msg)

    @patch("urllib.request.urlopen")
    @patch("socket.getaddrinfo")
    def test_remote_backed_model_in_tags_refuses(self, mock_getaddrinfo, mock_urlopen):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        remote_tags = json.dumps({
            "models": [
                {
                    "name": "remote-cloud-model:latest",
                    "remote_model": "cloud/model",
                    "remote_host": "https://cloud.ollama.ai"
                }
            ]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = remote_tags
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.dict(os.environ, {"OLLAMA_NO_CLOUD": "1"}):
            ok, msg = checker.verify_locality("remote-cloud-model", self.valid_config)
            self.assertFalse(ok)
            self.assertIn("remote/cloud infrastructure", msg)

    @patch("urllib.request.urlopen")
    @patch("socket.getaddrinfo")
    def test_absent_target_model_refuses(self, mock_getaddrinfo, mock_urlopen):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        mock_resp = MagicMock()
        mock_resp.read.return_value = self.valid_tags_response
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.dict(os.environ, {"OLLAMA_NO_CLOUD": "1"}):
            ok, msg = checker.verify_locality("deepseek-r1:latest", self.valid_config)
            self.assertFalse(ok)
            self.assertIn("not locally resident", msg)

    @patch("urllib.request.urlopen")
    @patch("socket.getaddrinfo")
    def test_valid_local_model_with_server_json_succeeds(self, mock_getaddrinfo, mock_urlopen):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        mock_resp = MagicMock()
        mock_resp.read.return_value = self.valid_tags_response
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump({"disable_ollama_cloud": True}, tf)
            tf_path = tf.name

        try:
            with patch.dict(os.environ, {}, clear=True):
                ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config, server_json_path=tf_path)
                self.assertTrue(ok)
                self.assertIn("OK: Verified loopback", msg)
                self.assertIn("qwen2.5-coder:3b", msg)
        finally:
            os.remove(tf_path)

    @patch("urllib.request.urlopen")
    @patch("socket.getaddrinfo")
    def test_url_with_trailing_slash_v1_succeeds(self, mock_getaddrinfo, mock_urlopen):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        mock_resp = MagicMock()
        mock_resp.read.return_value = self.valid_tags_response
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg_trailing = json.dumps({
            "provider": {
                "ollama": {
                    "options": {
                        "baseURL": "http://127.0.0.1:11434/v1/"
                    }
                }
            }
        })
        with patch.dict(os.environ, {"OLLAMA_NO_CLOUD": "1"}):
            ok, msg = checker.verify_locality("qwen2.5-coder:3b", cfg_trailing)
            self.assertTrue(ok)
            self.assertIn("OK: Verified loopback", msg)


if __name__ == "__main__":
    unittest.main()
