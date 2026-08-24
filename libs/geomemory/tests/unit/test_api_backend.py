"""Unit tests for ApiLLMBackend using an in-process fake gateway."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from geomemory.core.exceptions import AbstentionError
from geomemory.core.models import GenerationRequest
from geomemory.qa.api_backend import ApiLLMBackend


def _make_gateway(handler):
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


class _ChatHandler(BaseHTTPRequestHandler):
    received: dict = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        _ChatHandler.received = {"headers": dict(self.headers), "body": body}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "choices": [
                        {"message": {"content": "The NDVI value is 0.6 [1]."}}
                    ]
                }
            ).encode()
        )

    def log_message(self, *args):  # silence
        pass


class _LegacyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"choices": [{"text": "legacy completion"}]}).encode()
        )

    def log_message(self, *args):
        pass


class _ErrorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "unauthorized"}).encode())

    def log_message(self, *args):
        pass


@pytest.fixture()
def chat_gateway():
    server, port = _make_gateway(_ChatHandler)
    yield f"http://127.0.0.1:{port}/v1"
    server.shutdown()


@pytest.fixture()
def legacy_gateway():
    server, port = _make_gateway(_LegacyHandler)
    yield f"http://127.0.0.1:{port}/v1"
    server.shutdown()


@pytest.fixture()
def error_gateway():
    server, port = _make_gateway(_ErrorHandler)
    yield f"http://127.0.0.1:{port}/v1"
    server.shutdown()


class TestApiLLMBackend:
    def test_chat_response_mapping(self, chat_gateway, monkeypatch):
        monkeypatch.setenv("GEOMEMORY_LLM_API_KEY", "secret")
        backend = ApiLLMBackend(
            model_id="kilo-auto/free",
            api_base_url=chat_gateway,
            api_key="secret",
        )
        result = backend.generate(GenerationRequest(prompt="What is NDVI?"))
        assert result.text == "The NDVI value is 0.6 [1]."
        assert result.model_id == "kilo-auto/free"
        assert result.abstained is False
        # Auth header present when key provided.
        assert _ChatHandler.received["headers"]["Authorization"] == "Bearer secret"
        # Request path is /chat/completions.
        assert _ChatHandler.received["body"]["model"] == "kilo-auto/free"
        assert _ChatHandler.received["body"]["messages"][0]["role"] == "user"

    def test_legacy_response_mapping(self, legacy_gateway, monkeypatch):
        monkeypatch.setenv("GEOMEMORY_LLM_API_KEY", "secret")
        backend = ApiLLMBackend(
            model_id="kilo-auto/free",
            api_base_url=legacy_gateway,
            api_key="secret",
        )
        result = backend.generate(GenerationRequest(prompt="q"))
        assert result.text == "legacy completion"

    def test_http_error_raises_abstention(self, error_gateway, monkeypatch):
        monkeypatch.setenv("GEOMEMORY_LLM_API_KEY", "secret")
        backend = ApiLLMBackend(
            model_id="kilo-auto/free",
            api_base_url=error_gateway,
            api_key="secret",
        )
        with pytest.raises(AbstentionError):
            backend.generate(GenerationRequest(prompt="q"))

    def test_count_tokens_approximate(self, chat_gateway):
        backend = ApiLLMBackend(
            model_id="kilo-auto/free",
            api_base_url=chat_gateway,
            api_key="x",
        )
        assert backend.count_tokens("abcdefgh") >= 1
