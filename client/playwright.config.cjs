const fs = require("node:fs");
const path = require("node:path");
const { defineConfig } = require("@playwright/test");

const repositoryRoot = path.resolve(__dirname, "..");
const visualRoot = path.join(repositoryRoot, "build", "orrery-visual");
const browserCandidates = [
  process.env.PLAYWRIGHT_EXECUTABLE_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);
const browserExecutable = browserCandidates.find((candidate) => fs.existsSync(candidate));

module.exports = defineConfig({
  testDir: path.join(repositoryRoot, "client", "e2e"),
  outputDir: path.join(visualRoot, "results"),
  fullyParallel: false,
  workers: 1,
  timeout: 600_000,
  expect: { timeout: 15_000 },
  reporter: [["line"], ["html", { outputFolder: path.join(visualRoot, "report"), open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173/ui/",
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    launchOptions: browserExecutable ? { executablePath: browserExecutable } : undefined,
  },
  webServer: [
    {
      command: "python -m literary_engineering_studio serve --port 8791",
      cwd: repositoryRoot,
      url: "http://127.0.0.1:8791/application/bootstrap",
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        ...process.env,
        LES_DATA_ROOT: path.join(visualRoot, "data"),
      },
    },
    {
      command: "npm run client:dev",
      cwd: repositoryRoot,
      url: "http://127.0.0.1:5173/ui/",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
