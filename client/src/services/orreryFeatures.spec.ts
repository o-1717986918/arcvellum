import { describe, expect, it } from "vitest";
import { normalizeOrreryEngine } from "./orreryFeatures";

describe("orrery engine preference", () => {
  it("always returns the spatial field and migrates older preferences", () => {
    expect(normalizeOrreryEngine(null)).toBe("spatial");
    expect(normalizeOrreryEngine("spatial")).toBe("spatial");
    expect(normalizeOrreryEngine("legacy")).toBe("spatial");
  });
});
