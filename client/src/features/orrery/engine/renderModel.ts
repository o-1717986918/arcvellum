import type { OrreryDepth, OrreryMotion, OrreryRenderQuality } from "@/services/orreryPreferences";

export interface ScenePalette {
  core: number;
  canon: number;
  branch: number;
  warning: number;
  label: number;
  deep: number;
  shadow: number;
}

export interface NarrativeFrame {
  centerX: number;
  centerY: number;
  width: number;
  height: number;
}

export interface StageExperience {
  motion: OrreryMotion;
  depth: OrreryDepth;
  quality: OrreryRenderQuality;
}

export const DEFAULT_PALETTE: ScenePalette = {
  core: 0x68b99c,
  canon: 0xc2a45e,
  branch: 0x9184ad,
  warning: 0xd9644d,
  label: 0xedf4f1,
  deep: 0x071713,
  shadow: 0x06130f,
};

export function readStageExperience(): StageExperience {
  const root = document.documentElement.dataset;
  return {
    motion: root.arcvellumMotion === "system"
      || root.arcvellumMotion === "still"
      || root.arcvellumMotion === "reduced"
      ? root.arcvellumMotion
      : "full",
    depth: root.arcvellumDepth === "deep" || root.arcvellumDepth === "flat" ? root.arcvellumDepth : "balanced",
    quality: root.arcvellumQuality === "high" || root.arcvellumQuality === "efficient" ? root.arcvellumQuality : "auto",
  };
}

export function rendererResolution(quality: OrreryRenderQuality): number {
  const deviceResolution = window.devicePixelRatio || 1;
  if (quality === "efficient") return 1;
  if (quality === "high") return Math.min(deviceResolution, 2);
  return Math.min(deviceResolution, 1.5);
}

export function readPalette(host: HTMLElement): ScenePalette {
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

export function cssColor(value: string, fallback: number): number {
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
