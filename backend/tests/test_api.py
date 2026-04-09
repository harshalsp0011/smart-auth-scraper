"""
test_api.py — Integration tests for FastAPI routes.
Mocks scraper and LLM so no real network or API calls are made.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from unittest.mock import patch
from scraper import ScraperError
from llm import LLMError
from main import app

client = TestClient(app)

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


class TestHealthRoute:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestProvidersRoute:
    def test_returns_all_three_providers(self):
        resp = client.get("/providers")
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()["providers"]]
        assert "openai" in ids
        assert "anthropic" in ids
        assert "gemini" in ids

    def test_each_provider_has_required_fields(self):
        for p in client.get("/providers").json()["providers"]:
            for field in ("id", "name", "model", "configured", "rpm", "daily_tokens", "tier"):
                assert field in p


class TestScrapeRoute:
    def test_scrape_finds_auth_form(self):
        with patch("main.fetch_html", return_value=(SAMPLE_HTML, "requests")), \
             patch("main.analyze_auth_component", return_value=LLM_RESULT), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com/login", "provider": "openai"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_found"] is True
        assert data["provider_used"] == "openai"
        assert data["tokens_used"]["total"] == 150
        assert "password" in data["fields_detected"]

    def test_scrape_no_auth_form(self):
        with patch("main.fetch_html", return_value=(NO_AUTH_HTML, "requests")), \
             patch("main.analyze_auth_component", return_value=LLM_RESULT), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com", "provider": "openai"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_found"] is False
        assert data["html_snippet"] is None

    def test_scraper_error_returns_structured_json(self):
        err = ScraperError("SCRAPE_TIMEOUT", "Website Timed Out", "Took too long.", "Try again later.")
        with patch("main.fetch_html", side_effect=err), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://slow.example.com", "provider": "openai"})

        assert resp.status_code == 502
        _assert_error_shape(resp.json())
        assert resp.json()["error_type"] == "SCRAPE_TIMEOUT"

    def test_llm_error_returns_structured_json(self):
        err = LLMError("LLM_RATE_LIMIT", "Rate Limit", "Too many requests.", "Wait 60s.")
        with patch("main.fetch_html", return_value=(SAMPLE_HTML, "requests")), \
             patch("main.analyze_auth_component", side_effect=err), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com/login", "provider": "openai"})

        assert resp.status_code == 502
        _assert_error_shape(resp.json())
        assert resp.json()["error_type"] == "LLM_RATE_LIMIT"

    def test_invalid_provider_returns_structured_error(self):
        with patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com", "provider": "unknown_ai"})
        assert resp.status_code == 400
        _assert_error_shape(resp.json())
        assert resp.json()["error_type"] == "INVALID_PROVIDER"

    def test_unconfigured_provider_returns_structured_error(self):
        with patch("main.is_configured", return_value=False):
            resp = client.post("/scrape", json={"url": "https://example.com", "provider": "gemini"})
        assert resp.status_code == 400
        _assert_error_shape(resp.json())
        assert resp.json()["error_type"] == "PROVIDER_NOT_CONFIGURED"

    def test_invalid_url_returns_422(self):
        resp = client.post("/scrape", json={"url": "not-a-url", "provider": "openai"})
        assert resp.status_code == 422

    def test_missing_url_returns_422(self):
        resp = client.post("/scrape", json={})
        assert resp.status_code == 422

    def test_defaults_to_openai(self):
        with patch("main.fetch_html", return_value=(SAMPLE_HTML, "requests")), \
             patch("main.analyze_auth_component", return_value=LLM_RESULT), \
             patch("main.is_configured", return_value=True):
            resp = client.post("/scrape", json={"url": "https://example.com/login"})
        assert resp.status_code == 200
        assert resp.json()["provider_used"] == "openai"
