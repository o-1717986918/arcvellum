import { Container, Graphics } from "pixi.js";
import type { SpatialLayout, SpatialNarrativeProjection } from "@/types/spatial";
import { constellationClusterSize, stageActSize } from "@/features/orrery/layout/curveProfiles";
import { braidPath, spinePath } from "./renderMath";
import type { NarrativeFrame, ScenePalette, StageExperience } from "./renderModel";

export interface StageLayers {
  far: Container;
  mid: Container;
  near: Container;
}

export interface StageSceneryOptions {
  layers: StageLayers;
  layout: SpatialLayout;
  projection: SpatialNarrativeProjection;
  palette: ScenePalette;
  experience: StageExperience;
  frame: NarrativeFrame;
  primaryGroups(groupSize: number): NarrativeFrame[];
}

export function drawStageScenery(options: StageSceneryOptions): void {
  drawGrammarScenery(options);
}

function drawGrammarScenery(options: StageSceneryOptions): void {
  const { layers, layout, projection, palette, experience, frame, primaryGroups } = options;
  const grammar = layout.grammar;
  const silhouette = new Graphics();
  const shadow = new Graphics();
  const center = { x: frame.centerX, y: frame.centerY };
  if (grammar === "loop") {
    const width = Math.max(620, frame.width * 0.48);
    const height = Math.max(250, frame.height * 0.28);
    shadow.ellipse(center.x + 18, center.y + 28, width, height).stroke({ color: palette.shadow, width: 34, alpha: 0.34 });
    silhouette.ellipse(center.x, center.y, width, height).stroke({ color: palette.canon, width: 7, alpha: 0.4 });
  } else if (grammar === "constellation") {
    const count = projection.nodes.filter((node) => node.type === "chapter" || node.type === "scene").length;
    drawConstellations(silhouette, shadow, primaryGroups(constellationClusterSize(count)), palette, experience);
  } else if (grammar === "strata") {
    drawStrata(silhouette, shadow, frame, palette);
  } else if (grammar === "braid") {
    for (const side of [-1, 1]) {
      const path = braidPath(side, frame);
      shadow.poly(path.map((value, index) => index % 2 === 0 ? value + 18 : value + 24))
        .stroke({ color: palette.shadow, width: 48, alpha: 0.27 });
      silhouette.poly(path).stroke({ color: side < 0 ? palette.core : palette.branch, width: 11, alpha: 0.34 });
    }
  } else if (grammar === "stage") {
    const count = projection.nodes.filter((node) => node.type === "chapter" || node.type === "scene").length;
    drawStages(silhouette, shadow, primaryGroups(stageActSize(count)), palette);
  } else {
    const route = spinePath(frame);
    shadow.poly(route.map((value, index) => index % 2 === 0 ? value + 18 : value + 22))
      .stroke({ color: palette.shadow, width: 50, alpha: 0.3 });
    silhouette.poly(route).stroke({ color: palette.canon, width: 10, alpha: 0.43 });
  }
  layers.far.addChild(shadow);
  layers.mid.addChild(silhouette);
  drawForegroundOccluders(layers.near, grammar, center, palette, experience);
}

function drawConstellations(
  silhouette: Graphics,
  shadow: Graphics,
  families: NarrativeFrame[],
  palette: ScenePalette,
  experience: StageExperience,
): void {
  families.forEach((family, index) => {
    const width = Math.max(260, family.width + 260);
    const height = Math.max(170, family.height + 190);
    // A constellation is an open stellar field, not a planetary system.
    // Closed concentric ellipses visually trapped every chapter inside a
    // decorative ring and competed with the real narrative spine.
    const direction = index % 2 ? -1 : 1;
    const left = family.centerX - width * 0.52;
    const right = family.centerX + width * 0.52;
    const top = family.centerY - height * 0.34 * direction;
    const bottom = family.centerY + height * 0.28 * direction;
    shadow.moveTo(left + 18, bottom + 28)
      .bezierCurveTo(
        family.centerX - width * 0.18, top + 46,
        family.centerX + width * 0.2, bottom - 38,
        right + 18, top + 30,
      ).stroke({ color: palette.shadow, width: Math.max(30, height * 0.18), alpha: 0.12 });
    silhouette.moveTo(left, bottom)
      .bezierCurveTo(
        family.centerX - width * 0.22, top,
        family.centerX + width * 0.18, bottom,
        right, top,
      ).stroke({ color: index % 2 ? palette.branch : palette.core, width: 7, alpha: 0.18 });
    silhouette.moveTo(left + width * 0.08, bottom - height * 0.04)
      .bezierCurveTo(
        family.centerX - width * 0.12, top + height * 0.08,
        family.centerX + width * 0.26, bottom - height * 0.13,
        right - width * 0.06, top + height * 0.05,
      ).stroke({ color: palette.canon, width: 1.4, alpha: 0.24 });
    const starCount = experience.quality === "efficient" ? 24 : 44;
    for (let star = 0; star < starCount; star += 1) {
      const theta = star * 2.399963 + index * 0.73;
      const unitRadius = Math.sqrt((star + 1) / starCount);
      const x = family.centerX + Math.cos(theta) * width * 0.52 * unitRadius;
      const flow = Math.sin((x - family.centerX) / Math.max(1, width) * Math.PI * 1.45 + index) * height * 0.11;
      const y = family.centerY + flow + Math.sin(theta) * height * 0.31 * unitRadius;
      const bright = star % 11 === 0;
      const starColor = star % 7 === 0 ? palette.branch : star % 5 === 0 ? palette.core : star % 3 === 0 ? palette.canon : palette.label;
      silhouette.circle(x, y, bright ? 2.8 : star % 4 === 0 ? 1.65 : 0.9)
        .fill({ color: starColor, alpha: bright ? 0.58 : 0.3 });
      if (bright) {
        silhouette.moveTo(x - 7, y).lineTo(x + 7, y)
          .moveTo(x, y - 5).lineTo(x, y + 5)
          .stroke({ color: palette.label, width: 1, alpha: 0.32 });
      }
    }
    silhouette.moveTo(family.centerX - width * 0.48, family.centerY + height * 0.07 * direction)
      .bezierCurveTo(
        family.centerX - width * 0.2, family.centerY - height * 0.28 * direction,
        family.centerX + width * 0.3, family.centerY + height * 0.2 * direction,
        family.centerX + width * 0.5, family.centerY - height * 0.08 * direction,
      ).stroke({ color: index % 2 ? palette.core : palette.branch, width: 5, alpha: 0.16 });
    if (index) drawConstellationBridge(silhouette, families[index - 1], family, palette);
  });
}

