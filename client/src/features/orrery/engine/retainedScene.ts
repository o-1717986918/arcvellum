import type { SpatialLayout, SpatialNarrativeProjection, WorldPoint } from "@/types/spatial";
import { drawNarrativeRelations, syncRelationLod, type RelationLayers } from "./relationRenderer";
import { drawStageScenery, type SceneryGraphics, type StageLayers } from "./stageScenery";
import { projectedPrimaryGroups } from "./primaryGroupFrames";
import { NARRATIVE_STAGE, planeBounds } from "./parallaxProjection";
import type { NarrativeFrame, ScenePalette, StageExperience } from "./renderModel";

type ProjectPoint = (point: WorldPoint) => { x: number; y: number };

/** Retain GPU objects across camera updates; only their necessary geometry changes. */
export class RetainedScene {
  private scenery?: SceneryGraphics;
  private relations?: RelationLayers;
  private layout: SpatialLayout | null = null;
  private sceneryBinding = "";
  private relationBinding = "";

  constructor(private readonly layers: StageLayers) {}

  update(projection: SpatialNarrativeProjection, layout: SpatialLayout, palette: ScenePalette,
    experience: StageExperience, projectPoint: ProjectPoint, rotated = false): void {
    const style = rotated ? "" : JSON.stringify([palette, experience.depth, experience.quality]);
    const sceneryBinding = rotated ? this.sceneryBinding : JSON.stringify([style,
      projection.nodes.filter((n) => n.type === "chapter" || n.type === "scene").map((n) => n.node_id)]);
    const relationBinding = rotated ? this.relationBinding : JSON.stringify([style, projection.level, projection.relation_profiles,
      projection.edges.filter((e) => e.type === "sequence" || e.type === "bridge")]);
    if (rotated || layout !== this.layout || sceneryBinding !== this.sceneryBinding) {
      this.scenery = drawStageScenery({
        layers: this.layers, layout, projection, palette, experience,
        frame: projectedNarrativeFrame(projection, layout, projectPoint),
        primaryGroups: (size) => projectedPrimaryGroups(projection, layout, size, projectPoint),
      }, this.scenery);
    }
    if (rotated || layout !== this.layout || relationBinding !== this.relationBinding) {
      this.relations = drawNarrativeRelations({ projection, layout, palette,
        target: this.layers.mid, projectPoint, retained: this.relations });
    }
    this.layout = layout;
    this.sceneryBinding = sceneryBinding;
    this.relationBinding = relationBinding;
  }

  syncLod(scale: number, focused: boolean): void { syncRelationLod(this.relations || null, scale, focused); }
}

export function projectedNarrativeFrame(projection: SpatialNarrativeProjection | null, layout: SpatialLayout | null,
  projectPoint: ProjectPoint): NarrativeFrame {
  const projected = (projection?.nodes || []).filter((node) => node.type === "chapter" || node.type === "scene")
    .map((node) => layout?.points.get(node.node_id)).filter((p): p is WorldPoint => Boolean(p)).map(projectPoint);
  const bounds = planeBounds(projected);
  if (!bounds) return { centerX: NARRATIVE_STAGE.origin.x, centerY: NARRATIVE_STAGE.origin.y, width: 1880, height: 900 };
  return { centerX: bounds.centerX, centerY: bounds.centerY,
    width: Math.max(1200, bounds.maxX - bounds.minX + 520), height: Math.max(720, bounds.maxY - bounds.minY + 420) };
}
