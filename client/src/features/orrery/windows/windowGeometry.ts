import type {
  ReaderWindowMode,
  SpatialWindow,
  SpatialWindowAnchor,
  SpatialWindowKind,
  SpatialWindowPosition,
  SpatialWindowSize,
} from "@/types/spatialWindows";

export const DEFAULT_SIZES: Record<SpatialWindowKind, SpatialWindowSize> = {
  node: { width: 294, height: 348 },
  progress: { width: 342, height: 438 },
  agent: { width: 368, height: 510 },
  reader: { width: 332, height: 540 },
  decisions: { width: 328, height: 340 },
  rules: { width: 456, height: 600 },
  health: { width: 258, height: 290 },
  delivery: { width: 294, height: 282 },
};

const MIN_SIZES: Record<SpatialWindowKind, SpatialWindowSize> = {
  node: { width: 276, height: 270 },
  progress: { width: 286, height: 316 },
  agent: { width: 304, height: 336 },
  reader: { width: 300, height: 370 },
  decisions: { width: 300, height: 248 },
  rules: { width: 360, height: 430 },
  health: { width: 258, height: 240 },
  delivery: { width: 260, height: 210 },
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

export function instrumentPosition(
  kind: Exclude<SpatialWindowKind, "node">,
  size: SpatialWindowSize,
  offset: number,
): SpatialWindowPosition {
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  const positions: Record<Exclude<SpatialWindowKind, "node">, SpatialWindowPosition> = {
    progress: { left: viewportWidth - size.width - 30, top: 148 },
    agent: { left: viewportWidth - size.width - 42, top: 184 },
    reader: { left: 82, top: 148 },
    decisions: { left: viewportWidth - size.width - 42, top: 196 },
    rules: { left: viewportWidth - size.width - 52, top: 150 },
    health: { left: 26, top: viewportHeight - size.height - 34 },
    delivery: { left: viewportWidth - size.width - 44, top: viewportHeight - size.height - 40 },
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
  const candidates = [
    base,
    { left: base.left - size.width - 28, top: base.top },
    { left: base.left, top: base.top + size.height + 28 },
    { left: base.left - size.width - 28, top: base.top + Math.round(size.height * 0.45) },
    { left: 28, top: viewportHeight - size.height - 34 },
    { left: viewportWidth - size.width - 28, top: 132 },
  ].map((candidate) => clampPosition(candidate, size));
  const active = existing.filter((item) => !item.collapsed);
  return candidates.find((candidate) => active.every((item) => !overlaps(candidate, size, item)))
    ?? clampPosition({ left: base.left - active.length * 26, top: base.top + active.length * 32 }, size);
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
  return clampPosition({ left: point.x + anchor.offsetX, top: point.y + anchor.offsetY }, size);
}

export function anchoredPosition(
  item: SpatialWindow,
  point: { x: number; y: number },
): SpatialWindowPosition {
  if (!item.anchor) return item.position;
  return anchoredPositionFor(point, item.anchor, item.size);
}

export function isWindowKind(value: unknown): value is SpatialWindowKind {
  return ["node", "progress", "agent", "reader", "decisions", "rules", "health", "delivery"].includes(String(value));
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

function overlaps(
  position: SpatialWindowPosition,
  size: SpatialWindowSize,
  other: SpatialWindow,
): boolean {
  const gap = 18;
  return !(
    position.left + size.width + gap <= other.position.left
    || other.position.left + other.size.width + gap <= position.left
    || position.top + size.height + gap <= other.position.top
    || other.position.top + other.size.height + gap <= position.top
  );
}
