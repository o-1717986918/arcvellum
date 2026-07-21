export type ImmersivePanel =
  | "progress"
  | "decisions"
  | "reader"
  | "health"
  | "projects"
  | "library"
  | "quality"
  | "delivery"
  | "settings"
  | "help"
  | "details"
  | "legal";

export type ImmersiveEdge = "left" | "right" | "top" | "bottom";

export function panelEdge(panel: ImmersivePanel): ImmersiveEdge {
  if (["projects", "library"].includes(panel)) return "left";
  if (["progress", "decisions", "quality", "health", "delivery"].includes(panel)) return "right";
  if (panel === "reader") return "bottom";
  return "top";
}
