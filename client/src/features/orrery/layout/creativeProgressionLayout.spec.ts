import { describe, expect, it } from "vitest";
import { creativeProgressionPositions } from "./creativeProgressionLayout";

describe("creative progression safe-area layout", () => {
  it("keeps medium-width stage cards clear of the right progress instrument", () => {
    const positions = creativeProgressionPositions(6, 1050, 760, 280);
    expect(Math.min(...positions.map((point) => point.x))).toBeGreaterThanOrEqual(150);
    expect(Math.max(...positions.map((point) => point.x))).toBeLessThanOrEqual(812);
    expect(new Set(positions.map((point) => point.y)).size).toBeGreaterThan(1);
  });

  it("uses two compact columns in a phone-width stage", () => {
    const positions = creativeProgressionPositions(5, 390, 200, 260);
    expect(positions.map((point) => point.x)).toEqual([72, 318, 72, 318, 72]);
    expect(Math.max(...positions.map((point) => point.y))).toBeLessThan(180);
  });
});
