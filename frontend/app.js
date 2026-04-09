//const API_BASE = "http://localhost:8000";
const API_BASE = "https://smart-auth-scraper.onrender.com";
const AUTH_TOKEN_STORAGE_KEY = "smart-auth-scraper-auth-token";

let selectedProvider = null;
let providersData = [];
let appInitialized = false;

const form = document.getElementById("scrapeForm");
const urlInput = document.getElementById("urlInput");
const submitBtn = document.getElementById("submitBtn");
const loginSubmitBtn = document.getElementById("loginSubmitBtn");
const loader = document.getElementById("loader");
const results = document.getElementById("results");
const loginOverlay = document.getElementById("loginOverlay");
const loginForm = document.getElementById("loginForm");
const loginIdInput = document.getElementById("loginId");
const loginPasswordInput = document.getElementById("loginPassword");
const loginError = document.getElementById("loginError");
const infoBtn = document.getElementById("infoBtn");
const logoutBtn = document.getElementById("logoutBtn");
const infoOverlay = document.getElementById("infoOverlay");
const infoCloseBtn = document.getElementById("infoCloseBtn");
const coldStartToast = document.getElementById("coldStartToast");

const COLD_START_TOAST_DELAY_MS = 1200;
let backendIsWarm = false;
let pendingWakeRequests = 0;

// ── Error popup ───────────────────────────────────────────────────────────────

// Map error_type → icon + color theme
const ERROR_META = {
  // Scraping
  SCRAPE_TIMEOUT:       { icon: "⏱", theme: "warning" },
  SCRAPE_BLOCKED:       { icon: "🚫", theme: "danger"  },
  SCRAPE_NOT_FOUND:     { icon: "🔍", theme: "warning" },
  SCRAPE_DNS_ERROR:     { icon: "🌐", theme: "danger"  },
  SCRAPE_SSL_ERROR:     { icon: "🔒", theme: "danger"  },
  SCRAPE_REDIRECT_LOOP: { icon: "🔁", theme: "warning" },
  SCRAPE_RATE_LIMITED:  { icon: "⏳", theme: "warning" },
  SCRAPE_SERVER_ERROR:  { icon: "💥", theme: "danger"  },
  SCRAPE_HTTP_ERROR:    { icon: "⚠️", theme: "warning" },
  SCRAPE_EMPTY:         { icon: "📄", theme: "warning" },
  SCRAPE_FAILED:        { icon: "❌", theme: "danger"  },
  // LLM
  LLM_INVALID_KEY:      { icon: "🔑", theme: "danger"  },
  LLM_RATE_LIMIT:       { icon: "⏳", theme: "warning" },
  LLM_QUOTA_EXCEEDED:       { icon: "💳", theme: "danger"  },
  LLM_INSUFFICIENT_CREDITS: { icon: "💳", theme: "danger"  },
  LLM_NETWORK_ERROR:    { icon: "🌐", theme: "danger"  },
  LLM_OVERLOADED:       { icon: "🔥", theme: "warning" },
  LLM_NOT_CONFIGURED:   { icon: "⚙️", theme: "info"   },
  LLM_INVALID_PROVIDER: { icon: "❓", theme: "info"   },
  LLM_PACKAGE_MISSING:  { icon: "📦", theme: "info"   },
  LLM_API_ERROR:        { icon: "⚠️", theme: "danger"  },
  LLM_FAILED:           { icon: "❌", theme: "danger"  },
  // Provider config
  INVALID_PROVIDER:        { icon: "❓", theme: "info"  },
  PROVIDER_NOT_CONFIGURED: { icon: "⚙️", theme: "info" },
  INVALID_URL:             { icon: "🔗", theme: "warning" },
  SEARCH_WRAPPED_URL:      { icon: "🧭", theme: "info" },
  // Network / unknown
  NETWORK_ERROR:        { icon: "🌐", theme: "danger"  },
  UNKNOWN:              { icon: "⚠️", theme: "warning" },
};

function showErrorPopup({ error_type, title, message, suggestion }) {
  const meta = ERROR_META[error_type] || ERROR_META.UNKNOWN;

  document.getElementById("errorIcon").textContent = meta.icon;
  document.getElementById("errorTitle").textContent = title || "Something went wrong";
  document.getElementById("errorMessage").textContent = message || "An unexpected error occurred.";
  document.getElementById("errorTypeBadge").textContent = error_type || "UNKNOWN";

  const suggestionBox = document.getElementById("errorSuggestion");
  const suggestionText = document.getElementById("errorSuggestionText");
  if (suggestion) {
    suggestionText.textContent = suggestion;
    suggestionBox.classList.remove("hidden");
  } else {
    suggestionBox.classList.add("hidden");
  }

  const overlay = document.getElementById("errorOverlay");
  const modal = overlay.querySelector(".error-modal");
  overlay.className = `error-overlay theme-${meta.theme}`;
  overlay.classList.remove("hidden");
  document.getElementById("errorCloseBtn").focus();
}

