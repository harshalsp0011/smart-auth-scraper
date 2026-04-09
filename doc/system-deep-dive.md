# System Deep Dive — Features, Tech, Infrastructure, LLM Flow

---

## What This System Does (Plain English)

You give it a URL. It:
1. Fetches the page HTML (like a browser would)
2. Finds the login/signup form inside that HTML
3. Sends just that form to an AI model
4. Returns a plain-English description of what the form does, what fields it has, and any notable features

Every step has error handling. Every failure tells you exactly what went wrong and what to do.

---

## Features — What We Built and Why

### 1. Smart Scraping (requests → Playwright fallback)
**What:** Tries to fetch the page using a simple HTTP request first. If the page has no `<form>` or `<input>` tags in the raw HTML (meaning JS renders them), automatically falls back to launching a real headless Chromium browser.

**Why:** Most sites work fine with simple requests (GitHub, web-scraping.dev). But React/Angular SPAs load their forms via JavaScript — requests gets a near-empty HTML shell. Playwright runs the full browser, waits for the form to appear, then grabs the rendered HTML.

**Trigger logic:**
```python
is_minimal    = len(html) < 500 or "<body" not in html.lower()
is_js_rendered = "<input" not in html.lower() and "<form" not in html.lower()
if is_minimal or is_js_rendered:
    → fall back to Playwright
```

**Playwright wait strategy:** Uses `wait_until="load"` (not `networkidle` — SPAs fire requests forever and never settle), then waits up to 8s for any `input` or `form` element to appear.

---

### 2. Auth Form Detection (BeautifulSoup)
**What:** Parses the full HTML and finds the authentication form by looking for password-related fields.

**Why:** We don't want to send the entire page HTML to the LLM — that's thousands of tokens and wastes money. We extract just the form.

**Detection logic (in order):**
1. Find `<input type="password">` — standard password fields
2. If none found, search all inputs for `name`, `aria-label`, `placeholder`, `id`, or `autocomplete` containing "password" — catches sites like `web-scraping.dev` that use `type="text"` for password
3. Walk up the DOM to find the parent `<form>` element
4. If no parent `<form>`, grab the nearest container (`<div>`, `<section>`)
5. Return the HTML snippet + list of field types

**Field classification:**
| Detected as | Rule |
|---|---|
| `password` | type=password OR name/aria-label contains "password" |
| `email` | type=email OR name/placeholder contains "email" |
| `username` | name contains "user", "login" |
| `submit` | type=submit or button |
| `text` | type=text, not classifiable by name |

---

### 3. Multi-Provider LLM Analysis
**What:** Sends the extracted HTML snippet to an AI model and gets back a 4–5 sentence plain-English description covering all notable features of the form.

**Why LLM is called:**
- HTML is machine-readable but not human-friendly
- A `<form action="/session">` with `<input name="authenticity_token">` means nothing to a non-developer
- The LLM reads the form like a human would and describes: type of form, fields, alternative login methods, security features, and UX details

**How the LLM call works:**
```
1. HTML snippet extracted from detector.py
2. _build_prompt(html_snippet, url) wraps it in a structured prompt:
   - Sets the role: "You are analyzing the HTML of a login/authentication form"
   - Provides the URL for context
   - Passes the first 6000 chars of the HTML snippet (increased from 3000 to catch full forms like Discord)
   - Asks for: form type, input fields, alternative login methods (QR/passkey/SSO/OAuth),
     security features (CAPTCHA/CSRF/WebAuthn), UX details (forgot password/register links)
3. Prompt sent to selected provider's API
4. Response parsed → returns {"analysis": str, "tokens_used": {...}}
```

**Why 3000 char limit on snippet?** LLM input tokens cost money. Most forms are well under 3000 chars. Cutting off prevents runaway costs on huge forms.

**Providers:**
| Provider | Model | Why we use it |
|---|---|---|
| OpenAI | gpt-4.1-mini | Fastest, highest quality, most reliable |
| Ollama Cloud | gemma3:4b | Alternative paid API, good for testing |
| Google Gemini | gemini-2.5-flash | Free tier — 5 RPM, 250K TPM, 20 RPD |

