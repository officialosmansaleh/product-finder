(function () {
  const USER_KEY = "productFinderAuthUserV1";
  const AUTH_VIEW_KEY = "productFinderAuthViewV1";
  const LAST_ACTIVITY_KEY = "productFinderAuthLastActivityV1";
  const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
  const listeners = new Set();
  let authNotice = "";
  let authNoticeTone = "info";
  let refreshPromise = null;

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
    setGlobalNotice("Your session expired after inactivity. Please log in again.", "warn");
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
      return { text: "Email or password not recognized. Check both fields and try again.", tone: "error" };
    }
    if (lower.includes("account status is pending")) {
      return { text: "Your account request is waiting for admin approval.", tone: "warn" };
    }
    if (lower.includes("account status is rejected")) {
      return { text: "Your account was rejected. Contact an administrator if needed.", tone: "error" };
    }
    if (lower.includes("password must contain letters and numbers")) {
      return { text: "Use a stronger password with both letters and numbers.", tone: "error" };
    }
    if (lower.includes("email already registered")) {
      return { text: "This email is already registered. Try logging in instead.", tone: "warn" };
    }
    if (lower.includes("token expired") || lower.includes("session expired")) {
      return { text: "Your session expired. Please log in again.", tone: "warn" };
    }
    return { text: text || "Something went wrong. Please try again.", tone: "error" };
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
    if (role === "admin") return "Admin";
    if (role === "it") return "IT";
    if (role === "director") return "Director";
    if (role === "manager") return "Manager";
    return "User";
  }

  function countryOptions(selectedValue) {
    const api = window.ProductFinderCountries;
    if (api && typeof api.optionList === "function") {
      return api.optionList(selectedValue ? [selectedValue] : [], { includePlaceholder: true, placeholder: "Select country", includeOther: true });
    }
    const selected = String(selectedValue || "").trim();
    return `<option value=""${selected ? "" : ' selected="selected"'}>Select country</option>${selected ? `<option value="${escapeHtml(selected)}" selected="selected">${escapeHtml(selected)}</option>` : ""}`;
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
          <button id="btnAuthModalClose" class="authModalClose" type="button" aria-label="Close account panel">Close</button>
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
        <button id="btnAuthPanel" class="btn secondary compact" type="button">Panel</button>
        <button id="btnAuthAccount" class="authCompactTrigger" type="button" aria-label="Open account panel">
          <span class="authCompactBadge">${escapeHtml(userInitials(user))}</span>
          <span class="authCompactMeta">
            <span class="authCompactName">${escapeHtml(user.full_name || user.email || "User")}</span>
            <span class="authCompactRole">${escapeHtml(roleLabel(user))}</span>
          </span>
        </button>
      </div>
    `;
    mount.querySelector("#btnAuthAccount")?.addEventListener("click", () => openModal("account"));
    mount.querySelector("#btnAuthPanel")?.addEventListener("click", () => {
      window.location.href = "/frontend/admin.html";
    });
  }

  function renderLoggedOutMount() {
    const mount = document.getElementById("authMount");
    if (!mount) return;
    mount.innerHTML = `
      <div class="authTriggerGroup">
        <button id="btnAuthOpenLogin" class="btn secondary compact" type="button">Sign in</button>
        <button id="btnAuthOpenSignup" class="btn compact" type="button">Request access</button>
      </div>
    `;
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
            <div id="authModalTitle" class="authUserName">${escapeHtml(user.full_name || "User")}</div>
            <div class="authUserRole">
              <span class="authRolePill">${escapeHtml(roleLabel(user))}</span>
              <span>${escapeHtml(user.email || "")}</span>
            </div>
          </div>
        </div>
        <div class="authAccountInfo">
          <div class="authInfoRow"><span>Status</span><strong>${escapeHtml(user.status || "approved")}</strong></div>
          <div class="authInfoRow"><span>Country</span><strong>${escapeHtml(user.country || "Not set")}</strong></div>
          ${isAdmin ? '<div class="authInfoRow"><span>Admin tools</span><strong>Full access available</strong></div>' : ""}
          ${role === "manager" ? `<div class="authInfoRow"><span>Manager countries</span><strong>${escapeHtml(Array.isArray(user.assigned_countries) && user.assigned_countries.length ? user.assigned_countries.join(", ") : "None assigned")}</strong></div><div class="authInfoRow"><span>Manager tools</span><strong>Read-only country access</strong></div>` : ""}
        </div>
        <div class="authActions">
          ${canOpenPanel ? '<button id="btnAuthOpenAdmin" class="btn compact" type="button">Open panel</button>' : ""}
          <button id="btnAuthLogout" class="btn secondary compact" type="button">Logout</button>
        </div>
        ${renderStatusLine("Your account is active.", "info")}
      </div>
    `;
  }

  function renderAccessView(view) {
    const loginActive = view !== "signup";
    return `
      <div class="authBox authBoxExpanded">
        <div class="authHeader">
          <div>
            <div id="authModalTitle" class="authTitle">Workspace access</div>
            <div class="authSubtitle">Sign in to search, compare, quote, and collaborate in one workspace.</div>
          </div>
          <div class="authTabs" role="tablist" aria-label="Authentication tabs">
            <button id="btnAuthTabLogin" class="authTab ${loginActive ? "active" : ""}" type="button">Login</button>
            <button id="btnAuthTabSignup" class="authTab ${!loginActive ? "active" : ""}" type="button">Sign up</button>
          </div>
        </div>
        <div class="authFields">
          <input id="authEmail" type="email" placeholder="Work email" autocomplete="email" />
          <input id="authPassword" type="password" placeholder="Password" autocomplete="${loginActive ? "current-password" : "new-password"}" />
          <input id="authName" class="${loginActive ? "authHidden" : ""}" type="text" placeholder="Full name" autocomplete="name" />
          <input id="authCompany" class="${loginActive ? "authHidden" : ""}" type="text" placeholder="Company name" autocomplete="organization" />
          <select id="authCountry" class="${loginActive ? "authHidden" : ""}" autocomplete="country-name">
            ${countryOptions("")}
          </select>
          <input id="authCountryOther" class="authHidden" type="text" placeholder="Enter your country" autocomplete="country-name" />
        </div>
        ${loginActive ? "" : '<div class="authHelper">Password rules: at least 10 characters, with at least 1 letter and 1 number.</div>'}
        <div class="authActions">
          <button id="btnAuthPrimary" class="btn compact" type="button">${loginActive ? "Login" : "Request access"}</button>
          <div class="authHelper">${loginActive ? "Use your approved account to unlock search and filters." : "New access requests stay pending until an admin approves them."}</div>
        </div>
        ${loginActive ? '<div class="authActions"><button id="btnAuthForgotPassword" class="btn secondary compact" type="button">Forgot password?</button><div class="authHelper">We will send you a secure reset link if your account exists.</div></div>' : ""}
        ${renderStatusLine(loginActive ? "Use your approved account to continue." : "Create your request and wait for approval before logging in.", loginActive ? "info" : "warn")}
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
        setGlobalNotice("You have been logged out.", "info");
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
    country?.addEventListener("change", syncCountryField);
    syncCountryField();

    async function handlePrimaryAction() {
      const mode = readView();
      const emailValue = String(email?.value || "").trim();
      const passwordValue = String(password?.value || "");
      const nameValue = String(name?.value || "").trim();
      const companyValue = String(company?.value || "").trim();
      const countryValue = isOtherCountryValue(country?.value)
        ? String(countryOther?.value || "").trim()
        : String(country?.value || "").trim();

      if (!emailValue) {
        setStatus("Enter your email first.", "warn");
        email?.focus();
        return;
      }
      if (!passwordValue) {
        setStatus("Enter your password first.", "warn");
        password?.focus();
        return;
      }
      if (mode === "signup" && !nameValue) {
        setStatus("Add your full name so the admin can identify your request.", "warn");
        name?.focus();
        return;
      }
      if (mode === "signup" && !companyValue) {
        setStatus("Add your company name so we can prefill your quotes after login.", "warn");
        company?.focus();
        return;
      }
      if (mode === "signup" && !countryValue) {
        setStatus("Add your country so the admin can route your request correctly.", "warn");
        if (isOtherCountryValue(country?.value)) {
          countryOther?.focus();
        } else {
          country?.focus();
        }
        return;
      }

      try {
        if (mode === "login") {
          setStatus("Checking your credentials...", "info");
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

        setStatus("Creating your access request...", "info");
        const data = await jsonRequest("/auth/signup", {
          email: emailValue,
          password: passwordValue,
          full_name: nameValue,
          company_name: companyValue,
          country: countryValue,
        });
        setGlobalNotice(data.message || "Account request created. Wait for admin approval before logging in.", "warn");
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
        setStatus("Enter your email first so we can send the reset link.", "warn");
        email?.focus();
        return;
      }
      try {
        setStatus("Preparing your reset link...", "info");
        await jsonRequest("/auth/password-reset/request", { email: emailValue });
        setStatus("If the account exists, a reset link has been sent.", "info");
      } catch (error) {
        const mapped = mapErrorMessage(error?.message || error);
        setStatus(mapped.text, mapped.tone);
      }
    });
    [email, password, name, company, country, countryOther].forEach((field) => {
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
      setGlobalNotice("Your session expired. Please log in again.", "warn");
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
      setGlobalNotice("Your previous session is no longer valid. Please log in again.", "warn");
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
})();
