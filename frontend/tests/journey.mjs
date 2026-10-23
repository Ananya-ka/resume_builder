import { chromium } from "playwright";
import assert from "node:assert/strict";
const browser = await chromium.launch({
  channel: process.env.BROWSER_CHANNEL || "chrome",
  headless: true,
});
try {
  const page = await browser.newPage();
  page.on("pageerror", error => console.error("Browser error:", error.message));
  const bullet = {
    original_id: 7,
    original_bullet: "Built Python APIs.",
    optimized_bullet: "Developed Python APIs.",
    company: "Acme",
    role: "Engineer",
    section: "Experience",
    reason_for_change: "Clarifies contribution.",
    source_refs: ["resume:1:bullet:7"],
    evidence_context: "Built Python APIs.",
    included: true,
    review_state: "pending",
  };
  const session = {
    id: 1,
    job_id: 1,
    resume_ids: [1],
    status: "reviewing",
    questions: [],
    evidence: [],
    profile: { name: "Sam", skills: ["Python"], education: [], source_map: {} },
    conflicts: [
      {
        id: "dates",
        field: "Employment dates",
        kind: "profile",
        options: [{ value: "2020–2024", sources: ["resume:1"] }],
      },
    ],
  };
  const actions = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data = [];
    if (path.endsWith("/resumes"))
      data = [
        {
          id: 1,
          name: "sam-resume.pdf",
          parsed_raw: {
            parsing_status: "ready",
            raw_source_text: "Sam\nBuilt Python APIs.",
          },
          bullets: [],
        },
      ];
    if (path.endsWith("/evidence-drafts"))
      data = [
        {
          id: 1,
          session_id: 1,
          status: "complete",
          stale_evidence_ids: [],
          submitted: false,
        },
      ];
    if (path.endsWith("/discovery/1")) data = session;
    if (path.endsWith("/resolve")) {
      assert.equal(route.request().postDataJSON().choice, "2020–2024");
      session.conflicts = [];
      session.status = "ready";
      data = session;
    }
    if (path.endsWith("/optimizations/1"))
      data = { id: 1, optimized_content: [bullet] };
    if (path.endsWith("/review")) {
      const request = route.request().postDataJSON();
      assert.equal(request.expected_text, bullet.optimized_bullet);
      actions.push(request.action);
      if (request.action === "accept") bullet.review_state = "accepted";
      if (request.action === "edit") {
        bullet.optimized_bullet = request.text;
        bullet.review_state = "accepted";
      }
      if (request.action === "revert") {
        bullet.optimized_bullet = bullet.original_bullet;
        bullet.review_state = "reverted";
      }
      if (request.action === "exclude") bullet.included = false;
      if (request.action === "include") bullet.included = true;
      data = { id: 1, optimized_content: [bullet] };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
  await page.goto(process.env.BASE_URL || "http://localhost:3002");
  await page.getByText("Demo workspace", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Try sample resumes" }).click();
  await page.getByRole("button", { name: "Review combined profile" }).click();
  await page
    .getByRole("button", { name: "Open server workspace", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Resume session", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Combined candidate profile" })
    .waitFor();
  await page.getByRole("button", { name: "Confirm this version" }).click();
  await page.getByRole("button", { name: "Create tailored draft" }).waitFor();
  await page.getByRole("button", { name: "Review claims" }).click();
  await page.getByText("Supporting evidence", { exact: true }).click();
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await page.getByText("accepted", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Edit wording", exact: true }).click();
  await page
    .getByLabel("Proposed wording", { exact: true })
    .fill("Built Python APIs for internal tools.");
  await page.getByRole("button", { name: "Verify and save edit" }).click();
  await page.getByText("Built Python APIs for internal tools.", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Revert to source" }).click();
  await page.getByRole("button", { name: "Omit", exact: true }).click();
  await page.getByRole("button", { name: "Include", exact: true }).click();
  await page.getByText("reverted", { exact: true }).waitFor();
  assert.deepEqual(actions, ["accept", "edit", "revert", "exclude", "include"]);
  console.log(
    "Demo, merged profile, conflict resolution, and claim review passed.",
  );
} finally {
  await browser.close();
}
