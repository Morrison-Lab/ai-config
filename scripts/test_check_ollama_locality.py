#!/usr/bin/env python3
"""Unit tests for scripts/check-ollama-locality.py."""

import http.server
import importlib.util
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "check_ollama_locality", REPO_ROOT / "scripts" / "check-ollama-locality.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class _FakeOllamaHandler(http.server.BaseHTTPRequestHandler):
    """Serves /api/status and /api/tags, and redirects everything else.

    Runs as a real HTTP server on loopback so tests exercise the actual
    urllib opener chain (NoRedirectHandler, ProxyHandler({})) instead of
    mocking OpenerDirector.open --- a mock at that level never invokes
    either handler, so a test built on it cannot show redirects are
    refused or that proxies are bypassed.
    """

    status_body = json.dumps({"cloud": {"disabled": True}}).encode("utf-8")
    tags_body = json.dumps({"models": []}).encode("utf-8")

    def do_GET(self):
        if self.path == "/api/status":
            self._send_json(self.status_body)
        elif self.path == "/api/tags":
            self._send_json(self.tags_body)
        elif self.path == "/redirect-me":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence test output
        pass


class _LiveServerCase(unittest.TestCase):
    """Base class spinning up a real loopback HTTP server per test."""

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _FakeOllamaHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)


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

    def test_loopback_range_beyond_127_0_0_1_refuses(self):
        # ipaddress.ip_address(...).is_loopback treats all of 127.0.0.0/8
        # as loopback; the refuse text (and the docs) name only
        # '127.0.0.1'/'::1', so any other address in that range must
        # still be refused.
        for host in ("127.0.0.2", "127.255.255.255"):
            cfg = json.dumps({
                "provider": {
                    "ollama": {
                        "options": {
                            "baseURL": f"http://{host}:11434/v1"
                        }
                    }
                }
            })
            ok, msg = checker.verify_locality("qwen2.5-coder:3b", cfg)
            self.assertFalse(ok, f"{host} should be refused")
            self.assertIn("not a literal loopback address", msg)

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

    @patch("socket.getaddrinfo")
    def test_scope_qualified_ipv6_resolved_address_refuses_cleanly(self, mock_getaddrinfo):
        # A zone-qualified IPv6 address (e.g. a link-local address returned
        # for a loopback hostname on some platforms) is not a member of
        # LITERAL_LOOPBACK_ADDRESSES, so _is_literal_loopback_address must
        # refuse it with a clean message rather than raising -- see #1712.
        mock_getaddrinfo.return_value = [(10, 1, 6, "", ("fe80::1%lo0", 11434, 0, 0))]
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
    def test_target_model_absent_refuses(self, mock_getaddrinfo, mock_open):
        # A cleanly-formatted tags response that simply does not contain
        # the requested model (distinct from the malformed-elements test
        # above, which exercises defensive parsing rather than a normal
        # absent-model refusal).
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

        ok, msg = checker.verify_locality("some-other-model:latest", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("is not locally resident", msg)

    @patch("urllib.request.OpenerDirector.open")
    @patch("socket.getaddrinfo")
    def test_target_model_backed_by_remote_refuses(self, mock_getaddrinfo, mock_open):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 11434))]
        status_resp = MagicMock()
        status_resp.read.return_value = json.dumps({"cloud": {"disabled": True}}).encode("utf-8")
        status_resp.geturl.return_value = "http://localhost:11434/api/status"
        status_resp.__enter__.return_value = status_resp

        remote_backed_tags = json.dumps({
            "models": [
                {
                    "name": "qwen2.5-coder:3b",
                    "digest": "sha256:1234567890abcdef",
                    "size": 1900000000,
                    "remote_model": True,
                }
            ]
        }).encode("utf-8")
        tags_resp = MagicMock()
        tags_resp.read.return_value = remote_backed_tags
        tags_resp.geturl.return_value = "http://localhost:11434/api/tags"
        tags_resp.__enter__.return_value = tags_resp

        mock_open.side_effect = [status_resp, tags_resp]

        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self.valid_config)
        self.assertFalse(ok)
        self.assertIn("backed by remote/cloud infrastructure", msg)

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


class TestLiveHTTPBehavior(_LiveServerCase):
    """Exercises the real urllib opener chain against a loopback server.

    These do not mock OpenerDirector.open, so they actually run
    NoRedirectHandler and ProxyHandler({}) against real HTTP responses,
    unlike every mocked test above.
    """

    def _config_for(self, path_suffix=""):
        return json.dumps({
            "provider": {
                "ollama": {
                    "options": {
                        "baseURL": f"http://127.0.0.1:{self.port}{path_suffix}"
                    }
                }
            }
        })

    def test_trailing_v1_slash_is_stripped_before_api_calls(self):
        # baseURL carries a trailing /v1/ (as opencode's ollama provider
        # entries do); the checker must strip it and hit /api/status and
        # /api/tags directly on the host, not /v1/api/status.
        ok, msg = checker.verify_locality("qwen2.5-coder:3b", self._config_for("/v1/"))
        self.assertFalse(ok)
        # The fake server has an empty model list, so this refuses on
        # residency rather than on reachability -- proof the /api/status
        # and /api/tags calls themselves succeeded against the stripped path.
        self.assertIn("0 resident models", msg)

    def test_real_redirect_is_refused_not_followed(self):
        # The redirect target below is a LIVE, valid endpoint on this same
        # server, serving a real cloud.disabled=true body -- following it
        # would let verification proceed past the status check (it then
        # fails later, at the residency check, with a DIFFERENT message,
        # since tags_body is an empty model list). That makes the assertion
        # below discriminating: it can only pass if NoRedirectHandler genuinely
        # refused the redirect, never merely because some unrelated
        # connection failed. (An earlier version of this test redirected to
        # an unroutable port instead, so a refused redirect and a followed
        # redirect that then failed to connect produced the identical
        # failure message -- the test passed even with NoRedirectHandler
        # removed entirely.)
        class RedirectingHandler(_FakeOllamaHandler):
            def do_GET(self):
                if self.path == "/api/status":
                    self.send_response(302)
                    self.send_header("Location", "/api/status-redirected")
                    self.end_headers()
                elif self.path == "/api/status-redirected":
                    self._send_json(self.status_body)
                else:
                    super().do_GET()

        server = http.server.HTTPServer(("127.0.0.1", 0), RedirectingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            ok, msg = checker.verify_locality(
                "qwen2.5-coder:3b",
                json.dumps({
                    "provider": {
                        "ollama": {"options": {"baseURL": f"http://127.0.0.1:{port}/v1"}}
                    }
                }),
            )
            self.assertFalse(ok)
            self.assertIn("HTTP redirects disallowed", msg)
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
