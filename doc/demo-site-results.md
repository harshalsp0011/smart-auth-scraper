# Demo Site Scrape Results

All 5 sites scraped live. Results documented below.

---

## 1. GitHub Login — https://github.com/login

| Field | Value |
|---|---|
| Auth Found | Yes |
| Scrape Method | requests |
| Fields Detected | username, password, text, submit |
| Provider Used | Gemini (gemini-2.5-flash) |
| Tokens Used | ~260 |

**AI Analysis:**
> This is a login form designed to authenticate users. It contains visible input fields for a username or email address and a password. Notable features include a "Forgot password?" link, a CSRF token, and multiple hidden fields indicating support for WebAuthn and potential Single Sign-On (SSO) integration.

**Notes:** Static server-rendered page. requests fetched it directly — no Playwright needed. Clean standard form.

---

## 2. web-scraping.dev Login — https://web-scraping.dev/login

| Field | Value |
|---|---|
| Auth Found | Yes |
| Scrape Method | requests |
| Fields Detected | username, password |
| Provider Used | Gemini (gemini-2.5-flash) |
| Tokens Used | ~260 |

**AI Analysis:**
> This is a login authentication form, indicated by the action="/api/login" and the standard input fields. It includes fields for username and password. No other notable features like "remember me" checkboxes, SSO buttons, or CAPTCHA are present in this HTML snippet.

**Notes:** Demo site uses `type="text"` for both fields — including password. Our broadened detector correctly identified the password field via `name="password"` attribute. This was a real bug we fixed.

---

## 3. Discord Login — https://discord.com/login

| Field | Value |
|---|---|
| Auth Found | Yes |
| Scrape Method | playwright |
| Fields Detected | email, password |
| Provider Used | Gemini (gemini-2.5-flash) |
| Tokens Used | ~1,200 |

**AI Analysis:**
> This is a standard login form for Discord. It includes an "Email or Phone Number" field and a "Password" field. Notable features include a "Forgot your password?" button, a "Log In" submit button, a QR code login option, and a passkey sign-in option.

**Notes:** React SPA — static HTML has no form elements. Our updated Playwright trigger correctly detected this and launched headless Chromium. Used `wait_until="load"` + `wait_for_selector("input, form")` to wait for React to render the form. Higher token count due to complex, class-heavy HTML.

---

## 4. Google Accounts — https://accounts.google.com

| Field | Value |
|---|---|
| Auth Found | Yes |
| Scrape Method | requests |
| Fields Detected | email, password, text |
| Provider Used | OpenAI (gpt-4.1-mini) |
| Tokens Used | 1,480 |

**AI Analysis:**
> This is a login form for Google accounts, specifically the username/email entry step. It contains an input field for "Email or phone" but no password field visible here (likely a multi-step form). Notable features include a CAPTCHA image with an audio playback button and a "Forgot email?" button.

**Notes:** Google uses a multi-step form — email on step 1, password on step 2. Our scraper correctly detected the form on step 1. CAPTCHA detected and mentioned. Gemini rate limit hit on first attempt (5 RPM free tier) — switched to OpenAI. Largest token count due to Google's complex form HTML.

---

## 5. LinkedIn Login — https://www.linkedin.com/login

| Field | Value |
|---|---|
| Auth Found | Yes |
| Scrape Method | requests |
| Fields Detected | email, username, password, checkbox |
| Provider Used | OpenAI (gpt-4.1-mini) |
| Tokens Used | 1,002 |

**AI Analysis:**
> This is a login authentication form for LinkedIn. It includes an input field for the username identified as "Email or phone" and a password field. Notable features include multiple hidden inputs likely for CSRF protection and tracking, as well as a "Remember me" checkbox.

**Notes:** Static server-rendered page. requests worked directly. Checkbox field correctly detected — LinkedIn has a "Remember me" checkbox. Multiple hidden CSRF fields present, correctly skipped by detector.

---

## Summary

| Site | Auth Found | Method | Fields | Outcome |
|---|---|---|---|---|
| github.com/login | Yes | requests | username, password, submit | Full success |
| web-scraping.dev/login | Yes | requests | username, password | Full success — detector fix required |
| discord.com/login | Yes | playwright | email, password | Full success — Playwright trigger fix required |
| accounts.google.com | Yes | requests | email, password, text | Partial — multi-step form, step 1 only |
| linkedin.com/login | Yes | requests | email, username, password, checkbox | Full success |

**5/5 sites returned auth_found: true**

---

## Observations

- **requests is sufficient for most sites** — 4 out of 5 used it
- **Playwright only needed for true SPAs** — Discord is a React app with no server-rendered form
- **Multi-step forms** (Google) are a known limitation — we detect step 1 but cannot click through to step 2
- **Gemini rate limit** (5 RPM) hit on back-to-back requests — rotate providers or add delay between calls
- **Token count varies widely** — 260 tokens (simple form) to 1,480 tokens (Google's complex HTML)