**LLM is NOT called when:**
- No auth form found (`html_snippet` is None) → returns "No authentication component was found"
- Provider not configured (no API key) → returns `LLM_NOT_CONFIGURED` error
- Unknown provider name → returns `LLM_INVALID_PROVIDER` error

---

### 4. Structured Error System
**What:** Every failure — whether scraping, LLM, or config — returns a 4-field JSON object instead of a generic HTTP error.

**Why:** Vague errors ("500 Internal Server Error") tell you nothing. A structured error tells you exactly what failed, why, and what to do.

**Shape:**
```json
{
  "error_type": "SCRAPE_BLOCKED",
  "title": "Access Blocked (403)",
  "message": "The site refused the scraper request.",
  "suggestion": "Try a direct login URL."
}
```

**Scrape errors mapped:**
| error_type | When it triggers |
|---|---|
| SCRAPE_TIMEOUT | Site took >15s to respond |
| SCRAPE_BLOCKED | HTTP 403 |
| SCRAPE_NOT_FOUND | HTTP 404 |
| SCRAPE_DNS_ERROR | Domain doesn't exist / no internet |
| SCRAPE_SSL_ERROR | Invalid/expired SSL cert |
| SCRAPE_REDIRECT_LOOP | Too many redirects |
| SCRAPE_RATE_LIMITED | HTTP 429 |
| SCRAPE_SERVER_ERROR | HTTP 5xx |
| SCRAPE_EMPTY | Page loaded but returned no content |

**LLM errors mapped:**
| error_type | When it triggers |
|---|---|
| LLM_INVALID_KEY | API key rejected (401) |
| LLM_RATE_LIMIT | Too many requests (429) |
| LLM_QUOTA_EXCEEDED | Billing quota hit |
| LLM_NETWORK_ERROR | Cannot reach API |
| LLM_OVERLOADED | Provider temporarily unavailable |
| LLM_NOT_CONFIGURED | No API key set |
| LLM_MODEL_NOT_FOUND | Model ID doesn't exist on provider |
| LLM_PACKAGE_MISSING | Python SDK not installed |

---

### 5. Provider Switcher UI
**What:** Three cards at the top of the UI — one per AI provider. Click to select. Shows model name, tier (free/paid), RPM limit, and whether the provider is configured.

**Why:** Different providers have different limits and costs. The user should be able to switch without restarting the server or editing code.

**How it works:**
- On page load, frontend calls `GET /providers`
- Backend reads ENV_KEYS for each provider, checks if the key is set
- Returns `configured: true/false` per provider
- Unconfigured providers are greyed out and non-clickable
- Selected provider is sent in every `POST /scrape` request body

---

### 6. Token Usage Display
**What:** After each scrape, shows how many tokens were used (input, output, total) on the provider card and in the results.

**Why:** Helps you monitor API costs, especially on paid providers. Shows the cost of each call.

---

### 7. Error Popup Modal
**What:** When any error occurs, shows a themed modal popup instead of replacing the page or logging to console.

**Themes:**
- Red (danger) — hard errors: blocked, invalid key, DNS fail
- Yellow (warning) — soft errors: timeout, rate limit, redirect loop
- Blue (info) — config issues: provider not configured, unknown provider

---

### 8. Field Tooltips
**What:** Each detected field tag has a `?` icon. Hovering shows a tooltip explaining what the field is and how it was detected.

**Why:** Non-developers looking at "email / password / text" don't know what "text" means or why it's classified differently.

---

### 9. HTML Snippet — Formatted + Copy Button
**What:** The extracted form HTML is pretty-printed with proper indentation. A "Copy" button copies it to clipboard (turns green, says "Copied!").

**Why:** Raw HTML is one long unreadable string. Formatted HTML is readable and copy-pasteable for inspection.

---

### 10. Print Support
**What:** A Print button in the results toolbar. `@media print` CSS hides the header, provider cards, URL form, and print button — shows only the results.

**Why:** Assessors or reviewers may want a clean printout of the analysis.

---

## Infrastructure

