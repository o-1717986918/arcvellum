import { Application, Container, Graphics } from "pixi.js";
import { Viewport } from "pixi-viewport";
import type { SpatialLayout, SpatialNarrativeProjection, WorldPoint } from "@/types/spatial";
import type { OrreryDepth, OrreryMotion, OrreryRenderQuality } from "@/services/orreryPreferences";
import { DEFAULT_PARALLAX_VIEW, depthScale, isSameParallaxView, parallaxViewFromDrag, scenePoint, type ParallaxView } from "@/features/orrery/engine/parallaxProjection";
import { constellationClusterSize, stageActSize } from "@/features/orrery/layout/curveProfiles";

// Book-scale work surface. The world is intentionally generous so a 300+ scene
// projection can still fit without the camera clamping the last chapters.
const WORLD_WIDTH = 192000;
const WORLD_HEIGHT = 22000;
const ORIGIN = { x: WORLD_WIDTH / 2, y: WORLD_HEIGHT / 2 };

// Narrative facts and their DOM labels stay on the work plane. Only the
// atmospheric environment receives differential motion, so a long pan never
// separates an actionable node from its visible label.
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

interface AnimationTarget {
  from: { x: number; y: number; scale: number };
  to: { x: number; y: number; scale: number };
  elapsed: number;
  duration: number;
}

interface ScenePalette {
  core: number;
  canon: number;
  branch: number;
  warning: number;
  label: number;
  deep: number;
  shadow: number;
}

interface NarrativeFrame {
  centerX: number;
  centerY: number;
  width: number;
  height: number;
}

interface StageExperience {
  motion: OrreryMotion;
  depth: OrreryDepth;
  quality: OrreryRenderQuality;
}

const DEFAULT_PALETTE: ScenePalette = {
  core: 0x68b99c,
  canon: 0xc2a45e,
  branch: 0x9184ad,
  warning: 0xd9644d,
  label: 0xedf4f1,
  deep: 0x071713,
  shadow: 0x06130f,
};

/**
 * A two-dimensional GPU scene with a physical-looking camera grammar.
 * It deliberately has no meshes or 3D transforms: depth comes from parallax,
 * occluding silhouettes, side-shadows, and differential motion.
 */
