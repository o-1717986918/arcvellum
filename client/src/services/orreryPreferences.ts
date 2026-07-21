export type OrreryMode = "workbench" | "immersive";
export type OrreryBackground = "plain" | "mineral" | "archive" | "ink" | "iris" | "obsidian" | "bookcase" | "modern";
export type OrreryTheme = "moss" | "iris" | "obsidian" | "bookcase" | "modern";

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
