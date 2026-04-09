# Project Setup & MVP Build

---

## Done

- [x] Read the assessment PDF — 4 requirements: scraper, dynamic URL input, HTML output, optional deploy
- [x] Planned architecture — FastAPI + BeautifulSoup + Playwright + Claude API + Vanilla JS
- [x] Created `backend/scraper.py` — fetches HTML via requests, falls back to Playwright if page is JS-rendered
- [x] Created `backend/detector.py` — finds login forms using BeautifulSoup (`<input type="password">` → parent `<form>`)
- [x] Created `backend/llm.py` — sends HTML snippet to Claude (haiku) and returns plain-English description
- [x] Created `backend/main.py` — FastAPI with `POST /scrape` and `GET /health`
- [x] Created `backend/requirements.txt` — all dependencies pinned
- [x] Created `.env.example` — template for `ANTHROPIC_API_KEY`
- [x] Created `frontend/index.html` + `app.js` + `style.css` — URL input, calls API, shows results
- [x] Created `backend/tests/test_scraper.py` — unit tests for fetch logic (mocked)
- [x] Created `backend/tests/test_detector.py` — unit tests for auth detection against sample HTML
- [x] Created `backend/tests/test_api.py` — integration tests for API routes (mocked scraper + LLM)

---

- [x] Created `README.md` — setup instructions, API docs, project structure
- [x] Added multi-provider AI support — OpenAI, Anthropic, Google Gemini all integrated
- [x] Added structured error system — every failure (scrape, LLM, config) has error_type, title, message, suggestion
- [x] Added contextual error popup in UI — themed by error category (danger/warning/info), shows what went wrong and what to do
- [x] Mapped all scraping errors: timeout, blocked, 404, DNS fail, SSL, rate limit, redirect loop, empty page
- [x] Mapped all LLM errors per provider: invalid key, rate limit, quota exceeded, network error, overloaded, not configured
- [x] Added `GET /providers` API route — returns all providers, config status, rate limits
- [x] Updated `POST /scrape` — accepts `provider` field, returns `provider_used` + `tokens_used`
- [x] Added provider switcher UI — 3 cards showing model, tier, RPM limit, configured/not status
- [x] Token usage displayed per call on provider card and in results
- [x] Updated tests — covers `/providers` route, invalid provider, unconfigured provider

---

## To Do Next

- [x] Dockerized backend — `Dockerfile` + `docker-compose.yml` using official Playwright Python image
- [x] Backend running in Docker on `http://localhost:8000` — health + all 3 providers confirmed live
- [x] Updated README — agentic pipeline explanation, full tech stack with why, API reference, error table, Docker + local setup
- [x] Replaced Anthropic (no credits) with Ollama Cloud — model: gemma4:e4b, uses OLLAMA_API_KEY
- [x] Updated Ollama model to gemma4:e4b (llama3.1:8b not available on Ollama Cloud)
- [x] Rebuilt Docker — all 3 providers confirmed live (OpenAI gpt-4o-mini, Ollama gemma4:e4b, Gemini gemini-2.5-flash)
- [ ] Install dependencies (`pip install -r requirements.txt`)
- [ ] Install Playwright browser (`playwright install chromium`)
- [ ] Add `.env` with all 3 API keys (OpenAI, Anthropic, Gemini)
- [ ] Run tests (`pytest tests/`)
- [ ] Live end-to-end test via browser
- [ ] Scrape the 5 required demo sites and document results
