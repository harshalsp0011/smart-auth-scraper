"""
main.py — FastAPI application.
Routes:
  GET  /health       — liveness check
    POST /auth/login   — exchange access ID/password for an access token
    GET  /auth/me      — verify the current access token
  GET  /providers    — list all AI providers + config status + limits
  POST /scrape       — scrape a URL and detect auth components

All errors return a structured JSON body:
  { "error_type": str, "title": str, "message": str, "suggestion": str }
"""

from dotenv import load_dotenv
load_dotenv(dotenv_path=__import__("pathlib").Path(__file__).parent.parent / ".env")

import os
import secrets
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Request
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

AUTH_LOGIN_ID = os.getenv("FRONTEND_LOGIN_ID", "")
AUTH_LOGIN_PASSWORD = os.getenv("FRONTEND_LOGIN_PASSWORD", "")
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("FRONTEND_AUTH_TOKEN_TTL_SECONDS", "604800"))
AUTH_SESSIONS: dict[str, dict] = {}


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


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error_type" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_type": "HTTP_ERROR",
            "title": "Request Failed",
            "message": str(exc.detail),
            "suggestion": "Try again or check the request payload.",
        },
    )


def _issue_auth_token(login_id: str) -> str:
    token = secrets.token_urlsafe(32)
    AUTH_SESSIONS[token] = {
        "sub": login_id,
        "exp": int(time.time()) + AUTH_TOKEN_TTL_SECONDS,
    }
    return token


def _verify_auth_token(token: str) -> dict | None:
    payload = AUTH_SESSIONS.get(token)
    if not payload:
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        AUTH_SESSIONS.pop(token, None)
        return None

    return payload


def _require_auth(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={
            "error_type": "AUTH_REQUIRED",
            "title": "Login Required",
            "message": "Please sign in to access this dashboard.",
            "suggestion": "Use the login form on the frontend to authenticate.",
        })

    token = authorization.removeprefix("Bearer ").strip()
    payload = _verify_auth_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail={
            "error_type": "AUTH_INVALID",
            "title": "Session Expired",
            "message": "Your login session is invalid or expired.",
            "suggestion": "Sign in again to continue.",
        })
    return payload


class ScrapeRequest(BaseModel):
    url: HttpUrl
    provider: str = "openai"


class LoginRequest(BaseModel):
    login_id: str
    password: str


class LoginResponse(BaseModel):
    authenticated: bool
    token: str
    expires_in: int


class TokenUsage(BaseModel):
    input: int
    output: int
    total: int


class ScrapeResponse(BaseModel):
    url: str
    auth_found: bool
    auth_confidence: int
    html_snippet: str | None
    screenshot_base64: str | None
    fields_detected: list[str]
    llm_analysis: str
    scrape_method: str
    provider_used: str
    tokens_used: TokenUsage


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def auth_login(request: LoginRequest):
    if not AUTH_LOGIN_ID or not AUTH_LOGIN_PASSWORD:
        return error_response(
            500,
            error_type="AUTH_NOT_CONFIGURED",
            title="Authentication Not Configured",
            message="Frontend login credentials are not configured on the server.",
            suggestion="Set FRONTEND_LOGIN_ID and FRONTEND_LOGIN_PASSWORD in the backend environment.",
        )

    if request.login_id != AUTH_LOGIN_ID or request.password != AUTH_LOGIN_PASSWORD:
        return error_response(
            401,
            error_type="AUTH_INVALID",
            title="Invalid Credentials",
            message="The access ID or password is incorrect.",
            suggestion="Check the credentials and try again.",
        )

    token = _issue_auth_token(request.login_id)
    return LoginResponse(authenticated=True, token=token, expires_in=AUTH_TOKEN_TTL_SECONDS)


@app.get("/auth/me")
def auth_me(user: dict = Depends(_require_auth)):
    return {"authenticated": True, "login_id": user.get("sub")}


@app.get("/providers")
def providers(user: dict = Depends(_require_auth)):
    result = []
    for pid, meta in PROVIDERS.items():
        result.append({**meta, "configured": is_configured(pid)})
    return {"providers": result, "default": get_default_provider()}


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(request: ScrapeRequest, user: dict = Depends(_require_auth)):
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
        html, method, screenshot_base64 = fetch_html(url)
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
        auth_confidence=detection["auth_confidence"],
        html_snippet=detection["html_snippet"],
        screenshot_base64=screenshot_base64,
        fields_detected=detection["fields_detected"],
        llm_analysis=llm_result["analysis"],
        scrape_method=method,
        provider_used=provider,
        tokens_used=TokenUsage(**llm_result["tokens_used"]),
    )
