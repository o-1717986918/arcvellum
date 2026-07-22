import type { SpatialNarrativeNode, SpatialNodeDetail } from "@/types/spatial";

export type SpatialWindowKind = "node" | "progress" | "reader" | "decisions" | "rules" | "health" | "delivery";

export interface SpatialWindowPosition {
  left: number;
  top: number;
}

export interface SpatialWindowSize {
  width: number;
  height: number;
}

export interface SpatialWindowAnchor {
  nodeId: string;
  offsetX: number;
  offsetY: number;
  enabled: boolean;
}

export interface SpatialWindow {
  id: string;
  kind: SpatialWindowKind;
  title: string;
  position: SpatialWindowPosition;
  size: SpatialWindowSize;
  layer: number;
  collapsed: boolean;
  node?: SpatialNarrativeNode;
  detail?: SpatialNodeDetail | null;
  anchor?: SpatialWindowAnchor;
}
