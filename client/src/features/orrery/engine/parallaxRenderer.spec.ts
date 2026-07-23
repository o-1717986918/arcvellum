import { describe, expect, it } from "vitest";
import {
  DEFAULT_PARALLAX_VIEW,
  IDENTITY_PARALLAX_VIEW,
  orientWorldPoint,
  parallaxViewFromDrag,
  scenePoint,
} from "@/features/orrery/engine/parallaxProjection";

describe("parallax camera orientation", () => {
  it("opens with a restrained oblique view while retaining a testable front view", () => {
    const point = { x: 2, y: 3, z: 4 };
    expect(scenePoint(point, "deep", IDENTITY_PARALLAX_VIEW)).toEqual({ x: 96368, y: 10968 });
    expect(scenePoint(point, "deep", DEFAULT_PARALLAX_VIEW)).not.toEqual(
      scenePoint(point, "deep", IDENTITY_PARALLAX_VIEW),
    );
  });

  it("preserves vector length under quaternion rotation", () => {
    const point = { x: 1, y: 2, z: 3 };
    const view = parallaxViewFromDrag(DEFAULT_PARALLAX_VIEW, 730, -510);
    const rotated = orientWorldPoint(point, view);
    expect(Math.hypot(rotated.x, rotated.y, rotated.z)).toBeCloseTo(Math.hypot(1, 2, 3), 10);
    expect(Math.hypot(view.x, view.y, view.z, view.w)).toBeCloseTo(1, 10);
  });

  it("does not clamp large middle-drag gestures", () => {
    const medium = parallaxViewFromDrag(IDENTITY_PARALLAX_VIEW, 200, 200);
    const large = parallaxViewFromDrag(IDENTITY_PARALLAX_VIEW, 900, 900);
    expect(large).not.toEqual(medium);
    expect(orientWorldPoint({ x: 3, y: -2, z: 5 }, large)).not.toEqual(
      orientWorldPoint({ x: 3, y: -2, z: 5 }, medium),
    );
  });

  it("passes smoothly through a full yaw without reversing the depth axis", () => {
    const point = { x: 4, y: 1, z: -2 };
    const almostFull = parallaxViewFromDrag(
      IDENTITY_PARALLAX_VIEW,
      (Math.PI * 2 - 0.01) / 0.0052,
      0,
    );
    const full = parallaxViewFromDrag(
      IDENTITY_PARALLAX_VIEW,
      (Math.PI * 2) / 0.0052,
      0,
    );
    const near = orientWorldPoint(point, almostFull);
    const returned = orientWorldPoint(point, full);
    expect(Math.hypot(near.x - returned.x, near.y - returned.y, near.z - returned.z)).toBeLessThan(0.06);
    expect(returned.x).toBeCloseTo(point.x, 8);
    expect(returned.z).toBeCloseTo(point.z, 8);
  });
});
