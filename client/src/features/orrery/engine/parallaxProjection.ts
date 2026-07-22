import type { WorldPoint } from "@/types/spatial";
import type { OrreryDepth } from "@/services/orreryPreferences";

const ORIGIN = { x: 96000, y: 11000 };
export const DEFAULT_PARALLAX_VIEW: ParallaxView = { yaw: 0, pitch: 0 };
const MAX_YAW = 0.66;
const MAX_PITCH = 0.34;

export interface ParallaxView {
  yaw: number;
  pitch: number;
}

export function normalizeParallaxView(view: ParallaxView = DEFAULT_PARALLAX_VIEW): ParallaxView {
  return { yaw: clamp(view.yaw, -MAX_YAW, MAX_YAW), pitch: clamp(view.pitch, -MAX_PITCH, MAX_PITCH) };
}

/** Translate a middle-drag gesture into the deliberately bounded 2.5D view. */
export function parallaxViewFromDrag(origin: ParallaxView, deltaX: number, deltaY: number): ParallaxView {
  return normalizeParallaxView({
    yaw: origin.yaw + deltaX * 0.0052,
    pitch: origin.pitch - deltaY * 0.0038,
  });
}

export function orientWorldPoint(point: WorldPoint, view: ParallaxView = DEFAULT_PARALLAX_VIEW): WorldPoint {
  const { yaw, pitch } = normalizeParallaxView(view);
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const x = point.x * cosYaw + point.z * sinYaw;
  const depth = point.z * cosYaw - point.x * sinYaw;
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  return {
    x,
    y: point.y * cosPitch - depth * sinPitch,
    z: depth * cosPitch + point.y * sinPitch,
  };
}

export function scenePoint(point: WorldPoint, depth: OrreryDepth = "deep", view: ParallaxView = DEFAULT_PARALLAX_VIEW): { x: number; y: number } {
  const oriented = orientWorldPoint(point, view);
  const zFactor = depth === "deep" ? 1 : depth === "balanced" ? 0.56 : 0.08;
  const xFactor = depth === "deep" ? 1 : depth === "balanced" ? 0.78 : 0.65;
  return {
    // An oblique projection with a bounded yaw/pitch view transform. It keeps
    // the field lightweight while giving middle-drag a genuine camera feel.
    x: ORIGIN.x + oriented.x * 126 * xFactor + oriented.z * 29 * zFactor,
    y: ORIGIN.y + oriented.z * 58 * zFactor - oriented.y * 88,
  };
}

export function depthScale(point: WorldPoint, depth: OrreryDepth, view: ParallaxView): number {
  if (depth === "flat") return 1;
  const oriented = orientWorldPoint(point, view);
  const zFactor = depth === "deep" ? 1 : 0.48;
  return Math.max(0.72, Math.min(1.28, 0.99 + oriented.z * 0.025 * zFactor + oriented.y * 0.012));
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}
