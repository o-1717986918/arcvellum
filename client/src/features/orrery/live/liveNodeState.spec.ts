import { describe, expect, it } from "vitest";
import { resolveLiveNodeIds } from "./liveNodeState";
import type { CreativeLiveSnapshot } from "@/features/creative-live/types";
import type { SpatialNarrativeNode } from "@/types/spatial";

describe("Orrery live node state", () => {
  it("binds an active scene and its owning chapter without inventing project facts", () => {
    const result = resolveLiveNodeIds({ status: "active", active_task: { task_id: "scene_0003-prose-agent-task" }, artifacts: [{ path: "drafts/scenes/scene_0003.md" }] } as unknown as CreativeLiveSnapshot, [
      node("chapter:chapter_0001", "chapter", "chapter_0001", ""),
      node("scene:scene_0003", "scene", "scene_0003", "chapter_0001"),
      node("scene:scene_0004", "scene", "scene_0004", "chapter_0001"),
    ]);
    expect([...result]).toEqual(["scene:scene_0003", "chapter:chapter_0001"]);
  });
});

function node(nodeId: string, type: string, sourceId: string, chapterId: string): SpatialNarrativeNode {
  return { node_id: nodeId, type, source_id: sourceId, metrics: { chapter_id: chapterId }, parent_id: null, importance: 1 } as unknown as SpatialNarrativeNode;
}
