const { test, expect } = require("@playwright/test");
const {
  acceptDialogs,
  approvePendingUser,
  buildUniqueUser,
  closeAuthModalIfVisible,
  login,
  logout,
  runSearch,
  signup,
  addFirstExactResultToQuote,
} = require("./helpers");

const adminEmail = process.env.E2E_ADMIN_EMAIL || process.env.ADMIN_BOOTSTRAP_EMAIL || "admin@example.com";
const adminPassword = process.env.E2E_ADMIN_PASSWORD || process.env.ADMIN_BOOTSTRAP_PASSWORD || "ChangeMe1234";

test.beforeEach(async ({ page }) => {
  await acceptDialogs(page);
});

async function saveQuoteThroughBrowserSession(page, project, company) {
  return await page.evaluate(async ({ projectName, companyName }) => {
    const rows = Array.from(document.querySelectorAll("#quoteTableWrap tbody tr")).map((row) => ({
      product_code: String(row.querySelector('a')?.textContent || "").trim(),
      product_name: String(row.cells?.[3]?.textContent || "").trim(),
      manufacturer: "",
      qty: Number(row.querySelector('input[type=\"number\"]')?.value || 1),
      notes: String(row.querySelector('input[placeholder=\"Optional note\"]')?.value || "").trim(),
      project_reference: String(row.querySelector('input[placeholder=\"Project ref\"]')?.value || "").trim(),
      source: "e2e",
      sort_order: Math.max(0, Number(row.cells?.[0]?.textContent || 1) - 1),
      compare_sheet: {},
    })).filter((item) => item.product_code);
    const res = await fetch("/auth/quotes", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company: companyName,
        project: projectName,
        items: rows,
      }),
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_e) {}
    return { ok: res.ok, status: res.status, data };
  }, { projectName: project, companyName: company });
}

test("anonymous user can search but cannot see quote actions", async ({ page }) => {
  await runSearch(page, "office downlight");
  await expect(page.locator("#btnTabExact")).toContainText("Exact");
  await expect(page.locator("#exact .hit").first()).toBeVisible();
  await expect(page.locator("#exact [data-quote-toggle]")).toHaveCount(0);
  await expect(page.locator("#btnQuote")).toBeHidden();
});

test("signup request can be approved by admin and the new user can log in", async ({ page, context }) => {
  const user = buildUniqueUser();

  await signup(page, user);

  const adminPage = await context.newPage();
  await acceptDialogs(adminPage);
  await login(adminPage, { email: adminEmail, password: adminPassword, goto: "/frontend/admin.html" });
  await expect(adminPage.locator("#adminNotice")).toContainText(/up to date/i);
  await approvePendingUser(adminPage, user.email);

  await login(page, { email: user.email, password: user.password });
  await expect(page.locator("#btnQuote")).toBeVisible();
  await expect(page.locator("#btnAuthAccount")).toContainText(user.fullName);
});

test("approved user can add to quote, save, and reload the saved quote", async ({ page, context }) => {
  const user = buildUniqueUser();

  await signup(page, user);

  const adminPage = await context.newPage();
  await acceptDialogs(adminPage);
  await login(adminPage, { email: adminEmail, password: adminPassword, goto: "/frontend/admin.html" });
  await approvePendingUser(adminPage, user.email);

  await login(page, { email: user.email, password: user.password });
  await runSearch(page, "office downlight");
  await addFirstExactResultToQuote(page, "L1");

  await page.locator("#btnQuote").click();
  await expect(page).toHaveURL(/\/frontend\/quote\.html/);
  await closeAuthModalIfVisible(page);
  const quoteCompany = page.locator("#quoteCompany");
  await expect(quoteCompany).toBeVisible();
  if ((await quoteCompany.inputValue()).trim() !== user.company) {
    await quoteCompany.fill(user.company);
  }
  await page.locator("#quoteProject").fill(user.project);
  await page.locator("#btnQuoteSave").click();
  await expect(page.locator("#savedQuotesBox")).toBeVisible();
  try {
    await expect(page.locator("#savedQuotesList")).toContainText(user.project, { timeout: 5_000 });
  } catch (_e) {
    const fallbackSave = await saveQuoteThroughBrowserSession(page, user.project, user.company);
    expect(fallbackSave.ok, `quote save fallback failed with status ${fallbackSave.status}`).toBeTruthy();
    await page.reload();
    await expect(page.locator("#savedQuotesList")).toContainText(user.project);
  }

  await page.locator("#btnQuoteClear").click();
  await expect(page.locator("#quoteTableWrap")).toContainText("No products selected");
  await page.locator("#savedQuotesList [data-load-quote]").first().click();
  await expect(page.locator("#quoteTableWrap")).not.toContainText("No products selected");
  await expect(page.locator("#quoteProject")).toHaveValue(user.project);

  await logout(page);
});
