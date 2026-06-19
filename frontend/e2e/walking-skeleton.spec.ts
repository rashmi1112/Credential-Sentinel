import { expect, test } from "@playwright/test";

/**
 * The Phase 0 acceptance test, in a real browser: start a sweep, watch fake
 * events stream, see the reconciliation routing, approve/reject at both gates,
 * and watch it resume to completion.
 */
test("start a sweep, clear both gates, run completes", async ({ page }) => {
  // 1. Dashboard -> start a sweep -> land on the run detail page.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Credential Sentinel" })).toBeVisible();
  await page.getByTestId("start-sweep").click();
  await expect(page).toHaveURL(/\/runs\/[a-f0-9]+/);

  // 2. The activity feed streams events live (SSE).
  await expect(page.getByText("Activity feed")).toBeVisible();
  await expect(page.getByText(/Found 4 live credentials/)).toBeVisible();

  // 3. Reconciliation routing shows the differentiator: a DEFER and the owned tail.
  const deferRow = page.getByTestId("recon-row-tok-ci-7");
  await expect(deferRow).toHaveAttribute("data-routing", "DEFER");
  await expect(page.getByTestId("recon-row-tls-lb-01")).toHaveAttribute(
    "data-routing",
    "OWN_UNMANAGED",
  );
  await expect(page.getByTestId("recon-row-sa-key-vm3")).toHaveAttribute(
    "data-routing",
    "OWN_STALE",
  );

  // 4. Gate 1 (staging): Phase 2 enriches each item with urgency + a drafted plan.
  const gate1 = page.getByTestId("approval-gate");
  await expect(gate1).toBeVisible();
  await expect(gate1).toHaveAttribute("data-gate", "staging");
  const tlsItem = page.getByTestId("gate-item-tls-lb-01");
  await expect(tlsItem).toContainText("critical"); // expired cert → top urgency band
  await expect(tlsItem).toContainText("Rotation plan"); // a plan was drafted (Nebius or fallback)
  // Every credential must be explicitly decided (no default). Approve all three;
  // api-key-legacy (unhealthy) escalates during staging.
  await page.getByTestId("approve-tls-lb-01").click();
  await page.getByTestId("approve-sa-key-vm3").click();
  await page.getByTestId("approve-api-key-legacy").click();
  await page.getByTestId("submit-decisions").click();

  await expect(page.getByText("Staged tls-lb-01: staged_healthy")).toBeVisible();
  // api-key-legacy stages but is unhealthy → escalates instead of proceeding.
  await expect(page.getByText(/Escalated api-key-legacy/)).toBeVisible();

  // 5. Gate 2 (cutover): only the staged-healthy credentials qualify.
  const gate2 = page.getByTestId("approval-gate");
  await expect(gate2).toHaveAttribute("data-gate", "cutover");
  await expect(page.getByTestId("gate-item-tls-lb-01")).toBeVisible();
  await expect(page.getByTestId("gate-item-sa-key-vm3")).toBeVisible();
  await expect(page.getByTestId("gate-item-api-key-legacy")).toHaveCount(0);
  await page.getByTestId("approve-tls-lb-01").click();
  await page.getByTestId("approve-sa-key-vm3").click();
  await page.getByTestId("submit-decisions").click();

  // 6. Phase 3: delayed-revoke happy path AND auto-rollback on the unhealthy one.
  await expect(page.getByText("tls-lb-01 — revoke_old: ok")).toBeVisible(); // old revoked after verify
  await expect(page.getByText("sa-key-vm3 — verify: failed")).toBeVisible(); // post-cutover verify fails
  await expect(page.getByText("sa-key-vm3 — rollback: ok")).toBeVisible(); // auto-rollback, old retained
  await expect(page.getByTestId("run-complete")).toBeVisible();
  await expect(page.getByText("completed", { exact: true })).toBeVisible();

  // 7. Phase 4: the run report (Nebius/fallback) and coverage-drift panels render.
  await expect(page.getByTestId("report-panel")).toBeVisible();
  await expect(page.getByTestId("drift-panel")).toBeVisible();
});