export class NarrativeParallaxRenderer {
  private readonly app: Application;
  private readonly viewport: Viewport;
  private readonly far = new Container();
  private readonly mid = new Container();
  private readonly near = new Container();
  private readonly host: HTMLElement;
  private layout: SpatialLayout | null = null;
  private projection: SpatialNarrativeProjection | null = null;
  private animation: AnimationTarget | null = null;
  private anchorListener: ((anchors: Record<string, StageAnchor>) => void) | null = null;
  private lastViewport = "";
  private nextAnchorAt = 0;
  private palette: ScenePalette = DEFAULT_PALETTE;
  private elapsed = 0;
  private primaryRelations: Graphics | null = null;
  private secondaryRelations: Graphics | null = null;
  private focusedNodeId = "";
  private experience: StageExperience;
  private view: ParallaxView = { ...DEFAULT_PARALLAX_VIEW };
  private orbitPointer: { pointerId: number; clientX: number; clientY: number; view: ParallaxView; pivot: WorldPoint | null } | null = null;
  private viewRefreshQueued = false;
  private contextLostListener: (() => void) | null = null;
  private readonly handleContextLost = (event: Event) => {
    event.preventDefault();
    this.animation = null;
    this.contextLostListener?.();
  };
  private readonly handleContextRestored = () => {
    if (this.projection && this.layout) this.update(this.projection, this.layout);
  };
  private readonly handlePointerDown = (event: PointerEvent) => {
    if (event.button !== 1) return;
    // Middle drag owns the oblique camera; left drag remains world panning.
    event.preventDefault();
    event.stopImmediatePropagation();
    this.animation = null;
    this.orbitPointer = {
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      view: { ...this.view },
      pivot: this.viewPivot(),
    };
    this.app.canvas.dataset.orbiting = "true";
    this.app.canvas.setPointerCapture?.(event.pointerId);
  };
  private readonly handlePointerMove = (event: PointerEvent) => {
    const orbit = this.orbitPointer;
    if (!orbit || orbit.pointerId !== event.pointerId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    this.view = parallaxViewFromDrag(orbit.view, event.clientX - orbit.clientX, event.clientY - orbit.clientY);
    this.queueViewRefresh(orbit.pivot);
  };
  private readonly handlePointerStop = (event: PointerEvent) => {
    if (!this.orbitPointer || this.orbitPointer.pointerId !== event.pointerId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    this.orbitPointer = null;
    delete this.app.canvas.dataset.orbiting;
    if (this.app.canvas.hasPointerCapture?.(event.pointerId)) this.app.canvas.releasePointerCapture(event.pointerId);
  };
  private readonly handleAuxClick = (event: MouseEvent) => {
    if (event.button === 1) event.preventDefault();
  };

  private constructor(host: HTMLElement, viewport: Viewport, app: Application, experience: StageExperience) {
    this.host = host;
    this.viewport = viewport;
    this.app = app;
    this.experience = experience;
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
    app.canvas.addEventListener("pointerdown", instance.handlePointerDown, true);
    app.canvas.addEventListener("pointermove", instance.handlePointerMove, true);
    app.canvas.addEventListener("pointerup", instance.handlePointerStop, true);
    app.canvas.addEventListener("pointercancel", instance.handlePointerStop, true);
    app.canvas.addEventListener("auxclick", instance.handleAuxClick, true);
    host.append(app.canvas);
    app.stage.addChild(viewport);
    viewport.eventMode = "static";
    viewport.drag({ pressDrag: true, wheel: false })
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
    this.drawAtmosphere();
    this.drawGrammarScenery();
    this.drawNarrativeRelations();
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
    // A chapter-rail focus may still be easing when the reader changes
    // grammar. The old interpolation uses a different coordinate system and
    // can otherwise pull a fresh loop/constellation shot back to an off-screen
    // or all-book camera after this method has chosen its local opening shot.
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
    // The opening shot is a reading surface, not a miniature of the whole
    // book.  Keep only the next readable run in view; the full river remains
    // one click away through fit(), pan and the chapter rail.
    // A detailed scene view should open as a readable stretch of narrative,
    // not as a compressed inventory. The rest of the book remains available
    // through pan, zoom and the permanent chapter rail.
    const stageGrammar = this.layout.grammar === "stage";
    const radialGrammar = this.layout.grammar === "loop" || this.layout.grammar === "constellation";
    const visibleCount = stageGrammar
      ? 3
      : Math.max(5, Math.min(7, Math.floor(availableWidth / 172)));
    const windowed = primary.slice(start, Math.min(primary.length, start + visibleCount));
    const points = windowed
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
    // Circular and stellar grammars deliberately place chapters across wide
    // spatial fields. Their opening shot must favour a readable local orbit;
    // the full constellation remains an explicit `fit()` action.
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
    this.app.canvas.removeEventListener("pointerdown", this.handlePointerDown, true);
    this.app.canvas.removeEventListener("pointermove", this.handlePointerMove, true);
    this.app.canvas.removeEventListener("pointerup", this.handlePointerStop, true);
    this.app.canvas.removeEventListener("pointercancel", this.handlePointerStop, true);
    this.app.canvas.removeEventListener("auxclick", this.handleAuxClick, true);
    this.viewport.destroy({ children: true });
    this.app.destroy(true, { children: true });
    this.anchorListener = null;
    this.contextLostListener = null;
  }

  private tick(deltaMs: number): void {
    this.elapsed += deltaMs;
    if (this.animation) {
      this.animation.elapsed = Math.min(this.animation.duration, this.animation.elapsed + deltaMs);
      const progress = this.animation.elapsed / this.animation.duration;
      const eased = 1 - Math.pow(1 - progress, 4);
      const x = lerp(this.animation.from.x, this.animation.to.x, eased);
      const y = lerp(this.animation.from.y, this.animation.to.y, eased);
      const scale = lerp(this.animation.from.scale, this.animation.to.scale, eased);
      this.viewport.moveCenter(x, y);
      this.viewport.setZoom(scale, true);
      if (progress >= 1) this.animation = null;
    }
    this.syncParallax();
    this.syncRelationLod();
    const revision = `${this.viewport.x.toFixed(1)}:${this.viewport.y.toFixed(1)}:${this.viewport.scale.x.toFixed(3)}`;
    if (revision !== this.lastViewport) {
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
    this.primaryRelations = null;
    this.secondaryRelations = null;
    for (const layer of [this.far, this.mid, this.near]) {
      const children = layer.removeChildren();
      children.forEach((child) => child.destroy({ children: true }));
    }
  }

  private drawAtmosphere(): void {
    const atmosphere = new Graphics();
    const seed = this.projection ? seedFrom(this.projection.layout_seed) : 1;
    // The field is a shallow room of planes, cut-lines and cast shadows. It
    // avoids decorative star/bokeh fields so depth has a structural reason.
    const horizon = ORIGIN.y - 410;
    const atmosphereStrength = this.experience.depth === "deep" ? 1 : this.experience.depth === "balanced" ? 0.76 : 0.38;
    const planeCount = this.experience.quality === "efficient" ? 6 : 10;
    const rayCount = this.experience.quality === "efficient" ? 10 : 18;
    for (let index = 0; index < planeCount; index += 1) {
      const depth = index / planeCount;
      const y = horizon + depth * 1560;
      const inset = 120 + depth * 340;
      const skew = (pseudo(seed + index * 19) - 0.5) * 250;
      const color = index % 3 === 0 ? this.palette.core : index % 3 === 1 ? this.palette.canon : this.palette.branch;
      atmosphere.poly([
        inset, y - 88 - skew * 0.06,
        WORLD_WIDTH - inset, y - 168 + skew * 0.08,
        WORLD_WIDTH - inset - 180, y + 102,
        inset + 180, y + 176,
      ]).fill({ color, alpha: (0.012 + depth * 0.009) * atmosphereStrength }).stroke({ color: this.palette.label, width: 1, alpha: (0.02 + depth * 0.012) * atmosphereStrength });
    }
    for (let index = 0; index < rayCount; index += 1) {
      const left = 80 + pseudo(seed + index * 37) * (WORLD_WIDTH - 720);
      const rise = 120 + pseudo(seed + index * 53) * 620;
      const span = 260 + pseudo(seed + index * 71) * 820;
      const color = index % 4 === 0 ? this.palette.canon : this.palette.core;
      atmosphere.moveTo(left, WORLD_HEIGHT - 130)
        .lineTo(left + span * 0.48, horizon + rise)
        .lineTo(left + span, WORLD_HEIGHT - 130)
        .stroke({ color, width: 1, alpha: (0.022 + pseudo(seed + index) * 0.022) * atmosphereStrength });
    }
    const grammar = this.layout?.grammar || "spine";
    const bandColor = grammar === "braid" ? this.palette.branch : grammar === "strata" ? this.palette.core : this.palette.canon;
    atmosphere.poly([
      0, ORIGIN.y + 760,
      WORLD_WIDTH * 0.28, ORIGIN.y + 360,
      WORLD_WIDTH * 0.76, ORIGIN.y + 520,
      WORLD_WIDTH, ORIGIN.y + 1020,
      WORLD_WIDTH, WORLD_HEIGHT,
      0, WORLD_HEIGHT,
    ]).fill({ color: bandColor, alpha: 0.045 * atmosphereStrength });
    this.far.addChild(atmosphere);
    const veil = new Graphics();
    veil.poly([
      ORIGIN.x - 1680, ORIGIN.y - 720,
      ORIGIN.x + 1540, ORIGIN.y - 940,
      ORIGIN.x + 1880, ORIGIN.y + 320,
      ORIGIN.x - 1420, ORIGIN.y + 560,
    ]).fill({ color: this.palette.deep, alpha: 0.2 * atmosphereStrength });
    this.far.addChild(veil);
  }

  private drawGrammarScenery(): void {
    if (!this.layout || !this.projection) return;
    const grammar = this.layout.grammar;
    const silhouette = new Graphics();
    const shadow = new Graphics();
    const frame = this.narrativeFrame();
    const center = { x: frame.centerX, y: frame.centerY };
    if (grammar === "loop") {
      const width = Math.max(620, frame.width * 0.48);
      const height = Math.max(250, frame.height * 0.28);
      shadow.ellipse(center.x + 18, center.y + 28, width, height).stroke({ color: this.palette.shadow, width: 34, alpha: 0.34 });
      silhouette.ellipse(center.x, center.y, width, height).stroke({ color: this.palette.canon, width: 7, alpha: 0.4 });
    } else if (grammar === "constellation") {
      const primaryCount = this.projection.nodes.filter((node) => node.type === "chapter" || node.type === "scene").length;
      const families = this.projectedPrimaryGroups(constellationClusterSize(primaryCount));
      families.forEach((family, index) => {
        const width = Math.max(260, family.width + 260);
        const height = Math.max(170, family.height + 190);
        // Nested translucent ellipses read as a shallow stellar cloud without
        // bitmap blur. Offset cores preserve near/far depth while orbiting.
        shadow.ellipse(family.centerX + 24, family.centerY + 30, width * 0.64, height * 0.64)
          .fill({ color: this.palette.shadow, alpha: 0.14 })
          .stroke({ color: this.palette.shadow, width: 34, alpha: 0.18 });
        silhouette.ellipse(family.centerX - width * 0.04, family.centerY + height * 0.03, width * 0.58, height * 0.54)
          .fill({ color: index % 2 ? this.palette.branch : this.palette.core, alpha: 0.052 })
          .stroke({ color: index % 2 ? this.palette.branch : this.palette.core, width: 2, alpha: 0.26 });
        silhouette.ellipse(family.centerX + width * 0.05, family.centerY - height * 0.025, width * 0.43, height * 0.39)
          .fill({ color: this.palette.canon, alpha: 0.055 })
          .stroke({ color: this.palette.canon, width: 1.4, alpha: 0.22 });
        silhouette.ellipse(family.centerX - width * 0.02, family.centerY, width * 0.22, height * 0.2)
          .fill({ color: this.palette.label, alpha: 0.045 })
          .stroke({ color: this.palette.label, width: 1, alpha: 0.18 });
        const starCount = this.experience.quality === "efficient" ? 18 : 32;
        for (let star = 0; star < starCount; star += 1) {
          const theta = star * 2.399963 + index * 0.73;
          const unitRadius = Math.sqrt((star + 1) / starCount);
          const starX = family.centerX + Math.cos(theta) * width * 0.48 * unitRadius;
          const starY = family.centerY + Math.sin(theta) * height * 0.42 * unitRadius;
          const bright = star % 11 === 0;
          silhouette.circle(starX, starY, bright ? 2.8 : star % 4 === 0 ? 1.65 : 0.9)
            .fill({ color: star % 3 === 0 ? this.palette.canon : this.palette.label, alpha: bright ? 0.58 : 0.3 });
          if (bright) {
            silhouette.moveTo(starX - 7, starY).lineTo(starX + 7, starY)
              .moveTo(starX, starY - 5).lineTo(starX, starY + 5)
              .stroke({ color: this.palette.label, width: 1, alpha: 0.32 });
          }
        }
        // This partial dust lane restores the concentric sweep of the early
        // v0.9 design while keeping every stellar family independent.
        silhouette.moveTo(family.centerX - width * 0.48, family.centerY + height * 0.07)
          .bezierCurveTo(
            family.centerX - width * 0.2,
            family.centerY - height * 0.36,
            family.centerX + width * 0.3,
            family.centerY - height * 0.24,
            family.centerX + width * 0.5,
            family.centerY + height * 0.1,
          )
          .stroke({ color: index % 2 ? this.palette.core : this.palette.branch, width: 5, alpha: 0.16 });
        if (index) {
          const previous = families[index - 1];
          const dx = family.centerX - previous.centerX;
          const dy = family.centerY - previous.centerY;
          silhouette.moveTo(previous.centerX, previous.centerY)
            .bezierCurveTo(
              previous.centerX + dx * 0.36,
              previous.centerY + dy * 0.18 - 46,
              family.centerX - dx * 0.34,
              family.centerY - dy * 0.18 + 46,
              family.centerX,
              family.centerY,
            )
            .stroke({ color: this.palette.canon, width: 5, alpha: 0.11 });
          silhouette.moveTo(previous.centerX, previous.centerY)
            .bezierCurveTo(
              previous.centerX + dx * 0.32,
              previous.centerY + dy * 0.2 - 22,
              family.centerX - dx * 0.3,
              family.centerY - dy * 0.2 + 22,
              family.centerX,
              family.centerY,
            )
            .stroke({ color: this.palette.label, width: 1, alpha: 0.18 });
        }
      });
    } else if (grammar === "strata") {
      for (let index = 0; index < 5; index += 1) {
        const width = Math.max(1080, Math.min(3600, frame.width * 0.6)) - index * 140;
        const y = center.y - 290 + index * 146 + (index - 2) * Math.min(90, frame.height * 0.025);
        const inset = 78 + index * 16;
        shadow.poly([center.x - width / 2 + 18, y + 20, center.x + width / 2 + 20, y - 22, center.x + width / 2 - inset + 20, y + 84, center.x - width / 2 + inset + 18, y + 126]).fill({ color: this.palette.shadow, alpha: 0.34 });
        silhouette.poly([center.x - width / 2, y, center.x + width / 2, y - 42, center.x + width / 2 - inset, y + 64, center.x - width / 2 + inset, y + 106]).fill({ color: this.palette.core, alpha: 0.07 + index * 0.018 }).stroke({ color: this.palette.label, width: 1, alpha: 0.22 });
        silhouette.poly([center.x - width / 2 + inset, y + 106, center.x + width / 2 - inset, y + 64, center.x + width / 2 - inset, y + 81, center.x - width / 2 + inset, y + 123]).fill({ color: this.palette.canon, alpha: 0.08 });
      }
    } else if (grammar === "braid") {
      for (const side of [-1, 1]) {
        const path = braidPath(side, frame);
        shadow.poly(path.map((value, index) => index % 2 === 0 ? value + 18 : value + 24)).stroke({ color: this.palette.shadow, width: 48, alpha: 0.27 });
        silhouette.poly(path).stroke({ color: side < 0 ? this.palette.core : this.palette.branch, width: 11, alpha: 0.34 });
      }
    } else if (grammar === "stage") {
      const primaryCount = this.projection.nodes.filter((node) => node.type === "chapter" || node.type === "scene").length;
      const acts = this.projectedPrimaryGroups(stageActSize(primaryCount));
      acts.forEach((act, index) => {
        // The projection can span an entire chapter act even while the camera
        // shows only its opening beats. Cap the scenic shell so it remains a
        // stage around the nodes instead of a polygon covering the viewport.
        const halfWidth = Math.max(300, Math.min(620, act.width / 2 + 165));
        const halfHeight = Math.max(126, Math.min(250, act.height / 2 + 102));
        const backY = act.centerY - halfHeight * 0.76;
        const frontY = act.centerY + halfHeight;
        const archTop = backY - Math.max(150, halfHeight * 0.92);
        const wingWidth = Math.max(54, halfWidth * 0.13);
        shadow.poly([
          act.centerX - halfWidth + 20, backY + 26,
          act.centerX + halfWidth + 20, backY + 6,
          act.centerX + halfWidth * 0.82 + 20, frontY + 26,
          act.centerX - halfWidth * 0.82 + 20, frontY + 42,
        ]).fill({ color: this.palette.shadow, alpha: 0.27 });
        silhouette.poly([
          act.centerX - halfWidth, backY,
          act.centerX + halfWidth, backY - 20,
          act.centerX + halfWidth * 0.82, frontY,
          act.centerX - halfWidth * 0.82, frontY + 16,
        ]).fill({ color: index % 2 ? this.palette.branch : this.palette.core, alpha: 0.13 })
          .stroke({ color: this.palette.canon, width: 2, alpha: 0.42 });
        // Proscenium and curtain wings make the scenery a recognisable playing
        // space instead of a generic quadrilateral behind the narrative route.
        silhouette.poly([
          act.centerX - halfWidth, backY,
          act.centerX - halfWidth - wingWidth, backY + 30,
          act.centerX - halfWidth - wingWidth * 0.72, archTop + 28,
          act.centerX - halfWidth + wingWidth * 1.42, archTop + 12,
          act.centerX - halfWidth + wingWidth * 1.82, backY + 12,
        ]).fill({ color: index % 2 ? this.palette.branch : this.palette.core, alpha: 0.2 })
          .stroke({ color: this.palette.canon, width: 2, alpha: 0.34 });
        silhouette.poly([
          act.centerX + halfWidth, backY - 20,
          act.centerX + halfWidth + wingWidth, backY + 10,
          act.centerX + halfWidth + wingWidth * 0.72, archTop + 8,
          act.centerX + halfWidth - wingWidth * 1.42, archTop - 8,
          act.centerX + halfWidth - wingWidth * 1.82, backY - 8,
        ]).fill({ color: index % 2 ? this.palette.branch : this.palette.core, alpha: 0.2 })
          .stroke({ color: this.palette.canon, width: 2, alpha: 0.34 });
        silhouette.moveTo(act.centerX - halfWidth + wingWidth * 1.42, archTop + 12)
          .bezierCurveTo(
            act.centerX - halfWidth * 0.22,
            archTop - 54,
            act.centerX + halfWidth * 0.24,
            archTop - 58,
            act.centerX + halfWidth - wingWidth * 1.42,
            archTop - 8,
          )
          .stroke({ color: this.palette.canon, width: 8, alpha: 0.24 });
        // Crossing spotlights remain subtle so labels and interaction nodes are
        // still the brightest objects on the stage.
        silhouette.poly([
          act.centerX - halfWidth * 0.38, archTop + 8,
          act.centerX - halfWidth * 0.28, archTop + 8,
          act.centerX + halfWidth * 0.16, frontY - 4,
          act.centerX - halfWidth * 0.2, frontY + 8,
        ]).fill({ color: this.palette.label, alpha: 0.036 });
        silhouette.poly([
          act.centerX + halfWidth * 0.34, archTop - 8,
          act.centerX + halfWidth * 0.44, archTop - 8,
          act.centerX + halfWidth * 0.2, frontY,
          act.centerX - halfWidth * 0.1, frontY + 10,
        ]).fill({ color: this.palette.canon, alpha: 0.045 });
        for (let board = 1; board < 7; board += 1) {
          const backX = act.centerX - halfWidth + board * (halfWidth * 2 / 7);
          const frontX = act.centerX - halfWidth * 0.82 + board * (halfWidth * 1.64 / 7);
          silhouette.moveTo(backX, backY - board * 2.8)
            .lineTo(frontX, frontY + 16 - board * 2.2)
            .stroke({ color: this.palette.label, width: 1, alpha: 0.1 });
        }
        silhouette.moveTo(act.centerX - halfWidth * 0.82, frontY + 16)
          .bezierCurveTo(
            act.centerX - halfWidth * 0.32,
            frontY + 62,
            act.centerX + halfWidth * 0.34,
            frontY + 50,
            act.centerX + halfWidth * 0.82,
            frontY,
          )
          .stroke({ color: this.palette.label, width: 3, alpha: 0.18 });
        for (let light = 0; light < 9; light += 1) {
          const progress = light / 8;
          const x = act.centerX - halfWidth * 0.72 + progress * halfWidth * 1.44;
          const y = frontY + 18 + Math.sin(progress * Math.PI) * 12;
          silhouette.circle(x, y, light % 4 === 0 ? 2.8 : 1.8)
            .fill({ color: light % 3 === 0 ? this.palette.branch : this.palette.canon, alpha: 0.34 });
        }
      });
    } else {
      const route = spinePath(frame);
      shadow.poly(route.map((value, index) => index % 2 === 0 ? value + 18 : value + 22)).stroke({ color: this.palette.shadow, width: 50, alpha: 0.3 });
      silhouette.poly(route).stroke({ color: this.palette.canon, width: 10, alpha: 0.43 });
    }
    this.far.addChild(shadow);
    this.mid.addChild(silhouette);
    this.drawForegroundOccluders(grammar, center);
  }

  private drawNarrativeRelations(): void {
    if (!this.projection || !this.layout) return;
    const primary = new Graphics();
    const secondary = new Graphics();
    const detailProjection = this.projection.level !== "book";
    const globalBackboneGrammar = this.layout.grammar !== "loop" && this.layout.grammar !== "constellation";
    for (const edge of this.projection.edges) {
      const source = this.layout.points.get(edge.source);
      const target = this.layout.points.get(edge.target);
      if (!source || !target) continue;
      const start = this.projectPoint(source);
      const end = this.projectPoint(target);
      const color = edge.type === "branch" || edge.type === "raises" || edge.type === "promise"
        ? this.palette.branch
        : edge.type === "canon" || edge.type === "review"
          ? this.palette.canon
          : edge.type === "workflow"
            ? this.palette.core
            : mix(this.palette.core, this.palette.label, 0.46);
      const backbone = edge.type === "sequence" || edge.type === "bridge";
      // A detail view can contain every scene in the book. Only evidence
      // attached to an explicitly focused node deserves foreground treatment;
      // the rest remains quiet background context until the reader navigates
      // toward it.
      const focusedEvidence = Boolean(this.focusedNodeId) && (
        edge.source === this.focusedNodeId || edge.target === this.focusedNodeId
      );
      const localEvidence = detailProjection && focusedEvidence && !backbone;
      // In a linear grammar the full sequence is the scenery. In a radial
      // grammar that same all-book sequence becomes a bright tangled mesh, so
      // only the foreground SVG's currently visible spine speaks clearly.
      const connection = (backbone && globalBackboneGrammar) || localEvidence ? primary : secondary;
      // A narrative relationship is a route through the field, not a diagram
      // wire. Its stable bend keeps the graph legible across live refreshes.
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const normalX = -dy / distance;
      const normalY = dx / distance;
      const bend = Math.min(220, Math.max(26, distance * (backbone ? 0.11 : 0.18))) * curvePolarity(edge.edge_id);
      const controlA = { x: start.x + dx * 0.34 + normalX * bend, y: start.y + dy * 0.34 + normalY * bend };
      const controlB = { x: end.x - dx * 0.34 + normalX * bend, y: end.y - dy * 0.34 + normalY * bend };
      // The SVG foreground layer redraws nearby detail relations when both
      // endpoints are in view. Keep this GPU layer quiet so distant evidence
      // reads as atmosphere rather than a thicket of wires across the book.
      const width = edge.type === "branch" ? 2.3 : backbone ? 2.8 : localEvidence ? 1.15 : 1.1;
      const alpha = backbone ? (detailProjection ? 0.64 : 0.48) : localEvidence ? 0.38 : edge.strength > 0.7 ? 0.16 : 0.065;
      connection.moveTo(start.x, start.y).bezierCurveTo(controlA.x, controlA.y, controlB.x, controlB.y, end.x, end.y).stroke({ color, width, alpha });
    }
    this.primaryRelations = primary;
    this.secondaryRelations = secondary;
    this.mid.addChild(primary, secondary);
  }

  private drawForegroundOccluders(grammar: SpatialNarrativeProjection["spatial_grammar"], center: { x: number; y: number }): void {
    if (this.experience.depth === "flat") return;
    const foreground = new Graphics();
    const left = center.x - 1480;
    const right = center.x + 1480;
    const opacity = this.experience.depth === "deep" ? 1 : 0.6;
    if (grammar === "strata" || grammar === "stage") {
      foreground.poly([left, center.y + 490, right, center.y + 318, right, center.y + 690, left, center.y + 862]).fill({ color: this.palette.deep, alpha: 0.3 * opacity });
      foreground.poly([left, center.y + 490, right, center.y + 318]).stroke({ color: this.palette.canon, width: 2, alpha: 0.16 * opacity });
    } else {
      foreground.poly([left, center.y + 480, center.x - 420, center.y + 255, center.x + 160, center.y + 860, left, center.y + 1040]).fill({ color: this.palette.deep, alpha: 0.25 * opacity });
      foreground.poly([right, center.y + 480, center.x + 420, center.y + 255, center.x - 160, center.y + 860, right, center.y + 1040]).fill({ color: this.palette.deep, alpha: 0.22 * opacity });
    }
    this.near.addChild(foreground);
  }

  private narrativeFrame(): NarrativeFrame {
    const projected = (this.projection?.nodes || [])
      .filter((node) => node.type === "chapter" || node.type === "scene")
      .map((node) => this.layout?.points.get(node.node_id))
      .filter((point): point is WorldPoint => Boolean(point))
      .map((point) => this.projectPoint(point));
    if (!projected.length) return { centerX: ORIGIN.x, centerY: ORIGIN.y, width: 1880, height: 900 };
    const minX = Math.min(...projected.map((point) => point.x));
    const maxX = Math.max(...projected.map((point) => point.x));
    const minY = Math.min(...projected.map((point) => point.y));
    const maxY = Math.max(...projected.map((point) => point.y));
    return {
      centerX: (minX + maxX) / 2,
      centerY: (minY + maxY) / 2,
      width: Math.max(1200, maxX - minX + 520),
      height: Math.max(720, maxY - minY + 420),
    };
  }

  private projectedPrimaryGroups(groupSize: number): Array<NarrativeFrame> {
    if (!this.projection || !this.layout) return [];
    const primary = this.projection.nodes
      .filter((node) => node.type === "chapter" || node.type === "scene")
      .sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
    const result: Array<NarrativeFrame> = [];
    for (let index = 0; index < primary.length; index += Math.max(1, groupSize)) {
      const points = primary
        .slice(index, index + groupSize)
        .map((node) => this.layout?.points.get(node.node_id))
        .filter((point): point is WorldPoint => Boolean(point))
        .map((point) => this.projectPoint(point));
      if (!points.length) continue;
      const minX = Math.min(...points.map((point) => point.x));
      const maxX = Math.max(...points.map((point) => point.x));
      const minY = Math.min(...points.map((point) => point.y));
      const maxY = Math.max(...points.map((point) => point.y));
      result.push({
        centerX: (minX + maxX) / 2,
        centerY: (minY + maxY) / 2,
        width: Math.max(1, maxX - minX),
        height: Math.max(1, maxY - minY),
      });
    }
    return result;
  }

  private syncRelationLod(): void {
    if (!this.primaryRelations || !this.secondaryRelations) return;
    const scale = this.viewport.scale.x;
    const focused = Boolean(this.focusedNodeId);
    this.primaryRelations.alpha = scale >= 0.42 ? 1 : scale >= 0.22 ? 0.62 : 0.38;
    this.secondaryRelations.alpha = focused ? 0.26 : scale >= 0.82 ? 0.15 : scale >= 0.58 ? 0.06 : scale >= 0.3 ? 0.025 : 0.01;
  }

  private tideOffset(node: SpatialNarrativeProjection["nodes"][number], base: { x: number; y: number }): { x: number; y: number } {
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
      const drift = node && this.effectiveMotion() === "full" ? nodeDrift(node, this.elapsed / 1000) : { x: 0, y: 0 };
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
    // Changing yaw/pitch should orbit a narrative landmark, not push the
    // entire book out of frame. This preserves the reader's spatial anchor.
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
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return "reduced";
    return this.experience.motion;
  }
}

function nodeDrift(node: SpatialNarrativeProjection["nodes"][number], time: number): { x: number; y: number } {
  if (!(["current", "blocked", "alternative", "queued"].includes(node.status))) return { x: 0, y: 0 };
  const phase = (hashNode(node.node_id, 71) % 360) * (Math.PI / 180);
  const amplitude = node.status === "current" ? 3.4 : node.status === "blocked" ? 2.5 : node.status === "queued" ? 2.1 : 1.45;
  const speed = node.status === "current" ? 1.25 : 0.74;
  return {
    x: Math.sin(time * speed + phase) * amplitude,
    y: Math.cos(time * speed * 0.82 + phase) * amplitude * 0.58,
  };
}

function spinePath(frame: NarrativeFrame): number[] {
  const length = Math.max(1200, frame.width);
  const start = frame.centerX - length / 2;
  const points: number[] = [];
  for (let index = 0; index <= 32; index += 1) {
    const progress = index / 32;
    points.push(start + length * progress, frame.centerY + Math.sin(progress * Math.PI * 1.1) * Math.min(180, frame.height * 0.18) - progress * Math.min(160, frame.height * 0.13));
  }
  return points;
}

function braidPath(side: number, frame: NarrativeFrame): number[] {
  const points: number[] = [];
  const length = Math.max(1500, frame.width);
  for (let index = 0; index <= 36; index += 1) {
    const progress = index / 36;
    points.push(frame.centerX - length / 2 + progress * length, frame.centerY + side * Math.sin(progress * Math.PI * 2.6) * Math.min(210, frame.height * 0.24) - progress * Math.min(150, frame.height * 0.14));
  }
  return points;
}

function seedFrom(value: string): number {
  let state = 2166136261;
  for (const character of value) state = Math.imul(state ^ character.charCodeAt(0), 16777619);
  return state >>> 0;
}

function hashNode(value: string, salt: number): number {
  let state = 2166136261 ^ salt;
  for (const character of value) state = Math.imul(state ^ character.charCodeAt(0), 16777619);
  return state >>> 0;
}

function curvePolarity(value: string): number {
  return hashNode(value, 191) % 2 ? 1 : -1;
}

function pseudo(seed: number): number {
  let value = seed >>> 0;
  value ^= value << 13;
  value ^= value >>> 17;
  value ^= value << 5;
  return (value >>> 0) / 4294967296;
}

function lerp(start: number, end: number, ratio: number): number {
  return start + (end - start) * ratio;
}

function readStageExperience(): StageExperience {
  const root = document.documentElement.dataset;
  return {
    motion: root.arcvellumMotion === "still" || root.arcvellumMotion === "reduced" ? root.arcvellumMotion : "full",
    depth: root.arcvellumDepth === "deep" || root.arcvellumDepth === "flat" ? root.arcvellumDepth : "balanced",
    quality: root.arcvellumQuality === "high" || root.arcvellumQuality === "efficient" ? root.arcvellumQuality : "auto",
  };
}

function rendererResolution(quality: OrreryRenderQuality): number {
  const deviceResolution = window.devicePixelRatio || 1;
  if (quality === "efficient") return 1;
  if (quality === "high") return Math.min(deviceResolution, 2);
  return Math.min(deviceResolution, 1.5);
}

function readPalette(host: HTMLElement): ScenePalette {
  const styles = getComputedStyle(host);
  return {
    core: cssColor(styles.getPropertyValue("--orrery-core"), DEFAULT_PALETTE.core),
    canon: cssColor(styles.getPropertyValue("--orrery-canon"), DEFAULT_PALETTE.canon),
    branch: cssColor(styles.getPropertyValue("--orrery-branch"), DEFAULT_PALETTE.branch),
    warning: cssColor(styles.getPropertyValue("--orrery-warning"), DEFAULT_PALETTE.warning),
    label: cssColor(styles.getPropertyValue("--orrery-label"), DEFAULT_PALETTE.label),
    deep: cssColor(styles.getPropertyValue("--orrery-deep"), DEFAULT_PALETTE.deep),
    shadow: DEFAULT_PALETTE.shadow,
  };
}

function cssColor(value: string, fallback: number): number {
  const text = value.trim();
  const hex = text.match(/^#([\da-f]{3}|[\da-f]{6})$/i)?.[1];
  if (hex) {
    const expanded = hex.length === 3 ? hex.split("").map((item) => item + item).join("") : hex;
    return Number.parseInt(expanded, 16);
  }
  const rgb = text.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (rgb) return (Number(rgb[1]) << 16) | (Number(rgb[2]) << 8) | Number(rgb[3]);
  return fallback;
}

function mix(first: number, second: number, ratio: number): number {
  const amount = Math.max(0, Math.min(1, ratio));
  const channel = (shift: number) => Math.round((((first >> shift) & 0xff) * (1 - amount)) + (((second >> shift) & 0xff) * amount));
  return (channel(16) << 16) | (channel(8) << 8) | channel(0);
}
