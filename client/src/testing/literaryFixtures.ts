import type { QualityProfile } from "@/features/quality/types";
import type { AdvisorSession, DashboardResponse, ProjectSummary } from "@/types/api";
import type { SpatialNarrativeProjection } from "@/types/spatial";

export function projectSummaryFixture(): ProjectSummary {
  return {
    path: "C:/ArcVellum/Works/潮汐之后",
    title: "潮汐之后",
    work_type: "novel",
    target_length: 30000,
    target_chapters: 2,
    target_scenes: 6,
    status: "writing",
    genre: "science-fiction",
    premise: "潮汐退去后，失踪者留下的记忆开始回到城市。",
    direction_count: 1,
  };
}

export function dashboardFixture(): DashboardResponse {
  return {
    ok: true,
    project: { ...projectSummaryFixture() },
    workflow_state: { route: "scene-development", status: "active" },
    current_task: { task_id: "scene-0001-compose", title: "构成第一场" },
    route_audits: [],
  };
}

export function advisorSessionFixture(messages: AdvisorSession["messages"] = []): AdvisorSession {
  return {
    session_id: "advisor-session-1",
    project_root: projectSummaryFixture().path,
    title: "潮汐之后创作对话",
    messages,
  };
}

export function qualityProfileFixture(): QualityProfile {
  return {
    name: "克制叙事",
    preset: "literary-balanced",
    revision: 1,
    digest: "quality-fixture-v1",
    thresholds: { dash_ratio: 0.02 },
    rule_modes: { punctuation: "blocking", contrast_frame: "blocking" },
    custom_banned_phrases: [],
    preferred_habits: ["用准确细节代替情绪器官轮岗"],
    exceptions: [],
  };
}

export function spatialProjectionFixture(): SpatialNarrativeProjection {
  const project = projectSummaryFixture();
  return {
    ok: true,
    schema: "arcvellum/narrative-projection/v3",
    project_root: project.path,
    generated_at: "2026-08-20T00:00:00Z",
    revision: "fixture-r1",
    projection_revision: "fixture-p1",
    sequence: 1,
    source_revisions: { scenes: "scene-r1" },
    level: "book",
    focus: "",
    focus_scope: {
      level: "book",
      focus_id: "",
      chapter_ids: ["chapter_0001"],
      scene_ids: ["scene_0001"],
      character_ids: [],
      anchor_node_ids: ["chapter_0001"],
      context_node_ids: ["scene_0001"],
    },
    relation_profiles: [{
      family: "chapter-scene",
      label: "章节与场景",
      edge_count: 1,
      focused_edge_count: 1,
      far_mode: "aggregate",
      mid_mode: "individual",
      near_mode: "emphasized",
      aggregate_anchor: "chapter-centroid",
      base_weight: 1,
      focus_weight: 1.5,
    }],
    character_references: [],
    spatial_grammar: "spine",
    available_grammars: ["spine", "braid", "constellation"],
    layout_seed: "fixture-layout-v1",
    summary: { node_count: 2, edge_count: 1 },
    nodes: [
      spatialNode("chapter_0001", "chapter", "第一章", null, "chapter_0001", 1),
      spatialNode("scene_0001", "scene", "潮线", "chapter_0001", "chapter_0001", 2),
    ],
    edges: [{
      edge_id: "chapter_0001:scene_0001",
      source: "chapter_0001",
      target: "scene_0001",
      type: "chapter-scene",
      label: "包含",
      strength: 1,
      direction: "forward",
      temporal_relation: "advances",
      relation_family: "chapter-scene",
      focus_state: "global",
    }],
    clusters: [{ cluster_id: "chapter_0001", label: "第一章", node_ids: ["chapter_0001", "scene_0001"], importance: 1 }],
    layout_hints: {},
    lod_summary: { far: 1, mid: 1, near: 0 },
    timeline: [{ node_id: "chapter_0001", label: "第一章", status: "current", order: 1, formal_chars: 0, word_target: 15000 }],
    delta: { initial: true, added_nodes: [], removed_nodes: [], updated_nodes: [], added_edges: [], removed_edges: [], updated_edges: [] },
    motion_events: [],
    legend: [{ type: "scene", label: "场景", color: "#74b594" }],
    accessibility_summary: "第一章包含一个待创作场景。",
  };
}

function spatialNode(
  nodeId: string,
  type: string,
  label: string,
  parentId: string | null,
  clusterId: string,
  order: number,
): SpatialNarrativeProjection["nodes"][number] {
  return {
    node_id: nodeId,
    type,
    label,
    subtitle: "",
    status: order === 1 ? "current" : "planned",
    source_type: type,
    source_id: nodeId,
    navigate: nodeId,
    metrics: {},
    order,
    parent_id: parentId,
    cluster_id: clusterId,
    time_band: order,
    completion_state: order === 1 ? "active" : "planned",
    importance: 1,
    detail_level: "near",
    world_hint: { surface: "narrative", grammar: "spine", elevation_band: "midground", occlusion_priority: order },
    detail_endpoint: `/narrative/nodes/${nodeId}`,
  };
}
