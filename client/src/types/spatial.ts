import type { NarrativeEdge, NarrativeNode } from "@/types/api";

export type SpatialGrammar = "spine" | "braid" | "strata" | "constellation" | "loop" | "stage";
export type SpatialDetailLevel = "far" | "mid" | "near";

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
  importance: number;
  detail_level: SpatialDetailLevel;
  world_hint: SpatialWorldHint;
  rhythm?: SpatialRhythmHint;
  detail_endpoint: string;
}

export interface SpatialNarrativeEdge extends NarrativeEdge {
  strength: number;
  direction: "forward" | "context";
  temporal_relation: "advances" | "associates";
}

export interface SpatialCluster {
  cluster_id: string;
  label: string;
  node_ids: string[];
  importance: number;
}

export interface SpatialNarrativeProjection {
  ok: boolean;
  schema: "arcvellum/narrative-projection/v3";
  project_root: string;
  generated_at: string;
  revision: string;
  sequence: number;
  source_revisions: Record<string, string>;
  level: "book" | "chapter" | "scene";
  focus: string;
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
}

export interface SpatialNodeDetail {
  ok: boolean;
  schema: "arcvellum/narrative-node-detail/v1";
  project_root: string;
  projection_revision: string;
  node: SpatialNarrativeNode;
  relationships: SpatialNarrativeEdge[];
  available_actions: Array<{ id: string; label: string }>;
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
