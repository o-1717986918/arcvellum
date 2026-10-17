// @vitest-environment node
import { Container, Graphics } from "pixi.js";
import { describe, expect, it, vi } from "vitest";
import type { SpatialNarrativeProjection } from "@/types/spatial";
import { RetainedScene } from "./retainedScene";
import { DEFAULT_PALETTE } from "./renderModel";
import { createSpatialLayoutCache } from "../layout/layoutCache";
import { createParallaxProjector, DEFAULT_PARALLAX_VIEW, parallaxViewFromDrag } from "./parallaxProjection";

describe("retained star field", () => {
  it("retains every Graphics object across orbit, theme and status changes", () => {
    const projection = { nodes: [{ node_id: "scene:1", type: "scene", order: 1, metrics: {}, importance: 0.5 }],
      edges: [], relation_profiles: [], level: "book", layout_seed: "seed", layout_hints: {}, spatial_grammar: "constellation" } as unknown as SpatialNarrativeProjection;
    const layers = { far: new Container(), mid: new Container(), near: new Container() };
    const scene = new RetainedScene(layers), layout = createSpatialLayoutCache()(projection);
    const experience = { motion: "full", depth: "balanced", quality: "auto" } as const;
    const project = createParallaxProjector("balanced", DEFAULT_PARALLAX_VIEW).project;
    scene.update(projection, layout, DEFAULT_PALETTE, experience, project);
    const children = Object.values(layers).flatMap((layer) => [...layer.children]);
    const clear = vi.spyOn(Graphics.prototype, "clear");
    scene.update({ ...projection, revision: "status" }, layout, DEFAULT_PALETTE, experience, project);
    expect(clear).not.toHaveBeenCalled();
    const rotated = createParallaxProjector("balanced", parallaxViewFromDrag(DEFAULT_PARALLAX_VIEW, 350, 190)).project;
    scene.update(projection, layout, DEFAULT_PALETTE, experience, rotated, true);
    expect(clear).toHaveBeenCalled();
    scene.update(projection, layout, { ...DEFAULT_PALETTE, core: 0xff0000 }, experience, rotated);
    expect(Object.values(layers).flatMap((layer) => layer.children)).toEqual(children);
    expect(children.every((child) => !child.destroyed)).toBe(true);
    clear.mockRestore();
    Object.values(layers).forEach((layer) => layer.destroy({ children: true }));
  });
});
