export type OrreryMode = "workbench" | "immersive";
export type OrreryBackground = "plain" | "mineral" | "archive" | "ink" | "iris" | "obsidian" | "bookcase" | "modern";
export type OrreryTheme = "moss" | "iris" | "obsidian" | "bookcase" | "modern";
export type OrreryMotion = "full" | "reduced" | "still";
export type OrreryDepth = "deep" | "balanced" | "flat";
export type OrreryRenderQuality = "auto" | "high" | "efficient";

export interface OrreryExperience {
  theme: OrreryTheme;
  motion: OrreryMotion;
  depth: OrreryDepth;
  quality: OrreryRenderQuality;
}

export function normalizeOrreryMode(value: unknown, narrow = false): OrreryMode {
  return !narrow && value === "immersive" ? "immersive" : "workbench";
}

export function normalizeOrreryBackground(value: unknown): OrreryBackground {
  return ["plain", "mineral", "archive", "ink", "iris", "obsidian", "bookcase", "modern"].includes(String(value))
    ? value as OrreryBackground
    : "mineral";
}

export function normalizeInstrumentVisibility(value: unknown): boolean {
  return value !== "hidden";
}

export function normalizeOrreryTheme(value: unknown): OrreryTheme {
  return ["moss", "iris", "obsidian", "bookcase", "modern"].includes(String(value))
    ? value as OrreryTheme
    : "moss";
}

export function normalizeOrreryMotion(value: unknown): OrreryMotion {
  return ["full", "reduced", "still"].includes(String(value)) ? value as OrreryMotion : "full";
}

export function normalizeOrreryDepth(value: unknown): OrreryDepth {
  return ["deep", "balanced", "flat"].includes(String(value)) ? value as OrreryDepth : "balanced";
}

export function normalizeOrreryRenderQuality(value: unknown): OrreryRenderQuality {
  return ["auto", "high", "efficient"].includes(String(value)) ? value as OrreryRenderQuality : "auto";
}

export function readOrreryExperience(): OrreryExperience {
  return {
    theme: normalizeOrreryTheme(window.localStorage.getItem("arcvellum.visualTheme")),
    motion: normalizeOrreryMotion(window.localStorage.getItem("arcvellum.orreryMotion")),
    depth: normalizeOrreryDepth(window.localStorage.getItem("arcvellum.orreryDepth")),
    quality: normalizeOrreryRenderQuality(window.localStorage.getItem("arcvellum.orreryQuality")),
  };
}

export function applyOrreryExperience(experience: Partial<OrreryExperience>): OrreryExperience {
  const next = { ...readOrreryExperience(), ...experience };
  window.localStorage.setItem("arcvellum.visualTheme", next.theme);
  window.localStorage.setItem("arcvellum.orreryMotion", next.motion);
  window.localStorage.setItem("arcvellum.orreryDepth", next.depth);
  window.localStorage.setItem("arcvellum.orreryQuality", next.quality);
  document.documentElement.dataset.arcvellumTheme = next.theme;
  document.documentElement.dataset.arcvellumMotion = next.motion;
  document.documentElement.dataset.arcvellumDepth = next.depth;
  document.documentElement.dataset.arcvellumQuality = next.quality;
  window.dispatchEvent(new CustomEvent("arcvellum:orrery-experience", { detail: next }));
  return next;
}

export function backgroundForTheme(theme: OrreryTheme): OrreryBackground {
  const backgrounds: Record<OrreryTheme, OrreryBackground> = {
    moss: "mineral",
    iris: "iris",
    obsidian: "obsidian",
    bookcase: "bookcase",
    modern: "modern",
  };
  return backgrounds[theme];
}
