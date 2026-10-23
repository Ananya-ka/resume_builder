import assert from "node:assert/strict";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  await page.goto("http://localhost:3001");
  await page.getByRole("heading", { name: "Good morning, Alex." }).waitFor();
  const results = await new AxeBuilder({ page })
    .include(".cp-workspace")
    .analyze();
  console.log(
    JSON.stringify(
      results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => n.target),
      })),
      null,
      2,
    ),
  );
  assert.equal(results.violations.length, 0);
} finally {
  await browser.close();
}
