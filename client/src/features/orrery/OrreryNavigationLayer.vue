<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ArrowUpRight, LocateFixed, Map as MapIcon, Search, Tags, X } from "lucide-vue-next";
import {
  minimapPoints,
  nextSpatialNode,
  offscreenBeacons,
  searchNarrativeNodes,
  type SpatialDirection,
} from "@/features/orrery/model/spatialNavigation";
import type { SpatialNarrativeNode, WorldPoint } from "@/types/spatial";

const props = defineProps<{
  nodes: SpatialNarrativeNode[];
  points: Map<string, WorldPoint>;
  anchors: Record<string, { x: number; y: number; visible: boolean; scale: number }>;
  activeNodeId?: string;
}>();
const emit = defineEmits<{
  navigate: [node: SpatialNarrativeNode];
  inspect: [node: SpatialNarrativeNode];
  forcedLabels: [nodeIds: string[]];
  showAllLabels: [enabled: boolean];
}>();

const root = ref<HTMLElement | null>(null);
const searchInput = ref<HTMLInputElement | null>(null);
const query = ref("");
const searchOpen = ref(false);
const mapOpen = ref(true);
const showAll = ref(false);
const keyboardNodeId = ref("");
const size = ref({ width: 0, height: 0 });
let resizeObserver: ResizeObserver | null = null;

const results = computed(() => searchNarrativeNodes(props.nodes, query.value));
const mapPoints = computed(() => minimapPoints(props.nodes, props.points, 164, 106, 9));
const routeMapPoints = computed(() => {
  const chapters = mapPoints.value.filter((point) => point.type === "chapter");
  return chapters.length > 1 ? chapters : mapPoints.value.filter((point) => point.type === "scene");
});
const visibleMapFrame = computed(() => {
  const visibleIds = new Set(Object.entries(props.anchors).filter(([, anchor]) => anchor.visible).map(([nodeId]) => nodeId));
  const visible = mapPoints.value.filter((point) => visibleIds.has(point.node_id));
  if (!visible.length) return null;
  const xs = visible.map((point) => point.x);
  const ys = visible.map((point) => point.y);
  const minX = Math.max(2, Math.min(...xs) - 6);
  const minY = Math.max(2, Math.min(...ys) - 6);
  return {
    x: minX,
    y: minY,
    width: Math.min(160 - minX, Math.max(12, Math.max(...xs) - Math.min(...xs) + 12)),
    height: Math.min(102 - minY, Math.max(12, Math.max(...ys) - Math.min(...ys) + 12)),
  };
});
const beacons = computed(() => offscreenBeacons(props.nodes, props.anchors, size.value.width, size.value.height));

watch(results, (value) => {
  emit("forcedLabels", value.map((node) => node.node_id));
}, { immediate: true });
watch(showAll, (value) => emit("showAllLabels", value), { immediate: true });
watch(() => props.activeNodeId, (value) => {
  if (value) keyboardNodeId.value = value;
});

onMounted(() => {
  if (root.value) {
    resizeObserver = new ResizeObserver(([entry]) => {
      size.value = { width: entry.contentRect.width, height: entry.contentRect.height };
    });
    resizeObserver.observe(root.value);
  }
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  window.removeEventListener("keydown", handleKeydown);
  emit("forcedLabels", []);
  emit("showAllLabels", false);
});

async function openSearch(): Promise<void> {
  searchOpen.value = true;
  await nextTick();
  searchInput.value?.focus();
}

function closeSearch(): void {
  query.value = "";
  searchOpen.value = false;
}

function choose(node: SpatialNarrativeNode, inspect = false): void {
  keyboardNodeId.value = node.node_id;
  if (inspect) emit("inspect", node);
  else emit("navigate", node);
}

function inspectSearchResult(node: SpatialNarrativeNode): void {
  keyboardNodeId.value = node.node_id;
  emit("inspect", node);
  closeSearch();
}

function chooseMapPoint(nodeId: string): void {
  const node = props.nodes.find((item) => item.node_id === nodeId);
  if (node) choose(node);
}

function handleKeydown(event: KeyboardEvent): void {
  const target = event.target instanceof HTMLElement ? event.target : null;
  const isEditable = Boolean(target?.closest("input, textarea, select, [contenteditable='true']"));
  const outsideInstrument = Boolean(target?.closest(".spatial-window, .advisor-dock, .project-band-menu, .relation-lens, .chapter-rail, .character-thread-rail"));
  const interactive = Boolean(target?.closest("button, a, [role='button']"));
  if (outsideInstrument) return;
  if (event.key === "/" && !isEditable && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault();
    void openSearch();
    return;
  }
  if (event.key === "Escape" && searchOpen.value) {
    event.preventDefault();
    closeSearch();
    return;
  }
  if (event.altKey && !event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "l") {
    event.preventDefault();
    showAll.value = !showAll.value;
    return;
  }
  if (event.altKey && !event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "m") {
    event.preventDefault();
    mapOpen.value = !mapOpen.value;
    return;
  }
  if (isEditable || interactive || event.ctrlKey || event.metaKey || event.altKey) return;
  const direction = keyDirection(event.key);
  if (direction) {
    const next = nextSpatialNode(props.nodes, props.points, keyboardNodeId.value || props.activeNodeId || "", direction);
    if (next) {
      choose(next);
      event.preventDefault();
    }
    return;
  }
  if (event.key === "Enter" && keyboardNodeId.value) {
    const node = props.nodes.find((item) => item.node_id === keyboardNodeId.value);
    if (node) {
      emit("inspect", node);
      event.preventDefault();
    }
  }
}

