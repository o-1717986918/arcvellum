import { describe, expect, it } from "vitest";
import type { SpatialNarrativeNode } from "@/types/spatial";
import { ambientNodeOffset, hasAmbientNodeMotion } from "./ambientMotion";

function node(status: string): SpatialNarrativeNode {
  return {
    node_id: `scene-${status}`,
    type: "scene",
    label: status,
    status,
    completion_state: "planned",
    detail_level: "near",
    order: 1,
    importance: 0.8,
  } as SpatialNarrativeNode;
}

describe("orrery ambient motion", () => {
  it("keeps active narrative signals alive while a camera is stationary", () => {
    expect(hasAmbientNodeMotion([node("formal"), node("queued")])).toBe(true);
    expect(hasAmbientNodeMotion([node("formal"), node("completed")])).toBe(false);
  });

  it("moves only active statuses with a bounded offset", () => {
    const moving = ambientNodeOffset(node("current"), 1.4);
    const still = ambientNodeOffset(node("formal"), 1.4);
    expect(Math.hypot(moving.x, moving.y)).toBeGreaterThan(0);
    expect(Math.hypot(moving.x, moving.y)).toBeLessThan(4);
    expect(still).toEqual({ x: 0, y: 0 });
  });
});
