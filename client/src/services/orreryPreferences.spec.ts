import { describe, expect, it } from "vitest";
import { backgroundForTheme, normalizeInstrumentVisibility, normalizeOrreryBackground, normalizeOrreryMode, normalizeOrreryTheme } from "./orreryPreferences";

describe("orrery preferences", () => {
  it("accepts known modes and backgrounds", () => {
    expect(normalizeOrreryMode("immersive")).toBe("immersive");
    expect(normalizeOrreryBackground("ink")).toBe("ink");
    expect(normalizeOrreryTheme("iris")).toBe("iris");
    expect(normalizeOrreryTheme("bookcase")).toBe("bookcase");
    expect(backgroundForTheme("modern")).toBe("modern");
  });

  it("falls back safely for narrow screens and invalid values", () => {
    expect(normalizeOrreryMode("immersive", true)).toBe("workbench");
    expect(normalizeOrreryMode("broken")).toBe("workbench");
    expect(normalizeOrreryBackground("broken")).toBe("mineral");
    expect(normalizeOrreryTheme("broken")).toBe("moss");
  });

  it("keeps instruments visible unless explicitly hidden", () => {
    expect(normalizeInstrumentVisibility(null)).toBe(true);
    expect(normalizeInstrumentVisibility("hidden")).toBe(false);
  });
});