function hideErrorPopup() {
  document.getElementById("errorOverlay").classList.add("hidden");
}

document.getElementById("errorCloseBtn").addEventListener("click", hideErrorPopup);
document.getElementById("errorOverlay").addEventListener("click", (e) => {
  if (e.target === document.getElementById("errorOverlay")) hideErrorPopup();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    hideErrorPopup();
    hideInfoPopup();
  }
});

function showInfoPopup() {
  infoOverlay.classList.remove("hidden");
  infoCloseBtn.focus();
}

function hideInfoPopup() {
  infoOverlay.classList.add("hidden");
}

infoBtn.addEventListener("click", showInfoPopup);
infoCloseBtn.addEventListener("click", hideInfoPopup);
infoOverlay.addEventListener("click", (e) => {
  if (e.target === infoOverlay) hideInfoPopup();
});

function isAuthenticated() {
  return Boolean(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY));
}

function setAuthenticated(value) {
  if (!value) localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  syncAuthUi();
}

function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "";
}

function setAuthToken(token) {
  if (token) localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  else localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  syncAuthUi();
}

function syncAuthUi() {
  const hasSession = isAuthenticated();
  logoutBtn.classList.toggle("hidden", !hasSession);
}

function setLoginError(message) {
  loginError.textContent = message;
  loginError.classList.remove("hidden");
}

function clearLoginError() {
  loginError.textContent = "";
  loginError.classList.add("hidden");
}

function showColdStartToast() {
  coldStartToast.classList.remove("hidden");
  coldStartToast.classList.add("visible");
}

function hideColdStartToast() {
  if (coldStartToast.classList.contains("hidden")) return;
  coldStartToast.classList.remove("visible");
  setTimeout(() => {
    if (!coldStartToast.classList.contains("visible")) {
      coldStartToast.classList.add("hidden");
    }
  }, 220);
}

function startColdStartNoticeTimer() {
  if (backendIsWarm) {
    return () => {};
  }

  pendingWakeRequests += 1;
  const timer = setTimeout(() => {
    if (!backendIsWarm && pendingWakeRequests > 0) {
      showColdStartToast();
    }
  }, COLD_START_TOAST_DELAY_MS);

  return () => {
    clearTimeout(timer);
    pendingWakeRequests = Math.max(0, pendingWakeRequests - 1);
    if (pendingWakeRequests === 0) {
      hideColdStartToast();
    }
  };
}

function unlockApp() {
  loginOverlay.classList.add("hidden");
  clearLoginError();
  syncAuthUi();
  if (!appInitialized) {
    appInitialized = true;
    initApp();
  }
}

function initLoginGate() {
  syncAuthUi();

  if (isAuthenticated()) {
    verifyExistingSession();
    return;
  }

  loginOverlay.classList.remove("hidden");
  loginPasswordInput.value = "";
  loginIdInput.focus();

  loginForm.addEventListener("submit", (e) => {
    e.preventDefault();

    const enteredId = loginIdInput.value.trim();
    const enteredPassword = loginPasswordInput.value;

    authenticateWithBackend(enteredId, enteredPassword);
  });
}

async function apiFetch(path, options = {}) {
  const finishNotice = startColdStartNoticeTimer();
  const headers = {
    ...(options.headers || {}),
  };
  const token = getAuthToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });
    backendIsWarm = true;
    return response;
  } finally {
    finishNotice();
  }
}

async function authenticateWithBackend(loginId, password) {
  clearLoginError();
  loginSubmitBtn.disabled = true;

  try {
    const res = await apiFetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login_id: loginId, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      setAuthenticated(false);
      setLoginError(data.message || data.detail?.message || data.suggestion || "Login failed.");
      loginPasswordInput.value = "";
      loginPasswordInput.focus();
      return;
    }

    setAuthToken(data.token);
    unlockApp();
  } catch {
    setLoginError("Could not reach the backend login endpoint.");
  } finally {
    loginSubmitBtn.disabled = false;
  }
}

async function verifyExistingSession() {
  try {
    const res = await apiFetch("/auth/me");
    if (!res.ok) throw new Error("Invalid session");
    unlockApp();
  } catch {
    setAuthToken("");
    loginOverlay.classList.remove("hidden");
  }
}

