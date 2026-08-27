import { describe, expect, it } from "vitest";
import {
  normalizeInstrumentVisibility,
  normalizeOrreryBackground,
  normalizeOrreryDepth,
  normalizeOrreryMode,
  normalizeOrreryMotion,
  normalizeOrreryRenderQuality,
  normalizeOrreryTheme,
  resolveOrreryMotion,
} from "./orreryPreferences";

describe("orrery preferences", () => {
  it("accepts known modes and backgrounds", () => {
    expect(normalizeOrreryMode("immersive")).toBe("immersive");
    expect(normalizeOrreryBackground("mineral")).toBe("mineral");
    expect(normalizeOrreryTheme("moss")).toBe("moss");
  });

  it("falls back safely for narrow screens and invalid values", () => {
    expect(normalizeOrreryMode("immersive", true)).toBe("workbench");
    expect(normalizeOrreryMode("broken")).toBe("workbench");
    expect(normalizeOrreryBackground("broken")).toBe("mineral");
    expect(normalizeOrreryTheme("broken")).toBe("moss");
    expect(normalizeOrreryBackground("ink")).toBe("mineral");
    expect(normalizeOrreryTheme("iris")).toBe("moss");
  });

  it("keeps instruments visible unless explicitly hidden", () => {
    expect(normalizeInstrumentVisibility(null)).toBe(true);
    expect(normalizeInstrumentVisibility("hidden")).toBe(false);
  });

  it("normalizes visual comfort and quality preferences", () => {
    expect(normalizeOrreryMotion("still")).toBe("still");
    expect(normalizeOrreryMotion("unknown")).toBe("system");
    expect(resolveOrreryMotion("system", true)).toBe("reduced");
    expect(resolveOrreryMotion("full", true)).toBe("full");
    expect(normalizeOrreryDepth("flat")).toBe("flat");
    expect(normalizeOrreryDepth("unknown")).toBe("balanced");
    expect(normalizeOrreryRenderQuality("efficient")).toBe("efficient");
    expect(normalizeOrreryRenderQuality("unknown")).toBe("auto");
  });
});
