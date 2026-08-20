import { afterEach, describe, expect, it, vi } from "vitest";
import { advanceCameraAnimation } from "./cameraAnimation";
import { attachOrbitInteraction } from "./orbitInteraction";
import { cssColor, readStageExperience, rendererResolution } from "./renderModel";

afterEach(() => {
  delete document.documentElement.dataset.arcvellumMotion;
  delete document.documentElement.dataset.arcvellumDepth;
  delete document.documentElement.dataset.arcvellumQuality;
  vi.restoreAllMocks();
});

describe("parallax renderer modules", () => {
  it("advances the camera with the original quartic easing and closes at the target", () => {
    const animation = {
      from: { x: 0, y: 20, scale: 0.5 },
      to: { x: 100, y: 60, scale: 1.5 },
      elapsed: 0,
      duration: 100,
    };

    const middle = advanceCameraAnimation(animation, 50);
    const complete = advanceCameraAnimation(animation, 100);

    expect(middle.frame.x).toBeCloseTo(93.75);
    expect(middle.animation?.elapsed).toBe(50);
    expect(complete.frame).toEqual(animation.to);
    expect(complete.animation).toBeNull();
  });

  it("reads renderer preferences and colors without owning application state", () => {
    document.documentElement.dataset.arcvellumMotion = "reduced";
    document.documentElement.dataset.arcvellumDepth = "deep";
    document.documentElement.dataset.arcvellumQuality = "efficient";

    expect(readStageExperience()).toEqual({ motion: "reduced", depth: "deep", quality: "efficient" });
    expect(cssColor("#abc", 0)).toBe(0xaabbcc);
    expect(cssColor("rgb(17, 34, 51)", 0)).toBe(0x112233);
    expect(rendererResolution("efficient")).toBe(1);
  });

  it("removes every orbit listener when the renderer is disposed", () => {
    const canvas = document.createElement("canvas");
    const add = vi.spyOn(canvas, "addEventListener");
    const remove = vi.spyOn(canvas, "removeEventListener");
    const detach = attachOrbitInteraction(canvas, {
      currentView: () => ({ x: 0, y: 0, z: 0, w: 1 }),
      pivot: () => null,
      cancelAnimation: vi.fn(),
      updateView: vi.fn(),
    });

    detach();

    expect(add.mock.calls.map(([name]) => name)).toEqual([
      "pointerdown", "pointermove", "pointerup", "pointercancel", "auxclick",
    ]);
    expect(remove.mock.calls.map(([name]) => name)).toEqual([
      "pointerdown", "pointermove", "pointerup", "pointercancel", "auxclick",
    ]);
  });
});