async function initApp() {
  try {
    const res = await apiFetch("/providers");
    if (!res.ok) throw new Error("Server error");
    const data = await res.json();
    providersData = data.providers;
    selectedProvider = data.default;
    renderProviderCards();
  } catch {
    document.getElementById("providerCards").innerHTML =
      '<p style="color:#b91c1c;grid-column:1/-1">Could not load providers — is the server running on port 8000?</p>';
  }
}

// ── On load: gate + fetch providers after login ─────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  initLoginGate();
});

logoutBtn.addEventListener("click", () => {
  setAuthToken("");
  hideInfoPopup();
  hideColdStartToast();
  setLoading(false);
  results.classList.add("hidden");
  clearLoginError();
  loginPasswordInput.value = "";
  loginOverlay.classList.remove("hidden");
  loginIdInput.focus();
});

// ── Provider cards ────────────────────────────────────────────────────────────
function renderProviderCards() {
  const grid = document.getElementById("providerCards");
  grid.innerHTML = providersData.map(providerCardHTML).join("");
  grid.querySelectorAll(".provider-card[data-id]").forEach((card) => {
    card.addEventListener("click", () => {
      if (!card.classList.contains("not-configured")) {
        selectedProvider = card.dataset.id;
        renderProviderCards();
      }
    });
  });
}

function providerCardHTML(p) {
  const isActive = p.id === selectedProvider;
  const classes = [
    "provider-card",
    isActive ? "active" : "",
    !p.configured ? "not-configured" : "",
  ].filter(Boolean).join(" ");

  return `
    <div class="${classes}" data-id="${p.id}">
      <div class="card-header">
        <span class="provider-name">${p.name}</span>
        <span class="tier-badge tier-${p.tier}">${p.tier}</span>
      </div>
      <div class="card-model">${p.model}</div>
      <div class="card-limits">
        <span>${p.rpm} RPM</span>
        <span>${p.daily_tokens}</span>
      </div>
      <div class="card-status">
        ${p.configured
          ? '<span class="config-ok">&#10003; Configured</span>'
          : '<span class="not-config-label">&#10005; Not configured</span>'}
      </div>
      <div id="tokens-${p.id}" class="card-tokens hidden"></div>
    </div>`;
}

function getWrappedTargetUrl(rawUrl) {
  try {
    const parsed = new URL(rawUrl);
    const host = parsed.hostname.toLowerCase();
    const isSearchHost = ["google.", "bing.", "duckduckgo.com", "search.yahoo."].some((h) => host.includes(h));
    if (!isSearchHost) return "";

    // Common search engines store the target URL in query params like q, url, or u.
    const candidate = parsed.searchParams.get("q")
      || parsed.searchParams.get("url")
      || parsed.searchParams.get("u")
      || "";
    if (!candidate) return "";

    let decoded = candidate;
    try {
      decoded = decodeURIComponent(candidate);
    } catch {
      decoded = candidate;
    }

    if (/^https?:\/\//i.test(decoded)) return decoded;
    return "";
  } catch {
    return "";
  }
}

function _looksLikeLegitHost(hostname) {
  if (!hostname) return false;
  if (hostname === "localhost") return true;
  if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(hostname)) return true;
  return hostname.includes(".");
}

function normalizeUrlForScrape(rawInput) {
  const trimmed = (rawInput || "").trim();
  if (!trimmed) return "";

  let candidate = trimmed;
  if (!/^https?:\/\//i.test(candidate)) {
    candidate = `https://${candidate}`;
  }

  try {
    const parsed = new URL(candidate);
    const isHttp = parsed.protocol === "http:" || parsed.protocol === "https:";
    if (!isHttp) return "";
    if (!_looksLikeLegitHost(parsed.hostname.toLowerCase())) return "";
    return parsed.toString();
  } catch {
    return "";
  }
}

