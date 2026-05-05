(function () {
  const CONSENT_KEY = "productFinderConsentV1";
  const CONSENT_VERSION = "2026-03-31";
  const UI_LANG_KEY = "productFinderUiLangV1";
  const CONSENT_I18N = {
    en: {
      title:"Privacy and cookies",
      text:"We use essential cookies for login, security, and core app functions. With your permission, we also use first-party analytics to understand how the workspace is used and improve search, compare, and quote flows.",
      reject:"Reject analytics", manage:"Manage", accept:"Accept analytics", privacy:"Privacy",
      prefs:"Privacy settings", close_prefs:"Close privacy settings", close:"Close",
      prefs_sub:"You can use the workspace with essential cookies only. Analytics stays off until you actively enable it.",
      essential:"Essential cookies", essential_hint:"Required for authentication, security, language, and workspace continuity.", always_on:"Always on",
      analytics:"Analytics cookies", analytics_hint:"First-party usage analytics to understand searches, product views, compare actions, and quote activity.",
      legal:"Analytics is disabled by default. You can change your choice at any time from the Privacy button. Event data is first-party, minimized, and pseudonymized where possible.",
      save:"Save preferences",
      save_error:"Could not save cookie preferences",
      status_error:"Consent status unavailable",
    },
    it: {
      title:"Privacy e cookie",
      text:"Usiamo cookie essenziali per login, sicurezza e funzioni principali. Con il tuo consenso usiamo anche analytics di prima parte per capire come viene usato il workspace e migliorare ricerca, confronto e offerte.",
      reject:"Rifiuta analytics", manage:"Gestisci", accept:"Accetta analytics", privacy:"Privacy",
      prefs:"Impostazioni privacy", close_prefs:"Chiudi impostazioni privacy", close:"Chiudi",
      prefs_sub:"Puoi usare il workspace solo con cookie essenziali. Analytics resta disattivato finche non lo abiliti.",
      essential:"Cookie essenziali", essential_hint:"Necessari per autenticazione, sicurezza, lingua e continuita del workspace.", always_on:"Sempre attivi",
      analytics:"Cookie analytics", analytics_hint:"Analytics di prima parte per comprendere ricerche, viste prodotto, confronti e attivita offerta.",
      legal:"Analytics e disattivato di default. Puoi cambiare scelta in qualsiasi momento dal pulsante Privacy. I dati evento sono di prima parte, minimizzati e pseudonimizzati ove possibile.",
      save:"Salva preferenze",
      save_error:"Impossibile salvare le preferenze cookie",
      status_error:"Stato consenso non disponibile",
    },
  };
  ["fr","es","pt","ru","ar","pl","cs","hr","sl"].forEach(code => { CONSENT_I18N[code] = CONSENT_I18N.en; });

  function currentLang() {
    try { return String(localStorage.getItem(UI_LANG_KEY) || "en").toLowerCase().split("-")[0] || "en"; } catch (_e) { return "en"; }
  }

  function tc(key) {
    const pack = CONSENT_I18N[currentLang()] || CONSENT_I18N.en;
    return pack[key] || CONSENT_I18N.en[key] || key;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function readLocalConsent() {
    try {
      const raw = localStorage.getItem(CONSENT_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_e) {
      return null;
    }
  }

  function writeLocalConsent(data) {
    try {
      localStorage.setItem(CONSENT_KEY, JSON.stringify(data || {}));
    } catch (_e) {}
  }

  async function fetchConsentStatus() {
    try {
      const res = await fetch("/auth/consent", { credentials: "same-origin" });
      if (!res.ok) throw new Error(tc("status_error"));
      return await res.json();
    } catch (_e) {
      return null;
    }
  }

  async function persistConsent(analytics, source) {
    const payload = {
      analytics: !!analytics,
      source: String(source || "banner"),
      consent_version: CONSENT_VERSION,
    };
    const res = await fetch("/auth/consent", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(tc("save_error"));
    }
    const data = await res.json();
    writeLocalConsent({
      analytics: !!payload.analytics,
      updated_at: new Date().toISOString(),
      consent_version: CONSENT_VERSION,
    });
    document.dispatchEvent(new CustomEvent("productfinder:consent-changed", { detail: data?.consent || payload }));
    return data;
  }

  function currentConsent() {
    const local = readLocalConsent();
    return {
      analytics: !!local?.analytics,
      consent_version: String(local?.consent_version || ""),
      has_choice: !!String(local?.consent_version || "").trim(),
    };
  }

  function ensureUi() {
    if (document.getElementById("cookieConsentBanner")) return;
    const host = document.createElement("div");
    host.innerHTML = `
      <div id="cookieConsentBanner" class="cookieConsentBanner" aria-hidden="true">
        <div class="cookieConsentCard">
          <div class="cookieConsentTitle" data-consent-i18n="title">Privacy and cookies</div>
          <div class="cookieConsentText">
            We use essential cookies for login, security, and core app functions. With your permission, we also use first-party analytics to understand how the workspace is used and improve search, compare, and quote flows.
          </div>
          <div class="cookieConsentActions">
            <button id="btnConsentReject" class="btn secondary compact" type="button" data-consent-i18n="reject">Reject analytics</button>
            <button id="btnConsentManage" class="btn secondary compact" type="button" data-consent-i18n="manage">Manage</button>
            <button id="btnConsentAccept" class="btn compact" type="button" data-consent-i18n="accept">Accept analytics</button>
          </div>
        </div>
      </div>
      <button id="btnConsentPrefs" class="cookiePrefsBtn" type="button" aria-label="Privacy settings" data-consent-i18n="privacy">Privacy</button>
      <div id="cookiePrefsModal" class="cookiePrefsModal" aria-hidden="true">
        <div class="cookiePrefsBackdrop" data-consent-close="1"></div>
        <div class="cookiePrefsDialog" role="dialog" aria-modal="true" aria-labelledby="cookiePrefsTitle">
          <button id="btnCookiePrefsClose" class="authModalClose" type="button" aria-label="Close privacy settings" data-consent-i18n="close">Close</button>
          <div class="cookiePrefsBody">
            <div id="cookiePrefsTitle" class="authTitle" data-consent-i18n="prefs">Privacy settings</div>
            <div class="authSubtitle" data-consent-i18n="prefs_sub">You can use the workspace with essential cookies only. Analytics stays off until you actively enable it.</div>
            <div class="cookiePrefsRows">
              <div class="cookiePrefRow">
                <div>
                  <div class="cookiePrefLabel" data-consent-i18n="essential">Essential cookies</div>
                  <div class="cookiePrefHint" data-consent-i18n="essential_hint">Required for authentication, security, language, and workspace continuity.</div>
                </div>
                <div class="cookiePrefBadge" data-consent-i18n="always_on">Always on</div>
              </div>
              <label class="cookiePrefRow">
                <div>
                  <div class="cookiePrefLabel" data-consent-i18n="analytics">Analytics cookies</div>
                  <div class="cookiePrefHint" data-consent-i18n="analytics_hint">First-party usage analytics to understand searches, product views, compare actions, and quote activity.</div>
                </div>
                <input id="toggleAnalyticsConsent" type="checkbox" />
              </label>
            </div>
            <div class="cookiePrefsLegal" data-consent-i18n="legal">
              Analytics is disabled by default. You can change your choice at any time from the Privacy button. Event data is first-party, minimized, and pseudonymized where possible.
            </div>
            <div class="cookieConsentActions">
              <button id="btnConsentSavePrefs" class="btn compact" type="button" data-consent-i18n="save">Save preferences</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(host);
    applyConsentI18n();

    document.getElementById("btnConsentAccept")?.addEventListener("click", async () => {
      await saveChoice(true, "banner_accept");
    });
    document.getElementById("btnConsentReject")?.addEventListener("click", async () => {
      await saveChoice(false, "banner_reject");
    });
    document.getElementById("btnConsentManage")?.addEventListener("click", () => openPreferences());
    document.getElementById("btnConsentPrefs")?.addEventListener("click", () => openPreferences());
    document.getElementById("btnConsentSavePrefs")?.addEventListener("click", async () => {
      const checked = !!document.getElementById("toggleAnalyticsConsent")?.checked;
      await saveChoice(checked, "preferences");
      closePreferences();
    });
    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.matches("[data-consent-close='1']") || target.id === "btnCookiePrefsClose") {
        closePreferences();
      }
    });
  }

  function applyConsentI18n() {
    Array.from(document.querySelectorAll("[data-consent-i18n]")).forEach(el => {
      const key = String(el.getAttribute("data-consent-i18n") || "").trim();
      if (key) el.textContent = tc(key);
    });
    const text = document.querySelector(".cookieConsentText");
    if (text) text.textContent = tc("text");
    const prefs = document.getElementById("btnConsentPrefs");
    if (prefs) prefs.setAttribute("aria-label", tc("prefs"));
    const close = document.getElementById("btnCookiePrefsClose");
    if (close) close.setAttribute("aria-label", tc("close_prefs"));
  }

  function renderBanner() {
    ensureUi();
    const consent = currentConsent();
    const banner = document.getElementById("cookieConsentBanner");
    const prefsBtn = document.getElementById("btnConsentPrefs");
    const toggle = document.getElementById("toggleAnalyticsConsent");
    if (toggle) toggle.checked = !!consent.analytics;
    if (banner) {
      banner.classList.toggle("show", !consent.has_choice);
      banner.setAttribute("aria-hidden", consent.has_choice ? "true" : "false");
    }
    if (prefsBtn) {
      prefsBtn.style.display = consent.has_choice ? "inline-flex" : "none";
    }
  }

  function openPreferences() {
    ensureUi();
    const modal = document.getElementById("cookiePrefsModal");
    const toggle = document.getElementById("toggleAnalyticsConsent");
    const consent = currentConsent();
    if (toggle) toggle.checked = !!consent.analytics;
    if (!modal) return;
    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closePreferences() {
    const modal = document.getElementById("cookiePrefsModal");
    if (!modal) return;
    modal.classList.remove("show");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  async function saveChoice(analytics, source) {
    await persistConsent(analytics, source);
    renderBanner();
  }

  async function initConsent() {
    ensureUi();
    const remote = await fetchConsentStatus();
    if (remote && remote.has_choice) {
      writeLocalConsent({
        analytics: !!remote.analytics,
        updated_at: String(remote.updated_at || ""),
        consent_version: String(remote.consent_version || CONSENT_VERSION),
      });
    }
    renderBanner();
  }

  async function track(eventType, payload) {
    const consent = currentConsent();
    if (!consent.analytics) return false;
    const body = {
      event_type: String(eventType || "").trim(),
      page: String(payload?.page || document.body?.dataset?.page || ""),
      path: String(payload?.path || window.location.pathname || ""),
      product_code: String(payload?.product_code || ""),
      query_text: String(payload?.query_text || ""),
      filters: (payload?.filters && typeof payload.filters === "object") ? payload.filters : {},
      metadata: (payload?.metadata && typeof payload.metadata === "object") ? payload.metadata : {},
    };
    if (!body.event_type) return false;
    try {
      await fetch("/auth/analytics/event", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        keepalive: true,
      });
      return true;
    } catch (_e) {
      return false;
    }
  }

  window.ProductFinderConsent = {
    version: CONSENT_VERSION,
    hasAnalytics() {
      return !!currentConsent().analytics;
    },
    openPreferences,
    async setAnalytics(enabled, source) {
      await saveChoice(!!enabled, source || "api");
    },
    track,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initConsent, { once: true });
  } else {
    initConsent();
  }
  document.addEventListener("productfinder:language-changed", () => {
    ensureUi();
    applyConsentI18n();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === UI_LANG_KEY) applyConsentI18n();
  });
})();
