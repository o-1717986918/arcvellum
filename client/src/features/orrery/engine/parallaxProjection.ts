import type { SpatialOrientation, WorldPoint } from "@/types/spatial";
import type { OrreryDepth } from "@/services/orreryPreferences";

const ORIGIN = { x: 96000, y: 11000 };
const YAW_PER_PIXEL = 0.0052;
const PITCH_PER_PIXEL = 0.0038;

export type ParallaxView = SpatialOrientation;

export const IDENTITY_PARALLAX_VIEW: ParallaxView = { x: 0, y: 0, z: 0, w: 1 };
// The opening shot is deliberately oblique: enough depth to read chapter
// clusters, but not so theatrical that labels lose their table-of-contents role.
export const DEFAULT_PARALLAX_VIEW: ParallaxView = viewFromAngles(-0.18, 0.11);

export function normalizeParallaxView(view: ParallaxView = DEFAULT_PARALLAX_VIEW): ParallaxView {
  const length = Math.hypot(view.x, view.y, view.z, view.w);
  if (!Number.isFinite(length) || length < 1e-8) return { ...IDENTITY_PARALLAX_VIEW };
  return {
    x: view.x / length,
    y: view.y / length,
    z: view.z / length,
    w: view.w / length,
  };
}

/** Translate a middle-drag gesture into an unrestricted unit-quaternion orbit. */
export function parallaxViewFromDrag(origin: ParallaxView, deltaX: number, deltaY: number): ParallaxView {
  const yaw = axisAngle({ x: 0, y: 1, z: 0 }, deltaX * YAW_PER_PIXEL);
  const pitch = axisAngle({ x: 1, y: 0, z: 0 }, -deltaY * PITCH_PER_PIXEL);
  return normalizeParallaxView(multiply(pitch, multiply(yaw, normalizeParallaxView(origin))));
}

export function orientWorldPoint(point: WorldPoint, view: ParallaxView = DEFAULT_PARALLAX_VIEW): WorldPoint {
  const q = normalizeParallaxView(view);
  // Quaternion-vector rotation without allocating the inverse quaternion.
  const tx = 2 * (q.y * point.z - q.z * point.y);
  const ty = 2 * (q.z * point.x - q.x * point.z);
  const tz = 2 * (q.x * point.y - q.y * point.x);
  return {
    x: point.x + q.w * tx + (q.y * tz - q.z * ty),
    y: point.y + q.w * ty + (q.z * tx - q.x * tz),
    z: point.z + q.w * tz + (q.x * ty - q.y * tx),
  };
}

export function scenePoint(
  point: WorldPoint,
  depth: OrreryDepth = "deep",
  view: ParallaxView = DEFAULT_PARALLAX_VIEW,
): { x: number; y: number } {
  const oriented = orientWorldPoint(point, view);
  const zFactor = depth === "deep" ? 1 : depth === "balanced" ? 0.56 : 0.08;
  const xFactor = depth === "deep" ? 1 : depth === "balanced" ? 0.78 : 0.65;
  return {
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

export function isSameParallaxView(left: ParallaxView, right: ParallaxView, epsilon = 1e-7): boolean {
  const direct = Math.hypot(left.x - right.x, left.y - right.y, left.z - right.z, left.w - right.w);
  // q and -q represent the same orientation.
  const negated = Math.hypot(left.x + right.x, left.y + right.y, left.z + right.z, left.w + right.w);
  return Math.min(direct, negated) <= epsilon;
}

export function copyParallaxView(target: ParallaxView, source: ParallaxView): void {
  target.x = source.x;
  target.y = source.y;
  target.z = source.z;
  target.w = source.w;
}

export function viewFromAngles(yaw: number, pitch: number): ParallaxView {
  return normalizeParallaxView(
    multiply(
      axisAngle({ x: 1, y: 0, z: 0 }, pitch),
      axisAngle({ x: 0, y: 1, z: 0 }, yaw),
    ),
  );
}

function axisAngle(axis: WorldPoint, angle: number): ParallaxView {
  const half = angle / 2;
  const sine = Math.sin(half);
  return { x: axis.x * sine, y: axis.y * sine, z: axis.z * sine, w: Math.cos(half) };
}

function multiply(left: ParallaxView, right: ParallaxView): ParallaxView {
  return {
    x: left.w * right.x + left.x * right.w + left.y * right.z - left.z * right.y,
    y: left.w * right.y - left.x * right.z + left.y * right.w + left.z * right.x,
    z: left.w * right.z + left.x * right.y - left.y * right.x + left.z * right.w,
    w: left.w * right.w - left.x * right.x - left.y * right.y - left.z * right.z,
  };
}
