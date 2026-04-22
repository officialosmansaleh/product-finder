const { expect } = require("@playwright/test");

async function closeAuthModalIfVisible(page) {
  const authModal = page.locator("#authModal");
  if (!(await authModal.count())) return;
  if (!await authModal.isVisible().catch(() => false)) return;
  await page.locator("#btnAuthModalClose").click().catch(() => {});
  await expect(authModal).not.toBeVisible().catch(() => {});
}

function buildUniqueUser() {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
  return {
    email: `e2e.${suffix}@test.local`,
    password: "StrongPass123",
    fullName: `E2E User ${suffix}`,
    company: `E2E Company ${suffix}`,
    project: `Project ${suffix}`,
  };
}

async function acceptDialogs(page) {
  page.on("dialog", async (dialog) => {
    try {
      await dialog.accept();
    } catch (_e) {}
  });
}

async function openSignup(page) {
  await page.goto("/frontend/");
  await page.locator("#btnAuthOpenSignup").click();
  await expect(page.locator("#authModal")).toBeVisible();
}

async function signup(page, user) {
  await openSignup(page);
  await page.locator("#authEmail").fill(user.email);
  await page.locator("#authPassword").fill(user.password);
  await page.locator("#authName").fill(user.fullName);
  await page.locator("#authCompany").fill(user.company);
  await page.locator("#btnAuthPrimary").click();
  await expect(page.locator("#authStatus")).toContainText(/pending/i);
}

async function login(page, { email, password, goto = "/frontend/" }) {
  await page.goto(goto);
  await page.waitForTimeout(500);
  const existingUser = await page.evaluate(() => {
    try {
      const raw = sessionStorage.getItem("productFinderAuthUserV1");
      return raw ? JSON.parse(raw) : null;
    } catch (_e) {
      return null;
    }
  });
  if (existingUser && String(existingUser.email || "").toLowerCase() !== String(email || "").toLowerCase()) {
    await page.evaluate(async () => {
      try {
        await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
      } catch (_e) {}
      try {
        sessionStorage.removeItem("productFinderAuthUserV1");
        sessionStorage.removeItem("productFinderAuthLastActivityV1");
        localStorage.removeItem("productFinderAuthUserV1");
        localStorage.removeItem("productFinderAuthLastActivityV1");
      } catch (_e) {}
    });
    await page.reload();
  }
  const signInButton = page.locator("#btnAuthOpenLogin");
  const authModal = page.locator("#authModal");
  if ((await authModal.count()) && await authModal.isVisible().catch(() => false)) {
    // Reuse the already-open auth dialog instead of clicking through the backdrop again.
  } else {
    await signInButton.click();
  }
  await expect(page.locator("#authEmail")).toBeVisible();
  await page.locator("#authEmail").fill(email);
  await page.locator("#authPassword").fill(password);
  await page.locator("#btnAuthPrimary").click();
  await expect(page.locator("#btnAuthAccount")).toBeVisible();
  await closeAuthModalIfVisible(page);
}

async function logout(page) {
  await page.evaluate(async () => {
    try {
      await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
    } catch (_e) {}
    try {
      sessionStorage.removeItem("productFinderAuthUserV1");
      sessionStorage.removeItem("productFinderAuthLastActivityV1");
      localStorage.removeItem("productFinderAuthUserV1");
      localStorage.removeItem("productFinderAuthLastActivityV1");
    } catch (_e) {}
  });
  await page.goto("/frontend/");
  await expect(page.locator("#btnAuthOpenLogin")).toBeVisible();
}

async function approvePendingUser(page, email) {
  const pendingData = await page.evaluate(async () => {
    const res = await fetch("/admin/users/pending", { credentials: "same-origin" });
    let data = null;
    try {
      data = await res.json();
    } catch (_e) {}
    return { ok: res.ok, status: res.status, data };
  });
  expect(pendingData.ok, `pending request failed with status ${pendingData.status}`).toBeTruthy();
  const pendingItems = Array.isArray(pendingData.data?.items) ? pendingData.data.items : [];
  const target = pendingItems.find((item) => String(item?.email || "").toLowerCase() === String(email || "").toLowerCase());
  expect(target).toBeTruthy();

  const approveRes = await page.evaluate(async (userId) => {
    const res = await fetch(`/admin/users/${userId}/approve`, {
      method: "POST",
      credentials: "same-origin",
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_e) {}
    return { ok: res.ok, status: res.status, data };
  }, target.id);
  expect(approveRes.ok, `approve request failed with status ${approveRes.status}`).toBeTruthy();

  await page.goto("/frontend/admin.html");
  await expect(page.locator("#adminNotice")).not.toContainText(/only to approved admin users/i);
}

async function runSearch(page, query) {
  await page.goto("/frontend/");
  await page.locator("#q").fill(query);
  await page.locator("#btnRun").click();
  await expect(page.locator("#btnTabExact")).toContainText(/Exact/i);
  await page.waitForFunction(() => {
    const exactTab = document.querySelector("#btnTabExact");
    const exactHits = document.querySelectorAll("#exact .hit").length;
    const exactEmpty = document.querySelector("#exact .empty");
    if (!exactTab) return false;
    const label = String(exactTab.textContent || "");
    const hasResolvedCount = /\(\d+\)/.test(label);
    return hasResolvedCount && (exactHits > 0 || !!exactEmpty);
  });
}

async function addFirstExactResultToQuote(page, projectReference = "L1") {
  await closeAuthModalIfVisible(page);
  const firstCard = page.locator("#exact .hit").first();
  await expect(firstCard).toBeVisible();
  await firstCard.locator("[data-quote-toggle]").click();
  await expect(page.locator("#pfQuoteEntryModal")).toBeVisible();
  await page.locator("#pfQuoteEntryModalQty").fill("2");
  await page.locator("#pfQuoteEntryModalNotes").fill("E2E smoke");
  await page.locator("#pfQuoteEntryModalProjectRef").fill(projectReference);
  await page.locator("#pfQuoteEntryModalSave").click();
}

module.exports = {
  acceptDialogs,
  approvePendingUser,
  buildUniqueUser,
  closeAuthModalIfVisible,
  login,
  logout,
  runSearch,
  signup,
  addFirstExactResultToQuote,
};
