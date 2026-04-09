# Architecture, Tools & Setup

---

## What We Built

A web app that takes any URL, scrapes it, finds the login form, and uses AI to describe it.

---

## Architecture

```
Browser (frontend)
    ↓  enters URL + picks AI provider
FastAPI (backend)
    ↓  fetches page HTML
scraper.py          → requests (fast) → Playwright fallback (JS pages)
    ↓  raw HTML
detector.py         → BeautifulSoup → finds <form> with <input type="password">
    ↓  HTML snippet
llm.py              → OpenAI / Anthropic / Gemini → plain-English description
    ↓  JSON response
Browser (frontend)  → shows result + tokens used + error popup if anything fails
```

---

## Tools & Why

| Tool | Purpose |
|---|---|
| **FastAPI** | Backend API — fast, lightweight, auto-validates request/response |
| **requests** | Fetch HTML from URLs — simple and fast for static pages |
| **Playwright** | Fallback for JS-rendered pages (React, Angular login pages) |
| **BeautifulSoup4** | Parse HTML and find auth form elements |
| **OpenAI (gpt-4o-mini)** | AI analysis — paid, highest quality, 500 RPM |
| **Anthropic (claude-haiku-4-5)** | AI analysis — free tier, 5 RPM |
| **Google Gemini (gemini-1.5-flash)** | AI analysis — free tier, 15 RPM, 1M tokens/day |
| **Vanilla HTML/JS/CSS** | Frontend — no framework, lightweight and fast to load |
| **pytest** | Tests — unit + integration, all mocked (no real API calls needed) |

---

## Project Structure

```
smart-auth-scraper/
├── backend/
│   ├── main.py          ← FastAPI routes: GET /health, GET /providers, POST /scrape
│   ├── scraper.py       ← Fetch HTML (requests → Playwright fallback)
│   ├── detector.py      ← Find auth form in HTML (BeautifulSoup)
│   ├── llm.py           ← AI analysis (OpenAI / Anthropic / Gemini)
│   ├── requirements.txt
│   └── tests/
│       ├── test_scraper.py
│       ├── test_detector.py
│       └── test_api.py
├── frontend/
│   ├── index.html       ← UI layout + error popup modal
│   ├── app.js           ← API calls, provider switcher, error popup logic
│   └── style.css        ← Styles including provider cards + popup themes
├── .env.example         ← Template for API keys
├── README.md
└── doc/
```

---

## API Endpoints

| Method | Route | What it does |
|---|---|---|
| GET | `/health` | Check server is running |
| GET | `/providers` | List all 3 AI providers, their limits, and config status |
| POST | `/scrape` | Scrape a URL and return auth form + AI analysis |

---

## Error System

Every error returns:
```json
{
  "error_type": "SCRAPE_BLOCKED",
  "title": "Access Blocked (403)",
  "message": "The site refused the scraper request.",
  "suggestion": "Try a direct login URL or use Playwright mode."
}
```

Mapped categories:
- **Scrape errors** — timeout, blocked, 404, DNS fail, SSL, redirect loop, rate limit, empty page
- **LLM errors** — invalid key, rate limit, quota exceeded, network error, overloaded
- **Config errors** — provider not configured, unknown provider, server not running

---

## Setup (Step by Step)

### Step 1 — Clone and enter project
```bash
cd smart-auth-scraper
```

### Step 2 — Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 3 — Install Playwright browser
```bash
playwright install chromium
```

### Step 4 — Add API keys
```bash
cp .env.example .env
```
Open `.env` and fill in the keys you have:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
```
You only need at least one. Unconfigured providers show as greyed out in the UI.

### Step 5 — Run tests
```bash
pytest tests/
```
All tests use mocks — no real API calls or internet needed.

### Step 6 — Start the server
```bash
uvicorn main:app --reload
```
Server runs at `http://localhost:8000`

### Step 7 — Open the UI
Open `frontend/index.html` directly in your browser.

---

## Next Steps

- [ ] Run `pip install -r requirements.txt` — install all packages
- [ ] Run `pytest tests/` — verify all tests pass
- [ ] Add `.env` with at least one real API key
- [ ] Do a live end-to-end test via browser
- [ ] Scrape the 5 required demo sites (GitHub, Reddit, Wikipedia, WordPress, Shopify) and document results
- [ ] Deploy backend to Render or Railway (free tier)
- [ ] Deploy frontend to Vercel or GitHub Pages
- [ ] Update README with live URLs after deployment
