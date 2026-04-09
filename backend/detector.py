"""
detector.py — Detect authentication components in raw HTML.
Uses BeautifulSoup to find likely login forms and assigns a confidence score (0-100).
Returns the HTML snippet, detected field types, and confidence.
"""

import re
from bs4 import BeautifulSoup


def detect_auth_component(html: str) -> dict:
    """
    Parse HTML and look for authentication-related elements.

    Returns:
        {
            "auth_found": bool,
            "html_snippet": str | None,
            "fields_detected": list[str],
            "auth_confidence": int,
        }
    """
    if not html:
        return {
            "auth_found": False,
            "html_snippet": None,
            "fields_detected": [],
            "auth_confidence": 0,
        }

    soup = BeautifulSoup(html, "html.parser")

    # Find password fields by type, or by name/aria-label/placeholder containing "password"
    password_inputs = soup.find_all("input", {"type": "password"})
    if not password_inputs:
        password_inputs = [
            inp for inp in soup.find_all("input")
            if any(
                "password" in (inp.get(attr, "") or "").lower()
                for attr in ("name", "aria-label", "placeholder", "id", "autocomplete")
            )
        ]

    if not password_inputs:
        return {
            "auth_found": False,
            "html_snippet": None,
            "fields_detected": [],
            "auth_confidence": 0,
        }

    # Walk up to the nearest <form> ancestor
    form = None
    for pwd_input in password_inputs:
        parent = pwd_input.find_parent("form")
        if parent:
            form = parent
            break

    # If no wrapping form found, grab a container div around the password input
    if not form:
        form = password_inputs[0].find_parent(["div", "section", "main"]) or password_inputs[0]

    snippet = str(form)
    fields = _extract_field_types(form)
    confidence = _compute_auth_confidence(form, fields)

    return {
        "auth_found": True,
        "html_snippet": snippet,
        "fields_detected": fields,
        "auth_confidence": confidence,
    }


def _compute_auth_confidence(element, fields: list[str]) -> int:
    """Compute a 0-100 confidence score that the element is a login/auth form."""
    score = 0
    text = _element_text_for_scoring(element)

    # Strong signal: password field exists in detected fields.
    if "password" in fields:
        score += 45

    # Typical login identifier signals.
    if "username" in fields or "email" in fields:
        score += 20
    elif "text" in fields:
        score += 10

    # Action signal.
    if "submit" in fields:
        score += 10

    # Semantic keywords around the form.
    if re.search(r"\b(login|log in|sign in|signin|authenticate|auth|account)\b", text):
        score += 12

    if re.search(r"\b(password|passcode|email|username|user id)\b", text):
        score += 8

    if re.search(r"\b(remember me|forgot password|keep me signed in|2fa|mfa|otp)\b", text):
        score += 5

    return max(0, min(100, score))


def _element_text_for_scoring(element) -> str:
    """Extract compact lowercase text from relevant attributes and visible labels."""
    chunks = []

    action = element.get("action", "")
    if action:
        chunks.append(action)

    for node in element.find_all(["input", "button", "label", "a"]):
        for attr in ("name", "id", "placeholder", "aria-label", "autocomplete", "type", "value"):
            value = node.get(attr)
            if value:
                chunks.append(str(value))
        visible = node.get_text(" ", strip=True)
        if visible:
            chunks.append(visible)

    return " ".join(chunks).lower()


def _extract_field_types(element) -> list[str]:
    """Return a list of detected input field types/names from the form."""
    fields = []
    for inp in element.find_all("input"):
        input_type = inp.get("type", "text").lower()
        input_name = inp.get("name", "").lower()
        input_placeholder = inp.get("placeholder", "").lower()

        is_password_field = (
            input_type == "password"
            or any(
                "password" in (inp.get(attr, "") or "").lower()
                for attr in ("name", "aria-label", "placeholder", "id", "autocomplete")
            )
        )
        if is_password_field:
            fields.append("password")
        elif input_type in ("submit", "button"):
            fields.append("submit")
        elif input_type == "email" or "email" in input_name or "email" in input_placeholder:
            fields.append("email")
        elif "user" in input_name or "login" in input_name or "username" in input_placeholder:
            fields.append("username")
        elif input_type == "text":
            fields.append("text")
        elif input_type == "hidden":
            pass  # skip hidden fields
        else:
            fields.append(input_type)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for f in fields:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique
