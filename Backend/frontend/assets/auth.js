(function () {
  const USER_KEY = "productFinderAuthUserV1";
  const AUTH_VIEW_KEY = "productFinderAuthViewV1";
  const LAST_ACTIVITY_KEY = "productFinderAuthLastActivityV1";
  const UI_LANG_KEY = "productFinderUiLangV1";
  const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
  const listeners = new Set();
  let authNotice = "";
  let authNoticeTone = "info";
  let refreshPromise = null;
  let authConfig = { oauth2_enabled: false, oauth2_provider: "", local_login_enabled: true, local_signup_enabled: true };
  const AUTH_I18N = {
    en: {
      sign_in:"Sign in", request_access:"Request access", open_account_panel:"Open account panel", user:"User",
      sso_sign_in:"Sign in with SSO",
      admin:"Admin", it:"IT", director:"Director", manager:"Manager", marketing:"Marketing",
      status:"Status", country:"Country", not_set:"Not set", admin_tools:"Admin tools", full_access:"Full access available",
      manager_countries:"Manager countries", none_assigned:"None assigned", manager_tools:"Manager tools", readonly_country:"Read-only country access",
      open_panel:"Open panel", logout:"Logout", active:"Your account is active.", workspace_access:"Workspace access",
      subtitle:"Sign in to search, compare, quote, and collaborate in one workspace.", auth_tabs:"Authentication tabs",
      login:"Login", signup:"Sign up", work_email:"Work email", password:"Password", confirm_password:"Confirm password",
      full_name:"Full name", company_name:"Company name", select_country:"Select country", enter_country:"Enter your country",
      password_rules:"Password rules: at least 10 characters, with at least 1 letter and 1 number.",
      login_helper:"Use your approved account to unlock search and filters.", signup_helper:"New access requests stay pending until an admin approves them.",
      forgot_password:"Forgot password?", reset_helper:"We will send you a secure reset link if your account exists.",
      login_status:"Use your approved account to continue.", signup_status:"Create your request and wait for approval before logging in.",
      show:"Show", hide:"Hide", show_password:"Show password", hide_password:"Hide password", show_password_confirmation:"Show password confirmation",
      close_account_panel:"Close account panel", close:"Close", idle_expired:"Your session expired after inactivity. Please log in again.",
      invalid_credentials:"Email or password not recognized. Check both fields and try again.", pending:"Your account request is waiting for admin approval.",
      rejected:"Your account was rejected. Contact an administrator if needed.", weak_password:"Use a stronger password with both letters and numbers.",
      email_registered:"This email is already registered. Try logging in instead.", session_expired:"Your session expired. Please log in again.",
      generic_error:"Something went wrong. Please try again.", logged_out:"You have been logged out.",
      email_first:"Enter your email first.", password_first:"Enter your password first.", confirm_first:"Confirm your password before sending the request.",
      passwords_mismatch:"The two passwords do not match.", full_name_first:"Add your full name so the admin can identify your request.",
      company_first:"Add your company name so we can prefill your quotes after login.", country_first:"Add your country so the admin can route your request correctly.",
      checking:"Checking your credentials...", creating:"Creating your access request...", account_created:"Account request created. Wait for admin approval before logging in.",
      reset_email_first:"Enter your email first so we can send the reset link.", reset_preparing:"Preparing your reset link...",
      reset_sent:"If the account exists, a reset link has been sent.", previous_invalid:"Your previous session is no longer valid. Please log in again.",
    },
    it: {
      sign_in:"Accedi", request_access:"Richiedi accesso", open_account_panel:"Apri pannello account", user:"Utente",
      sso_sign_in:"Accedi con SSO",
      admin:"Admin", it:"IT", director:"Direttore", manager:"Manager", marketing:"Marketing",
      status:"Stato", country:"Paese", not_set:"Non impostato", admin_tools:"Strumenti admin", full_access:"Accesso completo disponibile",
      manager_countries:"Paesi manager", none_assigned:"Nessuno assegnato", manager_tools:"Strumenti manager", readonly_country:"Accesso paese in sola lettura",
      open_panel:"Apri pannello", logout:"Esci", active:"Il tuo account e attivo.", workspace_access:"Accesso workspace",
      subtitle:"Accedi per cercare, confrontare, preparare offerte e collaborare in un unico workspace.", auth_tabs:"Schede autenticazione",
      login:"Login", signup:"Registrati", work_email:"Email aziendale", password:"Password", confirm_password:"Conferma password",
      full_name:"Nome completo", company_name:"Nome azienda", select_country:"Seleziona paese", enter_country:"Inserisci il tuo paese",
      password_rules:"Regole password: almeno 10 caratteri, con almeno 1 lettera e 1 numero.",
      login_helper:"Usa il tuo account approvato per sbloccare ricerca e filtri.", signup_helper:"Le nuove richieste restano in attesa finche un admin le approva.",
      forgot_password:"Password dimenticata?", reset_helper:"Ti invieremo un link sicuro di reset se l'account esiste.",
      login_status:"Usa il tuo account approvato per continuare.", signup_status:"Crea la richiesta e attendi approvazione prima di accedere.",
      show:"Mostra", hide:"Nascondi", show_password:"Mostra password", hide_password:"Nascondi password", show_password_confirmation:"Mostra conferma password",
      close_account_panel:"Chiudi pannello account", close:"Chiudi", idle_expired:"Sessione scaduta per inattivita. Accedi di nuovo.",
      invalid_credentials:"Email o password non riconosciute. Controlla entrambi i campi e riprova.", pending:"La tua richiesta e in attesa di approvazione admin.",
      rejected:"Il tuo account e stato rifiutato. Contatta un amministratore se necessario.", weak_password:"Usa una password piu forte con lettere e numeri.",
      email_registered:"Questa email e gia registrata. Prova ad accedere.", session_expired:"Sessione scaduta. Accedi di nuovo.",
      generic_error:"Qualcosa e andato storto. Riprova.", logged_out:"Logout effettuato.",
      email_first:"Inserisci prima la tua email.", password_first:"Inserisci prima la password.", confirm_first:"Conferma la password prima di inviare la richiesta.",
      passwords_mismatch:"Le due password non coincidono.", full_name_first:"Aggiungi il nome completo cosi l'admin puo identificarti.",
      company_first:"Aggiungi il nome azienda per precompilare le offerte dopo il login.", country_first:"Aggiungi il paese per indirizzare correttamente la richiesta.",
      checking:"Verifica credenziali...", creating:"Creazione richiesta di accesso...", account_created:"Richiesta creata. Attendi approvazione admin prima di accedere.",
      reset_email_first:"Inserisci prima la tua email per inviare il link di reset.", reset_preparing:"Preparazione link di reset...",
      reset_sent:"Se l'account esiste, e stato inviato un link di reset.", previous_invalid:"La sessione precedente non e piu valida. Accedi di nuovo.",
    },
  };
  ["fr","es","pt","ru","ar","pl","cs","hr","sl"].forEach(code => { AUTH_I18N[code] = AUTH_I18N.en; });

  function currentLang() {
    try { return String(localStorage.getItem(UI_LANG_KEY) || "en").toLowerCase().split("-")[0] || "en"; } catch (_e) { return "en"; }
  }

  function ta(key, vars) {
    const lang = currentLang();
    const pack = AUTH_I18N[lang] || AUTH_I18N.en;
    let text = pack[key] || AUTH_I18N.en[key] || key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
    }
    return text;
  }

  function sameOrigin(url) {
    try {
      const target = new URL(url, window.location.origin);
      return target.origin === window.location.origin;
    } catch (_e) {
      return true;
    }
  }

  function readToken() {
    return "";
  }

  function readUser() {
    try {
      let raw = sessionStorage.getItem(USER_KEY);
      if (!raw) {
        raw = localStorage.getItem(USER_KEY);
        if (raw) {
          sessionStorage.setItem(USER_KEY, raw);
          localStorage.removeItem(USER_KEY);
        }
      }
      return raw ? JSON.parse(raw) : null;
    } catch (_e) {
      return null;
    }
  }

  function readView() {
    try {
      const value = String(localStorage.getItem(AUTH_VIEW_KEY) || "login").trim().toLowerCase();
      return value === "signup" ? "signup" : "login";
    } catch (_e) {
      return "login";
    }
  }

  function writeView(view) {
    try {
      localStorage.setItem(AUTH_VIEW_KEY, view === "signup" ? "signup" : "login");
    } catch (_e) {}
  }

  function writeSession(token, user) {
    try {
      sessionStorage.setItem(USER_KEY, JSON.stringify(user || null));
      touchSessionActivity();
      localStorage.removeItem(USER_KEY);
    } catch (_e) {}
  }

  function clearSession() {
    try {
      sessionStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(LAST_ACTIVITY_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(LAST_ACTIVITY_KEY);
    } catch (_e) {}
  }

  function touchSessionActivity() {
    try {
      sessionStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
    } catch (_e) {}
  }

  function isSessionIdleExpired() {
    try {
      const user = readUser();
      if (!user) return false;
      const last = Number(sessionStorage.getItem(LAST_ACTIVITY_KEY) || 0);
      if (!last) return false;
      return (Date.now() - last) > IDLE_TIMEOUT_MS;
    } catch (_e) {
      return false;
    }
  }

  function expireSessionForInactivity() {
    clearSession();
    setGlobalNotice(ta("idle_expired"), "warn");
    renderAuthMount();
    renderModalBody();
    emit({ authenticated: false, user: null, reason: "idle-timeout" });
  }

  function setGlobalNotice(message, tone) {
    authNotice = String(message || "").trim();
    authNoticeTone = tone || "info";
  }

  function clearGlobalNotice() {
    authNotice = "";
    authNoticeTone = "info";
  }

  function emit(state) {
    listeners.forEach((fn) => {
      try { fn(state); } catch (_e) {}
    });
    document.dispatchEvent(new CustomEvent("productfinder:auth-changed", { detail: state }));
  }

  function mapErrorMessage(message) {
    const text = String(message || "").trim();
    const lower = text.toLowerCase();
    if (lower.includes("invalid credentials")) {
      return { text: ta("invalid_credentials"), tone: "error" };
    }
    if (lower.includes("account status is pending")) {
      return { text: ta("pending"), tone: "warn" };
    }
    if (lower.includes("account status is rejected")) {
      return { text: ta("rejected"), tone: "error" };
    }
    if (lower.includes("password must contain letters and numbers")) {
      return { text: ta("weak_password"), tone: "error" };
    }
    if (lower.includes("email already registered")) {
      return { text: ta("email_registered"), tone: "warn" };
    }
    if (lower.includes("token expired") || lower.includes("session expired")) {
      return { text: ta("session_expired"), tone: "warn" };
    }
    return { text: text || ta("generic_error"), tone: "error" };
  }

  function extractErrorText(payload) {
    const source = payload && (payload.detail ?? payload.message ?? payload.error);
    if (Array.isArray(source)) {
      const text = source
        .map((item) => {
          if (item == null) return "";
          if (typeof item === "string") return item;
          const location = Array.isArray(item.loc) ? item.loc.filter(Boolean).join(" -> ") : "";
          const message = String(item.msg || item.message || "").trim();
          return [location, message].filter(Boolean).join(": ");
        })
        .filter(Boolean)
        .join(" | ");
      return text || "";
    }
    if (source && typeof source === "object") {
      const message = String(source.msg || source.message || "").trim();
      if (message) return message;
      try {
        return JSON.stringify(source);
      } catch (_e) {
        return "";
      }
    }
    return String(source || "").trim();
  }

  function toneClassName(tone) {
    return tone === "error" ? "isError" : tone === "warn" ? "isWarn" : "isInfo";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function userInitials(user) {
    const source = String(user?.full_name || user?.email || "User").trim();
    const parts = source.split(/\s+/).filter(Boolean).slice(0, 2);
    if (!parts.length) return "U";
    return parts.map((part) => part[0]?.toUpperCase() || "").join("");
  }

  function roleLabel(user) {
    const role = String(user?.role || "user").trim().toLowerCase();
    if (role === "admin") return ta("admin");
    if (role === "it") return ta("it");
    if (role === "director") return ta("director");
    if (role === "manager") return ta("manager");
    if (role === "marketing") return ta("marketing");
    return ta("user");
  }

  function countryOptions(selectedValue) {
    const api = window.ProductFinderCountries;
    if (api && typeof api.optionList === "function") {
      return api.optionList(selectedValue ? [selectedValue] : [], { includePlaceholder: true, placeholder: "Select country", includeOther: true });
    }
    const selected = String(selectedValue || "").trim();
    return `<option value=""${selected ? "" : ' selected="selected"'}>${escapeHtml(ta("select_country"))}</option>${selected ? `<option value="${escapeHtml(selected)}" selected="selected">${escapeHtml(selected)}</option>` : ""}`;
  }

  function isOtherCountryValue(value) {
    const api = window.ProductFinderCountries;
    return String(value || "").trim() === String(api?.otherValue || "__OTHER__");
  }

  function ensureModal() {
    if (document.getElementById("authModal")) return;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
      <div id="authModal" class="authModal" aria-hidden="true">
        <div class="authModalBackdrop" data-auth-close="1"></div>
        <div class="authModalDialog" role="dialog" aria-modal="true" aria-labelledby="authModalTitle">
          <button id="btnAuthModalClose" class="authModalClose" type="button" aria-label="${escapeHtml(ta("close_account_panel"))}">${escapeHtml(ta("close"))}</button>
          <div id="authModalBody"></div>
        </div>
      </div>
    `;
    document.body.appendChild(wrapper.firstElementChild);
    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.matches("[data-auth-close='1']") || target.id === "btnAuthModalClose") {
        closeModal();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeModal();
    });
  }

  function openModal(view) {
    ensureModal();
    if (view) writeView(view);
    renderModalBody();
    const modal = document.getElementById("authModal");
    if (!modal) return;
    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    const modal = document.getElementById("authModal");
    if (!modal) return;
    modal.classList.remove("show");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function renderStatusLine(fallbackText, fallbackTone) {
    const text = authNotice || fallbackText;
    const tone = authNotice ? authNoticeTone : (fallbackTone || "info");
    return `<div id="authStatus" class="authStatus ${toneClassName(tone)}">${escapeHtml(text)}</div>`;
  }

  function renderLoggedInMount(user) {
    const mount = document.getElementById("authMount");
    if (!mount) return;
    mount.innerHTML = `
      <div class="authTriggerGroup">
        <button id="btnAuthAccount" class="authCompactTrigger" type="button" aria-label="${escapeHtml(ta("open_account_panel"))}">
          <span class="authCompactBadge">${escapeHtml(userInitials(user))}</span>
          <span class="authCompactMeta">
            <span class="authCompactName">${escapeHtml(user.full_name || user.email || ta("user"))}</span>
            <span class="authCompactRole">${escapeHtml(roleLabel(user))}</span>
          </span>
        </button>
      </div>
    `;
    mount.querySelector("#btnAuthAccount")?.addEventListener("click", () => openModal("account"));
  }

  function renderLoggedOutMount() {
    const mount = document.getElementById("authMount");
    if (!mount) return;
    const ssoLabel = authConfig.oauth2_provider ? `${ta("sso_sign_in")} ${escapeHtml(authConfig.oauth2_provider)}` : ta("sso_sign_in");
    mount.innerHTML = `
      <div class="authTriggerGroup">
        ${authConfig.oauth2_enabled ? `<button id="btnAuthSso" class="btn compact" type="button">${ssoLabel}</button>` : ""}
        ${authConfig.local_login_enabled ? `<button id="btnAuthOpenLogin" class="btn secondary compact" type="button">${escapeHtml(ta("sign_in"))}</button>` : ""}
        ${authConfig.local_signup_enabled ? `<button id="btnAuthOpenSignup" class="btn compact" type="button">${escapeHtml(ta("request_access"))}</button>` : ""}
      </div>
    `;
    mount.querySelector("#btnAuthSso")?.addEventListener("click", () => {
      window.location.href = "/auth/oauth/login";
    });
    mount.querySelector("#btnAuthOpenLogin")?.addEventListener("click", () => openModal("login"));
    mount.querySelector("#btnAuthOpenSignup")?.addEventListener("click", () => openModal("signup"));
  }

  function renderAuthMount() {
    const user = readUser();
    if (user) {
      renderLoggedInMount(user);
    } else {
      renderLoggedOutMount();
    }
  }

  function renderAccountView(user) {
    const role = String(user?.role || "").toLowerCase();
    const isAdmin = role === "admin";
    const canOpenPanel = !!role;
    return `
      <div class="authAccountCard">
        <div class="authAccountHead">
          <div class="authIdentityBadge">${escapeHtml(userInitials(user))}</div>
          <div class="authUserMeta">
            <div id="authModalTitle" class="authUserName">${escapeHtml(user.full_name || ta("user"))}</div>
            <div class="authUserRole">
              <span class="authRolePill">${escapeHtml(roleLabel(user))}</span>
              <span>${escapeHtml(user.email || "")}</span>
            </div>
          </div>
        </div>
        <div class="authAccountInfo">
          <div class="authInfoRow"><span>${escapeHtml(ta("status"))}</span><strong>${escapeHtml(user.status || "approved")}</strong></div>
          <div class="authInfoRow"><span>${escapeHtml(ta("country"))}</span><strong>${escapeHtml(user.country || ta("not_set"))}</strong></div>
          ${isAdmin ? `<div class="authInfoRow"><span>${escapeHtml(ta("admin_tools"))}</span><strong>${escapeHtml(ta("full_access"))}</strong></div>` : ""}
          ${role === "manager" ? `<div class="authInfoRow"><span>${escapeHtml(ta("manager_countries"))}</span><strong>${escapeHtml(Array.isArray(user.assigned_countries) && user.assigned_countries.length ? user.assigned_countries.join(", ") : ta("none_assigned"))}</strong></div><div class="authInfoRow"><span>${escapeHtml(ta("manager_tools"))}</span><strong>${escapeHtml(ta("readonly_country"))}</strong></div>` : ""}
        </div>
        <div class="authActions">
          ${canOpenPanel ? `<button id="btnAuthOpenAdmin" class="btn compact" type="button">${escapeHtml(ta("open_panel"))}</button>` : ""}
          <button id="btnAuthLogout" class="btn secondary compact" type="button">${escapeHtml(ta("logout"))}</button>
        </div>
        ${renderStatusLine(ta("active"), "info")}
      </div>
    `;
  }

  function renderAccessView(view) {
    const loginActive = view !== "signup";
    const localLoginAvailable = loginActive ? authConfig.local_login_enabled : authConfig.local_signup_enabled;
    const ssoLabel = authConfig.oauth2_provider ? `${ta("sso_sign_in")} ${authConfig.oauth2_provider}` : ta("sso_sign_in");
    return `
      <div class="authBox authBoxExpanded">
        <div class="authHeader">
          <div>
            <div id="authModalTitle" class="authTitle">${escapeHtml(ta("workspace_access"))}</div>
            <div class="authSubtitle">${escapeHtml(ta("subtitle"))}</div>
          </div>
          ${authConfig.local_login_enabled && authConfig.local_signup_enabled ? `<div class="authTabs" role="tablist" aria-label="${escapeHtml(ta("auth_tabs"))}">
            <button id="btnAuthTabLogin" class="authTab ${loginActive ? "active" : ""}" type="button">${escapeHtml(ta("login"))}</button>
            <button id="btnAuthTabSignup" class="authTab ${!loginActive ? "active" : ""}" type="button">${escapeHtml(ta("signup"))}</button>
          </div>` : ""}
        </div>
        ${authConfig.oauth2_enabled ? `<div class="authActions"><button id="btnAuthSsoModal" class="btn compact" type="button">${escapeHtml(ssoLabel)}</button></div>` : ""}
        ${localLoginAvailable ? `<div class="authFields">
          <input id="authEmail" type="email" placeholder="${escapeHtml(ta("work_email"))}" autocomplete="email" />
          <div class="authPasswordField">
            <input id="authPassword" type="password" placeholder="${escapeHtml(ta("password"))}" autocomplete="${loginActive ? "current-password" : "new-password"}" />
            <button class="authPasswordToggle" type="button" data-auth-toggle-password="authPassword" aria-label="${escapeHtml(ta("show_password"))}">${escapeHtml(ta("show"))}</button>
          </div>
          ${loginActive ? "" : `
          <div class="authPasswordField">
            <input id="authPasswordConfirm" type="password" placeholder="${escapeHtml(ta("confirm_password"))}" autocomplete="new-password" />
            <button class="authPasswordToggle" type="button" data-auth-toggle-password="authPasswordConfirm" aria-label="${escapeHtml(ta("show_password_confirmation"))}">${escapeHtml(ta("show"))}</button>
          </div>`}
          <input id="authName" class="${loginActive ? "authHidden" : ""}" type="text" placeholder="${escapeHtml(ta("full_name"))}" autocomplete="name" />
          <input id="authCompany" class="${loginActive ? "authHidden" : ""}" type="text" placeholder="${escapeHtml(ta("company_name"))}" autocomplete="organization" />
          <select id="authCountry" class="${loginActive ? "authHidden" : ""}" autocomplete="country-name">
            ${countryOptions("")}
          </select>
          <input id="authCountryOther" class="authHidden" type="text" placeholder="${escapeHtml(ta("enter_country"))}" autocomplete="country-name" />
        </div>` : ""}
        ${loginActive || !localLoginAvailable ? "" : `<div class="authHelper">${escapeHtml(ta("password_rules"))}</div>`}
        ${localLoginAvailable ? `
        <div class="authActions">
          <button id="btnAuthPrimary" class="btn compact" type="button">${escapeHtml(loginActive ? ta("login") : ta("request_access"))}</button>
          <div class="authHelper">${escapeHtml(loginActive ? ta("login_helper") : ta("signup_helper"))}</div>
        </div>
        ${loginActive ? `<div class="authActions"><button id="btnAuthForgotPassword" class="btn secondary compact" type="button">${escapeHtml(ta("forgot_password"))}</button><div class="authHelper">${escapeHtml(ta("reset_helper"))}</div></div>` : ""}` : ""}
        ${renderStatusLine(loginActive ? ta("login_status") : ta("signup_status"), loginActive ? "info" : "warn")}
      </div>
    `;
  }

  function renderModalBody() {
    ensureModal();
    const body = document.getElementById("authModalBody");
    if (!body) return;
    const user = readUser();
    const view = readView();
    body.innerHTML = user ? renderAccountView(user) : renderAccessView(view);

    if (user) {
      body.querySelector("#btnAuthLogout")?.addEventListener("click", async () => {
        try {
          await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
        } catch (_e) {}
        clearSession();
        setGlobalNotice(ta("logged_out"), "info");
        renderAuthMount();
        renderModalBody();
        emit({ authenticated: false, user: null, reason: "logout" });
      });
      body.querySelector("#btnAuthOpenAdmin")?.addEventListener("click", () => {
        window.location.href = "/frontend/admin.html";
      });
      return;
    }

    const status = body.querySelector("#authStatus");
    const email = body.querySelector("#authEmail");
    const password = body.querySelector("#authPassword");
    const passwordConfirm = body.querySelector("#authPasswordConfirm");
    const name = body.querySelector("#authName");
    const company = body.querySelector("#authCompany");
    const country = body.querySelector("#authCountry");
    const countryOther = body.querySelector("#authCountryOther");

    function setStatus(message, tone) {
      if (!status) return;
      status.className = `authStatus ${toneClassName(tone || "info")}`;
      status.textContent = String(message || "").trim();
    }

    function switchView(nextView) {
      writeView(nextView);
      clearGlobalNotice();
      renderModalBody();
    }

    function syncCountryField() {
      const signupMode = readView() === "signup";
      const showCustomCountry = signupMode && isOtherCountryValue(country?.value);
      countryOther?.classList.toggle("authHidden", !showCustomCountry);
      if (!showCustomCountry && countryOther) {
        countryOther.value = "";
      }
    }

    body.querySelector("#btnAuthTabLogin")?.addEventListener("click", () => switchView("login"));
    body.querySelector("#btnAuthTabSignup")?.addEventListener("click", () => switchView("signup"));
    body.querySelector("#btnAuthSsoModal")?.addEventListener("click", () => {
      window.location.href = "/auth/oauth/login";
    });
    body.querySelectorAll("[data-auth-toggle-password]").forEach((button) => {
      button.addEventListener("click", () => {
        const targetId = String(button.getAttribute("data-auth-toggle-password") || "").trim();
        const target = targetId ? body.querySelector(`#${CSS.escape(targetId)}`) : null;
        if (!target) return;
        const showing = target.getAttribute("type") === "text";
        target.setAttribute("type", showing ? "password" : "text");
        button.textContent = showing ? ta("show") : ta("hide");
        button.setAttribute("aria-label", showing ? ta("show_password") : ta("hide_password"));
      });
    });
    country?.addEventListener("change", syncCountryField);
    syncCountryField();

    async function handlePrimaryAction() {
      const mode = readView();
      const emailValue = String(email?.value || "").trim();
      const passwordValue = String(password?.value || "");
      const passwordConfirmValue = String(passwordConfirm?.value || "");
      const nameValue = String(name?.value || "").trim();
      const companyValue = String(company?.value || "").trim();
      const countryValue = isOtherCountryValue(country?.value)
        ? String(countryOther?.value || "").trim()
        : String(country?.value || "").trim();

      if (!emailValue) {
        setStatus(ta("email_first"), "warn");
        email?.focus();
        return;
      }
      if (!passwordValue) {
        setStatus(ta("password_first"), "warn");
        password?.focus();
        return;
      }
      if (mode === "signup" && !passwordConfirmValue) {
        setStatus(ta("confirm_first"), "warn");
        passwordConfirm?.focus();
        return;
      }
      if (mode === "signup" && passwordValue !== passwordConfirmValue) {
        setStatus(ta("passwords_mismatch"), "error");
        passwordConfirm?.focus();
        return;
      }
      if (mode === "signup" && !nameValue) {
        setStatus(ta("full_name_first"), "warn");
        name?.focus();
        return;
      }
      if (mode === "signup" && !companyValue) {
        setStatus(ta("company_first"), "warn");
        company?.focus();
        return;
      }
      if (mode === "signup" && !countryValue) {
        setStatus(ta("country_first"), "warn");
        if (isOtherCountryValue(country?.value)) {
          countryOther?.focus();
        } else {
          country?.focus();
        }
        return;
      }

      try {
        if (mode === "login") {
          setStatus(ta("checking"), "info");
          const data = await jsonRequest("/auth/login", {
            email: emailValue,
            password: passwordValue,
          });
          writeSession("", data.user);
          clearGlobalNotice();
          renderAuthMount();
          renderModalBody();
          emit({ authenticated: true, user: data.user, reason: "login" });
          return;
        }

        setStatus(ta("creating"), "info");
        const data = await jsonRequest("/auth/signup", {
          email: emailValue,
          password: passwordValue,
          full_name: nameValue,
          company_name: companyValue,
          country: countryValue,
        });
        setGlobalNotice(data.message || ta("account_created"), "warn");
        writeView("login");
        renderModalBody();
      } catch (error) {
        const mapped = mapErrorMessage(error?.message || error);
        setStatus(mapped.text, mapped.tone);
      }
    }

    body.querySelector("#btnAuthPrimary")?.addEventListener("click", handlePrimaryAction);
    body.querySelector("#btnAuthForgotPassword")?.addEventListener("click", async () => {
      const emailValue = String(email?.value || "").trim();
      if (!emailValue) {
        setStatus(ta("reset_email_first"), "warn");
        email?.focus();
        return;
      }
      try {
        setStatus(ta("reset_preparing"), "info");
        await jsonRequest("/auth/password-reset/request", { email: emailValue });
        setStatus(ta("reset_sent"), "info");
      } catch (error) {
        const mapped = mapErrorMessage(error?.message || error);
        setStatus(mapped.text, mapped.tone);
      }
    });
    [email, password, passwordConfirm, name, company, country, countryOther].forEach((field) => {
      field?.addEventListener("keydown", async (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        await handlePrimaryAction();
      });
    });
  }

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function patchedFetch(input, init) {
    const req = init || {};
    const url = typeof input === "string" ? input : (input && input.url) || "";
    if (isSessionIdleExpired()) {
      expireSessionForInactivity();
    }
    const headers = new Headers(req.headers || (input instanceof Request ? input.headers : undefined) || {});
    if (readUser() && sameOrigin(url)) {
      touchSessionActivity();
    }
    const response = await nativeFetch(input, { ...req, headers, credentials: "same-origin" });
    if (response.status === 401 && sameOrigin(url) && !String(url).startsWith("/auth/")) {
      try {
        if (!refreshPromise) {
          refreshPromise = nativeFetch("/auth/refresh", {
            method: "POST",
            credentials: "same-origin",
          });
        }
        const refreshResponse = await refreshPromise;
        refreshPromise = null;
        if (refreshResponse.ok) {
          const refreshed = await nativeFetch("/auth/me", { credentials: "same-origin" });
          if (refreshed.ok) {
            const user = await refreshed.json();
            writeSession("", user);
            const retry = await nativeFetch(input, { ...req, headers, credentials: "same-origin" });
            if (retry.status !== 401) {
              return retry;
            }
          }
        }
      } catch (_e) {
        refreshPromise = null;
      }
      clearSession();
      setGlobalNotice(ta("session_expired"), "warn");
      renderAuthMount();
      renderModalBody();
      emit({ authenticated: false, user: null, reason: "expired" });
    }
    return response;
  };

  async function jsonRequest(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    let data = null;
    try { data = await res.json(); } catch (_e) {}
    if (!res.ok) {
      const msg = extractErrorText(data) || res.statusText || "Request failed";
      throw new Error(String(msg));
    }
    return data;
  }

  async function bootstrapUser() {
    ensureModal();
    try {
      const cfg = await fetch("/auth/config", { credentials: "same-origin" });
      if (cfg.ok) authConfig = { ...authConfig, ...(await cfg.json()) };
    } catch (_e) {}
    if (isSessionIdleExpired()) {
      expireSessionForInactivity();
      return;
    }
    try {
      const res = await fetch("/auth/me", { credentials: "same-origin" });
      if (!res.ok) throw new Error("Session expired");
      const user = await res.json();
      writeSession("", user);
      clearGlobalNotice();
      renderAuthMount();
      renderModalBody();
      emit({ authenticated: true, user, reason: "init" });
    } catch (_e) {
      clearSession();
      setGlobalNotice(ta("previous_invalid"), "warn");
      renderAuthMount();
      renderModalBody();
      emit({ authenticated: false, user: null, reason: "expired" });
    }
  }

  window.ProductFinderAuth = {
    hasSession() {
      return !!readUser();
    },
    getToken() {
      return "";
    },
    getUser() {
      return readUser();
    },
    onChange(fn) {
      if (typeof fn === "function") listeners.add(fn);
      return () => listeners.delete(fn);
    },
    async refresh() {
      await bootstrapUser();
    },
    open(view) {
      openModal(view);
    },
  };

  ["pointerdown", "keydown", "mousemove", "scroll", "focus"].forEach((eventName) => {
    window.addEventListener(eventName, () => {
      if (readUser()) touchSessionActivity();
    }, { passive: true });
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrapUser, { once: true });
  } else {
    bootstrapUser();
  }
  document.addEventListener("productfinder:language-changed", () => {
    renderAuthMount();
    renderModalBody();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === UI_LANG_KEY) {
      renderAuthMount();
      renderModalBody();
    }
  });
})();
