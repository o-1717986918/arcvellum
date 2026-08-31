import { computed, ref } from "vue";
import { defineStore } from "pinia";
import type { SpatialNarrativeNode, SpatialNodeDetail } from "@/types/spatial";
import type {
  ReaderWindowMode,
  SpatialWindow,
  SpatialWindowAnchor,
  SpatialWindowKind,
  SpatialWindowPosition,
  SpatialWindowSize,
  WorkspaceWindowMode,
} from "@/types/spatialWindows";
import {
  DEFAULT_SIZES,
  anchoredPosition,
  anchoredPositionFor,
  buildAnchor,
  clampPosition,
  clampSize,
  compactSize,
  instrumentPosition,
  isReaderMode,
  isWindowKind,
  placeWithoutCollision,
  readerModeSize,
  validAnchor,
  validReaderReturn,
  validSize,
} from "@/features/orrery/windows/windowGeometry";

const INSTRUMENT_TITLES: Record<Exclude<SpatialWindowKind, "node">, string> = {
  progress: "推进仪表",
  agent: "执行中心",
  reader: "正文长卷",
  decisions: "待定决定",
  rules: "创作规则",
  health: "作品健康",
  delivery: "交付中心",
  archive: "作品档案 IDE",
  style: "文风工作台",
  quality: "审查与质量",
  strategy: "创作策略",
  observatory: "创作现场",
  archaeology: "作品反推",
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
  reader_mode?: ReaderWindowMode;
  reader_return?: SpatialWindow["reader_return"];
  workspace_mode?: WorkspaceWindowMode;
  workspace_return?: SpatialWindow["workspace_return"];
}

