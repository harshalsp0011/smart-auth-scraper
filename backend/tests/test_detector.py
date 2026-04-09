"""
test_detector.py — Unit tests for detector.py
Tests auth detection logic against various HTML strings.
No network calls.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from detector import detect_auth_component, _extract_field_types
from bs4 import BeautifulSoup

# --- Sample HTML fixtures ---

LOGIN_FORM_HTML = """
<html><body>
  <form action="/login" method="post">
    <input type="text" name="username" placeholder="Username" />
    <input type="password" name="password" placeholder="Password" />
    <button type="submit">Login</button>
  </form>
</body></html>
"""

EMAIL_LOGIN_HTML = """
<html><body>
  <form>
    <input type="email" name="email" />
    <input type="password" name="password" />
    <input type="submit" value="Sign In" />
  </form>
</body></html>
"""

NO_AUTH_HTML = """
<html><body>
  <h1>Welcome</h1>
  <p>This is a public page with no login form.</p>
</body></html>
"""

EMPTY_HTML = ""

PASSWORD_NO_FORM_HTML = """
<html><body>
  <div class="auth-container">
    <input type="text" name="user" />
    <input type="password" name="pass" />
  </div>
</body></html>
"""


class TestDetectAuthComponent:
    def test_detects_standard_login_form(self):
        result = detect_auth_component(LOGIN_FORM_HTML)
        assert result["auth_found"] is True
        assert result["html_snippet"] is not None
        assert "password" in result["fields_detected"]

    def test_detects_email_login_form(self):
        result = detect_auth_component(EMAIL_LOGIN_HTML)
        assert result["auth_found"] is True
        assert "password" in result["fields_detected"]
        assert "email" in result["fields_detected"]

    def test_returns_false_when_no_auth(self):
        result = detect_auth_component(NO_AUTH_HTML)
        assert result["auth_found"] is False
        assert result["html_snippet"] is None
        assert result["fields_detected"] == []

    def test_handles_empty_html(self):
        result = detect_auth_component(EMPTY_HTML)
        assert result["auth_found"] is False

    def test_detects_password_outside_form(self):
        result = detect_auth_component(PASSWORD_NO_FORM_HTML)
        assert result["auth_found"] is True
        assert "password" in result["fields_detected"]

    def test_snippet_contains_password_input(self):
        result = detect_auth_component(LOGIN_FORM_HTML)
        assert 'type="password"' in result["html_snippet"] or "type='password'" in result["html_snippet"]


class TestExtractFieldTypes:
    def test_extracts_username_and_password(self):
        soup = BeautifulSoup(LOGIN_FORM_HTML, "html.parser")
        form = soup.find("form")
        fields = _extract_field_types(form)
        assert "password" in fields

    def test_no_duplicates(self):
        soup = BeautifulSoup(LOGIN_FORM_HTML, "html.parser")
        form = soup.find("form")
        fields = _extract_field_types(form)
        assert len(fields) == len(set(fields))
