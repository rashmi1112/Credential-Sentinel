import { defineConfig, devices } from "@playwright/test";

/**
 * Boots both the FastAPI backend and the Next.js dev server, then drives the
 * real UI through the two approval gates. Run with: `npm run e2e`.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Backend: uses a throwaway DB so the test starts from a clean slate.
      command:
        ".venv/bin/python -m uvicorn app.main:app --port 8000 --log-level warning",
      cwd: "../backend",
      // Throwaway DB + force the deterministic plan fallback so the test is fast
      // and offline regardless of any configured Nebius key.
      env: { SENTINEL_DB: "data/e2e.db", NEBIUS_API_KEY: "", SENTINEL_TLS_MODE: "sim" },
      url: "http://localhost:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      cwd: ".",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
