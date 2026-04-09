# Smart Auth Scraper

An **agentic AI-powered web scraper** that detects and analyzes login/authentication forms on any website. Built as an AI Engineer technical assessment.

---

## What It Does

Give it any URL. It:
1. Fetches the page HTML — using a simple HTTP request, or a real browser if the page is JavaScript-rendered
2. Finds the login/auth form inside that HTML
3. Sends just the form to an AI model (your choice of provider)
4. Returns a plain-English description + detected fields + raw HTML snippet + auth confidence (0-100) + screenshot

Every step has structured error handling — no vague messages.

---

## Why It's "Agentic"

Three components run in sequence, each making decisions based on the output of the previous:

```
User Input (URL)
    ↓
Agent 1 — Scraper (scraper.py)
  Decides: Can I fetch this with requests, or do I need a real browser?
  Acts:    Tries requests. If page has no form/input in static HTML → switches to Playwright.

    ↓
Agent 2 — Detector (detector.py)
  Decides: Is there an authentication form in this HTML?
  Acts:    Searches for password fields → walks up DOM to find the parent form → extracts it.

    ↓
Agent 3 — LLM (llm.py)
  Decides: What does this auth form mean in human language?
  Acts:    Reads the HTML snippet, identifies form type, fields, notable features.
  Returns: Plain-English description + token usage.

    ↓
Structured JSON → UI
```

Each agent handles its own errors and communicates failure context upstream.

---

## How Confidence and Screenshot Work

### Auth confidence score (0-100)
- Computed in `detector.py` using deterministic heuristics.
- High-weight signals include password fields, username/email fields, submit action, and auth-related keywords.
- The score is clamped to 0-100 and returned as `auth_confidence` in `POST /scrape`.

### Screenshot capture
- Captured by Playwright in `scraper.py` and returned as `screenshot_base64`.
- Capture priority:
  1. Form containing a password input
  2. First available form
  3. Viewport fallback screenshot
- Frontend renders it as an inline `data:image/png;base64,...` preview.

### Search-result URL warning popup
- The frontend checks for wrapper URLs from common search engines before scraping.
- If the user pastes a search result URL instead of the direct target page, the app shows a popup explaining the problem.
- The popup includes the extracted direct target URL when one is present in the query string.
- This prevents false "No Auth Form Detected" results caused by scraping the search page rather than the actual login page.

---

## Features

| Feature | Description |
|---|---|
| Smart scraping | requests → Playwright fallback for JS-rendered pages |
| Auth detection | Finds forms by password field (type, name, aria-label, placeholder) |
| Multi-provider AI | Switch between OpenAI, Ollama Cloud, Google Gemini from the UI |
| Field tooltips | Hover over detected fields to see what they mean and how detected |
| Auth confidence score | Heuristic 0-100 score indicating how likely the detected component is a real login form |
| Screenshot capture | Returns a Playwright screenshot of the detected form (or page fallback) alongside HTML |
| Search URL warning popup | Detects search-result wrapper URLs and explains why the scraper would analyze the wrong page |
| Frontend login gate | Full-screen access page that unlocks the dashboard after backend-verified login |
| Logout action | Clears current session token and returns user to login gate |
| Render cold-start toast | Shows a brief wake-up notice when free-tier backend is inactive |
| Analysis mode badge | Shows whether result came from LLM or deterministic rules fallback |
| HTML formatter | Snippet is pretty-printed with indentation + one-click copy button |
| Token usage | Shows input/output/total tokens per call on the provider card |
| Structured errors | Every failure has error_type, title, message, and suggestion |
| Error popup | Themed modal (red/yellow/blue) with full context — no vague messages |
| Print support | Clean print view — hides UI chrome, shows only results |
| Docker ready | Official Playwright image — runs anywhere with one command |

---

## AI Providers

