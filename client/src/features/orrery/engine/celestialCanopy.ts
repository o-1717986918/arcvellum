import { Graphics, type Container } from "pixi.js";
import type { SpatialLayout, SpatialNarrativeProjection } from "@/types/spatial";
import { NARRATIVE_STAGE } from "./parallaxProjection";
import { pseudo, seedFrom } from "./renderMath";
import type { NarrativeFrame, ScenePalette, StageExperience } from "./renderModel";

interface CanopyLayers {
  far: Container;
  mid: Container;
  near: Container;
}

interface CelestialCanopyOptions {
  layers: CanopyLayers;
  layout: SpatialLayout;
  projection: SpatialNarrativeProjection;
  palette: ScenePalette;
  experience: StageExperience;
  frame: NarrativeFrame;
}

/**
 * A deterministic, camera-spanning sky volume. It borrows the useful visual
 * grammar of the two observatory experiments without introducing a second GL
 * renderer: stellar magnitude, nebula depth, a milky-way current and sparse
 * armillary guides are all drawn into the existing Pixi parallax layers.
 */
export function drawCelestialCanopy(options: CelestialCanopyOptions): void {
  const { layers, projection, palette, experience, frame } = options;
  const strength = experience.depth === "deep" ? 1 : experience.depth === "balanced" ? 0.78 : 0.46;
  const seed = seedFrom(projection.layout_seed);

  drawSkyWash(layers.far, frame, palette, seed, strength);
  drawNebulaVolume(layers.far, frame, palette, seed, strength, experience);
  drawMilkyWay(layers.far, layers.mid, frame, palette, seed, strength, experience);
  drawAuroraCurrents(layers.far, layers.mid, frame, palette, seed, strength);
  drawStarVolume(layers, frame, palette, seed, strength, experience);
  drawCelestialScaffolding(layers.far, frame, palette, seed, strength);
}

function drawSkyWash(
  target: Container,
  frame: NarrativeFrame,
  palette: ScenePalette,
  seed: number,
  strength: number,
): void {
  const wash = new Graphics();
  const width = Math.max(3800, frame.width * 1.36);
  const height = Math.max(2400, frame.height * 2.1);
  const left = frame.centerX - width / 2;
  const top = frame.centerY - height / 2;
  wash.rect(left, top, width, height).fill({ color: palette.deep, alpha: 0.24 * strength });

  for (let index = 0; index < 7; index += 1) {
    const progress = index / 6;
    const y = top + height * (0.08 + progress * 0.84);
    const drift = (pseudo(seed + index * 43) - 0.5) * height * 0.12;
    wash.moveTo(left - 80, y)
      .bezierCurveTo(
        left + width * 0.28, y - height * 0.12 + drift,
        left + width * 0.7, y + height * 0.1 - drift,
        left + width + 80, y - height * 0.03,
      )
      .stroke({ color: index % 2 ? palette.core : palette.canon, width: 1.2, alpha: (0.025 + progress * 0.014) * strength });
  }
  target.addChild(wash);
}

function drawNebulaVolume(
  target: Container,
  frame: NarrativeFrame,
  palette: ScenePalette,
  seed: number,
  strength: number,
  experience: StageExperience,
): void {
  const nebula = new Graphics();
  const width = Math.max(3800, frame.width * 1.3);
  const height = Math.max(2300, frame.height * 1.9);
  const cloudCount = experience.quality === "efficient" ? 5 : 9;
  // Avoid a neutral label-colour cloud becoming an opaque white disc when
  // several deterministic shells overlap. Nebulae remain chromatic context.
  const colors = [palette.core, palette.canon, palette.branch];

  for (let cloud = 0; cloud < cloudCount; cloud += 1) {
    const centerX = frame.centerX + (pseudo(seed + cloud * 73) - 0.5) * width * 0.92;
    const centerY = frame.centerY + (pseudo(seed + cloud * 97) - 0.5) * height * 0.58;
    const radiusX = width * (0.08 + pseudo(seed + cloud * 109) * 0.13);
    const radiusY = height * (0.05 + pseudo(seed + cloud * 131) * 0.11);
    const color = colors[cloud % colors.length];
    for (let shell = 4; shell >= 0; shell -= 1) {
      const scale = 0.48 + shell * 0.17;
      const offsetX = (pseudo(seed + cloud * 149 + shell * 17) - 0.5) * radiusX * 0.36;
      const offsetY = (pseudo(seed + cloud * 163 + shell * 23) - 0.5) * radiusY * 0.34;
      nebula.ellipse(centerX + offsetX, centerY + offsetY, radiusX * scale, radiusY * scale)
        .stroke({
          color,
          width: Math.max(18, radiusY * (0.08 + (4 - shell) * 0.026)),
          alpha: (0.008 + (4 - shell) * 0.004) * strength,
        });
    }
  }
  target.addChild(nebula);
}

