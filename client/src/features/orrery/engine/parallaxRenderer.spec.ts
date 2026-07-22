import { describe, expect, it } from "vitest";
import { orientWorldPoint, parallaxViewFromDrag, scenePoint } from "@/features/orrery/engine/parallaxProjection";

describe("parallax camera orientation", () => {
  it("keeps the baseline oblique projection when the camera has not rotated", () => {
    expect(scenePoint({ x: 2, y: 3, z: 4 }, "deep")).toEqual({ x: 96368, y: 10968 });
  });

  it("changes the projected field under a bounded yaw and pitch", () => {
    const initial = scenePoint({ x: 8, y: 1, z: -3 }, "deep");
    const rotated = scenePoint({ x: 8, y: 1, z: -3 }, "deep", { yaw: 0.4, pitch: -0.18 });
    expect(rotated).not.toEqual(initial);
    expect(orientWorldPoint({ x: 1, y: 2, z: 3 }, { yaw: 4, pitch: -4 })).toEqual(orientWorldPoint({ x: 1, y: 2, z: 3 }, { yaw: 0.66, pitch: -0.34 }));
  });

  it("uses the same bounded middle-drag response for every renderer path", () => {
    expect(parallaxViewFromDrag({ yaw: 0, pitch: 0 }, 50, -25)).toEqual({ yaw: 0.26, pitch: 0.095 });
    expect(parallaxViewFromDrag({ yaw: 0.6, pitch: -0.3 }, 200, 200)).toEqual({ yaw: 0.66, pitch: -0.34 });
  });
});
