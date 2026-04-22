(function () {
  const CONSENT_KEY = "productFinderConsentV1";
  const CONSENT_VERSION = "2026-03-31";

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
      if (!res.ok) throw new Error("Consent status unavailable");
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
      throw new Error("Could not save cookie preferences");
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
          <div class="cookieConsentTitle">Privacy and cookies</div>
          <div class="cookieConsentText">
            We use essential cookies for login, security, and core app functions. With your permission, we also use first-party analytics to understand how the workspace is used and improve search, compare, and quote flows.
          </div>
          <div class="cookieConsentActions">
            <button id="btnConsentReject" class="btn secondary compact" type="button">Reject analytics</button>
            <button id="btnConsentManage" class="btn secondary compact" type="button">Manage</button>
            <button id="btnConsentAccept" class="btn compact" type="button">Accept analytics</button>
          </div>
        </div>
      </div>
      <button id="btnConsentPrefs" class="cookiePrefsBtn" type="button" aria-label="Privacy settings">Privacy</button>
      <div id="cookiePrefsModal" class="cookiePrefsModal" aria-hidden="true">
        <div class="cookiePrefsBackdrop" data-consent-close="1"></div>
        <div class="cookiePrefsDialog" role="dialog" aria-modal="true" aria-labelledby="cookiePrefsTitle">
          <button id="btnCookiePrefsClose" class="authModalClose" type="button" aria-label="Close privacy settings">Close</button>
          <div class="cookiePrefsBody">
            <div id="cookiePrefsTitle" class="authTitle">Privacy settings</div>
            <div class="authSubtitle">You can use the workspace with essential cookies only. Analytics stays off until you actively enable it.</div>
            <div class="cookiePrefsRows">
              <div class="cookiePrefRow">
                <div>
                  <div class="cookiePrefLabel">Essential cookies</div>
                  <div class="cookiePrefHint">Required for authentication, security, language, and workspace continuity.</div>
                </div>
                <div class="cookiePrefBadge">Always on</div>
              </div>
              <label class="cookiePrefRow">
                <div>
                  <div class="cookiePrefLabel">Analytics cookies</div>
                  <div class="cookiePrefHint">First-party usage analytics to understand searches, product views, compare actions, and quote activity.</div>
                </div>
                <input id="toggleAnalyticsConsent" type="checkbox" />
              </label>
            </div>
            <div class="cookiePrefsLegal">
              Analytics is disabled by default. You can change your choice at any time from the Privacy button. Event data is first-party, minimized, and pseudonymized where possible.
            </div>
            <div class="cookieConsentActions">
              <button id="btnConsentSavePrefs" class="btn compact" type="button">Save preferences</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(host);

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
})();
