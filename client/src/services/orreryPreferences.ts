export type OrreryMode = "workbench" | "immersive";
export type OrreryBackground = "mineral";
export type OrreryTheme = "moss";
export type OrreryMotion = "system" | "full" | "reduced" | "still";
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

export function normalizeOrreryBackground(_value: unknown): OrreryBackground {
  return "mineral";
}

export function normalizeInstrumentVisibility(value: unknown): boolean {
  return value !== "hidden";
}

export function normalizeOrreryTheme(_value: unknown): OrreryTheme {
  return "moss";
}

export function normalizeOrreryMotion(value: unknown): OrreryMotion {
  return ["system", "full", "reduced", "still"].includes(String(value)) ? value as OrreryMotion : "system";
}

export function resolveOrreryMotion(
  value: OrreryMotion,
  systemPrefersReduced: boolean,
): Exclude<OrreryMotion, "system"> {
  if (value === "system") return systemPrefersReduced ? "reduced" : "full";
  return value;
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
  const next: OrreryExperience = {
    ...readOrreryExperience(),
    ...experience,
    theme: "moss",
  };
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

export function resetOrreryColorIdentity(): void {
  window.localStorage.setItem("arcvellum.visualTheme", "moss");
  window.localStorage.setItem("arcvellum.orreryBackground", "mineral");
  document.documentElement.dataset.arcvellumTheme = "moss";
}
