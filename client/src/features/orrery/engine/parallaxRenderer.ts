import { Application, Container } from "pixi.js";
import { Viewport } from "pixi-viewport";
import type { SpatialLayout, SpatialNarrativeProjection, WorldPoint } from "@/types/spatial";
import { resolveOrreryMotion, type OrreryDepth, type OrreryMotion } from "@/services/orreryPreferences";
import { ambientNodeOffset, hasAmbientNodeMotion } from "./ambientMotion";
import { advanceCameraAnimation, type CameraAnimation } from "./cameraAnimation";
import { attachOrbitInteraction } from "./orbitInteraction";
import {
  DEFAULT_PARALLAX_VIEW,
  NARRATIVE_STAGE,
  depthScale,
  fittedCameraFrame,
  isSameParallaxView,
  planeBounds,
  scenePoint,
  type ParallaxView,
} from "./parallaxProjection";
import { drawNarrativeRelations, syncRelationLod, type RelationLayers } from "./relationRenderer";
import {
  DEFAULT_PALETTE,
  readPalette,
  readStageExperience,
  rendererResolution,
  type NarrativeFrame,
  type ScenePalette,
  type StageExperience,
} from "./renderModel";
import { drawStageScenery } from "./stageScenery";

const WORLD_WIDTH = NARRATIVE_STAGE.width;
const WORLD_HEIGHT = NARRATIVE_STAGE.height;
const ORIGIN = NARRATIVE_STAGE.origin;

// Narrative facts and DOM labels stay on the work plane. Only atmosphere
// receives differential motion, so a pan never separates a node from its label.
const LAYER_DEPTH: Record<OrreryDepth, { far: number; mid: number; near: number }> = {
  deep: { far: 0.28, mid: 1, near: 1.18 },
  balanced: { far: 0.52, mid: 1, near: 1.1 },
  flat: { far: 1, mid: 1, near: 1 },
};

export interface StageAnchor {
  x: number;
  y: number;
  visible: boolean;
  scale: number;
}

/** Coordinates the Pixi stage, camera and DOM anchor projection. */
export class NarrativeParallaxRenderer {
  private readonly far = new Container();
  private readonly mid = new Container();
  private readonly near = new Container();
  private layout: SpatialLayout | null = null;
  private projection: SpatialNarrativeProjection | null = null;
  private animation: CameraAnimation | null = null;
  private anchorListener: ((anchors: Record<string, StageAnchor>) => void) | null = null;
  private contextLostListener: (() => void) | null = null;
  private lastViewport = "";
  private nextAnchorAt = 0;
  private palette: ScenePalette = DEFAULT_PALETTE;
  private elapsed = 0;
  private relationLayers: RelationLayers | null = null;
  private focusedNodeId = "";
  private view: ParallaxView = { ...DEFAULT_PARALLAX_VIEW };
  private viewRefreshQueued = false;
  private detachOrbitInteraction: () => void;

  private readonly handleContextLost = (event: Event) => {
    event.preventDefault();
    this.animation = null;
    this.contextLostListener?.();
  };

  private readonly handleContextRestored = () => {
    if (this.projection && this.layout) this.update(this.projection, this.layout);
  };

  private constructor(
    private readonly host: HTMLElement,
    private readonly viewport: Viewport,
    private readonly app: Application,
    private experience: StageExperience,
  ) {
    this.detachOrbitInteraction = attachOrbitInteraction(app.canvas, {
      currentView: () => this.view,
      pivot: () => this.viewPivot(),
      cancelAnimation: () => { this.animation = null; },
      updateView: (view, pivot) => {
        this.view = view;
        this.queueViewRefresh(pivot);
      },
    });
  }

  static async create(host: HTMLElement): Promise<NarrativeParallaxRenderer> {
    const experience = readStageExperience();
    const app = new Application();
    await app.init({
      resizeTo: host,
      autoDensity: true,
      resolution: rendererResolution(experience.quality),
      backgroundAlpha: 0,
      antialias: true,
      preference: "webgl",
    });
    const viewport = new Viewport({
      screenWidth: Math.max(1, host.clientWidth),
      screenHeight: Math.max(1, host.clientHeight),
      worldWidth: WORLD_WIDTH,
      worldHeight: WORLD_HEIGHT,
      events: app.renderer.events,
      ticker: app.ticker,
      passiveWheel: false,
    });
    const instance = new NarrativeParallaxRenderer(host, viewport, app, experience);
    app.canvas.className = "narrative-parallax-canvas";
    app.canvas.addEventListener("webglcontextlost", instance.handleContextLost, false);
    app.canvas.addEventListener("webglcontextrestored", instance.handleContextRestored, false);
    host.append(app.canvas);
    app.stage.addChild(viewport);
    viewport.eventMode = "static";
    viewport.drag({ pressDrag: true, wheel: false, mouseButtons: "middle" })
      .pinch()
      .wheel({ smooth: 4, percent: 0.12 })
      .decelerate({ friction: 0.9, minSpeed: 0.01 })
      .clamp({ direction: "all", underflow: "center" })
      .clampZoom({ minScale: 0.012, maxScale: 2.7 });
    viewport.on("drag-start", () => { instance.animation = null; });
    viewport.addChild(instance.far, instance.mid, instance.near);
    app.ticker.add((ticker) => instance.tick(ticker.deltaMS));
    return instance;
  }

