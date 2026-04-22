(function () {
  const USER_KEY = "productFinderAuthUserV1";
  const MODAL_ID = "pfQuoteEntryModal";

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function readSessionAuthToken() {
    return "";
  }

  function readSessionAuthUser() {
    try {
      const raw = sessionStorage.getItem(USER_KEY);
      if (raw) return JSON.parse(raw);
    } catch (_e) {}
    try { localStorage.removeItem(USER_KEY); } catch (_e) {}
    return null;
  }

  function getQuoteStorageOwner(user) {
    const u = user || readSessionAuthUser();
    if (!u) return "anonymous";
    const byId = String(u?.id || "").trim();
    if (byId) return `user:${byId}`;
    const byEmail = String(u?.email || "").trim().toLowerCase();
    return byEmail ? `email:${byEmail}` : "anonymous";
  }

  function getQuoteCartStorageKey(baseKey, user) {
    return `${String(baseKey || "productFinderQuoteCartV1")}:${getQuoteStorageOwner(user)}`;
  }

  function ensureQuoteEntryModal(options) {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    const title = esc(options?.title || "Add to quote");
    const confirmLabel = esc(options?.confirmLabel || "Add");
    const cancelLabel = esc(options?.cancelLabel || "Cancel");
    const fieldLabelStyle = "display:flex;flex-direction:column;gap:6px;font-size:12px;font-weight:700;color:#475569";
    const inputStyle = "width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:12px";
    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
      <div id="${MODAL_ID}" style="display:none;position:fixed;inset:0;align-items:center;justify-content:center;z-index:1000">
        <div data-quote-modal-close="1" style="position:absolute;inset:0;background:rgba(15,23,42,.45)"></div>
        <div style="position:relative;z-index:1;width:min(420px,calc(100vw - 24px));background:#fff;border-radius:16px;padding:16px;box-shadow:0 20px 50px rgba(15,23,42,.22)">
          <div id="${MODAL_ID}Title" style="font-weight:800;margin:0 0 10px 0;font-size:16px">${title}</div>
          <div style="display:grid;gap:10px">
            <label style="${fieldLabelStyle}">
              <span>Quantity</span>
              <input id="${MODAL_ID}Qty" type="number" min="1" step="1" placeholder="Quantity" style="${inputStyle}" />
            </label>
            <label style="${fieldLabelStyle}">
              <span>Notes</span>
              <input id="${MODAL_ID}Notes" type="text" placeholder="Comment" style="${inputStyle}" />
            </label>
            <label style="${fieldLabelStyle}">
              <span>Project reference</span>
              <input id="${MODAL_ID}ProjectRef" type="text" placeholder="L1" style="${inputStyle}" />
            </label>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px">
            <button id="${MODAL_ID}Cancel" class="btn secondary" type="button">${cancelLabel}</button>
            <button id="${MODAL_ID}Save" class="btn" type="button">${confirmLabel}</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(wrapper.firstElementChild);
    modal = document.getElementById(MODAL_ID);
    return modal;
  }

  async function promptQuoteEntry(existingRow, options) {
    const modal = ensureQuoteEntryModal(options);
    const qty = document.getElementById(`${MODAL_ID}Qty`);
    const notes = document.getElementById(`${MODAL_ID}Notes`);
    const projectRef = document.getElementById(`${MODAL_ID}ProjectRef`);
    const btnSave = document.getElementById(`${MODAL_ID}Save`);
    const btnCancel = document.getElementById(`${MODAL_ID}Cancel`);
    const title = document.getElementById(`${MODAL_ID}Title`);
    if (!modal || !qty || !notes || !projectRef || !btnSave || !btnCancel || !title) return null;

    title.textContent = String(options?.title || "Add to quote");
    btnSave.textContent = String(options?.confirmLabel || "Add");
    btnCancel.textContent = String(options?.cancelLabel || "Cancel");
    qty.value = String(Math.max(1, Math.round(Number(existingRow?.qty) || 1)));
    notes.value = String(existingRow?.notes || "");
    projectRef.value = String(existingRow?.project_reference || "");
    projectRef.placeholder = String(options?.projectReferencePlaceholder || "L1");
    modal.style.display = "flex";
    setTimeout(() => qty.focus(), 0);

    return await new Promise((resolve) => {
      let done = false;
      const finish = (value) => {
        if (done) return;
        done = true;
        modal.style.display = "none";
        btnSave.removeEventListener("click", onSave);
        btnCancel.removeEventListener("click", onCancel);
        modal.removeEventListener("click", onBackdrop);
        document.removeEventListener("keydown", onKeydown);
        resolve(value);
      };
      const onSave = () => finish({
        qty: Math.max(1, Math.round(Number(qty.value) || 1)),
        notes: String(notes.value || ""),
        project_reference: String(projectRef.value || ""),
      });
      const onCancel = () => finish(null);
      const onBackdrop = (event) => {
        const target = event.target;
        if (target instanceof Element && target.matches("[data-quote-modal-close='1']")) finish(null);
      };
      const onKeydown = (event) => {
        if (event.key === "Escape") finish(null);
        if (event.key === "Enter") {
          event.preventDefault();
          onSave();
        }
      };
      btnSave.addEventListener("click", onSave);
      btnCancel.addEventListener("click", onCancel);
      modal.addEventListener("click", onBackdrop);
      document.addEventListener("keydown", onKeydown);
    });
  }

  window.ProductFinderQuoteUtils = {
    readSessionAuthToken,
    readSessionAuthUser,
    getQuoteStorageOwner,
    getQuoteCartStorageKey,
    promptQuoteEntry,
  };
})();