function drawConstellationBridge(
  silhouette: Graphics,
  previous: NarrativeFrame,
  family: NarrativeFrame,
  palette: ScenePalette,
): void {
  const dx = family.centerX - previous.centerX;
  const dy = family.centerY - previous.centerY;
  silhouette.moveTo(previous.centerX, previous.centerY)
    .bezierCurveTo(
      previous.centerX + dx * 0.36, previous.centerY + dy * 0.18 - 46,
      family.centerX - dx * 0.34, family.centerY - dy * 0.18 + 46,
      family.centerX, family.centerY,
    ).stroke({ color: palette.canon, width: 5, alpha: 0.11 });
  silhouette.moveTo(previous.centerX, previous.centerY)
    .bezierCurveTo(
      previous.centerX + dx * 0.32, previous.centerY + dy * 0.2 - 22,
      family.centerX - dx * 0.3, family.centerY - dy * 0.2 + 22,
      family.centerX, family.centerY,
    ).stroke({ color: palette.label, width: 1, alpha: 0.18 });
}

function drawStrata(silhouette: Graphics, shadow: Graphics, frame: NarrativeFrame, palette: ScenePalette): void {
  for (let index = 0; index < 5; index += 1) {
    const width = Math.max(1080, Math.min(3600, frame.width * 0.6)) - index * 140;
    const y = frame.centerY - 290 + index * 146 + (index - 2) * Math.min(90, frame.height * 0.025);
    const inset = 78 + index * 16;
    shadow.poly([frame.centerX - width / 2 + 18, y + 20, frame.centerX + width / 2 + 20, y - 22, frame.centerX + width / 2 - inset + 20, y + 84, frame.centerX - width / 2 + inset + 18, y + 126]).fill({ color: palette.shadow, alpha: 0.34 });
    silhouette.poly([frame.centerX - width / 2, y, frame.centerX + width / 2, y - 42, frame.centerX + width / 2 - inset, y + 64, frame.centerX - width / 2 + inset, y + 106]).fill({ color: palette.core, alpha: 0.07 + index * 0.018 }).stroke({ color: palette.label, width: 1, alpha: 0.22 });
    silhouette.poly([frame.centerX - width / 2 + inset, y + 106, frame.centerX + width / 2 - inset, y + 64, frame.centerX + width / 2 - inset, y + 81, frame.centerX - width / 2 + inset, y + 123]).fill({ color: palette.canon, alpha: 0.08 });
  }
}

