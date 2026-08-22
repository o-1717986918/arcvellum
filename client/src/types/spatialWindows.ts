import type { SpatialNarrativeNode, SpatialNodeDetail } from "@/types/spatial";

export type SpatialWindowKind =
  | "node" | "progress" | "agent" | "reader" | "decisions" | "rules" | "health" | "delivery"
  | "archive" | "style" | "quality" | "strategy" | "observatory" | "archaeology";
export type ReaderWindowMode = "peek" | "reading" | "immersive";
export type WorkspaceWindowMode = "float" | "fullscreen";

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
  reader_mode?: ReaderWindowMode;
  workspace_mode?: WorkspaceWindowMode;
  workspace_return?: {
    position: SpatialWindowPosition;
    size: SpatialWindowSize;
  };
  reader_return?: {
    position: SpatialWindowPosition;
    size: SpatialWindowSize;
    mode: Exclude<ReaderWindowMode, "immersive">;
  };
}