function keyDirection(key: string): SpatialDirection | null {
  if (key === "ArrowLeft") return "left";
  if (key === "ArrowRight") return "right";
  if (key === "ArrowUp") return "up";
  if (key === "ArrowDown") return "down";
  return null;
}

function typeLabel(type: string): string {
  return ({
    chapter: "章节",
    scene: "场景",
    character: "人物",
    branch: "分支",
    review: "审查",
    canon: "设定",
    promise: "承诺",
    "reader-question": "问题",
    task: "任务",
  } as Record<string, string>)[type] || "资料";
}
</script>

<template>
  <div ref="root" class="orrery-navigation-layer" aria-label="叙事空间导航">
    <div class="orrery-search-control" :class="{ expanded: searchOpen }">
      <button
        class="orrery-navigation-icon"
        :aria-expanded="searchOpen"
        title="搜索叙事节点（/）"
        @click="searchOpen ? closeSearch() : openSearch()"
      >
        <X v-if="searchOpen" :size="15" /><Search v-else :size="15" />
      </button>
      <template v-if="searchOpen">
        <input
          ref="searchInput"
          v-model="query"
          type="search"
          placeholder="寻找章节、场景、人物或承诺"
          aria-label="搜索叙事节点"
          @keydown.enter="results[0] && inspectSearchResult(results[0])"
        />
        <span v-if="query">{{ results.length }} 项</span>
      </template>
    </div>

    <div v-if="searchOpen && query" class="orrery-search-results">
      <button v-for="node in results" :key="node.node_id" @click="inspectSearchResult(node)">
        <i :data-type="node.type"></i>
        <span><strong>{{ node.label }}</strong><small>{{ typeLabel(node.type) }} · {{ node.subtitle || node.source_id }}</small></span>
        <LocateFixed :size="13" />
      </button>
      <p v-if="!results.length">没有找到对应的作品节点。</p>
    </div>

    <div class="orrery-navigation-tools">
      <button
        class="orrery-navigation-icon"
        :class="{ active: showAll }"
        :aria-pressed="showAll"
        title="临时显示全部标签（Alt+L）"
        @click="showAll = !showAll"
      >
        <Tags :size="15" />
      </button>
      <button
        class="orrery-navigation-icon"
        :class="{ active: mapOpen }"
        :aria-pressed="mapOpen"
        title="显示或收起叙事小地图（Alt+M）"
        @click="mapOpen = !mapOpen"
      >
        <MapIcon :size="15" />
      </button>
    </div>

    <aside v-if="mapOpen && mapPoints.length" class="orrery-minimap" aria-label="叙事小地图">
      <header><span><MapIcon :size="12" />全书方位</span><small>{{ mapPoints.length }} 个主节点</small></header>
      <svg viewBox="0 0 164 106" role="img" aria-label="全书章节和场景位置">
        <path
          v-if="routeMapPoints.length > 1"
          :d="`M ${routeMapPoints.map((point) => `${point.x},${point.y}`).join(' L ')}`"
          class="minimap-route"
        />
        <rect
          v-if="visibleMapFrame"
          class="minimap-viewport"
          :x="visibleMapFrame.x"
          :y="visibleMapFrame.y"
          :width="visibleMapFrame.width"
          :height="visibleMapFrame.height"
          rx="2"
        />
        <circle
          v-for="point in mapPoints"
          :key="point.node_id"
          class="minimap-node"
          :class="{ active: point.node_id === (keyboardNodeId || activeNodeId), chapter: point.type === 'chapter' }"
          :data-status="point.status"
          :cx="point.x"
          :cy="point.y"
          :r="point.type === 'chapter' ? 2.7 : 1.8"
          tabindex="0"
          role="button"
          @click="chooseMapPoint(point.node_id)"
          @keydown.enter="chooseMapPoint(point.node_id)"
        />
      </svg>
    </aside>

    <button
      v-for="beacon in beacons"
      :key="beacon.node.node_id"
      class="orrery-offscreen-beacon"
      :class="{ urgent: beacon.node.status === 'current' || beacon.node.status === 'blocked' }"
      :style="{ left: `${beacon.x}px`, top: `${beacon.y}px` }"
      :title="`定位：${beacon.node.label}`"
      @click="choose(beacon.node)"
    >
      <ArrowUpRight :size="12" :style="{ transform: `rotate(${beacon.angle - 45}deg)` }" />
      <span>{{ beacon.node.label.slice(0, 8) }}</span>
    </button>
  </div>
</template>