const PERSISTENCE_PREFIX = "arcvellum.spatial-window-layout.v1.";
const MAX_EXPANDED_WINDOWS = 12;


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
      if (kind === "reader" && !existing.reader_mode) existing.reader_mode = "peek";
      restore(id);
      constrainToViewport();
      return;
    }
    const readerMode = kind === "reader" ? "peek" : undefined;
    const size = readerMode ? readerModeSize(readerMode) : DEFAULT_SIZES[kind];
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
      reader_mode: readerMode,
      workspace_mode: "float",
    });
    constrainToViewport();
  }

  function setWorkspaceMode(id: string, mode: WorkspaceWindowMode): void {
    const target = windows.value.find((item) => item.id === id);
    if (!target || target.kind === "reader" || target.workspace_mode === mode) return;
    if (mode === "fullscreen") {
      target.workspace_return = { position: { ...target.position }, size: { ...target.size } };
      target.position = { left: 12, top: 12 };
      target.size = fullscreenSize();
    } else if (target.workspace_return) {
      target.position = clampPosition(target.workspace_return.position, target.workspace_return.size);
      target.size = clampSize(target.kind, target.workspace_return.size);
      target.workspace_return = undefined;
    }
    target.workspace_mode = mode;
    target.collapsed = false;
    bringForward(id);
    persist();
  }

  function setReaderMode(mode: ReaderWindowMode): void {
    const target = windows.value.find((item) => item.kind === "reader");
    if (!target || target.reader_mode === mode) return;
    const previous = target.reader_mode || "peek";
    if (mode === "immersive") {
      target.reader_return = {
        position: { ...target.position },
        size: { ...target.size },
        mode: previous === "immersive" ? "reading" : previous,
      };
      target.position = { left: 16, top: 16 };
      target.size = readerModeSize(mode);
    } else if (previous === "immersive" && target.reader_return) {
      const restoredSize = target.reader_return.mode === mode
        ? clampSize("reader", target.reader_return.size)
        : readerModeSize(mode);
      target.position = clampPosition(target.reader_return.position, restoredSize);
      target.size = restoredSize;
      target.reader_return = undefined;
    } else {
      if (target.workspace_mode === "fullscreen") {
        target.size = fullscreenSize();
        target.position = { left: 12, top: 12 };
        persist();
        return;
      }
      target.size = readerModeSize(mode);
      target.position = clampPosition(target.position, target.size);
    }
    target.reader_mode = mode;
    target.collapsed = false;
    bringForward(target.id);
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
      if (target.kind === "reader") {
        target.size = readerModeSize(target.reader_mode || "peek");
      }
      target.position = target.kind === "reader" && target.reader_mode === "immersive"
        ? { left: 16, top: 16 }
        : instrumentPosition(target.kind, target.size, 0);
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

  function constrainToViewport(): void {
    const expanded = windows.value
      .filter((item) => !item.collapsed)
      // Large instruments have fewer valid homes. Place them first, then fit
      // compact windows around them while preserving layer order as a tie-break.
      .sort((left, right) => (right.size.width * right.size.height) - (left.size.width * left.size.height) || right.layer - left.layer);
    if (window.innerWidth <= 760 && expanded.length > 1) {
      const active = [...expanded].sort((left, right) => right.layer - left.layer)[0];
      expanded.forEach((item) => { item.collapsed = item.id !== active.id; });
      persist();
      return;
    }
    if (expanded.length >= 4 && window.innerWidth > 760) {
      tileDenseWindows(expanded);
      persist();
      return;
    }
    const placed: SpatialWindow[] = [];
    expanded.forEach((item) => {
      if (item.kind === "reader" && item.reader_mode === "immersive") {
        item.size = readerModeSize("immersive");
        item.position = { left: 16, top: 16 };
      } else {
        item.size = item.kind === "reader"
          ? readerModeSize(item.reader_mode || "peek")
          : clampSize(item.kind, item.size);
        const preferred = clampPosition(item.position, item.size);
        item.position = item.kind === "node" && item.anchor?.enabled
          ? preferred
          : placeWithoutCollision(preferred, item.size, placed);
      }
      placed.push(item);
    });
    windows.value.filter((item) => item.collapsed).forEach((item) => {
      item.size = clampSize(item.kind, item.size);
      item.position = clampPosition(item.position, item.size);
    });
    persist();
  }

  function tileDenseWindows(items: SpatialWindow[]): void {
    const margin = 12;
    const gap = 18;
    const top = Math.min(96, Math.max(margin, window.innerHeight * 0.12));
    const columnCount = window.innerWidth >= 1080 ? 3 : 2;
    const columnWidth = Math.floor((window.innerWidth - margin * 2 - gap * (columnCount - 1)) / columnCount);
    const columnBottoms = Array.from({ length: columnCount }, () => top);
    items.forEach((item) => {
      if (item.kind === "reader" && item.reader_mode === "immersive") {
        item.size = readerModeSize("immersive");
        item.position = { left: 16, top: 16 };
        return;
      }
      const compact = item.kind === "reader" ? readerModeSize(item.reader_mode || "peek") : compactSize(item.kind);
      item.size = { width: Math.min(compact.width, columnWidth), height: compact.height };
      const column = columnBottoms.indexOf(Math.min(...columnBottoms));
      const nextTop = columnBottoms[column];
      if (nextTop + item.size.height > window.innerHeight - margin) {
        item.collapsed = true;
        return;
      }
      const trackLeft = margin + column * (columnWidth + gap);
      item.position = {
        left: Math.round(trackLeft + (columnWidth - item.size.width) / 2),
        top: Math.round(nextTop),
      };
      columnBottoms[column] = nextTop + item.size.height + gap;
    });
    windows.value.filter((item) => item.collapsed).forEach((item) => {
      item.position = clampPosition(item.position, item.size);
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
        const size = persistedWindowSize(item);
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
          reader_mode: item.kind === "reader"
            ? (isReaderMode(item.reader_mode) ? item.reader_mode : "peek")
            : undefined,
          reader_return: item.kind === "reader" && validReaderReturn(item.reader_return) ? item.reader_return : undefined,
          workspace_mode: item.kind !== "reader" && item.workspace_mode === "fullscreen" ? "fullscreen" : "float",
          workspace_return: item.kind !== "reader" && validWorkspaceReturn(item.workspace_return) ? item.workspace_return : undefined,
        });
      });
      windows.value = restored;
      highestLayer = Math.max(50, ...restored.map((item) => item.layer));
      while (windows.value.filter((item) => !item.collapsed).length > MAX_EXPANDED_WINDOWS) collapseForCapacity();
      if (restored.length) constrainToViewport();
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
      reader_mode: item.reader_mode,
      reader_return: item.reader_return,
      workspace_mode: item.workspace_mode,
      workspace_return: item.workspace_return,
    }));
    localStorage.setItem(persistenceKey, JSON.stringify(payload));
  }

  return { windows: sortedWindows, expandedWindows, minimizedWindows, selectedNodeId, openNode, openInstrument, setReaderMode, setWorkspaceMode, bringForward, updatePosition, updateSize, toggleCollapsed, restore, close, closeActive, toggleActive, resetPosition, resetActive, focusNext, syncNodeAnchors, constrainToViewport, clear, setScope };
});

function fullscreenSize(): SpatialWindowSize {
  return {
    width: Math.max(300, window.innerWidth - 24),
    height: Math.max(260, window.innerHeight - 24),
  };
}

function validWorkspaceReturn(value: SpatialWindow["workspace_return"]): boolean {
  return Boolean(
    value
    && validSize(value.size)
    && Number.isFinite(value.position.left)
    && Number.isFinite(value.position.top),
  );
}

function persistedWindowSize(item: PersistedSpatialWindow): SpatialWindowSize {
  if (item.kind === "reader") {
    const mode = isReaderMode(item.reader_mode) ? item.reader_mode : "peek";
    if (mode !== "reading") return readerModeSize(mode);
    return item.size && validSize(item.size) ? clampSize("reader", item.size) : readerModeSize(mode);
  }
  return item.size && validSize(item.size) ? clampSize(item.kind, item.size) : DEFAULT_SIZES[item.kind];
}