function drawMilkyWay(
  farTarget: Container,
  midTarget: Container,
  frame: NarrativeFrame,
  palette: ScenePalette,
  seed: number,
  strength: number,
  experience: StageExperience,
): void {
  const width = Math.max(4200, frame.width * 1.42);
  const left = frame.centerX - width / 2;
  const startY = frame.centerY + Math.min(480, frame.height * 0.18);
  const endY = frame.centerY - Math.min(360, frame.height * 0.16);
  const controls = {
    c1x: left + width * 0.27,
    c1y: frame.centerY - Math.max(620, frame.height * 0.42),
    c2x: left + width * 0.69,
    c2y: frame.centerY + Math.max(520, frame.height * 0.34),
  };
  const haze = new Graphics();
  for (const [lineWidth, alpha, color] of [
    [310, 0.021, palette.core],
    [156, 0.038, palette.canon],
    [48, 0.062, palette.label],
  ] as const) {
    haze.moveTo(left, startY)
      .bezierCurveTo(controls.c1x, controls.c1y, controls.c2x, controls.c2y, left + width, endY)
      .stroke({ color, width: lineWidth, alpha: alpha * strength });
  }
  farTarget.addChild(haze);

  const dust = new Graphics();
  const count = experience.quality === "efficient" ? 160 : 360;
  for (let index = 0; index < count; index += 1) {
    const t = (index + pseudo(seed + index * 31)) / count;
    const point = cubicPoint(
      { x: left, y: startY },
      { x: controls.c1x, y: controls.c1y },
      { x: controls.c2x, y: controls.c2y },
      { x: left + width, y: endY },
      t,
    );
    const spread = (pseudo(seed + index * 47) - 0.5) * (90 + Math.sin(t * Math.PI) * 160);
    const x = point.x + (pseudo(seed + index * 59) - 0.5) * 54;
    const y = point.y + spread;
    const bright = pseudo(seed + index * 71) > 0.94;
    dust.circle(x, y, bright ? 1.9 : 0.65)
      .fill({ color: index % 7 === 0 ? palette.canon : palette.label, alpha: (bright ? 0.82 : 0.34) * strength });
  }
  midTarget.addChild(dust);
}

function drawAuroraCurrents(
  farTarget: Container,
  midTarget: Container,
  frame: NarrativeFrame,
  palette: ScenePalette,
  seed: number,
  strength: number,
): void {
  const width = Math.max(4400, frame.width * 1.48);
  const left = frame.centerX - width / 2;
  const height = Math.max(1800, frame.height * 1.45);
  const veil = new Graphics();
  const filaments = new Graphics();
  for (let band = 0; band < 4; band += 1) {
    const phase = pseudo(seed + band * 281) * Math.PI * 2;
    const baseline = frame.centerY - height * 0.34 + band * height * 0.22;
    const amplitude = height * (0.1 + pseudo(seed + band * 307) * 0.09);
    const color = band % 3 === 0 ? palette.branch : band % 2 ? palette.canon : palette.core;
    veil.moveTo(left, baseline)
      .bezierCurveTo(
        left + width * 0.28, baseline + Math.sin(phase) * amplitude,
        left + width * 0.68, baseline - Math.cos(phase * 0.83) * amplitude,
        left + width, baseline + Math.sin(phase + 1.2) * amplitude * 0.52,
      )
      .stroke({ color, width: 48 + band * 18, alpha: (0.012 + band * 0.003) * strength });
    filaments.moveTo(left, baseline)
      .bezierCurveTo(
        left + width * 0.28, baseline + Math.sin(phase) * amplitude,
        left + width * 0.68, baseline - Math.cos(phase * 0.83) * amplitude,
        left + width, baseline + Math.sin(phase + 1.2) * amplitude * 0.52,
      )
      .stroke({ color, width: 1.1, alpha: (0.09 + band * 0.014) * strength });
  }
  farTarget.addChild(veil);
  midTarget.addChild(filaments);
}