// ── Scrape ────────────────────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const rawUrl = urlInput.value.trim();
  if (!rawUrl) return;

  const url = normalizeUrlForScrape(rawUrl);
  if (!url) {
    showErrorPopup({
      error_type: "INVALID_URL",
      title: "Invalid URL",
      message: "Enter a valid website URL. You can paste domains like discord.com/login and we will use https automatically.",
      suggestion: "Examples: https://discord.com/login or discord.com/login",
    });
    return;
  }
  urlInput.value = url;

  const wrappedTarget = getWrappedTargetUrl(url);
  if (wrappedTarget) {
    showErrorPopup({
      error_type: "SEARCH_WRAPPED_URL",
      title: "Search Results URL Detected",
      message: "You pasted a search page URL, so the scraper is analyzing search results instead of the login page.",
      suggestion: `Use the direct target URL instead: ${wrappedTarget}`,
    });
    return;
  }

  if (!selectedProvider) {
    showErrorPopup({
      error_type: "PROVIDER_NOT_CONFIGURED",
      title: "No Provider Selected",
      message: "No AI provider is selected or configured.",
      suggestion: "Add at least one API key to your .env file and restart the server.",
    });
    return;
  }

  setLoading(true);
  results.classList.add("hidden");

  try {
    const res = await apiFetch("/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, provider: selectedProvider }),
    });

    const data = await res.json();

    if (res.status === 401) {
      setAuthToken("");
      loginOverlay.classList.remove("hidden");
      setLoginError(data.message || data.detail?.message || "Please sign in again.");
      return;
    }

    if (!res.ok) {
      // Structured error from backend
      showErrorPopup({
        error_type: data.error_type || "UNKNOWN",
        title: data.title || "Request Failed",
        message: data.message || `Server returned ${res.status}.`,
        suggestion: data.suggestion || "",
      });
      return;
    }

    renderResults(data);
  } catch (err) {
    // Network-level error (server not running, CORS, etc.)
    showErrorPopup({
      error_type: "NETWORK_ERROR",
      title: "Cannot Reach Server",
      message: "Could not connect to the backend API at " + API_BASE + ".",
      suggestion: "Make sure the server is running: uvicorn main:app --reload (in the backend/ folder).",
    });
  } finally {
    setLoading(false);
  }
});

// ── Field type descriptions (shown as tooltips) ───────────────────────────────
const FIELD_INFO = {
  email:    "Email address field — type=email or name/placeholder contains 'email'",
  password: "Password field — type=password or name/aria-label contains 'password'",
  username: "Username or login field — matched by name or placeholder",
  text:     "Generic text input — purpose could not be determined from its attributes",
  submit:   "Submit button — triggers the form login action",
  checkbox: "Checkbox — commonly a 'Remember me' option",
  hidden:   "Hidden field — not visible to user, carries CSRF tokens or session data",
};

// ── HTML formatter — pretty-prints raw HTML with indentation ──────────────────
function formatHTML(html) {
  const SELF_CLOSING = new Set(["input","br","hr","img","meta","link","area","base","col","embed","param","source","track","wbr"]);
  let out = "";
  let depth = 0;
  const pad = () => "  ".repeat(depth);

  // Split into tokens: tags and text nodes
  const tokens = html.split(/(?=<)|(?<=>)/g);
  for (let token of tokens) {
    token = token.trim();
    if (!token) continue;

    if (token.startsWith("</")) {
      depth = Math.max(0, depth - 1);
      out += pad() + token + "\n";
    } else if (token.startsWith("<")) {
      out += pad() + token + "\n";
      const tagName = (token.match(/^<([a-zA-Z][^\s/>]*)/) || [])[1] || "";
      if (tagName && !SELF_CLOSING.has(tagName.toLowerCase()) && !token.endsWith("/>")) {
        depth++;
      }
    } else {
      const text = token.trim();
      if (text) out += pad() + text + "\n";
    }
  }
  return out.trim();
}

// ── Copy button ───────────────────────────────────────────────────────────────
document.getElementById("copyBtn").addEventListener("click", () => {
  const code = document.querySelector("#htmlSnippet code").textContent;
  navigator.clipboard.writeText(code).then(() => {
    const btn = document.getElementById("copyBtn");
    btn.textContent = "Copied!";
    btn.classList.add("copied");
    setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 2000);
  });
});

