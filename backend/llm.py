"""
llm.py — Analyze auth HTML snippets using OpenAI, Ollama Cloud, or Google Gemini.
Raises LLMError with specific context on every known failure mode.
"""

import os

PROVIDERS = {
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "model": "gpt-4.1-mini",
        "rpm": 500,
        "daily_tokens": "unlimited (paid)",
        "tier": "paid",
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama Cloud",
        "model": "gemma3:4b",
        "rpm": 60,
        "daily_tokens": "unlimited (cloud)",
        "tier": "paid",
    },
    "gemini": {
        "id": "gemini",
        "name": "Google Gemini",
        "model": "gemini-2.5-flash",
        "rpm": 5,
        "daily_tokens": "250K TPM / 20 RPD",
        "tier": "free",
    },
}

ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "ollama": "OLLAMA_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class LLMError(Exception):
    """Structured LLM error with type, title, message, and suggestion."""
    def __init__(self, error_type: str, title: str, message: str, suggestion: str = ""):
        self.error_type = error_type
        self.title = title
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)


def is_configured(provider_id: str) -> bool:
    return bool(os.environ.get(ENV_KEYS.get(provider_id, ""), "").strip())


def get_default_provider() -> str | None:
    for pid in ["openai", "anthropic", "gemini"]:
        if is_configured(pid):
            return pid
    return None


def _build_prompt(html_snippet: str, url: str) -> str:
    return f"""You are analyzing the HTML of a login/authentication form scraped from a website.

URL: {url}

HTML snippet:
```html
{html_snippet[:6000]}
```

Describe this authentication form clearly and completely. Cover all of the following that are present:
1. What type of form this is (login, signup, password reset, MFA, etc.)
2. What input fields are present (username, email, phone, password, etc.)
3. Any alternative login methods (QR code, passkey, SSO, OAuth buttons like Google/GitHub, magic link, etc.)
4. Any security features (CAPTCHA, remember me checkbox, CSRF token, WebAuthn, rate limiting hints, etc.)
5. Any notable UX details (multi-step flow, required fields marked, forgot password link, register link, etc.)

Be factual and specific. If something is present in the HTML, mention it. Keep the response to 4-5 sentences."""