function drawStarVolume(
  layers: CanopyLayers,
  frame: NarrativeFrame,
  palette: ScenePalette,
  seed: number,
  strength: number,
  experience: StageExperience,
): void {
  const fields = [new Graphics(), new Graphics(), new Graphics()];
  const width = Math.max(4000, frame.width * 1.42);
  const height = Math.max(2500, frame.height * 2.05);
  const scaleFactor = Math.max(1, Math.min(4.5, Math.sqrt(width * height / (4200 * 2500))));
  const baseCount = experience.quality === "efficient" ? 520 : 980;
  const starCount = Math.round(baseCount * scaleFactor);
  let state = (seed ^ 0x9e3779b9) >>> 0;
  const random = (): number => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 4294967296;
  };

  for (let index = 0; index < starCount; index += 1) {
    const x = frame.centerX + (random() - 0.5) * width;
    const y = frame.centerY + (random() - 0.5) * height;
    const magnitude = Math.pow(random(), 3.2);
    const depth = random();
    const layer = depth > 0.82 ? 2 : depth > 0.48 ? 1 : 0;
    const bright = magnitude > 0.78;
    const radius = bright ? 2.1 + magnitude * 2.4 : 0.56 + magnitude * 1.3;
    const color = index % 13 === 0 ? palette.canon : index % 8 === 0 ? palette.core : palette.label;
    fields[layer].circle(x, y, radius).fill({ color, alpha: (0.26 + magnitude * 0.7) * strength });
    if (bright) {
      const ray = 5 + magnitude * 9;
      fields[layer].moveTo(x - ray, y).lineTo(x + ray, y)
        .moveTo(x, y - ray * 0.66).lineTo(x, y + ray * 0.66)
        .stroke({ color, width: 0.7 + magnitude * 0.45, alpha: 0.2 + magnitude * 0.3 });
    }
  }
  layers.far.addChild(fields[0]);
  layers.mid.addChild(fields[1]);
  layers.near.addChild(fields[2]);
}

function drawCelestialScaffolding(
  target: Container,
  frame: NarrativeFrame,
  palette: ScenePalette,
  seed: number,
  strength: number,
): void {
  const guides = new Graphics();
  const repeatCount = Math.max(1, Math.min(8, Math.ceil(frame.width / 7600)));
  for (let index = 0; index < repeatCount; index += 1) {
    const progress = repeatCount === 1 ? 0.5 : index / (repeatCount - 1);
    const x = frame.centerX - frame.width * 0.52 + frame.width * 1.04 * progress;
    const y = frame.centerY + (pseudo(seed + index * 191) - 0.5) * Math.max(520, frame.height * 0.64);
    const radius = 420 + pseudo(seed + index * 211) * 460;
    guides.ellipse(x, y, radius * 1.7, radius * 0.54)
      .stroke({ color: index % 2 ? palette.canon : palette.core, width: 1.2, alpha: 0.055 * strength });
    guides.ellipse(x, y, radius * 0.72, radius * 1.28)
      .stroke({ color: palette.label, width: 0.8, alpha: 0.038 * strength });
  }
  target.addChild(guides);
}

function cubicPoint(
  start: { x: number; y: number },
  controlA: { x: number; y: number },
  controlB: { x: number; y: number },
  end: { x: number; y: number },
  t: number,
): { x: number; y: number } {
  const inverse = 1 - t;
  return {
    x: inverse ** 3 * start.x + 3 * inverse ** 2 * t * controlA.x + 3 * inverse * t ** 2 * controlB.x + t ** 3 * end.x,
    y: inverse ** 3 * start.y + 3 * inverse ** 2 * t * controlA.y + 3 * inverse * t ** 2 * controlB.y + t ** 3 * end.y,
  };
}
