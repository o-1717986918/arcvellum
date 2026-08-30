import type {
  ReaderWindowMode,
  SpatialWindow,
  SpatialWindowAnchor,
  SpatialWindowKind,
  SpatialWindowPosition,
  SpatialWindowSize,
} from "@/types/spatialWindows";

export const DEFAULT_SIZES: Record<SpatialWindowKind, SpatialWindowSize> = {
  node: { width: 310, height: 330 },
  progress: { width: 334, height: 424 },
  agent: { width: 360, height: 486 },
  reader: { width: 348, height: 540 },
  decisions: { width: 320, height: 272 },
  rules: { width: 456, height: 500 },
  health: { width: 258, height: 290 },
  delivery: { width: 294, height: 282 },
  archive: { width: 720, height: 590 },
  style: { width: 680, height: 570 },
  quality: { width: 660, height: 560 },
  strategy: { width: 620, height: 540 },
  observatory: { width: 690, height: 570 },
  archaeology: { width: 650, height: 550 },
};

const MIN_SIZES: Record<SpatialWindowKind, SpatialWindowSize> = {
  node: { width: 276, height: 270 },
  progress: { width: 286, height: 316 },
  agent: { width: 304, height: 336 },
  reader: { width: 300, height: 370 },
  decisions: { width: 300, height: 224 },
  rules: { width: 360, height: 386 },
  health: { width: 258, height: 240 },
  delivery: { width: 260, height: 210 },
  archive: { width: 520, height: 420 },
  style: { width: 480, height: 400 },
  quality: { width: 460, height: 390 },
  strategy: { width: 440, height: 380 },
  observatory: { width: 500, height: 410 },
  archaeology: { width: 460, height: 390 },
};

export function clampPosition(position: SpatialWindowPosition, size: SpatialWindowSize): SpatialWindowPosition {
  const margin = 12;
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  return {
    left: Math.min(Math.max(margin, position.left), Math.max(margin, viewportWidth - size.width - margin)),
    top: Math.min(Math.max(margin, position.top), Math.max(margin, viewportHeight - size.height - margin)),
  };
}

export function clampSize(kind: SpatialWindowKind, size: SpatialWindowSize): SpatialWindowSize {
  const minimum = MIN_SIZES[kind];
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  return {
    width: Math.round(Math.min(Math.max(minimum.width, size.width), Math.max(minimum.width, viewportWidth - 24))),
    height: Math.round(Math.min(Math.max(minimum.height, size.height), Math.max(minimum.height, viewportHeight - 24))),
  };
}

export function compactSize(kind: SpatialWindowKind): SpatialWindowSize {
  return clampSize(kind, MIN_SIZES[kind]);
}

export function instrumentPosition(
  kind: Exclude<SpatialWindowKind, "node">,
  size: SpatialWindowSize,
  offset: number,
): SpatialWindowPosition {
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  const positions: Record<Exclude<SpatialWindowKind, "node">, SpatialWindowPosition> = {
    progress: { left: viewportWidth - size.width - 30, top: 148 },
    agent: { left: viewportWidth - size.width - 42, top: 122 },
    reader: { left: 82, top: 148 },
    decisions: { left: viewportWidth - size.width - 42, top: 196 },
    rules: { left: viewportWidth - size.width - 52, top: 116 },
    health: { left: 26, top: viewportHeight - size.height - 34 },
    delivery: { left: viewportWidth - size.width - 44, top: 168 },
    archive: { left: Math.round((viewportWidth - size.width) / 2), top: 96 },
    style: { left: Math.round((viewportWidth - size.width) / 2), top: 104 },
    quality: { left: Math.round((viewportWidth - size.width) / 2), top: 104 },
    strategy: { left: 46, top: 112 },
    observatory: { left: Math.round((viewportWidth - size.width) / 2), top: 96 },
    archaeology: { left: 52, top: 104 },
  };
  return clampPosition({ left: positions[kind].left - offset * 12, top: positions[kind].top + offset * 12 }, size);
}

export function readerModeSize(mode: ReaderWindowMode): SpatialWindowSize {
  if (mode === "peek") {
    const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
    const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
    return {
      width: Math.min(356, Math.max(300, viewportWidth - 24)),
      height: Math.min(224, Math.max(190, viewportHeight - 24)),
    };
  }
  if (mode === "reading") return clampSize("reader", { width: 388, height: 640 });
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  return clampSize("reader", { width: viewportWidth - 32, height: viewportHeight - 32 });
}

export function isReaderMode(value: unknown): value is ReaderWindowMode {
  return ["peek", "reading", "immersive"].includes(String(value));
}

