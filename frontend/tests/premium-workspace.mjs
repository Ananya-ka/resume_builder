import { chromium } from "playwright";
import assert from "node:assert/strict";
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.setDefaultTimeout(15000);
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const go = async (name) => {
  console.log("Visiting", name);
  await page
    .getByRole("navigation", { name: "Workspace" })
    .getByRole("button", { name: new RegExp(`^${name}`) })
    .click();
  await page.getByRole("heading", { name: new RegExp(`^${name}`) }).waitFor();
};
try {
  await page.goto("http://localhost:3001");
  await page.getByRole("heading", { name: "Good morning, Alex." }).waitFor();
  await page.screenshot({
    path: "/tmp/careerproof-dashboard.png",
    fullPage: true,
  });
  await page.keyboard.press("Meta+k");
  await page.getByRole("dialog").waitFor();
  await page
    .getByRole("textbox", { name: "Search workspace", exact: true })
    .fill("Evidence");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Evidence Vault" })
    .click();
  await page.getByRole("textbox", { name: "Search evidence" }).fill("Redis");
  assert.equal(await page.locator(".cp-evidence-card").count(), 1);
  await page.locator(".cp-evidence-card").click();
  await page.getByRole("dialog").getByText("Claim history").waitFor();
  await page.keyboard.press("Escape");
  await go("Objection Engine");
  await page.locator(".cp-expand").first().click();
  await page.getByText("SUPPORTING SOURCE", { exact: true }).waitFor();
  await go("Gap Resolver");
  await page
    .locator("textarea")
    .first()
    .fill(
      "I selected Redis response caching and measured p95 latency with production monitoring.",
    );
  await page.getByRole("button", { name: "Save answer" }).first().click();
  await page.getByText("Answer saved", { exact: true }).waitFor();
  await go("Resume Studio");
  await page.getByRole("button", { name: "PDF view", exact: true }).click();
  await page.locator('iframe[title="Live resume PDF preview"]').waitFor();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PDF" }).click();
  const download = await downloadPromise;
  assert.match(download.suggestedFilename(), /\.pdf$/);
  await go("Interview Defense");
  await page.locator(".cp-flashcard").click();
  await page.getByText("THE EVIDENCE BEHIND YOUR CLAIM").waitFor();
  await page.getByRole("button", { name: "Next card", exact: true }).click();
  await go("Applications");
  await page
    .getByRole("combobox", { name: "Stage for Linear" })
    .selectOption("Interviewing");
  await page
    .getByRole("button", { name: "Add application", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Company", exact: true })
    .fill("Acme");
  await page
    .getByRole("textbox", { name: "Role", exact: true })
    .fill("Backend Engineer");
  await page.getByRole("button", { name: "Add opportunity" }).click();
  assert.equal(await page.locator(".cp-application").count(), 4);
  await page.reload();
  await go("Applications");
  assert.equal(
    await page.getByRole("combobox", { name: "Stage for Linear" }).inputValue(),
    "Interviewing",
  );
  assert.equal(await page.locator(".cp-application").count(), 4);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation", { name: "Workspace" })
    .getByRole("button", { name: "Dashboard", exact: true })
    .click();
  await page.getByRole("heading", { name: "Good morning, Alex." }).waitFor();
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await page.screenshot({
    path: "/tmp/careerproof-mobile.png",
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  console.log(
    "PASS: navigation, evidence, objections, saved answers, PDF export, flashcards, applications, persistence, and mobile layout",
  );
} finally {
  await browser.close();
}