function drawStages(silhouette: Graphics, shadow: Graphics, acts: NarrativeFrame[], palette: ScenePalette): void {
  acts.forEach((act, index) => {
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
    ]).fill({ color: palette.shadow, alpha: 0.27 });
    silhouette.poly([
      act.centerX - halfWidth, backY,
      act.centerX + halfWidth, backY - 20,
      act.centerX + halfWidth * 0.82, frontY,
      act.centerX - halfWidth * 0.82, frontY + 16,
    ]).fill({ color: index % 2 ? palette.branch : palette.core, alpha: 0.13 })
      .stroke({ color: palette.canon, width: 2, alpha: 0.42 });
    drawStageWings(silhouette, act, halfWidth, backY, archTop, wingWidth, index, palette);
    silhouette.moveTo(act.centerX - halfWidth + wingWidth * 1.42, archTop + 12)
      .bezierCurveTo(
        act.centerX - halfWidth * 0.22, archTop - 54,
        act.centerX + halfWidth * 0.24, archTop - 58,
        act.centerX + halfWidth - wingWidth * 1.42, archTop - 8,
      ).stroke({ color: palette.canon, width: 8, alpha: 0.24 });
    silhouette.poly([
      act.centerX - halfWidth * 0.38, archTop + 8,
      act.centerX - halfWidth * 0.28, archTop + 8,
      act.centerX + halfWidth * 0.16, frontY - 4,
      act.centerX - halfWidth * 0.2, frontY + 8,
    ]).fill({ color: palette.label, alpha: 0.036 });
    silhouette.poly([
      act.centerX + halfWidth * 0.34, archTop - 8,
      act.centerX + halfWidth * 0.44, archTop - 8,
      act.centerX + halfWidth * 0.2, frontY,
      act.centerX - halfWidth * 0.1, frontY + 10,
    ]).fill({ color: palette.canon, alpha: 0.045 });
    for (let board = 1; board < 7; board += 1) {
      const backX = act.centerX - halfWidth + board * (halfWidth * 2 / 7);
      const frontX = act.centerX - halfWidth * 0.82 + board * (halfWidth * 1.64 / 7);
      silhouette.moveTo(backX, backY - board * 2.8).lineTo(frontX, frontY + 16 - board * 2.2)
        .stroke({ color: palette.label, width: 1, alpha: 0.1 });
    }
    silhouette.moveTo(act.centerX - halfWidth * 0.82, frontY + 16)
      .bezierCurveTo(
        act.centerX - halfWidth * 0.32, frontY + 62,
        act.centerX + halfWidth * 0.34, frontY + 50,
        act.centerX + halfWidth * 0.82, frontY,
      ).stroke({ color: palette.label, width: 3, alpha: 0.18 });
    for (let light = 0; light < 9; light += 1) {
      const progress = light / 8;
      const x = act.centerX - halfWidth * 0.72 + progress * halfWidth * 1.44;
      const y = frontY + 18 + Math.sin(progress * Math.PI) * 12;
      silhouette.circle(x, y, light % 4 === 0 ? 2.8 : 1.8)
        .fill({ color: light % 3 === 0 ? palette.branch : palette.canon, alpha: 0.34 });
    }
  });
}

function drawStageWings(
  silhouette: Graphics,
  act: NarrativeFrame,
  halfWidth: number,
  backY: number,
  archTop: number,
  wingWidth: number,
  index: number,
  palette: ScenePalette,
): void {
  const color = index % 2 ? palette.branch : palette.core;
  silhouette.poly([
    act.centerX - halfWidth, backY,
    act.centerX - halfWidth - wingWidth, backY + 30,
    act.centerX - halfWidth - wingWidth * 0.72, archTop + 28,
    act.centerX - halfWidth + wingWidth * 1.42, archTop + 12,
    act.centerX - halfWidth + wingWidth * 1.82, backY + 12,
  ]).fill({ color, alpha: 0.2 }).stroke({ color: palette.canon, width: 2, alpha: 0.34 });
  silhouette.poly([
    act.centerX + halfWidth, backY - 20,
    act.centerX + halfWidth + wingWidth, backY + 10,
    act.centerX + halfWidth + wingWidth * 0.72, archTop + 8,
    act.centerX + halfWidth - wingWidth * 1.42, archTop - 8,
    act.centerX + halfWidth - wingWidth * 1.82, backY - 8,
  ]).fill({ color, alpha: 0.2 }).stroke({ color: palette.canon, width: 2, alpha: 0.34 });
}

function drawForegroundOccluders(
  target: Container,
  grammar: SpatialNarrativeProjection["spatial_grammar"],
  center: { x: number; y: number },
  palette: ScenePalette,
  experience: StageExperience,
): void {
  if (experience.depth === "flat") return;
  const foreground = new Graphics();
  const left = center.x - 1480;
  const right = center.x + 1480;
  const opacity = experience.depth === "deep" ? 1 : 0.6;
  if (grammar === "strata" || grammar === "stage") {
    foreground.poly([left, center.y + 490, right, center.y + 318, right, center.y + 690, left, center.y + 862]).fill({ color: palette.deep, alpha: 0.3 * opacity });
    foreground.poly([left, center.y + 490, right, center.y + 318]).stroke({ color: palette.canon, width: 2, alpha: 0.16 * opacity });
  } else {
    foreground.poly([left, center.y + 480, center.x - 420, center.y + 255, center.x + 160, center.y + 860, left, center.y + 1040]).fill({ color: palette.deep, alpha: 0.25 * opacity });
    foreground.poly([right, center.y + 480, center.x + 420, center.y + 255, center.x - 160, center.y + 860, right, center.y + 1040]).fill({ color: palette.deep, alpha: 0.22 * opacity });
  }
  target.addChild(foreground);
}
