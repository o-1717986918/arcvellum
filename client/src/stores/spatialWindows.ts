import { computed, ref } from "vue";
import { defineStore } from "pinia";
import type { SpatialNarrativeNode, SpatialNodeDetail } from "@/types/spatial";
import type { SpatialWindow, SpatialWindowAnchor, SpatialWindowKind, SpatialWindowPosition, SpatialWindowSize } from "@/types/spatialWindows";

const DEFAULT_SIZES: Record<SpatialWindowKind, SpatialWindowSize> = {
  node: { width: 294, height: 348 },
  progress: { width: 300, height: 332 },
  reader: { width: 332, height: 540 },
  decisions: { width: 328, height: 340 },
  rules: { width: 350, height: 440 },
  health: { width: 258, height: 290 },
  delivery: { width: 294, height: 282 },
};

const MIN_SIZES: Record<SpatialWindowKind, SpatialWindowSize> = {
  node: { width: 276, height: 270 },
  progress: { width: 282, height: 280 },
  reader: { width: 300, height: 370 },
  decisions: { width: 300, height: 248 },
  rules: { width: 320, height: 350 },
  health: { width: 258, height: 240 },
  delivery: { width: 260, height: 210 },
};

const INSTRUMENT_TITLES: Record<Exclude<SpatialWindowKind, "node">, string> = {
  progress: "推进仪表",
  reader: "正文长卷",
  decisions: "待定决定",
  rules: "创作规则",
  health: "作品健康",
  delivery: "交付中心",
};

interface PersistedSpatialWindow {
  id: string;
  kind: SpatialWindowKind;
  position: SpatialWindowPosition;
  size?: SpatialWindowSize;
  collapsed: boolean;
  layer: number;
  node_id?: string;
  anchor?: SpatialWindowAnchor;
}

const PERSISTENCE_PREFIX = "arcvellum.spatial-window-layout.v1.";
const MAX_EXPANDED_WINDOWS = 12;

function clampPosition(position: SpatialWindowPosition, size: SpatialWindowSize): SpatialWindowPosition {
  const margin = 12;
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  return {
    left: Math.min(Math.max(margin, position.left), Math.max(margin, viewportWidth - size.width - margin)),
    top: Math.min(Math.max(margin, position.top), Math.max(margin, viewportHeight - size.height - margin)),
  };
}

function clampSize(kind: SpatialWindowKind, size: SpatialWindowSize): SpatialWindowSize {
  const minimum = MIN_SIZES[kind];
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  return {
    width: Math.round(Math.min(Math.max(minimum.width, size.width), Math.max(minimum.width, viewportWidth - 24))),
    height: Math.round(Math.min(Math.max(minimum.height, size.height), Math.max(minimum.height, viewportHeight - 24))),
  };
}

