"""
scraper.py — Fetch raw HTML from a URL.
Strategy: try requests first (fast, lightweight).
If the page is empty or blocked, fall back to Playwright (handles JS-rendered pages).
Returns (html, method) on success, raises ScraperError on failure.
"""

import requests
from requests.exceptions import (
    ConnectionError, Timeout, TooManyRedirects, SSLError, HTTPError, RequestException
)


class ScraperError(Exception):
    """Structured scraping error with type, title, message, and suggestion."""
    def __init__(self, error_type: str, title: str, message: str, suggestion: str = ""):
        self.error_type = error_type
        self.title = title
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 15


def fetch_with_requests(url: str) -> str:
    """Fetch HTML using requests. Raises ScraperError on known failures."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        return response.text

    except Timeout:
        raise ScraperError(
            error_type="SCRAPE_TIMEOUT",
            title="Website Timed Out",
            message=f"The website '{url}' took too long to respond (>{TIMEOUT}s).",
            suggestion="The site may be slow or blocking scrapers. Try again or use a different URL.",
        )
    except SSLError:
        raise ScraperError(
            error_type="SCRAPE_SSL_ERROR",
            title="SSL Certificate Error",
            message=f"Could not establish a secure connection to '{url}'.",
            suggestion="The site may have an invalid or expired SSL certificate.",
        )
    except TooManyRedirects:
        raise ScraperError(
            error_type="SCRAPE_REDIRECT_LOOP",
            title="Redirect Loop Detected",
            message=f"'{url}' redirected too many times.",
            suggestion="Check the URL — it may be misconfigured or require authentication to access.",
        )
    except ConnectionError:
        raise ScraperError(
            error_type="SCRAPE_DNS_ERROR",
            title="Cannot Reach Website",
            message=f"Could not connect to '{url}'. The domain may not exist or the server is down.",
            suggestion="Double-check the URL spelling, or the site may be offline.",
        )
    except HTTPError as e:
        status = e.response.status_code if e.response else "?"
        if status == 403:
            raise ScraperError(
                error_type="SCRAPE_BLOCKED",
                title="Access Blocked (403)",
                message=f"'{url}' refused the request. The site is blocking scrapers.",
                suggestion="This site actively blocks bots. Try the Playwright fallback or use a different URL.",
            )
        elif status == 404:
            raise ScraperError(
                error_type="SCRAPE_NOT_FOUND",
                title="Page Not Found (404)",
                message=f"The page at '{url}' does not exist.",
                suggestion="Check the URL — the page may have moved or been removed.",
            )
        elif status == 429:
            raise ScraperError(
                error_type="SCRAPE_RATE_LIMITED",
                title="Rate Limited by Website (429)",
                message=f"'{url}' is rate-limiting requests. Too many requests sent.",
                suggestion="Wait a moment before trying again.",
            )
        elif status and str(status).startswith("5"):
            raise ScraperError(
                error_type="SCRAPE_SERVER_ERROR",
                title=f"Website Server Error ({status})",
                message=f"'{url}' returned a server error ({status}). The site may be down.",
                suggestion="Try again later — the issue is on the website's end.",
            )
        else:
            raise ScraperError(
                error_type="SCRAPE_HTTP_ERROR",
                title=f"HTTP Error {status}",
                message=f"'{url}' returned HTTP {status}.",
                suggestion="Check the URL and try again.",
            )
    except RequestException as e:
        raise ScraperError(
            error_type="SCRAPE_FAILED",
            title="Scrape Failed",
            message=f"Could not fetch '{url}': {str(e)}",
            suggestion="Check the URL and your internet connection.",
        )


def fetch_with_playwright(url: str) -> str:
    """Fetch HTML using Playwright. Returns empty string on failure (used as silent fallback)."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers(HEADERS)
            # Use "load" not "networkidle" — SPAs fire requests forever and never reach networkidle
            page.goto(url, timeout=TIMEOUT * 1000, wait_until="load")
            # Wait up to 8s for form/input to appear after JS renders
            try:
                page.wait_for_selector("input, form", timeout=8000)
            except Exception:
                pass  # no form appeared — return whatever we have
            html = page.content()
            browser.close()
            return html
    except Exception:
        return ""


def fetch_html(url: str) -> tuple[str, str]:
    """
    Fetch HTML from a URL. Returns (html, method_used).
    Raises ScraperError if the page cannot be fetched at all.
    """
    try:
        html = fetch_with_requests(url)
    except ScraperError:
        # requests failed with a known error — try Playwright silently
        playwright_html = fetch_with_playwright(url)
        if playwright_html and len(playwright_html) >= 500:
            return playwright_html, "playwright"
        raise  # re-raise the original ScraperError

    # If HTML looks empty/minimal OR has no form/input elements, try Playwright
    is_minimal = len(html) < 500 or "<body" not in html.lower()
    is_js_rendered = "<input" not in html.lower() and "<form" not in html.lower()
    if is_minimal or is_js_rendered:
        playwright_html = fetch_with_playwright(url)
        if playwright_html:
            return playwright_html, "playwright"

    if not html:
        raise ScraperError(
            error_type="SCRAPE_EMPTY",
            title="Empty Page",
            message=f"'{url}' returned no content.",
            suggestion="The page may require JavaScript — try a direct login URL.",
        )

    return html, "requests"