  onAnchors(listener: (anchors: Record<string, StageAnchor>) => void): void {
    this.anchorListener = listener;
  }

  onContextLost(listener: () => void): void {
    this.contextLostListener = listener;
  }

  resize(width: number, height: number): void {
    if (!width || !height) return;
    this.viewport.resize(width, height, WORLD_WIDTH, WORLD_HEIGHT);
    this.emitAnchors(true);
  }

  update(projection: SpatialNarrativeProjection, layout: SpatialLayout): void {
    this.projection = projection;
    this.layout = layout;
    this.experience = readStageExperience();
    this.palette = readPalette(this.host);
    this.clearLayers();
    drawStageScenery({
      layers: { far: this.far, mid: this.mid, near: this.near },
      layout,
      projection,
      palette: this.palette,
      experience: this.experience,
      frame: this.narrativeFrame(),
      primaryGroups: (groupSize) => this.projectedPrimaryGroups(groupSize),
    });
    this.relationLayers = drawNarrativeRelations({
      projection,
      layout,
      palette: this.palette,
      target: this.mid,
      projectPoint: (point) => this.projectPoint(point),
    });
    this.emitAnchors(true);
  }

  fit(): void {
    if (!this.layout) return;
    this.focusedNodeId = "";
    this.emitAnchors(true);
    const frame = this.narrativeFrame();
    const width = Math.max(480, this.host.clientWidth - 164);
    const height = Math.max(380, this.host.clientHeight - 176);
    const scale = Math.min(width / frame.width, height / frame.height);
    this.animateTo(frame.centerX, frame.centerY, Math.min(0.78, Math.max(0.012, scale)), 560);
  }

  showOpeningSegment(): void {
    if (!this.layout || !this.projection) return;
    this.animation = null;
    this.focusedNodeId = "";
    const primary = this.projection.nodes
      .filter((node) => node.type === "chapter" || node.type === "scene")
      .sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
    if (!primary.length) return;
    const detectedCurrentIndex = primary.findIndex((node) => node.status === "current" || node.status === "blocked");
    const currentIndex = detectedCurrentIndex >= 0 ? detectedCurrentIndex : 0;
    const start = Math.max(0, Math.min(primary.length - 1, currentIndex - 2));
    const availableWidth = Math.max(480, this.host.clientWidth - 148);
    const stageGrammar = this.layout.grammar === "stage";
    const radialGrammar = this.layout.grammar === "loop" || this.layout.grammar === "constellation";
    const visibleCount = stageGrammar ? 3 : Math.max(5, Math.min(7, Math.floor(availableWidth / 172)));
    const points = primary.slice(start, Math.min(primary.length, start + visibleCount))
      .map((node) => this.layout?.points.get(node.node_id))
      .filter((point): point is WorldPoint => Boolean(point))
      .map((point) => this.projectPoint(point));
    if (!points.length) return;
    const minX = Math.min(...points.map((point) => point.x));
    const maxX = Math.max(...points.map((point) => point.x));
    const minY = Math.min(...points.map((point) => point.y));
    const maxY = Math.max(...points.map((point) => point.y));
    const width = Math.max(680, maxX - minX + 360);
    const height = Math.max(520, maxY - minY + 420);
    const availableHeight = Math.max(380, this.host.clientHeight - 170);
    const minimumScale = stageGrammar ? 0.52 : radialGrammar ? 0.56 : 0.16;
    const scale = Math.min(0.98, Math.max(minimumScale, Math.min(availableWidth / width, availableHeight / height)));
    this.viewport.moveCenter((minX + maxX) / 2, (minY + maxY) / 2);
    this.viewport.setZoom(scale, true);
    this.emitAnchors(true);
  }

