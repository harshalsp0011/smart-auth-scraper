"""
test_scraper.py — Unit tests for scraper.py
Uses mocked HTTP responses so no real network calls are made.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scraper import fetch_with_requests, fetch_html, ScraperError
from requests.exceptions import Timeout, ConnectionError as ReqConnectionError

# Long enough HTML to not trigger the Playwright fallback (>500 chars, has <body)
SAMPLE_HTML = (
    "<html><body>"
    "<form action='/login'>"
    "<input type='text' name='username'/>"
    "<input type='password' name='password'/>"
    "<button type='submit'>Login</button>"
    "</form>"
    "</body></html>"
    + "<!-- padding -->" * 30  # push past 500 chars
)

SHORT_HTML = "<html></html>"
SCRIPT_ONLY_FORM_TEXT_HTML = (
    "<html><body>"
    "<script>const template = \"<form><input type='password'></form>\";</script>"
    "<div id='app'>Loading...</div>"
    "</body></html>"
    + "<!-- padding -->" * 40
)
LOGIN_SHELL_NON_AUTH_FORM_HTML = (
    "<html><body>"
    "<form><input type='text' name='search'><button>Search</button></form>"
    "</body></html>"
    + "<!-- padding -->" * 40
)


class TestFetchWithRequests:
    def test_returns_html_on_success(self):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status.return_value = None

        with patch("scraper.requests.get", return_value=mock_resp):
            result = fetch_with_requests("https://example.com")

        assert result == SAMPLE_HTML

    def test_raises_scraper_error_on_timeout(self):
        with patch("scraper.requests.get", side_effect=Timeout()):
            with pytest.raises(ScraperError) as exc_info:
                fetch_with_requests("https://example.com")
        assert exc_info.value.error_type == "SCRAPE_TIMEOUT"

    def test_raises_scraper_error_on_connection_error(self):
        with patch("scraper.requests.get", side_effect=ReqConnectionError()):
            with pytest.raises(ScraperError) as exc_info:
                fetch_with_requests("https://example.com")
        assert exc_info.value.error_type == "SCRAPE_DNS_ERROR"

    def test_scraper_error_has_all_fields(self):
        with patch("scraper.requests.get", side_effect=Timeout()):
            with pytest.raises(ScraperError) as exc_info:
                fetch_with_requests("https://example.com")
        err = exc_info.value
        assert err.error_type
        assert err.title
        assert err.message
        assert err.suggestion


class TestFetchHtml:
    def test_uses_requests_when_html_is_sufficient(self):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status.return_value = None

        with patch("scraper.requests.get", return_value=mock_resp), \
             patch("scraper._take_screenshot", return_value="mock_b64"):
            html, method, screenshot = fetch_html("https://example.com")

        assert html == SAMPLE_HTML
        assert method == "requests"
        assert screenshot == "mock_b64"

    def test_falls_back_to_playwright_on_short_html(self):
        mock_resp = MagicMock()
        mock_resp.text = SHORT_HTML
        mock_resp.raise_for_status.return_value = None

        with patch("scraper.requests.get", return_value=mock_resp), \
             patch("scraper.fetch_with_playwright", return_value=(SAMPLE_HTML, "mock_b64")):
            html, method, screenshot = fetch_html("https://example.com")

        assert html == SAMPLE_HTML
        assert method == "playwright"
        assert screenshot == "mock_b64"

    def test_falls_back_to_playwright_when_form_only_exists_in_script_text(self):
        mock_resp = MagicMock()
        mock_resp.text = SCRIPT_ONLY_FORM_TEXT_HTML
        mock_resp.raise_for_status.return_value = None

        with patch("scraper.requests.get", return_value=mock_resp), \
             patch("scraper.fetch_with_playwright", return_value=(SAMPLE_HTML, "mock_b64")):
            html, method, screenshot = fetch_html("https://discord.com/login")

        assert html == SAMPLE_HTML
        assert method == "playwright"
        assert screenshot == "mock_b64"

    def test_falls_back_to_playwright_for_auth_intent_url_without_password_signal(self):
        mock_resp = MagicMock()
        mock_resp.text = LOGIN_SHELL_NON_AUTH_FORM_HTML
        mock_resp.raise_for_status.return_value = None

        with patch("scraper.requests.get", return_value=mock_resp), \
             patch("scraper.fetch_with_playwright", return_value=(SAMPLE_HTML, "mock_b64")):
            html, method, screenshot = fetch_html("https://discord.com/login")

        assert html == SAMPLE_HTML
        assert method == "playwright"
        assert screenshot == "mock_b64"

    def test_returns_requests_html_if_playwright_also_fails(self):
        mock_resp = MagicMock()
        mock_resp.text = SHORT_HTML
        mock_resp.raise_for_status.return_value = None

        with patch("scraper.requests.get", return_value=mock_resp), \
             patch("scraper.fetch_with_playwright", return_value=("", None)), \
             patch("scraper._take_screenshot", return_value=None):
            html, method, screenshot = fetch_html("https://example.com")

        assert html == SHORT_HTML
        assert method == "requests"
        assert screenshot is None

    def test_raises_scraper_error_when_requests_fails_and_playwright_empty(self):
        with patch("scraper.fetch_with_requests", side_effect=ScraperError(
            "SCRAPE_BLOCKED", "Blocked", "Site blocked the request.", "Try another URL."
        )), patch("scraper.fetch_with_playwright", return_value=("", None)):
            with pytest.raises(ScraperError) as exc_info:
                fetch_html("https://blocked.example.com")
        assert exc_info.value.error_type == "SCRAPE_BLOCKED"
