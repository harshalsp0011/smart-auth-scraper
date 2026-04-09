# Changes, Tests, and Enhancements

---

## Changes Made (What & Why)

### llm.py — Improved prompt + increased snippet limit
- **What:** Updated `_build_prompt()` to ask for 4-5 sentences covering 5 specific categories: form type, input fields, alternative login methods (QR/passkey/SSO/OAuth), security features (CAPTCHA/CSRF/WebAuthn/remember me), and UX details (forgot password, register link, required field markers).
- **Why:** Old prompt asked for 2-3 sentences and only mentioned "notable features" vaguely — missed QR code login on Discord, passkey buttons, WebAuthn hints, register links. Now every feature in the HTML is explicitly asked for.
- **Also:** Increased snippet char limit from 3000 → 6000. Discord's form is 40,000 chars — the QR code section was beyond the old 3000 char cutoff and never reached the LLM.

### detector.py — Broadened password field detection
- **What:** Was only matching `<input type="password">`. Now also matches inputs where `name`, `aria-label`, `placeholder`, `id`, or `autocomplete` contains "password".
- **Why:** Demo and real sites sometimes use `type="text"` for the password field (e.g. `web-scraping.dev/login`). The old detector returned `auth_found: false` for these.
- **Also:** `_extract_field_types()` now labels these as "password" instead of "text".

### llm.py — Model corrections
- **Ollama:** Changed from `llama3.1:8b` → `gemma4:e4b` → `gemma3:4b` (first two don't exist on Ollama Cloud; confirmed by listing account's available models live).
- **OpenAI:** Changed from `gpt-4o-mini` → `gpt-4.1-mini` (project does not have access to `gpt-4o-mini`; listed available models to confirm).
- **Gemini:** Changed from `gemini-1.5-flash` → `gemini-2.0-flash` → `gemini-2.5-flash` (older models deprecated; correct ID found by calling `genai.list_models()`).

### Docker — Base image changed
- **What:** Changed from `python:3.12-slim` with manual Playwright install to `mcr.microsoft.com/playwright/python:v1.48.0-jammy`.
- **Why:** Debian trixie renamed `ttf-unifont` — the manual install path broke. Official image has everything pre-installed.

### main.py — load_dotenv() added
- **What:** Added `load_dotenv()` at top of `main.py`.
- **Why:** Without it, `.env` is only loaded if uvicorn is started from the project root. Adding it makes env vars load regardless of working directory.

### Anthropic removed, Ollama added
- **What:** Removed Anthropic provider, added Ollama Cloud.
- **Why:** Anthropic trial credits exhausted. Ollama Cloud provides a paid API using the same key format.

---

## Tests We Cover

All tests in `backend/tests/` are mocked — no real network or API calls required.

### test_scraper.py
- `test_fetch_returns_html` — requests returns valid HTML
- `test_raises_scraper_error_on_timeout` — Timeout → ScraperError with `SCRAPE_TIMEOUT`
- `test_raises_scraper_error_on_connection_error` — DNS/network fail → `SCRAPE_DNS_FAIL`
- `test_raises_scraper_error_on_403` — Blocked → `SCRAPE_BLOCKED`
- `test_raises_scraper_error_on_404` — Not found → `SCRAPE_NOT_FOUND`
- `test_uses_playwright_when_html_too_short` — requests returns < 500 chars → Playwright fallback triggered
- `test_uses_requests_when_html_is_sufficient` — requests returns > 500 chars → Playwright NOT called
- `test_scraper_error_has_all_fields` — error has error_type, title, message, suggestion

### test_detector.py
- `test_detects_standard_login_form` — `<input type="password">` → auth_found true
- `test_returns_false_when_no_password_field` — no password input → auth_found false
- `test_detects_fields_correctly` — field list includes email, password, submit
- `test_returns_html_snippet` — snippet is non-empty string
- `test_handles_empty_html` — empty string → auth_found false, no crash

### test_api.py
- `test_health_endpoint` — GET /health → `{"status": "ok"}`
- `test_providers_endpoint` — GET /providers → has providers list and default key
- `test_scrape_returns_result` — POST /scrape with valid URL → success shape
- `test_scraper_error_returns_structured_json` — ScraperError → 4-field JSON error
- `test_llm_error_returns_structured_json` — LLMError → 4-field JSON error
- `test_invalid_provider_returns_400` — unknown provider → 400 with LLM_INVALID_PROVIDER
- `test_unconfigured_provider_returns_400` — key missing → 400 with LLM_NOT_CONFIGURED
- `test_scrape_includes_provider_used` — response includes provider_used field
- `test_scrape_includes_tokens_used` — response includes tokens_used with input/output/total

---

## What We Have Not Tested (Gaps)

- Playwright fallback path is not tested end-to-end (only mocked)
- detector.py broadened matching (name/aria-label/placeholder) not yet covered by unit tests
- Ollama/Gemini/OpenAI error paths tested via mocks but not live API errors
- No test for empty page (page loads but has no body content)

---

## Possible Enhancements

### Functional
- **Batch URL scraping** — accept a list of URLs in one request, return results for all
- **Auth form scoring** — confidence score (0–100) on how likely the form is a real login vs. search/newsletter
- **Field-level detail** — return validation rules, required/optional, max length per field
- **Screenshot capture** — use Playwright to take a screenshot of the auth form alongside the HTML
- **Multi-form detection** — some pages have both login and signup forms; detect and return both

### Reliability
- **Retry logic** — auto-retry scrape once on transient errors (timeout, 429, 5xx)
- **Rate limit queue** — queue requests per provider so you never hit RPM limit
- **User-agent rotation** — cycle through browser user-agents to reduce blocking

### UX / UI
- **History panel** — show last N scraped URLs with results cached in localStorage
- **Copy button** — one-click copy for HTML snippet or LLM analysis
- **Dark mode** — CSS variable-based theme toggle
- **Export to JSON** — download full result as a `.json` file

### Deployment
- **Deploy backend** — Render or Railway (backend is already Dockerized, one-click deploy)
- **Deploy frontend** — Vercel or GitHub Pages (static HTML, zero config)
- **Environment check endpoint** — `GET /config` that shows which providers are configured without exposing keys

### Observability
- **Request logging** — log each scrape: URL, provider, tokens used, scrape method, duration
- **Error rate tracking** — count errors by type so you can see which provider fails most