  focus(point: WorldPoint, importance = 0.8, nodeId = ""): void {
    this.focusedNodeId = nodeId;
    this.emitAnchors(true);
    const target = this.projectPoint(point);
    this.animateTo(target.x, target.y, Math.min(1.8, 0.86 + importance * 0.58), 680);
  }

  focusCluster(points: WorldPoint[], nodeId = ""): void {
    const projected = points.map((point) => this.projectPoint(point));
    const frame = fittedCameraFrame(
      projected,
      { width: Math.max(480, this.host.clientWidth - 240), height: Math.max(360, this.host.clientHeight - 210) },
      { minWidth: 720, minHeight: 500, padX: 420, padY: 360, minScale: 0.12, maxScale: 1.32 },
    );
    if (!frame) return;
    this.focusedNodeId = nodeId;
    this.emitAnchors(true);
    this.animateTo(frame.centerX, frame.centerY, frame.scale, 720);
  }

  resetView(): void {
    if (isSameParallaxView(this.view, DEFAULT_PARALLAX_VIEW)) return;
    const pivot = this.viewPivot();
    this.view = { ...DEFAULT_PARALLAX_VIEW };
    this.animation = null;
    this.updateViewAround(pivot);
  }

  dispose(): void {
    this.app.canvas.removeEventListener("webglcontextlost", this.handleContextLost);
    this.app.canvas.removeEventListener("webglcontextrestored", this.handleContextRestored);
    this.detachOrbitInteraction();
    this.viewport.destroy({ children: true });
    this.app.destroy(true, { children: true });
    this.anchorListener = null;
    this.contextLostListener = null;
  }

  private tick(deltaMs: number): void {
    this.elapsed += deltaMs;
    if (this.animation) {
      const step = advanceCameraAnimation(this.animation, deltaMs);
      this.viewport.moveCenter(step.frame.x, step.frame.y);
      this.viewport.setZoom(step.frame.scale, true);
      this.animation = step.animation;
    }
    this.syncParallax();
    syncRelationLod(this.relationLayers, this.viewport.scale.x, Boolean(this.focusedNodeId));
    const revision = `${this.viewport.x.toFixed(1)}:${this.viewport.y.toFixed(1)}:${this.viewport.scale.x.toFixed(3)}`;
    const ambientMotion = this.effectiveMotion() === "full"
      && Boolean(this.projection && hasAmbientNodeMotion(this.projection.nodes));
    if (revision !== this.lastViewport || ambientMotion) {
      this.lastViewport = revision;
      this.emitAnchors();
    }
  }

  private animateTo(x: number, y: number, scale: number, duration: number): void {
    const motion = this.effectiveMotion();
    if (motion === "still") {
      this.viewport.moveCenter(x, y);
      this.viewport.setZoom(scale, true);
      this.animation = null;
      return;
    }
    const center = this.viewport.center;
    this.animation = {
      from: { x: center.x, y: center.y, scale: this.viewport.scale.x },
      to: { x, y, scale },
      elapsed: 0,
      duration: motion === "reduced" ? Math.min(200, duration) : duration,
    };
  }

  private clearLayers(): void {
    this.relationLayers = null;
    for (const layer of [this.far, this.mid, this.near]) {
      const children = layer.removeChildren();
      children.forEach((child) => child.destroy({ children: true }));
    }
  }

  private narrativeFrame(): NarrativeFrame {
    const projected = (this.projection?.nodes || [])
      .filter((node) => node.type === "chapter" || node.type === "scene")
      .map((node) => this.layout?.points.get(node.node_id))
      .filter((point): point is WorldPoint => Boolean(point))
      .map((point) => this.projectPoint(point));
    const bounds = planeBounds(projected);
    if (!bounds) return { centerX: ORIGIN.x, centerY: ORIGIN.y, width: 1880, height: 900 };
    return {
      centerX: bounds.centerX,
      centerY: bounds.centerY,
      width: Math.max(1200, bounds.maxX - bounds.minX + 520),
      height: Math.max(720, bounds.maxY - bounds.minY + 420),
    };
  }

