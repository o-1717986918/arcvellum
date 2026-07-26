import { describe, expect, it } from "vitest";
import { narrativeEntityId, nodeForReaderUnit, readerUnitForNode } from "@/features/orrery/model/readerLink";
import type { ReaderUnitSummary } from "@/types/api";
import type { SpatialNarrativeNode } from "@/types/spatial";

function sceneNode(sourceId = "scenes/scene_0002.yaml"): SpatialNarrativeNode {
  return {
    node_id: "scene:scene_0002",
    type: "scene",
    label: "第二场",
    subtitle: "",
    status: "formal",
    source_type: "scene",
    source_id: sourceId,
    navigate: "",
    metrics: { chapter_id: "chapter_0001" },
    order: 2,
    parent_id: "chapter:chapter_0001",
    cluster_id: "chapter:chapter_0001",
    time_band: 2,
    completion_state: "completed",
    importance: 0.8,
    detail_level: "near",
    world_hint: { surface: "main", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: "/node",
  };
}

const unit: ReaderUnitSummary = {
  unit_id: "chapter_0001.scene_0002",
  volume_id: "volume_0001",
  chapter_id: "chapter_0001",
  scene_id: "scene_0002",
  order: 2,
  title: "第二场",
  status: "promoted",
  source_kind: "scene",
  source_revision: "r1",
  content_hash: "hash",
  chinese_content_chars: 1000,
  machine_nonspace_chars: 1100,
  coverage: [],
  body_endpoint: "/reader/unit",
};

describe("Orrery reader links", () => {
  it("normalizes path-shaped scene sources to canonical work IDs", () => {
    expect(narrativeEntityId(sceneNode(), "scene")).toBe("scene_0002");
  });

  it("links a formal scene node to its exact promoted reader unit", () => {
    expect(readerUnitForNode(sceneNode(), [unit])?.unit_id).toBe(unit.unit_id);
  });

  it("links the active reader unit back to the exact scene node", () => {
    expect(nodeForReaderUnit([sceneNode()], unit)?.node_id).toBe("scene:scene_0002");
  });
});