def _provider_label(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("name", provider)


def _analyze_openai(prompt: str) -> dict:
    try:
        from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError, APIStatusError
    except ImportError:
        raise LLMError(
            error_type="LLM_PACKAGE_MISSING",
            title="OpenAI Package Not Installed",
            message="The 'openai' Python package is not installed.",
            suggestion="Run: pip install openai",
        )

    try:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = response.usage
        return {
            "analysis": response.choices[0].message.content.strip(),
            "tokens_used": {
                "input": usage.prompt_tokens,
                "output": usage.completion_tokens,
                "total": usage.total_tokens,
            },
        }
    except AuthenticationError:
        raise LLMError(
            error_type="LLM_INVALID_KEY",
            title="Invalid OpenAI API Key",
            message="OpenAI rejected the API key. It may be incorrect or revoked.",
            suggestion="Check your OPENAI_API_KEY in .env — get a valid key at platform.openai.com.",
        )
    except RateLimitError:
        raise LLMError(
            error_type="LLM_RATE_LIMIT",
            title="OpenAI Rate Limit Reached",
            message="You've hit OpenAI's rate limit (too many requests in a short time).",
            suggestion="Wait 60 seconds and try again, or switch to Anthropic or Gemini.",
        )
    except APIConnectionError:
        raise LLMError(
            error_type="LLM_NETWORK_ERROR",
            title="Cannot Reach OpenAI",
            message="Failed to connect to OpenAI's API. Check your internet connection.",
            suggestion="Verify your network connection, then retry.",
        )
    except APIStatusError as e:
        if e.status_code == 429:
            raise LLMError(
                error_type="LLM_QUOTA_EXCEEDED",
                title="OpenAI Quota Exceeded",
                message="Your OpenAI account has reached its usage limit or billing quota.",
                suggestion="Add credits at platform.openai.com/account/billing, or switch to a free provider.",
            )
        raise LLMError(
            error_type="LLM_API_ERROR",
            title=f"OpenAI API Error ({e.status_code})",
            message=f"OpenAI returned an error: {e.message}",
            suggestion="Check OpenAI status at status.openai.com.",
        )
    except Exception as e:
        raise LLMError(
            error_type="LLM_FAILED",
            title="OpenAI Request Failed",
            message=f"Unexpected error from OpenAI: {str(e)}",
            suggestion="Try again or switch to a different provider.",
        )


def _analyze_ollama(prompt: str) -> dict:
    try:
        from ollama import Client
    except ImportError:
        raise LLMError(
            error_type="LLM_PACKAGE_MISSING",
            title="Ollama Package Not Installed",
            message="The 'ollama' Python package is not installed.",
            suggestion="Run: pip install ollama",
        )

    try:
        client = Client(
            host="https://ollama.com",
            headers={"Authorization": "Bearer " + os.environ["OLLAMA_API_KEY"]},
        )
        response = client.chat(
            model="gemma3:4b",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response["message"]["content"].strip()
        input_tokens  = response.get("prompt_eval_count", 0)
        output_tokens = response.get("eval_count", 0)
        return {
            "analysis": content,
            "tokens_used": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
        }
    except Exception as e:
        err_str = str(e).lower()
        if "401" in err_str or "unauthorized" in err_str or "authentication" in err_str:
            raise LLMError(
                error_type="LLM_INVALID_KEY",
                title="Invalid Ollama API Key",
                message="Ollama Cloud rejected the API key.",
                suggestion="Check your OLLAMA_API_KEY in .env — get a key at ollama.com/settings/keys.",
            )
        if "429" in err_str or "rate" in err_str:
            raise LLMError(
                error_type="LLM_RATE_LIMIT",
                title="Ollama Rate Limit Reached",
                message="Too many requests to Ollama Cloud.",
                suggestion="Wait a moment and retry.",
            )
        if "404" in err_str or "not found" in err_str:
            raise LLMError(
                error_type="LLM_MODEL_NOT_FOUND",
                title="Ollama Model Not Found",
                message=f"Model 'gemma3:4b' not found on Ollama Cloud: {str(e)}",
                suggestion="Check available models at ollama.com/search?c=cloud.",
            )
        if "connect" in err_str or "network" in err_str or "timeout" in err_str:
            raise LLMError(
                error_type="LLM_NETWORK_ERROR",
                title="Cannot Reach Ollama Cloud",
                message="Failed to connect to ollama.com. Check your internet connection.",
                suggestion="Verify your network, then retry.",
            )
        raise LLMError(
            error_type="LLM_FAILED",
            title="Ollama Request Failed",
            message=f"{type(e).__name__}: {str(e)}",
            suggestion="Check your OLLAMA_API_KEY and try again.",
        )


def _analyze_gemini(prompt: str) -> dict:
    try:
        import google.generativeai as genai
        from google.api_core.exceptions import (
            PermissionDenied, ResourceExhausted, InvalidArgument,
            ServiceUnavailable, DeadlineExceeded, Unauthenticated, NotFound
        )
    except ImportError:
        raise LLMError(
            error_type="LLM_PACKAGE_MISSING",
            title="Gemini Package Not Installed",
            message="The 'google-generativeai' Python package is not installed.",
            suggestion="Run: pip install google-generativeai",
        )

    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
        return {
            "analysis": response.text.strip(),
            "tokens_used": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
        }

    except (PermissionDenied, Unauthenticated):
        raise LLMError(
            error_type="LLM_INVALID_KEY",
            title="Invalid Gemini API Key",
            message="Google Gemini rejected the API key. It may be incorrect, expired, or the Generative Language API is not enabled.",
            suggestion="Check your GEMINI_API_KEY in .env and ensure the API is enabled at aistudio.google.com.",
        )
    except ResourceExhausted:
        raise LLMError(
            error_type="LLM_RATE_LIMIT",
            title="Gemini Rate Limit Reached",
            message="You've hit Gemini's free tier rate limit (15 requests/minute or 1M tokens/day).",
            suggestion="Wait 60 seconds and retry, or switch to OpenAI or Anthropic.",
        )
    except NotFound as e:
        raise LLMError(
            error_type="LLM_MODEL_NOT_FOUND",
            title="Gemini Model Not Found",
            message=f"The Gemini model is not available: {str(e)}",
            suggestion="The model may have been deprecated. Check aistudio.google.com for available models.",
        )
    except InvalidArgument as e:
        raise LLMError(
            error_type="LLM_INVALID_REQUEST",
            title="Invalid Gemini Request",
            message=f"Gemini rejected the request: {str(e)}",
            suggestion="The prompt or model name may be invalid. Check your GEMINI_API_KEY and try again.",
        )
    except (ServiceUnavailable, DeadlineExceeded):
        raise LLMError(
            error_type="LLM_OVERLOADED",
            title="Gemini Service Unavailable",
            message="Google Gemini is temporarily unavailable or timed out.",
            suggestion="Wait a moment and try again, or switch to OpenAI or Anthropic.",
        )
    except Exception as e:
        # Show the real error — never silently misclassify
        raise LLMError(
            error_type="LLM_FAILED",
            title="Gemini Request Failed",
            message=f"{type(e).__name__}: {str(e)}",
            suggestion="Check your GEMINI_API_KEY is valid and the Generative Language API is enabled at console.cloud.google.com.",
        )


_HANDLERS = {
    "openai": _analyze_openai,
    "ollama": _analyze_ollama,
    "gemini": _analyze_gemini,
}


def analyze_auth_component(html_snippet: str | None, url: str, provider: str = "openai") -> dict:
    """
    Analyze an auth HTML snippet using the specified provider.
    Raises LLMError for all known failure modes.
    Returns {"analysis": str, "tokens_used": {"input": int, "output": int, "total": int}}
    """
    if not html_snippet:
        return {
            "analysis": "No authentication component was found on this page.",
            "tokens_used": {"input": 0, "output": 0, "total": 0},
        }

    if provider not in PROVIDERS:
        raise LLMError(
            error_type="LLM_INVALID_PROVIDER",
            title="Unknown AI Provider",
            message=f"'{provider}' is not a supported provider.",
            suggestion=f"Choose one of: {', '.join(PROVIDERS.keys())}",
        )

    if not is_configured(provider):
        raise LLMError(
            error_type="LLM_NOT_CONFIGURED",
            title=f"{_provider_label(provider)} Not Configured",
            message=f"No API key found for {_provider_label(provider)}. Set {ENV_KEYS[provider]} in your .env file.",
            suggestion=f"Add {ENV_KEYS[provider]}=your_key to .env, then restart the server.",
        )

    prompt = _build_prompt(html_snippet, url)
    return _HANDLERS[provider](prompt)
