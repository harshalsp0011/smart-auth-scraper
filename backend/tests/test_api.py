"""
test_api.py — Integration tests for FastAPI routes.
Mocks scraper and LLM so no real network or API calls are made.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from scraper import ScraperError
from llm import LLMError
import main as main_module
from main import app

client = TestClient(app)

AUTH_LOGIN_ID = "test-access-id"
AUTH_LOGIN_PASSWORD = "test-access-password"

SAMPLE_HTML = """
<html><body>
  <form>
    <input type="text" name="username"/>
    <input type="password" name="password"/>
    <input type="submit" value="Login"/>
  </form>
</body></html>
"""

NO_AUTH_HTML = "<html><body><p>No login here.</p></body></html>" * 20

LLM_RESULT = {
    "analysis": "Standard login form.",
    "tokens_used": {"input": 100, "output": 50, "total": 150},
}

def _assert_error_shape(data):
    """Helper: verify all structured error fields are present."""
    assert "error_type" in data
    assert "title" in data
    assert "message" in data
    assert "suggestion" in data


@pytest.fixture(autouse=True)
def _auth_settings():
    with patch.object(main_module, "AUTH_LOGIN_ID", AUTH_LOGIN_ID), \
         patch.object(main_module, "AUTH_LOGIN_PASSWORD", AUTH_LOGIN_PASSWORD):
        yield


def _auth_headers():
    resp = client.post(
        "/auth/login",
        json={"login_id": AUTH_LOGIN_ID, "password": AUTH_LOGIN_PASSWORD},
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


class TestHealthRoute:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestProvidersRoute:
    def test_returns_all_three_providers(self):
        resp = client.get("/providers", headers=_auth_headers())
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()["providers"]]
        assert "openai" in ids
        assert "ollama" in ids
        assert "gemini" in ids

    def test_each_provider_has_required_fields(self):
        for p in client.get("/providers", headers=_auth_headers()).json()["providers"]:
            for field in ("id", "name", "model", "configured", "rpm", "daily_tokens", "tier"):
                assert field in p


class TestAuthRoute:
    def test_login_returns_token(self):
        resp = client.post(
            "/auth/login",
            json={"login_id": AUTH_LOGIN_ID, "password": AUTH_LOGIN_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["token"]
        assert data["expires_in"] > 0

    def test_login_rejects_bad_credentials(self):
        resp = client.post(
            "/auth/login",
            json={"login_id": "wrong", "password": "bad"},
        )
        assert resp.status_code == 401
        _assert_error_shape(resp.json())
        assert resp.json()["error_type"] == "AUTH_INVALID"


class TestScrapeRoute:
    def test_scrape_finds_auth_form(self):
        headers = _auth_headers()
        with patch("main.fetch_html", return_value=(SAMPLE_HTML, "requests", "mock_b64")), \
             patch("main.analyze_auth_component", return_value=LLM_RESULT), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com/login", "provider": "openai"}, headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_found"] is True
        assert 0 <= data["auth_confidence"] <= 100
        assert data["screenshot_base64"] == "mock_b64"
        assert data["provider_used"] == "openai"
        assert data["tokens_used"]["total"] == 150
        assert "password" in data["fields_detected"]

    def test_scrape_no_auth_form(self):
        headers = _auth_headers()
        with patch("main.fetch_html", return_value=(NO_AUTH_HTML, "requests", None)), \
             patch("main.analyze_auth_component", return_value=LLM_RESULT), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com", "provider": "openai"}, headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_found"] is False
        assert data["auth_confidence"] == 0
        assert data["screenshot_base64"] is None
        assert data["html_snippet"] is None

    def test_scraper_error_returns_structured_json(self):
        err = ScraperError("SCRAPE_TIMEOUT", "Website Timed Out", "Took too long.", "Try again later.")
        headers = _auth_headers()
        with patch("main.fetch_html", side_effect=err), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://slow.example.com", "provider": "openai"}, headers=headers)

        assert resp.status_code == 502
        _assert_error_shape(resp.json())
        assert resp.json()["error_type"] == "SCRAPE_TIMEOUT"

    def test_llm_error_falls_back_to_rules_mode(self):
        err = LLMError("LLM_RATE_LIMIT", "Rate Limit", "Too many requests.", "Wait 60s.")
        headers = _auth_headers()
        with patch("main.fetch_html", return_value=(SAMPLE_HTML, "requests", "mock_b64")), \
             patch("main.analyze_auth_component", side_effect=err), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com/login", "provider": "openai"}, headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_mode"] == "rules"
        assert data["llm_fallback_reason"] == "LLM_RATE_LIMIT"
        assert "LLM analysis unavailable" in data["llm_analysis"]
        assert data["tokens_used"]["total"] == 0

    def test_invalid_provider_returns_structured_error(self):
        headers = _auth_headers()
        with patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com", "provider": "unknown_ai"}, headers=headers)
        assert resp.status_code == 400
        _assert_error_shape(resp.json())
        assert resp.json()["error_type"] == "INVALID_PROVIDER"

    def test_unconfigured_provider_returns_structured_error(self):
        headers = _auth_headers()
        with patch("main.is_configured", return_value=False):
            resp = client.post("/scrape", json={"url": "https://example.com", "provider": "gemini"}, headers=headers)
        assert resp.status_code == 400
        _assert_error_shape(resp.json())
        assert resp.json()["error_type"] == "PROVIDER_NOT_CONFIGURED"

    def test_invalid_url_returns_422(self):
        resp = client.post("/scrape", json={"url": "not-a-url", "provider": "openai"}, headers=_auth_headers())
        assert resp.status_code == 422

    def test_missing_url_returns_422(self):
        resp = client.post("/scrape", json={}, headers=_auth_headers())
        assert resp.status_code == 422

    def test_defaults_to_openai(self):
        headers = _auth_headers()
        with patch("main.fetch_html", return_value=(SAMPLE_HTML, "requests", "mock_b64")), \
             patch("main.analyze_auth_component", return_value=LLM_RESULT), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com/login"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["provider_used"] == "openai"
