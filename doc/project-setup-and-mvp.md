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
- [x] Replaced Anthropic (no credits) with Ollama Cloud — model: gemma3:4b, uses OLLAMA_API_KEY
- [x] Updated Ollama model to gemma3:4b (llama3.1:8b, gemma4:e4b not available on Ollama Cloud — confirmed by listing live account models)
- [x] Updated OpenAI model to gpt-4.1-mini (project doesn't have gpt-4o-mini access — confirmed by listing available models)
- [x] Rebuilt Docker — all 3 providers confirmed live (OpenAI gpt-4.1-mini, Ollama gemma3:4b, Gemini gemini-2.5-flash)
- [x] Fixed Playwright trigger — now uses `<form>/<input>` presence check, not just HTML length
- [x] Fixed Playwright wait — changed `networkidle` to `load` + `wait_for_selector` (SPAs never reach networkidle)
- [x] Fixed detector — broadened password field matching to name, aria-label, placeholder, id, autocomplete
- [x] Added field tooltips — hover on field tags to see what each means and how detected
- [x] Added HTML formatter — pretty-prints snippet with indentation
- [x] Added copy button — one-click copy of HTML snippet to clipboard
- [x] Added root-level Dockerfile for Render deployment
- [x] Updated README — full feature list, tech stack with why, API reference, deployment guide
- [x] Created doc/system-deep-dive.md — features, LLM flow, tech, infrastructure explained for study
- [x] Created doc/changes-tests-enhancements.md — all changes, test coverage, gaps, enhancement ideas

---

## To Do Next

- [ ] Run tests (`pytest tests/`) — verify nothing broke after detector + scraper changes
- [ ] Scrape 5 demo sites and document results (required by PDF)
- [ ] Deploy backend to Render
- [ ] Deploy frontend to Vercel
- [ ] Update API_BASE in app.js with Render URL
- [ ] Update README with live deployed URLs