export function placeWithoutCollision(
  preferred: SpatialWindowPosition,
  size: SpatialWindowSize,
  existing: SpatialWindow[],
): SpatialWindowPosition {
  const base = clampPosition(preferred, size);
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  const gap = 18;
  const topSafeArea = Math.min(96, Math.max(12, viewportHeight - size.height - 12));
  const active = existing.filter((item) => !item.collapsed);
  const perimeterCandidates = [12, Math.round((viewportWidth - size.width) / 2), viewportWidth - size.width - 12]
    .flatMap((left) => [topSafeArea, Math.round((viewportHeight - size.height) / 2), viewportHeight - size.height - 18]
      .map((top) => ({ left, top })));
  const neighborCandidates = active.flatMap((item) => [
    { left: item.position.left - size.width - gap, top: item.position.top },
    { left: item.position.left + item.size.width + gap, top: item.position.top },
    { left: item.position.left, top: item.position.top - size.height - gap },
    { left: item.position.left, top: item.position.top + item.size.height + gap },
  ]);
  const candidates = [
    base,
    ...neighborCandidates,
    ...perimeterCandidates,
  ]
    .map((candidate) => clampPosition(candidate, size))
    .filter((candidate, index, all) => all.findIndex((item) => item.left === candidate.left && item.top === candidate.top) === index)
    .sort((left, right) => placementScore(left, size, active, base) - placementScore(right, size, active, base));
  return candidates[0] ?? base;
}

export function buildAnchor(nodeId: string, stagger: number): SpatialWindowAnchor {
  const parity = [...nodeId].reduce((sum, character) => sum + character.charCodeAt(0), 0) % 4;
  const offsets = [
    { x: 26, y: -42 },
    { x: -360, y: -42 },
    { x: 26, y: 34 },
    { x: -360, y: 34 },
  ];
  const offset = offsets[(parity + stagger) % offsets.length];
  return { nodeId, offsetX: offset.x, offsetY: offset.y, enabled: Boolean(nodeId) };
}

export function anchoredPositionFor(
  point: { x: number; y: number },
  anchor: SpatialWindowAnchor,
  size: SpatialWindowSize,
): SpatialWindowPosition {
  const position = clampPosition({ left: point.x + anchor.offsetX, top: point.y + anchor.offsetY }, size);
  if (typeof window === "undefined") return position;
  // The advisor is a user-controlled floating console, not disposable chrome.
  // Node inspectors yield upward when their preferred anchor would cover it.
  const advisorSafeLeft = window.innerWidth - 116;
  const advisorSafeTop = window.innerHeight - 118;
  const overlapsAdvisor = position.left + size.width > advisorSafeLeft
    && position.top + size.height > advisorSafeTop;
  return overlapsAdvisor
    ? clampPosition({ left: position.left, top: advisorSafeTop - size.height - 12 }, size)
    : position;
}

export function anchoredPosition(
  item: SpatialWindow,
  point: { x: number; y: number },
): SpatialWindowPosition {
  if (!item.anchor) return item.position;
  return anchoredPositionFor(point, item.anchor, item.size);
}

export function isWindowKind(value: unknown): value is SpatialWindowKind {
  return ["node", "progress", "agent", "reader", "decisions", "rules", "health", "delivery", "archive", "style", "quality", "strategy", "observatory", "archaeology"].includes(String(value));
}

export function validSize(value: SpatialWindowSize): boolean {
  return Number.isFinite(value.width) && Number.isFinite(value.height) && value.width >= 260 && value.height >= 180;
}

export function validAnchor(value: SpatialWindowAnchor): boolean {
  return Boolean(value.nodeId)
    && Number.isFinite(value.offsetX)
    && Number.isFinite(value.offsetY)
    && typeof value.enabled === "boolean";
}

export function validReaderReturn(value: SpatialWindow["reader_return"]): boolean {
  return Boolean(
    value
    && validSize(value.size)
    && Number.isFinite(value.position.left)
    && Number.isFinite(value.position.top)
    && ["peek", "reading"].includes(String(value.mode)),
  );
}

function placementScore(
  position: SpatialWindowPosition,
  size: SpatialWindowSize,
  existing: SpatialWindow[],
  preferred: SpatialWindowPosition,
): number {
  const collisionPenalty = existing.reduce((total, item) => total + overlapArea(position, size, item), 0);
  const preferredDistance = Math.hypot(position.left - preferred.left, position.top - preferred.top);
  return collisionPenalty * 10_000 + preferredDistance;
}

function overlapArea(
  position: SpatialWindowPosition,
  size: SpatialWindowSize,
  other: SpatialWindow,
): number {
  const gap = 18;
  const horizontal = Math.max(0, Math.min(position.left + size.width + gap, other.position.left + other.size.width) - Math.max(position.left, other.position.left - gap));
  const vertical = Math.max(0, Math.min(position.top + size.height + gap, other.position.top + other.size.height) - Math.max(position.top, other.position.top - gap));
  return horizontal * vertical;
}
