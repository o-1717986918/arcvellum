import { describe, expect, it, vi } from "vitest";
import { dispatchConstellationAction } from "./actionDispatcher";
import type { NodeActionDescriptor, SpatialNarrativeNode } from "@/types/spatial";

const node: SpatialNarrativeNode = {
  node_id: "character:lin",
  type: "character",
  creative_kind: "character",
  label: "林澈",
  subtitle: "",
  status: "formal",
  source_type: "characters",
  source_id: "lin",
  navigate: "archive",
  metrics: {},
  order: 0,
  parent_id: "project:origin",
  cluster_id: "characters",
  time_band: 0,
  completion_state: "completed",
  importance: .8,
  detail_level: "mid",
  world_hint: { surface: "characters", grammar: "constellation", elevation_band: "midground", occlusion_priority: 1 },
  detail_endpoint: "/narrative/node/character:lin",
};

function action(overrides: Partial<NodeActionDescriptor>): NodeActionDescriptor {
  return {
    action_id: "workspace:character:lin",
    kind: "open-workspace",
    label: "打开人物档案",
    target: node.node_id,
    mutates_project: false,
    requires_confirmation: false,
    risk_level: "read",
    enabled: true,
    reason: "",
    workspace: "archive",
    ...overrides,
  };
}

describe("dispatchConstellationAction", () => {
  it("routes backend workspace descriptors without inventing file operations", () => {
    const ports = { focus: vi.fn(), openWorkspace: vi.fn(), advance: vi.fn(), read: vi.fn() };
    expect(dispatchConstellationAction(action({}), node, ports)).toBe(true);
    expect(ports.openWorkspace).toHaveBeenCalledWith("archive");
    expect(ports.advance).not.toHaveBeenCalled();
  });

  it("does not execute disabled actions", () => {
    const ports = { focus: vi.fn(), openWorkspace: vi.fn(), advance: vi.fn(), read: vi.fn() };
    expect(dispatchConstellationAction(action({ enabled: false }), node, ports)).toBe(false);
    expect(ports.openWorkspace).not.toHaveBeenCalled();
  });
});
