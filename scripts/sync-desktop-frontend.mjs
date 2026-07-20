import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, "src/literary_engineering_studio/frontend/dist");
const target = resolve(root, "desktop/dist");

mkdirSync(target, { recursive: true });
rmSync(resolve(target, "ui"), { recursive: true, force: true });
mkdirSync(resolve(target, "ui"), { recursive: true });
cpSync(resolve(source, "assets"), resolve(target, "ui/assets"), { recursive: true });
writeFileSync(resolve(target, "index.html"), readFileSync(resolve(source, "index.html")));