| Provider | Model | Tier | Rate Limit |
|---|---|---|---|
| **OpenAI** | gpt-4.1-mini | Paid | 500 RPM |
| **Ollama Cloud** | gemma3:4b | Paid | 60 RPM |
| **Google Gemini** | gemini-2.5-flash | Free | 5 RPM / 250K TPM / 20 RPD |

You only need **at least one** key configured. Unconfigured providers are greyed out in the UI.

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| **Backend** | FastAPI + Uvicorn | Fast, auto-validates requests, async-ready |
| **Scraping** | requests | Simple HTTP — fast for static pages |
| **JS fallback** | Playwright + Chromium | Handles React/Angular login pages |
| **HTML parsing** | BeautifulSoup4 + lxml | Best Python DOM traversal, fast parser |
| **AI — OpenAI** | openai SDK | Paid, highest quality, most reliable |
| **AI — Ollama** | ollama SDK | Cloud API, alternative paid provider |
| **AI — Gemini** | google-generativeai | Free tier with decent limits |
| **Env vars** | python-dotenv | Loads .env automatically on startup |
| **Validation** | pydantic | Request/response model validation |
| **Frontend** | Vanilla HTML/JS/CSS | No framework — lightweight, fast |
| **Container** | Docker (Playwright base image) | Pre-installed Chromium + system deps |
| **Backend deploy** | Render | Supports Docker, free tier, GitHub auto-deploy |
| **Frontend deploy** | Vercel | Serves static files, free, auto-deploy on push |
| **Tests** | pytest + pytest-asyncio | Unit + integration tests, all mocked |

The frontend includes a login gate, but the credentials are verified by the backend and the frontend only receives an opaque session token.

---

## Project Structure

```
smart-auth-scraper/
├── backend/
│   ├── main.py          ← FastAPI: auth routes, providers, and scrape orchestration
│   ├── scraper.py       ← Fetch HTML (requests → Playwright fallback)
│   ├── detector.py      ← Find auth form using BeautifulSoup
│   ├── llm.py           ← Multi-provider AI analysis
│   ├── Dockerfile       ← For local Docker
│   ├── requirements.txt
│   └── tests/
│       ├── test_scraper.py
│       ├── test_detector.py
│       └── test_api.py
├── frontend/
│   ├── index.html       ← UI layout + error popup modal
│   ├── app.js           ← Provider switcher, scrape logic, tooltips, copy button
│   └── style.css        ← Styles, provider cards, popup themes, print
├── Dockerfile           ← Root-level Dockerfile for Render deployment
├── docker-compose.yml   ← Local Docker setup
├── .env.example         ← Template for API keys
└── doc/
  ├── README.md                      ← Doc index and reading order
  ├── edge-case-test-matrix.md       ← Edge-case coverage: working vs remaining
    ├── project-setup-and-mvp.md      ← Build checklist
    ├── system-deep-dive.md           ← Features, LLM flow, tech, infrastructure
    ├── architecture-and-setup.md     ← Architecture diagram + setup steps
    └── changes-tests-enhancements.md ← Changes made, test coverage, enhancement ideas
```

---

## API Reference

### `GET /health`
```json
{ "status": "ok" }
```

### `GET /providers`
```json
{
  "providers": [
    { "id": "openai",  "name": "OpenAI",        "model": "gpt-4.1-mini",    "rpm": 500, "configured": true,  "tier": "paid" },
    { "id": "ollama",  "name": "Ollama Cloud",   "model": "gemma3:4b",       "rpm": 60,  "configured": true,  "tier": "paid" },
    { "id": "gemini",  "name": "Google Gemini",  "model": "gemini-2.5-flash","rpm": 5,   "configured": false, "tier": "free" }
  ],
  "default": "openai"
}
```

### `POST /scrape`
**Request:**
```json
{ "url": "https://github.com/login", "provider": "openai" }
```