function instrumentPosition(kind: Exclude<SpatialWindowKind, "node">, size: SpatialWindowSize, offset: number): SpatialWindowPosition {
  const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  const positions: Record<Exclude<SpatialWindowKind, "node">, SpatialWindowPosition> = {
    progress: { left: viewportWidth - size.width - 30, top: 148 },
    reader: { left: 82, top: 148 },
    decisions: { left: viewportWidth - size.width - 42, top: 196 },
    rules: { left: viewportWidth - size.width - 52, top: 150 },
    health: { left: 26, top: viewportHeight - size.height - 34 },
    delivery: { left: viewportWidth - size.width - 44, top: viewportHeight - size.height - 40 },
  };
  return clampPosition({ left: positions[kind].left - offset * 12, top: positions[kind].top + offset * 12 }, size);
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

function placeWithoutCollision(
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

export const useSpatialWindowsStore = defineStore("spatialWindows", () => {
  const windows = ref<SpatialWindow[]>([]);
  const selectedNodeId = ref("");
  let highestLayer = 50;
  let persistenceKey = "";
  const nodeAnchors = new Map<string, { x: number; y: number; visible: boolean }>();

  const sortedWindows = computed(() => [...windows.value].sort((left, right) => left.layer - right.layer));
  const expandedWindows = computed(() => sortedWindows.value.filter((item) => !item.collapsed));
  const minimizedWindows = computed(() => sortedWindows.value.filter((item) => item.collapsed));

  function collapseForCapacity(exceptId = ""): void {
    if (windows.value.filter((item) => !item.collapsed).length < MAX_EXPANDED_WINDOWS) return;
    const candidate = windows.value
      .filter((item) => !item.collapsed && item.id !== exceptId)
      .sort((left, right) => left.layer - right.layer)[0];
    if (candidate) candidate.collapsed = true;
  }

  function bringForward(id: string): void {
    const target = windows.value.find((item) => item.id === id);
    if (target) {
      target.layer = ++highestLayer;
      persist();
    }
  }

  function openNode(node: SpatialNarrativeNode, detail: SpatialNodeDetail | null, anchor?: { x: number; y: number }): void {
    const id = `node:${node.node_id}`;
    selectedNodeId.value = node.node_id;
    const existing = windows.value.find((item) => item.id === id);
    if (existing) {
      existing.node = node;
      existing.detail = detail;
      restore(id);
      if (anchor && existing.anchor?.enabled) {
        nodeAnchors.set(node.node_id, { ...anchor, visible: true });
        existing.position = anchoredPosition(existing, anchor);
      }
      bringForward(id);
      return;
    }
    const size = DEFAULT_SIZES.node;
    const stagger = windows.value.filter((item) => item.kind === "node").length % 4;
    const anchorSpec = anchor ? buildAnchor(node.node_id, stagger) : undefined;
    if (anchor) nodeAnchors.set(node.node_id, { ...anchor, visible: true });
    const base = anchor && anchorSpec
      ? anchoredPositionFor(anchor, anchorSpec, size)
      : { left: 90 + stagger * 26, top: 154 + stagger * 22 };
    const item: SpatialWindow = {
      id,
      kind: "node",
      title: node.label,
      position: placeWithoutCollision(base, size, windows.value),
      size,
      layer: ++highestLayer,
      collapsed: false,
      node,
      detail,
      anchor: anchorSpec,
    };
    collapseForCapacity(id);
    item.position = placeWithoutCollision(base, size, windows.value);
    windows.value.push(item);
    persist();
  }

  function openInstrument(kind: Exclude<SpatialWindowKind, "node">): void {
    const id = `instrument:${kind}`;
    const existing = windows.value.find((item) => item.id === id);
    if (existing) {
      restore(id);
      return;
    }
    const size = DEFAULT_SIZES[kind];
    const preferred = instrumentPosition(kind, size, windows.value.filter((item) => item.kind === kind).length);
    collapseForCapacity(id);
    windows.value.push({
      id,
      kind,
      title: INSTRUMENT_TITLES[kind],
      position: placeWithoutCollision(preferred, size, windows.value),
      size,
      layer: ++highestLayer,
      collapsed: false,
    });
    persist();
  }

  function updatePosition(id: string, position: SpatialWindowPosition): void {
    const target = windows.value.find((item) => item.id === id);
    if (target) {
      target.position = clampPosition(position, target.size);
      if (target.anchor) target.anchor.enabled = false;
      persist();
    }
  }

  function updateSize(id: string, size: SpatialWindowSize): void {
    const target = windows.value.find((item) => item.id === id);
    if (!target) return;
    target.size = clampSize(target.kind, size);
    target.position = clampPosition(target.position, target.size);
    persist();
  }

  function toggleCollapsed(id: string): void {
    const target = windows.value.find((item) => item.id === id);
    if (target) {
      if (target.collapsed) {
        restore(id);
        return;
      }
      target.collapsed = true;
      persist();
    }
  }

  function restore(id: string): void {
    const target = windows.value.find((item) => item.id === id);
    if (!target) return;
    collapseForCapacity(id);
    target.collapsed = false;
    bringForward(id);
  }

  function close(id: string): void {
    const closing = windows.value.find((item) => item.id === id);
    if (closing?.node?.node_id === selectedNodeId.value) selectedNodeId.value = "";
    windows.value = windows.value.filter((item) => item.id !== id);
    persist();
  }

  function activeWindow(): SpatialWindow | undefined {
    return [...windows.value].sort((left, right) => right.layer - left.layer)[0];
  }

  function closeActive(): void {
    const active = activeWindow();
    if (active) close(active.id);
  }

  function toggleActive(): void {
    const active = activeWindow();
    if (active) toggleCollapsed(active.id);
  }

  function resetActive(): void {
    const active = activeWindow();
    if (active) resetPosition(active.id);
  }

  function focusNext(): string {
    const ordered = [...windows.value].sort((left, right) => right.layer - left.layer);
    if (!ordered.length) return "";
    const current = ordered[0];
    const next = ordered[1] || current;
    bringForward(next.id);
    return next.id;
  }

  function resetPosition(id: string): void {
    const target = windows.value.find((item) => item.id === id);
    if (!target) return;
    if (target.kind === "node") {
      const anchor = target.anchor || buildAnchor(target.node?.node_id || "", 0);
      target.anchor = { ...anchor, enabled: Boolean(anchor.nodeId) };
      const point = nodeAnchors.get(anchor.nodeId);
      target.position = point ? anchoredPosition(target, point) : clampPosition({ left: 92, top: 156 }, target.size);
    } else {
      target.position = instrumentPosition(target.kind, target.size, 0);
    }
    persist();
  }

  function syncNodeAnchors(anchors: Record<string, { x: number; y: number; visible: boolean }>): void {
    Object.entries(anchors).forEach(([nodeId, point]) => nodeAnchors.set(nodeId, point));
    windows.value.forEach((item) => {
      if (item.kind !== "node" || !item.anchor?.enabled || item.collapsed) return;
      const point = nodeAnchors.get(item.anchor.nodeId);
      if (!point) return;
      // When a node leaves the viewport, clamp the attached instrument at the
      // edge instead of teleporting it away. Dragging takes ownership back.
      item.position = anchoredPosition(item, point);
    });
  }

  function clear(persistCurrent = false): void {
    windows.value = [];
    selectedNodeId.value = "";
    nodeAnchors.clear();
    if (persistCurrent) persist();
  }

  function setScope(scope: string, nodes: SpatialNarrativeNode[]): void {
    if (!scope || scope === persistenceKey) return;
    persistenceKey = `${PERSISTENCE_PREFIX}${encodeURIComponent(scope)}`;
    windows.value = [];
    selectedNodeId.value = "";
    highestLayer = 50;
    try {
      const saved = JSON.parse(localStorage.getItem(persistenceKey) || "[]") as PersistedSpatialWindow[];
      if (!Array.isArray(saved)) return;
      const nodeById = new Map(nodes.map((node) => [node.node_id, node]));
      const restored: SpatialWindow[] = [];
      saved.forEach((item) => {
        if (!isWindowKind(item.kind)) return [];
        const size = item.size && validSize(item.size) ? clampSize(item.kind, item.size) : DEFAULT_SIZES[item.kind];
        if (item.kind === "node") {
          const node = nodeById.get(String(item.node_id || ""));
          if (!node) return [];
          restored.push({
            id: `node:${node.node_id}`,
            kind: "node" as const,
            title: node.label,
            position: clampPosition(item.position, size),
            size,
            layer: Math.max(51, Number(item.layer) || 51),
            collapsed: Boolean(item.collapsed),
            node,
            detail: null,
            anchor: item.anchor && validAnchor(item.anchor) ? item.anchor : undefined,
          });
          return;
        }
        restored.push({
          id: `instrument:${item.kind}`,
          kind: item.kind,
          title: INSTRUMENT_TITLES[item.kind],
          position: clampPosition(item.position, size),
          size,
          layer: Math.max(51, Number(item.layer) || 51),
          collapsed: Boolean(item.collapsed),
        });
      });
      windows.value = restored;
      highestLayer = Math.max(50, ...restored.map((item) => item.layer));
      while (windows.value.filter((item) => !item.collapsed).length > MAX_EXPANDED_WINDOWS) collapseForCapacity();
      if (restored.length) persist();
    } catch {
      localStorage.removeItem(persistenceKey);
    }
  }

  function persist(): void {
    if (!persistenceKey) return;
    const payload: PersistedSpatialWindow[] = windows.value.map((item) => ({
      id: item.id,
      kind: item.kind,
      position: item.position,
      size: item.size,
      collapsed: item.collapsed,
      layer: item.layer,
      node_id: item.node?.node_id,
      anchor: item.anchor,
    }));
    localStorage.setItem(persistenceKey, JSON.stringify(payload));
  }

  return { windows: sortedWindows, expandedWindows, minimizedWindows, selectedNodeId, openNode, openInstrument, bringForward, updatePosition, updateSize, toggleCollapsed, restore, close, closeActive, toggleActive, resetPosition, resetActive, focusNext, syncNodeAnchors, clear, setScope };
});

function buildAnchor(nodeId: string, stagger: number): SpatialWindowAnchor {
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

function anchoredPositionFor(
  point: { x: number; y: number },
  anchor: SpatialWindowAnchor,
  size: SpatialWindowSize,
): SpatialWindowPosition {
  return clampPosition({ left: point.x + anchor.offsetX, top: point.y + anchor.offsetY }, size);
}

function anchoredPosition(item: SpatialWindow, point: { x: number; y: number }): SpatialWindowPosition {
  if (!item.anchor) return item.position;
  return anchoredPositionFor(point, item.anchor, item.size);
}

function isWindowKind(value: unknown): value is SpatialWindowKind {
  return ["node", "progress", "reader", "decisions", "rules", "health", "delivery"].includes(String(value));
}

function validSize(value: SpatialWindowSize): boolean {
  return Number.isFinite(value.width) && Number.isFinite(value.height) && value.width >= 260 && value.height >= 180;
}

function validAnchor(value: SpatialWindowAnchor): boolean {
  return Boolean(value.nodeId)
    && Number.isFinite(value.offsetX)
    && Number.isFinite(value.offsetY)
    && typeof value.enabled === "boolean";
}
