import { Container, Graphics } from "pixi.js";
import type { SpatialLayout, SpatialNarrativeProjection, WorldPoint } from "@/types/spatial";
import { relationModeForLevel } from "@/features/orrery/model/relationLens";
import { curvePolarity, mix } from "./renderMath";
import type { ScenePalette } from "./renderModel";

export interface RelationLayers {
  primary: Graphics;
  secondary: Graphics;
}

export function drawNarrativeRelations(options: {
  projection: SpatialNarrativeProjection;
  layout: SpatialLayout;
  palette: ScenePalette;
  target: Container;
  projectPoint(point: WorldPoint): { x: number; y: number };
}): RelationLayers {
  const { projection, layout, palette, target, projectPoint } = options;
  const primary = new Graphics();
  const secondary = new Graphics();
  const profiles = new Map(projection.relation_profiles.map((profile) => [profile.family, profile]));
  const detailProjection = projection.level !== "book";
  const globalBackboneGrammar = layout.grammar !== "loop" && layout.grammar !== "constellation";
  for (const edge of projection.edges) {
    const source = layout.points.get(edge.source);
    const targetPoint = layout.points.get(edge.target);
    if (!source || !targetPoint) continue;
    const start = projectPoint(source);
    const end = projectPoint(targetPoint);
    const color = edge.type === "branch" || edge.type === "raises" || edge.type === "promise"
      ? palette.branch
      : edge.type === "canon" || edge.type === "review"
        ? palette.canon
        : edge.type === "workflow"
          ? palette.core
          : mix(palette.core, palette.label, 0.46);
    const backbone = edge.type === "sequence" || edge.type === "bridge";
    // Interactive evidence and character relations stay in the SVG overlay;
    // this GPU pass owns only the narrative backbone.
    if (!backbone) continue;
    const relationMode = relationModeForLevel(profiles.get(edge.relation_family), projection.level);
    const emphasized = relationMode === "emphasized";
    const connection = globalBackboneGrammar || emphasized ? primary : secondary;
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const normalX = -dy / distance;
    const normalY = dx / distance;
    const bend = Math.min(220, Math.max(26, distance * 0.11)) * curvePolarity(edge.edge_id);
    const controlA = { x: start.x + dx * 0.34 + normalX * bend, y: start.y + dy * 0.34 + normalY * bend };
    const controlB = { x: end.x - dx * 0.34 + normalX * bend, y: end.y - dy * 0.34 + normalY * bend };
    const modeWidth = relationMode === "emphasized" ? 1.55 : relationMode === "individual" ? 1.15 : 0.82;
    const modeAlpha = relationMode === "emphasized" ? 1.6 : relationMode === "individual" ? 1.08 : 0.72;
    const width = 2.8 * modeWidth;
    const alpha = Math.min(0.78, (detailProjection ? 0.64 : 0.48) * modeAlpha);
    connection.moveTo(start.x, start.y)
      .bezierCurveTo(controlA.x, controlA.y, controlB.x, controlB.y, end.x, end.y)
      .stroke({ color, width, alpha });
  }
  target.addChild(primary, secondary);
  return { primary, secondary };
}

export function syncRelationLod(
  layers: RelationLayers | null,
  scale: number,
  focused: boolean,
): void {
  if (!layers) return;
  layers.primary.alpha = scale >= 0.42 ? 1 : scale >= 0.22 ? 0.62 : 0.38;
  layers.secondary.alpha = focused ? 0.46 : scale >= 0.82 ? 0.32 : scale >= 0.58 ? 0.22 : scale >= 0.3 ? 0.14 : 0.09;
}
