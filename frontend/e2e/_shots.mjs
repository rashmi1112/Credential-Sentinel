import { chromium } from "@playwright/test";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

await page.goto("http://localhost:3000");
await page.getByTestId("start-sweep").click();
await page.getByTestId("approval-gate").waitFor({ state: "visible", timeout: 20000 });
await page.waitForTimeout(700);
await page.screenshot({ path: "/tmp/i_gate_wide.png" }); // viewport only (above the fold)

await browser.close();
console.log("shot saved");