### Local Development
```
Browser → frontend/index.html (file://) → app.js → http://localhost:8000
                                                          ↓
                                                    uvicorn (FastAPI)
                                                          ↓
                                                    Docker container
                                                    (or venv locally)
```

### Docker Setup
- Base image: `mcr.microsoft.com/playwright/python:v1.48.0-jammy`
  - Why this image: It comes with Python, Chromium, and all Playwright system dependencies pre-installed. Using a plain Python image and installing Playwright manually breaks on newer Debian (package names changed).
- `backend/Dockerfile` — for local Docker
- `Dockerfile` (repo root) — for Render deployment (Render builds from repo root, not from `backend/`)
- `docker-compose.yml` — loads `.env`, maps port 8000

### Production Deployment
```
Browser → Vercel (frontend/index.html) → Render (FastAPI backend)
```
- **Vercel:** Serves static `frontend/` folder. Root directory set to `frontend` in Vercel settings.
- **Render:** Runs the Docker container. Dockerfile at repo root. Env vars set in Render dashboard.
- **CORS:** Backend allows all origins (`allow_origins=["*"]`) so Vercel frontend can call Render backend cross-domain.

---

## Full Data Flow (One Scrape Request)

```
1. User enters URL + selects provider in UI
2. app.js → POST /scrape { url, provider }
3. main.py receives request, validates provider
4. scraper.py:
   a. fetch_with_requests(url) → gets raw HTML
   b. If no <form>/<input> in HTML → fetch_with_playwright(url)
      - Launches headless Chromium
      - Navigates to URL, wait_until="load"
      - Waits up to 8s for input/form to appear
      - Returns rendered HTML
5. detector.py:
   a. BeautifulSoup parses HTML
   b. Finds password-related input (by type or name/aria-label/placeholder)
   c. Walks up DOM to parent <form>
   d. Extracts HTML snippet + field types
6. llm.py:
   a. If no snippet → return "No auth component found" (no LLM call)
   b. _build_prompt(snippet, url) → structured prompt string
   c. Call selected provider's API (OpenAI / Ollama / Gemini)
   d. Parse response → {analysis, tokens_used}
7. main.py builds ScrapeResponse JSON
8. app.js receives JSON → renderResults()
   - Shows status badge, AI analysis, field tags with tooltips
   - Shows formatted HTML snippet with copy button
   - Updates token count on provider card
```

---

## Tech Stack Summary

| Layer | Technology | Version | Why |
|---|---|---|---|
| Backend API | FastAPI | 0.115.0 | Auto request validation, fast, async-ready |
| ASGI server | Uvicorn | 0.30.6 | Runs FastAPI, supports hot reload |
| Static scraping | requests | 2.32.3 | Simple HTTP — fast for non-JS pages |
| Dynamic scraping | Playwright | 1.48.0 | Headless Chromium — handles JS-rendered pages |
| HTML parsing | BeautifulSoup4 | 4.12.3 | Best Python DOM traversal library |
| HTML parser | lxml | 5.3.0 | Faster than html.parser for large HTML |
| OpenAI SDK | openai | 1.54.0 | Official SDK — handles auth, retries, errors |
| Ollama SDK | ollama | 0.4.4 | Ollama Cloud API client |
| Gemini SDK | google-generativeai | 0.8.3 | Google's official Generative AI SDK |
| Env vars | python-dotenv | 1.0.1 | Loads .env into os.environ on startup |
| Data validation | pydantic | 2.9.2 | Request/response model validation in FastAPI |
| HTTP client | httpx | 0.27.2 | Async HTTP for FastAPI test client |
| Testing | pytest | 8.3.3 | Unit + integration tests |
| Async tests | pytest-asyncio | 0.24.0 | Async test support for FastAPI routes |
| Container | Docker | — | Reproducible environment, easy deploy |
| Container base | mcr.microsoft.com/playwright/python:v1.48.0-jammy | — | Pre-installed Chromium + system deps |
| Frontend | Vanilla HTML/JS/CSS | — | No framework needed — lightweight, fast |
| Deployment (backend) | Render | — | Supports Docker, free tier, GitHub integration |
| Deployment (frontend) | Vercel | — | Serves static files, free, auto-deploy on push |
