"""
main.py — FastAPI application.
Routes:
  GET  /health       — liveness check
  GET  /providers    — list all AI providers + config status + limits
  POST /scrape       — scrape a URL and detect auth components

All errors return a structured JSON body:
  { "error_type": str, "title": str, "message": str, "suggestion": str }
"""

from dotenv import load_dotenv
load_dotenv(dotenv_path=__import__("pathlib").Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

from scraper import fetch_html, ScraperError
from detector import detect_auth_component
from llm import analyze_auth_component, PROVIDERS, is_configured, get_default_provider, LLMError

app = FastAPI(title="Smart Auth Scraper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def error_response(status_code: int, error_type: str, title: str, message: str, suggestion: str = ""):
    """Return a consistent structured error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error_type": error_type,
            "title": title,
            "message": message,
            "suggestion": suggestion,
        },
    )


class ScrapeRequest(BaseModel):
    url: HttpUrl
    provider: str = "openai"


class TokenUsage(BaseModel):
    input: int
    output: int
    total: int


class ScrapeResponse(BaseModel):
    url: str
    auth_found: bool
    html_snippet: str | None
    fields_detected: list[str]
    llm_analysis: str
    scrape_method: str
    provider_used: str
    tokens_used: TokenUsage


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/providers")
def providers():
    result = []
    for pid, meta in PROVIDERS.items():
        result.append({**meta, "configured": is_configured(pid)})
    return {"providers": result, "default": get_default_provider()}


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(request: ScrapeRequest):
    url = str(request.url)
    provider = request.provider

    # Validate provider
    if provider not in PROVIDERS:
        return error_response(
            400,
            error_type="INVALID_PROVIDER",
            title="Unknown AI Provider",
            message=f"'{provider}' is not a supported provider.",
            suggestion=f"Choose one of: {', '.join(PROVIDERS.keys())}",
        )

    if not is_configured(provider):
        p_name = PROVIDERS[provider]["name"]
        env_key = f"{provider.upper()}_API_KEY"
        return error_response(
            400,
            error_type="PROVIDER_NOT_CONFIGURED",
            title=f"{p_name} Not Configured",
            message=f"No API key found for {p_name}.",
            suggestion=f"Add {env_key}=your_key to your .env file, then restart the server.",
        )

    # Fetch HTML
    try:
        html, method = fetch_html(url)
    except ScraperError as e:
        return error_response(502, e.error_type, e.title, e.message, e.suggestion)

    # Detect auth component
    detection = detect_auth_component(html)

    # LLM analysis
    try:
        llm_result = analyze_auth_component(detection.get("html_snippet"), url, provider)
    except LLMError as e:
        return error_response(502, e.error_type, e.title, e.message, e.suggestion)

    return ScrapeResponse(
        url=url,
        auth_found=detection["auth_found"],
        html_snippet=detection["html_snippet"],
        fields_detected=detection["fields_detected"],
        llm_analysis=llm_result["analysis"],
        scrape_method=method,
        provider_used=provider,
        tokens_used=TokenUsage(**llm_result["tokens_used"]),
    )
