import { describe, expect, it } from "vitest";
import { cameraPoseAt, cameraTransitionDuration } from "./cameraTransition";

describe("camera transition", () => {
  it("eases a fallback camera without overshooting", () => {
    const from = { x: 0, y: 20, scale: 0.5 };
    const to = { x: 100, y: -40, scale: 1.2 };
    expect(cameraPoseAt(from, to, 0)).toEqual(from);
    expect(cameraPoseAt(from, to, 1)).toEqual(to);
    const middle = cameraPoseAt(from, to, 0.5);
    expect(middle.x).toBeGreaterThan(50);
    expect(middle.x).toBeLessThanOrEqual(100);
    expect(middle.scale).toBeLessThanOrEqual(1.2);
  });

  it("honors full, reduced, and still motion contracts", () => {
    expect(cameraTransitionDuration("full", 680)).toBe(680);
    expect(cameraTransitionDuration("reduced", 680)).toBe(200);
    expect(cameraTransitionDuration("still", 680)).toBe(0);
  });
});
