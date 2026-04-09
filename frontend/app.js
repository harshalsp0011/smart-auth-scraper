// const API_BASE = "http://localhost:8000";
const API_BASE = "https://smart-auth-scraper.onrender.com";

let selectedProvider = null;
let providersData = [];

const form = document.getElementById("scrapeForm");
const urlInput = document.getElementById("urlInput");
const submitBtn = document.getElementById("submitBtn");
const loader = document.getElementById("loader");
const results = document.getElementById("results");

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
  if (e.key === "Escape") hideErrorPopup();
});

// ── On load: fetch providers ──────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", async () => {
  try {
    const res = await fetch(`${API_BASE}/providers`);
    if (!res.ok) throw new Error("Server error");
    const data = await res.json();
    providersData = data.providers;
    selectedProvider = data.default;
    renderProviderCards();
  } catch {
    document.getElementById("providerCards").innerHTML =
      '<p style="color:#b91c1c;grid-column:1/-1">Could not load providers — is the server running on port 8000?</p>';
  }
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

// ── Scrape ────────────────────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;

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
    const res = await fetch(`${API_BASE}/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, provider: selectedProvider }),
    });

    const data = await res.json();

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

  document.getElementById("providerUsed").textContent = `via ${data.provider_used}`;
  const t = data.tokens_used;
  document.getElementById("tokenUsage").textContent =
    `${t.total} tokens (in: ${t.input} / out: ${t.output})`;

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
  const snippet = data.html_snippet ? formatHTML(data.html_snippet) : "No HTML snippet available.";
  document.querySelector("#htmlSnippet code").textContent = snippet;

  results.classList.remove("hidden");
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setLoading(on) {
  submitBtn.disabled = on;
  loader.classList.toggle("hidden", !on);
}
