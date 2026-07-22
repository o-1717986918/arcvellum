import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const frontend = resolve(root, "src/literary_engineering_studio/frontend/dist");
const desktop = resolve(root, "desktop/dist");
const frontendAssets = resolve(frontend, "assets");
const desktopAssets = resolve(desktop, "ui/assets");

function fail(message) {
  throw new Error(`v0.9 build verification failed: ${message}`);
}

function assetNames(directory) {
  if (!existsSync(directory)) fail(`missing asset directory: ${directory}`);
  return readdirSync(directory).filter((name) => statSync(resolve(directory, name)).isFile()).sort();
}

if (!existsSync(resolve(frontend, "index.html"))) fail("frontend index.html is missing");
if (!existsSync(resolve(desktop, "index.html"))) fail("desktop index.html is missing");

const sourceIndex = readFileSync(resolve(frontend, "index.html"), "utf8");
const desktopIndex = readFileSync(resolve(desktop, "index.html"), "utf8");
if (sourceIndex !== desktopIndex) fail("desktop index.html is not synchronized with the frontend build");

const sourceAssets = assetNames(frontendAssets);
const copiedAssets = assetNames(desktopAssets);
const missing = sourceAssets.filter((name) => !copiedAssets.includes(name));
if (missing.length) fail(`desktop asset copy is incomplete: ${missing.join(", ")}`);
if (sourceAssets.some((name) => name.endsWith(".png"))) fail("PNG assets remain in the production frontend build");

const webpAssets = sourceAssets.filter((name) => name.endsWith(".webp"));
if (webpAssets.length < 8) fail(`expected at least 8 WebP environment assets, found ${webpAssets.length}`);
const orreryChunks = sourceAssets.filter((name) => name.startsWith("OrreryWorkbench-") && name.endsWith(".js"));
if (orreryChunks.length !== 1) fail(`expected one lazy OrreryWorkbench chunk, found ${orreryChunks.length}`);

console.log(JSON.stringify({
  ok: true,
  frontend_assets: sourceAssets.length,
  webp_assets: webpAssets.length,
  orrery_chunk: orreryChunks[0],
  desktop_sync: true,
}, null, 2));
