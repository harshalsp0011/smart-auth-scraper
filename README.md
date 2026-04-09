# Smart Auth Scraper

An **agentic AI-powered web scraper** that detects and analyzes login/authentication forms on any website. Built as an AI Engineer technical assessment.

---

## What Is "Agentic" About This System?

This is not just a scraper — it is an **agentic pipeline** where multiple components reason and act in sequence, each making decisions based on the output of the previous step:

```
User Input (URL)
    ↓
Agent 1 — Scraper
  Decides: Can I fetch this with requests, or do I need Playwright?
  Acts:    Tries requests first. If page looks JS-rendered → switches to Playwright automatically.

    ↓
Agent 2 — Detector
  Decides: Is there an authentication form in this HTML?
  Acts:    Searches for password fields → walks up DOM to find the parent form → extracts it.

    ↓
Agent 3 — LLM (OpenAI / Anthropic / Gemini)
  Decides: What does this auth form mean in human language?
  Acts:    Reads the HTML snippet, identifies form type, fields, and notable features.
  Returns: Plain-English description + token usage.

    ↓
Structured Result → UI
```

Each agent handles its own errors and communicates failure context upstream — the system tells you **exactly what went wrong and why**, not just "error 500".

---

## What It Can Do

- Scrape **any website URL** — static or JavaScript-rendered
- Detect **login, signup, password reset, and SSO** authentication forms
- Extract the **exact HTML snippet** containing the form
- Identify **field types** — username, email, password, submit, remember-me
- Analyze the form using **AI** and return a plain-English description
- Switch between **3 AI providers** (OpenAI, Anthropic, Google Gemini) from the UI
- Show **token usage** per API call — input, output, total
- Show **rate limits** for each provider so you know what you're working with
- Handle and display **every possible error** with context and a fix suggestion — scraping failures, invalid API keys, rate limits, quota exceeded, DNS errors, blocked sites, and more
- Fall back to **Playwright** automatically when a site requires JavaScript rendering

---

## AI Providers

| Provider | Model | Tier | Rate Limit | Why We Use It |
|---|---|---|---|---|
| **OpenAI** | gpt-4o-mini | Paid | 500 RPM | Fastest, highest quality, most reliable |
| **Anthropic** | claude-haiku-4-5 | Paid | 50 RPM | Strong reasoning, trial credits on signup then paid |
| **Google Gemini** | gemini-1.5-flash | Free | 15 RPM / 1M tokens/day | Best free tier limits |

You only need **at least one** key configured. Unconfigured providers are greyed out in the UI.

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| **Backend** | FastAPI (Python) | Lightweight, fast, auto-validates requests, easy to deploy |
| **Scraping** | requests | Simple and fast for static HTML pages |
| **JS Fallback** | Playwright + Chromium | Handles React/Angular login pages that need JavaScript |
| **HTML Parsing** | BeautifulSoup4 | Best Python library for DOM traversal and element extraction |
| **AI Analysis** | OpenAI / Anthropic / Gemini | LLM interprets the form and gives a human-readable description |
| **Frontend** | Vanilla HTML/JS/CSS | No framework needed — keeps it lightweight and fast |
| **Container** | Docker + docker-compose | Reproducible environment, easy to run anywhere |
| **Tests** | pytest | Unit + integration tests, all mocked — no API calls needed |

---

## Project Structure

```
smart-auth-scraper/
├── backend/
│   ├── main.py          ← FastAPI: GET /health, GET /providers, POST /scrape
│   ├── scraper.py       ← Fetch HTML (requests → Playwright fallback + error classification)
│   ├── detector.py      ← Find auth form using BeautifulSoup
│   ├── llm.py           ← Multi-provider AI analysis (OpenAI, Anthropic, Gemini)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/
│       ├── test_scraper.py   ← Unit tests for fetch logic
│       ├── test_detector.py  ← Unit tests for auth detection
│       └── test_api.py       ← Integration tests for all API routes
├── frontend/
│   ├── index.html       ← UI layout + error popup modal
│   ├── app.js           ← Provider switcher, API calls, error handling
│   └── style.css        ← Styles + popup themes (danger / warning / info)
├── docker-compose.yml
├── .env.example
└── doc/                 ← Session logs, architecture notes, setup guide
```

---

## API Reference

### `GET /health`
```json
{ "status": "ok" }
```

### `GET /providers`
Returns all AI providers with config status, model, and rate limits.
```json
{
  "providers": [
    { "id": "openai", "name": "OpenAI", "model": "gpt-4o-mini", "rpm": 500, "configured": true, "tier": "paid" },
    { "id": "anthropic", "name": "Anthropic (Claude)", "model": "claude-haiku-4-5", "rpm": 5, "configured": true, "tier": "free" },
    { "id": "gemini", "name": "Google Gemini", "model": "gemini-1.5-flash", "rpm": 15, "configured": false, "tier": "free" }
  ],
  "default": "openai"
}
```

### `POST /scrape`
**Request:**
```json
{ "url": "https://example.com/login", "provider": "openai" }
```

**Success Response:**
```json
{
  "url": "https://example.com/login",
  "auth_found": true,
  "html_snippet": "<form>...</form>",
  "fields_detected": ["email", "password", "submit"],
  "llm_analysis": "This is a standard login form with email and password fields and a remember-me checkbox.",
  "scrape_method": "requests",
  "provider_used": "openai",
  "tokens_used": { "input": 142, "output": 64, "total": 206 }
}
```

**Error Response (all errors):**
```json
{
  "error_type": "SCRAPE_BLOCKED",
  "title": "Access Blocked (403)",
  "message": "The site refused the scraper request.",
  "suggestion": "Try the direct login URL or switch to Playwright mode."
}
```

---

## Error Handling

Every failure returns a structured error — no vague messages. Errors are shown as a themed popup in the UI.

| Category | Errors Covered |
|---|---|
| Scraping | Timeout, 403 blocked, 404 not found, DNS fail, SSL error, redirect loop, rate limited, empty page |
| OpenAI | Invalid key, rate limit, quota exceeded, network error |
| Anthropic | Invalid key, rate limit, server overloaded, network error |
| Gemini | Invalid key, rate/quota limit, network error |
| Config | Provider not configured, unknown provider, server not running |

---

## Setup

### Option A — Docker (recommended)

```bash
# 1. Clone
git clone <repo-url>
cd smart-auth-scraper

# 2. Add API keys
cp .env.example .env
# Edit .env — add at least one key

# 3. Run
docker compose up -d

# 4. Open frontend/index.html in your browser
```

### Option B — Local (virtual environment)

```bash
# 1. Create venv
python3 -m venv venv
source venv/bin/activate

# 2. Install
cd backend
pip install -r requirements.txt
playwright install chromium

# 3. Add API keys
cp .env.example .env

# 4. Start server
uvicorn main:app --reload --reload-exclude venv

# 5. Open frontend/index.html in your browser
```

---

## Run Tests

```bash
source venv/bin/activate
cd backend
pytest tests/ -v
```

28 tests — all mocked, no real network or API calls needed.

---

## Environment Variables

| Variable | Provider | Required |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI | At least one must be set |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) | At least one must be set |
| `GEMINI_API_KEY` | Google Gemini | At least one must be set |

Get your keys:
- OpenAI → [platform.openai.com](https://platform.openai.com)
- Anthropic → [console.anthropic.com](https://console.anthropic.com)
- Gemini → [aistudio.google.com](https://aistudio.google.com)