**Success response:**
```json
{
  "url": "https://github.com/login",
  "auth_found": true,
  "auth_confidence": 94,
  "html_snippet": "<form>...</form>",
  "screenshot_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "fields_detected": ["username", "password", "submit"],
  "llm_analysis": "This is a standard login form with username and password fields.",
  "analysis_mode": "llm",
  "llm_fallback_reason": null,
  "scrape_method": "requests",
  "provider_used": "openai",
  "tokens_used": { "input": 232, "output": 50, "total": 282 }
}
```

If the selected LLM provider fails, `/scrape` still succeeds with deterministic detection data:
- `analysis_mode` is `rules`
- `llm_fallback_reason` contains the LLM error type
- `llm_analysis` contains a fallback summary
- `tokens_used` is zeroed

**Error response:**
```json
{
  "error_type": "SCRAPE_BLOCKED",
  "title": "Access Blocked (403)",
  "message": "The site refused the scraper request.",
  "suggestion": "Try the direct login URL."
}
```

---

## Error Handling

| Category | Errors Covered |
|---|---|
| Scraping | Timeout, blocked (403), not found (404), DNS fail, SSL error, redirect loop, rate limited (429), server error (5xx), empty page |
| OpenAI | Invalid key, rate limit, quota exceeded, network error, API error |
| Ollama | Invalid key, rate limit, model not found, network error |
| Gemini | Invalid key, rate/quota limit, model not found, invalid request, service unavailable |
| Config | Provider not configured, unknown provider, package not installed |

---

## Setup

### Option A — Docker (recommended)

```bash
# 1. Clone
git clone <repo-url>
cd smart-auth-scraper

# 2. Add API keys and backend login credentials
cp .env.example .env
# Edit .env — add at least one AI provider key plus FRONTEND_LOGIN_ID and FRONTEND_LOGIN_PASSWORD

# 3. Build + run
docker compose up --build -d

# 4. Open frontend/index.html in your browser
```

- `backend/Dockerfile` is used by `docker-compose.yml` for local development.
- Root `Dockerfile` is used for Render deployment from repo root.
- Both images use the official Playwright Python base (`mcr.microsoft.com/playwright/python:v1.48.0-jammy`) so Chromium and required system dependencies are already included.
- The backend login credentials live in environment variables on the backend service: `FRONTEND_LOGIN_ID` and `FRONTEND_LOGIN_PASSWORD`.

### Option B — Local (virtual environment)

```bash
# 1. Create venv
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install
cd backend
pip install -r requirements.txt
playwright install chromium

# 3. Add API keys
cp .env.example .env

# 4. Start server
uvicorn main:app --reload

# 5. Open frontend/index.html in your browser
```

---

## Run Tests

```bash
source venv/bin/activate
cd backend
pytest tests/ -v
```

All tests are mocked — no real network or API calls needed.

---

## Deployment

### Backend → Render
1. Push repo to GitHub
2. Render → New Web Service → connect repo
3. Set **Dockerfile Path** to `./Dockerfile` (repo root)
4. Add env vars in Render dashboard (OPENAI_API_KEY, OLLAMA_API_KEY, GEMINI_API_KEY)
5. Deploy → get URL like `https://smart-auth-scraper.onrender.com`

### Frontend → Vercel
1. Vercel → New Project → connect repo
2. Set **Root Directory** to `frontend`
3. Framework Preset: `Other`, no build command required
4. Update `API_BASE` in `frontend/app.js` with your Render URL
5. Deploy

### Backend → Render login config
1. Add these env vars to the backend Render service:
  - `FRONTEND_LOGIN_ID`
  - `FRONTEND_LOGIN_PASSWORD`
2. Deploy / restart the backend so the login gate can verify credentials server-side.

---

## Environment Variables

| Variable | Provider |
|---|---|
| `OPENAI_API_KEY` | OpenAI |
| `OLLAMA_API_KEY` | Ollama Cloud |
| `GEMINI_API_KEY` | Google Gemini |

At least one must be set. Get keys at:
- OpenAI → platform.openai.com
- Ollama → ollama.com/settings/keys
- Gemini → aistudio.google.com
