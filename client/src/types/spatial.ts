import type { NarrativeEdge, NarrativeNode } from "@/types/api";
import type { NarrativeFocusLevel, NarrativeFocusScope } from "@/features/orrery/model/focusScope";
import type { CharacterReference } from "@/features/orrery/model/characters";
import type { RelationFamily, RelationFocusState, RelationVisibilityProfile } from "@/features/orrery/model/relations";

export type SpatialGrammar = "spine" | "braid" | "strata" | "constellation" | "loop" | "stage";
export type SpatialDetailLevel = "far" | "mid" | "near";
export type SpatialCompletionState = "completed" | "active" | "planned" | "blocked";
export type CreativeNodeKind =
  | "project" | "story-architecture" | "word-budget" | "style" | "world" | "location" | "organization"
  | "character" | "relationship" | "volume" | "chapter" | "scene" | "event" | "branch" | "reader-question"
  | "promise" | "payoff" | "draft" | "formal-prose" | "review" | "revision" | "canon" | "human-decision" | "delivery";
export type CreativeNodeLifecycle =
  | "latent" | "locked" | "available" | "active" | "awaiting" | "reviewing" | "revision" | "formal" | "blocked" | "superseded" | "delivered";
export type NodeActionKind =
  | "inspect" | "focus" | "open-workspace" | "compare" | "propose-edit" | "request-agent" | "run-creative-step"
  | "choose-branch" | "request-revision" | "promote" | "approve" | "export";

export interface NodeActionDescriptor {
  action_id: string;
  kind: NodeActionKind;
  label: string;
  target: string;
  mutates_project: boolean;
  requires_confirmation: boolean;
  risk_level: "read" | "draft" | "formal" | string;
  enabled: boolean;
  reason: string;
  workspace: string;
}

export interface SpatialOrientation {
  x: number;
  y: number;
  z: number;
  w: number;
}

export interface SpatialViewState {
  orientation: SpatialOrientation;
  pan: { x: number; y: number };
  zoom: number;
  time_cursor: number;
  time_window: number;
  camera_preset: "recommended" | "front" | "current-chapter" | "custom";
}

export interface SpatialWorldHint {
  surface: string;
  grammar: SpatialGrammar;
  elevation_band: "foreground" | "midground" | "background";
  occlusion_priority: number;
}

export interface SpatialRhythmHint {
  entry: number;
  peak: number;
  exit: number;
  pace: string;
  role: string;
  detail_level: string;
  weight: number;
  timeline_start?: number;
  timeline_end?: number;
  spatial_time_gap_before?: number;
  source: string;
}

export interface SpatialNarrativeNode extends NarrativeNode {
  parent_id: string | null;
  cluster_id: string;
  time_band: number;
  completion_state: SpatialCompletionState;
  importance: number;
  detail_level: SpatialDetailLevel;
  world_hint: SpatialWorldHint;
  rhythm?: SpatialRhythmHint;
  detail_endpoint: string;
  creative_kind?: CreativeNodeKind;
  lifecycle?: CreativeNodeLifecycle;
  hierarchy_depth?: number;
  depth_role?: "far-anchor" | "mid-structure" | "near-detail";
  available_actions?: NodeActionDescriptor[];
  workspace_hints?: {
    preferred_workspace: string;
    supports_float: boolean;
    supports_dock: boolean;
    supports_fullscreen: boolean;
  };
}

export interface SpatialNarrativeEdge extends NarrativeEdge {
  strength: number;
  direction: "forward" | "context";
  temporal_relation: "advances" | "associates";
  relation_family: RelationFamily;
  focus_state: RelationFocusState;
}

export interface SpatialCluster {
  cluster_id: string;
  label: string;
  node_ids: string[];
  importance: number;
}

export interface SpatialNarrativeProjection {
  ok: boolean;
  schema: "arcvellum/narrative-projection/v3" | "arcvellum/narrative-projection/v4";
  project_root: string;
  generated_at: string;
  revision: string;
  projection_revision?: string;
  sequence: number;
  source_revisions: Record<string, string>;
  level: NarrativeFocusLevel;
  focus: string;
  focus_scope: NarrativeFocusScope;
  relation_profiles: RelationVisibilityProfile[];
  character_references: CharacterReference[];
  spatial_grammar: SpatialGrammar;
  available_grammars: SpatialGrammar[];
  layout_seed: string;
  summary: Record<string, number | boolean | string>;
  nodes: SpatialNarrativeNode[];
  edges: SpatialNarrativeEdge[];
  clusters: SpatialCluster[];
  layout_hints: Record<string, unknown>;
  lod_summary: Record<SpatialDetailLevel, number>;
  timeline: Array<{ node_id: string; label: string; status: string; order: number; formal_chars: number; word_target: number }>;
  delta: {
    initial: boolean;
    added_nodes: string[];
    removed_nodes: string[];
    updated_nodes: string[];
    added_edges: string[];
    removed_edges: string[];
    updated_edges: string[];
  };
  motion_events: Array<{ type: string; node_id: string; label: string }>;
  legend: Array<{ type: string; label: string; color: string }>;
  accessibility_summary: string;
  activities?: Array<{
    activity_id: string;
    kind: string;
    status: string;
    route: string;
    target: string;
    label: string;
    summary: string;
  }>;
}

export interface SpatialProjectionCollectionPatch<T> {
  upsert: T[];
  remove: string[];
  order: string[];
}

export interface SpatialNarrativeProjectionPatch {
  ok: boolean;
  schema: "arcvellum/narrative-projection-patch/v1";
  projection_schema?: SpatialNarrativeProjection["schema"];
  base_revision: string;
  target_revision: string;
  sequence: number;
  meta: Record<string, unknown>;
  meta_remove: string[];
  nodes: SpatialProjectionCollectionPatch<SpatialNarrativeNode>;
  edges: SpatialProjectionCollectionPatch<SpatialNarrativeEdge>;
  delta: SpatialNarrativeProjection["delta"];
  motion_events: SpatialNarrativeProjection["motion_events"];
}

export interface SpatialNodeDetail {
  ok: boolean;
  schema: "arcvellum/narrative-node-detail/v1" | "arcvellum/narrative-node-detail/v2";
  project_root: string;
  projection_revision: string;
  node: SpatialNarrativeNode;
  relationships: SpatialNarrativeEdge[];
  available_actions: NodeActionDescriptor[] | Array<{ id: string; label: string }>;
  workspace_hints?: SpatialNarrativeNode["workspace_hints"];
}

export interface WorldPoint {
  x: number;
  y: number;
  z: number;
}

export interface SpatialLayout {
  grammar: SpatialGrammar;
  revision: string;
  points: Map<string, WorldPoint>;
  bounds: { min: WorldPoint; max: WorldPoint; radius: number };
}
