const fs = require("node:fs");
const path = require("node:path");
const { defineConfig } = require("@playwright/test");

const repositoryRoot = path.resolve(__dirname, "..");
const visualRoot = path.join(repositoryRoot, "build", "orrery-visual");
const repositoryPythonPath = [
  path.join(repositoryRoot, "src"),
  process.env.PYTHONPATH,
].filter(Boolean).join(path.delimiter);
const browserCandidates = [
  process.env.PLAYWRIGHT_EXECUTABLE_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);
const browserExecutable = browserCandidates.find((candidate) => fs.existsSync(candidate));
const apiPort = Number(process.env.ARCVELLUM_VISUAL_API_PORT || 8791);
const clientPort = Number(process.env.ARCVELLUM_VISUAL_CLIENT_PORT || 5173);

module.exports = defineConfig({
  testDir: path.join(repositoryRoot, "client", "e2e"),
  outputDir: path.join(visualRoot, "results"),
  fullyParallel: false,
  workers: 1,
  timeout: 600_000,
  expect: { timeout: 15_000 },
  reporter: [["line"], ["html", { outputFolder: path.join(visualRoot, "report"), open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${clientPort}/ui/`,
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
      command: `python -m literary_engineering_studio serve --port ${apiPort}`,
      cwd: repositoryRoot,
      url: `http://127.0.0.1:${apiPort}/application/bootstrap`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        ...process.env,
        LES_DATA_ROOT: path.join(visualRoot, "data"),
        // A developer may have another ArcVellum checkout installed in editable
        // mode. Visual acceptance must always exercise this exact worktree.
        PYTHONPATH: repositoryPythonPath,
        ARCVELLUM_API_ORIGIN: `http://127.0.0.1:${apiPort}`,
        ARCVELLUM_CLIENT_PORT: String(clientPort),
      },
    },
    {
      command: "npm run client:dev",
      cwd: repositoryRoot,
      url: `http://127.0.0.1:${clientPort}/ui/`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: { ...process.env, ARCVELLUM_API_ORIGIN: `http://127.0.0.1:${apiPort}`, ARCVELLUM_CLIENT_PORT: String(clientPort) },
    },
  ],
});
