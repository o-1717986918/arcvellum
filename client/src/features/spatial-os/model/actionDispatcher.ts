import type { NodeActionDescriptor, SpatialNarrativeNode } from "@/types/spatial";
import type { SpatialWindowKind } from "@/types/spatialWindows";

export interface ConstellationActionPorts {
  focus(nodeId: string): void;
  openWorkspace(kind: Exclude<SpatialWindowKind, "node">): void;
  advance(): void;
  read(node: SpatialNarrativeNode): void;
}

const workspaceAliases: Record<string, Exclude<SpatialWindowKind, "node"> | undefined> = {
  "node-detail": "archive",
  archive: "archive",
  style: "style",
  quality: "quality",
  strategy: "strategy",
  decisions: "decisions",
  rules: "rules",
  reader: "reader",
  delivery: "delivery",
  observatory: "observatory",
  archaeology: "archaeology",
};

export function dispatchConstellationAction(
  action: NodeActionDescriptor,
  node: SpatialNarrativeNode,
  ports: ConstellationActionPorts,
): boolean {
  if (!action.enabled) return false;
  if (action.kind === "focus") {
    ports.focus(node.node_id);
    return true;
  }
  if (action.kind === "open-workspace" || action.kind === "inspect") {
    const kind = workspaceAliases[action.workspace || node.workspace_hints?.preferred_workspace || ""];
    if (kind) {
      ports.openWorkspace(kind);
      return true;
    }
  }
  if (["run-creative-step", "request-agent", "promote"].includes(action.kind)) {
    ports.advance();
    return true;
  }
  if (["choose-branch", "approve"].includes(action.kind)) {
    ports.openWorkspace("decisions");
    return true;
  }
  if (["request-revision", "propose-edit"].includes(action.kind)) {
    ports.openWorkspace("quality");
    return true;
  }
  if (action.kind === "export") {
    ports.openWorkspace("delivery");
    return true;
  }
  if (node.creative_kind === "formal-prose" || node.creative_kind === "draft") {
    ports.read(node);
    return true;
  }
  return false;
}
