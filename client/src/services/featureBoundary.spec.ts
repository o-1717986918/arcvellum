import { readFileSync, readdirSync } from "node:fs";
import { dirname, extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { paths as StudioApiPaths } from "@/types/generated/api-schema";

const sourceRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

function sourceFiles(root: string): string[] {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return [".ts", ".vue"].includes(extname(entry.name)) ? [path] : [];
  });
}

describe("frontend feature boundaries", () => {
  it("keeps generic HTTP transport out of Vue components", () => {
    const offenders = sourceFiles(sourceRoot)
      .filter((path) => extname(path) === ".vue")
      .filter((path) => readFileSync(path, "utf8").includes('from "@/services/api"'))
      .map((path) => relative(sourceRoot, path));
    expect(offenders).toEqual([]);
  });

  it("provides semantic clients for every M6 core feature", () => {
    const required = ["advisor", "delivery", "orrery", "projects", "quality", "settings", "workflow"];
    const missing = required.filter((name) => {
      const folder = join(sourceRoot, "features", name, "services");
      try {
        return !readdirSync(folder).some((file) => file.endsWith("Client.ts"));
      } catch {
        return true;
      }
    });
    expect(missing).toEqual([]);
  });

  it("compiles against the generated Studio OpenAPI path surface", () => {
    const required: Array<keyof StudioApiPaths> = [
      "/advisor/sessions",
      "/application/bootstrap",
      "/autopilot/status",
      "/narrative/projection/v4",
      "/project/delivery",
      "/projects",
      "/workflow/dashboard",
    ];
    expect(required).toHaveLength(7);
  });
});