  private projectedPrimaryGroups(groupSize: number): NarrativeFrame[] {
    if (!this.projection || !this.layout) return [];
    const primary = this.projection.nodes
      .filter((node) => node.type === "chapter" || node.type === "scene")
      .sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
    const result: NarrativeFrame[] = [];
    for (let index = 0; index < primary.length; index += Math.max(1, groupSize)) {
      const points = primary.slice(index, index + groupSize)
        .map((node) => this.layout?.points.get(node.node_id))
        .filter((point): point is WorldPoint => Boolean(point))
        .map((point) => this.projectPoint(point));
      const bounds = planeBounds(points);
      if (!bounds) continue;
      result.push({
        centerX: bounds.centerX,
        centerY: bounds.centerY,
        width: Math.max(1, bounds.maxX - bounds.minX),
        height: Math.max(1, bounds.maxY - bounds.minY),
      });
    }
    return result;
  }

  private tideOffset(
    node: SpatialNarrativeProjection["nodes"][number],
    base: { x: number; y: number },
  ): { x: number; y: number } {
    if (!this.focusedNodeId || node.parent_id !== this.focusedNodeId) return { x: 0, y: 0 };
    const focusPoint = this.layout?.points.get(this.focusedNodeId);
    if (!focusPoint) return { x: 0, y: -12 };
    const focus = this.projectPoint(focusPoint);
    const dx = base.x - focus.x;
    const dy = base.y - focus.y;
    const magnitude = Math.max(1, Math.hypot(dx, dy));
    return { x: dx / magnitude * 14, y: dy / magnitude * 14 - 7 };
  }

  private syncParallax(): void {
    const center = this.viewport.center;
    const depth = LAYER_DEPTH[this.experience.depth];
    for (const [layer, layerDepth] of [[this.far, depth.far], [this.mid, depth.mid], [this.near, depth.near]] as const) {
      layer.scale.set(layerDepth);
      layer.position.set(center.x * (1 - layerDepth), center.y * (1 - layerDepth));
    }
  }

  private emitAnchors(force = false): void {
    if (!this.anchorListener || !this.layout) return;
    const now = Date.now();
    if (!force && now < this.nextAnchorAt) return;
    this.nextAnchorAt = now + 42;
    const rect = this.host.getBoundingClientRect();
    const anchors: Record<string, StageAnchor> = {};
    const nodes = new Map(this.projection?.nodes.map((node) => [node.node_id, node]) || []);
    for (const [nodeId, point] of this.layout.points) {
      const scene = this.projectPoint(point);
      const node = nodes.get(nodeId);
      const drift = node && this.effectiveMotion() === "full"
        ? ambientNodeOffset(node, this.elapsed / 1000)
        : { x: 0, y: 0 };
      const tide = node ? this.tideOffset(node, scene) : { x: 0, y: 0 };
      const screen = this.viewport.toScreen(scene.x + drift.x + tide.x, scene.y + drift.y + tide.y);
      anchors[nodeId] = {
        x: screen.x,
        y: screen.y,
        visible: screen.x >= -96 && screen.x <= rect.width + 96 && screen.y >= -96 && screen.y <= rect.height + 96,
        scale: Math.max(0.54, Math.min(1.5, this.viewport.scale.x * this.projectDepthScale(point))),
      };
    }
    this.anchorListener(anchors);
  }

  private projectPoint(point: WorldPoint): { x: number; y: number } {
    return scenePoint(point, this.experience.depth, this.view);
  }

  private projectDepthScale(point: WorldPoint): number {
    return depthScale(point, this.experience.depth, this.view);
  }

  private queueViewRefresh(pivot: WorldPoint | null): void {
    if (this.viewRefreshQueued) return;
    this.viewRefreshQueued = true;
    window.requestAnimationFrame(() => {
      this.viewRefreshQueued = false;
      this.updateViewAround(pivot);
    });
  }

  private updateViewAround(pivot: WorldPoint | null): void {
    if (!this.projection || !this.layout) return;
    this.update(this.projection, this.layout);
    if (pivot) {
      const projected = this.projectPoint(pivot);
      this.viewport.moveCenter(projected.x, projected.y);
      this.emitAnchors(true);
    }
  }

  private viewPivot(): WorldPoint | null {
    if (!this.layout) return null;
    const focused = this.focusedNodeId ? this.layout.points.get(this.focusedNodeId) : undefined;
    if (focused) return focused;
    let closest: WorldPoint | null = null;
    let closestDistance = Number.POSITIVE_INFINITY;
    const center = this.viewport.center;
    for (const point of this.layout.points.values()) {
      const projected = this.projectPoint(point);
      const distance = Math.hypot(projected.x - center.x, projected.y - center.y);
      if (distance < closestDistance) {
        closest = point;
        closestDistance = distance;
      }
    }
    return closest;
  }

  private effectiveMotion(): OrreryMotion {
    return resolveOrreryMotion(
      this.experience.motion,
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    );
  }
}