// ── Render results ────────────────────────────────────────────────────────────
function renderResults(data) {
  const badge = document.getElementById("statusBadge");
  badge.textContent = data.auth_found ? "Auth Form Found" : "No Auth Form Detected";
  badge.className = `badge ${data.auth_found ? "badge-found" : "badge-not-found"}`;

  const confidence = Number.isFinite(data.auth_confidence) ? data.auth_confidence : 0;
  const safeConfidence = Math.max(0, Math.min(100, confidence));
  document.getElementById("confidenceScore").textContent = `${safeConfidence}%`;
  document.getElementById("confidenceFill").style.width = `${safeConfidence}%`;
  document.getElementById("confidenceLabel").textContent = confidenceLabel(safeConfidence);

  document.getElementById("providerUsed").textContent = `via ${data.provider_used}`;
  const t = data.tokens_used;
  document.getElementById("tokenUsage").textContent =
    `${t.total} tokens (in: ${t.input} / out: ${t.output})`;

  const analysisModeEl = document.getElementById("analysisMode");
  const isRulesFallback = (data.analysis_mode || "llm") === "rules";
  if (isRulesFallback) {
    const reason = data.llm_fallback_reason ? ` (${data.llm_fallback_reason})` : "";
    analysisModeEl.textContent = `Rules Fallback${reason}`;
    analysisModeEl.className = "tag tag-mode-rules";
  } else {
    analysisModeEl.textContent = "LLM";
    analysisModeEl.className = "tag tag-mode-llm";
  }

  const tokenEl = document.getElementById(`tokens-${data.provider_used}`);
  if (tokenEl) {
    tokenEl.textContent = `Last call: ${t.total} tokens`;
    tokenEl.classList.remove("hidden");
  }

  document.getElementById("llmAnalysis").textContent = data.llm_analysis;

  const fieldTags = document.getElementById("fieldTags");
  fieldTags.innerHTML = data.fields_detected.length
    ? data.fields_detected.map((f) => {
        const tip = FIELD_INFO[f] || `Input field type: ${f}`;
        return `<span class="tag field-tag" data-tooltip="${tip}">${f} <span class="field-info-icon">?</span></span>`;
      }).join("")
    : '<span style="color:#718096">None detected</span>';

  document.getElementById("scrapeMethod").textContent = data.scrape_method;

  const screenshotEl = document.getElementById("formScreenshot");
  const screenshotEmpty = document.getElementById("screenshotEmpty");
  if (data.screenshot_base64) {
    screenshotEl.src = `data:image/png;base64,${data.screenshot_base64}`;
    screenshotEl.classList.remove("hidden");
    screenshotEmpty.classList.add("hidden");
  } else {
    screenshotEl.removeAttribute("src");
    screenshotEl.classList.add("hidden");
    screenshotEmpty.classList.remove("hidden");
  }

  const snippet = data.html_snippet ? formatHTML(data.html_snippet) : "No HTML snippet available.";
  document.querySelector("#htmlSnippet code").textContent = snippet;

  results.classList.remove("hidden");
}

function confidenceLabel(score) {
  if (score >= 85) return "Very likely this is a real login/authentication form.";
  if (score >= 65) return "Likely an authentication form, with strong login signals.";
  if (score >= 40) return "Possible authentication UI, but confidence is moderate.";
  return "Low confidence that this is a true login form.";
}

// ── Loading messages ──────────────────────────────────────────────────────────
const LOADING_STEPS = [
  { at: 0,     msg: "Reaching out to the site…",              sub: "Sending a request — this usually takes a second." },
  { at: 2000,  msg: "Reading the page…",                      sub: "Parsing the HTML to find authentication elements." },
  { at: 4000,  msg: "Hmm, this site is a bit different.",     sub: "Launching a real browser in the background — some pages need JavaScript to load." },
  { at: 7000,  msg: "Still working on it…",                   sub: "The site may be slow or JS-heavy. Chromium is rendering it now." },
  { at: 12000, msg: "Almost there, hang tight.",              sub: "Waiting for the login form to appear on the page." },
  { at: 18000, msg: "This one is taking longer than usual.",  sub: "Complex sites can take up to 30 seconds. Please wait." },
  { at: 25000, msg: "Still here, still working.",             sub: "Some sites have heavy JavaScript — the browser is still loading." },
  { at: 35000, msg: "Nearly done…",                           sub: "Wrapping up the analysis. Thank you for your patience." },
];

let _loaderTimers = [];

function startLoadingMessages() {
  const msgEl = document.getElementById("loaderMessage");
  const subEl = document.getElementById("loaderSub");
  _loaderTimers.forEach(clearTimeout);
  _loaderTimers = [];
  LOADING_STEPS.forEach(({ at, msg, sub }) => {
    _loaderTimers.push(setTimeout(() => {
      msgEl.style.opacity = "0";
      subEl.style.opacity = "0";
      setTimeout(() => {
        msgEl.textContent = msg;
        subEl.textContent = sub;
        msgEl.style.opacity = "1";
        subEl.style.opacity = "1";
      }, 200);
    }, at));
  });
}

function stopLoadingMessages() {
  _loaderTimers.forEach(clearTimeout);
  _loaderTimers = [];
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setLoading(on) {
  submitBtn.disabled = on;
  loader.classList.toggle("hidden", !on);
  if (on) startLoadingMessages();
  else stopLoadingMessages();
}
